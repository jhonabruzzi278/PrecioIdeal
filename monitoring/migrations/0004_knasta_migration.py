from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("monitoring", "0003_updatereportentry_discount_amount_and_more"),
        ("products", "0003_knasta_migration"),
    ]

    operations = [
        migrations.RemoveField(model_name="monitor", name="collection_url"),
        migrations.AddField(
            model_name="monitor",
            name="category_id",
            field=models.CharField(default="", max_length=50),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="monitor",
            name="category_slug",
            field=models.CharField(default="", max_length=500),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="monitor",
            name="category_name",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.RemoveField(model_name="updatereportentry", name="sku_id"),
        migrations.AddField(
            model_name="updatereportentry",
            name="kid",
            field=models.CharField(default="", max_length=120),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="updatereportentry",
            name="retail",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
