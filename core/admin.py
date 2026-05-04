from django.contrib import admin

from .models import AiLog, Order, Platform, Profile


@admin.register(AiLog)
class AiLogAdmin(admin.ModelAdmin):
    list_display = ("order", "status", "created_at", "short_prompt")
    list_filter = ("status", "created_at")
    search_fields = ("order__title", "prompt", "response", "error_message")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"

    def short_prompt(self, obj: AiLog) -> str:
        return obj.prompt[:100] + "..." if len(obj.prompt) > 100 else obj.prompt

    short_prompt.short_description = "Промпт"


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "start_date",
        "first_order_date",
        "timezone",
        "target_monthly_income",
        "has_ai_insights",
    )
    search_fields = (
        "user__username",
        "user__email",
        "skills",
        "mistral_api_key_encrypted",
        "ai_insights",
    )
    list_filter = ("timezone", "start_date", "first_order_date")
    readonly_fields = ("ai_insights_preview",)

    def has_ai_insights(self, obj: Profile) -> bool:
        return bool(obj.ai_insights and obj.ai_insights.strip())

    has_ai_insights.boolean = True
    has_ai_insights.short_description = "AI-рекомендации"

    def ai_insights_preview(self, obj: Profile) -> str:
        if obj.ai_insights:
            return obj.ai_insights[:500] + ("..." if len(obj.ai_insights) > 500 else "")
        return "Нет рекомендаций"

    ai_insights_preview.short_description = "AI-рекомендации (превью)"


@admin.register(Platform)
class PlatformAdmin(admin.ModelAdmin):
    list_display = ("name", "commission_rate", "website", "is_active", "color")
    search_fields = ("name", "website")
    list_filter = ("is_active",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "platform",
        "gross_amount",
        "commission_amount",
        "net_amount",
        "status",
        "completed_at",
    )
    search_fields = (
        "title",
        "description",
        "tags",
        "platform__name",
        "ai_feedback",
    )
    list_filter = (
        "status",
        "platform",
        "completed_at",
        "ai_rating",
    )
    autocomplete_fields = ("platform",)
    readonly_fields = ("commission_amount", "net_amount")
