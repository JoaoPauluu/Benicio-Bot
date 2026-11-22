"""Command / listener / feature registry.

Add a new feature by creating a module in ``whatsapp_bot/commands/`` and using
the decorators below. Every module in that package is imported automatically.

    from whatsapp_bot.registry import command

    @command("foo", help="faz foo")
    async def foo(ctx):
        await ctx.reply("foo!")
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .context import Context

Handler = Callable[["Context"], Awaitable[None]]


@dataclass
class Command:
    name: str
    func: Handler
    help: str = ""
    usage: str = ""
    owner_only: bool = False
    group_only: bool = False
    aliases: tuple[str, ...] = ()


@dataclass
class Listener:
    func: Handler
    owner_only: bool = False
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
        return self.commands.get(word.lower())

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
    owner_only: bool = False,
    group_only: bool = False,
    aliases: tuple[str, ...] = (),
) -> Callable[[Handler], Handler]:
    def deco(func: Handler) -> Handler:
        cmd = Command(name.lower(), func, help, usage, owner_only, group_only, tuple(a.lower() for a in aliases))
        for key in (cmd.name, *cmd.aliases):
            REGISTRY.commands[key] = cmd
        return func

    return deco


def listener(owner_only: bool = False) -> Callable[[Handler], Handler]:
    """Run ``func`` for every incoming message (mentioned or not).

    With ``owner_only=True`` it only runs for messages sent by the owner,
    which is the hook for owner-specific special actions.
    """

    def deco(func: Handler) -> Handler:
        REGISTRY.listeners.append(Listener(func, owner_only, func.__name__))
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
        from . import commands

        for mod in pkgutil.iter_modules(commands.__path__):
            if not mod.name.startswith("_"):
                importlib.import_module(f"{commands.__name__}.{mod.name}")
        _loaded = True
    return REGISTRY
