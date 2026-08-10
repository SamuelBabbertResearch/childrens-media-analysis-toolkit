"""
ui/modal.py — the window title strip, and the frame the dialogs are drawn in.

`ui/reference/dialogs.css` gives a dialog the SAME chrome as the main window:
a 24px title strip with the document name left and round controls right, over
a 6px-rounded window in the ordinary window colour. That is the whole point of
the design — a dialog is a small window, not a differently-styled object — so
one `WindowTitleBar` serves both, and a dialog introduces no palette of its
own.

The frame is suppressed rather than removed: see `ui/native_frame.py`. Never
`Qt.FramelessWindowHint`, which strips `WS_THICKFRAME`/`WS_CAPTION` and takes
snap, edge resizing, the drop shadow and the system menu with it.

Modal 1 shows all three controls, modal 2 shows close alone, so the set is a
parameter.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ui import native_frame, theme
from ui.tokens import METRICS, color

LIGHT_D = 10          # .win-btn width/height
LIGHT_GAP = 6         # .titlebar-controls gap
PAD_X = 8             # .titlebar padding

# .win-btn.close / .min / .max, in the reference's left-to-right order.
LIGHTS = ("close", "min", "max")
LIGHT_FILL = {"close": "light_close", "min": "light_min", "max": "light_max"}
LIGHT_NAME = {"close": "Close", "min": "Minimise", "max": "Zoom"}


class WindowTitleBar(QWidget):
    """The reference's title strip, for the main window and for dialogs.

    The controls are drawn rather than made buttons so they sit on the exact
    10px circle the reference specifies without a control's padding around
    them; each is still a real click target through `mousePressEvent`.

    Windows conventions are preserved, not replaced. The strip reports
    HTCAPTION (see ui/native_frame.py), so dragging, snapping,
    double-click-to-maximise and the right-click system menu all still come
    from the system. The controls sit in the reference's order — close,
    minimise, zoom, left to right — which is the reverse of the Windows one;
    they carry tooltips and every action stays on the system menu and the
    usual keyboard shortcuts.
    """

    def __init__(self, window, title: str = "",
                 lights: tuple[str, ...] = LIGHTS) -> None:
        super().__init__()
        self._window = window
        self._title = title
        self._lights = lights
        self._hover = -1
        self.setFixedHeight(METRICS["titlebar_h"])
        self.setMouseTracking(True)

    # -- geometry ---------------------------------------------------------
    def _light_rects(self) -> list[QRect]:
        y = (self.height() - LIGHT_D) // 2
        out = []
        x = self.width() - PAD_X - LIGHT_D
        for _ in self._lights:
            out.append(QRect(x, y, LIGHT_D, LIGHT_D))
            x -= LIGHT_D + LIGHT_GAP
        return out[::-1]

    def _light_at(self, pos: QPoint) -> int:
        for i, r in enumerate(self._light_rects()):
            if r.adjusted(-2, -2, 2, 2).contains(pos):
                return i
        return -1

    def is_caption(self, x: int, y: int) -> bool:
        """False over a control, so it takes the click, not the drag."""
        return self._light_at(QPoint(x, y)) < 0

    # -- painting ---------------------------------------------------------
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, QColor(color("titlebar_top")))
        grad.setColorAt(1.0, QColor(color("titlebar_bottom")))
        p.fillRect(self.rect(), grad)
        p.setPen(QColor(color("titlebar_line")))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)

        p.setFont(theme.font("body", bold=True))
        p.setPen(QColor(color("titlebar_fg")))
        rects = self._light_rects()
        right = rects[0].left() - 12 if rects else self.width() - PAD_X
        p.drawText(QRect(PAD_X, 0, right - PAD_X, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft,
                   self._title or self._window.windowTitle())

        for i, rect in enumerate(rects):
            col = QColor(color(LIGHT_FILL[self._lights[i]]))
            if self._hover == i:
                col = col.lighter(112)
            p.setBrush(col)
            p.setPen(QColor(0, 0, 0, 64))
            p.drawEllipse(rect)

    # -- interaction ------------------------------------------------------
    def mouseMoveEvent(self, event) -> None:
        hit = self._light_at(event.position().toPoint())
        if hit != self._hover:
            self._hover = hit
            self.setToolTip(LIGHT_NAME[self._lights[hit]] if hit >= 0 else "")
            self.update()

    def leaveEvent(self, event) -> None:
        self._hover = -1
        self.update()

    def mousePressEvent(self, event) -> None:
        hit = self._light_at(event.position().toPoint())
        if hit < 0:
            return
        action = self._lights[hit]
        if action == "close":
            self._window.close()
        elif action == "min":
            self._window.showMinimized()
        elif action == "max":
            if self._window.isMaximized():
                self._window.showNormal()
            else:
                self._window.showMaximized()


class ModalDialogFrame:
    """Give a QDialog the reference's frame.

    Call before adding content. Returns the layout for the dialog body, so
    the title strip always sits above it. The caller adds its action bar with
    `add_action_bar`, which spans the dialog outside the body's gutter.
    """

    @staticmethod
    def install(dialog, title: str,
                lights: tuple[str, ...] = LIGHTS) -> QVBoxLayout:
        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        dialog.setWindowTitle(title)
        bar = WindowTitleBar(dialog, title, lights)
        if native_frame.install(dialog, METRICS["titlebar_h"], bar.is_caption):
            native_frame.round_corners(dialog)
            outer.addWidget(bar)
        # Otherwise the native title bar is kept; a drawn one as well would
        # show two titles.

        body = QWidget()
        body.setProperty("dialogContent", "true")
        body_layout = QVBoxLayout(body)
        # .dialog-content: padding 10px, gap 8px
        body_layout.setContentsMargins(10, 10, 10, 10)
        body_layout.setSpacing(8)
        outer.addWidget(body, 1)
        dialog._modal_outer = outer
        return body_layout

    @staticmethod
    def add_action_bar(dialog) -> QHBoxLayout:
        """The reference's `.dialog-action-bar`, flush to the dialog edges."""
        bar = QWidget()
        bar.setProperty("actionBar", "true")
        row = QHBoxLayout(bar)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(6)
        dialog._modal_outer.addWidget(bar)
        return row
