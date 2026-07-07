from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Monitor(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="monitors",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=200)
    category_id = models.CharField(max_length=50)
    category_slug = models.CharField(max_length=500)
    category_name = models.CharField(max_length=500, blank=True)
    active = models.BooleanField(default=True)
    last_execution = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def results_url(self):
        from products.services.knasta import KnastaScraper

        return KnastaScraper.results_url(self.category_slug)


class UpdateReport(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_PARTIAL = "partial"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendiente"),
        (STATUS_RUNNING, "En ejecución"),
        (STATUS_COMPLETED, "Completado"),
        (STATUS_PARTIAL, "Parcial"),
        (STATUS_FAILED, "Fallido"),
    ]

    TRIGGER_MANUAL = "manual"
    TRIGGER_SCHEDULED = "scheduled"

    TRIGGER_CHOICES = [
        (TRIGGER_MANUAL, "Manual"),
        (TRIGGER_SCHEDULED, "Programado"),
    ]

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    trigger = models.CharField(
        max_length=20, choices=TRIGGER_CHOICES, default=TRIGGER_MANUAL
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    current_step = models.CharField(max_length=500, blank=True)
    progress_current = models.PositiveIntegerField(default=0)
    progress_total = models.PositiveIntegerField(default=0)
    monitors_processed = models.PositiveIntegerField(default=0)
    products_scraped = models.PositiveIntegerField(default=0)
    products_created = models.PositiveIntegerField(default=0)
    products_updated = models.PositiveIntegerField(default=0)
    price_changes = models.PositiveIntegerField(default=0)
    error_log = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"Informe #{self.pk} — {self.get_status_display()} ({self.started_at:%d/%m/%Y %H:%M})"

    @property
    def is_finished(self):
        return self.status in {
            self.STATUS_COMPLETED,
            self.STATUS_PARTIAL,
            self.STATUS_FAILED,
        }

    @property
    def progress_percent(self):
        if self.progress_total == 0:
            return 0
        return min(100, int(self.progress_current / self.progress_total * 100))

    @property
    def duration_seconds(self):
        if not self.finished_at:
            return None
        return int((self.finished_at - self.started_at).total_seconds())


class UpdateReportEntry(models.Model):
    ENTRY_NEW = "new_product"
    ENTRY_PRICE = "price_change"

    ENTRY_CHOICES = [
        (ENTRY_NEW, "Producto nuevo"),
        (ENTRY_PRICE, "Cambio de precio"),
    ]

    report = models.ForeignKey(
        UpdateReport, on_delete=models.CASCADE, related_name="entries"
    )
    entry_type = models.CharField(max_length=20, choices=ENTRY_CHOICES)
    product = models.ForeignKey(
        "products.Product", null=True, blank=True, on_delete=models.SET_NULL
    )
    product_name = models.CharField(max_length=500)
    kid = models.CharField(max_length=120)
    brand = models.CharField(max_length=200, blank=True)
    retail = models.CharField(max_length=100, blank=True)
    image_url = models.URLField(max_length=1000, blank=True)
    monitor_name = models.CharField(max_length=200, blank=True)
    old_price = models.PositiveIntegerField(null=True, blank=True)
    new_price = models.PositiveIntegerField(null=True, blank=True)
    discount_percent = models.PositiveSmallIntegerField(null=True, blank=True)
    discount_amount = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["entry_type", "product_name"]

    @property
    def price_diff(self):
        if self.old_price is None or self.new_price is None:
            return None
        return self.new_price - self.old_price

    def formatted_old_price(self):
        return self._format_price(self.old_price)

    def formatted_new_price(self):
        return self._format_price(self.new_price)

    def formatted_diff(self):
        diff = self.price_diff
        if diff is None:
            return "—"
        sign = "+" if diff > 0 else ""
        return f"{sign}${abs(diff):,}".replace(",", ".")

    def get_discount_percent(self):
        if self.discount_percent is not None:
            return self.discount_percent
        if self.product_id:
            return self.product.discount_percent
        return None

    def get_discount_amount(self):
        if self.discount_amount is not None:
            return self.discount_amount
        if self.product_id:
            return self.product.discount_amount
        return None

    def formatted_discount_percent(self):
        percent = self.get_discount_percent()
        if not percent:
            return "—"
        return f"-{percent}%"

    def formatted_discount_amount(self):
        return self._format_price(self.get_discount_amount())

    def has_discount(self):
        return self.get_discount_percent() is not None and self.get_discount_amount() is not None

    @staticmethod
    def _format_price(price):
        if price is None:
            return "—"
        return f"${price:,}".replace(",", ".")


class UpdateSchedule(models.Model):
    enabled = models.BooleanField(default=False)
    interval_hours = models.PositiveIntegerField(
        default=6,
        validators=[MinValueValidator(1), MaxValueValidator(168)],
        help_text="Intervalo entre actualizaciones (1-168 horas).",
    )
    last_run = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Programación de actualización"
        verbose_name_plural = "Programación de actualización"

    def __str__(self):
        state = "activa" if self.enabled else "inactiva"
        return f"Actualización automática ({state}, cada {self.interval_hours}h)"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
