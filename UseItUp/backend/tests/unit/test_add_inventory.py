"""Unit tests for add_inventory handler."""

import importlib
import json
import os
import pytest

os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("TABLE_NAME", "UseItUp-dev")

app_module = importlib.import_module("src.functions.add_inventory.app")


def test_add_catalog_ingredient(monkeypatch):
    put_items = []

    def fake_put_item(pk, sk, data, **kwargs):
        put_items.append((pk, sk, data))

    monkeypatch.setattr(app_module.dynamo_client, "put_item", fake_put_item)
    monkeypatch.setattr(app_module.dynamo_client, "get_item", lambda pk, sk: {})

    event = {
        "body": json.dumps({
            "household_id": "hh-test",
            "ingredient_id": "tomato",
            "quantity_g": 300,
        })
    }

    result = app_module.handler(event, None)
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["ingredient_id"] == "tomato"
    assert body["quantity_g"] == 300
    assert len(put_items) == 1


def test_add_custom_ingredient_when_in_profile(monkeypatch):
    put_items = []

    def fake_put_item(pk, sk, data, **kwargs):
        put_items.append((pk, sk, data))

    def fake_get_item(pk, sk):
        return {"additional_valid_ingredients": ["bread", "cheese"]}

    monkeypatch.setattr(app_module.dynamo_client, "put_item", fake_put_item)
    monkeypatch.setattr(app_module.dynamo_client, "get_item", fake_get_item)

    event = {
        "body": json.dumps({
            "household_id": "hh-test",
            "ingredient_id": "bread",
            "quantity_g": 200,
        })
    }

    result = app_module.handler(event, None)
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["ingredient_id"] == "bread"


def test_reject_unlisted_ingredient(monkeypatch):
    monkeypatch.setattr(app_module.dynamo_client, "get_item", lambda pk, sk: {"additional_valid_ingredients": ["bread"]})

    event = {
        "body": json.dumps({
            "household_id": "hh-test",
            "ingredient_id": "unobtanium_powder",
            "quantity_g": 100,
        })
    }

    result = app_module.handler(event, None)
    assert result["statusCode"] == 400
    body = json.loads(result["body"])
    assert "not in the valid items list" in body["error"]
