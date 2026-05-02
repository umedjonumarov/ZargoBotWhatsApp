"""
ZargoBot — Avtomatik eslatmalar (cron task'lar)
Bu funksiyalar tashqi cron service (cron-job.org) tomonidan chaqiriladi.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict

import pytz

import sheets
import whatsapp
import prompts
import ai
import reports
from config import (
    ADMIN_CHAT_ID,
    REMINDER_BREAKFAST_DAY,
    REMINDER_REORDER_DAY,
    REMINDER_LOYALTY_DAY,
)

logger = logging.getLogger(__name__)

TZ = pytz.timezone("Asia/Dushanbe")


def send_morning_night_orders() -> Dict:
    """Ertalab 8:00 — tungi buyurtmalar uchun mijozlarga eslatma"""
    night_orders = sheets.get_night_orders()
    sent_count = 0

    for order in night_orders:
        phone = order["phone"]
        name = order.get("name", "Мижоз")
        items = order.get("items", "")
        total = order.get("total", 0)

        # Mijoz ismidan honorific yasash
        customer = sheets.get_customer(phone)
        gender = customer.get("gender", "эркак") if customer else "эркак"
        full_name = ai.honorific(name, gender) if name else "Мижоз"

        text = prompts.night_reminder_prompt(full_name, items, total)
        chat_id = whatsapp.chat_id_from_phone(phone)

        result = whatsapp.send_message(chat_id, text)
        if result:
            sent_count += 1

    logger.info(f"Tungi buyurtma eslatmalari: {sent_count}/{len(night_orders)}")
    return {"total": len(night_orders), "sent": sent_count}


def send_breakfast_reminders() -> Dict:
    """3-kun 20:00 — nonushta mahsulotlari haqida eslatma"""
    target_date = (datetime.now(TZ) - timedelta(days=REMINDER_BREAKFAST_DAY)).strftime("%Y-%m-%d")
    breakfast_categories = ("Нонушта",)

    # Mahsulotlar — kategoriya bo'yicha
    products = sheets.get_products()
    breakfast_names = {p["name"] for p in products if p.get("category") in breakfast_categories}

    sent_count = 0
    candidates = _customers_with_recent_order(target_date, only_categories=breakfast_names)

    for cust, order in candidates:
        if not _reminders_enabled(cust):
            continue

        # Nonushta mahsulotlari sotib olganmi?
        items_text = order.get("items", "")
        bought_breakfast = [
            name for name in breakfast_names
            if name in items_text
        ]

        if not bought_breakfast:
            continue

        full_name = ai.honorific(cust.get("name", ""), cust.get("gender", "эркак"))
        text = prompts.breakfast_reminder_prompt(full_name, bought_breakfast)

        chat_id = whatsapp.chat_id_from_phone(cust["phone"])
        result = whatsapp.send_message(chat_id, text)
        if result:
            sent_count += 1

    logger.info(f"Nonushta eslatmalari: {sent_count}")
    return {"sent": sent_count}


def send_reorder_reminders() -> Dict:
    """4-kun 15:00 — umumiy re-order eslatma"""
    target_date = (datetime.now(TZ) - timedelta(days=REMINDER_REORDER_DAY)).strftime("%Y-%m-%d")

    # Mijozlar: oxirgi zakazi aniq target_date da, undan keyin zakaz yo'q
    candidates = _customers_with_no_order_since(target_date)

    sent_count = 0
    for cust, last_order in candidates:
        if not _reminders_enabled(cust):
            continue

        full_name = ai.honorific(cust.get("name", ""), cust.get("gender", "эркак"))
        items_text = last_order.get("items", "(охирги буюртмадан)")

        text = prompts.reorder_reminder_prompt(full_name, items_text)
        chat_id = whatsapp.chat_id_from_phone(cust["phone"])
        result = whatsapp.send_message(chat_id, text)
        if result:
            sent_count += 1

    logger.info(f"Re-order eslatmalari: {sent_count}")
    return {"sent": sent_count}


def send_loyalty_recovery_reminders() -> Dict:
    """14-kun 12:00 — sog'indik eslatmasi"""
    target_date = (datetime.now(TZ) - timedelta(days=REMINDER_LOYALTY_DAY)).strftime("%Y-%m-%d")
    candidates = _customers_with_no_order_since(target_date)

    sent_count = 0
    for cust, _ in candidates:
        if not _reminders_enabled(cust):
            continue

        # Faqat 14-kun chegarasidagi mijozlarga (oldinroq emas)
        last_order_date = cust.get("last_order", "")
        if last_order_date != target_date:
            continue

        full_name = ai.honorific(cust.get("name", ""), cust.get("gender", "эркак"))
        text = prompts.loyalty_recovery_prompt(full_name)
        chat_id = whatsapp.chat_id_from_phone(cust["phone"])
        result = whatsapp.send_message(chat_id, text)
        if result:
            sent_count += 1

    logger.info(f"Sog'indik eslatmalari: {sent_count}")
    return {"sent": sent_count}


def send_weekly_report() -> Dict:
    """Har dushanba ertalab — admin'ga haftalik hisobot"""
    report = reports.weekly_report()
    whatsapp.send_to_admin(f"📅 *АВТО ҲАФТАЛИК ҲИСОБОТ*\n\n{report}")
    return {"sent": True}


def send_monthly_report() -> Dict:
    """Har oy 1-sanasi — admin'ga oylik hisobot"""
    report = reports.monthly_report()
    whatsapp.send_to_admin(f"📅 *АВТО ОЙЛИК ҲИСОБОТ*\n\n{report}")
    return {"sent": True}


# === YORDAMCHI ===

def _customers_with_recent_order(target_date: str, only_categories: set = None):
    """target_date da zakaz qilgan, lekin bugundan oldin yangi zakazi yo'q mijozlar"""
    all_orders = sheets.get_all_orders()
    all_customers = {c["phone"]: c for c in sheets.get_all_customers()}

    today = datetime.now(TZ).strftime("%Y-%m-%d")
    result = []

    for cust_phone, cust in all_customers.items():
        # Mijozning oxirgi zakazi aynan target_date dami?
        cust_orders = [o for o in all_orders if str(o.get("phone")) == str(cust_phone)]
        if not cust_orders:
            continue

        cust_orders.sort(key=lambda o: o.get("date", ""))
        last_order = cust_orders[-1]
        last_date = (last_order.get("date") or "")[:10]

        if last_date == target_date:
            result.append((cust, last_order))

    return result


def _customers_with_no_order_since(target_date: str):
    """Oxirgi zakazi target_date'da bo'lgan mijozlar (undan keyin yangi yo'q)"""
    return _customers_with_recent_order(target_date)


def _reminders_enabled(customer: Dict) -> bool:
    """Mijozda avtoeslatma yoqilganmi?"""
    val = customer.get("reminders", True)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() != "off"
    return True
