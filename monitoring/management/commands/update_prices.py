import logging

from django.core.management.base import BaseCommand

from monitoring.models import Monitor, UpdateReport
from monitoring.services.update import update_all_prices

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Actualiza precios de todos los monitores activos"

    def handle(self, *args, **options):
        if not Monitor.objects.filter(active=True).exists():
            self.stdout.write(self.style.WARNING("No hay monitores activos."))
            return

        results = update_all_prices()
        report = UpdateReport.objects.get(pk=results["report_id"])

        self.stdout.write(self.style.SUCCESS(f"Informe #{report.pk} — {report.get_status_display()}"))
        self.stdout.write(
            f"  - {report.products_scraped} productos | "
            f"{report.products_created} nuevos | "
            f"{report.products_updated} actualizados | "
            f"{report.price_changes} cambios de precio"
        )

        for line in report.error_log.splitlines():
            if line:
                self.stdout.write(self.style.ERROR(f"  - {line}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nResumen: {report.products_created} creados, "
                f"{report.products_updated} actualizados, "
                f"{report.price_changes} cambios de precio."
            )
        )
