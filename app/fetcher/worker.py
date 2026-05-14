import asyncio
import logging
from typing import Any

import httpx

from app.cache import cache_store
from app.config import Settings, get_settings
from app.database import mongo_store
from app.fetcher.webscraper import scrape_url

logger = logging.getLogger(__name__)
_semaphore: asyncio.Semaphore | None = None


def worker_semaphore(settings: Settings | None = None) -> asyncio.Semaphore:
    global _semaphore
    resolved_settings = settings or get_settings()
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(resolved_settings.max_concurrent_workers)
    return _semaphore


async def process_url(url: str, settings: Settings | None = None) -> dict[str, Any]:
    resolved_settings = settings or get_settings()
    async with worker_semaphore(resolved_settings):
        result = await _scrape_with_retry(url, resolved_settings)
        document = await mongo_store.upsert_result(url, result)
        await cache_store.set(url, document)
        return document


async def _scrape_with_retry(url: str, settings: Settings) -> dict[str, Any]:
    last_error: Exception | None = None

    for attempt in range(1, settings.max_retries + 1):
        try:
            return await scrape_url(url, settings)
        except (httpx.HTTPError, ValueError, RuntimeError) as exc:
            last_error = exc
            logger.warning("Scrape attempt %s/%s failed for %s: %s", attempt, settings.max_retries, url, exc)
            if attempt < settings.max_retries:
                await asyncio.sleep(2 ** (attempt - 1))

    return {
        "status": "failed",
        "headers": {},
        "cookies": {},
        "page_source": None,
        "metadata": {},
        "error": str(last_error) if last_error else "Unknown scrape failure",
    }
