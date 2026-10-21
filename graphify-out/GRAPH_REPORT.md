# Graph Report - open-fresh  (2026-10-20)

## Corpus Check
- Corpus is ~20,392 words - fits in a single context window. You may not need a graph.

## Summary
- 467 nodes · 1190 edges · 21 communities (15 shown, 6 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 12 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

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
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20

## God Nodes (most connected - your core abstractions)
1. `build_router()` - 35 edges
2. `get_or_create()` - 34 edges
3. `main()` - 30 edges
4. `create_recipe()` - 30 edges
5. `add_ingredient()` - 30 edges
6. `generate_list()` - 28 edges
7. `_client()` - 27 edges
8. `add_item()` - 26 edges
9. `_ok()` - 23 edges
10. `add_entry()` - 20 edges

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
- **Core Backend, Thin HTTP CLI, and Docker Compose Deployment Architecture** — docker_compose_openfresh_service, readme_http_api_reference, readme_cli_reference, docs_superpowers_plans_2026_10_15_core_backend_cli_plan, backend_openfresh_api_build_router, backend_openfresh_cli_main [EXTRACTED 1.00]
- **Live Kitchen State Correlation (Plan, Inventory, Grocery List, and Budget)** — idea_kitchen_model, docs_superpowers_specs_2026_10_15_open_fresh_design_inventory_management, docs_superpowers_specs_2026_10_15_open_fresh_design_layered_pricing, backend_openfresh_listgen_generate_list, backend_openfresh_budget_week_summary, backend_openfresh_planner_auto_populate [EXTRACTED 1.00]

## Communities (21 total, 6 thin omitted)

### Community 0 - "Thin HTTP CLI Client"
Cohesion: 0.10
Nodes (29): generate_list(), _week_entries(), add_ingredient(), create_recipe(), delete_recipe(), get_recipe(), list_recipes(), _fresh_conn() (+21 more)

### Community 1 - "Grocery List & Layered Pricing"
Cohesion: 0.10
Nodes (34): build_parser(), _current_monday(), main(), _print_response(), _run(), _week_params(), _canned(), _client() (+26 more)

### Community 2 - "FastAPI Request Schemas"
Cohesion: 0.12
Nodes (28): add_entry(), get_week(), list_entries(), mark_cooked(), _recipe_estimate(), remove_entry(), _round_robin_pick(), _scaled_ingredients() (+20 more)

### Community 3 - "Canonical Items & Cookbook Recipes"
Cohesion: 0.08
Nodes (18): build_router(), current_week_start(), delete_inventory(), delete_plan(), delete_recipe(), get_list(), get_plan(), ok() (+10 more)

### Community 4 - "Weekly Meal Planner & Consumption"
Cohesion: 0.13
Nodes (16): record_spend(), set_budget(), _spend_in_window(), week_summary(), _fresh_conn(), _no_network_openprices(), _plan_one_priced(), test_actual_from_spend_rows() (+8 more)

### Community 5 - "FastAPI Route Handlers"
Cohesion: 0.15
Nodes (18): add_item(), adjust(), consume(), get_all(), get_quantity(), _log_event(), _now(), remove_item() (+10 more)

### Community 6 - "Kitchen Inventory & Event Log"
Cohesion: 0.08
Nodes (8): client(), _make_recipe(), _no_network_openprices(), test_api_category_and_bulk_pricing_flow(), test_cooked_endpoint_consumes(), test_delete_planned_recipe_returns_409(), test_list_lines_carry_currency(), test_recipe_to_plan_to_list_roundtrip()

### Community 7 - "HTTP API Integration Tests"
Cohesion: 0.12
Nodes (15): AliasCreate, AutoPopulateBody, BudgetPut, EstimateCreate, IngredientCreate, InventoryCreate, InventoryPatch, ItemCreate (+7 more)

### Community 8 - "SQLite Database & Settings"
Cohesion: 0.16
Nodes (13): get_conn(), init_db(), get_household_size(), get_positive_int(), get_setting(), set_setting(), test_foreign_keys_enforced(), test_get_conn_pragmas() (+5 more)

### Community 9 - "Weekly Budget & Spend Tracking"
Cohesion: 0.19
Nodes (19): auto_populate(), _fresh_conn(), _item_id(), _planned_rows(), _recipe(), test_auto_populate_does_not_double_count_inventory_across_meals(), test_budget_pressure_defers_expensive_recipe(), test_chooser_hook_overrides_round_robin() (+11 more)

### Community 10 - "Auto-Populate & Laya Hook"
Cohesion: 0.11
Nodes (8): make_lookup(), test_make_lookup_adds_location_filter(), test_make_lookup_builds_url_with_product_name(), test_make_lookup_parses_response(), test_make_lookup_returns_none_on_empty_result(), test_make_lookup_returns_none_on_http_error(), test_make_lookup_returns_none_on_malformed_json(), test_make_lookup_uses_median_of_newest_10_rows()

### Community 11 - "Recipe & Receipt Ingest Spec"
Cohesion: 0.20
Nodes (12): get_or_create(), set_estimate(), _fresh_conn(), test_all_missing_returns_none(), test_bulk_package_proportional_pricing(), test_category_estimate_resolves_for_categorized_item(), test_falls_back_to_estimate(), test_generic_estimate_fallback_matches_true_generic_rows() (+4 more)

### Community 12 - "Docker Compose Service"
Cohesion: 0.18
Nodes (10): get_or_create_with_alias(), list_items(), _normalize(), rename_alias(), set_category(), _fresh_conn(), test_alias_redirects_after_manual_link(), test_alias_reuse() (+2 more)

### Community 13 - "Community 13"
Cohesion: 0.18
Nodes (8): convert(), convert_quantity(), _estimate(), _norm_unit(), _own_price(), price_item(), PricePer, record_own_price()

### Community 14 - "Community 14"
Cohesion: 0.22
Nodes (3): _get_client(), lookup(), _median_price()

## Knowledge Gaps
- **8 isolated node(s):** `openfresh`, `Open-Fresh Self-Hosted Meal Prep Concept`, `Kitchen Domain Model (Pantry, Fridge, Freezer, Range, Cookbook)`, `Docker Compose openfresh Service`, `Laya System-1 Decision Model (ONNX Runtime)` (+3 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 178 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `build_router()` connect `Canonical Items & Cookbook Recipes` to `HTTP API Integration Tests`?**
  _High betweenness centrality (0.137) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `build_router()` (e.g. with `Docker Compose openfresh Service` and `OpenFresh HTTP API Reference`) actually correct?**
  _`build_router()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `openfresh`, `Open-Fresh Self-Hosted Meal Prep Concept`, `Kitchen Domain Model (Pantry, Fridge, Freezer, Range, Cookbook)` to the rest of the system?**
  _8 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Thin HTTP CLI Client` be split into smaller, more focused modules?**
  _Cohesion score 0.1013277428371768 - nodes in this community are weakly interconnected._
- **Why does `make_lookup()` connect `Auto-Populate & Laya Hook` to `Community 13`, `Community 14`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Should `Grocery List & Layered Pricing` be split into smaller, more focused modules?**
  _Cohesion score 0.10377358490566038 - nodes in this community are weakly interconnected._
- **Why does `get_or_create()` connect `Recipe & Receipt Ingest Spec` to `Thin HTTP CLI Client`, `FastAPI Request Schemas`, `Weekly Meal Planner & Consumption`, `FastAPI Route Handlers`, `Weekly Budget & Spend Tracking`, `Docker Compose Service`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._