"""
ui/modal.py — the modal frame the reference dialogs are drawn in.

ui/reference/welcome.css gives a modal its own 28px metallic header with the
title on the left and a close mark on the right, over a 5px-rounded window.
Qt gives a QDialog the ordinary Windows title bar instead, which is why a
dialog built from the reference's body alone still does not look like it: the
single most visible element of that design is the part Qt supplies for you.

The frame is suppressed the same way the main window's is — see
ui/native_frame.py — so the header reports HTCAPTION and dragging, the system
menu and Esc all still behave. If the hook cannot attach, the dialog keeps its
native title bar and the drawn header is simply not added, rather than leaving
a dialog with two titles.

Shared rather than written into the wizard, because the Settings dialog in the
same reference file uses exactly this frame.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ui import native_frame, theme
from ui.tokens import color

HEADER_H = 28         # .modal-header height
PAD_X = 10            # .modal-header padding
CLOSE_BOX = 18        # hit target around the close mark


class ModalHeader(QWidget):
    """The reference's metallic modal header: title left, close mark right."""

    def __init__(self, dialog, title: str) -> None:
        super().__init__()
        self._dialog = dialog
        self._title = title
        self._hover = False
        self.setFixedHeight(HEADER_H)
        self.setMouseTracking(True)

    def _close_rect(self) -> QRect:
        return QRect(self.width() - PAD_X - CLOSE_BOX,
                     (self.height() - CLOSE_BOX) // 2, CLOSE_BOX, CLOSE_BOX)

    def is_caption(self, x: int, y: int) -> bool:
        """False over the close mark, so it takes the click, not the drag."""
        return not self._close_rect().contains(x, y)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, QColor(color("metal_top")))
        grad.setColorAt(1.0, QColor(color("metal_bottom")))
        p.fillRect(self.rect(), grad)
        p.setPen(QColor(color("metal_border")))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)

        p.setFont(theme.font("body", bold=True))
        p.setPen(QColor(color("modal_title_fg")))
        p.drawText(QRect(PAD_X, 0, self.width() - PAD_X * 3, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, self._title)

        box = self._close_rect()
        if self._hover:
            p.setBrush(QColor(0, 0, 0, 18))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(box, 3, 3)
        p.setPen(QColor(color("modal_close_fg")))
        p.setFont(theme.font("heading"))
        p.drawText(box, Qt.AlignCenter, "✕")

    def mouseMoveEvent(self, event) -> None:
        hit = self._close_rect().contains(event.position().toPoint())
        if hit != self._hover:
            self._hover = hit
            self.setToolTip("Close" if hit else "")
            self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def mousePressEvent(self, event) -> None:
        if self._close_rect().contains(event.position().toPoint()):
            self._dialog.reject()


class ModalDialogFrame:
    """Mixin helper: give a QDialog the reference's frame.

    Call from a dialog's __init__ BEFORE adding content. Returns the layout
    the caller should put its body into, so the header always sits above it.
    """

    @staticmethod
    def install(dialog, title: str) -> QVBoxLayout:
        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = ModalHeader(dialog, title)
        attached = native_frame.install(dialog, HEADER_H, header.is_caption)
        if attached:
            native_frame.round_corners(dialog)
            outer.addWidget(header)
        else:
            # Native title bar kept; a drawn one as well would show two titles.
            dialog.setWindowTitle(title)

        body = QWidget()
        body.setProperty("modalBody", "true")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 12, 12, 12)
        body_layout.setSpacing(10)
        outer.addWidget(body, 1)
        dialog._modal_outer = outer
        return body_layout
