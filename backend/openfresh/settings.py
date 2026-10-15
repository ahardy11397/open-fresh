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
    value = get_setting(conn, HOUSEHOLD_SIZE_KEY)
    if value is None:
        return HOUSEHOLD_SIZE_DEFAULT
    return int(value)
