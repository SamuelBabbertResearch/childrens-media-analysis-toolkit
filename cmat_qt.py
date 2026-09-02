"""cmat_qt.py — entry point for the CMAT PySide6 desktop application.

Run from source with ``python cmat_qt.py``. The Windows release packages this
entry point as ``CMAT.exe`` via ``build.spec``.
"""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from ui.main_window import run
    except ImportError as exc:               # noqa: BLE001
        print(f"PySide6 is required for CMAT: {exc}\n"
              f"Install it with:  pip install PySide6", file=sys.stderr)
        return 1
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
