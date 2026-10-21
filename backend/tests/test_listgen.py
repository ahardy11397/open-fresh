"""Tests for grocery list generation from the week plan minus inventory (task 6)."""

from datetime import date, timedelta

import pytest

from openfresh import db, inventory, items, listgen, pricing, recipes, settings

WEEK_START = "2026-10-19"  # a Monday
MID_WEEK = "2026-10-22"
NEXT_WEEK = "2026-10-26"  # exactly week_start + 7 -> outside the window


@pytest.fixture(autouse=True)
def _no_network_openprices(monkeypatch):
    """Avoid real network calls to Open Prices during unit tests."""
    monkeypatch.setattr(pricing, "make_lookup", lambda: (lambda _name: None))


def _fresh_conn(tmp_path):
    conn = db.get_conn(str(tmp_path / "kitchen.db"))
    db.init_db(conn)
    return conn


def _plan(conn, recipe_id, date_str, servings_override=None, cooked=0):
    conn.execute(
        "INSERT INTO plan_entries (recipe_id, date, slot, servings_override, cooked)"
        " VALUES (?, ?, ?, ?, ?)",
        (recipe_id, date_str, "dinner", servings_override, cooked),
    )
    conn.commit()


def _line_for(lines, name):
    matches = [line for line in lines if line["name"] == name]
    assert len(matches) == 1, f"expected exactly one line for {name!r}, got {lines}"
    return matches[0]


def test_merges_duplicates_sums_same_unit(tmp_path):
    conn = _fresh_conn(tmp_path)
    r1 = recipes.create_recipe(conn, "Rice Bowl")
    recipes.add_ingredient(conn, r1, "rice", 1.0, "cup")
    r2 = recipes.create_recipe(conn, "Fried Rice")
    recipes.add_ingredient(conn, r2, "rice", 1.0, "cup")
    _plan(conn, r1, MID_WEEK)
    _plan(conn, r2, MID_WEEK)

    lines = listgen.generate_list(conn, WEEK_START)

    assert len(lines) == 1
    assert lines[0]["quantity"] == 2
    assert lines[0]["unit"] == "cup"


def test_mixed_units_stay_separate(tmp_path):
    conn = _fresh_conn(tmp_path)
    r = recipes.create_recipe(conn, "Rice Two Ways")
    recipes.add_ingredient(conn, r, "rice", 200.0, "g")
    recipes.add_ingredient(conn, r, "rice", 1.0, "cup")
    _plan(conn, r, MID_WEEK)

    lines = listgen.generate_list(conn, WEEK_START)

    by_unit = {line["unit"]: line["quantity"] for line in lines}
    assert by_unit == {"g": 200.0, "cup": 1.0}


def test_subtracts_inventory(tmp_path):
    conn = _fresh_conn(tmp_path)
    r = recipes.create_recipe(conn, "Omelette")
    recipes.add_ingredient(conn, r, "eggs", 6.0, "")
    eggs = items.get_or_create(conn, "eggs")
    inventory.add_item(conn, eggs, "fridge", 4.0)
    _plan(conn, r, MID_WEEK)

    lines = listgen.generate_list(conn, WEEK_START)

    assert len(lines) == 1
    assert lines[0]["quantity"] == 2


def test_subtraction_matches_unit(tmp_path):
    """Only same-unit stock is subtracted from a line (final-review finding 2)."""
    conn = _fresh_conn(tmp_path)
    r = recipes.create_recipe(conn, "Rice Two Ways")
    recipes.add_ingredient(conn, r, "rice", 200.0, "g")
    recipes.add_ingredient(conn, r, "rice", 1.0, "cup")
    rice = items.get_or_create(conn, "rice")
    inventory.add_item(conn, rice, "pantry", 100.0, unit="g")
    _plan(conn, r, MID_WEEK)

    lines = listgen.generate_list(conn, WEEK_START)

    by_unit = {line["unit"]: line["quantity"] for line in lines}
    assert by_unit == {"g": 100.0, "cup": 1.0}


def test_staples_never_listed(tmp_path):
    conn = _fresh_conn(tmp_path)
    r = recipes.create_recipe(conn, "Salted Thing")
    recipes.add_ingredient(conn, r, "salt", 1.0, "tsp", staple=True)
    _plan(conn, r, MID_WEEK)

    lines = listgen.generate_list(conn, WEEK_START)

    assert lines == []


def test_scales_to_household(tmp_path):
    conn = _fresh_conn(tmp_path)
    settings.set_setting(conn, settings.HOUSEHOLD_SIZE_KEY, "4")
    r = recipes.create_recipe(conn, "Rice For Two", servings=2)
    recipes.add_ingredient(conn, r, "rice", 200.0, "g")
    _plan(conn, r, MID_WEEK)

    lines = listgen.generate_list(conn, WEEK_START)

    assert len(lines) == 1
    assert lines[0]["quantity"] == 400.0


def test_servings_override_wins(tmp_path):
    conn = _fresh_conn(tmp_path)
    settings.set_setting(conn, settings.HOUSEHOLD_SIZE_KEY, "4")
    r = recipes.create_recipe(conn, "Solo Rice", servings=2)
    recipes.add_ingredient(conn, r, "rice", 200.0, "g")
    _plan(conn, r, MID_WEEK, servings_override=1)

    lines = listgen.generate_list(conn, WEEK_START)

    assert len(lines) == 1
    assert lines[0]["quantity"] == 100.0


def test_lines_carry_price_source(tmp_path):
    conn = _fresh_conn(tmp_path)
    r = recipes.create_recipe(conn, "Omelette")
    recipes.add_ingredient(conn, r, "eggs", 6.0, "")
    eggs = items.get_or_create(conn, "eggs")
    pricing.set_estimate(conn, eggs, "dairy", 3.0, "USD")
    _plan(conn, r, MID_WEEK)

    lines = listgen.generate_list(conn, WEEK_START, lookup=None)

    assert len(lines) == 1
    assert lines[0]["price_source"] == "estimate"
    assert lines[0]["price"] == 18.0  # 3.0 per unit x 6 needed


def test_listgen_bulk_package_and_cross_unit_inventory(tmp_path):
    """1 cup milk needed when 1 gal is $4.00 -> $0.25; and if 0.5 gal (8 cups)
    is in inventory and recipe needs 10 cups, only 2 cups ($0.50) are listed."""
    conn = _fresh_conn(tmp_path)
    r = recipes.create_recipe(conn, "Custard", servings=2)
    recipes.add_ingredient(conn, r, "milk", 10.0, "cup")
    milk = items.get_or_create(conn, "milk", category="dairy")
    inventory.add_item(conn, milk, "fridge", 0.5, unit="gal")  # 8 cups on hand
    pricing.set_estimate(
        conn, None, "dairy", 4.0, "USD",
        package_quantity=1.0, package_unit="gal",
    )
    _plan(conn, r, MID_WEEK)

    lines = listgen.generate_list(conn, WEEK_START, lookup=None)

    assert len(lines) == 1
    assert lines[0]["quantity"] == 2.0  # 10 cups - 8 cups (0.5 gal)
    assert lines[0]["unit"] == "cup"
    assert lines[0]["price"] == 0.50    # 2 cups / 16 cups * $4.00
    assert lines[0]["price_source"] == "estimate"


def test_lines_carry_currency(tmp_path):
    """Line dicts carry the resolved price's currency (final-review finding 6)."""
    conn = _fresh_conn(tmp_path)
    r = recipes.create_recipe(conn, "Omelette")
    recipes.add_ingredient(conn, r, "eggs", 6.0, "")
    eggs = items.get_or_create(conn, "eggs")
    pricing.set_estimate(conn, eggs, "dairy", 3.0, "EUR")
    _plan(conn, r, MID_WEEK)

    lines = listgen.generate_list(conn, WEEK_START)

    assert len(lines) == 1
    assert lines[0]["currency"] == "EUR"


def test_unpriced_line_currency_defaults_to_usd(tmp_path):
    """A line with no resolvable price defaults its currency to USD."""
    conn = _fresh_conn(tmp_path)
    r = recipes.create_recipe(conn, "Mystery Dish")
    recipes.add_ingredient(conn, r, "mystery", 1.0, "cup")
    _plan(conn, r, MID_WEEK)

    lines = listgen.generate_list(conn, WEEK_START)

    assert len(lines) == 1
    assert lines[0]["price"] is None
    assert lines[0]["currency"] == "USD"


def test_odd_units_survive_listgen(tmp_path):
    conn = _fresh_conn(tmp_path)
    r = recipes.create_recipe(conn, "Glug Thing")
    recipes.add_ingredient(conn, r, "1 glug of oil", None)
    _plan(conn, r, MID_WEEK)

    lines = listgen.generate_list(conn, WEEK_START)  # must not raise

    assert len(lines) == 1
    assert lines[0]["quantity"] is None


def test_ignores_entries_outside_week(tmp_path):
    conn = _fresh_conn(tmp_path)
    r = recipes.create_recipe(conn, "Next Week Rice")
    recipes.add_ingredient(conn, r, "rice", 1.0, "cup")
    _plan(conn, r, NEXT_WEEK)

    assert listgen.generate_list(conn, WEEK_START) == []


def test_ignores_cooked_entries(tmp_path):
    conn = _fresh_conn(tmp_path)
    r = recipes.create_recipe(conn, "Already Cooked")
    recipes.add_ingredient(conn, r, "rice", 1.0, "cup")
    _plan(conn, r, MID_WEEK, cooked=1)

    assert listgen.generate_list(conn, WEEK_START) == []


def test_week_window_bounds():
    start = date.fromisoformat(WEEK_START)
    assert start + timedelta(days=7) == date.fromisoformat(NEXT_WEEK)
