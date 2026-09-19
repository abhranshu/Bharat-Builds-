"""Live Bedrock connectivity check for UseItUp (Amazon Nova 2 Lite).

Runs four checks against the real Bedrock Runtime, in increasing order of
how much of the application they exercise:

  1. Raw boto3 Converse call      -> records latency + token usage
  2. Project client, text mode    -> invoke_bedrock(force_json=False)
  3. Project client, JSON mode    -> invoke_bedrock(force_json=True)
  4. Project client, vision mode  -> invoke_bedrock_vision(<jpeg>)   [optional]

Usage:
    cd UseItUp/backend
    .venv/Scripts/python scripts/check_bedrock.py [path/to/image.jpg]

Notes:
    * Output is deliberately tiny (maxTokens capped) so a run costs a
      fraction of a cent.
    * Credentials are read from the standard AWS chain; nothing is printed.
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from src.shared import constants
from src.shared.bedrock_client import invoke_bedrock, invoke_bedrock_vision

REGION = constants.BEDROCK_REGION
MODEL_ID = constants.BEDROCK_MODEL_ID
PROMPT = "Return exactly one sentence saying hello."


def _header(title: str) -> None:
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)


def _text_from(response: dict) -> str:
    blocks = response.get("output", {}).get("message", {}).get("content", [])
    return "\n".join(b["text"] for b in blocks if "text" in b).strip()


def check_raw_converse() -> None:
    """Check 1 — direct boto3 Converse, with latency and token usage."""
    _header("1. Raw boto3 Converse (latency + token usage)")
    print(f"region  : {REGION}")
    print(f"modelId : {MODEL_ID}")

    client = boto3.client("bedrock-runtime", region_name=REGION)
    started = time.perf_counter()
    response = client.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": PROMPT}]}],
        inferenceConfig={"maxTokens": 64, "temperature": 0.2},
    )
    elapsed = time.perf_counter() - started

    usage = response.get("usage", {})
    metrics = response.get("metrics", {})

    print(f"stopReason: {response.get('stopReason')}")
    print(f"latency   : {elapsed:.2f}s (service-reported {metrics.get('latencyMs')} ms)")
    print(
        "tokens    : "
        f"input={usage.get('inputTokens')} "
        f"output={usage.get('outputTokens')} "
        f"total={usage.get('totalTokens')}"
    )
    print(f"response  : {_text_from(response)}")


def check_app_text() -> None:
    """Check 2 — the project's text entry point, raw text mode."""
    _header("2. Project client — invoke_bedrock(force_json=False)")
    text = invoke_bedrock(PROMPT, force_json=False, max_tokens=64)
    print(f"response  : {text}")


def check_app_json() -> None:
    """Check 3 — the project's JSON path (parsing + retry logic)."""
    _header("3. Project client — invoke_bedrock(force_json=True)")
    result = invoke_bedrock(
        'Return a JSON array with exactly one object: {"status": "ok"}',
        max_tokens=128,
    )
    print(f"parsed    : {result!r} (type={type(result).__name__})")


def check_app_vision(image_path: str) -> None:
    """Check 4 — the project's multimodal path with a real JPEG."""
    _header("4. Project client — invoke_bedrock_vision (real image)")
    with open(image_path, "rb") as handle:
        image_bytes = handle.read()
    print(f"image     : {image_path} ({len(image_bytes)} bytes)")

    started = time.perf_counter()
    result = invoke_bedrock_vision(
        image_bytes=image_bytes,
        image_format="jpeg",
        prompt=(
            "List the main objects visible in this image as a JSON array of "
            'strings, e.g. ["fridge", "shelf"]. Reply with JSON only.'
        ),
        max_tokens=256,
    )
    elapsed = time.perf_counter() - started
    print(f"latency   : {elapsed:.2f}s")
    print(f"parsed    : {result!r}")


def main() -> int:
    image_path = sys.argv[1] if len(sys.argv) > 1 else None

    checks: list[tuple[str, callable]] = [
        ("raw converse", check_raw_converse),
        ("app text", check_app_text),
        ("app json", check_app_json),
    ]
    if image_path:
        checks.append(("app vision", lambda: check_app_vision(image_path)))
    else:
        print("\n[skip] No image path given — vision check not run.")

    results: dict[str, str] = {}

    for name, fn in checks:
        try:
            fn()
            results[name] = "PASS"
        except ClientError as exc:
            error = exc.response.get("Error", {})
            code = error.get("Code", "Unknown")
            print(f"\nFAILED: {code} — {error.get('Message', '')}")
            results[name] = f"FAIL ({code})"
        except BotoCoreError as exc:
            print(f"\nFAILED: boto3 error — {exc}")
            results[name] = "FAIL (boto3)"
        except Exception as exc:  # diagnostic script: report everything
            print(f"\nFAILED: {type(exc).__name__} — {exc}")
            results[name] = f"FAIL ({type(exc).__name__})"

    _header("Summary")
    print(f"region  : {REGION}")
    print(f"modelId : {MODEL_ID}")
    for name, status in results.items():
        print(f"  {name:<14} {status}")

    return 0 if all(v == "PASS" for v in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
