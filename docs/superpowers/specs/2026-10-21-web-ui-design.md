# Open-fresh Phase 3 — React Web UI Design Spec

**Date:** 2026-10-21
**Parent Spec:** `docs/superpowers/specs/2026-10-15-open-fresh-design.md`
**Phase 2 Spec:** `docs/superpowers/specs/2026-10-20-recipe-ingest-design.md`
**Scope:** Sub-project 3 of 3 — React + Vite + TypeScript single-page application served by the FastAPI backend on port `4269`.

---

## 1. Goal & Scope

Build a responsive, mobile- and desktop-friendly **React + TypeScript** web interface (`frontend/`) that is compiled into static assets and served directly by the `openfresh` FastAPI server at `http://localhost:4269/`.

The Web UI exposes all seven kitchen surfaces defined in the master design spec:
1. **Planner** (weekly meal board, meal count target, auto-populate, mark cooked)
2. **Grocery List** (priced net-needed shopping list, check off to add into Kitchen inventory and optionally log prices/spend)
3. **Calendar** (month and week view of planned and cooked meals across arbitrary date ranges)
4. **Cookbook & Review Queue** (browse recipes, ingest via URL or raw text, inspect/edit/re-ingest recipes flagged with `needs_review`)
5. **Kitchen Inventory** (three tabs: `pantry` / `fridge` / `freezer`, search, quick-add with item category, `+` / `−` quantity steppers)
6. **Budget & Prices** (weekly target vs. estimated list cost vs. actual spend, log spend, manage own prices and category/item estimates)
7. **Settings** (`household_size`, `meals_per_week`, `preferred_days`)

---

## 2. Architecture & Single-Container Packaging

```
+-------------------------------------------------------------------+
| openfresh container (:4269)                                       |
|                                                                   |
|  GET / & /assets/*  ---> FastAPI StaticFiles (/app/static)        |
|                          (Built from frontend/ via Vite + React)  |
|                                                                   |
|  /settings, /recipes, /plan, /list, /inventory, /budget, /prices  |
|                     ---> FastAPI APIRouter (SQLite /data/...)     |
+-------------------------------------------------------------------+
```

1. **Frontend Project Layout (`frontend/`):**
   - `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/index.html`
   - `frontend/src/api/client.ts`: Typed HTTP client wrapping `fetch` against same-origin endpoints (`/settings`, `/recipes`, `/plan`, `/list`, `/inventory`, `/budget`, `/prices`, `/items`, `/spend`).
   - `frontend/src/types.ts`: Shared TypeScript interfaces matching the FastAPI JSON schemas.
   - `frontend/src/App.tsx`: Top-level shell with navigation (sidebar on desktop, bottom bar on mobile), active surface router, global toast/error banner, and shared week-start state.
   - Feature modules under `frontend/src/features/`:
     - `PlannerView.tsx`
     - `GroceryListView.tsx`
     - `CalendarView.tsx`
     - `CookbookView.tsx` (including `RecipeModal.tsx` for editing and re-ingesting)
     - `KitchenView.tsx`
     - `BudgetView.tsx`
     - `SettingsView.tsx`

2. **FastAPI Static Asset Serving (`backend/openfresh/app_factory.py`):**
   - Reads `OPENFRESH_STATIC_DIR` (defaults to `/app/static` if present, else `<repo>/frontend/dist`).
   - If the static directory exists and contains `index.html`, mounts `/assets` via `fastapi.staticfiles.StaticFiles` and serves `index.html` at `GET /`.
   - If the compiled bundle is not present on disk (e.g., during lightweight backend-only `pytest` runs), `GET /` still returns HTTP `200` (`text/html`) with a minimal HTML shell containing `<div id="root">Open-fresh Web UI</div>` so backend route tests never fail when Node build artifacts are absent.

3. **Multi-Stage Docker Build (`backend/Dockerfile` & `docker-compose.yml`):**
   - `docker-compose.yml` sets `build: { context: ., dockerfile: backend/Dockerfile }` on the `openfresh` service.
   - `backend/Dockerfile`:
     - **Stage 1 (`FROM node:22-alpine AS frontend-build`):** copies `frontend/package*.json` and `frontend/`, runs `npm install` and `npm run build`, outputting `/frontend/dist`.
     - **Stage 2 (`FROM python:3.12-slim`):** installs `./backend` and copies `--from=frontend-build /frontend/dist /app/static`, exposing and running `uvicorn` on port `4269`.

---

## 3. Backend API Additions

All existing Phase 1 and Phase 2 routes remain unchanged and backward-compatible. Two small additive enhancements support the Calendar and Grocery List views:

1. **Date-Range Filtering on `GET /plan` (`backend/openfresh/api.py`, `backend/openfresh/planner.py`):**
   - `planner.get_range(conn, start_date: str, end_date: str) -> list[dict]` returns all `plan_entries` with `date >= start_date AND date <= end_date` joined with `recipes.title`, ordered by `date, plan_entries.id`.
   - `GET /plan` accepts optional `start_date: date | None = None` and `end_date: date | None = None` query parameters. When both `start_date` and `end_date` are provided, it returns `planner.get_range(conn, start_date.isoformat(), end_date.isoformat())`; otherwise it preserves existing `week_start` behavior.

---

## 4. Surface-by-Surface Specification

### 4.1 Planner (`PlannerView.tsx`)
- **Header Controls:**
  - Week navigation (`← Prev Week`, `This Week`, `Next Week →`) displaying the Monday ISO date (`YYYY-MM-DD`).
  - Progress badge showing `X / Y meals planned` (where `Y` is `settings.meals_per_week`).
  - **Auto-Populate Week** button (`POST /plan/auto-populate` with `{"week_start": weekStart}`).
- **7-Day Grid (`Mon`–`Sun`):**
  - Lists planned entries for each day (`title`, `slot`, `servings_override`, `cooked` badge).
  - **+ Add Meal** control per day to assign any cookbook recipe (`POST /plan`) with optional slot (`dinner`, `lunch`, `breakfast`) and servings override.
  - **Mark Cooked** button on uncooked entries (`POST /plan/{id}/cooked`), immediately updating the entry to `Cooked` and deducting scaled ingredients from Kitchen inventory.
  - **Remove** button (`DELETE /plan/{id}`).

### 4.2 Grocery List (`GroceryListView.tsx`)
- Fetches `GET /list?week_start=YYYY-MM-DD` and `GET /budget/{week_start}`.
- Displays each needed line item with:
  - Checkbox to mark the item as picked up while shopping.
  - Item `name`, needed `quantity` + `unit`, resolved `price` + `currency`, and a badge for `price_source` (`own`, `openprices`, `estimate`, or `unpriced`).
  - Destination location selector (`pantry` / `fridge` / `freezer`, defaulting to `pantry`) and optional actual price paid input.
- **Complete Shopping (`Add Checked to Kitchen`)** action:
  - For each checked item:
    1. Calls `POST /inventory` (`{ item_id, location, quantity, unit }`) to add the purchased quantity into the chosen kitchen storage location.
    2. If an actual price is entered (or using the line's resolved price when "Log to weekly spend" is checked), records `POST /prices/own` and `POST /spend`.
  - Refreshes the grocery list (which automatically drops the newly stocked items to `0` net need).

### 4.3 Calendar (`CalendarView.tsx`)
- Toggles between **Month View** (full calendar month grid) and **Week View**.
- Fetches `GET /plan?start_date=YYYY-MM-01&end_date=YYYY-MM-31` for the visible month.
- Distinguishes **Cooked** meals (green check badge) from **Planned / Uncooked** meals (amber/blue badge) so household cooking history is visible at a glance.
- Clicking a day or week jumps directly to that week in the Planner or opens a quick add-meal popover.

### 4.4 Cookbook & Review Queue (`CookbookView.tsx`)
- **Ingest Bar:**
  - Input for **Recipe URL** (webpage or video URL: YouTube, TikTok, Instagram, etc.), optional **Title override**, and collapsible **Raw Recipe Text / Caption** textarea.
  - **Import Recipe** button (`POST /recipes/ingest`) with loading state; never fails—if extraction is partial or blocked, opens/highlights the recipe in the **Review Queue**.
- **Filter Tabs:**
  - **All Recipes** (`GET /recipes`)
  - **Review Queue** (`GET /recipes?needs_review=true`) with count badge.
- **Recipe Detail & Edit Modal (`RecipeModal.tsx`):**
  - Displays full recipe (`title`, `servings`, `total_time`, `source_url`, `review_notes` banner if `needs_review` is true, `ingredients` list with `raw` / `item_name` / `quantity` / `unit` / `staple`, and numbered `steps`).
  - **Edit Mode (`PATCH /recipes/{id}`):** Edit title, servings, total time, add/edit/remove ingredients, edit steps, and click **Save & Mark Reviewed** (`needs_review: false, review_notes: null`).
  - **Re-ingest from Text (`POST /recipes/{id}/reingest`):** Paste raw recipe text or video caption to re-run extraction in-place without losing any `plan_entries` references.

### 4.5 Kitchen Inventory (`KitchenView.tsx`)
- **Location Tabs:** `Pantry`, `Fridge`, `Freezer` (filtering `GET /inventory?location=...`).
- **Search & Quick-Add Bar:**
  - Filter items by name.
  - Quick-add form: item name, optional category (`produce`, `dairy`, `meat`, `pantry`, etc.), quantity, unit, and location (`POST /items` if category given + `POST /inventory`).
- **Item Rows:**
  - Shows item name, quantity, unit, and `+` / `−` stepper buttons (`PATCH /inventory/{id}` with `delta: +1` or `-1`) plus a delete button (`DELETE /inventory/{id}`).

### 4.6 Budget & Prices (`BudgetView.tsx`)
- Displays the selected week's budget summary (`GET /budget/{week_start}`):
  - **Weekly Target**, **Estimated List Cost**, **Actual Spend**, and **Remaining Budget** (with progress bar).
- **Set Weekly Budget Form** (`PUT /budget/{week_start}`).
- **Log Spend Form** (`POST /spend`) for ad-hoc grocery receipt totals or line items.
- **Price Library Manager:**
  - Record an item's own price (`POST /prices/own` with optional bulk `package_quantity` & `package_unit`) or set a category/item fallback estimate (`POST /prices/estimate`).

### 4.7 Settings (`SettingsView.tsx`)
- Loads `GET /settings` and saves changes via `PUT /settings`:
  - `household_size` (number input, $\ge 1$)
  - `meals_per_week` (number input, $1\text{–}21$)
  - `preferred_days` (interactive day-of-week pill toggles for `mon,tue,wed,thu,fri,sat,sun`)

---

## 5. Error Handling & Accessibility

- Uses native HTML `<dialog>` elements for modals with proper focus management and light-dismiss support.
- All API errors display non-destructive inline banners with the server's `detail` message.
- Semantic HTML landmarks (`<nav>`, `<main>`, `<section>`, `<header>`), accessible `<label>` associations on all form inputs, and touch-friendly tap targets ($\ge 44\text{px}$ on mobile).

---

## 6. Testing Strategy

1. **Backend Tests (`backend/tests/test_api.py`):**
   - `test_root_serves_web_ui_html`: verifies `GET /` returns `200 OK` with `text/html` content.
   - `test_get_plan_date_range`: verifies `GET /plan?start_date=...&end_date=...` returns planned and cooked entries across a multi-week calendar window.
2. **Frontend Tests (`frontend/src/__tests__/App.test.tsx` via `vitest` + `@testing-library/react` + `jsdom`):**
   - Renders the application shell and switches between Planner, Grocery List, Calendar, Cookbook, Kitchen, Budget, and Settings tabs.
   - Verifies Recipe Ingest (`POST /recipes/ingest`) and Review Queue badge/editing flow (`PATCH /recipes/{id}`).
   - Verifies Planner `Auto-Populate` (`POST /plan/auto-populate`) and `Mark Cooked` (`POST /plan/{id}/cooked`).
   - Verifies Grocery List item checkoff and `Complete Shopping` (`POST /inventory`).
   - Verifies Kitchen Inventory tab switching (`pantry` / `fridge` / `freezer`) and `+` / `−` steppers (`PATCH /inventory/{id}`).
