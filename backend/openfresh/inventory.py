"""Inventory store with source-tagged event log.

Global constraints: inventory quantities never fall below 0 (clamped, with the
true applied delta logged); every change records a source-tagged event;
inventory rows are UNIQUE(item_id, location).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

_CONSUME_ORDER = ("fridge", "freezer", "pantry")


def _log_event(
    conn: sqlite3.Connection,
    item_id: int,
    location: str | None,
    delta: float,
    source: str,
    note: str | None,
) -> None:
    conn.execute(
        """INSERT INTO inventory_events (item_id, location, delta, source, note)
           VALUES (?, ?, ?, ?, ?)""",
        (item_id, location, delta, source, note),
    )


def add_item(
    conn: sqlite3.Connection,
    item_id: int,
    location: str,
    quantity: float,
    unit: str = "",
    source: str = "manual",
    note: str | None = None,
) -> int:
    """Upsert an inventory row, adding to any existing quantity; log the delta."""
    row = conn.execute(
        "SELECT id, quantity FROM inventory WHERE item_id = ? AND location = ?",
        (item_id, location),
    ).fetchone()
    if row is not None:
        inv_id = row["id"]
        conn.execute(
            "UPDATE inventory SET quantity = ?, unit = ?, updated_at = ? WHERE id = ?",
            (row["quantity"] + quantity, unit, _now(), inv_id),
        )
    else:
        cur = conn.execute(
            """INSERT INTO inventory (item_id, location, quantity, unit, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (item_id, location, quantity, unit, _now()),
        )
        inv_id = cur.lastrowid
    assert inv_id is not None
    _log_event(conn, item_id, location, quantity, source, note)
    conn.commit()
    return inv_id


def remove_item(
    conn: sqlite3.Connection, inventory_id: int, note: str | None = None
) -> None:
    """Delete an inventory row and log the event with delta = -stored quantity."""
    row = conn.execute(
        "SELECT item_id, location, quantity FROM inventory WHERE id = ?",
        (inventory_id,),
    ).fetchone()
    if row is None:
        return
    conn.execute("DELETE FROM inventory WHERE id = ?", (inventory_id,))
    _log_event(conn, row["item_id"], row["location"], -row["quantity"], "manual", note)
    conn.commit()


def adjust(
    conn: sqlite3.Connection, inventory_id: int, delta: float, note: str | None = None
) -> float:
    """Apply delta floored at 0, log the true applied delta, return new quantity."""
    row = conn.execute(
        "SELECT item_id, location, quantity FROM inventory WHERE id = ?",
        (inventory_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"no inventory row with id {inventory_id}")
    new_quantity = max(0.0, row["quantity"] + delta)
    applied = new_quantity - row["quantity"]
    conn.execute(
        "UPDATE inventory SET quantity = ?, updated_at = ? WHERE id = ?",
        (new_quantity, _now(), inventory_id),
    )
    _log_event(conn, row["item_id"], row["location"], applied, "manual", note)
    conn.commit()
    return new_quantity


def consume(
    conn: sqlite3.Connection,
    item_id: int,
    quantity: float,
    source: str = "cooking",
    note: str | None = None,
) -> None:
    """Decrement across the item's locations (fridge, freezer, pantry), floored at 0."""
    remaining = quantity
    for location in _CONSUME_ORDER:
        if remaining <= 0:
            break
        row = conn.execute(
            "SELECT id, quantity FROM inventory WHERE item_id = ? AND location = ?",
            (item_id, location),
        ).fetchone()
        if row is None or row["quantity"] <= 0:
            continue
        new_quantity = max(0.0, row["quantity"] - remaining)
        applied = new_quantity - row["quantity"]
        conn.execute(
            "UPDATE inventory SET quantity = ?, updated_at = ? WHERE id = ?",
            (new_quantity, _now(), row["id"]),
        )
        _log_event(conn, item_id, location, applied, source, note)
        remaining += applied
    conn.commit()


def get_all(conn: sqlite3.Connection) -> list[dict]:
    """Return all inventory rows joined with item name, by item name then location."""
    return [
        dict(row)
        for row in conn.execute(
            """SELECT inventory.id, inventory.item_id, items.name AS item_name,
                      inventory.location, inventory.quantity, inventory.unit,
                      inventory.updated_at
               FROM inventory JOIN items ON items.id = inventory.item_id
               ORDER BY items.name, inventory.location"""
        )
    ]


def get_quantity(conn: sqlite3.Connection, item_id: int) -> float:
    """Total on hand for an item across all locations/units."""
    row = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) AS total FROM inventory WHERE item_id = ?",
        (item_id,),
    ).fetchone()
    return float(row["total"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
