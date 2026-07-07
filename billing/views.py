import logging

from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect, render

from billing.forms import SignupForm
from billing.services.access import get_or_create_subscription

logger = logging.getLogger(__name__)


def signup(request):
    """Self-service registration: create account, start trial, log in."""
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            try:
                get_or_create_subscription(user)
            except Exception:
                # Never block account creation on trial provisioning; it can
                # be retried lazily on the user's first gated action.
                logger.exception("No se pudo iniciar el trial para %s", user)
            login(request, user)
            messages.success(
                request,
                "¡Cuenta creada! Tienes 30 días de prueba con todas las "
                "funcionalidades Pro.",
            )
            return redirect("dashboard")
    else:
        form = SignupForm()

    return render(request, "registration/signup.html", {"form": form})
