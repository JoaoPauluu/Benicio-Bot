from datetime import date

import pytest
from conftest import GROUP

from whatsapp_bot.scheduler import Scheduler, parse_agendar, parse_rule


def test_parse_agendar_defaults_to_daily():
    assert parse_agendar(["8:05", "bomdia"]) == ("08:05", "diario", "bomdia")


def test_parse_agendar_with_rule_and_text():
    assert parse_agendar(["21h30", "seg,qua", "bora", "jogar"]) == ("21:30", "seg,qua", "bora jogar")


@pytest.mark.parametrize("args", [[], ["25:00", "x"], ["08:00"], ["08:00", "diario"]])
def test_parse_agendar_errors(args):
    with pytest.raises(ValueError):
        parse_agendar(args)


def test_parse_rule():
    assert parse_rule("uteis").day_of_week == "mon-fri"
    assert parse_rule("sex,sáb").day_of_week == "fri,sat"
    assert parse_rule("01/02/2099").day == date(2099, 2, 1)
    assert parse_rule("banana") is None


async def test_schedule_persists_and_runs_command(bot):
    sched = Scheduler(bot)
    bot.scheduler = sched
    item = sched.add(GROUP, "08:00", "diario", "ping")
    assert item and bot.store.schedules(GROUP)[0]["payload"] == "ping"
    assert sched.add(GROUP, "08:00", "2000-01-01", "ping") is None  # past date rejected
    await sched._fire(item)
    assert bot.client.sent == [("send", "pong 🏓", GROUP)]  # scheduled = plain message, runs as owner


async def test_schedule_plain_text_and_one_shot_removed(bot):
    sched = Scheduler(bot)
    item = sched.add(GROUP, "08:00", "2099-01-01", "Lembrete: reunião")
    await sched._fire(item)
    assert bot.client.sent == [("send", "Lembrete: reunião", GROUP)]
    assert bot.store.schedules() == []
