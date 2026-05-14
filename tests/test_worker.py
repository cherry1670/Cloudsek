import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from app.fetcher.worker import process_url, worker_semaphore, _scrape_with_retry
from app.config import Settings


@pytest.fixture
def test_settings():
    """Create test settings"""
    return Settings(
        MAX_CONCURRENT_WORKERS=5,
        MAX_RETRIES=3,
        REQUEST_TIMEOUT_SECONDS=10.0,
    )


@pytest.mark.asyncio
async def test_worker_semaphore_creates_instance(test_settings):
    """Test that worker_semaphore creates a semaphore with correct limit"""
    # Reset global semaphore
    import app.fetcher.worker as worker_module
    worker_module._semaphore = None
    
    semaphore = worker_semaphore(test_settings)
    
    assert semaphore is not None
    assert semaphore._value == test_settings.max_concurrent_workers


@pytest.mark.asyncio
async def test_worker_semaphore_returns_existing_instance(test_settings):
    """Test that worker_semaphore returns the same instance on subsequent calls"""
    import app.fetcher.worker as worker_module
    worker_module._semaphore = None
    
    semaphore1 = worker_semaphore(test_settings)
    semaphore2 = worker_semaphore(test_settings)
    
    assert semaphore1 is semaphore2


@pytest.mark.asyncio
async def test_process_url_successful_scrape(test_settings):
    """Test successful URL processing"""
    url = "https://example.com"
    scrape_result = {
        "status": "completed",
        "headers": {"content-type": "text/html"},
        "cookies": {},
        "page_source": "<html></html>",
        "metadata": {"title": "Example"},
        "error": None,
    }
    
    stored_document = {**scrape_result, "url": url}
    
    with patch("app.fetcher.worker._scrape_with_retry", new_callable=AsyncMock) as mock_scrape:
        with patch("app.fetcher.worker.mongo_store") as mock_mongo:
            with patch("app.fetcher.worker.cache_store") as mock_cache:
                mock_scrape.return_value = scrape_result
                mock_mongo.upsert_result = AsyncMock(return_value=stored_document)
                mock_cache.set = AsyncMock()
                
                result = await process_url(url, test_settings)
                
                assert result == stored_document
                mock_scrape.assert_called_once_with(url, test_settings)
                mock_mongo.upsert_result.assert_called_once_with(url, scrape_result)
                mock_cache.set.assert_called_once_with(url, stored_document)


@pytest.mark.asyncio
async def test_scrape_with_retry_success_first_attempt(test_settings):
    """Test successful scrape on first attempt"""
    url = "https://example.com"
    expected_result = {
        "status": "completed",
        "headers": {},
        "cookies": {},
        "page_source": "<html></html>",
        "metadata": {"title": "Example"},
        "error": None,
    }
    
    with patch("app.fetcher.worker.scrape_url", new_callable=AsyncMock) as mock_scrape:
        mock_scrape.return_value = expected_result
        
        result = await _scrape_with_retry(url, test_settings)
        
        assert result == expected_result
        assert mock_scrape.call_count == 1


@pytest.mark.asyncio
async def test_scrape_with_retry_success_after_failures(test_settings):
    """Test successful scrape after initial failures"""
    url = "https://example.com"
    expected_result = {
        "status": "completed",
        "headers": {},
        "cookies": {},
        "page_source": "<html></html>",
        "metadata": {"title": "Example"},
        "error": None,
    }
    
    with patch("app.fetcher.worker.scrape_url", new_callable=AsyncMock) as mock_scrape:
        # Fail twice, then succeed
        mock_scrape.side_effect = [
            httpx.RequestError("Network error"),
            httpx.RequestError("Network error"),
            expected_result,
        ]
        
        result = await _scrape_with_retry(url, test_settings)
        
        assert result == expected_result
        assert mock_scrape.call_count == 3


@pytest.mark.asyncio
async def test_scrape_with_retry_all_attempts_fail(test_settings):
    """Test scrape that fails all retry attempts"""
    url = "https://example.com"
    error_msg = "Connection timeout"
    
    with patch("app.fetcher.worker.scrape_url", new_callable=AsyncMock) as mock_scrape:
        mock_scrape.side_effect = httpx.RequestError(error_msg)
        
        result = await _scrape_with_retry(url, test_settings)
        
        assert result["status"] == "failed"
        assert result["error"] == error_msg
        assert result["headers"] == {}
        assert result["cookies"] == {}
        assert result["page_source"] is None
        assert result["metadata"] == {}
        assert mock_scrape.call_count == test_settings.max_retries


@pytest.mark.asyncio
async def test_scrape_with_retry_handles_http_error(test_settings):
    """Test retry handling for HTTP errors"""
    url = "https://example.com"
    
    with patch("app.fetcher.worker.scrape_url", new_callable=AsyncMock) as mock_scrape:
        mock_scrape.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=MagicMock(),
            response=MagicMock(),
        )
        
        result = await _scrape_with_retry(url, test_settings)
        
        assert result["status"] == "failed"
        assert "404 Not Found" in result["error"]
        assert mock_scrape.call_count == test_settings.max_retries


@pytest.mark.asyncio
async def test_scrape_with_retry_handles_value_error(test_settings):
    """Test retry handling for ValueError"""
    url = "https://example.com"
    
    with patch("app.fetcher.worker.scrape_url", new_callable=AsyncMock) as mock_scrape:
        mock_scrape.side_effect = ValueError("Invalid response")
        
        result = await _scrape_with_retry(url, test_settings)
        
        assert result["status"] == "failed"
        assert "Invalid response" in result["error"]


@pytest.mark.asyncio
async def test_scrape_with_retry_exponential_backoff(test_settings):
    """Test that retry implements exponential backoff"""
    url = "https://example.com"
    
    with patch("app.fetcher.worker.scrape_url", new_callable=AsyncMock) as mock_scrape:
        with patch("app.fetcher.worker.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_scrape.side_effect = httpx.RequestError("Error")
            
            await _scrape_with_retry(url, test_settings)
            
            # Should sleep with exponential backoff: 2^0, 2^1
            # (no sleep after last attempt)
            assert mock_sleep.call_count == test_settings.max_retries - 1
            sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
            assert sleep_calls == [1, 2]  # 2^0=1, 2^1=2
