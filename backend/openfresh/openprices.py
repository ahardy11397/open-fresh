"""Open Prices lookup factory.

Returns callables that query the Open Prices API for the median price of a
product. The HTTP session is injectable so tests never touch the network.

Global constraint: Open Prices lookups must NEVER raise — any network error
or malformed response resolves to None so the next pricing layer takes over.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable

import httpx

_BASE_URL = "https://prices.openfoodfacts.org/api/v1/prices"
_TIMEOUT_S = 10.0

_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    """Lazily-created shared client with a 10s timeout."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(timeout=_TIMEOUT_S)
    return _client


def _median_price(payload: dict) -> float | None:
    """Median price of the newest 10 rows, or None when there are none."""
    prices = [
        row["price"]
        for row in payload.get("items", [])[:10]
        if isinstance(row, dict) and isinstance(row.get("price"), (int, float))
    ]
    if not prices:
        return None
    return float(statistics.median(prices))


def make_lookup(
    session: httpx.Client | None = None,
    location_ids: list[int] | None = None,
) -> Callable[[str], float | None]:
    """Return a lookup(name) -> float | None callable against Open Prices.

    ``session`` is an injectable httpx.Client (or anything with a compatible
    ``get``) for tests; the default is a module-level client with a 10s
    timeout.
    """

    def lookup(name: str) -> float | None:
        params: dict[str, str] = {"product_name": name}
        if location_ids:
            params["location_id__in"] = ",".join(str(i) for i in location_ids)
        client = session if session is not None else _get_client()
        try:
            response = client.get(_BASE_URL, params=params)
            if getattr(response, "status_code", 200) >= 400:
                return None
            return _median_price(response.json())
        except Exception:
            return None

    return lookup
