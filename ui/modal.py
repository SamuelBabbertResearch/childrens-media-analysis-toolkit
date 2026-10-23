"""Shared dialog content and action bars beneath a standard native caption.

The platform owns movement, resizing and caption buttons. Dialogs retain the
shared compact content styling and declare supported native controls using
ModalDialogFrame.install's buttons argument.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from ui import native_frame


class ModalDialogFrame:
    """Give a QDialog native caption controls and shared content styling.

    Call before adding content. Returns the layout for the dialog body.
    `add_action_bar` spans the dialog outside the body's gutter.
    """

    @staticmethod
    def install(dialog, title: str,
                buttons: tuple[str, ...] = ("close",)) -> QVBoxLayout:
        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        dialog.setWindowTitle(title)
        native_frame.apply_native_frame(dialog, buttons)

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


class ConfirmDialog(QDialog):
    """A destructive confirmation, in the application's own chrome.

    Not a QMessageBox: the stock box arrives in the platform's dialog style
    rather than this one, and its default button is the affirmative — so
    dismissing it with Enter carries out the destruction. Here Cancel is the
    default and holds the keyboard, and the confirming button is ordinary
    rather than accented, because the accent means "this is the action you
    probably want" and for a deletion it is not.

    `detail` is where the caller says what will NOT be lost. That is usually
    the sentence a person actually needs before deciding.
    """

    def __init__(self, parent, title: str, question: str, detail: str = "",
                 confirm_text: str = "Delete") -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setMinimumWidth(400)
        body = ModalDialogFrame.install(self, title)

        ask = QLabel(question)
        ask.setWordWrap(True)
        ask.setProperty("confirmQuestion", "true")
        body.addWidget(ask)
        if detail:
            note = QLabel(detail)
            note.setWordWrap(True)
            note.setProperty("role", "dim")
            body.addWidget(note)
        body.addStretch(1)

        row = ModalDialogFrame.add_action_bar(self)
        row.addStretch(1)
        confirm = QPushButton(confirm_text)
        confirm.clicked.connect(self.accept)
        row.addWidget(confirm)
        cancel = QPushButton("Cancel")
        cancel.setDefault(True)
        cancel.setAutoDefault(True)
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        cancel.setFocus()

    @staticmethod
    def ask(parent, title: str, question: str, detail: str = "",
            confirm_text: str = "Delete") -> bool:
        dialog = ConfirmDialog(parent, title, question, detail, confirm_text)
        return dialog.exec() == QDialog.Accepted
