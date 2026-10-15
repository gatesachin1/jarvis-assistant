import customtkinter as ctk
import speech_recognition as sr
import pyttsx3
import ollama
import threading
import datetime
import subprocess
import webbrowser
import urllib.parse
import re
import os
import xml.etree.ElementTree as ET
import openwakeword
import sounddevice as sd
import numpy as np
import time
import subprocess
import json
from datetime import datetime, timedelta

ADB_PATH = r"C:\Users\saksh\Downloads\platform-tools-latest-windows\platform-tools\adb.exe"
# ==============================
# JARVIS REMINDERS AND PLANNER
# ==============================

REMINDERS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "jarvis_reminders.json"
)


def load_reminders():
    if not os.path.exists(REMINDERS_FILE):
        return []

    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return []


def save_reminders(reminder_list):
    with open(REMINDERS_FILE, "w", encoding="utf-8") as file:
        json.dump(reminder_list, file, indent=4)


reminders = load_reminders()

def open_mobile_app(package_name):
    try:
        result = subprocess.run(
            [
                ADB_PATH,
                "shell",
                "monkey",
                "-p",
                package_name,
                "1"
            ],
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode == 0:
            return f"Opening {package_name} on your phone."
        else:
            return "Sorry, I could not open that mobile app."

    except Exception as e:
        return f"Mobile app error: {e}"

# ==========================================================
# CONFIGURATION
# ==========================================================

OLLAMA_MODEL = "llama3.2:1b"

ADB_PATH = (
    r"C:\Users\saksh\Downloads"
    r"\platform-tools-latest-windows"
    r"\platform-tools\adb.exe"
)

# Keep this True if JARVIS should use your connected Android phone.
PHONE_CONTROL_ENABLED = True


# ==========================================================
# TEXT TO SPEECH
# ==========================================================

engine = pyttsx3.init()
engine.setProperty("rate", 175)

speech_lock = threading.Lock()


def speak(text):
    """Speak the response without blocking the GUI."""

    print("JARVIS:", text)

    def run_speech():
        with speech_lock:
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception as error:
                print("Speech error:", error)

    threading.Thread(
        target=run_speech,
        daemon=True
    ).start()


# ==========================================================
# ANDROID ADB FUNCTIONS
# ==========================================================

def adb_command(args, timeout=20):
    """Run an ADB command and return its output."""

    if not os.path.exists(ADB_PATH):
        raise RuntimeError(
            "ADB was not found. Check the ADB_PATH at the top "
            "of the code."
        )

    try:
        result = subprocess.run(
            [ADB_PATH] + list(args),
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=getattr(
                subprocess,
                "CREATE_NO_WINDOW",
                0
            )
        )
        print("ADB RETURN CODE:", result.returncode)
        print("ADB STDOUT:", repr(result.stdout))
        print("ADB STDERR:", repr(result.stderr))

        if result.returncode != 0:
            error = result.stderr.strip()

            raise RuntimeError(
                error or "ADB command failed."
            )

        return result.stdout.strip()

    except subprocess.TimeoutExpired:
        raise RuntimeError("The phone did not respond in time.")


def connected_device():
    """Find an authorized Android device."""

    output = adb_command(["devices"])

    devices = []

    for line in output.splitlines()[1:]:
        parts = line.strip().split()

        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])

    if not devices:
        raise RuntimeError(
            "No authorized Android phone found. "
            "Connect your phone and allow USB debugging."
        )

    return devices[0]


def phone_shell(args, timeout=20):
    """Execute a shell command on the connected phone."""

    device = connected_device()

    return adb_command(
        ["-s", device, "shell"] + list(args),
        timeout=timeout
    )
def open_whatsapp():
    try:
        package = resolve_app("whatsapp")
        open_app_by_package(package)
        return "WhatsApp is opening on your phone."
    except Exception as e:
        return f"Sorry, I couldn't open WhatsApp: {e}"    


def open_app_by_package(package):
    """Launch an Android app using its package name."""

    phone_shell([
        "monkey",
        "-p",
        package,
        "-c",
        "android.intent.category.LAUNCHER",
        "1"
    ])

    return f"Opening {package} on your phone."


# ==========================================================
# DISCOVER INSTALLED ANDROID APPS
# ==========================================================

def get_installed_apps():
    """
    Discover Android apps that have launcher activities.

    Returns:
        Dictionary mapping package names to package names.
        Package names are used as reliable identifiers.
    """

    output = phone_shell([
        "cmd",
        "package",
        "query-activities",
        "--brief",
        "-a",
        "android.intent.action.MAIN",
        "-c",
        "android.intent.category.LAUNCHER"
    ], timeout=30)

    apps = {}

    for line in output.splitlines():
        line = line.strip()

        if "/" not in line:
            continue

        if line.startswith("No activities"):
            continue

        package, activity = line.split("/", 1)

        package = package.strip()

        if not package:
            continue

        apps[package.lower()] = package

    return apps


def friendly_app_name(package):
    """Create a readable fallback name from a package name."""

    last_part = package.split(".")[-1]

    return last_part.replace("_", " ").title()


def resolve_app(query):
    """Find an installed Android app by name or package."""

    query = query.lower().strip()

    aliases = {
        "google maps": ["maps", "com.google.android.apps.maps"],
        "maps": ["maps", "com.google.android.apps.maps"],
        "play store": ["vending", "com.android.vending"],
        "google play store": ["vending", "com.android.vending"],
        "google photos": ["photos", "com.google.android.apps.photos"],
        "photos": ["photos", "com.google.android.apps.photos"],
        "whatsapp": ["whatsapp", "com.whatsapp"],
        "instagram": ["instagram", "com.instagram.android"],
        "youtube": ["youtube", "com.google.android.youtube"],
        "phone": ["dialer", "com.google.android.dialer"],
        "camera": ["camera", "com.android.camera"],
        "chrome": ["chrome", "com.android.chrome"],
        "gmail": ["gmail", "com.google.android.gm"],
        "spotify": ["spotify", "com.spotify.music"],
        "telegram": ["telegram", "org.telegram.messenger"],
        "phonepe": ["phonepe", "com.phonepe.app"],
        "paytm": ["paytm", "net.one97.paytm"],
        "messages": ["messages", "com.google.android.apps.messaging"],
    }

    apps = get_installed_apps()

    # First, try exact package-name matching.
    for package in apps.values():
        if query == package.lower():
            return package

    # Try aliases and package names.
    possible_terms = aliases.get(query, [query])

    for term in possible_terms:
        for package in apps.values():
            if term.lower() == package.lower():
                return package

    # Search for a match within package names.
    matches = []

    for package in apps.values():
        package_lower = package.lower()
        package_name = friendly_app_name(package).lower()

        if (
            query in package_lower
            or query in package_name
        ):
            matches.append(package)

    matches = list(dict.fromkeys(matches))

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        options = ", ".join(
            friendly_app_name(package)
            for package in matches[:8]
        )

        raise RuntimeError(
            f"I found multiple matching apps: {options}. "
            "Please say the app name more specifically."
        )

    raise RuntimeError(
        f"I couldn't find an installed app matching {query}. "
        "Try its exact package name."
    )


# ==========================================================
# WHATSAPP CONTACT SEARCH
# ==========================================================

def search_whatsapp_contact(contact_name):
    """
    Open WhatsApp and attempt to use its search interface.

    The user must choose the correct contact manually.
    
    """
    if not isinstance(contact_name, str) or not contact_name.strip():
     raise ValueError("Please provide a valid WhatsApp contact name.")

    

    package = resolve_app("whatsapp")

    open_app_by_package(package)

    # Allow WhatsApp time to open.
    import time
    time.sleep(2)

    # Save the current screen's UI hierarchy.
    phone_shell([
        "uiautomator",
        "dump",
        "/sdcard/window.xml"
    ], timeout=30)

    xml_text = phone_shell([
        "cat",
        "/sdcard/window.xml"
    ], timeout=15)

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        raise RuntimeError(
            "I couldn't read WhatsApp's screen. "
            "Please open WhatsApp and try again."
        )

    search_bounds = None

    for node in root.iter("node"):
        description = node.attrib.get(
            "content-desc", ""
        ).lower()

        text = node.attrib.get(
            "text", ""
        ).lower()

        if (
            "search" in description
            or "search" in text
        ):
            search_bounds = node.attrib.get("bounds")
            break

    if not search_bounds:
        raise RuntimeError(
            "I couldn't locate WhatsApp search. "
            "Please tap the search icon manually."
        )

    numbers = re.findall(r"\d+", search_bounds)

    if len(numbers) != 4:
        raise RuntimeError(
            "Couldn't determine the search icon position."
        )

    x1, y1, x2, y2 = map(int, numbers)

    x = (x1 + x2) // 2
    y = (y1 + y2) // 2

    phone_shell([
        "input",
        "tap",
        str(x),
        str(y)
    ])

    time.sleep(0.5)

    # ADB input text requires spaces to be escaped.
    safe_name = contact_name.replace(" ", "%s")


    phone_shell([
        "input",
        "text",
        safe_name
    ])
    time.sleep(1)

    


# ==========================================================
# WHATSAPP MESSAGE PREPARATION
# ==========================================================

def prepare_whatsapp(phone, message):
    """
    Open a WhatsApp conversation using a phone number.

    This prepares the message; it does not automatically send it.
    """

    phone = re.sub(r"\D", "", phone)

    if not phone:
        return "Please provide a valid phone number."

    encoded_message = urllib.parse.quote(message)

    url = (
        f"https://wa.me/{phone}"
        f"?text={encoded_message}"
    )

    webbrowser.open(url)

    return (
        "I prepared your WhatsApp message. "
        "Please review it and press Send yourself."
    )


def prepare_sms(phone, message):
    """Open the phone's SMS composer with a draft."""

    phone = re.sub(r"\D", "", phone)

    if not phone:
        return "Please provide a valid phone number."

    encoded_message = urllib.parse.quote(message)

    url = f"sms:{phone}?body={encoded_message}"

    webbrowser.open(url)

    return (
        "I opened the SMS draft. "
        "Please review it before sending."
    )


def open_dialer(phone):
    """Open the phone dialer with a number."""

    phone = re.sub(r"[^\d+]", "", phone)

    if not phone:
        return "Please provide a valid phone number."

    phone_shell([
        "am",
        "start",
        "-a",
        "android.intent.action.DIAL",
        "-d",
        f"tel:{phone}"
    ])

    return (
        f"I opened the dialer for {phone}. "
        "Please review the number before calling."
    )


# ==========================================================
# LAPTOP CONTROLS
# ==========================================================

def open_laptop_app(app_name):
    """Open common Windows applications."""

    apps = {
        "notepad": ["notepad.exe"],
        "calculator": ["calc.exe"],
        "paint": ["mspaint.exe"],
        "file explorer": ["explorer.exe"],
        "explorer": ["explorer.exe"],
        "command prompt": ["cmd.exe"],
    }

    key = (app_name or "").lower().strip()

    if key in apps:
        subprocess.Popen(apps[key])
        return f"Opening {app_name} on your laptop."

    return None


# ==========================================================
# WEBSITE AND SEARCH CONTROLS
# ==========================================================

def open_website(name):
    """Open known websites on the laptop."""

    websites = {
        "google": "https://www.google.com",
        "youtube": "https://www.youtube.com",
        "gmail": "https://mail.google.com",
        "github": "https://github.com",
        "chatgpt": "https://chatgpt.com",
        "whatsapp web": "https://web.whatsapp.com",
        "instagram web": "https://www.instagram.com",
        "gemini": "com.google.android.apps.bard",
"ola": "com.olacabs.customer",
"navi": "com.naviapp",
"instamart": "in.swiggy.android.instamart",
"my files": "com.google.android.apps.nbu.files",
"files": "com.google.android.apps.nbu.files",
"linkedin": "com.linkedin.android",
"settings": "com.android.settings",
"setting": "com.android.settings",
"kalnirnay": "com.awt.kalnirnay",
"videos": "com.google.android.videos",
"drive": "com.google.android.apps.docs",
"swiggy": "in.swiggy.android",
"khatabook": "com.vaibhavkalpe.android.khatabook",
"pdf reader": "com.smarttools.pdfreader.editor.viewer",
"canva": "com.canva.editor",
"apali pmpl": "in.chartr.pmpml",
"pmpml": "in.chartr.pmpml",
"play store": "com.android.vending",
"playstore": "com.android.vending",
"classroom": "com.google.android.apps.classroom",
"meesho": "com.meesho.supply",
"flipkart": "com.flipkart.android",
"pune metro": "org.mahametro.punemobileapp",
"mx player": "com.mxtech.videoplayer.ad",
"google": "com.google.android.googlequicksearchbox",
    }

    key = name.lower().strip()

    if key in websites:
        webbrowser.open(websites[key])

        return f"Opening {name} on your laptop."

    return None


def google_search(query):
    """Search Google."""

    url = (
        "https://www.google.com/search?q="
        + urllib.parse.quote_plus(query)
    )

    webbrowser.open(url)

    return f"Searching Google for {query}."


def youtube_search(query):
    """Search YouTube."""

    url = (
        "https://www.youtube.com/results?search_query="
        + urllib.parse.quote_plus(query)
    )

    webbrowser.open(url)

    return f"Searching YouTube for {query}."


# ==========================================================
# COMMAND EXECUTION
# ==========================================================
# -----------------------------------
# MULTI-TASK GOOGLE SEARCH
def execute_multiple_google_tasks(command):
    text = command.strip()

    # Split commands into separate tasks
    tasks = re.split(
        r"\s+and then\s+|\s+then\s+|\s+and search for\s+",
        text,
        flags=re.IGNORECASE
    )

    tasks = [task.strip(" .,") for task in tasks if task.strip(" .,")]

    if len(tasks) <= 1:
        return None

    results = []

    for task in tasks:
        task_lower = task.lower().strip()

        # Search Google
        if task_lower.startswith("search for "):
            query = task[len("search for "):].strip()

            if query:
                url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
                webbrowser.open(url, new=2)
                results.append(f"Searching Google for {query}")

        # Open Google
        elif task_lower in ("open google", "open google.com"):
            webbrowser.open("https://www.google.com", new=2)
            results.append("Opening Google")

        # Search Google for a phrase without 'search for'
        elif task_lower.startswith("search "):
            query = task[len("search "):].strip()

            if query:
                url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
                webbrowser.open(url, new=2)
                results.append(f"Searching Google for {query}")

        else:
            results.append(f"Task not recognized: {task}")

    return "\n".join(results)
# -----------------------------------

'''def execute_multiple_google_tasks(command):
    """
    Split a command into tasks using 'and then',
    'then', or 'and search for'.
    """

    text = command.strip()

    # Split the command into separate tasks
    tasks = re.split(
        r"\s+and then\s+|\s+then\s+|\s+and search for\s+",
        text,
        flags=re.IGNORECASE
    )

    tasks = [task.strip(" .,") for task in tasks if task.strip(" .,")]

    if len(tasks) <= 1:
        return None

    results = []

    for task in tasks:
        task_lower = task.lower().strip()

        # Search Google
        if task_lower.startswith("search for "):
            query = task[11:].strip()

            if query:
                url = (
                    "https://www.google.com/search?q="
                    + urllib.parse.quote_plus(query)
                )
                webbrowser.open_new_tab(url)
                results.append(f"Searching Google for {query}")

        # Open Google
        elif task_lower in ("open google", "open google.com"):
            webbrowser.open_new_tab("https://www.google.com")
            results.append("Opening Google")

        # Open YouTube
        elif task_lower in ("open youtube", "open youtube.com"):
            webbrowser.open_new_tab("https://www.youtube.com")
            results.append("Opening YouTube")

        # Open a website for other tasks
        else:
            results.append(
                f"I couldn't identify this task: {task}"
            )

    return "\n".join(results) if results else "No tasks completed."'''
    

def execute_one(command):
        
        # Handle multiple Google-related tasks
    multi_result = execute_multiple_google_tasks(command)
    

    if multi_result is not None:
        return multi_result
    """Execute one command at a time."""

    text = command.lower().strip()
    if not text:
            return None
    


    # OPEN GOOGLE CLASSROOM ON MOBILE
    if re.search(r"\b(open|launch|start)\s+(google\s+)?classroom\b", text, re.I):
        try:
            phone_shell([
                "monkey",
                "-p",
                "com.google.android.apps.classroom",
                "1"
            ])
            return "Opening Google Classroom on your mobile."
        except Exception as error:
            return f"Could not open Classroom: {error}"

    # Tumhare existing command handlers yahan se continue honge    
    
    low = text.lower()
    
    

    if not text:
        return None
        

    # -------------------------------
    # TIME AND DATE
    #
    # -------------------------------
    if re.search(r"\b(open|launch|start)\s+whatsapp\b", text, re.I):
         return open_whatsapp()
    if re.search(r"\b(time|current time)\b", low):
        now = datetime.datetime.now().strftime("%I:%M %p")
        return f"The time is {now}."

    if re.search(r"\b(today's date|current date|what date)\b", low):
        today = datetime.datetime.now().strftime("%d %B %Y")
        return f"Today's date is {today}."

    # -------------------------------
    # WHATSAPP MESSAGE DRAFT
    # -------------------------------

    match = re.search(
        r"(?:prepare|draft|write)\s+"
        r"(?:a\s+)?whatsapp message\s+"
        r"to\s+(\+?\d[\d\s-]{7,})\s*"
        r"(?:saying|that|:)\s*(.+)",
        text,
        re.I
    )

    if match:
        return prepare_whatsapp(
            match.group(1),
            match.group(2).strip()
        )

    # -------------------------------
    # SMS DRAFT
    # -------------------------------

    match = re.search(
        r"(?:prepare|draft)\s+(?:an?\s+)?sms\s+"
        r"to\s+(\+?\d[\d\s-]{7,})\s*"
        r"(?:saying|that|:)\s*(.+)",
        text,
        re.I
    )

    if match:
        return prepare_sms(
            match.group(1),
            match.group(2).strip()
        )

    # -------------------------------
    # DIAL A NUMBER
    # -------------------------------

    match = re.search(
        r"(?:open dialer|dial|call)\s+"
        r"(\+?\d[\d\s-]{7,})",
        text,
        re.I
    )

    if match:
        return open_dialer(match.group(1))

    # -------------------------------
    # WHATSAPP CONTACT SEARCH
    # -------------------------------

    match = re.search(
        r"(?:search|find)\s+(?:for\s+)?"
        r"(.+?)\s+(?:in|on)\s+whatsapp",
        text,
        re.I
    )

    if match:
        
        contact = (match.group(1) or "").strip()

        if contact.lower() not in {
            "a contact",
            "contacts",
            "messages",
        }:
            return search_whatsapp_contact(contact)

    # -------------------------------
    # PHONE APP LAUNCH
    # -------------------------------

    match = re.match(
        r"(?:open|launch|start)\s+(.+?)"
        r"(?:\s+on my phone|\s+on phone|\s+on mobile)?$",
        text,
        re.I
    )

    if match:
        app_name = match.group(1).strip()

        mobile_requested = bool(
            re.search(
                r"\s+on my phone$|\s+on phone$|\s+on mobile$",
                text,
                re.I
            )
        )

        # Known websites without a phone qualifier open on laptop.
        laptop_website = open_website(app_name)

        if laptop_website and not mobile_requested:
            return laptop_website

        # Known Windows applications open on laptop.
        laptop_app = open_laptop_app(app_name)

        if laptop_app and not mobile_requested:
            return laptop_app

        if PHONE_CONTROL_ENABLED:
            try:
                package = resolve_app(app_name)
                return open_app_by_package(package)

            except RuntimeError:
                if mobile_requested:
                    raise

        # Try a known website as a fallback.
        if laptop_website:
            return laptop_website

        if laptop_app:
            return laptop_app

    # -----------------
    # --------------
    # GOOGLE SEARCH
    # -------------------------------
     
    match = re.match(
        r"(?:search google for|google search for|"
        r"search for|google)\s+(.+)",
        text,
        re.I
    )

    if match:
        query = match.group(1).strip()

        if query:
            return google_search(query)

    # -------------------------------
    # YOUTUBE SEARCH
    # -------------------------------

    match = re.match(
        r"(?:search youtube for|youtube search for|"
        r"play|search youtube)\s+(.+)",
        text,
        re.I
    )

    if match:
        query = match.group(1).strip()

        if query:
            return youtube_search(query)

    # -------------------------------
    # EXPLICIT LAPTOP WEBSITE
    # -------------------------------

    match = re.match(
        r"(?:open|launch|start)\s+"
        r"(google|youtube|gmail|github|chatgpt|"
        r"whatsapp web|instagram web)"
        r"(?:\s+on my laptop|\s+on laptop)?$",
        text,
        re.I
    )

    if match:
        return open_website(match.group(1))

    # -------------------------------
    # EXPLICIT LAPTOP APPLICATION
    # -------------------------------

    match = re.match(
        r"(?:open|launch|start)\s+"
        r"(notepad|calculator|paint|file explorer|"
        r"explorer|command prompt)"
        r"(?:\s+on my laptop|\s+on laptop)?$",
        text,
        re.I
    )

    if match:
        return open_laptop_app(match.group(1))

    return None


# ==========================================================
# MULTIPLE COMMAND SUPPORT
# ==========================================================

def split_tasks(text):
    """
    Split simple multi-action commands.

    Examples:
        Open Instagram on my phone and then open YouTube on my phone
        Open Google and then open Notepad
    """

    # Protect message bodies after a colon.
    # This prevents "and then" inside a message from being split.
    if ":" in text:
        command_part, message_part = text.split(":", 1)

        if re.search(
            r"\b(whatsapp message|sms)\b",
            command_part,
            re.I
        ):
            return [text]

    parts = re.split(
        r"\s+(?:and then|then)\s+|\s+and\s+",
        text,
        flags=re.I
    )

    return [
        part.strip(" ,.")
        for part in parts
        if part.strip(" ,.")
    ]
    


def handle_message(user_text):
    """Process user requests and return a response."""

    user_text = user_text.strip()

    if not user_text:
        return "Please tell me what you want me to do."

    tasks = split_tasks(user_text)

    results = []

    for task in tasks:
        try:
            result = execute_one(task)

            if result:
                results.append(result)

        except Exception as error:
            results.append(
                f"I couldn't complete '{task}': {error}"
            )

    if results:
        return " ".join(results)

    # If no command matched, use local Ollama AI.
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are JARVIS, a helpful desktop AI "
                        "assistant. Respond clearly and briefly. "
                        "Do not claim to have performed actions "
                        "unless a command handler confirmed them."
                    )
                },
                {
                    "role": "user",
                    "content": user_text
                }
            ]
        )

        return response["message"]["content"]

    except Exception as error:
        return (
            "I couldn't connect to the local AI model. "
            "Check whether Ollama is running and the model "
            f"{OLLAMA_MODEL} is installed. Details: {error}"
        )


# ==========================================================
# VOICE INPUT
# ==========================================================

def listen():
    """Listen for one voice command."""

    recognizer = sr.Recognizer()

    try:
        with sr.Microphone() as source:
            update_status("Listening...")

            recognizer.adjust_for_ambient_noise(
                source,
                duration=0.5
            )

            audio = recognizer.listen(
                source,
                timeout=5,
                phrase_time_limit=12
            )
        update_status("Recognizing...")

        # Google speech recognition
        # Ollama handles AI responses locally.

        command = recognizer.recognize_google(
            audio,
            language="en-IN"
        )

        add_message("YOU", command)
        process_command(command)
       

    except sr.WaitTimeoutError:
        update_status("No speech detected.")

    except sr.UnknownValueError:
        update_status("I couldn't understand that.")

    except sr.RequestError:
        update_status(
            "Voice recognition needs an internet connection."
        )

    except Exception as error:
        update_status(f"Voice error: {error}")


# ==========================================================
# GUI
# ==========================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
'''app.configure(fg_color="#050B16")
app.geometry("1000x750")
app.minsize(800, 600)
app.title("J.A.R.V.I.S - AI Assistant")
app.geometry("900x650")
app.minsize(700, 500)

app.configure(fg_color="#050B18")'''
# ===== JARVIS PROFESSIONAL THEME =====

BG_COLOR = "#070B16"
PANEL_COLOR = "#101A2B"
CARD_COLOR = "#152238"

CYAN = "#00E5FF"
BLUE = "#60A5FA"
PURPLE = "#A78BFA"
GREEN = "#34D399"
YELLOW = "#FBBF24"
RED = "#FB7185"

TEXT_COLOR = "#F1F5F9"
MUTED_COLOR = "#94A3B8"
BORDER_COLOR = "#293B55"

app.configure(fg_color=BG_COLOR)
app.geometry("1100x780")
app.minsize(850, 650)

# Header
header = ctk.CTkFrame(
    app,
    fg_color=PANEL_COLOR,
    corner_radius=18,
    border_width=1,
    border_color=CYAN
)

title_label = ctk.CTkLabel(
    header,
    text="J.A.R.V.I.S",
    font=("Consolas", 32, "bold"),
    text_color=CYAN
)
title_label.pack(pady=(15, 5))

subtitle_label = ctk.CTkLabel(
    header,
    text="PERSONAL AI COMMAND CENTER",
    font=("Consolas", 11),
    text_color=MUTED_COLOR
)

subtitle_label.pack(pady=(0, 15))
# ==============================
# JARVIS FEATURE DASHBOARD
# ==============================

dashboard = ctk.CTkFrame(
    app,
    fg_color="#0B1930",
    corner_radius=15
)

dashboard.pack(
    fill="x",
    padx=20,
    pady=(5, 10)
)

dashboard_heading = ctk.CTkLabel(
    dashboard,
    text="JARVIS CONTROL CENTER",
    font=("Arial", 16, "bold"),
    text_color="#00D9FF"
)

dashboard_heading.pack(
    anchor="w",
    padx=15,
    pady=(12, 8)
)

dashboard_buttons = ctk.CTkFrame(
    dashboard,
    fg_color="transparent"
)

dashboard_buttons.pack(
    fill="x",
    padx=10,
    pady=(0, 12)
)


def dashboard_command(command_text):
    command_entry.delete(0, "end")
    command_entry.insert(0, command_text)
    process_command(command_text)


dashboard_features = [
    ("⏰ Reminders", "show my reminders"),
    ("📅 Daily Planner", "make my daily study plan"),
    ("📚 Study Assistant", "help me study"),
    ("🎯 Quiz Mode", "start quiz mode"),
    ("📱 WhatsApp", "open whatsapp"),
    ("🎵 Spotify", "search spotify for music")
]

for index, (label, command_text) in enumerate(dashboard_features):

    button = ctk.CTkButton(
        dashboard_buttons,
        text=label,
        height=36,
        font=("Arial", 12, "bold"),
        fg_color="#123453",
        hover_color="#087EAD",
        text_color="#FFFFFF",
        corner_radius=8,
        command=lambda cmd=command_text: dashboard_command(cmd)
    )

    button.grid(
        row=index // 3,
        column=index % 3,
        padx=5,
        pady=5,
        sticky="ew"
    )

for column in range(3):
    dashboard_buttons.grid_columnconfigure(
        column,
        weight=1
    )


# Status
'''status_label = ctk.CTkLabel(
    app,
    text="SYSTEM ONLINE",
    font=("Arial", 12, "bold"),
    text_color="#00D9FF"
)'''
status_label = ctk.CTkLabel(
    app,
    text="● SYSTEM ONLINE",
    font=("Consolas", 13, "bold"),
    text_color="#00FF9C",
    fg_color="#0B1628",
    corner_radius=10
)


status_label.pack(pady=5)


# Conversation display
chat_box = ctk.CTkTextbox(
    app,
    font=("Arial", 14),
    corner_radius=12,
    fg_color="#0B1528",
    text_color="#E8F1FF",
    wrap="word"
)

chat_box.pack(
    fill="both",
    expand=True,
    padx=20,
    pady=10
)

chat_box.configure(state="disabled")


def add_message(sender, message):
    """Add a message to the conversation window."""

    def update():
        chat_box.configure(state="normal")

        chat_box.insert(
            "end",
            f"{sender}: {message}\n\n"
        )

        chat_box.see("end")
        chat_box.configure(state="disabled")

    app.after(0, update)


def update_status(message):
    """Safely update the GUI status."""

    app.after(
        0,
        lambda: status_label.configure(text=message)
    )
ADB_PATH = r"C:\Users\saksh\Downloads\platform-tools-latest-windows\platform-tools\adb.exe"

MOBILE_APPS = {
    "whatsapp": "com.whatsapp",
    "instagram": "com.instagram.android",
    "youtube": "com.google.android.youtube",
    "chrome": "com.android.chrome",
    "maps": "com.google.android.apps.maps",
    "spotify": "com.spotify.music",
    "telegram": "org.telegram.messenger",
    "google": "com.google.android.googlequicksearchbox",
    "gemini": "com.google.android.apps.bard",
    "chatgpt": "com.openai.chatgpt",
"ola": "com.olacabs.customer",
"navi": "com.naviapp",
"instamart": "in.swiggy.android.instamart",
"my files": "com.google.android.apps.nbu.files",
"files": "com.google.android.apps.nbu.files",
"linkedin": "com.linkedin.android",
"settings": "com.android.settings",
"setting": "com.android.settings",
"kalnirnay": "com.awt.kalnirnay",
"videos": "com.google.android.videos",
"drive": "com.google.android.apps.docs",
"swiggy": "in.swiggy.android",
"khatabook": "com.vaibhavkalpe.android.khatabook",
"pdf reader": "com.smarttools.pdfreader.editor.viewer",
"canva": "com.canva.editor",
"apali pmpl": "in.chartr.pmpml",
"pmpml": "in.chartr.pmpml",
"play store": "com.android.vending",
"playstore": "com.android.vending",
"truecaller": "com.truecaller",
"meesho": "com.meesho.supply",
"flipkart": "com.flipkart.android",
"pune metro": "org.mahametro.punemobileapp",
"mx player": "com.mxtech.videoplayer.ad",
}


def open_mobile_app(app_name):
    package_name = MOBILE_APPS.get(app_name.lower().strip())

    if not package_name:
        return f"Sorry, I don't know the mobile app {app_name}."

    try:
        result = subprocess.run(
            [
                ADB_PATH,
                "shell",
                "monkey",
                "-p",
                package_name,
                "1"
            ],
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode == 0:
            return f"Opening {app_name} on your phone."

        return f"Could not open {app_name}. Check whether it is installed."

    except Exception as e:
        return f"Mobile app error: {e}"


def search_youtube_on_mobile(query):
    try:
        encoded_query = urllib.parse.quote_plus(query)

        result = subprocess.run(
            [
                ADB_PATH,
                "shell",
                "am",
                "start",
                "-a",
                "android.intent.action.VIEW",
                "-d",
                f"https://www.youtube.com/results?search_query={encoded_query}",
                "com.google.android.youtube"
            ],
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode == 0:
            return f"Searching YouTube for {query}."

        return f"YouTube search failed: {result.stderr.strip()}"

    except Exception as e:
        return f"YouTube search error: {e}"  
def mobile_youtube_control(action):
    """Control YouTube playback and phone volume using ADB."""

    key_events = {
        "play": "KEYCODE_MEDIA_PLAY",
        "pause": "KEYCODE_MEDIA_PAUSE",
        "resume": "KEYCODE_MEDIA_PLAY",
        "next": "KEYCODE_MEDIA_NEXT",
        "previous": "KEYCODE_MEDIA_PREVIOUS",
        "volume_up": "KEYCODE_VOLUME_UP",
        "volume_down": "KEYCODE_VOLUME_DOWN",
        "mute": "KEYCODE_VOLUME_MUTE",
    }

    if action not in key_events:
        return "Sorry, this command is not supported."

    try:
        subprocess.run(
            [
                ADB_PATH,
                "shell",
                "input",
                "keyevent",
                key_events[action],
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )

        messages = {
            "play": "Play command sent to your phone.",
            "pause": "Pause command sent to your phone.",
            "resume": "Resume command sent to your phone.",
            "next": "Next video command sent to your phone.",
            "previous": "Previous video command sent to your phone.",
            "volume_up": "Phone volume increased.",
            "volume_down": "Phone volume decreased.",
            "mute": "Mute command sent to your phone.",
        }

        return messages[action]

    except Exception as error:
        return f"Mobile control failed: {error}"
# ==============================
# WHATSAPP MOBILE CONTROL
# ==============================

import urllib.parse
import subprocess
import threading
'''def search_spotify_on_mobile(song_name):
    """Search for a specific song in Spotify on the connected phone."""

    import urllib.parse

    if not song_name or not song_name.strip():
        return "Please tell me the song name or artist."

    try:
        # Build the Spotify search URI
        query = urllib.parse.quote(song_name.strip())
        spotify_uri = f"spotify:search:{query}"

        # Open Spotify directly to the search results
        phone_shell([
            "am",
            "start",
            "-a",
            "android.intent.action.VIEW",
            "-d",
            spotify_uri,
            "-p",
            "com.spotify.music"
        ])

        return f"Searching Spotify for {song_name}."

    except Exception as error:
        return f"Spotify search error: {error}"
def search_spotify_on_mobile(song_name):
    """Search for a song in Spotify on the connected Android phone."""

    import urllib.parse

    song_name = song_name.strip()

    if not song_name:
        return "Please tell me the song name."

    try:
        encoded_song = urllib.parse.quote(song_name, safe="")
         = f"https://open.spotify.com/search/{encoded_song}"

        phone_shell([
            "am", "start",
            "-a", "android.intent.action.VIEW",
            "-d", spotify_url,spotify_url
            "-p", "com.spotify.music"
        ])

        return f"Opening Spotify search for {song_name}."

    except Exception as error:
        return f"Spotify search error: {error}"   
def search_spotify_on_mobile(song_name):
    """Open Spotify and search for a specific song."""

    import urllib.parse

    song_name = song_name.strip()

    if not song_name:
        return "Please tell me the song name."

    try:
        encoded_song = urllib.parse.quote(song_name, safe="")
        spotify_url = f"https://open.spotify.com/search/{encoded_song}"

        result = subprocess.run(
            [
                ADB_PATH,
                "shell",
                "am",
                "start",
                "-a",
                "android.intent.action.VIEW",
                "-d",
                spotify_url
            ],
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode != 0:
            return f"Could not open Spotify search: {result.stderr}"

        return f"Opening Spotify search for {song_name}."

    except Exception as error:
        return f"Spotify search error: {error}"    '''
def search_spotify_on_mobile(song_name):
    """Search for a song using Spotify's Android interface."""

    import time
    import xml.etree.ElementTree as ET

    song_name = str(song_name or "").strip()

    if not song_name:
        return "Please tell me the song name."

    def adb(*args):
        return subprocess.run(
            [ADB_PATH, *args],
            capture_output=True,
            text=True,
            timeout=15
        )

    def get_screen_xml():
        adb("shell", "uiautomator", "dump", "/sdcard/jarvis_screen.xml")
        result = adb("shell", "cat", "/sdcard/jarvis_screen.xml")
        return result.stdout or ""

    def tap_element(keywords):
        xml_text = get_screen_xml()

        if not (xml_text or "").strip():
            return False

        root = ET.fromstring(xml_text)

        for node in root.iter("node"):
            label = (
                node.attrib.get("text", "") + " " +
                node.attrib.get("content-desc", "") + " " +
                node.attrib.get("resource-id", "")
            ).lower()

            if any(word.lower() in label for word in keywords):
                bounds = node.attrib.get("bounds", "")
                numbers = re.findall(r"\d+", bounds)

                if len(numbers) == 4:
                    x1, y1, x2, y2 = map(int, numbers)
                    x = (x1 + x2) // 2
                    y = (y1 + y2) // 2

                    adb("shell", "input", "tap", str(x), str(y))
                    return True

        return False

    try:
        # Open Spotify on the phone
        result = adb(
            "shell", "monkey", "-p",
            "com.spotify.music", "1"
        )

        if result.returncode != 0:
            return "Could not open Spotify. Check that it is installed."

        time.sleep(4)

        # Tap Spotify's Search button
        '''if not tap_element(["search"]):
            return (
                "Spotify is open, but JARVIS could not find its Search "
                "button. Please check the Spotify screen."
            )
         # Try different labels used by Spotify's interface
        if not tap_element([
             "search",
             "search tab",
             "search icon",
             "search and browse",
             "com.spotify.music:id/search"
    ]):
         return (
        "Spotify is open, but its Search button could not be identified. "
        "Please open Spotify's Search screen manually and try again."
         )   

        time.sleep(2)

        # Tap the search input field
        if not tap_element(["search query", "search songs", "what do you want to play"]):
            # Try the common search field label
            if not tap_element(["search"]):
                return "Could not find Spotify's search field."

        time.sleep(1)'''

        # Enter the song name
        '''safe_song = song_name.replace("%", "%25").replace(" ", "%s")
        safe_song = safe_song.replace("&", "\\&").replace("'", "\\'")

        adb("shell", "input", "text", safe_song)
        time.sleep(2)
        adb("shell", "input", "keyevent", "66")

        return f"Entered the Spotify search for {song_name}."'''
        # Enter the song name
                # Open Spotify Search using the bottom navigation icon
        size_result = adb("shell", "wm", "size")
        size_match = re.search(
            r"(\d+)x(\d+)",
            size_result.stdout or ""
        )

        if not size_match:
            return "Could not determine your phone's screen size."

        screen_width, screen_height = map(
            int,
            size_match.groups()
        )

        # Tap Search icon in the bottom navigation bar
        search_x = int(screen_width * 0.30)
        search_y = int(screen_height * 0.905)

        adb(
            "shell",
            "input",
            "tap",
            str(search_x),
            str(search_y)
        )
        time.sleep(3)

        # Tap the search field near the top of the Search screen
        search_field_x = int(screen_width * 0.50)
        search_field_y = int(screen_height * 0.12)

        adb(
            "shell",
            "input",
            "tap",
            str(search_field_x),
            str(search_field_y)
        )
        time.sleep(2)
        safe_song = (
             song_name
            .replace("%", "%25")
            .replace(" ", "%s")
            .replace("&", "\\&")
            .replace("'", "\\'")
        )

        adb("shell", "input", "text", safe_song)
        time.sleep(2)

# Press Enter to display search results
        adb("shell", "input", "keyevent", "66")
        time.sleep(3)

        return f"Entered the search for {song_name} in Spotify."

    except Exception as error:
        return f"Spotify search error: {error}"   
def call_phone_number(phone_number):
    """Open the phone dialer with the requested number."""

    number = "".join(
        char for char in str(phone_number or "")
        if char.isdigit() or char == "+"
    )

    if len(number.replace("+", "")) < 10:
        return "Please provide a valid phone number."

    try:
        subprocess.run(
            [
                ADB_PATH,
                "shell",
                "am",
                "start",
                "-a",
                "android.intent.action.DIAL",
                "-d",
                f"tel:{number}"
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=True
        )

        return f"Opening the dialer for {number}. Review the number and tap Call."

    except Exception as error:
        return f"Phone dialer error: {error}"  
    '''def call_contact(contact_name):
    """Find a saved phone contact and open the dialer."""

    contact_name = str(contact_name or "").strip()

    if not contact_name:
        return "Please tell me the contact name."

    try:
        result = subprocess.run(
            [
                ADB_PATH,
                "shell",
                "content",
                "query",
                "--uri",
                "content://com.android.contacts/data/phones",
                "--projection",
                "display_name:number"
            ],
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode != 0:
            return (
                "Could not read phone contacts. Check the phone connection "
                "and Android permissions."
            )

        matches = []

        for line in result.stdout.splitlines():
            if "display_name=" not in line or "number=" not in line:
                continue

            try:
                name_part = line.split("display_name=", 1)[1]
                name = name_part.split(",", 1)[0].strip().strip("'\"")

                number_part = line.split("number=", 1)[1]
                number = number_part.split(",", 1)[0].strip().strip("'\"")

                if contact_name.casefold() in name.casefold():
                    matches.append((name, number))

            except (IndexError, ValueError):
                continue

        if not matches:
            return f"No saved contact found matching {contact_name}."

        # Avoid choosing the wrong person when names are ambiguous.
        unique_matches = list(dict.fromkeys(matches))

        if len(unique_matches) > 1:
            options = "\n".join(
                f"{i + 1}. {name}: {number}"
                for i, (name, number) in enumerate(unique_matches[:10])
            )
            return (
                "Multiple contacts matched. Please use a more specific name:\n"
                + options
            )

        name, number = unique_matches[0]

        dial_result = subprocess.run(
            [
                ADB_PATH,
                "shell",
                "am",
                "start",
                "-a",
                "android.intent.action.DIAL",
                "-d",
                f"tel:{number}"
            ],
            capture_output=True,
            text=True,
            timeout=15
        )

        if dial_result.returncode != 0:
            return f"Could not open the dialer for {name}."

        return f"Dialer opened for {name} ({number}). Review and tap Call."

    except Exception as error:
        return f"Contact lookup error: {error}" '''  
'''def call_contact(contact_name):
    """Find a saved contact and open the phone dialer."""

    contact_name = str(contact_name or "").strip()

    if not contact_name:
        return "Please tell me the contact name."

    try:
        result = subprocess.run(
            [
                ADB_PATH,
                "shell",
                "content",
                "query",
                "--uri",
                "content://com.android.contacts/data/phones",
                "--projection",
                "display_name:data1"
            ],
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode != 0:
            return "Could not read contacts from your phone."

        matches = []
        print("ADB PATH:", ADB_PATH)
        print("RETURN CODE:", result.returncode)
        print("STDOUT:", repr(result.stdout))
        print("STDERR:", repr(result.stderr))

        output = result.stdout or ""
        print("CONTACT SEARCH:", repr(contact_name))
        print("ADB OUTPUT LENGTH:", len(output))
        print(
            "PRAACHI FOUND:",
            any(
                "prachi shitole" in line.casefold()
                for line in output.splitlines()
            )
        )
        if not output.strip():
            return f"No contacts returned. ADB error: {result.stderr}"

        for line in output.splitlines():
            if "Prachi Shitole" in line.casefold():
                return f"DEBUG: Contact found: {line}"
        for line in output.splitlines():
            if "display_name=" not in line or "data1=" not in line:
                continue

            try:
                name = line.split("display_name=", 1)[1]
                name = name.split(", data1=", 1)[0].strip()

                number = line.split("data1=", 1)[1].strip()

                clean_name = name.strip().casefold()
                search_name = contact_name.strip().casefold()

                if search_name in clean_name and number:
                   matches.append((name, number))

            except (IndexError, ValueError):
                continue

        # Remove duplicate matches
        matches = list(dict.fromkeys(matches))

        if not matches:
            return f"No saved contact found matching {contact_name}."

        if len(matches) > 1:
            options = "\n".join(
                f"{i + 1}. {name}"
                for i, (name, number) in enumerate(matches[:10])
            )

            return (
                "Multiple contacts found. Please use a more specific name:\n"
                + options
            )

        name, number = matches[0]

        dial_result = subprocess.run(
            [
                ADB_PATH,
                "shell",
                "am",
                "start",
                "-a",
                "android.intent.action.DIAL",
                "-d",
                f"tel:{number}"
            ],
            capture_output=True,
            text=True,
            timeout=15
        )

        if dial_result.returncode != 0:
            return f"Could not open the dialer for {name}."

        return f"Opening the dialer for {name}. Review the number and tap Call."

    except Exception as error:
        return f"Contact lookup error: {error}" '''
def call_contact(contact_name):
    """Open Contacts, search a name, and let the user choose the contact."""

    contact_name = str(contact_name or "").strip()

    if not contact_name:
        return "Please tell me the contact name."

    try:
        # Open Google Contacts on the connected phone
        subprocess.run(
            [
                ADB_PATH,
                "shell",
                "monkey",
                "-p",
                "com.google.android.contacts",
                "1"
            ],
            capture_output=True,
            text=True,
            timeout=15
        )

        time.sleep(2)

        # Tap the Search icon/field
        subprocess.run(
            [
                ADB_PATH,
                "shell",
                "input",
                "keyevent",
                "84"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        time.sleep(1)

        # Enter the requested contact name
        safe_name = (
            contact_name
            .replace("%", "%25")
            .replace(" ", "%s")
            .replace("&", "\\&")
            .replace("'", "\\'")
        )

        subprocess.run(
            [
                ADB_PATH,
                "shell",
                "input",
                "text",
                safe_name
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        time.sleep(2)

        return (
            f"Searching Contacts for {contact_name}. "
            "Select the matching contact on your phone."
        )

    except Exception as error:
        return f"Contact search error: {error}"                               



def open_whatsapp():
    """Open WhatsApp on the connected Android phone."""

    subprocess.run(
        [
            ADB_PATH,
            "shell",
            "monkey",
            "-p",
            "com.whatsapp",
            "-c",
            "android.intent.category.LAUNCHER",
            "1"
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10
    )

    return "WhatsApp opened on your phone."



def open_whatsapp_chat(phone_number):
    """
    Open a WhatsApp chat using the contact's phone number.
    Include the country code without the + sign.
    Example: 919876543210
    """

    number = "".join(
        character for character in phone_number
        if character.isdigit()
    )

    if len(number) < 10:
        return "Please provide a valid phone number with country code."

    subprocess.run(
        [
            ADB_PATH,
            "shell",
            "am",
            "start",
            "-a",
            "android.intent.action.VIEW",
            "-d",
            f"https://wa.me/{number}",
            "-p",
            "com.whatsapp"
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=15
    )

    return "Opening WhatsApp chat."


def prepare_whatsapp_message(phone_number, message):
    """
    Open a WhatsApp chat with a prefilled message.
    The user must review and send it manually.
    """

    number = "".join(
        character for character in phone_number
        if character.isdigit()
    )

    if len(number) < 10:
        return "Please provide a valid phone number with country code."

    encoded_message = urllib.parse.quote(message)

    url = (
        f"https://wa.me/{number}"
        f"?text={encoded_message}"
    )

    subprocess.run(
        [
            ADB_PATH,
            "shell",
            "am",
            "start",
            "-a",
            "android.intent.action.VIEW",
            "-d",
            url,
            "-p",
            "com.whatsapp"
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=15
    )

    return "Message prepared. Please review it and tap Send."    

     
def normalize_command(command):
    """Convert common Hindi/Hinglish commands into English commands."""

    command = command.lower().strip()

    replacements = {
        "kholo": "open",
        "khol do": "open",
        "chalu karo": "open",
        "shuru karo": "open",
        "par search karo": "on youtube search",
        "youtube pe search karo": "search youtube for",
        "youtube par search karo": "search youtube for",
    }

    for phrase, replacement in sorted(
        replacements.items(),
        key=lambda item: len(item[0]),
        reverse=True
    ):
        command = command.replace(phrase, replacement)

    return command     


'''def process_command(command):
    """Run commands without freezing the GUI."""
    
    command = command.strip()

    # 1. Handle YouTube search commands
    match = re.search(
        r"\b(?:search|find)\s+(?:on\s+)?youtube\s+(?:for\s+)?(.+)$",
        command,
        re.IGNORECASE
    )

    if match:
        query = match.group(1).strip()

        def youtube_worker():
            update_status("Searching YouTube...")

            try:
                response = search_youtube_on_mobile(query)
                add_message("JARVIS", response)
                speak(response)
            finally:
                update_status("SYSTEM ONLINE")

        threading.Thread(
            target=youtube_worker,
            daemon=True
        ).start()

        return
        

    # 2. Handle mobile app opening commands
    match = re.search(
        r"\bopen\s+([a-zA-Z0-9 ]+?)(?:\s+on\s+(?:my\s+)?(?:phone|mobile))?$",
        command,
        re.IGNORECASE
    )

    if match:
        app_name = match.group(1).strip().lower()

        if app_name in MOBILE_APPS:

            def app_worker():
                update_status("Opening mobile app...")

                try:
                    response = open_mobile_app(app_name)
                    add_message("JARVIS", response)
                    speak(response)
                finally:
                    update_status("SYSTEM ONLINE")

            threading.Thread(
                target=app_worker,
                daemon=True
            ).start()

            return

    # 3. Handle all other commands normally
    def worker():
        update_status("JARVIS is processing...")

        try:
            response = handle_message(command)
            add_message("JARVIS", response)
            speak(response)
        finally:
            update_status("SYSTEM ONLINE")

    threading.Thread(
        target=worker,
        daemon=True
    ).start()'''
def study_assistant(question):
    """Answer academic questions using the local Ollama model."""

    question = str(question or "").strip()

    if not question:
        return "Please ask me a study question."

    prompt = f"""
You are JARVIS, a friendly AI study tutor for a second-year
Artificial Intelligence and Data Science engineering student.

Follow these rules:
1. Explain concepts in simple English.
2. Use headings and bullet points where helpful.
3. For exam questions, write clear, exam-ready answers.
4. Include examples for programming concepts.
5. For 5-mark questions, provide a suitable medium-length answer.
6. Never invent facts when you are unsure.
7. Help the student understand the concept instead of only
   giving the final answer.

Student's question:
{question}
"""

    try:
        response = ollama.chat(
            model="llama3.2:1b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are JARVIS Study Assistant, "
                        "a helpful engineering tutor."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response["message"]["content"].strip()

    except Exception as error:
        return f"Study Assistant error: {error}"
def add_reminder(task, reminder_time):
    reminders.append({
        "task": task,
        "time": reminder_time.isoformat(),
        "done": False
    })

    save_reminders(reminders)

    return (
        f"Reminder saved: {task} at "
        f"{reminder_time.strftime('%d %b, %I:%M %p')}."
    )


def show_reminders():
    pending = [
        reminder for reminder in reminders
        if not reminder["done"]
    ]

    if not pending:
        return "Abhi koi pending reminder nahi hai."

    result = ["Tumhare pending reminders:"]

    for number, reminder in enumerate(pending, start=1):
        reminder_time = datetime.fromisoformat(reminder["time"])

        result.append(
            f"{number}. {reminder['task']} - "
            f"{reminder_time.strftime('%d %b, %I:%M %p')}"
        )

    return "\n".join(result)
    
def process_command(command):
        # Handle calls by contact name or phone number
    call_match = re.match(
        r"^(?:call|phone)\s+(.+)$",
        command.strip(),
        re.IGNORECASE
    )

    if call_match:
        target = call_match.group(1).strip()

        if re.fullmatch(r"\+?[\d\s()-]{10,20}", target):
            number = re.sub(r"[^\d+]", "", target)

            def call_worker():
                update_status("Opening phone dialer...")
                try:
                    response = call_phone_number(number)
                    add_message("JARVIS", response)
                    speak(response)
                except Exception as error:
                    add_message("JARVIS", f"Call error: {error}")
                finally:
                    update_status("SYSTEM ONLINE")

        else:
            def call_worker():
                update_status("Searching contacts...")
                try:
                    response = call_contact(target)
                    add_message("JARVIS", response)
                    speak(response)
                except Exception as error:
                    add_message("JARVIS", f"Call error: {error}")
                finally:
                    update_status("SYSTEM ONLINE")

        threading.Thread(
            target=call_worker,
            daemon=True
        ).start()
        return
        # Handle phone call commands
    call_match = re.search(
        r"^(?:call|phone)\s+(.+)$",
        command.strip(),
        re.IGNORECASE
    )

    if call_match:
        target = call_match.group(1).strip()

        # Accept a phone number directly
        if re.fullmatch(r"\+?[\d\s()-]{10,20}", target):
            phone_number = re.sub(r"[^\d+]", "", target)

            def call_worker():
                update_status("Opening phone dialer...")
                try:
                    response = call_phone_number(phone_number)
                    add_message("JARVIS", response)
                    speak(response)
                except Exception as error:
                    add_message("JARVIS", f"Call error: {error}")
                finally:
                    update_status("SYSTEM ONLINE")

            threading.Thread(
                target=call_worker,
                daemon=True
            ).start()
            return
    """Run commands without freezing the GUI."""

    command = command.strip()
    if not command:
        return

    # 1. Handle multiple commands joined by "and then"
    
    '''controls = {
    "increase volume": "volume_up",
    "increase sound": "volume_up",
    "volume up": "volume_up",
    "sound up": "volume_up",

    "decrease volume": "volume_down",
    "decrease sound": "volume_down",
    "volume down": "volume_down",
    "sound down": "volume_down",

    "pause video": "pause",
    "resume video": "resume",
    "next video": "next",
    
    "previous video": "previous",
}
    
    if re.search(r"\s+(?:and then|then|phir|fir)\s+", command, re.IGNORECASE):
       commands = re.split(
    r"\s+(?:and then|then|phir|fir)\s+",
    command,
    flags=re.IGNORECASE
)
    def multi_command_worker():
            update_status("Processing multiple commands...")

            try:
                for cmd in commands:
                    process_command(cmd.strip())

            finally:
                update_status("SYSTEM ONLINE")'''
         # HANDLE MULTIPLE COMMANDS SEQUENTIALLY
    if re.search(r"\s+(?:and then|then)\s+|,\s*", command, re.IGNORECASE):
        commands = [
            part.strip(" ,.")
            for part in re.split(
                r"\s+(?:and then|then)\s+|,\s*",
                command,
                flags=re.IGNORECASE
            )
            if part.strip(" ,.")
        ]

        if len(commands) > 1:
            def multi_command_worker():
                update_status("Processing multiple commands...")

                try:
                    for cmd in commands:
                        text = normalize_command(cmd).strip()

                        # Open an app on the mobile phone
                        app_match = re.match(
                            r"^(?:open|launch|start)\s+(.+?)"
                            r"(?:\s+on\s+(?:my\s+)?(?:phone|mobile))?$",
                            text,
                            re.IGNORECASE
                        )

                        # Search YouTube on the mobile phone
                        youtube_match = re.match(
                            r"^(?:search|find)\s+(?:on\s+)?youtube"
                            r"(?:\s+for)?\s+(.+)$",
                            text,
                            re.IGNORECASE
                        )

                        # Play/search a video on mobile YouTube
                        play_match = re.match(
                            r"^play\s+(.+?)(?:\s+on\s+youtube)?$",
                            text,
                            re.IGNORECASE
                        )

                        if youtube_match:
                            response = search_youtube_on_mobile(
                                youtube_match.group(1).strip()
                            )

                        elif play_match:
                            response = search_youtube_on_mobile(
                                play_match.group(1).strip()
                            )

                        elif app_match:
                            app_name = app_match.group(1).strip().lower()

                            if app_name in MOBILE_APPS:
                                response = open_mobile_app(app_name)
                            else:
                                response = execute_one(text)

                        else:
                            response = execute_one(text)

                        if response:
                            add_message("JARVIS", str(response))
                            speak(str(response))

                        # Allow the current phone action to begin
                        time.sleep(2)

                except Exception as error:
                    add_message("JARVIS", f"Command error: {error}")

                finally:
                    update_status("SYSTEM ONLINE")

            threading.Thread(
                target=multi_command_worker,
                daemon=True
            ).start()

            return           

        # Process commands separately to avoid blocking the GUI.
        

    # 2. Handle YouTube search commands
    
    match = re.search(
        r"^(?:search|find)\s+(?:on\s+)?youtube"
        r"(?:\s+for)?\s+(.+)$",
        command,
        re.IGNORECASE
    )

    if match:
        query = match.group(1).strip()

        def youtube_worker():
            update_status("Searching YouTube...")

            try:
                response = search_youtube_on_mobile(query)
                add_message("JARVIS", response)
                speak(response)

            except Exception as error:
                add_message("JARVIS", f"YouTube error: {error}")

            finally:
                update_status("SYSTEM ONLINE")

        threading.Thread(
            target=youtube_worker,
            daemon=True
        ).start()

        return
        # PLAY MOVIE / VIDEO ON MOBILE YOUTUBE

    text = command.strip().lower()

    match = re.match(
        r"^play\s+(.+?)(?:\s+on\s+youtube)?$",
        text,
        re.IGNORECASE
    )

    if match:
        query = match.group(1).strip()

        def mobile_play_worker():
            try:
                update_status("Opening YouTube on your phone...")

                response = search_youtube_on_mobile(query)

                add_message("JARVIS", response)
                speak(response)

            except Exception as error:
                add_message(
                    "JARVIS",
                    f"Mobile YouTube error: {error}"
                )

            finally:
                update_status("SYSTEM ONLINE")

        threading.Thread(
            target=mobile_play_worker,
            daemon=True
        ).start()

        return
        # WHATSAPP COMMAND HANDLER

    text = normalize_command(command).strip().lower()

    # Open WhatsApp
    if text in (
        "open whatsapp",
        "whatsapp kholo",
        "open whatsapp on phone"
    ):
        def whatsapp_worker():
            try:
                response = open_whatsapp()
                add_message("JARVIS", response)
                speak(response)

            except Exception as error:
                add_message(
                    "JARVIS",
                    f"WhatsApp error: {error}"
                )

        threading.Thread(
            target=whatsapp_worker,
            daemon=True
        ).start()

        return
        # 2. Handle Spotify song search commands
    match = re.search(
        r"\b(?:search|find)\s+(?:for\s+)?(?:on\s+)?spotify"
        r"(?:\s+for)?\s+(.+)$",
        command,
        re.IGNORECASE
    )

    if match:
        song_name = (match.group(1) or "").strip()

        if not song_name:
                add_message("JARVIS", "Please tell me the song name.")
                return

        def spotify_worker():
            update_status("Searching Spotify...")

            try:
                response = search_spotify_on_mobile(song_name)
                add_message("JARVIS", response)
                speak(response)
            except Exception as error:
                error_message = f"Spotify search error: {error}"
                add_message("JARVIS", error_message)
                speak(error_message)
            finally:
                update_status("SYSTEM ONLINE")

        threading.Thread(
            target=spotify_worker,
            daemon=True
        ).start()

        return


    # 3. Handle mobile app opening commands
    match = re.search(
        r"^open\s+([a-zA-Z0-9 ]+?)"
        r"(?:\s+on\s+(?:my\s+)?(?:phone|mobile))?$",
        command,
        re.IGNORECASE
    )

    if match:
        app_name = match.group(1).strip().lower()

        if app_name in MOBILE_APPS:

            def app_worker():
                update_status("Opening mobile app...")

                try:
                    response = open_mobile_app(app_name)
                    add_message("JARVIS", response)
                    speak(response)

                except Exception as error:
                    add_message("JARVIS", f"Mobile app error: {error}")

                finally:
                    update_status("SYSTEM ONLINE")

            threading.Thread(
                target=app_worker,
                daemon=True
            ).start()      
            return
    

    # REMINDERS: SHOW PENDING REMINDERS

    text = normalize_command(command).strip().lower()

        # REMINDERS: SHOW PENDING REMINDERS

    text = normalize_command(command).strip().lower()

    if text in (
        "show my reminder",
        "show my reminders",
        "show reminder",
        "show reminders",
        "my reminder",
        "my reminders",
        "reminder dikhao",
        "reminders dikhao"
    ):
        response = show_reminders()
        add_message("JARVIS", response)
        speak(response)
        return
        response = show_reminders()
        add_message("JARVIS", response)
        speak(response)
        return


    # 4. Handle all other commands using Ollama
    def worker():
        update_status("JARVIS is processing...")

        try:
            response = handle_message(command)
            add_message("JARVIS", response)
            speak(response)

        except Exception as error:
            add_message("JARVIS", f"Error: {error}")

        finally:
            update_status("SYSTEM ONLINE")

    threading.Thread(
        target=worker,
        daemon=True
    ).start()    


# Input area
input_frame = ctk.CTkFrame(
    app,
    fg_color="transparent"
)

input_frame.pack(
    fill="x",
    padx=20,
    pady=(5, 20)
)


command_entry = ctk.CTkEntry(
    input_frame,
    placeholder_text=(
        "Ask JARVIS... e.g. Open Instagram on my phone"
    ),
    height=45,
    font=("Arial", 14)
)

command_entry.pack(
    side="left",
    fill="x",
    expand=True,
    padx=(0, 8)
)


def send_command(event=None):
    """Send text entered in the input box."""

    command = command_entry.get().strip()

    if not command:
        return

    command_entry.delete(0, "end")

    add_message("YOU", command)
    process_command(command)


send_button = ctk.CTkButton(
    input_frame,
    text="SEND",
    width=80,
    height=45,
    command=send_command
)

send_button.pack(
    side="left",
    padx=(0, 8)
)


voice_button = ctk.CTkButton(
    input_frame,
    text="🎤",
    width=55,
    height=45,
    command=lambda: threading.Thread(
        target=listen,
        daemon=True
    ).start()
)

voice_button.pack(side="left")


command_entry.bind(
    "<Return>",
    send_command
)


# Welcome message
add_message(
    "JARVIS",
    (
        "Hello! I am JARVIS. I can help with local AI "
        "conversations, laptop controls, Android app "
        "launching, searches, and message drafts."
    )
)

def wake_word_listener():
    import openwakeword
    from openwakeword.model import Model

    openwakeword.utils.download_models()

    model = Model(
        wakeword_models=["hey_jarvis"]
    )

    sample_rate = 16000
    chunk_size = 1280

    update_status("Listening for Hey JARVIS...")

    while True:
        try:
            audio = sd.rec(
                chunk_size,
                samplerate=sample_rate,
                channels=1,
                dtype="int16"
            )

            sd.wait()

            audio = audio.flatten()

            prediction = model.predict(audio)

            for name, score in prediction.items():
                if score > 0.5:
                    update_status("Wake word detected!")

                    app.after(
                        0,
                        lambda: threading.Thread(
                            target=listen,
                            daemon=True
                        ).start()
                    )

                    time.sleep(2)
                    break

        except Exception as error:
            print("Wake word error:", error)
            update_status("Wake word listener error")
            time.sleep(2)
            threading.Thread(
    target=wake_word_listener,
    daemon=True
).start()

# Start GUI
app.mainloop()