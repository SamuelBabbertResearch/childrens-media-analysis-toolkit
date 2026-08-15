"""
ui/sampler.py — the Episode Sampler dialog.

The last Tk-only screen. Sampling is the first stage of the pipeline and the
one that decides what every later number is a number ABOUT, so the design is
stated in one sentence and written down with the result:

    "Stratified by season, spread within stratum, n=2, seed=20260629."

WHAT THIS SCREEN IS FOR

Choosing episodes by hand is allowed and sometimes right, but it is a
*non-probability* sample and cannot support inference to the whole show. The
manifest records which of the two this draw was, and the preview says so
before anything is written, because that sentence is the difference between a
sample and a selection.

WHERE THE WORDS COME FROM

Every explanation is `analyzer.sampler.TOOLTIPS` — the module's docstring
calls it the authoritative source, imported by the interface and the docs.
Nothing here re-words them; a change to the method's meaning happens in one
place.

WHAT IT WRITES

`write_outputs` produces `selected.csv`, `manifest.json` and `worklist.txt` in
a dated folder beside the show. `analyzer.pipeline.build_pipelines` discovers
that folder as an episode sample, which is what a pipeline document binds to.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from analyzer.eras import (
    ERA_KEY, UNASSIGNED, assign_eras, attach_air_dates, coverage_note,
    has_declared_eras,
)
from analyzer.sampler import (
    TOOLTIPS, SampleResult, load_registry_csv, sample, scan_entry_root,
    stratification_columns, write_outputs,
)
from analyzer.show_index import show_key
from ui.modal import ModalDialogFrame

DIALOG_W = 900
DIALOG_H = 640

# (value, label, tooltip key). The value is what analyzer.sampler expects.
METHODS = (
    ("spread", "Spread — one at random from each equal chunk",
     "method_spread"),
    ("srs", "Simple random", "method_srs"),
    ("systematic", "Systematic — every Nth", "method_systematic"),
    ("census", "Census — every episode", "method_census"),
    ("manual", "Manual — hand-picked", "method_manual"),
)

# The third value is the key passed to `sample(stratify_by=...)`. "era" is a
# column on Episode.extra, filled by analyzer/eras.py from air dates — see
# _apply_eras below for why it needs the index and the season option does not.
STRATIFY = (
    ("season", "By season", "stratify_season"),
    ("era", "By era (production period)", "stratify_column"),
    (None, "Not stratified", "stratify_none"),
)

# Labelled by the axis in _sync_enabled, since "per season" is wrong when the
# draw is stratified by era.
ALLOCATION = (
    ("equal", "Equal per group", "allocation_equal"),
    ("proportional", "Proportional to group size", "allocation_proportional"),
)

PREVIEW_COLUMNS = ("Season", "Episode", "Title", "Air date", "File")
STRATA_COLUMNS = ("Stratum", "Available", "Allocated", "Selected", "Census")


class SamplerDialog(QDialog):
    """Draw a documented episode sample from a show folder."""

    def __init__(self, window, parent=None) -> None:
        super().__init__(parent or window)
        self.setModal(True)
        self.resize(DIALOG_W, DIALOG_H)
        self._window = window
        self._episodes: list = []
        self._result: SampleResult | None = None
        # Set by _write once a draw is on disk; read by MainWindow to make the
        # new sample the current scope. None means nothing was written.
        self.written_dir: Path | None = None
        self._folder: Path | None = None
        self._registry: Path | None = None
        self._eras_from_registry = False
        self._eras: list[dict] = []
        self._era_counts: dict[str, int] = {}

        body = ModalDialogFrame.install(self, "Episode Sampler",
                                        buttons=("min", "max", "close"))
        body.addWidget(self._source_box())
        body.addWidget(self._design_box())

        split = QHBoxLayout()
        split.setSpacing(8)
        split.addWidget(self._preview_box(), 3)
        split.addWidget(self._strata_box(), 2)
        body.addLayout(split, 1)

        self._notes = QLabel("Pick a show folder to begin.")
        self._notes.setWordWrap(True)
        self._notes.setProperty("role", "dim")
        body.addWidget(self._notes)

        row = ModalDialogFrame.add_action_bar(self)
        self._design_line = QLabel("")
        self._design_line.setProperty("role", "dim")
        row.addWidget(self._design_line, 1)
        self._btn_preview = QPushButton("Preview")
        self._btn_preview.setToolTip(TOOLTIPS["preview"])
        self._btn_preview.clicked.connect(self._preview)
        row.addWidget(self._btn_preview)
        self._btn_queue = QPushButton("Send to Analysis Queue")
        self._btn_queue.setToolTip(
            "Queue the selected episodes for the automated pass. The draw is "
            "not written to disk by this — use Draw & Save Sample for that.")
        self._btn_queue.setEnabled(False)
        self._btn_queue.clicked.connect(self._send_to_queue)
        row.addWidget(self._btn_queue)
        self._btn_write = QPushButton("Draw && Save Sample")
        self._btn_write.setProperty("primary", "true")
        self._btn_write.setEnabled(False)
        self._btn_write.clicked.connect(self._write)
        row.addWidget(self._btn_write)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        row.addWidget(close)

        self._sync_enabled()

    # -- source ------------------------------------------------------------
    def _source_box(self) -> QWidget:
        box = QGroupBox("1 · Which show")
        grid = QGridLayout(box)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(4)

        self._folder_label = QLabel("no folder chosen")
        self._folder_label.setProperty("role", "dim")
        browse = QPushButton("Choose Show Folder…")
        browse.setToolTip(TOOLTIPS["entry_root"])
        browse.clicked.connect(self._choose_folder)
        grid.addWidget(browse, 0, 0)
        registry = QPushButton("Load Registry CSV…")
        registry.setToolTip(TOOLTIPS["load_registry"])
        registry.clicked.connect(self._choose_registry)
        grid.addWidget(registry, 0, 1)
        grid.addWidget(self._folder_label, 0, 2, 1, 2)

        grid.addWidget(QLabel("Name this sample:"), 1, 0)
        self._name = QLineEdit()
        self._name.setPlaceholderText(
            "shown in the Trials tab and in the pipeline, e.g. "
            "“Little Bear S1, spread, n=2”")
        grid.addWidget(self._name, 1, 1, 1, 3)
        grid.setColumnStretch(1, 1)
        return box

    def _choose_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Choose the show's top folder",
            str(self._window._root or ""))
        if not chosen:
            return
        self._folder = Path(chosen)
        self._registry = None
        try:
            self._episodes = scan_entry_root(self._folder)
        except Exception as exc:               # noqa: BLE001 — shown, not hidden
            QMessageBox.warning(self, "Could not read that folder", str(exc))
            self._episodes = []
        seasons = {e.season for e in self._episodes if e.season is not None}
        self._folder_label.setText(
            f"{self._folder.name} — {len(self._episodes)} episode"
            f"{'s' if len(self._episodes) != 1 else ''}"
            f" across {len(seasons)} season{'s' if len(seasons) != 1 else ''}"
            if self._episodes else
            f"{self._folder.name} — no video files found")
        if not self._name.text().strip():
            self._name.setText(self._folder.name)
        self._apply_eras()
        self._refresh_stratify()
        self._sync_enabled()

    def _choose_registry(self) -> None:
        """Load a prepared episode list instead of scanning folders.

        A registry can carry columns a folder scan cannot know — air dates,
        titles, and any grouping column the study uses. Those extra columns
        become stratification options, which is the documented behaviour that
        `Episode.extra` never actually delivered until now.
        """
        chosen, _f = QFileDialog.getOpenFileName(
            self, "Load registry CSV", str(self._window._root or ""),
            "CSV (*.csv)")
        if not chosen:
            return
        try:
            self._episodes = load_registry_csv(Path(chosen))
        except Exception as exc:               # noqa: BLE001 — shown, not hidden
            QMessageBox.warning(self, "Could not read that CSV", str(exc))
            return
        self._folder = None
        self._registry = Path(chosen)
        dated = sum(1 for e in self._episodes if e.air_date)
        columns = stratification_columns(self._episodes)
        self._folder_label.setText(
            f"{self._registry.name} — {len(self._episodes)} episode"
            f"{'s' if len(self._episodes) != 1 else ''}, {dated} with an air "
            f"date"
            + (f"; grouping columns: {', '.join(columns)}" if columns else
               "; no extra grouping columns"))
        if not self._name.text().strip():
            self._name.setText(self._registry.stem)
        self._apply_eras()
        self._refresh_stratify()
        self._sync_enabled()

    def _refresh_stratify(self) -> None:
        """Rebuild the group-by list: the fixed axes plus real CSV columns.

        Only columns that actually carry a value are offered. Offering a key
        that resolves to "(none)" for every episode is exactly the failure
        this line of work started from.
        """
        current = self._stratify.currentData()
        self._stratify.blockSignals(True)
        self._stratify.clear()
        for value, label, tip in STRATIFY:
            self._stratify.addItem(label, value)
            self._stratify.setItemData(self._stratify.count() - 1,
                                       TOOLTIPS[tip], Qt.ToolTipRole)
        for column in stratification_columns(self._episodes):
            if column == ERA_KEY:
                continue                       # already offered above
            self._stratify.addItem(f"By {column} (from the registry)", column)
            self._stratify.setItemData(
                self._stratify.count() - 1,
                f"Group by the “{column}” column in the loaded registry CSV.",
                Qt.ToolTipRole)
        values = [self._stratify.itemData(i)
                  for i in range(self._stratify.count())]
        if current in values:
            self._stratify.setCurrentIndex(values.index(current))
        self._stratify.blockSignals(False)

    # -- eras --------------------------------------------------------------
    def _show_key(self) -> str:
        """The show's index key, which is what eras are stored against."""
        root = self._window._root
        if root and self._folder:
            try:
                return show_key(root, self._folder)
            except ValueError:
                pass
        return self._folder.name if self._folder else ""

    def _apply_eras(self) -> None:
        """Fill air dates from the index and tag each episode with its era.

        Without this `stratify_by="era"` would put every episode in the same
        `(none)` stratum — a folder scan cannot know an air date, and nothing
        else populates `Episode.extra`. This is the missing link between the
        era definitions in the index and the sampler that has always accepted
        an arbitrary stratification column.
        """
        self._eras = []
        self._era_counts = {}
        self._eras_from_registry = has_declared_eras(self._episodes)
        if not self._episodes:
            return
        if self._eras_from_registry:
            # The registry named each episode's era. That is data the
            # researcher typed; a range derived from air dates must not
            # overwrite it.
            self._era_counts = assign_eras(self._episodes, [], overwrite=False)
            return
        conn = self._window._db()
        if conn is not None:
            try:
                from analyzer.db import get_show_eras
                self._eras = get_show_eras(conn, self._show_key())
            except Exception:
                self._eras = []
            attach_air_dates(self._episodes, conn)
        self._era_counts = assign_eras(self._episodes, self._eras)

    def _edit_eras(self) -> None:
        conn = self._window._db()
        if conn is None:
            QMessageBox.information(
                self, "Eras",
                "The index could not be opened — choose a root folder first.")
            return
        if not self._episodes:
            QMessageBox.information(self, "Eras",
                                    "Choose a show folder first.")
            return
        from ui.eras import ErasDialog
        dialog = ErasDialog(self._show_key(), self._episodes, self._eras,
                            conn, self)
        dialog.exec()
        self._apply_eras()
        self._sync_enabled()

    # -- design ------------------------------------------------------------
    def _design_box(self) -> QWidget:
        box = QGroupBox("2 · The sampling design")
        grid = QGridLayout(box)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(4)

        grid.addWidget(QLabel("Group by:"), 0, 0)
        self._stratify = QComboBox()
        for value, label, tip in STRATIFY:
            self._stratify.addItem(label, value)
            self._stratify.setItemData(self._stratify.count() - 1,
                                       TOOLTIPS[tip], Qt.ToolTipRole)
        grid.addWidget(self._stratify, 0, 1)
        self._btn_eras = QPushButton("Define Eras…")
        self._btn_eras.setToolTip(
            "Name the date ranges this show's run divides into. Episodes are "
            "placed by air date, which comes from the index.")
        self._btn_eras.clicked.connect(self._edit_eras)
        self._btn_eras.setVisible(False)
        grid.addWidget(self._btn_eras, 0, 6)

        grid.addWidget(QLabel("Method:"), 0, 2)
        self._method = QComboBox()
        for value, label, tip in METHODS:
            self._method.addItem(label, value)
            self._method.setItemData(self._method.count() - 1,
                                     TOOLTIPS[tip], Qt.ToolTipRole)
        grid.addWidget(self._method, 0, 3)

        grid.addWidget(QLabel("Allocation:"), 0, 4)
        self._allocation = QComboBox()
        for value, label, tip in ALLOCATION:
            self._allocation.addItem(label, value)
            self._allocation.setItemData(self._allocation.count() - 1,
                                         TOOLTIPS[tip], Qt.ToolTipRole)
        grid.addWidget(self._allocation, 0, 5)

        self._per_n_label = QLabel("Per season:")
        grid.addWidget(self._per_n_label, 1, 0)
        self._per_n = QSpinBox()
        self._per_n.setRange(1, 500)
        self._per_n.setValue(2)
        self._per_n.setToolTip(TOOLTIPS["per_stratum_n"])
        grid.addWidget(self._per_n, 1, 1)

        grid.addWidget(QLabel("Total:"), 1, 2)
        self._total_n = QSpinBox()
        self._total_n.setRange(1, 5000)
        self._total_n.setValue(12)
        self._total_n.setToolTip(TOOLTIPS["total_n"])
        grid.addWidget(self._total_n, 1, 3)

        self._floor_label = QLabel("Floor per season:")
        grid.addWidget(self._floor_label, 1, 4)
        self._floor = QSpinBox()
        self._floor.setRange(0, 100)
        self._floor.setValue(1)
        self._floor.setToolTip(TOOLTIPS["floor"])
        grid.addWidget(self._floor, 1, 5)

        grid.addWidget(QLabel("Timeline order:"), 2, 0)
        self._sort = QComboBox()
        self._sort.addItem("Episode number", "episode")
        self._sort.addItem("Air date", "air_date")
        self._sort.setToolTip(TOOLTIPS["sort_col"])
        grid.addWidget(self._sort, 2, 1)

        grid.addWidget(QLabel("Random seed:"), 2, 2)
        self._seed = QSpinBox()
        self._seed.setRange(0, 2_147_483_647)
        self._seed.setValue(42)
        self._seed.setToolTip(TOOLTIPS["seed"])
        grid.addWidget(self._seed, 2, 3)

        grid.addWidget(QLabel("Every Nth:"), 2, 4)
        self._interval = QLineEdit()
        self._interval.setPlaceholderText("auto")
        self._interval.setToolTip(TOOLTIPS["interval_k"])
        grid.addWidget(self._interval, 2, 5)

        self._manual_label = QLabel("Episodes to include:")
        grid.addWidget(self._manual_label, 3, 0)
        self._manual = QPlainTextEdit()
        self._manual.setPlaceholderText(TOOLTIPS["manual_list"])
        self._manual.setToolTip(TOOLTIPS["manual_list"])
        self._manual.setMaximumHeight(56)
        grid.addWidget(self._manual, 3, 1, 1, 5)

        self._gather = QCheckBox("Collect the chosen files into the sample "
                                 "folder")
        self._gather.setToolTip(TOOLTIPS["gather_files"])
        self._copy = QCheckBox("Copy rather than link")
        self._copy.setEnabled(False)
        self._gather.toggled.connect(self._copy.setEnabled)
        grid.addWidget(self._gather, 4, 0, 1, 3)
        grid.addWidget(self._copy, 4, 3, 1, 3)

        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        grid.setColumnStretch(5, 1)

        for widget in (self._stratify, self._method, self._allocation):
            widget.currentIndexChanged.connect(self._sync_enabled)
        for widget in (self._per_n, self._total_n, self._floor, self._seed):
            widget.valueChanged.connect(self._describe)
        self._sort.currentIndexChanged.connect(self._sync_enabled)
        return box

    def _sync_enabled(self) -> None:
        """Show only the fields the chosen design actually uses.

        A field that does nothing for the current method is disabled rather
        than hidden, so the shape of the form does not jump — and disabled
        rather than left live, because a seed that is ignored still looks
        like it was honoured.
        """
        method = self._method.currentData()
        stratified = self._stratify.currentData() is not None
        proportional = self._allocation.currentData() == "proportional"

        self._allocation.setEnabled(stratified)
        self._per_n.setEnabled(method not in ("census", "manual")
                               and not (stratified and proportional))
        self._total_n.setEnabled(method not in ("census", "manual")
                                 and stratified and proportional)
        self._floor.setEnabled(stratified and proportional
                               and method not in ("census", "manual"))
        self._interval.setEnabled(method == "systematic")
        self._seed.setEnabled(method in ("srs", "systematic", "spread"))
        self._manual.setEnabled(method == "manual")
        self._manual_label.setEnabled(method == "manual")
        # The engine tooltip describes a registry, where titles exist. A
        # folder scan has no titles, so show what THIS frame can match —
        # taken from the loaded episodes rather than invented.
        if method == "manual" and self._episodes:
            examples = [e.label() for e in self._episodes[:2]]
            numbers = [str(e.episode) for e in self._episodes[:2]
                       if e.episode is not None]
            self._manual.setPlaceholderText(
                "One per line. This frame matches: "
                + ", ".join(examples)
                + (f" — or just {', '.join(numbers)}" if numbers else "")
                + ("" if any(e.title for e in self._episodes)
                   else ".  These episodes have no titles (a folder scan "
                        "cannot know them), so a title will not match."))
        self._btn_preview.setEnabled(bool(self._episodes))
        by_era = self._stratify.currentData() == "era"
        self._per_n_label.setText("Per era:" if by_era else "Per season:")
        self._floor_label.setText(
            "Floor per era:" if by_era else "Floor per season:")
        # Defining ranges is meaningless when the registry already declares
        # an era per episode — the ranges would be ignored.
        self._btn_eras.setVisible(by_era and not self._eras_from_registry)
        self._btn_eras.setEnabled(bool(self._episodes))
        # Sampling by era with no eras defined would draw one stratum called
        # "(no era)", which is not stratifying at all. Say so before the draw.
        if self._sort.currentData() == "air_date" and self._episodes:
            dated = sum(1 for e in self._episodes if e.air_date)
            if dated < len(self._episodes):
                self._notes.setText(
                    f"Timeline order is by air date, but only {dated} of "
                    f"{len(self._episodes)} episodes have one. The rest are "
                    f"ordered after them by episode number, which changes "
                    f"what a spread or systematic draw picks — the manifest "
                    f"records this. Import episode metadata for a true "
                    f"timeline.")
        if by_era and self._episodes:
            named = {k: v for k, v in self._era_counts.items()
                     if k != UNASSIGNED}
            if self._eras_from_registry:
                self._notes.setText(
                    "Eras come from the registry's own “era” column, not from "
                    "date ranges: "
                    + ", ".join(f"{k} ({v})" for k, v in sorted(named.items())))
            elif not named:
                self._notes.setText(
                    "No eras are defined for this show yet, so every episode "
                    "would fall into one “(no era)” group — the same as not "
                    "stratifying. Use Define Eras…, and import episode "
                    "metadata first if the air dates are missing.")
            else:
                self._notes.setText(coverage_note(self._era_counts))
        self._describe()

    def _describe(self) -> None:
        """The design as the one sentence a methods section needs."""
        method = self._method.currentData()
        parts = []
        stratify = self._stratify.currentData()
        parts.append("Stratified by season" if stratify == "season"
                     else "Stratified by era" if stratify == "era"
                     else f"Stratified by {stratify}" if stratify
                     else "Not stratified")
        parts.append(dict((m[0], m[1].split(" — ")[0].lower())
                          for m in METHODS)[method])
        if method not in ("census", "manual"):
            if self._total_n.isEnabled():
                parts.append(f"total n={self._total_n.value()}")
            else:
                parts.append(f"n={self._per_n.value()} per group")
        if self._seed.isEnabled():
            parts.append(f"seed={self._seed.value()}")
        if method == "manual":
            parts.append("NON-PROBABILITY — cannot support inference to the "
                         "whole show")
        self._design_line.setText(", ".join(parts) + ".")

    # -- output panels -----------------------------------------------------
    def _preview_box(self) -> QWidget:
        box = QGroupBox("3 · Episodes this design selects")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 8, 8, 8)
        self._preview_table = QTreeWidget()
        self._preview_table.setColumnCount(len(PREVIEW_COLUMNS))
        self._preview_table.setHeaderLabels(list(PREVIEW_COLUMNS))
        self._preview_table.setRootIsDecorated(False)
        self._preview_table.setUniformRowHeights(True)
        self._preview_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._preview_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._preview_table.setFrameShape(QFrame.NoFrame)
        lay.addWidget(self._preview_table)
        return box

    def _strata_box(self) -> QWidget:
        box = QGroupBox("What was drawn from where")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 8, 8, 8)
        self._strata_table = QTreeWidget()
        self._strata_table.setColumnCount(len(STRATA_COLUMNS))
        self._strata_table.setHeaderLabels(list(STRATA_COLUMNS))
        self._strata_table.setRootIsDecorated(False)
        self._strata_table.setUniformRowHeights(True)
        self._strata_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._strata_table.setFrameShape(QFrame.NoFrame)
        lay.addWidget(self._strata_table)
        return box

    # -- running -----------------------------------------------------------
    def _params(self) -> dict:
        method = self._method.currentData()
        interval = None
        if method == "systematic" and self._interval.text().strip():
            try:
                interval = int(self._interval.text().strip())
            except ValueError:
                interval = None
        manual = [line.strip()
                  for line in self._manual.toPlainText().splitlines()
                  if line.strip()] if method == "manual" else None
        return {
            "stratify_by": self._stratify.currentData(),
            "method": method,
            "allocation": self._allocation.currentData(),
            "per_stratum_n": self._per_n.value(),
            "total_n": self._total_n.value() if self._total_n.isEnabled()
            else None,
            "floor": self._floor.value(),
            "interval_k": interval,
            "sort_col": self._sort.currentData(),
            "seed": self._seed.value(),
            "manual_list": manual,
        }

    def _draw(self) -> SampleResult | None:
        if not self._episodes:
            QMessageBox.information(self, "Episode Sampler",
                                    "Choose a show folder first.")
            return None
        try:
            result = sample(self._episodes,
                            entry_id=(self._folder.name if self._folder
                                      else self._registry.stem
                                      if self._registry else "entry"),
                            **self._params())
        except Exception as exc:               # noqa: BLE001 — shown, not hidden
            QMessageBox.warning(self, "Sampling failed", str(exc))
            return None
        name = self._name.text().strip()
        if name:
            result.manifest.trial_name = name
        return result

    def _preview(self) -> None:
        result = self._draw()
        if result is None:
            return
        self._result = result
        self._fill(result)
        self._btn_write.setEnabled(True)
        self._btn_queue.setEnabled(bool(result.worklist))

    def _send_to_queue(self) -> None:
        """Hand the drawn episodes to the automated pass.

        A sample that only prints a list leaves the researcher to do the
        bookkeeping by hand — the reason sampling was made a first-class
        module in the first place (`DECISIONS.md`, 2026-06-30).
        """
        result = self._result or self._draw()
        if result is None:
            return
        paths = [p for p in result.worklist if p]
        if not paths:
            QMessageBox.information(
                self, "Nothing to queue",
                "None of the selected episodes has a file path — the draw "
                "came from a registry CSV without one.")
            return
        added = self._window._automated.enqueue(paths)
        self._notes.setText(
            f"Queued {added} episode{'s' if added != 1 else ''} for the "
            f"automated pass"
            + (f" ({len(paths) - added} already queued)."
               if added != len(paths) else ".")
            + "  This did not write the sample — use Draw & Save Sample to "
              "record the draw itself.")

    def _fill(self, result: SampleResult) -> None:
        self._preview_table.clear()
        for ep in result.selected:
            self._preview_table.addTopLevelItem(QTreeWidgetItem([
                str(ep.season) if ep.season is not None else "",
                str(ep.episode) if ep.episode is not None else "",
                ep.title or "",
                ep.air_date or "",
                ep.filepath.name if ep.filepath else ""]))
        head = self._preview_table.header()
        for col in range(len(PREVIEW_COLUMNS) - 1):
            head.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        head.setSectionResizeMode(len(PREVIEW_COLUMNS) - 1,
                                  QHeaderView.Stretch)

        self._strata_table.clear()
        for stratum in result.manifest.strata:
            self._strata_table.addTopLevelItem(QTreeWidgetItem([
                stratum.stratum_key, str(stratum.available),
                str(stratum.allocated), str(stratum.selected),
                "yes" if stratum.census_flag else ""]))
        for col in range(len(STRATA_COLUMNS)):
            self._strata_table.header().setSectionResizeMode(
                col, QHeaderView.ResizeToContents)

        manifest = result.manifest
        lines = [
            f"{manifest.total_selected} of {manifest.total_available} "
            f"episodes selected.",
        ]
        # The distinction the whole screen exists to preserve.
        lines.append(
            "Probability sample — supports inference to the show, given the "
            "frame above." if manifest.probability else
            "NON-PROBABILITY sample. Describe the selection rule explicitly "
            "when reporting; it does not support inference to the whole show.")
        lines += manifest.notes
        self._notes.setText("  ".join(lines))

    def _write(self) -> None:
        result = self._result or self._draw()
        if result is None:
            return
        base = (self._folder.parent if self._folder
                else self._registry.parent if self._registry
                else Path(self._window._root or Path.home()))
        outdir = self._outdir(base, result.manifest.method,
                              result.manifest.entry_id)
        try:
            paths = write_outputs(result, outdir,
                                  gather=self._gather.isChecked(),
                                  copy_files=self._copy.isChecked())
        except Exception as exc:               # noqa: BLE001 — shown, not hidden
            QMessageBox.warning(self, "Could not write the sample", str(exc))
            return
        self._notes.setText(
            f"Wrote {result.manifest.total_selected} episodes to "
            f"{outdir}. It appears in the Trials tab, and a pipeline can be "
            f"linked to it from Pipeline → Manage → Link to Episode Sample.")
        self._window.statusBar().showMessage(
            f"Sample written to {paths['csv'].parent}", 10000)
        # The folder the draw landed in, for the caller. MainWindow makes the
        # new draw the current scope, which it cannot do from the dialog's
        # result code alone.
        self.written_dir = outdir
        self.accept()

    @staticmethod
    def _outdir(base: Path, method: str, entry_id: str) -> Path:
        """A dated, descriptive folder, never overwriting an existing draw.

        Same naming as the Tk sampler, so the two builds' samples sit side by
        side and `build_pipelines` finds both.
        """
        safe = re.sub(r"[^\w\-]", "_", entry_id).strip("_") or "sample"
        stem = f"{safe}_{method}_" \
               f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        outdir = base / stem
        counter = 2
        while outdir.exists():
            outdir = base / f"{stem}_{counter}"
            counter += 1
        return outdir
