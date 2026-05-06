"""
ZargoBot — Green API orqali WhatsApp xabar yuborish
"""
import logging
from typing import Optional, Dict

import requests

from config import GREEN_API_BASE, GREEN_API_TOKEN, ADMIN_CHAT_ID

logger = logging.getLogger(__name__)


def send_message(chat_id: str, text: str) -> Optional[Dict]:
    """Xabar yuborish"""
    if not GREEN_API_TOKEN:
        logger.error("Green API token sozlanmagan!")
        return None

    url = f"{GREEN_API_BASE}/sendMessage/{GREEN_API_TOKEN}"
    payload = {"chatId": chat_id, "message": text}

    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"Yuborildi {chat_id}: {result.get('idMessage', 'no_id')}")
        return result
    except Exception as e:
        logger.error(f"Xabar yuborish xato ({chat_id}): {e}")
        return None


def send_to_admin(text: str) -> Optional[Dict]:
    """Adminga xabar yuborish"""
    return send_message(ADMIN_CHAT_ID, text)


def chat_id_from_phone(phone: str) -> str:
    """Telefon raqamidan WhatsApp chat ID yasash"""
    digits = "".join(c for c in str(phone) if c.isdigit())
    return f"{digits}@c.us"


def setup_webhook(webhook_url: str) -> Dict:
    """Green API'da webhook URL'ni o'rnatish"""
    url = f"{GREEN_API_BASE}/setSettings/{GREEN_API_TOKEN}"
    payload = {
        "webhookUrl": webhook_url,
        "webhookUrlToken": "",
        "delaySendMessagesMilliseconds": 500,
        "markIncomingMessagesReaded": "yes",
        "incomingWebhook": "yes",
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        return resp.json()
    except Exception as e:
        logger.error(f"Webhook setup xato: {e}")
        return {"error": str(e)}


def get_settings() -> Dict:
    """Green API joriy sozlamalarini olish"""
    url = f"{GREEN_API_BASE}/getSettings/{GREEN_API_TOKEN}"
    try:
        resp = requests.get(url, timeout=15)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def health_check() -> bool:
    """Green API ishlayotganini tekshirish"""
    try:
        url = f"{GREEN_API_BASE}/getStateInstance/{GREEN_API_TOKEN}"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        return data.get("stateInstance") == "authorized"
    except Exception:
        return False


def parse_incoming_message(data: Dict) -> Optional[Dict]:
    """Kelayotgan webhook ma'lumotidan xabarni ajratib olish"""
    if data.get("typeWebhook") != "incomingMessageReceived":
        return None

    sender_data = data.get("senderData", {})
    chat_id = sender_data.get("chatId", "")
    sender = sender_data.get("sender", "")
    sender_number = sender.split("@")[0] if sender else ""
    sender_name = sender_data.get("senderName", "") or sender_data.get("chatName", "")

    message_data = data.get("messageData", {})
    message_type = message_data.get("typeMessage", "")

    text = ""
    # 1. Оддий матн ёки линкли матн
    if "textMessageData" in message_data:
        text = message_data["textMessageData"].get("textMessage", "")
    elif "extendedTextMessageData" in message_data:
        text = message_data["extendedTextMessageData"].get("text", "")
        
    # 2. WhatsApp Каталогдан келган "Корзина" (Буюртма) хабари
    elif message_type == "orderMessage" and "orderMessageData" in message_data:
        order_data = message_data["orderMessageData"]
        items = []
        
        # Корзинадаги ҳар бир маҳсулотни ўқиб оламиз
        if "parameters" in order_data:
            for item in order_data["parameters"]:
                name = item.get("name", "Маҳсулот")
                qty = item.get("quantity", 1)
                items.append(f"{qty} та {name}")
        
        # Ботнинг сунъий интеллекти (AI) тушуниши учун гап тузамиз
        if items:
            text = "Мен каталогдан қуйидагиларни танладим:\n" + "\n".join(items)
        else:
            text = "Мен каталогдан маҳсулот танладим."
            
        # Агар мижоз корзина билан бирга изоҳ (комментарий) ёзган бўлса, уни ҳам қўшамиз
        caption = order_data.get("message", "")
        if caption:
            text += f"\nИзоҳ: {caption}"

    # Catalog order (WhatsApp Business korzinasi)
    order_items = []
    is_order = False
    if (
        message_type in ("orderMessage", "interactiveMessage")
        or "orderMessageData" in message_data
        or "interactiveButtonsReply" in message_data
    ):
        is_order = True
        order_data = (
            message_data.get("orderMessageData")
            or message_data.get("orderMessage")
            or message_data.get("interactiveMessageData", {}).get("orderData")
            or {}
        )
        items_raw = (
            order_data.get("items")
            or order_data.get("products")
            or order_data.get("orderItems")
            or order_data.get("itemsList")
            or []
        )
        for it in items_raw:
            order_items.append({
                "name": it.get("name") or it.get("productName") or it.get("itemName") or "",
                "qty": int(it.get("quantity") or it.get("qty") or 1),
                "price": float(it.get("price") or it.get("itemPrice") or 0),
                "currency": it.get("currency") or "",
            })

    return {
        "chat_id": chat_id,
        "sender_number": sender_number,
        "sender_name": sender_name,
        "message_type": message_type,
        "text": text.strip() if text else "",
        "is_text": bool(text),
        "is_voice": message_type == "audioMessage",
        "is_image": message_type == "imageMessage",
        "is_order": is_order,
        "order_items": order_items,
        "raw_message_data": message_data,
    }
