"""Thin CLI client over the openfresh HTTP API.

Every subcommand is a single HTTP request against ``OPENFRESH_URL``
(default ``http://localhost:4269``); no business logic and no database
access live here. Exit code 0 on success, 1 on HTTP error with the
response body printed to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from typing import Any

import httpx

DEFAULT_URL = "http://localhost:4269"


def _current_monday() -> str:
    today = date.today()
    return (today - timedelta(days=today.weekday())).isoformat()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openfresh",
        description="openfresh CLI (thin client over the HTTP API)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("add-recipe", help="ingest a recipe from a URL")
    sp.add_argument("url")
    sp.add_argument("--title", default=None, help="Recipe title override")
    sp.add_argument("--text", default=None, help="Raw recipe text or caption")

    sub.add_parser("review-queue", help="list recipes that need manual review")

    sub.add_parser("recipes", help="list recipes")

    sp = sub.add_parser("plan", help="show the plan for a week")
    sp.add_argument("week_start", nargs="?", default=None)

    sp = sub.add_parser("plan-add", help="add a recipe to the plan")
    sp.add_argument("recipe_id", type=int)
    sp.add_argument("date")

    sp = sub.add_parser("plan-cook", help="mark a plan entry as cooked")
    sp.add_argument("entry_id", type=int)

    sp = sub.add_parser("plan-remove", help="remove a plan entry")
    sp.add_argument("entry_id", type=int)

    sub.add_parser("autoplan", help="auto-populate the current week's plan")

    sp = sub.add_parser("list", help="generate the grocery list for a week")
    sp.add_argument("week_start", nargs="?", default=None)

    sub.add_parser("inventory", help="list inventory")

    sp = sub.add_parser("inv-add", help="add an item to inventory")
    sp.add_argument("name")
    sp.add_argument("location")
    sp.add_argument("quantity", type=float)
    sp.add_argument("unit", nargs="?", default="")

    sp = sub.add_parser("inv-adjust", help="adjust an inventory quantity")
    sp.add_argument("inventory_id", type=int)
    sp.add_argument("delta", type=float)

    sp = sub.add_parser("inv-remove", help="remove an inventory entry")
    sp.add_argument("inventory_id", type=int)

    sp = sub.add_parser("budget", help="show (or set the target of) a week's budget")
    sp.add_argument("week_start")
    sp.add_argument("target", nargs="?", type=float, default=None)

    sp = sub.add_parser("spend", help="show a week's spend")
    sp.add_argument("week_start")

    sp = sub.add_parser("set", help="set a setting")
    sp.add_argument("key")
    sp.add_argument("value")

    sp = sub.add_parser("show", help="show a setting value")
    sp.add_argument("key")

    return parser


def _week_params(week_start: str | None) -> dict[str, str] | None:
    """Query params for /plan and /list; omit the key entirely when unset."""
    return {"week_start": week_start} if week_start else None


def _print_response(resp: httpx.Response) -> None:
    try:
        data = resp.json()
    except ValueError:
        print(resp.text)
        return
    print(json.dumps(data, indent=2))


def _run(client: httpx.Client, args: argparse.Namespace) -> None:
    """Dispatch one HTTP request for the parsed subcommand."""
    cmd = args.command
    if cmd == "add-recipe":
        payload: dict[str, Any] = {"url": args.url}
        if getattr(args, "title", None):
            payload["title"] = args.title
        if getattr(args, "text", None):
            payload["raw_text"] = args.text
        resp = client.post("/recipes/ingest", json=payload)
        resp.raise_for_status()
        r = resp.json()
        flag = " (needs review)" if r.get("needs_review") else ""
        print(f"Added recipe #{r['id']}: {r['title']}{flag}")
        return
    elif cmd == "review-queue":
        resp = client.get("/recipes", params={"needs_review": "true"})
        resp.raise_for_status()
        recipes_list = resp.json()
        if not recipes_list:
            print("No recipes need review.")
        else:
            for r in recipes_list:
                notes = f" — {r['review_notes']}" if r.get("review_notes") else ""
                print(f"#{r['id']}: {r['title']}{notes}")
        return
    elif cmd == "recipes":
        resp = client.get("/recipes")
    elif cmd == "plan":
        resp = client.get("/plan", params=_week_params(args.week_start))
    elif cmd == "plan-add":
        resp = client.post(
            "/plan", json={"recipe_id": args.recipe_id, "date": args.date}
        )
    elif cmd == "plan-cook":
        resp = client.post(f"/plan/{args.entry_id}/cooked")
    elif cmd == "plan-remove":
        resp = client.delete(f"/plan/{args.entry_id}")
    elif cmd == "autoplan":
        resp = client.post("/plan/auto-populate", json={"week_start": _current_monday()})
    elif cmd == "list":
        resp = client.get("/list", params=_week_params(args.week_start))
    elif cmd == "inventory":
        resp = client.get("/inventory")
    elif cmd == "inv-add":
        resp = client.post(
            "/inventory",
            json={
                "name": args.name,
                "location": args.location,
                "quantity": args.quantity,
                "unit": args.unit,
            },
        )
    elif cmd == "inv-adjust":
        resp = client.patch(
            f"/inventory/{args.inventory_id}", json={"delta": args.delta}
        )
    elif cmd == "inv-remove":
        resp = client.delete(f"/inventory/{args.inventory_id}")
    elif cmd == "budget":
        if args.target is None:
            resp = client.get(f"/budget/{args.week_start}")
        else:
            resp = client.put(f"/budget/{args.week_start}", json={"target": args.target})
    elif cmd == "spend":
        resp = client.get(f"/budget/{args.week_start}")
    elif cmd == "set":
        resp = client.put("/settings", json={"key": args.key, "value": args.value})
    elif cmd == "show":
        resp = client.get("/settings")
        resp.raise_for_status()
        print(resp.json().get(args.key, ""))
        return
    else:  # pragma: no cover - argparse restricts choices
        raise AssertionError(f"unhandled command {cmd!r}")
    resp.raise_for_status()
    _print_response(resp)


def main(
    argv: list[str] | None = None,
    client: httpx.Client | None = None,
    transport: httpx.BaseTransport | None = None,
) -> int:
    """Run the CLI; returns the process exit code (0 ok, 1 on HTTP error)."""
    args = build_parser().parse_args(argv)
    owns_client = client is None
    if client is None:
        base_url = os.environ.get("OPENFRESH_URL", DEFAULT_URL)
        client = httpx.Client(base_url=base_url, timeout=10.0, transport=transport)
    try:
        _run(client, args)
    except httpx.HTTPStatusError as exc:
        print(exc.response.text, file=sys.stderr)
        return 1
    except httpx.HTTPError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        if owns_client:
            client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
