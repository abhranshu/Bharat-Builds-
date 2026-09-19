"""Unit tests for the Bedrock Converse client (Amazon Nova 2 Lite).

The boto3 client is replaced with a mock, so these run with no AWS access.
"""

from unittest.mock import MagicMock

import pytest

from src.shared import bedrock_client
from src.shared.constants import BEDROCK_MODEL_ID


def _response(text: str) -> dict:
    """Build a minimal Converse API response shape."""
    return {
        "output": {
            "message": {"role": "assistant", "content": [{"text": text}]}
        },
        "stopReason": "end_turn",
    }


@pytest.fixture
def mock_bedrock(monkeypatch):
    """Replace the module-level boto3 client with a MagicMock."""
    client = MagicMock()
    monkeypatch.setattr(bedrock_client, "_bedrock", client)
    return client


class TestModelConfiguration:
    def test_default_model_is_nova_2_lite(self):
        assert "nova-2-lite" in BEDROCK_MODEL_ID

    def test_model_id_is_injected_into_the_converse_call(self, mock_bedrock, monkeypatch):
        monkeypatch.setattr(
            bedrock_client.constants,
            "BEDROCK_MODEL_ID",
            "global.amazon.nova-2-lite-v1:0",
        )
        mock_bedrock.converse.return_value = _response('{"ok": true}')

        bedrock_client.invoke_bedrock("hello")

        assert mock_bedrock.converse.call_args.kwargs["modelId"] == (
            "global.amazon.nova-2-lite-v1:0"
        )

    def test_uses_converse_api_not_invoke_model(self, mock_bedrock):
        mock_bedrock.converse.return_value = _response("[]")

        bedrock_client.invoke_bedrock("hello")

        assert mock_bedrock.converse.called
        assert not mock_bedrock.invoke_model.called

    def test_max_tokens_is_bounded(self, mock_bedrock):
        mock_bedrock.converse.return_value = _response("[]")

        bedrock_client.invoke_bedrock("hello")

        config = mock_bedrock.converse.call_args.kwargs["inferenceConfig"]
        assert 0 < config["maxTokens"] <= 4096


class TestInvokeBedrock:
    def test_parses_json_array(self, mock_bedrock):
        mock_bedrock.converse.return_value = _response('[{"ingredient_id": "tomato"}]')

        assert bedrock_client.invoke_bedrock("hi") == [{"ingredient_id": "tomato"}]

    def test_parses_json_object(self, mock_bedrock):
        mock_bedrock.converse.return_value = _response('{"name": "Dal Tadka"}')

        assert bedrock_client.invoke_bedrock("hi") == {"name": "Dal Tadka"}

    def test_strips_markdown_code_fences(self, mock_bedrock):
        mock_bedrock.converse.return_value = _response(
            '```json\n{"ok": true}\n```'
        )

        assert bedrock_client.invoke_bedrock("hi") == {"ok": True}

    def test_survives_prose_around_json(self, mock_bedrock):
        mock_bedrock.converse.return_value = _response(
            'Here you go:\n[{"a": 1}]\nHope that helps!'
        )

        assert bedrock_client.invoke_bedrock("hi") == [{"a": 1}]

    def test_retries_once_with_stricter_reminder(self, mock_bedrock):
        mock_bedrock.converse.side_effect = [
            _response("I cannot do that"),
            _response('{"ok": true}'),
        ]

        assert bedrock_client.invoke_bedrock("hi") == {"ok": True}
        assert mock_bedrock.converse.call_count == 2

        # The retry prompt should carry the stricter reminder.
        retry_text = mock_bedrock.converse.call_args_list[1].kwargs["messages"][0][
            "content"
        ][0]["text"]
        assert "not valid JSON" in retry_text

    def test_raises_after_failed_retry(self, mock_bedrock):
        mock_bedrock.converse.return_value = _response("still not json")

        with pytest.raises(ValueError, match="Failed to parse Bedrock response"):
            bedrock_client.invoke_bedrock("hi")

        assert mock_bedrock.converse.call_count == 2

    def test_force_json_false_returns_raw_text(self, mock_bedrock):
        mock_bedrock.converse.return_value = _response("plain prose response")

        assert (
            bedrock_client.invoke_bedrock("hi", force_json=False)
            == "plain prose response"
        )

    def test_system_prompt_is_forwarded(self, mock_bedrock):
        mock_bedrock.converse.return_value = _response("{}")

        bedrock_client.invoke_bedrock("hi", system_prompt="Be a chef.")

        system = mock_bedrock.converse.call_args.kwargs["system"]
        assert system[0]["text"].startswith("Be a chef.")
        assert "valid JSON only" in system[0]["text"]


class TestInvokeBedrockVision:
    def test_sends_image_block_then_prompt(self, mock_bedrock):
        mock_bedrock.converse.return_value = _response("[]")

        bedrock_client.invoke_bedrock_vision(
            image_bytes=b"\xff\xd8\xff\xe0", prompt="What is in this fridge?"
        )

        content = mock_bedrock.converse.call_args.kwargs["messages"][0]["content"]
        assert content[0]["image"]["source"]["bytes"] == b"\xff\xd8\xff\xe0"
        assert content[0]["image"]["format"] == "jpeg"
        assert content[1]["text"] == "What is in this fridge?"

    def test_normalizes_mime_type_format(self, mock_bedrock):
        mock_bedrock.converse.return_value = _response("[]")

        bedrock_client.invoke_bedrock_vision(
            image_bytes=b"x", image_format="image/png"
        )

        content = mock_bedrock.converse.call_args.kwargs["messages"][0]["content"]
        assert content[0]["image"]["format"] == "png"

    def test_parses_json_from_vision_response(self, mock_bedrock):
        mock_bedrock.converse.return_value = _response(
            '[{"ingredient_id": "curd", "estimated_quantity_g": 400}]'
        )

        result = bedrock_client.invoke_bedrock_vision(image_bytes=b"x")

        assert result == [{"ingredient_id": "curd", "estimated_quantity_g": 400}]

    def test_vision_uses_smaller_token_budget(self, mock_bedrock):
        mock_bedrock.converse.return_value = _response("[]")

        bedrock_client.invoke_bedrock_vision(image_bytes=b"x")

        config = mock_bedrock.converse.call_args.kwargs["inferenceConfig"]
        assert 0 < config["maxTokens"] <= 2048

    def test_empty_image_is_rejected_before_calling_bedrock(self, mock_bedrock):
        with pytest.raises(ValueError, match="empty image"):
            bedrock_client.invoke_bedrock_vision(image_bytes=b"")

        assert not mock_bedrock.converse.called

    def test_oversized_image_is_rejected_before_calling_bedrock(self, mock_bedrock):
        oversized = b"x" * (bedrock_client.MAX_IMAGE_BYTES + 1)

        with pytest.raises(ValueError, match="too large"):
            bedrock_client.invoke_bedrock_vision(image_bytes=oversized)

        assert not mock_bedrock.converse.called

    def test_image_within_limit_is_sent(self, mock_bedrock):
        mock_bedrock.converse.return_value = _response("[]")
        image = b"x" * 1024

        bedrock_client.invoke_bedrock_vision(image_bytes=image)

        content = mock_bedrock.converse.call_args.kwargs["messages"][0]["content"]
        assert content[0]["image"]["source"]["bytes"] == image
