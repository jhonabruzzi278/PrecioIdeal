import logging

from django.utils import timezone

from monitoring.models import Monitor, UpdateReport, UpdateReportEntry
from products.services.knasta import KnastaScraper
from products.services.persistence import save_products

logger = logging.getLogger(__name__)


def _set_report_step(report, step, current=0, total=0):
    report.current_step = step
    report.progress_current = current
    report.progress_total = total
    report.save(update_fields=["current_step", "progress_current", "progress_total"])


def _save_report_entries(report, changes):
    entries = [
        UpdateReportEntry(
            report=report,
            entry_type=change["entry_type"],
            product=change["product"],
            product_name=change["product_name"],
            kid=change["kid"],
            brand=change["brand"],
            retail=change.get("retail", ""),
            image_url=change["image_url"],
            monitor_name=change["monitor_name"],
            old_price=change["old_price"],
            new_price=change["new_price"],
            discount_percent=change.get("discount_percent"),
            discount_amount=change.get("discount_amount"),
        )
        for change in changes
    ]
    UpdateReportEntry.objects.bulk_create(entries)


def run_update_report(report_id):
    report = UpdateReport.objects.get(pk=report_id)
    report.status = UpdateReport.STATUS_RUNNING
    report.save(update_fields=["status"])

    monitors = list(Monitor.objects.filter(active=True))
    if not monitors:
        report.status = UpdateReport.STATUS_FAILED
        report.current_step = "No hay monitores activos."
        report.finished_at = timezone.now()
        report.save()
        return report

    scraper = KnastaScraper()
    errors = []

    for index, monitor in enumerate(monitors, start=1):
        _set_report_step(
            report,
            f"Preparando monitor {monitor.name} ({index}/{len(monitors)})...",
            index - 1,
            len(monitors),
        )
        try:

            def progress_callback(page, total_pages, label):
                _set_report_step(
                    report,
                    f"{monitor.name}: {label}",
                    page,
                    total_pages,
                )

            products = scraper.scrape_category(
                monitor.category_slug,
                progress_callback=progress_callback,
            )
            _set_report_step(
                report,
                f"Guardando {len(products)} productos de {monitor.name}...",
                len(monitors),
                len(monitors),
            )
            stats = save_products(products, monitor_name=monitor.name)
            _save_report_entries(report, stats["changes"])

            monitor.last_execution = timezone.now()
            monitor.save(update_fields=["last_execution"])

            report.monitors_processed += 1
            report.products_scraped += len(products)
            report.products_created += stats["created"]
            report.products_updated += stats["updated"]
            report.price_changes += stats["price_changes"]
            report.save(
                update_fields=[
                    "monitors_processed",
                    "products_scraped",
                    "products_created",
                    "products_updated",
                    "price_changes",
                ]
            )
        except Exception as exc:
            logger.exception("Error procesando monitor %s", monitor.name)
            errors.append(f"{monitor.name}: {exc}")

    report.finished_at = timezone.now()
    report.error_log = "\n".join(errors)
    if errors and report.monitors_processed == 0:
        report.status = UpdateReport.STATUS_FAILED
        report.current_step = "Actualización fallida."
    elif errors:
        report.status = UpdateReport.STATUS_PARTIAL
        report.current_step = "Actualización completada con errores."
    else:
        report.status = UpdateReport.STATUS_COMPLETED
        report.current_step = "Actualización completada."
    report.progress_current = report.progress_total or 1
    report.save()
    return report


def update_all_prices(report=None):
    if report is None:
        report = UpdateReport.objects.create(
            status=UpdateReport.STATUS_RUNNING,
            trigger=UpdateReport.TRIGGER_MANUAL,
            current_step="Iniciando actualización...",
        )
    run_update_report(report.pk)
    report.refresh_from_db()
    return {
        "report_id": report.pk,
        "monitors_processed": report.monitors_processed,
        "total_created": report.products_created,
        "total_updated": report.products_updated,
        "total_history": report.price_changes,
        "errors": [
            {"name": line.split(":")[0], "error": line}
            for line in report.error_log.splitlines()
            if line
        ],
    }
