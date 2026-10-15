"""Android phone control: apps, YouTube, Spotify, media keys, WhatsApp, SMS and calls.

Where a phone action has a sensible laptop equivalent (YouTube, Spotify,
WhatsApp drafts, media keys) it falls back to the laptop when no phone is
connected, instead of failing.
"""

from __future__ import annotations

import logging
import re
import time
import urllib.parse

from jarvis.core.errors import JarvisError
from jarvis.core.registry import command
from jarvis.services import media_keys
from jarvis.skills.laptop import LAPTOP_APPS, WEBSITES, open_on_laptop, youtube_search_laptop

log = logging.getLogger(__name__)

MOBILE_APPS = {
    "whatsapp": "com.whatsapp",
    "instagram": "com.instagram.android",
    "youtube": "com.google.android.youtube",
    "chrome": "com.android.chrome",
    "maps": "com.google.android.apps.maps",
    "google maps": "com.google.android.apps.maps",
    "spotify": "com.spotify.music",
    "telegram": "org.telegram.messenger",
    "google": "com.google.android.googlequicksearchbox",
    "gemini": "com.google.android.apps.bard",
    "chatgpt": "com.openai.chatgpt",
    "gmail": "com.google.android.gm",
    "photos": "com.google.android.apps.photos",
    "google photos": "com.google.android.apps.photos",
    "messages": "com.google.android.apps.messaging",
    "contacts": "com.google.android.contacts",
    "phone": "com.google.android.dialer",
    "dialer": "com.google.android.dialer",
    "phonepe": "com.phonepe.app",
    "paytm": "net.one97.paytm",
    "truecaller": "com.truecaller",
    "ola": "com.olacabs.customer",
    "navi": "com.naviapp",
    "instamart": "in.swiggy.android.instamart",
    "swiggy": "in.swiggy.android",
    "my files": "com.google.android.apps.nbu.files",
    "files": "com.google.android.apps.nbu.files",
    "linkedin": "com.linkedin.android",
    "kalnirnay": "com.awt.kalnirnay",
    "videos": "com.google.android.videos",
    "drive": "com.google.android.apps.docs",
    "google drive": "com.google.android.apps.docs",
    "khatabook": "com.vaibhavkalpe.android.khatabook",
    "pdf reader": "com.smarttools.pdfreader.editor.viewer",
    "canva": "com.canva.editor",
    "apali pmpml": "in.chartr.pmpml",
    "apali pmpl": "in.chartr.pmpml",
    "pmpml": "in.chartr.pmpml",
    "play store": "com.android.vending",
    "playstore": "com.android.vending",
    "google play store": "com.android.vending",
    "classroom": "com.google.android.apps.classroom",
    "google classroom": "com.google.android.apps.classroom",
    "meesho": "com.meesho.supply",
    "flipkart": "com.flipkart.android",
    "pune metro": "org.mahametro.punemobileapp",
    "mx player": "com.mxtech.videoplayer.ad",
}

# Apps whose package differs between phone brands: open them by intent instead.
INTENT_APPS = {
    "camera": ["-a", "android.media.action.STILL_IMAGE_CAMERA"],
    "settings": ["-a", "android.settings.SETTINGS"],
    "setting": ["-a", "android.settings.SETTINGS"],
    "wifi settings": ["-a", "android.settings.WIFI_SETTINGS"],
    "bluetooth settings": ["-a", "android.settings.BLUETOOTH_SETTINGS"],
}

YOUTUBE = "com.google.android.youtube"
SPOTIFY = "com.spotify.music"
WHATSAPP = "com.whatsapp"


def _friendly(package: str) -> str:
    return package.split(".")[-1].replace("_", " ").title()


def resolve_package(ctx, name: str) -> str:
    """Map a spoken app name to an installed package name."""

    key = name.lower().strip()

    if key in MOBILE_APPS:
        return MOBILE_APPS[key]

    if re.fullmatch(r"[a-z][\w]*(\.[\w]+)+", key):
        return key  # already a package name

    compact = key.replace(" ", "")
    installed = ctx.adb.installed_packages()
    matches = sorted(
        p for p in installed
        if compact in p.lower().replace("_", "") or key in _friendly(p).lower()
    )

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        options = ", ".join(_friendly(p) for p in matches[:8])
        raise JarvisError(f"I found several matching apps: {options}. Please be more specific.")

    raise JarvisError(f"I couldn't find an app called {name} on your phone.")


def open_on_phone(ctx, name: str) -> str:
    key = name.lower().strip()

    if key in INTENT_APPS:
        ctx.adb.start_activity(*INTENT_APPS[key])
    else:
        ctx.adb.launch(resolve_package(ctx, name))

    return f"Opening {name} on your phone."


def _on_laptop_known(name: str) -> bool:
    return name.lower().strip() in LAPTOP_APPS or name.lower().strip() in WEBSITES


# --------------------------------------------------------------------- open

@command(
    "open app",
    r"(?:open|launch|start) (?P<name>.+)",
    priority=60,
    examples=["open instagram on my phone", "open notepad", "open youtube on laptop"],
)
def open_app(ctx, req):
    name = re.sub(r"^(?:the|my)\s+", "", req["name"], flags=re.I)
    name = re.sub(r"\s+app$", "", name, flags=re.I)

    if req.target == "laptop":
        return open_on_laptop(ctx, name) or f"I don't know how to open {name} on your laptop."

    if req.target == "phone":
        return open_on_phone(ctx, name)

    key = name.lower()
    phone_known = key in MOBILE_APPS or key in INTENT_APPS
    laptop_known = _on_laptop_known(name)
    prefer_phone = ctx.settings.prefer_device == "phone"

    if phone_known and (prefer_phone or not laptop_known) and ctx.phone_ready():
        return open_on_phone(ctx, name)

    if laptop_known:
        return open_on_laptop(ctx, name)

    if ctx.phone_ready():
        return open_on_phone(ctx, name)  # discover installed apps

    laptop = open_on_laptop(ctx, name)
    if laptop:
        return laptop

    if phone_known:
        return f"I can open {name} on your phone, but no phone is connected."

    return None  # let the AI answer, e.g. "start a conversation about..."


# ------------------------------------------------------------------ YouTube

@command(
    "youtube search",
    r"(?:search|find) (?:on )?youtube(?: for)? (?P<q>.+)",
    r"youtube (?:search )?(?:for )?(?P<q>.+)",
    r"(?:search|find|play) (?P<q>.+?) on youtube",
    r"play (?!(?:the )?(?:video|music|song|track)$)(?P<q>.+)",
    priority=40,
    examples=["play lofi beats", "search youtube for DBMS normalization"],
)
def youtube(ctx, req):
    query = req["q"]

    if req.target == "laptop" or (req.target is None and not ctx.phone_ready()):
        return youtube_search_laptop(ctx, query)

    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
    ctx.adb.view(url, YOUTUBE)
    return f"Searching YouTube for {query} on your phone."


# ------------------------------------------------------------------ Spotify

@command(
    "spotify search",
    r"(?:search|find|play) (?:for )?(?:on )?spotify(?: for)? (?P<q>.+)",
    r"(?:search|find|play) (?P<q>.+?) on spotify",
    r"spotify (?:search )?(?:for )?(?P<q>.+)",
    priority=35,
    examples=["play believer on spotify"],
)
def spotify(ctx, req):
    query = req["q"]
    url = "https://open.spotify.com/search/" + urllib.parse.quote(query, safe="")

    if req.target == "laptop" or (req.target is None and not ctx.phone_ready()):
        ctx.open_url(url)
        return f"Searching Spotify for {query} on your laptop."

    # Deep links replace v1's coordinate tapping, which broke on other screen sizes.
    try:
        ctx.adb.view(url, SPOTIFY)
    except JarvisError:
        ctx.adb.view("spotify:search:" + urllib.parse.quote(query, safe=""), SPOTIFY)
    return f"Searching Spotify for {query} on your phone."


# ------------------------------------------------------------ media control

PHONE_KEYS = {
    "play": "KEYCODE_MEDIA_PLAY",
    "pause": "KEYCODE_MEDIA_PAUSE",
    "resume": "KEYCODE_MEDIA_PLAY",
    "next": "KEYCODE_MEDIA_NEXT",
    "previous": "KEYCODE_MEDIA_PREVIOUS",
    "volume_up": "KEYCODE_VOLUME_UP",
    "volume_down": "KEYCODE_VOLUME_DOWN",
    "mute": "KEYCODE_VOLUME_MUTE",
    "toggle": "KEYCODE_MEDIA_PLAY_PAUSE",
}

MEDIA_REPLIES = {
    "play": "Playing.",
    "pause": "Paused.",
    "resume": "Resuming.",
    "next": "Skipping to the next track.",
    "previous": "Going back to the previous track.",
    "volume_up": "Volume increased.",
    "volume_down": "Volume decreased.",
    "mute": "Muted.",
    "toggle": "Toggled play/pause.",
}

_MEDIA_NOUN = r"(?: (?:the )?(?:video|music|song|track|playback))?"


def _media(action):
    def handler(ctx, req):
        steps = 3 if action.startswith("volume") else 1
        on_phone = req.target == "phone" or (req.target is None and ctx.phone_ready())

        if on_phone:
            for _ in range(steps):
                ctx.adb.keyevent(PHONE_KEYS[action])
            where = "on your phone"
        else:
            (ctx.media_keys or media_keys).press(action, steps if action.startswith("volume") else 1)
            where = "on your laptop"

        return f"{MEDIA_REPLIES[action][:-1]} {where}."

    return handler


command(
    "play/pause",
    r"play\s*(?:/|or)?\s*pause",
    r"toggle (?:play(?:back)?|pause|music|video)",
    priority=19,
    examples=["play pause"],
)(_media("toggle"))
command("pause", rf"(?:pause|stop){_MEDIA_NOUN}", priority=20, examples=["pause"])(_media("pause"))
command("resume", rf"(?:resume|play|continue){_MEDIA_NOUN}", priority=20)(_media("resume"))
command("next", r"(?:next|skip)(?: (?:video|song|track))?", priority=20, examples=["next song"])(_media("next"))
command("previous", r"(?:previous|prev|last)(?: (?:video|song|track))?", priority=20)(_media("previous"))
command(
    "volume up",
    r"(?:increase|raise|turn up) (?:the )?(?:volume|sound)",
    r"(?:volume|sound) up|louder",
    priority=20,
    examples=["volume up"],
)(_media("volume_up"))
command(
    "volume down",
    r"(?:decrease|lower|reduce|turn down) (?:the )?(?:volume|sound)",
    r"(?:volume|sound) down|quieter",
    priority=20,
)(_media("volume_down"))
command("mute", r"mute(?: (?:the )?(?:volume|sound))?|unmute", priority=20)(_media("mute"))


# ----------------------------------------------------------------- WhatsApp

_NUMBER = r"(?P<num>\+?\d[\d\s-]{7,}\d)"


def _digits(number: str) -> str:
    return re.sub(r"\D", "", number)


@command(
    "whatsapp draft",
    rf"(?:prepare|draft|write|send) (?:an? )?whatsapp(?: message)? to {_NUMBER}\s*(?:saying|that|:)\s*(?P<msg>.+)",
    priority=15,
    atomic=True,
    examples=["draft a whatsapp message to 919876543210 saying I'll be late"],
)
def whatsapp_draft(ctx, req):
    number = _digits(req["num"])
    url = f"https://wa.me/{number}?text={urllib.parse.quote(req['msg'])}"

    if req.target != "laptop" and ctx.phone_ready():
        ctx.adb.view(url, WHATSAPP)
        where = "on your phone"
    else:
        ctx.open_url(url)
        where = "in your browser"

    # Never auto-send: the user always reviews the message.
    return f"WhatsApp message prepared {where}. Please review it and tap Send."


@command(
    "whatsapp chat",
    rf"open (?:a )?whatsapp chat (?:with|for) {_NUMBER}",
    priority=15,
)
def whatsapp_chat(ctx, req):
    number = _digits(req["num"])
    if len(number) < 10:
        raise JarvisError("Please give the number with country code, e.g. 919876543210.")
    ctx.adb.view(f"https://wa.me/{number}", WHATSAPP)
    return "Opening the WhatsApp chat on your phone."


@command(
    "whatsapp contact search",
    r"(?:search|find) (?:for )?(?P<name>.+?) (?:in|on) whatsapp",
    priority=15,
    examples=["find rahul on whatsapp"],
)
def whatsapp_search(ctx, req):
    name = req["name"]
    if name.lower() in {"a contact", "contacts", "messages", "someone"}:
        return None

    ctx.adb.launch(WHATSAPP)
    time.sleep(2)

    if not ctx.adb.tap_node(["search"]):
        raise JarvisError("WhatsApp is open, but I couldn't find its search button.")

    time.sleep(0.5)
    ctx.adb.input_text(name)
    return f"Searching WhatsApp for {name}. Pick the right chat on your phone."


# ---------------------------------------------------------------------- SMS

@command(
    "sms draft",
    rf"(?:prepare|draft|write|send) (?:an? )?(?:sms|text message|text) to {_NUMBER}\s*(?:saying|that|:)\s*(?P<msg>.+)",
    priority=15,
    atomic=True,
    examples=["draft an sms to 9876543210 saying reached home"],
)
def sms_draft(ctx, req):
    if not ctx.phone_ready():
        raise JarvisError("SMS drafts need your phone connected.")

    ctx.adb.start_activity(
        "-a", "android.intent.action.SENDTO",
        "-d", f"sms:{_digits(req['num'])}",
        "--es", "sms_body", req["msg"],
    )
    return "SMS draft opened on your phone. Please review it before sending."


# -------------------------------------------------------------------- calls

def _lookup_contacts(ctx, name: str) -> list[tuple[str, str]]:
    output = ctx.adb.shell(
        "content", "query",
        "--uri", "content://com.android.contacts/data/phones",
        "--projection", "display_name:data1",
        timeout=20,
    )

    if "Row:" not in output:
        raise JarvisError("Contacts are not readable over ADB on this phone.")

    found = {}
    for line in output.splitlines():
        match = re.search(r"display_name=(.*?), data1=(.*)$", line)
        if match and name.casefold() in match.group(1).casefold():
            number = re.sub(r"[^\d+]", "", match.group(2))
            found.setdefault(number, match.group(1).strip())

    return [(contact, number) for number, contact in found.items()]


@command(
    "call",
    r"(?:call|phone|dial|ring)\s+(?P<who>.+)",
    r"open dialer (?:for |with )?(?P<who>.+)",
    priority=15,
    examples=["call mom", "call 9876543210"],
)
def call(ctx, req):
    who = req["who"]

    if re.fullmatch(r"\+?[\d\s()-]{7,20}", who):
        number = re.sub(r"[^\d+]", "", who)
        if len(number.lstrip("+")) < 10:
            raise JarvisError("Please provide a valid phone number.")
        ctx.adb.dial(number)
        return f"Dialer opened for {number}. Review the number and tap Call."

    try:
        matches = _lookup_contacts(ctx, who)
    except JarvisError:
        matches = None  # contacts provider blocked on this phone: use the UI instead

    if matches:
        if len(matches) > 1:
            options = "\n".join(f"{i}. {n}: {num}" for i, (n, num) in enumerate(matches[:8], 1))
            return f"I found several contacts for {who}. Say 'call' with the full name:\n{options}"

        contact, number = matches[0]
        ctx.adb.dial(number)
        return f"Dialer opened for {contact} ({number}). Review and tap Call."

    if matches == []:
        return f"I couldn't find a saved contact named {who}."

    ctx.adb.launch("com.google.android.contacts")
    time.sleep(2)
    ctx.adb.keyevent("KEYCODE_SEARCH")
    time.sleep(1)
    ctx.adb.input_text(who)
    return f"Searching Contacts for {who}. Select the right contact on your phone."
