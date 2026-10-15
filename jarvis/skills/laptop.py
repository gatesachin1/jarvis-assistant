"""Laptop apps, websites and web searches."""

from __future__ import annotations

import shutil
import urllib.parse

from jarvis.core.registry import command

# name -> (argv, needs its own console window)
LAPTOP_APPS = {
    "notepad": (["notepad.exe"], False),
    "calculator": (["calc.exe"], False),
    "calc": (["calc.exe"], False),
    "paint": (["mspaint.exe"], False),
    "file explorer": (["explorer.exe"], False),
    "explorer": (["explorer.exe"], False),
    "files": (["explorer.exe"], False),
    "command prompt": (["cmd.exe"], True),
    "cmd": (["cmd.exe"], True),
    "terminal": (["cmd.exe"], True),
    "powershell": (["powershell.exe"], True),
    "task manager": (["taskmgr.exe"], False),
    "control panel": (["control.exe"], False),
    "vs code": (["code"], False),
    "vscode": (["code"], False),
    "visual studio code": (["code"], False),
}

WEBSITES = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "chatgpt": "https://chatgpt.com",
    "gemini": "https://gemini.google.com",
    "whatsapp web": "https://web.whatsapp.com",
    "instagram web": "https://www.instagram.com",
    "linkedin": "https://www.linkedin.com",
    "classroom": "https://classroom.google.com",
    "google classroom": "https://classroom.google.com",
    "drive": "https://drive.google.com",
    "google drive": "https://drive.google.com",
    "maps": "https://maps.google.com",
    "google maps": "https://maps.google.com",
    "spotify": "https://open.spotify.com",
    "settings": "ms-settings:",
    "windows settings": "ms-settings:",
}


def open_on_laptop(ctx, name: str) -> str | None:
    """Open a known laptop app or website, or return None if unknown."""

    key = name.lower().strip()

    if key in LAPTOP_APPS:
        argv, console = LAPTOP_APPS[key]
        if argv[0] == "code":
            exe = shutil.which("code")
            if not exe:
                return "VS Code isn't on your PATH."
            argv = [exe]
        ctx.launch(argv, new_console=console)
        return f"Opening {name} on your laptop."

    if key in WEBSITES:
        ctx.open_url(WEBSITES[key])
        return f"Opening {name} on your laptop."

    if "." in key and " " not in key:  # "open wikipedia.org"
        ctx.open_url(key if key.startswith("http") else f"https://{key}")
        return f"Opening {key} in your browser."

    return None


def google_search(ctx, query: str) -> str:
    ctx.open_url("https://www.google.com/search?q=" + urllib.parse.quote_plus(query))
    return f"Searching Google for {query}."


def youtube_search_laptop(ctx, query: str) -> str:
    ctx.open_url("https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query))
    return f"Searching YouTube for {query} on your laptop."


@command(
    "google search",
    r"(?:search google for|google search for|search on google for|search for|google|search) (?P<q>.+)",
    r"(?:search|find) (?P<q>.+?) on google",
    priority=80,  # after YouTube/Spotify/WhatsApp searches
    examples=["search for python list comprehension"],
)
def search_google(ctx, req):
    return google_search(ctx, req["q"])
