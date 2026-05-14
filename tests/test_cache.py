import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from app.cache import CacheStore
from app.config import Settings


@pytest.fixture
def test_settings():
    """Create test settings"""
    return Settings(
        REDIS_URL="redis://localhost:6379/0",
        CACHE_TTL_SECONDS=3600,
    )


@pytest.fixture
def cache_store(test_settings):
    """Create a CacheStore instance with test settings"""
    return CacheStore(settings=test_settings)


@pytest.mark.asyncio
async def test_connect_creates_client(cache_store):
    """Test that connect creates Redis client and pings"""
    mock_client = AsyncMock()
    mock_client.ping = AsyncMock()
    
    with patch("app.cache.Redis.from_url", return_value=mock_client):
        await cache_store.connect()
        
        assert cache_store.client is not None
        mock_client.ping.assert_called_once()


@pytest.mark.asyncio
async def test_close_closes_client(cache_store):
    """Test that close properly closes the client"""
    mock_client = AsyncMock()
    mock_client.aclose = AsyncMock()
    cache_store.client = mock_client
    
    await cache_store.close()
    
    mock_client.aclose.assert_called_once()
    assert cache_store.client is None


def test_key_generation(cache_store):
    """Test cache key generation"""
    url = "https://example.com"
    key = cache_store.key(url)
    
    assert key == "url_metadata:https://example.com"


@pytest.mark.asyncio
async def test_get_returns_cached_value(cache_store):
    """Test getting a cached value"""
    url = "https://example.com"
    cached_data = {
        "url": url,
        "status": "completed",
        "metadata": {"title": "Example"},
    }
    
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=json.dumps(cached_data))
    cache_store.client = mock_client
    
    result = await cache_store.get(url)
    
    assert result == cached_data
    mock_client.get.assert_called_once_with(f"url_metadata:{url}")


@pytest.mark.asyncio
async def test_get_returns_none_when_not_cached(cache_store):
    """Test getting a non-existent cache entry returns None"""
    url = "https://example.com"
    
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=None)
    cache_store.client = mock_client
    
    result = await cache_store.get(url)
    
    assert result is None


@pytest.mark.asyncio
async def test_set_stores_value_with_ttl(cache_store):
    """Test setting a cache value with TTL"""
    url = "https://example.com"
    data = {
        "url": url,
        "status": "completed",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    
    mock_client = AsyncMock()
    mock_client.set = AsyncMock()
    cache_store.client = mock_client
    
    await cache_store.set(url, data)
    
    mock_client.set.assert_called_once()
    call_args = mock_client.set.call_args
    assert call_args[0][0] == f"url_metadata:{url}"
    assert call_args[1]["ex"] == cache_store.settings.cache_ttl_seconds


@pytest.mark.asyncio
async def test_set_serializes_datetime(cache_store):
    """Test that datetime objects are properly serialized"""
    url = "https://example.com"
    now = datetime.now(timezone.utc)
    data = {
        "url": url,
        "status": "completed",
        "created_at": now,
    }
    
    mock_client = AsyncMock()
    mock_client.set = AsyncMock()
    cache_store.client = mock_client
    
    await cache_store.set(url, data)
    
    # Verify that the serialized data contains ISO format datetime
    call_args = mock_client.set.call_args
    serialized = call_args[0][1]
    deserialized = json.loads(serialized)
    assert "created_at" in deserialized
    assert isinstance(deserialized["created_at"], str)


@pytest.mark.asyncio
async def test_delete_removes_cache_entry(cache_store):
    """Test deleting a cache entry"""
    url = "https://example.com"
    
    mock_client = AsyncMock()
    mock_client.delete = AsyncMock()
    cache_store.client = mock_client
    
    await cache_store.delete(url)
    
    mock_client.delete.assert_called_once_with(f"url_metadata:{url}")


@pytest.mark.asyncio
async def test_get_raises_when_not_connected(cache_store):
    """Test that get raises RuntimeError when client is not connected"""
    # Ensure client is None but connect sets it
    cache_store.client = None
    
    with patch("app.cache.Redis.from_url") as mock_redis:
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)
        mock_redis.return_value = mock_client
        
        # Should auto-connect
        result = await cache_store.get("https://example.com")
        assert result is None


def test_json_default_handles_datetime():
    """Test the JSON serialization default handler"""
    now = datetime.now(timezone.utc)
    result = CacheStore._json_default(now)
    assert isinstance(result, str)
    assert "T" in result  # ISO format contains 'T'


def test_json_default_raises_for_unsupported_type():
    """Test that _json_default raises TypeError for unsupported types"""
    with pytest.raises(TypeError, match="not JSON serializable"):
        CacheStore._json_default(object())
