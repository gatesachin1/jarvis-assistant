"""Command registry.

Skills register handlers with the @command decorator instead of adding another
branch to a giant if/elif chain:

    @command("time", r"what time is it", examples=["what time is it"])
    def tell_time(ctx, req):
        return "..."

Patterns are matched with re.fullmatch (case-insensitive) against the task text
after any trailing device qualifier ("on my phone", "on laptop") is removed.
Handlers may return None to let the next matching command try.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

_TARGET_SUFFIX = re.compile(
    r"\s+(?:on|in|from|pe|par)\s+(?:my\s+|the\s+)?"
    r"(phone|mobile|android|laptop|pc|computer|desktop)$",
    re.I,
)
_PHONE_WORDS = {"phone", "mobile", "android"}


@dataclass
class Request:
    """What a handler receives: the task text, regex match and target device."""

    text: str
    match: re.Match
    target: str | None = None  # "phone", "laptop" or None (handler decides)

    def __getitem__(self, group):
        value = self.match.group(group)
        return value.strip() if isinstance(value, str) else value


@dataclass
class Command:
    name: str
    patterns: list[re.Pattern]
    handler: Callable
    priority: int = 50
    examples: tuple[str, ...] = ()
    atomic: bool = False  # never split this command's text on "and"/"then"
    order: int = field(default=0, compare=False)


_COMMANDS: list[Command] = []


def command(name, *patterns, priority=50, examples=(), atomic=False):
    """Register a command handler. Lower priority numbers are tried first."""

    def decorator(handler):
        _COMMANDS.append(
            Command(
                name=name,
                patterns=[re.compile(p, re.I) for p in patterns],
                handler=handler,
                priority=priority,
                examples=tuple(examples),
                atomic=atomic,
                order=len(_COMMANDS),
            )
        )
        _COMMANDS.sort(key=lambda c: (c.priority, c.order))
        return handler

    return decorator


def split_target(text: str) -> tuple[str, str | None]:
    """'open youtube on my phone' -> ('open youtube', 'phone')."""

    match = _TARGET_SUFFIX.search(text)
    if not match:
        return text, None

    word = match.group(1).lower()
    return text[: match.start()].strip(), "phone" if word in _PHONE_WORDS else "laptop"


def matches(text: str) -> Iterator[tuple[Command, Request]]:
    """Yield every (command, request) whose pattern matches, in priority order."""

    stripped, target = split_target(text)

    for cmd in list(_COMMANDS):
        for pattern in cmd.patterns:
            match = pattern.fullmatch(stripped) or (
                pattern.fullmatch(text) if stripped != text else None
            )
            if match:
                yield cmd, Request(text=text, match=match, target=target)
                break


def first_match(text: str) -> Command | None:
    return next((cmd for cmd, _ in matches(text)), None)


def commands() -> list[Command]:
    return list(_COMMANDS)
