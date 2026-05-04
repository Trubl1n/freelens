from datetime import date, datetime, timedelta, time as dt_time
from decimal import ROUND_HALF_UP, Decimal
from json import dumps as json_dumps

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView
from django_filters.views import FilterView

from .services.ai_service import (
    MistralService,
    analyze_freelance_stats,
    evaluate_order,
    resolve_mistral_key_for_user,
)
from .filters import OrderFilter
from .forms import OrderForm, PlatformForm, ProfileForm, UserRegistrationForm
from .models import AiLog, Order, Platform, Profile


class SuccessUrlMixin:
    """Редирект после успешной формы или удаления на именованный маршрут."""

    success_route: str | None = None
    success_route_needs_pk: bool = False

    def get_success_url(self):  # type: ignore[override]
        route = getattr(self, "success_route", None)
        if route:
            if self.success_route_needs_pk and getattr(self.object, "pk", None):
                return reverse(route, kwargs={"pk": self.object.pk})
            return reverse(route)
        return super().get_success_url()  # type: ignore[misc]


class OrderCommissionRefreshMixin:
    """Отражает суммы после сохранения: Order.save() пересчитывает commission/net."""

    def form_valid(self, form):  # type: ignore[override]
        response = super().form_valid(form)
        self.object.refresh_from_db(fields=["commission_amount", "net_amount"])
        return response


def index(request):
    return render(request, "core/index.html")


_COMPLETED_STATUSES = (Order.Status.COMPLETED, Order.Status.PAID)
_MONEY_SUM = DecimalField(max_digits=12, decimal_places=2)


def _dashboard_month_series(months_back: int = 6):
    """Список (date первого числа месяца, короткая подпись для графика)."""
    MONTH_ABBR = (
        "янв",
        "фев",
        "мар",
        "апр",
        "мая",
        "июн",
        "июл",
        "авг",
        "сен",
        "окт",
        "ноя",
        "дек",
    )
    today = timezone.localdate()
    y, mo = today.year, today.month
    out = []
    for k in range(months_back - 1, -1, -1):
        mm = mo - k
        yy = y
        while mm <= 0:
            mm += 12
            yy -= 1
        dt = date(yy, mm, 1)
        out.append((dt, f"{MONTH_ABBR[dt.month - 1]} {dt.year}"))
    return out


def _month_bounds_tz(d: date) -> tuple[datetime, datetime]:
    tz_cur = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(d, dt_time.min), tz_cur)
    if d.month == 12:
        nxt_date = date(d.year + 1, 1, 1)
    else:
        nxt_date = date(d.year, d.month + 1, 1)
    end_excl = timezone.make_aware(datetime.combine(nxt_date, dt_time.min), tz_cur)
    return start, end_excl


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        orders_all_qs = Order.objects.all()
        zero_money = Value(Decimal("0.00"), output_field=_MONEY_SUM)

        totals_agg = orders_all_qs.aggregate(
            tg=Sum("gross_amount"),
            tn=Sum("net_amount"),
        )
        total_gross = totals_agg["tg"] or Decimal("0.00")
        total_net = totals_agg["tn"] or Decimal("0.00")

        orders_count = orders_all_qs.count()
        active_platforms_count = Platform.objects.filter(is_active=True).count()

        done_qs = Order.objects.filter(
            status__in=_COMPLETED_STATUSES,
            completed_at__isnull=False,
        )

        hourly_basis = Order.objects.filter(
            status__in=_COMPLETED_STATUSES,
            completed_at__isnull=False,
            time_spent_minutes__gt=0,
        )
        hourly_agg = hourly_basis.aggregate(
            m=Sum("time_spent_minutes"),
            net=Sum("net_amount"),
        )
        mins = hourly_agg["m"] or 0
        hourly_net_total = hourly_agg["net"] or Decimal("0.00")
        if mins > 0:
            hours = Decimal(mins) / Decimal("60")
            avg_hourly_rate = (hourly_net_total / hours).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            avg_hourly_rate = None

        cutoff_30 = timezone.now() - timedelta(days=30)
        last_30_days_net = Order.objects.filter(
            completed_at__isnull=False,
            completed_at__gte=cutoff_30,
        ).aggregate(s=Sum("net_amount"))["s"] or Decimal("0.00")

        done_minutes_total = (
            done_qs.aggregate(s=Sum("time_spent_minutes"))["s"] or 0
        )

        orders_by_platform = (
            Platform.objects.values("pk", "name", "color", "is_active")
            .annotate(
                total_orders=Count("orders"),
                gross_sum=Coalesce(
                    Sum("orders__gross_amount"),
                    zero_money,
                    output_field=_MONEY_SUM,
                ),
                net_sum=Coalesce(
                    Sum("orders__net_amount"),
                    zero_money,
                    output_field=_MONEY_SUM,
                ),
            )
            .order_by("-net_sum", "name")
        )

        chart_labels = []
        chart_values = []
        for month_dt, lbl in _dashboard_month_series(6):
            start_d, end_d = _month_bounds_tz(month_dt)
            month_net = (
                Order.objects.filter(
                    completed_at__isnull=False,
                    completed_at__gte=start_d,
                    completed_at__lt=end_d,
                ).aggregate(r=Sum("net_amount"))["r"]
                or Decimal("0.00")
            )
            chart_labels.append(lbl)
            chart_values.append(float(month_net.quantize(Decimal("0.01"))))

        chart_payload = mark_safe(json_dumps({"labels": chart_labels, "values": chart_values}))

        ctx["stats"] = {
            "total_gross": total_gross,
            "total_net": total_net,
            "avg_hourly_rate": avg_hourly_rate,
            "orders_count": orders_count,
            "active_platforms_count": active_platforms_count,
            "last_30_days_net": last_30_days_net,
            "completed_minutes_total": int(done_minutes_total),
            "completed_orders_done_count": done_qs.count(),
        }
        ctx["orders_by_platform"] = list(orders_by_platform)
        ctx["chart_payload"] = chart_payload
        ctx["recent_orders"] = (
            Order.objects.select_related("platform")
            .order_by("-completed_at", "-pk")[:8]
        )
        ctx["profile"], _ = Profile.objects.get_or_create(
            user=self.request.user,
            defaults={
                "start_date": timezone.localdate(),
                "target_monthly_income": Decimal("0.00"),
            },
        )
        return ctx


class ProfileUpdateView(SuccessMessageMixin, LoginRequiredMixin, SuccessUrlMixin, UpdateView):
    model = Profile
    form_class = ProfileForm
    template_name = "core/profile.html"
    success_message = "Профиль сохранён."
    success_route = "core:profile"

    def get_object(self, queryset=None):
        profile, _ = Profile.objects.get_or_create(
            user=self.request.user,
            defaults={
                "start_date": timezone.localdate(),
                "target_monthly_income": Decimal("0.00"),
            },
        )
        return profile

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profile = self.get_object()
        today = timezone.localdate()

        # Даты
        days_since_start = (today - profile.start_date).days if profile.start_date else 0
        days_since_first_order = None
        if profile.first_order_date:
            days_since_first_order = (today - profile.first_order_date).days

        # Статистика заказов
        orders_qs = Order.objects.all()
        total_orders = orders_qs.count()
        completed_orders = orders_qs.filter(status__in=_COMPLETED_STATUSES).count()
        completion_rate = (completed_orders / total_orders * 100) if total_orders > 0 else 0

        # Потери на комиссиях
        commission_loss_total = orders_qs.aggregate(
            total=Sum("commission_amount")
        )["total"] or Decimal("0.00")

        # Агрегаты за все время (только с отслеженным временем для ставки)
        all_time_agg = orders_qs.aggregate(
            total_gross=Sum("gross_amount"),
            total_net=Sum("net_amount"),
            total_hours=Sum("time_spent_minutes"),
            total_hours_for_rate=Sum(
                "time_spent_minutes",
                filter=Q(time_spent_minutes__gt=0)
            ),
            net_for_rate=Sum(
                "net_amount",
                filter=Q(time_spent_minutes__gt=0)
            ),
            completed_count=Count("id", filter=Q(status__in=_COMPLETED_STATUSES)),
        )

        # Агрегаты за последний месяц (только с отслеженным временем для ставки)
        cutoff_30 = timezone.now() - timedelta(days=30)
        last_month_agg = orders_qs.filter(
            completed_at__isnull=False,
            completed_at__gte=cutoff_30,
        ).aggregate(
            total_net=Sum("net_amount"),
            total_hours=Sum("time_spent_minutes"),
            total_hours_for_rate=Sum(
                "time_spent_minutes",
                filter=Q(time_spent_minutes__gt=0)
            ),
            net_for_rate=Sum(
                "net_amount",
                filter=Q(time_spent_minutes__gt=0)
            ),
            order_count=Count("id"),
        )

        # Средняя часовая ставка (только для заказов с отслеженным временем)
        total_mins_for_rate = all_time_agg["total_hours_for_rate"] or 0
        total_hours = Decimal(total_mins_for_rate) / Decimal("60") if total_mins_for_rate else Decimal("0")
        avg_rate = Decimal("0.00")
        if total_hours > 0 and all_time_agg["net_for_rate"]:
            avg_rate = (all_time_agg["net_for_rate"] / total_hours).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        # Платформы (для AI-анализа)
        platforms_data = list(
            Platform.objects.annotate(
                order_count=Count("orders"),
                net_sum=Sum("orders__net_amount"),
            )
            .filter(order_count__gt=0)
            .values("name", "order_count", "net_sum")
        )

        ctx["profile_stats"] = {
            "days_since_start": days_since_start,
            "days_since_first_order": days_since_first_order,
            "total_orders": total_orders,
            "completion_rate": round(completion_rate, 1),
            "commission_loss_total": commission_loss_total,
            "all_time_net": all_time_agg["total_net"] or Decimal("0.00"),
            "all_time_hours": total_hours.quantize(Decimal("0.1")),
            "avg_hourly_rate": avg_rate,
            "completed_count": all_time_agg["completed_count"] or 0,
            "last_month_net": last_month_agg["total_net"] or Decimal("0.00"),
            "last_month_hours": Decimal((last_month_agg["total_hours"] or 0)) / Decimal("60"),
            "last_month_orders": last_month_agg["order_count"] or 0,
            "platforms": platforms_data,
        }
        target = profile.target_monthly_income or Decimal("0.00")
        last_month_net = ctx["profile_stats"]["last_month_net"] or Decimal("0.00")
        if target > 0:
            ctx["profile_goal_percent"] = min(100, int((last_month_net / target) * 100))
        else:
            ctx["profile_goal_percent"] = 0
        return ctx


class PlatformListView(LoginRequiredMixin, ListView):
    model = Platform
    paginate_by = 15
    template_name = "core/platform_list.html"
    context_object_name = "platforms"


class PlatformCreateView(LoginRequiredMixin, SuccessUrlMixin, CreateView):
    model = Platform
    form_class = PlatformForm
    template_name = "core/platform_form.html"
    extra_context = {"form_title": "Новая площадка"}
    success_route = "core:platform-list"


class PlatformUpdateView(LoginRequiredMixin, SuccessUrlMixin, UpdateView):
    model = Platform
    form_class = PlatformForm
    template_name = "core/platform_form.html"
    pk_url_kwarg = "pk"
    extra_context = {"form_title": "Редактирование площадки"}
    success_route = "core:platform-list"


class PlatformDeleteView(LoginRequiredMixin, SuccessUrlMixin, DeleteView):
    model = Platform
    template_name = "core/platform_confirm_delete.html"
    success_route = "core:platform-list"


class OrderListView(LoginRequiredMixin, FilterView):
    model = Order
    filterset_class = OrderFilter
    template_name = "core/order_list.html"
    paginate_by = 15
    context_object_name = "orders"

    def get_queryset(self):
        return (
            Order.objects.select_related("platform")
            .all()
            .order_by("-completed_at", "-pk")
        )


class OrderCreateView(
    LoginRequiredMixin,
    OrderCommissionRefreshMixin,
    SuccessUrlMixin,
    CreateView,
):
    model = Order
    form_class = OrderForm
    template_name = "core/order_form.html"
    extra_context = {"form_title": "Новый заказ"}
    success_route = "core:order-detail"
    success_route_needs_pk = True

    def form_valid(self, form):
        order = form.save()
        result = evaluate_order(order, user=self.request.user)
        order.ai_rating = result.get("rating")
        order.ai_feedback = result.get("feedback", "")
        order.save(update_fields=["ai_rating", "ai_feedback"])
        self.object = order
        if order.ai_rating:
            messages.success(self.request, f"Заказ создан. AI-оценка: {order.ai_rating}/5")
        else:
            messages.success(self.request, "Заказ создан.")
        return redirect(self.get_success_url())


class OrderUpdateView(
    LoginRequiredMixin,
    OrderCommissionRefreshMixin,
    SuccessUrlMixin,
    UpdateView,
):
    model = Order
    form_class = OrderForm
    template_name = "core/order_form.html"
    pk_url_kwarg = "pk"
    extra_context = {"form_title": "Редактирование заказа"}
    success_route = "core:order-detail"
    success_route_needs_pk = True

    def form_valid(self, form):
        order = form.save()
        result = evaluate_order(order, user=self.request.user)
        order.ai_rating = result.get("rating")
        order.ai_feedback = result.get("feedback", "")
        order.save(update_fields=["ai_rating", "ai_feedback"])
        self.object = order
        if order.ai_rating:
            messages.success(self.request, f"Заказ обновлён. AI-оценка: {order.ai_rating}/5")
        else:
            messages.success(self.request, "Заказ обновлён.")
        return redirect(self.get_success_url())


class OrderDetailView(LoginRequiredMixin, DetailView):
    model = Order
    template_name = "core/order_detail.html"
    context_object_name = "order"

    def get_queryset(self):
        return Order.objects.select_related("platform")


@login_required
@require_POST
def order_save_and_ai_evaluate(request, pk):
    """Сохранить форму заказа и выполнить AI-оценку (используется из order_form.html)."""
    order = get_object_or_404(Order, pk=pk)
    form = OrderForm(request.POST, instance=order)
    if not form.is_valid():
        return render(
            request,
            "core/partials/order_ai_panel.html",
            {"form_errors": form.errors},
            status=422,
        )
    saved = form.save()

    # Новый API: evaluate_order возвращает dict
    result = evaluate_order(saved, user=request.user)
    saved.ai_rating = result.get("rating")
    saved.ai_feedback = result.get("feedback", "")
    saved.save(update_fields=["ai_rating", "ai_feedback"])

    return render(request, "core/partials/order_ai_panel.html", {"order": saved})


@login_required
@require_POST
def order_ai_evaluate(request, pk):
    """Выполнить AI-оценку для существующего заказа (используется из order_detail.html)."""
    order = get_object_or_404(Order.objects.select_related("platform"), pk=pk)

    result = evaluate_order(order, user=request.user)
    order.ai_rating = result.get("rating")
    order.ai_feedback = result.get("feedback", "")
    order.save(update_fields=["ai_rating", "ai_feedback"])

    return render(request, "core/partials/order_ai_panel.html", {"order": order})


@login_required
@require_POST
def analyze_freelance(request):
    """Выполнить AI-анализ фриланс-статистики и сохранить рекомендации в профиль."""
    profile, _ = Profile.objects.get_or_create(
        user=request.user,
        defaults={
            "start_date": timezone.localdate(),
            "target_monthly_income": Decimal("0.00"),
        },
    )

    # Собираем агрегаты (консистентно с Dashboard)
    orders_qs = Order.objects.all()
    today = timezone.localdate()
    cutoff_30 = timezone.now() - timedelta(days=30)

    # Все время (только с отслеженным временем для ставки)
    all_time_agg = orders_qs.aggregate(
        total_gross=Sum("gross_amount"),
        total_net=Sum("net_amount"),
        total_hours=Sum("time_spent_minutes"),
        total_hours_for_rate=Sum(
            "time_spent_minutes",
            filter=Q(time_spent_minutes__gt=0)
        ),
        net_for_rate=Sum(
            "net_amount",
            filter=Q(time_spent_minutes__gt=0)
        ),
        completed_count=Count("id", filter=Q(status__in=_COMPLETED_STATUSES)),
        total_orders=Count("id"),
    )

    # Последний месяц
    last_month_agg = orders_qs.filter(
        completed_at__isnull=False,
        completed_at__gte=cutoff_30,
    ).aggregate(
        net=Sum("net_amount"),
        hours=Sum("time_spent_minutes"),
        orders=Count("id"),
    )

    # Средняя ставка (только для заказов с отслеженным временем - консистентно с Dashboard)
    total_mins_for_rate = all_time_agg["total_hours_for_rate"] or 0
    total_hours = Decimal(total_mins_for_rate) / Decimal("60") if total_mins_for_rate else Decimal("0")
    avg_rate = Decimal("0.00")
    if total_hours > 0 and all_time_agg["net_for_rate"]:
        avg_rate = (all_time_agg["net_for_rate"] / total_hours).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    # Платформы
    platforms_data = list(
        Platform.objects.annotate(
            order_count=Count("orders"),
            net_sum=Sum("orders__net_amount"),
        )
        .filter(order_count__gt=0)
        .values("name", "order_count", "net_sum")
    )
    platforms_str = ", ".join(
        [f"{p['name']} ({p['order_count']} заказов)" for p in platforms_data]
    ) if platforms_data else "нет данных"

    # Потери на комиссиях
    commission_loss = (all_time_agg["total_gross"] or Decimal("0")) - (all_time_agg["total_net"] or Decimal("0"))

    # Загрузка (часы)
    total_hours_int = int(total_hours)

    # Дни с начала фриланса и первого заказа
    days_since_start = (today - profile.start_date).days if profile.start_date else 0
    days_since_first_order = (
        (today - profile.first_order_date).days
        if profile.first_order_date else 0
    )

    # Подготавливаем данные для AI
    stats = {
        "net": all_time_agg["total_net"] or Decimal("0.00"),
        "avg_rate": avg_rate,
        "comm_loss": commission_loss,
        "hours_total": total_hours_int,
        "platforms": platforms_str,
        "completed_rate": (
            (all_time_agg["completed_count"] / all_time_agg["total_orders"] * 100)
            if all_time_agg["total_orders"] else 0
        ),
        "last_month_net": last_month_agg["net"] or Decimal("0.00"),
        "last_month_orders": last_month_agg["orders"] or 0,
        "target_income": profile.target_monthly_income,
        "days_since_start": days_since_start,
        "days_since_first_order": days_since_first_order,
    }

    # Вызываем AI
    insights = analyze_freelance_stats(stats, user=request.user)

    # Сохраняем в профиль
    profile.ai_insights = insights
    profile.save(update_fields=["ai_insights"])
    profile.refresh_from_db()

    return render(request, "core/partials/profile_ai_insights.html", {"profile": profile})


class RegisterView(CreateView):
    """Регистрация нового пользователя с автоматическим входом."""

    form_class = UserRegistrationForm
    template_name = "registration/register.html"
    success_url = reverse_lazy("core:dashboard")

    def dispatch(self, request, *args, **kwargs):
        """Перенаправить аутентифицированных пользователей на dashboard."""
        if request.user.is_authenticated:
            return redirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, "Аккаунт создан! Добро пожаловать.")
        return super().form_valid(form)


class CustomLoginView(LoginView):
    """Кастомная страница входа с редиректом для аутентифицированных."""

    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse("core:dashboard")
