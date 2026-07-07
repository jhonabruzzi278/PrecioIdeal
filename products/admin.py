from django.contrib import admin

from products.models import PriceHistory, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "brand",
        "seller",
        "retail",
        "price_best",
        "reference_price",
        "discount_percent",
        "is_best_price",
        "updated_at",
    )
    list_filter = ("retail", "brand", "is_best_price", "source", "created_at")
    search_fields = ("name", "kid", "product_id", "brand", "seller", "retail")
    readonly_fields = ("created_at", "updated_at")


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ("product", "price", "created_at")
    list_filter = ("created_at",)
    search_fields = ("product__name", "product__kid")
    readonly_fields = ("created_at",)
    raw_id_fields = ("product",)
