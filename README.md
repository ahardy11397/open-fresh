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
docker compose exec llm ollama pull gemma3n:e4b
curl -s localhost:4269/settings
# {"household_size": 2, "meals_per_week": 5, "preferred_days": "mon,tue,wed,thu,fri,sat,sun"}
```

Data lives in `./data/openfresh.db` on the host (mounted at `/data` in the
container), so kitchens survive `docker compose down` and upgrades. The
service listens on port 4269; a healthcheck polls `GET /settings`.
Compose also runs an internal `llm` sidecar service (`ollama/ollama:latest`
with `gemma3n:e4b`) on the private network (no host ports exposed) for
unstructured recipe extraction fallback. Pull the model once after starting
the containers: `docker compose exec llm ollama pull gemma3n:e4b`.

## Quickstart (CLI)

The `openfresh` CLI ships with the backend package and talks to the server
over HTTP (`OPENFRESH_URL`, default `http://localhost:4269`):

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
  recipes, pricing, openprices, listgen, planner, budget, API, CLI.
- `backend/tests/` — pytest suite (131 tests across 13 test files).
- `docs/superpowers/specs/2026-10-15-open-fresh-design.md` — the design
  spec this implementation follows. Read it before changing behavior.
- `docs/superpowers/plans/2026-10-15-core-backend-cli.md` — completed
  implementation plan for the core backend and CLI.

## CLI Reference

| Command | Description |
| --- | --- |
| `openfresh add-recipe <url> [--title <title>] [--text <raw_text>]` | Ingest a recipe from a webpage, video URL, or raw text |
| `openfresh review-queue` | List recipes flagged with `needs_review=true` needing manual review |
| `openfresh recipes` | List all recipes in the cookbook |
| `openfresh plan [week_start]` | Show the meal plan for a week (defaults to current Monday) |
| `openfresh plan-add <recipe_id> <date>` | Add a recipe to the plan on `YYYY-MM-DD` |
| `openfresh plan-cook <entry_id>` | Mark a planned meal as cooked (consumes ingredients from inventory) |
| `openfresh plan-remove <entry_id>` | Remove a planned meal entry |
| `openfresh autoplan` | Auto-populate the current week's meal plan |
| `openfresh list [week_start]` | Generate the priced grocery list (`plan needs − inventory`) |
| `openfresh inventory` | List all pantry, fridge, and freezer inventory |
| `openfresh inv-add <name> <location> <qty> [unit]` | Add stock to `pantry`, `fridge`, or `freezer` |
| `openfresh inv-adjust <inventory_id> <delta>` | Adjust an inventory item's quantity (`+` or `-`, clamped at `0`) |
| `openfresh inv-remove <inventory_id>` | Remove an inventory item |
| `openfresh budget <week_start> [target]` | Show (or set the target for) a week's budget |
| `openfresh spend <week_start>` | Show a week's budget and spend summary |
| `openfresh set <key> <value>` | Update a setting (`household_size`, `meals_per_week`, `preferred_days`) |
| `openfresh show <key>` | Print a setting value |

## HTTP API Reference

- **Items**: `GET /items`, `POST /items`, `PATCH /items/{item_id}`, `POST /items/alias`
- **Inventory**: `GET /inventory`, `POST /inventory`, `PATCH /inventory/{inventory_id}`, `DELETE /inventory/{inventory_id}`
- **Recipes**: `GET /recipes[?needs_review=true|false]`, `POST /recipes`, `POST /recipes/ingest`, `GET /recipes/{recipe_id}`, `PATCH /recipes/{recipe_id}`, `POST /recipes/{recipe_id}/reingest`, `POST /recipes/{recipe_id}/ingredients`, `DELETE /recipes/{recipe_id}`
- **Plan**: `GET /plan`, `POST /plan`, `DELETE /plan/{entry_id}`, `POST /plan/{entry_id}/cooked`, `POST /plan/auto-populate`
- **Grocery List**: `GET /list`
- **Pricing**: `POST /prices/own`, `POST /prices/estimate`, `GET /prices/resolve?name=...` (supports bulk `package_quantity` & `package_unit` with culinary unit conversion, item categories, and default Open Prices lookup)
- **Budget**: `GET /budget/{week_start}`, `PUT /budget/{week_start}`, `POST /budget/{week_start}/spend`
- **Settings**: `GET /settings`, `PUT /settings`

## Recipe Ingest Pipeline (Phase 2)

- **Deterministic-first**: Webpages with `schema.org/Recipe` JSON-LD are parsed directly in-process without calling the LLM.
- **Video transcript extraction**: Social and video URLs (YouTube, TikTok, Instagram, etc.) use `yt-dlp` to download subtitles and transcripts before structured extraction.
- **Internal LLM sidecar**: Docker Compose runs an internal `llm` service (`ollama/ollama:latest` with `gemma3n:e4b`) accessible only inside the Compose network at `http://llm:11434/v1` (no host ports exposed). Pull the model using `docker compose exec llm ollama pull gemma3n:e4b`.
- **Never fails loudly**: Any network, format, or LLM error degrades gracefully into a stored recipe with `needs_review = True` and a descriptive `review_notes` message.
- **Review & correction**: Review flagged recipes with `openfresh review-queue` (or `GET /recipes?needs_review=true`), re-parse pasted text via `POST /recipes/{id}/reingest`, or adjust fields and ingredients with `PATCH /recipes/{id}`.

## Project Status

- [x] **Core Backend & CLI**: SQLite state layer (WAL), canonical items & aliases, source-tagged inventory, cookbook, layered pricing (own library, Open Prices client, category estimates), grocery list generator, deterministic auto-planner with chooser hook, weekly budget tracking, FastAPI HTTP server, thin CLI client, Docker Compose packaging.
- [x] **Recipe Ingest Pipeline**: Webpage (`schema.org/Recipe` + local LLM fallback), video transcript (`yt-dlp` + local LLM), review queue, reingest, and partial recipe patch. (Receipt photo scanning deferred to separate phase).
- [ ] **Laya Decision Model**: In-process ONNX Runtime integration into the planner's `chooser` hook.
- [ ] **React Frontend**: Mobile- and desktop-friendly web interface for Planner, Grocery List, Calendar, Cookbook, Kitchen Inventory, Budget, and Settings.

## Development

```sh
cd backend
pip install -e . --group dev   # or: pip install -e . pytest
pytest
```
