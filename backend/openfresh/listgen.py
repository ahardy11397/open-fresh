"""Grocery list generation: week plan entries -> merged, priced lines.

Global constraints: merge/sum only identical (item_id, unit) pairs; mixed
units stay separate lines; inventory subtraction matches on item_id only
and is floored at 0; staples never appear; zero-need lines are dropped;
odd ingredients (quantity None) survive as lines with quantity None.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from openfresh import inventory, pricing, recipes, settings


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
    household = settings.get_household_size(conn)

    # (item_id, unit) -> {"name": str, "quantity": float|None}
    # quantity is None when any contributing ingredient was unquantified.
    need: dict[tuple[int, str], dict] = {}
    for entry in _week_entries(conn, week_start):
        recipe = recipes.get_recipe(conn, entry["recipe_id"])
        if recipe is None:
            continue
        servings = entry["servings_override"] or household
        scale = servings / recipe["servings"]
        for ing in recipe["ingredients"]:
            if ing["staple"]:
                continue
            key = (ing["item_id"], ing["unit"])
            line = need.setdefault(
                key, {"name": ing["item_name"], "quantity": 0.0}
            )
            if ing["quantity"] is None:
                line["quantity"] = None
            elif line["quantity"] is not None:
                line["quantity"] += ing["quantity"] * scale

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
