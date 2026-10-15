"""Compatibility launcher: `python jarvis_gui.py` still starts JARVIS.

The original single-file version is kept in legacy/jarvis_gui_v1.py.
"""

from jarvis.__main__ import main

if __name__ == "__main__":
    main()
