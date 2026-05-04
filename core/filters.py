import django_filters
from django import forms as django_forms

from .models import Order, Platform


class OrderFilter(django_filters.FilterSet):
    title_contains = django_filters.CharFilter(
        field_name="title",
        lookup_expr="icontains",
        label="В названии",
        widget=django_forms.TextInput(attrs={"placeholder": "Найти заказ"}),
    )
    tags_contains = django_filters.CharFilter(
        field_name="tags",
        lookup_expr="icontains",
        label="Теги",
        widget=django_forms.TextInput(attrs={"placeholder": "Например: дизайн"}),
    )
    platform = django_filters.ModelChoiceFilter(
        queryset=Platform.objects.order_by("name"),
        label="Платформа",
        empty_label="Все платформы",
    )
    status = django_filters.ChoiceFilter(
        choices=Order.Status.choices,
        empty_label="Все статусы",
        label="Статус",
    )

    class Meta:
        model = Order
        fields: list[str] = []
