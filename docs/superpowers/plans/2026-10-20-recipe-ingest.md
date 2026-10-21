# Open-fresh Phase 2 — Recipe Ingest Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the deterministic-first recipe ingest pipeline (`schema.org/Recipe` JSON-LD + ingredient line parser + video transcript extractor + internal local LLM sidecar fallback) with a review queue and never-fail graceful degradation across the database, FastAPI server, CLI, and Docker Compose setup.

**Architecture:** `backend/openfresh/ingest.py` classifies inputs (video URL, webpage URL, or raw text), extracts structured data deterministically when `schema.org/Recipe` JSON-LD is present, and falls back to an internal Ollama sidecar (`http://llm:11434/v1`, model `gemma3n:e4b`) for unstructured webpages and video transcripts (`yt-dlp`). Every failure path degrades gracefully into a stored recipe in SQLite with `needs_review = 1` and `review_notes`.

**Tech Stack:** Python 3.12+, FastAPI, sqlite3 (stdlib), httpx, yt-dlp (optional/injectable runtime extractor), pytest, Docker Compose (`ollama/ollama:latest` internal sidecar).

**Spec:** `docs/superpowers/specs/2026-10-20-recipe-ingest-design.md`

## Global Constraints

- Extraction must never fail loudly and vanish: any network error, blocked video platform, unreachable LLM, or incomplete parse must still store a recipe row with `needs_review = True` and descriptive `review_notes`.
- Webpage ingest checks `<script type="application/ld+json">` for `schema.org/Recipe` first; when title, $\ge 1$ ingredient, and $\ge 1$ step are present, it completes deterministically without calling the LLM.
- Cleaned ingredient names normalize through `items.get_or_create_with_alias(conn, name)` while `recipe_ingredients.raw` preserves the original ingredient line text.
- Default staples (`salt`, `kosher salt`, `sea salt`, `pepper`, `black pepper`, `water`, `olive oil`, `vegetable oil`, `cooking oil`) are auto-flagged with `staple = True`.
- The LLM service in `docker-compose.yml` must NOT publish `ports:` to the host; it is reachable only on the internal Compose network at `OPENFRESH_LLM_URL` (default `http://llm:11434/v1`) with `OPENFRESH_LLM_MODEL` (default `gemma3n:e4b`).
- All unit and API tests must run offline using injected HTTP/LLM/yt-dlp fakes.

## Review Focus

1. **Malformed or non-Recipe JSON-LD blocks on webpages** — pages with invalid JSON inside `<script type="application/ld+json">` or only `Organization`/`BreadcrumbList` blocks must not raise `JSONDecodeError`; they must skip bad blocks and fall through cleanly to the LLM or `needs_review` fallback. Pinned by `test_malformed_and_non_recipe_jsonld_falls_back` (Task 3).
2. **Unicode fractions and prep notes in ingredient strings** — lines like `"1 ½ cups whole milk"` or `"2 cloves garlic, finely minced"` must parse to `quantity=1.5, unit="cup", name="whole milk"` and `quantity=2.0, unit="clove", name="garlic"` while keeping full `raw`. Pinned by `test_parse_ingredient_line_fractions_and_prep_notes` (Task 2).
3. **LLM returning markdown-fenced JSON or missing fields** — small models (`gemma3n:e4b`) frequently wrap JSON in ```` ```json ... ``` ```` fences or omit fields; `extract_with_llm` must strip fences and validate safely without raising. Pinned by `test_extract_with_llm_strips_fences_and_handles_partial` (Task 4).
4. **Re-ingesting or patching a planned recipe** — updating ingredients on a recipe that is already on the weekly plan (`update_recipe` / `POST /recipes/{id}/reingest` / `PATCH /recipes/{id}`) must update `recipes` in place and replace `recipe_ingredients` without violating the `plan_entries.recipe_id` foreign key. Pinned by `test_reingest_and_patch_planned_recipe_preserves_plan_fk` (Task 5).
5. **Empty ingest request body** — `POST /recipes/ingest` with both `url=None` and `raw_text=None` (or whitespace-only) must return HTTP `422`. Pinned by `test_ingest_empty_body_returns_422` (Task 5).

---

### Task 1: Schema migration and cookbook recipe fields (`steps`, `total_time`, `review_notes`, `update_recipe`)

**Files:**
- Modify: `backend/openfresh/db.py`
- Modify: `backend/openfresh/recipes.py`
- Test: `backend/tests/test_recipes.py`

**Interfaces:**
- Consumes: `db.get_conn`, `db.init_db`, `items.get_or_create_with_alias`
- Produces:
  - Schema columns on `recipes`: `steps TEXT NOT NULL DEFAULT '[]'`, `total_time TEXT`, `review_notes TEXT` (in `_SCHEMA_STATEMENTS` and `_MIGRATIONS`).
  - `recipes.create_recipe(conn, title: str, servings: int = 2, source_url: str | None = None, *, steps: list[str] | None = None, total_time: str | None = None, needs_review: bool = False, review_notes: str | None = None) -> int`
  - `recipes.add_ingredient(conn, recipe_id: int, raw: str, quantity: float | None, unit: str = "", staple: bool = False, *, item_name: str | None = None) -> int` — normalizes `item_name or raw` through `items.get_or_create_with_alias`.
  - `recipes.update_recipe(conn, recipe_id: int, *, title: str | None = None, servings: int | None = None, steps: list[str] | None = None, total_time: str | None = ..., needs_review: bool | None = None, review_notes: str | None = ..., ingredients: list[dict] | None = None) -> dict | None` — updates specified fields in place; when `ingredients` is provided, deletes existing `recipe_ingredients` for `recipe_id` and inserts the new list; returns `get_recipe(conn, recipe_id)`.
  - `recipes.list_recipes(conn, needs_review: bool | None = None) -> list[dict]` — returns recipes with `steps` decoded as `list[str]`, `total_time`, `needs_review` as `bool`, and `review_notes`; filters by `needs_review` when not `None`.

- [x] **Step 1: Write failing tests in `backend/tests/test_recipes.py`**
  - `test_create_recipe_with_steps_time_and_review`: creates a recipe with `steps=["Boil water", "Simmer"]`, `total_time="25m"`, `needs_review=True`, `review_notes="check quantities"`, asserts `get_recipe` and `list_recipes(conn, needs_review=True)` return those exact values and `list_recipes(conn, needs_review=False)` returns `[]`.
  - `test_add_ingredient_uses_cleaned_item_name`: calls `recipes.add_ingredient(conn, rid, "2 cloves garlic, minced", 2.0, "clove", item_name="garlic")` and asserts `ing["raw"] == "2 cloves garlic, minced"` while `ing["item_name"] == "garlic"`.
  - `test_update_recipe_replaces_fields_and_ingredients`: calls `recipes.update_recipe(conn, rid, title="Fixed Title", needs_review=False, review_notes=None, steps=["Step 1"], ingredients=[{"raw": "1 cup rice", "name": "rice", "quantity": 1.0, "unit": "cup", "staple": False}])` and asserts the updated recipe reflects the new values and replaced ingredients.
- [x] **Step 2: Run `pytest backend/tests/test_recipes.py -v` — verify FAIL**
- [x] **Step 3: Implement schema and cookbook updates in `backend/openfresh/db.py` and `backend/openfresh/recipes.py`**
- [x] **Step 4: Run `pytest backend/tests/test_recipes.py -v` — verify PASS**
- [x] **Step 5: Commit** — `git add backend/openfresh/db.py backend/openfresh/recipes.py backend/tests/test_recipes.py && git commit -m "feat: add steps, total_time, review_notes, and update_recipe to cookbook"`

---

### Task 2: Deterministic ingredient line parser and ISO-8601 duration formatter

**Files:**
- Create: `backend/openfresh/ingest.py`
- Create: `backend/tests/test_ingest.py`

**Interfaces:**
- Produces:
  - `ingest.parse_ingredient_line(raw: str) -> dict` — returns `{"raw": str, "name": str, "quantity": float | None, "unit": str, "staple": bool}`. Parses leading integers, decimals, ASCII fractions (`1/2`), mixed fractions (`1 1/2`), and Unicode fractions (`½`, `¼`, `¾`, `⅓`, `⅔`, `⅛`, `⅜`, `⅝`, `⅞`); maps unit aliases (`cups`->`cup`, `tablespoons`/`tbsp.`->`tbsp`, `teaspoons`/`tsp.`->`tsp`, `ounces`->`oz`, `pounds`/`lbs`->`lb`, `grams`->`g`, `kilograms`->`kg`, `cloves`->`clove`, `cans`->`can`, `bunches`->`bunch`); strips leading `"of "` and trailing comma prep notes (`", finely chopped"`) from `name`; sets `staple=True` when `name` is in `{"salt", "kosher salt", "sea salt", "pepper", "black pepper", "water", "olive oil", "vegetable oil", "cooking oil"}`.
  - `ingest.parse_iso_duration(value: str | None) -> str | None` — converts ISO-8601 durations like `"PT45M"` -> `"45m"`, `"PT1H30M"` -> `"1h 30m"`, `"PT2H"` -> `"2h"`, or passes through non-ISO human strings like `"30 mins"`.

- [x] **Step 1: Write failing tests in `backend/tests/test_ingest.py`**
  - `test_parse_ingredient_line_fractions_and_prep_notes`:
    - `parse_ingredient_line("1 ½ cups whole milk")` -> `{"raw": "1 ½ cups whole milk", "name": "whole milk", "quantity": 1.5, "unit": "cup", "staple": False}`
    - `parse_ingredient_line("2 cloves garlic, finely minced")` -> `{"raw": "2 cloves garlic, finely minced", "name": "garlic", "quantity": 2.0, "unit": "clove", "staple": False}`
    - `parse_ingredient_line("1/2 tsp kosher salt")` -> `{"raw": "1/2 tsp kosher salt", "name": "kosher salt", "quantity": 0.5, "unit": "tsp", "staple": True}`
    - `parse_ingredient_line("1 glug of olive oil")` -> `{"raw": "1 glug of olive oil", "name": "olive oil", "quantity": None, "unit": "", "staple": True}`
  - `test_parse_iso_duration`: asserts `"PT45M"` -> `"45m"`, `"PT1H15M"` -> `"1h 15m"`, `"PT2H"` -> `"2h"`, `None` -> `None`.
- [x] **Step 2: Run `pytest backend/tests/test_ingest.py -v` — verify FAIL**
- [x] **Step 3: Implement `parse_ingredient_line` and `parse_iso_duration` in `backend/openfresh/ingest.py`**
- [x] **Step 4: Run `pytest backend/tests/test_ingest.py -v` — verify PASS**
- [x] **Step 5: Commit** — `git add backend/openfresh/ingest.py backend/tests/test_ingest.py && git commit -m "feat: deterministic ingredient line parser and ISO duration formatter"`

---

### Task 3: Webpage `schema.org/Recipe` JSON-LD extractor and HTML text cleaner

**Files:**
- Modify: `backend/openfresh/ingest.py`
- Modify: `backend/tests/test_ingest.py`

**Interfaces:**
- Consumes: `ingest.parse_ingredient_line`, `ingest.parse_iso_duration`
- Produces:
  - `ingest.extract_schema_org_recipe(html: str) -> dict | None` — scans `<script type="application/ld+json">` tags, traverses top-level dicts, lists, and `@graph` arrays for `@type` matching `"Recipe"` (string or list containing `"Recipe"`). Returns `{"title": str, "servings": int, "total_time": str | None, "ingredients": list[dict], "steps": list[str], "needs_review": bool, "review_notes": str | None}` when found, or `None` if no Recipe JSON-LD node exists.
  - `ingest.extract_html_text_and_title(html: str) -> tuple[str, str | None]` — strips `<script>` and `<style>` blocks and HTML tags to clean plain text, and returns `(clean_text, page_title)`.

- [x] **Step 1: Write failing tests in `backend/tests/test_ingest.py`**
  - `test_extract_schema_org_recipe_complete`: HTML containing a `@graph` with a `Recipe` node (`name="Chili"`, `recipeYield="4 servings"`, `totalTime="PT1H15M"`, `recipeIngredient=["500 g ground beef", "1 tsp salt"]`, `recipeInstructions=[{"@type": "HowToStep", "text": "Brown beef."}, {"@type": "HowToStep", "text": "Simmer."}]`) returns `servings=4`, `total_time="1h 15m"`, 2 parsed ingredients (with salt marked `staple=True`), 2 steps, `needs_review=False`.
  - `test_malformed_and_non_recipe_jsonld_falls_back`: HTML with one broken JSON script tag and one `@type: "WebSite"` script tag returns `None` without raising.
  - `test_extract_html_text_and_title`: strips `<script>`/`<style>` and extracts `<title>`.
- [x] **Step 2: Run `pytest backend/tests/test_ingest.py -v` — verify FAIL**
- [x] **Step 3: Implement `extract_schema_org_recipe` and `extract_html_text_and_title` in `backend/openfresh/ingest.py`**
- [x] **Step 4: Run `pytest backend/tests/test_ingest.py -v` — verify PASS**
- [x] **Step 5: Commit** — `git add backend/openfresh/ingest.py backend/tests/test_ingest.py && git commit -m "feat: schema.org/Recipe JSON-LD extractor and HTML text cleaner"`

---

### Task 4: Local LLM extractor, video transcript (`yt-dlp`) extractor, and end-to-end `ingest_recipe` orchestrator

**Files:**
- Modify: `backend/openfresh/ingest.py`
- Modify: `backend/tests/test_ingest.py`
- Modify: `backend/pyproject.toml` (add `yt-dlp` to dependencies)

**Interfaces:**
- Consumes: Tasks 1–3 (`recipes.create_recipe`, `recipes.add_ingredient`, `recipes.update_recipe`, `recipes.get_recipe`)
- Produces:
  - `ingest.is_video_url(url: str) -> bool`
  - `ingest.extract_video_text(url: str, ytdlp_runner=None) -> tuple[str | None, str | None, str | None]` — returns `(combined_text, video_title, error_note)`. Uses `yt_dlp.YoutubeDL` when `ytdlp_runner is None` (catching `ImportError` and any `Exception` so it never raises).
  - `ingest.extract_with_llm(text: str, fallback_title: str = "Untitled Recipe", llm_client: httpx.Client | None = None) -> dict` — calls `POST {OPENFRESH_LLM_URL}/chat/completions` (`model=OPENFRESH_LLM_MODEL`), strips markdown code fences if present, normalizes ingredients via `parse_ingredient_line`, and flags `needs_review=True` if LLM fails or returns incomplete data.
  - `ingest.ingest_recipe(conn: sqlite3.Connection, *, url: str | None = None, raw_text: str | None = None, title: str | None = None, http_client: httpx.Client | None = None, llm_client: httpx.Client | None = None, ytdlp_runner=None) -> dict` — orchestrates video/webpage/raw_text extraction, persists the recipe and ingredients in SQLite, and returns `recipes.get_recipe(conn, recipe_id)`.
  - `ingest.reingest_recipe(conn: sqlite3.Connection, recipe_id: int, raw_text: str, *, llm_client: httpx.Client | None = None) -> dict | None` — extracts from `raw_text` and updates `recipe_id` via `recipes.update_recipe`.

- [x] **Step 1: Write failing tests in `backend/tests/test_ingest.py`**
  - `test_extract_with_llm_strips_fences_and_handles_partial`: fake `llm_client` returning ```` ```json\n{"title": "Garlic Pasta", "servings": 3, "total_time": "20m", "ingredients": [{"raw": "200 g pasta", "name": "pasta", "quantity": 200, "unit": "g", "staple": false}], "steps": ["Boil pasta."], "low_confidence": false}\n``` ```` parses cleanly with `needs_review=False`.
  - `test_webpage_ingest_uses_jsonld_without_calling_llm`: fake `http_client` serves HTML with `schema.org/Recipe`; `llm_client` raises `AssertionError("should not be called")`; `ingest_recipe` stores the recipe with `needs_review=False`.
  - `test_webpage_ingest_falls_back_to_llm_when_no_jsonld`: fake `http_client` serves plain HTML without JSON-LD; fake `llm_client` returns structured JSON; `ingest_recipe` stores the LLM-extracted recipe.
  - `test_video_url_ingest_extracts_transcript_and_calls_llm`: URL `https://www.youtube.com/watch?v=abc` routes to `ytdlp_runner`, combines title/description/subtitles, calls `llm_client`, and stores the complete recipe with `needs_review=False`.
  - `test_never_fail_when_video_and_llm_both_fail`: `ytdlp_runner` raises `RuntimeError("Instagram login required")`; `ingest_recipe` still creates a recipe in SQLite with `needs_review=True`, `source_url` preserved, and `review_notes` mentioning the transcript failure.
- [x] **Step 2: Run `pytest backend/tests/test_ingest.py -v` — verify FAIL**
- [x] **Step 3: Implement `is_video_url`, `extract_video_text`, `extract_with_llm`, `ingest_recipe`, and `reingest_recipe` in `backend/openfresh/ingest.py`**
- [x] **Step 4: Run `pytest backend/tests/test_ingest.py -v` — verify PASS**
- [x] **Step 5: Commit** — `git add backend/openfresh/ingest.py backend/tests/test_ingest.py backend/pyproject.toml && git commit -m "feat: video transcript, LLM fallback, and never-fail ingest orchestrator"`

---

### Task 5: FastAPI endpoints (`POST /recipes/ingest`, `POST /recipes/{id}/reingest`, `PATCH /recipes/{id}`, `GET /recipes?needs_review=`), CLI (`add-recipe`, `review-queue`), and Docker Compose internal LLM sidecar

**Files:**
- Modify: `backend/openfresh/api.py`
- Modify: `backend/openfresh/cli.py`
- Modify: `docker-compose.yml`
- Modify: `README.md`
- Test: `backend/tests/test_api.py`, `backend/tests/test_cli.py`

**Interfaces:**
- Consumes: Tasks 1–4
- Produces:
  - `POST /recipes/ingest` (`RecipeIngestBody`: `url: str | None = None`, `raw_text: str | None = None`, `title: str | None = None`) -> returns full recipe dict (`200`), or `422` when both `url` and `raw_text` are empty.
  - `POST /recipes/{recipe_id}/reingest` (`RecipeReingestBody`: `raw_text: str`) -> returns updated recipe dict (`200`), or `404` if recipe missing.
  - `PATCH /recipes/{recipe_id}` (`RecipePatch`: optional `title`, `servings`, `steps`, `total_time`, `needs_review`, `review_notes`, `ingredients`) -> returns updated recipe dict (`200`), or `404` if recipe missing.
  - `GET /recipes?needs_review=` -> optional `bool` query filter.
  - CLI: `openfresh add-recipe <url> [--text <raw_text>]` posts to `/recipes/ingest`; `openfresh review-queue` gets `/recipes?needs_review=true`.
  - `docker-compose.yml`: internal `llm` service (`ollama/ollama:latest`, `./data/ollama:/root/.ollama`, no `ports:` published) and `OPENFRESH_LLM_URL: http://llm:11434/v1`, `OPENFRESH_LLM_MODEL: gemma3n:e4b` on `openfresh`.

- [x] **Step 1: Write failing tests in `backend/tests/test_api.py` and `backend/tests/test_cli.py`**
  - `test_ingest_empty_body_returns_422` (`test_api.py`): `POST /recipes/ingest` with `{}` or `{"url": "   "}` returns `422`.
  - `test_ingest_and_review_queue_flow` (`test_api.py`): `POST /recipes/ingest` with `raw_text` when LLM is offline lands in `GET /recipes?needs_review=true` with `needs_review=True`; `PATCH /recipes/{id}` with cleaned `steps`, `ingredients`, and `needs_review=False` clears it from `GET /recipes?needs_review=true`.
  - `test_reingest_and_patch_planned_recipe_preserves_plan_fk` (`test_api.py`): plan a stub recipe on `MONDAY`, then call `POST /recipes/{id}/reingest` and `PATCH /recipes/{id}` with new ingredients; verify `200` and that `/list` reflects the updated ingredients.
  - Update `test_add_recipe` and add `test_add_recipe_with_text` + `test_review_queue` in `backend/tests/test_cli.py`.
- [x] **Step 2: Run `pytest backend/tests/test_api.py backend/tests/test_cli.py -v` — verify FAIL**
- [x] **Step 3: Implement routes in `api.py`, commands in `cli.py`, sidecar in `docker-compose.yml`, and docs in `README.md`**
- [x] **Step 4: Run full test suite `pytest -v` — verify all PASS**
- [x] **Step 5: Commit** — `git add backend/openfresh/api.py backend/openfresh/cli.py backend/tests/test_api.py backend/tests/test_cli.py docker-compose.yml README.md && git commit -m "feat: ingest API endpoints, CLI commands, and internal Compose LLM sidecar"`
