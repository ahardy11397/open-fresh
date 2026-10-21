# Graph Report - open-fresh  (2026-10-20)

## Corpus Check
- Corpus is ~18,513 words - fits in a single context window. You may not need a graph.

## Summary
- 424 nodes · 1076 edges · 13 communities (11 shown, 2 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 10 edges (avg confidence: 0.89)
- Token cost: 5,800 input · 1,850 output

## Community Hubs (Navigation)
- Thin HTTP CLI Client
- Grocery List & Layered Pricing
- FastAPI Request Schemas
- Canonical Items & Cookbook Recipes
- Weekly Meal Planner & Consumption
- FastAPI Route Handlers
- Kitchen Inventory & Event Log
- HTTP API Integration Tests
- SQLite Database & Settings
- Weekly Budget & Spend Tracking
- Auto-Populate & Laya Hook
- Recipe & Receipt Ingest Spec
- Docker Compose Service

## God Nodes (most connected - your core abstractions)
1. `build_router()` - 34 edges
2. `main()` - 30 edges
3. `get_or_create()` - 28 edges
4. `create_recipe()` - 27 edges
5. `add_ingredient()` - 27 edges
6. `_client()` - 27 edges
7. `generate_list()` - 26 edges
8. `_ok()` - 23 edges
9. `add_item()` - 22 edges
10. `get_conn()` - 19 edges

## Surprising Connections (you probably didn't know these)
- `Docker Compose openfresh Service` --conceptually_related_to--> `build_router()`  [INFERRED]
  docker-compose.yml → backend/openfresh/api.py
- `OpenFresh HTTP API Reference` --conceptually_related_to--> `build_router()`  [INFERRED]
  README.md → backend/openfresh/api.py
- `OpenFresh CLI Reference` --conceptually_related_to--> `main()`  [INFERRED]
  README.md → backend/openfresh/cli.py
- `Core Backend + CLI Implementation Plan` --references--> `week_summary()`  [EXTRACTED]
  docs/superpowers/plans/2026-10-15-core-backend-cli.md → backend/openfresh/budget.py
- `Core Backend + CLI Implementation Plan` --references--> `init_db()`  [EXTRACTED]
  docs/superpowers/plans/2026-10-15-core-backend-cli.md → backend/openfresh/db.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Live Kitchen State Correlation (Plan, Inventory, Grocery List, and Budget)** — idea_kitchen_model, docs_superpowers_specs_2026_10_15_open_fresh_design_inventory_management, docs_superpowers_specs_2026_10_15_open_fresh_design_layered_pricing, backend_openfresh_listgen_generate_list, backend_openfresh_budget_week_summary, backend_openfresh_planner_auto_populate [EXTRACTED 1.00]
- **Core Backend, Thin HTTP CLI, and Docker Compose Deployment Architecture** — docker_compose_openfresh_service, readme_http_api_reference, readme_cli_reference, docs_superpowers_plans_2026_10_15_core_backend_cli_plan, backend_openfresh_api_build_router, backend_openfresh_cli_main [EXTRACTED 1.00]

## Communities (13 total, 2 thin omitted)

### Community 0 - "Thin HTTP CLI Client"
Cohesion: 0.10
Nodes (34): build_parser(), _current_monday(), main(), _print_response(), _run(), _week_params(), _canned(), _client() (+26 more)

### Community 1 - "Grocery List & Layered Pricing"
Cohesion: 0.11
Nodes (27): generate_list(), _week_entries(), add_ingredient(), create_recipe(), delete_recipe(), get_recipe(), list_recipes(), _fresh_conn() (+19 more)

### Community 2 - "FastAPI Request Schemas"
Cohesion: 0.06
Nodes (24): AliasCreate, AutoPopulateBody, BudgetPut, EstimateCreate, IngredientCreate, InventoryCreate, InventoryPatch, ItemCreate (+16 more)

### Community 3 - "Canonical Items & Cookbook Recipes"
Cohesion: 0.08
Nodes (24): get_or_create(), get_or_create_with_alias(), list_items(), _normalize(), rename_alias(), convert(), _estimate(), _own_price() (+16 more)

### Community 4 - "Weekly Meal Planner & Consumption"
Cohesion: 0.14
Nodes (26): add_entry(), get_week(), list_entries(), mark_cooked(), _recipe_estimate(), remove_entry(), _round_robin_pick(), _scaled_ingredients() (+18 more)

### Community 5 - "FastAPI Route Handlers"
Cohesion: 0.08
Nodes (17): build_router(), current_week_start(), delete_inventory(), delete_plan(), delete_recipe(), get_list(), get_plan(), ok() (+9 more)

### Community 6 - "Kitchen Inventory & Event Log"
Cohesion: 0.15
Nodes (18): add_item(), adjust(), consume(), get_all(), get_quantity(), _log_event(), _now(), remove_item() (+10 more)

### Community 7 - "HTTP API Integration Tests"
Cohesion: 0.08
Nodes (7): create_app(), client(), _make_recipe(), test_cooked_endpoint_consumes(), test_delete_planned_recipe_returns_409(), test_list_lines_carry_currency(), test_recipe_to_plan_to_list_roundtrip()

### Community 8 - "SQLite Database & Settings"
Cohesion: 0.15
Nodes (13): get_conn(), init_db(), get_household_size(), get_positive_int(), get_setting(), set_setting(), test_foreign_keys_enforced(), test_get_conn_pragmas() (+5 more)

### Community 9 - "Weekly Budget & Spend Tracking"
Cohesion: 0.17
Nodes (15): record_spend(), set_budget(), _spend_in_window(), week_summary(), _fresh_conn(), _plan_one_priced(), test_actual_from_spend_rows(), test_actual_sums_only_matching_currency() (+7 more)

### Community 10 - "Auto-Populate & Laya Hook"
Cohesion: 0.22
Nodes (17): auto_populate(), _fresh_conn(), _item_id(), _planned_rows(), _recipe(), test_budget_pressure_defers_expensive_recipe(), test_chooser_hook_overrides_round_robin(), test_fills_up_to_meals_per_week() (+9 more)

## Knowledge Gaps
- **8 isolated node(s):** `openfresh`, `Open-Fresh Self-Hosted Meal Prep Concept`, `Kitchen Domain Model (Pantry, Fridge, Freezer, Range, Cookbook)`, `OpenFresh CLI Reference`, `OpenFresh HTTP API Reference` (+3 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 158 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `build_router()` connect `FastAPI Route Handlers` to `FastAPI Request Schemas`, `HTTP API Integration Tests`?**
  _High betweenness centrality (0.146) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `build_router()` (e.g. with `Docker Compose openfresh Service` and `OpenFresh HTTP API Reference`) actually correct?**
  _`build_router()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `openfresh`, `Open-Fresh Self-Hosted Meal Prep Concept`, `Kitchen Domain Model (Pantry, Fridge, Freezer, Range, Cookbook)` to the rest of the system?**
  _8 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Thin HTTP CLI Client` be split into smaller, more focused modules?**
  _Cohesion score 0.10062893081761007 - nodes in this community are weakly interconnected._
- **Why does `make_lookup()` connect `FastAPI Request Schemas` to `Canonical Items & Cookbook Recipes`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Should `Grocery List & Layered Pricing` be split into smaller, more focused modules?**
  _Cohesion score 0.10522496371552975 - nodes in this community are weakly interconnected._
- **Why does `generate_list()` connect `Grocery List & Layered Pricing` to `Canonical Items & Cookbook Recipes`, `Weekly Meal Planner & Consumption`, `Kitchen Inventory & Event Log`, `Weekly Budget & Spend Tracking`, `Auto-Populate & Laya Hook`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._