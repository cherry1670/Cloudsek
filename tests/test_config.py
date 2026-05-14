from app.config import Settings


def test_settings_accept_compose_environment_values() -> None:
    settings = Settings(
        MONGODB_URI="mongodb://mongo:27017",
        MONGODB_DATABASE="metadata_service",
        REDIS_URL="redis://redis:6379/0",
        MAX_CONCURRENT_WORKERS=12,
    )

    assert settings.mongodb_uri == "mongodb://mongo:27017"
    assert settings.mongodb_database == "metadata_service"
    assert settings.redis_url == "redis://redis:6379/0"
    assert settings.max_concurrent_workers == 12
