from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from app.config import Settings, get_settings
from app.models.db_models import build_pending_document, utcnow


class MongoStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client: AsyncIOMotorClient | None = None

    async def connect(self) -> None:
        if self.client is None:
            self.client = AsyncIOMotorClient(self.settings.mongodb_uri)
            await self.collection.create_index([("url", ASCENDING)], unique=True)

    async def close(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None

    @property
    def database(self) -> AsyncIOMotorDatabase:
        if self.client is None:
            raise RuntimeError("MongoDB client is not connected")
        return self.client[self.settings.mongodb_database]

    @property
    def collection(self) -> AsyncIOMotorCollection:
        return self.database[self.settings.mongodb_collection]

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncIOMotorCollection]:
        await self.connect()
        yield self.collection

    async def get_by_url(self, url: str) -> dict[str, Any] | None:
        async with self.session() as collection:
            document = await collection.find_one({"url": url}, {"_id": False})
        return document

    async def create_pending(self, url: str) -> tuple[dict[str, Any], bool]:
        async with self.session() as collection:
            document = build_pending_document(url)
            try:
                await collection.insert_one(document)
                document.pop("_id", None)
                return document, True
            except DuplicateKeyError:
                existing = await collection.find_one({"url": url}, {"_id": False})
                if existing is None:
                    raise
                return existing, False

    async def upsert_result(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = utcnow()
        update = {
            "$set": {
                **payload,
                "url": url,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        }
        async with self.session() as collection:
            await collection.update_one({"url": url}, update, upsert=True)
            document = await collection.find_one({"url": url}, {"_id": False})
        if document is None:
            raise RuntimeError(f"Failed to persist scrape result for {url}")
        return document


mongo_store = MongoStore()
