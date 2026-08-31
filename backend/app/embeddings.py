import asyncio
import hashlib
import math
import re
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from .config import get_settings


TOKEN_RE = re.compile(r"[a-z0-9]+")


class EmbeddingService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = None
        if self.settings.embedding_provider == "openai":
            if not (self.settings.openai_api_key or "").strip():
                raise RuntimeError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai")
            self.client = AsyncOpenAI(
                api_key=self.settings.openai_api_key,
                timeout=self.settings.request_timeout_seconds,
                max_retries=0,
            )

    def _hash_embed(self, text: str) -> list[float]:
        vector = [0.0] * self.settings.embedding_dimensions
        tokens = TOKEN_RE.findall(text.lower())
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.settings.embedding_dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    @retry(wait=wait_exponential(multiplier=0.5, min=1, max=8), stop=stop_after_attempt(3))
    async def embed_one(self, text: str) -> list[float]:
        if self.settings.embedding_provider == "hash":
            return await asyncio.to_thread(self._hash_embed, text)

        if self.client is None:
            raise RuntimeError("Embedding client is not configured")

        result = await self.client.embeddings.create(
            model=self.settings.openai_embedding_model,
            input=text,
            encoding_format="float",
        )
        return result.data[0].embedding

    @retry(wait=wait_exponential(multiplier=0.5, min=1, max=8), stop=stop_after_attempt(3))
    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.settings.embedding_provider == "hash":
            return await asyncio.to_thread(lambda: [self._hash_embed(text) for text in texts])

        if self.client is None:
            raise RuntimeError("Embedding client is not configured")

        result = await self.client.embeddings.create(
            model=self.settings.openai_embedding_model,
            input=texts,
            encoding_format="float",
        )
        return [item.embedding for item in result.data]

    async def aclose(self) -> None:
        if self.client is not None:
            await self.client.close()
