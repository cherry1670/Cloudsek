from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ScrapeRequest(BaseModel):
    url: HttpUrl


class StatusResponse(BaseModel):
    url: str
    status: str
    message: str


class MetadataResponse(BaseModel):
    url: str
    status: str
    headers: dict[str, str] = Field(default_factory=dict)
    cookies: dict[str, str] = Field(default_factory=dict)
    page_source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
