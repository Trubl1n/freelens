"""
Template tags для рендеринга Markdown в шаблонах.
"""
import markdown
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='render_markdown')
def render_markdown(value):
    """
    Конвертирует Markdown-текст в HTML.
    
    Использует расширения:
    - fenced_code: блоки кода с ```
    - tables: таблицы
    - nl2br: переносы строк → <br>
    
    Пример использования:
    {{ ai_feedback|render_markdown }}
    """
    if not value:
        return ""
    
    try:
        html = markdown.markdown(
            str(value),
            extensions=[
                'fenced_code',
                'tables',
                'nl2br',
            ],
            safe_mode=False,
        )
        return mark_safe(html)
    except Exception:
        # Если markdown сломался, вернуть как есть
        return mark_safe(str(value).replace('\n', '<br>'))


@register.filter(name='render_markdown_safe')
def render_markdown_safe(value):
    """
    Безопасная версия с экранированием HTML.
    """
    if not value:
        return ""
    
    try:
        html = markdown.markdown(
            str(value),
            extensions=[
                'fenced_code',
                'tables',
                'nl2br',
            ],
            safe_mode='escape',
        )
        return mark_safe(html)
    except Exception:
        return mark_safe(str(value).replace('\n', '<br>'))
