"""Canonical items and alias normalization.

Global constraints: canonical item names are stored lowercase-stripped; free
text normalizes through the alias table so cross-recipe merging works.
"""

from __future__ import annotations

import sqlite3


def _normalize(raw: str) -> str:
    """Strip, lowercase, and collapse internal whitespace."""
    return " ".join(raw.split()).lower()


def get_or_create(
    conn: sqlite3.Connection, name: str, category: str | None = None
) -> int:
    """Return the item id for a canonical name, creating it if needed."""
    canonical = _normalize(name)
    norm_cat = _normalize(category) if category is not None else None
    row = conn.execute(
        "SELECT id, category FROM items WHERE name = ?", (canonical,)
    ).fetchone()
    if row is not None:
        if norm_cat is not None and row["category"] != norm_cat:
            conn.execute(
                "UPDATE items SET category = ? WHERE id = ?",
                (norm_cat, row["id"]),
            )
            conn.commit()
        return row["id"]
    cur = conn.execute(
        "INSERT INTO items (name, category) VALUES (?, ?)",
        (canonical, norm_cat),
    )
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def set_category(
    conn: sqlite3.Connection, item_id: int, category: str | None
) -> None:
    """Update the category of an existing item."""
    norm_cat = _normalize(category) if category is not None else None
    cur = conn.execute(
        "UPDATE items SET category = ? WHERE id = ?", (norm_cat, item_id)
    )
    if cur.rowcount == 0:
        raise ValueError(f"no item with id {item_id}")
    conn.commit()


def get_or_create_with_alias(conn: sqlite3.Connection, raw: str) -> int:
    """Resolve free text to a canonical item id, registering an alias on create.

    Aliases take precedence over exact item-name matches so a manual
    rename_alias link keeps redirecting even if an item of the same name
    still exists.
    """
    normalized = _normalize(raw)
    row = conn.execute(
        "SELECT item_id FROM item_aliases WHERE alias = ?", (normalized,)
    ).fetchone()
    if row is not None:
        return row["item_id"]

    row = conn.execute("SELECT id FROM items WHERE name = ?", (normalized,)).fetchone()
    if row is not None:
        return row["id"]

    cur = conn.execute("INSERT INTO items (name) VALUES (?)", (normalized,))
    item_id = cur.lastrowid
    assert item_id is not None
    conn.execute(
        "INSERT INTO item_aliases (alias, item_id) VALUES (?, ?)", (normalized, item_id)
    )
    conn.commit()
    return item_id


def rename_alias(conn: sqlite3.Connection, raw: str, item_id: int) -> None:
    """Point the alias for raw at item_id (creating or moving it)."""
    alias = _normalize(raw)
    conn.execute(
        """INSERT INTO item_aliases (alias, item_id) VALUES (?, ?)
           ON CONFLICT(alias) DO UPDATE SET item_id = excluded.item_id""",
        (alias, item_id),
    )
    conn.commit()


def list_items(conn: sqlite3.Connection) -> list[dict]:
    """Return all canonical items as dicts, ordered by name."""
    return [
        dict(row)
        for row in conn.execute(
            "SELECT id, name, category, created_at FROM items ORDER BY name"
        )
    ]
