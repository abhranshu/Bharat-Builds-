"""Expiry date prediction logic.

Computes predicted expiry date from purchase date + catalog shelf life.
Supports confidence levels based on whether the source is a bill (high)
or a fridge photo (estimated).
"""

from __future__ import annotations

from datetime import date, timedelta

from .ingredient_catalog import get_shelf_life


def predict_expiry(
    ingredient_id: str,
    purchase_date: date,
    source: str = "bill",
) -> tuple[date, str]:
    """Predict expiry date for an ingredient.

    Args:
        ingredient_id: Canonical ingredient ID from catalog.
        purchase_date: Date the item was purchased (or photo date).
        source: "bill" for high-confidence, "fridge_photo" for estimated.

    Returns:
        Tuple of (predicted_expiry_date, confidence_level).
        confidence_level is "high" for bills, "estimated" for photos.
    """
    shelf_life_days = get_shelf_life(ingredient_id)

    # For fridge photos, we don't know when it was purchased,
    # so apply a conservative 70% discount to shelf life
    if source == "fridge_photo":
        shelf_life_days = int(shelf_life_days * 0.7)
        confidence = "estimated"
    else:
        confidence = "high"

    predicted = purchase_date + timedelta(days=shelf_life_days)

    return predicted, confidence


def days_until_expiry(predicted_expiry: date, reference_date: date | None = None) -> int:
    """Calculate days remaining until expiry.

    Args:
        predicted_expiry: The predicted expiry date.
        reference_date: Date to compare against (defaults to today).

    Returns:
        Number of days until expiry. Negative if already past.
    """
    if reference_date is None:
        reference_date = date.today()

    return (predicted_expiry - reference_date).days


def expiry_status_label(predicted_expiry: date, reference_date: date | None = None) -> str:
    """Return a human-readable expiry status.

    Returns one of: "expired", "urgent", "warning", "fresh".
    """
    days = days_until_expiry(predicted_expiry, reference_date)

    if days < 0:
        return "expired"
    elif days <= 1:
        return "urgent"
    elif days <= 3:
        return "warning"
    else:
        return "fresh"


def is_expiring_soon(
    predicted_expiry: date,
    within_days: int = 2,
    reference_date: date | None = None,
) -> bool:
    """Check if an item is expiring within N days."""
    days = days_until_expiry(predicted_expiry, reference_date)
    return 0 <= days <= within_days
