from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.config import Settings, get_settings


def _first_content(soup: BeautifulSoup, *selectors: tuple[str, dict[str, str]]) -> str | None:
    for name, attrs in selectors:
        tag = soup.find(name, attrs=attrs)
        if tag:
            content = tag.get("content") or tag.get_text(" ", strip=True)
            if content:
                return content.strip()
    return None


def _all_meta(soup: BeautifulSoup) -> dict[str, str]:
    values: dict[str, str] = {}
    for tag in soup.find_all("meta"):
        key = tag.get("name") or tag.get("property") or tag.get("http-equiv")
        content = tag.get("content")
        if key and content:
            values[str(key)] = str(content)
    return values


def extract_metadata(html: str, base_url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    canonical = soup.find("link", rel="canonical")
    icon = soup.find("link", rel=lambda value: value and "icon" in value)

    metadata: dict[str, Any] = {
        "title": title_tag.get_text(" ", strip=True) if title_tag else None,
        "description": _first_content(
            soup,
            ("meta", {"name": "description"}),
            ("meta", {"property": "og:description"}),
        ),
        "keywords": _first_content(soup, ("meta", {"name": "keywords"})),
        "canonical_url": urljoin(base_url, canonical.get("href")) if canonical and canonical.get("href") else None,
        "favicon_url": urljoin(base_url, icon.get("href")) if icon and icon.get("href") else None,
        "open_graph": {
            key.removeprefix("og:"): value
            for key, value in _all_meta(soup).items()
            if key.startswith("og:")
        },
        "twitter": {
            key.removeprefix("twitter:"): value
            for key, value in _all_meta(soup).items()
            if key.startswith("twitter:")
        },
        "meta": _all_meta(soup),
    }
    return metadata


async def scrape_url(url: str, settings: Settings | None = None) -> dict[str, Any]:
    resolved_settings = settings or get_settings()
    headers = {"User-Agent": resolved_settings.user_agent}

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=resolved_settings.request_timeout_seconds,
        headers=headers,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

    page_source = response.text[: resolved_settings.max_page_source_chars]
    cookies = {cookie.name: cookie.value for cookie in response.cookies.jar}

    return {
        "status": "completed",
        "headers": dict(response.headers),
        "cookies": cookies,
        "page_source": page_source,
        "metadata": {
            **extract_metadata(page_source, str(response.url)),
            "final_url": str(response.url),
            "http_status": response.status_code,
            "content_type": response.headers.get("content-type"),
        },
        "error": None,
    }
