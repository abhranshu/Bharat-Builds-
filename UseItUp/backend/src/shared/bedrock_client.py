"""Bedrock client built on the Bedrock Runtime Converse API.

Backed by Amazon Nova 2 Lite (``BEDROCK_MODEL_ID``), a multimodal model that
accepts text and images. The Converse API provides a single request/response
shape across models, so no model-specific request bodies are constructed here.

Two entry points are exposed to the Lambda functions:

* :func:`invoke_bedrock` — text in, JSON (or raw text) out.
* :func:`invoke_bedrock_vision` — image + text in, JSON out.

JSON output is not trusted blindly: the response is parsed and, on failure, the
model is retried once with a stricter reminder.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import boto3

from . import constants

logger = logging.getLogger(__name__)

_bedrock = boto3.client("bedrock-runtime", region_name=constants.BEDROCK_REGION)

# Responses only need to carry a small JSON payload (a list of recipes or
# normalized bill items), so keep generation short and cheap instead of using
# the model's much larger output ceiling. Reasoning is disabled by default on
# Nova 2, so these budgets are not consumed by thinking tokens.
DEFAULT_MAX_TOKENS = 2048
VISION_MAX_TOKENS = 1024
DEFAULT_TEMPERATURE = 0.2

# Converse accepts inline image bytes up to ~3.75 MB. Anything larger is
# rejected by the service, so fail fast with a clear message instead.
MAX_IMAGE_BYTES = 3_750_000

# One retry with a stricter reminder when the first response isn't valid JSON.
_MAX_RETRIES = 1

_JSON_ONLY_INSTRUCTION = (
    "You MUST respond with valid JSON only. No markdown, no explanation, "
    "no code fences. Just the raw JSON object or array."
)
_JSON_RETRY_REMINDER = (
    "\n\nYour previous response was not valid JSON. Respond with ONLY valid "
    "JSON, no prose and no markdown fences."
)


# ============================================
# INTERNALS
# ============================================

def _model_id() -> str:
    """Resolve the model / inference profile ID at call time.

    The value comes from the ``BEDROCK_MODEL_ID`` Lambda environment variable
    (see ``shared/constants.py``); it is never hardcoded at the call sites.
    """
    return constants.BEDROCK_MODEL_ID


def _extract_text(response: dict[str, Any]) -> str:
    """Pull the assistant's text out of a Converse response."""
    content = response.get("output", {}).get("message", {}).get("content", [])
    parts = [block["text"] for block in content if "text" in block]
    return "\n".join(parts).strip()


def _converse(
    messages: list[dict[str, Any]],
    system_prompt: str = "",
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> str:
    """Call the Converse API and return the assistant's text."""
    request: dict[str, Any] = {
        "modelId": _model_id(),
        "messages": messages,
        "inferenceConfig": {
            "maxTokens": max_tokens,
            "temperature": temperature,
        },
    }
    if system_prompt:
        request["system"] = [{"text": system_prompt}]

    response = _bedrock.converse(**request)
    return _extract_text(response)


def _parse_json(raw_text: str) -> Any:
    """Parse model output as JSON, tolerating code fences or stray prose."""
    cleaned = raw_text.strip()

    # Strip a ```json ... ``` fence if the model added one anyway.
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fall back to the outermost array/object if there is surrounding prose.
    for opener, closer in (("[", "]"), ("{", "}")):
        start = cleaned.find(opener)
        end = cleaned.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                continue

    raise ValueError(f"no JSON value found in response: {cleaned[:200]}")


def _normalize_image_format(image_format: str) -> str:
    """Map ``image/jpeg`` / ``jpg`` style values to Converse format names."""
    fmt = (image_format or "").lower().split("/")[-1].strip()
    if fmt in ("jpg", "jpeg"):
        return "jpeg"
    if fmt in ("png", "gif", "webp"):
        return fmt
    return "jpeg"


def _strict_system(system_prompt: str) -> str:
    """Combine a caller system prompt with the JSON-only instruction."""
    return "\n".join(p for p in (system_prompt, _JSON_ONLY_INSTRUCTION) if p)


def _with_json_retry(messages, call, describe: str) -> Any:
    """Run ``call``, retrying once with a stricter prompt on bad JSON."""
    attempts = 1 + _MAX_RETRIES
    current_messages = messages

    for attempt in range(attempts):
        raw_text = call(current_messages)
        try:
            return _parse_json(raw_text)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "Bedrock JSON parse failed (attempt %d/%d): %s. Raw: %.200s",
                attempt + 1,
                attempts,
                exc,
                raw_text,
            )
            if attempt < _MAX_RETRIES:
                current_messages = _append_retry_reminder(messages)
                continue

            raise ValueError(
                f"Failed to parse Bedrock response as JSON after {attempts} "
                f"attempts ({describe}). Last response: {raw_text[:500]}"
            ) from exc

    # Unreachable: the loop either returns or raises.
    raise ValueError(f"Failed to obtain JSON from Bedrock ({describe}).")


def _append_retry_reminder(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a copy of ``messages`` with the JSON reminder appended to text."""
    remined: list[dict[str, Any]] = []
    for message in messages:
        content = []
        for block in message.get("content", []):
            if "text" in block:
                content.append({"text": block["text"] + _JSON_RETRY_REMINDER})
            else:
                content.append(dict(block))
        remined.append({**message, "content": content})
    return remined


# ============================================
# PUBLIC API
# ============================================

def invoke_bedrock(
    prompt: str,
    force_json: bool = True,
    system_prompt: str = "",
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> Any:
    """Invoke Nova 2 Lite with a text prompt.

    Args:
        prompt: The user prompt.
        force_json: When True (default) a system prompt enforcing JSON-only
            output is applied, the response is parsed, and a single stricter
            retry is attempted if parsing fails. When False, the raw text is
            returned instead.
        system_prompt: Optional extra system instructions.
        max_tokens: Maximum tokens to generate (kept deliberately small).
        temperature: Sampling temperature.

    Returns:
        Parsed JSON (dict/list) when ``force_json`` is True, else the raw
        response text.
    """
    messages = [{"role": "user", "content": [{"text": prompt}]}]

    if not force_json:
        return _converse(
            messages,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    strict_system = _strict_system(system_prompt)
    return _with_json_retry(
        messages,
        call=lambda msgs: _converse(
            msgs,
            system_prompt=strict_system,
            max_tokens=max_tokens,
            temperature=temperature,
        ),
        describe="text",
    )


def invoke_bedrock_vision(
    image_bytes: bytes,
    prompt: str = "Identify all food items in this image.",
    image_format: str = "jpeg",
    force_json: bool = True,
    system_prompt: str = "",
    max_tokens: int = VISION_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> Any:
    """Invoke Nova 2 Lite with a multimodal (image + text) prompt.

    The image is sent inline as raw bytes using the Converse image content
    block, which is what Nova 2 Lite expects for multimodal input.

    Args:
        image_bytes: Raw JPEG/PNG image bytes.
        prompt: Text instructions describing what to extract.
        image_format: Image format (``"jpeg"``, ``"image/jpeg"``, ``"png"``...).
        force_json: When True (default), parse JSON and retry once on failure.
        system_prompt: Optional extra system instructions.
        max_tokens: Maximum tokens to generate.
        temperature: Sampling temperature.

    Returns:
        Parsed JSON (dict/list) when ``force_json`` is True, else raw text.
    """
    if not image_bytes:
        raise ValueError("Cannot send an empty image to Bedrock.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError(
            f"Image is too large for the Converse API ({len(image_bytes)} bytes; "
            f"limit {MAX_IMAGE_BYTES}). Resize or re-compress before uploading."
        )

    image_block = {
        "image": {
            "format": _normalize_image_format(image_format),
            "source": {"bytes": image_bytes},
        }
    }
    messages = [{"role": "user", "content": [image_block, {"text": prompt}]}]

    if not force_json:
        return _converse(
            messages,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    strict_system = _strict_system(system_prompt)
    return _with_json_retry(
        messages,
        call=lambda msgs: _converse(
            msgs,
            system_prompt=strict_system,
            max_tokens=max_tokens,
            temperature=temperature,
        ),
        describe="vision",
    )
