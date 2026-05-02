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

    # Matn xabari
    text = ""
    if "textMessageData" in message_data:
        text = message_data["textMessageData"].get("textMessage", "")
    elif "extendedTextMessageData" in message_data:
        text = message_data["extendedTextMessageData"].get("text", "")

    return {
        "chat_id": chat_id,
        "sender_number": sender_number,
        "sender_name": sender_name,
        "message_type": message_type,
        "text": text.strip() if text else "",
        "is_text": bool(text),
        "is_voice": message_type == "audioMessage",
        "is_image": message_type == "imageMessage",
    }
