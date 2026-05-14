import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from pymongo.errors import DuplicateKeyError
from app.database import MongoStore
from app.config import Settings


@pytest.fixture
def test_settings():
    """Create test settings"""
    return Settings(
        MONGODB_URI="mongodb://localhost:27017",
        MONGODB_DATABASE="test_db",
        MONGODB_COLLECTION="test_collection",
    )


@pytest.fixture
def mongo_store(test_settings):
    """Create a MongoStore instance with test settings"""
    return MongoStore(settings=test_settings)


@pytest.mark.asyncio
async def test_connect_creates_client_and_index():
    """Test that connect creates client and index"""
    test_settings = Settings(
        MONGODB_URI="mongodb://localhost:27017",
        MONGODB_DATABASE="test_db",
        MONGODB_COLLECTION="test_collection",
    )
    store = MongoStore(settings=test_settings)

    mock_collection = MagicMock()
    mock_collection.create_index = AsyncMock()

    mock_database = MagicMock()
    mock_database.__getitem__ = MagicMock(return_value=mock_collection)

    mock_client = MagicMock()
    mock_client.__getitem__ = MagicMock(return_value=mock_database)

    with patch("app.database.AsyncIOMotorClient", return_value=mock_client):
        await store.connect()

        assert store.client is not None
        assert store.client == mock_client
        mock_collection.create_index.assert_called_once()


@pytest.mark.asyncio
async def test_close_closes_client(mongo_store):
    """Test that close properly closes the client"""
    mock_client = MagicMock()
    mongo_store.client = mock_client
    
    await mongo_store.close()
    
    mock_client.close.assert_called_once()
    assert mongo_store.client is None


@pytest.mark.asyncio
async def test_get_by_url_returns_document(mongo_store):
    """Test getting a document by URL"""
    expected_doc = {
        "url": "https://example.com",
        "status": "completed",
        "created_at": datetime.now(timezone.utc),
    }
    
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=expected_doc)
    
    with patch.object(mongo_store, "session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_collection
        
        result = await mongo_store.get_by_url("https://example.com")
        
        assert result == expected_doc
        mock_collection.find_one.assert_called_once_with(
            {"url": "https://example.com"}, {"_id": False}
        )


@pytest.mark.asyncio
async def test_get_by_url_returns_none_when_not_found(mongo_store):
    """Test getting a non-existent document returns None"""
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=None)
    
    with patch.object(mongo_store, "session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_collection
        
        result = await mongo_store.get_by_url("https://notfound.com")
        
        assert result is None


@pytest.mark.asyncio
async def test_create_pending_new_document(mongo_store):
    """Test creating a new pending document"""
    mock_collection = MagicMock()
    mock_collection.insert_one = AsyncMock()
    
    with patch.object(mongo_store, "session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_collection
        
        document, created = await mongo_store.create_pending("https://example.com")
        
        assert created is True
        assert document["url"] == "https://example.com"
        assert document["status"] == "processing"
        assert "created_at" in document
        assert "updated_at" in document
        mock_collection.insert_one.assert_called_once()


@pytest.mark.asyncio
async def test_create_pending_duplicate_returns_existing(mongo_store):
    """Test creating a duplicate document returns existing"""
    existing_doc = {
        "url": "https://example.com",
        "status": "completed",
        "created_at": datetime.now(timezone.utc),
    }
    
    mock_collection = MagicMock()
    mock_collection.insert_one = AsyncMock(side_effect=DuplicateKeyError("duplicate"))
    mock_collection.find_one = AsyncMock(return_value=existing_doc)
    
    with patch.object(mongo_store, "session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_collection
        
        document, created = await mongo_store.create_pending("https://example.com")
        
        assert created is False
        assert document == existing_doc


@pytest.mark.asyncio
async def test_upsert_result_updates_document(mongo_store):
    """Test upserting a scrape result"""
    payload = {
        "status": "completed",
        "headers": {"content-type": "text/html"},
        "metadata": {"title": "Test"},
    }
    
    updated_doc = {
        "url": "https://example.com",
        **payload,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    
    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock()
    mock_collection.find_one = AsyncMock(return_value=updated_doc)
    
    with patch.object(mongo_store, "session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_collection
        
        result = await mongo_store.upsert_result("https://example.com", payload)
        
        assert result == updated_doc
        mock_collection.update_one.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_result_raises_on_failure(mongo_store):
    """Test that upsert raises RuntimeError if document not found after update"""
    payload = {"status": "completed"}
    
    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock()
    mock_collection.find_one = AsyncMock(return_value=None)
    
    with patch.object(mongo_store, "session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_collection
        
        with pytest.raises(RuntimeError, match="Failed to persist scrape result"):
            await mongo_store.upsert_result("https://example.com", payload)
