"""
ui/handcoding.py — the Human coding tab: Code, Validate tool, Agreement.

Three screens over one idea: a person's coding is a measurement, and it is
also the only thing the automated measure can be graded against.

**Code** — mark an event at the playhead, give it a type, and the row is
written to the same CSV `code_events.py` reads: the columns come from
`analyzer.event_coding`, so a sheet coded here is a sheet the command line can
score and publish, and neither can quietly change the format on the other.
Fantasy, narrative relevance and repetition are properties of the story, not
of the pixels, which is why they are coded rather than computed.

**Validate tool** — runs the detector over an episode and scores it against
that episode's hand coding (`analyzer.validation`). It adds no scoring logic
of its own; `validate_cuts.py` runs the same functions.

**Agreement** — Cohen's kappa and detection agreement between two coders'
event sheets (`event_coding.inter_coder_agreement`). Inter-rater reliability
is the figure the validation study is currently missing.

TWO GUARDRAILS

* **Blind coding.** Detections must not be opened before the coding for that
  episode is finished, or the "hand coding" is a copy of the tool's answer.
  The screen warns before running the detector on an uncoded episode.
* **An F1 is never shown bare.** Every result states its tolerance, its
  scoring (boundary vs. type-matched), and how many episodes it covers.
  Boundary localisation and rate accuracy are different claims — see
  `ARCHITECTURE.md` §9.

If VLC is unavailable the Code screen explains exactly what is missing instead
of opening a black rectangle: see ui/player.available().

THE WORKLIST

Hand coding is a pass over a SET of episodes, not one file. When the research
context is a drawn sample (`analyzer/scope.py`) both Code and Validate tool show
that sample as a worklist with each episode's coding state beside it, so the
screen answers "what is left?" instead of waiting to be told which file to open.

The state comes from the engine — `event_coding.event_sheet_status` for the
event sheets, `validation.episode_status` for the transition ones — so the
worklist and the command line cannot disagree about whether an episode is
coded. The worklist selects; it never writes.
"""

from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
    QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QSplitter, QStackedWidget,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from analyzer.event_coding import (
    EVENT_TYPES, event_sheet_status, find_event_sheet, parse_event_csv,
)
from analyzer.scope import Scope, library_scope
from analyzer.trials import get_validation_dir
from ui import player as player_mod

# The column order code_events.py reads. Kept as a constant here so a mismatch
# is one obvious edit rather than a silently malformed sheet.
COLUMNS = ["timestamp_hms", "timestamp_sec", "event_type",
           "narrative_relevance", "repeat", "duration_sec", "notes"]

RELEVANCE = ("integral", "incidental")
REPEAT = ("new", "repeat")


def _table(headers: list[str]) -> QTreeWidget:
    table = QTreeWidget()
    table.setColumnCount(len(headers))
    table.setHeaderLabels(headers)
    table.setRootIsDecorated(False)
    table.setUniformRowHeights(True)
    table.setProperty("inPanel", "true")
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setFrameShape(QFrame.NoFrame)
    return table


def event_coding_state(episode: Path) -> tuple[str, bool]:
    """(cell text, has any coding) for this episode's EVENT sheet.

    The flag is returned rather than inferred from the text: a worklist that
    decides "is this done?" by reading its own label is `LEARNINGS.md` § *A
    claim was restated instead of read*, and it breaks silently the first time
    the wording changes.
    """
    status = event_sheet_status(episode, get_validation_dir())
    if not status["exists"]:
        return "not coded", False
    if status["step"] == "unreadable":
        return "sheet unreadable", False
    n = status["n_events"]
    if not n:
        return "sheet started, no events yet", False
    return f"{n} event{'s' if n != 1 else ''}", True


def transition_coding_state(episode: Path) -> tuple[str, bool]:
    """(cell text, has any coding) for this episode's TRANSITION sheet."""
    from analyzer.validation import episode_status
    try:
        st = episode_status(episode, get_validation_dir())
    except Exception:                       # noqa: BLE001 — a cell, not a crash
        return "unreadable", False
    rows = st.get("coded_rows", 0)
    text = {
        "start": "no sheet",
        "template": "sheet started, no transitions yet",
        "coded": f"{rows} coded",
        "detected": f"{rows} coded, detector run",
        "compared": f"{rows} coded, compared",
        "annotated": f"{rows} coded, annotated",
    }.get(st.get("step", ""), str(st.get("step", "")))
    return text, bool(rows)


class Worklist(QWidget):
    """The current sample as a list of episodes, each with its coding state.

    A view over the scope, never a filter on it: choosing a row loads that
    episode and nothing else changes. Under the whole-library scope it shows
    no rows and says why — a worklist of 137 episodes is a library, and the
    thing that makes a worklist useful is that it ends.
    """

    episode_chosen = Signal(object)         # Path

    def __init__(self, state_fn) -> None:
        super().__init__()
        self._state_fn = state_fn
        self._scope: Scope = library_scope()

        from ui.main_window import Panel
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        panel = Panel("Worklist")
        self._count = QLabel("")
        self._count.setProperty("role", "dim")
        panel.add_header_widget(self._count)
        self._note = QLabel("")
        self._note.setProperty("role", "dim")
        self._note.setWordWrap(True)
        panel.body_layout.addWidget(self._note)
        self._table = _table(["Episode", "Coding", "Show"])
        self._table.itemDoubleClicked.connect(self._chosen)
        panel.body_layout.addWidget(self._table)
        lay.addWidget(panel)
        # The splitter honours size hints over setSizes, and the panels below
        # this one are tall tables — without a floor the worklist is squeezed
        # to two rows on the Validate screen. A worklist you have to drag open
        # before you can read it is not a worklist.
        self.setMinimumHeight(150)

    def set_scope(self, scope: Scope) -> None:
        self._scope = scope
        self.refresh()

    def refresh(self) -> None:
        """Re-read every episode's coding state from disk.

        Called after a sheet is saved as well as on a scope change, because
        the row that just changed is the one the coder is looking at.
        """
        self._table.clear()
        if self._scope.is_library:
            self._note.setText(
                "Showing the whole library. Choose a drawn sample in the "
                "Showing: control on the toolbar and its episodes appear here "
                "as a worklist.")
            self._note.setVisible(True)
            self._count.setText("")
            return
        done = 0
        for episode in self._scope.episodes:
            state, coded = self._state_fn(episode)
            done += bool(coded)
            item = QTreeWidgetItem([episode.name, state, episode.parent.name])
            item.setData(0, Qt.UserRole, str(episode))
            item.setToolTip(0, str(episode))
            self._table.addTopLevelItem(item)
        head = self._table.header()
        head.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2):
            head.setSectionResizeMode(col, QHeaderView.ResizeToContents)

        total = self._scope.total_drawn
        listed = len(self._scope.episodes)
        self._count.setText(f"{done} of {listed} with coding")
        parts = [f"{self._scope.label} — {total} episode"
                 f"{'s' if total != 1 else ''} drawn"]
        if self._scope.missing:
            parts.append(f"{len(self._scope.missing)} no longer on disk, so "
                         f"{listed} can be coded")
        parts.append("double-click an episode to open it")
        self._note.setText(" — ".join(parts))
        self._note.setVisible(True)

    def _chosen(self, item, _column) -> None:
        payload = item.data(0, Qt.UserRole)
        if payload:
            self.episode_chosen.emit(Path(payload))


class CodeView(QWidget):
    """Play an episode, mark events, save the sheet."""

    def __init__(self, window, bar) -> None:
        super().__init__()
        self._window = window
        self._episode: Path | None = None
        self._sheet: Path | None = None
        self._player = None
        self._events: list[dict] = []
        self._dirty = False
        self.controls: list[QWidget] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        from ui.main_window import Ambox, Panel
        self._target = QLabel("No episode selected")
        self.controls.append(self._target)
        bar.row.addWidget(self._target, 1)
        self._btn_open = QPushButton("Open Episode")
        self._btn_open.clicked.connect(self._open_episode)
        bar.row.addWidget(self._btn_open)
        self.controls.append(self._btn_open)
        self._btn_load = QPushButton("Load Sheet…")
        self._btn_load.clicked.connect(self._load_sheet)
        bar.row.addWidget(self._btn_load)
        self.controls.append(self._btn_load)
        self._btn_save = QPushButton("Save Sheet")
        self._btn_save.setProperty("primary", "true")
        self._btn_save.setEnabled(False)
        self._btn_save.clicked.connect(self._save_sheet)
        bar.row.addWidget(self._btn_save)
        self.controls.append(self._btn_save)

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

        # The worklist sits above the events rather than beside the video: the
        # coder needs the picture large, and "which episode am I on / what is
        # left" belongs with the sheet it is about.
        right_side = QSplitter(Qt.Vertical)
        right_side.setChildrenCollapsible(False)
        self.worklist = Worklist(event_coding_state)
        self.worklist.episode_chosen.connect(self._open_from_worklist)
        right_side.addWidget(self.worklist)

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
        right_side.addWidget(right)
        right_side.setSizes([200, 320])
        split.addWidget(right_side)

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

    def set_scope(self, scope: Scope) -> None:
        """The research context changed: show it as the worklist."""
        if hasattr(self, "worklist"):
            self.worklist.set_scope(scope)

    def _open_episode(self) -> None:
        if self._episode is None:
            chosen, _ = QFileDialog.getOpenFileName(
                self, "Open episode", str(self._window._root or ""),
                "Video (*.mp4 *.mkv *.avi *.mov)")
            if not chosen:
                return
            self._episode = Path(chosen)
        self._load_episode(self._episode)

    def _open_from_worklist(self, episode: Path) -> None:
        """Switch episodes from the worklist, without losing unsaved marks."""
        if self._dirty:
            from ui.modal import ConfirmDialog
            dialog = ConfirmDialog(
                self, "Unsaved coding",
                f"{len(self._events)} event"
                f"{'s' if len(self._events) != 1 else ''} on "
                f"{self._episode.name if self._episode else 'this episode'} "
                f"{'have' if len(self._events) != 1 else 'has'} not been "
                f"saved. Open {episode.name} and discard them?",
                "Nothing already saved to disk is affected — only the marks "
                "made since the last Save Sheet.",
                confirm_text="Discard and open")
            if dialog.exec() != QDialog.Accepted:
                return
        self._load_episode(episode)

    def _load_episode(self, episode: Path) -> None:
        """Open *episode* and its sheet, replacing whatever was loaded.

        The events list is cleared when the new episode has no sheet. It was
        not: opening a second, uncoded episode kept the first one's marks in
        the table, and Save Sheet would have written them into the second
        episode's file under the second episode's name.
        """
        self._episode = episode
        self._player.open(episode)
        existing = find_event_sheet(episode, get_validation_dir())
        if existing is not None:
            # Found wherever a coder filed it — the same lookup code_events.py
            # scores from, so the screen and the command line open one sheet.
            self._read_sheet(existing)
        else:
            self._events = []
            self._dirty = False
            self._sheet = (get_validation_dir()
                           / f"{episode.stem}_events.csv")
            self._refill()
        self._target.setText(f"{episode.name} — sheet: {self._sheet.name}")
        if hasattr(self, "worklist"):
            self.worklist.refresh()
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
        if hasattr(self, "worklist"):
            self.worklist.refresh()      # the row that just changed
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


# ---------------------------------------------------------------------------
# Validate tool
# ---------------------------------------------------------------------------

class DetectWorker(QThread):
    """Shot detection for one episode, off the interface thread."""

    status = Signal(str)
    progress = Signal(float)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, video: Path, vdir: Path, params: dict) -> None:
        super().__init__()
        self._video = video
        self._vdir = vdir
        self._params = params

    def run(self) -> None:
        from analyzer.validation import export_detections
        try:
            result = export_detections(
                self._video, self._vdir,
                progress_cb=self.progress.emit,
                status_cb=self.status.emit, **self._params)
        except Exception as exc:               # noqa: BLE001 — shown, not hidden
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.done.emit(result)


class ValidateView(QWidget):
    """Grade the detector against one episode's hand coding.

    Every scoring function here lives in `analyzer/validation.py` and is the
    same one `validate_cuts.py` calls, so a figure produced on this screen and
    a figure produced at the command line cannot disagree.
    """

    SCORING_NOTE = (
        "Boundary scoring asks whether a transition was found at the right "
        "time; type-matched scoring also asks whether it was called the right "
        "kind. They are different claims and both are shown. Rate accuracy — "
        "whether cuts/min is right — is a third claim again, because false "
        "positives and false negatives partly cancel in a count.")

    def __init__(self, window, bar) -> None:
        super().__init__()
        self._window = window
        self._episode: Path | None = None
        self._worker: DetectWorker | None = None
        self._last: dict | None = None
        self.controls: list[QWidget] = []

        from ui.main_window import Ambox, Panel
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        # -- sub-bar controls --
        self._target = QLabel("No episode selected")
        self._add(bar, self._target, stretch=1)
        self._btn_choose = QPushButton("Choose Episode…")
        self._btn_choose.clicked.connect(self._choose)
        self._add(bar, self._btn_choose)
        self._btn_template = QPushButton("Create Coding Sheet")
        self._btn_template.setToolTip(
            "Write an empty transition-coding template for this episode into "
            "the validation folder.")
        self._btn_template.clicked.connect(self._create_template)
        self._add(bar, self._btn_template)
        self._btn_detect = QPushButton("Run Detector")
        self._btn_detect.clicked.connect(self._run_detector)
        self._add(bar, self._btn_detect)
        self._btn_compare = QPushButton("Compare")
        self._btn_compare.setProperty("primary", "true")
        self._btn_compare.clicked.connect(self._compare)
        self._add(bar, self._btn_compare)

        # -- body --
        lay.addWidget(Ambox(
            "Code first, then detect",
            "Opening the detector's output before your coding is finished "
            "makes the hand coding a copy of the tool's answer, and the "
            "comparison meaningless. Code the episode, save the sheet, then "
            "run the detector.", "warn"))

        settings = QWidget()
        srow = QHBoxLayout(settings)
        srow.setContentsMargins(0, 0, 0, 0)
        srow.setSpacing(6)
        srow.addWidget(QLabel("Detector:"))
        self._detector = QComboBox()
        self._detector.addItems(["content", "adaptive"])
        srow.addWidget(self._detector)
        srow.addWidget(QLabel("Threshold:"))
        self._threshold = QDoubleSpinBox()
        self._threshold.setRange(1.0, 100.0)
        self._threshold.setValue(27.0)
        srow.addWidget(self._threshold)
        self._dissolves = QCheckBox("Dissolve pass")
        self._dissolves.setChecked(True)
        self._dissolves.setToolTip(
            "Dissolve detection is EXPERIMENTAL — see ARCHITECTURE.md §9.")
        srow.addWidget(self._dissolves)
        srow.addWidget(QLabel("Noise floor:"))
        self._floor = QDoubleSpinBox()
        self._floor.setRange(0.0, 50.0)
        self._floor.setValue(3.0)
        srow.addWidget(self._floor)
        srow.addWidget(QLabel("Min frames:"))
        self._minframes = QSpinBox()
        self._minframes.setRange(1, 200)
        self._minframes.setValue(15)
        srow.addWidget(self._minframes)
        srow.addWidget(QLabel("Tolerance (s):"))
        self._tolerance = QDoubleSpinBox()
        self._tolerance.setRange(0.1, 10.0)
        self._tolerance.setSingleStep(0.5)
        self._tolerance.setValue(2.0)
        self._tolerance.setToolTip(
            "A detection counts as correct if it lands within this many "
            "seconds of a hand-coded transition. The published figure uses "
            "±2 s; changing it changes what the F1 means.")
        srow.addWidget(self._tolerance)
        srow.addStretch(1)
        lay.addWidget(settings)

        self._status = QLabel("Choose an episode to begin.")
        self._status.setProperty("role", "dim")
        self._status.setWordWrap(True)
        lay.addWidget(self._status)

        split = QSplitter(Qt.Vertical)
        lay.addWidget(split, 1)

        self.worklist = Worklist(transition_coding_state)
        self.worklist.episode_chosen.connect(self._open_from_worklist)
        split.addWidget(self.worklist)

        scores = Panel("Scores for this episode")
        self._window_note = QLabel("")
        self._window_note.setProperty("role", "dim")
        scores.add_header_widget(self._window_note)
        self._scores = _table(["Transition type", "Scoring", "TP", "FP", "FN",
                               "Precision", "Recall", "F1"])
        scores.body_layout.addWidget(self._scores)
        split.addWidget(scores)

        detail = Panel("Every disagreement")
        self._detail = _table(["Hand-coded", "Coded type", "Tool", "Tool type",
                               "Offset (s)", "Match", "Type match"])
        detail.body_layout.addWidget(self._detail)
        split.addWidget(detail)

        totals = Panel("Across every comparison recorded")
        self._totals_detector = QComboBox()
        self._totals_detector.setToolTip(
            "Scores are per DETECTOR configuration. Averaging across "
            "configurations produces a figure describing no detector you can "
            "actually run.")
        self._totals_detector.currentIndexChanged.connect(
            lambda _i: self.refresh_totals(keep_selection=True))
        totals.add_header_widget(self._totals_detector)
        self._totals_note = QLabel("")
        self._totals_note.setProperty("role", "dim")
        totals.add_header_widget(self._totals_note)
        self._totals = _table(["Transition type", "TP", "FP", "FN",
                               "Precision", "Recall", "F1"])
        totals.body_layout.addWidget(self._totals)
        split.addWidget(totals)
        split.setSizes([170, 190, 240, 190])

        note = QLabel(self.SCORING_NOTE)
        note.setProperty("role", "dim")
        note.setWordWrap(True)
        lay.addWidget(note)

        self.refresh_totals()

    def _add(self, bar, widget, stretch: int = 0) -> None:
        bar.row.addWidget(widget, stretch)
        self.controls.append(widget)

    # -- episode --
    def set_target(self, path: Path | None) -> None:
        if path is not None and path.is_file():
            self._episode = path
            self._show_status()

    def set_scope(self, scope: Scope) -> None:
        """The research context changed: show it as the worklist."""
        self.worklist.set_scope(scope)

    def _open_from_worklist(self, episode: Path) -> None:
        """Grade a different episode. Nothing here is unsaved, so no warning.

        The score tables are cleared rather than left showing the previous
        episode's figures under a new episode's name — the last comparison is
        a result ABOUT one episode, not a property of the screen.
        """
        self._episode = episode
        self._last = None
        self._scores.clear()
        self._detail.clear()
        self._window_note.setText("")
        self._show_status()

    def _choose(self) -> None:
        chosen, _f = QFileDialog.getOpenFileName(
            self, "Choose episode", str(self._window._root or ""),
            "Video (*.mp4 *.mkv *.avi *.mov)")
        if chosen:
            self._episode = Path(chosen)
            self._show_status()

    def _show_status(self) -> None:
        from analyzer.validation import episode_status
        if self._episode is None:
            return
        self._target.setText(self._episode.name)
        st = episode_status(self._episode, get_validation_dir())
        steps = {
            "start": "no coding sheet yet — create one, then code the episode",
            "template": "sheet created but empty — code the episode",
            "coded": f"{st['coded_rows']} transitions hand-coded — "
                     "run the detector next",
            "detected": f"{st['coded_rows']} hand-coded, "
                        f"{len(st['detections'])} detector run"
                        f"{'s' if len(st['detections']) != 1 else ''} — "
                        "press Compare",
            "compared": f"{st['coded_rows']} hand-coded, compared; "
                        f"{st['errors_annotated']}/{st['errors_total']} "
                        "disagreements annotated",
            "annotated": f"{st['coded_rows']} hand-coded, compared, every "
                         "disagreement annotated",
        }
        self._status.setText(steps.get(st["step"], st["step"]))

    def _create_template(self) -> None:
        from analyzer.validation import write_template
        if self._episode is None:
            QMessageBox.information(self, "Validate tool",
                                    "Choose an episode first.")
            return
        path = write_template(self._episode, get_validation_dir())
        self._show_status()
        self.worklist.refresh()
        QMessageBox.information(
            self, "Coding sheet created",
            f"Wrote {path.name}.\n\nCode the episode against "
            f"validation/CODEBOOK.md, then come back and run the detector.")

    # -- detection --
    def _run_detector(self) -> None:
        from analyzer.validation import episode_status
        if self._episode is None:
            QMessageBox.information(self, "Validate tool",
                                    "Choose an episode first.")
            return
        if self._worker is not None and self._worker.isRunning():
            return
        st = episode_status(self._episode, get_validation_dir())
        if st["coded_rows"] == 0:
            answer = QMessageBox.question(
                self, "This episode is not coded yet",
                "There is no hand coding for this episode.\n\n"
                "Running the detector now is allowed, but do NOT open its "
                "output until your coding is finished and saved — otherwise "
                "the coding is a copy of the tool's answer and the comparison "
                "measures nothing.\n\nRun the detector anyway?")
            if answer != QMessageBox.Yes:
                return
        self._btn_detect.setEnabled(False)
        self._btn_detect.setText("Detecting…")
        self._worker = DetectWorker(
            self._episode, get_validation_dir(),
            {"detector": self._detector.currentText(),
             "threshold": self._threshold.value(),
             "noise_floor": self._floor.value(),
             "min_frames": self._minframes.value(),
             "dissolves_on": self._dissolves.isChecked()})
        self._worker.status.connect(self._status.setText)
        self._worker.done.connect(self._detected)
        self._worker.failed.connect(self._detect_failed)
        self._worker.start()

    def _detected(self, result: dict) -> None:
        self._reset_detect_button()
        self.worklist.refresh()
        self._status.setText(
            f"Detector wrote {result['n_hard_cuts']} hard cut"
            f"{'s' if result['n_hard_cuts'] != 1 else ''} and "
            f"{result['n_dissolves']} dissolve"
            f"{'s' if result['n_dissolves'] != 1 else ''} "
            f"({result['tag']}). Press Compare to score it.")

    def _detect_failed(self, message: str) -> None:
        self._reset_detect_button()
        self._status.setText(f"Detection failed: {message}")
        QMessageBox.warning(self, "Detection failed", message)

    def _reset_detect_button(self) -> None:
        # NOT `self._worker = None`. This runs in a slot connected to the
        # worker's own signal, so dropping the last reference here frees the
        # QThread while it is still emitting — the process dies with no
        # traceback. Guards use isRunning(); the object is released when the
        # next run replaces it.
        self._btn_detect.setEnabled(True)
        self._btn_detect.setText("Run Detector")

    # -- comparison --
    def _compare(self) -> None:
        from analyzer.validation import compare_detections, find_manual
        if self._episode is None:
            QMessageBox.information(self, "Validate tool",
                                    "Choose an episode first.")
            return
        vdir = get_validation_dir()
        manual = find_manual(self._episode, vdir)
        if manual is None:
            QMessageBox.information(
                self, "No coding sheet",
                "This episode has no hand coding. The comparison grades the "
                "tool against a person, so it needs the person's answer "
                "first — use Create Coding Sheet, then code the episode.")
            return
        runs = sorted(vdir.rglob(f"{self._episode.stem}__*_detections.csv"))
        if not runs:
            QMessageBox.information(
                self, "No detector output",
                "The detector has not been run on this episode yet.")
            return
        det = runs[-1]
        if len(runs) > 1:
            from PySide6.QtWidgets import QInputDialog
            labels = [p.name for p in runs]
            chosen, ok = QInputDialog.getItem(
                self, "Which detector run?",
                "Several detector configurations exist for this episode. "
                "Grade which one?", labels, len(labels) - 1, False)
            if not ok:
                return
            det = runs[labels.index(chosen)]

        warnings: list[str] = []
        try:
            result = compare_detections(det, manual,
                                        tolerance=self._tolerance.value(),
                                        warn_cb=warnings.append)
        except Exception as exc:               # noqa: BLE001 — shown, not hidden
            QMessageBox.warning(self, "Compare failed", str(exc))
            return
        self._last = result
        self._fill_scores(result)
        self._fill_detail(result)
        self.refresh_totals()
        self.worklist.refresh()
        if warnings:
            QMessageBox.information(
                self, "Check the coding sheet",
                "The comparison ran, with:\n\n" + "\n".join(warnings[:12]))

    def _fill_scores(self, result: dict) -> None:
        self._scores.clear()
        for row in result.get("summary_rows", []):
            self._scores.addTopLevelItem(QTreeWidgetItem([
                str(row.get("type", "")),
                str(row.get("scoring", "boundary")),
                str(row.get("TP", 0)), str(row.get("FP", 0)),
                str(row.get("FN", 0)),
                f"{row.get('precision', 0):.3f}",
                f"{row.get('recall', 0):.3f}",
                f"{row.get('F1', 0):.3f}"]))
        head = self._scores.header()
        for col in range(self._scores.columnCount()):
            head.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        window = result.get("window")
        self._window_note.setText(
            f"±{self._tolerance.value():g} s"
            + (f", window {window[0]:.0f}–{window[1]:.0f} s" if window else "")
            + f", {self._episode.stem}")

    def _fill_detail(self, result: dict) -> None:
        self._detail.clear()
        rows = list(result.get("results", []))
        rows += [dict(r, match="FP") for r in result.get("false_positives", [])]
        for row in rows:
            if row.get("match") == "TP" and row.get("type_match") != "no":
                continue                       # only the disagreements
            offset = row.get("offset_sec")
            self._detail.addTopLevelItem(QTreeWidgetItem([
                str(row.get("manual_hms") or "—"),
                str(row.get("manual_type") or "—"),
                str(row.get("timestamp_hms") or row.get("tool_hms") or "—"),
                str(row.get("tool_type") or row.get("type") or "—"),
                f"{offset:+.2f}" if isinstance(offset, (int, float)) else "—",
                str(row.get("match") or "—"),
                str(row.get("type_match") or "—")]))
        head = self._detail.header()
        for col in range(self._detail.columnCount()):
            head.setSectionResizeMode(col, QHeaderView.ResizeToContents)

    def refresh_totals(self, keep_selection: bool = False) -> None:
        """The aggregate for ONE detector configuration.

        This is the number the product's honesty claim rests on, so it says
        how many comparison files it covers rather than presenting one figure
        as if it described the whole corpus — and it is per detector, because
        summing ContentDetector and TransNetV2 runs over the same episodes
        gave 0.891 against their real 0.855 and 0.928, and hid that the
        shipped detector scores 0.133 on dissolves where TransNetV2 scores
        1.000.
        """
        from analyzer.validation import aggregate_summary, available_detector_tags
        self._totals.clear()
        try:
            tags = available_detector_tags(get_validation_dir())
        except Exception as exc:               # noqa: BLE001 — shown, not hidden
            self._totals_note.setText(f"could not read comparisons: {exc}")
            return
        if not keep_selection:
            current = self._totals_detector.currentText()
            self._totals_detector.blockSignals(True)
            self._totals_detector.clear()
            self._totals_detector.addItems(tags)
            if current in tags:
                self._totals_detector.setCurrentIndex(tags.index(current))
            self._totals_detector.blockSignals(False)
        if not tags:
            self._totals_note.setText("no comparisons recorded yet")
            return
        try:
            summary = aggregate_summary(
                get_validation_dir(),
                detector_tag=self._totals_detector.currentText() or tags[0])
        except Exception as exc:               # noqa: BLE001 — shown, not hidden
            self._totals_note.setText(f"could not read comparisons: {exc}")
            return
        for row in summary["rows"]:
            item = QTreeWidgetItem([
                str(row["type"]), str(row["TP"]), str(row["FP"]),
                str(row["FN"]), f"{row['precision']:.3f}",
                f"{row['recall']:.3f}", f"{row['F1']:.3f}"])
            if row["type"] == "AGGREGATE":
                font = item.font(0)
                font.setBold(True)
                for col in range(self._totals.columnCount()):
                    item.setFont(col, font)
            self._totals.addTopLevelItem(item)
        head = self._totals.header()
        for col in range(self._totals.columnCount()):
            head.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        n = summary["n_files"]
        tag = summary.get("detector_tag") or "?"
        others = [x for x in summary.get("detector_tags", []) if x != tag]
        note = (f"{tag} only — boundary scoring, latest run per episode, "
                f"{n} comparison file{'s' if n != 1 else ''}")
        if others:
            note += (f".  {len(others)} other detector"
                     f"{'s have' if len(others) != 1 else ' has'} results too "
                     f"({', '.join(others)}); their scores are not combined "
                     f"with these.")
        self._totals_note.setText(note if n else "no comparisons recorded yet")


# ---------------------------------------------------------------------------
# Agreement
# ---------------------------------------------------------------------------

class AgreementView(QWidget):
    """Two coders on the same episode: how much do they agree?

    Inter-rater reliability is the figure the validation study currently
    lacks, and it is a property of the CODING, not of the tool. Nothing here
    involves the detector.
    """

    def __init__(self, window, bar) -> None:
        super().__init__()
        self._window = window
        self._a: Path | None = None
        self._b: Path | None = None
        self.controls: list[QWidget] = []

        from ui.main_window import Ambox, Panel
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        self._btn_a = QPushButton("Coder A sheet…")
        self._btn_a.clicked.connect(lambda: self._pick("a"))
        self._add(bar, self._btn_a)
        self._btn_b = QPushButton("Coder B sheet…")
        self._btn_b.clicked.connect(lambda: self._pick("b"))
        self._add(bar, self._btn_b)
        self._btn_run = QPushButton("Compare Coders")
        self._btn_run.setProperty("primary", "true")
        self._btn_run.setEnabled(False)
        self._btn_run.clicked.connect(self._run)
        self._add(bar, self._btn_run)
        self._picked = QLabel("No sheets chosen")
        self._picked.setProperty("role", "dim")
        self._add(bar, self._picked, stretch=1)

        lay.addWidget(Ambox(
            "This measures the coders, not the programme",
            "Cohen's kappa here says how consistently two people applied "
            "EVENT_CODEBOOK.md to the same episode. A low value means the "
            "codebook or the training needs work — it says nothing about the "
            "episode."))

        summary = Panel("Agreement")
        self._summary = _table(["Measure", "Value", "What it means"])
        summary.body_layout.addWidget(self._summary)
        lay.addWidget(summary, 1)

        detail = Panel("Event by event")
        self._detail = _table(["Time", "Coder A", "Coder B", "Agreement"])
        detail.body_layout.addWidget(self._detail)
        lay.addWidget(detail, 1)

    def _add(self, bar, widget, stretch: int = 0) -> None:
        bar.row.addWidget(widget, stretch)
        self.controls.append(widget)

    def _pick(self, which: str) -> None:
        chosen, _f = QFileDialog.getOpenFileName(
            self, f"Coder {which.upper()} event sheet",
            str(get_validation_dir()), "Coding sheet (*.csv)")
        if not chosen:
            return
        setattr(self, f"_{which}", Path(chosen))
        self._btn_run.setEnabled(self._a is not None and self._b is not None)
        self._picked.setText(
            f"A: {self._a.name if self._a else '—'}   "
            f"B: {self._b.name if self._b else '—'}")

    def _run(self) -> None:
        from analyzer.event_coding import inter_coder_agreement
        if self._a is None or self._b is None:
            return
        warnings: list[str] = []
        try:
            result = inter_coder_agreement(self._a, self._b,
                                           warn_cb=warnings.append)
        except Exception as exc:               # noqa: BLE001 — shown, not hidden
            QMessageBox.warning(self, "Agreement failed", str(exc))
            return

        kappa = result["type_kappa"]
        rows = [
            ("Events, coder A", str(result["n_coder_a"]),
             "how many events A logged"),
            ("Events, coder B", str(result["n_coder_b"]),
             "how many events B logged"),
            ("Matched", str(result["n_matched"]),
             f"events both coders logged within ±{result['tolerance']:g} s"),
            ("Detection agreement",
             f"{result['detection_agreement']:.3f}",
             "Dice: 2 × matched ÷ (A + B). Whether they SPOTTED the same "
             "events"),
            ("Type agreement",
             f"{result['type_agreement']:.3f}"
             if result["type_agreement"] is not None else "—",
             "of the matched events, the share given the same type"),
            ("Cohen's kappa",
             f"{kappa:.3f}" if kappa is not None else "—",
             self._kappa_reading(kappa)),
        ]
        self._summary.clear()
        for row in rows:
            self._summary.addTopLevelItem(QTreeWidgetItem(list(row)))
        head = self._summary.header()
        head.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        head.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        head.setSectionResizeMode(2, QHeaderView.Stretch)

        self._detail.clear()
        for pair in result["matched_pairs"]:
            same = pair["a_type"] == pair["b_type"]
            self._detail.addTopLevelItem(QTreeWidgetItem([
                pair["timestamp_hms"], pair["a_type"], pair["b_type"],
                "same type" if same else "different type"]))
        for only in result["a_only"]:
            self._detail.addTopLevelItem(QTreeWidgetItem([
                only["timestamp_hms"], only["type"], "—", "A only"]))
        for only in result["b_only"]:
            self._detail.addTopLevelItem(QTreeWidgetItem([
                only["timestamp_hms"], "—", only["type"], "B only"]))
        self._detail.sortItems(0, Qt.AscendingOrder)
        for col in range(self._detail.columnCount()):
            self._detail.header().setSectionResizeMode(
                col, QHeaderView.ResizeToContents)

        if warnings:
            QMessageBox.information(
                self, "Check the sheets",
                "The comparison ran, with:\n\n" + "\n".join(warnings[:12]))

    @staticmethod
    def _kappa_reading(kappa) -> str:
        """Landis & Koch's bands, named as the convention they are.

        Deliberately not colour-coded and deliberately attributed: the bands
        are a rule of thumb from 1977, not a property of these data.
        """
        if kappa is None:
            return "not computable — too few matched events, or one type only"
        return ("chance-corrected type agreement. Landis & Koch's rule of "
                "thumb calls this "
                + ("poor" if kappa < 0.0 else
                   "slight" if kappa < 0.21 else
                   "fair" if kappa < 0.41 else
                   "moderate" if kappa < 0.61 else
                   "substantial" if kappa < 0.81 else "almost perfect")
                + " — a convention, not a threshold")


# ---------------------------------------------------------------------------
# The tab
# ---------------------------------------------------------------------------

class HandCodingTab(QWidget):
    """Code, Validate tool and Agreement, switched from the sub-toolbar."""

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window

        from ui.main_window import SubToolBar, SubViews
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._bar = SubToolBar()
        self._stack = QStackedWidget()
        self._views = SubViews(self._bar, self._stack)
        self._bar.row.addSpacing(8)

        self.code = CodeView(window, self._bar)
        self.validate = ValidateView(window, self._bar)
        self.agreement = AgreementView(window, self._bar)
        self._views.add("Code", self.code)
        self._views.add("Validate tool", self.validate)
        self._views.add("Agreement", self.agreement)

        self._bar.row.addStretch(1)
        lay.addWidget(self._bar)
        lay.addWidget(self._stack, 1)

        self._views.changed.connect(self._sync_controls)
        self._sync_controls()

    def _sync_controls(self) -> None:
        current = self._stack.currentWidget()
        for view in (self.code, self.validate, self.agreement):
            for widget in view.controls:
                widget.setVisible(view is current)

    def set_target(self, path: Path | None) -> None:
        """The Library selection reaches both screens that use an episode."""
        self.code.set_target(path)
        self.validate.set_target(path)

    def set_scope(self, scope) -> None:
        """The research context reaches both worklists.

        Agreement is deliberately left out: it compares two coders' SHEETS,
        which are not episodes and are not drawn by a sample.
        """
        self.code.set_scope(scope)
        self.validate.set_scope(scope)

    def show_view(self, name: str) -> None:
        self._views.show(name)
