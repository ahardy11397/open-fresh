"""CLI tests: thin httpx client over the HTTP API via a fake transport."""

from __future__ import annotations

import json
from datetime import date, timedelta

import httpx
import pytest

from openfresh import cli

MONDAY = "2026-10-12"


def _canned(body):
    return json.dumps(body)


def _client(calls: list[httpx.Request], responses: list[httpx.Response]):
    """Build an httpx client with a fake transport that records requests and
    replays ``responses`` in order."""

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return responses.pop(0)

    return httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://test"
    )


def _ok(body):
    return httpx.Response(200, content=_canned(body))


# --- add-recipe -------------------------------------------------------------


def test_add_recipe(capsys):
    calls: list[httpx.Request] = []
    client = _client(
        calls,
        [_ok({"id": 1, "title": "chili", "needs_review": False})],
    )
    assert cli.main(["add-recipe", "https://example.com/chili"], client=client) == 0
    (req,) = calls
    assert req.method == "POST"
    assert req.url.path == "/recipes/ingest"
    body = json.loads(req.read())
    assert body == {"url": "https://example.com/chili"}
    assert "Added recipe #1: chili" in capsys.readouterr().out


def test_add_recipe_with_text_and_title(capsys):
    calls: list[httpx.Request] = []
    client = _client(
        calls,
        [_ok({"id": 2, "title": "Chili Con Carne", "needs_review": True})],
    )
    assert (
        cli.main(
            [
                "add-recipe",
                "https://example.com/chili",
                "--title",
                "Chili Con Carne",
                "--text",
                "1 lb beef, 1 can beans",
            ],
            client=client,
        )
        == 0
    )
    (req,) = calls
    assert req.method == "POST"
    assert req.url.path == "/recipes/ingest"
    body = json.loads(req.read())
    assert body == {
        "url": "https://example.com/chili",
        "title": "Chili Con Carne",
        "raw_text": "1 lb beef, 1 can beans",
    }
    assert "Added recipe #2: Chili Con Carne (needs review)" in capsys.readouterr().out


# --- review-queue -----------------------------------------------------------


def test_review_queue_empty(capsys):
    calls: list[httpx.Request] = []
    client = _client(calls, [_ok([])])
    assert cli.main(["review-queue"], client=client) == 0
    (req,) = calls
    assert req.method == "GET"
    assert req.url.path == "/recipes"
    assert req.url.params["needs_review"] == "true"
    assert "No recipes need review." in capsys.readouterr().out


def test_review_queue_with_items(capsys):
    calls: list[httpx.Request] = []
    client = _client(
        calls,
        [
            _ok(
                [
                    {
                        "id": 5,
                        "title": "Grandma's Pie",
                        "review_notes": "Missing oven temperature",
                    },
                    {
                        "id": 6,
                        "title": "Soup",
                        "review_notes": None,
                    },
                ]
            )
        ],
    )
    assert cli.main(["review-queue"], client=client) == 0
    (req,) = calls
    assert req.method == "GET"
    assert req.url.path == "/recipes"
    assert req.url.params["needs_review"] == "true"
    out = capsys.readouterr().out
    assert "#5: Grandma's Pie — Missing oven temperature" in out
    assert "#6: Soup" in out


# --- recipes ----------------------------------------------------------------


def test_recipes():
    calls: list[httpx.Request] = []
    client = _client(calls, [_ok([{"id": 1, "title": "chili"}])])
    assert cli.main(["recipes"], client=client) == 0
    (req,) = calls
    assert req.method == "GET"
    assert req.url.path == "/recipes"


# --- plan -------------------------------------------------------------------


def test_plan_with_week_start():
    calls: list[httpx.Request] = []
    client = _client(calls, [_ok([])])
    assert cli.main(["plan", MONDAY], client=client) == 0
    (req,) = calls
    assert req.method == "GET"
    assert req.url.path == "/plan"
    assert req.url.params["week_start"] == MONDAY


def test_plan_default_no_week_start_param():
    calls: list[httpx.Request] = []
    client = _client(calls, [_ok([])])
    assert cli.main(["plan"], client=client) == 0
    (req,) = calls
    assert req.method == "GET"
    assert req.url.path == "/plan"
    assert "week_start" not in req.url.params


def test_plan_add():
    calls: list[httpx.Request] = []
    client = _client(calls, [_ok({"entry_id": 7})])
    assert cli.main(["plan-add", "3", "2026-10-14"], client=client) == 0
    (req,) = calls
    assert req.method == "POST"
    assert req.url.path == "/plan"
    assert json.loads(req.read()) == {"recipe_id": 3, "date": "2026-10-14"}


def test_plan_cook():
    calls: list[httpx.Request] = []
    client = _client(calls, [_ok({"ok": True})])
    assert cli.main(["plan-cook", "7"], client=client) == 0
    (req,) = calls
    assert req.method == "POST"
    assert req.url.path == "/plan/7/cooked"


def test_plan_remove():
    calls: list[httpx.Request] = []
    client = _client(calls, [_ok({"ok": True})])
    assert cli.main(["plan-remove", "7"], client=client) == 0
    (req,) = calls
    assert req.method == "DELETE"
    assert req.url.path == "/plan/7"


def test_autoplan():
    calls: list[httpx.Request] = []
    client = _client(calls, [_ok({"entry_ids": [1, 2]})])
    assert cli.main(["autoplan"], client=client) == 0
    (req,) = calls
    assert req.method == "POST"
    assert req.url.path == "/plan/auto-populate"
    today = date.today()
    expected_monday = (today - timedelta(days=today.weekday())).isoformat()
    assert json.loads(req.read()) == {"week_start": expected_monday}


# --- list -------------------------------------------------------------------


def test_list():
    calls: list[httpx.Request] = []
    client = _client(calls, [_ok([])])
    assert cli.main(["list", MONDAY], client=client) == 0
    (req,) = calls
    assert req.method == "GET"
    assert req.url.path == "/list"
    assert req.url.params["week_start"] == MONDAY


# --- inventory ----------------------------------------------------------------


def test_inventory():
    calls: list[httpx.Request] = []
    client = _client(calls, [_ok([])])
    assert cli.main(["inventory"], client=client) == 0
    (req,) = calls
    assert req.method == "GET"
    assert req.url.path == "/inventory"


def test_inv_add():
    calls: list[httpx.Request] = []
    client = _client(calls, [_ok({"inventory_id": 5})])
    assert (
        cli.main(["inv-add", "rice", "pantry", "2", "kg"], client=client) == 0
    )
    (req,) = calls
    assert req.method == "POST"
    assert req.url.path == "/inventory"
    assert json.loads(req.read()) == {
        "name": "rice",
        "location": "pantry",
        "quantity": 2.0,
        "unit": "kg",
    }


def test_inv_add_default_unit():
    calls: list[httpx.Request] = []
    client = _client(calls, [_ok({"inventory_id": 6})])
    assert cli.main(["inv-add", "rice", "pantry", "2"], client=client) == 0
    (req,) = calls
    assert json.loads(req.read())["unit"] == ""


def test_inv_adjust():
    calls: list[httpx.Request] = []
    client = _client(calls, [_ok({"quantity": 1.0})])
    assert cli.main(["inv-adjust", "5", "-1"], client=client) == 0
    (req,) = calls
    assert req.method == "PATCH"
    assert req.url.path == "/inventory/5"
    assert json.loads(req.read()) == {"delta": -1.0}


def test_inv_remove():
    calls: list[httpx.Request] = []
    client = _client(calls, [_ok({"ok": True})])
    assert cli.main(["inv-remove", "5"], client=client) == 0
    (req,) = calls
    assert req.method == "DELETE"
    assert req.url.path == "/inventory/5"


# --- budget / spend -----------------------------------------------------------


def test_budget_get():
    calls: list[httpx.Request] = []
    client = _client(calls, [_ok({"target": None, "lines": []})])
    assert cli.main(["budget", MONDAY], client=client) == 0
    (req,) = calls
    assert req.method == "GET"
    assert req.url.path == f"/budget/{MONDAY}"


def test_budget_set_target():
    calls: list[httpx.Request] = []
    client = _client(calls, [_ok({"ok": True})])
    assert cli.main(["budget", MONDAY, "150"], client=client) == 0
    (req,) = calls
    assert req.method == "PUT"
    assert req.url.path == f"/budget/{MONDAY}"
    assert json.loads(req.read()) == {"target": 150.0}


def test_spend():
    calls: list[httpx.Request] = []
    client = _client(calls, [_ok({"target": 150.0, "spent": 12.0})])
    assert cli.main(["spend", MONDAY], client=client) == 0
    (req,) = calls
    assert req.method == "GET"
    assert req.url.path == f"/budget/{MONDAY}"


# --- settings -----------------------------------------------------------------


def test_set():
    calls: list[httpx.Request] = []
    client = _client(calls, [_ok({"ok": True})])
    assert cli.main(["set", "currency", "USD"], client=client) == 0
    (req,) = calls
    assert req.method == "PUT"
    assert req.url.path == "/settings"
    assert json.loads(req.read()) == {"key": "currency", "value": "USD"}


def test_show():
    calls: list[httpx.Request] = []
    client = _client(calls, [_ok({"currency": "USD", "household_size": 2})])
    assert cli.main(["show", "currency"], client=client) == 0
    (req,) = calls
    assert req.method == "GET"
    assert req.url.path == "/settings"
    assert "USD" in json.dumps({"currency": "USD"})


# --- error handling / exit codes -----------------------------------------------


def test_cli_error_exit_code(capsys):
    calls: list[httpx.Request] = []
    client = _client(calls, [httpx.Response(500, text="boom")])
    assert cli.main(["recipes"], client=client) == 1
    assert calls[0].method == "GET"
    captured = capsys.readouterr()
    assert "boom" in captured.err


def test_cli_error_exit_code_post(capsys):
    calls: list[httpx.Request] = []
    client = _client(calls, [httpx.Response(404, text="not found")])
    assert cli.main(["plan-add", "999", "2026-10-14"], client=client) == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err
    assert captured.out == ""


def test_base_url_from_env(monkeypatch):
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return _ok([])

    monkeypatch.setenv("OPENFRESH_URL", "http://example.test:9999")
    exit_code = cli.main(["recipes"], transport=httpx.MockTransport(handler))
    assert exit_code == 0
    (req,) = calls
    assert str(req.url) == "http://example.test:9999/recipes"
