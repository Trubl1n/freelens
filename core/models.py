from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name=_("Пользователь"),
    )
    start_date = models.DateField(verbose_name=_("Дата начала"))
    first_order_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Дата первого заказа"),
    )
    skills = models.TextField(blank=True, default="", verbose_name=_("Навыки"))
    timezone = models.CharField(
        max_length=64,
        default="Europe/Moscow",
        verbose_name=_("Часовой пояс"),
    )
    target_monthly_income = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name=_("Целевой месячный доход"),
    )
    mistral_api_key_encrypted = models.CharField(
        max_length=512,
        blank=True,
        default="",
        verbose_name=_("Mistral API key (encrypted)"),
    )
    ai_insights = models.TextField(
        blank=True,
        default="",
        verbose_name=_("AI-рекомендации"),
    )

    class Meta:
        ordering = ["start_date"]
        verbose_name = _("Профиль")
        verbose_name_plural = _("Профили")

    def __str__(self) -> str:
        return f"{self.user.get_username()} — профиль"


class AiLog(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "success", _("Успех")
        ERROR = "error", _("Ошибка")
        TIMEOUT = "timeout", _("Таймаут")

    order = models.ForeignKey(
        "Order",
        on_delete=models.CASCADE,
        related_name="ai_logs",
        verbose_name=_("Заказ"),
    )
    prompt = models.TextField(verbose_name=_("Промпт"))
    response = models.TextField(blank=True, default="", verbose_name=_("Ответ"))
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUCCESS,
        verbose_name=_("Статус"),
    )
    error_message = models.TextField(blank=True, default="", verbose_name=_("Сообщение об ошибке"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Создан"))

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Лог AI")
        verbose_name_plural = _("Логи AI")

    def __str__(self) -> str:
        return f"AI лог #{self.pk} для заказа {self.order_id}"


class Platform(models.Model):
    name = models.CharField(max_length=120, verbose_name=_("Название"))
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0")),
            MaxValueValidator(Decimal("100")),
        ],
        verbose_name=_("Комиссия, %"),
    )
    website = models.URLField(
        blank=True,
        null=True,
        verbose_name=_("Сайт"),
    )
    color = models.CharField(
        max_length=32,
        default="#6366f1",
        verbose_name=_("Цвет (UI)"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Активна"))

    class Meta:
        ordering = ["name"]
        verbose_name = _("Площадка")
        verbose_name_plural = _("Площадки")

    def __str__(self) -> str:
        return self.name


class Order(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Черновик")
        ACTIVE = "active", _("В работе")
        COMPLETED = "completed", _("Завершён")
        PAID = "paid", _("Оплачен")
        CANCELLED = "cancelled", _("Отменён")

    platform = models.ForeignKey(
        Platform,
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name=_("Площадка"),
    )
    title = models.CharField(max_length=255, verbose_name=_("Название"))
    description = models.TextField(blank=True, default="", verbose_name=_("Описание"))
    gross_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name=_("Сумма до комиссии"),
    )
    commission_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        editable=False,
        verbose_name=_("Комиссия"),
    )
    net_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        editable=False,
        verbose_name=_("На руки"),
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Дата начала заказа"),
        help_text=_("Когда начали работу над заказом"),
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Дата завершения"),
        help_text=_("Когда заказ был завершён"),
    )
    time_spent_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Время (часы)"),
        help_text=_("Затраченное время в часах (можно рассчитать автоматически)"),
    )
    time_spent_minutes = models.PositiveIntegerField(
        default=0,
        editable=False,
        verbose_name=_("Затрачено времени, мин. (deprecated)"),
        help_text=_("Устаревшее поле, используйте time_spent_hours"),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name=_("Статус"),
    )
    tags = models.CharField(
        max_length=512,
        blank=True,
        default="",
        verbose_name=_("Теги"),
    )
    ai_feedback = models.TextField(
        blank=True,
        default="",
        editable=False,
        verbose_name=_("Отзыв AI"),
        help_text=_("Автоматически генерируется AI при сохранении"),
    )
    ai_rating = models.IntegerField(
        null=True,
        blank=True,
        editable=False,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("Оценка AI"),
        help_text=_("Автоматически генерируется AI при сохранении"),
    )

    class Meta:
        ordering = ["-completed_at", "-pk"]
        verbose_name = _("Заказ")
        verbose_name_plural = _("Заказы")

    def __str__(self) -> str:
        return self.title

    def calculate_time_spent(self) -> None:
        """Автоматически рассчитать time_spent_hours из started_at и completed_at."""
        if self.started_at and self.completed_at:
            from decimal import ROUND_HALF_UP
            delta = self.completed_at - self.started_at
            hours = delta.total_seconds() / 3600
            self.time_spent_hours = Decimal(str(hours)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

    def save(self, *args, **kwargs) -> None:
        # Автозаполнение времени если даты заполнены
        if self.started_at and self.completed_at and self.time_spent_hours is None:
            self.calculate_time_spent()

        # Синхронизация time_spent_minutes для обратной совместимости
        if self.time_spent_hours is not None:
            self.time_spent_minutes = int(float(self.time_spent_hours) * 60)

        cents = Decimal("0.01")
        gross = self.gross_amount
        pid = getattr(self, "platform_id", None)

        if pid and gross is not None:
            rate_pct = Platform.objects.only("commission_rate").get(pk=pid).commission_rate
            self.commission_amount = (
                gross * rate_pct / Decimal("100")
            ).quantize(cents, rounding=ROUND_HALF_UP)
            self.net_amount = (gross - self.commission_amount).quantize(
                cents, rounding=ROUND_HALF_UP
            )
        else:
            self.commission_amount = Decimal("0.00").quantize(cents)
            zero_gross = Decimal("0.00").quantize(cents)
            self.net_amount = gross.quantize(cents, rounding=ROUND_HALF_UP) if gross is not None else zero_gross
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse("core:order-detail", kwargs={"pk": self.pk})
