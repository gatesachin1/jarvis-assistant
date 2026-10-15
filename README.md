# J.A.R.V.I.S - Personal AI Command Center

A local voice assistant for Windows. It runs commands on your laptop and on your
Android phone (over ADB), and sends anything else to a local Ollama model.

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

ollama pull llama3.2:1b          # local AI model (https://ollama.com)
copy config.example.json config.json   # optional: change settings

python -m jarvis --web           # desktop app + web dashboard (http://127.0.0.1:8765)
```

Or double-click `run_jarvis.bat`. `python jarvis_gui.py` also still works.

| Flag | Effect |
|---|---|
| `--web` | also start the web dashboard |
| `--headless` | web dashboard only, no desktop window |
| `--no-wake` | turn off the "Hey JARVIS" wake word |
| `--mute` | no spoken replies |
| `--port 9000` | change the dashboard port |
| `--minimized` | start hidden in the system tray |
| `--install-startup` / `--remove-startup` | start (or stop starting) with Windows |

### Offline voice
Voice input uses **Whisper** and spoken replies use a **Piper** neural voice. Both
run locally, so they work without internet. The models (~200 MB) download into
`data/models` on first start. To change engines, set `"stt_engine": "google"` or
`"tts_engine": "sapi"` in `config.json`. A bigger Whisper model (`"whisper_model": "small"`)
is more accurate but slower.

### Desktop integration
- Closing the window keeps JARVIS running in the **system tray** (the J icon). Right-click
  it for the dashboard, voice on/off, *Start with Windows* and *Quit*.
- Reminders also show as **Windows notifications**.
- Say `start with windows` (or use the tray menu) to launch it automatically at sign-in.

### Phone setup
1. Turn on **Developer options → USB debugging** on the phone.
2. Install [Android platform-tools](https://developer.android.com/tools/releases/platform-tools).
   JARVIS finds `adb` on PATH, in the Android SDK, or in `Downloads\platform-tools*`.
   Otherwise set `adb_path` in `config.json`.
3. Connect the phone and accept the "Allow USB debugging" prompt.

**Going wireless:** with the phone plugged in and on the same Wi-Fi as the PC, say
`connect phone wirelessly`. After that you can unplug the cable. JARVIS remembers the
phone and reconnects automatically. On Android 11+ you can also skip USB completely:
**Developer options → Wireless debugging → Pair with code**, then say
`pair phone 192.168.1.20:37123 code 123456` and `connect phone at 192.168.1.20:<port>`.

## Things to say

| Area | Examples |
|---|---|
| Apps | `open instagram`, `open notepad`, `open youtube on laptop`, `youtube kholo` |
| Media | `play lofi beats`, `play believer on spotify`, `pause`, `next song`, `volume up` |
| Messages | `draft a whatsapp message to 919876543210 saying running late`, `find rahul on whatsapp` |
| Calls | `call mom`, `call 9876543210` (always opens the dialer; you press Call) |
| Reminders | `remind me to submit the assignment tomorrow at 6 pm`, `remind me to stretch in 30 minutes`, `show my reminders`, `delete reminder 2`, `plan my day` |
| Study | `study explain normalization in DBMS` |
| Phone link | `connect phone wirelessly`, `connect phone at 192.168.1.20`, `disconnect phone` |
| System | `what time is it`, `system status`, `stop talking`, `start with windows`, `what can you do` |
| Chains | `open instagram and then search youtube for DSA` |

If a command doesn't match, the local AI model answers it.

## Project layout

```
jarvis/
  __main__.py        entry point: wires services together, CLI flags
  config.py          settings (defaults → config.json → JARVIS_* env vars)
  core/
    assistant.py     command engine: split → normalise → route → reply (one ordered worker)
    registry.py      @command decorator + matching
    text.py          Hinglish normalisation, multi-task splitting
    events.py        event bus shared by desktop + web UIs
  services/          adb (+Wi-Fi), reminders (+scheduler), tts (Piper/SAPI), stt (Whisper/Google),
                     wakeword, llm, media_keys, autostart, health
  skills/            phone, laptop, reminders, study, system  ← add new commands here
  ui/                CustomTkinter window, system tray + notifications, app icon
  web/               FastAPI + WebSocket server and dashboard (index.html, app.js, style.css)
tests/               pytest suite (no phone, mic or Ollama needed)
legacy/              original v1 files, for reference
```

### Adding a command

```python
# jarvis/skills/laptop.py
@command("lock pc", r"lock (?:my )?(?:pc|laptop|computer)", examples=["lock my laptop"])
def lock_pc(ctx, req):
    ctx.launch(["rundll32.exe", "user32.dll,LockWorkStation"])
    return "Locking your laptop."
```

It shows up in `what can you do` automatically. Lower `priority` numbers are matched first.

## Development

```powershell
pip install -r requirements-dev.txt
pytest            # run the tests
ruff check .      # lint
```

Logs are written to `logs/jarvis.log`. Reminders are stored in `data/reminders.json`
(an old `jarvis_reminders.json` is migrated automatically).

Every push runs lint and tests on GitHub Actions (`.github/workflows/ci.yml`).

### Build and install the Windows app

```powershell
.\build_exe.ps1     # creates dist\JARVIS\JARVIS.exe and dist\JARVIS-<version>-win64.zip
```

To install on any Windows PC (Python not needed): unzip, then run
`powershell -ExecutionPolicy Bypass -File install.ps1 -StartWithWindows`.
This installs to `%LOCALAPPDATA%\Programs\JARVIS` with Start menu and desktop shortcuts.
To remove it, run `install.ps1 -Uninstall`.

## Privacy and safety
- AI answers, speech recognition (Whisper) and the voice (Piper) all run locally.
  Nothing is sent to the cloud unless you switch `stt_engine` to `google`.
- The dashboard listens on `127.0.0.1` only, and refuses requests from other websites.
- JARVIS never sends messages or places calls by itself. It prepares them and you confirm.
