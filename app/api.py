import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import BackgroundTasks, FastAPI, Query, Response, status
from pydantic import HttpUrl

from app.cache import cache_store
from app.config import get_settings
from app.database import mongo_store
from app.fetcher.worker import process_url
from app.models.api_models import MetadataResponse, ScrapeRequest, StatusResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await mongo_store.connect()
    await cache_store.connect()
    try:
        yield
    finally:
        await cache_store.close()
        await mongo_store.close()


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/scrape", response_model=StatusResponse)
async def scrape(request: ScrapeRequest, background_tasks: BackgroundTasks, response: Response) -> StatusResponse:
    url = str(request.url)
    document, created = await mongo_store.create_pending(url)

    if created:
        background_tasks.add_task(_run_worker, url)
        response.status_code = status.HTTP_202_ACCEPTED
        return StatusResponse(url=url, status="processing", message="Scraping initiated")

    response.status_code = status.HTTP_200_OK
    return StatusResponse(
        url=url,
        status=document.get("status", "unknown"),
        message="URL already exists",
    )


@app.get("/metadata", response_model=MetadataResponse | StatusResponse)
async def metadata(
    background_tasks: BackgroundTasks,
    response: Response,
    url: HttpUrl = Query(..., description="URL to fetch metadata for"),
) -> MetadataResponse | StatusResponse:
    normalized_url = str(url)
    cached = await cache_store.get(normalized_url)
    if cached is not None:
        return MetadataResponse.model_validate(cached)

    document = await mongo_store.get_by_url(normalized_url)
    if document is not None:
        if document.get("status") == "completed":
            await cache_store.set(normalized_url, document)
        return MetadataResponse.model_validate(document)

    _, created = await mongo_store.create_pending(normalized_url)
    if created:
        background_tasks.add_task(_run_worker, normalized_url)

    response.status_code = status.HTTP_202_ACCEPTED
    return StatusResponse(url=normalized_url, status="processing", message="Scraping initiated")


async def _run_worker(url: str) -> None:
    try:
        await process_url(url)
    except Exception as exc:
        logger.exception("Background worker crashed for %s", url)
        failed = {
            "status": "failed",
            "headers": {},
            "cookies": {},
            "page_source": None,
            "metadata": {},
            "error": str(exc),
        }
        document = await mongo_store.upsert_result(url, failed)
        try:
            await cache_store.set(url, document)
        except Exception:
            logger.exception("Failed to cache worker error for %s", url)
