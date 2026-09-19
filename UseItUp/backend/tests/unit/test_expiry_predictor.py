"""Unit tests for expiry date prediction."""

from datetime import date, timedelta

import pytest

from src.shared.expiry_predictor import (
    predict_expiry,
    days_until_expiry,
    expiry_status_label,
    is_expiring_soon,
)


class TestPredictExpiry:
    """Tests for predict_expiry function."""

    def test_bill_source_high_confidence(self):
        """Bill source should give full shelf life with high confidence."""
        purchase = date(2025, 1, 1)
        predicted, confidence = predict_expiry("tomato", purchase, source="bill")

        # Tomato shelf_life_days = 7
        assert predicted == date(2025, 1, 8)
        assert confidence == "high"

    def test_fridge_photo_source_estimated(self):
        """Fridge photo should give 70% shelf life with estimated confidence."""
        purchase = date(2025, 1, 1)
        predicted, confidence = predict_expiry("tomato", purchase, source="fridge_photo")

        # Tomato shelf_life_days = 7, 70% = 4.9 → int(4.9) = 4
        assert predicted == date(2025, 1, 5)
        assert confidence == "estimated"

    def test_long_shelf_life_item(self):
        """Rice (365 days) should have appropriate expiry."""
        purchase = date(2025, 1, 1)
        predicted, confidence = predict_expiry("rice", purchase, source="bill")

        assert predicted == date(2025, 12, 31) or predicted == date(2026, 1, 1)
        assert confidence == "high"

    def test_unknown_ingredient_defaults(self):
        """Unknown ingredient should default to 7 days shelf life."""
        purchase = date(2025, 6, 1)
        predicted, confidence = predict_expiry("unknown_food", purchase, source="bill")

        assert predicted == date(2025, 6, 8)
        assert confidence == "high"


class TestDaysUntilExpiry:
    """Tests for days_until_expiry function."""

    def test_future_date(self):
        today = date(2025, 1, 10)
        expiry = date(2025, 1, 15)
        assert days_until_expiry(expiry, today) == 5

    def test_past_date(self):
        today = date(2025, 1, 20)
        expiry = date(2025, 1, 15)
        assert days_until_expiry(expiry, today) == -5

    def test_today(self):
        today = date(2025, 1, 15)
        expiry = date(2025, 1, 15)
        assert days_until_expiry(expiry, today) == 0


class TestExpiryStatusLabel:
    """Tests for expiry_status_label function."""

    def test_expired(self):
        today = date(2025, 1, 20)
        expiry = date(2025, 1, 15)
        assert expiry_status_label(expiry, today) == "expired"

    def test_urgent(self):
        today = date(2025, 1, 14)
        expiry = date(2025, 1, 15)
        assert expiry_status_label(expiry, today) == "urgent"

    def test_warning(self):
        today = date(2025, 1, 12)
        expiry = date(2025, 1, 15)
        assert expiry_status_label(expiry, today) == "warning"

    def test_fresh(self):
        today = date(2025, 1, 10)
        expiry = date(2025, 1, 15)
        assert expiry_status_label(expiry, today) == "fresh"


class TestIsExpiringSoon:
    """Tests for is_expiring_soon function."""

    def test_expiring_tomorrow(self):
        today = date(2025, 1, 14)
        expiry = date(2025, 1, 15)
        assert is_expiring_soon(expiry, within_days=2, reference_date=today) is True

    def test_expiring_in_5_days(self):
        today = date(2025, 1, 10)
        expiry = date(2025, 1, 15)
        assert is_expiring_soon(expiry, within_days=2, reference_date=today) is False

    def test_already_expired(self):
        today = date(2025, 1, 20)
        expiry = date(2025, 1, 15)
        assert is_expiring_soon(expiry, within_days=2, reference_date=today) is False
