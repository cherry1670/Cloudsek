import uvicorn

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.api:app",
        host=settings.app_host,
        port=settings.app_port,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    main()
