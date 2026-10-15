"""HTTP API tests: FastAPI app over the openfresh core via ASGI transport."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from openfresh.app_factory import create_app

MONDAY = "2026-10-12"


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    app = create_app(db_path=str(tmp_path / "test.db"))
    with TestClient(app) as c:
        yield c


def _make_recipe(client: TestClient, title: str, ingredients: list[dict]) -> int:
    resp = client.post("/recipes", json={"title": title, "servings": 2})
    recipe_id = resp.json()["recipe_id"]
    for ingredient in ingredients:
        resp = client.post(
            f"/recipes/{recipe_id}/ingredients", json=ingredient
        )
        assert resp.status_code == 200, resp.text
    return recipe_id


def test_empty_kitchen_returns_empty(client):
    for path in ("/inventory", "/recipes", "/plan", f"/list?week_start={MONDAY}",
                 f"/budget/{MONDAY}"):
        resp = client.get(path)
        assert resp.status_code == 200, path
        body = resp.json()
        if path.startswith("/budget/"):
            assert body["lines"] == []
            assert body["target"] == 0
        else:
            assert body == [], path


def test_inventory_crud_roundtrip(client):
    # create by name
    resp = client.post(
        "/inventory",
        json={"name": "brown rice", "location": "pantry",
              "quantity": 500, "unit": "g"},
    )
    assert resp.status_code == 200
    inv_id = resp.json()["inventory_id"]
    assert isinstance(inv_id, int)

    rows = client.get("/inventory").json()
    assert len(rows) == 1
    assert rows[0]["item_name"] == "brown rice"
    assert rows[0]["quantity"] == 500

    # adjust by delta
    resp = client.patch(f"/inventory/{inv_id}", json={"delta": -200})
    assert resp.status_code == 200
    assert resp.json()["quantity"] == 300

    # delta clamped at 0
    resp = client.patch(f"/inventory/{inv_id}", json={"delta": -999})
    assert resp.json()["quantity"] == 0

    # delete
    resp = client.delete(f"/inventory/{inv_id}")
    assert resp.status_code == 200
    assert client.get("/inventory").json() == []


def test_recipe_to_plan_to_list_roundtrip(client):
    recipe_id = _make_recipe(
        client,
        "Rice Bowl",
        [{"raw": "rice", "quantity": 200, "unit": "g"},
         {"raw": "tomato", "quantity": 100, "unit": "g"}],
    )
    # two planned entries of the same recipe merge into scaled lines
    resp = client.post("/plan", json={"recipe_id": recipe_id, "date": MONDAY})
    assert resp.status_code == 200
    entry_id = resp.json()["entry_id"]
    client.post("/plan", json={"recipe_id": recipe_id, "date": "2026-10-13"})

    # some rice already in the pantry gets subtracted from the list
    client.post(
        "/inventory",
        json={"name": "rice", "location": "pantry", "quantity": 100, "unit": "g"},
    )

    lines = client.get(f"/list?week_start={MONDAY}").json()
    by_name = {line["name"]: line for line in lines}
    assert set(by_name) == {"rice", "tomato"}
    # 2 entries x 200 g - 100 g in stock
    assert by_name["rice"]["quantity"] == pytest.approx(300)
    assert by_name["rice"]["unit"] == "g"
    # 2 entries x 100 g
    assert by_name["tomato"]["quantity"] == pytest.approx(200)
    for line in lines:
        assert "price_source" in line

    # week view shows both entries
    week = client.get(f"/plan?week_start={MONDAY}").json()
    assert [entry["id"] for entry in week] == sorted(e["id"] for e in week)
    assert len(week) == 2

    # removing one entry drops the merge back to a single serving
    client.delete(f"/plan/{entry_id}")
    lines = client.get(f"/list?week_start={MONDAY}").json()
    by_name = {line["name"]: line for line in lines}
    assert by_name["rice"]["quantity"] == pytest.approx(100)
    assert by_name["tomato"]["quantity"] == pytest.approx(100)

    # recipe detail and deletion (plan entries must go first — FK constraint)
    detail = client.get(f"/recipes/{recipe_id}").json()
    assert detail["title"] == "Rice Bowl"
    assert len(detail["ingredients"]) == 2
    missing = client.get("/recipes/99999")
    assert missing.status_code == 404
    week = client.get(f"/plan?week_start={MONDAY}").json()
    for entry in week:
        client.delete(f"/plan/{entry['id']}")
    resp = client.delete(f"/recipes/{recipe_id}")
    assert resp.status_code == 200
    assert client.get(f"/recipes/{recipe_id}").status_code == 404


def test_cooked_endpoint_consumes(client):
    client.post(
        "/inventory",
        json={"name": "rice", "location": "pantry", "quantity": 500, "unit": "g"},
    )
    recipe_id = _make_recipe(
        client, "Rice Bowl", [{"raw": "rice", "quantity": 200, "unit": "g"}]
    )
    resp = client.post("/plan", json={"recipe_id": recipe_id, "date": MONDAY})
    entry_id = resp.json()["entry_id"]

    resp = client.post(f"/plan/{entry_id}/cooked")
    assert resp.status_code == 200

    rows = client.get("/inventory").json()
    assert rows[0]["quantity"] == pytest.approx(300)

    # idempotent: cooking again consumes nothing more
    client.post(f"/plan/{entry_id}/cooked")
    rows = client.get("/inventory").json()
    assert rows[0]["quantity"] == pytest.approx(300)


def test_settings_roundtrip_endpoint(client):
    resp = client.get("/settings")
    assert resp.status_code == 200
    assert resp.json()["household_size"] == 2

    resp = client.put("/settings", json={"key": "household_size", "value": "4"})
    assert resp.status_code == 200

    body = client.get("/settings").json()
    assert body["household_size"] == 4


def test_422_on_bad_body(client):
    # missing required fields
    resp = client.post("/inventory", json={"location": "pantry"})
    assert resp.status_code == 422
    # wrong type
    resp = client.post("/recipes", json={"title": 42})
    assert resp.status_code == 422
    # no body at all
    resp = client.post("/plan", json=None)
    assert resp.status_code == 422
    # PATCH with a missing delta
    resp = client.patch("/inventory/1", json={})
    assert resp.status_code == 422


def test_delete_planned_recipe_returns_409(client):
    recipe_id = _make_recipe(
        client, "Rice Bowl", [{"raw": "rice", "quantity": 200, "unit": "g"}]
    )
    resp = client.post("/plan", json={"recipe_id": recipe_id, "date": MONDAY})
    assert resp.status_code == 200
    entry_id = resp.json()["entry_id"]

    # deleting a recipe that plan entries still reference is a conflict
    resp = client.delete(f"/recipes/{recipe_id}")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "recipe is planned; remove plan entries first"
    # the recipe itself survives
    assert client.get(f"/recipes/{recipe_id}").status_code == 200

    # after removing the plan entry, deletion succeeds
    resp = client.delete(f"/plan/{entry_id}")
    assert resp.status_code == 200
    resp = client.delete(f"/recipes/{recipe_id}")
    assert resp.status_code == 200
    assert client.get(f"/recipes/{recipe_id}").status_code == 404
