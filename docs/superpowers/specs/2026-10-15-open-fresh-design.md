# Open-fresh — self-hosted meal planner, grocery list, and budget

Design document. Written 2026-10-15 from a conversation with the project
owner. Anything marked **[owner]** was decided by them; anything marked
**[builder's call]** is a decision left to whoever builds it, with a
default recorded.

## Intent and why

Open-fresh is a self-hosted, open-source alternative to meal-kit services
like Hello Fresh. The value is not curation or shipping — it is the
planning and list math: give it recipes you already know you like, and it
builds a weekly meal plan, a correlated grocery list, and a budget that
tracks both. The owner tried Grocy and bounced off it because it forced
its own workflow instead of adapting to how they actually shop and
budget. Open-fresh inverts that: it is a utility that adds to the
kitchen, never a sequential wizard.

## Who it serves

**[owner]** A single family home. Each family that wants it spins up its
own instance — one kitchen per instance, shared by the household (one
pantry, one list, one budget). Not multi-tenant. The source will be
released on GitHub, so other families can run it, but there is no
shared/social layer between instances.

## Goals

- Recipe ingest by URL: paste a webpage or video link, extraction runs
  locally, the recipe lands structured in the cookbook.
- Meal planning: user selects meals onto a weekly calendar, or the
  calendar auto-populates from the cookbook. The user controls how many
  meals per week and which days each meal lands on.
- Grocery list generated from what is on the calendar, minus what the
  kitchen already has (pantry/fridge/freezer inventory), merged across
  recipes (duplicate items combine, quantities sum).
- Budget: the user sets a weekly budget; the list is priced line by line
  and the budget correlates with both the calendar and the list. Actual
  spend is recorded against it.
- Inventory tracking: pantry, fridge, and freezer are real stores.
  Cooking a meal consumes from them; shopping refills them; the list only
  ever asks for what is missing.
- Live correlation: the planner, grocery list, and calendar interfaces
  are all views of the same underlying state and are always in sync. The
  user can enter any surface at any time; nothing locks them into a
  step sequence.
- Customizable flow: shopping day and planning day are per-household
  settings, not required steps (owner's own rhythm: plan Sunday, shop
  Monday).

## Non-goals

- Multi-user/multi-tenant hosting, accounts beyond one household.
- Social features, sharing between instances, gamification.
- Order automation / paying for groceries in-app.
- Guaranteed price accuracy from third-party data (see Pricing model).

## Anti-goals (failure even if it technically works)

- Making grocery shopping or meal planning more complicated than doing
  it by hand. If a flow needs a manual to follow, the design failed.
- A wizard or locked sequential flow.
- Extraction that fails loudly: a recipe that cannot be fully parsed
  must still land and be flagged for quick manual cleanup, never error
  out and vanish.

## Constraints

- **[owner]** Stack: React frontend (mobile and desktop friendly),
  Python backend, CLI alongside.
- **[owner]** Recipe extraction runs on local, small models — Gemma-class
  edge models, E2B/E4B size (owner names them "Gemma 4 e2b/e4b"; verify
  the exact model at implementation time — the well-known models at those
  sizes are Gemma 3n E2B/E4B). Extraction must run on a modest GPU or
  CPU; it must not require a datacenter.
- **[owner]** Decision-making model (auto-planning, substitutions,
  merging): a local LLM named "Laya" — verify the exact model before
  implementation.
- **[builder's call, default recorded]** The app talks to models over an
  OpenAI-compatible HTTP endpoint configured by the user (e.g. a
  llama.cpp server on localhost:8080). Models run OUTSIDE the app
  container. This keeps the stack LLM-agnostic and avoids GPU
  passthrough in the container.
- **[owner]** Price data: Open Prices (openfoodfacts/open-prices), used
  as one layer of the pricing model, not the foundation (see below).
- **[owner]** Distribution: Docker Compose. App + frontend + SQLite in a
  bind-mounted volume (one database file per kitchen). The CLI talks to
  the API over HTTP so it works against a container instance with no
  special setup. Running natively under systemd must remain possible for
  owners who prefer it.
- Self-hosted, LAN-first. No cloud dependency except optional open-prices
  lookups and the recipe URLs the user pastes.

## Pricing model [builder's call, layered]

Recon findings (live API checks, 2026-10-15): open-prices holds ~330k
price rows globally, heavily France/Europe. US coverage is thin: 380
stores have any prices at all, only 4 have meaningful depth (>2,000 each,
all Bay Area). Common US grocery barcodes return zero results. The API
itself is good — filterable by `location_id__in`, `product_code__in`,
`category_tag` — and the data is ODbL-licensed.

Therefore prices resolve in this order, per kitchen:

1. **Own price library** (highest priority). Prices the household has
   entered or confirmed — from receipt scanning (below) or manual entry.
   Per kitchen, per item, with a date.
2. **Open Prices nearest match.** Lookup filtered to the household's
   chosen store(s) where possible, else country, else nearest category
   match. Result is labeled with its source.
3. **Category estimate.** Rough per-category defaults. Always flagged as
   an estimate in the UI.

The grocery list shows the source of every price (yours / open-prices /
estimate). The budget sums the priced list; variance lands as actual
spend is recorded.

**Receipt scanning [builder's call, proposed].** After shopping, the user
snaps a photo of the receipt; the local extraction model pulls line-item
names and prices; matched items update the kitchen's price library and
record actual spend against the budget. This is the mechanism that makes
the budget correlation real without manual entry. It uses the same
extraction model/endpoint as recipe ingest.

## Recipe ingest pipeline

1. User pastes a URL (webpage or video, including social media video).
2. Webpage: fetch, look for schema.org/Recipe structured data first;
   fall back to LLM extraction over the page text.
3. Video: get the transcript (yt-dlp for supported sites), run LLM
   extraction over the transcript. Non-YouTube platforms may fail —
   degrade to "paste the recipe manually" prompt, never a dead end.
4. Output: structured recipe (title, servings, ingredients with
   quantity+unit, steps, time, source URL). Confidence-flagged fields are
   marked for review; the recipe is usable immediately and editable.
5. Ingredient normalization: map free-text ingredient strings to
   canonical items (shared item table used by inventory and the price
   library) so cross-recipe merging works.

## Interfaces

Three primary surfaces, all live views of the same state, all mobile and
desktop friendly:

- **Planner**: the week's meals, meal count target, auto-populate
  control, drag/assign meals to days.
- **Grocery list**: priced line items with source labels, grouped
  (produce/dairy/etc. is a builder's call), check off as you shop,
  taps into inventory on completion.
- **Calendar**: month/week view of what is planned and what was cooked;
  history feeds back into what the household actually eats.

Supporting surfaces: **Cookbook** (recipes, add-by-URL, flag-for-review
queue), **Kitchen** (pantry/fridge/freezer inventory with quantities),
**Budget** (weekly target, list estimate, actual spend, trend), and
**Settings** (shopping day, planning day, meals per week, model endpoint,
currency, stores for price lookups).

## CLI

Thin client over the HTTP API: add recipe by URL, show/edit the plan,
generate the list, set budget, manage inventory. Works against a
container instance or native run identically.

## What's left to the builder

- Python web framework choice, project layout, migrations, packaging.
- Exact React setup and component structure.
- SQLite schema (single-file DB per kitchen, WAL mode suggested).
- The extraction prompt engineering and confidence-flagging mechanics.
- Auto-populate planning logic (respect meals/week, day preferences,
  budget pressure, recipe rotation) — the decision-making model's exact
  role vs. deterministic rules is a builder's call; both are allowed.
- Deployment details: Compose file, volume layout, health checks.

## Open questions

Filled after the builder check; see the review round.
