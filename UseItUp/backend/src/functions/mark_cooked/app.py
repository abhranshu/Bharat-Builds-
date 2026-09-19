"""Deducts ingredients, logs meal when a recipe is marked as cooked."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any

from src.shared import dynamo_client
from src.shared.constants import (
    PK_PREFIX_HOUSEHOLD,
    SK_PREFIX_ITEM,
    SK_PREFIX_COOKED,
)
from src.shared.models import MarkCookedRequest, MarkCookedResponse, NutritionInfo
from src.shared.nutrition_calculator import calculate_recipe_nutrition

logger = logging.getLogger(__name__)


def handler(event, context):
    """Lambda handler for POST /cooked."""
    try:
        body = json.loads(event.get("body", "{}"))
        request = MarkCookedRequest(**body)

        pk = f"{PK_PREFIX_HOUSEHOLD}{request.household_id}"

        # Step 1: Deduct ingredients from inventory
        updated_items = []
        for recipe_ing in request.recipe.ingredients:
            item_id = f"{recipe_ing.ingredient_id}_*"

            # Find the matching inventory item
            existing_items = dynamo_client.query_items(
                pk=pk, sk_prefix=SK_PREFIX_ITEM
            )

            for item in existing_items:
                if item.get("ingredient_id") == recipe_ing.ingredient_id:
                    current_qty = float(item.get("quantity_g", 0))
                    used_qty = recipe_ing.grams * request.servings_cooked
                    new_qty = max(0, current_qty - used_qty)

                    item_sk = item.get("SK", "")

                    if new_qty <= 0:
                        # Delete the item if quantity hits zero
                        dynamo_client.delete_item(pk=pk, sk=item_sk)
                        logger.info("Deleted item %s (quantity depleted)", item_sk)
                    else:
                        # Update quantity
                        dynamo_client.update_item(
                            pk=pk,
                            sk=item_sk,
                            updates={"quantity_g": new_qty},
                        )
                        logger.info(
                            "Updated %s: %.1fg → %.1fg",
                            item_sk,
                            current_qty,
                            new_qty,
                        )

                    break

        # Step 2: Write COOKED# record
        nutrition_totals = calculate_recipe_nutrition(
            ingredients=[
                {"ingredient_id": ri.ingredient_id, "grams": ri.grams}
                for ri in request.recipe.ingredients
            ],
            servings=request.servings_cooked,
        )
        # Scale totals to actual servings
        for key in nutrition_totals:
            nutrition_totals[key] = round(
                nutrition_totals[key] * request.servings_cooked / request.recipe.servings,
                1,
            )

        cooked_timestamp = datetime.utcnow().isoformat()
        cooked_sk = f"{SK_PREFIX_COOKED}{cooked_timestamp}"

        dynamo_client.put_item(
            pk=pk,
            sk=cooked_sk,
            data={
                "recipe_name": request.recipe.name,
                "ingredients_used": [
                    {
                        "ingredient_id": ri.ingredient_id,
                        "name": ri.name,
                        "grams": ri.grams,
                    }
                    for ri in request.recipe.ingredients
                ],
                "nutrition_totals": nutrition_totals,
                "servings_cooked": request.servings_cooked,
            },
        )

        # Step 3: Get updated inventory
        remaining_items = dynamo_client.query_items(pk=pk, sk_prefix=SK_PREFIX_ITEM)

        # Step 4: Get updated daily nutrition
        today_iso = date.today().isoformat()
        cooked_today = dynamo_client.query_items(
            pk=pk, sk_prefix=f"{SK_PREFIX_COOKED}{today_iso}"
        )

        total_nutrition = NutritionInfo()
        for record in cooked_today:
            totals = record.get("nutrition_totals", {})
            total_nutrition.calories += totals.get("calories", 0)
            total_nutrition.protein += totals.get("protein", 0)
            total_nutrition.carbs += totals.get("carbs", 0)
            total_nutrition.fat += totals.get("fat", 0)
            total_nutrition.fiber += totals.get("fiber", 0)

        response = MarkCookedResponse(
            message=f"Marked '{request.recipe.name}' as cooked for {request.servings_cooked} servings",
            updated_inventory=[],  # Simplified for response
            daily_nutrition=total_nutrition,
        )

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": response.model_dump_json(),
        }

    except Exception as exc:
        logger.error("Error marking cooked: %s", exc)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Internal server error",
                "detail": str(exc),
                "status_code": 500,
            }),
        }
