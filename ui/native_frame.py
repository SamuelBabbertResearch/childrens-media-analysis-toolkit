"""Standard window frames for CMAT's Qt windows and dialogs.

Windows owns caption hit testing, moving, resizing and caption buttons. The
former custom non-client hook is retired: rendering a title bar did not prove
that its controls or drag region worked on a scaled display.
"""
from __future__ import annotations

from PySide6.QtCore import Qt


def apply_native_frame(window, buttons: tuple[str, ...] = ("min", "max", "close")) -> None:
    """Configure native caption controls before the window is first shown.

    Keep the existing window/dialog type and modality. Dialog callers declare
    their controls through the same shared helper as the main window.
    """
    flags = window.windowFlags()
    flags &= ~(Qt.FramelessWindowHint | Qt.CustomizeWindowHint
               | Qt.WindowContextHelpButtonHint | Qt.WindowMinimizeButtonHint
               | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
    flags |= Qt.WindowTitleHint | Qt.WindowSystemMenuHint
    for name, flag in (("min", Qt.WindowMinimizeButtonHint),
                       ("max", Qt.WindowMaximizeButtonHint),
                       ("close", Qt.WindowCloseButtonHint)):
        if name in buttons:
            flags |= flag
    window.setWindowFlags(flags)
