"""Receipt ingestion and text extraction utilities."""

import datetime
import io
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any

import httpx
from PIL import Image
import pytesseract
from pypdf import PdfReader

PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}

UNIT_NORMALIZATION = {
    "gal": "gal",
    "gallon": "gal",
    "gallons": "gal",
    "oz": "oz",
    "ounce": "oz",
    "ounces": "oz",
    "fl oz": "fl oz",
    "floz": "fl oz",
    "fl. oz.": "fl oz",
    "fl. oz": "fl oz",
    "fluid ounce": "fl oz",
    "fluid ounces": "fl oz",
    "lb": "lb",
    "lbs": "lb",
    "pound": "lb",
    "pounds": "lb",
    "g": "g",
    "gram": "g",
    "grams": "g",
    "kg": "kg",
    "kgs": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "ml": "ml",
    "l": "l",
    "liter": "l",
    "liters": "l",
    "pt": "pt",
    "pint": "pt",
    "pints": "pt",
    "qt": "qt",
    "quart": "qt",
    "quarts": "qt",
    "ct": "ct",
    "count": "ct",
    "pk": "pk",
    "pack": "pk",
    "pkg": "pk",
}

EXCLUDED_LINE_PREFIXES = (
    "subtotal",
    "total",
    "tax",
    "cash",
    "change",
    "balance",
    "visa",
    "mastercard",
    "amex",
    "discover",
    "debit",
    "credit",
    "account",
    "tend",
    "tendered",
    "approved",
    "ref #",
    "trans #",
    "terminal",
    "manager",
    "walmart",
    "save money",
    "live better",
    "phone",
    "store",
    "order",
    "items sold",
    "tc#",
    "you saved",
    "coupon",
    "discount",
)

WALMART_ITEM_RE = re.compile(
    r"^(?P<raw_name>.+?)\s+"
    r"(?P<upc>\d{6,14})\s+"
    r"(?P<price>-?\d+\.\d{2})"
    r"(?:\s+(?P<flag>[A-Za-z0-9]))?\s*$"
)

WALMART_ITEM_NO_UPC_RE = re.compile(
    r"^(?P<raw_name>.+?)\s+"
    r"(?P<price>-?\d+\.\d{2})\s+"
    r"(?P<flag>[FTNXOY])\s*$"
)

WALMART_ONLINE_ITEM_RE = re.compile(
    r"^(?P<raw_name>.+?)"
    r"(?:\s+\d+\s+(?:shopped|weight adjusted|substituted))?"
    r"\s+(?:Qty\s*:?|x)\s*(?P<qty>\d+(?:\.\d+)?)\s+\$?(?P<price>\d+\.\d{2})\s*$",
    re.IGNORECASE,
)

GENERIC_ITEM_RE = re.compile(
    r"^(?P<raw_name>.+?)\s+"
    r"(?:(?:Qty\s*:?|x)\s*(?P<qty>\d+(?:\.\d+)?)\s+)?\$?(?P<price>\d+\.\d{2})\s*$",
    re.IGNORECASE,
)

GENERIC_EXCLUDED_PREFIXES = (
    "subtotal",
    "total",
    "tax",
    "balance",
    "cash",
    "visa",
    "mastercard",
    "amex",
    "discover",
    "debit",
    "credit",
    "tender",
    "change",
    "savings",
    "discount",
    "tip",
    "order#",
    "order #",
    "invoice",
    "buyer",
    "store",
    "delivery",
    "shipping",
    "fees",
    "fee",
    "shopped",
    "driver tip",
    "free delivery",
    "http",
    "www.",
)

MONTH_MAP = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

WEIGHED_LINE_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*(lb|lbs|kg|g|oz)\s*@\s*",
    re.IGNORECASE,
)

RECEIPT_LLM_SYSTEM_PROMPT = (
    "You are a receipt extraction assistant. Extract structured receipt information "
    "from the provided receipt text. Return ONLY a valid JSON object with the following fields:\n"
    "- store: string (store name, e.g. 'Walmart', 'Trader Joe\\'s', 'Kroger', or 'Unknown')\n"
    "- date: string (receipt date in YYYY-MM-DD format)\n"
    "- total: float (total amount paid on receipt)\n"
    "- currency: string (3-letter currency code, default 'USD')\n"
    "- items: list of objects with:\n"
    "    - raw_name: string (raw line item description from receipt)\n"
    "    - name: string (clean, human-readable grocery product name)\n"
    "    - quantity: float (numeric quantity, default 1.0)\n"
    "    - unit: string (measurement unit such as 'lb', 'oz', 'gal', 'g', 'kg', 'ct', or '' for count)\n"
    "    - price: float (item line price, never negative)\n"
    "Important rules:\n"
    "1. Exclude coupons, discounts, tender/change lines, and taxes from items.\n"
    "2. If an item was weighed (e.g. produce by weight), quantity should be the weight and unit should be the weight unit (e.g. 'lb').\n"
    "3. Clean item names by stripping internal codes, store abbreviations, and UPC numbers.\n"
)


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract raw text from a PDF document byte stream using pypdf.

    Concatenates text across all pages. Returns an empty string if no
    text is found or if parsing fails.
    """
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages_text: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                pages_text.append(page_text)
        return "\n".join(pages_text).strip()
    except Exception:
        return ""


def extract_text_from_image(image_bytes: bytes) -> str:
    """Extract text from an image byte stream using Tesseract OCR.

    Returns extracted text string, or empty string on failure.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception:
        return ""


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Dispatch text extraction based on file extension.

    Supports PDF documents and common raster image formats (PNG, JPG, WEBP, etc.).
    Raises ValueError for unsupported file extensions.
    """
    ext = Path(filename).suffix.lower()
    if ext in PDF_EXTENSIONS:
        return extract_text_from_pdf(file_bytes)
    if ext in IMAGE_EXTENSIONS:
        return extract_text_from_image(file_bytes)
    raise ValueError(f"Unsupported file type: {filename}")


def _extract_receipt_date(text: str) -> str:
    """Extract receipt date formatted as YYYY-MM-DD from raw text."""
    # 1. Textual month e.g. Oct 29, 2026 or October 29, 2026
    m_text = re.search(r"\b([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(20\d{2})\b", text)
    if m_text:
        mon_str = m_text.group(1).lower()
        if mon_str in MONTH_MAP:
            m = MONTH_MAP[mon_str]
            d = int(m_text.group(2))
            y = int(m_text.group(3))
            if 1 <= d <= 31:
                return f"{y:04d}-{m:02d}-{d:02d}"

    # 2. YYYY-MM-DD
    m_iso = re.search(r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b", text)
    if m_iso:
        y, m, d = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
        if 1 <= m <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{m:02d}-{d:02d}"

    # 3. MM/DD/YYYY or MM-DD-YYYY
    m_us4 = re.search(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2})\b", text)
    if m_us4:
        m, d, y = int(m_us4.group(1)), int(m_us4.group(2)), int(m_us4.group(3))
        if 1 <= m <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{m:02d}-{d:02d}"
        if 1 <= d <= 12 and 1 <= m <= 31:
            return f"{y:04d}-{d:02d}-{m:02d}"

    # 4. MM/DD/YY or MM-DD-YY
    m_us2 = re.search(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2})\b", text)
    if m_us2:
        m, d, y2 = int(m_us2.group(1)), int(m_us2.group(2)), int(m_us2.group(3))
        y = 2000 + y2
        if 1 <= m <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{m:02d}-{d:02d}"

    return datetime.date.today().isoformat()


def _clean_item_name_and_unit(raw_name: str) -> tuple[str, str]:
    """Clean store brand prefixes and extract package unit from Walmart item name."""
    s = re.sub(
        r"^(?:GV|GREAT\s+VALUE|MARKETSIDE|EQUATE|MAINSTAYS|PARENTS\s+CHOICE|PARENT'S\s+CHOICE|FRESHNESS\s+GUARANTEED)\s+",
        "",
        raw_name.strip(),
        flags=re.IGNORECASE,
    )

    unit = ""
    m_pkg = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(FL\.?\s*OZ|OZ|GAL(?:LON)?|LB|LBS|CT|COUNT|PK|PKG|PT|QT|G|KG|ML|L)\b\.?"
        r"(?:\s*(?:JAR|BOTTLE|CARTON|TRAY|CONTAINER|BOX|BAG|TUB|PACK|CAN|CANS|BLOCK|\(FROZEN\)))?\s*$",
        s,
        re.IGNORECASE,
    )
    is_frozen = bool(re.search(r"\(frozen\)", s, re.IGNORECASE))
    if m_pkg:
        unit_raw = m_pkg.group(2).lower().replace(".", "").strip()
        unit = UNIT_NORMALIZATION.get(unit_raw, unit_raw)
        s = s[: m_pkg.start()].strip()

    s = s.rstrip(", -")
    if is_frozen and not re.search(r"\(frozen\)", s, re.IGNORECASE):
        s += " (Frozen)"

    cleaned_name = " ".join(s.split())
    if cleaned_name.isupper() or cleaned_name.islower():
        words = []
        for w in cleaned_name.split():
            words.append(w.capitalize())
        cleaned_name = " ".join(words)
        cleaned_name = re.sub(r"'S\b", "'s", cleaned_name)

    return (cleaned_name or raw_name.strip(), unit)


def parse_walmart_receipt_text(text: str) -> dict[str, Any] | None:
    """Parse deterministic Walmart receipt text (digital or printed).

    Returns structured receipt dict or None if no valid items are parsed.
    """
    if not text or not text.strip():
        return None

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None

    items: list[dict[str, Any]] = []
    total: float | None = None

    for line in lines:
        # Check for Total line
        m_tot = re.match(
            r"^(?:GRAND\s+|FINAL\s+)?TOTAL(?:\s+(?:PURCHASE|SALE|DUE))?:?\s*(?:\$\s*)?(\d+\.\d{2})",
            line,
            re.IGNORECASE,
        )
        if m_tot and not line.lower().startswith(("subtotal", "total tax")):
            total = float(m_tot.group(1))
            continue

        # Check for weighed line following an item
        m_weighed = WEIGHED_LINE_RE.match(line)
        if m_weighed and items:
            items[-1]["quantity"] = float(m_weighed.group(1))
            unit_raw = m_weighed.group(2).lower()
            items[-1]["unit"] = UNIT_NORMALIZATION.get(unit_raw, unit_raw)
            continue

        # Check for quantity multiplier line
        m_qty = re.match(r"^\s*(\d+(?:\.\d+)?)\s*@\s*(\d+\.\d{2})", line)
        if m_qty and items:
            items[-1]["quantity"] = float(m_qty.group(1))
            continue

        line_lower = line.lower()
        if any(line_lower.startswith(p) for p in EXCLUDED_LINE_PREFIXES):
            continue

        # Try matching item line with UPC
        m_item = WALMART_ITEM_RE.match(line)
        if not m_item:
            # Try matching item line without UPC but with tax flag
            m_item = WALMART_ITEM_NO_UPC_RE.match(line)

        if m_item:
            raw_name = m_item.group("raw_name").strip()
            price_val = float(m_item.group("price"))
            # Discard coupons/discounts or negative prices from items
            if price_val < 0 or any(kw in raw_name.lower() for kw in ("coupon", "discount")):
                continue

            cleaned_name, unit = _clean_item_name_and_unit(raw_name)
            items.append({
                "raw_name": raw_name,
                "name": cleaned_name,
                "quantity": 1.0,
                "unit": unit,
                "price": price_val,
            })
            continue

        # Try online order item format (e.g. "Item name Qty 1 $2.82")
        m_online = WALMART_ONLINE_ITEM_RE.match(line)
        if m_online:
            raw_name = m_online.group("raw_name").strip()
            price_val = float(m_online.group("price"))
            qty_val = float(m_online.group("qty"))
            if price_val < 0 or any(kw in raw_name.lower() for kw in ("coupon", "discount", "savings")):
                continue

            cleaned_name, unit = _clean_item_name_and_unit(raw_name)
            items.append({
                "raw_name": raw_name,
                "name": cleaned_name,
                "quantity": qty_val,
                "unit": unit,
                "price": price_val,
            })
            continue

    if not items:
        return None

    if total is None:
        total = round(sum(i["price"] for i in items), 2)

    date_str = _extract_receipt_date(text)

    return {
        "store": "Walmart",
        "date": date_str,
        "total": total,
        "currency": "USD",
        "items": items,
    }


def parse_generic_receipt_text(text: str) -> dict[str, Any] | None:
    """Parse receipt text using generic line-item heuristics.

    Acts as a resilient fallback for non-Walmart receipts or when LLM is unavailable.
    """
    if not text or not text.strip():
        return None

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None

    items: list[dict[str, Any]] = []
    total: float | None = None
    detected_store = "Unknown Store"

    for i, line in enumerate(lines):
        # Look for store name in early header lines
        if i < 4 and detected_store == "Unknown Store":
            for known in ("Walmart", "Trader Joe's", "Kroger", "Target", "Aldi", "Costco", "Publix", "Whole Foods", "Safeway", "Meijer", "HEB"):
                if known.lower() in line.lower():
                    detected_store = known
                    break

        # Check total
        m_tot = re.match(
            r"^(?:GRAND\s+|FINAL\s+)?TOTAL(?:\s+(?:PURCHASE|SALE|DUE))?:?\s*(?:\$\s*)?(\d+\.\d{2})",
            line,
            re.IGNORECASE,
        )
        if m_tot and not line.lower().startswith(("subtotal", "total tax")):
            total = float(m_tot.group(1))
            continue

        line_lower = line.lower()
        if any(line_lower.startswith(p) for p in GENERIC_EXCLUDED_PREFIXES):
            continue

        m_item = GENERIC_ITEM_RE.match(line)
        if m_item:
            raw_name = m_item.group("raw_name").strip()
            price_val = float(m_item.group("price"))
            qty_raw = m_item.group("qty")
            qty_val = float(qty_raw) if qty_raw else 1.0

            # Ignore lines that look like payment, tax, or have no alphabetic letters
            if price_val <= 0 or not re.search(r"[A-Za-z]{2,}", raw_name):
                continue
            if any(kw in raw_name.lower() for kw in ("coupon", "discount", "savings", "subtotal", "tax", "total", "driver tip")):
                continue

            cleaned_name, unit = _clean_item_name_and_unit(raw_name)
            items.append({
                "raw_name": raw_name,
                "name": cleaned_name,
                "quantity": qty_val,
                "unit": unit,
                "price": price_val,
            })

    if not items:
        return None

    if total is None:
        total = round(sum(i["price"] for i in items), 2)

    date_str = _extract_receipt_date(text)

    return {
        "store": detected_store,
        "date": date_str,
        "total": total,
        "currency": "USD",
        "items": items,
    }



def parse_receipt_with_llm(text: str, client: httpx.Client | None = None) -> dict[str, Any]:
    """Call Ollama / OpenAI-compatible LLM to extract structured receipt data."""
    base_url = os.environ.get("OPENFRESH_LLM_URL", "http://llm:11434/v1").rstrip("/")
    model = os.environ.get("OPENFRESH_LLM_MODEL", "gemma3n:e4b")
    api_key = os.environ.get("OPENFRESH_LLM_API_KEY", "ollama")

    payload = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": RECEIPT_LLM_SYSTEM_PROMPT},
            {"role": "user", "content": text[:24000]},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        if client is not None:
            resp = client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
        else:
            timeout_s = float(os.environ.get("OPENFRESH_LLM_TIMEOUT", "300.0"))
            with httpx.Client(timeout=timeout_s) as http_client:
                resp = http_client.post(f"{base_url}/chat/completions", json=payload, headers=headers)

        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        raw_content = str(data["choices"][0]["message"]["content"]).strip()
        parsed_json = None

        stripped = raw_content
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
            stripped = re.sub(r"\s*```$", "", stripped)
        try:
            parsed_json = json.loads(stripped)
        except Exception:
            parsed_json = None

        if parsed_json is None:
            m_fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_content, re.DOTALL)
            if m_fence:
                try:
                    parsed_json = json.loads(m_fence.group(1))
                except Exception:
                    parsed_json = None

        if parsed_json is None:
            m_brace = re.search(r"(\{.*\})", raw_content, re.DOTALL)
            if m_brace:
                try:
                    parsed_json = json.loads(m_brace.group(1))
                except Exception:
                    parsed_json = None

        if not isinstance(parsed_json, dict):
            raise ValueError("LLM returned non-dictionary JSON")
    except Exception:
        return {
            "store": "Unknown",
            "date": datetime.date.today().isoformat(),
            "total": 0.0,
            "currency": "USD",
            "items": [],
        }

    store = str(parsed_json.get("store") or "Unknown").strip()
    raw_date = str(parsed_json.get("date") or "").strip()
    date_val = _extract_receipt_date(raw_date) if raw_date else datetime.date.today().isoformat()
    try:
        total_val = float(parsed_json.get("total") or 0.0)
    except (ValueError, TypeError):
        total_val = 0.0
    currency_val = str(parsed_json.get("currency") or "USD").strip()

    raw_items = parsed_json.get("items") or []
    items: list[dict[str, Any]] = []
    if isinstance(raw_items, list):
        for it in raw_items:
            if not isinstance(it, dict):
                continue
            raw_n = str(it.get("raw_name") or it.get("name") or "").strip()
            name_n = str(it.get("name") or it.get("raw_name") or "").strip()
            if not name_n:
                continue
            try:
                qty = float(it.get("quantity") or 1.0)
            except (ValueError, TypeError):
                qty = 1.0
            unit_str = str(it.get("unit") or "").strip().lower()
            unit_str = UNIT_NORMALIZATION.get(unit_str, unit_str)
            try:
                price_val = max(0.0, float(it.get("price") or 0.0))
            except (ValueError, TypeError):
                price_val = 0.0

            items.append({
                "raw_name": raw_n or name_n,
                "name": name_n,
                "quantity": qty,
                "unit": unit_str,
                "price": price_val,
            })

    return {
        "store": store,
        "date": date_val,
        "total": total_val,
        "currency": currency_val,
        "items": items,
    }


def parse_receipt_data(text: str, client: httpx.Client | None = None) -> dict[str, Any]:
    """Parse receipt text into structured receipt data.

    Tries deterministic Walmart heuristics first; if no items are found,
    attempts LLM extraction, and falls back to generic line-item heuristics.
    """
    walmart_result = parse_walmart_receipt_text(text)
    if walmart_result is not None and len(walmart_result.get("items", [])) > 0:
        return walmart_result

    generic_result = parse_generic_receipt_text(text)

    try:
        llm_result = parse_receipt_with_llm(text, client=client)
        if llm_result is not None and len(llm_result.get("items", [])) > 0:
            return llm_result
    except Exception:
        pass

    if generic_result is not None and len(generic_result.get("items", [])) > 0:
        return generic_result

    return {
        "store": "Unknown",
        "date": _extract_receipt_date(text),
        "total": 0.0,
        "currency": "USD",
        "items": [],
    }


NON_FOOD_RE = re.compile(
    r"\b("
    r"motor\s*oil|engine\s*oil|brake\s*fluid|antifreeze|wiper\s*fluid|"
    r"batter(?:y|ies)|"
    r"paper\s*towels?|toilet\s*paper|bath\s*tissue|facial\s*tissue|kleenex|napkins?|"
    r"detergents?|fabric\s*softener|bleach|dishwasher|"
    r"trash\s*bags?|garbage\s*bags?|"
    r"(?:aluminum\s+)?foil|plastic\s*wrap|cling\s*wrap|ziploc|storage\s*bags?|"
    r"(?:dish|hand|bar)?\s*soaps?|shampoos?|conditioners?|body\s*wash|deodorant|"
    r"toothpastes?|toothbrush(?:es)?|dental\s*floss|"
    r"light\s*bulbs?|cleaners?|disinfectant|wipes?|hardware"
    r")\b",
    re.IGNORECASE,
)

FREEZER_RE = re.compile(
    r"\b("
    r"ice\s*cream|frozen|pizzas?|popsicles?|ice\s*pops?|gelato|sorbets?|waffles?"
    r")\b",
    re.IGNORECASE,
)

FRIDGE_EXCLUDE_RE = re.compile(
    r"\b("
    r"(?:peanut|almond|apple|cookie|cocoa|shea)\s+butter|"
    r"nutmeg|graham(?:\s+crackers?)?|"
    r"cream\s+of\s+(?:mushroom|chicken|celery)|shaving\s+cream"
    r")\b",
    re.IGNORECASE,
)

FRIDGE_MEAT_RE = re.compile(
    r"\b("
    r"meats?|beef|chickens?|pork|fish(?:es)?|seafood|salmon|tuna|turkey|"
    r"bacon|sausages?|hams?|steaks?|ribeye|patt(?:y|ies)"
    r")\b",
    re.IGNORECASE,
)

FRIDGE_DAIRY_RE = re.compile(
    r"\b("
    r"\w*milks?|dairy|yog[h]?urts?|\w*cheese(?:s)?|butter|"
    r"(?:sour\s+)?cream|cottage\s+cheese|eggs?|tofu|hummus|guacamole|salsa|mayo(?:nnaise)?|refrigerated"
    r")\b",
    re.IGNORECASE,
)

FRIDGE_PRODUCE_RE = re.compile(
    r"\b("
    r"produce|\w*berr(?:y|ies)|salads?|lettuce|spinach|kale|celery|cucumbers?|"
    r"carrots?|broccoli|cauliflower|asparagus|mushrooms?|avocados?|"
    r"tomatoes?|bananas?|apples?|oranges?|grapes?"
    r")\b",
    re.IGNORECASE,
)

PANTRY_BAKERY_RE = re.compile(
    r"\b("
    r"breads?|bagels?|tortillas?|buns?|bakery|croissants?|muffins?"
    r")\b",
    re.IGNORECASE,
)

PANTRY_BEVERAGE_RE = re.compile(
    r"\b("
    r"juices?|sodas?|coffee|tea|beverages?|drinks?"
    r")\b",
    re.IGNORECASE,
)

PANTRY_DRY_RE = re.compile(
    r"\b("
    r"pastas?|rice|beans?|cereals?|flour|sugar|oils?|sauces?|soups?|canned|"
    r"spices?|snacks?|chips?|crackers?|cookies?|nuts?|oats|peanut\s+butter"
    r")\b",
    re.IGNORECASE,
)


def _find_item_match(
    conn: sqlite3.Connection, name: str, raw_name: str
) -> tuple[int | None, str | None]:
    """Find matched item_id and category from item_aliases and items tables."""
    def _norm(s: str) -> str:
        return " ".join(s.split()).lower()

    candidates: list[str] = []
    norm_n = _norm(name)
    if norm_n:
        candidates.append(norm_n)
    norm_r = _norm(raw_name)
    if norm_r and norm_r not in candidates:
        candidates.append(norm_r)

    # 1. Alias match takes precedence
    for cand in candidates:
        row = conn.execute(
            "SELECT item_id FROM item_aliases WHERE alias = ? OR LOWER(alias) = ?",
            (cand, cand),
        ).fetchone()
        if row is not None:
            item_id = row[0]
            cat_row = conn.execute(
                "SELECT category FROM items WHERE id = ?", (item_id,)
            ).fetchone()
            category = cat_row[0] if cat_row is not None and cat_row[0] else None
            return (item_id, category)

    # 2. Exact items name match
    for cand in candidates:
        row = conn.execute(
            "SELECT id, category FROM items WHERE name = ? OR LOWER(name) = ?",
            (cand, cand),
        ).fetchone()
        if row is not None:
            item_id = row[0]
            category = row[1] if row[1] else None
            return (item_id, category)

    return (None, None)


def _find_prior_location(conn: sqlite3.Connection, item_id: int) -> str | None:
    """Find prior storage location for an item from inventory or events."""
    row = conn.execute(
        "SELECT location FROM inventory WHERE item_id = ? "
        "ORDER BY (quantity > 0) DESC, updated_at DESC, id DESC LIMIT 1",
        (item_id,),
    ).fetchone()
    if row is not None and row[0]:
        loc = str(row[0]).lower().strip()
        if loc in {"pantry", "fridge", "freezer"}:
            return loc

    ev_row = conn.execute(
        "SELECT location FROM inventory_events "
        "WHERE item_id = ? AND location IN ('pantry', 'fridge', 'freezer') "
        "ORDER BY created_at DESC, id DESC LIMIT 1",
        (item_id,),
    ).fetchone()
    if ev_row is not None and ev_row[0]:
        loc = str(ev_row[0]).lower().strip()
        if loc in {"pantry", "fridge", "freezer"}:
            return loc

    return None


def _infer_heuristics(
    name: str, raw_name: str, category: str | None
) -> tuple[str, str | None, bool]:
    """Infer (suggested_location, category, include) based on text patterns."""
    text = f"{name} {raw_name} {category or ''}".lower()

    # Check non-food exclusion first
    if NON_FOOD_RE.search(text):
        return ("pantry", category or "household", False)

    # Check freezer keywords next (e.g. "frozen pizza", "ice cream", "frozen chicken")
    if FREEZER_RE.search(text):
        return ("freezer", category or "frozen", True)

    # Check fridge keywords (unless explicitly excluded, e.g. peanut butter, nutmeg)
    if not FRIDGE_EXCLUDE_RE.search(text):
        if FRIDGE_MEAT_RE.search(text):
            return ("fridge", category or "meat", True)
        if FRIDGE_DAIRY_RE.search(text):
            return ("fridge", category or "dairy", True)
        if FRIDGE_PRODUCE_RE.search(text):
            return ("fridge", category or "produce", True)

    # Check pantry categories
    if PANTRY_BAKERY_RE.search(text):
        return ("pantry", category or "bakery", True)
    if PANTRY_BEVERAGE_RE.search(text):
        return ("pantry", category or "beverages", True)
    if PANTRY_DRY_RE.search(text):
        return ("pantry", category or "pantry", True)

    # Default fallback
    return ("pantry", category, True)


def enrich_receipt_items(
    conn: sqlite3.Connection, parsed: dict[str, Any]
) -> dict[str, Any]:
    """Enrich receipt line items with database matching and location heuristics.

    Adds `matched_item_id`, `suggested_location`, `category`, and `include`
    to each line item in `parsed['items']`.
    """
    result = dict(parsed)
    raw_items = parsed.get("items") or []
    enriched_items: list[dict[str, Any]] = []

    for item in raw_items:
        enriched = dict(item)
        name = str(enriched.get("name") or enriched.get("raw_name") or "").strip()
        raw_name = str(enriched.get("raw_name") or enriched.get("name") or "").strip()

        matched_id, db_category = _find_item_match(conn, name, raw_name)
        category = db_category or enriched.get("category")

        prior_location = _find_prior_location(conn, matched_id) if matched_id is not None else None

        inferred_loc, inferred_cat, inferred_include = _infer_heuristics(name, raw_name, category)

        # Prior inventory location beats keyword heuristic
        suggested_location = prior_location or inferred_loc

        # If non-food matched, include is False; otherwise preserve or default to True
        if not inferred_include:
            include = False
        else:
            include = bool(enriched.get("include", True))

        final_category = category or inferred_cat

        enriched["matched_item_id"] = matched_id
        enriched["suggested_location"] = suggested_location
        enriched["category"] = final_category
        enriched["include"] = include
        enriched_items.append(enriched)

    result["items"] = enriched_items
    return result


