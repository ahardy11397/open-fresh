"""Tests for inventory store with source-tagged event log (task 3)."""

from openfresh import db, inventory, items


def _fresh_conn(tmp_path):
    conn = db.get_conn(str(tmp_path / "kitchen.db"))
    db.init_db(conn)
    return conn


def _events(conn):
    return [
        dict(row)
        for row in conn.execute(
            "SELECT item_id, location, delta, source, note FROM inventory_events ORDER BY id"
        )
    ]


def test_add_upserts_existing_row(tmp_path):
    conn = _fresh_conn(tmp_path)
    eggs = items.get_or_create(conn, "eggs")
    inv_id = inventory.add_item(conn, eggs, "fridge", 2.0, unit="dozen")
    assert conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0] == 1
    again = inventory.add_item(conn, eggs, "fridge", 1.0, unit="dozen")
    assert again == inv_id
    row = conn.execute(
        "SELECT quantity FROM inventory WHERE id = ?", (inv_id,)
    ).fetchone()
    assert row["quantity"] == 3.0


def test_remove_deletes_and_logs_negative_event(tmp_path):
    conn = _fresh_conn(tmp_path)
    eggs = items.get_or_create(conn, "eggs")
    inv_id = inventory.add_item(conn, eggs, "fridge", 2.0)
    inventory.remove_item(conn, inv_id, note="thrown out")
    assert conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0] == 0
    events = _events(conn)
    assert events[-1]["delta"] == -2.0
    assert events[-1]["note"] == "thrown out"


def test_adjust_floors_at_zero(tmp_path):
    conn = _fresh_conn(tmp_path)
    eggs = items.get_or_create(conn, "eggs")
    inv_id = inventory.add_item(conn, eggs, "fridge", 2.0)
    new_q = inventory.adjust(conn, inv_id, -5.0)
    assert new_q == 0.0
    row = conn.execute(
        "SELECT quantity FROM inventory WHERE id = ?", (inv_id,)
    ).fetchone()
    assert row["quantity"] == 0.0
    events = _events(conn)
    assert events[-1]["delta"] == -2.0


def test_consumption_floors_at_zero(tmp_path):
    conn = _fresh_conn(tmp_path)
    eggs = items.get_or_create(conn, "eggs")
    inventory.add_item(conn, eggs, "fridge", 4.0)
    inventory.add_item(conn, eggs, "pantry", 2.0)
    inventory.consume(conn, eggs, 10.0)
    rows = {
        row["location"]: row["quantity"]
        for row in conn.execute(
            "SELECT location, quantity FROM inventory WHERE item_id = ?", (eggs,)
        )
    }
    assert rows == {"fridge": 0.0, "pantry": 0.0}
    events = [e for e in _events(conn) if e["source"] == "cooking"]
    assert len(events) == 2


def test_logged_event_has_created_at(tmp_path):
    conn = _fresh_conn(tmp_path)
    eggs = items.get_or_create(conn, "eggs")
    inventory.add_item(conn, eggs, "fridge", 2.0)
    row = conn.execute(
        "SELECT created_at FROM inventory_events ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row["created_at"] is not None


def test_get_quantity_sums_locations(tmp_path):
    conn = _fresh_conn(tmp_path)
    eggs = items.get_or_create(conn, "eggs")
    inventory.add_item(conn, eggs, "fridge", 4.0)
    inventory.add_item(conn, eggs, "pantry", 2.0)
    assert inventory.get_quantity(conn, eggs) == 6.0


def test_add_item_negative_floors_at_zero(tmp_path):
    """Negative quantity can never store a negative row (final-review finding 1)."""
    conn = _fresh_conn(tmp_path)
    eggs = items.get_or_create(conn, "eggs")

    # insert path: negative quantity floors at 0
    inv_id = inventory.add_item(conn, eggs, "fridge", -5.0)
    row = conn.execute(
        "SELECT quantity FROM inventory WHERE id = ?", (inv_id,)
    ).fetchone()
    assert row["quantity"] == 0.0
    events = _events(conn)
    assert events[-1]["delta"] == 0.0  # the true applied delta is logged

    # upsert path: 2.0 in stock + (-5.0) floors at 0, applies -2.0
    inventory.add_item(conn, eggs, "fridge", 2.0)
    inventory.add_item(conn, eggs, "fridge", -5.0)
    row = conn.execute(
        "SELECT quantity FROM inventory WHERE id = ?", (inv_id,)
    ).fetchone()
    assert row["quantity"] == 0.0
    events = _events(conn)
    assert events[-1]["delta"] == -2.0


def test_get_quantity_filters_by_unit(tmp_path):
    conn = _fresh_conn(tmp_path)
    rice = items.get_or_create(conn, "rice")
    inventory.add_item(conn, rice, "pantry", 100.0, unit="g")
    inventory.add_item(conn, rice, "fridge", 1.0, unit="cup")
    assert inventory.get_quantity(conn, rice) == 101.0
    assert inventory.get_quantity(conn, rice, unit="g") == 100.0
    assert inventory.get_quantity(conn, rice, unit="cup") == 1.0
