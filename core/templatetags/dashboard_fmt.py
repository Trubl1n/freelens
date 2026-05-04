from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


def _quantize_money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _spaced_digits(whole_digits: str) -> str:
    rev = "".join(reversed(whole_digits))
    chunks = [rev[i : i + 3] for i in range(0, len(rev), 3)]
    return " ".join("".join(reversed(ch)) for ch in reversed(chunks))


@register.filter(is_safe=False)
def rub(value):
    """Формат денег: 1 234,56 ₽."""
    if value is None or value == "":
        return "—"
    try:
        d = _quantize_money(value)
    except (InvalidOperation, TypeError, ValueError):
        return "—"
    neg = d < 0
    d_abs = abs(d)
    whole, _, frac = format(d_abs, "f").partition(".")
    frac = (frac + "00")[:2]
    prefix = "−" if neg else ""
    return mark_safe(prefix + _spaced_digits(whole) + "," + frac + "\xa0₽")


@register.filter
def minutes_human(value):
    """Минуты -> строка вида 42 ч 10 м."""
    if value is None or value == "":
        return "—"
    try:
        total = int(value)
    except (TypeError, ValueError):
        return "—"
    if total <= 0:
        return "0 м"
    h, m = divmod(total, 60)
    if h and m:
        return f"{h} ч {m} м"
    if h:
        return f"{h} ч"
    return f"{m} м"


@register.filter
def hours_decimal(value):
    """Минуты -> число часов с запятой, 2 знака."""
    if value is None or value == "":
        return "—"
    try:
        mins = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return "—"
    if mins <= 0:
        return "0"
    hours = (mins / Decimal("60")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return str(hours).replace(".", ",")


@register.filter
def div(value, arg):
    try:
        return Decimal(str(value)) / Decimal(str(arg))
    except (InvalidOperation, TypeError, ValueError, ZeroDivisionError):
        return ""
