"""Gemini wrapper. Every request gets prompts/base.md as system instruction."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from google import genai
from google.genai import types

from .config import Settings

log = logging.getLogger(__name__)

FALLBACK_ERROR = "Desculpa, não consegui pensar em uma resposta agora. 😅"


class AI:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = settings.gemini_model
        self._client = genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else None

    def read_prompt(self, name: str) -> str:
        """Read prompts/<name>.md (re-read on every call so edits apply live)."""
        path: Path = self.settings.prompts_dir / f"{name}.md"
        try:
            return path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            log.warning("prompt file missing: %s", path)
            return ""

    def system_prompt(self, *extra: str) -> str:
        parts = [self.read_prompt("base"), *extra]
        return "\n\n".join(p for p in parts if p and p.strip())

    async def ask(self, contents: str, *extra_instructions: str) -> str:
        """Send ``contents`` to Gemini. Returns a friendly error text on failure."""
        if self._client is None:
            return "GEMINI_API_KEY não configurada no .env."
        return await self._generate(contents, *extra_instructions) or FALLBACK_ERROR

    async def gif_query(self, contents: str, *extra_instructions: str) -> str | None:
        """Ask Gemini for a short GIF search query matching ``contents``. None on failure."""
        text = await self._generate(contents, *extra_instructions, self.read_prompt("figurinha"))
        return clean_query(text) if text else None

    async def _generate(self, contents: str, *extra_instructions: str) -> str | None:
        """Raw Gemini call: the response text, or None when unavailable / on error."""
        if self._client is None:
            return None
        try:
            resp = await self._client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(system_instruction=self.system_prompt(*extra_instructions)),
            )
            return (resp.text or "").strip() or None
        except Exception:
            log.exception("Gemini request failed")
            return None


def clean_query(text: str, limit: int = 60) -> str | None:
    """First non-empty line, without quotes/markup/punctuation, capped at ``limit`` chars."""
    line = next((ln for ln in text.splitlines() if ln.strip()), "")
    line = re.sub(r"^\s*(query|busca|pesquisa)\s*:\s*", "", line, flags=re.IGNORECASE)
    line = re.sub(r"[\"'`*_#<>\[\]{}()]+", " ", line)
    line = " ".join(line.strip(" .,;:!?-").split())
    return line[:limit].strip() or None
