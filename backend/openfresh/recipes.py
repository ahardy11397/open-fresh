"""Cookbook: recipes and their ingredients.

Global constraints: recipes carry servings (default 2), source_url, and a
needs_review flag; ingredients normalize through the canonical item table.
"""

from __future__ import annotations

import sqlite3

from openfresh import items


def create_recipe(
    conn: sqlite3.Connection,
    title: str,
    servings: int = 2,
    source_url: str | None = None,
) -> int:
    """Insert a recipe and return its id. Title whitespace is collapsed."""
    cur = conn.execute(
        "INSERT INTO recipes (title, servings, source_url) VALUES (?, ?, ?)",
        (" ".join(title.split()), servings, source_url),
    )
    conn.commit()
    recipe_id = cur.lastrowid
    assert recipe_id is not None
    return recipe_id


def add_ingredient(
    conn: sqlite3.Connection,
    recipe_id: int,
    raw: str,
    quantity: float | None,
    unit: str = "",
    staple: bool = False,
) -> int:
    """Add an ingredient to a recipe, normalizing raw through the item table.

    Returns the recipe_ingredient row id. The raw text is stored with
    collapsed whitespace; item-level normalization happens in items.
    """
    item_id = items.get_or_create_with_alias(conn, raw)
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


def get_recipe(conn: sqlite3.Connection, recipe_id: int) -> dict | None:
    """Return the recipe as a dict with nested ingredients, or None.

    Each ingredient carries the canonical item id (item_id) and name
    (item_name) alongside the original raw text.
    """
    row = conn.execute(
        "SELECT id, title, servings, source_url, needs_review, created_at"
        " FROM recipes WHERE id = ?",
        (recipe_id,),
    ).fetchone()
    if row is None:
        return None
    recipe = dict(row)
    recipe["needs_review"] = bool(recipe["needs_review"])
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


def list_recipes(conn: sqlite3.Connection) -> list[dict]:
    """Return all recipes (without ingredients), ordered by title."""
    return [
        dict(row)
        for row in conn.execute(
            "SELECT id, title, servings, source_url, needs_review, created_at"
            " FROM recipes ORDER BY title"
        )
    ]


def delete_recipe(conn: sqlite3.Connection, recipe_id: int) -> None:
    """Delete a recipe; its ingredients cascade via the schema."""
    conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    conn.commit()
