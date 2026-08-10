"""
ui/main_window.py — the Qt shell: toolbar, tabs, Library grid, Results report.

The first screen ported for real. Reads the same library, the same cache, and
the same preferences as the Tk front-end, so both can be run against one
project and compared directly.

Tabs that have not been ported yet say so plainly rather than showing an empty
frame — during a migration an unported screen and a broken screen must not look
alike.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QMainWindow, QMessageBox, QPushButton, QSplitter, QTabWidget,
    QTextBrowser, QToolBar, QTreeView, QVBoxLayout, QWidget,
)

from analyzer.cache import load_cached
from analyzer.config_loader import load_config
from analyzer.prefs import get_pref, set_pref
from analyzer.schema import EpisodeResult
from analyzer.show_index import (
    list_category_shows, list_episodes, list_shows, list_top_level, show_key,
)
from ui import theme
from ui.report import episode_html
from ui.tokens import METRICS, color

# Column order for the library grid.
COL_NAME, COL_STATUS, COL_LENGTH, COL_ADDED = range(4)

UNPORTED = {
    "Pipeline": "The pipeline editor is still on the Tkinter build.",
    "Index": "The searchable index is still on the Tkinter build.",
    "Automated coding": "Analysis actions are still on the Tkinter build.",
    "Human coding": "Coding, validation, and agreement are still on the "
                    "Tkinter build.",
    "Trials": "The trials registry is still on the Tkinter build.",
}


def _fmt_duration(seconds: float) -> str:
    if not seconds:
        return "—"
    m, s = divmod(int(round(seconds)), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _fmt_added(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
    except OSError:
        return ""


class Ambox(QFrame):
    """A MediaWiki-style notice: tinted panel with an accent rule on the left."""

    def __init__(self, title: str, body: str, kind: str = "info") -> None:
        super().__init__()
        self.setProperty("ambox", kind)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 10, 9)
        lay.setSpacing(2)
        head = QLabel(title)
        head.setStyleSheet(
            f"color:{color('info_text')}; font-weight:bold;")
        lay.addWidget(head)
        text = QLabel(body)
        text.setWordWrap(True)
        lay.addWidget(text)


class Panel(QFrame):
    """A titled content panel: header strip over a body, hairline framed.

    `body_layout` is where callers put their content. The header carries a
    title on the left and optional widgets on the right (a count, a button).
    """

    def __init__(self, title: str) -> None:
        super().__init__()
        self.setProperty("panel", "true")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._header = QWidget()
        self._header.setStyleSheet(
            f"background:{color('panel_header')};"
            f"border-bottom:1px solid {color('panel_border')};")
        hh = QHBoxLayout(self._header)
        hh.setContentsMargins(6, 3, 5, 3)
        hh.setSpacing(6)
        self._title = QLabel(title)
        self._title.setTextFormat(Qt.PlainText)
        self._title.setStyleSheet("font-weight:bold; border:none;")
        hh.addWidget(self._title)
        hh.addStretch(1)
        self._header_row = hh
        outer.addWidget(self._header)

        body = QWidget()
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)
        outer.addWidget(body, 1)

    def set_title(self, text: str) -> None:
        self._title.setText(text)

    def add_header_widget(self, widget: QWidget) -> None:
        widget.setStyleSheet(widget.styleSheet() + ";border:none;")
        self._header_row.addWidget(widget)


class SubToolBar(QFrame):
    """Per-tab controls, sitting directly under the tab strip."""

    def __init__(self) -> None:
        super().__init__()
        self.setProperty("subbar", "true")
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(8, 4, 8, 4)
        self.row.setSpacing(6)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Children's Media Analysis Toolkit (CMAT)")
        self.resize(1280, 820)

        self._cfg = load_config()
        self._root: Path | None = None

        self._build_menu()
        self._build_toolbar()
        self._build_tabs()
        self._build_status_bar()

        # Reopen the last library, exactly as the Tk build does.
        saved = get_pref("last_root_folder")
        if saved and Path(saved).is_dir():
            QTimer.singleShot(0, lambda: self.set_root(Path(saved)))

    # ---- chrome ----

    def _build_menu(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("&File")
        act_open = QAction("Choose Root Folder…", self)
        act_open.triggered.connect(self.choose_root)
        file_menu.addAction(act_open)
        file_menu.addSeparator()
        act_quit = QAction("E&xit", self)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        help_menu = bar.addMenu("&Help")
        act_about = QAction("About CMAT", self)
        act_about.triggered.connect(lambda: QMessageBox.information(
            self, "About CMAT",
            "Children's Media Analysis Toolkit.\n\n"
            "Measures formal features of children's television — pacing, "
            "colour, motion, flashing, audio, language — and supports "
            "structured hand-coding.\n\n"
            "It reports measurements of the stimulus. It does not rate "
            "appropriateness, target age, or educational value."))
        help_menu.addAction(act_about)

    def _build_status_bar(self) -> None:
        """Message on the left, state on the right."""
        sb = self.statusBar()
        sb.setSizeGripEnabled(True)
        self._state = QLabel("Ready")
        self._state.setStyleSheet(f"color:{color('text_dim')};")
        sb.addPermanentWidget(self._state)
        sb.showMessage("Ready.")

    def _build_toolbar(self) -> None:
        tb = QToolBar()
        tb.setMovable(False)
        self.addToolBar(tb)

        tb.addWidget(QLabel("Root folder:"))
        choose = QPushButton("Choose Folder...")
        choose.clicked.connect(self.choose_root)
        tb.addWidget(choose)

        self._root_label = QLabel("(none chosen)")
        self._root_label.setProperty("pathDisplay", "true")
        self._root_label.setTextFormat(Qt.PlainText)
        tb.addWidget(self._root_label)

        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy().Expanding,
                             spacer.sizePolicy().verticalPolicy().Preferred)
        tb.addWidget(spacer)

        tb.addWidget(QLabel("Preset:"))
        self._preset = QComboBox()
        self._preset.addItems(list(self._cfg.get("presets", {})) or
                              ["General / All Ages"])
        tb.addWidget(self._preset)

        for label in ("Episode Sampler...", "Settings..."):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, n=label: self._not_yet(n))
            tb.addWidget(b)

    def _build_tabs(self) -> None:
        self._tabs = QTabWidget()
        self.setCentralWidget(self._tabs)

        for name in ("Pipeline",):
            self._tabs.addTab(self._placeholder(name), name)

        self._tabs.addTab(self._build_library(), "Library")

        for name in ("Index", "Automated coding", "Human coding", "Trials"):
            self._tabs.addTab(self._placeholder(name), name)

        self._tabs.setCurrentIndex(1)

    def _placeholder(self, name: str) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.addWidget(Ambox(
            f"{name} — not yet ported",
            UNPORTED.get(name, "") + "  Run the Tkinter build (python gui.py) "
            "to use it; both read the same project.", "warn"))
        lay.addStretch(1)
        return page

    # ---- library ----

    def _build_library(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        self._hint = Ambox(
            "GETTING STARTED",
            "1. Choose Folder… — pick the folder that CONTAINS your show "
            "folders, not a show folder itself.    2. Pick a show or episode "
            "below to see its analysis.")
        lay.addWidget(self._hint)

        split = QSplitter(Qt.Horizontal)
        lay.addWidget(split, 1)

        left = Panel("Shows / Episodes")
        self._count = QLabel("no library loaded")
        self._count.setProperty("role", "dim")
        left.add_header_widget(self._count)

        self._model = QStandardItemModel()
        self._model.setHorizontalHeaderLabels(
            ["Name", "Status", "Episodes / Length", "Added"])
        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setAlternatingRowColors(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setIndentation(METRICS["row_h"] - 2)
        self._tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        hv = self._tree.header()
        hv.setSectionResizeMode(COL_NAME, QHeaderView.Stretch)
        for col in (COL_STATUS, COL_LENGTH, COL_ADDED):
            hv.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self._tree.setFrameShape(QFrame.NoFrame)
        self._tree.selectionModel().selectionChanged.connect(self._on_select)
        left.body_layout.addWidget(self._tree)
        split.addWidget(left)

        right = Panel("Results")
        self._btn_chart = QPushButton("Show Chart")
        self._btn_chart.setProperty("primary", "true")
        self._btn_chart.setEnabled(False)
        right.add_header_widget(self._btn_chart)

        self._report = QTextBrowser()
        self._report.setOpenExternalLinks(False)
        self._report.setFrameShape(QFrame.NoFrame)
        self._report.setHtml(
            f"<p style='color:{color('text_dim')}'>Choose a show or episode "
            f"on the left.</p>")
        right.body_layout.addWidget(self._report)
        split.addWidget(right)

        # 46 / 54, matching the reference layout.
        split.setStretchFactor(0, 46)
        split.setStretchFactor(1, 54)
        return page

    # ---- data ----

    def choose_root(self) -> None:
        QMessageBox.information(
            self, "Choose Root Folder",
            "Select the folder that CONTAINS your show folders.\n\n"
            "  Project/\n      Little Bear/\n          episode01.mp4\n\n"
            "Do NOT navigate into a show folder — select its parent.")
        chosen = QFileDialog.getExistingDirectory(
            self, "Select the ROOT folder (the one containing show folders)")
        if chosen:
            self.set_root(Path(chosen))
            set_pref("last_root_folder", chosen)

    def set_root(self, folder: Path) -> None:
        self._root = folder
        self._root_label.setText(str(folder))
        self._hint.setVisible(False)
        self.populate()

    def populate(self) -> None:
        self._model.removeRows(0, self._model.rowCount())
        if not self._root:
            self._count.setText("no library loaded")
            return

        shows = episodes = 0
        for kind, path in list_top_level(self._root):
            if kind == "category":
                node = self._row(path.name, "", "", _fmt_added(path),
                                 bold=True)
                self._model.appendRow(node)
                for show_dir in list_category_shows(path):
                    s, e = self._add_show(node[0], show_dir)
                    shows += s
                    episodes += e
            else:
                s, e = self._add_show(None, path)
                shows += s
                episodes += e

        self._tree.expandAll()
        self._count.setText(
            f"{shows} show{'s' if shows != 1 else ''}, "
            f"{episodes} episode{'s' if episodes != 1 else ''}")
        self.statusBar().showMessage(
            f"{shows} shows, {episodes} episodes in {self._root}")

    def _row(self, name, status, length, added, bold=False, payload=None):
        cells = [QStandardItem(str(v)) for v in (name, status, length, added)]
        for cell in cells:
            cell.setEditable(False)
            if bold:
                f = cell.font()
                f.setBold(True)
                cell.setFont(f)
        if payload is not None:
            cells[0].setData(str(payload), Qt.UserRole)
        return cells

    def _add_show(self, parent, show_dir: Path) -> tuple[int, int]:
        skey = show_key(self._root, show_dir)
        eps = list_episodes(show_dir)
        analyzed = 0
        rows = []
        for ep in eps:
            cached = load_cached(self._root, skey, ep.stem)
            if cached:
                analyzed += 1
            status = "Analyzed" if cached else "Not measured"
            row = self._row(ep.name, status,
                            _fmt_duration((cached or {}).get("duration_sec", 0)),
                            _fmt_added(ep), payload=ep)
            row[COL_STATUS].setForeground(
                Qt.GlobalColor.darkBlue if cached else Qt.GlobalColor.darkGray)
            rows.append(row)

        head = self._row(show_dir.name,
                         f"{analyzed}/{len(eps)} analyzed" if eps else "empty",
                         f"{len(eps)} ep." if eps else "—",
                         _fmt_added(show_dir), bold=True)
        for r in rows:
            head[0].appendRow(r)
        if parent is None:
            self._model.appendRow(head)
        else:
            parent.appendRow(head)
        return 1, len(eps)

    def _on_select(self, *_args) -> None:
        idx = self._tree.selectionModel().currentIndex()
        if not idx.isValid():
            return
        payload = self._model.itemFromIndex(idx.siblingAtColumn(COL_NAME)).data(
            Qt.UserRole)
        if not payload:
            self._report.setHtml(
                "<p style='color:#54595d'>Select an episode to see its "
                "analysis.</p>")
            return
        ep = Path(payload)
        cached = load_cached(self._root, show_key(self._root, ep.parent),
                             ep.stem)
        if not cached:
            self._report.setHtml(
                f"<p style='color:#54595d'><b>{ep.name}</b><br>"
                "Not analyzed yet. Run the analysis from the Tkinter build "
                "(Automated coding → Analyze Episode); the result will appear "
                "here.</p>")
            return
        result = EpisodeResult.from_dict(cached)
        events = None
        try:
            from analyzer.event_coding import latest_rates_for_stem
            events = latest_rates_for_stem(ep.stem)
        except Exception:
            pass
        self._report.setHtml(episode_html(result, events=events))

    def _not_yet(self, what: str) -> None:
        QMessageBox.information(
            self, "Not yet ported",
            f"{what.rstrip('.')} is still on the Tkinter build.\n\n"
            "Run  python gui.py  to use it — both builds read the same "
            "project folder, cache, and settings.")


def run() -> int:
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    theme.apply(app)
    win = MainWindow()
    win.show()
    return app.exec()
