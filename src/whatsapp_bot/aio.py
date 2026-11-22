"""Minimal async client for the AIO Toolkit HTTP API (yt-dlp downloads and share links)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)


class AIOError(Exception):
    def __init__(self, message: str, logs: list[str] | None = None):
        super().__init__(message)
        self.logs = logs or []


def _error_of(resp: httpx.Response) -> AIOError:
    try:
        body = resp.json()
    except ValueError:
        return AIOError(f"HTTP {resp.status_code}")
    return AIOError(body.get("error") or f"HTTP {resp.status_code}", body.get("logs"))


class AIO:
    def __init__(self, base_url: str, timeout: float = 1800, transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._transport = transport
        self._public_url: str | None = None

    def _client(self) -> httpx.AsyncClient:
        # generous read timeout: ?wait= keeps the request open until the job ends
        timeout = httpx.Timeout(self.timeout + 60, connect=10)
        return httpx.AsyncClient(base_url=self.base_url, timeout=timeout, transport=self._transport)

    # ---- jobs ----------------------------------------------------------
    async def run(self, plugin: str, fields: dict[str, Any], files: dict[str, Path] | None = None) -> dict[str, Any]:
        """Start a job, wait for it to finish and return its JSON. Raises AIOError on failure."""
        wait = {"wait": str(int(self.timeout))}
        async with self._client() as http:
            if files:
                data = {k: (json.dumps(v) if isinstance(v, (dict, list)) else
                            str(v).lower() if isinstance(v, bool) else str(v)) for k, v in fields.items()}
                handles = {k: (p.name, p.read_bytes()) for k, p in files.items()}
                resp = await http.post(f"/api/plugins/{plugin}/run", params=wait, data=data, files=handles)
            else:
                resp = await http.post(f"/api/plugins/{plugin}/run", params=wait, json=fields)
            if resp.status_code >= 400:
                raise _error_of(resp)
            job = resp.json()
            while resp.status_code == 202 or job.get("state") in ("queued", "running"):
                resp = await http.get(f"/api/jobs/{job['id']}", params=wait)
                if resp.status_code >= 400:
                    raise _error_of(resp)
                job = resp.json()
        if job.get("state") != "done":
            raise AIOError(job.get("error") or f"job {job.get('state')}", job.get("logs"))
        return job

    async def run_ytdlp(self, urls: list[str], format: str = "mp4", quality: str | None = None,
                        bitrate: str | None = None, cookies: Path | None = None) -> dict[str, Any]:
        fields: dict[str, Any] = {"urls": "\n".join(urls), "format": format, "library": False, "playlist": False,
                                  "__title": f"WhatsApp: {urls[0]}"}
        if quality:
            fields["quality"] = quality
        if bitrate:
            fields["bitrate"] = bitrate
        files = {"cookies": cookies} if cookies and cookies.exists() else None
        return await self.run("ytdlp", fields, files)

    async def download(self, file_url: str, dest: Path) -> Path:
        """Stream one job output to ``dest`` (never held fully in memory)."""
        async with self._client() as http, http.stream("GET", file_url) as resp:
            if resp.status_code >= 400:
                await resp.aread()
                raise _error_of(resp)
            with dest.open("wb") as fh:
                async for chunk in resp.aiter_bytes(1 << 16):
                    fh.write(chunk)
        return dest

    async def delete_job(self, job_id: str) -> None:
        try:
            async with self._client() as http:
                await http.delete(f"/api/jobs/{job_id}")
        except httpx.HTTPError:
            log.warning("could not delete AIO job %s", job_id, exc_info=True)

    # ---- shares --------------------------------------------------------
    async def public_url(self) -> str:
        if self._public_url is None:
            try:
                async with self._client() as http:
                    resp = await http.get("/api/config")
                    self._public_url = (resp.json().get("public_url") or "").rstrip("/") or self.base_url
            except (httpx.HTTPError, ValueError):
                return self.base_url  # don't cache: retry next time
        return self._public_url

    async def share(self, path: Path, expires: str = "1d", note: str = "") -> str:
        """Upload ``path`` as a public share and return its link."""
        async with self._client() as http:
            with path.open("rb") as fh:
                resp = await http.post("/api/shares", data={"expires": expires, "note": note},
                                       files={"files": (path.name, fh)})
            if resp.status_code >= 400:
                raise _error_of(resp)
            share_id = resp.json()["id"]
        return f"{await self.public_url()}/files/{share_id}"
