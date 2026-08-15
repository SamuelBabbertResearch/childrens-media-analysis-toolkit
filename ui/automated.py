"""
ui/automated.py — the Automated coding tab: run the analysis, watch it run.

Analysis happens on a worker thread with a progress callback, per the
architecture rule that the interface must never freeze. The engine is called
exactly as `cli.py` calls it — `analyze_episode` then `save_cache` for one
file, `analyze_show_batch` for a folder — so there is one analysis path and
the front-end adds no logic of its own to it.

THE QUEUE

A run is a LIST of targets, each an episode or a whole show. Analysing one
selection at a time is the wrong shape for the actual work: a sampling draw
produces twenty episodes spread across four shows, and a researcher wants to
start them and walk away. The queue is the only place this screen holds state
of its own, and it holds paths — not results — so nothing in it can go stale.

A target that vanishes between queueing and running is reported as a failed
row rather than ending the run: the other nineteen episodes are still worth
measuring.

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
    QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QProgressBar,
    QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from analyzer.batch import analyze_show_batch
from analyzer.cache import load_cached, save_cache
from analyzer.engine import analyze_episode
from analyzer.schema import EpisodeResult
from analyzer.show_index import list_episodes, show_key


class _Cancelled(BaseException):
    """Not an Exception on purpose — see the module docstring."""


class AnalysisWorker(QThread):
    """Runs the engine off the interface thread."""

    progress = Signal(str, float, float)     # episode, episode frac, overall
    finished_ok = Signal(list, float)        # results, elapsed seconds
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, root: Path, targets: list[Path], config: dict,
                 force: bool) -> None:
        super().__init__()
        self._root = root
        self._targets = list(targets)
        self._config = config
        self._force = force
        self._stop = False
        self._index = 0

    def cancel(self) -> None:
        self._stop = True

    def _tick(self, name: str, ep_frac: float, overall: float) -> None:
        """Progress within one target, rescaled across the whole queue."""
        if self._stop:
            raise _Cancelled
        total = max(len(self._targets), 1)
        self.progress.emit(name, ep_frac, (self._index + overall) / total)

    def _one(self, target: Path) -> list:
        if target.is_dir():
            return analyze_show_batch(
                target, root=self._root, config=self._config,
                force=self._force, progress_cb=self._tick)
        skey = show_key(self._root, target.parent)
        result = analyze_episode(
            target, config=self._config,
            progress_cb=lambda f: self._tick(target.name, f, f))
        if result.status != "failed":
            save_cache(self._root, skey, target.stem, result.to_dict())
        return [result]

    def run(self) -> None:
        started = time.monotonic()
        results: list = []
        try:
            for self._index, target in enumerate(self._targets):
                if not target.exists():
                    # Queued, then moved or deleted. One missing file must not
                    # throw away the rest of the run.
                    results.append(EpisodeResult(
                        file=target.name, status="failed",
                        error="no longer on disk"))
                    continue
                results.extend(self._one(target))
        except _Cancelled:
            self.cancelled.emit()
            return
        except Exception as exc:            # noqa: BLE001 - reported, not hidden
            self.failed.emit(str(exc))
            return
        self.finished_ok.emit(results, time.monotonic() - started)


class TranscribeWorker(QThread):
    """Whisper over episodes that have no caption file, off the interface.

    Transcription only — it does not re-run the video or audio analysis. The
    cached result is patched with the new speech figures so the Language
    screen and the episode report show them without a full re-measure, which
    would cost minutes per episode to recompute numbers that have not changed.
    """

    progress = Signal(str, int, int)     # episode, done, total
    finished_all = Signal(int, int)      # transcribed, attempted
    failed = Signal(str)

    def __init__(self, root: Path, targets: list[tuple[Path, float]],
                 config: dict) -> None:
        super().__init__()
        self._root = root
        self._targets = targets
        self._config = config
        self._stop = False

    def cancel(self) -> None:
        self._stop = True

    def run(self) -> None:
        from analyzer.speech import transcribe_only
        done = 0
        try:
            for index, (episode, duration) in enumerate(self._targets, 1):
                if self._stop:
                    break
                self.progress.emit(episode.name, index, len(self._targets))
                result = transcribe_only(episode, duration, self._config)
                if not result.available:
                    continue
                done += 1
                key = show_key(self._root, episode.parent)
                cached = load_cached(self._root, key, episode.stem)
                if cached:
                    cached.setdefault("metrics", {})["speech"] = {
                        "available": True,
                        "source": result.source,
                        "words_per_minute": result.words_per_minute,
                        "speech_density": result.speech_density,
                        "total_words": result.total_words,
                    }
                    save_cache(self._root, key, episode.stem, cached)
        except Exception as exc:            # noqa: BLE001 — shown, not hidden
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.finished_all.emit(done, len(self._targets))


class AutomatedTab(QWidget):
    """Choose a target in the Library, then run the automated pass on it."""

    library_changed = Signal()

    COLS = ("Episode", "Result", "Cuts/min", "Sensory load")

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self._target: Path | None = None
        self._worker: AnalysisWorker | None = None
        # Paths, not results: a queue entry cannot go stale, and a target that
        # disappears before its turn is reported when its turn comes.
        self._queue: list[Path] = []
        self._transcriber: TranscribeWorker | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        from ui.main_window import Ambox, Panel, SubToolBar
        bar = SubToolBar()
        self._target_label = QLabel("No episode or show selected")
        bar.row.addWidget(self._target_label, 1)
        self._btn_queue = QPushButton("Add to Queue")
        self._btn_queue.setToolTip(
            "Queue the Library selection. Queue several, then start them all "
            "and walk away.")
        self._btn_queue.clicked.connect(self._enqueue_target)
        bar.row.addWidget(self._btn_queue)
        self._btn_run = QPushButton("Analyze")
        self._btn_run.setProperty("primary", "true")
        self._btn_run.clicked.connect(lambda: self._start(force=False))
        bar.row.addWidget(self._btn_run)
        self._btn_force = QPushButton("Re-analyze")
        self._btn_force.setToolTip(
            "Measure again even where a cached result exists.")
        self._btn_force.clicked.connect(lambda: self._start(force=True))
        bar.row.addWidget(self._btn_force)
        self._btn_transcribe = QPushButton("Transcribe Missing Subtitles")
        self._btn_transcribe.setToolTip(
            "Run Whisper only on episodes with no .srt or .vtt beside them. "
            "Transcription only — it does not re-measure the video, and "
            "episodes that already have captions are skipped.")
        self._btn_transcribe.clicked.connect(self._transcribe)
        bar.row.addWidget(self._btn_transcribe)
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

        queue_panel = Panel("Analysis queue")
        self._queue_count = QLabel("empty")
        self._queue_count.setProperty("role", "dim")
        queue_panel.add_header_widget(self._queue_count)
        self._btn_dequeue = QPushButton("Remove Selected")
        self._btn_dequeue.clicked.connect(self._remove_queued)
        queue_panel.add_header_widget(self._btn_dequeue)
        self._btn_clear = QPushButton("Clear Queue")
        self._btn_clear.clicked.connect(self.clear_queue)
        queue_panel.add_header_widget(self._btn_clear)
        self._queue_view = QListWidget()
        self._queue_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._queue_view.setProperty("inPanel", "true")
        self._queue_view.setFrameShape(QFrame.NoFrame)
        self._queue_view.setMaximumHeight(110)
        queue_panel.body_layout.addWidget(self._queue_view)
        bl.addWidget(queue_panel)

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
        self._refill_queue()

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

    # -- the queue ---------------------------------------------------------
    def enqueue(self, paths) -> int:
        """Add episodes or shows to the queue. Returns how many were added.

        Public because the Episode Sampler calls it: a drawn sample should go
        straight into the measurement pass rather than making the researcher
        re-find twenty files in the Library by hand.
        """
        existing = set(self._queue)
        added = 0
        for path in paths:
            path = Path(path)
            if path not in existing:
                self._queue.append(path)
                existing.add(path)
                added += 1
        self._refill_queue()
        return added

    def _enqueue_target(self) -> None:
        if self._target is None:
            return
        added = self.enqueue([self._target])
        self._status.setText(
            f"Queued {self._target.name}." if added
            else f"{self._target.name} is already queued.")

    def _remove_queued(self) -> None:
        for item in self._queue_view.selectedItems():
            row = self._queue_view.row(item)
            if 0 <= row < len(self._queue):
                del self._queue[row]
            self._queue_view.takeItem(row)
        self._refill_queue()

    def clear_queue(self) -> None:
        self._queue.clear()
        self._refill_queue()

    def _queue_episode_count(self) -> int:
        return sum(len(list_episodes(p)) if p.is_dir() else 1
                   for p in self._queue)

    def _refill_queue(self) -> None:
        self._queue_view.clear()
        for path in self._queue:
            if path.is_dir():
                count = len(list_episodes(path))
                label = f"{path.name}  -  show, {count} episode"
                if count != 1:
                    label += "s"
            else:
                label = f"{path.name}  -  episode"
            item = QListWidgetItem(label)
            item.setToolTip(str(path))
            self._queue_view.addItem(item)

        entries = len(self._queue)
        episodes = self._queue_episode_count()
        if not entries:
            self._queue_count.setText("empty")
        else:
            word = "entry" if entries == 1 else "entries"
            plural = "" if episodes == 1 else "s"
            self._queue_count.setText(
                f"{entries} {word} - {episodes} episode{plural}")
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        transcribing = (self._transcriber is not None
                        and self._transcriber.isRunning())
        running = transcribing or (self._worker is not None
                                   and self._worker.isRunning())
        queued = bool(self._queue)
        ready = (self._target is not None or queued) and not running
        self._btn_run.setEnabled(ready)
        self._btn_force.setEnabled(ready)
        self._btn_cancel.setEnabled(running)
        self._btn_queue.setEnabled(self._target is not None and not running)
        self._btn_transcribe.setEnabled(
            (self._target is not None or queued) and not running)
        self._btn_dequeue.setEnabled(queued and not running)
        self._btn_clear.setEnabled(queued and not running)
        # Which of the two Analyze acts on, said plainly rather than left to
        # be discovered after pressing it.
        if queued:
            word = "entry" if len(self._queue) == 1 else "entries"
            self._btn_run.setToolTip(
                f"Analyze the {len(self._queue)} queued {word}.")
        else:
            self._btn_run.setToolTip(
                "Analyze the Library selection. Nothing is queued.")

    # -- transcription -----------------------------------------------------
    def _needs_captions(self) -> list[tuple[Path, float]]:
        """Episodes in the queue or selection with no caption file beside them.

        Duration comes from the cached result when there is one, and from the
        video header otherwise — an episode can need a transcript before it has
        ever been measured.
        """
        from analyzer.speech import _find_cc_file
        targets: list[Path] = []
        for entry in (self._queue or
                      ([self._target] if self._target is not None else [])):
            targets.extend(list_episodes(entry) if entry.is_dir() else [entry])

        out: list[tuple[Path, float]] = []
        for episode in targets:
            if _find_cc_file(episode) is not None:
                continue
            duration = 0.0
            cached = load_cached(self._window._root,
                                 show_key(self._window._root, episode.parent),
                                 episode.stem)
            if cached and cached.get("status") == "ok":
                duration = cached.get("duration_sec", 0.0)
            else:
                try:
                    import cv2
                    capture = cv2.VideoCapture(str(episode))
                    fps = capture.get(cv2.CAP_PROP_FPS) or 1.0
                    frames = capture.get(cv2.CAP_PROP_FRAME_COUNT)
                    capture.release()
                    duration = frames / fps if fps else 0.0
                except Exception:
                    duration = 0.0
            out.append((episode, duration))
        return out

    def _transcribe(self) -> None:
        if self._window._root is None:
            return
        if self._transcriber is not None and self._transcriber.isRunning():
            return
        try:
            import faster_whisper                      # noqa: F401
        except ImportError:
            QMessageBox.information(
                self, "Whisper is not installed",
                "Transcription needs faster-whisper.\n\n"
                "Install it with:  pip install faster-whisper\n\n"
                "Episodes with an .srt or .vtt beside them already have "
                "speech data and do not need it.")
            return
        targets = self._needs_captions()
        if not targets:
            self._status.setText(
                "Every episode in the selection already has a caption file — "
                "nothing to transcribe.")
            return
        answer = QMessageBox.question(
            self, "Transcribe missing subtitles",
            f"{len(targets)} episode{'s have' if len(targets) != 1 else ' has'} "
            f"no caption file.\n\n"
            f"Whisper takes a few minutes per episode on CPU. It writes an "
            f".srt beside each video and updates the cached speech figures; "
            f"it does not re-measure the video.\n\nStart?")
        if answer != QMessageBox.Yes:
            return
        self._progress.setValue(0)
        self._transcriber = TranscribeWorker(
            self._window._root, targets, self._window._cfg)
        self._transcriber.progress.connect(self._on_transcribe_progress)
        self._transcriber.finished_all.connect(self._on_transcribed)
        self._transcriber.failed.connect(self._on_failed)
        self._transcriber.finished.connect(self._sync_buttons)
        self._transcriber.start()
        self._sync_buttons()

    def _on_transcribe_progress(self, name: str, done: int,
                                total: int) -> None:
        self._progress.setValue(int(done / max(total, 1) * 1000))
        self._status.setText(f"Transcribing {name} — {done} of {total}")

    def _on_transcribed(self, done: int, attempted: int) -> None:
        self._progress.setValue(1000)
        self._status.setText(
            f"Transcribed {done} of {attempted} episode"
            f"{'s' if attempted != 1 else ''}."
            + ("" if done == attempted else
               "  The rest produced no usable speech."))
        self.library_changed.emit()

    # -- running ----------------------------------------------------------
    def _start(self, force: bool) -> None:
        """Run the queue if there is one, otherwise the Library selection."""
        if self._window._root is None:
            return
        targets = list(self._queue) or (
            [self._target] if self._target is not None else [])
        if not targets:
            return
        self._table.clear()
        self._progress.setValue(0)
        word = "entry" if len(targets) == 1 else "entries"
        self._status.setText(f"Starting {len(targets)} {word}…")
        self._worker = AnalysisWorker(
            self._window._root, targets, self._window._cfg, force)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.finished.connect(self._sync_buttons)
        self._worker.start()
        self._sync_buttons()

    def _cancel(self) -> None:
        if self._transcriber is not None and self._transcriber.isRunning():
            self._transcriber.cancel()
            self._status.setText("Finishing the current transcript, then "
                                 "stopping…")
            return
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
        # The queue is spent; leaving it filled would re-run everything on the
        # next press of Analyze.
        self.clear_queue()
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
