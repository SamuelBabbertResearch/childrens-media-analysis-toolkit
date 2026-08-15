"""
ui/metadata_import.py — import episode metadata from Wikipedia or TVMaze.

One dialog for both sources, because after the fetch they are the same job:
each returns a list of `WikiEpisode`, both go through `match_to_files`, and
both end at `upsert_episode_metadata`. Two near-identical dialogs would be two
places for the matching rules to drift apart.

WHY THIS MATTERS MORE THAN IT LOOKS
-----------------------------------
Air dates are not decoration. They drive era stratification in the Episode
Sampler and the timeline the published corpus is split along, and they fill
the air-date column on the Language screen. Retyping a season of them is how
they end up wrong, so they are imported.

MATCHING IS A GUESS, AND SAYS SO
--------------------------------
`match_to_files` matches on season+episode numbers in the filename first
(exact), then falls back to fuzzy title similarity down to a ratio of 0.45.
A fuzzy match is a guess about which file is which episode, and applying it
writes a wrong air date that nothing downstream will ever question. So:

* every row shows how it was matched and with what score;
* fuzzy matches are counted in a warning above the table;
* every row can be unchecked, and nothing unchecked is written.

Fetching happens on a worker thread — it is network I/O, and the interface
must never freeze.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from analyzer.show_index import list_episodes, list_shows, show_key
from analyzer.wiki_importer import match_to_files
from ui.modal import ModalDialogFrame

DIALOG_W = 860
DIALOG_H = 620

COLUMNS = ("Season", "Episode", "Title", "Air date", "Matched file",
           "How matched")

SOURCES = (
    ("wiki_url", "Wikipedia — episode-list URL",
     "Paste the URL of a “List of … episodes” page. Only wikipedia.org "
     "links are accepted."),
    ("wiki_file", "Wikipedia — saved HTML file",
     "Use a page you have already saved. Save it as rendered HTML, not "
     "wikitext — an action=raw URL will not parse."),
    ("tvmaze", "TVMaze — show URL or numeric ID",
     "Paste a tvmaze.com/shows/<id>/… URL, or just the ID. Specials are "
     "skipped: they rarely carry numbers that match filenames."),
)


class FetchWorker(QThread):
    """Network I/O off the interface thread."""

    done = Signal(object)          # list[WikiEpisode]
    failed = Signal(str)

    def __init__(self, source: str, value: str) -> None:
        super().__init__()
        self._source = source
        self._value = value

    def run(self) -> None:
        try:
            episodes = self._fetch()
        except Exception as exc:            # noqa: BLE001 — shown, not hidden
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.done.emit(episodes)

    def _fetch(self) -> list:
        if self._source == "wiki_url":
            from analyzer.wiki_importer import (
                fetch_wikipedia_html, parse_wikipedia_html,
            )
            return parse_wikipedia_html(fetch_wikipedia_html(self._value))
        if self._source == "wiki_file":
            from analyzer.wiki_importer import parse_wikipedia_episode_list
            return parse_wikipedia_episode_list(Path(self._value))
        from analyzer.tvmaze_importer import extract_show_id, fetch_episodes
        show_id = extract_show_id(self._value)
        if show_id is None:
            if not self._value.strip().isdigit():
                raise ValueError(
                    "That is neither a tvmaze.com/shows/<id> URL nor a "
                    "numeric show ID.")
            show_id = int(self._value.strip())
        return fetch_episodes(show_id)


class MetadataImportDialog(QDialog):
    """Fetch an episode list, match it to files, write the matches you keep."""

    def __init__(self, window, parent=None) -> None:
        super().__init__(parent or window)
        self.setModal(True)
        self.resize(DIALOG_W, DIALOG_H)
        self._window = window
        self._worker: FetchWorker | None = None
        self._matches: list = []
        self.applied = 0

        body = ModalDialogFrame.install(self, "Import episode metadata",
                                        buttons=("min", "max", "close"))

        note = QLabel(
            "Air dates drive era stratification in the Episode Sampler and "
            "the air-date column on the Language screen. They are stored in "
            "the index, not the cache, so re-analysing an episode does not "
            "erase them.")
        note.setWordWrap(True)
        note.setProperty("role", "dim")
        body.addWidget(note)

        body.addWidget(self._source_row())
        body.addWidget(self._show_row())

        self._hint = QLabel(SOURCES[0][2])
        self._hint.setWordWrap(True)
        self._hint.setProperty("role", "dim")
        body.addWidget(self._hint)

        self._warning = QLabel("")
        self._warning.setWordWrap(True)
        body.addWidget(self._warning)

        self._table = QTreeWidget()
        self._table.setColumnCount(len(COLUMNS))
        self._table.setHeaderLabels(list(COLUMNS))
        self._table.setRootIsDecorated(False)
        self._table.setUniformRowHeights(True)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setFrameShape(QFrame.NoFrame)
        body.addWidget(self._table, 1)

        self._status = QLabel("Choose a source and a show, then Fetch.")
        self._status.setProperty("role", "dim")
        self._status.setWordWrap(True)
        body.addWidget(self._status)

        row = ModalDialogFrame.add_action_bar(self)
        self._btn_uncheck = QPushButton("Uncheck Fuzzy Matches")
        self._btn_uncheck.setToolTip(
            "A fuzzy match is a guess from title similarity. Unchecking them "
            "writes only the rows matched by season and episode number.")
        self._btn_uncheck.setEnabled(False)
        self._btn_uncheck.clicked.connect(self._uncheck_fuzzy)
        row.addWidget(self._btn_uncheck)
        row.addStretch(1)
        self._btn_fetch = QPushButton("Fetch")
        self._btn_fetch.clicked.connect(self._fetch)
        row.addWidget(self._btn_fetch)
        self._btn_apply = QPushButton("Apply Checked")
        self._btn_apply.setProperty("primary", "true")
        self._btn_apply.setEnabled(False)
        self._btn_apply.clicked.connect(self._apply)
        row.addWidget(self._btn_apply)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        row.addWidget(close)

    # -- inputs ------------------------------------------------------------
    def _source_row(self) -> QWidget:
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(QLabel("Source:"))
        self._source = QComboBox()
        for key, label, _hint in SOURCES:
            self._source.addItem(label, key)
        self._source.currentIndexChanged.connect(self._source_changed)
        row.addWidget(self._source)
        self._value = QLineEdit()
        self._value.setPlaceholderText(
            "https://en.wikipedia.org/wiki/List_of_..._episodes")
        row.addWidget(self._value, 1)
        self._btn_browse = QPushButton("Browse…")
        self._btn_browse.setVisible(False)
        self._btn_browse.clicked.connect(self._browse)
        row.addWidget(self._btn_browse)
        return page

    def _show_row(self) -> QWidget:
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(QLabel("Match against:"))
        self._show = QComboBox()
        self._show.setToolTip(
            "The episode files the fetched list is matched to. Pick the "
            "folder these episodes actually live in.")
        root = self._window._root
        if root:
            for show_dir in list_shows(root):
                count = len(list_episodes(show_dir))
                self._show.addItem(
                    f"{show_key(root, show_dir)}  ({count} episode"
                    f"{'s' if count != 1 else ''})", str(show_dir))
        row.addWidget(self._show, 1)
        return page

    def _source_changed(self) -> None:
        key = self._source.currentData()
        self._hint.setText(dict((k, h) for k, _l, h in SOURCES)[key])
        self._btn_browse.setVisible(key == "wiki_file")
        self._value.setPlaceholderText(
            "https://en.wikipedia.org/wiki/List_of_..._episodes"
            if key == "wiki_url" else
            "path to a saved .html file" if key == "wiki_file" else
            "https://www.tvmaze.com/shows/431/... or 431")

    def _browse(self) -> None:
        chosen, _f = QFileDialog.getOpenFileName(
            self, "Saved Wikipedia page", "", "HTML (*.html *.htm)")
        if chosen:
            self._value.setText(chosen)

    # -- fetching ----------------------------------------------------------
    def _fetch(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        value = self._value.text().strip()
        if not value:
            QMessageBox.information(self, "Import",
                                    "Enter a URL, an ID, or a file first.")
            return
        if self._show.count() == 0:
            QMessageBox.information(
                self, "Import",
                "No shows were found under the root folder — choose a root "
                "folder with episodes in it first.")
            return
        self._btn_fetch.setEnabled(False)
        self._btn_fetch.setText("Fetching…")
        self._status.setText("Fetching the episode list…")
        self._worker = FetchWorker(self._source.currentData(), value)
        self._worker.done.connect(self._fetched)
        self._worker.failed.connect(self._fetch_failed)
        self._worker.start()

    def _reset_fetch_button(self) -> None:
        # NOT `self._worker = None` — see ui/automated.py. Freeing a QThread
        # from a slot connected to it kills the process.
        self._btn_fetch.setEnabled(True)
        self._btn_fetch.setText("Fetch")

    def _fetch_failed(self, message: str) -> None:
        self._reset_fetch_button()
        self._status.setText(f"Fetch failed: {message}")
        QMessageBox.warning(self, "Could not fetch the episode list", message)

    def _fetched(self, episodes) -> None:
        self._reset_fetch_button()
        if not episodes:
            self._status.setText(
                "The page fetched, but no episode rows were recognised in "
                "it. Wikipedia's episode tables vary; try the TVMaze source "
                "for this show.")
            return
        show_dir = Path(self._show.currentData())
        self._matches = match_to_files(episodes, list_episodes(show_dir))
        self._fill()

    # -- the table ---------------------------------------------------------
    def _fill(self) -> None:
        self._table.clear()
        fuzzy = unmatched = 0
        for match in self._matches:
            wiki = match.wiki_ep
            if match.local_file is None or match.match_type == "none":
                how = "no file matched"
                unmatched += 1
            elif match.match_type == "number":
                how = "season + episode number"
            else:
                how = f"title similarity {match.score:.2f}"
                fuzzy += 1
            item = QTreeWidgetItem([
                str(wiki.season), str(wiki.episode_num), wiki.title or "—",
                wiki.air_date or "—",
                match.local_file.name if match.local_file else "—", how])
            item.setData(0, Qt.UserRole, match)
            matched = match.local_file is not None \
                and match.match_type != "none"
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(0, Qt.Checked if matched else Qt.Unchecked)
            if not matched:
                item.setDisabled(True)
            self._table.addTopLevelItem(item)

        head = self._table.header()
        head.setStretchLastSection(False)
        for col in range(len(COLUMNS)):
            head.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        head.setSectionResizeMode(2, QHeaderView.Stretch)

        total = len(self._matches)
        self._btn_apply.setEnabled(total > unmatched)
        self._btn_uncheck.setEnabled(fuzzy > 0)
        self._status.setText(
            f"{total} episode{'s' if total != 1 else ''} in the list; "
            f"{total - unmatched} matched to a file.")
        if fuzzy:
            self._warning.setText(
                f"⚠  {fuzzy} row{'s were' if fuzzy != 1 else ' was'} matched "
                f"by TITLE SIMILARITY, not by episode number. That is a "
                f"guess: applying a wrong one writes an air date that nothing "
                f"downstream will question. Check the “How matched” column, "
                f"or uncheck them all below.")
        else:
            self._warning.setText("")

    def _uncheck_fuzzy(self) -> None:
        for row in range(self._table.topLevelItemCount()):
            item = self._table.topLevelItem(row)
            match = item.data(0, Qt.UserRole)
            if match is not None and match.match_type == "title":
                item.setCheckState(0, Qt.Unchecked)

    # -- applying ----------------------------------------------------------
    def _apply(self) -> None:
        conn = self._window._db()
        if conn is None:
            QMessageBox.warning(
                self, "No index",
                "The index could not be opened — choose a root folder first.")
            return
        from analyzer.db import upsert_episode_metadata

        applied = 0
        for row in range(self._table.topLevelItemCount()):
            item = self._table.topLevelItem(row)
            if item.checkState(0) != Qt.Checked:
                continue
            match = item.data(0, Qt.UserRole)
            if match is None or match.local_file is None:
                continue
            try:
                upsert_episode_metadata(
                    conn, str(match.local_file), match.wiki_ep.air_date,
                    match.wiki_ep.season, match.wiki_ep.episode_num)
            except Exception as exc:        # noqa: BLE001 — shown, not hidden
                QMessageBox.warning(self, "Could not write metadata",
                                    f"{match.local_file.name}: {exc}")
                return
            applied += 1

        self.applied = applied
        self._status.setText(
            f"Wrote metadata for {applied} episode"
            f"{'s' if applied != 1 else ''}.")
        if applied:
            self.accept()
