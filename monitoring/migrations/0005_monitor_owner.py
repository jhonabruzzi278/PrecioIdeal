from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def assign_existing_monitors_to_first_superuser(apps, schema_editor):
    """Backfill owner on monitors created before multi-tenancy existed.

    Assigns every ownerless monitor to the first superuser (by pk). On a fresh
    database there are no monitors and/or no superuser, so this is a no-op.
    """
    Monitor = apps.get_model("monitoring", "Monitor")
    User = apps.get_model(settings.AUTH_USER_MODEL)

    orphan_monitors = Monitor.objects.filter(owner__isnull=True)
    if not orphan_monitors.exists():
        return

    superuser = User.objects.filter(is_superuser=True).order_by("pk").first()
    if superuser is None:
        return

    orphan_monitors.update(owner=superuser)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("monitoring", "0004_knasta_migration"),
    ]

    operations = [
        migrations.AddField(
            model_name="monitor",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="monitors",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(
            assign_existing_monitors_to_first_superuser,
            migrations.RunPython.noop,
        ),
    ]
