import asyncio

import pytest

from app.gemini import GeminiService
from app.llm import MentorLLMService
from app.nvidia import NvidiaService


class FakeProvider:
    def __init__(self, *, answer="ok", answer_error=None, stream_parts=None, stream_error=None):
        self.answer = answer
        self.answer_error = answer_error
        self.stream_parts = stream_parts or []
        self.stream_error = stream_error

    async def answer_text(self, **kwargs):
        if self.answer_error:
            raise self.answer_error
        return self.answer

    async def stream_text(self, **kwargs):
        for part in self.stream_parts:
            yield part
        if self.stream_error:
            raise self.stream_error


def collect_stream(service):
    async def collect():
        return [part async for part in service.stream_text(system_prompt="system", user_prompt="user")]

    return asyncio.run(collect())


def test_gemini_extracts_answer_text_and_ignores_thoughts():
    response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"thought": True, "text": "private reasoning"},
                        {"text": "Student-facing answer"},
                    ]
                }
            }
        ]
    }

    assert GeminiService._extract_text(response) == "Student-facing answer"


def test_nvidia_fast_request_disables_thinking_without_exposing_reasoning():
    service = NvidiaService()

    request = service._request(system_prompt="system", user_prompt="user", stream=False)

    assert request["model"] == "nvidia/nemotron-3-ultra-550b-a55b"
    assert request["max_tokens"] == service.settings.nvidia_max_tokens
    assert request["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False
    assert "reasoning_budget" not in request["extra_body"]


def test_nvidia_policy_request_disables_thinking_and_uses_small_output():
    service = NvidiaService()

    request = service._request(
        system_prompt="Return only ALLOW or BLOCK.",
        user_prompt="policy input",
        stream=False,
    )

    assert request["max_tokens"] == 32
    assert request["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False
    assert "reasoning_budget" not in request["extra_body"]


def test_answer_uses_fallback_when_primary_fails():
    service = MentorLLMService(
        primary=FakeProvider(answer_error=RuntimeError("primary failed")),
        fallback=FakeProvider(answer="fallback answer"),
    )

    result = asyncio.run(service.answer_text(system_prompt="system", user_prompt="user"))

    assert result == "fallback answer"


def test_stream_uses_fallback_when_primary_fails_before_output():
    service = MentorLLMService(
        primary=FakeProvider(stream_error=RuntimeError("primary failed")),
        fallback=FakeProvider(stream_parts=["fallback", " answer"]),
    )

    assert collect_stream(service) == ["fallback", " answer"]


def test_stream_does_not_duplicate_after_partial_primary_output():
    service = MentorLLMService(
        primary=FakeProvider(stream_parts=["partial"], stream_error=RuntimeError("primary failed")),
        fallback=FakeProvider(stream_parts=["fallback answer"]),
    )

    with pytest.raises(RuntimeError, match="primary failed"):
        collect_stream(service)
