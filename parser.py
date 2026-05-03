"""
ZargoBot — Mahsulot va miqdor parsingi (matematika qatiy server tomonida)
"""
import logging
import re
from typing import Optional, Tuple, Dict, List

import sheets
from cart import CartItem

logger = logging.getLogger(__name__)


# === MAHSULOT QIDIRISH ===

def find_product(name_query: str, products: List[Dict]) -> Optional[Dict]:
    """Mahsulotni qisman nomi bo'yicha topish"""
    if not name_query:
        return None

    query = name_query.lower().strip()

    # 1. Aynan mos kelish
    for p in products:
        if p["name"].lower() == query:
            return p

    # 2. Qisqa nomda mos
    for p in products:
        short = re.sub(r'\s*\([^)]*\)\s*', '', p["name"]).lower().strip()
        if short == query:
            return p

    # 3. Boshlanishi mos
    for p in products:
        short = re.sub(r'\s*\([^)]*\)\s*', '', p["name"]).lower().strip()
        if short.startswith(query) or query.startswith(short):
            return p

    # 4. Substring
    for p in products:
        if query in p["name"].lower():
            return p

    return None


def get_unit_price(product: Dict) -> Tuple[float, str]:
    """
    1 birlik (dona, kg, l) narxini hisoblash.
    "Тухум (10 дона)" → (1.5, "дона")
    "Гўшт (1кг)" → (80, "кг")
    "Сариқ ёғ (200г)" → (25, "пакет")  [bo'linmaydi]
    """
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


# === MIQDOR BO'YICHA QO'SHISH ===

def add_by_quantity(
    product_name: str,
    quantity: float,
    unit: str,
) -> Tuple[Optional[CartItem], str]:
    """
    Mijoz aniq miqdor bergan: "10 дона тухум", "0.5 кг гўшт", "2 та сут"
    Qaytaradi: (CartItem yoki None, izoh)
    """
    products = sheets.get_products()
    product = find_product(product_name, products)

    if not product:
        return None, f'"{product_name}" маҳсулоти топилмади'

    splittable = product.get("splittable", "Йўқ")
    unit_price, base_unit = get_unit_price(product)
    pack_price = product["somoni"] + product["diram"] / 100.0

    user_unit = (unit or "").lower().strip()

    # Birliklarni standartga keltirish
    if user_unit in ("гр", "грамм", "г"):
        quantity = quantity / 1000
        user_unit = "кг"
    elif user_unit == "мл":
        quantity = quantity / 1000
        user_unit = "л"

    # === 1. Bo'linmaydigan ===
    if splittable == "Йўқ":
        if user_unit in ("", "та", "паулдалик", "паулдалар", "пакет", "дона", "штука"):
            n = int(round(quantity))
            if n < 1:
                n = 1
            total = round(pack_price * n, 2)
            return CartItem(
                product_name=product["name"],
                qty_value=n,
                qty_unit="пакет",
                price_total=total,
            ), ""
        return None, f'{product["name"]} фақат тўлиқ паулдалик сотилади ({format_money(pack_price)})'

    # === 2. Donada bo'linadigan ===
    if splittable == "Дона":
        if user_unit not in ("дона", "та", "штука", ""):
            return None, f'{product["name"]} фақат дона билан сотилади'
        n = int(quantity)
        if n < 1:
            return None, "Энг кам 1 дона олиш мумкин"
        total = round(unit_price * n, 2)
        return CartItem(
            product_name=product["name"],
            qty_value=n,
            qty_unit="дона",
            price_total=total,
        ), ""

    # === 3. Vazn/hajm bo'linadigan ===
    if splittable == "Грамм":
        if user_unit and user_unit != base_unit:
            return None, f'{product["name"]} {base_unit} билан сотилади ({format_money(unit_price)}/{base_unit})'
        if quantity <= 0:
            return None, "Миқдор тўғри киритилмаган"
        total = round(unit_price * quantity, 2)
        return CartItem(
            product_name=product["name"],
            qty_value=quantity,
            qty_unit=base_unit,
            price_total=total,
        ), ""

    return None, "Маҳсулот тури аниқ эмас"


# === PUL BO'YICHA QO'SHISH ===

def add_by_money(
    product_name: str,
    money_amount: float,
) -> Tuple[Optional[CartItem], str, Optional[Dict]]:
    """
    "X сомонлик Y" — pul miqdoriga mahsulot
    Qaytaradi: (CartItem, izoh, alternativa)
    Alternativa — yumaloq variant (taklif uchun): {qty, unit, price}
    """
    products = sheets.get_products()
    product = find_product(product_name, products)

    if not product:
        return None, f'"{product_name}" маҳсулоти топилмади', None

    splittable = product.get("splittable", "Йўқ")
    unit_price, base_unit = get_unit_price(product)
    pack_price = product["somoni"] + product["diram"] / 100.0

    if money_amount <= 0:
        return None, "Сўм миқдори нотўғри", None

    # === 1. Bo'linmaydigan ===
    if splittable == "Йўқ":
        if money_amount < pack_price:
            return None, (
                f'{product["name"]} фақат тўлиқ паулдалик сотилади — {format_money(pack_price)}. '
                f'Шу пулга оласизми, ёки бошқа нарса олсангизми?'
            ), None
        n = int(money_amount // pack_price)
        total = round(pack_price * n, 2)
        return CartItem(
            product_name=product["name"],
            qty_value=n,
            qty_unit="пакет",
            price_total=total,
        ), "", None

    # === 2. Donada ===
    if splittable == "Дона":
        n = int(money_amount / unit_price)
        if n < 1:
            return None, (
                f'1 дона {product["name"]} {format_money(unit_price)} туради. '
                f'{format_money(money_amount)} сўмга етмайди.'
            ), None
        total = round(unit_price * n, 2)
        return CartItem(
            product_name=product["name"],
            qty_value=n,
            qty_unit="дона",
            price_total=total,
        ), "", None

    # === 3. Vazn ===
    if splittable == "Грамм":
        qty_exact = money_amount / unit_price
        total = round(unit_price * qty_exact, 2)

        # Yaqin yumaloq alternativa
        alt = None
        if base_unit == "кг":
            rounded = round(qty_exact * 2) / 2  # 0.5 ga yumaloq
            if rounded > 0 and abs(rounded - qty_exact) > 0.01:
                alt_total = round(unit_price * rounded, 2)
                alt = {
                    "qty": rounded,
                    "unit": "кг",
                    "price": alt_total,
                }

        # Aniq vazni 3 raqamgacha
        qty_exact = round(qty_exact, 3)

        return CartItem(
            product_name=product["name"],
            qty_value=qty_exact,
            qty_unit=base_unit,
            price_total=total,
        ), "", alt

    return None, "Маҳсулот тури аниқ эмас", None


# === YORDAMCHI ===

def format_money(amount: float) -> str:
    """49с yoki 9.5с"""
    if amount == int(amount):
        return f"{int(amount)}с"
    return f"{amount:.2f}с"


def format_qty_with_unit(qty: float, unit: str) -> str:
    """0.5 кг yoki 6 дона"""
    if unit == "дона":
        return f"{int(qty)} дона"
    if qty == int(qty):
        return f"{int(qty)} {unit}"
    return f"{qty:g} {unit}"


def is_tajik_phone(phone_text: str) -> bool:
    digits = re.sub(r'\D', '', phone_text)
    return digits.startswith("992") and len(digits) == 12


def normalize_phone(phone_text: str) -> str:
    return re.sub(r'\D', '', phone_text)


def format_phone(phone: str) -> str:
    digits = normalize_phone(phone)
    if len(digits) == 12 and digits.startswith("992"):
        return f"+{digits[:3]} {digits[3:5]} {digits[5:8]} {digits[8:10]} {digits[10:]}"
    return f"+{digits}"


def extract_phone_from_text(text: str) -> Optional[str]:
    """Matn ichidan telefon raqami topish"""
    digits = re.sub(r'\D', '', text)
    if len(digits) >= 9:
        # Faqat oxirgi 12 ta raqam
        if digits.startswith("992"):
            return digits[:12] if len(digits) >= 12 else None
        elif digits.startswith("9") and len(digits) >= 9:
            return "992" + digits[-9:]
    return None
