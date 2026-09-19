"""Seed DynamoDB with ingredient catalog and IFCT nutrition data.

Usage:
    # Local (with dynamodb-local docker container):
    TABLE_NAME=UseItUp-dev AWS_DEFAULT_REGION=us-east-1 \
        AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local \
        python scripts/seed_dynamo.py

    # Remote (against deployed table):
    TABLE_NAME=UseItUp-dev AWS_DEFAULT_REGION=us-east-1 \
        python scripts/seed_dynamo.py
"""

from __future__ import annotations

import json
import os
import sys

import boto3
from boto3.dynamodb.conditions import Key

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.shared.ingredient_catalog import STATIC_CATALOG


def seed_catalog(table_name: str, endpoint_url: str | None = None) -> int:
    """Load the static catalog into DynamoDB.

    Returns the number of items written.
    """
    kwargs = {"region_name": os.environ.get("AWS_DEFAULT_REGION", "us-east-1")}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url

    dynamodb = boto3.resource("dynamodb", **kwargs)
    table = dynamodb.Table(table_name)

    count = 0
    for item in STATIC_CATALOG:
        ingredient_id = item["ingredient_id"]
        pk = f"CAT#{ingredient_id}"
        sk = "META"

        db_item = {
            "PK": pk,
            "SK": sk,
            "GSI1PK": pk,
            "GSI1SK": ingredient_id,
            "ingredient_id": ingredient_id,
            "canonical_name": item["canonical_name"],
            "aliases": item.get("aliases", []),
            "shelf_life_days": item.get("shelf_life_days", 7),
            "category": item.get("category", "general"),
            "ifct_macros_per_100g": item.get("ifct_macros_per_100g", {}),
        }

        table.put_item(Item=db_item)
        count += 1
        print(f"  ✓ {ingredient_id}: {item['canonical_name']}")

    return count


def verify_seed(table_name: str, endpoint_url: str | None = None) -> list[dict]:
    """Verify seeded data by querying GSI1."""
    kwargs = {"region_name": os.environ.get("AWS_DEFAULT_REGION", "us-east-1")}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url

    dynamodb = boto3.resource("dynamodb", **kwargs)
    table = dynamodb.Table(table_name)

    resp = table.query(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").begins_with("CAT#"),
    )

    return resp.get("Items", [])


def main():
    table_name = os.environ.get("TABLE_NAME", "UseItUp-dev")
    endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL")

    print(f"Seeding DynamoDB table: {table_name}")
    print(f"Endpoint: {endpoint_url or '(default AWS)'}")
    print(f"Items to seed: {len(STATIC_CATALOG)}")
    print()

    count = seed_catalog(table_name, endpoint_url)

    print(f"\n✅ Seeded {count} catalog items")

    # Verify
    print("\nVerifying...")
    items = verify_seed(table_name, endpoint_url)
    print(f"✅ Verified {len(items)} items in DynamoDB\n")

    # Show first 5
    print("Sample items:")
    for item in items[:5]:
        print(f"  - {item['ingredient_id']}: {item['canonical_name']}")


if __name__ == "__main__":
    main()
