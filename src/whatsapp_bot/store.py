"""Tiny JSON-backed persistent state (per-chat flags/prompts, schedules and global roles)."""

from __future__ import annotations

import json
import os
import secrets
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any


class Store:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {"chats": {}, "schedules": [], "roles": []}
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

    # ---- global roles --------------------------------------------------
    # {"roles": [{"ids": ["5511...", "99001"], "roles": ["admin"]}, ...]}: one record per
    # person, holding every id they were seen under (phone, 9th-digit variant, LID).
    def _people(self, ids: Iterable[str]) -> list[dict[str, Any]]:
        ids = set(ids) - {""}
        return [p for p in self._data["roles"] if ids & set(p["ids"])]

    def roles_of(self, ids: Iterable[str]) -> set[str]:
        return {r for p in self._people(ids) for r in p["roles"]}

    def grant_role(self, ids: Iterable[str], role: str) -> None:
        with self._lock:
            person = self._merge(ids)
            if role not in person["roles"]:
                person["roles"].append(role)
            self._save()

    def revoke_role(self, ids: Iterable[str], role: str) -> bool:
        with self._lock:
            changed = False
            for person in self._people(ids):
                if role in person["roles"]:
                    person["roles"].remove(role)
                    changed = True
            if changed:
                self._data["roles"] = [p for p in self._data["roles"] if p["roles"]]
                self._save()
            return changed

    def link_ids(self, ids: Iterable[str]) -> None:
        """A person with roles seen under a new id (e.g. LID next to phone): remember it."""
        ids = set(ids) - {""}
        people = self._people(ids)
        if not people or (len(people) == 1 and ids <= set(people[0]["ids"])):
            return
        with self._lock:
            self._merge(ids)
            self._save()

    def _merge(self, ids: Iterable[str]) -> dict[str, Any]:
        """Single record covering ``ids`` (merging any overlapping ones). Caller saves."""
        ids = set(ids) - {""}
        people = self._people(ids)
        merged = {"ids": sorted(ids.union(*(p["ids"] for p in people))),
                  "roles": sorted({r for p in people for r in p["roles"]})}
        self._data["roles"] = [p for p in self._data["roles"] if all(p is not q for q in people)] + [merged]
        return merged

    def role_holders(self) -> list[dict[str, Any]]:
        return [p for p in self._data["roles"] if p["roles"]]
