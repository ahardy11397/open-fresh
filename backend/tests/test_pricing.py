"""Tests for layered pricing: own library > Open Prices lookup > estimates (task 5)."""

import pytest

from openfresh import db, items, pricing


@pytest.fixture(autouse=True)
def _no_network_openprices(monkeypatch):
    """Default to offline no-op HTTP session in unit tests unless overridden."""
    from openfresh import openprices

    class _NoopClient:
        is_closed = False

        def get(self, *args, **kwargs):
            return None

    monkeypatch.setattr(openprices, "_client", _NoopClient())


def _fresh_conn(tmp_path):
    conn = db.get_conn(str(tmp_path / "kitchen.db"))
    db.init_db(conn)
    return conn


def test_own_beats_estimate(tmp_path):
    conn = _fresh_conn(tmp_path)
    eggs = items.get_or_create(conn, "eggs")
    pricing.set_estimate(conn, eggs, "dairy", 3.0, "USD")
    pricing.record_own_price(conn, eggs, 2.5, "USD", "2026-10-15")
    assert pricing.price_item(conn, eggs) == (2.5, "own", "USD")


def test_falls_back_to_estimate(tmp_path):
    conn = _fresh_conn(tmp_path)
    eggs = items.get_or_create(conn, "eggs")
    pricing.set_estimate(conn, eggs, "dairy", 3.0, "EUR")
    lookup = lambda name: None
    assert pricing.price_item(conn, eggs, lookup=lookup) == (3.0, "estimate", "EUR")


def test_openprices_lookup_used_when_no_own(tmp_path):
    conn = _fresh_conn(tmp_path)
    eggs = items.get_or_create(conn, "eggs")
    pricing.set_estimate(conn, eggs, "dairy", 3.0, "USD")
    lookup = lambda name: 4.5
    # lookup returns a bare number: no currency is known
    assert pricing.price_item(conn, eggs, lookup=lookup) == (4.5, "openprices", None)


def test_openprices_is_default_lookup_when_omitted(tmp_path, monkeypatch):
    """When lookup is omitted, price_item uses openprices.make_lookup() by default."""
    conn = _fresh_conn(tmp_path)
    eggs = items.get_or_create(conn, "eggs")
    called = []

    def fake_make_lookup():
        def _lookup(name):
            called.append(name)
            return 2.75
        return _lookup

    monkeypatch.setattr(pricing, "make_lookup", fake_make_lookup)
    assert pricing.price_item(conn, eggs) == (2.75, "openprices", None)
    assert called == ["eggs"]


def test_bulk_package_proportional_pricing(tmp_path):
    """1 cup of milk from a 16-cup (or 1-gal) jug @ $4.00 costs $0.25."""
    conn = _fresh_conn(tmp_path)
    milk = items.get_or_create(conn, "milk")
    pricing.record_own_price(
        conn, milk, 4.0, "USD", "2026-10-15",
        package_quantity=1.0, package_unit="gal",
    )
    resolved = pricing.price_item(conn, milk, lookup=None)
    assert resolved[:3] == (4.0, "own", "USD")
    # 1 cup is 1/16 of 1 gal -> $0.25
    assert pricing.convert(conn, milk, 1.0, "cup", resolved, "USD") == 0.25
    # 250 g of flour from a 2 kg bag @ $3.00 -> 250/2000 * 3.00 = $0.375
    flour = items.get_or_create(conn, "flour")
    pricing.set_estimate(
        conn, flour, "baking", 3.0, "USD",
        package_quantity=2.0, package_unit="kg",
    )
    flour_res = pricing.price_item(conn, flour, lookup=None)
    assert pricing.convert(conn, flour, 250.0, "g", flour_res, "USD") == 0.375


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
    assert pricing.price_item(conn, eggs, lookup=None) == (3.25, "estimate", "USD")


def test_category_estimate_resolves_for_categorized_item(tmp_path):
    """Item-specific > item's category estimate > global estimate."""
    conn = _fresh_conn(tmp_path)
    milk = items.get_or_create(conn, "milk", category="dairy")
    pricing.set_estimate(conn, None, None, 1.50, "USD")
    pricing.set_estimate(conn, None, "dairy", 4.25, "USD")
    pricing.set_estimate(conn, None, "produce", 2.00, "USD")
    assert pricing.price_item(conn, milk, lookup=None) == (4.25, "estimate", "USD")

    # Item-specific estimate beats category estimate
    pricing.set_estimate(conn, milk, "dairy", 3.75, "USD")
    assert pricing.price_item(conn, milk, lookup=None) == (3.75, "estimate", "USD")


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
