"""Reminder commands and the (non-AI) daily planner."""

from __future__ import annotations

from datetime import datetime

from jarvis.core.errors import JarvisError
from jarvis.core.registry import command
from jarvis.services.reminders import format_when, parse_reminder


@command(
    "add reminder",
    r"remind me (?P<rest>.+)",
    r"(?:set|add|create) (?:a )?reminder (?P<rest>.+)",
    r"(?:yaad dilana|yaad dila do) (?P<rest>.+)",
    priority=25,
    atomic=True,
    examples=["remind me to submit the DBMS assignment tomorrow at 6 pm", "remind me to drink water in 30 minutes"],
)
def add_reminder(ctx, req):
    task, when = parse_reminder(req["rest"])
    if when <= datetime.now():
        raise JarvisError("That time has already passed.")
    ctx.reminders.add(task, when)
    return f"Reminder set: {task}, {format_when(when)}."


@command(
    "show reminders",
    r"(?:show|list|tell|read)(?: me)? (?:all )?(?:my )?(?:pending )?reminders?",
    r"(?:my|pending) reminders?",
    r"reminders?",
    r"what are my reminders",
    priority=25,
    examples=["show my reminders"],
)
def show_reminders(ctx, req):
    pending = ctx.reminders.pending()
    if not pending:
        return "You have no pending reminders."

    lines = ["Your pending reminders:"]
    lines += [f"{i}. {r.task} - {format_when(r.when)}" for i, r in enumerate(pending, 1)]
    return "\n".join(lines)


@command(
    "complete reminder",
    r"(?:complete|finish|done with|mark) reminder (?:number )?(?P<n>\d+)(?: (?:as )?(?:done|complete|completed))?",
    priority=25,
    examples=["mark reminder 1 done"],
)
def complete_reminder(ctx, req):
    reminder = ctx.reminders.by_number(int(req["n"]))
    ctx.reminders.complete(reminder.id)
    return f"Marked '{reminder.task}' as done."


@command(
    "delete reminder",
    r"(?:delete|remove|cancel) reminder (?:number )?(?P<n>\d+)",
    priority=25,
    examples=["delete reminder 2"],
)
def delete_reminder(ctx, req):
    reminder = ctx.reminders.by_number(int(req["n"]))
    ctx.reminders.delete(reminder.id)
    return f"Deleted the reminder '{reminder.task}'."


@command(
    "clear reminders",
    r"(?:clear|delete|remove|cancel) all(?: my)? reminders",
    priority=25,
)
def clear_reminders(ctx, req):
    count = ctx.reminders.clear_pending()
    return f"Cleared {count} pending reminder{'s' if count != 1 else ''}."


@command(
    "daily plan",
    r"(?:make|create|show|build)(?: me)? (?:my )?(?:a )?(?:daily )?(?:study )?plan(?: for today)?",
    r"(?:daily planner|plan my day|today'?s plan|my day)",
    r"what(?:'s| is) my (?:plan|schedule)(?: for today)?",
    priority=25,
    examples=["plan my day"],
)
def daily_plan(ctx, req):
    now = datetime.now()
    pending = ctx.reminders.pending()
    overdue = [r for r in pending if r.when < now]
    today = [r for r in pending if r.when >= now and r.when.date() == now.date()]
    later = [r for r in pending if r.when.date() > now.date()][:3]

    if not pending:
        return (
            "Your day is clear. Add tasks with something like "
            "'remind me to revise DBMS at 7 pm'."
        )

    lines = [f"Plan for {now.strftime('%A, %d %B')}:"]
    if overdue:
        lines.append("Overdue:")
        lines += [f"• {r.task} (was {format_when(r.when, now)})" for r in overdue]
    if today:
        lines.append("Today:")
        lines += [f"• {r.when.strftime('%I:%M %p').lstrip('0')} - {r.task}" for r in today]
    else:
        lines.append("Nothing else scheduled for today." if overdue else "Nothing scheduled for today.")
    if later:
        lines.append("Coming up:")
        lines += [f"• {r.task} - {format_when(r.when, now)}" for r in later]
    return "\n".join(lines)
