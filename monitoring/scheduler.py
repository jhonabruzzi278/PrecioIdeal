import logging
import threading

from django.db import connection
from django.utils import timezone

logger = logging.getLogger(__name__)

_scheduler = None


def _run_in_background(report_id, update_schedule=False):
    from monitoring.models import UpdateSchedule
    from monitoring.services.update import run_update_report

    try:
        run_update_report(report_id)
        if update_schedule:
            schedule = UpdateSchedule.get_solo()
            schedule.last_run = timezone.now()
            schedule.save(update_fields=["last_run"])
    except Exception:
        logger.exception("Error en actualización en segundo plano")
    finally:
        connection.close()


def start_update_async(report_id, update_schedule=False):
    thread = threading.Thread(
        target=_run_in_background,
        args=(report_id, update_schedule),
        daemon=True,
    )
    thread.start()


def run_scheduled_update():
    from monitoring.models import UpdateReport

    if UpdateReport.objects.filter(status=UpdateReport.STATUS_RUNNING).exists():
        logger.info("Actualización programada omitida: ya hay una en ejecución.")
        return

    report = UpdateReport.objects.create(
        status=UpdateReport.STATUS_PENDING,
        trigger=UpdateReport.TRIGGER_SCHEDULED,
        current_step="Iniciando actualización programada...",
    )
    start_update_async(report.pk, update_schedule=True)
    logger.info("Actualización programada iniciada (informe #%s)", report.pk)


def sync_scheduler():
    from apscheduler.schedulers.background import BackgroundScheduler

    from monitoring.models import UpdateSchedule

    global _scheduler

    schedule = UpdateSchedule.get_solo()

    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="America/Santiago")
        _scheduler.start()

    if _scheduler.get_job("price_update"):
        _scheduler.remove_job("price_update")

    if schedule.enabled:
        _scheduler.add_job(
            run_scheduled_update,
            trigger="interval",
            hours=schedule.interval_hours,
            id="price_update",
            replace_existing=True,
        )
        logger.info("Scheduler activo: cada %s horas", schedule.interval_hours)
    else:
        logger.info("Scheduler desactivado")


def start_scheduler():
    try:
        sync_scheduler()
    except Exception:
        logger.exception("No se pudo iniciar el scheduler")
