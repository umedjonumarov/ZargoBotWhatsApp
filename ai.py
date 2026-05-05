"""
ZargoBot - OpenAI bilan ishlash (intent parsing va boshqa)
"""
import json
import logging
import re
from typing import Dict

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL
from prompts import INTENT_PARSING_SYSTEM, build_intent_prompt

logger = logging.getLogger(__name__)

client = OpenAI(api_key=OPENAI_API_KEY)


def parse_intent(user_message: str, context_hint: str = "", products_menu: str = "") -> Dict:
    """Mijoz xabarini AI orqali tushunish va structured ma'lumot qaytarish."""
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": INTENT_PARSING_SYSTEM},
                {"role": "user", "content": build_intent_prompt(user_message, context_hint, products_menu)},
            ],
            temperature=0.1,
            max_tokens=400,
        )
        ai_text = response.choices[0].message.content or ""
        return _extract_json(ai_text)
    except Exception as e:
        logger.error(f"Intent parsing error: {e}")
        return {"intent": "unclear", "raw_text": user_message}


def _extract_json(ai_text: str) -> Dict:
    """AI javobidan JSON blokni ajratib olish"""
    pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
    match = re.search(pattern, ai_text, re.DOTALL)

    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")
            return {"intent": "unclear", "raw_text": ai_text}

    try:
        return json.loads(ai_text.strip())
    except json.JSONDecodeError:
        pass

    return {"intent": "unclear", "raw_text": ai_text}


def detect_gender(name: str) -> str:
    """Ismdan jinsni aniqlash"""
    if not name:
        return "эркак"

    name_lower = name.strip().lower()
    female_endings = ("а", "я", "о", "ия", "иса")
    if name_lower.endswith(female_endings):
        return "аёл"

    male_names = {
        "музаффар", "шуҳрат", "алишер", "жасур", "санжар", "нодир", "акбар",
        "бахтиёр", "комрон", "комил", "карим", "икром", "ислом", "иброҳим",
        "ёқуб", "юсуф", "умарали", "умед", "темур", "тимур", "хамза",
        "сардор", "ҳасан", "ҳусайн", "акмал", "аброр", "анвар", "артур",
        "фарҳод", "фаррух", "фозил", "ғофур", "достон", "ёрбек",
    }
    if name_lower in male_names:
        return "эркак"

    return "эркак"


def honorific(name: str, gender: str) -> str:
    """Ism + 'ака' yoki 'опа'"""
    if not name:
        return ""
    suffix = "ака" if gender == "эркак" else "опа"
    return f"{name.strip()} {suffix}"
