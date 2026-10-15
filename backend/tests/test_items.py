"""Tests for canonical items and alias normalization (task 2)."""

from openfresh import db, items


def _fresh_conn(tmp_path):
    conn = db.get_conn(str(tmp_path / "kitchen.db"))
    db.init_db(conn)
    return conn


def test_alias_reuse(tmp_path):
    conn = _fresh_conn(tmp_path)
    first = items.get_or_create_with_alias(conn, "Tomatoes")
    second = items.get_or_create_with_alias(conn, "tomatoes  ")
    assert first == second
    assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 1


def test_free_text_creates_alias(tmp_path):
    conn = _fresh_conn(tmp_path)
    item_id = items.get_or_create_with_alias(conn, "Roma tomatoes")
    row = conn.execute("SELECT name FROM items WHERE id = ?", (item_id,)).fetchone()
    assert row["name"] == "roma tomatoes"
    aliases = {
        r["alias"]
        for r in conn.execute(
            "SELECT alias FROM item_aliases WHERE item_id = ?", (item_id,)
        )
    }
    # aliases are stored normalized (collapsed lowercase), not raw
    assert "roma tomatoes" in aliases
    assert "Roma tomatoes" not in aliases


def test_alias_redirects_after_manual_link(tmp_path):
    conn = _fresh_conn(tmp_path)
    tomatoes_id = items.get_or_create_with_alias(conn, "Tomatoes")
    items.get_or_create_with_alias(conn, "Roma tomatoes")
    items.rename_alias(conn, "roma tomatoes", tomatoes_id)
    assert items.get_or_create_with_alias(conn, "roma tomatoes") == tomatoes_id
