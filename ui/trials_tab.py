"""
ui/trials_tab.py — the Trials tab: every recorded run, and what it produced.

A trial is a run that was written down: a validation against hand coding, a
detector sweep, an episode sample. `analyzer.trials.discover_trials` finds them
on disk, so this screen adds no bookkeeping of its own and cannot drift from
what `validate_cuts.py` and `code_events.py` actually wrote.

The detail pane shows the run's own record — its result, its window, the commit
it ran at — beside the registry's plain-English explanation of what that kind
of trial is for. A figure like "F1 0.91" means nothing without knowing what was
compared with what, and that sentence is already in `KIND_EXPLANATIONS`.

Guardrail: a trial's result describes the TOOL's agreement with a human coder.
It is not a statement about the programme.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFrame, QGridLayout, QHeaderView, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from analyzer.trials import (
    KIND_EXPLANATIONS, KIND_LABELS, discover_trials, get_validation_dir,
)

COLUMNS = ("Kind", "Episode or sample", "Date", "Result", "Episodes",
           "Published")
KEY_W = 140


class TrialsTab(QWidget):
    """Recorded runs, newest first, with the detail of the selected one."""

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self._trials: list[dict] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        from ui.main_window import Panel, SubToolBar
        bar = SubToolBar()
        bar.row.addWidget(QLabel("Kind:"))
        self._kind = QComboBox()
        self._kind.addItem("All kinds", "")
        for key, label in KIND_LABELS.items():
            self._kind.addItem(label, key)
        self._kind.currentIndexChanged.connect(self._fill)
        bar.row.addWidget(self._kind)
        bar.row.addStretch(1)
        self._count = QLabel("")
        self._count.setProperty("role", "dim")
        bar.row.addWidget(self._count)
        self._btn_folder = QPushButton("Open Folder")
        self._btn_folder.setEnabled(False)
        self._btn_folder.clicked.connect(self._open_folder)
        bar.row.addWidget(self._btn_folder)
        self._btn_refresh = QPushButton("Refresh")
        self._btn_refresh.clicked.connect(self.refresh)
        bar.row.addWidget(self._btn_refresh)
        lay.addWidget(bar)

        holder = QWidget()
        hv = QVBoxLayout(holder)
        hv.setContentsMargins(8, 8, 8, 8)
        hv.setSpacing(6)

        panel = Panel("Recorded runs")
        self._table = QTreeWidget()
        self._table.setColumnCount(len(COLUMNS))
        self._table.setHeaderLabels(list(COLUMNS))
        self._table.setRootIsDecorated(False)
        self._table.setUniformRowHeights(True)
        self._table.setProperty("inPanel", "true")
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setFrameShape(QFrame.NoFrame)
        self._table.header().setStretchLastSection(False)
        self._table.itemSelectionChanged.connect(self._show_detail)
        self._table.itemDoubleClicked.connect(
            lambda *_: self._open_folder())
        panel.body_layout.addWidget(self._table)
        hv.addWidget(panel, 2)

        self._detail_panel = Panel("Trial detail")
        detail = QWidget()
        detail.setAttribute(Qt.WA_StyledBackground, True)
        detail.setStyleSheet("background:#ffffff;")
        self._grid = QGridLayout(detail)
        self._grid.setContentsMargins(8, 8, 8, 8)
        self._grid.setSpacing(0)
        self._detail_panel.body_layout.addWidget(detail)
        hv.addWidget(self._detail_panel, 1)

        lay.addWidget(holder, 1)

    # -- data -------------------------------------------------------------
    def refresh(self) -> None:
        extra = [self._window._root] if self._window._root else []
        try:
            self._trials = discover_trials(get_validation_dir(),
                                           extra_dirs=extra)
        except Exception as exc:            # noqa: BLE001 - shown, not hidden
            self._trials = []
            self._count.setText(f"could not read trials: {exc}")
            return
        self._fill()

    def _fill(self) -> None:
        wanted = self._kind.currentData()
        rows = [t for t in self._trials
                if not wanted or t.get("kind") == wanted]
        self._table.clear()
        for trial in rows:
            item = QTreeWidgetItem([
                KIND_LABELS.get(trial.get("kind", ""), trial.get("kind", "—")),
                trial.get("name") or trial.get("episode") or "—",
                str(trial.get("date") or "—"),
                trial.get("result") or "—",
                str(trial.get("n_episodes") or "—"),
                "yes" if trial.get("published") else "—",
            ])
            for col in (4, 5):
                item.setTextAlignment(col, Qt.AlignRight | Qt.AlignVCenter)
            item.setData(0, Qt.UserRole, trial)
            self._table.addTopLevelItem(item)

        head = self._table.header()
        head.setSectionResizeMode(1, QHeaderView.Stretch)
        for col in (0, 2, 3, 4, 5):
            head.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self._count.setText(
            f"{len(rows)} trial{'s' if len(rows) != 1 else ''}"
            + (f" of {len(self._trials)}" if wanted else ""))
        self._clear_detail()

    # -- detail -----------------------------------------------------------
    def _clear_detail(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._btn_folder.setEnabled(False)
        self._detail_panel.set_title("Trial detail")

    def _selected(self) -> dict | None:
        items = self._table.selectedItems()
        return items[0].data(0, Qt.UserRole) if items else None

    def _show_detail(self) -> None:
        trial = self._selected()
        self._clear_detail()
        if not trial:
            return
        kind = trial.get("kind", "")
        self._detail_panel.set_title(
            KIND_LABELS.get(kind, kind) or "Trial detail")
        self._btn_folder.setEnabled(bool(trial.get("folder")
                                         or trial.get("manifest_path")))

        rows: list[tuple[str, str]] = []
        # What this kind of trial is, before what this one found: a figure
        # like "F1 0.91" says nothing without the comparison behind it.
        if KIND_EXPLANATIONS.get(kind):
            rows.append(("What this is", KIND_EXPLANATIONS[kind]))
        for label, key in (("Episode", "episode"), ("Sample", "name"),
                           ("Date", "date"), ("Result", "result"),
                           ("Detail", "detail"), ("Window", "window"),
                           ("Episodes", "n_episodes"),
                           ("Sampling", "sampling"),
                           ("Code version", "git_commit")):
            value = trial.get(key)
            if value not in (None, "", []):
                rows.append((label, str(value)))
        path = trial.get("manifest_path") or trial.get("folder")
        if path:
            rows.append(("On disk", str(path)))

        for r, (key, value) in enumerate(rows):
            k = QLabel(key)
            k.setProperty("kvKey", "true")
            k.setFixedWidth(KEY_W)
            k.setAlignment(Qt.AlignRight | Qt.AlignTop)
            v = QLabel(value)
            v.setProperty("kvVal", "true")
            v.setWordWrap(True)
            self._grid.addWidget(k, r, 0)
            self._grid.addWidget(v, r, 1)
        self._grid.setColumnStretch(1, 1)
        self._grid.setRowStretch(len(rows), 1)

    # -- actions ----------------------------------------------------------
    def _open_folder(self) -> None:
        """Reveal the run on disk, since that is where its raw files are."""
        trial = self._selected()
        if not trial:
            return
        target = trial.get("folder") or trial.get("manifest_path")
        if not target:
            return
        path = Path(target)
        folder = path if path.is_dir() else path.parent
        if not folder.exists():
            self._window.statusBar().showMessage(
                f"{folder} is recorded but no longer on disk.", 6000)
            return
        if sys.platform == "win32":
            os.startfile(folder)            # noqa: S606 - a folder, not input
        else:
            subprocess.Popen(
                ["open" if sys.platform == "darwin" else "xdg-open",
                 str(folder)])
