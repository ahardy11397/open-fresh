"""Tests for planner.auto_populate: deterministic fill (task 8)."""

from openfresh import db, items, planner, pricing, recipes, settings

WEEK_START = "2026-10-19"  # a Monday
MON, TUE, WED, THU, FRI = (
    "2026-10-19",
    "2026-10-20",
    "2026-10-21",
    "2026-10-22",
    "2026-10-23",
)


def _fresh_conn(tmp_path):
    conn = db.get_conn(str(tmp_path / "kitchen.db"))
    db.init_db(conn)
    return conn


def _recipe(conn, title, item_name, quantity=1.0, servings=2):
    recipe_id = recipes.create_recipe(conn, title, servings=servings)
    recipes.add_ingredient(conn, recipe_id, item_name, quantity, "")
    return recipe_id


def _item_id(conn, name):
    return items.get_or_create(conn, name)


def _planned_rows(conn):
    return [
        dict(row)
        for row in conn.execute(
            "SELECT id, recipe_id, date FROM plan_entries ORDER BY date, id"
        )
    ]


def test_fills_up_to_meals_per_week(tmp_path):
    conn = _fresh_conn(tmp_path)
    _recipe(conn, "Rice Bowl", "rice")
    _recipe(conn, "Soup", "carrot")
    _recipe(conn, "Salad", "lettuce")

    created = planner.auto_populate(conn, WEEK_START)

    assert len(created) == 5  # default meals_per_week
    rows = _planned_rows(conn)
    assert [r["date"] for r in rows] == [MON, TUE, WED, THU, FRI]
    assert sorted(created) == sorted(r["id"] for r in rows)


def test_respects_preferred_days(tmp_path):
    conn = _fresh_conn(tmp_path)
    settings.set_setting(conn, "preferred_days", "mon,fri")
    _recipe(conn, "Rice Bowl", "rice")
    _recipe(conn, "Soup", "carrot")
    _recipe(conn, "Salad", "lettuce")

    created = planner.auto_populate(conn, WEEK_START)

    rows = _planned_rows(conn)
    # Only 2 preferred dates exist, so only 2 entries are made.
    assert [r["date"] for r in rows] == [MON, FRI]
    assert sorted(created) == sorted(r["id"] for r in rows)


def test_skips_days_already_planned(tmp_path):
    conn = _fresh_conn(tmp_path)
    recipe_id = _recipe(conn, "Manual Pick", "rice")
    _recipe(conn, "Rice Bowl", "rice")
    _recipe(conn, "Soup", "carrot")
    _recipe(conn, "Salad", "lettuce")
    planner.add_entry(conn, recipe_id, TUE)

    created = planner.auto_populate(conn, WEEK_START)

    rows = _planned_rows(conn)
    assert len(created) == 4  # 1 uncooked entry already there, 5 - 1 slots
    dates = [r["date"] for r in rows]
    assert dates.count(TUE) == 1  # existing entry untouched, no second entry
    assert sorted(dates) == [MON, TUE, WED, THU, FRI]


def test_round_robin_no_repeat_until_exhausted(tmp_path):
    conn = _fresh_conn(tmp_path)
    r1 = _recipe(conn, "Rice Bowl", "rice")
    r2 = _recipe(conn, "Soup", "carrot")
    r3 = _recipe(conn, "Salad", "lettuce")

    planner.auto_populate(conn, WEEK_START)

    ids = [r["recipe_id"] for r in _planned_rows(conn)]
    # Each recipe used once before any repeats; the cycle then restarts.
    assert set(ids[:3]) == {r1, r2, r3}
    assert len(ids) == 5
    assert ids[3] == ids[0]
    assert ids[4] == ids[1]


def test_budget_pressure_defers_expensive_recipe(tmp_path):
    conn = _fresh_conn(tmp_path)
    rice = _item_id(conn, "rice")
    steak = _item_id(conn, "steak")
    cheap = _recipe(conn, "Rice Bowl", "rice")
    pricey = _recipe(conn, "Steak Night", "steak")
    pricing.set_estimate(conn, rice, None, 3.0, "USD")
    pricing.set_estimate(conn, steak, None, 25.0, "USD")
    conn.execute(
        "INSERT INTO budgets (week_start, target, currency) VALUES (?, ?, ?)",
        (WEEK_START, 20.0, "USD"),
    )
    conn.commit()

    planner.auto_populate(conn, WEEK_START)

    ids = [r["recipe_id"] for r in _planned_rows(conn)]
    assert len(ids) == 5  # 5 * 3.0 = 15.0 fits the 20 budget
    assert set(ids) == {cheap}  # the 25-cost recipe is deferred entirely
    assert pricey not in ids


def test_no_budget_row_never_skips(tmp_path):
    conn = _fresh_conn(tmp_path)
    rice = _item_id(conn, "rice")
    steak = _item_id(conn, "steak")
    cheap = _recipe(conn, "Rice Bowl", "rice")
    pricey = _recipe(conn, "Steak Night", "steak")
    pricing.set_estimate(conn, rice, None, 5.0, "USD")
    pricing.set_estimate(conn, steak, None, 25.0, "USD")
    # No budgets row at all.

    planner.auto_populate(conn, WEEK_START)

    ids = [r["recipe_id"] for r in _planned_rows(conn)]
    assert len(ids) == 5
    assert set(ids) == {cheap, pricey}  # nothing skipped without a budget


def test_chooser_hook_overrides_round_robin(tmp_path):
    conn = _fresh_conn(tmp_path)
    _recipe(conn, "Rice Bowl", "rice")
    fixed = _recipe(conn, "Soup", "carrot")
    _recipe(conn, "Salad", "lettuce")
    calls = []

    def chooser(conn, candidates, context):
        calls.append((candidates, context))
        return {"id": fixed}

    created = planner.auto_populate(conn, WEEK_START, chooser=chooser)

    ids = [r["recipe_id"] for r in _planned_rows(conn)]
    assert ids == [fixed] * 5
    assert len(created) == 5
    # Consulted once per slot with the recipe candidates and slot context.
    assert len(calls) == 5
    candidates, context = calls[0]
    assert {c["id"] for c in candidates} == {fixed - 1, fixed, fixed + 1}
    assert context["week_start"] == WEEK_START
    assert context["date"] == MON
