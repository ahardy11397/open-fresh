"""Grocery list generation: week plan entries -> merged, priced lines.

Global constraints: merge/sum only identical (item_id, unit) pairs; mixed
units stay separate lines; inventory subtraction matches on item_id only
and is floored at 0; staples never appear; zero-need lines are dropped;
odd ingredients (quantity None) survive as lines with quantity None.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from openfresh import inventory, planner, pricing


def _week_entries(conn: sqlite3.Connection, week_start: str) -> list:
    """Uncooked plan entries dated in [week_start, week_start + 7 days)."""
    start = date.fromisoformat(week_start)
    end = start + timedelta(days=7)
    return conn.execute(
        """SELECT recipe_id, servings_override
           FROM plan_entries
           WHERE date >= ? AND date < ? AND cooked = 0""",
        (start.isoformat(), end.isoformat()),
    ).fetchall()


def generate_list(
    conn: sqlite3.Connection,
    week_start: str,
    lookup=None,
) -> list[dict]:
    """Build the grocery list for the week starting at week_start (ISO date).

    Collects ingredients of all uncooked plan entries in
    ``[week_start, week_start + 7 days)``, scales each by
    ``entry.servings_override or settings.get_household_size(conn)`` divided
    by the recipe's servings, groups by (item_id, unit) summing quantities,
    subtracts inventory (floored at 0), drops staples and zero-need lines,
    and prices each line through the pricing layer.
    """
    names: dict[int | None, str | None] = {}

    def item_name(item_id: int | None) -> str | None:
        if item_id not in names:
            row = conn.execute(
                "SELECT name FROM items WHERE id = ?", (item_id,)
            ).fetchone()
            names[item_id] = row["name"] if row is not None else None
        return names[item_id]

    # (item_id, unit) -> {"name": str, "quantity": float|None}
    # quantity is None when any contributing ingredient was unquantified.
    need: dict[tuple, dict] = {}
    for entry in _week_entries(conn, week_start):
        # One shared scaling code path with the cooked check-off.
        for item_id, _raw, quantity, unit, staple in (
            planner._scaled_ingredients(conn, entry)
        ):
            if staple:
                continue
            key = (item_id, unit)
            line = need.setdefault(
                key, {"name": item_name(item_id), "quantity": 0.0}
            )
            if quantity is None:
                line["quantity"] = None
            elif line["quantity"] is not None:
                line["quantity"] += quantity

    lines: list[dict] = []
    for (item_id, unit), line in sorted(
        need.items(), key=lambda kv: (kv[1]["name"] or "", kv[0][1])
    ):
        quantity = line["quantity"]
        if quantity is not None:
            quantity = round(max(0.0, quantity - inventory.get_quantity(conn, item_id)), 6)
            if quantity == 0:
                continue

        price_per = pricing.price_item(conn, item_id, lookup=lookup)
        if price_per is None or quantity is None:
            price = None
            price_source = None
        else:
            price = pricing.convert(conn, item_id, quantity, unit, price_per, "")
            price_source = price_per[1]

        lines.append(
            {
                "item_id": item_id,
                "name": line["name"],
                "quantity": quantity,
                "unit": unit,
                "price": price,
                "price_source": price_source,
            }
        )
    return lines
