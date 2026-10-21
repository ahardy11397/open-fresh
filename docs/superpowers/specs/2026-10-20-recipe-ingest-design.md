# Open-fresh Phase 2 — Recipe Ingest Pipeline Design

Design document. Written 2026-10-20 as a sub-project of
`docs/superpowers/specs/2026-10-15-open-fresh-design.md`.

## Intent and Scope

Users add recipes to their household cookbook by pasting a webpage URL, a
social-media/video URL, or raw recipe text. The ingest pipeline extracts a
structured recipe (title, servings, total time, normalized ingredients with
quantities/units/staple flags, and step-by-step instructions) and stores it in
SQLite.

To respect the core anti-goal ("extraction that fails loudly: a recipe that
cannot be fully parsed must still land and be flagged for quick manual cleanup,
never error out and vanish"), every failure path degrades gracefully into a
stored recipe with `needs_review = True` and a human-readable `review_notes`
message.

Receipt photo scanning is deferred to a separate sub-project.

## Architecture: Deterministic-First with Internal LLM Sidecar

1. **URL & Input Router (`backend/openfresh/ingest.py`)**
   - Classifies input as:
     - **Video URL**: matches known video domains (`youtube.com`, `youtu.be`,
       `tiktok.com`, `instagram.com`, `vimeo.com`, `twitch.tv`,
       `facebook.com/reel`, `fb.watch`).
     - **Webpage URL**: any other `http://` or `https://` URL.
     - **Raw Text**: direct recipe text provided with or without a `source_url`.

2. **Webpage Pipeline**
   - Fetches HTML via `httpx` (with a browser-like `User-Agent` and 10s timeout).
   - **Step 1 — `schema.org/Recipe` JSON-LD**: Parses `<script type="application/ld+json">`
     blocks (supporting top-level objects, arrays, and `@graph` wrappers) for
     nodes where `@type` is `"Recipe"` or includes `"Recipe"`.
   - When JSON-LD contains a title, at least one ingredient, and at least one
     instruction step, extraction finishes deterministically in-process without
     calling the LLM:
     - `recipeYield` parses the first integer $\ge 1$ (default `2`).
     - `totalTime` (or `prepTime` + `cookTime`) converts ISO-8601 durations
       (e.g. `PT1H15M` $\rightarrow$ `"1h 15m"`).
     - `recipeInstructions` normalizes plain strings, lists of strings,
       `HowToStep`, and `HowToSection` objects into `list[str]`.
     - `recipeIngredient` strings run through `parse_ingredient_line()`.
   - **Step 2 — Local LLM Fallback**: When JSON-LD is absent or incomplete,
     strips `<script>`/`<style>` tags and HTML markup to plain text, extracts
     the `<title>` tag as a fallback title, and sends the text to the internal
     LLM sidecar.

3. **Video Pipeline (`yt-dlp` + Local LLM)**
   - Uses `yt_dlp.YoutubeDL({"skip_download": True, "writesubtitles": True, "writeautomaticsub": True, "quiet": True})`
     (injectable for offline testing) to extract video metadata (`title`,
     `description`, `subtitles`, `automatic_captions`).
   - Downloads caption text when available, strips WebVTT/JSON3/SRV timestamps
     and duplicate lines, and combines `title + description + transcript`.
   - Sends the combined text to the internal LLM sidecar (`extract_with_llm`).
   - If `yt-dlp` raises an error (e.g. unsupported or blocked social platform)
     or returns no usable text, the recipe still lands in SQLite with
     `needs_review = True` and `review_notes` prompting the user to paste the
     recipe text manually.

4. **Internal LLM Sidecar (`docker-compose.yml` + `ingest.py`)**
   - `docker-compose.yml` runs an internal `llm` service (`ollama/ollama:latest`,
     volume `./data/ollama:/root/.ollama`) on the default Compose network with
     **no `ports:` published to the host**, so it is accessible only to the
     `openfresh` container at `http://llm:11434/v1`.
   - `openfresh` reads `OPENFRESH_LLM_URL` (default `http://llm:11434/v1`) and
     `OPENFRESH_LLM_MODEL` (default `gemma3n:e4b`).
   - `extract_with_llm()` sends a `POST {OPENFRESH_LLM_URL}/chat/completions`
     request with `response_format={"type": "json_object"}` asking for:
     ```json
     {
       "title": "string",
       "servings": 2,
       "total_time": "45m",
       "ingredients": [
         {"raw": "1 1/2 cups whole milk", "name": "whole milk", "quantity": 1.5, "unit": "cup", "staple": false}
       ],
       "steps": ["Step 1...", "Step 2..."],
       "low_confidence": false,
       "review_notes": null
     }
     ```
   - Any network error, timeout, or invalid JSON from the LLM is caught and
     degrades to a partial/stub recipe with `needs_review = True`.

5. **Ingredient Line Parser & Normalization (`parse_ingredient_line`)**
   - Parses raw ingredient lines (both from `schema.org` and from fallback text)
     into `{raw, name, quantity, unit, staple}`:
     - Handles integers, decimals, ASCII fractions (`1/2`), mixed numbers
       (`1 1/2`), and Unicode fractions (`½`, `¼`, `¾`, `⅓`, `⅔`, `⅛`).
     - Normalizes common culinary units (`cup`, `tbsp`, `tsp`, `fl oz`, `pt`,
       `qt`, `gal`, `ml`, `l`, `g`, `kg`, `oz`, `lb`, `clove`, `can`, `bunch`).
     - Strips leading quantity/unit and trailing comma prep notes
       (e.g. `"2 cloves garlic, minced"` $\rightarrow$ canonical item name
       `"garlic"`, while `recipe_ingredients.raw` keeps `"2 cloves garlic, minced"`).
     - Auto-flags default staples (`salt`, `kosher salt`, `sea salt`, `pepper`,
       `black pepper`, `water`, `olive oil`, `vegetable oil`, `cooking oil`).
   - Registers the cleaned `name` via `items.get_or_create_with_alias(conn, name)`
     so recipes, inventory, and pricing share the same canonical item IDs.

## Database Schema & Cookbook API Changes

1. **Schema (`backend/openfresh/db.py`)**
   - `recipes` table gains three columns (both in `CREATE TABLE` and idempotent
     `_MIGRATIONS`):
     - `steps TEXT NOT NULL DEFAULT '[]'` (JSON array of strings)
     - `total_time TEXT` (nullable string)
     - `review_notes TEXT` (nullable string)
   - `recipes.add_ingredient()` accepts an optional `item_name: str | None = None`
     so the canonical item is created from the cleaned ingredient name (`"garlic"`)
     while `raw` stores the full display string (`"2 cloves garlic, minced"`).

2. **Cookbook (`backend/openfresh/recipes.py`)**
   - `create_recipe(conn, title, servings=2, source_url=None, *, steps=None, total_time=None, needs_review=False, review_notes=None) -> int`
   - `update_recipe(conn, recipe_id, *, title=..., servings=..., steps=..., total_time=..., needs_review=..., review_notes=..., ingredients=...) -> dict | None`
   - `list_recipes(conn, needs_review: bool | None = None) -> list[dict]`
   - `get_recipe(conn, recipe_id) -> dict | None` returns `steps` as `list[str]`,
     `total_time`, `needs_review` as `bool`, and `review_notes`.

## HTTP API & CLI Changes

1. **HTTP API (`backend/openfresh/api.py`)**
   - `POST /recipes/ingest`: accepts `{"url": str | None = None, "raw_text": str | None = None, "title": str | None = None}`
     (at least one of `url` or `raw_text` required; `422` otherwise). Runs
     `ingest.ingest_recipe(conn, ...)` and returns the created recipe dict (`200`).
   - `POST /recipes/{recipe_id}/reingest`: accepts `{"raw_text": str}`. Re-runs
     extraction from user-pasted text onto an existing recipe, replacing its
     parsed fields and clearing `needs_review` if extraction succeeds (`404` if
     recipe does not exist).
   - `PATCH /recipes/{recipe_id}`: updates any combination of `title`, `servings`,
     `steps`, `total_time`, `needs_review`, `review_notes`, and `ingredients`
     (`404` if recipe does not exist).
   - `GET /recipes?needs_review=true|false`: filters cookbook list by review state.

2. **CLI (`backend/openfresh/cli.py`)**
   - `openfresh add-recipe <url> [--text <raw_text>]` calls `POST /recipes/ingest`.
   - `openfresh review-queue` calls `GET /recipes?needs_review=true`.

## Testing

All unit and API tests run offline with injected fakes:
- `backend/tests/test_ingest.py`: tests `parse_ingredient_line`, ISO-8601
  duration formatting, `schema.org/Recipe` JSON-LD parsing (direct + `@graph` +
  `HowToStep`), webpage LLM fallback, video `yt-dlp` transcript + LLM extraction,
  and never-fail graceful degradation when `yt-dlp`, HTTP fetch, or the LLM
  endpoint fails.
- `backend/tests/test_api.py` & `backend/tests/test_cli.py`: tests
  `POST /recipes/ingest`, `POST /recipes/{id}/reingest`, `PATCH /recipes/{id}`,
  `GET /recipes?needs_review=true`, and CLI `add-recipe` / `review-queue`.
