"""Roles and permission checks.

To add a role, add a member to ``Role`` and a label to ``LABELS``. The owner
and admins get it automatically. Commands then ask for it with
``@command(..., role=Role.NEW)``.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum


class Role(StrEnum):
    OWNER = "dono"    # single person, from OWNER_NUMBER; holds every role
    ADMIN = "admin"   # holds every role except owner
    MEDIA = "media"


LABELS: dict[Role, str] = {
    Role.OWNER: "dono",
    Role.ADMIN: "admin",
    Role.MEDIA: "mídia",
}

# Roles that can be given/taken with the `cargo` command.
GRANTABLE: frozenset[Role] = frozenset(Role) - {Role.OWNER}


def parse_role(name: str) -> Role | None:
    name = name.strip().lower()
    for role in Role:
        if name in (role.value, LABELS[role].lower()):
            return role
    return None


def normalize(roles: Role | Iterable[Role] | None) -> frozenset[Role]:
    if roles is None:
        return frozenset()
    if isinstance(roles, Role):
        return frozenset({roles})
    return frozenset(Role(r) for r in roles)


def from_values(values: Iterable[str]) -> set[Role]:
    """Stored role names -> Roles, ignoring names that no longer exist."""
    values = set(values)
    return {r for r in Role if r.value in values}


def expand(roles: Iterable[Role | str]) -> frozenset[Role]:
    """Owner holds everything; admin holds everything except owner."""
    out = {Role(r) for r in roles}
    if Role.OWNER in out:
        out |= set(Role)
    if Role.ADMIN in out:
        out |= set(Role) - {Role.OWNER}
    return frozenset(out)


def allowed(user_roles: Iterable[Role], required: Iterable[Role]) -> bool:
    """True if the user holds any of ``required`` (empty means everyone)."""
    required = set(required)
    return not required or bool(expand(user_roles) & required)


def ordered(roles: Iterable[Role]) -> list[Role]:
    """``roles`` in declaration order (owner first)."""
    order = list(Role)
    return sorted(roles, key=order.index)


def describe(roles: Iterable[Role]) -> str:
    return " ou ".join(LABELS[r] for r in ordered(roles))


def denied_message(what: str, required: Iterable[Role]) -> str:
    return f"🚫 Você não tem permissão para usar *{what}* (requer: {describe(required)})."
