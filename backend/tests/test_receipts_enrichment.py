"""Tests for receipt item enrichment and location heuristics (Task 3)."""

import sqlite3

from openfresh.db import get_conn, init_db
from openfresh.inventory import add_item, remove_item
from openfresh.items import get_or_create, rename_alias
from openfresh.receipts import enrich_receipt_items


def _setup_db() -> sqlite3.Connection:
    conn = get_conn(":memory:")
    init_db(conn)
    return conn


def test_enrich_suggests_prior_location():
    conn = _setup_db()
    item_id = get_or_create(conn, "Whole Milk", category="Dairy")
    add_item(conn, item_id, "fridge", 1.0, "gal")

    parsed = {
        "store": "Walmart",
        "date": "2026-10-30",
        "total": 3.48,
        "currency": "USD",
        "items": [
            {
                "raw_name": "GV WHOLE MILK 1GAL",
                "name": "Whole Milk",
                "quantity": 1.0,
                "unit": "gal",
                "price": 3.48,
            }
        ],
    }
    enriched = enrich_receipt_items(conn, parsed)
    assert len(enriched["items"]) == 1
    item = enriched["items"][0]
    assert item["matched_item_id"] == item_id
    assert item["suggested_location"] == "fridge"
    assert item["category"] == "dairy"
    assert item["include"] is True


def test_enrich_prior_location_overrides_keyword_heuristic():
    conn = _setup_db()
    # Butter would normally match fridge keyword, but user stores it in freezer
    item_id = get_or_create(conn, "Salted Butter", category="Dairy")
    add_item(conn, item_id, "freezer", 2.0, "lb")

    parsed = {
        "store": "Walmart",
        "date": "2026-10-30",
        "total": 4.98,
        "currency": "USD",
        "items": [
            {
                "raw_name": "LAND O LAKES BUTTER",
                "name": "Salted Butter",
                "quantity": 1.0,
                "unit": "lb",
                "price": 4.98,
            }
        ],
    }
    enriched = enrich_receipt_items(conn, parsed)
    item = enriched["items"][0]
    assert item["matched_item_id"] == item_id
    assert item["suggested_location"] == "freezer"


def test_enrich_alias_match():
    conn = _setup_db()
    item_id = get_or_create(conn, "Bananas", category="Produce")
    rename_alias(conn, "fresh yellow bananas", item_id)

    parsed = {
        "store": "Walmart",
        "date": "2026-10-30",
        "total": 1.58,
        "currency": "USD",
        "items": [
            {
                "raw_name": "4011 FRESH YELLOW BANANAS",
                "name": "Fresh Yellow Bananas",
                "quantity": 2.1,
                "unit": "lb",
                "price": 1.58,
            }
        ],
    }
    enriched = enrich_receipt_items(conn, parsed)
    item = enriched["items"][0]
    assert item["matched_item_id"] == item_id
    assert item["suggested_location"] == "fridge"


def test_enrich_prior_location_from_inventory_events():
    conn = _setup_db()
    item_id = get_or_create(conn, "Ice Cream Sandwiches", category="Frozen")
    inv_id = add_item(conn, item_id, "freezer", 1.0, "pk")
    remove_item(conn, inv_id)

    parsed = {
        "store": "Walmart",
        "date": "2026-10-30",
        "total": 3.99,
        "currency": "USD",
        "items": [
            {
                "raw_name": "ICE CREAM SANDWICHES",
                "name": "Ice Cream Sandwiches",
                "quantity": 1.0,
                "unit": "pk",
                "price": 3.99,
            }
        ],
    }
    enriched = enrich_receipt_items(conn, parsed)
    item = enriched["items"][0]
    assert item["matched_item_id"] == item_id
    assert item["suggested_location"] == "freezer"


def test_enrich_fallback_fridge_keywords():
    conn = _setup_db()
    parsed = {
        "store": "Walmart",
        "date": "2026-10-30",
        "total": 15.00,
        "currency": "USD",
        "items": [
            {"raw_name": "ORGANIC WHOLE MILK", "name": "Organic Whole Milk", "quantity": 1.0, "unit": "gal", "price": 4.50},
            {"raw_name": "BEEF RIBEYE STEAK", "name": "Beef Ribeye Steak", "quantity": 1.0, "unit": "lb", "price": 12.99},
            {"raw_name": "FRESH STRAWBERRIES 1LB", "name": "Fresh Strawberries", "quantity": 1.0, "unit": "lb", "price": 3.99},
            {"raw_name": "CHOBANI GREEK YOGURT", "name": "Greek Yogurt", "quantity": 1.0, "unit": "ct", "price": 1.50},
            {"raw_name": "GRADE A LARGE EGGS 12CT", "name": "Large Eggs", "quantity": 1.0, "unit": "ct", "price": 2.99},
        ],
    }
    enriched = enrich_receipt_items(conn, parsed)
    for it in enriched["items"]:
        assert it["matched_item_id"] is None
        assert it["suggested_location"] == "fridge"
        assert it["include"] is True


def test_enrich_fallback_freezer_keywords():
    conn = _setup_db()
    parsed = {
        "store": "Walmart",
        "date": "2026-10-30",
        "total": 12.00,
        "currency": "USD",
        "items": [
            {"raw_name": "BEN & JERRY ICE CREAM", "name": "Vanilla Ice Cream", "quantity": 1.0, "unit": "pt", "price": 4.99},
            {"raw_name": "DIGIORNO PEPPERONI PIZZA", "name": "Pepperoni Pizza", "quantity": 1.0, "unit": "ct", "price": 6.99},
            {"raw_name": "BIRDS EYE FROZEN PEAS", "name": "Frozen Peas", "quantity": 1.0, "unit": "lb", "price": 1.99},
            {"raw_name": "FRUIT POPSICLES 6PK", "name": "Fruit Popsicles", "quantity": 1.0, "unit": "pk", "price": 3.49},
        ],
    }
    enriched = enrich_receipt_items(conn, parsed)
    for it in enriched["items"]:
        assert it["matched_item_id"] is None
        assert it["suggested_location"] == "freezer"
        assert it["category"] == "frozen"
        assert it["include"] is True


def test_enrich_fallback_pantry_default():
    conn = _setup_db()
    parsed = {
        "store": "Walmart",
        "date": "2026-10-30",
        "total": 8.00,
        "currency": "USD",
        "items": [
            {"raw_name": "BARILLA PENNE PASTA 1LB", "name": "Penne Pasta", "quantity": 1.0, "unit": "lb", "price": 1.78},
            {"raw_name": "JASMINE RICE 5LB", "name": "Jasmine Rice", "quantity": 1.0, "unit": "bag", "price": 5.99},
            {"raw_name": "BERTOLLI OLIVE OIL 500ML", "name": "Olive Oil", "quantity": 1.0, "unit": "ml", "price": 8.49},
        ],
    }
    enriched = enrich_receipt_items(conn, parsed)
    for it in enriched["items"]:
        assert it["matched_item_id"] is None
        assert it["suggested_location"] == "pantry"
        assert it["include"] is True


def test_enrich_non_food_item_exclusion():
    conn = _setup_db()
    parsed = {
        "store": "Walmart",
        "date": "2026-10-30",
        "total": 45.00,
        "currency": "USD",
        "items": [
            {"raw_name": "MOBIL 1 MOTOR OIL 5W-30", "name": "Motor Oil 5W-30", "quantity": 1.0, "unit": "qt", "price": 28.97},
            {"raw_name": "ENERGIZER AA BATTERIES 8PK", "name": "AA Batteries", "quantity": 1.0, "unit": "pk", "price": 9.98},
            {"raw_name": "BOUNTY PAPER TOWELS 6PK", "name": "Paper Towels", "quantity": 1.0, "unit": "pk", "price": 14.50},
            {"raw_name": "TIDE LAUNDRY DETERGENT", "name": "Laundry Detergent", "quantity": 1.0, "unit": "ct", "price": 12.99},
        ],
    }
    enriched = enrich_receipt_items(conn, parsed)
    for it in enriched["items"]:
        assert it["matched_item_id"] is None
        assert it["include"] is False
        assert it["suggested_location"] == "pantry"
        assert it["category"] == "household"


def test_enrich_word_boundary_avoidance():
    conn = _setup_db()
    parsed = {
        "store": "Walmart",
        "date": "2026-10-30",
        "total": 10.00,
        "currency": "USD",
        "items": [
            # "Nutmeg" has "egg", but is a spice (pantry)
            {"raw_name": "MCCORMICK GROUND NUTMEG", "name": "Ground Nutmeg", "quantity": 1.0, "unit": "oz", "price": 3.49},
            # "Graham Crackers" has "ham", but is a cracker (pantry)
            {"raw_name": "HONEY MAID GRAHAM CRACKERS", "name": "Graham Crackers", "quantity": 1.0, "unit": "box", "price": 4.29},
            # "Peanut Butter" has "butter", but is shelf-stable (pantry)
            {"raw_name": "JIF CREAMY PEANUT BUTTER", "name": "Creamy Peanut Butter", "quantity": 1.0, "unit": "oz", "price": 3.99},
        ],
    }
    enriched = enrich_receipt_items(conn, parsed)
    for it in enriched["items"]:
        assert it["suggested_location"] == "pantry"
        assert it["include"] is True


def test_enrich_preserves_other_parsed_fields():
    conn = _setup_db()
    parsed = {
        "store": "Target",
        "date": "2026-10-25",
        "total": 3.50,
        "currency": "USD",
        "items": [
            {"raw_name": "WHOLE MILK", "name": "Whole Milk", "quantity": 1.0, "unit": "gal", "price": 3.50}
        ],
    }
    enriched = enrich_receipt_items(conn, parsed)
    assert enriched["store"] == "Target"
    assert enriched["date"] == "2026-10-25"
    assert enriched["total"] == 3.50
    assert enriched["currency"] == "USD"
    item = enriched["items"][0]
    assert item["raw_name"] == "WHOLE MILK"
    assert item["name"] == "Whole Milk"
    assert item["quantity"] == 1.0
    assert item["unit"] == "gal"
    assert item["price"] == 3.50


def test_enrich_empty_receipt():
    conn = _setup_db()
    parsed = {"store": "Walmart", "items": []}
    enriched = enrich_receipt_items(conn, parsed)
    assert enriched["store"] == "Walmart"
    assert enriched["items"] == []
