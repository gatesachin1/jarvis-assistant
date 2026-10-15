import pytest

from jarvis.core.text import normalize, split_tasks


@pytest.mark.parametrize(
    "spoken, expected",
    [
        ("youtube kholo", "open youtube"),
        ("kholo instagram", "open instagram"),
        ("WhatsApp khol do", "open WhatsApp"),
        ("arijit songs youtube pe search karo", "search youtube for arijit songs"),
        ("believer spotify par bajao", "search spotify for believer"),
        ("mom ko call karo", "call mom"),
        ("reminder dikhao", "show reminders"),
        ("time kya hai", "what time is it"),
        ("  open   notepad.  ", "open notepad"),
        ("Hey JARVIS, open YouTube.", "open YouTube"),
        ("hey Jarvis open YouTube", "open YouTube"),
        ("ok jarvis what time is it?", "what time is it"),
        ("hello jarvis", "hello jarvis"),  # nothing after the wake phrase: keep it
        ("Draft a WhatsApp to 919876543210 saying Hi THERE", "Draft a WhatsApp to 919876543210 saying Hi THERE"),
    ],
)
def test_normalize(spoken, expected):
    assert normalize(spoken) == expected


KNOWN = {"open instagram", "open youtube", "search for cats", "search for dogs", "what time is it"}


def is_command(text):
    return text.lower() in KNOWN


def test_strong_separators_always_split():
    assert split_tasks("open instagram and then tell me a joke", is_command) == [
        "open instagram",
        "tell me a joke",
    ]
    assert split_tasks("open instagram phir open youtube", is_command) == ["open instagram", "open youtube"]


def test_weak_and_split_only_when_every_part_is_a_command():
    assert split_tasks("search for salt and pepper", is_command) == ["search for salt and pepper"]
    assert split_tasks("search for cats and search for dogs", is_command) == [
        "search for cats",
        "search for dogs",
    ]


def test_open_verb_is_carried_over():
    assert split_tasks("open instagram and youtube", is_command) == ["open instagram", "open youtube"]


def test_atomic_commands_are_never_split():
    text = "remind me to eat and then sleep at 6 pm"
    assert split_tasks(text, is_command, is_atomic=lambda t: True) == [text]
