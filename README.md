# J.A.R.V.I.S - Personal AI Command Center

A private voice assistant for Windows. It runs commands on your laptop and on your
Android phone (over ADB). Anything it doesn't recognise as a command goes to a
**local Ollama AI model**. AI, speech recognition and voice all run on your own PC.

## Requirements

| | Minimum | Notes |
|---|---|---|
| OS | Windows 10/11 | |
| Python | 3.10+ (tested on 3.14) | Not needed if you use the built `.exe` |
| RAM | 8 GB (16 GB recommended) | JARVIS uses ~0.6 GB; the AI model needs ~2 GB **free** while answering |
| Disk | ~5 GB | Ollama ~2.8 GB + model 1.3 GB + voice models 0.2 GB + Python packages |
| Microphone | Any | For voice commands and "Hey JARVIS" |
| Android phone | Optional | USB debugging on, for phone control |

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy config.example.json config.json   # optional: personal settings (not committed to git)
python -m jarvis --web                 # desktop app + web dashboard (http://127.0.0.1:8765)
```

Or double-click `run_jarvis.bat`. `python jarvis_gui.py` also still works. Without
Ollama, everything except AI chat and the study assistant works. Set Ollama up next.

| Flag | Effect |
|---|---|
| `--web` | also start the web dashboard |
| `--headless` | web dashboard only, no desktop window |
| `--no-wake` | turn off the "Hey JARVIS" wake word |
| `--mute` | no spoken replies |
| `--port 9000` | change the dashboard port |
| `--minimized` | start hidden in the system tray |
| `--install-startup` / `--remove-startup` | start (or stop starting) with Windows |

## Local AI setup (Ollama)

JARVIS uses [Ollama](https://ollama.com) with **`llama3.2:1b`** by default. The steps
below install it to a custom drive (`E:\Ollama-setup` here) and keep it **private to
this PC**.

**1. Configure first.** Ollama reads these when it starts. In PowerShell:

```powershell
setx OLLAMA_MODELS  "E:\Ollama-setup\models"   # store models off the C: drive
setx OLLAMA_HOST    "127.0.0.1:11434"          # listen on this PC only, never the network
setx OLLAMA_ORIGINS "http://127.0.0.1:8765,http://localhost:8765"   # browser access: JARVIS dashboard only
setx OLLAMA_NO_CLOUD "1"                       # local models only, no Ollama cloud
```

**2. Install** to the custom folder (download `OllamaSetup.exe` from ollama.com):

```powershell
.\OllamaSetup.exe /DIR="E:\Ollama-setup" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
```

**3. Check the model location.** The Ollama app keeps its own *Model location* setting,
which overrides `OLLAMA_MODELS`. Open Ollama → **Settings → Model location** and set it
to `E:\Ollama-setup\models`. Then quit Ollama from its tray icon and start it again
from the Start menu.

**4. Download the model:**

```powershell
ollama pull llama3.2:1b        # 1.3 GB
```

**5. Check it.** Run `system status` in JARVIS, or look at the dashboard's *AI Engine*
card. It should show **Ready**. Ollama starts automatically at sign-in.

### Choosing a model

| Model | Disk | RAM while answering | Speed (Ryzen 5 5500U, CPU only) | Quality |
|---|---|---|---|---|
| `llama3.2:1b` (default) | 1.3 GB | ~1.5–2 GB | ~21 tokens/s, chat reply ~4–7 s | Fast, sometimes inaccurate |
| `llama3.2:3b` | 2.0 GB | ~3.5–4 GB | ~8–12 tokens/s | Noticeably better answers |
| `llama3.1:8b` | 4.9 GB | ~6–8 GB | ~3–5 tokens/s | Too slow for most laptops |

To switch, run `ollama pull <model>` and set `"ollama_model": "<model>"` in `config.json`.
Integrated AMD/Intel graphics aren't used by Ollama, so models run on the CPU.

## Offline voice

Voice input uses **Whisper** and spoken replies use a **Piper** neural voice. Both run
locally and work without internet. The models (~200 MB) download into `data/models`
on first start and load in the background, so the first command is quick.

- JARVIS ignores the wake word while it is speaking, so it won't wake itself up.
- No PyAudio needed: the microphone is read with `sounddevice`.
- Settings: `"stt_engine": "google"` or `"tts_engine": "sapi"` switch back to the lighter
  online/Windows engines (saves ~0.5 GB RAM). `"whisper_model": "small"` is more accurate
  but slower.

## Desktop integration

- Closing the window keeps JARVIS running in the **system tray** (the J icon). Right-click
  it for the dashboard, voice on/off, *Start with Windows* and *Quit*.
- Reminders also show as **Windows notifications**.
- Say `start with windows` (or use the tray menu) to launch it minimised at sign-in.
- Press **Esc** in the window to stop speech; **↑/↓** recall previous commands.

## Phone setup

1. Turn on **Developer options → USB debugging** on the phone.
2. Install [Android platform-tools](https://developer.android.com/tools/releases/platform-tools).
   JARVIS finds `adb` on PATH, in the Android SDK, or in `Downloads\platform-tools*`.
   Otherwise set `adb_path` in `config.json`.
3. Connect the phone and accept the "Allow USB debugging" prompt.

**Going wireless:** with the phone plugged in and on the same Wi-Fi as the PC, say
`connect phone wirelessly`. After that you can unplug the cable. JARVIS remembers the
phone and reconnects automatically. On Android 11+ you can skip USB completely:
**Developer options → Wireless debugging → Pair with code**, then say
`pair phone 192.168.1.20:37123 code 123456` and `connect phone at 192.168.1.20:<port>`.

When no phone is connected, YouTube, Spotify, WhatsApp drafts and media keys fall back
to the laptop.

## Things to say

| Area | Examples |
|---|---|
| Apps | `open instagram`, `open notepad`, `open youtube on laptop`, `youtube kholo` |
| Media | `play lofi beats`, `play believer on spotify`, `pause`, `play pause`, `next song`, `volume up` |
| Messages | `draft a whatsapp message to 919876543210 saying running late`, `find rahul on whatsapp` |
| Calls | `call mom`, `call 9876543210` (always opens the dialer; you press Call) |
| Reminders | `remind me to submit the assignment tomorrow at 6 pm`, `remind me to stretch in 30 minutes`, `show my reminders`, `mark reminder 1 done`, `delete reminder 2`, `plan my day` |
| AI chat | `tell me a joke`, `explain recursion simply`, or anything else |
| Study | `help me study`, `study explain normalization in DBMS` |
| Phone link | `connect phone wirelessly`, `connect phone at 192.168.1.20`, `disconnect phone` |
| System | `what time is it`, `time kya hai`, `system status`, `stop talking`, `voice on`, `start with windows`, `what can you do` |
| Chains | `open instagram and then search youtube for DSA` |

## Configuration

Settings are read from defaults, then `config.json`, then `JARVIS_<SETTING>` environment
variables (e.g. `JARVIS_OLLAMA_MODEL`). See `config.example.json` for every option. The
most useful ones:

| Setting | Default | Purpose |
|---|---|---|
| `ollama_model` | `llama3.2:1b` | AI model for chat and study |
| `ollama_host` | `http://127.0.0.1:11434` | Ollama server. Keep it on `127.0.0.1` so it stays private |
| `stt_engine` / `tts_engine` | `whisper` / `piper` | Offline voice engines |
| `wake_word_threshold` | `0.5` | Raise it if "Hey JARVIS" triggers by mistake |
| `prefer_device` | `phone` | Where `open X` goes when both phone and laptop can open it |
| `adb_path`, `adb_wifi_address` | auto | Phone connection |
| `web_host`, `web_port` | `127.0.0.1`, `8765` | Dashboard address |
| `models_dir` | `data/models` | Where Whisper/Piper models are stored |

## Troubleshooting

| Problem | Fix |
|---|---|
| *"I couldn't connect to the local AI model…"* | Ollama isn't running: start **Ollama** from the Start menu. Check with `ollama list` that the model is installed. |
| Ollama tray icon shows but AI stays offline | Quit Ollama from the tray and start it again from the Start menu. Check `%LOCALAPPDATA%\Ollama\server.log`. |
| Models downloading to `C:\Users\<you>\.ollama` | Set **Ollama → Settings → Model location** (it overrides `OLLAMA_MODELS`). |
| AI replies are slow or the PC freezes | Close browser tabs to free RAM (the model needs ~2 GB free), or stay on `llama3.2:1b`. |
| "No Android phone found" | Check USB debugging, accept the prompt on the phone, or say `connect phone wirelessly`. |
| Voice commands not recognised | `system status` shows the microphone state. Speak after the status changes to *Listening…*. |

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
                     wakeword, llm (Ollama client), media_keys, autostart, health
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
(an old `jarvis_reminders.json` is migrated automatically). Every push runs lint and
tests on GitHub Actions (`.github/workflows/ci.yml`).

### Build and install the Windows app

```powershell
.\build_exe.ps1     # creates dist\JARVIS\JARVIS.exe and dist\JARVIS-<version>-win64.zip
```

To install on any Windows PC (Python not needed): unzip, then run
`powershell -ExecutionPolicy Bypass -File install.ps1 -StartWithWindows`.
This installs to `%LOCALAPPDATA%\Programs\JARVIS` with Start menu and desktop shortcuts.
To remove it, run `install.ps1 -Uninstall`. Ollama is installed separately (see above).

## Privacy and safety

- **Everything runs on this PC:** the AI model (Ollama), speech recognition (Whisper) and
  the voice (Piper). Nothing is sent to the cloud unless you switch `stt_engine` to `google`.
- **Only you can use it.** Ollama and the dashboard listen on `127.0.0.1` only, so other
  devices on your network can't reach them. Ollama's cloud models are disabled. The
  dashboard and Ollama refuse requests from other websites.
- **Nothing happens without you.** JARVIS never sends messages or places calls by itself.
  It prepares them and you confirm.
- Personal files (`config.json`, `data/`, `logs/`) are excluded from git.
