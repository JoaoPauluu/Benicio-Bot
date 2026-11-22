import time

from conftest import BOT_LID, GROUP, OWNER, OWNER_LID, dm, group_msg

from whatsapp_bot.incoming import Identity, Incoming, parse_event
from whatsapp_bot.registry import REGISTRY

STRANGER = "5511900000009"


async def test_commands_are_discovered(bot):
    for name in ("ajuda", "bomdia", "status", "comentarista", "agendar", "agendamentos", "desagendar",
                 "prompt", "recurso", "ia", "ping", "cargo", "cargos"):
        assert REGISTRY.find(name), name


async def test_group_without_mention_is_ignored(bot):
    await bot.handle(group_msg("status", mention=False))
    assert bot.client.sent == []


async def test_command_answers_with_native_reply(bot):
    ev = object()
    await bot.handle(group_msg("ping"), ev)
    assert bot.client.sent == [("reply", "pong 🏓", ev)]


async def test_restricted_commands_tell_others_they_are_not_allowed(bot):
    await bot.handle(group_msg("status", sender=STRANGER))
    await bot.handle(group_msg("comentarista", sender=STRANGER))
    texts = [s[1] for s in bot.client.sent]
    assert len(texts) == 2 and all("🚫" in t and "admin" in t for t in texts)
    assert "*status*" in texts[0] and "*comentarista*" in texts[1]


async def test_owner_recognised_by_lid(bot):
    await bot.handle(group_msg("status", lid=OWNER_LID))
    assert bot.client.sent and "Status" in bot.client.sent[0][1]
    assert OWNER_LID in bot.identity.owner_ids  # learned for later messages


async def test_mention_without_command_goes_to_ai(bot):
    await bot.handle(group_msg("qual a capital da França?", sender=STRANGER, name="Beto"))
    assert bot.client.sent[0][1] == "AI:Beto: qual a capital da França?"


async def test_command_prefixes_and_case(bot):
    await bot.handle(group_msg("!PING"))
    assert bot.client.sent[0][1] == "pong 🏓"


async def test_ia_feature_can_be_turned_off(bot):
    await bot.handle(group_msg("recurso ia off"))
    bot.client.sent.clear()
    await bot.handle(group_msg("oi", sender=STRANGER))
    assert bot.client.sent == []


async def test_dm_owner_needs_no_mention_but_strangers_ignored(bot):
    await bot.handle(dm("ping"))
    await bot.handle(dm("oi", sender=STRANGER))
    assert [s[1] for s in bot.client.sent] == ["pong 🏓"]


async def test_ajuda_hides_owner_commands_from_others(bot):
    await bot.handle(group_msg("ajuda", sender=STRANGER))
    text = bot.client.sent[0][1]
    assert "bomdia" in text and "status" not in text and "agendar" not in text


async def test_stale_and_own_messages_ignored(bot):
    old = group_msg("ping")
    old.timestamp = time.time() - 3600
    mine = group_msg("ping")
    mine.from_me = True
    await bot.handle(old)
    await bot.handle(mine)
    assert bot.client.sent == []


async def test_comentarista_fires_every_n_messages(bot):
    await bot.handle(group_msg("comentarista"))
    assert "ligado" in bot.client.sent[-1][1]
    bot.client.sent.clear()
    for i in range(5):
        await bot.handle(group_msg(f"msg {i}", sender=STRANGER, mention=False, name=f"P{i}"), f"ev{i}")
    await bot.drain()
    assert len(bot.ai.calls) == 1  # interval=3 in tests: fired once after 3 msgs, 2 buffered
    contents, extra = bot.ai.calls[0]
    assert "P0: msg 0" in contents and "P2: msg 2" in contents and "P3" not in contents
    assert "<comentarista>" in extra
    assert bot.client.sent[0][0] == "reply" and bot.client.sent[0][2] == "ev2"  # quotes the 3rd msg


def test_identity_strip_and_mentions():
    ident = Identity(OWNER)
    ident.set_bot("5511900000002", BOT_LID)
    inc = Incoming(chat=GROUP, sender="x", mentioned={BOT_LID}, text=f"@{BOT_LID} bomdia")
    assert ident.mentions_bot(inc)
    assert ident.strip_mentions(inc.text) == "bomdia"
    reply_to_bot = Incoming(chat=GROUP, sender="x", quoted_participant=BOT_LID)
    assert ident.mentions_bot(reply_to_bot)


def test_parse_real_protobuf_event():
    from neonize.proto import Neonize_pb2 as p
    from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import ContextInfo, ExtendedTextMessage, Message

    ev = p.Message(
        Info=p.MessageInfo(
            MessageSource=p.MessageSource(
                Chat=p.JID(User="120363000000000001", Server="g.us"),
                Sender=p.JID(User=OWNER_LID, Device=12, Server="lid"),
                SenderAlt=p.JID(User=OWNER, Server="s.whatsapp.net"),
                IsGroup=True, IsFromMe=False,
            ),
            Pushname="Ana", Timestamp=int(time.time()),
        ),
        Message=Message(extendedTextMessage=ExtendedTextMessage(
            text=f"@{BOT_LID} status",
            contextInfo=ContextInfo(mentionedJID=[f"{BOT_LID}@lid"]),
        )),
    )
    inc = parse_event(ev)
    assert inc.chat == GROUP and inc.is_group and inc.sender == OWNER_LID and inc.sender_alt == OWNER
    assert inc.mentioned == {BOT_LID} and inc.text.endswith("status") and inc.sender_name == "Ana"


def test_brazilian_ninth_digit_owner_matches_both_forms():
    # .env has the 13-digit form; WhatsApp reports the legacy 12-digit JID (and vice-versa)
    for configured, reported in (("5511987654321", "551187654321"), ("551187654321", "5511987654321")):
        ident = Identity(configured)
        inc = Incoming(chat="22235163185258@lid", sender="22235163185258", sender_alt=reported)
        ident.learn(inc)
        assert ident.is_owner(inc), (configured, reported)
        assert "22235163185258" in ident.owner_ids  # LID learned for later messages


def test_phone_variants_leaves_other_numbers_alone():
    from whatsapp_bot.incoming import phone_variants

    assert phone_variants("5511987654321") == {"5511987654321", "551187654321"}
    assert phone_variants("551187654321") == {"5511987654321", "551187654321"}
    assert phone_variants("351912345678") == {"351912345678"}
    assert phone_variants("") == set()


# ---- roles -------------------------------------------------------------

STRANGER_LID = "99009"


def test_role_expansion():
    from whatsapp_bot.roles import Role, allowed, expand

    assert expand({Role.OWNER}) == frozenset(Role)
    assert expand({Role.ADMIN}) == frozenset(Role) - {Role.OWNER}
    assert allowed({Role.ADMIN}, {Role.MEDIA})
    assert not allowed({Role.ADMIN}, {Role.OWNER})
    assert not allowed({Role.MEDIA}, {Role.ADMIN})
    assert allowed(set(), set())  # no requirement = everyone


async def test_owner_grants_admin_by_mention(bot):
    inc = group_msg(f"cargo dar admin @{STRANGER_LID}")
    inc.mentioned.add(STRANGER_LID)
    await bot.handle(inc)
    assert "admin" in bot.client.sent[-1][1] and "✅" in bot.client.sent[-1][1]
    bot.client.sent.clear()

    await bot.handle(group_msg("status", lid=STRANGER_LID, sender=STRANGER))
    assert "Status" in bot.client.sent[-1][1]
    await bot.handle(group_msg("cargo", lid=STRANGER_LID, sender=STRANGER))
    assert "🚫" in bot.client.sent[-1][1] and "dono" in bot.client.sent[-1][1]


async def test_media_cannot_run_admin_commands_and_revoke_works(bot):
    await bot.handle(group_msg(f"cargo dar media {STRANGER}"))
    await bot.handle(group_msg("status", sender=STRANGER))
    assert "🚫" in bot.client.sent[-1][1]

    await bot.handle(group_msg(f"cargo dar admin {STRANGER}"))
    await bot.handle(group_msg("status", sender=STRANGER))
    assert "Status" in bot.client.sent[-1][1]

    await bot.handle(group_msg(f"cargo tirar admin {STRANGER}"))
    await bot.handle(group_msg("status", sender=STRANGER))
    assert "🚫" in bot.client.sent[-1][1]


async def test_role_granted_by_phone_follows_lid_and_revokes_everywhere(bot):
    await bot.handle(group_msg(f"cargo dar admin +{STRANGER}"))
    # later seen by LID, with the phone as alt id: recognised, and the LID is learned
    await bot.handle(group_msg("status", lid=STRANGER_LID, sender=STRANGER))
    assert "Status" in bot.client.sent[-1][1]
    assert bot.store.roles_of({STRANGER_LID}) == {"admin"}

    # revoking by LID alone also clears the phone entry
    inc = group_msg(f"cargo tirar admin @{STRANGER_LID}")
    inc.mentioned.add(STRANGER_LID)
    await bot.handle(inc)
    await bot.handle(group_msg("status", sender=STRANGER))
    assert "🚫" in bot.client.sent[-1][1]


async def test_cargo_errors_and_listing(bot):
    await bot.handle(group_msg("cargo dar rei 5511900000009"))
    assert "desconhecido" in bot.client.sent[-1][1]
    await bot.handle(group_msg("cargo dar dono 5511900000009"))
    assert "desconhecido" in bot.client.sent[-1][1]  # owner is not grantable
    await bot.handle(group_msg("cargo dar admin"))
    assert "Diga quem" in bot.client.sent[-1][1]
    await bot.handle(group_msg("cargos"))
    assert "Ninguém" in bot.client.sent[-1][1]
    await bot.handle(group_msg(f"cargo dar mídia {STRANGER}"))
    await bot.handle(group_msg("cargos"))
    assert STRANGER in bot.client.sent[-1][1] and "mídia" in bot.client.sent[-1][1]


def test_roles_persist(tmp_path):
    from whatsapp_bot.store import Store

    s = Store(tmp_path / "state.json")
    s.grant_role({"111", "222"}, "admin")
    s.link_ids({"222", "333"})
    again = Store(tmp_path / "state.json")
    assert again.roles_of({"333"}) == {"admin"}
    assert len(again.role_holders()) == 1


async def test_ajuda_for_admin_hides_owner_commands(bot):
    bot.store.grant_role({STRANGER}, "admin")
    await bot.handle(group_msg("ajuda", sender=STRANGER))
    text = bot.client.sent[-1][1]
    assert "status" in text and "🔒 admin" in text and "cargo" not in text


async def test_dm_from_role_holder_is_answered(bot):
    bot.store.grant_role({STRANGER}, "media")
    await bot.handle(dm("ping", sender=STRANGER))
    assert "🚫" in bot.client.sent[-1][1]
