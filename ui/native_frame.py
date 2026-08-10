"""
ui/native_frame.py — a custom title bar that keeps the native window behaviour.

The reference layouts draw their own title bar: a 24px strip with the document
name and three round controls. Reproducing that is normally where an
application quietly loses Aero Snap, edge resizing, the drop shadow, the
maximise animation, the Win+Arrow shortcuts, and the right-click system menu —
because the usual route is Qt.FramelessWindowHint, which strips WS_THICKFRAME
and WS_CAPTION and takes all of that with it.

This takes the other route. The window keeps its real Win32 frame styles, so
Windows still owns every one of those behaviours; only the frame's *drawing* is
suppressed, by answering WM_NCCALCSIZE with a client area covering the whole
window. Hit testing is then handed back to Windows through WM_NCHITTEST: the
title strip answers HTCAPTION, which is what makes dragging, snapping, and
double-click-to-maximise work without a line of code implementing them, and the
outer few pixels answer the eight resize codes.

Two details that are easy to get wrong and unpleasant to debug:

  * A maximised window with a suppressed frame overhangs the work area by the
    border thickness, hiding the taskbar. The client area is inset by the
    system frame metrics in that state only.
  * A maximised window must not report resize borders, or the top edge grabs
    a resize the window cannot honour.

If anything here is unavailable — a non-Windows host, a ctypes failure — the
helper reports that it did not attach and the caller keeps the ordinary native
frame. Degrading to a normal window is always better than a broken one.
"""

from __future__ import annotations

import sys

IS_WINDOWS = sys.platform == "win32"

WM_NCCALCSIZE = 0x0083
WM_NCHITTEST = 0x0084

HTCLIENT = 1
HTCAPTION = 2
HTLEFT, HTRIGHT, HTTOP = 10, 11, 12
HTTOPLEFT, HTTOPRIGHT = 13, 14
HTBOTTOM, HTBOTTOMLEFT, HTBOTTOMRIGHT = 15, 16, 17

SM_CXSIZEFRAME = 32
SM_CYSIZEFRAME = 33
SM_CXPADDEDBORDER = 92

# How far in from the edge counts as a resize grip, in device-independent px.
RESIZE_MARGIN = 5


def _frame_metrics():
    """The border thickness Windows would have drawn, in physical pixels."""
    import ctypes

    user32 = ctypes.windll.user32
    padded = user32.GetSystemMetrics(SM_CXPADDEDBORDER)
    return (user32.GetSystemMetrics(SM_CXSIZEFRAME) + padded,
            user32.GetSystemMetrics(SM_CYSIZEFRAME) + padded)


def install(window, caption_height: int, is_caption=None) -> bool:
    """Suppress *window*'s frame drawing while keeping its frame behaviour.

    `caption_height` is the height of the custom title strip in
    device-independent pixels. `is_caption(x, y)` is an optional predicate
    taking a point in that strip's coordinates and returning False where a
    control sits, so buttons stay clickable instead of dragging the window.

    Returns True if the hook attached. On False the caller should leave the
    native frame alone.
    """
    if not IS_WINDOWS:
        return False
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return False

    class MSG(ctypes.Structure):
        _fields_ = [("hWnd", wintypes.HWND), ("message", wintypes.UINT),
                    ("wParam", wintypes.WPARAM), ("lParam", wintypes.LPARAM),
                    ("time", wintypes.DWORD), ("pt", wintypes.POINT)]

    class NCCALCSIZE_PARAMS(ctypes.Structure):
        _fields_ = [("rgrc", wintypes.RECT * 3), ("lppos", ctypes.c_void_p)]

    def native_event(event_type, message):
        if event_type != b"windows_generic_MSG":
            return False, 0
        msg = MSG.from_address(int(message))

        if msg.message == WM_NCCALCSIZE and msg.wParam:
            # Returning without shrinking the rectangle gives the client area
            # the whole window, frame included — which is the entire trick.
            if window.isMaximized():
                # Except here: the frame Windows reserved is off-screen, so
                # not insetting would hide the taskbar behind the window.
                params = NCCALCSIZE_PARAMS.from_address(msg.lParam)
                bx, by = _frame_metrics()
                params.rgrc[0].left += bx
                params.rgrc[0].right -= bx
                params.rgrc[0].top += by
                params.rgrc[0].bottom -= by
            return True, 0

        if msg.message == WM_NCHITTEST:
            ratio = window.devicePixelRatioF() or 1.0
            # lParam packs two signed 16-bit screen coordinates.
            x = ctypes.c_short(msg.lParam & 0xFFFF).value
            y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
            local = window.mapFromGlobal(
                window.screen().geometry().topLeft().__class__(
                    int(x / ratio), int(y / ratio)))
            lx, ly = local.x(), local.y()
            w, h = window.width(), window.height()

            if not window.isMaximized():
                m = RESIZE_MARGIN
                left, right = lx < m, lx >= w - m
                top, bottom = ly < m, ly >= h - m
                if top and left:
                    return True, HTTOPLEFT
                if top and right:
                    return True, HTTOPRIGHT
                if bottom and left:
                    return True, HTBOTTOMLEFT
                if bottom and right:
                    return True, HTBOTTOMRIGHT
                if left:
                    return True, HTLEFT
                if right:
                    return True, HTRIGHT
                if top:
                    return True, HTTOP
                if bottom:
                    return True, HTBOTTOM

            if 0 <= ly < caption_height:
                if is_caption is None or is_caption(lx, ly):
                    # HTCAPTION is what buys drag, snap, double-click maximise
                    # and the right-click system menu, all from Windows.
                    return True, HTCAPTION
            return True, HTCLIENT

        return False, 0

    window.nativeEvent = native_event  # type: ignore[method-assign]

    # Force Windows to recompute the frame now that WM_NCCALCSIZE answers
    # differently; without this the old frame lingers until the first resize.
    try:
        import ctypes

        hwnd = int(window.winId())
        SWP_FRAMECHANGED = 0x0020
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOZORDER = 0x0004
        ctypes.windll.user32.SetWindowPos(
            hwnd, 0, 0, 0, 0, 0,
            SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER)
    except Exception:
        pass
    return True
