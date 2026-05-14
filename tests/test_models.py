import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from app.models.api_models import ScrapeRequest, StatusResponse, MetadataResponse
from app.models.db_models import build_pending_document, utcnow


def test_scrape_request_valid_url():
    """Test ScrapeRequest with valid URL"""
    request = ScrapeRequest(url="https://example.com")
    assert str(request.url) == "https://example.com/"


def test_scrape_request_invalid_url():
    """Test ScrapeRequest with invalid URL raises ValidationError"""
    with pytest.raises(ValidationError):
        ScrapeRequest(url="not-a-valid-url")


def test_scrape_request_accepts_http():
    """Test ScrapeRequest accepts HTTP URLs"""
    request = ScrapeRequest(url="http://example.com")
    assert str(request.url).startswith("http://")


def test_status_response_creation():
    """Test StatusResponse model creation"""
    response = StatusResponse(
        url="https://example.com",
        status="processing",
        message="Scraping initiated"
    )
    
    assert response.url == "https://example.com"
    assert response.status == "processing"
    assert response.message == "Scraping initiated"


def test_metadata_response_with_all_fields():
    """Test MetadataResponse with all fields populated"""
    now = datetime.now(timezone.utc)
    
    response = MetadataResponse(
        url="https://example.com",
        status="completed",
        headers={"content-type": "text/html"},
        cookies={"session": "abc123"},
        page_source="<html></html>",
        metadata={"title": "Example", "description": "A test page"},
        error=None,
        created_at=now,
        updated_at=now,
    )
    
    assert response.url == "https://example.com"
    assert response.status == "completed"
    assert response.headers["content-type"] == "text/html"
    assert response.cookies["session"] == "abc123"
    assert response.page_source == "<html></html>"
    assert response.metadata["title"] == "Example"
    assert response.error is None
    assert response.created_at == now
    assert response.updated_at == now


def test_metadata_response_with_defaults():
    """Test MetadataResponse uses default values for optional fields"""
    now = datetime.now(timezone.utc)
    
    response = MetadataResponse(
        url="https://example.com",
        status="processing",
        created_at=now,
        updated_at=now,
    )
    
    assert response.headers == {}
    assert response.cookies == {}
    assert response.page_source is None
    assert response.metadata == {}
    assert response.error is None


def test_metadata_response_with_error():
    """Test MetadataResponse with error status"""
    now = datetime.now(timezone.utc)
    
    response = MetadataResponse(
        url="https://example.com",
        status="failed",
        error="Connection timeout",
        created_at=now,
        updated_at=now,
    )
    
    assert response.status == "failed"
    assert response.error == "Connection timeout"


def test_utcnow_returns_utc_datetime():
    """Test that utcnow returns timezone-aware UTC datetime"""
    now = utcnow()
    
    assert isinstance(now, datetime)
    assert now.tzinfo is not None
    assert now.tzinfo == timezone.utc


def test_build_pending_document_structure():
    """Test build_pending_document creates correct structure"""
    url = "https://example.com"
    document = build_pending_document(url)
    
    assert document["url"] == url
    assert document["status"] == "processing"
    assert document["headers"] == {}
    assert document["cookies"] == {}
    assert document["page_source"] is None
    assert document["metadata"] == {}
    assert document["error"] is None
    assert isinstance(document["created_at"], datetime)
    assert isinstance(document["updated_at"], datetime)
    assert document["created_at"] == document["updated_at"]


def test_build_pending_document_datetime_is_utc():
    """Test that build_pending_document uses UTC timezone"""
    url = "https://example.com"
    document = build_pending_document(url)
    
    assert document["created_at"].tzinfo == timezone.utc
    assert document["updated_at"].tzinfo == timezone.utc


def test_metadata_response_model_validate():
    """Test MetadataResponse.model_validate works with dict"""
    now = datetime.now(timezone.utc)
    data = {
        "url": "https://example.com",
        "status": "completed",
        "headers": {"content-type": "text/html"},
        "cookies": {},
        "page_source": "<html></html>",
        "metadata": {"title": "Example"},
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
    
    response = MetadataResponse.model_validate(data)
    
    assert response.url == "https://example.com"
    assert response.status == "completed"
    assert response.metadata["title"] == "Example"


def test_status_response_serialization():
    """Test that StatusResponse can be serialized to dict"""
    response = StatusResponse(
        url="https://example.com",
        status="processing",
        message="Scraping initiated"
    )
    
    data = response.model_dump()
    
    assert data["url"] == "https://example.com"
    assert data["status"] == "processing"
    assert data["message"] == "Scraping initiated"


def test_metadata_response_serialization():
    """Test that MetadataResponse can be serialized to dict"""
    now = datetime.now(timezone.utc)
    
    response = MetadataResponse(
        url="https://example.com",
        status="completed",
        headers={"content-type": "text/html"},
        cookies={},
        page_source="<html></html>",
        metadata={"title": "Example"},
        error=None,
        created_at=now,
        updated_at=now,
    )
    
    data = response.model_dump()
    
    assert isinstance(data, dict)
    assert data["url"] == "https://example.com"
    assert data["status"] == "completed"
    assert "created_at" in data
    assert "updated_at" in data
