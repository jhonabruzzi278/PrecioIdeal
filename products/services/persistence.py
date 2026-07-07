from products.models import PriceHistory, Product
from products.services.pricing import apply_pricing_fields


def _current_price(product_data):
    return product_data.get("price_best")


def _build_change(entry_type, product, old_price, new_price, monitor_name=""):
    return {
        "entry_type": entry_type,
        "product": product,
        "product_name": product.name,
        "kid": product.kid,
        "brand": product.brand,
        "retail": product.retail,
        "image_url": product.image_url,
        "monitor_name": monitor_name,
        "old_price": old_price,
        "new_price": new_price,
        "discount_percent": product.discount_percent,
        "discount_amount": product.discount_amount,
    }


def save_products(products, monitor_name=""):
    created_count = 0
    updated_count = 0
    history_count = 0
    changes = []

    for item in products:
        apply_pricing_fields(item)
        kid = item["kid"]
        new_price = _current_price(item)

        try:
            product = Product.objects.get(kid=kid)
            old_price = product.current_price
            for field, value in item.items():
                setattr(product, field, value)
            product.save()
            updated_count += 1

            if new_price is not None and new_price != old_price:
                PriceHistory.objects.create(product=product, price=new_price)
                history_count += 1
                changes.append(
                    _build_change(
                        "price_change",
                        product,
                        old_price,
                        new_price,
                        monitor_name,
                    )
                )

        except Product.DoesNotExist:
            product = Product.objects.create(**item)
            created_count += 1
            if new_price is not None:
                PriceHistory.objects.create(product=product, price=new_price)
                history_count += 1
            changes.append(
                _build_change(
                    "new_product",
                    product,
                    None,
                    new_price,
                    monitor_name,
                )
            )

    price_change_count = sum(
        1 for change in changes if change["entry_type"] == "price_change"
    )

    return {
        "created": created_count,
        "updated": updated_count,
        "history_entries": history_count,
        "price_changes": price_change_count,
        "changes": changes,
    }
