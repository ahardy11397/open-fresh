"""Tests for layered pricing: own library > Open Prices lookup > estimates (task 5)."""

from openfresh import db, items, pricing


def _fresh_conn(tmp_path):
    conn = db.get_conn(str(tmp_path / "kitchen.db"))
    db.init_db(conn)
    return conn


def test_own_beats_estimate(tmp_path):
    conn = _fresh_conn(tmp_path)
    eggs = items.get_or_create(conn, "eggs")
    pricing.set_estimate(conn, eggs, "dairy", 3.0, "USD")
    pricing.record_own_price(conn, eggs, 2.5, "USD", "2026-10-15")
    assert pricing.price_item(conn, eggs) == (2.5, "own")


def test_falls_back_to_estimate(tmp_path):
    conn = _fresh_conn(tmp_path)
    eggs = items.get_or_create(conn, "eggs")
    pricing.set_estimate(conn, eggs, "dairy", 3.0, "USD")
    lookup = lambda name: None
    assert pricing.price_item(conn, eggs, lookup=lookup) == (3.0, "estimate")


def test_openprices_lookup_used_when_no_own(tmp_path):
    conn = _fresh_conn(tmp_path)
    eggs = items.get_or_create(conn, "eggs")
    pricing.set_estimate(conn, eggs, "dairy", 3.0, "USD")
    lookup = lambda name: 4.5
    assert pricing.price_item(conn, eggs, lookup=lookup) == (4.5, "openprices")


def test_all_missing_returns_none(tmp_path):
    conn = _fresh_conn(tmp_path)
    eggs = items.get_or_create(conn, "eggs")
    assert pricing.price_item(conn, eggs) is None


def test_generic_estimate_fallback_skips_category_tagged_rows(tmp_path):
    """A category-tagged generic row (item_id IS NULL, category NOT NULL)
    must NOT resolve via the generic fallback (review finding)."""
    conn = _fresh_conn(tmp_path)
    eggs = items.get_or_create(conn, "eggs")
    pricing.set_estimate(conn, None, "household", 9.99, "USD")
    assert pricing.price_item(conn, eggs) is None


def test_generic_estimate_fallback_matches_true_generic_rows(tmp_path):
    """A true generic estimate (item_id IS NULL AND category IS NULL)
    must still resolve via the generic fallback."""
    conn = _fresh_conn(tmp_path)
    eggs = items.get_or_create(conn, "eggs")
    pricing.set_estimate(conn, None, "household", 9.99, "USD")
    pricing.set_estimate(conn, None, None, 3.25, "USD")
    assert pricing.price_item(conn, eggs) == (3.25, "estimate")


def test_make_lookup_parses_response():
    class FakeResponse:
        def json(self):
            return {"items": [{"price": 3.0}, {"price": 3.4}], "total": 2}

    class FakeSession:
        def get(self, url, **kwargs):
            return FakeResponse()

    lookup = pricing.make_lookup(session=FakeSession())
    assert lookup("eggs") == 3.2


def test_make_lookup_returns_none_on_http_error():
    class FakeSession:
        def get(self, url, **kwargs):
            raise ConnectionError("network down")

    lookup = pricing.make_lookup(session=FakeSession())
    assert lookup("eggs") is None
