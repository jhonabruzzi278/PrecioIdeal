from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

TRIAL_DAYS = 30


class Plan(models.Model):
    """A subscription tier (Free / Pro) and the limits it grants.

    Limits live as fields so they can be tuned from the admin without code
    changes. The catalog/price history is a global shared asset and is never
    gated here — only the per-account monitoring capability is.
    """

    SLUG_FREE = "free"
    SLUG_PRO = "pro"

    name = models.CharField("nombre", max_length=100)
    slug = models.SlugField(unique=True)
    price_clp = models.PositiveIntegerField("precio (CLP)", default=0)
    # Limits / capabilities
    max_active_monitors = models.PositiveIntegerField(
        "monitores activos máximos", default=0
    )
    can_create_monitors = models.BooleanField("puede crear monitores", default=False)
    can_run_manual_update = models.BooleanField(
        "puede actualizar manualmente", default=False
    )
    can_receive_price_alerts = models.BooleanField(
        "recibe alertas de precio", default=False
    )
    can_export = models.BooleanField("puede exportar", default=False)
    is_pro = models.BooleanField("es plan pro", default=False)

    class Meta:
        verbose_name = "Plan"
        verbose_name_plural = "Planes"
        ordering = ["price_clp"]

    def __str__(self):
        return self.name


class Subscription(models.Model):
    """Links a user account to a plan and tracks its lifecycle state.

    A brand-new account starts in ``trialing`` with full Pro access for
    ``TRIAL_DAYS`` days. When the trial/paid period lapses without payment the
    account moves to ``expired`` and its monitors are deactivated (never
    deleted); historical data stays accessible.
    """

    STATUS_TRIALING = "trialing"
    STATUS_ACTIVE = "active"
    STATUS_PAST_DUE = "past_due"
    STATUS_EXPIRED = "expired"
    STATUS_CANCELED = "canceled"

    STATUS_CHOICES = [
        (STATUS_TRIALING, "En prueba"),
        (STATUS_ACTIVE, "Activa"),
        (STATUS_PAST_DUE, "Pago pendiente"),
        (STATUS_EXPIRED, "Vencida"),
        (STATUS_CANCELED, "Cancelada"),
    ]

    # Statuses that grant full Pro capabilities.
    PRO_ACCESS_STATUSES = frozenset({STATUS_TRIALING, STATUS_ACTIVE})

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.ForeignKey(
        Plan, on_delete=models.PROTECT, related_name="subscriptions"
    )
    status = models.CharField(
        "estado", max_length=20, choices=STATUS_CHOICES, default=STATUS_TRIALING
    )
    trial_ends_at = models.DateTimeField("fin de prueba", null=True, blank=True)
    current_period_end = models.DateTimeField(
        "fin del período actual", null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Suscripción"
        verbose_name_plural = "Suscripciones"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} — {self.plan} ({self.get_status_display()})"

    @property
    def access_until(self):
        """The moment current access lapses (trial end or paid period end)."""
        if self.status == self.STATUS_TRIALING:
            return self.trial_ends_at
        return self.current_period_end

    @property
    def has_pro_access(self):
        """True while the account may use paid monitoring features."""
        if self.status not in self.PRO_ACCESS_STATUSES:
            return False
        deadline = self.access_until
        return deadline is None or deadline > timezone.now()

    @property
    def is_lapsed(self):
        """True when a trialing/active subscription has passed its deadline."""
        if self.status not in self.PRO_ACCESS_STATUSES:
            return False
        deadline = self.access_until
        return deadline is not None and deadline <= timezone.now()

    def days_left(self):
        deadline = self.access_until
        if deadline is None:
            return None
        remaining = deadline - timezone.now()
        return max(0, remaining.days)

    @classmethod
    def start_trial(cls, user, plan):
        """Create a 30-day Pro trial subscription for a new user."""
        now = timezone.now()
        return cls.objects.create(
            user=user,
            plan=plan,
            status=cls.STATUS_TRIALING,
            trial_ends_at=now + timedelta(days=TRIAL_DAYS),
        )
