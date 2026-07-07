from django.urls import path

from billing import views

urlpatterns = [
    path("signup/", views.signup, name="signup"),
]
