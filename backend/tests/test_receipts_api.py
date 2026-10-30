"""Tests for receipt ingestion API endpoints: /receipts/parse and /receipts/commit."""

from __future__ import annotations

import sqlite3
from unittest.mock import patch
from fastapi.testclient import TestClient

from openfresh.app_factory import create_app
from openfresh import receipts


SAMPLE_RECEIPT_TEXT = """
Walmart
10/30/2026 12:00:00

GV 2% MILK 1GAL       007874235186    3.48 F
BANANAS               000000004011    1.64 F
OREO COOKIES 12OZ     004400003202    4.28 T
BLEACH 64OZ           001234567890    2.99 T

SUBTOTAL                             12.39
TOTAL TAX                             0.11
TOTAL                                12.50
"""


def test_receipt_parse_and_commit(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    client = TestClient(app)

    # Test commit directly
    commit_payload = {
        "date": "2026-10-30",
        "currency": "USD",
        "record_spend": True,
        "total_spend": 12.50,
        "items": [
            {
                "name": "Apple Gala",
                "category": "Produce",
                "location": "fridge",
                "quantity": 3.0,
                "unit": "each",
                "price": 2.50,
                "include_inventory": True,
                "include_price": True,
            }
        ],
    }
    resp = client.post("/receipts/commit", json=commit_payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "ok"
    assert data["inventory_items_added"] == 1
    assert data["prices_updated"] == 1
    assert data["spend_recorded"] == 12.50

    # Verify inventory was created
    inv = client.get("/inventory?location=fridge").json()
    assert any(
        (i.get("name") == "Apple Gala" or i.get("name") == "apple gala" or i.get("item_name") == "apple gala")
        and i["quantity"] == 3.0
        for i in inv
    )

    # Verify spend was recorded
    budget = client.get("/budget?week_start=2026-10-26").json()
    assert budget["actual"] == 12.50


def test_receipt_commit_options_and_sources(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    client = TestClient(app)

    commit_payload = {
        "date": "2026-10-30",
        "currency": "USD",
        "record_spend": True,
        "total_spend": 15.00,
        "items": [
            {
                "name": "Whole Milk",
                "category": "dairy",
                "location": "fridge",
                "quantity": 1.0,
                "unit": "gal",
                "price": 3.50,
                "include_inventory": True,
                "include_price": True,
            },
            {
                "name": "Paper Towels",
                "category": "household",
                "location": "pantry",
                "quantity": 2.0,
                "unit": "pk",
                "price": 5.00,
                "include_inventory": False,  # Not added to inventory
                "include_price": True,       # Added to price library
            },
            {
                "name": "Snack Chips",
                "category": "pantry",
                "location": "pantry",
                "quantity": 3.0,
                "unit": "bag",
                "price": 2.00,
                "include_inventory": True,   # Added to inventory
                "include_price": False,      # Price not saved
            },
        ],
    }

    resp = client.post("/receipts/commit", json=commit_payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "ok"
    assert data["inventory_items_added"] == 2
    assert data["prices_updated"] == 2
    assert data["spend_recorded"] == 15.00

    # Verify directly against DB connection for source tags
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # 1. inventory_events source="receipt"
    events = conn.execute("SELECT * FROM inventory_events").fetchall()
    assert len(events) == 2
    for ev in events:
        assert ev["source"] == "receipt"

    # 2. prices_own source="receipt"
    prices = conn.execute("SELECT * FROM prices_own").fetchall()
    assert len(prices) == 2
    for p in prices:
        assert p["source"] == "receipt"
        assert p["date"] == "2026-10-30"

    # 3. spend source="receipt"
    spend_rows = conn.execute("SELECT * FROM spend").fetchall()
    assert len(spend_rows) == 1
    assert spend_rows[0]["source"] == "receipt"
    assert spend_rows[0]["price"] == 15.00
    assert spend_rows[0]["date"] == "2026-10-30"
    conn.close()


def test_receipt_commit_no_spend(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    client = TestClient(app)

    commit_payload = {
        "date": "2026-10-30",
        "currency": "USD",
        "record_spend": False,
        "total_spend": 25.00,
        "items": [
            {
                "name": "Cheddar Cheese",
                "category": "dairy",
                "location": "fridge",
                "quantity": 1.0,
                "unit": "pack",
                "price": 4.50,
                "include_inventory": True,
                "include_price": True,
            }
        ],
    }
    resp = client.post("/receipts/commit", json=commit_payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["spend_recorded"] == 0.0

    conn = sqlite3.connect(db_path)
    spend_rows = conn.execute("SELECT * FROM spend").fetchall()
    assert len(spend_rows) == 0
    conn.close()


def test_receipt_commit_transaction_rollback_on_failure(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    client = TestClient(app)

    commit_payload = {
        "date": "2026-10-30",
        "currency": "USD",
        "record_spend": True,
        "total_spend": 10.00,
        "items": [
            {
                "name": "Item 1",
                "category": "pantry",
                "location": "pantry",
                "quantity": 1.0,
                "unit": "each",
                "price": 2.00,
                "include_inventory": True,
                "include_price": True,
            },
            {
                "name": "Item 2",
                "category": "pantry",
                "location": "pantry",
                "quantity": 1.0,
                "unit": "each",
                "price": 3.00,
                "include_inventory": True,
                "include_price": True,
            },
        ],
    }

    # Simulate an error on the second item inside the commit transaction
    with patch("openfresh.inventory.add_item", side_effect=[1, RuntimeError("DB error on item 2")]):
        resp = client.post("/receipts/commit", json=commit_payload)
        assert resp.status_code >= 400

    # Ensure nothing was committed: rollback was clean
    conn = sqlite3.connect(db_path)
    inv_rows = conn.execute("SELECT * FROM inventory").fetchall()
    assert len(inv_rows) == 0
    prices_rows = conn.execute("SELECT * FROM prices_own").fetchall()
    assert len(prices_rows) == 0
    spend_rows = conn.execute("SELECT * FROM spend").fetchall()
    assert len(spend_rows) == 0
    conn.close()


def test_receipt_parse_endpoint(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    client = TestClient(app)

    with patch("openfresh.receipts.extract_text", return_value=SAMPLE_RECEIPT_TEXT):
        resp = client.post(
            "/receipts/parse",
            files={"file": ("receipt.pdf", b"%PDF-1.4 dummy", "application/pdf")},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["store"] == "Walmart"
        assert data["date"] == "2026-10-30"
        assert data["total"] == 12.50
        assert data["currency"] == "USD"
        assert len(data["items"]) >= 3

        # Check enrichment properties on items
        milk = next(i for i in data["items"] if "MILK" in i["raw_name"])
        assert milk["suggested_location"] == "fridge"
        assert milk["include"] is True
        assert milk["price"] == 3.48

        bleach = next((i for i in data["items"] if "BLEACH" in i["raw_name"]), None)
        if bleach:
            # Bleach is non-food, should be excluded from inventory by default
            assert bleach["include"] is False


def test_receipt_parse_unsupported_file(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    client = TestClient(app)

    resp = client.post(
        "/receipts/parse",
        files={"file": ("malware.exe", b"MZ...", "application/octet-stream")},
    )
    assert resp.status_code == 400
