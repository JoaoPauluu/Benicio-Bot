"""Command / listener / feature registry.

Add a new feature by creating a module in ``whatsapp_bot/commands/`` and using
the decorators below. Every module in that package is imported automatically.

    from whatsapp_bot.core.registry import command
    from whatsapp_bot.core.roles import Role

    @command("foo", help="faz foo", role=Role.ADMIN)   # role is optional
    async def foo(ctx: Context):
        await ctx.reply("foo!")
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from whatsapp_bot.core.roles import Role, normalize

if TYPE_CHECKING:
    from whatsapp_bot.core.context import Context

Handler = Callable[["Context"], Awaitable[None]]

COMMAND_PREFIXES = "/!"  # optional: "/ajuda" and "!ajuda" work like "ajuda"


@dataclass
class Command:
    name: str
    func: Handler
    help: str = ""
    usage: str = ""
    roles: frozenset[Role] = frozenset()   # any one of these is enough; empty = everyone
    group_only: bool = False
    aliases: tuple[str, ...] = ()


@dataclass
class Listener:
    func: Handler
    roles: frozenset[Role] = frozenset()
    name: str = ""


@dataclass
class Feature:
    """A per-chat on/off switch, toggled from chat with the ``recurso`` command."""

    name: str
    help: str = ""
    default: bool = False


@dataclass
class Registry:
    commands: dict[str, Command] = field(default_factory=dict)
    listeners: list[Listener] = field(default_factory=list)
    features: dict[str, Feature] = field(default_factory=dict)

    def find(self, word: str) -> Command | None:
        return self.commands.get(word.lstrip(COMMAND_PREFIXES).lower())

    def match(self, text: str) -> tuple[Command | None, list[str]]:
        """'baixar alta link' -> (baixar command, ['alta', 'link']); (None, words) when not a command."""
        words = text.split()
        if not words:
            return None, []
        return self.find(words[0]), words[1:]

    def unique_commands(self) -> list[Command]:
        seen: dict[str, Command] = {}
        for cmd in self.commands.values():
            seen.setdefault(cmd.name, cmd)
        return sorted(seen.values(), key=lambda c: c.name)


REGISTRY = Registry()


def command(
    name: str,
    help: str = "",
    usage: str = "",
    role: Role | Iterable[Role] | None = None,
    group_only: bool = False,
    aliases: tuple[str, ...] = (),
) -> Callable[[Handler], Handler]:
    """``role``: who may run it (one role or several, any matches). None = everyone."""

    def deco(func: Handler) -> Handler:
        cmd = Command(name.lower(), func, help, usage, normalize(role), group_only,
                      tuple(a.lower() for a in aliases))
        for key in (cmd.name, *cmd.aliases):
            REGISTRY.commands[key] = cmd
        return func

    return deco


def listener(role: Role | Iterable[Role] | None = None) -> Callable[[Handler], Handler]:
    """Run ``func`` for every incoming message (mentioned or not).

    With ``role=Role.OWNER`` (or any role) it only runs for messages from
    people holding that role, e.g. owner-specific special actions.
    """

    def deco(func: Handler) -> Handler:
        REGISTRY.listeners.append(Listener(func, normalize(role), func.__name__))
        return func

    return deco


def feature(name: str, help: str = "", default: bool = False) -> Feature:
    feat = Feature(name.lower(), help, default)
    REGISTRY.features[feat.name] = feat
    return feat


_loaded = False


def load_commands() -> Registry:
    global _loaded
    if not _loaded:
        from whatsapp_bot import commands

        for mod in pkgutil.iter_modules(commands.__path__):
            if not mod.name.startswith("_"):
                importlib.import_module(f"{commands.__name__}.{mod.name}")
        _loaded = True
    return REGISTRY
