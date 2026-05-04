from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import TYPE_CHECKING

from django.conf import settings
from django.db.models import Sum

if TYPE_CHECKING:
    from ..models import Order


FREE_MODEL = "open-mistral-nemo"

ORDER_SYSTEM_PROMPT = """Ты аналитик эффективности фриланс-заказов.
Верни только JSON вида {"rating": int, "feedback": string}.
Оценка от 1 до 5. Feedback пиши на русском, в Markdown, коротко и практично."""

PROFILE_SYSTEM_PROMPT = """Ты бизнес-аналитик для фрилансера.
Дай рекомендации на русском в Markdown: краткая оценка, 3 совета по доходу, 3 совета по времени, итоговый фокус на месяц."""


def _money(value) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal("0")


def _local_order_analysis(order: "Order", reason: str = "") -> dict:
    hours = _money(order.time_spent_hours)
    net = _money(order.net_amount)
    hourly = net / hours if hours > 0 else Decimal("0")

    if hours <= 0:
        rating = 3
        verdict = "Недостаточно данных по времени"
    elif hourly >= 2500:
        rating = 5
        verdict = "Отличный заказ"
    elif hourly >= 1500:
        rating = 4
        verdict = "Хороший заказ"
    elif hourly >= 800:
        rating = 3
        verdict = "Средний заказ"
    elif hourly >= 400:
        rating = 2
        verdict = "Низкая эффективность"
    else:
        rating = 1
        verdict = "Слабая экономика заказа"

    note = f"\n\n> Mistral недоступен: {reason}" if reason else ""
    feedback = f"""## {verdict}

**Чистый доход:** {net:.2f} ₽  
**Время:** {hours:.2f} ч  
**Ставка:** {hourly:.0f} ₽/ч

- Проверьте, покрывает ли ставка вашу целевую норму.
- Если заказ похож на повторяемый тип работ, используйте его как шаблон для будущих оценок.
- Для следующего похожего заказа зафиксируйте минимальную цену до старта.{note}"""
    return {"rating": rating, "feedback": feedback}


def _local_profile_analysis(stats: dict, reason: str = "") -> str:
    net = _money(stats.get("net"))
    last_month_net = _money(stats.get("last_month_net"))
    target = _money(stats.get("target_income"))
    avg_rate = _money(stats.get("avg_rate"))
    completed_rate = stats.get("completed_rate", 0) or 0
    gap = max(target - last_month_net, Decimal("0"))
    note = f"\n\n> Mistral недоступен: {reason}" if reason else ""

    return f"""## Короткий разбор

За всё время чистый доход: **{net:.2f} ₽**. За последние 30 дней: **{last_month_net:.2f} ₽**. Средняя ставка: **{avg_rate:.2f} ₽/ч**.

### Что улучшить

- Поднимайте цену на типовые задачи, если ставка ниже целевой.
- Отмечайте теги у заказов: через 10-15 заказов будет проще увидеть самые прибыльные направления.
- Следите за комиссиями платформ и переводите повторных клиентов на площадки с меньшими потерями.

### Фокус на месяц

- До цели осталось примерно **{gap:.2f} ₽**.
- Доведите завершение заказов до стабильных **85-90%**. Сейчас: **{completed_rate:.1f}%**.
- Выберите 1-2 категории задач, где ставка выше средней, и делайте на них упор.{note}"""


class MistralService:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or self._get_api_key()
        self.client = None
        if self.api_key:
            self.client = self._make_client(self.api_key)

    def _make_client(self, api_key: str):
        from mistralai.client import Mistral

        return Mistral(api_key=api_key)

    def _get_api_key(self) -> str | None:
        key = getattr(settings, "MISTRAL_API_KEY", None)
        return key.strip() if key and key.strip() else None

    def _get_api_key_for_user(self, user) -> str | None:
        key = self._get_api_key()
        if key:
            return key
        if user is None:
            return None
        try:
            profile_key = user.profile.mistral_api_key_encrypted
            return profile_key.strip() if profile_key and profile_key.strip() else None
        except Exception:
            return None

    def _order_messages(self, order: "Order", user=None) -> list[dict]:
        hours = _money(order.time_spent_hours)
        hourly = _money(order.net_amount) / hours if hours > 0 else Decimal("0")
        total_earned = Decimal("0")
        if user is not None:
            try:
                from ..models import Order as OrderModel

                total_earned = OrderModel.objects.filter(status=OrderModel.Status.PAID).aggregate(total=Sum("net_amount"))["total"] or Decimal("0")
            except Exception:
                pass

        content = f"""Заказ:
- Название: {order.title}
- Платформа: {order.platform.name if order.platform else "—"}
- Статус: {order.get_status_display()}
- Валово: {order.gross_amount} ₽
- На руки: {order.net_amount} ₽
- Комиссия: {order.commission_amount} ₽
- Время: {hours:.2f} ч
- Ставка: {hourly:.0f} ₽/ч
- Описание: {order.description or "—"}

Контекст:
- Оплачено всего: {total_earned} ₽"""
        return [{"role": "system", "content": ORDER_SYSTEM_PROMPT}, {"role": "user", "content": content}]

    def _extract_json(self, text: str) -> dict | None:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1).strip()
        else:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                text = text[start : end + 1]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def evaluate_order(self, order: "Order", user=None) -> dict:
        api_key = self._get_api_key_for_user(user) if user else self.api_key
        if not api_key:
            return _local_order_analysis(order, "API-ключ не настроен")
        try:
            if not self.client:
                self.client = self._make_client(api_key)
            response = self.client.chat.complete(
                model=FREE_MODEL,
                messages=self._order_messages(order, user),
                temperature=0.25,
                max_tokens=650,
                response_format={"type": "json_object"},
            )
            text = str(response.choices[0].message.content or "").strip()
            data = self._extract_json(text) or {}
            rating = int(data.get("rating") or 0)
            feedback = str(data.get("feedback") or "").strip()
            if not 1 <= rating <= 5 or not feedback:
                return _local_order_analysis(order, "ответ AI не удалось разобрать")
            return {"rating": rating, "feedback": feedback}
        except Exception as exc:
            return _local_order_analysis(order, str(exc)[:140])


def evaluate_order(order: "Order", user=None) -> dict:
    return MistralService().evaluate_order(order, user=user)


def resolve_mistral_key_for_user(user) -> str:
    return MistralService()._get_api_key_for_user(user) or ""


def analyze_freelance_stats(stats: dict, user=None) -> str:
    service = MistralService()
    api_key = service._get_api_key_for_user(user)
    if not api_key:
        return _local_profile_analysis(stats, "API-ключ не настроен")

    prompt = f"""Статистика:
- Чистый доход всего: {stats.get("net")}
- Средняя ставка: {stats.get("avg_rate")}
- Потери на комиссии: {stats.get("comm_loss")}
- Часы работы: {stats.get("hours_total")}
- Платформы: {stats.get("platforms")}
- Завершение заказов: {stats.get("completed_rate", 0):.1f}%
- Доход за 30 дней: {stats.get("last_month_net")}
- Заказов за 30 дней: {stats.get("last_month_orders")}
- Цель в месяц: {stats.get("target_income")}
- Стаж: {stats.get("days_since_start", 0)} дней"""

    try:
        if not service.client:
            service.client = service._make_client(api_key)
        response = service.client.chat.complete(
            model=FREE_MODEL,
            messages=[{"role": "system", "content": PROFILE_SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            temperature=0.35,
            max_tokens=1000,
        )
        text = str(response.choices[0].message.content or "").strip()
        return text or _local_profile_analysis(stats, "пустой ответ AI")
    except Exception as exc:
        return _local_profile_analysis(stats, str(exc)[:140])
