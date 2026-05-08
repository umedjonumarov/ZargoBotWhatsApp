"""
ZargoBot - Korzina (Cart) modeli va boshqaruvi
Hybrid: In-memory (asosiy) + Sheets (fallback, agar Apps Script qo'llab-quvvatlasa)
"""
import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional

import sheets

logger = logging.getLogger(__name__)


@dataclass
class CartItem:
    """Korzinadagi bitta mahsulot"""
    product_name: str
    qty_value: float
    qty_unit: str
    price_total: float

    def display_qty(self) -> str:
        if self.qty_unit == "дона":
            return f"{int(self.qty_value)} дона"
        elif self.qty_unit in ("кг", "л"):
            if self.qty_value == int(self.qty_value):
                return f"{int(self.qty_value)} {self.qty_unit}"
            return f"{self.qty_value:g} {self.qty_unit}"
        elif self.qty_unit == "пакет":
            n = int(self.qty_value)
            return f"{n} та" if n > 1 else "1 та"
        return f"{self.qty_value:g} {self.qty_unit}"

    def display_price(self) -> str:
        if self.price_total == int(self.price_total):
            return f"{int(self.price_total)}с"
        return f"{self.price_total:.2f}с"

    def short_name(self) -> str:
        return re.sub(r'\s*\([^)]*\)\s*', '', self.product_name).strip()

    def to_dict(self) -> Dict:
        return {
            "product_name": self.product_name,
            "qty_value": self.qty_value,
            "qty_unit": self.qty_unit,
            "price_total": self.price_total,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CartItem":
        return cls(
            product_name=data.get("product_name", ""),
            qty_value=data.get("qty_value", 0),
            qty_unit=data.get("qty_unit", ""),
            price_total=data.get("price_total", 0),
        )


@dataclass
class Cart:
    """Mijozning korzinasi"""
    phone: str
    items: List[CartItem] = field(default_factory=list)
    customer_name: Optional[str] = None
    customer_gender: Optional[str] = None
    address: Optional[str] = None
    confirmed_phone: Optional[str] = None
    stage: str = "collecting"
    is_night: bool = False
    has_pending_catalog_order: bool = False  # Yangi mijozning ismini kutib turamiz, keyin katalogni qayta ishlaymiz

    @property
    def total(self) -> float:
        return round(sum(item.price_total for item in self.items), 2)

    def total_display(self) -> str:
        t = self.total
        return f"{int(t)}с" if t == int(t) else f"{t:.2f}с"

    def is_empty(self) -> bool:
        return len(self.items) == 0

    def add_item(self, item: CartItem) -> None:
        for existing in self.items:
            if existing.product_name == item.product_name and existing.qty_unit == item.qty_unit:
                existing.qty_value += item.qty_value
                existing.price_total = round(existing.price_total + item.price_total, 2)
                return
        self.items.append(item)

    def remove_item(self, product_name_query: str) -> bool:
        query_lower = product_name_query.lower().strip()
        for i, item in enumerate(self.items):
            if (
                query_lower in item.product_name.lower()
                or query_lower in item.short_name().lower()
            ):
                del self.items[i]
                return True
        return False

    def clear(self) -> None:
        self.items = []
        self.address = None
        self.confirmed_phone = None
        self.stage = "collecting"
        self.is_night = False

    def format_items(self) -> str:
        if not self.items:
            return "(корзинангиз бўш)"
        lines = []
        for item in self.items:
            lines.append(f"• {item.short_name()} - {item.display_qty()} ({item.display_price()})")
        return "\n".join(lines)

    def format_full(self) -> str:
        if not self.items:
            return "Корзинангиз бўш."
        result = self.format_items()
        result += f"\n\n💰 Жами: *{self.total_display()}*"
        return result

    def to_admin_format(self) -> str:
        if not self.items:
            return "(буюртма бўш)"
        lines = []
        for item in self.items:
            lines.append(f"• {item.product_name} x {item.display_qty()} = {item.display_price()}")
        return "\n".join(lines)

    def to_metadata(self) -> List[Dict]:
        return [item.to_dict() for item in self.items]

    def to_dict(self) -> Dict:
        return {
            "phone": self.phone,
            "items": [item.to_dict() for item in self.items],
            "customer_name": self.customer_name,
            "customer_gender": self.customer_gender,
            "address": self.address,
            "confirmed_phone": self.confirmed_phone,
            "stage": self.stage,
            "is_night": self.is_night,
            "has_pending_catalog_order": self.has_pending_catalog_order,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Cart":
        cart = cls(phone=data.get("phone", ""))
        cart.items = [CartItem.from_dict(i) for i in data.get("items", [])]
        cart.customer_name = data.get("customer_name")
        cart.customer_gender = data.get("customer_gender")
        cart.address = data.get("address")
        cart.confirmed_phone = data.get("confirmed_phone")
        cart.stage = data.get("stage", "collecting")
        cart.is_night = data.get("is_night", False)
        cart.has_pending_catalog_order = data.get("has_pending_catalog_order", False)
        return cart


# =========================================================================
# IN-MEMORY storage (asosiy) + Sheets fallback (agar mavjud bo'lsa)
# =========================================================================

_memory_carts: Dict[str, Cart] = {}


def get_cart(phone: str) -> Cart:
    """Mijoz korzinasini olish - avval xotira, keyin Sheets fallback"""
    # 1) In-memory
    if phone in _memory_carts:
        return _memory_carts[phone]

    # 2) Sheets (agar Apps Script qo'llab-quvvatlasa)
    try:
        cart_data = sheets.get_cart(phone)
        if cart_data and isinstance(cart_data, dict) and cart_data.get("phone"):
            cart = Cart.from_dict(cart_data)
            _memory_carts[phone] = cart
            return cart
    except Exception as e:
        logger.debug(f"Sheets get_cart fallback: {e}")

    # 3) Yangi cart yaratish
    cart = Cart(phone=phone)
    _memory_carts[phone] = cart
    return cart


def save_cart(cart: Cart) -> None:
    """Korzinani saqlash - xotirada doim, Sheets'da imkoni bo'lsa"""
    _memory_carts[cart.phone] = cart
    try:
        sheets.save_cart(cart.to_dict())
    except Exception as e:
        logger.debug(f"Sheets save_cart fallback: {e}")


def reset_cart(phone: str) -> None:
    """Korzinani tashlash"""
    if phone in _memory_carts:
        del _memory_carts[phone]
    try:
        sheets.delete_cart(phone)
    except Exception as e:
        logger.debug(f"Sheets delete_cart fallback: {e}")


def has_active_cart(phone: str) -> bool:
    if phone in _memory_carts and not _memory_carts[phone].is_empty():
        return True
    return False
