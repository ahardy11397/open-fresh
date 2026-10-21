"""Layered pricing: own library > Open Prices lookup > category estimates.

Every priced line carries a source label: "own", "openprices", or "estimate".
Money values are (amount: float, currency: str).
"""

from __future__ import annotations

import sqlite3

# Re-export: make_lookup is consumed through the injectable-lookup seam.
from openfresh.openprices import make_lookup  # noqa: F401

_DEFAULT_LOOKUP = object()

# Standard culinary conversions to base units (ml for volume, g for weight).
_VOLUME_ML: dict[str, float] = {
    "ml": 1.0,
    "milliliter": 1.0,
    "milliliters": 1.0,
    "l": 1000.0,
    "liter": 1000.0,
    "liters": 1000.0,
    "tsp": 5.0,
    "teaspoon": 5.0,
    "teaspoons": 5.0,
    "tbsp": 15.0,
    "tablespoon": 15.0,
    "tablespoons": 15.0,
    "fl oz": 30.0,
    "floz": 30.0,
    "cup": 240.0,
    "cups": 240.0,
    "pt": 480.0,
    "pint": 480.0,
    "pints": 480.0,
    "qt": 960.0,
    "quart": 960.0,
    "quarts": 960.0,
    "gal": 3840.0,
    "gallon": 3840.0,
    "gallons": 3840.0,
}

_WEIGHT_G: dict[str, float] = {
    "g": 1.0,
    "gram": 1.0,
    "grams": 1.0,
    "kg": 1000.0,
    "kilogram": 1000.0,
    "kilograms": 1000.0,
    "oz": 28.3495,
    "ounce": 28.3495,
    "ounces": 28.3495,
    "lb": 453.592,
    "lbs": 453.592,
    "pound": 453.592,
    "pounds": 453.592,
}


def _norm_unit(unit: str | None) -> str:
    return " ".join((unit or "").split()).lower()


def convert_quantity(quantity: float, from_unit: str, to_unit: str) -> float | None:
    """Convert ``quantity`` from ``from_unit`` into ``to_unit`` when compatible.

    Returns ``None`` when the two units belong to different or unknown
    dimensions and are not identical.
    """
    u_from = _norm_unit(from_unit)
    u_to = _norm_unit(to_unit)
    if u_from == u_to:
        return quantity
    if u_from in _VOLUME_ML and u_to in _VOLUME_ML:
        return quantity * (_VOLUME_ML[u_from] / _VOLUME_ML[u_to])
    if u_from in _WEIGHT_G and u_to in _WEIGHT_G:
        return quantity * (_WEIGHT_G[u_from] / _WEIGHT_G[u_to])
    return None


class PricePer(tuple):
    """3-tuple ``(price, source, currency)`` carrying package size metadata.

    Comparing or unpacking ``PricePer`` behaves identically to a regular
    3-tuple ``(price, source, currency)``, while ``pkg_qty`` and ``pkg_unit``
    remain accessible to ``convert()`` for bulk/fractional scaling.
    """

    pkg_qty: float
    pkg_unit: str

    def __new__(
        cls,
        price: float,
        source: str,
        currency: str | None,
        pkg_qty: float = 1.0,
        pkg_unit: str = "",
    ) -> PricePer:
        obj = super().__new__(cls, (float(price), source, currency))
        obj.pkg_qty = float(pkg_qty) if pkg_qty and pkg_qty > 0 else 1.0
        obj.pkg_unit = _norm_unit(pkg_unit)
        return obj


def record_own_price(
    conn: sqlite3.Connection,
    item_id: int,
    price: float,
    currency: str,
    date: str,
    source: str = "manual",
    package_quantity: float = 1.0,
    package_unit: str = "",
) -> None:
    """Record a first-hand price observation for an item."""
    conn.execute(
        "INSERT INTO prices_own"
        " (item_id, price, currency, date, source, package_quantity, package_unit)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (item_id, price, currency, date, source, package_quantity, _norm_unit(package_unit)),
    )
    conn.commit()


def set_estimate(
    conn: sqlite3.Connection,
    item_id: int | None,
    category: str | None,
    price: float,
    currency: str,
    package_quantity: float = 1.0,
    package_unit: str = "",
) -> None:
    """Record a category (or item-specific) price estimate."""
    norm_cat = " ".join(category.split()).lower() if category is not None else None
    conn.execute(
        "INSERT INTO price_estimates"
        " (item_id, category, price, currency, package_quantity, package_unit)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (item_id, norm_cat, price, currency, package_quantity, _norm_unit(package_unit)),
    )
    conn.commit()


def _own_price(conn: sqlite3.Connection, item_id: int) -> PricePer | None:
    row = conn.execute(
        "SELECT price, currency, package_quantity, package_unit"
        " FROM prices_own WHERE item_id = ?"
        " ORDER BY date DESC, id DESC LIMIT 1",
        (item_id,),
    ).fetchone()
    if row is None:
        return None
    return PricePer(
        row["price"],
        "own",
        row["currency"],
        row["package_quantity"],
        row["package_unit"],
    )


def _estimate(conn: sqlite3.Connection, item_id: int) -> PricePer | None:
    # 1. Item-specific estimate
    row = conn.execute(
        "SELECT price, currency, package_quantity, package_unit"
        " FROM price_estimates WHERE item_id = ?"
        " ORDER BY id DESC LIMIT 1",
        (item_id,),
    ).fetchone()
    # 2. Item's category estimate
    if row is None:
        item_row = conn.execute(
            "SELECT category FROM items WHERE id = ?", (item_id,)
        ).fetchone()
        item_cat = item_row["category"] if item_row is not None else None
        if item_cat is not None:
            row = conn.execute(
                "SELECT price, currency, package_quantity, package_unit"
                " FROM price_estimates WHERE item_id IS NULL AND category = ?"
                " ORDER BY id DESC LIMIT 1",
                (item_cat,),
            ).fetchone()
    # 3. Global fallback estimate
    if row is None:
        row = conn.execute(
            "SELECT price, currency, package_quantity, package_unit"
            " FROM price_estimates WHERE item_id IS NULL"
            " AND category IS NULL"
            " ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return PricePer(
        row["price"],
        "estimate",
        row["currency"],
        row["package_quantity"],
        row["package_unit"],
    )


def price_item(
    conn: sqlite3.Connection,
    item_id: int,
    lookup=_DEFAULT_LOOKUP,
) -> PricePer | None:
    """Resolve a price for an item.

    Resolution order: most recent ``prices_own`` row -> ``lookup(item_name)``
    (defaults to ``make_lookup()`` against Open Prices; pass ``lookup=None``
    to skip network lookup) -> ``price_estimates`` (item -> category -> global)
    -> None.
    Returns ``(price, source, currency)`` (as ``PricePer``) with source in
    {"own", "openprices", "estimate"}.
    """
    own = _own_price(conn, item_id)
    if own is not None:
        return own

    if lookup is _DEFAULT_LOOKUP:
        lookup = make_lookup()

    if lookup is not None:
        row = conn.execute(
            "SELECT name FROM items WHERE id = ?", (item_id,)
        ).fetchone()
        if row is not None:
            try:
                value = lookup(row["name"])
            except Exception:
                value = None
            if value is not None:
                return PricePer(float(value), "openprices", None)

    return _estimate(conn, item_id)


def convert(
    conn: sqlite3.Connection,
    item_id: int,
    quantity: float,
    unit: str,
    price_per: tuple,
    currency: str,
) -> float:
    """Line price for ``quantity`` of ``unit`` given a resolved ``price_per``.

    Accounts for bulk package sizes and compatible culinary unit conversions
    (e.g. 1 cup of milk from a 1 gal package @ $4.00 costs $0.25).
    """
    price = float(price_per[0])
    pkg_qty = getattr(price_per, "pkg_qty", 1.0) or 1.0
    pkg_unit = getattr(price_per, "pkg_unit", "") or ""

    if pkg_unit:
        converted = convert_quantity(quantity, unit, pkg_unit)
        if converted is not None:
            return round(price * (converted / pkg_qty), 6)

    return round(price * (quantity / pkg_qty), 6)
