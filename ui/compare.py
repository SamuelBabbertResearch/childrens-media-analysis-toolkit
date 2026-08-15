"""
ui/compare.py — two episodes, or two shows, side by side.

Pin one thing in the Library, select another, compare. The rendering is
`ui.report.compare_html`, which imports no Qt, so the comparison is testable
headless and could back a PDF or the static site later — the same reason the
episode and show reports live there.

GUARDRAIL. A side-by-side is the easiest place in the product to imply a
ranking, and this one does not. Two value columns and a signed difference; no
ordering, no colour, no arrow, no wording that makes one side the winner. See
`CLAUDE.md` §2.1 — CMAT measures the stimulus and issues no verdict.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QFrame, QTextBrowser

from ui import theme
from ui.modal import ModalDialogFrame
from ui.report import compare_html

DIALOG_W = 760
DIALOG_H = 560


class CompareDialog(QDialog):
    """A comparison of two episodes or two show aggregates."""

    def __init__(self, left, right, left_name: str, right_name: str,
                 kind: str = "episode", parent=None) -> None:
        super().__init__(parent)
        self.setModal(False)
        self.resize(DIALOG_W, DIALOG_H)
        body = ModalDialogFrame.install(
            self, f"{left_name}  vs  {right_name}",
            buttons=("min", "max", "close"))

        view = QTextBrowser()
        view.setOpenExternalLinks(False)
        view.setFrameShape(QFrame.NoFrame)
        # Same document metrics as the Library report, or the two panes render
        # the reference's px sizes against different bases.
        view.document().setDocumentMargin(6)
        view.document().setDefaultFont(theme.font("body"))
        view.setHtml(compare_html(left, right, left_name, right_name, kind))
        body.addWidget(view, 1)
