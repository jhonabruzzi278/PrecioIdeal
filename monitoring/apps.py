from django.apps import AppConfig


class MonitoringConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "monitoring"

    def ready(self):
        import os
        import sys

        if "runserver" not in sys.argv or os.environ.get("RUN_MAIN") != "true":
            return

        from monitoring.scheduler import start_scheduler

        start_scheduler()
