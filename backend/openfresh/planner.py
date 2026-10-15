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

from openfresh import inventory, pricing, recipes, settings

MEALS_PER_WEEK_KEY = "meals_per_week"
MEALS_PER_WEEK_DEFAULT = 5
PREFERRED_DAYS_KEY = "preferred_days"
PREFERRED_DAYS_DEFAULT = "mon,tue,wed,thu,fri,sat,sun"

# Day abbreviations (as stored in the preferred_days setting) to weekday().
_DAY_INDEX = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


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
    if recipe["servings"] < 1:
        # Never divide by a non-positive servings value (stored garbage).
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


def _recipe_estimate(
    conn: sqlite3.Connection, recipe_id: int
) -> float:
    """Estimated cost of cooking a recipe for the household size.

    Scales the same way listgen does (household_size / recipe servings) and
    prices each quantified ingredient via ``pricing.price_item``. Unpriced or
    unquantified ingredients contribute 0. Missing recipe yields 0.0.
    """
    recipe = recipes.get_recipe(conn, recipe_id)
    if recipe is None or recipe["servings"] < 1:
        return 0.0
    scale = settings.get_household_size(conn) / recipe["servings"]
    total = 0.0
    for ing in recipe["ingredients"]:
        if ing["quantity"] is None or ing["item_id"] is None:
            continue
        priced = pricing.price_item(conn, ing["item_id"])
        if priced is None:
            continue
        total += priced[0] * ing["quantity"] * scale
    return total


def _round_robin_pick(
    conn: sqlite3.Connection,
    all_recipes: list[dict],
    budget_target: float | None,
    week_cost: float,
) -> dict | None:
    """Pick the least-recently-planned recipe that fits the budget.

    Never-planned recipes come first (by id), then recipes ordered by their
    most recent plan date (oldest first) — cycling round-robin. With a budget
    in force, the first candidate whose estimated cost would NOT push the week
    over budget wins; if every candidate would, return None.
    """
    def key(recipe: dict):
        row = conn.execute(
            "SELECT MAX(date) AS last FROM plan_entries WHERE recipe_id = ?",
            (recipe["id"],),
        ).fetchone()
        last = row["last"]
        return (0, "", recipe["id"]) if last is None else (1, last, recipe["id"])

    for recipe in sorted(all_recipes, key=key):
        if budget_target is None:
            return recipe
        if week_cost + _recipe_estimate(conn, recipe["id"]) <= budget_target:
            return recipe
    return None


def auto_populate(
    conn: sqlite3.Connection,
    week_start: str,
    chooser=None,
) -> list[int]:
    """Deterministically fill the week up to ``meals_per_week`` entries.

    Fills uncooked entries up to the ``meals_per_week`` setting (default 5) on
    the household's ``preferred_days`` (default "mon,tue,wed,thu,fri,sat,sun",
    filled in listed order), skipping dates that already hold an entry.
    Recipes cycle round-robin by least-recently-planned. Budget pressure defers
    an expensive recipe ONLY when a ``budgets`` row exists for this week_start
    and its target is > 0; estimates are allowed otherwise.

    ``chooser(conn, candidates, context) -> dict | None`` is consulted first
    per slot; its pick is used as-is, and None falls back to round-robin.

    Returns the ids of the created entries.
    """
    start = date.fromisoformat(week_start)
    end = start + timedelta(days=7)

    meals_per_week = settings.get_positive_int(
        conn, MEALS_PER_WEEK_KEY, MEALS_PER_WEEK_DEFAULT
    )
    raw_days = settings.get_setting(
        conn, PREFERRED_DAYS_KEY, PREFERRED_DAYS_DEFAULT
    )
    preferred = [
        day.strip().lower()
        for day in (raw_days or "").split(",")
        if day.strip()
    ]

    existing = [
        dict(row)
        for row in conn.execute(
            """SELECT id, recipe_id, date, cooked
               FROM plan_entries WHERE date >= ? AND date < ?""",
            (start.isoformat(), end.isoformat()),
        )
    ]
    taken_dates = {entry["date"] for entry in existing}
    slots = max(0, meals_per_week - sum(1 for e in existing if not e["cooked"]))

    budget_row = conn.execute(
        "SELECT target FROM budgets WHERE week_start = ?", (week_start,)
    ).fetchone()
    budget_target = (
        float(budget_row["target"])
        if budget_row is not None and float(budget_row["target"]) > 0
        else None
    )
    week_cost = sum(
        _recipe_estimate(conn, entry["recipe_id"]) for entry in existing
    )

    all_recipes = recipes.list_recipes(conn)
    created: list[int] = []
    for day in preferred:
        if slots <= 0:
            break
        offset = _DAY_INDEX.get(day)
        if offset is None:
            continue
        iso = (start + timedelta(days=offset)).isoformat()
        if iso in taken_dates:
            continue

        pick = None
        if chooser is not None:
            pick = chooser(
                conn, all_recipes, {"week_start": week_start, "date": iso}
            )
        if pick is None:
            pick = _round_robin_pick(conn, all_recipes, budget_target, week_cost)
            if pick is None:  # everything would push the week over budget
                break
        recipe_id = pick["id"]

        created.append(add_entry(conn, recipe_id, iso))
        taken_dates.add(iso)
        slots -= 1
        if budget_target is not None:
            week_cost += _recipe_estimate(conn, recipe_id)
    return created
