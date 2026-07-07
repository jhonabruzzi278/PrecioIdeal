import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from monitoring.forms import MonitorForm, UpdateScheduleForm
from monitoring.models import Monitor, UpdateReport, UpdateReportEntry, UpdateSchedule
from monitoring.scheduler import start_update_async, sync_scheduler
from billing.services.access import can_create_monitor, has_pro_access
from products.services.knasta import KnastaScraper, get_flat_categories
from products.services.persistence import save_products

logger = logging.getLogger(__name__)


def _categories_for_picker():
    return get_flat_categories()


def _categories_json(categories):
    items = []
    for item in categories:
        if not item.get("slug"):
            continue
        name = item.get("category_name", "")
        path = item.get("long_path", "")
        slug = item["slug"]
        items.append(
            {
                "value": f"{item['category_id']}|{slug}",
                "name": name,
                "path": path,
                "slug": slug,
            }
        )
    return items


@login_required
def monitor_list(request):
    monitors = Monitor.objects.filter(owner=request.user)
    schedule = UpdateSchedule.get_solo()
    return render(
        request,
        "monitoring/monitor_list.html",
        {"monitors": monitors, "schedule": schedule},
    )


@login_required
def monitor_create(request):
    if not can_create_monitor(request.user):
        messages.warning(
            request,
            "Tu plan no permite crear más monitores. Renueva tu suscripción Pro "
            "para seguir monitoreando categorías.",
        )
        return redirect("monitor_list")

    categories = _categories_for_picker()
    categories_data = _categories_json(categories)
    if request.method == "POST":
        form = MonitorForm(request.POST, categories=categories)
        if form.is_valid():
            monitor = form.save(commit=False)
            monitor.owner = request.user
            monitor.save()
            try:
                scraper = KnastaScraper()
                products = scraper.scrape_category(monitor.category_slug)
                stats = save_products(products, monitor_name=monitor.name)
                monitor.last_execution = timezone.now()
                monitor.save(update_fields=["last_execution"])
                messages.success(
                    request,
                    f"Monitor creado. {stats['created']} productos nuevos, "
                    f"{stats['updated']} actualizados.",
                )
            except Exception as exc:
                logger.exception("Error al scrapear categoría Knasta")
                messages.warning(
                    request,
                    f"Monitor creado, pero hubo un error al extraer productos: {exc}",
                )
            return redirect("monitor_list")
    else:
        form = MonitorForm(categories=categories)

    return render(
        request,
        "monitoring/monitor_form.html",
        {
            "form": form,
            "categories_json": json.dumps(categories_data, ensure_ascii=False),
        },
    )


@login_required
@require_POST
def update_prices(request):
    if not has_pro_access(request.user):
        messages.warning(
            request,
            "Las actualizaciones manuales requieren una suscripción Pro activa.",
        )
        return redirect(request.POST.get("next", "/"))

    if not Monitor.objects.filter(active=True).exists():
        messages.warning(request, "No hay monitores activos.")
        return redirect(request.POST.get("next", "/"))

    if UpdateReport.objects.filter(
        status__in=[UpdateReport.STATUS_RUNNING, UpdateReport.STATUS_PENDING]
    ).exists():
        messages.warning(request, "Ya hay una actualización en curso.")
        running = UpdateReport.objects.filter(
            status__in=[UpdateReport.STATUS_RUNNING, UpdateReport.STATUS_PENDING]
        ).first()
        return redirect("report_detail", pk=running.pk)

    report = UpdateReport.objects.create(
        status=UpdateReport.STATUS_PENDING,
        trigger=UpdateReport.TRIGGER_MANUAL,
        current_step="Iniciando actualización...",
    )
    start_update_async(report.pk)
    return redirect("report_detail", pk=report.pk)


@login_required
def report_list(request):
    reports = (
        UpdateReport.objects.annotate(
            price_changes_count=Count(
                "entries",
                filter=Q(entries__entry_type=UpdateReportEntry.ENTRY_PRICE),
            )
        )[:50]
    )
    schedule = UpdateSchedule.get_solo()
    return render(
        request,
        "monitoring/report_list.html",
        {"reports": reports, "schedule": schedule},
    )


@login_required
def report_detail(request, pk):
    report = get_object_or_404(UpdateReport, pk=pk)
    if not report.is_finished:
        return render(request, "monitoring/report_loading.html", {"report": report})

    new_products = report.entries.filter(entry_type=UpdateReportEntry.ENTRY_NEW)
    price_changes = report.entries.filter(entry_type=UpdateReportEntry.ENTRY_PRICE)
    price_changes_count = price_changes.count()
    unchanged_count = max(0, report.products_updated - price_changes_count)

    top_changes = price_changes[:12]
    chart_labels = [entry.product_name[:35] for entry in top_changes]
    chart_old_prices = [entry.old_price or 0 for entry in top_changes]
    chart_new_prices = [entry.new_price or 0 for entry in top_changes]

    decreases = sum(
        1 for entry in price_changes if entry.price_diff is not None and entry.price_diff < 0
    )
    increases = sum(
        1 for entry in price_changes if entry.price_diff is not None and entry.price_diff > 0
    )

    context = {
        "report": report,
        "new_products": new_products,
        "price_changes": price_changes,
        "price_changes_count": price_changes_count,
        "unchanged_count": unchanged_count,
        "decreases": decreases,
        "increases": increases,
        "chart_labels": json.dumps(chart_labels, ensure_ascii=False),
        "chart_old_prices": json.dumps(chart_old_prices),
        "chart_new_prices": json.dumps(chart_new_prices),
        "summary_chart_data": json.dumps(
            [
                report.products_created,
                price_changes_count,
                unchanged_count,
            ]
        ),
    }
    return render(request, "monitoring/report_detail.html", context)


@login_required
def report_status(request, pk):
    report = get_object_or_404(UpdateReport, pk=pk)
    return JsonResponse(
        {
            "status": report.status,
            "current_step": report.current_step,
            "progress_current": report.progress_current,
            "progress_total": report.progress_total,
            "progress_percent": report.progress_percent,
            "is_finished": report.is_finished,
            "redirect_url": f"/reports/{report.pk}/",
        }
    )


@login_required
def schedule_settings(request):
    schedule = UpdateSchedule.get_solo()

    if request.method == "POST":
        form = UpdateScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            form.save()
            sync_scheduler()
            messages.success(request, "Programación de actualización guardada.")
            return redirect("schedule_settings")
    else:
        form = UpdateScheduleForm(instance=schedule)

    return render(
        request,
        "monitoring/schedule_settings.html",
        {"form": form, "schedule": schedule},
    )
