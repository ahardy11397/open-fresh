import pytest
from openfresh.ingest import parse_ingredient_line, parse_iso_duration


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
