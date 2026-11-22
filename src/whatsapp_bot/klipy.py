"""Minimal async client for the KLIPY GIF API (https://docs.klipy.com)."""

from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)

BASE_URL = "https://api.klipy.com"
# Small renditions first: stickers must stay under WhatsApp's size limits.
SIZES = ("sm", "md", "xs", "hd")
FORMATS = ("gif", "mp4", "webp")


class KlipyError(Exception):
    pass


def media_url(item: dict) -> str | None:
    """First usable GIF/MP4/WebP url of a search result (None for ads or items without files)."""
    files = item.get("file")
    if not isinstance(files, dict):
        return None
    for size in SIZES:
        variants = files.get(size)
        if not isinstance(variants, dict):
            continue
        for fmt in FORMATS:
            media = variants.get(fmt)
            if isinstance(media, dict) and media.get("url"):
                return media["url"]
    return None


class Klipy:
    def __init__(self, api_key: str, locale: str = "br", content_filter: str = "low",
                 base_url: str = BASE_URL, transport: httpx.AsyncBaseTransport | None = None):
        self.api_key = api_key
        self.locale = locale
        self.content_filter = content_filter
        self.base_url = base_url.rstrip("/")
        self._transport = transport

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=httpx.Timeout(30, connect=10), transport=self._transport,
                                 follow_redirects=True)

    async def search(self, q: str, per_page: int = 24) -> list[str]:
        """Media urls of the GIFs matching ``q`` (may be empty). Raises KlipyError on HTTP errors."""
        if not self.enabled:
            raise KlipyError("KLIPY_API_KEY não configurada")
        params = {"q": q, "page": 1, "per_page": max(8, min(per_page, 50)), "locale": self.locale}
        if self.content_filter:
            params["content_filter"] = self.content_filter
        async with self._client() as http:
            try:
                resp = await http.get(f"{self.base_url}/api/v1/{self.api_key}/gifs/search", params=params)
            except httpx.HTTPError as e:
                raise KlipyError(f"falha de rede: {type(e).__name__}") from e
        if resp.status_code >= 400:
            raise KlipyError(f"HTTP {resp.status_code}")
        try:
            body = resp.json()
        except ValueError as e:
            raise KlipyError("resposta inválida") from e
        data = body.get("data") if isinstance(body, dict) else None
        items = data.get("data") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return []
        return [url for item in items if isinstance(item, dict) and (url := media_url(item))]

    async def download(self, url: str) -> bytes:
        async with self._client() as http:
            try:
                resp = await http.get(url)
            except httpx.HTTPError as e:
                raise KlipyError(f"falha de rede: {type(e).__name__}") from e
        if resp.status_code >= 400:
            raise KlipyError(f"HTTP {resp.status_code} ao baixar o gif")
        return resp.content
