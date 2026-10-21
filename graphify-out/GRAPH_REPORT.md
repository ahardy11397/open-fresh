# Graph Report - open-fresh  (2026-10-21)

## Corpus Check
- Corpus is ~32,818 words - fits in a single context window. You may not need a graph.

## Summary
- 1034 nodes · 2700 edges · 46 communities (31 shown, 15 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 44 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45

## God Nodes (most connected - your core abstractions)
1. `create_recipe()` - 37 edges
2. `build_router()` - 36 edges
3. `build_router()` - 35 edges
4. `get_or_create()` - 34 edges
5. `add_ingredient()` - 34 edges
6. `get_or_create()` - 34 edges
7. `main()` - 32 edges
8. `_client()` - 30 edges
9. `add_ingredient()` - 30 edges
10. `create_recipe()` - 30 edges

## Surprising Connections (you probably didn't know these)
- `OpenFresh CLI Reference` --conceptually_related_to--> `main()`  [INFERRED]
  README.md → backend/openfresh/cli.py
- `Docker Compose openfresh Service` --conceptually_related_to--> `build_router()`  [INFERRED]
  docker-compose.yml → backend/openfresh/api.py
- `OpenFresh HTTP API Reference` --conceptually_related_to--> `build_router()`  [INFERRED]
  README.md → backend/openfresh/api.py
- `Core Backend + CLI Implementation Plan` --references--> `generate_list()`  [EXTRACTED]
  docs/superpowers/plans/2026-10-15-core-backend-cli.md → backend/openfresh/listgen.py
- `Household Servings Scaling, Coarse Units, and Staple Flags` --rationale_for--> `generate_list()`  [EXTRACTED]
  docs/superpowers/specs/2026-10-15-open-fresh-design.md → backend/openfresh/listgen.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Core Backend, Thin HTTP CLI, and Docker Compose Deployment Architecture** — docker_compose_openfresh_service, readme_http_api_reference, readme_cli_reference, docs_superpowers_plans_2026_10_15_core_backend_cli_plan, backend_openfresh_api_build_router, backend_openfresh_cli_main [EXTRACTED 1.00]
- **Live Kitchen State Correlation (Plan, Inventory, Grocery List, and Budget)** — idea_kitchen_model, docs_superpowers_specs_2026_10_15_open_fresh_design_inventory_management, docs_superpowers_specs_2026_10_15_open_fresh_design_layered_pricing, backend_openfresh_listgen_generate_list, backend_openfresh_budget_week_summary, backend_openfresh_planner_auto_populate [EXTRACTED 1.00]

## Communities (46 total, 15 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (70): build_parser(), _current_monday(), main(), _print_response(), _run(), _week_params(), _canned(), _client() (+62 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (60): get_conn(), init_db(), add_entry(), auto_populate(), get_week(), list_entries(), mark_cooked(), _recipe_estimate() (+52 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (45): record_spend(), set_budget(), _spend_in_window(), week_summary(), generate_list(), _week_entries(), add_ingredient(), create_recipe() (+37 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (46): add_item(), adjust(), consume(), get_all(), get_quantity(), _log_event(), _now(), remove_item() (+38 more)

### Community 4 - "Community 4"
Cohesion: 0.08
Nodes (30): add_item(), adjust(), consume(), get_all(), get_quantity(), _log_event(), _now(), remove_item() (+22 more)

### Community 5 - "Community 5"
Cohesion: 0.11
Nodes (28): get_conn(), init_db(), auto_populate(), get_household_size(), get_positive_int(), get_setting(), set_setting(), _fresh_conn() (+20 more)

### Community 6 - "Community 6"
Cohesion: 0.09
Nodes (32): AliasCreate, AutoPopulateBody, BudgetPut, EstimateCreate, IngredientCreate, InventoryCreate, InventoryPatch, ItemCreate (+24 more)

### Community 7 - "Community 7"
Cohesion: 0.08
Nodes (19): build_router(), current_week_start(), delete_inventory(), delete_plan(), delete_recipe(), get_list(), get_plan(), ok() (+11 more)

### Community 8 - "Community 8"
Cohesion: 0.08
Nodes (16): build_router(), current_week_start(), delete_inventory(), delete_plan(), delete_recipe(), get_list(), get_plan(), ok() (+8 more)

### Community 9 - "Community 9"
Cohesion: 0.21
Nodes (19): generate_list(), add_ingredient(), create_recipe(), _fresh_conn(), _plan(), test_ignores_cooked_entries(), test_ignores_entries_outside_week(), test_lines_carry_currency() (+11 more)

### Community 10 - "Community 10"
Cohesion: 0.18
Nodes (15): record_spend(), set_budget(), _spend_in_window(), week_summary(), _fresh_conn(), _plan_one_priced(), test_actual_from_spend_rows(), test_actual_sums_only_matching_currency() (+7 more)

### Community 11 - "Community 11"
Cohesion: 0.09
Nodes (7): _make_recipe(), test_api_category_and_bulk_pricing_flow(), test_cooked_endpoint_consumes(), test_delete_planned_recipe_returns_409(), test_list_lines_carry_currency(), test_patch_recipe_empty_ingredient_returns_422(), test_recipe_to_plan_to_list_roundtrip()

### Community 12 - "Community 12"
Cohesion: 0.16
Nodes (14): delete_recipe(), get_recipe(), _hydrate_recipe(), list_recipes(), update_recipe(), _fresh_conn(), test_add_ingredient_uses_cleaned_item_name(), test_create_and_get_with_ingredients() (+6 more)

### Community 13 - "Community 13"
Cohesion: 0.10
Nodes (6): _make_recipe(), test_api_category_and_bulk_pricing_flow(), test_cooked_endpoint_consumes(), test_delete_planned_recipe_returns_409(), test_list_lines_carry_currency(), test_recipe_to_plan_to_list_roundtrip()

### Community 14 - "Community 14"
Cohesion: 0.11
Nodes (8): make_lookup(), test_make_lookup_adds_location_filter(), test_make_lookup_builds_url_with_product_name(), test_make_lookup_parses_response(), test_make_lookup_returns_none_on_empty_result(), test_make_lookup_returns_none_on_http_error(), test_make_lookup_returns_none_on_malformed_json(), test_make_lookup_uses_median_of_newest_10_rows()

### Community 15 - "Community 15"
Cohesion: 0.18
Nodes (13): _clean_step_text(), _clean_subtitle_text(), _collect_steps(), extract_with_llm(), _find_positive_int(), _find_recipe_node(), _is_recipe_type(), parse_iso_duration() (+5 more)

### Community 16 - "Community 16"
Cohesion: 0.14
Nodes (19): extract_schema_org_recipe(), is_video_url(), parse_ingredient_line(), test_extract_schema_org_recipe_complete(), test_extract_schema_org_recipe_direct_and_type_list(), test_extract_schema_org_recipe_howto_sections_and_html_steps(), test_extract_schema_org_recipe_needs_review_flags(), test_extract_with_llm_failure_handling() (+11 more)

### Community 17 - "Community 17"
Cohesion: 0.14
Nodes (12): ingest_recipe(), _fresh_conn(), test_ingest_recipe_raw_text_direct(), test_never_fail_when_video_and_llm_both_fail(), test_reingest_recipe(), test_video_url_ingest_extracts_transcript_and_calls_llm(), test_webpage_incomplete_jsonld_falls_back_to_llm(), test_webpage_incomplete_jsonld_preserves_partial_when_llm_fails() (+4 more)

### Community 18 - "Community 18"
Cohesion: 0.11
Nodes (8): make_lookup(), test_make_lookup_adds_location_filter(), test_make_lookup_builds_url_with_product_name(), test_make_lookup_parses_response(), test_make_lookup_returns_none_on_empty_result(), test_make_lookup_returns_none_on_http_error(), test_make_lookup_returns_none_on_malformed_json(), test_make_lookup_uses_median_of_newest_10_rows()

### Community 19 - "Community 19"
Cohesion: 0.19
Nodes (12): price_item(), set_estimate(), _fresh_conn(), test_all_missing_returns_none(), test_bulk_package_proportional_pricing(), test_category_estimate_resolves_for_categorized_item(), test_falls_back_to_estimate(), test_generic_estimate_fallback_matches_true_generic_rows() (+4 more)

### Community 20 - "Community 20"
Cohesion: 0.20
Nodes (12): get_or_create(), set_estimate(), _fresh_conn(), test_all_missing_returns_none(), test_bulk_package_proportional_pricing(), test_category_estimate_resolves_for_categorized_item(), test_falls_back_to_estimate(), test_generic_estimate_fallback_matches_true_generic_rows() (+4 more)

### Community 21 - "Community 21"
Cohesion: 0.18
Nodes (10): get_or_create_with_alias(), list_items(), _normalize(), rename_alias(), set_category(), _fresh_conn(), test_alias_redirects_after_manual_link(), test_alias_reuse() (+2 more)

### Community 22 - "Community 22"
Cohesion: 0.21
Nodes (8): convert(), convert_quantity(), _estimate(), _norm_unit(), _own_price(), price_item(), PricePer, record_own_price()

### Community 23 - "Community 23"
Cohesion: 0.22
Nodes (6): convert(), _estimate(), _norm_unit(), _own_price(), PricePer, record_own_price()

### Community 24 - "Community 24"
Cohesion: 0.18
Nodes (8): extract_video_text(), test_extract_video_text_avoids_duplicate_captions(), test_extract_video_text_fetches_caption_url(), runner(), test_extract_video_text_json3_captions(), test_extract_video_text_runner_failure(), test_extract_video_text_with_runner(), fake_runner()

### Community 26 - "Community 26"
Cohesion: 0.20
Nodes (5): _extract_subtitle_text(), _get_track_text(), reingest_recipe(), _sort_formats(), _sort_lang_keys()

### Community 27 - "Community 27"
Cohesion: 0.22
Nodes (3): _get_client(), lookup(), _median_price()

### Community 28 - "Community 28"
Cohesion: 0.22
Nodes (4): client(), _no_network_openprices(), client(), _no_network_openprices()

### Community 29 - "Community 29"
Cohesion: 0.29
Nodes (3): _get_client(), lookup(), _median_price()

### Community 31 - "Community 31"
Cohesion: 0.33
Nodes (4): test_extract_with_llm_cleans_ingredient_name_descriptors(), test_extract_with_llm_preamble_and_conversational_text(), test_extract_with_llm_strips_fences_and_handles_partial(), handler()

### Community 33 - "Community 33"
Cohesion: 0.50
Nodes (3): extract_html_text_and_title(), test_extract_html_text_and_title(), test_extract_html_text_preserves_block_newlines()

## Knowledge Gaps
- **10 isolated node(s):** `openfresh`, `Local Recipe & Receipt Ingest Pipeline (Gemma 3n E2B/E4B)`, `Laya System-1 Decision Model (ONNX Runtime)`, `OpenFresh CLI Reference`, `OpenFresh HTTP API Reference` (+5 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 369 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `build_router()` connect `Community 8` to `Community 25`, `Community 6`, `Community 7`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `build_router()` (e.g. with `Docker Compose openfresh Service` and `OpenFresh HTTP API Reference`) actually correct?**
  _`build_router()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `openfresh`, `Local Recipe & Receipt Ingest Pipeline (Gemma 3n E2B/E4B)`, `Laya System-1 Decision Model (ONNX Runtime)` to the rest of the system?**
  _10 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.0602020202020202 - nodes in this community are weakly interconnected._
- **Why does `build_router()` connect `Community 7` to `Community 25`, `Community 6`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.05584192439862543 - nodes in this community are weakly interconnected._
- **Why does `get_conn()` connect `Community 5` to `Community 3`, `Community 9`, `Community 10`, `Community 12`, `Community 17`, `Community 20`, `Community 21`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._