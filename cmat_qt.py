"""
cmat_qt.py — entry point for the PySide6 build.

    python cmat_qt.py

Every tab is ported: Pipeline, Library, Index, Automated coding, Human coding
and Trials, plus the Settings dialog and the starting-layout wizard. The
Episode Sampler is the one action still only on the Tk build, and its button
says so rather than sitting there looking live.

The Tkinter build is still `python gui.py`. Both read the same project folder,
cache, preferences and settings, so they can be run against one project and
compared directly.
"""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from ui.main_window import run
    except ImportError as exc:               # noqa: BLE001
        print(f"PySide6 is required for this build: {exc}\n"
              f"Install it with:  pip install PySide6\n"
              f"Or run the Tkinter build:  python gui.py", file=sys.stderr)
        return 1
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
