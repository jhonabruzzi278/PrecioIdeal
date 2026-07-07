from django.contrib import admin

from billing.models import Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "price_clp", "max_active_monitors", "is_pro"]
    list_filter = ["is_pro"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["user", "plan", "status", "access_until", "created_at"]
    list_filter = ["status", "plan"]
    search_fields = ["user__username", "user__email"]
    autocomplete_fields = ["user"]
    readonly_fields = ["created_at", "updated_at"]
