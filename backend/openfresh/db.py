"""SQLite connection handling and schema for openfresh.

Global constraints: single SQLite file, WAL mode, foreign keys ON.
"""

from __future__ import annotations

import sqlite3

_SCHEMA_STATEMENTS: list[str] = [
    """CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS item_aliases (
        alias TEXT PRIMARY KEY,
        item_id INTEGER NOT NULL REFERENCES items(id)
    )""",
    """CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY,
        item_id INTEGER NOT NULL REFERENCES items(id),
        location TEXT NOT NULL CHECK(location IN ('pantry','fridge','freezer')),
        quantity REAL NOT NULL,
        unit TEXT NOT NULL DEFAULT '',
        updated_at TEXT,
        UNIQUE(item_id, location)
    )""",
    """CREATE TABLE IF NOT EXISTS inventory_events (
        id INTEGER PRIMARY KEY,
        item_id INTEGER NOT NULL,
        location TEXT,
        delta REAL NOT NULL,
        source TEXT NOT NULL,
        note TEXT,
        created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS recipes (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        servings INTEGER NOT NULL DEFAULT 2,
        source_url TEXT,
        needs_review INTEGER NOT NULL DEFAULT 0,
        created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS recipe_ingredients (
        id INTEGER PRIMARY KEY,
        recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
        item_id INTEGER REFERENCES items(id),
        raw TEXT NOT NULL,
        quantity REAL,
        unit TEXT DEFAULT '',
        staple INTEGER NOT NULL DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS plan_entries (
        id INTEGER PRIMARY KEY,
        recipe_id INTEGER NOT NULL REFERENCES recipes(id),
        date TEXT NOT NULL,
        slot TEXT,
        servings_override INTEGER,
        cooked INTEGER NOT NULL DEFAULT 0,
        created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS prices_own (
        id INTEGER PRIMARY KEY,
        item_id INTEGER NOT NULL REFERENCES items(id),
        price REAL NOT NULL,
        currency TEXT NOT NULL,
        date TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'manual'
    )""",
    """CREATE TABLE IF NOT EXISTS price_estimates (
        id INTEGER PRIMARY KEY,
        item_id INTEGER,
        category TEXT,
        price REAL NOT NULL,
        currency TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS budgets (
        week_start TEXT PRIMARY KEY,
        target REAL NOT NULL,
        currency TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS spend (
        id INTEGER PRIMARY KEY,
        item_id INTEGER,
        price REAL NOT NULL,
        currency TEXT NOT NULL,
        date TEXT NOT NULL,
        source TEXT NOT NULL
    )""",
]


def get_conn(db_path: str) -> sqlite3.Connection:
    """Open a connection with WAL mode, foreign keys ON, and Row rows."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create the schema. Idempotent: safe to call repeatedly."""
    for statement in _SCHEMA_STATEMENTS:
        conn.execute(statement)
    conn.commit()
