"""Unit tests for nutrition calculator."""

import pytest

from src.shared.nutrition_calculator import (
    calculate_ingredient_nutrition,
    calculate_recipe_nutrition,
    calculate_daily_totals,
)


class TestCalculateIngredientNutrition:
    """Tests for calculate_ingredient_nutrition function."""

    def test_tomato_100g(self):
        """100g of tomato should return per-100g values."""
        result = calculate_ingredient_nutrition("tomato", 100)

        assert result["calories"] == 20.0
        assert result["protein"] == 0.9
        assert result["carbs"] == 3.9
        assert result["fat"] == 0.2
        assert result["fiber"] == 1.2

    def test_tomato_200g(self):
        """200g of tomato should double the values."""
        result = calculate_ingredient_nutrition("tomato", 200)

        assert result["calories"] == 40.0
        assert result["protein"] == 1.8
        assert result["carbs"] == 7.8

    def test_chicken_150g(self):
        """150g of chicken breast should scale correctly."""
        result = calculate_ingredient_nutrition("chicken_breast", 150)

        # 165 kcal/100g × 1.5 = 247.5
        assert result["calories"] == 247.5
        # 31g/100g × 1.5 = 46.5
        assert result["protein"] == 46.5

    def test_zero_grams(self):
        """0g should return all zeros."""
        result = calculate_ingredient_nutrition("tomato", 0)

        assert result["calories"] == 0.0
        assert result["protein"] == 0.0

    def test_unknown_ingredient(self):
        """Unknown ingredient should return all zeros."""
        result = calculate_ingredient_nutrition("unknown_food", 100)

        assert result["calories"] == 0.0


class TestCalculateRecipeNutrition:
    """Tests for calculate_recipe_nutrition function."""

    def test_simple_recipe(self):
        """Recipe with two ingredients should sum correctly."""
        ingredients = [
            {"ingredient_id": "tomato", "grams": 200},
            {"ingredient_id": "oil", "grams": 15},
        ]
        result = calculate_recipe_nutrition(ingredients, servings=2)

        # Tomato: 40 kcal, Oil: 132.6 kcal → total 172.6 → per serving 86.3
        assert result["calories"] == 86.3
        # Tomato: 1.8g protein, Oil: 0g → total 1.8 → per serving 0.9
        assert result["protein"] == 0.9

    def test_recipe_with_zero_servings(self):
        """Zero servings should not divide by zero."""
        ingredients = [{"ingredient_id": "tomato", "grams": 100}]
        result = calculate_recipe_nutrition(ingredients, servings=0)

        # Should return full amount (no division)
        assert result["calories"] == 20.0

    def test_empty_recipe(self):
        """Empty ingredients list should return all zeros."""
        result = calculate_recipe_nutrition([], servings=2)

        assert result["calories"] == 0.0
        assert result["protein"] == 0.0


class TestCalculateDailyTotals:
    """Tests for calculate_daily_totals function."""

    def test_sum_multiple_meals(self):
        """Multiple cooked records should sum correctly."""
        records = [
            {"nutrition_totals": {"calories": 500, "protein": 20, "carbs": 60, "fat": 15, "fiber": 5}},
            {"nutrition_totals": {"calories": 300, "protein": 15, "carbs": 40, "fat": 10, "fiber": 3}},
        ]
        result = calculate_daily_totals(records)

        assert result["calories"] == 800.0
        assert result["protein"] == 35.0
        assert result["carbs"] == 100.0
        assert result["fat"] == 25.0
        assert result["fiber"] == 8.0

    def test_empty_records(self):
        """No records should return all zeros."""
        result = calculate_daily_totals([])

        assert result["calories"] == 0.0
        assert result["protein"] == 0.0
