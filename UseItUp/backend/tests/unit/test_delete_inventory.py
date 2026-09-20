"""Unit tests for delete_inventory handler."""

import importlib
import json
import os
import pytest

os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("TABLE_NAME", "UseItUp-dev")

app_module = importlib.import_module("src.functions.delete_inventory.app")


def test_delete_by_item_sk(monkeypatch):
    deleted = []

    def fake_delete_item(pk, sk):
        deleted.append((pk, sk))

    monkeypatch.setattr(app_module.dynamo_client, "delete_item", fake_delete_item)

    event = {
        "body": json.dumps({
            "household_id": "hh-test",
            "item_sk": "ITEM#tomato_2026-09-20",
        })
    }

    result = app_module.handler(event, None)
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["household_id"] == "hh-test"
    assert body["deleted_sk"] == "ITEM#tomato_2026-09-20"
    assert len(deleted) == 1
    assert deleted[0] == ("HH#hh-test", "ITEM#tomato_2026-09-20")


def test_delete_by_ingredient_id(monkeypatch):
    deleted = []

    def fake_delete_item(pk, sk):
        deleted.append((pk, sk))

    def fake_query_items(pk, sk_prefix):
        return [
            {"SK": "ITEM#chicken_breast", "ingredient_id": "chicken_breast"},
            {"SK": "ITEM#onion_2026-09-20", "ingredient_id": "onion"},
        ]

    monkeypatch.setattr(app_module.dynamo_client, "delete_item", fake_delete_item)
    monkeypatch.setattr(app_module.dynamo_client, "query_items", fake_query_items)

    event = {
        "body": json.dumps({
            "household_id": "hh-test",
            "ingredient_id": "chicken_breast",
        })
    }

    result = app_module.handler(event, None)
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["household_id"] == "hh-test"
    assert body["ingredient_id"] == "chicken_breast"
    assert len(deleted) == 1
    assert deleted[0] == ("HH#hh-test", "ITEM#chicken_breast")


def test_delete_query_parameters(monkeypatch):
    deleted = []

    def fake_delete_item(pk, sk):
        deleted.append((pk, sk))

    monkeypatch.setattr(app_module.dynamo_client, "delete_item", fake_delete_item)

    event = {
        "queryStringParameters": {
            "household_id": "hh-test",
            "item_sk": "ITEM#egg",
        }
    }

    result = app_module.handler(event, None)
    assert result["statusCode"] == 200
    assert deleted == [("HH#hh-test", "ITEM#egg")]


def test_missing_household_id():
    event = {
        "body": json.dumps({
            "item_sk": "ITEM#egg",
        })
    }
    result = app_module.handler(event, None)
    assert result["statusCode"] == 400
    body = json.loads(result["body"])
    assert "household_id" in body["error"]


def test_missing_item_sk_and_ingredient_id():
    event = {
        "body": json.dumps({
            "household_id": "hh-test",
        })
    }
    result = app_module.handler(event, None)
    assert result["statusCode"] == 400


def test_invalid_json():
    event = {
        "body": "not-valid-json{"
    }
    result = app_module.handler(event, None)
    assert result["statusCode"] == 400
