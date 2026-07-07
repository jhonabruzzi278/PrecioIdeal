"""Expire lapsed subscriptions and deactivate their monitors.

A subscription is *lapsed* when it is still in ``trialing`` or ``active`` but
its deadline (trial end / paid period end) has passed. Such subscriptions are
moved to ``expired`` and the owner's monitors are deactivated — never deleted.
Historical catalog and price data remain globally accessible.

Run on a schedule (cron / scheduled task):

    python manage.py expire_subscriptions
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from billing.models import Subscription


class Command(BaseCommand):
    help = "Marca como vencidas las suscripciones expiradas y desactiva sus monitores."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostrar qué se haría sin guardar cambios.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        now = timezone.now()

        candidates = Subscription.objects.filter(
            status__in=Subscription.PRO_ACCESS_STATUSES
        ).select_related("user")

        lapsed = [sub for sub in candidates if sub.is_lapsed]

        if not lapsed:
            self.stdout.write(self.style.SUCCESS("No hay suscripciones vencidas."))
            return

        expired_count = 0
        deactivated_count = 0

        for sub in lapsed:
            monitors = sub.user.monitors.filter(active=True)
            count = monitors.count()
            label = (
                f"{sub.user} — {sub.plan} (vence {sub.access_until:%Y-%m-%d %H:%M})"
            )

            if dry_run:
                self.stdout.write(
                    f"[dry-run] Vencería: {label} | {count} monitores se desactivarían"
                )
                expired_count += 1
                deactivated_count += count
                continue

            with transaction.atomic():
                deactivated_count += monitors.update(active=False)
                sub.status = Subscription.STATUS_EXPIRED
                sub.save(update_fields=["status", "updated_at"])
            expired_count += 1
            self.stdout.write(f"Vencida: {label} | {count} monitores desactivados")

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}{expired_count} suscripciones vencidas, "
                f"{deactivated_count} monitores desactivados."
            )
        )
