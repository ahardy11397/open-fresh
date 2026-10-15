"""Key/value settings stored in the settings table."""

from __future__ import annotations

import sqlite3

HOUSEHOLD_SIZE_KEY = "household_size"
HOUSEHOLD_SIZE_DEFAULT = 2


def get_setting(conn: sqlite3.Connection, key: str, default=None) -> str | None:
    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?", (key,)
    ).fetchone()
    if row is None:
        return default
    return row["value"]


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """INSERT INTO settings (key, value) VALUES (?, ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
        (key, value),
    )
    conn.commit()


def get_household_size(conn: sqlite3.Connection) -> int:
    """Household size, falling back to the default on absent/unparseable/invalid values."""
    return get_positive_int(conn, HOUSEHOLD_SIZE_KEY, HOUSEHOLD_SIZE_DEFAULT)


def get_positive_int(conn: sqlite3.Connection, key: str, default: int) -> int:
    """Int-parsing getter: falls back to default on absent/unparseable/<1 values."""
    value = get_setting(conn, key)
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 1 else default
