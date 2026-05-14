import json
from datetime import datetime
from typing import Any

from redis.asyncio import Redis

from app.config import Settings, get_settings


class CacheStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client: Redis | None = None

    async def connect(self) -> None:
        if self.client is None:
            self.client = Redis.from_url(self.settings.redis_url, decode_responses=True)
            await self.client.ping()

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    def key(self, url: str) -> str:
        return f"url_metadata:{url}"

    async def get(self, url: str) -> dict[str, Any] | None:
        await self.connect()
        if self.client is None:
            raise RuntimeError("Redis client is not connected")
        raw_value = await self.client.get(self.key(url))
        if raw_value is None:
            return None
        return json.loads(raw_value)

    async def set(self, url: str, value: dict[str, Any]) -> None:
        await self.connect()
        if self.client is None:
            raise RuntimeError("Redis client is not connected")
        await self.client.set(
            self.key(url),
            json.dumps(value, default=self._json_default),
            ex=self.settings.cache_ttl_seconds,
        )

    async def delete(self, url: str) -> None:
        await self.connect()
        if self.client is None:
            raise RuntimeError("Redis client is not connected")
        await self.client.delete(self.key(url))

    @staticmethod
    def _json_default(value: Any) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


cache_store = CacheStore()
