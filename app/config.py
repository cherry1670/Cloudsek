from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "scrapper-server"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "info"

    mongodb_uri: str = Field(default="mongodb://mongo:27017", validation_alias="MONGODB_URI")
    mongodb_database: str = Field(default="metadata_service", validation_alias="MONGODB_DATABASE")
    mongodb_collection: str = Field(default="url_metadata", validation_alias="MONGODB_COLLECTION")

    redis_url: str = Field(default="redis://redis:6379/0", validation_alias="REDIS_URL")
    cache_ttl_seconds: int = Field(default=86400, validation_alias="CACHE_TTL_SECONDS")

    max_concurrent_workers: int = Field(default=10, validation_alias="MAX_CONCURRENT_WORKERS")
    request_timeout_seconds: float = Field(default=20.0, validation_alias="REQUEST_TIMEOUT_SECONDS")
    max_retries: int = Field(default=3, validation_alias="MAX_RETRIES")
    user_agent: str = Field(default="scrapper-server/1.0", validation_alias="USER_AGENT")
    max_page_source_chars: int = Field(default=500000, validation_alias="MAX_PAGE_SOURCE_CHARS")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
