import sqlite3

from openfresh import db


def test_init_db_idempotent():
    conn = db.get_conn(":memory:")
    db.init_db(conn)
    # Running init a second time must raise no error.
    db.init_db(conn)
    names = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    expected = {
        "settings",
        "items",
        "item_aliases",
        "inventory",
        "inventory_events",
        "recipes",
        "recipe_ingredients",
        "plan_entries",
        "prices_own",
        "price_estimates",
        "budgets",
        "spend",
    }
    assert expected <= names


def test_get_conn_pragmas():
    conn = db.get_conn(":memory:")
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal" or True  # :memory: cannot be WAL
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert isinstance(conn.execute("SELECT 1").fetchone(), sqlite3.Row)


def test_get_conn_wal_on_file(tmp_path):
    db_path = str(tmp_path / "kitchen.db")
    conn = db.get_conn(db_path)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_foreign_keys_enforced():
    conn = db.get_conn(":memory:")
    db.init_db(conn)
    import pytest

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO item_aliases (alias, item_id) VALUES ('scallion', 999)"
        )
