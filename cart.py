"""
ZargoBot — Korzina (Cart) modeli va boshqaruvi
Server tomonida har bir mijoz uchun korzina holati saqlanadi.
Math bu yerda — AI ga ishonmaymiz.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class CartItem:
    """Korzinadagi bitta mahsulot"""
    product_name: str       # "Тухум (10 дона)" — Sheets'dagi to'liq nomi
    qty_value: float        # 6 yoki 0.5
    qty_unit: str           # "дона" yoki "кг" yoki "пакет" yoki "л"
    price_total: float      # jami narxi shu pozitsiya uchun

    def display_qty(self) -> str:
        """Foydalanuvchiga ko'rinadigan miqdor"""
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
        """Narxni '40с' yoki '9.5с' ko'rinishida"""
        if self.price_total == int(self.price_total):
            return f"{int(self.price_total)}с"
        return f"{self.price_total:.2f}с"

    def short_name(self) -> str:
        """Mahsulot nomidan o'lchov bilan birgalik qismni olib tashlash"""
        return re.sub(r'\s*\([^)]*\)\s*', '', self.product_name).strip()


@dataclass
class Cart:
    """Mijozning korzinasi va hamma ma'lumotlari"""
    phone: str
    items: List[CartItem] = field(default_factory=list)
    customer_name: Optional[str] = None
    customer_gender: Optional[str] = None
    address: Optional[str] = None
    confirmed_phone: Optional[str] = None
    stage: str = "collecting"  # collecting / awaiting_address / awaiting_phone / confirming / completed
    is_night: bool = False     # тунги буюртма flagi

    @property
    def total(self) -> float:
        return round(sum(item.price_total for item in self.items), 2)

    def total_display(self) -> str:
        t = self.total
        return f"{int(t)}с" if t == int(t) else f"{t:.2f}с"

    def is_empty(self) -> bool:
        return len(self.items) == 0

    def add_item(self, item: CartItem) -> None:
        """Korzinaga qo'shish — bir xil mahsulot bo'lsa miqdor yig'iladi"""
        for existing in self.items:
            if existing.product_name == item.product_name and existing.qty_unit == item.qty_unit:
                existing.qty_value += item.qty_value
                existing.price_total = round(existing.price_total + item.price_total, 2)
                return
        self.items.append(item)

    def remove_item(self, product_name_query: str) -> bool:
        """Mahsulotni qisman nomidan o'chirish"""
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
        """Korzinani butunlay tozalash"""
        self.items = []
        self.address = None
        self.confirmed_phone = None
        self.stage = "collecting"
        self.is_night = False

    def format_items(self) -> str:
        """Mijozga ko'rinadigan korzina ro'yxati"""
        if not self.items:
            return "(корзинангиз бўш)"
        lines = []
        for item in self.items:
            lines.append(f"• {item.short_name()} — {item.display_qty()} ({item.display_price()})")
        return "\n".join(lines)

    def format_full(self) -> str:
        """To'liq korzina + jami summa"""
        if not self.items:
            return "Корзинангиз бўш."
        result = self.format_items()
        result += f"\n\n💰 Жами: *{self.total_display()}*"
        return result

    def to_admin_format(self) -> str:
        """Admin uchun batafsil format"""
        if not self.items:
            return "(буюртма бўш)"
        lines = []
        for item in self.items:
            lines.append(f"• {item.product_name} × {item.display_qty()} = {item.display_price()}")
        return "\n".join(lines)

    def to_metadata(self) -> List[Dict]:
        """Sheets'ga saqlash uchun metadata"""
        return [
            {
                "name": item.short_name(),
                "qty": item.display_qty(),
                "price": int(item.price_total) if item.price_total == int(item.price_total) else round(item.price_total, 2),
            }
            for item in self.items
        ]


# === IN-MEMORY KORZINA SAQLASH ===
_carts: Dict[str, Cart] = {}


def get_cart(phone: str) -> Cart:
    """Mijoz korzinasini olish (yo'q bo'lsa, yangi yaratiladi)"""
    if phone not in _carts:
        _carts[phone] = Cart(phone=phone)
    return _carts[phone]


def reset_cart(phone: str) -> None:
    """Korzinani tashlash"""
    if phone in _carts:
        del _carts[phone]


def has_active_cart(phone: str) -> bool:
    return phone in _carts and not _carts[phone].is_empty()
