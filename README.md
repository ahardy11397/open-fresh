# openfresh

Self-hosted meal planner. Not a recipe carousel — a kitchen.

## The kitchen metaphor

An openfresh instance is a kitchen, never a sequential wizard. It's yours:
one instance per household, shared by everyone in it — one pantry, one
list, one budget. Not multi-tenant. Prices resolve per kitchen, and the
things that think for you (recipe import, price suggestions) run outside
the container as services, so the core stays small and private.

- The **plan** is the week's menu: what you intend to cook, day by day.
- The **pantry** (fridge/freezer inventory) is what you already have.
- The **list** is what the plan needs minus what the kitchen already has.
- The **budget** is what the week cost against what you expected to spend.

The backend keeps state in a single SQLite file; the CLI is a thin client
over the HTTP API, so anything that can talk HTTP can talk to your kitchen.

## Quickstart (Compose)

```sh
docker compose up -d
curl -s localhost:8000/settings
# {"household_size": 2, "meals_per_week": 5, "preferred_days": "mon,tue,wed,thu,fri,sat,sun"}
```

Data lives in `./data/openfresh.db` on the host (mounted at `/data` in the
container), so kitchens survive `docker compose down` and upgrades. The
service listens on port 8000; a healthcheck polls `GET /settings`.

## Quickstart (CLI)

The `openfresh` CLI ships with the backend package and talks to the server
over HTTP (`OPENFRESH_URL`, default `http://localhost:8000`):

```sh
pip install ./backend

# add a recipe, plan the week, shop, cook
openfresh add-recipe https://example.com/chili
openfresh autoplan
openfresh list
openfresh inv-add rice pantry 2 kg
openfresh budget 2026-10-19 80
openfresh plan-cook <entry-id>
```

Without a running server, the CLI is just a remote — start Compose first
(or run `uvicorn openfresh.app_factory:create_app --factory` yourself).

## Layout

- `backend/openfresh/` — the core: db, settings, items, inventory,
  recipes, pricing, listgen, planner, budget, API, CLI.
- `backend/tests/` — pytest suite.
- `docs/superpowers/specs/2026-10-15-open-fresh-design.md` — the design
  spec this implementation follows. Read it before changing behavior.

## Development

```sh
cd backend
pip install -e . --group dev   # or: pip install -e . pytest
pytest
```
