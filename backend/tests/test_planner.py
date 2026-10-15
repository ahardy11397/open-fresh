"""Tests for planner: plan entries and cooked check-off consumption (task 7)."""

from openfresh import db, inventory, items, planner, recipes, settings

MID_WEEK = "2026-10-22"


def _fresh_conn(tmp_path):
    conn = db.get_conn(str(tmp_path / "kitchen.db"))
    db.init_db(conn)
    return conn


def _egg_recipe(conn, title="Omelette", servings=2, eggs=4.0):
    recipe_id = recipes.create_recipe(conn, title, servings=servings)
    recipes.add_ingredient(conn, recipe_id, "eggs", eggs, "")
    return recipe_id


def _egg_item_id(conn):
    return items.get_or_create(conn, "eggs")


def _egg_inventory(conn):
    eggs = _egg_item_id(conn)
    row = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) AS total FROM inventory WHERE item_id = ?",
        (eggs,),
    ).fetchone()
    return float(row["total"])


# --- add_entry / get_week / list_entries -----------------------------------


def test_add_entry_returns_id_and_stores_row(tmp_path):
    conn = _fresh_conn(tmp_path)
    recipe_id = _egg_recipe(conn)

    entry_id = planner.add_entry(conn, recipe_id, MID_WEEK, slot="dinner")

    row = conn.execute(
        "SELECT recipe_id, date, slot, servings_override, cooked"
        " FROM plan_entries WHERE id = ?",
        (entry_id,),
    ).fetchone()
    assert row["recipe_id"] == recipe_id
    assert row["date"] == MID_WEEK
    assert row["slot"] == "dinner"
    assert row["servings_override"] is None
    assert row["cooked"] == 0


def test_add_entry_servings_override(tmp_path):
    conn = _fresh_conn(tmp_path)
    recipe_id = _egg_recipe(conn)

    entry_id = planner.add_entry(conn, recipe_id, MID_WEEK, servings_override=6)

    row = conn.execute(
        "SELECT servings_override FROM plan_entries WHERE id = ?", (entry_id,)
    ).fetchone()
    assert row["servings_override"] == 6


def test_get_week_joins_titles_ordered_by_date(tmp_path):
    conn = _fresh_conn(tmp_path)
    r1 = _egg_recipe(conn, title="Late Dish")
    r2 = _egg_recipe(conn, title="Early Dish")
    planner.add_entry(conn, r1, "2026-10-23")
    planner.add_entry(conn, r2, "2026-10-20")

    entries = planner.get_week(conn, "2026-10-19")

    assert [e["title"] for e in entries] == ["Early Dish", "Late Dish"]
    assert [e["date"] for e in entries] == ["2026-10-20", "2026-10-23"]


def test_get_week_includes_cooked_but_not_outside_week(tmp_path):
    # Spec: calendar shows "what is planned and what was cooked".
    conn = _fresh_conn(tmp_path)
    recipe_id = _egg_recipe(conn)
    planner.add_entry(conn, recipe_id, "2026-10-20")
    cooked_id = planner.add_entry(conn, recipe_id, "2026-10-21")
    planner.mark_cooked(conn, cooked_id)
    planner.add_entry(conn, recipe_id, "2026-10-26")  # week_start + 7

    entries = planner.get_week(conn, "2026-10-19")

    assert [e["date"] for e in entries] == ["2026-10-20", "2026-10-21"]
    assert [e["cooked"] for e in entries] == [0, 1]


def test_list_entries_filters_by_cooked(tmp_path):
    conn = _fresh_conn(tmp_path)
    recipe_id = _egg_recipe(conn)
    planner.add_entry(conn, recipe_id, "2026-10-20")
    cooked_id = planner.add_entry(conn, recipe_id, "2026-10-21")
    planner.mark_cooked(conn, cooked_id)

    all_entries = planner.list_entries(conn)
    cooked = planner.list_entries(conn, cooked=True)
    uncooked = planner.list_entries(conn, cooked=False)

    assert len(all_entries) == 2
    assert [e["id"] for e in cooked] == [cooked_id]
    assert all(e["cooked"] == 0 for e in uncooked)
    assert all(e["title"] == "Omelette" for e in all_entries)


# --- cooked check-off consumption (brief's required tests) ------------------


def test_mark_cooked_consumes_scaled_ingredients(tmp_path):
    conn = _fresh_conn(tmp_path)
    settings.set_setting(conn, settings.HOUSEHOLD_SIZE_KEY, "4")
    recipe_id = _egg_recipe(conn, servings=2, eggs=4.0)
    entry_id = planner.add_entry(conn, recipe_id, MID_WEEK)
    eggs = _egg_item_id(conn)
    inventory.add_item(conn, eggs, "fridge", 12.0)

    planner.mark_cooked(conn, entry_id)

    assert _egg_inventory(conn) == 4.0  # 12 - (4 eggs * 4/2)
    row = conn.execute(
        "SELECT cooked FROM plan_entries WHERE id = ?", (entry_id,)
    ).fetchone()
    assert row["cooked"] == 1


def test_cooked_consumes_and_floors(tmp_path):
    conn = _fresh_conn(tmp_path)
    recipe_id = _egg_recipe(conn, servings=2, eggs=4.0)
    entry_id = planner.add_entry(conn, recipe_id, MID_WEEK)
    eggs = _egg_item_id(conn)
    inventory.add_item(conn, eggs, "fridge", 3.0)

    planner.mark_cooked(conn, entry_id)  # must not raise

    assert _egg_inventory(conn) == 0.0


def test_remove_after_cooked_keeps_inventory(tmp_path):
    conn = _fresh_conn(tmp_path)
    recipe_id = _egg_recipe(conn, servings=2, eggs=4.0)
    entry_id = planner.add_entry(conn, recipe_id, MID_WEEK)
    eggs = _egg_item_id(conn)
    inventory.add_item(conn, eggs, "fridge", 10.0)
    planner.mark_cooked(conn, entry_id)
    assert _egg_inventory(conn) == 6.0

    planner.remove_entry(conn, entry_id)

    assert _egg_inventory(conn) == 6.0  # unchanged


def test_remove_uncooked_never_touches_inventory(tmp_path):
    conn = _fresh_conn(tmp_path)
    recipe_id = _egg_recipe(conn, servings=2, eggs=4.0)
    entry_id = planner.add_entry(conn, recipe_id, MID_WEEK)
    eggs = _egg_item_id(conn)
    inventory.add_item(conn, eggs, "fridge", 10.0)

    planner.remove_entry(conn, entry_id)

    assert _egg_inventory(conn) == 10.0
    row = conn.execute(
        "SELECT id FROM plan_entries WHERE id = ?", (entry_id,)
    ).fetchone()
    assert row is None


def test_staples_not_consumed(tmp_path):
    conn = _fresh_conn(tmp_path)
    recipe_id = recipes.create_recipe(conn, "Salted Eggs", servings=2)
    recipes.add_ingredient(conn, recipe_id, "eggs", 4.0, "")
    recipes.add_ingredient(conn, recipe_id, "salt", 1.0, "tsp", staple=True)
    entry_id = planner.add_entry(conn, recipe_id, MID_WEEK)
    salt = items.get_or_create(conn, "salt")
    inventory.add_item(conn, salt, "pantry", 100.0)

    planner.mark_cooked(conn, entry_id)

    row = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) AS total FROM inventory WHERE item_id = ?",
        (salt,),
    ).fetchone()
    assert float(row["total"]) == 100.0


def test_unquantified_ingredient_skips_consumption(tmp_path):
    conn = _fresh_conn(tmp_path)
    recipe_id = recipes.create_recipe(conn, "Glug Thing", servings=2)
    recipes.add_ingredient(conn, recipe_id, "1 glug of oil", None)
    entry_id = planner.add_entry(conn, recipe_id, MID_WEEK)
    oil = items.get_or_create(conn, "1 glug of oil")
    inventory.add_item(conn, oil, "pantry", 5.0)

    planner.mark_cooked(conn, entry_id)  # must not raise

    row = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) AS total FROM inventory WHERE item_id = ?",
        (oil,),
    ).fetchone()
    assert float(row["total"]) == 5.0


def test_mark_cooked_idempotent(tmp_path):
    conn = _fresh_conn(tmp_path)
    recipe_id = _egg_recipe(conn, servings=2, eggs=4.0)
    entry_id = planner.add_entry(conn, recipe_id, MID_WEEK)
    eggs = _egg_item_id(conn)
    inventory.add_item(conn, eggs, "fridge", 12.0)

    planner.mark_cooked(conn, entry_id)  # household default 2 -> consume 4
    planner.mark_cooked(conn, entry_id)  # second time must not consume again

    assert _egg_inventory(conn) == 8.0


def test_scaled_ingredients_helper_shape(tmp_path):
    conn = _fresh_conn(tmp_path)
    settings.set_setting(conn, settings.HOUSEHOLD_SIZE_KEY, "4")
    recipe_id = _egg_recipe(conn, servings=2, eggs=4.0)
    entry_id = planner.add_entry(conn, recipe_id, MID_WEEK)
    entry = conn.execute(
        "SELECT * FROM plan_entries WHERE id = ?", (entry_id,)
    ).fetchone()

    scaled = planner._scaled_ingredients(conn, entry)

    assert len(scaled) == 1
    item_id, raw, quantity, unit, staple = scaled[0]
    assert item_id == _egg_item_id(conn)
    assert raw == "eggs"
    assert quantity == 8.0  # 4 eggs * (4 household / 2 servings)
    assert unit == ""
    assert staple is False
