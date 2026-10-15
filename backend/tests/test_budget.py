"""Tests for the weekly budget: estimated vs actual spend (task 9)."""

import pytest

from openfresh import budget, db, items, listgen, pricing, recipes

WEEK_START = "2026-10-19"  # a Monday
MID_WEEK = "2026-10-22"
NEXT_WEEK = "2026-10-26"  # exactly week_start + 7 -> outside the window


def _fresh_conn(tmp_path):
    conn = db.get_conn(str(tmp_path / "kitchen.db"))
    db.init_db(conn)
    return conn


def _plan_one_priced(conn, name="rice", price=2.0):
    """Plan one recipe with one priced (non-staple) ingredient."""
    r = recipes.create_recipe(conn, "Rice Bowl")
    recipes.add_ingredient(conn, r, name, 2.0, "cup")
    item_id = items.get_or_create(conn, name)
    pricing.record_own_price(conn, item_id, price, "USD", WEEK_START)
    conn.execute(
        "INSERT INTO plan_entries (recipe_id, date, slot, cooked)"
        " VALUES (?, ?, 'dinner', 0)",
        (r, MID_WEEK),
    )
    conn.commit()
    return item_id


def test_summary_estimates_from_list(tmp_path):
    conn = _fresh_conn(tmp_path)
    _plan_one_priced(conn, price=2.0)

    summary = budget.week_summary(conn, WEEK_START)

    assert summary["week_start"] == WEEK_START
    assert summary["target"] == 0.0  # no budget set
    assert summary["currency"] == "USD"
    assert summary["estimated"] > 0
    assert summary["actual"] == 0.0
    assert len(summary["lines"]) == 1
    assert summary["lines"][0]["price"] is not None


def test_summary_estimated_skips_unpriced_lines(tmp_path):
    """A planned line with no resolvable price is skipped by the estimate."""
    conn = _fresh_conn(tmp_path)
    _plan_one_priced(conn, name="rice", price=2.0)
    r2 = recipes.create_recipe(conn, "Mystery Dish")
    recipes.add_ingredient(conn, r2, "mystery", 1.0, "cup")
    conn.execute(
        "INSERT INTO plan_entries (recipe_id, date, slot, cooked)"
        " VALUES (?, ?, 'dinner', 0)",
        (r2, MID_WEEK),
    )
    conn.commit()

    lines = listgen.generate_list(conn, WEEK_START)
    assert any(line["price"] is None for line in lines)

    summary = budget.week_summary(conn, WEEK_START)
    priced = sum(
        line["price"] for line in lines if line["price"] is not None
    )
    assert summary["estimated"] == priced


def test_actual_from_spend_rows(tmp_path):
    conn = _fresh_conn(tmp_path)
    item_id = _plan_one_priced(conn, price=2.0)
    budget.set_budget(conn, WEEK_START, 50.0)
    budget.record_spend(conn, item_id, 3.50, "USD", MID_WEEK)
    budget.record_spend(conn, None, 1.25, "USD", WEEK_START)
    budget.record_spend(conn, None, 9.99, "USD", NEXT_WEEK)  # outside window

    summary = budget.week_summary(conn, WEEK_START)

    assert summary["target"] == 50.0
    assert summary["currency"] == "USD"
    assert summary["actual"] == 4.75
    assert summary["estimated"] > 0


def test_remaining_uses_actual_when_present(tmp_path):
    conn = _fresh_conn(tmp_path)
    item_id = _plan_one_priced(conn, price=2.0)
    budget.set_budget(conn, WEEK_START, 50.0)
    # Estimated would be 4.00 (2 cups x 2.00); actual spend is 10.00.
    budget.record_spend(conn, item_id, 6.00, "USD", MID_WEEK)
    budget.record_spend(conn, item_id, 4.00, "USD", MID_WEEK)

    summary = budget.week_summary(conn, WEEK_START)

    assert summary["estimated"] == 4.0
    assert summary["actual"] == 10.0
    assert summary["remaining"] == 50.0 - 10.0


def test_remaining_uses_estimated_when_no_spend(tmp_path):
    conn = _fresh_conn(tmp_path)
    _plan_one_priced(conn, price=2.0)
    budget.set_budget(conn, WEEK_START, 50.0)

    summary = budget.week_summary(conn, WEEK_START)

    assert summary["estimated"] == 4.0
    assert summary["actual"] == 0.0
    assert summary["remaining"] == 50.0 - 4.0


def test_set_budget_upserts(tmp_path):
    conn = _fresh_conn(tmp_path)
    budget.set_budget(conn, WEEK_START, 50.0, currency="EUR")
    budget.set_budget(conn, WEEK_START, 60.0, currency="EUR")

    row = conn.execute(
        "SELECT target, currency FROM budgets WHERE week_start = ?",
        (WEEK_START,),
    ).fetchone()
    assert row["target"] == 60.0
    assert row["currency"] == "EUR"

    summary = budget.week_summary(conn, WEEK_START)
    assert summary["target"] == 60.0
    assert summary["currency"] == "EUR"


def test_empty_week_zeroes(tmp_path):
    conn = _fresh_conn(tmp_path)

    summary = budget.week_summary(conn, WEEK_START)

    assert summary == {
        "week_start": WEEK_START,
        "target": 0.0,
        "currency": "USD",
        "estimated": 0.0,
        "actual": 0.0,
        "remaining": 0.0,
        "lines": [],
    }


def test_summary_estimated_sums_only_matching_currency(tmp_path):
    """Currency-blind summing of mixed-currency lines is fixed (finding 6)."""
    conn = _fresh_conn(tmp_path)
    _plan_one_priced(conn, name="rice", price=2.0)  # USD line, 2 cups x 2.0
    r2 = recipes.create_recipe(conn, "Euro Dish")
    recipes.add_ingredient(conn, r2, "beans", 1.0, "cup")
    beans = items.get_or_create(conn, "beans")
    pricing.record_own_price(conn, beans, 3.0, "EUR", WEEK_START)
    conn.execute(
        "INSERT INTO plan_entries (recipe_id, date, slot, cooked)"
        " VALUES (?, ?, 'dinner', 0)",
        (r2, MID_WEEK),
    )
    conn.commit()

    summary = budget.week_summary(conn, WEEK_START)

    assert summary["currency"] == "USD"
    assert summary["estimated"] == pytest.approx(4.0)  # EUR line excluded
    currencies = {line["currency"] for line in summary["lines"]}
    assert currencies == {"USD", "EUR"}


def test_actual_sums_only_matching_currency(tmp_path):
    conn = _fresh_conn(tmp_path)
    item_id = _plan_one_priced(conn, price=2.0)
    budget.set_budget(conn, WEEK_START, 50.0)
    budget.record_spend(conn, item_id, 3.50, "USD", MID_WEEK)
    budget.record_spend(conn, None, 10.00, "EUR", MID_WEEK)

    summary = budget.week_summary(conn, WEEK_START)

    assert summary["actual"] == pytest.approx(3.50)  # EUR spend excluded
