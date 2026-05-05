"""
ZargoBot — Mijoz xabarlarini qayta ishlash
Server-side cart + intent-based AI parsing
"""
import logging
from datetime import datetime
from typing import Dict, Optional

import pytz

import sheets
import whatsapp
import ai
import parser as p
import prompts
import cart as cart_mod
from cart import Cart, CartItem
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
    """Mijoz xabarini qayta ishlash (asosiy entry point)"""
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
        whatsapp.send_message(chat_id, prompts.voice_image_response())
        return

    # 4. Bo'sh xabar
    if not parsed["is_text"]:
        return

    user_message = parsed["text"]
    phone = sender_number

    try:
        _process(chat_id, phone, user_message)
    except Exception as e:
        logger.error(f"Xato: {e}", exc_info=True)
        whatsapp.send_message(chat_id, prompts.technical_error())
        try:
            whatsapp.send_to_admin(
                f"⚠️ *БОТ ХАТОЛИГИ*\n"
                f"Вақт: {datetime.now(TZ).strftime('%H:%M %d.%m.%Y')}\n"
                f"Хатолик: {type(e).__name__}: {str(e)[:200]}\n"
                f"Мижоз: +{phone}\n"
                f"Хабар: {user_message[:200]}",
            )
        except Exception:
            pass


def _process(chat_id: str, phone: str, user_message: str) -> None:
    """Asosiy mantiq"""
    # Mijoz va korzina
    customer = sheets.get_customer(phone)
    cart = cart_mod.get_cart(phone)

    # Korzina mijozning ma'lumotlarini saqlasin
    if customer and not cart.customer_name:
        cart.customer_name = customer.get("name")
        cart.customer_gender = customer.get("gender", "эркак")
        if customer.get("address") and not cart.address:
            cart.address = customer["address"]

    # === BIRINCHI XABAR (yangi mijoz) ===
    is_new = customer is None
    is_first_message = is_new and not cart.customer_name

    if is_first_message:
        # AI dan intent parse qilamiz — agar ism aytsa qabul qilamiz
        intent_data = ai.parse_intent(user_message)
        intent = intent_data.get("intent")

        if intent == "provide_name" and intent_data.get("name"):
            _save_name_and_continue(chat_id, phone, intent_data["name"], cart)
        else:
            # Aks holda salomlashib, ismini so'raymiz
            whatsapp.send_message(chat_id, prompts.greeting_new_customer())
        return

    # === AI DAN INTENT OLISH ===
    context_hint = _build_context_hint(cart)
    intent_data = ai.parse_intent(user_message, context_hint, _products_menu_for_ai())
    intent = intent_data.get("intent", "unclear")

    logger.info(f"+{phone}: intent={intent}, msg={user_message[:80]}")

    # === INTENT BO'YICHA AMAL ===

    if intent == "greeting":
        _handle_greeting(chat_id, cart, customer)

    elif intent == "provide_name":
        name = intent_data.get("name")
        if name:
            _save_name_and_continue(chat_id, phone, name, cart)
        else:
            whatsapp.send_message(chat_id, prompts.greeting_new_customer())

    elif intent == "menu":
        products_text = sheets.format_products_for_ai()
        whatsapp.send_message(chat_id, prompts.menu_text(products_text))

    elif intent == "add_by_qty":
        _handle_add_by_qty(chat_id, cart, intent_data)

    elif intent == "add_by_money":
        _handle_add_by_money(chat_id, cart, intent_data)

    elif intent == "view_cart":
        _handle_view_cart(chat_id, cart)

    elif intent == "remove":
        _handle_remove(chat_id, cart, intent_data)

    elif intent == "set_address":
        _handle_address(chat_id, cart, intent_data)

    elif intent == "confirm_phone_yes":
        _handle_phone_confirm(chat_id, phone, cart, use_whatsapp=True)

    elif intent == "provide_phone":
        _handle_phone_confirm(chat_id, phone, cart, raw_phone=intent_data.get("phone"))

    elif intent == "confirm_order":
        _handle_order_confirm(chat_id, phone, cart, customer)

    elif intent == "proceed":
        _handle_proceed(chat_id, phone, cart)

    elif intent == "cancel_order":
        _handle_cancel(chat_id, phone, cart)

    elif intent == "night_order_yes":
        _handle_night_order_yes(chat_id, phone, cart)

    elif intent == "night_order_no":
        whatsapp.send_message(chat_id, "Тушунарли. Иш вақтимиз бошланганда яна ёзинг! 😊")
        cart_mod.reset_cart(phone)

    elif intent == "stop_reminders":
        sheets.set_reminder_status(phone, "off")
        whatsapp.send_message(chat_id, prompts.stop_reminders_confirmed())

    elif intent == "ask_question":
        whatsapp.send_message(chat_id, prompts.shop_info())

    else:  # unclear
        name_part = ""
        if cart.customer_name:
            name_part = ai.honorific(cart.customer_name, cart.customer_gender or "эркак")
        whatsapp.send_message(chat_id, prompts.unclear_response(name_part))


# =========================================================================
# AMAL FUNKSIYALARI
# =========================================================================

def _save_name_and_continue(chat_id: str, phone: str, name: str, cart: Cart) -> None:
    """Mijoz ismini saqlash"""
    gender = ai.detect_gender(name)
    cart.customer_name = name
    cart.customer_gender = gender

    sheets.save_customer({
        "phone": phone,
        "name": name,
        "gender": gender,
    })

    whatsapp.send_message(chat_id, prompts.name_received(name, gender))


def _handle_greeting(chat_id: str, cart: Cart, customer: Optional[Dict]) -> None:
    """Salomlashish — agar suhbat o'rtasida bo'lsa, kontekstni saqlaydi"""
    if cart.is_empty() and not cart.address:
        # Yangi suhbat
        if customer:
            whatsapp.send_message(
                chat_id,
                prompts.greeting_returning_customer(
                    customer.get("name", "Мижоз"),
                    customer.get("gender", "эркак"),
                ),
            )
        else:
            whatsapp.send_message(chat_id, prompts.greeting_new_customer())
    else:
        # Suhbat o'rtasida — kontekstni davom ettiramiz
        _resume_flow(chat_id, cart)


def _resume_flow(chat_id: str, cart: Cart) -> None:
    """Korzina dolzarb — qaysi qadamda turganimizni eslatamiz"""
    name = ai.honorific(cart.customer_name or "", cart.customer_gender or "эркак")
    if not cart.address:
        whatsapp.send_message(
            chat_id,
            f"{name}, {prompts.address_request()}",
        )
    elif not cart.confirmed_phone:
        # Telefon kutamiz
        whatsapp.send_message(
            chat_id,
            f"{name}, илтимос телефон рақамингизни тасдиқланг.",
        )
    else:
        # Tasdiqlash kutamiz
        _ask_confirmation(chat_id, cart)


def _handle_add_by_qty(chat_id: str, cart: Cart, intent_data: Dict) -> None:
    """Aniq miqdor (10 dona, 0.5 kg) bo'yicha qo'shish"""
    products = intent_data.get("products", [])
    money_products = intent_data.get("money_products", [])

    added_messages = []
    errors = []

    for prod in products:
        item, err = p.add_by_quantity(
            prod.get("name", ""),
            float(prod.get("qty", 0)),
            prod.get("unit", "")
        )
        if item:
            cart.add_item(item)
            added_messages.append(
                f"✅ *{item.short_name()}* — {item.display_qty()} ({item.display_price()})"
            )
        elif err:
            errors.append(err)

    # Bir xabarda ham pul, ham aniq bo'lishi mumkin
    for prod in money_products:
        item, err, alt = p.add_by_money(
            prod.get("name", ""),
            float(prod.get("money", 0))
        )
        if item:
            cart.add_item(item)
            added_messages.append(
                f"✅ *{item.short_name()}* — {item.display_qty()} ({item.display_price()})"
            )
            if alt:
                added_messages.append(
                    f"💡 Ёки *{alt['qty']:g} {alt['unit']}* ({p.format_money(alt['price'])}) олсангиз бутунроқ — алмаштирайми?"
                )
        elif err:
            errors.append(err)

    # Hech narsa qo'shilmadi
    if not added_messages and not errors:
        whatsapp.send_message(chat_id, prompts.unclear_response())
        return

    response_parts = added_messages + errors
    response_parts.append(f"\n💰 Жами: *{cart.total_display()}*")

    # 100с dan kam bo'lsa eslatma
    if 0 < cart.total < MIN_ORDER_SOMONI:
        needed = MIN_ORDER_SOMONI - cart.total
        response_parts.append(
            f"\n💡 Яна *{p.format_money(needed)}* қўшсангиз — *бепул етказамиз!* "
            f"Қўшимча оласизми?"
        )
    elif cart.total >= MIN_ORDER_SOMONI and cart.address is None:
        response_parts.append(f"\nЯна нима керак, ёки манзилни айтамизми? 📍")

    whatsapp.send_message(chat_id, "\n".join(response_parts))


def _handle_add_by_money(chat_id: str, cart: Cart, intent_data: Dict) -> None:
    """Pul miqdori bo'yicha qo'shish ("10 сомонлик тухум")"""
    # add_by_qty ga o'xshash, lekin money_products ga e'tibor
    _handle_add_by_qty(chat_id, cart, intent_data)


def _handle_view_cart(chat_id: str, cart: Cart) -> None:
    """Korzinani ko'rsatish"""
    if cart.is_empty():
        whatsapp.send_message(chat_id, prompts.cart_empty())
    else:
        whatsapp.send_message(chat_id, prompts.cart_view(cart.format_items(), cart.total_display()))


def _handle_remove(chat_id: str, cart: Cart, intent_data: Dict) -> None:
    """Korzinadan o'chirish"""
    products = intent_data.get("products", []) + intent_data.get("money_products", [])
    if not products:
        whatsapp.send_message(chat_id, "Қайси маҳсулотни ўчиришни истайсиз?")
        return

    name_query = products[0].get("name", "")
    if cart.remove_item(name_query):
        whatsapp.send_message(chat_id, prompts.item_removed(name_query, cart.total_display()))
    else:
        whatsapp.send_message(chat_id, prompts.item_not_found(name_query))


def _handle_address(chat_id: str, cart: Cart, intent_data: Dict) -> None:
    """Manzil belgilash"""
    address = intent_data.get("address", "").strip()
    if not address:
        whatsapp.send_message(chat_id, prompts.address_request())
        return

    # Korzina bo'sh bo'lsa
    if cart.is_empty():
        whatsapp.send_message(chat_id, "Аввал маҳсулот танланг — корзинангиз бўш. 🛒")
        return

    # Eng kam zakaz tekshiruvi
    if cart.total < MIN_ORDER_SOMONI:
        needed = MIN_ORDER_SOMONI - cart.total
        whatsapp.send_message(
            chat_id,
            f"Манзил қабул қилинди, лекин жами *{cart.total_display()}* — энг кам *{MIN_ORDER_SOMONI}с* керак. "
            f"Яна *{p.format_money(needed)}* қўшсангиз — бепул етказамиз!",
        )
        cart.address = address
        return

    cart.address = address

    # Telefon bosqichiga o'tamiz
    if p.is_tajik_phone(cart.phone):
        # WhatsApp raqami Tojikistoniki
        whatsapp.send_message(chat_id, prompts.phone_confirm_request(p.format_phone(cart.phone)))
    else:
        # Tojikistoniki emas — boshqa raqam so'raymiz
        whatsapp.send_message(chat_id, prompts.phone_request_tajik())


def _handle_phone_confirm(chat_id: str, phone: str, cart: Cart, use_whatsapp: bool = False, raw_phone: Optional[str] = None) -> None:
    """Telefonni tasdiqlash"""
    if cart.is_empty():
        whatsapp.send_message(chat_id, prompts.cart_empty())
        return

    if use_whatsapp:
        if p.is_tajik_phone(phone):
            cart.confirmed_phone = phone
            _ask_confirmation(chat_id, cart)
        else:
            whatsapp.send_message(chat_id, prompts.phone_request_tajik())
        return

    # Boshqa raqam berilgan
    candidate = raw_phone or ""
    digits = p.normalize_phone(candidate)
    if p.is_tajik_phone(digits):
        cart.confirmed_phone = digits
        _ask_confirmation(chat_id, cart)
    else:
        whatsapp.send_message(chat_id, prompts.phone_invalid())


def _ask_confirmation(chat_id: str, cart: Cart) -> None:
    """Yakuniy tasdiqlash so'rovi"""
    if not cart.confirmed_phone or not cart.address or cart.is_empty():
        return

    whatsapp.send_message(
        chat_id,
        prompts.order_confirmation_request(
            cart.format_items(),
            cart.total_display(),
            cart.address,
            p.format_phone(cart.confirmed_phone),
        ),
    )


def _handle_order_confirm(chat_id: str, phone: str, cart: Cart, customer: Optional[Dict]) -> None:
    """Buyurtmani yakuniy tasdiqlash → Sheets va admin"""
    if cart.is_empty():
        whatsapp.send_message(chat_id, prompts.cart_empty())
        return

    if not cart.address:
        whatsapp.send_message(chat_id, prompts.address_request())
        return

    if not cart.confirmed_phone:
        if p.is_tajik_phone(phone):
            whatsapp.send_message(chat_id, prompts.phone_confirm_request(p.format_phone(phone)))
        else:
            whatsapp.send_message(chat_id, prompts.phone_request_tajik())
        return

    # Tungi buyurtma?
    if cart.is_night or is_after_hours():
        _handle_night_order_save(chat_id, phone, cart)
        return

    # Saqlash
    items_text = cart.to_admin_format()
    result = sheets.save_order({
        "phone": cart.confirmed_phone,
        "name": cart.customer_name or "?",
        "address": cart.address,
        "items": items_text,
        "total": cart.total,
        "payment": "нақд",
        "status": "қабул қилинди",
    })

    order_number = result.get("number", "?")

    # Mijoz statistikasi
    new_total_orders = (customer.get("total_orders", 0) if customer else 0) + 1
    new_total_spent = (customer.get("total_spent", 0) if customer else 0) + cart.total

    sheets.save_customer({
        "phone": cart.confirmed_phone,
        "name": cart.customer_name,
        "gender": cart.customer_gender,
        "address": cart.address,
        "total_orders": new_total_orders,
        "total_spent": new_total_spent,
        "last_order": datetime.now(TZ).strftime("%Y-%m-%d"),
    })

    has_loyalty = (new_total_orders % LOYALTY_EVERY_N_ORDERS == 0)

    # Mijozga
    whatsapp.send_message(
        chat_id,
        prompts.order_confirmed(order_number, cart.total_display(), has_loyalty),
    )

    # Adminga
    admin_msg = (
        f"🛒 *ЯНГИ БУЮРТМА!*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 #{order_number}\n"
        f"👤 {cart.customer_name or '?'}\n"
        f"📱 {p.format_phone(cart.confirmed_phone)}\n"
        f"📍 {cart.address}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{items_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Жами: *{cart.total_display()}*\n"
        f"💳 Тўлов: нақд\n"
    )
    if has_loyalty:
        admin_msg += f"\n🎁 *{LOYALTY_EVERY_N_ORDERS}-БУЮРТМА — 2 та нон ҳадя қўшинг!*"

    whatsapp.send_to_admin(admin_msg)
    logger.info(f"Buyurtma: #{order_number}, +{phone}, {cart.total_display()}")

    # Korzinani tozalaymiz
    cart_mod.reset_cart(phone)


def _handle_proceed(chat_id: str, phone: str, cart: Cart) -> None:
    """Mijoz mahsulot tanlashni tugatdi — keyingi qadamga o'tamiz"""
    if cart.is_empty():
        whatsapp.send_message(chat_id, prompts.cart_empty())
        return

    # Eng kam zakaz tekshiruvi
    if cart.total < MIN_ORDER_SOMONI:
        needed = MIN_ORDER_SOMONI - cart.total
        whatsapp.send_message(
            chat_id,
            f"Жорий жами: *{cart.total_display()}*. Энг кам буюртма *{MIN_ORDER_SOMONI}с*. "
            f"Яна *{p.format_money(needed)}* қўшсангиз — бепул етказамиз!",
        )
        return

    # Manzil yo'q bo'lsa — manzil so'raymiz
    if not cart.address:
        whatsapp.send_message(
            chat_id,
            f"🛒 Жами: *{cart.total_display()}*\n\n{prompts.address_request()}",
        )
        return

    # Telefon yo'q bo'lsa — telefon so'raymiz
    if not cart.confirmed_phone:
        if p.is_tajik_phone(phone):
            whatsapp.send_message(chat_id, prompts.phone_confirm_request(p.format_phone(phone)))
        else:
            whatsapp.send_message(chat_id, prompts.phone_request_tajik())
        return

    # Hammasi tayyor — tasdiqlash so'raymiz
    _ask_confirmation(chat_id, cart)


def _handle_cancel(chat_id: str, phone: str, cart: Cart) -> None:
    """Bekor qilish — agar tasdiqlanmagan bo'lsa"""
    if cart.is_empty():
        whatsapp.send_message(chat_id, "Корзинангиз бўш эди.")
        return
    cart_mod.reset_cart(phone)
    whatsapp.send_message(chat_id, prompts.cancel_during_collection())


def _handle_night_order_yes(chat_id: str, phone: str, cart: Cart) -> None:
    """Tungi buyurtma uchun rozilik"""
    cart.is_night = True
    if cart.is_empty():
        whatsapp.send_message(chat_id, "Қайси маҳсулотни буюртма қилмоқчисиз? 🛒")
    else:
        whatsapp.send_message(chat_id, "Яхши, тунги буюртма сифатида қабул қилишга тайёрмиз. Манзил ва телефон керак.")
        if not cart.address:
            whatsapp.send_message(chat_id, prompts.address_request())


def _handle_night_order_save(chat_id: str, phone: str, cart: Cart) -> None:
    """Tungi buyurtmani saqlash"""
    items_text = cart.to_admin_format()
    sheets.save_night_order({
        "phone": cart.confirmed_phone,
        "name": cart.customer_name or "?",
        "address": cart.address,
        "items": items_text,
        "total": cart.total,
    })

    whatsapp.send_message(
        chat_id,
        prompts.night_order_saved(cart.format_items(), cart.total_display()),
    )

    # Mijoz ma'lumotini ham saqlash
    if cart.customer_name:
        sheets.save_customer({
            "phone": cart.confirmed_phone or phone,
            "name": cart.customer_name,
            "gender": cart.customer_gender,
            "address": cart.address,
        })

    cart_mod.reset_cart(phone)


def _products_menu_for_ai() -> str:
    """AI ga mahsulotlar ro'yxatini qisqa ko'rinishda berish (sinonimlar bilan)"""
    products = sheets.get_products()
    lines = []
    for p in products:
        short = p["name"]
        syns = p.get("synonyms", "")
        if syns:
            lines.append(f"- {short} (синонимлар: {syns})")
        else:
            lines.append(f"- {short}")
    return "\n".join(lines)


def _build_context_hint(cart: Cart) -> str:
    """AI uchun joriy holat haqida qisqa kontekst"""
    parts = []
    if cart.customer_name:
        parts.append(f"мижоз исми {cart.customer_name}")
    if not cart.is_empty():
        parts.append(f"корзинада {len(cart.items)} та маҳсулот, жами {cart.total_display()}")
    if cart.address:
        parts.append("манзил аллақачон бор")
    elif not cart.is_empty():
        parts.append("манзил кутилмоқда")
    if cart.confirmed_phone:
        parts.append("телефон тасдиқланган")
    return ", ".join(parts) if parts else "янги суҳбат"
