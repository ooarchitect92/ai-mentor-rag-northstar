import hashlib
import json
from redis.asyncio import Redis
from .config import get_settings


def normalize_question(course: str, message: str, mode: str, level: str) -> str:
    compact = " ".join(message.lower().strip().split())
    return f"{course.upper()}::{mode}::{level}::{compact}"


def cache_key(course: str, message: str, mode: str, level: str) -> str:
    return "mentor:answer:course-flexible-v3:" + hashlib.sha256(
        normalize_question(course, message, mode, level).encode("utf-8")
    ).hexdigest()


class Cache:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.redis = Redis.from_url(self.settings.redis_url, decode_responses=True)

    async def get(self, key: str) -> dict | None:
        try:
            raw = await self.redis.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            return None

    async def set(self, key: str, value: dict) -> None:
        try:
            await self.redis.setex(
                key,
                self.settings.cache_ttl_seconds,
                json.dumps(value, ensure_ascii=False),
            )
        except Exception:
            # Cache should never break the mentor.
            return

    async def set_if_absent(self, key: str, ttl_seconds: int) -> bool:
        try:
            return bool(await self.redis.set(key, "1", ex=ttl_seconds, nx=True))
        except Exception:
            # If Redis is down, prefer answering over dropping the user's message.
            return True

    async def get_text(self, key: str) -> str | None:
        try:
            return await self.redis.get(key)
        except Exception:
            return None

    async def set_text(self, key: str, value: str, ttl_seconds: int) -> None:
        try:
            await self.redis.setex(key, ttl_seconds, value)
        except Exception:
            return

    async def delete(self, key: str) -> None:
        try:
            await self.redis.delete(key)
        except Exception:
            return

    async def aclose(self) -> None:
        await self.redis.aclose()
