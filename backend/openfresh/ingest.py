"""Recipe ingestion helpers: parsing ingredient lines and ISO durations."""

import re
import unicodedata
from typing import Any

STAPLE_NAMES = {
    "salt",
    "kosher salt",
    "sea salt",
    "pepper",
    "black pepper",
    "water",
    "olive oil",
    "vegetable oil",
    "cooking oil",
}

UNIT_ALIASES = {
    "cup": "cup",
    "cups": "cup",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "tbsp": "tbsp",
    "tbsp.": "tbsp",
    "tbs": "tbsp",
    "tbs.": "tbsp",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "tsp": "tsp",
    "tsp.": "tsp",
    "ounce": "oz",
    "ounces": "oz",
    "oz": "oz",
    "oz.": "oz",
    "pound": "lb",
    "pounds": "lb",
    "lb": "lb",
    "lbs": "lb",
    "lb.": "lb",
    "lbs.": "lb",
    "gram": "g",
    "grams": "g",
    "g": "g",
    "g.": "g",
    "kilogram": "kg",
    "kilograms": "kg",
    "kg": "kg",
    "kgs": "kg",
    "kg.": "kg",
    "kgs.": "kg",
    "clove": "clove",
    "cloves": "clove",
    "can": "can",
    "cans": "can",
    "bunch": "bunch",
    "bunches": "bunch",
}

UNICODE_FRACTION_CHARS = "½¼¾⅓⅔⅛⅜⅝⅞⅕⅖⅗⅘⅙⅚"


def parse_ingredient_line(raw: str) -> dict[str, Any]:
    """Parse a single raw ingredient line deterministically.

    Returns:
        {
            "raw": str,
            "name": str,
            "quantity": float | None,
            "unit": str,
            "staple": bool,
        }
    """
    s = raw.strip()
    if not s:
        return {
            "raw": raw,
            "name": "",
            "quantity": None,
            "unit": "",
            "staple": False,
        }

    qty: float | None = None
    remainder: str = s

    # 1. Mixed fraction with Unicode fraction: e.g. "1 ½" or "1½"
    m_mixed_uni = re.match(
        rf"^(\d+)\s*([{UNICODE_FRACTION_CHARS}])(?:\s+|$)(.*)$", s
    )
    if m_mixed_uni:
        qty = float(m_mixed_uni.group(1)) + unicodedata.numeric(m_mixed_uni.group(2))
        remainder = m_mixed_uni.group(3)
    else:
        # 2. Mixed fraction with ASCII fraction: e.g. "1 1/2" or "1-1/2"
        m_mixed_ascii = re.match(
            r"^(\d+)[-\s]+(\d+)\s*/\s*(\d+)(?:\s+|$)(.*)$", s
        )
        if m_mixed_ascii:
            qty = float(m_mixed_ascii.group(1)) + float(m_mixed_ascii.group(2)) / float(m_mixed_ascii.group(3))
            remainder = m_mixed_ascii.group(4)
        else:
            # 3. ASCII fraction alone: e.g. "1/2"
            m_frac_ascii = re.match(r"^(\d+)\s*/\s*(\d+)(?:\s+|$)(.*)$", s)
            if m_frac_ascii:
                qty = float(m_frac_ascii.group(1)) / float(m_frac_ascii.group(2))
                remainder = m_frac_ascii.group(3)
            else:
                # 4. Unicode fraction alone: e.g. "½"
                m_frac_uni = re.match(
                    rf"^([{UNICODE_FRACTION_CHARS}])(?:\s+|$)(.*)$", s
                )
                if m_frac_uni:
                    qty = unicodedata.numeric(m_frac_uni.group(1))
                    remainder = m_frac_uni.group(2)
                else:
                    # 5. Decimal or integer: e.g. "2" or "1.5" or ".5"
                    m_num = re.match(
                        r"^(\d+(?:\.\d+)?|\.\d+)(?:\s+|$|(?=[a-zA-Z]))(.*)$", s
                    )
                    if m_num:
                        qty = float(m_num.group(1))
                        remainder = m_num.group(2)

    quantity: float | None = None
    unit: str = ""
    name: str = ""

    if qty is not None:
        remainder = remainder.strip()
        m_word = re.match(r"^([^\s]+)\s*(.*)$", remainder)
        if m_word:
            token = m_word.group(1)
            after_token = m_word.group(2)

            token_lower = token.lower()
            unit_key = None
            if token_lower in UNIT_ALIASES:
                unit_key = token_lower
            elif token_lower.rstrip(".,") in UNIT_ALIASES:
                unit_key = token_lower.rstrip(".,")

            if unit_key is not None:
                unit = UNIT_ALIASES[unit_key]
                name_part = re.sub(r"^of\s+", "", after_token, flags=re.IGNORECASE)
                name = name_part.split(",")[0].strip()
                quantity = qty
            else:
                # Unrecognized unit word.
                # If followed by "of " (e.g. "1 glug of olive oil"), treat as unquantified odd-unit phrase.
                if re.match(r"^of\s+", after_token, re.IGNORECASE):
                    quantity = None
                    unit = ""
                    name_part = re.sub(r"^of\s+", "", after_token, flags=re.IGNORECASE)
                    name = name_part.split(",")[0].strip()
                else:
                    # e.g. "4 eggs" or "2 medium onions, diced"
                    quantity = qty
                    unit = ""
                    name_part = remainder
                    name = name_part.split(",")[0].strip()
        else:
            quantity = qty
            unit = ""
            name = ""
    else:
        # No leading number
        quantity = None
        unit = ""
        name_part = re.sub(r"^of\s+", "", remainder, flags=re.IGNORECASE)
        name = name_part.split(",")[0].strip()

    staple = name.lower() in STAPLE_NAMES
    return {
        "raw": raw,
        "name": name,
        "quantity": quantity,
        "unit": unit,
        "staple": staple,
    }


def parse_iso_duration(value: str | None) -> str | None:
    """Format an ISO-8601 duration (e.g. 'PT45M', 'PT1H30M', 'PT2H') into human string like '45m', '1h 30m', '2h'.

    Returns None if value is None or empty. Passes through non-ISO strings (e.g. '30 mins').
    """
    if value is None:
        return None
    val = value.strip()
    if not val:
        return None

    m = re.match(
        r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$",
        val,
        re.IGNORECASE,
    )
    if m:
        days = int(m.group("days")) if m.group("days") else 0
        hours = int(m.group("hours")) if m.group("hours") else 0
        minutes = int(m.group("minutes")) if m.group("minutes") else 0
        seconds = int(m.group("seconds")) if m.group("seconds") else 0

        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if seconds:
            parts.append(f"{seconds}s")

        if parts:
            return " ".join(parts)
        if val.upper() in ("PT0M", "PT0S", "PT0H", "P0D"):
            return "0m"

    return val
