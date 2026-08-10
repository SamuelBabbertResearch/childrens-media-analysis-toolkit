"""
ui/handcoding.py — the Human coding tab: code events against the video.

Mark an event at the playhead, give it a type, and the row is written to the
same CSV `code_events.py` reads: the columns come from
`analyzer.event_coding`, so a sheet coded here is a sheet the command line can
score and publish, and neither can quietly change the format on the other.

Coding is a human judgement, and the screen says so. Fantasy, narrative
relevance and repetition are not things a pixel measure can decide, which is
why they are coded rather than computed — the point is not that the tool is
too weak to do it, but that these are properties of the story.

If VLC is unavailable the tab explains exactly what is missing instead of
opening a black rectangle: see ui/player.available().
"""

from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QSplitter,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from analyzer.event_coding import EVENT_TYPES, parse_event_csv
from analyzer.trials import get_validation_dir
from ui import player as player_mod

# The column order code_events.py reads. Kept as a constant here so a mismatch
# is one obvious edit rather than a silently malformed sheet.
COLUMNS = ["timestamp_hms", "timestamp_sec", "event_type",
           "narrative_relevance", "repeat", "duration_sec", "notes"]

RELEVANCE = ("integral", "incidental")
REPEAT = ("new", "repeat")


class HandCodingTab(QWidget):
    """Play an episode, mark events, save the sheet."""

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self._episode: Path | None = None
        self._sheet: Path | None = None
        self._player = None
        self._events: list[dict] = []
        self._dirty = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        from ui.main_window import Ambox, Panel, SubToolBar
        bar = SubToolBar()
        self._target = QLabel("No episode selected")
        bar.row.addWidget(self._target, 1)
        self._btn_open = QPushButton("Open Episode")
        self._btn_open.clicked.connect(self._open_episode)
        bar.row.addWidget(self._btn_open)
        self._btn_load = QPushButton("Load Sheet…")
        self._btn_load.clicked.connect(self._load_sheet)
        bar.row.addWidget(self._btn_load)
        self._btn_save = QPushButton("Save Sheet")
        self._btn_save.setProperty("primary", "true")
        self._btn_save.setEnabled(False)
        self._btn_save.clicked.connect(self._save_sheet)
        bar.row.addWidget(self._btn_save)
        lay.addWidget(bar)

        ok, reason = player_mod.available()
        if not ok:
            body = QWidget()
            bl = QVBoxLayout(body)
            bl.setContentsMargins(12, 12, 12, 12)
            bl.addWidget(Ambox(
                "Video playback unavailable", reason
                + "  Coding needs frame-accurate playback, so the screen is "
                  "disabled rather than shown without it.", "warn"))
            bl.addStretch(1)
            lay.addWidget(body, 1)
            for b in (self._btn_open, self._btn_load, self._btn_save):
                b.setEnabled(False)
            return

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(8, 8, 4, 8)
        ll.setSpacing(6)
        self._player = player_mod.VideoPlayer()
        ll.addWidget(self._player, 1)
        ll.addWidget(self._mark_row())
        split.addWidget(left)

        right = Panel("Coded events")
        self._table = QTreeWidget()
        self._table.setColumnCount(5)
        self._table.setHeaderLabels(
            ["Time", "Type", "Relevance", "Repeat", "Note"])
        self._table.setRootIsDecorated(False)
        self._table.setUniformRowHeights(True)
        self._table.setProperty("inPanel", "true")
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setFrameShape(QFrame.NoFrame)
        self._table.header().setStretchLastSection(True)
        self._table.itemDoubleClicked.connect(self._seek_to_event)
        right.body_layout.addWidget(self._table)

        self._btn_delete = QPushButton("Delete Event")
        self._btn_delete.clicked.connect(self._delete_event)
        right.add_header_widget(self._btn_delete)
        split.addWidget(right)

        split.setStretchFactor(0, 60)
        split.setStretchFactor(1, 40)

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(8, 8, 8, 8)
        bl.setSpacing(6)
        bl.addWidget(Ambox(
            "This is a human judgement",
            "Whether something is impossible, whether it matters to the "
            "story, and whether it is a repeat are properties of the story, "
            "not of the pixels. Code them against EVENT_CODEBOOK.md so "
            "another coder can be compared with you."))
        bl.addWidget(split, 1)
        lay.addWidget(body, 1)

    # -- the mark row ------------------------------------------------------
    def _mark_row(self) -> QWidget:
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)

        self._type = QComboBox()
        for key, description in EVENT_TYPES:
            self._type.addItem(key, key)
            self._type.setItemData(self._type.count() - 1, description,
                                   Qt.ToolTipRole)
        rl.addWidget(QLabel("Type:"))
        rl.addWidget(self._type)

        self._relevance = QComboBox()
        self._relevance.addItems(RELEVANCE)
        rl.addWidget(QLabel("Relevance:"))
        rl.addWidget(self._relevance)

        self._repeat = QComboBox()
        self._repeat.addItems(REPEAT)
        rl.addWidget(QLabel("Repeat:"))
        rl.addWidget(self._repeat)

        self._note = QLineEdit()
        self._note.setPlaceholderText("note (required for other_impossible)")
        rl.addWidget(self._note, 1)

        self._btn_mark = QPushButton("Mark at playhead")
        self._btn_mark.setProperty("primary", "true")
        self._btn_mark.setEnabled(False)
        self._btn_mark.clicked.connect(self._mark)
        rl.addWidget(self._btn_mark)
        return row

    # -- episode -----------------------------------------------------------
    def set_target(self, path: Path | None) -> None:
        """The Library selection, when it names a file rather than a folder."""
        if path is not None and path.is_file():
            self._episode = path
            self._target.setText(f"Ready: {path.name}")
        self._sync()

    def _open_episode(self) -> None:
        if self._episode is None:
            chosen, _ = QFileDialog.getOpenFileName(
                self, "Open episode", str(self._window._root or ""),
                "Video (*.mp4 *.mkv *.avi *.mov)")
            if not chosen:
                return
            self._episode = Path(chosen)
        self._player.open(self._episode)
        self._sheet = get_validation_dir() / f"{self._episode.stem}_events.csv"
        if self._sheet.exists():
            self._read_sheet(self._sheet)
        self._target.setText(f"{self._episode.name} — sheet: {self._sheet.name}")
        self._sync()

    # -- events ------------------------------------------------------------
    def _mark(self) -> None:
        if self._player is None:
            return
        etype = self._type.currentData()
        note = self._note.text().strip()
        if etype == "other_impossible" and not note:
            QMessageBox.warning(
                self, "Note required",
                "other_impossible needs a note saying what happened — "
                "otherwise the row cannot be checked by a second coder.")
            return
        seconds = self._player.position()
        self._events.append({
            "timestamp_sec": round(seconds, 3),
            "timestamp_hms": player_mod.sec_to_hms(seconds),
            "event_type": etype,
            "narrative_relevance": self._relevance.currentText(),
            "repeat": self._repeat.currentText(),
            "duration_sec": None,
            "notes": note,
        })
        self._events.sort(key=lambda e: e["timestamp_sec"])
        self._note.clear()
        self._dirty = True
        self._refill()

    def _delete_event(self) -> None:
        items = self._table.selectedItems()
        if not items:
            return
        index = self._table.indexOfTopLevelItem(items[0])
        del self._events[index]
        self._dirty = True
        self._refill()

    def _seek_to_event(self, item, _column) -> None:
        index = self._table.indexOfTopLevelItem(item)
        if self._player is not None and 0 <= index < len(self._events):
            self._player.seek(self._events[index]["timestamp_sec"])

    def _refill(self) -> None:
        self._table.clear()
        for event in self._events:
            self._table.addTopLevelItem(QTreeWidgetItem([
                event["timestamp_hms"], event["event_type"],
                event["narrative_relevance"], event["repeat"],
                event["notes"]]))
        head = self._table.header()
        for col in range(4):
            head.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self._sync()

    # -- the sheet ---------------------------------------------------------
    def _load_sheet(self) -> None:
        chosen, _ = QFileDialog.getOpenFileName(
            self, "Load coding sheet", str(get_validation_dir()),
            "Coding sheet (*.csv)")
        if chosen:
            self._read_sheet(Path(chosen))

    def _read_sheet(self, path: Path) -> None:
        warnings: list[str] = []
        self._events = parse_event_csv(path, warn_cb=warnings.append)
        self._sheet = path
        self._dirty = False
        self._refill()
        if warnings:
            QMessageBox.information(
                self, "Sheet loaded with warnings",
                f"{path.name} loaded, with:\n\n" + "\n".join(warnings[:12]))

    def _save_sheet(self) -> None:
        if self._sheet is None:
            return
        self._sheet.parent.mkdir(parents=True, exist_ok=True)
        with self._sheet.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=COLUMNS)
            writer.writeheader()
            for event in self._events:
                writer.writerow({
                    k: ("" if event.get(k) is None else event.get(k, ""))
                    for k in COLUMNS})
        self._dirty = False
        self._sync()
        self._window.statusBar().showMessage(
            f"Saved {len(self._events)} event"
            f"{'s' if len(self._events) != 1 else ''} to {self._sheet.name}. "
            f"code_events.py can score and publish this sheet.", 8000)

    def _sync(self) -> None:
        has_video = self._player is not None and self._episode is not None
        if hasattr(self, "_btn_mark"):
            self._btn_mark.setEnabled(has_video)
        self._btn_save.setEnabled(self._sheet is not None and self._dirty)
        if hasattr(self, "_btn_delete"):
            self._btn_delete.setEnabled(bool(self._events))
