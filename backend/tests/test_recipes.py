"""Tests for cookbook recipes with normalized ingredients (task 4)."""

from openfresh import db, items, recipes


def _fresh_conn(tmp_path):
    conn = db.get_conn(str(tmp_path / "kitchen.db"))
    db.init_db(conn)
    return conn


def test_create_and_get_with_ingredients(tmp_path):
    conn = _fresh_conn(tmp_path)
    recipe_id = recipes.create_recipe(
        conn, "  Veggie   Stir-Fry  ", servings=3, source_url="https://example.com/sf"
    )
    ing1 = recipes.add_ingredient(conn, recipe_id, "  Garlic   clove ", 2.0, unit="cloves")
    ing2 = recipes.add_ingredient(conn, recipe_id, "Soy Sauce", 1.5, unit="tbsp")

    recipe = recipes.get_recipe(conn, recipe_id)
    assert recipe["id"] == recipe_id
    assert recipe["title"] == "Veggie Stir-Fry"
    assert recipe["servings"] == 3
    assert recipe["source_url"] == "https://example.com/sf"
    assert recipe["needs_review"] is False

    ingredients = recipe["ingredients"]
    assert len(ingredients) == 2
    assert [i["id"] for i in ingredients] == [ing1, ing2]
    by_raw = {i["raw"]: i for i in ingredients}
    garlic = by_raw["Garlic clove"]
    soy = by_raw["Soy Sauce"]
    # item ids attached and raw text normalized through the canonical item table
    assert garlic["item_id"] == items.get_or_create_with_alias(conn, "Garlic clove")
    assert garlic["item_name"] == "garlic clove"
    assert garlic["quantity"] == 2.0
    assert garlic["unit"] == "cloves"
    assert soy["item_id"] == items.get_or_create_with_alias(conn, "soy sauce")
    assert soy["item_name"] == "soy sauce"
    assert soy["quantity"] == 1.5


def test_staple_flag_persists(tmp_path):
    conn = _fresh_conn(tmp_path)
    recipe_id = recipes.create_recipe(conn, "Pantry Rice")
    recipes.add_ingredient(conn, recipe_id, "Rice", 1.0, unit="cup")
    recipes.add_ingredient(conn, recipe_id, "Salt", 0.5, unit="tsp", staple=True)

    recipe = recipes.get_recipe(conn, recipe_id)
    staples = {i["raw"]: i["staple"] for i in recipe["ingredients"]}
    assert staples == {"Rice": False, "Salt": True}


def test_delete_cascades_ingredients(tmp_path):
    conn = _fresh_conn(tmp_path)
    recipe_id = recipes.create_recipe(conn, "Temp Dish")
    recipes.add_ingredient(conn, recipe_id, "Onion", 1.0)
    assert conn.execute("SELECT COUNT(*) FROM recipe_ingredients").fetchone()[0] == 1

    recipes.delete_recipe(conn, recipe_id)

    assert conn.execute("SELECT COUNT(*) FROM recipes").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM recipe_ingredients").fetchone()[0] == 0
    assert recipes.get_recipe(conn, recipe_id) is None
    assert recipes.list_recipes(conn) == []


def test_create_defaults_and_listing(tmp_path):
    conn = _fresh_conn(tmp_path)
    first = recipes.create_recipe(conn, "Defaults Recipe")
    recipes.create_recipe(conn, "Zesty Soup")

    recipe = recipes.get_recipe(conn, first)
    assert recipe["servings"] == 2
    assert recipe["source_url"] is None
    assert recipe["ingredients"] == []

    titles = [r["title"] for r in recipes.list_recipes(conn)]
    assert titles == ["Defaults Recipe", "Zesty Soup"]
    listed = recipes.list_recipes(conn)
    assert listed[0]["id"] == first
    assert listed[0]["servings"] == 2
