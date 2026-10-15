"""Tests for the Open Prices lookup factory (task 5).

No network calls: a fake httpx-style session is injected in every test.
"""

from openfresh import openprices


def test_make_lookup_builds_url_with_product_name():
    seen = {}

    class FakeResponse:
        def json(self):
            return {"items": [], "total": 0}

    class FakeSession:
        def get(self, url, **kwargs):
            seen["url"] = url
            seen["params"] = kwargs.get("params")
            return FakeResponse()

    lookup = openprices.make_lookup(session=FakeSession())
    assert lookup("eggs") is None
    assert seen["url"].startswith(
        "https://prices.openfoodfacts.org/api/v1/prices"
    )
    assert seen["params"]["product_name"] == "eggs"


def test_make_lookup_adds_location_filter():
    seen = {}

    class FakeResponse:
        def json(self):
            return {"items": [], "total": 0}

    class FakeSession:
        def get(self, url, **kwargs):
            seen["params"] = kwargs.get("params")
            return FakeResponse()

    lookup = openprices.make_lookup(session=FakeSession(), location_ids=[42, 7])
    lookup("eggs")
    assert seen["params"]["location_id__in"] == "42,7"


def test_make_lookup_uses_median_of_newest_10_rows():
    class FakeResponse:
        def json(self):
            return {
                "items": [
                    {"price": p}
                    for p in [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 999.0]
                ],
                "total": 11,
            }

    class FakeSession:
        def get(self, url, **kwargs):
            return FakeResponse()

    lookup = openprices.make_lookup(session=FakeSession())
    assert lookup("eggs") == 5.5  # median of first 10 rows, 999.0 ignored


def test_make_lookup_parses_response():
    class FakeResponse:
        def json(self):
            return {"items": [{"price": 3.0}, {"price": 3.4}], "total": 2}

    class FakeSession:
        def get(self, url, **kwargs):
            return FakeResponse()

    lookup = openprices.make_lookup(session=FakeSession())
    assert lookup("eggs") == 3.2


def test_make_lookup_returns_none_on_http_error():
    class FakeSession:
        def get(self, url, **kwargs):
            raise ConnectionError("network down")

    lookup = openprices.make_lookup(session=FakeSession())
    assert lookup("eggs") is None


def test_make_lookup_returns_none_on_empty_result():
    class FakeResponse:
        def json(self):
            return {"items": [], "total": 0}

    class FakeSession:
        def get(self, url, **kwargs):
            return FakeResponse()

    lookup = openprices.make_lookup(session=FakeSession())
    assert lookup("eggs") is None


def test_make_lookup_returns_none_on_malformed_json():
    class FakeResponse:
        def json(self):
            raise ValueError("not json")

    class FakeSession:
        def get(self, url, **kwargs):
            return FakeResponse()

    lookup = openprices.make_lookup(session=FakeSession())
    assert lookup("eggs") is None
