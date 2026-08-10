"""
ui/modal.py — the window title strip, and the frame the dialogs are drawn in.

`ui/reference/dialogs.css` gives a dialog the SAME chrome as the main window:
a title strip with the document name left and the caption controls right, over
a rounded window in the ordinary window colour. That is the point of the
design — a dialog is a small window, not a differently-styled object — so one
`WindowTitleBar` serves both, and a dialog introduces no palette of its own.

**The caption controls are Windows', not the reference's.** The mockups draw
three round lights in close-minimise-zoom order, which is another platform's
convention: the order is reversed from Windows, the shapes carry no meaning to
anyone who has not used that platform, and there is no restore affordance.
This is a Windows application, and `DESIGN.md` §7 already puts platform
behaviour above the visual specification. So the strip carries minimise,
maximise/restore and close, left to right at the right-hand end, drawn as
Windows draws them, red close hover included. The title is set in the
platform's caption size rather than the bold small type the mockups use.

The glyphs are painted rather than taken from an icon font, so they do not
depend on Segoe Fluent Icons or Segoe MDL2 Assets being installed and they
stay crisp at every scale factor.

The frame is suppressed rather than removed: see `ui/native_frame.py`. Never
`Qt.FramelessWindowHint`, which strips `WS_THICKFRAME`/`WS_CAPTION` and takes
snap, edge resizing, the drop shadow and the system menu with it.

A dialog that cannot be maximised shows close alone, so the set is a parameter.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ui import native_frame, theme
from ui.tokens import METRICS, color

PAD_X = 8

# Windows order, left to right at the right-hand end of the strip.
CAPTION_BUTTONS = ("min", "max", "close")
CAPTION_NAME = {"min": "Minimize", "max": "Maximize", "close": "Close"}


class WindowTitleBar(QWidget):
    """The title strip: document name left, Windows caption controls right.

    Windows conventions are preserved rather than replaced. The strip reports
    HTCAPTION (see ui/native_frame.py), so dragging, snapping,
    double-click-to-maximise and the right-click system menu all still come
    from the system; only the painting is ours.
    """

    def __init__(self, window, title: str = "",
                 buttons: tuple[str, ...] = CAPTION_BUTTONS) -> None:
        super().__init__()
        self._window = window
        self._title = title
        self._buttons = buttons
        self._hover = -1
        self.setFixedHeight(METRICS["titlebar_h"])
        self.setMouseTracking(True)

    # -- geometry ---------------------------------------------------------
    def _button_rects(self) -> list[QRect]:
        w = METRICS["caption_btn_w"]
        out = []
        x = self.width() - w * len(self._buttons)
        for _ in self._buttons:
            out.append(QRect(x, 0, w, self.height() - 1))
            x += w
        return out

    def _button_at(self, pos: QPoint) -> int:
        for i, r in enumerate(self._button_rects()):
            if r.contains(pos):
                return i
        return -1

    def is_caption(self, x: int, y: int) -> bool:
        """False over a control, so it takes the click, not the drag."""
        return self._button_at(QPoint(x, y)) < 0

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

        rects = self._button_rects()
        p.setFont(theme.font("caption"))
        p.setPen(QColor(color("titlebar_fg")))
        right = rects[0].left() - 8 if rects else self.width() - PAD_X
        p.drawText(QRect(PAD_X, 0, max(0, right - PAD_X), self.height() - 1),
                   Qt.AlignVCenter | Qt.AlignLeft,
                   self._title or self._window.windowTitle())

        for i, rect in enumerate(rects):
            self._paint_button(p, rect, self._buttons[i], i == self._hover)

    def _paint_button(self, p: QPainter, rect: QRect, kind: str,
                      hover: bool) -> None:
        fg = QColor(color("titlebar_fg"))
        if hover:
            if kind == "close":
                p.fillRect(rect, QColor(color("caption_close_hover")))
                fg = QColor(color("text_on_accent"))
            else:
                p.fillRect(rect, QColor(color("caption_hover")))

        # A 10px box centred in the button, the size Windows draws its glyphs.
        box = QRectF(0, 0, 10, 10)
        box.moveCenter(QRectF(rect).center())
        p.setPen(QPen(fg, 1))
        p.setBrush(Qt.NoBrush)
        if kind == "min":
            y = int(box.center().y())
            p.drawLine(int(box.left()), y, int(box.right()), y)
        elif kind == "max":
            if self._window.isMaximized():
                # Restore: the two offset frames Windows uses.
                p.drawLine(int(box.left() + 2), int(box.top()),
                           int(box.right()), int(box.top()))
                p.drawLine(int(box.right()), int(box.top()),
                           int(box.right()), int(box.bottom() - 2))
                p.drawRect(box.adjusted(0, 2, -2, 0))
            else:
                p.drawRect(box)
        else:
            p.drawLine(box.topLeft().toPoint(), box.bottomRight().toPoint())
            p.drawLine(box.topRight().toPoint(), box.bottomLeft().toPoint())

    # -- interaction ------------------------------------------------------
    def mouseMoveEvent(self, event) -> None:
        hit = self._button_at(event.position().toPoint())
        if hit != self._hover:
            self._hover = hit
            self.setToolTip(CAPTION_NAME[self._buttons[hit]] if hit >= 0
                            else "")
            self.update()

    def leaveEvent(self, event) -> None:
        self._hover = -1
        self.update()

    def mousePressEvent(self, event) -> None:
        hit = self._button_at(event.position().toPoint())
        if hit < 0:
            return
        action = self._buttons[hit]
        if action == "close":
            self._window.close()
        elif action == "min":
            self._window.showMinimized()
        elif action == "max":
            if self._window.isMaximized():
                self._window.showNormal()
            else:
                self._window.showMaximized()
            self.update()


class ModalDialogFrame:
    """Give a QDialog the reference's frame.

    Call before adding content. Returns the layout for the dialog body, so
    the title strip always sits above it. The caller adds its action bar with
    `add_action_bar`, which spans the dialog outside the body's gutter.
    """

    @staticmethod
    def install(dialog, title: str,
                buttons: tuple[str, ...] = ("close",)) -> QVBoxLayout:
        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        dialog.setWindowTitle(title)
        bar = WindowTitleBar(dialog, title, buttons)
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
