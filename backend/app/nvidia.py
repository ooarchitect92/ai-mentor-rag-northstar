from collections.abc import AsyncGenerator

from openai import AsyncOpenAI

from .config import get_settings


class NvidiaService:
    """NVIDIA NIM text generation through its OpenAI-compatible endpoint."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if not self.settings.nvidia_api_key:
            raise RuntimeError("NVIDIA_API_KEY is missing. Add it to .env.")
        if self._client is None:
            self._client = AsyncOpenAI(
                base_url=self.settings.nvidia_base_url,
                api_key=self.settings.nvidia_api_key,
                timeout=self.settings.request_timeout_seconds,
                max_retries=1,
            )
        return self._client

    def _request(self, *, system_prompt: str, user_prompt: str, stream: bool) -> dict:
        is_policy_request = "return only" in system_prompt.casefold()
        extra_body = {
            "chat_template_kwargs": {
                "enable_thinking": self.settings.nvidia_enable_thinking and not is_policy_request,
            },
        }
        if not is_policy_request and self.settings.nvidia_enable_thinking:
            extra_body["reasoning_budget"] = self.settings.nvidia_reasoning_budget

        return {
            "model": self.settings.nvidia_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1 if is_policy_request else self.settings.nvidia_temperature,
            "top_p": self.settings.nvidia_top_p,
            "max_tokens": (
                self.settings.nvidia_policy_max_tokens
                if is_policy_request
                else self.settings.nvidia_max_tokens
            ),
            "extra_body": extra_body,
            "stream": stream,
        }

    async def answer_text(self, *, system_prompt: str, user_prompt: str) -> str:
        completion = await self._get_client().chat.completions.create(
            **self._request(system_prompt=system_prompt, user_prompt=user_prompt, stream=False)
        )
        if not completion.choices:
            raise RuntimeError("NVIDIA returned no completion choices.")
        text = completion.choices[0].message.content or ""
        text = text.strip()
        if not text:
            raise RuntimeError("NVIDIA returned no student-facing text.")
        return text

    async def stream_text(self, *, system_prompt: str, user_prompt: str) -> AsyncGenerator[str, None]:
        stream = await self._get_client().chat.completions.create(
            **self._request(system_prompt=system_prompt, user_prompt=user_prompt, stream=True)
        )
        emitted = False
        async for chunk in stream:
            if not chunk.choices:
                continue
            # Deliberately never expose reasoning_content to students.
            text = chunk.choices[0].delta.content
            if text:
                emitted = True
                yield text
        if not emitted:
            raise RuntimeError("NVIDIA returned no streamed student-facing text.")

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
