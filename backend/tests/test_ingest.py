import json
import httpx
import pytest
from openfresh import db, recipes
from openfresh.ingest import (
    extract_html_text_and_title,
    extract_schema_org_recipe,
    extract_video_text,
    extract_with_llm,
    ingest_recipe,
    is_video_url,
    parse_ingredient_line,
    parse_iso_duration,
    reingest_recipe,
)


def _fresh_conn(tmp_path):
    conn = db.get_conn(str(tmp_path / "kitchen.db"))
    db.init_db(conn)
    return conn


def test_parse_ingredient_line_fractions_and_prep_notes():
    # 1 ½ cups whole milk -> quantity: 1.5, unit: "cup", staple: False
    res = parse_ingredient_line("1 ½ cups whole milk")
    assert res == {
        "raw": "1 ½ cups whole milk",
        "name": "whole milk",
        "quantity": 1.5,
        "unit": "cup",
        "staple": False,
    }

    # 2 cloves garlic, finely minced -> quantity: 2.0, unit: "clove", prep notes stripped
    res = parse_ingredient_line("2 cloves garlic, finely minced")
    assert res == {
        "raw": "2 cloves garlic, finely minced",
        "name": "garlic",
        "quantity": 2.0,
        "unit": "clove",
        "staple": False,
    }

    # 1/2 tsp kosher salt -> quantity: 0.5, unit: "tsp", staple: True
    res = parse_ingredient_line("1/2 tsp kosher salt")
    assert res == {
        "raw": "1/2 tsp kosher salt",
        "name": "kosher salt",
        "quantity": 0.5,
        "unit": "tsp",
        "staple": True,
    }

    # 1 glug of olive oil -> odd-unit phrase: quantity: None, unit: "", name: "olive oil", staple: True
    res = parse_ingredient_line("1 glug of olive oil")
    assert res == {
        "raw": "1 glug of olive oil",
        "name": "olive oil",
        "quantity": None,
        "unit": "",
        "staple": True,
    }


def test_parse_ingredient_line_unit_aliases():
    assert parse_ingredient_line("2 tablespoons olive oil")["unit"] == "tbsp"
    assert parse_ingredient_line("1 tbsp. butter")["unit"] == "tbsp"
    assert parse_ingredient_line("1 teaspoon pepper")["unit"] == "tsp"
    assert parse_ingredient_line("1 tsp. black pepper")["unit"] == "tsp"
    assert parse_ingredient_line("8 ounces cheddar cheese")["unit"] == "oz"
    assert parse_ingredient_line("8 oz. cheddar cheese")["unit"] == "oz"
    assert parse_ingredient_line("1 pound ground beef")["unit"] == "lb"
    assert parse_ingredient_line("2 lbs chicken thighs")["unit"] == "lb"
    assert parse_ingredient_line("1 lb. ground pork")["unit"] == "lb"
    assert parse_ingredient_line("500 grams flour")["unit"] == "g"
    assert parse_ingredient_line("500 g sugar")["unit"] == "g"
    assert parse_ingredient_line("1 kilogram potatoes")["unit"] == "kg"
    assert parse_ingredient_line("1 kg rice")["unit"] == "kg"
    assert parse_ingredient_line("3 cloves garlic")["unit"] == "clove"
    assert parse_ingredient_line("1 clove garlic")["unit"] == "clove"
    assert parse_ingredient_line("2 cans black beans")["unit"] == "can"
    assert parse_ingredient_line("1 can diced tomatoes")["unit"] == "can"
    assert parse_ingredient_line("2 bunches scallions")["unit"] == "bunch"
    assert parse_ingredient_line("1 bunch cilantro")["unit"] == "bunch"


def test_parse_ingredient_line_strips_of():
    res = parse_ingredient_line("1 cup of whole milk")
    assert res["unit"] == "cup"
    assert res["name"] == "whole milk"
    assert res["quantity"] == 1.0

    res = parse_ingredient_line("1 bunch of scallions")
    assert res["unit"] == "bunch"
    assert res["name"] == "scallions"
    assert res["quantity"] == 1.0


def test_parse_ingredient_line_unrecognized_units_and_counts():
    # Unrecognized unit followed by "of " -> quantity None, unit ""
    res = parse_ingredient_line("1 pinch of salt")
    assert res == {
        "raw": "1 pinch of salt",
        "name": "salt",
        "quantity": None,
        "unit": "",
        "staple": True,
    }

    res = parse_ingredient_line("2 pinches of sea salt")
    assert res == {
        "raw": "2 pinches of sea salt",
        "name": "sea salt",
        "quantity": None,
        "unit": "",
        "staple": True,
    }

    # Count with no unit alias and no "of " -> quantity preserved, unit ""
    res = parse_ingredient_line("4 eggs")
    assert res == {
        "raw": "4 eggs",
        "name": "eggs",
        "quantity": 4.0,
        "unit": "",
        "staple": False,
    }

    res = parse_ingredient_line("2 medium onions, diced")
    assert res == {
        "raw": "2 medium onions, diced",
        "name": "medium onions",
        "quantity": 2.0,
        "unit": "",
        "staple": False,
    }

    res = parse_ingredient_line("2 packets ramen")
    assert res == {
        "raw": "2 packets ramen",
        "name": "packets ramen",
        "quantity": 2.0,
        "unit": "",
        "staple": False,
    }


def test_parse_ingredient_line_fractions_and_numbers():
    # Mixed ASCII fraction
    res = parse_ingredient_line("1 1/2 cups flour")
    assert res["quantity"] == 1.5
    assert res["unit"] == "cup"
    assert res["name"] == "flour"

    # Mixed ASCII fraction with hyphen
    res = parse_ingredient_line("2-1/2 lbs chicken breasts")
    assert res["quantity"] == 2.5
    assert res["unit"] == "lb"
    assert res["name"] == "chicken breasts"

    # Unicode fraction alone
    res = parse_ingredient_line("¼ cup sugar")
    assert res["quantity"] == 0.25
    assert res["unit"] == "cup"
    assert res["name"] == "sugar"

    # Mixed Unicode fraction
    res = parse_ingredient_line("2 ¾ cups vegetable broth")
    assert res["quantity"] == 2.75
    assert res["unit"] == "cup"
    assert res["name"] == "vegetable broth"

    # Decimal
    res = parse_ingredient_line("0.25 tsp black pepper")
    assert res["quantity"] == 0.25
    assert res["unit"] == "tsp"
    assert res["name"] == "black pepper"
    assert res["staple"] is True


def test_parse_ingredient_line_staples():
    staples = [
        "salt",
        "kosher salt",
        "sea salt",
        "pepper",
        "black pepper",
        "water",
        "olive oil",
        "vegetable oil",
        "cooking oil",
    ]
    for staple_name in staples:
        res = parse_ingredient_line(f"1 tsp {staple_name}")
        assert res["staple"] is True, f"Expected {staple_name} to be identified as staple"

    # Case insensitive
    res = parse_ingredient_line("2 tbsp Olive Oil")
    assert res["staple"] is True

    # Non-staple
    res = parse_ingredient_line("1 cup whole milk")
    assert res["staple"] is False


def test_parse_ingredient_line_edge_cases():
    # Bare staple with no quantity
    res = parse_ingredient_line("salt")
    assert res == {
        "raw": "salt",
        "name": "salt",
        "quantity": None,
        "unit": "",
        "staple": True,
    }

    # Item with prep note and no quantity
    res = parse_ingredient_line("fresh parsley, finely chopped")
    assert res == {
        "raw": "fresh parsley, finely chopped",
        "name": "fresh parsley",
        "quantity": None,
        "unit": "",
        "staple": False,
    }

    # Empty string
    res = parse_ingredient_line("")
    assert res == {
        "raw": "",
        "name": "",
        "quantity": None,
        "unit": "",
        "staple": False,
    }


def test_parse_iso_duration():
    assert parse_iso_duration("PT45M") == "45m"
    assert parse_iso_duration("PT1H15M") == "1h 15m"
    assert parse_iso_duration("PT2H") == "2h"
    assert parse_iso_duration("PT1H30M") == "1h 30m"
    assert parse_iso_duration("PT1H") == "1h"
    assert parse_iso_duration("P1DT2H") == "1d 2h"
    assert parse_iso_duration(None) is None
    assert parse_iso_duration("") is None
    assert parse_iso_duration("   ") is None
    assert parse_iso_duration("30 mins") == "30 mins"
    assert parse_iso_duration("1 hour 15 minutes") == "1 hour 15 minutes"


def test_extract_schema_org_recipe_complete():
    html_doc = """
    <!DOCTYPE html>
    <html>
    <head>
      <title>Best Chili Recipe - Food Blog</title>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@graph": [
          {
            "@type": "WebSite",
            "name": "Food Blog"
          },
          {
            "@type": "Recipe",
            "name": "Chili",
            "recipeYield": "4 servings",
            "totalTime": "PT1H15M",
            "recipeIngredient": [
              "500 g ground beef",
              "1 tsp salt"
            ],
            "recipeInstructions": [
              {"@type": "HowToStep", "text": "Brown beef."},
              {"@type": "HowToStep", "text": "Simmer."}
            ]
          }
        ]
      }
      </script>
    </head>
    <body><h1>Chili</h1></body>
    </html>
    """
    res = extract_schema_org_recipe(html_doc)
    assert res is not None
    assert res["title"] == "Chili"
    assert res["servings"] == 4
    assert res["total_time"] == "1h 15m"
    assert len(res["ingredients"]) == 2
    assert res["ingredients"][0]["name"] == "ground beef"
    assert res["ingredients"][0]["quantity"] == 500.0
    assert res["ingredients"][0]["unit"] == "g"
    assert res["ingredients"][0]["staple"] is False
    assert res["ingredients"][1]["name"] == "salt"
    assert res["ingredients"][1]["quantity"] == 1.0
    assert res["ingredients"][1]["unit"] == "tsp"
    assert res["ingredients"][1]["staple"] is True
    assert res["steps"] == ["Brown beef.", "Simmer."]
    assert res["needs_review"] is False
    assert res["review_notes"] is None


def test_malformed_and_non_recipe_jsonld_falls_back():
    html_doc = """
    <html>
    <head>
      <script type="application/ld+json">
        { invalid json here ...
      </script>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "Some Site"
      }
      </script>
    </head>
    <body><p>Hello world</p></body>
    </html>
    """
    res = extract_schema_org_recipe(html_doc)
    assert res is None


def test_extract_html_text_and_title():
    html_doc = """
    <!DOCTYPE html>
    <html>
    <head>
      <title>Quick &amp; Easy Pancakes</title>
      <style>body { font-family: sans-serif; }</style>
      <script>console.log("analytics");</script>
    </head>
    <body>
      <noscript><p>Please enable JS</p></noscript>
      <svg><path d="M0 0"/></svg>
      <h1>Delicious Pancakes</h1>
      <p>Mix 1 cup flour with 1 cup milk.</p>
    </body>
    </html>
    """
    text, title = extract_html_text_and_title(html_doc)
    assert title == "Quick & Easy Pancakes"
    assert "console.log" not in text
    assert "font-family" not in text
    assert "Please enable JS" not in text
    assert "M0 0" not in text
    assert "Delicious Pancakes" in text
    assert "Mix 1 cup flour with 1 cup milk." in text


def test_extract_schema_org_recipe_direct_and_type_list():
    html_doc = """
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": ["ItemPage", "Recipe"],
      "name": "Guacamole",
      "recipeYield": 6,
      "prepTime": "PT15M",
      "recipeIngredient": [
        "3 avocados",
        "1 lime"
      ],
      "recipeInstructions": "Mash avocados.\\nSqueeze lime."
    }
    </script>
    """
    res = extract_schema_org_recipe(html_doc)
    assert res is not None
    assert res["title"] == "Guacamole"
    assert res["servings"] == 6
    assert res["total_time"] == "15m"
    assert len(res["ingredients"]) == 2
    assert res["steps"] == ["Mash avocados.", "Squeeze lime."]
    assert res["needs_review"] is False
    assert res["review_notes"] is None


def test_extract_schema_org_recipe_howto_sections_and_html_steps():
    html_doc = """
    <script type="application/ld+json">
    {
      "@type": "https://schema.org/Recipe",
      "name": "Fancy Pasta",
      "recipeYield": ["4 servings"],
      "cookTime": "PT20M",
      "recipeIngredient": ["200 g pasta"],
      "recipeInstructions": [
        {
          "@type": "HowToSection",
          "name": "Prep",
          "itemListElement": [
            {"@type": "HowToStep", "text": "<p>Boil salted water &amp; add pasta.</p>"}
          ]
        },
        {
          "@type": "HowToSection",
          "name": "Cook",
          "itemListElement": [
            {"@type": "HowToStep", "text": "Drain &amp; serve."}
          ]
        }
      ]
    }
    </script>
    """
    res = extract_schema_org_recipe(html_doc)
    assert res is not None
    assert res["title"] == "Fancy Pasta"
    assert res["steps"] == ["Boil salted water & add pasta.", "Drain & serve."]


def test_extract_schema_org_recipe_needs_review_flags():
    # 1. Missing ingredients
    html_no_ing = """
    <script type="application/ld+json">
    {
      "@type": "Recipe",
      "name": "Mystery",
      "recipeIngredient": [],
      "recipeInstructions": ["Do something."]
    }
    </script>
    """
    res = extract_schema_org_recipe(html_no_ing)
    assert res is not None
    assert res["needs_review"] is True
    assert "Missing ingredients" in res["review_notes"]

    # 2. Missing instructions
    html_no_steps = """
    <script type="application/ld+json">
    {
      "@type": "Recipe",
      "name": "Mystery 2",
      "recipeIngredient": ["1 apple"],
      "recipeInstructions": []
    }
    </script>
    """
    res = extract_schema_org_recipe(html_no_steps)
    assert res is not None
    assert res["needs_review"] is True
    assert "Missing instructions" in res["review_notes"]

    # 3. Non-staple missing quantity
    html_no_qty = """
    <script type="application/ld+json">
    {
      "@type": "Recipe",
      "name": "Herbed Butter",
      "recipeIngredient": ["1 stick butter", "fresh parsley, chopped"],
      "recipeInstructions": ["Mix well."]
    }
    </script>
    """
    res = extract_schema_org_recipe(html_no_qty)
    assert res is not None
    assert res["needs_review"] is True
    assert "One or more non-staple ingredients missing quantity" in res["review_notes"]

    # 4. Missing name defaults to "Untitled Recipe" with review note
    html_no_title = """
    <script type="application/ld+json">
    {
      "@type": "Recipe",
      "recipeIngredient": ["2 eggs"],
      "recipeInstructions": ["Fry eggs."]
    }
    </script>
    """
    res = extract_schema_org_recipe(html_no_title)
    assert res is not None
    assert res["title"] == "Untitled Recipe"
    assert res["needs_review"] is True
    assert "Missing recipe title" in res["review_notes"]


def test_is_video_url():
    assert is_video_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is True
    assert is_video_url("http://youtu.be/dQw4w9WgXcQ") is True
    assert is_video_url("https://tiktok.com/@user/video/1234567") is True
    assert is_video_url("https://www.tiktok.com/@user/video/1234567") is True
    assert is_video_url("https://www.instagram.com/reel/C3_abc123/") is True
    assert is_video_url("https://instagram.com/p/C3_abc123/") is True
    assert is_video_url("https://vimeo.com/123456789") is True
    assert is_video_url("https://twitch.tv/videos/987654321") is True
    assert is_video_url("https://www.facebook.com/reel/123456") is True
    assert is_video_url("https://fb.watch/abc123xyz/") is True

    # Non-video URLs
    assert is_video_url("https://cooking.nytimes.com/recipes/1234-garlic-pasta") is False
    assert is_video_url("https://www.seriouseats.com/the-best-chili-recipe") is False
    assert is_video_url("https://example.com/food") is False


def test_extract_video_text_with_runner():
    def fake_runner(url):
        return {
            "title": "Quick Ramen",
            "description": "How to make 5-minute ramen broth.",
            "transcript": "Boil water, add noodles, stir in miso paste.",
        }

    text, title, error = extract_video_text("https://youtu.be/123", ytdlp_runner=fake_runner)
    assert error is None
    assert title == "Quick Ramen"
    assert "Quick Ramen" in text
    assert "How to make 5-minute ramen broth." in text
    assert "Boil water, add noodles, stir in miso paste." in text


def test_extract_video_text_runner_failure():
    def failing_runner(url):
        raise RuntimeError("Network timeout")

    text, title, error = extract_video_text("https://youtu.be/123", ytdlp_runner=failing_runner)
    assert text is None
    assert title is None
    assert "Video transcript unavailable: Network timeout" in error


def test_extract_with_llm_strips_fences_and_handles_partial():
    def handler(request: httpx.Request) -> httpx.Response:
        fenced_payload = (
            "```json\n"
            '{"title": "Garlic Pasta", "servings": 3, "total_time": "20m", '
            '"ingredients": [{"raw": "200 g pasta", "name": "pasta", "quantity": 200, "unit": "g", "staple": false}], '
            '"steps": ["Boil pasta."], "low_confidence": false}\n'
            "```"
        )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": fenced_payload,
                        }
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    res = extract_with_llm("make garlic pasta", llm_client=client)
    assert res["title"] == "Garlic Pasta"
    assert res["servings"] == 3
    assert res["total_time"] == "20m"
    assert res["steps"] == ["Boil pasta."]
    assert res["needs_review"] is False
    assert res["review_notes"] is None
    assert len(res["ingredients"]) == 1
    assert res["ingredients"][0]["name"] == "pasta"
    assert res["ingredients"][0]["quantity"] == 200.0
    assert res["ingredients"][0]["unit"] == "g"
    assert res["ingredients"][0]["staple"] is False


def test_extract_with_llm_failure_handling():
    def failing_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    client = httpx.Client(transport=httpx.MockTransport(failing_handler))
    res = extract_with_llm("recipe text", fallback_title="Fallback Title", llm_client=client)
    assert res["title"] == "Fallback Title"
    assert res["needs_review"] is True
    assert "LLM extraction failed" in res["review_notes"]


def test_webpage_ingest_uses_jsonld_without_calling_llm(tmp_path):
    html_doc = """
    <html>
    <head>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": "Classic Pancakes",
        "recipeYield": 4,
        "totalTime": "PT20M",
        "recipeIngredient": ["1 cup flour", "1 cup milk", "1/2 tsp salt"],
        "recipeInstructions": ["Mix ingredients.", "Cook on skillet."]
      }
      </script>
    </head>
    <body>Pancakes recipe page</body>
    </html>
    """

    def web_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html_doc)

    http_client = httpx.Client(transport=httpx.MockTransport(web_handler))

    def llm_handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("LLM should not be called when JSON-LD is complete")

    llm_client = httpx.Client(transport=httpx.MockTransport(llm_handler))

    conn = _fresh_conn(tmp_path)
    recipe = ingest_recipe(
        conn,
        url="https://example.com/pancakes",
        http_client=http_client,
        llm_client=llm_client,
    )
    assert recipe["title"] == "Classic Pancakes"
    assert recipe["servings"] == 4
    assert recipe["total_time"] == "20m"
    assert recipe["needs_review"] is False
    assert recipe["steps"] == ["Mix ingredients.", "Cook on skillet."]
    assert len(recipe["ingredients"]) == 3


def test_webpage_ingest_falls_back_to_llm_when_no_jsonld(tmp_path):
    html_doc = """
    <html>
    <head><title>Grandma's Tomato Soup</title></head>
    <body>
      <h1>Grandma's Tomato Soup</h1>
      <p>Ingredients: 4 tomatoes, 1 cup water, 1/2 tsp salt</p>
      <p>Simmer tomatoes in water for 15 mins. Blend and season with salt.</p>
    </body>
    </html>
    """

    def web_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html_doc)

    http_client = httpx.Client(transport=httpx.MockTransport(web_handler))

    def llm_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({
                                "title": "Grandma's Tomato Soup",
                                "servings": 2,
                                "total_time": "15m",
                                "ingredients": [
                                    {"raw": "4 tomatoes", "name": "tomato", "quantity": 4.0, "unit": "", "staple": False},
                                    {"raw": "1 cup water", "name": "water", "quantity": 1.0, "unit": "cup", "staple": True},
                                    {"raw": "1/2 tsp salt", "name": "salt", "quantity": 0.5, "unit": "tsp", "staple": True},
                                ],
                                "steps": ["Simmer tomatoes in water for 15 mins.", "Blend and season with salt."],
                                "low_confidence": False,
                            }),
                        }
                    }
                ]
            },
        )

    llm_client = httpx.Client(transport=httpx.MockTransport(llm_handler))

    conn = _fresh_conn(tmp_path)
    recipe = ingest_recipe(
        conn,
        url="https://example.com/soup",
        http_client=http_client,
        llm_client=llm_client,
    )
    assert recipe["title"] == "Grandma's Tomato Soup"
    assert recipe["servings"] == 2
    assert recipe["total_time"] == "15m"
    assert recipe["needs_review"] is False
    assert len(recipe["ingredients"]) == 3
    assert len(recipe["steps"]) == 2


def test_video_url_ingest_extracts_transcript_and_calls_llm(tmp_path):
    runner_called = False

    def fake_ytdlp(url):
        nonlocal runner_called
        runner_called = True
        return {
            "title": "15 Minute Fried Rice",
            "description": "Quick fried rice recipe with eggs and scallions.",
            "transcript": "Heat wok. Add oil. Fry 2 eggs. Add 2 cups cooked rice. Stir in 2 tbsp soy sauce.",
        }

    def llm_handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        user_prompt = payload["messages"][1]["content"]
        assert "15 Minute Fried Rice" in user_prompt
        assert "Fry 2 eggs" in user_prompt
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({
                                "title": "15 Minute Fried Rice",
                                "servings": 2,
                                "total_time": "15m",
                                "ingredients": [
                                    {"raw": "2 eggs", "name": "egg", "quantity": 2.0, "unit": "", "staple": False},
                                    {"raw": "2 cups cooked rice", "name": "cooked rice", "quantity": 2.0, "unit": "cup", "staple": False},
                                    {"raw": "2 tbsp soy sauce", "name": "soy sauce", "quantity": 2.0, "unit": "tbsp", "staple": False},
                                ],
                                "steps": ["Heat wok and add oil.", "Fry 2 eggs.", "Add rice and stir in soy sauce."],
                                "low_confidence": False,
                            }),
                        }
                    }
                ]
            },
        )

    llm_client = httpx.Client(transport=httpx.MockTransport(llm_handler))

    conn = _fresh_conn(tmp_path)
    recipe = ingest_recipe(
        conn,
        url="https://www.youtube.com/watch?v=abc",
        llm_client=llm_client,
        ytdlp_runner=fake_ytdlp,
    )
    assert runner_called is True
    assert recipe["title"] == "15 Minute Fried Rice"
    assert recipe["needs_review"] is False
    assert len(recipe["ingredients"]) == 3
    assert len(recipe["steps"]) == 3


def test_never_fail_when_video_and_llm_both_fail(tmp_path):
    def failing_ytdlp(url):
        raise RuntimeError("Instagram login required")

    conn = _fresh_conn(tmp_path)
    recipe = ingest_recipe(
        conn,
        url="https://www.instagram.com/reel/xyz123/",
        ytdlp_runner=failing_ytdlp,
    )
    assert recipe is not None
    assert recipe["source_url"] == "https://www.instagram.com/reel/xyz123/"
    assert recipe["needs_review"] is True
    assert "Instagram login required" in recipe["review_notes"]


def test_ingest_recipe_raw_text_direct(tmp_path):
    def llm_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({
                                "title": "Scrambled Eggs",
                                "servings": 1,
                                "total_time": "5m",
                                "ingredients": [
                                    {"raw": "2 eggs", "name": "egg", "quantity": 2.0, "unit": "", "staple": False},
                                    {"raw": "1 tbsp butter", "name": "butter", "quantity": 1.0, "unit": "tbsp", "staple": False},
                                ],
                                "steps": ["Melt butter.", "Whisk and cook eggs."],
                                "low_confidence": False,
                            }),
                        }
                    }
                ]
            },
        )

    llm_client = httpx.Client(transport=httpx.MockTransport(llm_handler))

    conn = _fresh_conn(tmp_path)
    recipe = ingest_recipe(
        conn,
        raw_text="2 eggs, 1 tbsp butter. Whisk and scramble.",
        title="Override Title",
        llm_client=llm_client,
    )
    assert recipe["title"] == "Override Title"
    assert recipe["servings"] == 1
    assert recipe["needs_review"] is False
    assert len(recipe["ingredients"]) == 2


def test_reingest_recipe(tmp_path):
    conn = _fresh_conn(tmp_path)
    # Create an initial recipe that needs review
    recipe_id = recipes.create_recipe(
        conn,
        title="Mystery Recipe",
        needs_review=True,
        review_notes="Initial extraction failed",
    )

    def llm_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({
                                "title": "Garlic Butter Toast",
                                "servings": 2,
                                "total_time": "10m",
                                "ingredients": [
                                    {"raw": "2 slices bread", "name": "bread", "quantity": 2.0, "unit": "slice", "staple": False},
                                    {"raw": "1 tbsp butter", "name": "butter", "quantity": 1.0, "unit": "tbsp", "staple": False},
                                    {"raw": "1 clove garlic", "name": "garlic", "quantity": 1.0, "unit": "clove", "staple": False},
                                ],
                                "steps": ["Toast bread.", "Rub garlic and spread butter."],
                                "low_confidence": False,
                            }),
                        }
                    }
                ]
            },
        )

    llm_client = httpx.Client(transport=httpx.MockTransport(llm_handler))
    updated = reingest_recipe(
        conn,
        recipe_id,
        "2 slices bread, 1 tbsp butter, 1 clove garlic. Toast bread and rub garlic.",
        llm_client=llm_client,
    )
    assert updated is not None
    assert updated["id"] == recipe_id
    assert updated["title"] == "Garlic Butter Toast"
    assert updated["needs_review"] is False
    assert updated["review_notes"] is None
    assert len(updated["ingredients"]) == 3

    # Non-existent recipe returns None
    assert reingest_recipe(conn, 9999, "some text", llm_client=llm_client) is None


def test_webpage_incomplete_jsonld_falls_back_to_llm(tmp_path):
    # Page contains stub Recipe JSON-LD with only title, missing ingredients and steps
    html_doc = """
    <html>
    <head>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": "Stub Pasta",
        "recipeIngredient": [],
        "recipeInstructions": []
      }
      </script>
    </head>
    <body>
      <h1>Stub Pasta</h1>
      <p>Ingredients: 200g penne, 2 tbsp pesto.</p>
      <p>Boil penne and toss with pesto.</p>
    </body>
    </html>
    """

    def web_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html_doc)

    http_client = httpx.Client(transport=httpx.MockTransport(web_handler))

    llm_called = False

    def llm_handler(request: httpx.Request) -> httpx.Response:
        nonlocal llm_called
        llm_called = True
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({
                                "title": "Stub Pasta",
                                "servings": 2,
                                "total_time": "15m",
                                "ingredients": [
                                    {"raw": "200g penne", "name": "penne", "quantity": 200.0, "unit": "g", "staple": False},
                                    {"raw": "2 tbsp pesto", "name": "pesto", "quantity": 2.0, "unit": "tbsp", "staple": False},
                                ],
                                "steps": ["Boil penne and toss with pesto."],
                                "low_confidence": False,
                            }),
                        }
                    }
                ]
            },
        )

    llm_client = httpx.Client(transport=httpx.MockTransport(llm_handler))

    conn = _fresh_conn(tmp_path)
    recipe = ingest_recipe(
        conn,
        url="https://example.com/stub-pasta",
        http_client=http_client,
        llm_client=llm_client,
    )
    assert llm_called is True
    assert recipe["title"] == "Stub Pasta"
    assert recipe["servings"] == 2
    assert recipe["needs_review"] is False
    assert len(recipe["ingredients"]) == 2
    assert recipe["steps"] == ["Boil penne and toss with pesto."]


def test_webpage_incomplete_jsonld_preserves_partial_when_llm_fails(tmp_path):
    # Page contains partial Recipe JSON-LD (has 1 ingredient, but 0 steps)
    html_doc = """
    <html>
    <head>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": "Partial Soup",
        "recipeIngredient": ["4 cups broth"],
        "recipeInstructions": []
      }
      </script>
    </head>
    <body>
      <h1>Partial Soup</h1>
    </body>
    </html>
    """

    def web_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html_doc)

    http_client = httpx.Client(transport=httpx.MockTransport(web_handler))

    def llm_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    llm_client = httpx.Client(transport=httpx.MockTransport(llm_handler))

    conn = _fresh_conn(tmp_path)
    recipe = ingest_recipe(
        conn,
        url="https://example.com/partial-soup",
        http_client=http_client,
        llm_client=llm_client,
    )
    assert recipe["title"] == "Partial Soup"
    assert recipe["needs_review"] is True
    # Schema.org had 1 ingredient preserved
    assert len(recipe["ingredients"]) == 1
    assert recipe["ingredients"][0]["raw"] == "4 cups broth"
    assert "Missing instructions" in recipe["review_notes"]
    assert "LLM extraction failed" in recipe["review_notes"]


def test_extract_video_text_avoids_duplicate_captions():
    def fake_runner(url):
        return {
            "title": "Cooking Video",
            "description": "Video description.",
            "subtitles": "Manual subtitle line 1.\nManual subtitle line 2.",
            "automatic_captions": "Auto caption line 1.\nAuto caption line 2.",
        }

    text, title, error = extract_video_text("https://youtu.be/test1234", ytdlp_runner=fake_runner)
    assert error is None
    assert title == "Cooking Video"
    assert "Manual subtitle line 1." in text
    assert "Auto caption line 1." not in text


def test_extract_with_llm_cleans_ingredient_name_descriptors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({
                                "title": "Garlic Dressing",
                                "servings": 2,
                                "total_time": "5m",
                                "ingredients": [
                                    {"name": "garlic, finely minced", "quantity": 2, "unit": "cloves"},
                                    {"name": "olive oil, extra virgin", "quantity": 3, "unit": "tbsp", "staple": True},
                                ],
                                "steps": ["Whisk together."],
                                "low_confidence": False,
                            }),
                        }
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    res = extract_with_llm("make garlic dressing", llm_client=client)
    assert res["needs_review"] is False
    assert len(res["ingredients"]) == 2
    garlic = res["ingredients"][0]
    assert garlic["name"] == "garlic"
    assert garlic["unit"] == "clove"
    assert garlic["quantity"] == 2.0
    assert garlic["raw"] == "2 cloves garlic, finely minced"

    oil = res["ingredients"][1]
    assert oil["name"] == "olive oil"
    assert oil["unit"] == "tbsp"
    assert oil["staple"] is True



