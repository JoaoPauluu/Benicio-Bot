from conftest import BOT_LID, GROUP, group_msg

from whatsapp_bot.services.history import Entry, MessageLog


def test_message_log_chain_limit_order_and_loops():
    log = MessageLog()
    for i in range(1, 9):
        log.record("c", f"m{i}", f"P{i}", f"t{i}", f"m{i - 1}" if i > 1 else "")
    log.record("c", "other", "X", "fora da cadeia")
    assert [e.text for e in log.chain("c", "m8", 6)] == ["t3", "t4", "t5", "t6", "t7", "t8"]
    assert log.chain("c", "unknown") == [] and log.chain("other-chat", "m8") == []
    log.record("c", "a", "A", "x", "b")
    log.record("c", "b", "B", "y", "a")
    assert log.chain("c", "a") == [Entry("B", "y", "a"), Entry("A", "x", "b")]


def test_message_log_is_bounded():
    log = MessageLog(per_chat=3)
    for i in range(5):
        log.record("c", f"m{i}", "P", f"t{i}")
    assert log.chain("c", "m1") == [] and log.chain("c", "m4") == [Entry("P", "t4")]


async def test_reply_to_bot_passes_the_reply_chain(bot):
    # Ana and Benício go back and forth, every message replying to the previous one.
    await bot.handle(group_msg("oi benicio", id="u1"), "ev1")
    bot.history.record(GROUP, "noise", "Zé", "mensagem solta no grupo")  # same chat, not in the chain
    for n in range(2, 6):
        await bot.handle(group_msg(f"resposta {n}", mention=False, id=f"u{n}", quoted_id=bot.client.sent_ids[-1],
                                   quoted_participant=BOT_LID, quoted_text="(só a última)"), f"ev{n}")
    assert bot.ai.calls[-1][0].splitlines() == [
        "(Conversa anterior, respondendo em cadeia:)",
        "Ana: resposta 2", "Benício: AI:Ana: resposta 2",   # 6 earlier messages: u1 / BOT1 are cut
        "Ana: resposta 3", "Benício: AI:Ana: resposta 3",
        "Ana: resposta 4", "Benício: AI:Ana: resposta 4",
        "Ana: resposta 5",
    ]


async def test_unknown_quote_falls_back_to_quoted_text(bot):
    await bot.handle(group_msg("e ai", mention=False, id="u1", quoted_id="before-restart",
                               quoted_participant=BOT_LID, quoted_text="msg antiga"))
    assert bot.ai.calls[-1][0] == '(Em resposta a: "msg antiga")\nAna: e ai'


async def test_plain_mention_has_no_reply_context(bot):
    await bot.handle(group_msg("qual a boa", id="u1"))
    assert bot.ai.calls[-1][0] == "Ana: qual a boa"
