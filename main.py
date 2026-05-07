"""
ZargoBot — Asosiy Flask serveri
WhatsApp webhook + cron endpoints + health check
YANGILANDI: __import__("config") o'chirildi, ADMIN_PHONE to'g'ridan-to'g'ri import qilindi
"""
import logging
from datetime import datetime

from flask import Flask, request, jsonify
import pytz

from config import (
    LOG_LEVEL,
    CRON_SECRET,
    SHOP_NAME,
    OPENAI_API_KEY,
    GREEN_API_TOKEN,
    GREEN_API_INSTANCE_ID,
    SHEETS_URL,
    ADMIN_PHONE,
)

import sheets
import whatsapp
import handlers
import admin
import reminders

# === LOGGING ===
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

TZ = pytz.timezone("Asia/Dushanbe")

# === FLASK ===
app = Flask(__name__)

# =========================================================================
# UMUMIY ENDPOINT'LAR
# =========================================================================

@app.route("/")
def index():
    return f"{SHOP_NAME} Bot ишлаяпти ✅", 200

@app.route("/health")
def health():
    """Bot va barcha xizmatlar holatini tekshirish"""
    sheets_ok = sheets.health_check()
    wa_ok = whatsapp.health_check() if GREEN_API_TOKEN else False
    openai_ok = bool(OPENAI_API_KEY)

    status = {
        "bot": "✅ Ишлаяпти" if admin.is_bot_active() else "⏸ Тўхтатилган",
        "openai": "✅ ОК" if openai_ok else "❌ Конфиг йўқ",
        "green_api": "✅ ОК" if wa_ok else "❌ Уланиш йўқ",
        "google_sheets": "✅ ОК" if sheets_ok else "❌ Уланиш йўқ",
        "time": datetime.now(TZ).strftime("%H:%M %d.%m.%Y"),
    }

    overall_ok = sheets_ok and wa_ok and openai_ok
    return jsonify(status), 200 if overall_ok else 503

# =========================================================================
# WHATSAPP WEBHOOK
# =========================================================================

@app.route("/webhook", methods=["POST"])
def webhook():
    """Green API'dan kelayotgan xabarlar"""
    try:
        data = request.json
        if not data:
            return jsonify({"status": "empty"}), 200

        webhook_type = data.get("typeWebhook")
        logger.info(f"Webhook: {webhook_type}")

        # DEBUG: catalog/order xabarlarni log'ga to'liq yozish
        try:
            message_data = data.get("messageData", {})
            msg_type = message_data.get("typeMessage", "")
            if msg_type and msg_type != "textMessage":
                import json as _json
                payload_str = _json.dumps(data, ensure_ascii=False)[:2000]
                logger.info(f"[DEBUG] Non-text msg type={msg_type}: {payload_str}")
                try:
                    whatsapp.send_to_admin(
                        f"🔍 DEBUG: typeMessage={msg_type}\n\n```\n{payload_str[:1500]}\n```"
                    )
                except Exception:
                    pass
        except Exception:
            pass

        # Faqat kelayotgan xabarlar
        if webhook_type != "incomingMessageReceived":
            return jsonify({"status": "ignored"}), 200

        # Bot to'xtatilgan bo'lsa — admindan boshqa hech kim bilan ishlamaymiz
        parsed = whatsapp.parse_incoming_message(data)
        if not parsed:
            return jsonify({"status": "no_message"}), 200

        # YANGI: To'g'ridan-to'g'ri ADMIN_PHONE ishlatiladi
        if not admin.is_bot_active() and parsed["sender_number"] not in (ADMIN_PHONE,):
            logger.info(f"Bot to'xtatilgan, e'tiborga olinmadi: +{parsed['sender_number']}")
            return jsonify({"status": "bot_paused"}), 200

        handlers.handle_customer_message(parsed)
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"Webhook xato: {e}", exc_info=True)
        try:
            whatsapp.send_to_admin(
                f"⚠️ *WEBHOOK ХАТОЛИГИ*\n"
                f"Вақт: {datetime.now(TZ).strftime('%H:%M')}\n"
                f"Хато: {type(e).__name__}: {str(e)[:200]}"
            )
        except Exception:
            pass
        return jsonify({"status": "error"}), 200

# =========================================================================
# CRON TASK ENDPOINT'LARI
# =========================================================================

def _check_secret() -> bool:
    return request.args.get("secret") == CRON_SECRET

@app.route("/cron/morning-night-orders", methods=["GET", "POST"])
def cron_morning_night():
    """Har kuni 8:00 — tungi buyurtma egalariga eslatma"""
    if not _check_secret():
        return jsonify({"error": "unauthorized"}), 401
    result = reminders.send_morning_night_orders()
    return jsonify(result), 200

@app.route("/cron/breakfast-reminder", methods=["GET", "POST"])
def cron_breakfast():
    """Har kuni 20:00 — 3 kun oldin nonushta sotib olganlarga"""
    if not _check_secret():
        return jsonify({"error": "unauthorized"}), 401
    result = reminders.send_breakfast_reminders()
    return jsonify(result), 200

@app.route("/cron/reorder-reminder", methods=["GET", "POST"])
def cron_reorder():
    """Har kuni 15:00 — 4 kun oldin zakaz qilganlarga"""
    if not _check_secret():
        return jsonify({"error": "unauthorized"}), 401
    result = reminders.send_reorder_reminders()
    return jsonify(result), 200

@app.route("/cron/loyalty-recovery", methods=["GET", "POST"])
def cron_loyalty():
    """Har kuni 12:00 — 14 kun yo'q mijozlarga"""
    if not _check_secret():
        return jsonify({"error": "unauthorized"}), 401
    result = reminders.send_loyalty_recovery_reminders()
    return jsonify(result), 200

@app.route("/cron/weekly-report", methods=["GET", "POST"])
def cron_weekly():
    """Har dushanba ertalab — adminga haftalik hisobot"""
    if not _check_secret():
        return jsonify({"error": "unauthorized"}), 401
    result = reminders.send_weekly_report()
    return jsonify(result), 200

@app.route("/cron/monthly-report", methods=["GET", "POST"])
def cron_monthly():
    """Har oy 1-sanasi ertalab — adminga oylik hisobot"""
    if not _check_secret():
        return jsonify({"error": "unauthorized"}), 401
    result = reminders.send_monthly_report()
    return jsonify(result), 200

@app.route("/cron/keep-alive", methods=["GET", "POST"])
def cron_keep_alive():
    """Render bepul tarif uxlamasligi uchun (har 10 daqiqada)"""
    # YANGI: Secret tekshiruvi qo'shildi
    if not _check_secret():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"status": "alive", "time": datetime.now(TZ).isoformat()}), 200

# =========================================================================
# WEBHOOK SOZLASH (admin uchun)
# =========================================================================

@app.route("/setup-webhook", methods=["GET"])
def setup_webhook():
    """Green API'da webhook URL'ni o'rnatish"""
    if not _check_secret():
        return jsonify({"error": "unauthorized"}), 401

    base_url = request.args.get("url") or f"https://{request.host}"
    webhook_url = f"{base_url}/webhook"

    result = whatsapp.setup_webhook(webhook_url)
    return jsonify({"webhook_url": webhook_url, "result": result}), 200

@app.route("/check-settings", methods=["GET"])
def check_settings():
    """Green API joriy sozlamalarini ko'rish"""
    if not _check_secret():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(whatsapp.get_settings()), 200

# =========================================================================
# ISHGA TUSHIRISH
# =========================================================================

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)