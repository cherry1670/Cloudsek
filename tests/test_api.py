import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timezone


@pytest.fixture(autouse=True)
def mock_stores():
    """Mock both mongo and cache stores for all API tests"""
    with patch("app.api.mongo_store") as mock_mongo:
        with patch("app.api.cache_store") as mock_cache:
            with patch("app.api.process_url", new_callable=AsyncMock) as mock_process:
                mock_mongo.connect = AsyncMock()
                mock_mongo.close = AsyncMock()
                mock_cache.connect = AsyncMock()
                mock_cache.close = AsyncMock()
                yield {"mongo": mock_mongo, "cache": mock_cache, "process_url": mock_process}


@pytest.fixture
def client():
    """Create a test client with mocked stores"""
    from app.api import app
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client):
    """Test the health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_scrape_new_url(client, mock_stores):
    """Test scraping a new URL returns 202 Accepted"""
    mock_stores["mongo"].create_pending = AsyncMock(
        return_value=(
            {
                "url": "https://example.com/",
                "status": "processing",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
            True,  # created=True
        )
    )

    response = client.post("/scrape", json={"url": "https://example.com"})

    assert response.status_code == 202
    data = response.json()
    assert data["url"] == "https://example.com/"  # Pydantic adds trailing slash
    assert data["status"] == "processing"
    assert data["message"] == "Scraping initiated"


def test_scrape_existing_url(client, mock_stores):
    """Test scraping an existing URL returns 200 with existing status"""
    # Use the exact URL that Pydantic will normalize to
    mock_stores["mongo"].create_pending = AsyncMock(
        return_value=(
            {
                "url": "https://example.com/",
                "status": "completed",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
            False,  # created=False (already exists)
        )
    )

    response = client.post("/scrape", json={"url": "https://example.com/"})

    assert response.status_code == 200
    data = response.json()
    assert data["url"] == "https://example.com/"
    assert data["status"] == "completed"
    assert data["message"] == "URL already exists"


def test_scrape_invalid_url(client):
    """Test scraping with invalid URL returns 422"""
    response = client.post("/scrape", json={"url": "not-a-valid-url"})
    assert response.status_code == 422


def test_metadata_from_cache(client, mock_stores):
    """Test getting metadata from cache"""
    cached_data = {
        "url": "https://example.com",
        "status": "completed",
        "headers": {"content-type": "text/html"},
        "cookies": {},
        "page_source": "<html></html>",
        "metadata": {"title": "Example"},
        "error": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    mock_stores["cache"].get = AsyncMock(return_value=cached_data)

    response = client.get("/metadata?url=https://example.com")
    
    assert response.status_code == 200
    data = response.json()
    assert data["url"] == "https://example.com"
    assert data["status"] == "completed"
    assert data["metadata"]["title"] == "Example"


def test_metadata_from_database(client, mock_stores):
    """Test getting metadata from database when not in cache"""
    db_data = {
        "url": "https://example.com",
        "status": "completed",
        "headers": {"content-type": "text/html"},
        "cookies": {},
        "page_source": "<html></html>",
        "metadata": {"title": "Example"},
        "error": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    mock_stores["cache"].get = AsyncMock(return_value=None)
    mock_stores["mongo"].get_by_url = AsyncMock(return_value=db_data)
    mock_stores["cache"].set = AsyncMock()

    response = client.get("/metadata?url=https://example.com")
    
    assert response.status_code == 200
    data = response.json()
    assert data["url"] == "https://example.com"
    assert data["status"] == "completed"
    # Verify cache was updated
    mock_stores["cache"].set.assert_called_once()


def test_metadata_not_found_triggers_scraping(client, mock_stores):
    """Test that requesting metadata for unknown URL triggers scraping"""
    mock_stores["cache"].get = AsyncMock(return_value=None)
    mock_stores["mongo"].get_by_url = AsyncMock(return_value=None)
    mock_stores["mongo"].create_pending = AsyncMock(
        return_value=(
            {
                "url": "https://newsite.com/",
                "status": "processing",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
            True,
        )
    )
    # Mock the worker to prevent actual scraping
    mock_stores["mongo"].upsert_result = AsyncMock()
    mock_stores["cache"].set = AsyncMock()

    response = client.get("/metadata?url=https://newsite.com")

    assert response.status_code == 202
    data = response.json()
    assert data["url"] == "https://newsite.com/"
    assert data["status"] == "processing"
    assert data["message"] == "Scraping initiated"
