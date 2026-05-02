"""
ZargoBot — Admin buyruqlari
"""
import logging
from datetime import datetime
from typing import Dict

import pytz

import sheets
import whatsapp
import reports
from config import ADMIN_CHAT_ID

logger = logging.getLogger(__name__)

TZ = pytz.timezone("Asia/Dushanbe")

# In-memory bot holati
_bot_active = True


def is_bot_active() -> bool:
    return _bot_active


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

    elif text in ("стоп", "stop", "тўхтат", "тухтат"):
        global _bot_active
        _bot_active = False
        whatsapp.send_message(
            chat_id,
            "⏸ *Бот вақтинча тўхтатилди.*\nҚайта ишга тушириш учун: *старт*",
        )
        logger.info("Bot to'xtatildi (admin)")

    elif text in ("старт", "start", "ишга тушир", "yoq"):
        _bot_active = True
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
        # Admin oddiy xabar yozsa — ehtiyot bo'lib javob beramiz
        whatsapp.send_message(
            chat_id,
            "Буйруқни танимадим. Мумкин буйруқлар учун *ёрдам* деб ёзинг.",
        )
