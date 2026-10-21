"""Weekly budget: target, estimated vs actual spend, summary.

Global constraints: manual inventory add/remove/adjust never touches the
budget; money values are (amount: float, currency: str). ``remaining``
prefers actual spend when any spend row exists in the week window, and
falls back to the list estimate for weeks with no spend recorded.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from openfresh import listgen, pricing


def set_budget(
    conn: sqlite3.Connection,
    week_start: str,
    target: float,
    currency: str = "USD",
) -> None:
    """Set (or replace) the budget target for the week starting at week_start."""
    conn.execute(
        "INSERT INTO budgets (week_start, target, currency) VALUES (?, ?, ?)"
        " ON CONFLICT(week_start) DO UPDATE SET target = excluded.target,"
        " currency = excluded.currency",
        (week_start, target, currency),
    )
    conn.commit()


def record_spend(
    conn: sqlite3.Connection,
    item_id: int | None,
    price: float,
    currency: str,
    date: str,
    source: str = "receipt",
) -> None:
    """Record one money-out row (item_id may be None for non-item spend)."""
    conn.execute(
        "INSERT INTO spend (item_id, price, currency, date, source)"
        " VALUES (?, ?, ?, ?, ?)",
        (item_id, price, currency, date, source),
    )
    conn.commit()


def _spend_in_window(
    conn: sqlite3.Connection, week_start: str, currency: str
) -> float:
    """Sum of spend rows (matching currency) dated in [week_start, +7 days)."""
    start = date.fromisoformat(week_start)
    end = start + timedelta(days=7)
    row = conn.execute(
        "SELECT SUM(price) FROM spend WHERE date >= ? AND date < ?"
        " AND currency = ?",
        (start.isoformat(), end.isoformat(), currency),
    ).fetchone()
    return float(row[0]) if row[0] is not None else 0.0


def week_summary(
    conn: sqlite3.Connection,
    week_start: str,
    lookup=pricing._DEFAULT_LOOKUP,
) -> dict:
    """Estimated vs actual for the week starting at week_start (ISO date).

    ``estimated`` sums generate_list line prices in the budget's currency
    (skipping None prices and other currencies); ``actual`` sums spend rows
    in the window matching the currency; ``remaining`` is ``target - actual``
    when any spend row exists, else ``target - estimated``.
    """
    start = date.fromisoformat(week_start)
    end = start + timedelta(days=7)
    spend_count = conn.execute(
        "SELECT COUNT(*) FROM spend WHERE date >= ? AND date < ?",
        (start.isoformat(), end.isoformat()),
    ).fetchone()[0]

    lines = listgen.generate_list(conn, week_start, lookup=lookup)
    budget_row = conn.execute(
        "SELECT target, currency FROM budgets WHERE week_start = ?",
        (week_start,),
    ).fetchone()
    target = float(budget_row["target"]) if budget_row is not None else 0.0
    currency = budget_row["currency"] if budget_row is not None else "USD"

    estimated = float(
        sum(
            line["price"]
            for line in lines
            if line["price"] is not None and line["currency"] == currency
        )
    )
    actual = _spend_in_window(conn, week_start, currency)

    base = actual if spend_count > 0 else estimated
    remaining = target - base

    return {
        "week_start": week_start,
        "target": target,
        "currency": currency,
        "estimated": estimated,
        "actual": actual,
        "remaining": remaining,
        "lines": lines,
    }
