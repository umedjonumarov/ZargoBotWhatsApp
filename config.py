"""
ZargoBot — Sozlamalar va konstantalar
"""
import os

# === GREEN API (WhatsApp) ===
GREEN_API_INSTANCE_ID = os.environ.get("GREEN_API_INSTANCE_ID", "7107601809")
GREEN_API_TOKEN = os.environ.get("GREEN_API_TOKEN", "")
GREEN_API_BASE = f"https://api.green-api.com/waInstance{GREEN_API_INSTANCE_ID}"

# === OPENAI ===
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_TEMPERATURE = 0.7
OPENAI_MAX_TOKENS = 600

# === GOOGLE SHEETS (Apps Script Web App URL) ===
SHEETS_URL = os.environ.get(
    "SHEETS_URL",
    "https://script.google.com/macros/s/AKfycbziUIX313Iw8gkdwnIXtjJROIBSN12vvIanzLVcxugQXb_eJFOXj0mrMqRzHLo3WAdXGQ/exec"
)

# === BOT VA ADMIN RAQAMLARI ===
BOT_PHONE = "79099885383"               # Botning Green API raqami
ADMIN_PHONE = "992927909698"             # Admin (zakaz va ogohlantirishlar)
ADMIN_CHAT_ID = f"{ADMIN_PHONE}@c.us"

# === DO'KON MA'LUMOTLARI ===
SHOP_NAME = "Zargo"
SHOP_ADDRESS = "Тожикистон Республикаси, Суғд вилояти, Бобожон Ғафуров ноҳияси, Зарзамин қишлоғи"
SHOP_HOURS_START = 8           # 8:00
SHOP_HOURS_END = 22            # 22:00
DELIVERY_ZONE = "Зарзамин қишлоғи"

# === BIZNES QOIDALARI ===
MIN_ORDER_SOMONI = 100         # Eng kam zakaz miqdori (100 сомони)
LOYALTY_EVERY_N_ORDERS = 10    # Har necha-zakazga sovg'a
LOYALTY_GIFT = "2 та нон"      # Sovg'a turi
PRODUCTS_CACHE_MINUTES = 3     # Mahsulotlar nechta daqiqa cache'da bo'ladi

# === ESLATMA TRIGGERLARI ===
REMINDER_BREAKFAST_DAY = 3     # 3-kun nonushta eslatmasi
REMINDER_BREAKFAST_HOUR = 20   # 20:00 da yuboriladi
REMINDER_REORDER_DAY = 4       # 4-kun re-order
REMINDER_REORDER_HOUR = 15     # 15:00 da yuboriladi
REMINDER_LOYALTY_DAY = 14      # 14-kun "sog'indik"
REMINDER_LOYALTY_HOUR = 12     # 12:00 da yuboriladi

# === XAVFSIZLIK / CRON SECRET ===
# Cron task'larni faqat shu kalit bilan ishga tushirish mumkin
CRON_SECRET = os.environ.get("CRON_SECRET", "zargo-bot-cron-2026")

# === BOT HOLATI ===
BOT_ACTIVE_KEY = "bot_active"   # In-memory holat: бот ishlamoqda yoki to'xtatilgan

# === LOGGING ===
LOG_LEVEL = "INFO"
