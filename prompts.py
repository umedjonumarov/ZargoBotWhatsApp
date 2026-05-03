"""
ZargoBot — AI uchun prompts (intent parsing va response generation)
"""
from config import (
    SHOP_NAME,
    SHOP_ADDRESS,
    SHOP_HOURS_START,
    SHOP_HOURS_END,
    DELIVERY_ZONE,
    MIN_ORDER_SOMONI,
    LOYALTY_EVERY_N_ORDERS,
    LOYALTY_GIFT,
)


# =========================================================================
# INTENT PARSING PROMPT — AI mijoz xabarini "tushunadi"
# =========================================================================

INTENT_PARSING_SYSTEM = """Сен Zargo дўкони чат ботининг тушуниш қисмисан.
Сенинг иш — мижоз WhatsApp хабарини ўқиб, нима истаётганини JSON форматда қайтариш.
ҲЕЧ ҚАЧОН математика қилма, ҳеч қачон жавоб ёзма — фақат тушун ва JSON қайтар.

Мижоз ёзиши мумкин бўлган мақсадлар (intents):

1. greeting — саломлашиш ("салом", "ассалому алейкум", "хай")
2. provide_name — исмини айтиш ("мени Музаффар дейишади", "Зарина", "Умед")
3. add_by_qty — аниқ миқдор маҳсулот сўраш ("10 дона тухум", "0.5 кг гўшт", "2 та сут", "1 кг картошка")
4. add_by_money — пул миқдори бўйича маҳсулот сўраш ("10 сомонлик тухум", "30 сомонга гўшт")
5. remove — корзинадан олиб ташлаш ("тухумни олма", "гуштни ўчир")
6. view_cart — корзинани кўриш ("нима бор корзинада", "жами қанча", "буюртмамда нима бор")
7. menu — менюни сўраш ("нималар бор", "меню кўрсат", "нима сотасиз")
8. set_address — манзил айтиш ("Зарзамин Кучаи Истиқлол 12", "Боғи Боло")
9. confirm_phone_yes — WhatsApp рақамга розилик ("ҳа", "майли", "шу рақамга бўлади")
10. provide_phone — бошқа рақам айтиш ("+992 90 123 45 67")
11. confirm_order — буюртмани тасдиқлаш ("тасдиқлайман", "ҳа майли", "тайёр")
12. cancel_order — бекор қилиш ("бекор қил", "керак эмас")
13. night_order_yes — тунги буюртмага розилик ("ҳа эртанги учун олинг")
14. night_order_no — тунги буюртмадан рад ("йўқ керак эмас")
15. stop_reminders — авто-эслатмаларни тўхтатиш ("хабар юборманг бошқа")
16. ask_question — умумий савол ("ишлаш вақти?", "қаердасиз?")
17. unclear — тушунарсиз

Жавобни АНИҚ шу JSON форматда бер:

```json
{
  "intent": "...",
  "products": [
    {"name": "Тухум", "qty": 10, "unit": "дона"}
  ],
  "money_products": [
    {"name": "Гўшт", "money": 30}
  ],
  "name": null,
  "address": null,
  "phone": null,
  "raw_text": "..."
}
```

МИСОЛЛАР:

Мижоз: "10 дона тухум керак"
Жавоб:
```json
{
  "intent": "add_by_qty",
  "products": [{"name": "Тухум", "qty": 10, "unit": "дона"}],
  "money_products": [],
  "name": null, "address": null, "phone": null,
  "raw_text": "10 дона тухум керак"
}
```

Мижоз: "10 сомонлик тухум бер"
Жавоб:
```json
{
  "intent": "add_by_money",
  "products": [],
  "money_products": [{"name": "Тухум", "money": 10}],
  "name": null, "address": null, "phone": null,
  "raw_text": "10 сомонлик тухум бер"
}
```

Мижоз: "30 сомонлик гушт ва 1 кг картошка"
Жавоб:
```json
{
  "intent": "add_by_money",
  "products": [{"name": "Картошка", "qty": 1, "unit": "кг"}],
  "money_products": [{"name": "Гўшт", "money": 30}],
  "name": null, "address": null, "phone": null,
  "raw_text": "30 сомонлик гушт ва 1 кг картошка"
}
```

Мижоз: "Менга 0.5 кг гўшт ва 2 та нон"
Жавоб:
```json
{
  "intent": "add_by_qty",
  "products": [
    {"name": "Гўшт", "qty": 0.5, "unit": "кг"},
    {"name": "Нон", "qty": 2, "unit": "та"}
  ],
  "money_products": [],
  "name": null, "address": null, "phone": null,
  "raw_text": "..."
}
```

Мижоз: "Умед"
Жавоб:
```json
{
  "intent": "provide_name",
  "products": [], "money_products": [],
  "name": "Умед",
  "address": null, "phone": null,
  "raw_text": "Умед"
}
```

Мижоз: "Зарзамин Кучаи Истиқлол 12"
Жавоб:
```json
{
  "intent": "set_address",
  "products": [], "money_products": [],
  "name": null,
  "address": "Зарзамин Кучаи Истиқлол 12",
  "phone": null,
  "raw_text": "..."
}
```

Мижоз: "корзинамда нима бор"
Жавоб:
```json
{
  "intent": "view_cart",
  "products": [], "money_products": [],
  "name": null, "address": null, "phone": null,
  "raw_text": "..."
}
```

Мижоз: "тасдиқлайман"
Жавоб:
```json
{
  "intent": "confirm_order",
  "products": [], "money_products": [],
  "name": null, "address": null, "phone": null,
  "raw_text": "тасдиқлайман"
}
```

Мижоз: "ха" (агар олдинги хабар "Шу рақамга қўнғироқ қилса бўладими?" бўлса)
Жавоб:
```json
{
  "intent": "confirm_phone_yes",
  "products": [], "money_products": [],
  "name": null, "address": null, "phone": null,
  "raw_text": "ха"
}
```

ҚАТЪИЙ ҚОИДАЛАР:
- Маҳсулот номини ҚИСҚА (қавссиз) ёз: "Тухум", "Гўшт", "Картошка"
- "X сомонлик Y" → add_by_money
- "X дона/кг/та Y" → add_by_qty
- Бирлик аниқ берилмаса (масалан "5 та тухум") → "та" / "дона" дея фараз қил
- "5 сомонлик гўшт ва 10 та тухум" → ҲАР ИККАЛАСИНИ юбор (products + money_products)
- АГАР intent шубҳали бўлса → "unclear"
- ҲЕЧ ҚАЧОН математика қилма, миқдор ҳисобла, нархни кўрсатма
- Жавоб ФАҚАТ JSON блок бўлсин, бошқа гап бўлмасин"""


def build_intent_prompt(user_message: str, context_hint: str = "") -> str:
    """Intent parsing uchun user prompt"""
    hint = f"\n\nКонтекст: {context_hint}" if context_hint else ""
    return f'Мижоз хабари: "{user_message}"{hint}\n\nIntent JSON ни қайтар:'


# =========================================================================
# AVTO ESLATMALAR — alohida prompts
# =========================================================================

def night_reminder_prompt(customer_name: str, items_text: str, total: int) -> str:
    return f"""Хайрли субҳ, {customer_name}! ☀️

Кечаги буюртмангизни эслатамиз:
{items_text}

💰 Жами: {total} сомони

Буюртмангиз ҳалигача кучидами? *Ҳа* ёки *Йўқ* деб ёзинг."""


def breakfast_reminder_prompt(customer_name: str, breakfast_items: list) -> str:
    items_str = ", ".join(f"*{x}*" for x in breakfast_items)
    return f"""{customer_name}, ассалому алейкум! 🌙

Ўтган сафар олган {items_str} тугаб қолмадими?

Эртанги нонушта учун ҳозирдан брон қилиб қўйсангиз — эрталаб шошмайсиз. Тасдиқлайми? 🥖🧈"""


def reorder_reminder_prompt(customer_name: str, last_items_text: str) -> str:
    return f"""{customer_name}, ассалому алейкум! 👋

Ўтган сафар олган маҳсулотларингиз тугаган бўлиши мумкин:
{last_items_text}

Такрорлаймизми ёки бошқа нарса оласизми?"""


def loyalty_recovery_prompt(customer_name: str) -> str:
    return f"""{customer_name}, ассалому алейкум! 💚

Узоқ кўрмадик. Маҳсулотларимизни ёқмадими, ёки бошқа сабаб бордир?

Шу ҳафта учун *бирор имтиёз* қилишимиз мумкин. Сизга нима керак — биринчи бўлиб айтинг."""


# =========================================================================
# FIXED RESPONSES — koddagi tayyor matnlar (math = 100% to'g'ri)
# =========================================================================

def greeting_new_customer() -> str:
    return "Ассалому алейкум! Сизга қандай мурожаат қилишим мумкин? 👋"


def greeting_returning_customer(name: str, gender: str) -> str:
    honorific = "ака" if gender == "эркак" else "опа"
    return f"{name} {honorific}, ассалому алейкум! Бугун нимани оламиз? 🛒"


def menu_text(products_text: str) -> str:
    return f"Бизда қуйидаги маҳсулотлар мавжуд:\n{products_text}\n\nНима олмоқчисиз? 🛒"


def name_received(name: str, gender: str) -> str:
    honorific = "ака" if gender == "эркак" else "опа"
    return f"Танишганимиздан хурсандман, {name} {honorific}! 😊\nБугун нимани оламиз? 🛒"


def address_request() -> str:
    return f"Манзилингизни айтинг (фақат {DELIVERY_ZONE} учун хизмат қиламиз). 📍"


def address_confirmed(address: str) -> str:
    return f"📍 Манзил қабул қилинди: *{address}*"


def phone_confirm_request(formatted_phone: str) -> str:
    return (
        f"Сизнинг рақамингиз *{formatted_phone}*. "
        f"Шу рақамга қўнғироқ қилса бўладими? *Ҳа* ёки *Йўқ* (бошқа рақам бераман)"
    )


def phone_request_tajik() -> str:
    return (
        "Сизнинг WhatsApp рақамингиз Тожикистон рақами эмас. "
        "Етказиб бериш учун *+992* билан бошланган Тожикистон рақамингизни айтинг. 📱"
    )


def phone_invalid() -> str:
    return "Рақам нотўғри. Илтимос, +992 билан бошланган тўғри Тожикистон рақамини айтинг."


def order_confirmation_request(cart_text: str, total: str, address: str, phone: str) -> str:
    return (
        f"📋 *Буюртмангизни тасдиқланг:*\n\n{cart_text}\n\n"
        f"💰 Жами: *{total}*\n"
        f"📍 Манзил: {address}\n"
        f"📞 Телефон: {phone}\n\n"
        f"Тасдиқлайми? *Ҳа* ёки *Йўқ*"
    )


def order_confirmed(order_number: int, total: str, has_loyalty_gift: bool = False) -> str:
    msg = (
        f"✅ *Буюртмангизни брон қилдик!*\n\n"
        f"📦 Буюртма: *#{order_number}*\n"
        f"💰 Жами: *{total}*\n\n"
        f"📞 Тез орада сиз билан боғланамиз."
    )
    if has_loyalty_gift:
        msg += f"\n\n🎉 Бу {LOYALTY_EVERY_N_ORDERS}-буюртмангиз! Сизга {LOYALTY_GIFT} ҳадя!"
    return msg


def order_cancel_after_confirm() -> str:
    return (
        "Буюртмангизни бекор қилиш учун админ билан боғланинг: *+992 92 790 96 98* 📞\n"
        "Биз қайта кутамиз!"
    )


def order_cancelled() -> str:
    return "Буюртмангиз бекор қилинди. Яна бирор нарса керак бўлса — ёзинг! 👋"


def voice_image_response() -> str:
    return (
        "Илтимос, маҳсулот рўйхатини *матн кўринишида* ёзинг — "
        "биз ҳозирча овозли хабар ва расм қабул қилмаймиз. 📝"
    )


def technical_error() -> str:
    return "Кечирасиз, техник носозлик юз берди. Илтимос, бироздан сўнг яна уриниб кўринг. 🙏"


def after_hours_message() -> str:
    return (
        f"Иш вақтимиз *{SHOP_HOURS_START}:00 — {SHOP_HOURS_END}:00*. "
        f"Ҳозир иш вақтидан ташқари. Эртанги кун учун буюртмангизни қабул қилайми? *Ҳа* ёки *Йўқ*"
    )


def night_order_saved(cart_text: str, total: str) -> str:
    return (
        f"✅ Тунги буюртмангизни сақладик:\n\n{cart_text}\n\n"
        f"💰 Жами: *{total}*\n\n"
        f"Эрталаб {SHOP_HOURS_START}:00 да тасдиқлаш учун яна боғланамиз. Хайрли тун! 🌙"
    )


def shop_info() -> str:
    return (
        f"📍 *{SHOP_NAME}*\n"
        f"{SHOP_ADDRESS}\n"
        f"🕐 Иш вақти: {SHOP_HOURS_START}:00 — {SHOP_HOURS_END}:00\n"
        f"🚚 Етказиб бериш: фақат {DELIVERY_ZONE}, нақд тўлов\n"
        f"💰 Энг кам буюртма: {MIN_ORDER_SOMONI} сомони"
    )


def min_order_warning(current_total: str, needed_more: str) -> str:
    return (
        f"💡 Жорий жами: *{current_total}*. "
        f"Яна *{needed_more}* қўшсангиз — бепул етказамиз! "
        f"Қўшимча оласизми? Тухум, нон, сут ёки бошқа маҳсулот таклиф қилишим мумкин."
    )


def cart_view(cart_text: str, total: str) -> str:
    return f"🛒 *Корзинангиз:*\n\n{cart_text}\n\n💰 Жами: *{total}*"


def cart_empty() -> str:
    return "Корзинангиз ҳозирча бўш. Нима олмоқчисиз? 🛒"


def item_added(item_short_name: str, qty_display: str, price_display: str, total: str) -> str:
    return (
        f"✅ Қўшилди: *{item_short_name}* — {qty_display} ({price_display})\n"
        f"💰 Жами: *{total}*"
    )


def item_added_with_alternative(
    item_short_name: str,
    qty_display: str,
    price_display: str,
    alt_qty: str,
    alt_price: str,
    total: str,
) -> str:
    return (
        f"✅ Қўшилди: *{item_short_name}* — {qty_display} ({price_display})\n\n"
        f"💡 Ёки *{alt_qty}* ({alt_price}) олсангиз бутунроқ бўларди — алмаштирайми?\n\n"
        f"💰 Жами: *{total}*"
    )


def item_removed(short_name: str, total: str) -> str:
    return f"🗑 *{short_name}* олиб ташланди. \n💰 Жами: *{total}*"


def item_not_found(query: str) -> str:
    return f'Кечирасиз, "{query}" корзинада топилмади.'


def product_not_in_menu(query: str) -> str:
    return f'Кечирасиз, *"{query}"* бизда йўқ. Менюдан танлаш учун *"меню"* деб ёзинг.'


def stop_reminders_confirmed() -> str:
    return (
        "✅ Авто-эслатмалар тўхтатилди. "
        "Сиз ёзганингизда биз доим тайёрмиз!"
    )


def unclear_response(name_part: str = "") -> str:
    prefix = f"{name_part}, " if name_part else ""
    return (
        f"{prefix}кечирасиз, тўлиқ тушунмадим. "
        f"Қандай маҳсулот керак — *\"меню\"* деб ёзинг ёки тўғридан-тўғри сўранг "
        f"(масалан: *\"10 дона тухум\"*, *\"0.5 кг гўшт\"*, *\"30 сомонлик картошка\"*)"
    )


def cancel_during_collection() -> str:
    return "Буюртма бекор қилинди. Янгидан бошлайлик!"
