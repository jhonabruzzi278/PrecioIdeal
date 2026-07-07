def compute_knasta_pricing(
    current_price,
    reference_price,
    price_internet=None,
    price_card=None,
    percent=None,
):
    price_best = current_price
    discount_percent = None
    discount_amount = None

    if reference_price and price_best and reference_price > price_best:
        discount_amount = reference_price - price_best
        discount_percent = round(discount_amount / reference_price * 100)

    if percent is not None:
        try:
            percent_value = abs(int(percent))
        except (TypeError, ValueError):
            percent_value = None
        if percent_value:
            discount_percent = percent_value
            if reference_price and price_best and reference_price > price_best:
                discount_amount = reference_price - price_best

    return {
        "price_best": price_best,
        "discount_percent": discount_percent,
        "discount_amount": discount_amount,
        "price_internet": price_internet,
        "price_card": price_card,
    }


def apply_pricing_fields(data):
    if data.get("source") == "knasta" or "kid" in data:
        pricing = compute_knasta_pricing(
            data.get("price_best"),
            data.get("reference_price"),
            data.get("price_internet"),
            data.get("price_card"),
            data.get("discount_percent"),
        )
        data["price_best"] = pricing["price_best"]
        data["discount_percent"] = pricing["discount_percent"]
        data["discount_amount"] = pricing["discount_amount"]
    return data
