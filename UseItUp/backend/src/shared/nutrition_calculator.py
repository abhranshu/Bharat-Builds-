"""Deterministic nutrition calculator using IFCT data.

Computes per-serving macros from recipe ingredients and quantities.
This is NOT derived from LLM output — it uses the IFCT table data
stored in the ingredient catalog.
"""

from __future__ import annotations

from typing import Any

from .ingredient_catalog import get_macros_per_100g, get_catalog_item


def calculate_ingredient_nutrition(
    ingredient_id: str,
    grams: float,
) -> dict[str, float]:
    """Calculate nutrition for a specific quantity of an ingredient.

    Args:
        ingredient_id: Canonical ingredient ID.
        grams: Quantity in grams.

    Returns:
        Dict with calories, protein, carbs, fat, fiber values.
    """
    macros_per_100g = get_macros_per_100g(ingredient_id)
    factor = grams / 100.0

    return {
        "calories": round(macros_per_100g["calories"] * factor, 1),
        "protein": round(macros_per_100g["protein"] * factor, 1),
        "carbs": round(macros_per_100g["carbs"] * factor, 1),
        "fat": round(macros_per_100g["fat"] * factor, 1),
        "fiber": round(macros_per_100g["fiber"] * factor, 1),
    }


def calculate_recipe_nutrition(
    ingredients: list[dict[str, Any]],
    servings: int = 2,
) -> dict[str, float]:
    """Calculate total and per-serving nutrition for a recipe.

    Args:
        ingredients: List of {"ingredient_id": str, "grams": float}.
        servings: Number of servings the recipe yields.

    Returns:
        Dict with per-serving calories, protein, carbs, fat, fiber.
    """
    totals = {
        "calories": 0.0,
        "protein": 0.0,
        "carbs": 0.0,
        "fat": 0.0,
        "fiber": 0.0,
    }

    for ing in ingredients:
        ingredient_id = ing.get("ingredient_id", "")
        grams = ing.get("grams", 0)

        if grams <= 0 or not ingredient_id:
            continue

        nutrition = calculate_ingredient_nutrition(ingredient_id, grams)

        for key in totals:
            totals[key] += nutrition[key]

    # Divide by servings
    if servings > 0:
        for key in totals:
            totals[key] = round(totals[key] / servings, 1)

    return totals


def calculate_daily_totals(
    cooked_records: list[dict[str, Any]],
) -> dict[str, float]:
    """Sum nutrition from all cooked records for a given day.

    Args:
        cooked_records: List of dicts with "nutrition_totals" key.

    Returns:
        Aggregated nutrition totals.
    """
    totals = {
        "calories": 0.0,
        "protein": 0.0,
        "carbs": 0.0,
        "fat": 0.0,
        "fiber": 0.0,
    }

    for record in cooked_records:
        nutrition = record.get("nutrition_totals", {})
        for key in totals:
            totals[key] += nutrition.get(key, 0.0)

    for key in totals:
        totals[key] = round(totals[key], 1)

    return totals
