"""Textract client for AnalyzeExpense API calls.

Handles grocery bill/receipt parsing with structured output.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import boto3

from .constants import TEXTRACT_REGION

logger = logging.getLogger(__name__)

_textract = boto3.client(
    "textract",
    region_name=TEXTRACT_REGION,
)


class TextractExpenseItem:
    """Parsed line item from a receipt."""

    def __init__(
        self,
        name: str,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        unit_price: Optional[float] = None,
    ):
        self.name = name
        self.quantity = quantity
        self.price = price
        self.unit_price = unit_price

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"name": self.name}
        if self.quantity is not None:
            result["quantity"] = self.quantity
        if self.price is not None:
            result["price"] = self.price
        if self.unit_price is not None:
            result["unit_price"] = self.unit_price
        return result


class TextractExpenseResult:
    """Full parsed result from Textract AnalyzeExpense."""

    def __init__(
        self,
        vendor: Optional[str] = None,
        transaction_date: Optional[str] = None,
        total: Optional[float] = None,
        items: Optional[list[TextractExpenseItem]] = None,
        raw_blocks: Optional[list[dict]] = None,
    ):
        self.vendor = vendor
        self.transaction_date = transaction_date
        self.total = total
        self.items = items or []
        self.raw_blocks = raw_blocks or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "vendor": self.vendor,
            "transaction_date": self.transaction_date,
            "total": self.total,
            "items": [item.to_dict() for item in self.items],
        }


def analyze_expense(image_bytes: bytes) -> TextractExpenseResult:
    """Analyze a grocery receipt/bill image using Textract.

    Args:
        image_bytes: Raw image bytes (JPEG/PNG).

    Returns:
        Parsed expense result with line items, vendor, date, and total.

    Raises:
        ValueError: If the image doesn't appear to be a receipt.
    """
    import base64

    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    resp = _textract.analyze_expense(
        Document={"Bytes": image_bytes},
        FeatureTypes=["FORMS", "TABLES"],
    )

    documents = resp.get("ExpenseDocuments", [])

    if not documents:
        raise ValueError(
            "Textract could not detect any receipt/bill content. "
            "Please ensure you're uploading a clear photo of a grocery bill."
        )

    result = TextractExpenseResult(raw_blocks=resp.get("Blocks", []))

    # Extract summary fields
    summary_fields = documents[0].get("SummaryFields", [])
    for field in summary_fields:
        field_type = field.get("Type", {}).get("Text", "")
        field_value = field.get("ValueDetection", {}).get("Text", "")

        if field_type in ("VENDOR_NAME", "RECEIVER_NAME"):
            result.vendor = field_value
        elif field_type == "INVOICE_DATE":
            result.transaction_date = field_value
        elif field_type == "TOTAL":
            try:
                result.total = float(
                    field_value.replace(",", "").replace("₹", "").strip()
                )
            except (ValueError, AttributeError):
                pass

    # Extract line items
    line_item_groups = documents[0].get("LineItemGroups", [])
    for group in line_item_groups:
        for line_item in group.get("LineItems", []):
            fields = line_item.get("LineItemExpenseFields", [])
            name = ""
            quantity = None
            price = None
            unit_price = None

            for field in fields:
                field_type = field.get("Type", {}).get("Text", "")
                field_value = field.get("ValueDetection", {}).get("Text", "")

                if field_type in (
                    "ITEM",
                    "PRODUCT_NAME",
                    "DESCRIPTION",
                    "OTHER",
                ):
                    if not name:
                        name = field_value
                elif field_type == "QUANTITY":
                    try:
                        quantity = float(field_value)
                    except (ValueError, AttributeError):
                        pass
                elif field_type == "PRICE":
                    try:
                        price = float(
                            field_value.replace(",", "")
                            .replace("₹", "")
                            .strip()
                        )
                    except (ValueError, AttributeError):
                        pass
                elif field_type == "UNIT_PRICE":
                    try:
                        unit_price = float(
                            field_value.replace(",", "")
                            .replace("₹", "")
                            .strip()
                        )
                    except (ValueError, AttributeError):
                        pass

            if name:
                result.items.append(
                    TextractExpenseItem(
                        name=name,
                        quantity=quantity,
                        price=price,
                        unit_price=unit_price,
                    )
                )

    if not result.items:
        raise ValueError(
            "Textract found a receipt but could not extract any line items. "
            "The image may be too blurry or the format is unsupported."
        )

    logger.info(
        "Textract extracted %d items from bill", len(result.items)
    )
    return result
