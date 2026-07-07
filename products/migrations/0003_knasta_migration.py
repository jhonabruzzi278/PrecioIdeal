from django.db import migrations, models


def wipe_scraped_data(apps, schema_editor):
    UpdateReportEntry = apps.get_model("monitoring", "UpdateReportEntry")
    UpdateReport = apps.get_model("monitoring", "UpdateReport")
    Monitor = apps.get_model("monitoring", "Monitor")
    PriceHistory = apps.get_model("products", "PriceHistory")
    Product = apps.get_model("products", "Product")

    UpdateReportEntry.objects.all().delete()
    UpdateReport.objects.all().delete()
    Monitor.objects.all().delete()
    PriceHistory.objects.all().delete()
    Product.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0002_product_discount_amount_product_discount_percent_and_more"),
        ("monitoring", "0003_updatereportentry_discount_amount_and_more"),
    ]

    operations = [
        migrations.RunPython(wipe_scraped_data, migrations.RunPython.noop),
        migrations.RemoveField(model_name="product", name="sku_id"),
        migrations.RemoveField(model_name="product", name="price_cmr"),
        migrations.RemoveField(model_name="product", name="price_event"),
        migrations.RemoveField(model_name="product", name="price_normal"),
        migrations.AddField(
            model_name="product",
            name="kid",
            field=models.CharField(default="", max_length=120, unique=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="product",
            name="retail",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="product",
            name="price_card",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="product",
            name="reference_price",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="product",
            name="best_variation_price",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="product",
            name="is_best_price",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="product",
            name="product_id",
            field=models.CharField(max_length=80),
        ),
        migrations.AlterField(
            model_name="product",
            name="source",
            field=models.CharField(default="knasta", max_length=50),
        ),
    ]
