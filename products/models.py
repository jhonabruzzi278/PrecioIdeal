from django.db import models


class Product(models.Model):
    SOURCE_KNASTA = "knasta"

    kid = models.CharField(max_length=120, unique=True)
    product_id = models.CharField(max_length=80)
    name = models.CharField(max_length=500)
    brand = models.CharField(max_length=200, blank=True)
    retail = models.CharField(max_length=100, blank=True)
    seller = models.CharField(max_length=200, blank=True)
    product_url = models.URLField(max_length=1000)
    image_url = models.URLField(max_length=1000, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    reviews = models.PositiveIntegerField(default=0)
    price_best = models.PositiveIntegerField(null=True, blank=True)
    price_internet = models.PositiveIntegerField(null=True, blank=True)
    price_card = models.PositiveIntegerField(null=True, blank=True)
    reference_price = models.PositiveIntegerField(null=True, blank=True)
    best_variation_price = models.PositiveIntegerField(null=True, blank=True)
    discount_percent = models.PositiveSmallIntegerField(null=True, blank=True)
    discount_amount = models.PositiveIntegerField(null=True, blank=True)
    is_best_price = models.BooleanField(default=False)
    source = models.CharField(max_length=50, default=SOURCE_KNASTA)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name

    def resolve_pricing(self):
        from products.services.pricing import compute_knasta_pricing

        return compute_knasta_pricing(
            self.price_best,
            self.reference_price,
            self.price_internet,
            self.price_card,
            self.discount_percent,
        )

    @property
    def current_price(self):
        return self.price_best

    @property
    def has_discount(self):
        return self.discount_percent is not None and self.discount_amount is not None

    def formatted_discount_percent(self):
        if not self.discount_percent:
            return "—"
        return f"-{self.discount_percent}%"

    def formatted_discount_amount(self):
        return self._format_price(self.discount_amount)

    def formatted_current_price(self):
        return self._format_price(self.current_price)

    @property
    def formatted_internet_price(self):
        return self._format_price(self.price_internet)

    @property
    def formatted_card_price(self):
        return self._format_price(self.price_card)

    @property
    def formatted_reference_price(self):
        return self._format_price(self.reference_price)

    @property
    def formatted_best_variation_price(self):
        return self._format_price(self.best_variation_price)

    def sync_pricing_fields(self, save=False):
        pricing = self.resolve_pricing()
        self.discount_percent = pricing["discount_percent"]
        self.discount_amount = pricing["discount_amount"]
        if save:
            self.save(update_fields=["discount_percent", "discount_amount"])
        return pricing

    @staticmethod
    def _format_price(price):
        if price is None:
            return "—"
        return f"${price:,.0f}".replace(",", ".")


class PriceHistory(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="price_history"
    )
    price = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "price histories"

    def __str__(self):
        return f"{self.product.name} — ${self.price} ({self.created_at:%Y-%m-%d})"

    def formatted_price(self):
        return f"${self.price:,.0f}".replace(",", ".")
