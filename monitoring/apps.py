from django.apps import AppConfig


class MonitoringConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "monitoring"

    def ready(self):
        import os
        import sys

        argv = sys.argv
        is_manage_command = bool(argv) and argv[0].endswith("manage.py")
        if is_manage_command:
            # Any other manage.py command (migrate, shell, test, ...) also
            # triggers ready() — only run under the dev server, and only once
            # per reload (Django's autoreloader forks a second process).
            if "runserver" not in argv or os.environ.get("RUN_MAIN") != "true":
                return
        # Otherwise the app was loaded by a WSGI server (gunicorn in
        # production) — start the scheduler there too. Requires a single
        # worker process so only one background scheduler thread ever runs.

        from monitoring.scheduler import start_scheduler

        start_scheduler()
