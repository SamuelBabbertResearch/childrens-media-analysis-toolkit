"""
cmat_qt.py — entry point for the PySide6 build.

    python cmat_qt.py

IN PROGRESS — not yet the product. `python gui.py` is the software people
actually use; this is its replacement, still being built.

Present here: Pipeline, Library, Index, Automated coding (Analyze only), Human
coding (Code only), Trials, the Settings dialog and the starting-layout wizard.

NOT here, and only on the Tk build: the Language screen (Speech + Vocabulary),
Human coding's Validate tool and Agreement, Full Series Aggregate, and the
Episode Sampler.

Both read the same project folder, cache, preferences and settings, so they can
be run against one project and compared directly.
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
