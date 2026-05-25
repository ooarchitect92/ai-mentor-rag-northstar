import json
from collections.abc import AsyncGenerator

import httpx

from .config import get_settings


class ClaudeService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _headers(self) -> dict[str, str]:
        if not self.settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is missing. Add your Claude key to .env.")

        return {
            "x-api-key": self.settings.anthropic_api_key,
            "anthropic-version": self.settings.anthropic_version,
            "content-type": "application/json",
        }

    def _payload(self, *, system_prompt: str, user_prompt: str, stream: bool) -> dict:
        return {
            "model": self.settings.anthropic_model,
            "max_tokens": self.settings.anthropic_max_tokens,
            "temperature": 0.25,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "stream": stream,
        }

    @staticmethod
    def _extract_text(message: dict) -> str:
        parts = []
        for block in message.get("content", []):
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts).strip()

    async def answer_text(self, *, system_prompt: str, user_prompt: str) -> str:
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.post(
                self.settings.anthropic_api_url,
                headers=self._headers(),
                json=self._payload(system_prompt=system_prompt, user_prompt=user_prompt, stream=False),
            )
            response.raise_for_status()
            return self._extract_text(response.json())

    async def stream_text(self, *, system_prompt: str, user_prompt: str) -> AsyncGenerator[str, None]:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                self.settings.anthropic_api_url,
                headers=self._headers(),
                json=self._payload(system_prompt=system_prompt, user_prompt=user_prompt, stream=True),
            ) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    raise RuntimeError(body.decode("utf-8", errors="replace"))

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    raw = line[6:]
                    if not raw:
                        continue

                    event = json.loads(raw)
                    event_type = event.get("type")

                    if event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta" and delta.get("text"):
                            yield delta["text"]
                    elif event_type == "message_stop":
                        return
                    elif event_type == "error":
                        error = event.get("error", {})
                        raise RuntimeError(error.get("message", "Claude streaming error"))
