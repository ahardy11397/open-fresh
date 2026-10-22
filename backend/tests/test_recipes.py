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


def test_create_recipe_with_steps_time_and_review(tmp_path):
    conn = _fresh_conn(tmp_path)
    rid = recipes.create_recipe(
        conn,
        "Pasta Simple",
        steps=["Boil water", "Simmer"],
        total_time="25m",
        needs_review=True,
        review_notes="check quantities",
    )
    rec = recipes.get_recipe(conn, rid)
    assert rec["title"] == "Pasta Simple"
    assert rec["steps"] == ["Boil water", "Simmer"]
    assert rec["total_time"] == "25m"
    assert rec["needs_review"] is True
    assert rec["review_notes"] == "check quantities"

    flagged = recipes.list_recipes(conn, needs_review=True)
    assert len(flagged) == 1
    assert flagged[0]["id"] == rid
    assert flagged[0]["steps"] == ["Boil water", "Simmer"]
    assert flagged[0]["total_time"] == "25m"
    assert flagged[0]["needs_review"] is True
    assert flagged[0]["review_notes"] == "check quantities"

    unflagged = recipes.list_recipes(conn, needs_review=False)
    assert unflagged == []


def test_add_ingredient_uses_cleaned_item_name(tmp_path):
    conn = _fresh_conn(tmp_path)
    rid = recipes.create_recipe(conn, "Garlic Dish")
    ing_id = recipes.add_ingredient(
        conn, rid, "2 cloves garlic, minced", 2.0, "clove", item_name="garlic"
    )
    rec = recipes.get_recipe(conn, rid)
    assert len(rec["ingredients"]) == 1
    ing = rec["ingredients"][0]
    assert ing["id"] == ing_id
    assert ing["raw"] == "2 cloves garlic, minced"
    assert ing["item_name"] == "garlic"
    assert ing["name"] == "garlic"
    assert ing["quantity"] == 2.0
    assert ing["unit"] == "clove"


def test_update_recipe_replaces_fields_and_ingredients(tmp_path):
    conn = _fresh_conn(tmp_path)
    rid = recipes.create_recipe(
        conn,
        "Draft Title",
        steps=["Draft step"],
        total_time="10m",
        needs_review=True,
        review_notes="initial notes",
    )
    recipes.add_ingredient(conn, rid, "old ingredient", 1.0, "tbsp")

    updated = recipes.update_recipe(
        conn,
        rid,
        title="Fixed Title",
        needs_review=False,
        review_notes=None,
        steps=["Step 1"],
        ingredients=[
            {
                "raw": "1 cup rice",
                "name": "rice",
                "quantity": 1.0,
                "unit": "cup",
                "staple": False,
            }
        ],
    )
    assert updated is not None
    assert updated["id"] == rid
    assert updated["title"] == "Fixed Title"
    assert updated["needs_review"] is False
    assert updated["review_notes"] is None
    assert updated["steps"] == ["Step 1"]
    assert updated["total_time"] == "10m"

    assert len(updated["ingredients"]) == 1
    ing = updated["ingredients"][0]
    assert ing["raw"] == "1 cup rice"
    assert ing["item_name"] == "rice"
    assert ing["quantity"] == 1.0
    assert ing["unit"] == "cup"
    assert ing["staple"] is False

    stored = recipes.get_recipe(conn, rid)
    assert stored == updated


def test_update_recipe_partial_and_clear_total_time(tmp_path):
    conn = _fresh_conn(tmp_path)
    rid = recipes.create_recipe(
        conn,
        "Curry",
        total_time="45m",
        review_notes="tasty",
    )
    # Clear total_time with None, leave review_notes untouched by omitting it
    updated = recipes.update_recipe(conn, rid, total_time=None)
    assert updated is not None
    assert updated["total_time"] is None
    assert updated["review_notes"] == "tasty"

    # Non-existent recipe returns None
    assert recipes.update_recipe(conn, 99999, title="Nope") is None


def test_schema_migration_recipes_columns(tmp_path):
    db_path = str(tmp_path / "legacy.db")
    conn = db.get_conn(db_path)
    # Create legacy recipes table without steps, total_time, review_notes
    conn.execute(
        """CREATE TABLE recipes (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            servings INTEGER NOT NULL DEFAULT 2,
            source_url TEXT,
            needs_review INTEGER NOT NULL DEFAULT 0,
            created_at TEXT
        )"""
    )
    conn.commit()

    # Run init_db which should apply migrations
    db.init_db(conn)

    cols = {row["name"] for row in conn.execute("PRAGMA table_info(recipes)")}
    assert "steps" in cols
    assert "total_time" in cols
    assert "review_notes" in cols

