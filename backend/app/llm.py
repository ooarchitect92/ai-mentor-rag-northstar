import logging
from collections.abc import AsyncGenerator
from typing import Protocol

from .claude import ClaudeService
from .config import get_settings
from .gemini import GeminiService
from .nvidia import NvidiaService


logger = logging.getLogger(__name__)


class TextGenerationService(Protocol):
    async def answer_text(self, *, system_prompt: str, user_prompt: str) -> str: ...

    def stream_text(self, *, system_prompt: str, user_prompt: str) -> AsyncGenerator[str, None]: ...


class MentorLLMService:
    def __init__(
        self,
        primary: TextGenerationService | None = None,
        fallback: TextGenerationService | None = None,
    ) -> None:
        self.settings = get_settings()
        self.primary_name = self.settings.mentor_provider
        self.fallback_name = self.settings.mentor_fallback_provider
        self.primary = primary or self._build_provider(self.primary_name)
        self.fallback = fallback
        if (
            fallback is None
            and self.fallback_name != "none"
            and self.fallback_name != self.primary_name
            and self._provider_configured(self.fallback_name)
        ):
            self.fallback = self._build_provider(self.fallback_name)

    def _provider_configured(self, name: str) -> bool:
        if name == "nvidia":
            return bool(self.settings.nvidia_api_key)
        if name == "gemini":
            return bool(self.settings.gemini_api_key)
        if name == "anthropic":
            return bool(self.settings.anthropic_api_key)
        return False

    @staticmethod
    def _build_provider(name: str) -> TextGenerationService:
        if name == "nvidia":
            return NvidiaService()
        if name == "gemini":
            return GeminiService()
        if name == "anthropic":
            return ClaudeService()
        raise ValueError(f"Unsupported mentor provider: {name}")

    async def answer_text(self, *, system_prompt: str, user_prompt: str) -> str:
        try:
            return await self.primary.answer_text(system_prompt=system_prompt, user_prompt=user_prompt)
        except Exception:
            if self.fallback is None:
                raise
            logger.exception("Primary mentor provider %s failed; trying %s", self.primary_name, self.fallback_name)
            return await self.fallback.answer_text(system_prompt=system_prompt, user_prompt=user_prompt)

    async def stream_text(self, *, system_prompt: str, user_prompt: str) -> AsyncGenerator[str, None]:
        emitted = False
        try:
            async for delta in self.primary.stream_text(system_prompt=system_prompt, user_prompt=user_prompt):
                emitted = True
                yield delta
            return
        except Exception:
            if emitted or self.fallback is None:
                raise
            logger.exception(
                "Primary mentor provider %s failed before streaming text; trying %s",
                self.primary_name,
                self.fallback_name,
            )

        async for delta in self.fallback.stream_text(system_prompt=system_prompt, user_prompt=user_prompt):
            yield delta

    async def aclose(self) -> None:
        seen: set[int] = set()
        for provider in (self.primary, self.fallback):
            if provider is None or id(provider) in seen:
                continue
            seen.add(id(provider))
            closer = getattr(provider, "aclose", None)
            if closer is not None:
                await closer()
