"""
ZargoBot — OpenAI bilan suhbat
"""
import json
import logging
import re
from typing import Dict, List, Optional, Tuple

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_TEMPERATURE, OPENAI_MAX_TOKENS

logger = logging.getLogger(__name__)

client = OpenAI(api_key=OPENAI_API_KEY)

# In-memory suhbat tarixi (faqat hozirgi suhbat uchun)
# Format: { phone: [{role: ..., content: ...}, ...] }
_conversations: Dict[str, List[Dict]] = {}

# Bitta suhbatda eng ko'p saqlanadigan xabarlar (eski xabarlarni o'chirish)
MAX_HISTORY_MESSAGES = 30


def get_conversation(phone: str) -> List[Dict]:
    """Mijozning suhbat tarixi"""
    return _conversations.get(phone, [])


def reset_conversation(phone: str):
    """Mijoz suhbatini tozalash (yangi zakaz uchun)"""
    if phone in _conversations:
        del _conversations[phone]


def chat(
    phone: str,
    user_message: str,
    system_prompt: str,
) -> Tuple[str, Dict]:
    """
    Mijoz xabariga AI javob qaytarish.
    Qaytaradi: (mijozga ko'rinadigan matn, parsed JSON metadata)
    """

    if phone not in _conversations:
        _conversations[phone] = []

    # System prompt'ni har gal yangilash (mahsulotlar/holat o'zgargan bo'lishi mumkin)
    history = _conversations[phone]
    messages = [{"role": "system", "content": system_prompt}] + history
    messages.append({"role": "user", "content": user_message})

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=OPENAI_TEMPERATURE,
            max_tokens=OPENAI_MAX_TOKENS,
        )
        ai_text = response.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"OpenAI xato ({phone}): {e}")
        raise

    # JSON blokni ajratib olish
    visible_text, metadata = _extract_json(ai_text)

    # Suhbat tarixiga qo'shish (sof matnni saqlash)
    _conversations[phone].append({"role": "user", "content": user_message})
    _conversations[phone].append({"role": "assistant", "content": ai_text})

    # Eng eski xabarlarni o'chirish (token tejash uchun)
    if len(_conversations[phone]) > MAX_HISTORY_MESSAGES:
        _conversations[phone] = _conversations[phone][-MAX_HISTORY_MESSAGES:]

    # Vaqt aytishni tekshirish (qat'iy taqiq)
    if _contains_time_mention(visible_text):
        logger.warning(f"AI vaqt aytdi! Matn tozalandi: {visible_text[:100]}")
        visible_text = _strip_time_mentions(visible_text)

    return visible_text, metadata


def _extract_json(ai_text: str) -> Tuple[str, Dict]:
    """AI javobidan JSON blokni ajratib olish"""
    # ```json ... ``` formatini qidirish
    json_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
    match = re.search(json_pattern, ai_text, re.DOTALL)

    metadata = {}
    visible_text = ai_text

    if match:
        try:
            metadata = json.loads(match.group(1))
            # JSON blokni matndan o'chirish
            visible_text = ai_text[: match.start()] + ai_text[match.end():]
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse xato: {e}")

    # Bo'shliqlarni tozalash
    visible_text = visible_text.strip()
    return visible_text, metadata


def _contains_time_mention(text: str) -> bool:
    """Matnda yetkazib berish vaqti haqida gap borligini tekshirish"""
    # Pattern: "30 daqiqa", "1 soat", "tez", va h.k.
    forbidden_patterns = [
        r"\d+\s*(дақиқа|минут|мин)",
        r"\d+\s*(соат|часа|час)",
        r"\b(тез орада|тезда|шу заҳоти|ҳозироқ)\b",
        # NB: "тез орада сиз билан боғланамиз" tasdiqlangan zakazda ruxsat
    ]
    text_lower = text.lower()
    for pattern in forbidden_patterns:
        if re.search(pattern, text_lower):
            # "тез орада сиз билан боғланамиз" rasmiy javobini istisno qilish
            if "тез орада сиз билан" in text_lower:
                continue
            return True
    return False


def _strip_time_mentions(text: str) -> str:
    """Vaqt haqidagi gaplarni olib tashlash"""
    # Bu yerda jiddiy NLP qilmasdan, faqat oddiy almashtirish
    replacements = [
        (r"\d+\s*(дақиқа|минут|мин)\s*ичида", "тез орада"),
        (r"\d+\s*(соат|часа|час)\s*ичида", "тез орада"),
        (r"\b(шу заҳоти|ҳозироқ)\b", "тез орада"),
    ]
    result = text
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def detect_gender(name: str) -> str:
    """Ismdan jinsni aniqlash uchun AI ishlatish (oddiy fallback bilan)"""
    if not name:
        return "эркак"

    name_lower = name.strip().lower()

    # Aniq belgilar (ayollar uchun ko'pincha 'a' yoki 'o' bilan tugaydi)
    female_endings = ("а", "я", "о", "ия", "иса")
    if name_lower.endswith(female_endings):
        return "аёл"

    # Aniq erkak nomlari
    male_names = {
        "музаффар", "шуҳрат", "алишер", "жасур", "санжар", "нодир", "акбар",
        "бахтиёр", "комрон", "комил", "карим", "икром", "ислом", "иброҳим",
        "ёқуб", "юсуф", "умарали", "умед", "темур", "тимур", "хамза",
        "сардор", "ҳасан", "ҳусайн", "акмал", "аброр", "анвар", "артур",
        "фарҳод", "фаррух", "фозил", "ғофур", "достон", "ёрбек",
    }
    if name_lower in male_names:
        return "эркак"

    # Default — erkak
    return "эркак"


def honorific(name: str, gender: str) -> str:
    """Ism + 'ака' yoki 'опа'"""
    if not name:
        return ""
    suffix = "ака" if gender == "эркак" else "опа"
    return f"{name.strip()} {suffix}"
