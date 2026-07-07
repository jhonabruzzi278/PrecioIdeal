from monitoring.models import Monitor
from products.models import PriceHistory, Product


def clear_scraped_data():
    history_deleted, _ = PriceHistory.objects.all().delete()
    products_deleted, _ = Product.objects.all().delete()
    monitors_deleted, _ = Monitor.objects.all().delete()

    return {
        "history": history_deleted,
        "products": products_deleted,
        "monitors": monitors_deleted,
    }
