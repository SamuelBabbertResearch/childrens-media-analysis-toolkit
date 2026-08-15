"""
ui/language.py — the Language tab: Speech and Vocabulary.

The second measurement track that stands on its own. A language study needs no
sensory pass at all, which is why `analyzer/pipeline.py` gives `language` its
own stage and `pipeline_graph.py` a "Language only" template — and why this is
a tab beside Automated coding rather than a screen inside it.

TWO GUARDRAILS THIS SCREEN CARRIES

1. **Words per minute is never shown without speech density.** WPM divides by
   *dialogue time, not runtime*: it is how fast characters speak when they
   speak, not how talkative an episode is. The two columns are adjacent and
   the note says which is which, because WPM alone invites the wrong reading.
2. **Readability and vocabulary figures are relative indices, not grades.**
   Flesch-Kincaid was validated on written prose; the tier cut-offs are Zipf
   frequency bands. Both are labelled as comparisons between episodes measured
   the same way, and neither is a claim about a viewer.

Speech comes from the cached analysis, so this screen runs no measurement of
its own. Vocabulary does run — `analyzer/vocab_complexity.py` over caption
files the user picks — on a worker thread, because spaCy takes seconds per
file.
"""

from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QFrame, QHeaderView, QLabel,
    QListWidget, QMessageBox, QPushButton, QSplitter, QStackedWidget,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from analyzer.cache import load_cached, save_cache
from analyzer.schema import EpisodeResult
from analyzer.show_index import (
    display_show_name, list_episodes, list_shows, show_key,
)

# (header, width hint, right-aligned)
SPEECH_COLUMNS = (
    ("Show", 150, False),
    ("File", 220, False),
    ("Air date", 80, False),
    ("Words per minute", 110, True),
    ("Speech density", 100, True),
    ("Total words", 90, True),
    ("Source", 70, False),
)

VOCAB_COLUMNS = (
    ("Caption file", 220, False),
    ("Status", 60, False),
    ("Flesch", 60, True),
    ("F-K grade", 70, True),
    ("Tier 1", 55, True),
    ("Tier 2", 55, True),
    ("Tier 3", 55, True),
    ("Mean AoA", 70, True),
    ("MTLD", 60, True),
)

# Column tooltips. Every one of these says what the number is and what it is
# not — the Tk build carried the same text and it is the only place a reader
# learns that a "grade level" is not a grade level.
VOCAB_HELP = {
    "Flesch": (
        "Flesch Reading Ease (0–100). Higher = simpler language.\n"
        "Computed from sentence length and syllable count.\n\n"
        "A relative index across episodes measured the same way. It is not a "
        "reading-level claim about any viewer."),
    "F-K grade": (
        "Flesch-Kincaid Grade Level, from sentence length and syllable "
        "count.\n\nValidated on written prose, not on children's television "
        "dialogue. Use it to compare episodes, not as a literal school "
        "grade."),
    "Tier 1": (
        "Everyday words — Zipf frequency ≥ 4.5 ('go', 'big', 'dog').\n"
        "Zipf = log₁₀(occurrences per billion words) + 3.\n"
        "NOUN, VERB, ADJ and ADV tokens only; proper nouns excluded."),
    "Tier 2": (
        "Cross-domain words — Zipf 3.0–4.5 ('examine', 'curious').\n"
        "Words that appear across many subjects without being everyday."),
    "Tier 3": (
        "Rare or domain-specific words — Zipf < 3.0 ('metamorphosis').\n"
        "Invented names inflate this band even though proper nouns are "
        "excluded, so read it with the episode in mind."),
    "Mean AoA": (
        "Mean Age of Acquisition in years (Kuperman et al. norms) — the "
        "average age at which speakers report first learning each content "
        "word.\n\nCovers only words present in the norm list. Blank when the "
        "norm file is not installed or coverage is zero."),
    "MTLD": (
        "Measure of Textual Lexical Diversity. Higher = more varied "
        "vocabulary, and less sensitive to text length than a raw "
        "type-token ratio.\n\nComputed on lemmatised content tokens. Blank "
        "below 50 of them."),
    "Status": (
        "ok — analysed\n"
        "skipped — the file was empty or held only stage directions\n"
        "failed — an error occurred; the message is in the row's tooltip"),
}

VOCAB_CHARTS = (
    "Word tiers (stacked)",
    "Flesch Reading Ease",
    "Flesch-Kincaid grade",
    "Mean age of acquisition",
    "MTLD (lexical diversity)",
)


def _table(columns) -> QTreeWidget:
    """A data table in this design: no root decoration, rows selected whole."""
    table = QTreeWidget()
    table.setColumnCount(len(columns))
    table.setHeaderLabels([c[0] for c in columns])
    table.setRootIsDecorated(False)
    table.setUniformRowHeights(True)
    table.setProperty("inPanel", "true")
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setFrameShape(QFrame.NoFrame)
    table.setSortingEnabled(True)
    head = table.header()
    head.setStretchLastSection(False)
    for i, (_h, width, _right) in enumerate(columns):
        head.setSectionResizeMode(i, QHeaderView.Interactive)
        table.setColumnWidth(i, width)
    return table


class _NumericItem(QTreeWidgetItem):
    """Sorts the numeric columns as numbers, not as text.

    Without this "9.5" sorts after "10.2", which is the sort of defect that
    survives review because the column still looks ordered.
    """

    def __init__(self, values, sort_values: dict[int, float]) -> None:
        super().__init__(values)
        self._sort = sort_values

    def __lt__(self, other) -> bool:
        col = self.treeWidget().sortColumn() if self.treeWidget() else 0
        mine = self._sort.get(col)
        theirs = getattr(other, "_sort", {}).get(col)
        if mine is None or theirs is None:
            return self.text(col) < other.text(col)
        return mine < theirs


# ---------------------------------------------------------------------------
# Vocabulary worker
# ---------------------------------------------------------------------------

class VocabWorker(QThread):
    """spaCy over caption files, off the interface thread.

    Each file is analysed independently and a failure is reported as a failed
    row rather than ending the run — one malformed caption file must not throw
    away the other forty results.
    """

    progress = Signal(int, int, str)
    finished_all = Signal(object)

    def __init__(self, paths: list[Path]) -> None:
        super().__init__()
        self._paths = paths
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        from analyzer.vocab_complexity import (
            NormTables, analyze_caption_file, load_norms,
        )
        try:
            norms = load_norms()
        except Exception:
            norms = NormTables(aoa={}, concreteness={},
                               aoa_path="(not found)", conc_path="(not found)",
                               aoa_n=0, conc_n=0)
        results = []
        for i, path in enumerate(self._paths, 1):
            if self._cancel:
                break
            self.progress.emit(i, len(self._paths), path.name)
            try:
                results.append(analyze_caption_file(path, norms=norms))
            except Exception as exc:            # noqa: BLE001 — shown as a row
                from analyzer.vocab_complexity import VocabResult
                results.append(VocabResult(
                    episode_id=path.stem, cc_path=str(path),
                    status="failed", error=f"{type(exc).__name__}: {exc}"))
        self.finished_all.emit(results)


# ---------------------------------------------------------------------------
# Speech
# ---------------------------------------------------------------------------

class SpeechView(QWidget):
    """Words per minute and speech density for every cached episode.

    Reads the cache; measures nothing. An episode with no caption file and no
    transcript is *named* rather than silently absent, because an empty table
    reads as "nothing here" when the truth is "no transcript yet".
    """

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self._rows: list[dict] = []
        self._conn = None

        from ui.main_window import Panel
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        panel = Panel("Episodes with speech data")
        self._count = QLabel("")
        self._count.setProperty("role", "dim")
        panel.add_header_widget(self._count)
        self._table = _table(SPEECH_COLUMNS)
        self._table.itemDoubleClicked.connect(self._open_episode)
        panel.body_layout.addWidget(self._table)
        lay.addWidget(panel, 1)

        self._note = QLabel("Choose a root folder, then press Refresh.")
        self._note.setProperty("role", "dim")
        self._note.setWordWrap(True)
        lay.addWidget(self._note)

    # -- data --
    def refresh(self) -> None:
        root = self._window._root
        if not root:
            self._note.setText("Choose a root folder first (File → Choose "
                               "Folder).")
            return
        rows: list[dict] = []
        missing: list[str] = []
        try:
            from analyzer.db import get_db
            self._conn = get_db(root)
        except Exception:
            self._conn = None            # air dates stay blank; nothing else
        for show_dir in list_shows(root):
            skey = show_key(root, show_dir)
            dname, _season = display_show_name(root, show_dir)
            for ep in list_episodes(show_dir):
                cached = load_cached(root, skey, ep.stem)
                if not cached:
                    continue
                try:
                    speech = EpisodeResult.from_dict(cached).metrics.speech
                except Exception:
                    continue
                if not speech.available:
                    speech = self._backfill(root, skey, ep, cached)
                if not speech.available:
                    missing.append(ep.name)
                    continue
                rows.append({
                    "show": dname,
                    "file": ep.name,
                    "path": ep,
                    "air_date": self._air_date(ep),
                    "wpm": speech.words_per_minute,
                    "density": speech.speech_density,
                    "words": speech.total_words,
                    "source": speech.source,
                })
        self._rows = rows
        self._fill()
        self._write_note(len(rows), len(missing))

    def _backfill(self, root, skey: str, ep: Path, cached: dict):
        """Read a caption file that appeared after the episode was analysed.

        This writes to the cache, which a refresh would not normally do. It is
        deliberate and it is what the Tk screen does: adding an `.srt` beside
        an episode is the ordinary way speech data arrives, and re-running the
        whole analysis to pick it up would cost minutes per episode.
        """
        from analyzer.speech import _find_cc_file, _parse_cc
        cc = _find_cc_file(ep)
        if cc is None:
            return EpisodeResult.from_dict(cached).metrics.speech
        try:
            speech = _parse_cc(cc, cached.get("duration_sec", 0.0))
        except Exception:
            return EpisodeResult.from_dict(cached).metrics.speech
        if speech.available:
            cached.setdefault("metrics", {})["speech"] = {
                "available": True,
                "source": speech.source,
                "words_per_minute": speech.words_per_minute,
                "speech_density": speech.speech_density,
                "total_words": speech.total_words,
            }
            try:
                save_cache(root, skey, ep.stem, cached)
            except Exception:
                pass                      # the figure still shows this session
        return speech

    def _air_date(self, ep: Path) -> str:
        """Air date from the index, when the importers have put one there.

        The connection is opened once per refresh by the caller and cached on
        the instance; a per-episode `get_db` would reopen the database for
        every row in the library.
        """
        if self._conn is None:
            return ""
        try:
            from analyzer.db import get_episode_metadata
            meta = get_episode_metadata(self._conn, str(ep))
        except Exception:
            return ""
        return (meta or {}).get("air_date") or ""

    def _fill(self) -> None:
        self._table.setSortingEnabled(False)
        self._table.clear()
        for r in self._rows:
            item = _NumericItem(
                [r["show"], r["file"], r["air_date"],
                 f"{r['wpm']:.1f}", f"{r['density']:.2f}",
                 f"{r['words']:,}", r["source"]],
                {3: r["wpm"], 4: r["density"], 5: float(r["words"])})
            for col in (3, 4, 5):
                item.setTextAlignment(col, Qt.AlignRight | Qt.AlignVCenter)
            item.setData(0, Qt.UserRole, r)
            self._table.addTopLevelItem(item)
        self._table.setSortingEnabled(True)
        self._count.setText(
            f"{len(self._rows)} episode"
            f"{'s' if len(self._rows) != 1 else ''}")

    def _write_note(self, found: int, gap: int) -> None:
        note = (
            "Words per minute divides by DIALOGUE time, not runtime — it is "
            "how fast characters speak when they speak. Speech density is the "
            "fraction of the episode that carries dialogue; read the two "
            "together.")
        if gap:
            note += (
                f"\n\n{gap} analysed episode{'s are' if gap != 1 else ' is'} "
                "not listed: no caption file and no transcript. Use Analyze → "
                "Transcribe Missing Subtitles, or enable Whisper under "
                "Settings → Speech Analysis in the Tk build.")
        elif found == 0:
            note += ("\n\nNothing to show yet. Analyse episodes first "
                     "(Automated coding → Analyze), then press Refresh.")
        self._note.setText(note)

    def _open_episode(self) -> None:
        """Double-click opens the episode's report, as the Index tab does."""
        items = self._table.selectedItems()
        if items:
            row = items[0].data(0, Qt.UserRole)
            self._window._show_indexed_episode(str(row["path"]))

    def chart(self) -> None:
        if not self._rows:
            QMessageBox.information(
                self, "Words per minute",
                "Nothing to chart yet — press Refresh first.")
            return
        from ui.chart import SpeechChartDialog
        SpeechChartDialog(self._rows, self._window).show()


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

class VocabularyView(QWidget):
    """Readability, word tiers, age of acquisition and lexical diversity."""

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self._results: list = []
        self._worker: VocabWorker | None = None

        from ui.main_window import Panel
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        split = QSplitter(Qt.Vertical)
        lay.addWidget(split, 1)

        files = Panel("Caption files to analyse")
        self._norms = QLabel("")
        self._norms.setProperty("role", "dim")
        files.add_header_widget(self._norms)
        self._files = QListWidget()
        self._files.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._files.setProperty("inPanel", "true")
        self._files.setFrameShape(QFrame.NoFrame)
        files.body_layout.addWidget(self._files)
        split.addWidget(files)

        results = Panel("Results")
        self._progress = QLabel("")
        self._progress.setProperty("role", "dim")
        results.add_header_widget(self._progress)
        self._table = _table(VOCAB_COLUMNS)
        for i, (header, _w, _r) in enumerate(VOCAB_COLUMNS):
            if header in VOCAB_HELP:
                self._table.headerItem().setToolTip(i, VOCAB_HELP[header])
        results.body_layout.addWidget(self._table)
        split.addWidget(results)
        split.setSizes([140, 400])

        self._note = QLabel(
            "Flesch-Kincaid was validated on written prose and the tier bands "
            "are word-frequency cut-offs. Both compare episodes measured the "
            "same way; neither is a statement about a reader.")
        self._note.setProperty("role", "dim")
        self._note.setWordWrap(True)
        lay.addWidget(self._note)

        self._show_norm_status()

    def _show_norm_status(self) -> None:
        from analyzer.vocab_complexity import _NORM_DIR
        aoa = (_NORM_DIR / "kuperman_aoa.csv").exists()
        conc = (_NORM_DIR / "brysbaert_concreteness.csv").exists()
        self._norms.setText(
            f"AoA norms: {'found' if aoa else 'missing — AoA stays blank'}"
            f"  ·  Concreteness: "
            f"{'found' if conc else 'missing — stays blank'}")

    # -- file list --
    def add_files(self) -> None:
        paths, _f = QFileDialog.getOpenFileNames(
            self, "Select caption files", "",
            "Caption files (*.srt *.vtt);;All files (*)")
        self._add(paths)

    def add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Select a folder of caption files")
        if not folder:
            return
        found = sorted(list(Path(folder).rglob("*.srt"))
                       + list(Path(folder).rglob("*.vtt")))
        self._add([str(p) for p in found])

    def _add(self, paths) -> None:
        existing = {self._files.item(i).text()
                    for i in range(self._files.count())}
        added = 0
        for p in paths:
            if p not in existing:
                self._files.addItem(p)
                existing.add(p)
                added += 1
        if added:
            self._progress.setText(
                f"added {added} file{'s' if added != 1 else ''}")

    def remove_selected(self) -> None:
        for item in self._files.selectedItems():
            self._files.takeItem(self._files.row(item))

    def clear_files(self) -> None:
        self._files.clear()

    # -- run --
    @property
    def running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def analyze(self) -> bool:
        """Start the run. Returns True if it actually started."""
        if self.running:
            return False
        paths = [Path(self._files.item(i).text())
                 for i in range(self._files.count())]
        if not paths:
            QMessageBox.information(
                self, "Vocabulary",
                "Add caption files first — Add Files… or Add Folder….")
            return False
        try:
            import spacy
            spacy.load("en_core_web_sm")
        except Exception:
            QMessageBox.warning(
                self, "spaCy is not ready",
                "Vocabulary analysis needs spaCy and its English model.\n\n"
                "Install them with:\n"
                "    pip install spacy\n"
                "    python -m spacy download en_core_web_sm")
            return False

        self._table.clear()
        self._results = []
        self._worker = VocabWorker(paths)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_all.connect(self._on_done)
        self._worker.start()
        return True

    def cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def _on_progress(self, done: int, total: int, name: str) -> None:
        self._progress.setText(f"analysing {done} of {total} — {name}")

    def _on_done(self, results) -> None:
        self._results = results
        self._table.setSortingEnabled(False)
        for r in results:
            self._table.addTopLevelItem(self._row(r))
        self._table.setSortingEnabled(True)
        ok = sum(1 for r in results if r.status == "ok")
        self._progress.setText(
            f"{ok} of {len(results)} analysed"
            + (f", {len(results) - ok} not" if ok != len(results) else ""))
        # NOT `self._worker = None`. This runs in a slot connected to the
        # worker's own signal, so dropping the last reference here frees the
        # QThread while it is still emitting — the process dies with no
        # traceback. Guards use isRunning(); the object is released when the
        # next run replaces it.
        self.run_finished()

    def run_finished(self) -> None:
        """Overridden by the tab to re-enable its buttons."""

    def _row(self, r) -> QTreeWidgetItem:
        name = Path(r.cc_path).name if r.cc_path else r.episode_id
        if r.status != "ok":
            item = QTreeWidgetItem([name, r.status, "", "", "", "", "", "",
                                    ""])
            if r.error:
                item.setToolTip(0, r.error)
            return item
        flat = r.to_flat_row()
        fields = (
            ("read_flesch_reading_ease", "{:.1f}"),
            ("read_flesch_kincaid_grade", "{:.1f}"),
            ("vocab_tier1_proportion", "{:.0%}"),
            ("vocab_tier2_proportion", "{:.0%}"),
            ("vocab_tier3_proportion", "{:.0%}"),
            ("vocab_aoa_mean", "{:.1f}"),
            ("div_mtld", "{:.0f}"),
        )
        texts, sorts = [name, "ok"], {}
        for i, (key, fmt) in enumerate(fields, start=2):
            value = flat.get(key)
            texts.append(fmt.format(value) if value is not None else "")
            if value is not None:
                sorts[i] = float(value)
        item = _NumericItem(texts, sorts)
        for col in range(2, len(VOCAB_COLUMNS)):
            item.setTextAlignment(col, Qt.AlignRight | Qt.AlignVCenter)
        return item

    # -- outputs --
    def export_csv(self) -> None:
        rows = [r.to_flat_row() for r in self._results if r.status == "ok"]
        if not rows:
            QMessageBox.information(self, "Export",
                                    "No successful analyses to export.")
            return
        path, _f = QFileDialog.getSaveFileName(
            self, "Save vocabulary CSV", "vocab_complexity.csv",
            "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        self._window.statusBar().showMessage(
            f"Exported {len(rows)} row{'s' if len(rows) != 1 else ''} to "
            f"{Path(path).name}", 6000)

    def chart(self, kind: str) -> None:
        ok = [r for r in self._results if r.status == "ok"]
        if not ok:
            QMessageBox.information(self, "Chart",
                                    "Analyse some caption files first.")
            return
        from ui.chart import VocabChartDialog
        VocabChartDialog(kind, ok, self._window).show()


# ---------------------------------------------------------------------------
# The tab
# ---------------------------------------------------------------------------

class LanguageTab(QWidget):
    """Speech and Vocabulary, switched from the sub-toolbar."""

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

        self.speech = SpeechView(window)
        self.vocabulary = VocabularyView(window)
        self.vocabulary.run_finished = self._vocab_finished
        self._views.add("Speech", self.speech)
        self._views.add("Vocabulary", self.vocabulary)

        # Per-view controls. Both sets live in the one sub-bar and are shown
        # with their view, so the bar always describes the screen under it.
        self._speech_controls: list[QWidget] = []
        self._vocab_controls: list[QWidget] = []

        self._bar.row.addSpacing(8)
        self._add(self._speech_controls, "Refresh", self.speech.refresh)
        self._add(self._speech_controls, "Chart WPM…", self.speech.chart)

        self._add(self._vocab_controls, "Add Files…",
                  self.vocabulary.add_files)
        self._add(self._vocab_controls, "Add Folder…",
                  self.vocabulary.add_folder)
        self._add(self._vocab_controls, "Remove Selected",
                  self.vocabulary.remove_selected)
        self._add(self._vocab_controls, "Clear List",
                  self.vocabulary.clear_files)
        self._btn_run = self._add(self._vocab_controls, "Analyze",
                                  self._run_vocab)
        self._btn_run.setProperty("primary", "true")
        self._chart_kind = QComboBox()
        self._chart_kind.addItems(VOCAB_CHARTS)
        self._vocab_controls.append(self._chart_kind)
        self._bar.row.addWidget(self._chart_kind)
        self._add(self._vocab_controls, "Show Chart",
                  lambda: self.vocabulary.chart(
                      self._chart_kind.currentText()))
        self._add(self._vocab_controls, "Export CSV…",
                  self.vocabulary.export_csv)

        self._bar.row.addStretch(1)
        lay.addWidget(self._bar)
        lay.addWidget(self._stack, 1)

        self._views.changed.connect(self._sync_controls)
        self._sync_controls()

    def _add(self, bucket: list, label: str, slot) -> QPushButton:
        button = QPushButton(label)
        button.clicked.connect(slot)
        bucket.append(button)
        self._bar.row.addWidget(button)
        return button

    def _sync_controls(self) -> None:
        speech = self._stack.currentWidget() is self.speech
        for w in self._speech_controls:
            w.setVisible(speech)
        for w in self._vocab_controls:
            w.setVisible(not speech)

    def _run_vocab(self) -> None:
        if self.vocabulary.analyze():
            self._btn_run.setEnabled(False)
            self._btn_run.setText("Analyzing…")

    def _vocab_finished(self) -> None:
        self._btn_run.setEnabled(True)
        self._btn_run.setText("Analyze")

    def show_view(self, name: str) -> None:
        self._views.show(name)

    def refresh(self) -> None:
        self.speech.refresh()
