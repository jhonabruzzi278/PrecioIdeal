from django.contrib import admin

from monitoring.models import Monitor, UpdateReport, UpdateReportEntry, UpdateSchedule


@admin.register(Monitor)
class MonitorAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category_name",
        "category_id",
        "active",
        "last_execution",
        "created_at",
    )
    list_filter = ("active", "created_at", "last_execution")
    search_fields = ("name", "category_name", "category_slug", "category_id")
    list_editable = ("active",)
    readonly_fields = ("created_at", "last_execution")


class UpdateReportEntryInline(admin.TabularInline):
    model = UpdateReportEntry
    extra = 0
    readonly_fields = ("entry_type", "product_name", "kid", "retail", "old_price", "new_price")
    can_delete = False


@admin.register(UpdateReport)
class UpdateReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "trigger",
        "started_at",
        "products_created",
        "price_changes",
    )
    list_filter = ("status", "trigger", "started_at")
    readonly_fields = (
        "started_at",
        "finished_at",
        "current_step",
        "monitors_processed",
        "products_scraped",
        "products_created",
        "products_updated",
        "price_changes",
        "error_log",
    )
    inlines = [UpdateReportEntryInline]


@admin.register(UpdateSchedule)
class UpdateScheduleAdmin(admin.ModelAdmin):
    list_display = ("enabled", "interval_hours", "last_run", "updated_at")
    readonly_fields = ("last_run", "updated_at")
