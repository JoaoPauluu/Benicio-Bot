"""Settings loaded from the .env file at the project root."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Project root: holds .env, prompts/ and data/. BOT_HOME overrides it (used in Docker).
ROOT = Path(os.getenv("BOT_HOME") or Path(__file__).resolve().parents[2])


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


def parse_duration(value: str) -> float:
    """'90s' / '30m' / '1h' / '120' -> seconds."""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([smh]?)\s*", value.lower())
    if not m:
        raise ValueError(f"invalid duration: {value!r}")
    return float(m.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600}[m.group(2)]


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_model: str
    owner_number: str
    timezone: str
    bomdia_url: str
    comentarista_interval: int
    allow_dms_from_others: bool
    data_dir: Path
    prompts_dir: Path
    aio_base_url: str = "http://localhost:8765"
    baixar_timeout: float = 1800.0      # seconds
    baixar_max_mb: float = 100.0        # bigger files go to a share link instead
    baixar_share_expires: str = "1d"


def load_settings(env_file: Path | None = None) -> Settings:
    load_dotenv(env_file or ROOT / ".env")
    data_dir = Path(os.getenv("DATA_DIR", ROOT / "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        # digits only, with country code, e.g. 5511999998888
        owner_number=re.sub(r"\D", "", os.getenv("OWNER_NUMBER", "")),
        timezone=os.getenv("TIMEZONE", "America/Sao_Paulo"),
        bomdia_url=os.getenv("BOMDIA_URL", "https://www.pensador.com/frases_de_bom_dia/"),
        comentarista_interval=int(os.getenv("COMENTARISTA_INTERVAL", "10")),
        allow_dms_from_others=_bool(os.getenv("ALLOW_DMS_FROM_OTHERS"), False),
        data_dir=data_dir,
        prompts_dir=Path(os.getenv("PROMPTS_DIR", ROOT / "prompts")),
        aio_base_url=os.getenv("AIO_BASE_URL", "http://localhost:8765").rstrip("/"),
        baixar_timeout=parse_duration(os.getenv("BAIXAR_TIMEOUT", "30m")),
        baixar_max_mb=float(os.getenv("BAIXAR_MAX_MB", "100")),
        baixar_share_expires=os.getenv("BAIXAR_SHARE_EXPIRES", "1d"),
    )
