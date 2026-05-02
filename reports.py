"""
ZargoBot — Hisobot generatsiyasi
"""
import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import List, Dict

import pytz

import sheets
from config import SHOP_NAME

logger = logging.getLogger(__name__)

TZ = pytz.timezone("Asia/Dushanbe")


def daily_report() -> str:
    """Bugungi zakazlar ro'yxati"""
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    orders = [o for o in sheets.get_all_orders() if _date_only(o.get("date")) == today]

    if not orders:
        return f"📊 *БУГУНГИ БУЮРТМАЛАР* ({today})\n\nБугун ҳали буюртма йўқ."

    total = sum(o.get("total", 0) for o in orders)
    msg = [f"📊 *БУГУНГИ БУЮРТМАЛАР* ({today})\n"]
    msg.append(f"🛒 Жами: *{len(orders)} та буюртма*")
    msg.append(f"💰 Тушум: *{total} сомони*")
    msg.append("─" * 30)

    for o in orders:
        msg.append(
            f"#{o['number']} — {o.get('name', '?')} (+{o.get('phone', '?')})\n"
            f"  {o.get('items', '')}\n"
            f"  💰 {o.get('total', 0)}с — {o.get('status', '?')}"
        )

    return "\n\n".join(msg)


def weekly_report() -> str:
    """O'tgan haftaning hisoboti"""
    now = datetime.now(TZ)
    week_ago = now - timedelta(days=7)

    orders = [
        o for o in sheets.get_all_orders()
        if _date_only(o.get("date")) and _date_only(o.get("date")) >= week_ago.strftime("%Y-%m-%d")
    ]

    if not orders:
        return f"📊 *ҲАФТАЛИК ҲИСОБОТ*\n\nҲафта мобайнида буюртма йўқ."

    return _generate_period_report("ҲАФТАЛИК ҲИСОБОТ", orders, days=7)


def monthly_report() -> str:
    """O'tgan oyning hisoboti"""
    now = datetime.now(TZ)
    month_ago = now - timedelta(days=30)

    orders = [
        o for o in sheets.get_all_orders()
        if _date_only(o.get("date")) and _date_only(o.get("date")) >= month_ago.strftime("%Y-%m-%d")
    ]

    if not orders:
        return f"📊 *ОЙЛИК ҲИСОБОТ*\n\nОй мобайнида буюртма йўқ."

    return _generate_period_report("ОЙЛИК ҲИСОБОТ", orders, days=30)


def customer_report(phone_query: str) -> str:
    """Mijoz tarixi"""
    # Telefon raqamini tozalash
    digits = "".join(c for c in phone_query if c.isdigit())
    if not digits:
        return "❌ Телефон рақамини тўғри киритинг. Масалан: `мижоз +992901234567`"

    # Mijozni qidirish (oxirgi raqamlar bo'yicha)
    customers = sheets.get_all_customers()
    matches = [c for c in customers if str(c.get("phone", "")).endswith(digits[-7:])]

    if not matches:
        return f"❌ +{digits} рақамли мижоз топилмади."

    customer = matches[0]
    phone = customer["phone"]
    orders = sheets.get_customer_orders(phone)

    msg = [
        f"👤 *МИЖОЗ МАЪЛУМОТЛАРИ*",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"📱 Телефон: +{phone}",
        f"👤 Исм: {customer.get('name', '?')}",
        f"⚧ Жинси: {customer.get('gender', '?')}",
        f"📅 Биринчи буюртма: {customer.get('first_order', '?')}",
        f"📅 Охирги буюртма: {customer.get('last_order', '?')}",
        f"🛒 Жами буюртмалар: *{customer.get('total_orders', 0)} та*",
        f"💰 Жами харажат: *{customer.get('total_spent', 0)} сомони*",
        f"📍 Манзил: {customer.get('address', '?')}",
        f"━━━━━━━━━━━━━━━━━━━━",
    ]

    if orders:
        msg.append(f"\n📜 *ОХИРГИ {min(5, len(orders))} БУЮРТМА:*")
        for o in orders[-5:]:
            msg.append(
                f"\n#{o['number']} ({_date_only(o.get('date', ''))}) — {o.get('total', 0)}с"
                f"\n  {o.get('items', '')}"
            )

    return "\n".join(msg)


def _generate_period_report(title: str, orders: List[Dict], days: int) -> str:
    """Davr uchun hisobot yaratish"""
    if not orders:
        return f"📊 *{title}*\n\nБуюртма йўқ."

    total_revenue = sum(o.get("total", 0) for o in orders)
    avg_check = total_revenue / len(orders) if orders else 0

    # Mijozlar
    unique_phones = set(o.get("phone") for o in orders)
    customer_orders = Counter(o.get("phone") for o in orders)

    # Yangi va qaytgan mijozlar
    all_orders = sheets.get_all_orders()
    period_phones = {o.get("phone") for o in orders}
    earlier_phones = {o.get("phone") for o in all_orders if o not in orders}
    new_customers = period_phones - earlier_phones
    returning_customers = period_phones & earlier_phones

    # Eng faol mijozlar
    top_customers = customer_orders.most_common(5)

    # Eng ko'p sotilgan mahsulotlar
    item_counter = Counter()
    for o in orders:
        items_text = o.get("items", "")
        # Oddiy parser: "• Нон x2 — 6с" qatorlardan nomni olish
        for line in items_text.split("\n"):
            line = line.strip().lstrip("•").strip()
            if not line:
                continue
            # "Нон x2 — 6с" → "Нон"
            parts = line.split(" x")
            if len(parts) >= 2:
                name = parts[0].strip()
                try:
                    qty = int(parts[1].split(" ")[0])
                    item_counter[name] += qty
                except (ValueError, IndexError):
                    item_counter[name] += 1

    top_items = item_counter.most_common(5)

    msg = [
        f"📊 *{title}*\n",
        f"🛒 Жами буюртмалар: *{len(orders)} та*",
        f"💰 Жами тушум: *{int(total_revenue)} сомони*",
        f"📈 Ўртача чек: *{int(avg_check)} сомони*",
        f"👥 Мижозлар: *{len(unique_phones)} та*",
        f"🆕 Янги мижозлар: *{len(new_customers)} та*",
        f"🔄 Қайтган мижозлар: *{len(returning_customers)} та*",
    ]

    if top_customers:
        msg.append("\n🏆 *ЭНГ ФАОЛ МИЖОЗЛАР:*")
        all_customers = {c["phone"]: c for c in sheets.get_all_customers()}
        for phone, count in top_customers:
            cust = all_customers.get(phone, {})
            name = cust.get("name", "?")
            spent = sum(o.get("total", 0) for o in orders if o.get("phone") == phone)
            msg.append(f"• {name} (+{phone}) — {count} та / {int(spent)}с")

    if top_items:
        msg.append("\n🥕 *ЭНГ КЎП СОТИЛГАН:*")
        for name, qty in top_items:
            msg.append(f"• {name} — {qty} та")

    return "\n".join(msg)


def _date_only(date_str: str) -> str:
    """ISO sanani YYYY-MM-DD ga aylantirish"""
    if not date_str:
        return ""
    if "T" in date_str:
        return date_str.split("T")[0]
    if " " in date_str:
        return date_str.split(" ")[0]
    return date_str[:10]
