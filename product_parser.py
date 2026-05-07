"""
ZargoBot — Mahsulot va miqdor parsingi
ESKI NOM: parser.py → YANGI NOM: product_parser.py
"""
import logging
import re
from typing import Optional, Tuple, Dict, List

import sheets
from cart import CartItem

logger = logging.getLogger(__name__)


def format_money(amount: float) -> str:
    """Narxni chiroyli formatda chiqarish"""
    if amount == int(amount):
        return f"{int(amount)}с"
    return f"{amount:.2f}с"


def normalize_phone(phone: str) -> str:
    """Telefon raqamini faqat raqamlarga aylantirish"""
    if not phone:
        return ""
    return "".join(c for c in str(phone) if c.isdigit())


def is_tajik_phone(phone: str) -> bool:
    """Telefon raqami Tojikistoniki ekanini tekshirish"""
    digits = normalize_phone(phone)
    return digits.startswith("992") and len(digits) == 12


def format_phone(phone: str) -> str:
    """Telefon raqamini chiroyli ko'rinishda chiqarish"""
    digits = normalize_phone(phone)
    if len(digits) == 12 and digits.startswith("992"):
        return f"+{digits[:3]} {digits[3:5]} {digits[5:8]} {digits[8:10]} {digits[10:]}"
    return f"+{digits}"


def _normalize_cyrillic(text: str) -> str:
    """O'zbek/tojik kirill harflarini standart shaklga keltirish"""
    if not text:
        return ""
    replacements = {
        'ҳ': 'х', 'Ҳ': 'Х',
        'қ': 'к', 'Қ': 'К',
        'ў': 'у', 'Ў': 'У',
        'ғ': 'г', 'Ғ': 'Г',
        'ё': 'е', 'Ё': 'Е',
    }
    result = text
    for old, new in replacements.items():
        result = result.replace(old, new)
    return result.lower().strip()


def find_product(name_query: str, products: List[Dict]) -> Optional[Dict]:
    """Mahsulotni qisman nomi bo'yicha topish"""
    if not name_query:
        return None

    query = name_query.lower().strip()
    query_norm = _normalize_cyrillic(query)

    # 1. Aynan mos kelish
    for p in products:
        if p["name"].lower() == query:
            return p

    # 2. Qisqa nomda mos
    for p in products:
        short = re.sub(r'\s*\([^)]*\)\s*', '', p["name"]).lower().strip()
        if short == query:
            return p

    # 3. Sinonimlar ichida qidirish
    for p in products:
        synonyms_raw = p.get("synonyms", "")
        if not synonyms_raw:
            continue
        for syn in synonyms_raw.split(","):
            syn_clean = syn.strip().lower()
            if not syn_clean:
                continue
            if syn_clean == query or _normalize_cyrillic(syn_clean) == query_norm:
                return p

    # 4. Normalized fuzzy mos kelish
    for p in products:
        short = re.sub(r'\s*\([^)]*\)\s*', '', p["name"]).lower().strip()
        if _normalize_cyrillic(short) == query_norm:
            return p

    # 5. Boshlanishi mos
    for p in products:
        short_norm = _normalize_cyrillic(re.sub(r'\s*\([^)]*\)\s*', '', p["name"]))
        if short_norm.startswith(query_norm) or query_norm.startswith(short_norm):
            return p

    # 6. Sinonim ichida substring
    for p in products:
        synonyms_raw = p.get("synonyms", "")
        if not synonyms_raw:
            continue
        for syn in synonyms_raw.split(","):
            syn_norm = _normalize_cyrillic(syn.strip())
            if syn_norm and (query_norm in syn_norm or syn_norm in query_norm):
                return p

    # 7. Substring
    for p in products:
        if query_norm in _normalize_cyrillic(p["name"]):
            return p

    return None


def get_unit_price(product: Dict) -> Tuple[float, str]:
    """1 birlik narxini hisoblash"""
    pack_price = product["somoni"] + product["diram"] / 100.0
    name = product["name"]
    splittable = product.get("splittable", "Йўқ")

    pack_qty = 1.0
    pack_unit = "пакет"

    match = re.search(r'\((\d+(?:[.,]\d+)?)\s*(дона|кг|г|л|мл)\)', name)
    if match:
        pack_qty = float(match.group(1).replace(",", "."))
        pack_unit = match.group(2)
        if pack_unit == "г":
            pack_qty = pack_qty / 1000
            pack_unit = "кг"
        elif pack_unit == "мл":
            pack_qty = pack_qty / 1000
            pack_unit = "л"

    if splittable == "Дона":
        return (pack_price / pack_qty, "дона")
    elif splittable == "Грамм":
        return (pack_price / pack_qty, pack_unit)
    else:
        return (pack_price, "пакет")


def get_pack_info(product: Dict) -> Dict:
    """Mahsulotning paket ma'lumotini olish"""
    pack_price = product["somoni"] + product["diram"] / 100.0
    return {
        "name": product["name"],
        "pack_price": pack_price,
        "splittable": product.get("splittable", "Йўқ"),
    }


def add_by_quantity(product_name: str, quantity: float, unit: str) -> Tuple[Optional[CartItem], str]:
    """Aniq miqdor bo'yicha qo'shish"""
    products = sheets.get_products()
    product = find_product(product_name, products)

    if not product:
        return None, f'"{product_name}" маҳсулоти топилмади.'