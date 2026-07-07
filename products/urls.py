from django.urls import path

from products import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("clear-data/", views.clear_data, name="clear_data"),
    path("products/", views.product_list, name="product_list"),
    path("products/<int:pk>/", views.product_detail, name="product_detail"),
]
