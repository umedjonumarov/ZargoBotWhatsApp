"""
ZargoBot — Admin buyruqlari
YANGILANDI: _bot_active in-memory emas, Sheets'da saqlanadi
YANGI: Status o'zgartirish buyruqlari qo'shildi
"""
import logging
from datetime import datetime
from typing import Dict

import pytz

import sheets
import whatsapp
import reports

logger = logging.getLogger(__name__)

TZ = pytz.timezone("Asia/Dushanbe")


def is_bot_active() -> bool:
    """Bot holatini Sheets'dan olish"""
    return sheets.get_bot_status()


def set_bot_active(active: bool) -> None:
    """Bot holatini Sheets'da o'zgartirish"""
    sheets.set_bot_status(active)


def handle_admin_message(parsed: Dict) -> None:
    """Admin xabarini qayta ishlash"""
    text = parsed["text"].strip().lower()
    chat_id = parsed["chat_id"]

    # Buyruqni aniqlash
    if text in ("ҳисобот", "хисобот", "hisobot", "отчет", "ҳисобот ойлик"):
        report = reports.monthly_report()
        whatsapp.send_message(chat_id, report)

    elif text in ("ҳафталик", "хафталик", "haftalik", "недельный"):
        report = reports.weekly_report()
        whatsapp.send_message(chat_id, report)

    elif text in ("бугун", "сегодня", "bugun"):
        report = reports.daily_report()
        whatsapp.send_message(chat_id, report)

    elif text.startswith("мижоз ") or text.startswith("mijoz "):
        phone_query = text.split(" ", 1)[1].strip()
        report = reports.customer_report(phone_query)
        whatsapp.send_message(chat_id, report)

    # === YANGI: Status o'zgartirish ===
    elif text.startswith("статус ") or text.startswith("status "):
        parts = text.split(" ", 2)
        if len(parts) >= 3:
            order_number = parts[1].strip()
            new_status = parts[2].strip()
            result = sheets.update_order_status(order_number, new_status)
            if result.get("updated"):
                whatsapp.send_message(chat_id, f"✅ #{order_number} статуси: *{new_status}*")
                # Mijozga ham xabar
                order = sheets.get_order(order_number)
                if order:
                    customer_phone = order.get("phone")
                    if customer_phone:
                        status_messages = {
                            "тайёрланмоқда": "📦 Буюртмангиз тайёрланмоқда...",
                            "йўлда": "🚚 Буюртмангиз йўлда! Тез орада етиб келади.",
                            "етказилди": "✅ Буюртмангиз етказилди! Раҳмат!",
                            "бекор": "❌ Буюртмангиз бекор қилинди."
                        }
                        msg = status_messages.get(new_status, f"Буюртма статуси: {new_status}")
                        whatsapp.send_message(whatsapp.chat_id_from_phone(customer_phone), msg)
            else:
                whatsapp.send_message(chat_id, f"❌ #{order_number} топилмади")

    elif text in ("стоп", "stop", "тўхтат", "тухтат"):
        set_bot_active(False)
        whatsapp.send_message(
            chat_id,
            "⏸ *Бот вақтинча тўхтатилди.*\nҚайта ишга тушириш учун: *старт*",
        )
        logger.info("Bot to'xtatildi (admin)")

    elif text in ("старт", "start", "ишга тушир", "yoq"):
        set_bot_active(True)
        whatsapp.send_message(
            chat_id,
            "▶️ *Бот қайта ишга тушди.*\nМижозлар билан ишлашни давом эттирамиз.",
        )
        logger.info("Bot ishga tushirildi (admin)")

    elif text in ("ёрдам", "help", "yordam", "помощь", "/help"):
        help_text = (
            "🤖 *ZargoBot — Admin буйруқлари*\n\n"
            "📊 *Ҳисоботлар:*\n"
            "• `ҳисобот` — Ойлик ҳисобот\n"
            "• `ҳафталик` — Ҳафталик ҳисобот\n"
            "• `бугун` — Бугунги буюртмалар\n"
            "• `мижоз +992XXX` — Мижоз тарихи\n\n"
            "📦 *Буюртма бошқаруви:*\n"
            "• `статус 123 тайёрланмоқда` — Статус ўзгартириш\n"
            "• `статус 123 йўлда`\n"
            "• `статус 123 етказилди`\n"
            "• `статус 123 бекор`\n\n"
            "⚙️ *Бошқарув:*\n"
            "• `стоп` — Ботни вақтинча тўхтатиш\n"
            "• `старт` — Қайта ишга тушириш\n"
            "• `ёрдам` — Шу хабар\n\n"
            "📅 *Авто:*\n"
            "• Ҳар куни 8:00 — тунги буюртмаларни юбориш\n"
            "• 3-кун 20:00 — нонушта эслатмаси\n"
            "• 4-кун 15:00 — re-order эслатмаси\n"
            "• 14-кун 12:00 — sog'индик эслатмаси\n"
            "• Ҳар душанба эрталаб — ҳафталик ҳисобот\n"
            "• Ҳар ой 1-сана эрталаб — ойлик ҳисобот\n"
        )
        whatsapp.send_message(chat_id, help_text)

    else:
        whatsapp.send_message(
            chat_id,
            "Буйруқни танимадим. Мумкин буйруқлар учун *ёрдам* деб ёзинг.",
        )