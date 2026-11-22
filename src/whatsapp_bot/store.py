"""Tiny JSON-backed persistent state (per-chat flags/prompts and schedules)."""

from __future__ import annotations

import json
import os
import secrets
import threading
from pathlib import Path
from typing import Any


class Store:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {"chats": {}, "schedules": []}
        if path.exists():
            self._data.update(json.loads(path.read_text(encoding="utf-8")))

    def _save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)

    def _chat(self, chat: str) -> dict[str, Any]:
        return self._data["chats"].setdefault(chat, {"flags": {}, "prompt": ""})

    # ---- feature flags -------------------------------------------------
    def get_flag(self, chat: str, name: str, default: bool = False) -> bool:
        return bool(self._data["chats"].get(chat, {}).get("flags", {}).get(name, default))

    def set_flag(self, chat: str, name: str, value: bool) -> None:
        with self._lock:
            self._chat(chat)["flags"][name] = value
            self._save()

    def chats_with_flag(self, name: str) -> list[str]:
        return [c for c, d in self._data["chats"].items() if d.get("flags", {}).get(name)]

    # ---- per-chat custom prompt ----------------------------------------
    def get_prompt(self, chat: str) -> str:
        return self._data["chats"].get(chat, {}).get("prompt", "")

    def set_prompt(self, chat: str, prompt: str) -> None:
        with self._lock:
            self._chat(chat)["prompt"] = prompt
            self._save()

    # ---- schedules -----------------------------------------------------
    def schedules(self, chat: str | None = None) -> list[dict[str, Any]]:
        items = self._data["schedules"]
        return [s for s in items if chat is None or s["chat"] == chat]

    def add_schedule(self, chat: str, time: str, rule: str, payload: str) -> dict[str, Any]:
        with self._lock:
            item = {"id": secrets.token_hex(2), "chat": chat, "time": time, "rule": rule, "payload": payload}
            self._data["schedules"].append(item)
            self._save()
            return item

    def remove_schedule(self, schedule_id: str, chat: str | None = None) -> bool:
        with self._lock:
            before = len(self._data["schedules"])
            self._data["schedules"] = [
                s for s in self._data["schedules"]
                if not (s["id"] == schedule_id and (chat is None or s["chat"] == chat))
            ]
            changed = len(self._data["schedules"]) != before
            if changed:
                self._save()
            return changed
