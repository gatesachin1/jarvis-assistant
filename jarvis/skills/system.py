"""Time, date, health check, help and voice on/off."""

from __future__ import annotations

from datetime import datetime

from jarvis.core.registry import command, commands
from jarvis.services import autostart, health


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
    "stop speaking",
    r"stop (?:talking|speaking)",
    r"(?:be quiet|shut up|silence|quiet|chup)",
    priority=10,
    immediate=True,
    examples=["stop talking"],
)
def stop_speaking(ctx, req):
    if ctx.speaker:
        ctx.speaker.stop()
    return "Okay."


@command(
    "voice off",
    r"(?:mute|turn off|disable) (?:your )?(?:voice|speech|talking)",
    r"(?:voice|speech) off",
    priority=10,
    immediate=True,
    examples=["voice off"],
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
    immediate=True,
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


@command(
    "autostart on",
    r"(?:start|launch|run|open) (?:jarvis |yourself )?(?:with|on|when) windows(?: starts)?",
    r"(?:enable|turn on) (?:auto ?start|start with windows|startup)",
    priority=10,
    examples=["start with windows"],
)
def autostart_on(ctx, req):
    autostart.enable()
    return "Done. I'll start minimised in the system tray whenever you sign in to Windows."


@command(
    "autostart off",
    r"(?:disable|turn off|stop) (?:auto ?start|start(?:ing)? with windows|startup)",
    r"don'?t start with windows",
    priority=10,
)
def autostart_off(ctx, req):
    autostart.disable()
    return "I won't start with Windows any more."
