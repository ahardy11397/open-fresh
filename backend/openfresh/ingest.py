"""Recipe ingestion helpers: parsing ingredient lines, ISO durations, and schema.org JSON-LD."""

import html
import json
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


def _is_recipe_type(val: Any) -> bool:
    if isinstance(val, str):
        s = val.strip().lower()
        return s == "recipe" or s.endswith("/recipe")
    if isinstance(val, list):
        return any(_is_recipe_type(item) for item in val)
    return False


def _find_recipe_node(data: Any) -> dict[str, Any] | None:
    if isinstance(data, dict):
        if _is_recipe_type(data.get("@type")):
            return data
        if "@graph" in data:
            found = _find_recipe_node(data["@graph"])
            if found is not None:
                return found
        for k, v in data.items():
            if k != "@graph" and isinstance(v, (dict, list)):
                found = _find_recipe_node(v)
                if found is not None:
                    return found
    elif isinstance(data, list):
        for item in data:
            found = _find_recipe_node(item)
            if found is not None:
                return found
    return None


def _find_positive_int(val: Any) -> int | None:
    if isinstance(val, int) and val > 0:
        return val
    if isinstance(val, float) and val > 0:
        return int(val)
    if isinstance(val, str):
        m = re.search(r"(\d+)", val)
        if m:
            n = int(m.group(1))
            if n > 0:
                return n
    if isinstance(val, list):
        for item in val:
            found = _find_positive_int(item)
            if found is not None:
                return found
    return None


def _parse_servings(val: Any) -> int:
    found = _find_positive_int(val)
    return found if found is not None else 2


def _clean_step_text(text: str) -> str:
    s = re.sub(r"<[^>]+>", "", text)
    s = html.unescape(s)
    return " ".join(s.split())


def _split_and_clean_steps(text: str) -> list[str]:
    normalized = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>", "\n", text)
    out: list[str] = []
    for line in normalized.split("\n"):
        cleaned = _clean_step_text(line)
        if cleaned:
            out.append(cleaned)
    return out


def _collect_steps(inst: Any) -> list[str]:
    steps: list[str] = []
    if isinstance(inst, str):
        steps.extend(_split_and_clean_steps(inst))
    elif isinstance(inst, list):
        for item in inst:
            steps.extend(_collect_steps(item))
    elif isinstance(inst, dict):
        if "itemListElement" in inst:
            steps.extend(_collect_steps(inst["itemListElement"]))
        else:
            text = inst.get("text") or inst.get("name")
            if text:
                steps.extend(_collect_steps(text))
    return steps


def _parse_recipe_node(node: dict[str, Any]) -> dict[str, Any]:
    name = node.get("name")
    title_missing = False
    if isinstance(name, str) and name.strip():
        title = html.unescape(name.strip())
    else:
        title = "Untitled Recipe"
        title_missing = True

    servings = _parse_servings(node.get("recipeYield"))

    raw_time = node.get("totalTime") or node.get("cookTime") or node.get("prepTime")
    if isinstance(raw_time, str):
        total_time = parse_iso_duration(raw_time)
    elif isinstance(raw_time, list) and raw_time and isinstance(raw_time[0], str):
        total_time = parse_iso_duration(raw_time[0])
    else:
        total_time = None

    raw_ingredients = node.get("recipeIngredient") or node.get("ingredients") or []
    if isinstance(raw_ingredients, str):
        raw_ingredients = [raw_ingredients]

    ingredients: list[dict[str, Any]] = []
    if isinstance(raw_ingredients, list):
        for item in raw_ingredients:
            if isinstance(item, str):
                s = item.strip()
                if s:
                    ingredients.append(parse_ingredient_line(s))
            elif isinstance(item, dict) and item.get("name"):
                s = str(item["name"]).strip()
                if s:
                    ingredients.append(parse_ingredient_line(s))

    raw_instructions = node.get("recipeInstructions")
    steps: list[str] = []
    if raw_instructions:
        steps = _collect_steps(raw_instructions)

    notes: list[str] = []
    if title_missing:
        notes.append("Missing recipe title in schema.org data")
    if not ingredients:
        notes.append("Missing ingredients in schema.org data")
    if not steps:
        notes.append("Missing instructions in schema.org data")
    if ingredients and any(
        (not ing.get("name")) or (not ing.get("staple") and ing.get("quantity") is None)
        for ing in ingredients
    ):
        notes.append("One or more non-staple ingredients missing quantity")

    if notes:
        needs_review = True
        review_notes = "; ".join(notes)
    else:
        needs_review = False
        review_notes = None

    return {
        "title": title,
        "servings": servings,
        "total_time": total_time,
        "ingredients": ingredients,
        "steps": steps,
        "needs_review": needs_review,
        "review_notes": review_notes,
    }


def extract_schema_org_recipe(html_content: str) -> dict[str, Any] | None:
    """Extract a recipe dict from schema.org JSON-LD scripts in HTML.

    Returns:
        {
            "title": str,
            "servings": int,
            "total_time": str | None,
            "ingredients": list[dict],
            "steps": list[str],
            "needs_review": bool,
            "review_notes": str | None,
        }
        or None if no Recipe JSON-LD node is found.
    """
    if not html_content:
        return None

    # Find all <script type="application/ld+json"> blocks
    pattern = re.compile(
        r'<script\b[^>]*?type\s*=\s*["\']?application/ld\+json[^"\'\s>]*["\']?[^>]*>(.*?)</script>',
        re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(html_content):
        raw_payload = match.group(1).strip()
        if not raw_payload:
            continue

        # Strip optional HTML comments or CDATA wrappers
        if raw_payload.startswith("<!--") and raw_payload.endswith("-->"):
            raw_payload = raw_payload[4:-3].strip()
        if raw_payload.startswith("/*<![CDATA[*/") and raw_payload.endswith("/*]]>*/"):
            raw_payload = raw_payload[13:-7].strip()
        elif raw_payload.startswith("<![CDATA[") and raw_payload.endswith("]]>"):
            raw_payload = raw_payload[9:-3].strip()

        try:
            payload = json.loads(raw_payload)
        except Exception:
            continue

        node = _find_recipe_node(payload)
        if node is not None:
            return _parse_recipe_node(node)

    return None


def extract_html_text_and_title(html_content: str) -> tuple[str, str | None]:
    """Strip script/style/noscript/svg and HTML markup to clean text, and extract <title>."""
    if not html_content:
        return ("", None)

    # 1. Extract <title> if present
    page_title: str | None = None
    m_title = re.search(r"<title\b[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
    if m_title:
        raw_title = m_title.group(1)
        clean_title = re.sub(r"<[^>]+>", "", raw_title)
        clean_title = html.unescape(clean_title)
        clean_title = " ".join(clean_title.split())
        if clean_title:
            page_title = clean_title

    # 2. Strip comments and non-prose blocks
    text = re.sub(r"<!--.*?-->", "", html_content, flags=re.DOTALL)
    text = re.sub(r"(?i)<script\b[^>]*>.*?</script>", "", text, flags=re.DOTALL)
    text = re.sub(r"(?i)<style\b[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"(?i)<noscript\b[^>]*>.*?</noscript>", "", text, flags=re.DOTALL)
    text = re.sub(r"(?i)<svg\b[^>]*>.*?</svg>", "", text, flags=re.DOTALL)

    # 3. Strip all remaining HTML tags, replacing with a space to prevent token collision
    text = re.sub(r"<[^>]+>", " ", text)

    # 4. Unescape HTML entities
    text = html.unescape(text)

    # 5. Collapse whitespace cleanly
    clean_text = " ".join(text.split())

    return (clean_text, page_title)

