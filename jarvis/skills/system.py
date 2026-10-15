"""Time, date, health check, help and voice on/off."""

from __future__ import annotations

from datetime import datetime

from jarvis.core.registry import command, commands
from jarvis.services import health


@command(
    "time",
    r"(?:what(?:'s| is) the )?(?:current )?time(?: is it)?(?: now)?(?: please)?",
    r"what time is it(?: now)?",
    r"tell me the time",
    priority=10,
    examples=["what time is it"],
)
def tell_time(ctx, req):
    return f"The time is {datetime.now().strftime('%I:%M %p').lstrip('0')}."


@command(
    "date",
    r"(?:what(?:'s| is) )?(?:today'?s|the current|the) date(?: today)?",
    r"what(?:'s| is)? the date(?: today)?",
    r"what date is (?:it|today)",
    r"what day is (?:it|today)",
    r"date",
    priority=10,
    examples=["what is today's date"],
)
def tell_date(ctx, req):
    return f"Today is {datetime.now().strftime('%A, %d %B %Y')}."


@command(
    "status",
    r"(?:show )?(?:my )?system (?:status|check)",
    r"(?:status|health check|diagnostics)",
    priority=10,
    examples=["system status"],
)
def system_status(ctx, req):
    if not ctx.health:
        return "Health check is not available."
    return health.summary(ctx.health())


@command(
    "voice off",
    r"(?:stop|mute|turn off) (?:talking|speaking|voice|speech)",
    r"(?:be quiet|shut up|silence)",
    priority=10,
    examples=["stop talking"],
)
def voice_off(ctx, req):
    if ctx.speaker:
        ctx.speaker.set_enabled(False)
    return "Voice replies are off. Say 'voice on' to hear me again."


@command(
    "voice on",
    r"(?:voice|speech|talking) on",
    r"(?:turn on|enable|unmute) (?:voice|speech|talking)",
    r"start talking",
    priority=10,
    examples=["voice on"],
)
def voice_on(ctx, req):
    if ctx.speaker:
        ctx.speaker.set_enabled(True)
    return "Voice replies are on."


@command(
    "help",
    r"help",
    r"what can you do",
    r"(?:show |list )?(?:all )?commands",
    priority=10,
    examples=["what can you do"],
)
def show_help(ctx, req):
    lines = ["Here are some things you can say:"]
    seen = set()
    for cmd in commands():
        for example in cmd.examples:
            if example not in seen:
                seen.add(example)
                lines.append(f"• {example}")
    lines.append("Anything else goes to the local AI model.")
    return "\n".join(lines)
