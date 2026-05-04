from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def pagination_url(context, page_number):
    """Тот же path + GET с заменённым параметром page (для фильтров django-filter)."""
    request = context["request"]
    qs = request.GET.copy()
    qs["page"] = str(page_number)
    suffix = qs.urlencode()
    return f"{request.path}?{suffix}" if suffix else request.path
