"""Command text clean-up: Hindi/Hinglish normalisation and multi-task splitting."""

from __future__ import annotations

import re
from collections.abc import Callable

# Whole-command phrases.
_PHRASES = {
    "reminder dikhao": "show reminders",
    "reminders dikhao": "show reminders",
    "mere reminders dikhao": "show reminders",
    "time kya hai": "what time is it",
    "kitne baje hai": "what time is it",
    "kitne baje hain": "what time is it",
    "date kya hai": "what is today's date",
    "aaj ki date kya hai": "what is today's date",
    "awaaz badhao": "volume up",
    "awaz badhao": "volume up",
    "awaaz kam karo": "volume down",
    "awaz kam karo": "volume down",
    "video roko": "pause",
    "gaana roko": "pause",
    "chup raho": "stop talking",
}

_OPEN_VERBS = r"(?:kholo|khol do|open karo|chalu karo|shuru karo)"
_SEARCH_VERBS = r"(?:search karo|dhundo|chalao|lagao|bajao)"

# (pattern, replacement) applied with fullmatch, first match wins.
# Hindi puts the verb last ("youtube kholo"), so these move it to the front.
_RULES = [
    (rf"{_OPEN_VERBS}\s+(.+)", r"open \1"),
    (rf"(.+?)\s+youtube\s+(?:pe|par)\s+{_SEARCH_VERBS}", r"search youtube for \1"),
    (rf"(.+?)\s+spotify\s+(?:pe|par)\s+{_SEARCH_VERBS}", r"search spotify for \1"),
    (r"(.+?)\s+google\s+(?:pe|par)\s+(?:search karo|dhundo)", r"search for \1"),
    (rf"(.+?)\s+(?:ko\s+)?{_OPEN_VERBS}", r"open \1"),
    (r"(.+?)\s+(?:ko\s+)?(?:call|phone)\s+karo", r"call \1"),
    (r"(.+?)\s+(?:bajao|chalao|lagao)", r"play \1"),
]
_RULES = [(re.compile(pattern, re.I), replacement) for pattern, replacement in _RULES]


def normalize(text: str) -> str:
    """Tidy whitespace/punctuation and convert common Hinglish commands to English.

    Original casing is preserved so message bodies are sent as typed.
    """

    text = re.sub(r"\s+", " ", str(text or "")).strip().rstrip(".!?").strip()

    phrase = _PHRASES.get(text.lower())
    if phrase:
        return phrase

    for pattern, replacement in _RULES:
        match = pattern.fullmatch(text)
        if match:
            return match.expand(replacement).strip()

    return text


# "and then", "then", "phir" always mean "do these in order".
_STRONG_SPLIT = re.compile(
    r"\s*,?\s+\b(?:and then|then|phir|fir|uske baad)\b\s+|\s*;\s*", re.I
)
# Plain "and" and commas are only split when every part is a real command,
# so "search for salt and pepper" stays one search.
_WEAK_SPLIT = re.compile(r"\s+and\s+|\s*,\s*", re.I)
_CARRY_VERB = re.compile(r"^(open|launch|start)\s+", re.I)


def split_tasks(
    text: str,
    is_command: Callable[[str], bool],
    is_atomic: Callable[[str], bool] = lambda _: False,
) -> list[str]:
    """Split "open instagram and then search youtube for lofi" into separate tasks."""

    text = text.strip()

    if not text or is_atomic(text):
        return [text] if text else []

    tasks = []

    for part in _STRONG_SPLIT.split(text):
        part = part.strip(" ,.")
        if part:
            tasks.extend(_weak_split(part, is_command))

    return tasks


def _weak_split(text: str, is_command: Callable[[str], bool]) -> list[str]:
    parts = [part.strip(" ,.") for part in _WEAK_SPLIT.split(text)]
    parts = [part for part in parts if part]

    if len(parts) < 2:
        return [text]

    # "open instagram and youtube" -> "open instagram", "open youtube"
    verb = _CARRY_VERB.match(parts[0])
    resolved = []

    for part in parts:
        candidate = part
        if not is_command(candidate) and verb:
            candidate = f"{verb.group(1)} {part}"
        if not is_command(candidate):
            return [text]
        resolved.append(candidate)

    return resolved
