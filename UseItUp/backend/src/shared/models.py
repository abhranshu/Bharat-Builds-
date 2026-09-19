"""Pydantic models for request/response validation and data structures."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ============================================
# ENUMS
# ============================================

class UploadType(str, Enum):
    BILL = "bill"
    FRIDGE_PHOTO = "fridge_photo"


class UploadStatus(str, Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"


class DietType(str, Enum):
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    NON_VEGETARIAN = "non_vegetarian"
    EGGETARIAN = "eggetarian"
    JAIN = "jain"


class MealType(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


# ============================================
# INGREDIENT / ITEM MODELS
# ============================================

class Ingredient(BaseModel):
    """A single ingredient in the inventory."""
    ingredient_id: str = Field(..., description="Canonical ID from catalog")
    name: str = Field(..., description="Human-readable name")
    quantity_g: float = Field(..., ge=0, description="Quantity in grams")
    purchase_date: date = Field(..., description="Date purchased or photo date")
    predicted_expiry: date = Field(..., description="Predicted expiry date")
    source: UploadType = Field(..., description="How this was captured")
    expiry_confidence: str = Field(
        default="high",
        description="high (from bill) or estimated (from photo)",
    )


class IngredientUpsert(BaseModel):
    """Used when writing items to DynamoDB."""
    ingredient_id: str
    quantity_g: float = Field(ge=0)
    purchase_date: date
    predicted_expiry: date
    source: UploadType
    expiry_confidence: str = "high"


# ============================================
# CATALOG MODELS
# ============================================

class CatalogItem(BaseModel):
    """An entry in the ingredient catalog."""
    ingredient_id: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    shelf_life_days: int = Field(
        ..., description="Days from purchase to expected expiry"
    )
    category: str = Field(default="general")
    ifct_macros_per_100g: MacrosPer100g


class MacrosPer100g(BaseModel):
    """Nutritional macros per 100g from IFCT data."""
    calories: float = Field(ge=0, description="kcal")
    protein: float = Field(ge=0, description="grams")
    carbs: float = Field(ge=0, description="grams")
    fat: float = Field(ge=0, description="grams")
    fiber: float = Field(ge=0, description="grams")


# ============================================
# NUTRITION MODELS
# ============================================

class NutritionInfo(BaseModel):
    """Computed nutrition for a recipe or daily summary."""
    calories: float = 0.0
    protein: float = 0.0
    carbs: float = 0.0
    fat: float = 0.0
    fiber: float = 0.0


class RecipeIngredient(BaseModel):
    """An ingredient used in a recipe."""
    ingredient_id: str
    name: str
    grams: float = Field(ge=0)


class Recipe(BaseModel):
    """A generated recipe."""
    name: str
    ingredients: list[RecipeIngredient]
    steps: list[str]
    prep_time_minutes: int
    servings: int = 2
    nutrition_per_serving: NutritionInfo = Field(default_factory=NutritionInfo)
    reason: str = Field(
        default="",
        description="Why this recipe was suggested",
    )


# ============================================
# PROFILE MODELS
# ============================================

class HouseholdProfile(BaseModel):
    """Household profile with diet and nutrition targets."""
    diet_type: DietType = Field(default=DietType.VEGETARIAN)
    household_size: int = Field(default=4, ge=1, le=20)
    language: str = Field(default="en")
    daily_calorie_target: float = Field(default=2000.0, ge=500, le=10000)
    daily_protein_target: float = Field(default=60.0, ge=10, le=500)


# ============================================
# COOKED RECORD MODELS
# ============================================

class CookedRecord(BaseModel):
    """A record of a meal that was cooked."""
    recipe_name: str
    ingredients_used: list[RecipeIngredient]
    nutrition_totals: NutritionInfo
    cooked_at: datetime


# ============================================
# UPLOAD MODELS
# ============================================

class UploadRecord(BaseModel):
    """Tracks the status of an uploaded image."""
    image_id: str
    status: UploadStatus = UploadStatus.PENDING
    upload_type: UploadType
    household_id: str
    raw_output: Optional[dict] = None


# ============================================
# API REQUEST / RESPONSE MODELS
# ============================================

class GetUploadUrlRequest(BaseModel):
    """Request to generate a presigned upload URL."""
    household_id: str = Field(..., min_length=1)
    upload_type: UploadType


class GetUploadUrlResponse(BaseModel):
    """Response with presigned URL and image ID."""
    upload_url: str
    image_id: str
    expires_in: int = Field(default=3600, description="URL TTL in seconds")


class GetInventoryResponse(BaseModel):
    """Response with household inventory."""
    household_id: str
    items: list[Ingredient]
    count: int


class MarkCookedRequest(BaseModel):
    """Request to mark a recipe as cooked."""
    household_id: str = Field(..., min_length=1)
    recipe: Recipe
    servings_cooked: int = Field(default=2, ge=1, le=20)


class MarkCookedResponse(BaseModel):
    """Response after marking cooked."""
    message: str
    updated_inventory: list[Ingredient]
    daily_nutrition: NutritionInfo


class GenerateRecipesRequest(BaseModel):
    """Request to generate recipes."""
    household_id: str = Field(..., min_length=1)
    meal_type: MealType = Field(default=MealType.LUNCH)
    prep_time_preference: int = Field(
        default=30, ge=5, le=120, description="Max prep time in minutes"
    )


class GenerateRecipesResponse(BaseModel):
    """Response with generated recipes."""
    household_id: str
    recipes: list[Recipe]
    nutrition_gap: NutritionInfo


class GetNutritionSummaryResponse(BaseModel):
    """Response with daily nutrition summary."""
    household_id: str
    date: date
    consumed: NutritionInfo
    targets: NutritionInfo
    remaining: NutritionInfo


class UpdateProfileRequest(BaseModel):
    """Request to update household profile."""
    household_id: str = Field(..., min_length=1)
    diet_type: Optional[DietType] = None
    household_size: Optional[int] = Field(default=None, ge=1, le=20)
    language: Optional[str] = None
    daily_calorie_target: Optional[float] = Field(default=None, ge=500)
    daily_protein_target: Optional[float] = Field(default=None, ge=10)


class UpdateProfileResponse(BaseModel):
    """Response after updating profile."""
    message: str
    profile: HouseholdProfile


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    status_code: int
