from datetime import datetime, timezone
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_pending_document(url: str) -> dict[str, Any]:
    now = utcnow()
    return {
        "url": url,
        "status": "processing",
        "headers": {},
        "cookies": {},
        "page_source": None,
        "metadata": {},
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
