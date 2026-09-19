"""Bedrock client for invoke_model calls.

Handles prompt templates, JSON response parsing, and retry logic
for Claude model invocations via Amazon Bedrock.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import boto3

from .constants import BEDROCK_MODEL_ID, BEDROCK_REGION

logger = logging.getLogger(__name__)

_bedrock = boto3.client(
    "bedrock-runtime",
    region_name=BEDROCK_REGION,
)

# Max retry attempts for malformed responses
_MAX_RETRIES = 1


def invoke_claude(
    prompt: str,
    system_prompt: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    """Invoke Claude and return the raw text response."""
    messages = [{"role": "user", "content": prompt}]

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }

    if system_prompt:
        body["system"] = system_prompt

    resp = _bedrock.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )

    result = json.loads(resp["body"].read())

    # Extract text content from Claude response
    content_blocks = result.get("content", [])
    text_parts = []
    for block in content_blocks:
        if block.get("type") == "text":
            text_parts.append(block["text"])

    return "\n".join(text_parts)


def invoke_claude_json(
    prompt: str,
    system_prompt: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.2,
    retries: int = _MAX_RETRIES,
) -> dict[str, Any]:
    """Invoke Claude with strict JSON output parsing.

    Retries once with a stricter prompt reminder if JSON parsing fails.
    """
    strict_system = (
        (system_prompt + "\n" if system_prompt else "")
        + "You MUST respond with valid JSON only. "
        "No markdown, no explanation, no code fences. "
        "Just the raw JSON object or array."
    )

    for attempt in range(1 + retries):
        raw_text = invoke_claude(
            prompt=prompt,
            system_prompt=strict_system,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        try:
            # Strip markdown code fences if present
            cleaned = raw_text.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                # Remove first and last lines (fences)
                lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned = "\n".join(lines)

            return json.loads(cleaned)

        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "JSON parse failed (attempt %d/%d): %s. Raw: %.200s",
                attempt + 1,
                1 + retries,
                exc,
                raw_text,
            )
            if attempt < retries:
                prompt = (
                    prompt
                    + "\n\nIMPORTANT: Your previous response was not valid JSON. "
                    "Please respond with ONLY valid JSON."
                )
                continue

            raise ValueError(
                f"Failed to parse Claude response as JSON after {1 + retries} "
                f"attempts. Last response: {raw_text[:500]}"
            ) from exc


def invoke_claude_vision(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    prompt: str = "Identify all food items in this image.",
    system_prompt: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.2,
    retries: int = _MAX_RETRIES,
) -> dict[str, Any]:
    """Invoke Claude with an image input for vision tasks.

    Returns parsed JSON from the model's response.
    """
    import base64

    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    vision_prompt = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": image_b64,
            },
        },
        {
            "type": "text",
            "text": prompt,
        },
    ]

    messages = [{"role": "user", "content": vision_prompt}]

    strict_system = (
        (system_prompt + "\n" if system_prompt else "")
        + "Respond with valid JSON only. No markdown, no explanation."
    )

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
        "system": strict_system,
    }

    for attempt in range(1 + retries):
        resp = _bedrock.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )

        result = json.loads(resp["body"].read())
        content_blocks = result.get("content", [])
        text_parts = [
            b["text"] for b in content_blocks if b.get("type") == "text"
        ]
        raw_text = "\n".join(text_parts)

        try:
            cleaned = raw_text.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned = "\n".join(lines)

            return json.loads(cleaned)

        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "Vision JSON parse failed (attempt %d/%d): %s",
                attempt + 1,
                1 + retries,
                exc,
            )
            if attempt < retries:
                continue

            raise ValueError(
                f"Failed to parse vision response as JSON: {raw_text[:500]}"
            ) from exc
