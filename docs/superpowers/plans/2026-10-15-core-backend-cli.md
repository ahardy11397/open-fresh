# Open-fresh Core Backend + CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The open-fresh core — SQLite state layer, inventory, cookbook, planner, grocery list, budget, layered pricing — served over a FastAPI HTTP API with a thin CLI client, runnable in Docker Compose.

**Architecture:** One Python package (`backend/openfresh/`) of small focused modules over a single SQLite file (WAL mode). Planner, list, budget, and inventory are all reads/writes of the same state; no module calls another's UI logic. The grocery list is always derived (`calendar needs − inventory`); cooking consumption and shopping completion are the only automatic inventory writers besides direct manual CRUD. LLMs and Laya are NOT in this plan — the extraction LLM arrives with the ingest plan, Laya with the planning-intelligence plan; the deterministic behaviors stand alone.

**Tech Stack:** Python 3.12+, FastAPI, uvicorn, sqlite3 (stdlib, WAL), httpx (CLI + open-prices client), pytest. Docker Compose for distribution.

**Spec:** `docs/superpowers/specs/2026-10-15-open-fresh-design.md`

## Global Constraints

- Single SQLite file per kitchen, WAL mode, foreign keys ON.
- Price resolution order: own price library > Open Prices > category estimate; every priced line carries its source label (`own` / `openprices` / `estimate`).
- Staples carry a "never list" flag and never appear on the grocery list.
- No expiry tracking, no substitutions anywhere in this plan.
- Servings scale: a planned meal feeds `servings_override` or the household-size setting; ingredient quantities scale by `planned_servings / recipe.servings`.
- Unit handling is coarse: merge/sum only identical (item_id, unit) pairs; inventory subtraction matches on item_id only, floored at 0.
- Cooked check-off consumes ingredients; removing a plan entry never restores inventory; inventory quantities never go below 0.
- Manual inventory add/remove/adjust never touches the budget.
- CLI is a thin HTTP client — no business logic, no direct DB access.
- All money values are (amount: float, currency: str); currency comes from settings (default `USD`).

## Review Focus

1. **Odd units in manually entered recipes** ("1 glug of oil", "2 packets ramen") — list generation and cooking consumption must keep raw text and still produce lines, never raise. Pinned by `test_odd_units_survive_listgen` (Task 6).
2. **Empty kitchen** — fresh DB, no recipes/inventory/plan: every endpoint and listgen call returns empty collections with HTTP 200, never 500. Pinned by `test_empty_kitchen_returns_empty` (Task 10).
3. **Quantity floor** — consuming or adjusting more than on hand clamps inventory at 0 and logs the true delta; no negative quantities anywhere. Pinned by `test_consumption_floors_at_zero` (Task 3) and `test_cooked_consumes_and_floors` (Task 7).
4. **Mixed-unit merge** — same item needed in grams and cups across recipes produces two list lines, not a crash or a bogus sum. Pinned by `test_mixed_units_stay_separate` (Task 6).
5. **Plan removal after cooking** — removing a cooked (or any) entry leaves inventory untouched. Pinned by `test_remove_after_cooked_keeps_inventory` (Task 7).

---

### Task 1: Package scaffold, database, settings

**Files:**
- Create: `backend/openfresh/__init__.py`, `backend/openfresh/db.py`, `backend/openfresh/settings.py`
- Create: `backend/pyproject.toml` (project deps: fastapi, uvicorn, httpx; dev: pytest)
- Test: `backend/tests/test_db.py`, `backend/tests/test_settings.py`

**Interfaces (produces):**
- `db.get_conn(db_path: str) -> sqlite3.Connection` — WAL, foreign_keys ON, row_factory=sqlite3.Row
- `db.init_db(conn)` — creates schema (idempotent): `settings(key TEXT PK, value TEXT)`, `items(id INTEGER PK, name TEXT UNIQUE NOT NULL, created_at TEXT)`, `item_aliases(alias TEXT PK, item_id INTEGER NOT NULL REFERENCES items(id))`, `inventory(id INTEGER PK, item_id INTEGER NOT NULL REFERENCES items(id), location TEXT NOT NULL CHECK(location IN ('pantry','fridge','freezer')), quantity REAL NOT NULL, unit TEXT NOT NULL DEFAULT '', updated_at TEXT, UNIQUE(item_id, location))`, `inventory_events(id INTEGER PK, item_id INTEGER NOT NULL, location TEXT, delta REAL NOT NULL, source TEXT NOT NULL, note TEXT, created_at TEXT)`, `recipes(id INTEGER PK, title TEXT NOT NULL, servings INTEGER NOT NULL DEFAULT 2, source_url TEXT, needs_review INTEGER NOT NULL DEFAULT 0, created_at TEXT)`, `recipe_ingredients(id INTEGER PK, recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE, item_id INTEGER REFERENCES items(id), raw TEXT NOT NULL, quantity REAL, unit TEXT DEFAULT '', staple INTEGER NOT NULL DEFAULT 0)`, `plan_entries(id INTEGER PK, recipe_id INTEGER NOT NULL REFERENCES recipes(id), date TEXT NOT NULL, slot TEXT, servings_override INTEGER, cooked INTEGER NOT NULL DEFAULT 0, created_at TEXT)`, `prices_own(id INTEGER PK, item_id INTEGER NOT NULL REFERENCES items(id), price REAL NOT NULL, currency TEXT NOT NULL, date TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'manual')`, `price_estimates(id INTEGER PK, item_id INTEGER, category TEXT, price REAL NOT NULL, currency TEXT NOT NULL)`, `budgets(week_start TEXT PK, target REAL NOT NULL, currency TEXT NOT NULL)`, `spend(id INTEGER PK, item_id INTEGER, price REAL NOT NULL, currency TEXT NOT NULL, date TEXT NOT NULL, source TEXT NOT NULL)`
- `settings.get_setting(conn, key: str, default=None) -> str|None`
- `settings.set_setting(conn, key: str, value: str) -> None`
- `settings.get_household_size(conn) -> int` (key `household_size`, default 2)

- [x] **Step 1: Write failing tests** — `test_init_db_idempotent` (init twice on `:memory:` DB raises no error, both schemas present); `test_settings_roundtrip` (set then get returns value; get of unset key returns default).
- [x] **Step 2: Run** `pytest backend/tests/test_db.py backend/tests/test_settings.py -v` — expected FAIL (ModuleNotFoundError).
- [x] **Step 3: Implement** `db.py` (DDL in one list of CREATE TABLE IF NOT EXISTS statements, executed in order) and `settings.py`.
- [x] **Step 4: Run tests** — expected PASS.
- [x] **Step 5: Commit** — `git add backend && git commit -m "feat: db schema and settings"`

### Task 2: Canonical items and normalization

**Files:**
- Create: `backend/openfresh/items.py`
- Test: `backend/tests/test_items.py`

**Interfaces:**
- Consumes: `db.get_conn`, `db.init_db`
- Produces: `items.get_or_create(conn, name: str) -> int` (id; name stored lowercase-stripped); `items.get_or_create_with_alias(conn, raw: str) -> int` — normalize `raw` (strip, lowercase, collapse whitespace); if an exact item name or alias matches, return its id; else create item and register the raw string as an alias; `items.rename_alias(conn, raw: str, item_id: int) -> None`; `items.list_items(conn) -> list[dict]`.

- [x] **Step 1: Write failing tests** — `test_alias_reuse` (get_or_create_with_alias("Tomatoes") then ("tomatoes  ") returns same id, one row in items); `test_free_text_creates_alias` (raw "Roma tomatoes" creates item "roma tomatoes" with alias "Roma tomatoes"); `test_alias_redirects_after_manual_link` (rename_alias("roma tomatoes", tomatoes_id) then get_or_create_with_alias("roma tomatoes") returns tomatoes_id).
- [x] **Step 2: Run** — expected FAIL.
- [x] **Step 3: Implement** in `items.py`.
- [x] **Step 4: Run** — PASS.
- [x] **Step 5: Commit** — `feat: canonical items with alias normalization`

### Task 3: Inventory store with event log

**Files:**
- Create: `backend/openfresh/inventory.py`
- Test: `backend/tests/test_inventory.py`

**Interfaces:**
- Consumes: Task 1 db/settings, Task 2 items
- Produces:
  - `inventory.add_item(conn, item_id: int, location: str, quantity: float, unit: str = "", source: str = "manual", note: str | None = None) -> int` — upserts (adds quantity if the (item, location) row exists), logs event with delta.
  - `inventory.remove_item(conn, inventory_id: int, note: str | None = None) -> None` — deletes row, logs event delta = −stored quantity.
  - `inventory.adjust(conn, inventory_id: int, delta: float, note: str | None = None) -> float` — applies delta floored at 0 (row updated to max(0, q+delta), event logs the actual applied delta), returns new quantity.
  - `inventory.consume(conn, item_id: int, quantity: float, source: str = "cooking", note: str | None = None) -> None` — decrements across that item's locations in order fridge, freezer, pantry, floored at 0, one event per touched row.
  - `inventory.get_all(conn) -> list[dict]` — joined with item name, ordered by item name then location.
  - `inventory.get_quantity(conn, item_id: int) -> float` — total on hand across all locations/units (coarse have/need model).

- [x] **Step 1: Write failing tests** — `test_add_upserts_existing_row`; `test_remove_deletes_and_logs_negative_event`; `test_adjust_floors_at_zero` (add 2 eggs, adjust −5 → quantity 0, event delta −2); `test_consumption_floors_at_zero` (add 4 eggs fridge + 2 pantry, consume 10 → both rows 0, events recorded); `test_get_quantity_sums_locations`.
- [x] **Step 2: Run** — FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** — PASS.
- [x] **Step 5: Commit** — `feat: inventory store with source-tagged event log`

### Task 4: Cookbook (recipes)

**Files:**
- Create: `backend/openfresh/recipes.py`
- Test: `backend/tests/test_recipes.py`

**Interfaces:**
- Consumes: Tasks 1–2
- Produces:
  - `recipes.create_recipe(conn, title: str, servings: int = 2, source_url: str | None = None) -> int`
  - `recipes.add_ingredient(conn, recipe_id: int, raw: str, quantity: float | None, unit: str = "", staple: bool = False) -> int` — normalizes `raw` through `items.get_or_create_with_alias`.
  - `recipes.get_recipe(conn, recipe_id: int) -> dict` (ingredients nested)
  - `recipes.list_recipes(conn) -> list[dict]`
  - `recipes.delete_recipe(conn, recipe_id: int) -> None` (cascade deletes ingredients)

- [x] **Step 1: Write failing tests** — `test_create_and_get_with_ingredients` (2 ingredients round-trip with item ids attached); `test_staple_flag_persists`; `test_delete_cascades_ingredients`.
- [x] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** — PASS.
- [x] **Step 5: Commit** — `feat: cookbook recipes with normalized ingredients`

### Task 5: Layered pricing

**Files:**
- Create: `backend/openfresh/pricing.py`, `backend/openfresh/openprices.py`
- Test: `backend/tests/test_pricing.py`, `backend/tests/test_openprices.py`

**Interfaces:**
- Consumes: Tasks 1–2
- Produces:
  - `pricing.record_own_price(conn, item_id: int, price: float, currency: str, date: str, source: str = "manual") -> None`
  - `pricing.set_estimate(conn, item_id: int | None, category: str | None, price: float, currency: str) -> None`
  - `pricing.price_item(conn, item_id: int, lookup=None) -> tuple[float, str] | None` — resolution: most recent `prices_own` row → `lookup(item_name)` (Open Prices, optional callable; skipped when None) → `price_estimates` → None. Returns `(price, source)` with source in {"own","openprices","estimate"}.
  - `openprices.make_lookup(session=None, location_ids: list[int] | None = None) -> Callable[[str], float | None]` — factory returning a lookup callable; the callable queries `GET https://prices.openfoodfacts.org/api/v1/prices?product_name=<name>` (plus `location_id__in` when set), returns the median price of the newest 10 rows in the response currency, or None on any error/empty result. Session injectable for tests (httpx.Client); default a module-level client with 10s timeout.
  - `pricing.convert(conn, item_id: int, quantity: float, unit: str, price_per: tuple[float, str], currency: str) -> float` — line price: unit-aware only when the unit is empty or matches the price's implied unit (empty); coarse model — otherwise price × quantity (quantity treated as count of the priced unit). Keep simple: `price * quantity`.

- [x] **Step 1: Write failing tests** — `test_own_beats_estimate` (both set → (own price, "own")); `test_falls_back_to_estimate` (no own, lookup returns None → estimate, "estimate"); `test_openprices_lookup_used_when_no_own` (fake lookup callable returning 4.5 → (4.5, "openprices")); `test_all_missing_returns_none`; `test_make_lookup_parses_response` (inject a fake session whose get returns `{"items":[{"price":3.0},{"price":3.4}], "total":2}` → callable returns 3.2); `test_make_lookup_returns_none_on_http_error` (fake session raising → None).
- [x] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** — PASS.
- [x] **Step 5: Commit** — `feat: layered pricing with own library, open-prices, estimates`

### Task 6: Grocery list generation

**Files:**
- Create: `backend/openfresh/listgen.py`
- Test: `backend/tests/test_listgen.py`

**Interfaces:**
- Consumes: Tasks 1–5 (settings.get_household_size, recipes.get_recipe, inventory.get_quantity, pricing.price_item, pricing.convert)
- Produces: `listgen.generate_list(conn, week_start: str, lookup=None) -> list[dict]` — collects ingredients of all uncooked plan entries dated within `[week_start, week_start+7)`, scales each by `entry.servings_override or settings.get_household_size(conn)` ÷ `recipe.servings`, groups by (item_id, unit) summing quantities, subtracts `inventory.get_quantity(item_id)` floored at 0, drops staples and zero-need lines, prices each line via the pricing layer. Line dict: `{item_id, name, quantity, unit, price, price_source}`.

- [x] **Step 1: Write failing tests** — `test_merges_duplicates_sums_same_unit` (2 recipes each needing 1 cup rice → one line quantity 2); `test_mixed_units_stay_separate` (200 g rice + 1 cup rice → two lines); `test_subtracts_inventory` (need 6 eggs, 4 on hand → line quantity 2); `test_staples_never_listed` (salt flagged staple → absent even with no stock); `test_scales_to_household` (household 4, recipe serves 2, need 200 g → line 400 g); `test_servings_override_wins` (override 1 → need 100 g); `test_lines_carry_price_source` (estimate-only → price_source "estimate"); `test_odd_units_survive_listgen` (ingredient raw "1 glug of oil", quantity None → line present with quantity None, no exception).
- [x] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** — PASS.
- [x] **Step 5: Commit** — `feat: grocery list generation from calendar minus inventory`

### Task 7: Planner — plan entries and cooked check-off

**Files:**
- Create: `backend/openfresh/planner.py`
- Test: `backend/tests/test_planner.py`

**Interfaces:**
- Consumes: Tasks 1–6 (recipes.get_recipe for ingredients, inventory.consume)
- Produces:
  - `planner.add_entry(conn, recipe_id: int, date: str, slot: str | None = None, servings_override: int | None = None) -> int`
  - `planner.remove_entry(conn, entry_id: int) -> None` — deletes; never touches inventory.
  - `planner.mark_cooked(conn, entry_id: int) -> None` — sets cooked=1, consumes each non-staple ingredient scaled the same way as listgen (shared helper `planner._scaled_ingredients(conn, entry) -> list[(item_id, raw, quantity, unit, staple)]` — export this; Task 6 may refactor listgen to use it).
  - `planner.get_week(conn, week_start: str) -> list[dict]` (entries with recipe titles, ordered by date)
  - `planner.list_entries(conn, cooked: bool | None = None) -> list[dict]`

- [x] **Step 1: Write failing tests** — `test_mark_cooked_consumes_scaled_ingredients` (household 4, recipe serves 2 needing 4 eggs → consume 8); `test_cooked_consumes_and_floors` (only 3 eggs on hand → inventory 0, no error); `test_remove_after_cooked_keeps_inventory` (mark cooked, remove entry → egg inventory unchanged); `test_remove_uncooked_never_touches_inventory`; `test_staples_not_consumed`.
- [x] **Step 2: Run** — FAIL.
- [x] **Step 3: Implement**, extracting the shared scaling helper so listgen and mark_cooked use one code path (refactor Task 6's listgen in the same commit).
- [x] **Step 4: Run all tests** — PASS.
- [x] **Step 5: Commit** — `feat: planner with cooked check-off consumption`

### Task 8: Deterministic auto-populate

**Files:**
- Modify: `backend/openfresh/planner.py`
- Test: `backend/tests/test_autopopulate.py`

**Interfaces:**
- Consumes: Task 7, settings (`meals_per_week`, `planning_day` unused for logic, `shopping_day`), recipes.list_recipes, budgets
- Produces: `planner.auto_populate(conn, week_start: str, chooser=None) -> list[int]` — fills uncooked entries up to `meals_per_week` (setting, default 5) on the household's preferred days (setting `preferred_days`, default "mon,tue,wed,thu,fri,sat,sun" comma list, filling in order), skipping dates already holding an entry, cycling recipes round-robin by least-recently-planned, skipping a recipe whose scaled estimated cost would push the week over budget **only when a budget row exists and is > 0** (estimates allowed otherwise). `chooser(conn, candidates: list[dict], context: dict) -> dict | None` is the future Laya hook: when provided it is consulted first per slot and its pick used; None falls back to round-robin. Returns created entry ids.

- [x] **Step 1: Write failing tests** — `test_fills_up_to_meals_per_week` (3 recipes, default 5 → 5 entries); `test_respects_preferred_days` (preferred "mon,fri" → entries only on those dates); `test_skips_days_already_planned`; `test_round_robin_no_repeat_until_exhausted`; `test_budget_pressure_defers_expensive_recipe` (budget 20, one recipe estimated 25 → other recipes chosen first); `test_no_budget_row_never_skips`; `test_chooser_hook_overrides_round_robin` (fake chooser returning a fixed pick → used).
- [x] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** — PASS.
- [x] **Step 5: Commit** — `feat: deterministic auto-populate with Laya chooser hook`

### Task 9: Budget

**Files:**
- Create: `backend/openfresh/budget.py`
- Test: `backend/tests/test_budget.py`

**Interfaces:**
- Consumes: Tasks 1, 5, 6 (generate_list for estimates)
- Produces:
  - `budget.set_budget(conn, week_start: str, target: float, currency: str = "USD") -> None`
  - `budget.record_spend(conn, item_id: int | None, price: float, currency: str, date: str, source: str = "receipt") -> None`
  - `budget.week_summary(conn, week_start: str, lookup=None) -> dict` — `{week_start, target, currency, estimated, actual, remaining, lines}` where estimated = sum of generate_list prices, actual = sum of spend rows in the window, remaining = target − max(actual, estimated)... (decide: `target − actual` when any spend exists, else `target − estimated`; return both raw numbers in `estimated`/`actual` and let the UI compose — summary keeps `remaining = target − (actual or estimated)`).

- [x] **Step 1: Write failing tests** — `test_summary_estimates_from_list` (one planned recipe → estimated > 0, actual 0); `test_actual_from_spend_rows`; `test_remaining_uses_actual_when_present`; `test_empty_week_zeroes`.
- [x] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** — PASS.
- [x] **Step 5: Commit** — `feat: weekly budget with estimated vs actual`

### Task 10: FastAPI HTTP API

**Files:**
- Create: `backend/openfresh/api.py`, `backend/openfresh/app_factory.py` (wires get_conn per request via dependency, DB path from env `OPENFRESH_DB`, default `./openfresh.db`)
- Test: `backend/tests/test_api.py` (httpx TestClient / ASGI transport against a tmp DB)

**Interfaces:**
- Consumes: Tasks 1–9
- Produces: REST routes, JSON in/out, all returning 200 on success and empty collections on empty state:
  - `GET/POST /items`, `POST /items/alias` {raw, item_id}
  - `GET/POST /inventory`, `POST /inventory` {name|item_id, location, quantity, unit}, `PATCH /inventory/{id}` {delta}, `DELETE /inventory/{id}`
  - `GET/POST /recipes`, `GET /recipes/{id}`, `POST /recipes/{id}/ingredients`, `DELETE /recipes/{id}`
  - `GET /plan?week_start=`, `POST /plan`, `DELETE /plan/{id}`, `POST /plan/{id}/cooked`, `POST /plan/auto-populate`
  - `GET /list?week_start=`
  - `POST /prices/own`, `POST /prices/estimate`, `GET /prices/resolve?name=`
  - `GET/PUT /budget/{week_start}`, `POST /budget/{week_start}/spend`
  - `GET/PUT /settings`
- Pydantic request models for every POST/PATCH body; no raw dict bodies.

- [x] **Step 1: Write failing tests** — `test_empty_kitchen_returns_empty` (GET /inventory, /recipes, /plan, /list, /budget → 200 and empty); `test_inventory_crud_roundtrip`; `test_recipe_to_plan_to_list_roundtrip` (create recipe w/ 2 ingredients → plan → /list shows scaled merged lines with price_source); `test_cooked_endpoint_consumes` (GET /inventory reflects consumption); `test_settings_roundtrip_endpoint`; `test_422_on_bad_body`.
- [x] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run full suite** — PASS.
- [x] **Step 5: Commit** — `feat: FastAPI over the openfresh core`

### Task 11: CLI

**Files:**
- Create: `backend/openfresh/cli.py` (httpx against `OPENFRESH_URL`, default `http://localhost:8000`; argparse subcommands only, no third-party CLI framework)
- Test: `backend/tests/test_cli.py` (fake transport returning canned JSON; asserts correct method/path/payload per command)

**Interfaces:**
- Produces subcommands: `add-recipe URL` (stub in this plan: creates an empty recipe with source_url, real ingest comes with the ingest plan), `recipes`, `plan [week_start]`, `plan-add RECIPE_ID DATE`, `plan-cook ENTRY_ID`, `plan-remove ENTRY_ID`, `autoplan`, `list [week_start]`, `inventory`, `inv-add NAME LOCATION QUANTITY [UNIT]`, `inv-adjust ID DELTA`, `inv-remove ID`, `budget WEEK_START [TARGET]`, `spend WEEK_START`, `set KEY VALUE`, `show KEY`. Exit code 0 on success, 1 on HTTP error with the response body on stderr.

- [x] **Step 1: Write failing tests** — one per subcommand group asserting request path/payload and exit codes; `test_cli_error_exit_code` (500 from server → exit 1, body on stderr).
- [x] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** — PASS.
- [x] **Step 5: Commit** — `feat: thin CLI over the HTTP API`

### Task 12: Docker Compose + README

**Files:**
- Create: `docker-compose.yml`, `backend/Dockerfile`, `README.md`
- Test: manual verification steps below

**Interfaces:**
- Consumes: everything; compose mounts `./data` → `/data`, env `OPENFRESH_DB=/data/openfresh.db`, port 8000:8000.

- [x] **Step 1: Write `backend/Dockerfile`** (python:3.12-slim, install project, uvicorn entrypoint) and `docker-compose.yml` (single service `openfresh`, healthcheck `GET /settings`).
- [x] **Step 2: Verify** — `docker compose up -d && curl -s localhost:8000/settings` returns `{}`; `docker compose down` (this machine needs `sudo docker`, foreground).
- [x] **Step 3: Write README** — quickstart (compose up, CLI pointing at it), the kitchen metaphor, pointer to the spec.
- [x] **Step 4: Commit** — `feat: compose distribution and README`
