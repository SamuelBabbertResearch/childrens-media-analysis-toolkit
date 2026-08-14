"""
ui/eras.py — define a show's production eras.

An era is a named date range. They exist because a long-running show is not
one thing: forty years of *Sesame Street* averaged into a single row describes
nothing that exists, which is why the published-corpus policy splits long runs
into eras rather than averaging them whole (`DECISIONS.md`, 2026-07-01).

Defined here, eras are used in two places:

* the **Episode Sampler**, to stratify a draw by era so a study gets
  comparable coverage of the 1980s and the 2000s rather than a sample
  dominated by whichever period has more episodes on disk;
* chart colouring, which is what they were originally added for.

Eras are stored per show in the index (`show_eras`). The matching itself is
`analyzer/eras.py` — a pure function over air dates, so it is testable without
a database and behaves identically wherever it is called.

WHAT THIS SCREEN CHECKS, BECAUSE IT IS THE POINT
------------------------------------------------
An era with no episodes in it is a stratum the sampler cannot draw from, and
an era covering one episode is censused rather than sampled. Both are shown as
you type, against the show's real air dates, so the ranges get fixed here
rather than producing a strange sample later.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from analyzer.eras import UNASSIGNED, assign_eras, coverage_note, normalise_date
from ui.modal import ModalDialogFrame

DIALOG_W = 660
DIALOG_H = 480

COLUMNS = ("Era", "From", "To", "Episodes")


class ErasDialog(QDialog):
    """Name the date ranges a show's run divides into."""

    def __init__(self, show_key: str, episodes: list, eras: list[dict],
                 conn, parent=None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.resize(DIALOG_W, DIALOG_H)
        self._show_key = show_key
        self._episodes = episodes
        self._conn = conn
        self.eras = [dict(e) for e in eras]
        self.saved = False

        body = ModalDialogFrame.install(self, f"Eras — {show_key}",
                                        buttons=("close",))

        intro = QLabel(
            "An era is a named date range. Stratifying a sample by era gives "
            "a long-running show comparable coverage across its periods, "
            "instead of a draw dominated by whichever years have more "
            "episodes on disk.\n\n"
            "Episodes are placed by AIR DATE, which comes from the index — "
            "import metadata first, or episodes land in "
            f"“{UNASSIGNED}”.")
        intro.setWordWrap(True)
        intro.setProperty("role", "dim")
        body.addWidget(intro)

        self._table = QTreeWidget()
        self._table.setColumnCount(len(COLUMNS))
        self._table.setHeaderLabels(list(COLUMNS))
        self._table.setRootIsDecorated(False)
        self._table.setUniformRowHeights(True)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setFrameShape(QFrame.NoFrame)
        body.addWidget(self._table, 1)

        body.addWidget(self._add_row())

        self._note = QLabel("")
        self._note.setWordWrap(True)
        body.addWidget(self._note)

        row = ModalDialogFrame.add_action_bar(self)
        self._btn_remove = QPushButton("Remove Selected")
        self._btn_remove.clicked.connect(self._remove)
        row.addWidget(self._btn_remove)
        row.addStretch(1)
        save = QPushButton("Save Eras")
        save.setProperty("primary", "true")
        save.clicked.connect(self._save)
        row.addWidget(save)
        close = QPushButton("Cancel")
        close.clicked.connect(self.reject)
        row.addWidget(close)

        self._refresh()

    def _add_row(self) -> QWidget:
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(QLabel("Name:"))
        self._name = QLineEdit()
        self._name.setPlaceholderText("1980s")
        row.addWidget(self._name, 2)
        row.addWidget(QLabel("From:"))
        self._start = QLineEdit()
        self._start.setPlaceholderText("1980 or 1980-01-01")
        row.addWidget(self._start, 1)
        row.addWidget(QLabel("To:"))
        self._end = QLineEdit()
        self._end.setPlaceholderText("blank = to the present")
        row.addWidget(self._end, 1)
        add = QPushButton("Add Era")
        add.clicked.connect(self._add)
        row.addWidget(add)
        return page

    # -- editing -----------------------------------------------------------
    def _add(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.information(self, "Eras",
                                    "An era needs a name — “1980s”, "
                                    "“post-2000 revival”, whatever you will "
                                    "call it in the write-up.")
            return
        start_raw, end_raw = self._start.text().strip(), self._end.text().strip()
        start, end = normalise_date(start_raw), normalise_date(end_raw)
        unreadable = [raw for raw, iso in ((start_raw, start), (end_raw, end))
                      if raw and not iso]
        if unreadable:
            QMessageBox.information(
                self, "Eras",
                f"Could not read {' and '.join(repr(u) for u in unreadable)} "
                f"as a date. Try 1985, 1985-06-01, or 1 June 1985.")
            return
        if start and end and end < start:
            QMessageBox.information(self, "Eras",
                                    "The end date is before the start date.")
            return
        self.eras.append({"era_name": name, "start_date": start or None,
                          "end_date": end or None, "color": None})
        # Kept in start-date order, matching how the index returns them — and
        # era_for_date takes the first match, so the order is not cosmetic.
        self.eras.sort(key=lambda e: e.get("start_date") or "0")
        self._name.clear()
        self._start.clear()
        self._end.clear()
        self._refresh()

    def _remove(self) -> None:
        for item in self._table.selectedItems():
            index = self._table.indexOfTopLevelItem(item)
            if 0 <= index < len(self.eras):
                del self.eras[index]
        self._refresh()

    def _refresh(self) -> None:
        """Re-tag the episodes and show how many land in each era."""
        counts = assign_eras(self._episodes, self.eras)
        self._table.clear()
        for era in self.eras:
            name = era.get("era_name", "")
            item = QTreeWidgetItem([
                name, era.get("start_date") or "—",
                era.get("end_date") or "present",
                str(counts.get(name, 0))])
            item.setTextAlignment(3, Qt.AlignRight | Qt.AlignVCenter)
            self._table.addTopLevelItem(item)
        if counts.get(UNASSIGNED):
            item = QTreeWidgetItem([UNASSIGNED, "—", "—",
                                    str(counts[UNASSIGNED])])
            item.setTextAlignment(3, Qt.AlignRight | Qt.AlignVCenter)
            item.setDisabled(True)
            self._table.addTopLevelItem(item)
        head = self._table.header()
        head.setStretchLastSection(False)
        head.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2, 3):
            head.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self._btn_remove.setEnabled(bool(self.eras))
        self._note.setText(coverage_note(counts))

    def _save(self) -> None:
        if self._conn is None:
            QMessageBox.warning(self, "Eras",
                                "The index could not be opened, so eras "
                                "cannot be saved.")
            return
        from analyzer.db import save_show_eras
        try:
            save_show_eras(self._conn, self._show_key, self.eras)
        except Exception as exc:            # noqa: BLE001 — shown, not hidden
            QMessageBox.warning(self, "Could not save eras", str(exc))
            return
        self.saved = True
        self.accept()
