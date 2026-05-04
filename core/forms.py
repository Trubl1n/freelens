from decimal import Decimal

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Field, Layout, Submit
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import Order, Platform, Profile


FORM_CONTROL_CLASS = "form-control"


def _style_form_fields(form: forms.BaseForm) -> None:
    for field in form.fields.values():
        widget = field.widget
        existing = widget.attrs.get("class", "")
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs["class"] = (existing + " form-checkbox").strip()
            continue
        if isinstance(widget, forms.Select):
            widget.attrs["class"] = (existing + " form-select").strip()
            continue
        widget.attrs["class"] = (existing + " form-control").strip()


class PlatformForm(forms.ModelForm):
    color = forms.CharField(
        widget=forms.TextInput(attrs={"type": "color"}),
        label=_("Цвет"),
        help_text=_("Цветовой акцент для карточки платформы."),
    )

    class Meta:
        model = Platform
        fields = ("name", "commission_rate", "website", "color", "is_active")
        labels = {
            "name": _("Название"),
            "commission_rate": _("Комиссия"),
            "website": _("Сайт"),
            "is_active": _("Активна"),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        _style_form_fields(self)
        self.fields["commission_rate"].widget.attrs.update({"placeholder": "10"})
        self.fields["website"].widget.attrs.update({"placeholder": "https://example.com"})
        self.helper = FormHelper(self)
        self.helper.form_tag = False


class OrderForm(forms.ModelForm):
    started_at = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "step": "60"}, format="%Y-%m-%dT%H:%M"),
        label=_("Дата начала"),
        help_text=_("Когда начали работу над заказом."),
        required=False,
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"],
    )
    completed_at = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "step": "60"}, format="%Y-%m-%dT%H:%M"),
        label=_("Дата завершения"),
        help_text=_("Когда заказ был завершён."),
        required=False,
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"],
    )
    time_spent_hours = forms.DecimalField(
        widget=forms.NumberInput(attrs={"type": "number", "step": "0.5", "min": "0"}),
        label=_("Время, часы"),
        help_text=_("Например: 1.5 = 1 час 30 минут."),
        required=False,
        min_value=0,
        decimal_places=2,
        max_digits=5,
    )
    gross_amount = forms.DecimalField(
        widget=forms.NumberInput(attrs={"type": "number", "step": "0.01", "min": "0"}),
        label=_("Сумма до комиссии"),
        help_text=_("Полная сумма заказа до вычета комиссии платформы."),
        min_value=0,
        decimal_places=2,
        max_digits=12,
    )

    class Meta:
        model = Order
        exclude = ("commission_amount", "net_amount", "ai_feedback", "ai_rating", "time_spent_minutes")
        labels = {
            "platform": _("Платформа"),
            "title": _("Название"),
            "description": _("Описание"),
            "status": _("Статус"),
            "tags": _("Теги"),
        }
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Например: Лендинг для SaaS"}),
            "description": forms.Textarea(attrs={"placeholder": "Кратко опишите задачу"}),
            "tags": forms.TextInput(attrs={"placeholder": "дизайн, frontend, срочно"}),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        _style_form_fields(self)
        self.helper = FormHelper(self)
        self.helper.form_tag = False

    def clean_gross_amount(self):
        gross = self.cleaned_data.get("gross_amount")
        if gross is None:
            return gross
        if gross <= Decimal("0"):
            raise ValidationError(_("Сумма до комиссии должна быть больше нуля."))
        return gross

    def clean(self):
        cleaned_data = super().clean()
        started_at = cleaned_data.get("started_at")
        completed_at = cleaned_data.get("completed_at")
        if started_at and completed_at and completed_at < started_at:
            raise ValidationError(_("Дата завершения не может быть раньше даты начала."))
        return cleaned_data


class ProfileForm(forms.ModelForm):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}, format="%Y-%m-%d"),
        label=_("Дата начала"),
        help_text=_("Формат: YYYY-MM-DD"),
    )
    first_order_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}, format="%Y-%m-%d"),
        label=_("Дата первого заказа"),
        help_text=_("Опционально."),
        required=False,
    )

    class Meta:
        model = Profile
        fields = ("start_date", "first_order_date", "skills", "timezone", "target_monthly_income")
        labels = {
            "skills": _("Навыки"),
            "timezone": _("Часовой пояс"),
            "target_monthly_income": _("Целевой месячный доход"),
        }
        widgets = {
            "skills": forms.Textarea(attrs={"rows": 3, "placeholder": "Python, дизайн, React, аналитика"}),
            "timezone": forms.TextInput(attrs={"placeholder": "Europe/Moscow"}),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        _style_form_fields(self)
        self.helper = FormHelper(self)
        self.helper.form_method = "post"
        self.helper.form_id = "profile-form"
        self.helper.add_input(Submit("submit", _("Сохранить профиль"), css_class="btn btn-primary btn-full"))

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        first_order_date = cleaned_data.get("first_order_date")
        if start_date and first_order_date and first_order_date < start_date:
            raise ValidationError(_("Дата первого заказа не может быть раньше даты начала карьеры."))
        return cleaned_data


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={"placeholder": "you@example.com"}), label=_("Email"))

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]
        labels = {
            "username": _("Имя пользователя"),
            "password1": _("Пароль"),
            "password2": _("Повторите пароль"),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        _style_form_fields(self)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            Field("username"),
            Field("email"),
            Field("password1"),
            Field("password2"),
            Submit("submit", _("Зарегистрироваться"), css_class="btn btn-primary btn-full mt-4"),
        )

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and User.objects.filter(email=email).exists():
            raise ValidationError(_("Пользователь с таким email уже существует."))
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user
