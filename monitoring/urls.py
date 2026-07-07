from django.urls import path

from monitoring import views

urlpatterns = [
    path("monitors/", views.monitor_list, name="monitor_list"),
    path("monitors/new/", views.monitor_create, name="monitor_create"),
    path("update-prices/", views.update_prices, name="update_prices"),
    path("reports/", views.report_list, name="report_list"),
    path("reports/<int:pk>/", views.report_detail, name="report_detail"),
    path("reports/<int:pk>/status/", views.report_status, name="report_status"),
    path("settings/schedule/", views.schedule_settings, name="schedule_settings"),
]
