"""
ui/welcome.py — the starting-layout wizard, shown when CMAT opens.

Follows ui/reference/dialogs.css modal 1: a 580px dialog in the ordinary window
chrome (ui/modal.py), a header pair, one inset list box of layouts, a name
field, and an action bar carrying the "show this at startup" toggle beside the
buttons.

The layouts are the real templates from analyzer.pipeline_graph.TEMPLATES, with
the summary and detail text the registry already carries. The reference draws
four; there are seven, including Mixed methods, Validation study and Blank
canvas. Showing four would make the wizard a worse map of the tool than the
tool is.

The reference's action bar has a Back button, which is dropped: this is the
first screen, so there is nothing behind it, and a dead control is worse than
an honest one. Skip takes its place.

The list is built from radio buttons in one group rather than a QListView with
a delegate, because the rows carry wrapped prose of very different heights.
Arrow-key navigation is NOT free that way: Qt moves between radio buttons with
the arrows only when they share a parent, and each row here is its own widget,
so `keyPressEvent` does it explicitly.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from analyzer.pipeline_graph import TEMPLATES, unique_name
from analyzer.prefs import get_pref, set_pref
from ui.modal import ModalDialogFrame
from ui.tokens import color

DIALOG_W = 580        # .layout-dialog width
LIST_MAX_H = 320      # .list-view max-height

# The record of which templates have a row. Add a template, add it here; a
# test fails otherwise, so a new layout cannot be silently left out.
TEMPLATE_KEYS = ("full", "automated", "handcoding", "language", "mixed",
                 "validation", "blank")


class Dot(QWidget):
    """The chosen-row mark, painted rather than a styled QRadioButton.

    Qt draws a radio indicator as a small bevelled box, and the box takes the
    widget background, so on a filled row it stamped a pale slab over the
    fill. Styling it away needs a radial gradient for the dot, and Qt rejects
    `transparent` as a gradient stop and substitutes white — which is the pale
    disc that survived two attempts to remove it. Painting it is both shorter
    and exact.
    """

    D = 13

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(self.D + 2, self.D + 2)
        self._on = False

    def set_on(self, on: bool) -> None:
        if on != self._on:
            self._on = on
            self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        ring = QRectF(1, 1, self.D, self.D)
        if self._on:
            # On the filled row: white ring, fill showing through, white dot.
            p.setPen(QPen(QColor(color("text_on_accent")), 1))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(ring)
            p.setBrush(QColor(color("text_on_accent")))
            p.setPen(Qt.NoPen)
            p.drawEllipse(ring.adjusted(3.5, 3.5, -3.5, -3.5))
        else:
            p.setPen(QPen(QColor(color("control_border")), 1))
            p.setBrush(QColor(color("panel_bg")))
            p.drawEllipse(ring)


class LayoutRow(QWidget):
    """One layout, as the reference's `.list-item`."""

    picked = Signal(str)

    def __init__(self, template) -> None:
        super().__init__()
        self.key = template.key
        self.setProperty("listItem", "true")
        self.setProperty("selected", "false")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)

        # .list-item: padding 6px 8px, gap 8px, align-items flex-start
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(8)

        self.dot = Dot()
        row.addWidget(self.dot, 0, Qt.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(2)
        self._title = QLabel(template.name)
        self._title.setProperty("listItemTitle", "true")
        text.addWidget(self._title)
        self._desc = QLabel(f"{template.summary}. {template.detail}")
        self._desc.setProperty("listItemDesc", "true")
        self._desc.setWordWrap(True)
        text.addWidget(self._desc)
        row.addLayout(text, 1)

    def set_selected(self, on: bool) -> None:
        for w in (self, self._title, self._desc):
            w.setProperty("selected", "true" if on else "false")
            # A property change needs an explicit repolish to take effect.
            w.style().unpolish(w)
            w.style().polish(w)
        self.dot.set_on(on)

    def mousePressEvent(self, event) -> None:
        self.picked.emit(self.key)


class WelcomeDialog(QDialog):
    """Choose a starting layout. Leaves `doc` set to the built PipelineDoc."""

    def __init__(self, existing_names: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setFixedWidth(DIALOG_W)
        self._existing = existing_names
        self.doc = None

        body = ModalDialogFrame.install(self, "Welcome to CMAT")

        header = QWidget()
        hv = QVBoxLayout(header)
        hv.setContentsMargins(0, 0, 0, 0)
        hv.setSpacing(0)
        title = QLabel("Choose a starting layout")
        title.setProperty("wizardTitle", "true")
        hv.addWidget(title)
        sub = QLabel("A starting point, not a restriction — add, remove, and "
                     "rewire stages at any time.")
        sub.setProperty("wizardSubtitle", "true")
        sub.setWordWrap(True)
        hv.addWidget(sub)
        body.addWidget(header)

        # .list-view: one inset box, rows divided by a hairline.
        listbox = QScrollArea()
        listbox.setProperty("listView", "true")
        listbox.setWidgetResizable(True)
        # The list takes the keyboard, so the arrows reach keyPressEvent
        # instead of being swallowed by whatever Qt focused first.
        listbox.setFocusPolicy(Qt.StrongFocus)
        listbox.setMaximumHeight(LIST_MAX_H)
        host = QWidget()
        host.setProperty("listHost", "true")
        host.setAttribute(Qt.WA_StyledBackground, True)
        rows = QVBoxLayout(host)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(0)

        self._rows: dict[str, LayoutRow] = {}
        for i, template in enumerate(TEMPLATES):
            row = LayoutRow(template)
            row.picked.connect(self._select)
            rows.addWidget(row)
            self._rows[template.key] = row
            if i < len(TEMPLATES) - 1:
                rows.addWidget(self._divider())
        rows.addStretch(1)
        listbox.setWidget(host)
        body.addWidget(listbox, 1)

        name_row = QWidget()
        nr = QHBoxLayout(name_row)
        nr.setContentsMargins(0, 2, 0, 0)
        nr.setSpacing(6)
        nr.addWidget(QLabel("Pipeline name:"))
        self._name = QLineEdit()
        nr.addWidget(self._name, 1)
        body.addWidget(name_row)

        action = ModalDialogFrame.add_action_bar(self)
        self._show_again = QCheckBox("Show this when CMAT starts")
        self._show_again.setChecked(bool(get_pref("show_welcome_on_start",
                                                  True)))
        action.addWidget(self._show_again)
        action.addStretch(1)
        skip = QPushButton("Skip")
        skip.clicked.connect(self.reject)
        action.addWidget(skip)
        self._create = QPushButton("Create Pipeline")
        self._create.setProperty("primary", "true")
        self._create.setDefault(True)
        self._create.clicked.connect(self._accept)
        action.addWidget(self._create)

        self._order = [t.key for t in TEMPLATES]
        self._listbox = listbox
        self._select(TEMPLATES[0].key)

    def showEvent(self, event) -> None:
        """Focus the list, not the name field.

        Qt gives focus to the first widget in the tab order, which was the
        name field — and the arrow keys are deliberately left to it while it
        has focus, so on a freshly opened dialog they appeared dead.
        """
        super().showEvent(event)
        self._listbox.setFocus()

    @staticmethod
    def _divider() -> QFrame:
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background:{color('list_divider')};border:none;")
        return line

    # -- behaviour --------------------------------------------------------
    def keyPressEvent(self, event) -> None:
        """Up and down move through the layouts.

        Qt moves between radio buttons with the arrow keys only when they
        share a parent. Each row is its own widget here, so the group never
        forms and the navigation has to be explicit.
        """
        if event.key() in (Qt.Key_Up, Qt.Key_Down) and not self._name.hasFocus():
            step = -1 if event.key() == Qt.Key_Up else 1
            i = self._order.index(self._selected)
            nxt = min(max(i + step, 0), len(self._order) - 1)
            if nxt != i:
                self._select(self._order[nxt])
                self._listbox.ensureWidgetVisible(self._rows[self._order[nxt]])
            event.accept()
            return
        super().keyPressEvent(event)

    def _select(self, key: str) -> None:
        self._selected = key
        for row_key, row in self._rows.items():
            row.set_selected(row_key == key)
        template = next(t for t in TEMPLATES if t.key == key)
        # The suggested name follows the chosen layout and stays unique.
        self._name.setText(unique_name(self._existing, template.name))

    def _accept(self) -> None:
        template = next(t for t in TEMPLATES if t.key == self._selected)
        name = self._name.text().strip() or template.name
        self.doc = template.build(name)
        set_pref("show_welcome_on_start", self._show_again.isChecked())
        self.accept()

    def reject(self) -> None:
        # The toggle is honoured even when the wizard is dismissed; otherwise
        # unticking it and closing would leave it ticked next time.
        set_pref("show_welcome_on_start", self._show_again.isChecked())
        super().reject()
