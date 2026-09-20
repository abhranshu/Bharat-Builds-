"""Unit tests for the ingredient catalog.

These exercise the hardcoded catalog only — no DynamoDB or AWS access.
"""

import pytest

from src.shared.ingredient_catalog import (
    STATIC_CATALOG,
    get_all_aliases,
    get_all_ingredient_ids,
    get_canonical_name,
    get_catalog_for_prompt,
    get_macros_per_100g,
    get_shelf_life,
    search_by_name,
)

# The ingredients explicitly required to be seeded for the demo.
REQUIRED_INGREDIENTS = [
    "paneer",
    "coriander",
    "tomato",
    "onion",
    "potato",
    "wheat_flour",  # atta
    "rice",
    "moong_dal",  # dal
    "curd",
    "milk",
]


class TestStaticCatalogShape:
    """The catalog must be usable without any DynamoDB load."""

    def test_required_ingredients_present(self):
        ids = get_all_ingredient_ids()
        for ingredient in REQUIRED_INGREDIENTS:
            assert ingredient in ids, f"missing seeded ingredient: {ingredient}"

    def test_every_entry_has_required_fields(self):
        for iid, item in STATIC_CATALOG.items():
            assert item["ingredient_id"] == iid
            assert item["canonical_name"]
            assert isinstance(item["aliases"], list)
            assert item["shelf_life_days"] > 0
            macros = item["ifct_macros_per_100g"]
            for key in ("calories", "protein", "carbs", "fat", "fiber"):
                assert key in macros, f"{iid} missing macro {key}"


class TestCatalogLookups:
    def test_get_shelf_life(self):
        assert get_shelf_life("tomato") == 7
        assert get_shelf_life("curd") == 5

    def test_get_shelf_life_unknown_defaults_to_seven(self):
        assert get_shelf_life("unobtanium") == 7

    def test_get_macros_paneer(self):
        macros = get_macros_per_100g("paneer")
        assert macros["calories"] == 265
        assert macros["protein"] == 18.3

    def test_get_macros_unknown_returns_zeros(self):
        macros = get_macros_per_100g("unobtanium")
        assert macros == {
            "calories": 0, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0,
        }

    def test_get_canonical_name(self):
        assert get_canonical_name("wheat_flour") == "Wheat Flour"
        assert get_canonical_name("unknown_thing") == "Unknown Thing"


class TestAliases:
    def test_hindi_aliases_resolve(self):
        assert search_by_name("tamatar") == "tomato"
        assert search_by_name("atta") == "wheat_flour"
        assert search_by_name("dahi") == "curd"
        assert search_by_name("aloo") == "potato"

    def test_canonical_name_resolves(self):
        assert search_by_name("Paneer") == "paneer"

    def test_unknown_name_returns_none(self):
        assert search_by_name("dragonfruit souffle") is None

    def test_aliases_map_is_populated(self):
        aliases = get_all_aliases()
        assert aliases["dhania"] == "coriander"


class TestCatalogForPrompt:
    def test_prompt_contains_ids(self):
        prompt = get_catalog_for_prompt()
        assert "- tomato: Tomato" in prompt
        assert "- paneer: Paneer" in prompt

    def test_expanded_catalog_prompt_with_custom_items(self):
        from src.shared.ingredient_catalog import get_expanded_catalog_prompt, is_valid_ingredient
        prompt = get_expanded_catalog_prompt(["bread", "cheese slice"])
        assert "- tomato: Tomato" in prompt
        assert "- bread: Bread" in prompt
        assert "- cheese_slice: Cheese Slice" in prompt

        assert is_valid_ingredient("tomato") is True
        assert is_valid_ingredient("tamatar") is True
        assert is_valid_ingredient("bread", ["bread"]) is True
        assert is_valid_ingredient("cheese_slice", ["cheese slice"]) is True
        assert is_valid_ingredient("dragonfruit", ["bread"]) is False
