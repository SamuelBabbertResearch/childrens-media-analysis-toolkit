"""ui/clip_finder.py — the Clip Finder, the Selection stage at window scale.

WHAT THIS SCREEN IS FOR

Selection is the stage that decides which material a study is about. The
Episode Sampler works at episode scale; this works one level down, on the
contiguous windows *inside* those episodes, because a stimulus study rarely
wants a whole episode — it wants thirty seconds with particular properties.

WHERE THE NUMBERS COME FROM

`analyzer.study_clips.run_candidate_pool` measures every window of every
episode once, under one pinned configuration, and writes the pool to disk.
This screen runs that pass on a worker thread and then reads the result
through `analyzer.clip_query`. It computes no metric of its own: a number on
this screen is a number the engine produced, and the panel beside the results
says which configuration produced it.

WHAT IT WILL NOT DO

Rank windows by suitability, quality, or fit for an age group. A query filters
and orders; every ordering here is on a measured quantity the researcher named.
`low`, `middle` and `high` are thirds of the measured pool — a property of this
pool, not of a clip — and the wording for that is read from the run's own
manifest rather than restated here.
"""

from __future__ import annotations

import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PySide6.QtCore import QUrl, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QProgressBar, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QDialog,
)

from analyzer.clip_query import (
    COLUMNS, LEVELS, CandidatePool, ClipQuery, PoolError, Range,
    export_manifest, label_for_export, load_pool, sort_rows,
)
from analyzer.study_clips import (
    FEATURE_LABEL, FEATURE_VALUE, FEATURES, export_selected_clips,
    run_candidate_pool,
)
from ui.modal import ModalDialogFrame
from ui.pair_cut_marker import build_pair_cut_marker
from ui.player import VideoPlayer, available as video_available

DIALOG_W = 1180
DIALOG_H = 800

# Label and step for each measured feature's filter. The step matters: motion
# and audio live in the third decimal, and a spin box stepping by 1 makes them
# unfilterable without anyone noticing why.
FEATURE_UI: dict[str, tuple[str, str, int, float]] = {
    # feature: (label, unit shown after the value, decimals, single step)
    "cuts":   ("Cuts per minute", "cuts/min", 2, 1.0),
    "motion": ("Motion mean", "", 4, 0.005),
    "audio":  ("Audio RMS mean", "", 4, 0.005),
}

LEVEL_CHOICES = (("", "Any"),) + tuple((lv, lv.capitalize()) for lv in LEVELS)

# A spin box cannot be empty, so its minimum doubles as "no bound" and says so.
NO_BOUND = -1.0


class _Cancelled(BaseException):
    """Raised out of the status callback to stop a run.

    Derives from `BaseException`, not `Exception`, and this is not a style
    choice — `run_candidate_pool` wraps each episode in `except Exception` and
    CACHES the result, so a cancel raised as an ordinary exception is caught,
    written to the episode cache as a permanent failure, and then believed by
    every later resumed run. Stopping a measurement would quietly poison the
    pool. `ARCHITECTURE.md` §7 records the same rule for the analysis worker,
    which was bitten by it first.
    """


class PoolWorker(QThread):
    """Runs the candidate measurement pass off the interface thread."""

    progress = Signal(str)
    finished_ok = Signal(str, float)     # output dir, elapsed seconds
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, source: Path, output: Path, params: dict) -> None:
        super().__init__()
        self._source = source
        self._output = output
        self._params = dict(params)
        self._stop = False

    def cancel(self) -> None:
        self._stop = True

    def _tick(self, message: str) -> None:
        # The pass caches each episode as it finishes, so stopping here loses
        # at most the episode in flight and a resumed run picks up the rest.
        if self._stop:
            raise _Cancelled
        self.progress.emit(message)

    def run(self) -> None:
        started = time.monotonic()
        try:
            run_candidate_pool(self._source, self._output,
                               status_cb=self._tick, **self._params)
        except _Cancelled:      # must be listed before the Exception clause
            self.cancelled.emit()
            return
        except Exception as exc:            # noqa: BLE001 - reported, not hidden
            self.failed.emit(str(exc))
            return
        self.finished_ok.emit(str(self._output), time.monotonic() - started)


class ExportWorker(QThread):
    """Renders the chosen windows as standalone files, and re-measures them."""

    progress = Signal(str)
    finished_ok = Signal(list)
    failed = Signal(str)

    def __init__(self, rows: list[dict], output: Path) -> None:
        super().__init__()
        self._rows = rows
        self._output = output

    def run(self) -> None:
        try:
            results = export_selected_clips(
                self._rows, self._output, status_cb=self.progress.emit)
        except Exception as exc:            # noqa: BLE001 - reported, not hidden
            self.failed.emit(str(exc))
            return
        self.finished_ok.emit(results)


class FeatureMapDialog(QDialog):
    """Researcher-only heat-map view of selected candidate windows.

    This is deliberately part of the Clip Finder rather than Study Runner:
    pair identities and feature values must not be shown to participants. Its
    cut column comes from the candidate measurement pass, so the instruction
    explains that hand-coded cuts replace it for a final stimulus set.
    """

    _COLUMNS = (
        ("cuts_per_min", "Candidate cuts/min"),
        ("motion_mean", "Visual motion"),
        ("audio_rms_mean", "Audio intensity\n(linear RMS)"),
    )

    def __init__(self, rows: list[dict[str, Any]], parent=None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Candidate Feature Map")
        self.resize(820, min(720, 180 + 42 * max(1, len(rows))))
        layout = QVBoxLayout(self)
        self._note = QLabel(
            "Darker means more of that one measured characteristic among the "
            "windows shown; it is not a score, verdict, or suitability rating. "
            "Candidate cuts are automated screening values. Use hand-coded cuts "
            "in a final participant-stimulus map.")
        self._note.setWordWrap(True)
        self._note.setProperty("role", "dim")
        layout.addWidget(self._note)

        self._table = QTableWidget(len(rows), len(self._COLUMNS))
        self._table.setHorizontalHeaderLabels([label for _, label in self._COLUMNS])
        self._table.setVerticalHeaderLabels([self._row_label(row) for row in rows])
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.NoSelection)
        self._table.verticalHeader().setDefaultSectionSize(34)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._fill(rows)
        layout.addWidget(self._table, 1)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close, alignment=Qt.AlignRight)

    @staticmethod
    def _row_label(row: dict[str, Any]) -> str:
        episode = Path(str(row.get("source_relpath") or "clip")).stem
        start = str(row.get("start_timecode") or "")
        return f"{episode[:42]} · {start}".strip(" ·")

    @staticmethod
    def _blue(value: float | None, low: float, high: float) -> QColor:
        if value is None:
            return QColor("#ECECEC")
        fraction = 0.5 if high == low else (value - low) / (high - low)
        # One hue, light to dark: quantity only, never approval or a verdict.
        return QColor.fromHsvF(0.58, 0.56, 0.98 - 0.36 * fraction)

    def _fill(self, rows: list[dict[str, Any]]) -> None:
        for column, (key, _label) in enumerate(self._COLUMNS):
            values = [row.get(key) for row in rows
                      if isinstance(row.get(key), (int, float))]
            low, high = (min(values), max(values)) if values else (0.0, 0.0)
            for index, row in enumerate(rows):
                value = row.get(key)
                item = QTableWidgetItem("—" if value is None else f"{value:.4g}")
                item.setTextAlignment(Qt.AlignCenter)
                item.setBackground(self._blue(value, low, high))
                self._table.setItem(index, column, item)


HAND_CODED_CUTS_FILE = "hand_coded_pair_cuts.csv"
HAND_CODED_CUTS_FIELDS = (
    "pair_id", "target_feature", "study_label", "target_level", "clip_id",
    "source_relpath", "source_path", "start_sec", "end_sec", "duration_sec",
    "hard_cut_count", "hand_coded_cuts_per_min", "coded_at_utc",
)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def save_hand_coded_pair(run_dir: Path, rows: list[dict[str, Any]],
                         counts: dict[str, int]) -> Path:
    """Persist the latest manual hard-cut count for both clips in a pair.

    Automated measurements remain untouched. Existing coding for other clips
    is preserved, while saving the same clip again deliberately replaces its
    earlier value so the file always represents the current verified set.
    """
    destination = run_dir / HAND_CODED_CUTS_FILE
    retained = [row for row in _read_csv_rows(destination)
                if row.get("clip_id") not in counts]
    coded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for row in rows:
        clip_id = str(row.get("clip_id") or "")
        if clip_id not in counts:
            continue
        duration = float(row.get("duration_sec") or
                         (float(row["end_sec"]) - float(row["start_sec"])))
        count = int(counts[clip_id])
        retained.append({
            "pair_id": row.get("pair_id", ""),
            "target_feature": row.get("target_feature", ""),
            "study_label": row.get("study_label", ""),
            "target_level": row.get("target_level", ""),
            "clip_id": clip_id,
            "source_relpath": row.get("source_relpath", ""),
            "source_path": row.get("source_path", ""),
            "start_sec": row.get("start_sec", ""),
            "end_sec": row.get("end_sec", ""),
            "duration_sec": duration,
            "hard_cut_count": count,
            "hand_coded_cuts_per_min": round(count * 60.0 / duration, 6),
            "coded_at_utc": coded_at,
        })
    temporary = destination.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HAND_CODED_CUTS_FIELDS,
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(retained)
    temporary.replace(destination)
    return destination


class PairCutCodingDialog(QDialog):
    """Play matched candidate windows and verify their hard-cut counts."""

    def __init__(self, run_dir: Path, parent=None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Hand-code Matched Pair Cuts")
        self.resize(1050, 760)
        self._run_dir = Path(run_dir)
        selected = _read_csv_rows(self._run_dir / "selected_clips.csv")
        self._pairs: dict[str, list[dict[str, Any]]] = {}
        for row in selected:
            pair_id = row.get("pair_id", "")
            if pair_id:
                self._pairs.setdefault(pair_id, []).append(row)
        self._current_rows: list[dict[str, Any]] = []
        self._count_spins: dict[str, QSpinBox] = {}
        self._reviewed: dict[str, QCheckBox] = {}
        self._active_start: float | None = None
        self._active_end: float | None = None

        layout = QVBoxLayout(self)
        note = QLabel(
            "Count only abrupt shot changes (hard cuts). Do not count the start "
            "of the clip, fades, or dissolves. Automated cuts/min is shown only "
            "as a reference; your saved number is calculated from your count.")
        note.setWordWrap(True)
        note.setProperty("role", "dim")
        layout.addWidget(note)

        choose = QHBoxLayout()
        choose.addWidget(QLabel("Matched pair"))
        self._pair = QComboBox()
        for pair_id in sorted(self._pairs):
            self._pair.addItem(pair_id, pair_id)
        preferred = self._pair.findData("AUDIO_1")
        if preferred >= 0:
            self._pair.setCurrentIndex(preferred)
        self._pair.currentIndexChanged.connect(self._load_pair)
        choose.addWidget(self._pair)
        choose.addStretch(1)
        layout.addLayout(choose)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels([
            "Level", "Episode and window", "Automated cuts/min",
            "Hard-cut count", "Hand-coded cuts/min", "Reviewed",
        ])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.setMaximumHeight(150)
        layout.addWidget(self._table)

        load_row = QHBoxLayout()
        self._btn_load_clip = QPushButton("Load Selected Clip")
        self._btn_load_clip.clicked.connect(self._load_selected_clip)
        load_row.addWidget(self._btn_load_clip)
        self._clip_status = QLabel("Select a row, then load its 30-second window.")
        self._clip_status.setProperty("role", "dim")
        load_row.addWidget(self._clip_status, 1)
        layout.addLayout(load_row)

        self._player = VideoPlayer()
        self._player.position_changed.connect(self._keep_inside_window)
        layout.addWidget(self._player, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self._btn_save = QPushButton("Save Verified Pair")
        self._btn_save.setProperty("primary", "true")
        self._btn_save.clicked.connect(self._save)
        actions.addWidget(self._btn_save)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        actions.addWidget(close)
        layout.addLayout(actions)

        self._load_pair()

    @staticmethod
    def _number(row: dict[str, Any], key: str) -> float:
        return float(row.get(key) or 0.0)

    def _load_pair(self) -> None:
        pair_id = str(self._pair.currentData() or "")
        self._current_rows = sorted(
            self._pairs.get(pair_id, []),
            key=lambda row: str(row.get("target_level", "")), reverse=True)
        prior = {row.get("clip_id", ""): row
                 for row in _read_csv_rows(self._run_dir / HAND_CODED_CUTS_FILE)}
        self._count_spins.clear()
        self._reviewed.clear()
        self._table.setRowCount(len(self._current_rows))
        for index, row in enumerate(self._current_rows):
            clip_id = str(row.get("clip_id") or "")
            level = str(row.get("target_level") or "").title()
            description = (f"{row.get('source_relpath', '')}  ·  "
                           f"{row.get('start_timecode', '')}–{row.get('end_timecode', '')}")
            self._table.setItem(index, 0, QTableWidgetItem(level))
            self._table.setItem(index, 1, QTableWidgetItem(description))
            self._table.setItem(index, 2, QTableWidgetItem(
                f"{self._number(row, 'cuts_per_min'):.1f}"))

            spin = QSpinBox()
            spin.setRange(0, 300)
            spin.setAlignment(Qt.AlignCenter)
            previous = prior.get(clip_id)
            if previous:
                spin.setValue(int(float(previous.get("hard_cut_count") or 0)))
            spin.valueChanged.connect(
                lambda value, r=index: self._update_rate(r, value))
            self._table.setCellWidget(index, 3, spin)
            self._count_spins[clip_id] = spin

            rate = QLabel()
            rate.setAlignment(Qt.AlignCenter)
            self._table.setCellWidget(index, 4, rate)
            self._update_rate(index, spin.value())

            reviewed = QCheckBox("Done")
            reviewed.setChecked(bool(previous))
            reviewed.stateChanged.connect(self._sync_save)
            self._table.setCellWidget(index, 5, reviewed)
            self._reviewed[clip_id] = reviewed
        if self._current_rows:
            self._table.selectRow(0)
        self._sync_save()

    def _update_rate(self, table_row: int, count: int) -> None:
        if table_row >= len(self._current_rows):
            return
        duration = self._number(self._current_rows[table_row], "duration_sec") or 30.0
        label = self._table.cellWidget(table_row, 4)
        if isinstance(label, QLabel):
            label.setText(f"{count * 60.0 / duration:.1f}")

    def _selected_row(self) -> dict[str, Any] | None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None
        index = indexes[0].row()
        return self._current_rows[index] if index < len(self._current_rows) else None

    def _load_selected_clip(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        source = Path(str(row.get("source_path") or ""))
        if not source.is_file():
            QMessageBox.warning(self, "Episode not found",
                                f"The source episode is not available:\n{source}")
            return
        self._active_start = self._number(row, "start_sec")
        self._active_end = self._number(row, "end_sec")
        self._player.open(source)
        QTimer.singleShot(450, lambda: self._player.seek(self._active_start or 0.0))
        self._clip_status.setText(
            f"Loaded {row.get('study_label', '')} · "
            f"{row.get('start_timecode', '')}–{row.get('end_timecode', '')}. "
            "Playback returns to the start at the end of the window.")

    def _keep_inside_window(self, position: float) -> None:
        if self._active_start is None or self._active_end is None:
            return
        if position >= self._active_end:
            if self._player.is_playing():
                self._player.toggle()
            self._player.seek(self._active_start)

    def _sync_save(self) -> None:
        complete_pair = len(self._current_rows) == 2
        reviewed = complete_pair and all(box.isChecked()
                                         for box in self._reviewed.values())
        self._btn_save.setEnabled(reviewed)

    def _save(self) -> None:
        counts = {clip_id: spin.value()
                  for clip_id, spin in self._count_spins.items()}
        try:
            destination = save_hand_coded_pair(
                self._run_dir, self._current_rows, counts)
        except (OSError, ValueError, KeyError) as exc:
            QMessageBox.critical(self, "Could not save hand coding", str(exc))
            return
        QMessageBox.information(
            self, "Pair saved",
            f"Saved the verified hard-cut counts and calculated cuts/min to:\n"
            f"{destination}")
        self.accept()

    def done(self, result: int) -> None:
        self._player.close()
        super().done(result)


class ClipFinderDialog(QDialog):
    """Measure a folder into a window pool, then find windows in it."""

    def __init__(self, parent=None, source_dir: Path | None = None,
                 run_dir: Path | None = None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.resize(DIALOG_W, DIALOG_H)
        self._pool: CandidatePool | None = None
        self._shown: list[dict[str, Any]] = []
        self._sort_column = "start_sec"
        self._sort_descending = False
        self._worker: PoolWorker | None = None
        self._exporter: ExportWorker | None = None
        # Set once clips are written; read by the caller to record the result
        # on the Selection node. None means nothing was exported.
        self.exported_dir: Path | None = None

        body = ModalDialogFrame.install(self, "Clip Finder",
                                        buttons=("min", "max", "close"))
        body.addWidget(self._source_box())
        body.addWidget(self._filter_box())
        split = QHBoxLayout()
        split.setSpacing(8)
        split.addWidget(self._results_box(), 3)
        split.addWidget(self._provenance_box(), 1)
        body.addLayout(split, 1)

        row = ModalDialogFrame.add_action_bar(self)
        self._query_line = QLabel("No pool loaded.")
        self._query_line.setProperty("role", "dim")
        self._query_line.setWordWrap(True)
        row.addWidget(self._query_line, 1)
        self._btn_export = QPushButton("Export Selected Clips…")
        self._btn_export.setProperty("primary", "true")
        self._btn_export.setEnabled(False)
        self._btn_export.clicked.connect(self._export)
        row.addWidget(self._btn_export)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        row.addWidget(close)

        if source_dir:
            self._source.setText(str(source_dir))
            self._suggest_run_dir()
        if run_dir and (Path(run_dir) / "candidates.csv").is_file():
            self._run_dir.setText(str(run_dir))
            self._open_existing()
        self._sync_enabled()

    @property
    def pool_dir(self) -> Path | None:
        """The run folder currently loaded, or None if nothing is loaded.

        Read by the caller so a Selection node can record which pool it was
        working in — a pool the node does not name is a pool the next session
        has to find again by hand.
        """
        return self._pool.run_dir if self._pool is not None else None

    # -- 1 · source and measurement -----------------------------------------

    def _source_box(self) -> QWidget:
        box = QGroupBox("1 · Measure a pool of windows")
        grid = QGridLayout(box)
        grid.setContentsMargins(10, 6, 10, 8)
        grid.setHorizontalSpacing(8)

        grid.addWidget(QLabel("Episodes"), 0, 0)
        self._source = QLineEdit()
        self._source.setPlaceholderText(
            "Folder of source episodes — every window of every file is measured")
        self._source.textChanged.connect(self._on_source_changed)
        grid.addWidget(self._source, 0, 1, 1, 4)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._choose_source)
        grid.addWidget(browse, 0, 5)

        grid.addWidget(QLabel("Run folder"), 1, 0)
        self._run_dir = QLineEdit()
        self._run_dir.setPlaceholderText(
            "Where the measured pool is written and read back from")
        grid.addWidget(self._run_dir, 1, 1, 1, 4)
        browse_out = QPushButton("Browse…")
        browse_out.clicked.connect(self._choose_run_dir)
        grid.addWidget(browse_out, 1, 5)

        grid.addWidget(QLabel("Window"), 2, 0)
        self._window_sec = QDoubleSpinBox()
        self._window_sec.setRange(1.0, 600.0)
        self._window_sec.setDecimals(1)
        self._window_sec.setValue(30.0)
        self._window_sec.setSuffix(" s")
        self._window_sec.setToolTip(
            "Length of each contiguous window. Windows do not overlap; the "
            "episode is divided from the first measured second onward.")
        grid.addWidget(self._window_sec, 2, 1)

        self._skip_first = QDoubleSpinBox()
        self._skip_first.setRange(0.0, 3600.0)
        self._skip_first.setDecimals(1)
        self._skip_first.setSuffix(" s")
        self._skip_first.setToolTip(
            "Seconds ignored at the start of every episode — titles and "
            "recaps are measurable but are not the programme.")
        grid.addWidget(QLabel("Skip start"), 2, 2)
        grid.addWidget(self._skip_first, 2, 3)

        self._skip_last = QDoubleSpinBox()
        self._skip_last.setRange(0.0, 3600.0)
        self._skip_last.setDecimals(1)
        self._skip_last.setSuffix(" s")
        self._skip_last.setToolTip("Seconds ignored at the end, for credits.")
        grid.addWidget(QLabel("Skip end"), 2, 4)
        grid.addWidget(self._skip_last, 2, 5)

        self._partial = QCheckBox("Keep the short final window of each episode")
        self._partial.setToolTip(
            "A trailing window shorter than the rest. Its per-minute figures "
            "are computed over its own length, so it is comparable, but it is "
            "not the same stimulus length as the others.")
        grid.addWidget(self._partial, 3, 1, 1, 3)
        self._recursive = QCheckBox("Include subfolders")
        self._recursive.setChecked(True)
        grid.addWidget(self._recursive, 3, 4, 1, 2)

        self._btn_measure = QPushButton("Measure Windows")
        self._btn_measure.clicked.connect(self._measure)
        grid.addWidget(self._btn_measure, 4, 1)
        self._btn_open = QPushButton("Open Existing Pool")
        self._btn_open.setToolTip(
            "Read a run folder that has already been measured, without "
            "measuring anything again.")
        self._btn_open.clicked.connect(self._open_existing)
        grid.addWidget(self._btn_open, 4, 2)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        grid.addWidget(self._progress, 4, 3)
        self._status = QLabel("Choose a folder of episodes to begin.")
        self._status.setProperty("role", "dim")
        grid.addWidget(self._status, 4, 4, 1, 2)
        return box

    def _choose_source(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Choose the folder of source episodes",
            self._source.text() or str(Path.home()))
        if chosen:
            self._source.setText(chosen)
            self._suggest_run_dir()

    def _choose_run_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Choose the run folder",
            self._run_dir.text() or self._source.text() or str(Path.home()))
        if chosen:
            self._run_dir.setText(chosen)

    def _on_source_changed(self) -> None:
        self._sync_enabled()

    def _suggest_run_dir(self) -> None:
        """Default the run folder beside the library's other clip runs."""
        source = Path(self._source.text().strip())
        if not source.name or self._run_dir.text().strip():
            return
        self._run_dir.setText(
            str(Path.cwd() / ".analysis" / "study_clips" / source.name))

    # -- 2 · filters ---------------------------------------------------------

    def _filter_box(self) -> QWidget:
        box = QGroupBox("2 · Find windows")
        grid = QGridLayout(box)
        grid.setContentsMargins(10, 6, 10, 8)
        grid.setHorizontalSpacing(8)
        grid.addWidget(QLabel("At least"), 0, 1)
        grid.addWidget(QLabel("At most"), 0, 2)
        grid.addWidget(QLabel("Level in this pool"), 0, 3)

        self._mins: dict[str, QDoubleSpinBox] = {}
        self._maxes: dict[str, QDoubleSpinBox] = {}
        self._levels: dict[str, QComboBox] = {}
        for row, feature in enumerate(FEATURES, start=1):
            label, unit, decimals, step = FEATURE_UI[feature]
            grid.addWidget(QLabel(label), row, 0)
            for column, store in ((1, self._mins), (2, self._maxes)):
                spin = QDoubleSpinBox()
                spin.setDecimals(decimals)
                spin.setSingleStep(step)
                spin.setRange(NO_BOUND, 1e6)
                spin.setValue(NO_BOUND)
                spin.setSpecialValueText("any")
                if unit:
                    spin.setSuffix(f" {unit}")
                spin.valueChanged.connect(self._refresh)
                grid.addWidget(spin, row, column)
                store[feature] = spin
            combo = QComboBox()
            for value, text in LEVEL_CHOICES:
                combo.addItem(text, value)
            combo.setToolTip(
                "Thirds of this measured pool — a property of the pool, not "
                "of the clip. Measure a different set of episodes and the "
                "same window can change level.")
            combo.currentIndexChanged.connect(self._refresh)
            self._levels[feature] = combo
            grid.addWidget(combo, row, 3)

        grid.addWidget(QLabel("Episode"), 4, 0)
        self._episode = QLineEdit()
        self._episode.setPlaceholderText("Part of a file name")
        self._episode.textChanged.connect(self._refresh)
        grid.addWidget(self._episode, 4, 1, 1, 2)
        self._whole_only = QCheckBox("Whole windows only")
        self._whole_only.setChecked(True)
        self._whole_only.stateChanged.connect(self._refresh)
        grid.addWidget(self._whole_only, 4, 3)
        self._audio_only = QCheckBox("Audio measured")
        self._audio_only.stateChanged.connect(self._refresh)
        grid.addWidget(self._audio_only, 4, 4)
        reset = QPushButton("Reset Filters")
        reset.clicked.connect(self._reset_filters)
        grid.addWidget(reset, 4, 5)
        return box

    def _reset_filters(self) -> None:
        for store in (self._mins, self._maxes):
            for spin in store.values():
                spin.blockSignals(True)
                spin.setValue(NO_BOUND)
                spin.blockSignals(False)
        for combo in self._levels.values():
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self._episode.blockSignals(True)
        self._episode.clear()
        self._episode.blockSignals(False)
        self._refresh()

    def query(self) -> ClipQuery:
        """The filter as the engine's own query object."""
        ranges: dict[str, Range] = {}
        levels: dict[str, frozenset[str]] = {}
        for feature in FEATURES:
            low = self._mins[feature].value()
            high = self._maxes[feature].value()
            low = None if low <= NO_BOUND else low
            high = None if high <= NO_BOUND else high
            if low is not None and high is not None and low > high:
                # An impossible range would match nothing and look like an
                # empty pool. Treat the pair as the single bound given last.
                low, high = min(low, high), max(low, high)
            if low is not None or high is not None:
                ranges[feature] = Range(low, high)
            chosen = self._levels[feature].currentData()
            if chosen:
                levels[feature] = frozenset({chosen})
        return ClipQuery(
            ranges=ranges, levels=levels,
            episode=self._episode.text().strip(),
            full_windows_only=self._whole_only.isChecked(),
            audio_available_only=self._audio_only.isChecked(),
        )

    # -- 3 · results ---------------------------------------------------------

    def _results_box(self) -> QWidget:
        box = QGroupBox("3 · Matching windows")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 6, 10, 8)
        self._table = QTableWidget(0, len(COLUMNS))
        self._table.setHorizontalHeaderLabels([label for _, label in COLUMNS])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Interactive)
        self._table.horizontalHeader().setStretchLastSection(False)
        # Sorting goes through analyzer.clip_query.sort_rows rather than Qt's
        # own, so one implementation decides where an unmeasured value lands.
        self._table.setSortingEnabled(False)
        self._table.horizontalHeader().sectionClicked.connect(self._on_sort)
        self._table.itemSelectionChanged.connect(self._sync_enabled)
        lay.addWidget(self._table, 1)
        footer = QHBoxLayout()
        self._count = QLabel("No pool loaded.")
        footer.addWidget(self._count, 1)
        self._btn_map = QPushButton("Feature Map…")
        self._btn_map.setToolTip(
            "Show cuts, motion, and audio for the selected candidate windows. "
            "This researcher view never appears in Study Runner.")
        self._btn_map.setEnabled(False)
        self._btn_map.clicked.connect(self._show_feature_map)
        footer.addWidget(self._btn_map)
        self._btn_handcode = QPushButton("Open Browser Cut Marker…")
        self._btn_handcode.setToolTip(
            "Open the matched pairs in a browser, then mark the exact "
            "timestamp of every hard cut.")
        self._btn_handcode.setEnabled(False)
        self._btn_handcode.clicked.connect(self._handcode_matched_pair)
        footer.addWidget(self._btn_handcode)
        lay.addLayout(footer)
        return box

    def _provenance_box(self) -> QWidget:
        box = QGroupBox("How these numbers were made")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 6, 10, 8)
        self._provenance = QLabel(
            "Nothing loaded. Measure a folder of episodes, or open a run "
            "folder that has already been measured.")
        self._provenance.setWordWrap(True)
        self._provenance.setAlignment(Qt.AlignTop)
        self._provenance.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self._provenance, 1)
        return box

    def _on_sort(self, index: int) -> None:
        column = COLUMNS[index][0]
        if column == self._sort_column:
            self._sort_descending = not self._sort_descending
        else:
            self._sort_column = column
            self._sort_descending = False
        self._refresh()

    def _refresh(self) -> None:
        """Re-apply the filter and redraw. The only path that fills the table."""
        if self._pool is None:
            return
        query = self.query()
        rows = query.apply(self._pool.rows)
        rows = sort_rows(rows, self._sort_column, self._sort_descending)
        self._shown = rows

        self._table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, (key, _label) in enumerate(COLUMNS):
                value = row.get(key)
                item = QTableWidgetItem()
                if isinstance(value, float):
                    item.setText(f"{value:.4g}")
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                elif value is None:
                    # Not measured is not zero, and must not read as a value.
                    item.setText("—")
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setText(str(value))
                self._table.setItem(r, c, item)
        self._table.resizeColumnsToContents()

        total = len(self._pool.rows)
        self._count.setText(
            f"{len(rows)} of {total} measured windows match."
            if rows else
            f"No window in this pool of {total} matches. Widen the filter.")
        self._query_line.setText(f"Filter: {query.describe()}")
        self._sync_enabled()

    # -- running -------------------------------------------------------------

    def _measure(self) -> None:
        source = Path(self._source.text().strip())
        run_dir = Path(self._run_dir.text().strip())
        if not source.is_dir():
            QMessageBox.warning(self, "No episodes",
                                f"{source} is not a folder of episodes.")
            return
        if not run_dir.name:
            QMessageBox.warning(self, "No run folder",
                                "Choose where to write the measured pool.")
            return
        params = {
            "window_sec": self._window_sec.value(),
            "include_partial": self._partial.isChecked(),
            "exclude_first_sec": self._skip_first.value(),
            "exclude_last_sec": self._skip_last.value(),
            "recursive": self._recursive.isChecked(),
        }
        self._worker = PoolWorker(source, run_dir, params)
        self._worker.progress.connect(self._status.setText)
        self._worker.finished_ok.connect(self._on_measured)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(
            lambda: self._status.setText("Measurement stopped. "
                                         "Finished episodes are kept."))
        self._worker.finished.connect(self._sync_enabled)
        self._progress.setVisible(True)
        self._btn_measure.setText("Stop")
        self._sync_enabled()
        self._worker.start()

    def _stop(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._status.setText("Stopping after this episode…")

    def _on_measured(self, output: str, elapsed: float) -> None:
        self._progress.setVisible(False)
        self._status.setText(f"Measured in {elapsed:.0f} s.")
        self._load(Path(output))

    def _on_failed(self, message: str) -> None:
        self._progress.setVisible(False)
        self._status.setText("Measurement failed.")
        QMessageBox.critical(self, "Measurement failed", message)

    def _open_existing(self) -> None:
        run_dir = Path(self._run_dir.text().strip())
        if not run_dir.name:
            chosen = QFileDialog.getExistingDirectory(
                self, "Choose a measured run folder", str(Path.cwd()))
            if not chosen:
                return
            run_dir = Path(chosen)
            self._run_dir.setText(chosen)
        self._load(run_dir)

    def _load(self, run_dir: Path) -> None:
        try:
            pool = load_pool(run_dir)
        except PoolError as exc:
            QMessageBox.warning(self, "Not a measured pool", str(exc))
            return
        self._pool = pool
        self._apply_pool_bounds()
        self._provenance.setText(
            "\n".join(f"{label}: {value}" for label, value in pool.provenance()))
        self._status.setText(f"{len(pool.rows)} windows loaded.")
        self._refresh()

    def _apply_pool_bounds(self) -> None:
        """Step and range each filter to the pool it will be applied to."""
        if self._pool is None:
            return
        for feature in FEATURES:
            bounds = self._pool.bounds(FEATURE_VALUE[feature])
            if bounds is None:
                continue
            low, high = bounds
            for spin in (self._mins[feature], self._maxes[feature]):
                spin.blockSignals(True)
                spin.setRange(NO_BOUND, max(high * 2, 1.0))
                spin.setToolTip(
                    f"Measured range in this pool: {low:.4g} to {high:.4g}. "
                    f"“any” leaves this end unbounded.")
                spin.blockSignals(False)

    # -- export --------------------------------------------------------------

    def selected_rows(self) -> list[dict[str, Any]]:
        indexes = sorted({i.row() for i in self._table.selectedIndexes()})
        return [self._shown[i] for i in indexes if i < len(self._shown)]

    def _show_feature_map(self) -> None:
        rows = self.selected_rows()
        if rows:
            FeatureMapDialog(rows, self).exec()

    def _handcode_matched_pair(self) -> None:
        if self._pool is None:
            return
        try:
            page = build_pair_cut_marker(self._pool.run_dir)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not build cut marker", str(exc))
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(page))):
            QMessageBox.warning(
                self, "Could not open browser",
                f"Open this page in your browser:\n{page}")
            return
        self._status.setText(
            "Browser cut marker opened. Download its CSV when coding is complete.")

    def _export(self) -> None:
        rows = self.selected_rows()
        if not rows or self._pool is None:
            return
        target = QFileDialog.getExistingDirectory(
            self, "Choose where to write the clips", str(self._pool.run_dir))
        if not target:
            return
        out = Path(target)
        labelled = label_for_export(rows)
        try:
            (out / "clip_finder_export.json").parent.mkdir(
                parents=True, exist_ok=True)
            (out / "clip_finder_export.json").write_text(
                json.dumps(export_manifest(self._pool, self.query(), labelled),
                           indent=2),
                encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Could not write the export record",
                                 str(exc))
            return
        self._exporter = ExportWorker(labelled, out)
        self._exporter.progress.connect(self._status.setText)
        self._exporter.finished_ok.connect(
            lambda results: self._on_exported(out, results))
        self._exporter.failed.connect(self._on_failed)
        self._exporter.finished.connect(self._sync_enabled)
        self._progress.setVisible(True)
        self._sync_enabled()
        self._exporter.start()

    def _on_exported(self, out: Path, results: list) -> None:
        self._progress.setVisible(False)
        self.exported_dir = out
        failed = [r for r in results if r.get("status") != "ok"]
        message = (f"{len(results) - len(failed)} clip(s) written to {out}, "
                   f"each re-measured after export.")
        if failed:
            message += (f"\n\n{len(failed)} failed:\n"
                        + "\n".join(f"· {r['study_label']}: {r.get('error', '')}"
                                    for r in failed[:5]))
        self._status.setText(f"Exported to {out}.")
        QMessageBox.information(self, "Clips exported", message)

    # -- enabling ------------------------------------------------------------

    def _sync_enabled(self) -> None:
        running = bool(self._worker is not None and self._worker.isRunning())
        exporting = bool(self._exporter is not None
                         and self._exporter.isRunning())
        busy = running or exporting
        has_source = bool(self._source.text().strip())
        self._btn_measure.setEnabled(has_source or running)
        self._btn_measure.setText("Stop" if running else "Measure Windows")
        try:
            self._btn_measure.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._btn_measure.clicked.connect(self._stop if running else self._measure)
        self._btn_open.setEnabled(not busy)
        chosen = len(self.selected_rows())
        self._btn_map.setEnabled(bool(chosen) and not busy)
        has_pairs = bool(self._pool is not None and
                         (self._pool.run_dir / "selected_clips.csv").is_file())
        self._btn_handcode.setEnabled(has_pairs and not busy)
        self._btn_export.setEnabled(bool(chosen) and not busy)
        self._btn_export.setText(
            f"Export {chosen} Selected Clip{'s' if chosen != 1 else ''}…"
            if chosen else "Export Selected Clips…")
        if not busy and self._pool is None and not has_source:
            self._status.setText("Choose a folder of episodes to begin.")

    def closeEvent(self, event) -> None:
        for worker in (self._worker, self._exporter):
            if worker is not None and worker.isRunning():
                if hasattr(worker, "cancel"):
                    worker.cancel()
                worker.wait(5000)
        super().closeEvent(event)
