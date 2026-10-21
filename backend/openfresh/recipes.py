"""Cookbook: recipes and their ingredients.

Global constraints: recipes carry servings (default 2), source_url, and a
needs_review flag; ingredients normalize through the canonical item table.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from openfresh import items

_UNSET = object()


def create_recipe(
    conn: sqlite3.Connection,
    title: str,
    servings: int = 2,
    source_url: str | None = None,
    *,
    steps: list[str] | None = None,
    total_time: str | None = None,
    needs_review: bool = False,
    review_notes: str | None = None,
) -> int:
    """Insert a recipe and return its id. Title whitespace is collapsed."""
    steps_json = json.dumps(steps or [])
    cur = conn.execute(
        """INSERT INTO recipes
             (title, servings, source_url, steps, total_time, needs_review, review_notes, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (
            " ".join(title.split()),
            servings,
            source_url,
            steps_json,
            total_time,
            int(needs_review),
            review_notes,
        ),
    )
    conn.commit()
    recipe_id = cur.lastrowid
    assert recipe_id is not None
    return recipe_id


def add_ingredient(
    conn: sqlite3.Connection,
    recipe_id: int,
    raw: str,
    quantity: float | None = None,
    unit: str = "",
    staple: bool = False,
    *,
    item_name: str | None = None,
) -> int:
    """Add an ingredient to a recipe, normalizing raw through the item table.

    Returns the recipe_ingredient row id. The raw text is stored with
    collapsed whitespace; item-level normalization happens in items.
    """
    item_id = items.get_or_create_with_alias(conn, item_name or raw)
    clean_raw = " ".join(raw.split())
    cur = conn.execute(
        """INSERT INTO recipe_ingredients
             (recipe_id, item_id, raw, quantity, unit, staple)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (recipe_id, item_id, clean_raw, quantity, unit, int(staple)),
    )
    conn.commit()
    ing_id = cur.lastrowid
    assert ing_id is not None
    return ing_id


def _hydrate_recipe(row: sqlite3.Row | dict) -> dict:
    """Hydrate a SQLite row or dict into a full recipe dict with parsed steps."""
    recipe = dict(row)
    recipe["needs_review"] = bool(recipe["needs_review"])
    raw_steps = recipe.get("steps")
    if raw_steps:
        try:
            parsed = json.loads(raw_steps)
            recipe["steps"] = parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            recipe["steps"] = []
    else:
        recipe["steps"] = []
    return recipe


def get_recipe(conn: sqlite3.Connection, recipe_id: int) -> dict | None:
    """Return the recipe as a dict with nested ingredients, or None.

    Each ingredient carries the canonical item id (item_id) and name
    (item_name) alongside the original raw text.
    """
    row = conn.execute(
        "SELECT id, title, servings, source_url, steps, total_time,"
        " needs_review, review_notes, created_at"
        " FROM recipes WHERE id = ?",
        (recipe_id,),
    ).fetchone()
    if row is None:
        return None
    recipe = _hydrate_recipe(row)
    recipe["ingredients"] = [
        {
            "id": ing["id"],
            "item_id": ing["item_id"],
            "item_name": ing["item_name"],
            "raw": ing["raw"],
            "quantity": ing["quantity"],
            "unit": ing["unit"],
            "staple": bool(ing["staple"]),
        }
        for ing in conn.execute(
            """SELECT ri.id, ri.item_id, it.name AS item_name, ri.raw,
                      ri.quantity, ri.unit, ri.staple
               FROM recipe_ingredients ri
               LEFT JOIN items it ON it.id = ri.item_id
               WHERE ri.recipe_id = ?
               ORDER BY ri.id""",
            (recipe_id,),
        )
    ]
    return recipe


def list_recipes(
    conn: sqlite3.Connection, needs_review: bool | None = None
) -> list[dict]:
    """Return all recipes (without ingredients), ordered by title."""
    if needs_review is not None:
        rows = conn.execute(
            "SELECT id, title, servings, source_url, steps, total_time,"
            " needs_review, review_notes, created_at"
            " FROM recipes WHERE needs_review = ? ORDER BY title",
            (int(needs_review),),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, title, servings, source_url, steps, total_time,"
            " needs_review, review_notes, created_at"
            " FROM recipes ORDER BY title"
        ).fetchall()

    return [_hydrate_recipe(row) for row in rows]


def update_recipe(
    conn: sqlite3.Connection,
    recipe_id: int,
    *,
    title: str | None = None,
    servings: int | None = None,
    source_url: Any = _UNSET,
    steps: list[str] | None = None,
    total_time: Any = _UNSET,
    needs_review: bool | None = None,
    review_notes: Any = _UNSET,
    ingredients: list[dict] | None = None,
) -> dict | None:
    """Update specified recipe fields in place and return get_recipe(conn, recipe_id)."""
    exists = conn.execute(
        "SELECT 1 FROM recipes WHERE id = ?", (recipe_id,)
    ).fetchone()
    if exists is None:
        return None

    updates: list[str] = []
    params: list[Any] = []

    if title is not None:
        updates.append("title = ?")
        params.append(" ".join(title.split()))
    if servings is not None:
        updates.append("servings = ?")
        params.append(servings)
    if source_url is not _UNSET:
        updates.append("source_url = ?")
        params.append(source_url)
    if steps is not None:
        updates.append("steps = ?")
        params.append(json.dumps(steps))
    if total_time is not _UNSET:
        updates.append("total_time = ?")
        params.append(total_time)
    if needs_review is not None:
        updates.append("needs_review = ?")
        params.append(int(needs_review))
    if review_notes is not _UNSET:
        updates.append("review_notes = ?")
        params.append(review_notes)

    if updates:
        params.append(recipe_id)
        conn.execute(
            f"UPDATE recipes SET {', '.join(updates)} WHERE id = ?",
            params,
        )

    if ingredients is not None:
        conn.execute(
            "DELETE FROM recipe_ingredients WHERE recipe_id = ?",
            (recipe_id,),
        )
        for ing in ingredients:
            raw = ing.get("raw") or ing.get("name") or ing.get("item_name") or ""
            item_name = ing.get("item_name") or ing.get("name")
            quantity = ing.get("quantity")
            unit = ing.get("unit", "")
            staple = bool(ing.get("staple", False))
            add_ingredient(
                conn,
                recipe_id,
                raw=raw,
                quantity=quantity,
                unit=unit,
                staple=staple,
                item_name=item_name,
            )

    conn.commit()
    return get_recipe(conn, recipe_id)


def delete_recipe(conn: sqlite3.Connection, recipe_id: int) -> None:
    """Delete a recipe; its ingredients cascade via the schema."""
    conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    conn.commit()
