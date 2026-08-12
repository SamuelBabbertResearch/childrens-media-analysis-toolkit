"""
ui/automated.py — the Automated coding tab: run the analysis, watch it run.

Analysis happens on a worker thread with a progress callback, per the
architecture rule that the interface must never freeze. The engine is called
exactly as `cli.py` calls it — `analyze_episode` then `save_cache` for one
file, `analyze_show_batch` for a folder — so there is one analysis path and
the front-end adds no logic of its own to it.

Cancellation is the one subtlety. `analyze_show_batch` has no cancel flag, and
it wraps each episode in `except Exception`, so an ordinary exception raised
from the progress callback would be swallowed and recorded as a failed
episode. `_Cancelled` therefore derives from BaseException, which that clause
does not catch, so it unwinds the batch loop cleanly and leaves already
finished episodes cached.

Guardrail: this screen reports what was measured and how long it took. It does
not rate the episode.
"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QProgressBar,
    QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from analyzer.batch import analyze_show_batch
from analyzer.cache import save_cache
from analyzer.engine import analyze_episode
from analyzer.show_index import list_episodes, show_key


class _Cancelled(BaseException):
    """Not an Exception on purpose — see the module docstring."""


class AnalysisWorker(QThread):
    """Runs the engine off the interface thread."""

    progress = Signal(str, float, float)     # episode, episode frac, overall
    finished_ok = Signal(list, float)        # results, elapsed seconds
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, root: Path, target: Path, config: dict,
                 force: bool) -> None:
        super().__init__()
        self._root = root
        self._target = target
        self._config = config
        self._force = force
        self._stop = False

    def cancel(self) -> None:
        self._stop = True

    def _tick(self, name: str, ep_frac: float, overall: float) -> None:
        if self._stop:
            raise _Cancelled
        self.progress.emit(name, ep_frac, overall)

    def run(self) -> None:
        started = time.monotonic()
        try:
            if self._target.is_dir():
                results = analyze_show_batch(
                    self._target, root=self._root, config=self._config,
                    force=self._force, progress_cb=self._tick)
            else:
                skey = show_key(self._root, self._target.parent)
                result = analyze_episode(
                    self._target, config=self._config,
                    progress_cb=lambda f: self._tick(self._target.name, f, f))
                if result.status != "failed":
                    save_cache(self._root, skey, self._target.stem,
                               result.to_dict())
                results = [result]
        except _Cancelled:
            self.cancelled.emit()
            return
        except Exception as exc:            # noqa: BLE001 - reported, not hidden
            self.failed.emit(str(exc))
            return
        self.finished_ok.emit(results, time.monotonic() - started)


class AutomatedTab(QWidget):
    """Choose a target in the Library, then run the automated pass on it."""

    library_changed = Signal()

    COLS = ("Episode", "Result", "Cuts/min", "Sensory load")

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self._target: Path | None = None
        self._worker: AnalysisWorker | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        from ui.main_window import Ambox, Panel, SubToolBar
        bar = SubToolBar()
        self._target_label = QLabel("No episode or show selected")
        bar.row.addWidget(self._target_label, 1)
        self._btn_run = QPushButton("Analyze")
        self._btn_run.setProperty("primary", "true")
        self._btn_run.clicked.connect(lambda: self._start(force=False))
        bar.row.addWidget(self._btn_run)
        self._btn_force = QPushButton("Re-analyze")
        self._btn_force.setToolTip(
            "Measure again even where a cached result exists.")
        self._btn_force.clicked.connect(lambda: self._start(force=True))
        bar.row.addWidget(self._btn_force)
        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.setEnabled(False)
        self._btn_cancel.clicked.connect(self._cancel)
        bar.row.addWidget(self._btn_cancel)
        lay.addWidget(bar)

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(8, 8, 8, 8)
        bl.setSpacing(6)

        bl.addWidget(Ambox(
            "What this measures",
            "Pacing, colour, motion, flashing and audio, from the video "
            "itself. Cached episodes are skipped unless you choose "
            "Re-analyze. Nothing here judges the episode — it records what "
            "was measured."))

        self._progress = QProgressBar()
        self._progress.setRange(0, 1000)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        bl.addWidget(self._progress)
        self._status = QLabel("Idle.")
        self._status.setProperty("role", "dim")
        bl.addWidget(self._status)

        panel = Panel("Measured this run")
        self._table = QTreeWidget()
        self._table.setColumnCount(len(self.COLS))
        self._table.setHeaderLabels(list(self.COLS))
        self._table.setRootIsDecorated(False)
        self._table.setUniformRowHeights(True)
        self._table.setProperty("inPanel", "true")
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setFrameShape(QFrame.NoFrame)
        head = self._table.header()
        # Without this the trailing column absorbs the slack and its figures
        # sit an inch from their heading.
        head.setStretchLastSection(False)
        head.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, len(self.COLS)):
            head.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        panel.body_layout.addWidget(self._table)
        bl.addWidget(panel, 1)

        lay.addWidget(body, 1)
        self._sync_buttons()

    # -- target -----------------------------------------------------------
    def set_target(self, path: Path | None) -> None:
        """Called when the Library selection changes."""
        self._target = path
        if path is None:
            self._target_label.setText("No episode or show selected")
        elif path.is_dir():
            n = len(list_episodes(path))
            self._target_label.setText(
                f"Show: {path.name} — {n} episode{'s' if n != 1 else ''}")
        else:
            self._target_label.setText(f"Episode: {path.name}")
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        running = self._worker is not None and self._worker.isRunning()
        ready = self._target is not None and not running
        self._btn_run.setEnabled(ready)
        self._btn_force.setEnabled(ready)
        self._btn_cancel.setEnabled(running)

    # -- running ----------------------------------------------------------
    def _start(self, force: bool) -> None:
        if self._target is None or self._window._root is None:
            return
        self._table.clear()
        self._progress.setValue(0)
        self._status.setText("Starting…")
        self._worker = AnalysisWorker(
            self._window._root, self._target, self._window._cfg, force)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.finished.connect(self._sync_buttons)
        self._worker.start()
        self._sync_buttons()

    def _cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._status.setText("Finishing the current episode, then "
                                 "stopping…")

    def _on_progress(self, name: str, ep_frac: float, overall: float) -> None:
        self._progress.setValue(int(overall * 1000))
        self._status.setText(f"{name} — {ep_frac:.0%} of this episode, "
                             f"{overall:.0%} overall")

    def _on_done(self, results, elapsed: float) -> None:
        for result in results:
            self._add_row(result)
        failed = sum(1 for r in results if r.status == "failed")
        summary = (f"{len(results)} episode"
                   f"{'s' if len(results) != 1 else ''} in {elapsed:.0f}s")
        if failed:
            summary += f"; {failed} failed"
        self._progress.setValue(1000)
        self._status.setText(summary + ".")
        self.library_changed.emit()

    def _on_failed(self, message: str) -> None:
        self._progress.setValue(0)
        self._status.setText(f"Analysis failed: {message}")

    def _on_cancelled(self) -> None:
        self._status.setText(
            "Stopped. Episodes already measured are cached and will not be "
            "measured again.")
        self.library_changed.emit()

    def _add_row(self, result) -> None:
        if result.status == "failed":
            cells = [result.file, f"failed — {result.error}", "—", "—"]
        else:
            cells = [result.file, "measured",
                     f"{result.metrics.scene_pacing.cuts_per_min:.1f}",
                     f"{result.metrics.sensory_load.score:.3f}"]
        item = QTreeWidgetItem(cells)
        for col in range(1, len(self.COLS)):
            item.setTextAlignment(col, Qt.AlignRight | Qt.AlignVCenter)
        item.setTextAlignment(1, Qt.AlignLeft | Qt.AlignVCenter)
        self._table.addTopLevelItem(item)
