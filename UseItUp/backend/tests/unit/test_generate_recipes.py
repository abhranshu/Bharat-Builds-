"""Unit tests for generate_recipes Bedrock integration.

Covers two things the model cannot be trusted to get right on its own:
  1. Ingredient IDs it returns are filtered against the household inventory.
  2. The prompt carries real days-until-expiry, not "unknown".
"""

import importlib
import json
import os
from datetime import date, timedelta

# Dummy AWS env before importing the handler module (boto3 clients at import).
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("TABLE_NAME", "UseItUp-dev")

app_module = importlib.import_module("src.functions.generate_recipes.app")


def _event() -> dict:
    return {
        "body": json.dumps(
            {
                "household_id": "hh-test",
                "meal_type": "lunch",
                "prep_time_preference": 30,
            }
        )
    }


def _install_fakes(monkeypatch, items, model_output):
    """Patch DynamoDB + Bedrock so the handler runs fully offline."""
    captured = {}

    def fake_query_items(pk, sk_prefix=None, **kwargs):
        if sk_prefix == "ITEM#":
            return list(items)
        return []  # COOKED# records

    def fake_invoke_bedrock(prompt, **kwargs):
        captured["prompt"] = prompt
        return model_output

    monkeypatch.setattr(app_module.dynamo_client, "query_items", fake_query_items)
    monkeypatch.setattr(app_module.dynamo_client, "get_item", lambda pk, sk: {})
    monkeypatch.setattr(app_module, "invoke_bedrock", fake_invoke_bedrock)
    return captured


def _item(ingredient_id, days, qty=500):
    return {
        "ingredient_id": ingredient_id,
        "quantity_g": qty,
        "predicted_expiry": (date.today() + timedelta(days=days)).isoformat(),
    }


def test_invented_ingredients_are_discarded(monkeypatch):
    captured = _install_fakes(
        monkeypatch,
        items=[_item("tomato", 3)],
        model_output=[
            {
                "name": "Tomato & Dragonfruit Salad",
                "ingredients": [
                    {"ingredient_id": "tomato", "grams": 200},
                    {"ingredient_id": "dragonfruit", "grams": 100},
                ],
                "steps": ["Chop and mix."],
                "prep_time_minutes": 10,
                "servings": 2,
            }
        ],
    )

    response = app_module.handler(_event(), None)
    assert response["statusCode"] == 200

    recipes = json.loads(response["body"])["recipes"]
    assert len(recipes) == 1
    assert [i["ingredient_id"] for i in recipes[0]["ingredients"]] == ["tomato"]

    # The invented item must not reach the prompt-dependent reason either.
    assert "dragonfruit" not in captured["prompt"]


def test_recipe_with_only_invented_ingredients_is_skipped(monkeypatch):
    _install_fakes(
        monkeypatch,
        items=[_item("tomato", 3)],
        model_output=[
            {
                "name": "Ghost Curry",
                "ingredients": [{"ingredient_id": "dragonfruit", "grams": 100}],
                "steps": ["Cook."],
                "prep_time_minutes": 20,
                "servings": 2,
            }
        ],
    )

    response = app_module.handler(_event(), None)
    assert response["statusCode"] == 200
    assert json.loads(response["body"])["recipes"] == []


def test_prompt_carries_real_days_until_expiry(monkeypatch):
    captured = _install_fakes(
        monkeypatch,
        items=[_item("tomato", 3), _item("paneer", 1)],
        model_output=[
            {
                "name": "Paneer Tomato",
                "ingredients": [
                    {"ingredient_id": "tomato", "grams": 200},
                    {"ingredient_id": "paneer", "grams": 150},
                ],
                "steps": ["Cook."],
                "prep_time_minutes": 15,
                "servings": 2,
            }
        ],
    )

    app_module.handler(_event(), None)

    prompt = captured["prompt"]
    assert "expires in 3 days" in prompt
    assert "expires in 1 days" in prompt
    assert "unknown" not in prompt
    # Soonest-expiring first, so the model can prioritise.
    assert prompt.index("(paneer)") < prompt.index("(tomato)")


def test_expired_item_is_labelled(monkeypatch):
    captured = _install_fakes(
        monkeypatch,
        items=[_item("coriander", -2)],
        model_output=[
            {
                "name": "Coriander Chutney",
                "ingredients": [{"ingredient_id": "coriander", "grams": 30}],
                "steps": ["Blend."],
                "prep_time_minutes": 5,
                "servings": 2,
            }
        ],
    )

    app_module.handler(_event(), None)
    assert "already expired" in captured["prompt"]


def test_empty_inventory_short_circuits_without_calling_bedrock(monkeypatch):
    captured = _install_fakes(monkeypatch, items=[], model_output=[])

    response = app_module.handler(_event(), None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["recipes"] == []
    assert "prompt" not in captured  # Bedrock never called
