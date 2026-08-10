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
from PySide6.QtGui import (
    QAction, QFont, QIcon, QKeySequence,
    QPainter, QPixmap, QShortcut, QStandardItem, QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QMainWindow, QMenu, QMenuBar, QMessageBox,
    QPushButton, QSplitter, QTabWidget,
    QTextBrowser, QToolBar, QTreeView, QVBoxLayout, QWidget,
)

from analyzer.cache import load_cached
from analyzer.config_loader import load_config
from analyzer.prefs import get_pref, set_pref
from analyzer.schema import EpisodeResult
from analyzer.show_index import (
    list_category_shows, list_episodes, list_shows, list_top_level, show_key,
)
from ui import native_frame, theme
from analyzer.pipeline import build_pipelines
from analyzer.pipeline_graph import (
    NODE_TYPES, default_doc, delete_doc, duplicate_doc, list_docs,
    node_type, save_doc, unique_name,
)
from ui.modal import WindowTitleBar
from ui.pipeline_view import Canvas, ZoomPill
from ui.welcome import WelcomeDialog
from ui.inspector import Inspector
from ui.report import episode_html
from ui.automated import AutomatedTab
from ui.index_tab import IndexTab
from ui.settings import SettingsDialog
from ui.tokens import METRICS, color

# The reference marks folders and episodes with these two glyphs.
FOLDER = "📁"
FILE = "📄"

# Column order for the library grid.
COL_NAME, COL_STATUS, COL_LENGTH, COL_ADDED = range(4)

UNPORTED = {
    "Pipeline": "The pipeline editor is still on the Tkinter build.",
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


_ICON_CACHE: dict[tuple[str, int], "QIcon"] = {}


def _glyph_icon(char: str, px: int = 13) -> QIcon:
    """The reference marks folders and files with a glyph; this is that glyph.

    Rendered to a pixmap rather than prefixed to the item text, so the model's
    text stays the name alone and sorting, filtering and accessible names are
    not polluted with a decoration.
    """
    key = (char, px)
    if key not in _ICON_CACHE:
        size = px + 3
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        f = QFont("Segoe UI Emoji")
        f.setPixelSize(px)
        p.setFont(f)
        p.drawText(pm.rect(), Qt.AlignCenter, char)
        p.end()
        _ICON_CACHE[key] = QIcon(pm)
    return _ICON_CACHE[key]


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

        self._build_title_bar()
        self._build_menu()
        self._build_toolbar()
        self._build_tabs()
        self._build_status_bar()

        # Reopen the last library, exactly as the Tk build does.
        saved = get_pref("last_root_folder")
        if saved and Path(saved).is_dir():
            QTimer.singleShot(0, lambda: self.set_root(Path(saved)))

        # The starting-layout wizard is the first screen, after the window is
        # up and the library has been restored — it offers to name a pipeline
        # against the ones already there, so it needs the root first.
        if get_pref("show_welcome_on_start", True):
            QTimer.singleShot(0, self.show_welcome)

    def show_welcome(self) -> None:
        """Offer a starting layout. Declining leaves the window as it is."""
        existing = [d.name for d in getattr(self, "_docs", [])]
        dialog = WelcomeDialog(existing, self)
        if dialog.exec() != QDialog.Accepted or dialog.doc is None:
            return
        save_doc(dialog.doc, self._root)
        self._docs.append(dialog.doc)
        self._pipe_pick.addItem(dialog.doc.name)
        self._pipe_pick.setCurrentIndex(len(self._docs) - 1)
        self._tabs.setCurrentIndex(0)
        self.statusBar().showMessage(
            f"Created the pipeline {dialog.doc.name!r}. Use Manage to link it "
            f"to an episode sample.", 8000)

    # ---- chrome ----

    def _build_title_bar(self) -> None:
        """Attach the reference's title strip, or keep the native frame.

        The strip is only installed if the Win32 hook attaches. Everywhere else
        — another platform, an older Windows, a ctypes failure — the window
        keeps its ordinary title bar, which is a worse match for the reference
        and a much better outcome than a window that cannot be moved.
        """
        self._title_bar = WindowTitleBar(self)
        self._menubar = QMenuBar()
        attached = native_frame.install(
            self, METRICS["titlebar_h"], self._title_bar.is_caption)
        if not attached:
            self._title_bar = None
            return

        # The strip has to sit ABOVE the menu bar, and QMainWindow keeps the
        # menu bar topmost no matter where a toolbar is added. So the two are
        # stacked into one widget and installed as the menu area together.
        holder = QWidget()
        v = QVBoxLayout(holder)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self._title_bar)
        v.addWidget(self._menubar)
        self.setMenuWidget(holder)

    def _build_menu(self) -> None:
        bar = getattr(self, "_menubar", None) or self.menuBar()
        file_menu = bar.addMenu("&File")
        act_open = QAction("Choose Root Folder…", self)
        act_open.triggered.connect(self.choose_root)
        file_menu.addAction(act_open)
        act_settings = QAction("Settings…", self)
        act_settings.triggered.connect(self.open_settings)
        file_menu.addAction(act_settings)
        act_new = QAction("New Pipeline from Layout…", self)
        act_new.triggered.connect(self.show_welcome)
        file_menu.addAction(act_new)
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

    def open_settings(self) -> None:
        """Scoring settings. Accepting re-scores from cache; nothing is stale.

        The edited config is held in memory rather than written to
        config.json: that file is versioned and shared, and a preference set
        while looking at one project should not silently change it for
        everyone. Save as Preset is the deliberate way to keep values.
        """
        dialog = SettingsDialog(self._cfg, self)
        if dialog.exec() != QDialog.Accepted or not dialog.rescore:
            return
        self._cfg = dialog.config
        self.populate()
        self.statusBar().showMessage(
            "Re-scored from cache with the new weights. No episode needs "
            "re-analysing — these are scoring settings.", 8000)

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

        sampler = QPushButton("Episode Sampler...")
        sampler.setEnabled(False)
        sampler.setToolTip("Still on the Tkinter build — run python gui.py")
        tb.addWidget(sampler)
        settings = QPushButton("Settings...")
        settings.clicked.connect(self.open_settings)
        tb.addWidget(settings)
        for label in ():
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, n=label: self._not_yet(n))
            tb.addWidget(b)

    def _build_tabs(self) -> None:
        self._tabs = QTabWidget()
        self.setCentralWidget(self._tabs)

        # Built first: the Library's selection handler sets its target, so it
        # must exist before that signal can fire.
        self._automated = AutomatedTab(self)
        self._automated.library_changed.connect(self._on_analysis_finished)

        self._tabs.addTab(self._build_pipeline(), "Pipeline")
        self._library_page = self._build_library()
        self._tabs.addTab(self._library_page, "Library")

        self._index = IndexTab(self)
        self._index.episode_chosen.connect(self._show_indexed_episode)
        self._tabs.addTab(self._index, "Index")
        self._tabs.addTab(self._automated, "Automated coding")
        for name in ("Human coding", "Trials"):
            self._tabs.addTab(self._placeholder(name), name)

        self._tabs.setCurrentIndex(1)

    # ---- pipeline ----

    def _build_pipeline(self) -> QWidget:
        """The pipeline workbench: sub-toolbar, node canvas, inspector."""
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        bar = SubToolBar()
        bar.row.addWidget(QLabel("Pipeline:"))
        self._pipe_pick = QComboBox()
        self._pipe_pick.setMinimumWidth(160)
        bar.row.addWidget(self._pipe_pick)
        self._btn_manage = QPushButton("Manage ▾")
        self._btn_manage.setMenu(self._manage_menu())
        bar.row.addWidget(self._btn_manage)

        self._btn_add = QPushButton("Add Stage ▾")
        self._btn_add.setMenu(self._add_stage_menu())
        bar.row.addWidget(self._btn_add)

        self._btn_del = QPushButton("Delete")
        self._btn_del.setEnabled(False)
        self._btn_del.clicked.connect(self._delete_selected)
        bar.row.addWidget(self._btn_del)

        self._btn_fit = QPushButton("Fit View")
        bar.row.addWidget(self._btn_fit)

        self._btn_undo = QPushButton("Undo")
        self._btn_undo.setEnabled(False)
        self._btn_undo.clicked.connect(self._undo)
        bar.row.addWidget(self._btn_undo)

        self._btn_redo = QPushButton("Redo")
        self._btn_redo.setEnabled(False)
        self._btn_redo.clicked.connect(self._redo)
        bar.row.addWidget(self._btn_redo)

        bar.row.addStretch(1)
        self._pipe_count = QLabel("")
        self._pipe_count.setProperty("role", "dim")
        bar.row.addWidget(self._pipe_count)
        lay.addWidget(bar)

        self._canvas = Canvas()
        self._zoom = ZoomPill(self._canvas)
        lay.addWidget(self._canvas, 1)

        self._inspector = Inspector()
        lay.addWidget(self._inspector)

        self._btn_fit.clicked.connect(self._zoom.fit)
        self._canvas.selection_changed.connect(self._on_node_selected)
        self._canvas.connect_requested.connect(self._connect_nodes)
        self._canvas.doc_changed.connect(self._save_current)
        self._pipe_pick.currentIndexChanged.connect(self._load_pipeline)
        self._inspector.link_requested.connect(self._link_to_sample)

        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []

        # Keyboard alongside the on-screen controls, using the platform
        # sequences so Ctrl+Z / Ctrl+Y / Ctrl+- are whatever Windows says.
        for keys, slot in (
                (QKeySequence.ZoomIn, lambda: self._zoom.step(1.15)),
                (QKeySequence.ZoomOut, lambda: self._zoom.step(1 / 1.15)),
                (QKeySequence("Ctrl+0"), self._zoom.fit),
                (QKeySequence.Undo, self._undo),
                (QKeySequence.Redo, self._redo),
                (QKeySequence.Delete, self._delete_selected)):
            QShortcut(keys, page, activated=slot)
        # ZoomIn is Ctrl++, which needs a shift on most layouts; Ctrl+= too.
        QShortcut(QKeySequence("Ctrl+="), page,
                  activated=lambda: self._zoom.step(1.15))

        return page

    # -- pipeline menus --

    def _manage_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.addAction("New Pipeline…", self._new_pipeline)
        menu.addAction("Rename…", self._rename_pipeline)
        menu.addAction("Duplicate", self._duplicate_pipeline)
        menu.addSeparator()
        menu.addAction("Link to Episode Sample…", self._link_to_sample)
        menu.addSeparator()
        menu.addAction("Delete Pipeline…", self._delete_pipeline)
        return menu

    def _add_stage_menu(self) -> QMenu:
        """One entry per registered node type: a stage is a registry entry."""
        menu = QMenu(self)
        for key, kind in NODE_TYPES.items():
            menu.addAction(kind.name,
                           lambda checked=False, k=key: self._add_stage(k))
        return menu

    # -- pipeline edits --

    def _doc(self):
        idx = self._pipe_pick.currentIndex()
        docs = getattr(self, "_docs", None)
        return docs[idx] if docs and 0 <= idx < len(docs) else None

    def _push_undo(self) -> None:
        """Snapshot before a change; the model round-trips through dicts."""
        doc = self._doc()
        if doc is None:
            return
        self._undo_stack.append(doc.snapshot())
        del self._undo_stack[:-50]
        self._redo_stack.clear()
        self._sync_history()

    def _sync_history(self) -> None:
        self._btn_undo.setEnabled(bool(self._undo_stack))
        self._btn_redo.setEnabled(bool(self._redo_stack))

    def _undo(self) -> None:
        doc = self._doc()
        if doc is None or not self._undo_stack:
            return
        self._redo_stack.append(doc.snapshot())
        doc.restore(self._undo_stack.pop())
        self._refresh_canvas()
        self._save_current()
        self._sync_history()

    def _redo(self) -> None:
        doc = self._doc()
        if doc is None or not self._redo_stack:
            return
        self._undo_stack.append(doc.snapshot())
        doc.restore(self._redo_stack.pop())
        self._refresh_canvas()
        self._save_current()
        self._sync_history()

    def _add_stage(self, type_key: str) -> None:
        doc = self._doc()
        if doc is None:
            return
        self._push_undo()
        # Placed clear of what is already there rather than on top of it.
        _, y0, x1, _ = doc.bounds()
        doc.add_node(type_key, x1 + 40, y0)
        self._refresh_canvas()
        self._save_current()

    def _delete_selected(self) -> None:
        doc = self._doc()
        node = self._canvas.selected_node()
        if doc is None or node is None:
            return
        self._push_undo()
        doc.remove_node(node.id)
        self._refresh_canvas()
        self._save_current()

    def _connect_nodes(self, src: str, dst: str) -> None:
        doc = self._doc()
        if doc is None:
            return
        self._push_undo()
        if doc.connect(src, dst) is None:
            # Refused: a self-link, a duplicate, or it would close a loop.
            self._undo_stack.pop()
            self._sync_history()
            self.statusBar().showMessage(
                "Those stages were not connected: it would repeat a link or "
                "close a loop.", 6000)
            return
        self._refresh_canvas()
        self._save_current()

    def _on_node_selected(self, node) -> None:
        self._btn_del.setEnabled(node is not None)
        self._inspector.show_node(node)

    # -- pipeline documents --

    def _new_pipeline(self) -> None:
        doc = default_doc(unique_name([d.name for d in self._docs]))
        save_doc(doc, self._root)
        self._docs.append(doc)
        self._pipe_pick.addItem(doc.name)
        self._pipe_pick.setCurrentIndex(len(self._docs) - 1)

    def _rename_pipeline(self) -> None:
        doc = self._doc()
        if doc is None:
            return
        name, ok = QInputDialog.getText(self, "Rename Pipeline", "Name:",
                                        text=doc.name)
        if ok and name.strip():
            doc.name = name.strip()
            save_doc(doc, self._root)
            self._pipe_pick.setItemText(self._pipe_pick.currentIndex(),
                                        doc.name)
            self._inspector.show_doc(doc)

    def _duplicate_pipeline(self) -> None:
        doc = self._doc()
        if doc is None:
            return
        copy = duplicate_doc(
            doc, unique_name([d.name for d in self._docs], doc.name))
        save_doc(copy, self._root)
        self._docs.append(copy)
        self._pipe_pick.addItem(copy.name)
        self._pipe_pick.setCurrentIndex(len(self._docs) - 1)

    def _delete_pipeline(self) -> None:
        doc = self._doc()
        if doc is None:
            return
        answer = QMessageBox.question(
            self, "Delete Pipeline",
            f"Delete the pipeline {doc.name!r}?\n\n"
            f"Episodes, cached analysis and hand coding are not touched — "
            f"only this diagram.")
        if answer != QMessageBox.Yes:
            return
        index = self._pipe_pick.currentIndex()
        delete_doc(doc)
        del self._docs[index]
        self._pipe_pick.removeItem(index)
        if not self._docs:
            self._new_pipeline()

    def _link_to_sample(self) -> None:
        """Bind the pipeline to a show, so stages can report derived status."""
        doc = self._doc()
        if doc is None:
            return
        if not self._root:
            QMessageBox.information(
                self, "Link to Episode Sample",
                "Choose a root folder first — the sample is a show "
                "inside it.")
            return
        keys = sorted({show_key(self._root, path)
                       for kind, path in list_top_level(self._root)
                       for path in ([path] if kind == "show"
                                    else list_category_shows(path))})
        if not keys:
            QMessageBox.information(self, "Link to Episode Sample",
                                    "No shows were found under the root "
                                    "folder.")
            return
        key, ok = QInputDialog.getItem(
            self, "Link to Episode Sample", "Show:", keys, 0, False)
        if ok and key:
            doc.source_key = key
            save_doc(doc, self._root)
            self._refresh_canvas()

    def _save_current(self) -> None:
        doc = self._doc()
        if doc is not None:
            save_doc(doc, self._root)

    def _refresh_canvas(self) -> None:
        doc = self._doc()
        if doc is None:
            return
        # Derived status is read once per refresh; it walks the cache, so
        # doing it per node would re-scan the library for every box drawn.
        self._derived = {}
        if doc.source_key:
            try:
                self._derived = {p.key: p
                                 for p in build_pipelines(self._root)}
            except Exception:
                self._derived = {}
        self._canvas.load(doc, self._stage_status)
        self._zoom.refresh()
        plural_n = "s" if len(doc.nodes) != 1 else ""
        plural_l = "s" if len(doc.connections) != 1 else ""
        self._pipe_count.setText(
            f"{len(doc.nodes)} node{plural_n} · "
            f"{len(doc.connections)} link{plural_l}")
        self._inspector.show_doc(doc)

    def _discover_pipelines(self) -> None:
        """Load this root's pipelines, or offer the default shape if none."""
        self._docs = list_docs(self._root) or [default_doc()]
        self._pipe_pick.blockSignals(True)
        self._pipe_pick.clear()
        self._pipe_pick.addItems([d.name for d in self._docs])
        self._pipe_pick.blockSignals(False)
        self._load_pipeline(0)

    def _load_pipeline(self, index: int) -> None:
        if not getattr(self, "_docs", None) or index < 0:
            return
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._sync_history()
        self._refresh_canvas()

    def _stage_status(self, node) -> str:
        """The node's real state, derived from what is on disk.

        An unlinked pipeline says so rather than showing a plausible figure: a
        stage cannot report progress until it knows which episodes it is
        progressing through.
        """
        doc = self._doc()
        if doc is None or not doc.source_key:
            return "— no data source"
        kind = node_type(node.type)
        if not kind.stage_key:
            return ""
        pipeline = getattr(self, "_derived", {}).get(doc.source_key)
        if pipeline is None:
            return "— no derived status"
        stage = pipeline.stage(kind.stage_key)
        return f"— {stage.status_label}" if stage is not None else ""

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
        # Plain white with a hover tint, as the reference tree is. Striping is
        # reserved for the numeric tables in the report, where rows are read
        # across; here rows are read down a hierarchy and the banding fights
        # the indentation.
        self._tree.setAlternatingRowColors(False)
        self._tree.setUniformRowHeights(True)
        self._tree.setIndentation(METRICS["row_h"] - 2)
        self._tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tree.setProperty("inPanel", "true")
        self._tree.setTextElideMode(Qt.ElideRight)
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
        # The reference results pane is a 6px gutter, not the ~4px Qt default,
        # and the document font has to be set on the document rather than the
        # widget or the stylesheet's px sizes resolve against the wrong base.
        self._report.document().setDocumentMargin(6)
        self._report.document().setDefaultFont(theme.font("body"))
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
        # Pipelines live under the root (<root>/.analysis/pipelines), so the
        # list has to be rebuilt when the root changes. Without this the tab
        # keeps whatever was found before a root was known — which is the
        # fallback location, not the project's own pipelines.
        self._discover_pipelines()

    def populate(self) -> None:
        self._model.removeRows(0, self._model.rowCount())
        if not self._root:
            self._count.setText("no library loaded")
            return

        shows = episodes = 0
        for kind, path in list_top_level(self._root):
            if kind == "category":
                node = self._row(path.name, "", "", _fmt_added(path),
                                 bold=True, icon=FOLDER)
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
        self._release_columns()
        if hasattr(self, "_index"):
            self._index.refresh()
        self._count.setText(
            f"{shows} show{'s' if shows != 1 else ''}, "
            f"{episodes} episode{'s' if episodes != 1 else ''}")
        self.statusBar().showMessage(
            f"{shows} shows, {episodes} episodes in {self._root}")

    def _release_columns(self) -> None:
        """Let the user resize the trailing columns after their first sizing.

        ResizeToContents gives good initial widths but pins them there, so the
        stretched Name column keeps whatever is left and a long episode name
        stays elided with no way to widen it.
        """
        hv = self._tree.header()
        for col in (COL_STATUS, COL_LENGTH, COL_ADDED):
            width = hv.sectionSize(col)
            hv.setSectionResizeMode(col, QHeaderView.Interactive)
            hv.resizeSection(col, width)

    def _row(self, name, status, length, added, bold=False, payload=None,
             icon=None):
        cells = [QStandardItem(str(v)) for v in (name, status, length, added)]
        for cell in cells:
            cell.setEditable(False)
            if bold:
                f = cell.font()
                f.setBold(True)
                cell.setFont(f)
        if icon:
            cells[0].setIcon(_glyph_icon(icon))
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
                            _fmt_added(ep), payload=ep, icon=FILE)
            row[COL_STATUS].setForeground(
                Qt.GlobalColor.darkBlue if cached else Qt.GlobalColor.darkGray)
            rows.append(row)

        head = self._row(show_dir.name,
                         f"{analyzed}/{len(eps)} analyzed" if eps else "empty",
                         f"{len(eps)} ep." if eps else "—",
                         _fmt_added(show_dir), bold=True, icon=FOLDER)
        for r in rows:
            head[0].appendRow(r)
        if parent is None:
            self._model.appendRow(head)
        else:
            parent.appendRow(head)
        return 1, len(eps)

    def _on_analysis_finished(self) -> None:
        """Re-read the library so new results show without a manual refresh."""
        self.populate()
        self._index.refresh()

    def _show_indexed_episode(self, file_path: str) -> None:
        """Double-clicking an indexed row opens its report in the Library."""
        path = Path(file_path)
        if not path.exists():
            self.statusBar().showMessage(
                f"{path.name} is indexed but no longer on disk. "
                f"Use Remove Stale to clear rows like this.", 8000)
            return
        cached = load_cached(self._root, show_key(self._root, path.parent),
                             path.stem)
        if cached:
            self._report.setHtml(
                episode_html(EpisodeResult.from_dict(cached)))
            self._tabs.setCurrentWidget(self._library_page)

    def _on_select(self, *_args) -> None:
        idx = self._tree.selectionModel().currentIndex()
        if not idx.isValid():
            return
        item = self._model.itemFromIndex(idx.siblingAtColumn(COL_NAME))
        payload = item.data(Qt.UserRole)
        if not payload:
            self._automated.set_target(self._show_dir_for(item))
            self._report.setHtml(
                "<p style='color:#54595d'>Select an episode to see its "
                "analysis, or run the whole show from Automated coding.</p>")
            return
        ep = Path(payload)
        self._automated.set_target(ep)
        cached = load_cached(self._root, show_key(self._root, ep.parent),
                             ep.stem)
        if not cached:
            self._report.setHtml(
                f"<p style='color:#54595d'><b>{ep.name}</b><br>"
                "Not analyzed yet. Run it from Automated coding; the result "
                "appears here when it finishes.</p>")
            return
        result = EpisodeResult.from_dict(cached)
        events = None
        try:
            from analyzer.event_coding import latest_rates_for_stem
            events = latest_rates_for_stem(ep.stem)
        except Exception:
            pass
        self._report.setHtml(episode_html(result, events=events))

    def _show_dir_for(self, item):
        """The folder a non-episode row stands for, if it is a show.

        Category rows have no episodes of their own, so they resolve to None
        rather than to a folder the analysis would find empty.
        """
        if self._root is None:
            return None
        names = []
        node = item
        while node is not None:
            names.append(node.text())
            node = node.parent()
        path = self._root.joinpath(*reversed(names))
        return path if path.is_dir() and list_episodes(path) else None

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
