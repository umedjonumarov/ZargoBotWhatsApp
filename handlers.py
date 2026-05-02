"""
ZargoBot — Mijoz xabarlarini qayta ishlash
"""
import json
import logging
from datetime import datetime
from typing import Dict, Optional

import pytz

import sheets
import whatsapp
import ai
import prompts
from config import (
    SHOP_HOURS_START,
    SHOP_HOURS_END,
    MIN_ORDER_SOMONI,
    LOYALTY_EVERY_N_ORDERS,
    BOT_PHONE,
    ADMIN_PHONE,
)

logger = logging.getLogger(__name__)

TZ = pytz.timezone("Asia/Dushanbe")


def is_after_hours() -> bool:
    """Hozir ish vaqtidan tashqarimi?"""
    now = datetime.now(TZ)
    hour = now.hour
    return hour < SHOP_HOURS_START or hour >= SHOP_HOURS_END


def handle_customer_message(parsed: Dict) -> None:
    """Mijoz xabarini qayta ishlash (asosiy mantiq)"""
    chat_id = parsed["chat_id"]
    sender_number = parsed["sender_number"]

    # 1. Bot o'ziga javob bermasin
    if sender_number == BOT_PHONE:
        return

    # 2. Admin xabari → alohida ishlov
    if sender_number == ADMIN_PHONE:
        from admin import handle_admin_message
        handle_admin_message(parsed)
        return

    # 3. Ovozli yoki rasm xabar
    if parsed["is_voice"] or parsed["is_image"]:
        whatsapp.send_message(
            chat_id,
            "Илтимос, маҳсулот рўйхатини **матн кўринишида** ёзинг — биз ҳозирча овозли хабар ва расм қабул қилмаймиз. 📝",
        )
        return

    # 4. Bo'sh xabar
    if not parsed["is_text"]:
        return

    user_message = parsed["text"]
    phone = sender_number

    try:
        _handle_with_ai(chat_id, phone, user_message, parsed.get("sender_name", ""))
    except Exception as e:
        logger.error(f"Mijoz xabarini ishlash xatosi: {e}", exc_info=True)
        # Mijozga uzr
        whatsapp.send_message(
            chat_id,
            "Кечирасиз, техник носозлик юз берди. Илтимос, бироздан сўнг яна уриниб кўринг. 🙏",
        )
        # Adminga ogohlantirish
        whatsapp.send_to_admin(
            f"⚠️ *БОТ ХАТОЛИГИ*\n"
            f"Вақт: {datetime.now(TZ).strftime('%H:%M %d.%m.%Y')}\n"
            f"Хатолик: {type(e).__name__}: {str(e)[:200]}\n"
            f"Мижоз: +{phone}\n"
            f"Хабар: {user_message[:200]}",
        )


def _handle_with_ai(chat_id: str, phone: str, user_message: str, whatsapp_name: str = "") -> None:
    """AI yordamida mijoz bilan suhbat"""

    # Mijoz ma'lumotlari
    customer = sheets.get_customer(phone)
    is_new_customer = customer is None

    if customer:
        customer_info = (
            f"📱 Телефон: +{customer['phone']}\n"
            f"👤 Исм: {customer.get('name', '?')}\n"
            f"⚧ Жинси: {customer.get('gender', '?')}\n"
            f"🛒 Жами буюртмалар: {customer.get('total_orders', 0)} та\n"
            f"💰 Жами харажат: {customer.get('total_spent', 0)} сомони\n"
            f"📍 Манзил: {customer.get('address', '?')}\n"
        )
        # Oxirgi 3 zakaz
        last_orders = sheets.get_customer_orders(phone)[-3:]
        if last_orders:
            customer_info += "\nОхирги буюртмалар:\n"
            for o in last_orders:
                customer_info += f"  • #{o['number']} — {o.get('items', '')} ({o.get('total', 0)}с)\n"
    else:
        customer_info = (
            f"📱 Телефон: +{phone} (янги мижоз — исмини сўра)\n"
            f"⚠️ WhatsApp профил исми: {whatsapp_name or 'номаълум'}\n"
        )

    # Loyalty: navbatdagi zakaz N-chimi?
    next_order_number = (customer.get("total_orders", 0) + 1) if customer else 1
    is_loyalty = (next_order_number % LOYALTY_EVERY_N_ORDERS == 0)

    # System prompt
    products_text = sheets.format_products_for_ai()
    system_prompt = prompts.build_system_prompt(
        products_text=products_text,
        customer_info=customer_info,
        is_after_hours=is_after_hours(),
        is_loyalty_reward=is_loyalty,
    )

    # AI ga so'rov
    visible_text, metadata = ai.chat(phone, user_message, system_prompt)

    # Javobni yuborish
    if visible_text:
        whatsapp.send_message(chat_id, visible_text)

    # Metadata bo'yicha keyingi ish
    _process_metadata(phone, chat_id, metadata, is_new_customer)


def _process_metadata(phone: str, chat_id: str, metadata: Dict, is_new_customer: bool) -> None:
    """AI qaytargan metadata asosida ish bajarish"""

    if not metadata:
        return

    # Mijoz ma'lumotini saqlash (agar yangi ma'lumotlar bo'lsa)
    if metadata.get("customer_name") and is_new_customer:
        gender = metadata.get("customer_gender") or ai.detect_gender(metadata["customer_name"])
        sheets.save_customer({
            "phone": phone,
            "name": metadata["customer_name"],
            "gender": gender,
            "address": metadata.get("address", ""),
        })
        logger.info(f"Yangi mijoz saqlandi: {metadata['customer_name']} (+{phone})")

    # Eslatmalarni o'chirish
    if metadata.get("wants_stop_reminders"):
        sheets.set_reminder_status(phone, "off")
        logger.info(f"Avtoeslatmalar o'chirildi: +{phone}")

    # Buyurtmani bekor qilish
    if metadata.get("wants_cancel"):
        ai.reset_conversation(phone)
        logger.info(f"Suhbat tozalandi (bekor qilish): +{phone}")
        return

    # Tungi buyurtma
    if metadata.get("night_order") and metadata.get("order_complete"):
        _save_night_order(phone, chat_id, metadata)
        return

    # To'liq tasdiqlangan buyurtma
    if metadata.get("order_complete"):
        _save_confirmed_order(phone, chat_id, metadata)


def _save_night_order(phone: str, chat_id: str, metadata: Dict) -> None:
    """Tungi buyurtmani saqlash"""
    items_text = _format_items(metadata.get("items", []))

    sheets.save_night_order({
        "phone": phone,
        "name": metadata.get("customer_name", ""),
        "address": metadata.get("address", ""),
        "items": items_text,
        "total": metadata.get("total", 0),
    })

    logger.info(f"Tungi buyurtma saqlandi: +{phone}, {metadata.get('total')}с")
    ai.reset_conversation(phone)


def _save_confirmed_order(phone: str, chat_id: str, metadata: Dict) -> None:
    """Tasdiqlangan buyurtmani saqlash va adminga yuborish"""
    items_text = _format_items(metadata.get("items", []))
    total = metadata.get("total", 0)
    name = metadata.get("customer_name", "")
    address = metadata.get("address", "")

    # Sheets'ga saqlash
    result = sheets.save_order({
        "phone": phone,
        "name": name,
        "address": address,
        "items": items_text,
        "total": total,
        "payment": "нақд",
        "status": "қабул қилинди",
    })

    order_number = result.get("number", "?")

    # Mijoz statistikasini yangilash
    customer = sheets.get_customer(phone)
    new_total_orders = (customer.get("total_orders", 0) if customer else 0) + 1
    new_total_spent = (customer.get("total_spent", 0) if customer else 0) + total
    sheets.save_customer({
        "phone": phone,
        "name": name or (customer.get("name") if customer else ""),
        "gender": metadata.get("customer_gender") or (customer.get("gender") if customer else ""),
        "address": address or (customer.get("address") if customer else ""),
        "total_orders": new_total_orders,
        "total_spent": new_total_spent,
        "last_order": datetime.now(TZ).strftime("%Y-%m-%d"),
    })

    # Mijozga tasdiq xabari
    confirm_msg = (
        f"✅ *Буюртмангизни брон қилдик!*\n\n"
        f"📦 Буюртма: *#{order_number}*\n"
        f"💰 Жами: *{total} сомони*\n"
        f"📍 Манзил: {address}\n\n"
        f"📞 Тез орада сиз билан боғланамиз."
    )
    whatsapp.send_message(chat_id, confirm_msg)

    # Adminga xabar
    admin_msg = (
        f"🛒 *ЯНГИ БУЮРТМА!*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Буюртма: *#{order_number}*\n"
        f"👤 {name}\n"
        f"📱 +{phone}\n"
        f"📍 {address}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{items_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Жами: *{total} сомони*\n"
        f"💳 Тўлов: нақд\n"
    )

    # Loyalty mukofoti?
    if new_total_orders % LOYALTY_EVERY_N_ORDERS == 0:
        admin_msg += f"\n🎁 *{LOYALTY_EVERY_N_ORDERS}-БУЮРТМА — 2 та нон ҳадя қўшинг!*"

    whatsapp.send_to_admin(admin_msg)
    logger.info(f"Buyurtma adminga yuborildi: #{order_number}, +{phone}, {total}с")

    # Suhbatni tozalash (yangi zakaz uchun)
    ai.reset_conversation(phone)


def _format_items(items: list) -> str:
    """Mahsulotlar ro'yxatini matn ko'rinishida"""
    if not items:
        return "(маҳсулотлар йўқ)"
    lines = []
    for item in items:
        name = item.get("name", "?")
        qty = item.get("qty", 1)
        price = item.get("price", 0)
        lines.append(f"• {name} x{qty} — {price}с")
    return "\n".join(lines)
