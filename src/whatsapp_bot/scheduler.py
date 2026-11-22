"""Persistent scheduled messages on top of APScheduler."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

if TYPE_CHECKING:
    from .bot import Bot

log = logging.getLogger(__name__)

WEEKDAYS = {"seg": "mon", "ter": "tue", "qua": "wed", "qui": "thu", "sex": "fri",
            "sab": "sat", "sáb": "sat", "dom": "sun"}
SHORTCUTS = {"diario": "*", "diário": "*", "todo": "*", "uteis": "mon-fri", "úteis": "mon-fri", "fds": "sat,sun"}
TIME_RE = re.compile(r"^([01]?\d|2[0-3])[:h]([0-5]\d)$")


@dataclass
class Rule:
    kind: str            # "cron" | "date"
    day_of_week: str = "*"
    day: date | None = None


def parse_rule(rule: str) -> Rule | None:
    r = rule.lower().strip()
    if r in SHORTCUTS:
        return Rule("cron", SHORTCUTS[r])
    days = r.split(",")
    if all(d in WEEKDAYS for d in days):
        return Rule("cron", ",".join(WEEKDAYS[d] for d in days))
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return Rule("date", day=datetime.strptime(r, fmt).date())
        except ValueError:
            pass
    return None


def parse_agendar(args: list[str]) -> tuple[str, str, str]:
    """['08:00', 'seg,qua', 'bomdia'] -> ('08:00', 'seg,qua', 'bomdia'). Rule defaults to 'diario'."""
    if not args or not (m := TIME_RE.match(args[0])):
        raise ValueError("horário inválido, use HH:MM")
    hhmm = f"{int(m.group(1)):02d}:{m.group(2)}"
    rest = args[1:]
    rule = "diario"
    if rest and parse_rule(rest[0]) is not None:
        rule, rest = rest[0].lower(), rest[1:]
    if not rest:
        raise ValueError("faltou o que enviar (um comando, ex: bomdia, ou um texto)")
    return hhmm, rule, " ".join(rest)


def describe(item: dict) -> str:
    return f"`{item['id']}` {item['time']} ({item['rule']}) → {item['payload']}"


class Scheduler:
    def __init__(self, bot: "Bot"):
        self.bot = bot
        self.tz = ZoneInfo(bot.settings.timezone)
        self._aps = AsyncIOScheduler(timezone=self.tz)

    def start(self) -> None:
        for item in list(self.bot.store.schedules()):
            if not self._register(item):
                self.bot.store.remove_schedule(item["id"])
        self._aps.start()
        log.info("scheduler started with %d job(s)", len(self._aps.get_jobs()))

    def trigger_for(self, item: dict):
        hour, minute = map(int, item["time"].split(":"))
        rule = parse_rule(item["rule"])
        if rule is None:
            return None
        if rule.kind == "cron":
            return CronTrigger(day_of_week=rule.day_of_week, hour=hour, minute=minute, timezone=self.tz)
        when = datetime(rule.day.year, rule.day.month, rule.day.day, hour, minute, tzinfo=self.tz)
        if when <= datetime.now(self.tz):
            return None  # already in the past
        return DateTrigger(run_date=when, timezone=self.tz)

    def _register(self, item: dict) -> bool:
        trig = self.trigger_for(item)
        if trig is None:
            return False
        self._aps.add_job(self._fire, trig, args=[item], id=item["id"], replace_existing=True,
                          misfire_grace_time=300)
        return True

    def add(self, chat: str, hhmm: str, rule: str, payload: str) -> dict | None:
        probe = {"time": hhmm, "rule": rule}
        if self.trigger_for(probe) is None:
            return None
        item = self.bot.store.add_schedule(chat, hhmm, rule, payload)
        self._register(item)
        return item

    def remove(self, schedule_id: str, chat: str | None = None) -> bool:
        if not self.bot.store.remove_schedule(schedule_id, chat):
            return False
        if self._aps.get_job(schedule_id):
            self._aps.remove_job(schedule_id)
        return True

    async def _fire(self, item: dict) -> None:
        log.info("running schedule %s", item["id"])
        try:
            await self.bot.run_payload(item["chat"], item["payload"])
        finally:
            if parse_rule(item["rule"]).kind == "date":
                self.bot.store.remove_schedule(item["id"])
