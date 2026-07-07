"""Seed the Free and Pro plans.

Free is the lapsed/limited tier (no monitoring); Pro is the full demo/paid tier.
Idempotent via update_or_create so re-running on an existing DB is safe.
"""

from django.db import migrations

FREE = {
    "slug": "free",
    "name": "Free",
    "price_clp": 0,
    "max_active_monitors": 0,
    "can_create_monitors": False,
    "can_run_manual_update": False,
    "can_receive_price_alerts": False,
    "can_export": False,
    "is_pro": False,
}

PRO = {
    "slug": "pro",
    "name": "Pro",
    "price_clp": 9990,
    "max_active_monitors": 50,
    "can_create_monitors": True,
    "can_run_manual_update": True,
    "can_receive_price_alerts": True,
    "can_export": True,
    "is_pro": True,
}


def seed_plans(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    for data in (FREE, PRO):
        Plan.objects.update_or_create(slug=data["slug"], defaults=data)


def unseed_plans(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    Plan.objects.filter(slug__in=[FREE["slug"], PRO["slug"]]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_plans, unseed_plans),
    ]
