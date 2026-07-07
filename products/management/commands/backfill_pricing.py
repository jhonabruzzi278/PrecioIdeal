from django.core.management.base import BaseCommand

from products.models import Product


class Command(BaseCommand):
    help = "Recalcula descuentos de todos los productos Knasta"

    def handle(self, *args, **options):
        updated = 0
        with_discount = 0

        for product in Product.objects.iterator():
            product.sync_pricing_fields(save=True)
            updated += 1
            if product.has_discount:
                with_discount += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{updated} productos actualizados, {with_discount} con descuento."
            )
        )
