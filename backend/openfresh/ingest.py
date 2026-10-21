"""Recipe ingestion helpers: parsing ingredient lines, ISO durations, and schema.org JSON-LD."""

import html
import json
import math
import os
import re
import sqlite3
import unicodedata
import urllib.parse
from typing import Any

import httpx

from openfresh import recipes

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
    "ml": "ml",
    "ml.": "ml",
    "milliliter": "ml",
    "milliliters": "ml",
    "millilitre": "ml",
    "millilitres": "ml",
    "l": "l",
    "l.": "l",
    "liter": "l",
    "liters": "l",
    "litre": "l",
    "litres": "l",
    "pt": "pt",
    "pt.": "pt",
    "pint": "pt",
    "pints": "pt",
    "qt": "qt",
    "qt.": "qt",
    "quart": "qt",
    "quarts": "qt",
    "gal": "gal",
    "gal.": "gal",
    "gallon": "gal",
    "gallons": "gal",
    "fl oz": "fl oz",
    "fl. oz.": "fl oz",
    "fl. oz": "fl oz",
    "fl oz.": "fl oz",
    "fluid ounce": "fl oz",
    "fluid ounces": "fl oz",
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
            denom = float(m_mixed_ascii.group(3))
            if denom != 0:
                qty = float(m_mixed_ascii.group(1)) + float(m_mixed_ascii.group(2)) / denom
                remainder = m_mixed_ascii.group(4)
        else:
            # 3. ASCII fraction alone: e.g. "1/2"
            m_frac_ascii = re.match(r"^(\d+)\s*/\s*(\d+)(?:\s+|$)(.*)$", s)
            if m_frac_ascii:
                denom = float(m_frac_ascii.group(2))
                if denom != 0:
                    qty = float(m_frac_ascii.group(1)) / denom
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
        m_multi = re.match(
            r"^(fluid\s+ounces?|fl\.?\s*oz\.?)(?:\s+|$)(.*)$",
            remainder,
            re.IGNORECASE,
        )
        if m_multi:
            unit = "fl oz"
            after_token = m_multi.group(2)
            name_part = re.sub(r"^of\s+", "", after_token, flags=re.IGNORECASE)
            name = name_part.split(",")[0].strip()
            quantity = qty
        else:
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

    if val.upper() in ("P", "PT"):
        return None

    m = re.match(
        r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$",
        val,
        re.IGNORECASE,
    )
    if m:
        if not any(m.group(g) is not None for g in ("days", "hours", "minutes", "seconds")):
            return None

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
        return "0m"

    return val


def _is_recipe_type(val: Any) -> bool:
    if isinstance(val, str):
        s = val.strip().lower()
        return s == "recipe" or s.endswith("/recipe") or s.endswith(":recipe")
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
    if isinstance(val, bool):
        return None
    if isinstance(val, int) and val > 0:
        return val
    if isinstance(val, float) and math.isfinite(val) and val > 0:
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

    # 3. Replace block tags with newlines
    text = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>|</h[1-6]>|</tr>", "\n", text)

    # 4. Strip all remaining HTML tags, replacing with a space to prevent token collision
    text = re.sub(r"<[^>]+>", " ", text)

    # 5. Unescape HTML entities
    text = html.unescape(text)

    # 6. Collapse horizontal whitespace per line and join non-empty lines with \n
    lines = []
    for line in text.splitlines():
        cleaned_line = " ".join(line.split())
        if cleaned_line:
            lines.append(cleaned_line)
    clean_text = "\n".join(lines)

    return (clean_text, page_title)


def is_video_url(url: str) -> bool:
    """Return True if the URL matches known video/social platforms."""
    if not url:
        return False
    u = url.strip()
    if "://" not in u:
        u = "https://" + u
    parsed = urllib.parse.urlparse(u)
    netloc = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower()

    if ":" in netloc:
        netloc = netloc.split(":")[0]

    video_domains = (
        "youtube.com",
        "youtu.be",
        "tiktok.com",
        "instagram.com",
        "vimeo.com",
        "twitch.tv",
        "fb.watch",
    )
    for domain in video_domains:
        if netloc == domain or netloc.endswith("." + domain):
            return True

    if netloc == "facebook.com" or netloc.endswith(".facebook.com"):
        if "/reel" in path:
            return True

    return False


def _clean_subtitle_text(text: str) -> str:
    """Strip VTT/SRT headers, cues, timestamps, and duplicate lines from subtitles."""
    trimmed = text.strip()
    if trimmed.startswith("{"):
        try:
            j_data = json.loads(trimmed)
            if isinstance(j_data, dict) and "events" in j_data:
                segs: list[str] = []
                for ev in j_data.get("events", []):
                    for s in ev.get("segs", []):
                        utf8_str = s.get("utf8", "")
                        if utf8_str:
                            segs.append(utf8_str)
                text = "".join(segs)
        except Exception:
            pass

    lines: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("WEBVTT") or s.startswith("NOTE"):
            continue
        if re.match(r"^\d+$", s):
            continue
        if "-->" in s:
            continue
        s = re.sub(r"<[^>]+>", "", s).strip()
        if s and (not lines or lines[-1] != s):
            lines.append(s)
    return "\n".join(lines)


def _get_track_text(entry: dict[str, Any], http_client: httpx.Client | None = None) -> str:
    """Retrieve raw text from a subtitle track entry, fetching url if necessary."""
    if "data" in entry and entry["data"]:
        return str(entry["data"])
    if "text" in entry and entry["text"]:
        return str(entry["text"])
    sub_url = entry.get("url")
    if sub_url and isinstance(sub_url, str):
        try:
            if http_client is not None:
                resp = http_client.get(sub_url)
            else:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.get(sub_url)
            if resp.status_code < 400:
                content = resp.text
                ext = str(entry.get("ext", "")).lower()
                if ext == "json3" or content.strip().startswith("{"):
                    try:
                        j_data = json.loads(content)
                        if isinstance(j_data, dict) and "events" in j_data:
                            segs = []
                            for ev in j_data["events"]:
                                for s in ev.get("segs", []):
                                    utf8_str = s.get("utf8", "")
                                    if utf8_str:
                                        segs.append(utf8_str)
                            return "".join(segs)
                    except Exception:
                        pass
                return content
        except Exception:
            return ""
    return ""


def _sort_formats(formats: list[Any]) -> list[dict[str, Any]]:
    pref = {"vtt": 0, "srv1": 1, "ttml": 2, "srt": 3, "json3": 4}
    valid = [f for f in formats if isinstance(f, dict)]
    return sorted(
        valid,
        key=lambda f: (
            0 if ("data" in f or "text" in f) else 1,
            pref.get(str(f.get("ext", "")).lower(), 10),
        ),
    )


def _sort_lang_keys(keys: list[str]) -> list[str]:
    def lang_priority(k: str) -> tuple[int, str]:
        kl = k.lower()
        if kl in ("en", "en-us", "en-gb", "en-ca", "en-au"):
            return (0, kl)
        if kl.startswith("en"):
            return (1, kl)
        return (2, kl)
    return sorted(keys, key=lang_priority)


def _extract_subtitle_text(sub_data: Any, http_client: httpx.Client | None = None) -> str:
    """Extract and clean text from various subtitle formats (string, dict, list)."""
    if not sub_data:
        return ""
    if isinstance(sub_data, str):
        return _clean_subtitle_text(sub_data)
    if isinstance(sub_data, list):
        sorted_fmts = _sort_formats(sub_data)
        for item in sorted_fmts:
            raw = _get_track_text(item, http_client)
            if raw:
                cleaned = _clean_subtitle_text(raw)
                if cleaned:
                    return cleaned
        return ""
    if isinstance(sub_data, dict):
        sorted_langs = _sort_lang_keys(list(sub_data.keys()))
        for lang in sorted_langs:
            val = sub_data[lang]
            res = _extract_subtitle_text(val, http_client)
            if res:
                return res
    return ""


def extract_video_text(
    url: str,
    ytdlp_runner: Any = None,
    http_client: httpx.Client | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Extract transcript, title, and description from a video URL via yt-dlp.

    Returns:
        (combined_text, video_title, error_note)
    """
    if ytdlp_runner is not None:
        try:
            info = ytdlp_runner(url)
        except Exception as exc:
            return (None, None, f"Video transcript unavailable: {exc}")
    else:
        try:
            import yt_dlp
        except ImportError as e:
            return (None, None, f"Video transcript unavailable: {e}")
        try:
            ydl_opts = {
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "quiet": True,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:
            return (None, None, f"Video transcript unavailable: {exc}")

    if not isinstance(info, dict):
        return (None, None, "Video transcript unavailable: empty metadata/transcript")

    video_title = str(info["title"]).strip() if info.get("title") else None
    description = str(info["description"]).strip() if info.get("description") else ""

    sub_text: str | None = None
    for sub_key in ("transcript", "requested_subtitles", "subtitles", "automatic_captions"):
        if info.get(sub_key):
            t = _extract_subtitle_text(info[sub_key], http_client=http_client)
            if t:
                sub_text = t
                break

    parts: list[str] = []
    if video_title:
        parts.append(video_title)
    if description:
        parts.append(description)
    if sub_text:
        parts.append(sub_text)

    combined = "\n\n".join(parts).strip()
    if not combined:
        return (None, video_title, "Video transcript unavailable: empty metadata/transcript")

    return (combined, video_title, None)


LLM_SYSTEM_PROMPT = (
    "You are a recipe extraction assistant. Extract structured recipe information "
    "from the provided text. Return ONLY a valid JSON object with the following fields:\n"
    "- title: string (recipe name)\n"
    "- servings: integer (default 2)\n"
    "- total_time: string or null (e.g. '45m', '1h 15m')\n"
    "- ingredients: list of objects with {raw: string, name: string, quantity: float or null, unit: string, staple: boolean}\n"
    "- steps: list of string instruction steps in order\n"
    "- low_confidence: boolean (true if the text did not contain a clear recipe or ingredients/steps were incomplete)\n"
    "- review_notes: string or null (explanation if confidence is low or info is missing)\n"
)


def extract_with_llm(
    text: str,
    fallback_title: str = "Untitled Recipe",
    llm_client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Call local LLM endpoint to extract structured recipe data from raw text."""
    base_url = os.environ.get("OPENFRESH_LLM_URL", "http://llm:11434/v1").rstrip("/")
    model = os.environ.get("OPENFRESH_LLM_MODEL", "gemma3n:e4b")
    api_key = os.environ.get("OPENFRESH_LLM_API_KEY", "ollama")

    payload = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {"role": "user", "content": text[:24000]},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        if llm_client is not None:
            resp = llm_client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
        else:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(f"{base_url}/chat/completions", json=payload, headers=headers)

        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        raw_content = str(data["choices"][0]["message"]["content"]).strip()
        parsed_json = None
        # 1. Try stripping exact code fences
        stripped = raw_content
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
            stripped = re.sub(r"\s*```$", "", stripped)
        try:
            parsed_json = json.loads(stripped)
        except Exception:
            parsed_json = None

        # 2. If preamble/conversational text exists before/after fence:
        if parsed_json is None:
            m_fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_content, re.DOTALL)
            if m_fence:
                try:
                    parsed_json = json.loads(m_fence.group(1))
                except Exception:
                    parsed_json = None

        # 3. If no fence or fence parse failed, try outermost JSON object {...}
        if parsed_json is None:
            m_brace = re.search(r"(\{.*\})", raw_content, re.DOTALL)
            if m_brace:
                try:
                    parsed_json = json.loads(m_brace.group(1))
                except Exception:
                    parsed_json = None

        if not isinstance(parsed_json, dict):
            raise ValueError("LLM returned non-dictionary JSON")
    except Exception as exc:
        return {
            "title": fallback_title,
            "servings": 2,
            "total_time": None,
            "ingredients": [],
            "steps": [],
            "needs_review": True,
            "review_notes": f"LLM extraction failed: {exc}",
        }

    # Normalize title
    title_val = parsed_json.get("title")
    if isinstance(title_val, str) and title_val.strip():
        extracted_title = title_val.strip()
    else:
        extracted_title = fallback_title

    # Normalize servings
    servings = _parse_servings(parsed_json.get("servings"))

    # Normalize total_time
    raw_time = parsed_json.get("total_time")
    if isinstance(raw_time, str) and raw_time.strip():
        total_time = parse_iso_duration(raw_time.strip())
    else:
        total_time = None

    # Normalize steps
    steps: list[str] = []
    raw_steps = parsed_json.get("steps") or []
    if isinstance(raw_steps, str):
        steps = _split_and_clean_steps(raw_steps)
    elif isinstance(raw_steps, list):
        for s in raw_steps:
            if isinstance(s, str):
                cleaned = " ".join(s.split())
                if cleaned:
                    steps.append(cleaned)
            elif isinstance(s, dict):
                t = s.get("text") or s.get("name")
                if t:
                    cleaned = " ".join(str(t).split())
                    if cleaned:
                        steps.append(cleaned)

    # Normalize ingredients
    ingredients: list[dict[str, Any]] = []
    raw_ingredients = parsed_json.get("ingredients") or []
    if isinstance(raw_ingredients, str):
        raw_ingredients = [raw_ingredients]
    elif not isinstance(raw_ingredients, list):
        raw_ingredients = []

    for ing in raw_ingredients:
        if isinstance(ing, str):
            s = ing.strip()
            if s:
                ingredients.append(parse_ingredient_line(s))
        elif isinstance(ing, dict):
            raw_val = str(ing.get("raw") or "").strip()
            name_val = str(ing.get("name") or "").strip()
            name_val = re.sub(r"^of\s+", "", name_val, flags=re.IGNORECASE).split(",")[0].strip()
            if not name_val:
                ingredients.append(parse_ingredient_line(raw_val))
            else:
                unit_val = str(ing.get("unit") or "").strip().lower()
                if unit_val in UNIT_ALIASES:
                    unit_val = UNIT_ALIASES[unit_val]
                elif unit_val.rstrip(".,") in UNIT_ALIASES:
                    unit_val = UNIT_ALIASES[unit_val.rstrip(".,")]

                is_staple = bool(ing.get("staple", False)) or (name_val.lower() in STAPLE_NAMES)

                qty_val = ing.get("quantity")
                if qty_val is not None:
                    try:
                        qty_val = float(qty_val)
                        if not math.isfinite(qty_val):
                            qty_val = None
                    except (ValueError, TypeError):
                        qty_val = None

                if not raw_val:
                    original_name = str(ing.get("name") or "").strip()
                    unit_raw = str(ing.get("unit") or "").strip()
                    parts = []
                    if qty_val is not None and math.isfinite(qty_val):
                        parts.append(str(int(qty_val)) if qty_val == int(qty_val) else str(qty_val))
                    if unit_raw:
                        parts.append(unit_raw)
                    elif unit_val:
                        parts.append(unit_val)
                    parts.append(original_name or name_val)
                    raw_val = " ".join(parts)

                ingredients.append({
                    "raw": raw_val,
                    "name": name_val,
                    "quantity": qty_val,
                    "unit": unit_val,
                    "staple": is_staple,
                })

    # Evaluate review flags
    notes: list[str] = []
    if parsed_json.get("low_confidence"):
        note = parsed_json.get("review_notes") or parsed_json.get("notes")
        notes.append(str(note) if note else "LLM reported low confidence")
    elif parsed_json.get("review_notes"):
        notes.append(str(parsed_json["review_notes"]))

    if not ingredients:
        notes.append("Missing ingredients")
    if not steps:
        notes.append("Missing instructions")
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
        "title": extracted_title,
        "servings": servings,
        "total_time": total_time,
        "ingredients": ingredients,
        "steps": steps,
        "needs_review": needs_review,
        "review_notes": review_notes,
    }


def ingest_recipe(
    conn: sqlite3.Connection,
    *,
    url: str | None = None,
    raw_text: str | None = None,
    title: str | None = None,
    http_client: httpx.Client | None = None,
    llm_client: httpx.Client | None = None,
    ytdlp_runner: Any = None,
) -> dict[str, Any]:
    """Orchestrate recipe ingestion from URL or raw text with never-fail guarantee."""
    clean_url = url.strip() if url and url.strip() else None
    clean_text = raw_text.strip() if raw_text and raw_text.strip() else None

    extracted: dict[str, Any]

    if clean_url and is_video_url(clean_url):
        if clean_text:
            extracted = extract_with_llm(
                clean_text,
                fallback_title=title or clean_url,
                llm_client=llm_client,
            )
        else:
            video_text, video_title, error_note = extract_video_text(
                clean_url, ytdlp_runner=ytdlp_runner, http_client=http_client
            )
            if video_text is not None:
                extracted = extract_with_llm(
                    video_text,
                    fallback_title=title or video_title or clean_url,
                    llm_client=llm_client,
                )
            else:
                extracted = {
                    "title": title or video_title or clean_url,
                    "servings": 2,
                    "total_time": None,
                    "ingredients": [],
                    "steps": [],
                    "needs_review": True,
                    "review_notes": error_note or "Video transcript unavailable",
                }
    elif clean_url:
        html_content: str | None = None
        fetch_error: str | None = None
        try:
            if http_client is not None:
                resp = http_client.get(clean_url)
            else:
                with httpx.Client(
                    follow_redirects=True,
                    timeout=15.0,
                    headers={"User-Agent": "OpenFresh/1.0 (Recipe Ingest)"},
                ) as client:
                    resp = client.get(clean_url)
            if resp.status_code >= 400:
                fetch_error = f"HTTP {resp.status_code}"
            else:
                html_content = resp.text
        except Exception as exc:
            fetch_error = str(exc)

        if html_content is not None:
            schema_recipe = None
            try:
                schema_recipe = extract_schema_org_recipe(html_content)
            except Exception:
                schema_recipe = None
            is_complete_jsonld = (
                schema_recipe is not None
                and schema_recipe.get("title")
                and schema_recipe.get("title") != "Untitled Recipe"
                and bool(schema_recipe.get("ingredients"))
                and bool(schema_recipe.get("steps"))
            )
            if is_complete_jsonld:
                extracted = schema_recipe
            else:
                page_text, page_title = extract_html_text_and_title(html_content)
                fallback_title_to_use = (
                    title
                    or (schema_recipe.get("title") if schema_recipe and schema_recipe.get("title") != "Untitled Recipe" else None)
                    or page_title
                    or clean_url
                )
                llm_extracted = extract_with_llm(
                    page_text,
                    fallback_title=fallback_title_to_use,
                    llm_client=llm_client,
                )
                if (
                    schema_recipe is not None
                    and not llm_extracted.get("ingredients")
                    and not llm_extracted.get("steps")
                    and (schema_recipe.get("ingredients") or schema_recipe.get("steps"))
                ):
                    extracted = schema_recipe
                    combined_notes = []
                    if schema_recipe.get("review_notes"):
                        combined_notes.append(schema_recipe["review_notes"])
                    if llm_extracted.get("review_notes"):
                        combined_notes.append(llm_extracted["review_notes"])
                    extracted["needs_review"] = True
                    extracted["review_notes"] = "; ".join(combined_notes) if combined_notes else "Incomplete recipe"
                else:
                    extracted = llm_extracted
        else:
            if clean_text:
                extracted = extract_with_llm(
                    clean_text,
                    fallback_title=title or clean_url,
                    llm_client=llm_client,
                )
            else:
                extracted = {
                    "title": title or clean_url,
                    "servings": 2,
                    "total_time": None,
                    "ingredients": [],
                    "steps": [],
                    "needs_review": True,
                    "review_notes": f"Webpage fetch failed: {fetch_error}",
                }
    elif clean_text:
        extracted = extract_with_llm(
            clean_text,
            fallback_title=title or "Untitled Recipe",
            llm_client=llm_client,
        )
    else:
        extracted = {
            "title": title or "Untitled Recipe",
            "servings": 2,
            "total_time": None,
            "ingredients": [],
            "steps": [],
            "needs_review": True,
            "review_notes": "No URL or recipe text provided",
        }

    final_title = title.strip() if (title and title.strip()) else (extracted.get("title") or "Untitled Recipe")

    recipe_id = recipes.create_recipe(
        conn,
        title=final_title,
        servings=extracted.get("servings", 2),
        source_url=clean_url,
        steps=extracted.get("steps", []),
        total_time=extracted.get("total_time"),
        needs_review=extracted.get("needs_review", False),
        review_notes=extracted.get("review_notes"),
    )

    for ing in extracted.get("ingredients", []):
        recipes.add_ingredient(
            conn,
            recipe_id,
            raw=ing.get("raw") or ing.get("name") or "",
            quantity=ing.get("quantity"),
            unit=ing.get("unit", ""),
            staple=bool(ing.get("staple", False)),
            item_name=ing.get("name"),
        )

    saved = recipes.get_recipe(conn, recipe_id)
    assert saved is not None
    return saved


def reingest_recipe(
    conn: sqlite3.Connection,
    recipe_id: int,
    raw_text: str,
    *,
    llm_client: httpx.Client | None = None,
) -> dict[str, Any] | None:
    """Re-extract an existing recipe from user-pasted text and update it."""
    existing = recipes.get_recipe(conn, recipe_id)
    if existing is None:
        return None

    extracted = extract_with_llm(
        raw_text,
        fallback_title=existing["title"],
        llm_client=llm_client,
    )

    return recipes.update_recipe(
        conn,
        recipe_id,
        title=extracted["title"],
        servings=extracted["servings"],
        steps=extracted["steps"],
        total_time=extracted["total_time"],
        needs_review=extracted["needs_review"],
        review_notes=extracted["review_notes"],
        ingredients=extracted["ingredients"],
    )


