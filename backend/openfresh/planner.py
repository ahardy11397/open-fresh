"""Weekly planner: plan entries and the cooked check-off.

Global constraints: the cooked check-off consumes ingredients scaled the SAME
way listgen scales them — (servings_override or household_size) divided by the
recipe's servings — via the single shared helper ``_scaled_ingredients``;
removing an entry never touches inventory; staples are never consumed;
consumption floors at 0 (inventory.consume handles that); unquantified
ingredients (quantity None) skip consumption without error.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from openfresh import inventory, recipes, settings


def _scaled_ingredients(
    conn: sqlite3.Connection, entry: sqlite3.Row | dict
) -> list[tuple[int | None, str, float | None, str, bool]]:
    """Scale an entry's recipe ingredients the way listgen does.

    Returns ``(item_id, raw, quantity, unit, staple)`` tuples where quantity
    is multiplied by ``(entry.servings_override or household_size) / recipe
    servings``. Unquantified ingredients keep ``quantity = None``. Staples are
    included (callers filter); a missing recipe yields an empty list. This is
    the ONE shared scaling code path for listgen and mark_cooked.
    """
    recipe = recipes.get_recipe(conn, entry["recipe_id"])
    if recipe is None:
        return []
    servings = entry["servings_override"] or settings.get_household_size(conn)
    scale = servings / recipe["servings"]
    return [
        (
            ing["item_id"],
            ing["raw"],
            None if ing["quantity"] is None else ing["quantity"] * scale,
            ing["unit"],
            bool(ing["staple"]),
        )
        for ing in recipe["ingredients"]
    ]


def add_entry(
    conn: sqlite3.Connection,
    recipe_id: int,
    date: str,
    slot: str | None = None,
    servings_override: int | None = None,
) -> int:
    """Plan a recipe on an ISO date; return the entry id."""
    cur = conn.execute(
        """INSERT INTO plan_entries (recipe_id, date, slot, servings_override)
           VALUES (?, ?, ?, ?)""",
        (recipe_id, date, slot, servings_override),
    )
    conn.commit()
    entry_id = cur.lastrowid
    assert entry_id is not None
    return entry_id


def remove_entry(conn: sqlite3.Connection, entry_id: int) -> None:
    """Delete a plan entry. Never touches inventory."""
    conn.execute("DELETE FROM plan_entries WHERE id = ?", (entry_id,))
    conn.commit()


def mark_cooked(conn: sqlite3.Connection, entry_id: int) -> None:
    """Check off an entry as cooked and consume its non-staple ingredients.

    Consumption uses the shared scaling helper (same scaling as the grocery
    list), floors at 0, skips staples and unquantified ingredients, and is
    idempotent: an already-cooked entry consumes nothing again.
    """
    entry = conn.execute(
        """SELECT id, recipe_id, servings_override, cooked
           FROM plan_entries WHERE id = ?""",
        (entry_id,),
    ).fetchone()
    if entry is None or entry["cooked"]:
        return
    conn.execute(
        "UPDATE plan_entries SET cooked = 1 WHERE id = ?", (entry_id,)
    )
    conn.commit()
    for item_id, _raw, quantity, _unit, staple in _scaled_ingredients(conn, entry):
        if staple or quantity is None or item_id is None:
            continue
        inventory.consume(conn, item_id, quantity, source="cooking")


def get_week(conn: sqlite3.Connection, week_start: str) -> list[dict]:
    """Entries (with recipe titles) dated in [week_start, week_start + 7 days).

    Includes both planned and cooked entries, ordered by date.
    """
    start = date.fromisoformat(week_start)
    end = start + timedelta(days=7)
    return [
        dict(row)
        for row in conn.execute(
            """SELECT plan_entries.id, recipe_id, date, slot,
                      servings_override, cooked, recipes.title
               FROM plan_entries JOIN recipes ON recipes.id = recipe_id
               WHERE date >= ? AND date < ?
               ORDER BY date, plan_entries.id""",
            (start.isoformat(), end.isoformat()),
        )
    ]


def list_entries(
    conn: sqlite3.Connection, cooked: bool | None = None
) -> list[dict]:
    """All plan entries (with recipe titles) ordered by date.

    ``cooked`` filters: True for cooked-only, False for uncooked-only,
    None for everything.
    """
    query = """SELECT plan_entries.id, recipe_id, date, slot,
                      servings_override, cooked, recipes.title
               FROM plan_entries JOIN recipes ON recipes.id = recipe_id"""
    params: tuple = ()
    if cooked is not None:
        query += " WHERE cooked = ?"
        params = (int(cooked),)
    query += " ORDER BY date, plan_entries.id"
    return [dict(row) for row in conn.execute(query, params)]
