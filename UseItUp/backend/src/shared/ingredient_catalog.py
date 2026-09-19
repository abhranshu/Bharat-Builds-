"""Ingredient catalog with canonical IDs, aliases, shelf-life lookups, and IFCT data.

The catalog is small enough to load into Lambda memory at cold start.
This module provides lookup helpers for the most common Indian household
ingredients with their nutrition data from the Indian Food Composition Tables.
"""

from __future__ import annotations

import logging
from typing import Optional

from .constants import (
    PK_PREFIX_CATALOG,
    SK_META,
)
from . import dynamo_client

logger = logging.getLogger(__name__)

# In-memory cache loaded at cold start
_catalog_cache: dict[str, dict] = {}


def _load_catalog_from_dynamo() -> dict[str, dict]:
    """Load the full catalog from DynamoDB."""
    items = dynamo_client.scan(
        filter_expression=None,
        index_name="GSI1",
    )
    catalog = {}
    for item in items:
        iid = item.get("ingredient_id", "")
        if iid:
            catalog[iid] = item
    return catalog


def load_catalog() -> dict[str, dict]:
    """Load catalog into memory (call at cold start)."""
    global _catalog_cache
    if not _catalog_cache:
        _catalog_cache = _load_catalog_from_dynamo()
        logger.info("Loaded %d catalog items", len(_catalog_cache))
    return _catalog_cache


def get_catalog_item(ingredient_id: str) -> Optional[dict]:
    """Get a single catalog entry by ID."""
    catalog = load_catalog()
    return catalog.get(ingredient_id)


def get_shelf_life(ingredient_id: str) -> int:
    """Get shelf life in days for an ingredient. Default: 7 days."""
    item = get_catalog_item(ingredient_id)
    if item:
        return int(item.get("shelf_life_days", 7))
    return 7


def get_macros_per_100g(ingredient_id: str) -> dict[str, float]:
    """Get IFCT nutrition macros per 100g. Returns zeros if not found."""
    item = get_catalog_item(ingredient_id)
    if item:
        return item.get("ifct_macros_per_100g", {
            "calories": 0, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0,
        })
    return {
        "calories": 0, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0,
    }


def get_canonical_name(ingredient_id: str) -> str:
    """Get human-readable name for an ingredient."""
    item = get_catalog_item(ingredient_id)
    if item:
        return item.get("canonical_name", ingredient_id)
    return ingredient_id.replace("_", " ").title()


def get_all_aliases() -> dict[str, str]:
    """Build a mapping from alias → canonical ingredient_id."""
    catalog = load_catalog()
    alias_map = {}
    for iid, item in catalog.items():
        for alias in item.get("aliases", []):
            alias_map[alias.lower().strip()] = iid
    return alias_map


def search_by_name(name: str) -> Optional[str]:
    """Find ingredient_id by name or alias."""
    alias_map = get_all_aliases()
    normalized = name.lower().strip()

    # Direct alias match
    if normalized in alias_map:
        return alias_map[normalized]

    # Partial match
    catalog = load_catalog()
    for iid, item in catalog.items():
        canonical = item.get("canonical_name", "").lower()
        if normalized in canonical or canonical in normalized:
            return iid
        for alias in item.get("aliases", []):
            if normalized in alias or alias in normalized:
                return iid

    return None


def get_all_ingredient_ids() -> list[str]:
    """Return all valid ingredient IDs from the catalog."""
    catalog = load_catalog()
    return list(catalog.keys())


def get_catalog_for_prompt() -> str:
    """Return a compact catalog string for Bedrock prompts.

    Lists ingredient_id and canonical_name, suitable for including
    in LLM prompts to constrain output.
    """
    catalog = load_catalog()
    lines = []
    for iid in sorted(catalog.keys()):
        item = catalog[iid]
        name = item.get("canonical_name", iid)
        lines.append(f"- {iid}: {name}")
    return "\n".join(lines)


# ============================================
# STATIC CATALOG (fallback / seed data)
# ============================================

STATIC_CATALOG: list[dict] = [
    {
        "ingredient_id": "tomato",
        "canonical_name": "Tomato",
        "aliases": ["tomatoes", "tamatar", "red tomato"],
        "shelf_life_days": 7,
        "category": "vegetable",
        "ifct_macros_per_100g": {
            "calories": 20, "protein": 0.9, "carbs": 3.9, "fat": 0.2, "fiber": 1.2,
        },
    },
    {
        "ingredient_id": "onion",
        "canonical_name": "Onion",
        "aliases": ["onions", "pyaaz", "pyaj"],
        "shelf_life_days": 21,
        "category": "vegetable",
        "ifct_macros_per_100g": {
            "calories": 40, "protein": 1.1, "carbs": 9.3, "fat": 0.1, "fiber": 1.7,
        },
    },
    {
        "ingredient_id": "potato",
        "canonical_name": "Potato",
        "aliases": ["potatoes", "aloo", "batata"],
        "shelf_life_days": 21,
        "category": "vegetable",
        "ifct_macros_per_100g": {
            "calories": 77, "protein": 2.0, "carbs": 17.5, "fat": 0.1, "fiber": 2.2,
        },
    },
    {
        "ingredient_id": "rice",
        "canonical_name": "Rice",
        "aliases": ["white rice", "basmati", "chawal", "chaval"],
        "shelf_life_days": 365,
        "category": "grain",
        "ifct_macros_per_100g": {
            "calories": 130, "protein": 2.7, "carbs": 28.2, "fat": 0.3, "fiber": 0.4,
        },
    },
    {
        "ingredient_id": "wheat_flour",
        "canonical_name": "Wheat Flour",
        "aliases": ["atta", "aata", "maida", "plain flour", "wheat flour"],
        "shelf_life_days": 180,
        "category": "grain",
        "ifct_macros_per_100g": {
            "calories": 364, "protein": 10.7, "carbs": 76.3, "fat": 1.0, "fiber": 2.7,
        },
    },
    {
        "ingredient_id": "milk",
        "canonical_name": "Milk",
        "aliases": ["doodh", "cow milk", "toned milk"],
        "shelf_life_days": 5,
        "category": "dairy",
        "ifct_macros_per_100g": {
            "calories": 61, "protein": 3.2, "carbs": 4.8, "fat": 3.4, "fiber": 0,
        },
    },
    {
        "ingredient_id": "ghee",
        "canonical_name": "Ghee",
        "aliases": ["clarified butter", "desi ghee"],
        "shelf_life_days": 180,
        "category": "fat",
        "ifct_macros_per_100g": {
            "calories": 883, "protein": 0, "carbs": 0, "fat": 99.5, "fiber": 0,
        },
    },
    {
        "ingredient_id": "chicken_breast",
        "canonical_name": "Chicken Breast",
        "aliases": ["chicken", "murgh", "murgi"],
        "shelf_life_days": 3,
        "category": "meat",
        "ifct_macros_per_100g": {
            "calories": 165, "protein": 31.0, "carbs": 0, "fat": 3.6, "fiber": 0,
        },
    },
    {
        "ingredient_id": "paneer",
        "canonical_name": "Paneer",
        "aliases": ["cottage cheese", "cottage cheese paneer"],
        "shelf_life_days": 5,
        "category": "dairy",
        "ifct_macros_per_100g": {
            "calories": 265, "protein": 18.3, "carbs": 3.5, "fat": 20.0, "fiber": 0,
        },
    },
    {
        "ingredient_id": "moong_dal",
        "canonical_name": "Moong Dal",
        "aliases": ["moong", "green gram", "mung bean"],
        "shelf_life_days": 365,
        "category": "pulse",
        "ifct_macros_per_100g": {
            "calories": 347, "protein": 24.5, "carbs": 62.9, "fat": 1.2, "fiber": 9.8,
        },
    },
    {
        "ingredient_id": "turmeric",
        "canonical_name": "Turmeric",
        "aliases": ["haldi", "turmeric powder"],
        "shelf_life_days": 730,
        "category": "spice",
        "ifct_macros_per_100g": {
            "calories": 354, "protein": 7.8, "carbs": 64.9, "fat": 9.9, "fiber": 21.1,
        },
    },
    {
        "ingredient_id": "coriander",
        "canonical_name": "Coriander",
        "aliases": ["dhania", "coriander leaves", "cilantro", "dhaniya"],
        "shelf_life_days": 5,
        "category": "herb",
        "ifct_macros_per_100g": {
            "calories": 23, "protein": 2.1, "carbs": 3.7, "fat": 0.5, "fiber": 2.8,
        },
    },
    {
        "ingredient_id": "green_chilli",
        "canonical_name": "Green Chilli",
        "aliases": ["chilli", "hari mirch", "green chili", "green peppers"],
        "shelf_life_days": 10,
        "category": "vegetable",
        "ifct_macros_per_100g": {
            "calories": 40, "protein": 2.0, "carbs": 7.3, "fat": 0.2, "fiber": 1.5,
        },
    },
    {
        "ingredient_id": "ginger",
        "canonical_name": "Ginger",
        "aliases": ["adrak", "fresh ginger", "ginger root"],
        "shelf_life_days": 14,
        "category": "spice",
        "ifct_macros_per_100g": {
            "calories": 80, "protein": 1.8, "carbs": 17.8, "fat": 0.8, "fiber": 2.0,
        },
    },
    {
        "ingredient_id": "garlic",
        "canonical_name": "Garlic",
        "aliases": ["lahsun", "lahsan", "garlic cloves"],
        "shelf_life_days": 60,
        "category": "spice",
        "ifct_macros_per_100g": {
            "calories": 149, "protein": 6.4, "carbs": 33.1, "fat": 0.5, "fiber": 2.1,
        },
    },
    {
        "ingredient_id": "oil",
        "canonical_name": "Cooking Oil",
        "aliases": ["oil", "vegetable oil", "mustard oil", "sunflower oil", "refined oil"],
        "shelf_life_days": 365,
        "category": "fat",
        "ifct_macros_per_100g": {
            "calories": 884, "protein": 0, "carbs": 0, "fat": 100, "fiber": 0,
        },
    },
    {
        "ingredient_id": "sugar",
        "canonical_name": "Sugar",
        "aliases": ["cheeni", "white sugar", "granulated sugar"],
        "shelf_life_days": 365,
        "category": "sweetener",
        "ifct_macros_per_100g": {
            "calories": 387, "protein": 0, "carbs": 100, "fat": 0, "fiber": 0,
        },
    },
    {
        "ingredient_id": "salt",
        "canonical_name": "Salt",
        "aliases": ["namak", "table salt", "rock salt"],
        "shelf_life_days": 1825,
        "category": "spice",
        "ifct_macros_per_100g": {
            "calories": 0, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0,
        },
    },
    {
        "ingredient_id": "egg",
        "canonical_name": "Egg",
        "aliases": ["eggs", "anda", "chicken egg"],
        "shelf_life_days": 21,
        "category": "protein",
        "ifct_macros_per_100g": {
            "calories": 155, "protein": 12.6, "carbs": 1.1, "fat": 10.6, "fiber": 0,
        },
    },
    {
        "ingredient_id": "banana",
        "canonical_name": "Banana",
        "aliases": ["bananas", "kela", "kela ke phal"],
        "shelf_life_days": 5,
        "category": "fruit",
        "ifct_macros_per_100g": {
            "calories": 89, "protein": 1.1, "carbs": 22.8, "fat": 0.3, "fiber": 2.6,
        },
    },
]
