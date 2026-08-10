"""
ui/welcome.py — the starting-layout wizard, shown when CMAT opens.

Follows ui/reference/welcome.css: a 620px modal with a metallic header (see
ui/modal.py), a scrolling list of option cards, a name field, and a footer
carrying the "show this at startup" toggle beside the buttons.

The reference draws a glyph on each card; they are left off at the user's
request. The reference's footer also has a Back button, which is dropped:
this is the first screen, so there is nothing behind it, and a dead control
is worse than an honest one. Skip takes its place.

The cards are the real templates from analyzer.pipeline_graph.TEMPLATES, and
their titles and descriptions are the ones the registry already carries. The
reference shows four; there are seven, including Mixed methods, Validation
study, and Blank canvas. Showing four and quietly dropping three would make
the wizard a worse map of the tool than the tool is.

The wizard is a starting point, not a commitment: every template is an
ordinary document that can be rewired afterwards, which is what the subtitle
says and what the Pipeline tab then allows.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from analyzer.pipeline_graph import TEMPLATES, unique_name
from analyzer.prefs import get_pref, set_pref
from ui.modal import ModalDialogFrame
from ui.tokens import color

MODAL_W = 620         # .layout-modal width
CARD_LIST_H = 380     # .card-list max-height

# The reference draws a glyph beside each card; they are deliberately not used.
# Kept as the record of which templates a card exists for, which is what the
# test checks — add a template, add it here.
TEMPLATE_KEYS = ("full", "automated", "handcoding", "language", "mixed",
                 "validation", "blank")


class OptionCard(QFrame):
    """One template, as the reference's .option-card."""

    clicked = Signal(str)

    def __init__(self, template) -> None:
        super().__init__()
        self.key = template.key
        self.setProperty("card", "true")
        self.setProperty("selected", "false")
        self.setCursor(Qt.PointingHandCursor)

        # .option-card padding: 10px 12px
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(10)

        text = QVBoxLayout()
        text.setSpacing(4)
        title = QLabel(template.name)
        title.setProperty("cardTitle", "true")
        text.addWidget(title)
        # Summary then detail, both straight from the registry.
        body = QLabel(f"{template.summary}. {template.detail}")
        body.setProperty("cardDesc", "true")
        body.setWordWrap(True)
        text.addWidget(body)
        row.addLayout(text, 1)

    def set_selected(self, on: bool) -> None:
        self.setProperty("selected", "true" if on else "false")
        # A property change needs an explicit repolish to take effect.
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self.key)


class WelcomeDialog(QDialog):
    """Choose a starting layout. Returns the built PipelineDoc, or None."""

    def __init__(self, existing_names: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Welcome to CMAT")
        self.setModal(True)
        self.setFixedWidth(MODAL_W)
        self._existing = existing_names
        self.doc = None

        outer = ModalDialogFrame.install(self, "Welcome to CMAT")

        heading = QLabel("Choose a starting layout")
        heading.setProperty("wizardTitle", "true")
        outer.addWidget(heading)
        sub = QLabel("A starting point, not a restriction — add, remove, and "
                     "rewire stages at any time.")
        sub.setProperty("wizardSubtitle", "true")
        sub.setWordWrap(True)
        outer.addWidget(sub)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMaximumHeight(CARD_LIST_H)
        host = QWidget()
        cards = QVBoxLayout(host)
        cards.setContentsMargins(0, 0, 4, 0)
        cards.setSpacing(8)

        self._cards: dict[str, OptionCard] = {}
        for template in TEMPLATES:
            card = OptionCard(template)
            card.clicked.connect(self._select)
            cards.addWidget(card)
            self._cards[template.key] = card
        cards.addStretch(1)
        scroll.setWidget(host)
        outer.addWidget(scroll, 1)

        name_row = QWidget()
        name_row.setProperty("nameRow", "true")
        nr = QHBoxLayout(name_row)
        nr.setContentsMargins(0, 8, 0, 0)
        nr.setSpacing(8)
        nr.addWidget(QLabel("Pipeline name:"))
        self._name = QLineEdit()
        nr.addWidget(self._name, 1)
        outer.addWidget(name_row)

        footer = QWidget()
        footer.setProperty("modalFooter", "true")
        fr = QHBoxLayout(footer)
        fr.setContentsMargins(12, 8, 12, 8)
        fr.setSpacing(6)
        self._show_again = QCheckBox("Show this when CMAT starts")
        self._show_again.setChecked(bool(get_pref("show_welcome_on_start",
                                                  True)))
        fr.addWidget(self._show_again)
        fr.addStretch(1)
        skip = QPushButton("Skip")
        skip.clicked.connect(self.reject)
        fr.addWidget(skip)
        self._create = QPushButton("Create Pipeline")
        self._create.setProperty("primary", "true")
        self._create.setDefault(True)
        self._create.clicked.connect(self._accept)
        fr.addWidget(self._create)
        # The footer spans the modal, outside the body's 12px gutter.
        self._modal_outer.addWidget(footer)

        self._select(TEMPLATES[0].key)

    # -- behaviour --------------------------------------------------------
    def _select(self, key: str) -> None:
        self._selected = key
        for card_key, card in self._cards.items():
            card.set_selected(card_key == key)
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
