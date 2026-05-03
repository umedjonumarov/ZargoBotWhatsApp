"""
ZargoBot — Google Sheets bilan ishlash (Apps Script orqali)
"""
import logging
import time
from datetime import datetime
from typing import Optional, List, Dict, Any

import requests

from config import SHEETS_URL, PRODUCTS_CACHE_MINUTES

logger = logging.getLogger(__name__)

# === CACHE ===
_products_cache: Optional[List[Dict]] = None
_products_cache_time: float = 0


def _get(action: str, **params) -> Dict[str, Any]:
    """Apps Script'ga GET so'rovi yuborish"""
    try:
        params["action"] = action
        resp = requests.get(SHEETS_URL, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Sheets GET xato ({action}): {e}")
        return {"error": str(e)}


def _post(action: str, payload: Dict) -> Dict[str, Any]:
    """Apps Script'ga POST so'rovi yuborish"""
    try:
        payload["action"] = action
        resp = requests.post(SHEETS_URL, json=payload, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Sheets POST xato ({action}): {e}")
        return {"error": str(e)}


# === MAHSULOTLAR ===

def get_products(force_refresh: bool = False) -> List[Dict]:
    """Mahsulotlar ro'yxatini olish (cache bilan)"""
    global _products_cache, _products_cache_time

    cache_age = time.time() - _products_cache_time
    cache_valid = (
        _products_cache is not None
        and cache_age < PRODUCTS_CACHE_MINUTES * 60
    )

    if cache_valid and not force_refresh:
        return _products_cache

    result = _get("products")
    if "error" in result:
        # Xato bo'lsa eski cache'ni qaytarish, yo'q bo'lsa bo'sh ro'yxat
        return _products_cache or []

    _products_cache = result.get("products", [])
    _products_cache_time = time.time()
    logger.info(f"Mahsulotlar yangilandi: {len(_products_cache)} ta")
    return _products_cache


def format_products_for_ai() -> str:
    """AI uchun mahsulotlar ro'yxatini matn ko'rinishida"""
    products = get_products()
    if not products:
        return "(Маҳсулотлар рўйхати ҳозирча мавжуд эмас)"

    by_category: Dict[str, List[Dict]] = {}
    for p in products:
        cat = p.get("category", "Бошқа")
        by_category.setdefault(cat, []).append(p)

    lines = []
    category_order = ["Нонушта", "Кунлик", "Узоқ муддат"]
    for cat in category_order + [c for c in by_category if c not in category_order]:
        if cat not in by_category:
            continue
        lines.append(f"\n📦 {cat.upper()}:")
        for p in by_category[cat]:
            price = format_price(p["somoni"], p["diram"])
            split = p.get("splittable", "Йўқ")
            split_info = ""
            if split == "Дона":
                # Mahsulot nomidan dona sonini olishga harakat
                split_info = " [бўлинади дона билан]"
            elif split == "Грамм":
                split_info = " [бўлинади грамм/кг билан]"
            lines.append(f"  • {p['name']} — {price}{split_info}")

    return "\n".join(lines)


def format_price(somoni: int, diram: int) -> str:
    """Narxni '10с25дирам' ko'rinishida formatlash"""
    s = int(somoni)
    d = int(diram)
    if d == 0:
        return f"{s}с"
    return f"{s}с{d}дирам"


# === MIJOZLAR ===

def get_customer(phone: str) -> Optional[Dict]:
    """Mijozni telefon raqami bo'yicha topish"""
    phone = _normalize_phone(phone)
    result = _get("customer", phone=phone)
    if result.get("found"):
        return result.get("customer")
    return None


def save_customer(customer: Dict) -> bool:
    """Yangi mijozni saqlash yoki mavjudini yangilash"""
    customer["phone"] = _normalize_phone(customer.get("phone", ""))
    result = _post("save_customer", {"customer": customer})
    return result.get("saved", False)


def update_customer(phone: str, updates: Dict) -> bool:
    """Mijoz ma'lumotlarini yangilash (ba'zi maydonlar)"""
    phone = _normalize_phone(phone)
    result = _post("update_customer", {"phone": phone, "updates": updates})
    return result.get("updated", False)


def set_reminder_status(phone: str, value: str) -> bool:
    """Mijozning eslatma holatini o'zgartirish ('on' yoki 'off')"""
    phone = _normalize_phone(phone)
    result = _post("set_reminder", {"phone": phone, "value": value})
    return result.get("updated", False)


def get_all_customers() -> List[Dict]:
    """Barcha mijozlar"""
    result = _get("customers")
    return result.get("customers", [])


# === BUYURTMALAR ===

def get_all_orders() -> List[Dict]:
    """Barcha buyurtmalar"""
    result = _get("orders")
    return result.get("orders", [])


def get_customer_orders(phone: str) -> List[Dict]:
    """Mijozning barcha buyurtmalari"""
    phone = _normalize_phone(phone)
    result = _get("customer_orders", phone=phone)
    return result.get("orders", [])


def save_order(order: Dict) -> Dict:
    """Yangi buyurtmani saqlash, raqamini qaytaradi"""
    order["phone"] = _normalize_phone(order.get("phone", ""))
    if "date" not in order:
        order["date"] = datetime.now().isoformat()
    result = _post("save_order", {"order": order})
    return result


# === TUNGI BUYURTMALAR ===

def get_night_orders() -> List[Dict]:
    """Tasdiqlanmagan tungi buyurtmalar"""
    result = _get("night_orders")
    orders = result.get("night_orders", [])
    return [o for o in orders if o.get("confirmed") == "кутилмоқда"]


def save_night_order(order: Dict) -> bool:
    """Tungi buyurtmani saqlash (ertalab tasdiqlanadi)"""
    order["phone"] = _normalize_phone(order.get("phone", ""))
    if "date" not in order:
        order["date"] = datetime.now().isoformat()
    result = _post("save_night_order", {"order": order})
    return result.get("saved", False)


def confirm_night_order(phone: str) -> Optional[Dict]:
    """Tungi buyurtmani tasdiqlash, buyurtma ma'lumotlarini qaytaradi"""
    phone = _normalize_phone(phone)
    result = _post("confirm_night_order", {"phone": phone})
    if result.get("confirmed"):
        return result.get("order")
    return None


# === YORDAMCHI ===

def _normalize_phone(phone: str) -> str:
    """Telefon raqamini standart shaklga keltirish (faqat raqamlar)"""
    if not phone:
        return ""
    return "".join(c for c in str(phone) if c.isdigit())


def is_tajik_phone(phone: str) -> bool:
    """Telefon raqami Tojikistoniki ekanini tekshirish (+992 + 9 raqam)"""
    digits = _normalize_phone(phone)
    return digits.startswith("992") and len(digits) == 12


def format_phone_display(phone: str) -> str:
    """Telefon raqamini chiroyli ko'rinishda chiqarish: +992 90 123 45 67"""
    digits = _normalize_phone(phone)
    if len(digits) == 12 and digits.startswith("992"):
        return f"+{digits[:3]} {digits[3:5]} {digits[5:8]} {digits[8:10]} {digits[10:]}"
    return f"+{digits}"


def health_check() -> bool:
    """Sheets API ishlayotganini tekshirish"""
    try:
        result = _get("ping")
        return result.get("status") == "ok"
    except Exception:
        return False
