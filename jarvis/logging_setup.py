import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_dir: str, verbose: bool = False) -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        Path(log_dir) / "jarvis.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(threadName)s %(name)s: %(message)s")
    )

    handlers: list[logging.Handler] = [file_handler]
    if sys.stderr:  # None under pythonw / a windowed .exe
        try:
            sys.stderr.reconfigure(errors="replace")  # emoji in replies vs. cp1252 consoles
        except AttributeError:
            pass
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(levelname)-7s %(name)s: %(message)s"))
        handlers.append(console)

    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, handlers=handlers, force=True)
    for noisy in ("httpx", "httpx2", "huggingface_hub", "comtypes", "faster_whisper"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
