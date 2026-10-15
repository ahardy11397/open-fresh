"""Layered pricing: own library > Open Prices lookup > category estimates.

Every priced line carries a source label: "own", "openprices", or "estimate".
Money values are (amount: float, currency: str).
"""

from __future__ import annotations

import sqlite3

# Re-export: make_lookup is consumed through the injectable-lookup seam.
from openfresh.openprices import make_lookup  # noqa: F401


def record_own_price(
    conn: sqlite3.Connection,
    item_id: int,
    price: float,
    currency: str,
    date: str,
    source: str = "manual",
) -> None:
    """Record a first-hand price observation for an item."""
    conn.execute(
        "INSERT INTO prices_own (item_id, price, currency, date, source)"
        " VALUES (?, ?, ?, ?, ?)",
        (item_id, price, currency, date, source),
    )
    conn.commit()


def set_estimate(
    conn: sqlite3.Connection,
    item_id: int | None,
    category: str | None,
    price: float,
    currency: str,
) -> None:
    """Record a category (or item-specific) price estimate."""
    conn.execute(
        "INSERT INTO price_estimates (item_id, category, price, currency)"
        " VALUES (?, ?, ?, ?)",
        (item_id, category, price, currency),
    )
    conn.commit()


def _own_price(conn: sqlite3.Connection, item_id: int) -> tuple[float, str] | None:
    row = conn.execute(
        "SELECT price FROM prices_own WHERE item_id = ?"
        " ORDER BY date DESC, id DESC LIMIT 1",
        (item_id,),
    ).fetchone()
    if row is None:
        return None
    return (row["price"], "own")


def _estimate(conn: sqlite3.Connection, item_id: int) -> tuple[float, str] | None:
    row = conn.execute(
        "SELECT price FROM price_estimates WHERE item_id = ?"
        " ORDER BY id DESC LIMIT 1",
        (item_id,),
    ).fetchone()
    if row is None:
        row = conn.execute(
            "SELECT price FROM price_estimates WHERE item_id IS NULL"
            " ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return (row["price"], "estimate")


def price_item(
    conn: sqlite3.Connection,
    item_id: int,
    lookup=None,
) -> tuple[float, str] | None:
    """Resolve a price for an item.

    Resolution order: most recent ``prices_own`` row -> ``lookup(item_name)``
    (optional callable, skipped when None) -> ``price_estimates`` -> None.
    Returns ``(price, source)`` with source in {"own", "openprices",
    "estimate"}. The lookup itself never raises: any error is treated as a
    miss so the next layer applies.
    """
    own = _own_price(conn, item_id)
    if own is not None:
        return own

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
                return (float(value), "openprices")

    return _estimate(conn, item_id)


def convert(
    conn: sqlite3.Connection,
    item_id: int,
    quantity: float,
    unit: str,
    price_per: tuple[float, str],
    currency: str,
) -> float:
    """Line price for a quantity of an item at a per-unit price.

    Coarse model: the price is per priced unit, so the line price is simply
    ``price * quantity`` (quantity treated as a count of the priced unit).
    """
    return price_per[0] * quantity
