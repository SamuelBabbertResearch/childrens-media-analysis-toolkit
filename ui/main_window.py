"""
ui/main_window.py — the Qt shell: toolbar, tabs, Library grid, Results report.

The first screen ported for real. Reads the same library, the same cache, and
the same preferences as the Tk front-end, so both can be run against one
project and compared directly.

**Every screen the Tk build has now exists here** (2026-08-14). That is
coverage, not mileage — see `onboarding.md` before calling the Qt build the
product.

Two things here are load-bearing beyond the shell:

* `STAGE_TABS` / `STAGE_ACTIONS` map a pipeline stage to the screen that does
  its work. Without them a pipeline node is a picture of the workflow rather
  than a way into it. `STAGE_UNPORTED` is the escape hatch for a stage type
  added before its screen exists — an unavailable control must not look like a
  broken one, so the control stays and says why.
* `MainWindow._cached` is the single place a cached result is read, because it
  is also the single place the composite is re-scored with the settings in
  force. Read the cache around it and Settings' "Apply & Re-score" silently
  stops working. A test enforces this.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction, QFont, QIcon, QKeySequence,
    QPainter, QPixmap, QShortcut, QStandardItem, QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QComboBox, QDialog, QFileDialog, QFrame,
    QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QMainWindow, QMenu, QMenuBar, QMessageBox,
    QPushButton, QSplitter, QStackedWidget, QTabWidget,
    QTextBrowser, QToolBar, QTreeView, QVBoxLayout, QWidget,
)

from analyzer import constructs as C
from analyzer.cache import load_cached
from analyzer.config_loader import load_config
from analyzer.prefs import get_pref, set_pref
from analyzer.schema import EpisodeResult
from analyzer.show_index import (
    list_category_shows, list_episodes, list_shows, list_top_level, show_key,
)
from ui import native_frame, theme
from analyzer.pipeline import build_pipelines, merged_pipeline
from analyzer.scope import (
    LIBRARY_LABEL, Scope, library_scope, scope_from_draw, scope_from_draws,
    scope_from_pipeline,
)
from analyzer.pipeline_graph import (
    NODE_TYPES, default_doc, delete_doc, duplicate_doc, list_docs,
    node_type, save_doc, unique_name,
)
from ui.modal import ConfirmDialog, WindowTitleBar
from ui.pipeline_view import Canvas, ZoomPill
from ui.welcome import WelcomeDialog
from ui.inspector import Inspector
from analyzer.aggregate import compute_show_aggregate
from ui.report import episode_html, show_html
from ui.automated import AutomatedTab
from ui.handcoding import HandCodingTab
from ui.index_tab import IndexTab
from ui.language import LanguageTab
from ui.settings import SettingsDialog
from ui.trials_tab import TrialsTab
from ui.tokens import METRICS, color

# The reference marks folders and episodes with these two glyphs.
FOLDER = "📁"
FILE = "📄"

# Column order for the library grid.
COL_NAME, COL_STATUS, COL_LENGTH, COL_ADDED = range(4)

# Which screen does a stage's work: (tab title, sub-view or None). The
# pipeline is a control surface only if a node can reach the screen that does
# its job; without this a node is a picture. Keyed by NodeType.stage_key, so a
# new stage type is still a registry entry plus one line here.
STAGE_TABS: dict[str, tuple[str, str | None]] = {
    "selection": ("Library", None),
    "automated": ("Automated coding", None),
    "language": ("Language", "Speech"),
    "measurement": ("Automated coding", None),
    "handcode_transitions": ("Human coding", "Code"),
    "handcode_events": ("Human coding", "Code"),
    "validation": ("Human coding", "Validate tool"),
    "results": ("Index", None),
}

# Stages whose work is done in a dialog rather than a tab: (button label,
# MainWindow method).
STAGE_ACTIONS: dict[str, tuple[str, str]] = {
    "sampling": ("Episode Sampler", "open_sampler"),
}

# Stages whose screen is not in this front-end. The control stays, disabled
# and saying why — an unavailable control must not look like a broken one.
# Empty now that every stage has a screen; the mechanism stays because the
# next stage type added will need it before its screen exists.
STAGE_UNPORTED: dict[str, str] = {}


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


class SubViews(QObject):
    """Named screens inside one tab, switched from the sub-toolbar.

    The reference has a tab strip and a `.sub-toolbar`; it has no nested tab
    strip, and a second row of tabs inside the first is not a Windows
    convention either. So the sub-bar carries a group of checkable buttons —
    the platform's segmented control — over a `QStackedWidget`.
    """

    changed = Signal(str)

    def __init__(self, bar, stack: QStackedWidget) -> None:
        super().__init__(stack)
        self._bar = bar
        self._stack = stack
        self._buttons: dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

    def add(self, name: str, widget: QWidget) -> None:
        button = QPushButton(name)
        button.setCheckable(True)
        button.setProperty("segment", "true")
        index = self._stack.count()
        self._stack.addWidget(widget)
        self._group.addButton(button, index)
        self._bar.row.addWidget(button)
        self._buttons[name] = button
        button.clicked.connect(lambda _=False, n=name: self.show(n))
        if index == 0:
            button.setChecked(True)

    def show(self, name: str) -> None:
        button = self._buttons.get(name)
        if button is None:
            return
        button.setChecked(True)
        self._stack.setCurrentIndex(self._group.id(button))
        self.changed.emit(name)

    def current(self) -> str:
        checked = self._group.checkedButton()
        return checked.text() if checked else ""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Children's Media Analysis Toolkit (CMAT)")
        self.resize(1280, 820)

        self._cfg = load_config()
        self._root: Path | None = None
        # The research context. Deliberately NOT persisted across launches:
        # opening the application on a narrowed library, with no memory of
        # having narrowed it, is the failure this control exists to avoid.
        self._scope = library_scope()

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
        self._tabs.setCurrentWidget(self._pipeline_page)
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
            # Drop the strip's menu bar too. It is only ever parented in the
            # holder below, so keeping it here left `_build_menu` filling a
            # QMenuBar that is never added to the window — no File menu, no
            # Help menu, on any platform where the Win32 hook does not attach.
            # Falling back to None sends `_build_menu` to self.menuBar().
            self._menubar = None
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
        # Do NOT also stash these on self. addMenu() returns a QMenu owned by
        # the bar; a second Python wrapper held on the window goes stale when
        # the bar is reparented into the title-strip holder, and then reads as
        # "C++ object already deleted" while the real menu is perfectly fine.
        # Reach a menu through bar.actions()[i].menu() if you need it later.
        file_menu = bar.addMenu("&File")
        act_open = QAction("Choose Root Folder…", self)
        act_open.triggered.connect(self.choose_root)
        file_menu.addAction(act_open)
        act_sampler = QAction("Episode Sampler…", self)
        # Not self.open_sampler directly: triggered emits a checked bool,
        # which auto-matching would otherwise pass into open_sampler's node
        # argument.
        act_sampler.triggered.connect(lambda: self.open_sampler())
        file_menu.addAction(act_sampler)
        file_menu.addSeparator()

        act_settings = QAction("Scoring settings…", self)
        act_settings.triggered.connect(self.open_settings)
        file_menu.addAction(act_settings)
        act_measure = QAction("Measurement settings…", self)
        act_measure.setToolTip(
            "Which detector measures what, and with which parameters. These "
            "change the raw numbers, so they make cached results stale.")
        act_measure.triggered.connect(self.open_measurement_settings)
        file_menu.addAction(act_measure)
        act_recipes = QAction("Recipes…", self)
        act_recipes.setToolTip(
            "How a construct was operationalized: which measures stand in for "
            "it, by which methods, with which parameters. A recipe PINS its "
            "parameters, so it does not follow the two dialogs above.")
        act_recipes.triggered.connect(self.open_recipes)
        file_menu.addAction(act_recipes)
        act_tools = QAction("Optional tools…", self)
        act_tools.triggered.connect(self.open_optional_tools)
        file_menu.addAction(act_tools)
        act_meta = QAction("Import Episode Metadata…", self)
        act_meta.setToolTip(
            "Air dates and episode numbers from Wikipedia or TVMaze. They "
            "drive era stratification in the sampler.")
        act_meta.triggered.connect(self.open_metadata_import)
        file_menu.addAction(act_meta)
        act_new = QAction("New Pipeline from Layout…", self)
        act_new.triggered.connect(self.show_welcome)
        file_menu.addAction(act_new)
        file_menu.addSeparator()

        # Export acts on whatever the Results pane is currently showing, which
        # is why the three are disabled until it shows something. The pipeline's
        # Results stage tells the user to come here, so they have to exist.
        self._act_json = QAction("Export Results as JSON…", self)
        self._act_json.triggered.connect(self.export_json)
        self._act_csv = QAction("Export Results as CSV…", self)
        self._act_csv.triggered.connect(self.export_csv)
        self._act_pdf = QAction("Export Report as PDF…", self)
        self._act_pdf.triggered.connect(self.export_pdf)
        for act in (self._act_json, self._act_csv, self._act_pdf):
            act.setEnabled(False)
            file_menu.addAction(act)
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
        # The index stores the composite, so it has to be rewritten too or the
        # Library and the Index disagree about the same episode.
        rows = self.rescore_index()
        self.populate()
        self.statusBar().showMessage(
            f"Re-scored {rows} episode{'s' if rows != 1 else ''} from cache "
            f"with the new weights, in the Library and the Index. No episode "
            f"needs re-analysing — these are scoring settings.", 8000)

    # ---- exports ----
    #
    # Every export carries the accuracy statement with it. A CSV of numbers
    # with no provenance is exactly the artefact `CLAUDE.md` §2.2 exists to
    # prevent: the figures leave the tool and the qualifiers do not.

    def _set_export_source(self, episode=None, show=None) -> None:
        """Record what the Results pane is showing, for the export actions.

        *show* is (name, results). Exactly one of the two is set; both None
        means the pane is showing prose rather than a result, and the three
        export actions go grey rather than exporting whatever was last seen.
        """
        self._export_episode = episode
        self._export_show = show
        for act in (getattr(self, "_act_json", None),
                    getattr(self, "_act_csv", None),
                    getattr(self, "_act_pdf", None)):
            if act is not None:
                act.setEnabled(episode is not None or show is not None)

    def _export_stem(self) -> str:
        if self._export_episode is not None:
            return Path(self._export_episode.file).stem
        return self._export_show[0] if self._export_show else "results"

    def _export_results(self) -> list:
        if self._export_episode is not None:
            return [self._export_episode]
        return list(self._export_show[1]) if self._export_show else []

    def export_json(self) -> None:
        """The result plus the provenance block, in one file."""
        import json
        from analyzer.provenance import validation_dict
        results = self._export_results()
        if not results:
            return
        path, _f = QFileDialog.getSaveFileName(
            self, "Export results as JSON",
            f"{self._export_stem()}_analysis.json", "JSON (*.json)")
        if not path:
            return
        payload = {"validation_provenance": validation_dict()}
        if self._export_episode is not None:
            payload["episode"] = self._export_episode.to_dict()
        else:
            payload["show"] = self._export_show[0]
            payload["episodes"] = [r.to_dict() for r in results]
        try:
            Path(path).write_text(json.dumps(payload, indent=2),
                                  encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
            return
        self.statusBar().showMessage(
            f"Exported {Path(path).name}, with the validation provenance "
            f"block.", 8000)

    def export_csv(self) -> None:
        """One row per episode, plus a provenance sidecar.

        The statement goes in a sidecar rather than a comment row so the CSV
        stays machine-readable — but it goes, every time.
        """
        from analyzer.aggregate import results_to_dataframe
        from analyzer.provenance import validation_statement
        results = self._export_results()
        if not results:
            return
        path, _f = QFileDialog.getSaveFileName(
            self, "Export results as CSV",
            f"{self._export_stem()}_analysis.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            results_to_dataframe(results).to_csv(path, index=False)
            sidecar = Path(path).with_name(Path(path).stem + "_PROVENANCE.txt")
            sidecar.write_text(validation_statement(), encoding="utf-8")
        except Exception as exc:            # noqa: BLE001 — shown, not hidden
            QMessageBox.warning(self, "Export failed", str(exc))
            return
        self.statusBar().showMessage(
            f"Exported {Path(path).name} and {sidecar.name} — keep the two "
            f"together.", 8000)

    def export_pdf(self) -> None:
        results = self._export_results()
        if not results:
            return
        try:
            from analyzer.report_pdf import export_episode_pdf, export_show_pdf
        except ImportError as exc:
            QMessageBox.information(
                self, "PDF export unavailable",
                f"The PDF exporter needs reportlab: {exc}\n\n"
                f"Install it with:  pip install reportlab")
            return
        path, _f = QFileDialog.getSaveFileName(
            self, "Export report as PDF",
            f"{self._export_stem()}_report.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            if self._export_episode is not None:
                export_episode_pdf(self._export_episode, self._cfg,
                                   Path(path))
            else:
                aggregate = compute_show_aggregate(self._export_show[0],
                                                   results)
                export_show_pdf(aggregate, results, self._cfg, Path(path))
        except Exception as exc:            # noqa: BLE001 — shown, not hidden
            QMessageBox.warning(self, "PDF export failed", str(exc))
            return
        self.statusBar().showMessage(f"PDF saved: {Path(path).name}", 8000)

    # ---- the other settings axis ----

    def rescore_index(self) -> int:
        """Rewrite the index's derived scores from cache. Returns rows written.

        The composite is DERIVED, and the index stores it. When the weights
        change, the stored value is stale — so after "Apply & Re-score" the
        Library showed 0.107 for an episode while the Index still showed
        0.132, with nothing marking either as out of date. The Index is the
        cross-episode comparison screen, so it was also computing its outlier
        fences from scores under a mix of weightings.

        Raw metrics are untouched; only the composite is recomputed, which is
        what makes this instant rather than a re-analysis. The Tk build does
        the same in `_backfill_index`.
        """
        conn = self._db()
        if conn is None or not self._root:
            return 0
        from analyzer.db import rebuild_show_aggregates

        return rebuild_show_aggregates(
            conn, self._root,
            fetch_result=lambda show_dir, skey, ep: self._cached(skey, ep.stem),
            set_season=True,
        )

    def open_measurement_settings(self) -> None:
        """Which tool measures what. Changing these makes cached results stale.

        Kept apart from Settings on purpose: scoring settings re-score from
        cache, measurement settings invalidate it. See `ARCHITECTURE.md` §3.
        """
        from ui.measurements import MeasurementsDialog
        dialog = MeasurementsDialog(self._cfg, self._root, self)
        if dialog.exec() != QDialog.Accepted:
            return
        self._cfg = dialog.config
        self.populate()
        message = "Measurement settings applied."
        if dialog.stale_count:
            message += (f" {dialog.stale_count} cached episode"
                        f"{'s are' if dialog.stale_count != 1 else ' is'} now "
                        f"stale — re-analyze to compare like with like.")
        if dialog.unknown_count:
            message += (f" {dialog.unknown_count} predate measurement "
                        f"fingerprinting and cannot be checked either way.")
        self.statusBar().showMessage(message, 12000)

    def open_recipes(self) -> None:
        """How a construct was operationalized — the third settings axis.

        Not a settings dialog in the sense the other two are: a recipe PINS its
        parameters rather than following the config, so nothing here changes
        `self._cfg` and nothing here invalidates a cached result. It reads the
        config to pin from it and to report where a recipe's pins have since
        diverged. See `ARCHITECTURE.md` §3b.

        Given the current scope so "apply to the current scope" means the same
        set of episodes the rest of the window is showing.
        """
        from ui.recipes import RecipesDialog
        RecipesDialog(self._cfg, self._root, self._scope, self).exec()

    def open_optional_tools(self) -> None:
        from ui.optional_tools import OptionalToolsDialog
        OptionalToolsDialog(self).exec()

    def open_metadata_import(self) -> None:
        """Air dates and episode numbers from Wikipedia or TVMaze."""
        if not self._root:
            QMessageBox.information(
                self, "Import Episode Metadata",
                "Choose a root folder first — the fetched list is matched "
                "against the episode files in it.")
            return
        from ui.metadata_import import MetadataImportDialog
        dialog = MetadataImportDialog(self, self)
        if dialog.exec() != QDialog.Accepted:
            return
        self._index.refresh()
        # The panel for the selected episode may now have an air date in it.
        self._show_episode_details(self._details_episode)
        self.statusBar().showMessage(
            f"Imported metadata for {dialog.applied} episode"
            f"{'s' if dialog.applied != 1 else ''}. Air dates feed era "
            f"stratification in the Episode Sampler.", 10000)

    def open_sampler(self, node=None) -> None:
        """Draw an episode sample.

        *node* is the specific Sampling node this was opened from — set only
        when reached by double-clicking a Sampling node on the pipeline
        canvas (`_open_stage_screen`). When given, a successful draw links
        itself to THAT node directly (`node.config["sample_key"]`), the same
        write `_link_node_to_sample` makes, without a separate manual
        "now go link it" step — the user asked THIS node to draw, so the
        draw belongs to it. Without a node (the File menu item, or the
        toolbar's Episode Sampler button — neither tied to any specific
        pipeline node), only the session scope follows the draw, same as
        always; linking it to a pipeline stays an explicit separate step.
        Without this, every draw only ever changed the document's session
        scope, so two Sampling nodes drawing independently both ended up
        reading the same underlying value and nothing about either draw was
        ever saved to the pipeline document at all — see `LEARNINGS.md`.

        Refreshes the Trials tab and the pipeline afterwards: a new draw is a
        new recorded run and a new thing a pipeline can bind to, and having to
        press Refresh to see work you just did is how a screen looks broken.
        """
        from ui.sampler import SamplerDialog
        dialog = SamplerDialog(self, self)
        if dialog.exec() != QDialog.Accepted:
            return
        written = getattr(dialog, "written_dir", None)
        if written is not None and node is not None and node.type == "sampling":
            doc = self._doc()
            if doc is not None:
                node.config["sample_key"] = f"sample:{written}"
                save_doc(doc, self._root)
        self._trials.refresh()
        self._refresh_canvas()
        # Drawing a sample is the moment the working set stops being "whatever
        # is on disk", so the Library follows the draw. It is a view: the
        # chooser still offers the whole library, one click away.
        if written is not None:
            self.set_scope(scope_from_draw(f"sample:{written}",
                                           written.name, written),
                           announce=False)
            self._tabs.setCurrentWidget(self._library_page)
            self.statusBar().showMessage(
                f"Showing {self._scope.describe()}. "
                f"Use Showing → {LIBRARY_LABEL} for everything again.", 12000)

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

        # The research context lives on the toolbar rather than inside the
        # Library, because more than one screen now obeys it. A control that
        # narrows the Index while sitting on another tab would be a filter the
        # user cannot see from the screen it is filtering.
        tb.addWidget(QLabel("Showing:"))
        self._scope_pick = QComboBox()
        self._scope_pick.setMinimumWidth(230)
        self._scope_pick.setToolTip(
            "Which episodes the Library and Index show: the whole library, or "
            "exactly the episodes one documented sample drew. This narrows "
            "the view only — nothing is deleted, and no measurement changes.")
        self._scope_pick.currentIndexChanged.connect(self._on_scope_picked)
        tb.addWidget(self._scope_pick)

        tb.addWidget(QLabel("Preset:"))
        self._preset = QComboBox()
        self._preset.addItems(list(self._cfg.get("presets", {})) or
                              ["General / All Ages"])
        tb.addWidget(self._preset)

        sampler = QPushButton("Episode Sampler...")
        sampler.setToolTip(
            "Draw a documented episode sample: the design is recorded with "
            "the result, so the draw can be re-run and reviewed.")
        sampler.clicked.connect(lambda: self.open_sampler())
        tb.addWidget(sampler)
        settings = QPushButton("Settings...")
        settings.clicked.connect(self.open_settings)
        tb.addWidget(settings)
    def _build_tabs(self) -> None:
        self._tabs = QTabWidget()
        self.setCentralWidget(self._tabs)

        # Built first: the Library's selection handler sets its target, so it
        # must exist before that signal can fire.
        self._automated = AutomatedTab(self)
        self._automated.library_changed.connect(self._on_analysis_finished)

        self._pipeline_page = self._build_pipeline()
        self._tabs.addTab(self._pipeline_page, "Pipeline")
        # Beside Pipeline on purpose. `MEASUREMENT_MODEL.md` §2 names three
        # views of one research process: Pipeline is the study WORKFLOW
        # ("what are the stages of my study?"), Constructs is the
        # MEASUREMENT view ("how did I operationalize what I wanted to
        # study?"). They are peers, not a screen inside a screen.
        from ui.constructs_tab import ConstructsTab
        self._constructs = ConstructsTab(self)
        self._tabs.addTab(self._constructs, "Constructs")
        self._library_page = self._build_library()
        self._tabs.addTab(self._library_page, "Library")

        self._index = IndexTab(self)
        self._index.episode_chosen.connect(self._show_indexed_episode)
        self._tabs.addTab(self._index, "Index")
        self._tabs.addTab(self._automated, "Automated coding")
        # Language is its own tab, not a screen inside Automated coding: the
        # pipeline gives it a separate stage and a "Language only" template
        # because a language study needs no sensory pass at all.
        self._language = LanguageTab(self)
        self._tabs.addTab(self._language, "Language")
        self._handcoding = HandCodingTab(self)
        self._tabs.addTab(self._handcoding, "Human coding")
        self._trials = TrialsTab(self)
        self._tabs.addTab(self._trials, "Trials")

        # By WIDGET, not by index: adding a tab renumbers every one after it,
        # and a hard-coded index then opens a different screen with nothing to
        # reveal that it changed.
        self._tabs.setCurrentWidget(self._library_page)

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

        self._btn_del = QPushButton("Delete Stage")
        self._btn_del.setEnabled(False)
        self._btn_del.setToolTip(
            "Remove the selected stage and its links from this pipeline.")
        self._btn_del.clicked.connect(self._delete_selected)
        bar.row.addWidget(self._btn_del)

        self._btn_del_pipe = QPushButton("Delete Pipeline…")
        self._btn_del_pipe.setToolTip(
            "Delete this whole pipeline diagram. Episodes, cached analysis "
            "and hand coding are not touched.")
        self._btn_del_pipe.clicked.connect(self._delete_pipeline)
        bar.row.addWidget(self._btn_del_pipe)

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
        self._canvas.node_activated.connect(self._open_stage_screen)
        self._canvas.connect_requested.connect(self._connect_nodes)
        self._canvas.doc_changed.connect(self._save_current)
        self._pipe_pick.currentIndexChanged.connect(self._load_pipeline)
        self._inspector.link_requested.connect(self._link_to_sample)
        self._inspector.link_node_requested.connect(self._link_node_to_sample)
        self._inspector.open_requested.connect(
            lambda: self._open_stage_screen(self._canvas.selected_node()))
        self._inspector.exclude_requested.connect(
            self._exclude_from_selection_node)
        self._inspector.find_clips_requested.connect(
            self._find_clips_from_selection_node)

        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self._derived: dict = {}
        self._source_label: str | None = None

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
        if node is None:
            self._inspector.show_node(None)
            return
        stage, reason = self._stage_for(node)
        doc = self._doc()
        keys = doc.upstream_sample_keys(node.id) if doc is not None else []
        # _stage_for merges every branch it can actually resolve
        # (analyzer.pipeline.merged_pipeline) for ANY node type fed by more
        # than one Sampling node, not just Validation — so the only thing
        # left to flag here is a key that named a sample not found on disk,
        # which merging cannot include no matter how it is computed.
        derived = getattr(self, "_derived", {})
        missing = [k for k in keys if k not in derived]
        media = self._node_media(node)
        extra_rows = []
        if missing:
            extra_rows.append((
                "Sample not found",
                f"{len(missing)} of {len(keys)} upstream sample"
                f"{'s' if len(keys) != 1 else ''} feeding this node "
                f"{'were' if len(missing) != 1 else 'was'} not found under "
                "the root folder, and could not be included above."))
        can_exclude = node.type == "selection" and bool(keys)
        # Window-scale selection needs no linked sample: a researcher can point
        # the finder at a folder of episodes directly, which is how a stimulus
        # set usually starts.
        can_find_clips = node.type == "selection"
        if node.config.get("clip_pool_dir"):
            extra_rows.append(("Clip pool", node.config["clip_pool_dir"]))
        if node.config.get("clip_export_dir"):
            extra_rows.append(("Exported clips", node.config["clip_export_dir"]))
        self._inspector.show_node(node, stage, reason,
                                  self._target_for(node),
                                  can_exclude=can_exclude,
                                  extra_rows=extra_rows or None,
                                  media=media,
                                  can_find_clips=can_find_clips)

    # -- pipeline as a control surface --

    def _stage_for(self, node):
        """(Stage, reason) for a node — the derived state behind the box.

        analyzer/pipeline.py computes a headline, details and a next action
        for every stage from what is on disk. A node that cannot reach one
        says why rather than showing nothing.

        The one place that decides which sample(s) a node's derived status
        comes from — `_stage_status` (the canvas subtitle) calls this too,
        rather than re-deriving it, after the two used to independently
        re-implement the same `doc.source_key` lookup (see `LEARNINGS.md`).

        A node fed by more than one upstream sample — two Sampling nodes
        both wired into one Selection node, or Validation's two input ports
        — gets a real merged view (`analyzer.pipeline.merged_pipeline`)
        computed over the UNION of every resolvable branch's episodes,
        instead of silently reporting only the first branch and dropping
        the rest. See `DECISIONS.md` for why that merge only ever unions
        episode sets and never treats two different samples' results as
        directly comparable.
        """
        doc = self._doc()
        if doc is None:
            return None, "no pipeline is open"
        kind = node_type(node.type)
        if not kind.stage_key:
            return None, "this stage type has no derived status"
        keys = doc.upstream_sample_keys(node.id)
        if not keys:
            return None, ("no Sampling node upstream is linked to an "
                          "episode sample, so there is nothing to report "
                          "progress against")
        derived = getattr(self, "_derived", {})
        pipelines = [derived[k] for k in keys if k in derived]
        if not pipelines:
            return None, (
                f"linked to “{keys[0]}”, which is not one of the episode "
                "samples found under the root folder — relink the Sampling "
                "node feeding it")
        if len(pipelines) > 1:
            merged = merged_pipeline(pipelines, root=self._root)
            stage = merged.stage(kind.stage_key)
        else:
            stage = pipelines[0].stage(kind.stage_key)
        if stage is None:
            return None, f"no derived stage named {kind.stage_key}"
        return stage, ""

    def _target_for(self, node):
        """(label, reason) for the node's screen; None if it has none.

        The label is what the button says, so a stage that lands on a screen
        inside a tab names that screen: "Open Human coding → Validate tool"
        tells the user where they are about to end up.
        """
        kind = node_type(node.type)
        if not kind.stage_key:
            return None
        route = STAGE_TABS.get(kind.stage_key)
        if route:
            title, view = route
            return (f"{title} → {view}" if view else title), None
        action = STAGE_ACTIONS.get(kind.stage_key)
        if action:
            return action[0], None
        return None, STAGE_UNPORTED.get(
            kind.stage_key, "No screen in this build does this stage's work.")

    def _follow_node_scope(self, node) -> None:
        """Opening a node's screen makes ITS resolved sample the current
        scope — not just the document's default.

        Mirrors `_follow_pipeline_scope` (which runs once, on doc load, from
        `doc.source_key`) but per node: a node fed by a specific Sampling
        node, not the document default, should stage THAT sample when its
        screen opens. Without this, two branches on one canvas could each
        show correct derived status in the Inspector while both handing the
        SAME (document-default) sample to the tab that actually does the
        work — the wire would be honest on the canvas and still lying the
        moment you touched a tab.
        """
        doc = self._doc()
        if doc is None:
            return
        keys = doc.upstream_sample_keys(node.id)
        if not keys:
            return
        derived = getattr(self, "_derived", {})
        pipelines = [derived[k] for k in keys if k in derived]
        if not pipelines:
            return
        if len(pipelines) > 1:
            # Every branch's episodes, not just the first one's. The derived
            # status already merges (`_stage_for` -> merged_pipeline); if the
            # scope did not, the Library would show one sample at a time while
            # the node above it reported both, and the other sample would look
            # lost rather than merely unshown.
            folders = [p.folder for p in pipelines if p.folder]
            scope = scope_from_draws(
                "merged:" + "|".join(sorted(p.key for p in pipelines)),
                " + ".join(p.name for p in pipelines), folders)
        else:
            scope = scope_from_pipeline(pipelines[0])
        if scope is not None and scope.key != self._scope.key:
            self.set_scope(scope)

    def _open_stage_screen(self, node) -> None:
        """Go to the screen that does this stage's work."""
        if node is None:
            return
        self._follow_node_scope(node)
        target = self._target_for(node)
        if target is None:
            self.statusBar().showMessage(
                f"“{node.title}” is an annotation, not a stage with a screen.",
                6000)
            return
        label, reason = target
        if not label:
            self.statusBar().showMessage(reason, 8000)
            return
        stage_key = node_type(node.type).stage_key
        if stage_key in STAGE_ACTIONS:
            # STAGE_ACTIONS has exactly one entry today ("sampling" ->
            # open_sampler), which is the one action that needs to know
            # WHICH node asked for it, so node is always passed through
            # rather than added conditionally.
            getattr(self, STAGE_ACTIONS[stage_key][1])(node)
            return
        title, view = STAGE_TABS[stage_key]
        page = self._tab_named(title)
        if page is None:                     # a tab that was never added
            self.statusBar().showMessage(
                f"The {title} tab is not available in this window.", 6000)
            return
        self._tabs.setCurrentWidget(page)
        if view and hasattr(page, "show_view"):
            page.show_view(view)
        self.statusBar().showMessage(
            f"{label} — the screen for “{node.title}”.", 4000)

    def _tab_named(self, title: str):
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i) == title:
                return self._tabs.widget(i)
        return None

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
            self._inspector.show_doc(doc, getattr(self, "_source_label", None),
                                     getattr(self, "_source_unresolved", ""))

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
        nodes, links = len(doc.nodes), len(doc.connections)
        if not ConfirmDialog.ask(
                self, "Delete Pipeline",
                f"Delete the pipeline “{doc.name}”?",
                f"Its {nodes} stage{'s' if nodes != 1 else ''} and "
                f"{links} link{'s' if links != 1 else ''} go with it, and this "
                f"cannot be undone.\n\n"
                f"Nothing measured is affected: the episodes, their cached "
                f"analysis, the index and every hand-coded sheet stay exactly "
                f"as they are. Only this diagram is removed.",
                confirm_text="Delete Pipeline"):
            return
        index = self._pipe_pick.currentIndex()
        delete_doc(doc)
        del self._docs[index]
        self._pipe_pick.removeItem(index)
        if not self._docs:
            self._new_pipeline()

    def _pick_sample(self, title: str, current_key: str | None):
        """Show the "which episode sample" dialog; return its `Pipeline.key`,
        or None if cancelled, no root, or nothing to offer.

        It must be a sample, not a show: the derived stages in
        analyzer/pipeline.py are keyed by the sample they were computed for.
        This once offered a list of SHOWS, whose keys are a different
        namespace entirely, so every link made resolved to nothing and no
        node ever showed a derived status. Shared by `_link_to_sample` (the
        document's default) and `_link_node_to_sample` (one Sampling node's
        own key) so the dialog itself cannot drift between the two callers —
        only WHERE the chosen key gets written differs between them.
        """
        if not self._root:
            QMessageBox.information(
                self, "Link to Episode Sample",
                "Choose a root folder first — the samples are found inside "
                "it.")
            return None
        try:
            found = build_pipelines(self._root)
        except Exception:
            found = []
        if not found:
            QMessageBox.information(
                self, "Link to Episode Sample",
                "No episode samples were found under the root folder.\n\n"
                "Draw one with the Episode Sampler, on the toolbar. Episodes "
                "worked on without a formal draw appear here as “Unsampled "
                "work” once they have been analysed or coded.")
            return None
        labels = [f"{p.name}  ({p.episode_count} episode"
                  f"{'s' if p.episode_count != 1 else ''})" for p in found]
        current = next((i for i, p in enumerate(found)
                        if p.key == current_key), 0)
        choice, ok = QInputDialog.getItem(
            self, title, "Episode sample:", labels, current, False)
        if not (ok and choice):
            return None
        return found[labels.index(choice)].key

    def _link_to_sample(self) -> None:
        """Bind the DOCUMENT's default sample — `Manage → Link to Episode
        Sample…`, and the Inspector's button when no node is selected.

        Never touches a specific node's own binding; see `_link_node_to_
        sample` for that. The two used to be one method that inferred which
        was meant from whatever happened to be selected on the canvas at
        click-time — reachable from this exact menu item regardless of
        canvas state, which made it silently do the wrong thing whenever a
        Sampling node was still selected from browsing around. Split so
        which one runs is decided by which button was pressed, not by
        incidental state. See `LEARNINGS.md`.
        """
        doc = self._doc()
        if doc is None:
            return
        key = self._pick_sample("Link to Episode Sample", doc.source_key)
        if key is None:
            return
        doc.source_key = key
        save_doc(doc, self._root)
        self._refresh_canvas()

    def _link_node_to_sample(self) -> None:
        """Bind the SELECTED Sampling node's own sample
        (`node.config["sample_key"]`) — the Inspector's button, only ever
        visible while a Sampling node is selected (`show_node`'s
        `is_sampling` check). See `_link_to_sample` for why this is a
        separate method rather than one that infers which is meant.
        """
        doc = self._doc()
        node = self._canvas.selected_node()
        if doc is None or node is None or node.type != "sampling":
            return
        key = self._pick_sample(f"Link “{node.title}”",
                                node.config.get("sample_key"))
        if key is None:
            return
        node.config["sample_key"] = key
        save_doc(doc, self._root)
        self._refresh_canvas()
        # Which samples this pipeline draws on just changed, so the chooser's
        # pipeline entry has to be recomputed — otherwise a study only
        # becomes selectable in Showing: after a restart.
        self._rebuild_scope_choices()

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
        # Any Sampling node's OWN binding counts here too, not just the
        # document's default -- a canvas can have Sampling nodes linked to a
        # sample without the document itself ever being linked.
        self._derived = {}
        has_any_link = bool(doc.source_key) or any(
            n.type == "sampling" and n.config.get("sample_key")
            for n in doc.nodes)
        if has_any_link:
            try:
                self._derived = {p.key: p
                                 for p in build_pipelines(self._root)}
            except Exception:
                self._derived = {}
        # What this pipeline ACTUALLY draws on, which since per-node binding is
        # not the same question as what `doc.source_key` says. A Sampling node
        # carrying its own `sample_key` resolves through that; the document's
        # key is only a fallback for nodes (and documents) that have none.
        #
        # Reading `doc.source_key` here reported a show that contributes
        # nothing: a pipeline whose Sampling node was bound to an Arthur sample
        # displayed "Data source: Peep and the Big Wide World/Season 1", the
        # document's stale leftover key, while every node beside it correctly
        # read Arthur. `LEARNINGS.md` shape 1 — the display and the calculation
        # disagreed. `_doc_sample_pipelines` is the one implementation of this
        # question, already shared by the scope chooser and pipeline selection,
        # so this asks it rather than deriving a third answer.
        sources = self._doc_sample_pipelines(doc, self._derived)
        if len(sources) == 1:
            self._source_label = sources[0].name
        elif sources:
            # A pipeline may legitimately draw on several samples, and naming
            # one of them would be the "one branch at a time" defect again.
            self._source_label = ", ".join(p.name for p in sources)
        else:
            self._source_label = None
        # A key that is set but resolves to no known sample or show is its own
        # state, and saying "not linked" would hide it. Kept separate so the
        # panel can name the key that no longer resolves.
        self._source_unresolved = (
            "" if sources or not doc.source_key else str(doc.source_key))
        self._canvas.load(doc, self._stage_status, self._node_media)
        self._zoom.refresh()
        plural_n = "s" if len(doc.nodes) != 1 else ""
        plural_l = "s" if len(doc.connections) != 1 else ""
        self._pipe_count.setText(
            f"{len(doc.nodes)} node{plural_n} · "
            f"{len(doc.connections)} link{plural_l}")
        self._inspector.show_doc(doc, self._source_label,
                                 getattr(self, "_source_unresolved", ""))

    def _discover_pipelines(self) -> None:
        """Load this root's pipelines, or offer the default shape if none."""
        self._docs = list_docs(self._root) or [default_doc()]
        self._pipe_pick.blockSignals(True)
        self._pipe_pick.clear()
        self._pipe_pick.addItems([d.name for d in self._docs])
        self._pipe_pick.blockSignals(False)
        # Not follow_scope: discovery runs at startup and when the root
        # changes, and the application must open on the whole library.
        self._load_pipeline(0, follow_scope=False)
        # The chooser offers pipelines as well as samples, so it can only be
        # built once the documents are known — see `_rebuild_scope_choices`.
        self._rebuild_scope_choices()

    def _load_pipeline(self, index: int, follow_scope: bool = True) -> None:
        if not getattr(self, "_docs", None) or index < 0:
            return
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._sync_history()
        self._refresh_canvas()
        if follow_scope:
            self._follow_pipeline_scope()

    def _follow_pipeline_scope(self) -> None:
        """Choosing a pipeline makes what it draws on the current scope.

        This is the spec's "selecting a node establishes the current research
        context", at the level the context actually varies. A pipeline with
        **two or more Sampling blocks defaults to all of them together** —
        the combination the researcher assembled is the working set they
        meant, so selecting the study should not land on one arbitrary half
        of it. One Sampling block scopes to that sample, as before.

        A pipeline with nothing resolvable linked leaves the scope alone
        rather than silently emptying the Library — the honest reading of an
        unlinked pipeline is "no opinion about which episodes", not "no
        episodes".
        """
        doc = self._doc()
        if doc is None:
            return
        by_key = getattr(self, "_derived", {})
        scope = self._doc_scope(doc, by_key)
        if scope is None:
            pipelines = self._doc_sample_pipelines(doc, by_key)
            if not pipelines:
                return
            scope = scope_from_pipeline(pipelines[0])
        if scope is not None and scope.key != self._scope.key:
            self.set_scope(scope)

    def _node_media(self, node) -> str:
        """What this node is working on, named — for the box on the canvas
        and the Inspector's subtitle and rows.

        The sample's own name (`Pipeline.name`, from the draw's manifest
        `trial_name`/`entry_id`) rather than anything invented here: it is
        what the Trials tab and the Showing: chooser already call that draw,
        and `CLAUDE.md` §4 is explicit that words come from the engine.
        Every upstream branch is named when a node is fed by more than one,
        so a merged node says which media it merged rather than naming one
        and leaving the rest to be inferred.
        """
        doc = self._doc()
        if doc is None:
            return ""
        derived = getattr(self, "_derived", {})
        names = [derived[k].name for k in doc.upstream_sample_keys(node.id)
                 if k in derived]
        return " + ".join(names)

    def _stage_status(self, node) -> str:
        """The node's real state, derived from what is on disk.

        An unlinked pipeline says so rather than showing a plausible figure: a
        stage cannot report progress until it knows which episodes it is
        progressing through. Delegates to `_stage_for` — see its docstring
        for why there is one lookup here, not two.
        """
        kind = node_type(node.type)
        if not kind.stage_key:
            return ""
        stage, _reason = self._stage_for(node)
        if stage is not None:
            return f"— {stage.status_label}"
        doc = self._doc()
        keys = doc.upstream_sample_keys(node.id) if doc is not None else []
        return "— no data source" if not keys else "— sample not found"

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

        # The chooser itself is on the toolbar (window-level, because the Index
        # obeys it too). What stays here is the sentence explaining the current
        # context, next to the tree it is filtering.
        self._scope_note = QLabel("")
        self._scope_note.setProperty("role", "dim")
        self._scope_note.setWordWrap(True)
        lay.addWidget(self._scope_note)

        split = QSplitter(Qt.Horizontal)
        lay.addWidget(split, 1)

        left = Panel("Shows / Episodes")
        self._count = QLabel("no library loaded")
        self._count.setProperty("role", "dim")
        left.add_header_widget(self._count)
        self._btn_series = QPushButton("Full Series Aggregate")
        self._btn_series.setToolTip(
            "One aggregate over every analysed episode under the root "
            "folder, across season folders. Each episode counts once.")
        self._btn_series.clicked.connect(self._show_full_series)
        left.add_header_widget(self._btn_series)
        self._btn_sample = QPushButton("Sample Aggregate…")
        self._btn_sample.setToolTip(
            "Results for one drawn sample: pick its manifest.json and see the "
            "aggregate over exactly the episodes that sample selected.")
        self._btn_sample.clicked.connect(self._show_sample_aggregate)
        left.add_header_widget(self._btn_sample)
        self._btn_pin = QPushButton("Pin for Compare")
        self._btn_pin.setEnabled(False)
        self._btn_pin.clicked.connect(self._pin_for_compare)
        left.add_header_widget(self._btn_pin)
        self._btn_compare = QPushButton("Compare with Pinned")
        self._btn_compare.setEnabled(False)
        self._btn_compare.clicked.connect(self._open_compare)
        left.add_header_widget(self._btn_compare)
        # (kind, path) for the current selection and the pinned one. Compare is
        # only meaningful like for like, so the kinds have to match.
        self._selected: tuple[str, Path] | None = None
        self._pinned: tuple[str, Path] | None = None

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
        # Extended, so a batch can be queued in one gesture. The report still
        # follows the CURRENT item — selecting five episodes shows the last
        # one's report and queues all five, which is what the tree's own
        # conventions already imply.
        self._tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
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
        # Right-click is the platform's "act on this item" gesture, and it is
        # how an episode reaches another tab without hunting for the tab.
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._library_menu)
        left.body_layout.addWidget(self._tree)
        split.addWidget(left)

        right = Panel("Results")
        self._btn_chart = QPushButton("Show Chart")
        self._btn_chart.setProperty("primary", "true")
        self._btn_chart.setEnabled(False)
        self._btn_chart.setToolTip(
            "Show the component contributions to each episode's FFC.")
        self._btn_chart.clicked.connect(self._open_chart)
        self._chart_source = None
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
        self._export_episode = None
        self._export_show = None
        right.body_layout.addWidget(self._report)
        right.body_layout.addWidget(self._details_panel())
        split.addWidget(right)

        # 46 / 54, matching the reference layout.
        split.setStretchFactor(0, 46)
        split.setStretchFactor(1, 54)
        return page

    # ---- sending a selection to another tab ----
    #
    # One reader and one send path, used by the context menu and by anything
    # added later. Selecting an episode already pushed it to two tabs; what
    # was missing was any way to GET to those tabs, and any way to act on more
    # than one episode at a time.

    def _selected_paths(self) -> list[Path]:
        """Every selected row as a path — episodes as files, shows as folders.

        Category rows resolve to nothing: they group shows and have no
        episodes of their own.
        """
        out: list[Path] = []
        for index in self._tree.selectionModel().selectedRows(COL_NAME):
            item = self._model.itemFromIndex(index)
            if item is None:
                continue
            payload = item.data(Qt.UserRole)
            if payload:
                out.append(Path(payload))
            else:
                show_dir = self._show_dir_for(item)
                if show_dir is not None:
                    out.append(show_dir)
        # Stable and de-duplicated: selecting a show and one of its episodes
        # should not queue that episode twice.
        seen, unique = set(), []
        for path in out:
            if path not in seen:
                seen.add(path)
                unique.append(path)
        return unique

    def _selected_episode_paths(self) -> list[Path]:
        """`_selected_paths()`, with any selected show folder expanded to its
        episode files — what a Selection node's exclude list actually needs."""
        out: list[Path] = []
        for p in self._selected_paths():
            out.extend(list_episodes(p) if p.is_dir() else [p])
        return out

    def _exclude_from_selection_node(self) -> None:
        """Write the Library's current row selection out of the active
        Selection node's linked sample, as a new, real, discoverable sample.

        This is the "wires carry the set" slice from `TODO.md`: excluding
        here writes selected.csv + manifest.json exactly like an Episode
        Sampler draw (`analyzer.selection.write_narrowed_selection`), so the
        narrowed set becomes its own entry in the Showing: chooser rather
        than a pipeline-canvas-only annotation the chooser could silently
        disagree with.

        Narrows whichever sample(s) actually feed THIS node
        (`doc.upstream_sample_keys`, nearest Sampling node(s) first) — not
        always the document's default — so excluding on a Selection node
        wired to one specific branch of a multi-sample canvas narrows that
        branch, not whichever sample the document happens to be linked to.
        Fed by more than one Sampling node, this narrows the UNION of every
        branch's episodes (`analyzer.selection
        .write_narrowed_selection_from_sources`) — the same union
        `_stage_for`'s derived status already shows, so what you exclude
        here matches what you were looking at.
        """
        doc = self._doc()
        node = self._canvas.selected_node()
        if doc is None or node is None or node.type != "selection":
            return
        keys = doc.upstream_sample_keys(node.id)
        if not keys:
            return
        derived = getattr(self, "_derived", {})
        pipelines = [derived[k] for k in keys if k in derived]
        folders = [p.folder for p in pipelines if p.folder]
        if not folders:
            self.statusBar().showMessage(
                "This pipeline's linked sample was not found on disk.", 6000)
            return
        exclude = self._selected_episode_paths()
        if not exclude:
            self.statusBar().showMessage(
                "Select rows in the Library to exclude first.", 6000)
            return
        name = " + ".join(p.name for p in pipelines)
        if len(folders) > 1:
            from analyzer.selection import write_narrowed_selection_from_sources
            outdir = write_narrowed_selection_from_sources(
                folders, name, set(exclude), node.id)
        else:
            from analyzer.selection import write_narrowed_selection
            outdir = write_narrowed_selection(
                folders[0], name, set(exclude), node.id)
        if outdir is None:
            self.statusBar().showMessage(
                "Nothing to exclude — none of the selected rows are in this "
                "sample.", 6000)
            return
        self._trials.refresh()
        self.set_scope(scope_from_draw(
            f"sample:{outdir}", f"{name} — Selection", outdir))
        n = len(exclude)
        self.statusBar().showMessage(
            f"Wrote a narrowed sample excluding {n} episode{'s' if n != 1 else ''} "
            f"to {outdir.name}. It now appears in Showing: and the Trials tab.",
            10000)

    def _clip_finder_source(self, node) -> Path | None:
        """The folder of episodes to offer the finder, or None to ask.

        A Selection node knows its upstream sample, and a sample knows its
        episodes; the candidate pass wants the FOLDER those episodes live in,
        so this is their common parent. Guessing wrongly here is cheap — the
        screen shows the folder and the researcher can change it — but
        guessing at all saves the common case of a single-show sample.
        """
        doc = self._doc()
        if doc is None:
            return None
        from analyzer.scope import read_selected
        derived = getattr(self, "_derived", {})
        episodes: list[Path] = []
        for key in doc.upstream_sample_keys(node.id):
            pipeline = derived.get(key)
            if pipeline is not None and pipeline.folder:
                episodes.extend(read_selected(pipeline.folder))
        parents = {p.parent for p in episodes if p.parent}
        if len(parents) == 1:
            return parents.pop()
        if len(parents) > 1:
            # Several folders: offer the nearest shared ancestor rather than
            # one arbitrary branch, and let the recursive option cover it.
            try:
                import os
                return Path(os.path.commonpath([str(p) for p in parents]))
            except ValueError:
                return None
        return None

    def _find_clips_from_selection_node(self) -> None:
        """Open the Clip Finder for the active Selection node.

        What the finder does is recorded ON the node — the measured pool and
        any export — so the node states what it holds and a later session
        opens the same pool instead of measuring the folder again.
        """
        doc = self._doc()
        node = self._canvas.selected_node()
        if doc is None or node is None or node.type != "selection":
            return
        from ui.clip_finder import ClipFinderDialog
        recorded = node.config.get("clip_pool_dir")
        dialog = ClipFinderDialog(
            self,
            source_dir=self._clip_finder_source(node),
            run_dir=Path(recorded) if recorded else None,
        )
        dialog.exec()
        changed = False
        if dialog.pool_dir is not None:
            changed |= node.config.get("clip_pool_dir") != str(dialog.pool_dir)
            node.config["clip_pool_dir"] = str(dialog.pool_dir)
        if dialog.exported_dir is not None:
            changed |= (node.config.get("clip_export_dir")
                        != str(dialog.exported_dir))
            node.config["clip_export_dir"] = str(dialog.exported_dir)
        if changed:
            self._save_current()
            self._on_node_selected(node)

    def _episode_count(self, paths: list[Path]) -> int:
        return sum(len(list_episodes(p)) if p.is_dir() else 1 for p in paths)

    def _send_to(self, destination: str, paths: list[Path]) -> None:
        """Hand the selection to another screen and go there.

        `destination` is a key in SEND_TARGETS. Everything routes through here
        so the menu, the pipeline nodes and any future button cannot drift
        apart about what "send to Human coding" means.
        """
        if not paths:
            return
        first = paths[0]
        episodes = self._episode_count(paths)

        if destination == "queue":
            added = self._automated.enqueue(paths)
            self._tabs.setCurrentWidget(self._automated)
            self.statusBar().showMessage(
                f"Queued {added} entr{'y' if added == 1 else 'ies'} "
                f"({episodes} episode{'s' if episodes != 1 else ''}). "
                f"Press Analyze to start.", 8000)
            return

        if destination == "analyze":
            self._automated.set_target(first)
            self._tabs.setCurrentWidget(self._automated)
            self.statusBar().showMessage(
                f"{first.name} is the analysis target. Press Analyze to "
                f"measure it.", 8000)
            return

        if destination == "transcribe":
            self._automated.enqueue(paths)
            self._tabs.setCurrentWidget(self._automated)
            self.statusBar().showMessage(
                f"{episodes} episode{'s' if episodes != 1 else ''} queued. "
                f"Press Transcribe Missing Subtitles to run Whisper on the "
                f"ones with no captions.", 10000)
            return

        if destination in ("code", "validate"):
            self._handcoding.set_target(first)
            self._tabs.setCurrentWidget(self._handcoding)
            self._handcoding.show_view(
                "Code" if destination == "code" else "Validate tool")
            self.statusBar().showMessage(
                f"{first.name} is ready in Human coding. "
                + ("Press Open Episode to load the video."
                   if destination == "code" else
                   "Run the detector, then Compare against your coding."),
                10000)
            return

        if destination == "index":
            self._tabs.setCurrentWidget(self._index)
            self._index.focus_episode(str(first))
            return

        if destination == "language":
            self._tabs.setCurrentWidget(self._language)
            self._language.show_view("Speech")
            self.statusBar().showMessage(
                "Language → Speech lists every episode with speech data. "
                "Press Refresh if this one is missing.", 8000)
            return

    def _reveal(self, paths: list[Path]) -> None:
        """Show the file in the platform's file manager."""
        import os
        import subprocess
        import sys
        if not paths:
            return
        target = paths[0]
        if not target.exists():
            self.statusBar().showMessage(
                f"{target.name} is listed but no longer on disk.", 6000)
            return
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", str(target)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target.parent)])
        except Exception as exc:            # noqa: BLE001 — shown, not hidden
            self.statusBar().showMessage(f"Could not open the folder: {exc}",
                                         6000)

    def _library_menu(self, point) -> None:
        """Right-click on the Library tree."""
        self.build_library_menu().exec(
            self._tree.viewport().mapToGlobal(point))

    def build_library_menu(self) -> QMenu:
        """The menu for the current selection.

        Built separately from showing it so the entries and their enabled
        states can be checked without a display — the whole point of this menu
        is which destinations are offered for which selection.
        """
        paths = self._selected_paths()
        menu = QMenu(self)
        if not paths:
            act = menu.addAction("No episode or show selected")
            act.setEnabled(False)
            return menu

        episodes = self._episode_count(paths)
        files = [p for p in paths if p.is_file()]
        many = len(paths) > 1
        subject = (f"{len(paths)} items — {episodes} episodes" if many
                   else paths[0].name)

        header = menu.addAction(subject)
        header.setEnabled(False)
        menu.addSeparator()

        # Measurement first: it is what most selections are for.
        if not many:
            menu.addAction(
                "Analyze this now…",
                lambda: self._send_to("analyze", paths))
        menu.addAction(
            f"Add to analysis queue ({episodes} episode"
            f"{'s' if episodes != 1 else ''})",
            lambda: self._send_to("queue", paths))
        menu.addAction(
            "Queue for Transcribe Missing Subtitles…",
            lambda: self._send_to("transcribe", paths))
        menu.addSeparator()

        # Hand coding needs one episode, not a folder.
        code = menu.addAction("Code by hand…",
                              lambda: self._send_to("code", files))
        validate = menu.addAction("Validate the tool against coding…",
                                  lambda: self._send_to("validate", files))
        for act in (code, validate):
            act.setEnabled(len(files) == 1)
            if len(files) != 1:
                act.setToolTip("Select a single episode — hand coding is per "
                               "episode, not per show.")
        menu.addSeparator()

        show_index = menu.addAction("Show in Index",
                                    lambda: self._send_to("index", files))
        show_index.setEnabled(len(files) == 1)
        menu.addAction("Speech and vocabulary…",
                       lambda: self._send_to("language", paths))
        menu.addSeparator()
        reveal = menu.addAction("Reveal in File Explorer",
                                lambda: self._reveal(paths))
        reveal.setEnabled(bool(paths))
        return menu

    # ---- episode metadata and notes ----
    #
    # Both live in the index, not in the cache: they are things a PERSON
    # recorded, so re-analysing an episode must not wipe them. Air date drives
    # era stratification in the sampler and the air-date column on the Language
    # screen, which is why it is editable here rather than only importable.

    def _details_panel(self) -> QWidget:
        from PySide6.QtWidgets import QLineEdit, QPlainTextEdit
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(4)

        meta = QWidget()
        row = QHBoxLayout(meta)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(QLabel("Air date:"))
        self._meta_air = QLineEdit()
        self._meta_air.setMaximumWidth(96)
        self._meta_air.setPlaceholderText("any format")
        row.addWidget(self._meta_air)
        row.addWidget(QLabel("Season:"))
        self._meta_season = QLineEdit()
        self._meta_season.setMaximumWidth(44)
        row.addWidget(self._meta_season)
        row.addWidget(QLabel("Episode:"))
        self._meta_episode = QLineEdit()
        self._meta_episode.setMaximumWidth(44)
        row.addWidget(self._meta_episode)
        self._btn_meta = QPushButton("Save Metadata")
        self._btn_meta.clicked.connect(self._save_metadata)
        row.addWidget(self._btn_meta)
        row.addStretch(1)
        lay.addWidget(meta)

        self._notes = QPlainTextEdit()
        self._notes.setMaximumHeight(56)
        self._notes.setPlaceholderText(
            "Notes on this episode — kept in the index, not the cache, so "
            "re-analysing does not erase them.")
        lay.addWidget(self._notes)
        self._btn_note = QPushButton("Save Note")
        self._btn_note.clicked.connect(self._save_note)
        note_row = QHBoxLayout()
        note_row.addStretch(1)
        note_row.addWidget(self._btn_note)
        lay.addLayout(note_row)

        self._details_page = page
        self._details_episode: Path | None = None
        page.setEnabled(False)
        return page

    def _db(self):
        """The index connection, opened once and kept."""
        if not self._root:
            return None
        conn = getattr(self, "_conn", None)
        if conn is None:
            try:
                from analyzer.db import get_db
                conn = self._conn = get_db(self._root)
            except Exception:
                return None
        return conn

    def _show_episode_details(self, episode: Path | None) -> None:
        """Fill the metadata and notes fields for the selected episode."""
        self._details_episode = episode
        self._details_page.setEnabled(episode is not None)
        if episode is None:
            for field in (self._meta_air, self._meta_season,
                          self._meta_episode):
                field.clear()
            self._notes.setPlainText("")
            return
        conn = self._db()
        if conn is None:
            return
        try:
            from analyzer.db import get_episode_metadata, get_note
            meta = get_episode_metadata(conn, str(episode))
            note = get_note(conn, str(episode))
        except Exception:
            return
        self._meta_air.setText(meta.get("air_date") or "")
        season, number = meta.get("season_num"), meta.get("episode_num")
        self._meta_season.setText("" if season is None else str(season))
        self._meta_episode.setText("" if number is None else str(number))
        self._notes.setPlainText(note or "")

    def _save_metadata(self) -> None:
        conn = self._db()
        if conn is None or self._details_episode is None:
            return

        def _number(text: str):
            text = text.strip()
            if not text:
                return None
            try:
                return int(text)
            except ValueError:
                return None

        season_text = self._meta_season.text().strip()
        episode_text = self._meta_episode.text().strip()
        season, number = _number(season_text), _number(episode_text)
        # Silently storing None for "abc" would look like the save worked.
        bad = [name for name, text, value in
               (("Season", season_text, season),
                ("Episode", episode_text, number))
               if text and value is None]
        if bad:
            QMessageBox.warning(
                self, "Metadata",
                f"{' and '.join(bad)} must be a whole number, or blank.")
            return
        try:
            from analyzer.db import upsert_episode_metadata
            upsert_episode_metadata(
                conn, str(self._details_episode),
                self._meta_air.text().strip() or None, season, number)
        except Exception as exc:            # noqa: BLE001 — shown, not hidden
            QMessageBox.warning(self, "Could not save metadata", str(exc))
            return
        self._index.refresh()
        self.statusBar().showMessage(
            f"Saved metadata for {self._details_episode.name}. Air dates feed "
            f"era stratification in the sampler.", 8000)

    def _save_note(self) -> None:
        conn = self._db()
        if conn is None or self._details_episode is None:
            return
        try:
            from analyzer.db import save_note
            save_note(conn, str(self._details_episode),
                      self._notes.toPlainText())
        except Exception as exc:            # noqa: BLE001 — shown, not hidden
            QMessageBox.warning(self, "Could not save note", str(exc))
            return
        self.statusBar().showMessage(
            f"Saved note for {self._details_episode.name}.", 6000)

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
        # The index lives under the root, so a cached connection to the
        # previous project's database would silently answer for this one.
        conn = getattr(self, "_conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        self._conn = None
        # Constructs a researcher wrote live under the root
        # (<root>/.analysis/constructs), so they belong to the library being
        # opened. Loaded HERE, before anything reads a construct, because
        # `set_library` replaces the loaded set wholesale — without it, opening
        # a second library would leave the first one's constructs answering
        # `get_construct`, and a recipe would resolve its construct against a
        # definition from a different project.
        C.set_library(folder)
        self._show_episode_details(None)
        # Samples are discovered under the root, so both the chooser and the
        # current scope belong to the library being opened, not the last one.
        self._scope = library_scope()
        self._automated.set_scope(self._scope)
        self._handcoding.set_scope(self._scope)
        self._language.set_scope(self._scope)
        self._constructs.set_scope(self._scope)
        self.populate()
        # Pipelines live under the root (<root>/.analysis/pipelines), so the
        # list has to be rebuilt when the root changes. Without this the tab
        # keeps whatever was found before a root was known — which is the
        # fallback location, not the project's own pipelines.
        #
        # This also rebuilds the scope chooser, at the end rather than here:
        # the chooser now offers pipelines as well as samples, so it has to be
        # built AFTER `self._docs` is loaded or every pipeline entry is
        # missing on the first draw of the list. Doing it once, there, also
        # keeps a root change to one `build_pipelines` pass rather than two.
        self._discover_pipelines()

    def populate(self) -> None:
        """Fill the tree with the episodes the current scope admits.

        Under the whole-library scope this walks the root exactly as it always
        did. Under a sample's scope a show contributes only its drawn
        episodes, and a show that drew none is left out rather than shown
        empty — an empty row would read as a show with no files.
        """
        self._model.removeRows(0, self._model.rowCount())
        if not self._root:
            self._sync_scope_note(0)
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
                if node[0].rowCount() == 0:
                    # Every show under this category was filtered out, so the
                    # category has nothing to group.
                    self._model.removeRow(node[0].row())
            else:
                s, e = self._add_show(None, path)
                shows += s
                episodes += e

        self._tree.expandAll()
        self._release_columns()
        self._sync_scope_note(episodes)
        if hasattr(self, "_index"):
            self._index.refresh()
            self._trials.refresh()
            # Recipes live under the root, so the diagram's chooser has to be
            # rebuilt when the root changes — the same reason the pipeline list
            # is rebuilt there.
            self._constructs.refresh()
        self._count.setText(
            f"{shows} show{'s' if shows != 1 else ''}, "
            f"{episodes} episode{'s' if episodes != 1 else ''}")
        self.statusBar().showMessage(
            f"{shows} shows, {episodes} episodes in {self._root} "
            f"({self._scope.describe()})")

    # ---- the research context ----
    #
    # One scope, set here and read by the Library. `analyzer/scope.py` owns
    # what a scope IS; this owns which one is current. The distinction is the
    # north-star spec's — the Qt layer must not become the source of truth for
    # research state.

    def set_scope(self, scope: Scope, announce: bool = True) -> None:
        """Make *scope* current and redraw the Library."""
        self._scope = scope
        self._select_scope_in_chooser()
        self.populate()          # also refreshes the Index, which obeys it too
        # The measurement tabs stage the working set rather than filtering to
        # it: a scope is a view, and these screens are where work is started.
        self._automated.set_scope(scope)
        self._handcoding.set_scope(scope)
        self._language.set_scope(scope)
        # Constructs is a VIEW, not a workbench, so it narrows rather than
        # stages (`DECISIONS.md` § *A view narrows to the scope; a workbench
        # stages from it*). It also drops any computed contributions, because
        # those were means over a different set of episodes.
        self._constructs.set_scope(scope)
        if announce:
            self.statusBar().showMessage(
                f"Showing {scope.describe()}.", 8000)

    def _doc_sample_pipelines(self, doc, by_key: dict) -> list:
        """Every sample a PIPELINE DOCUMENT draws on, in canvas order.

        A Sampling node's own `sample_key` if it has one, else the document's
        `source_key` — the same fallback `PipelineDoc.upstream_sample_keys`
        applies per node, so a pipeline saved before per-node binding existed
        resolves identically here. A document with no Sampling node at all
        still resolves through `source_key`, so an older diagram that never
        had one keeps reporting what it always did.

        One implementation, because both the chooser (`_doc_scope`) and
        pipeline selection (`_follow_pipeline_scope`) ask this question and
        must not answer it differently — see `LEARNINGS.md` on the two
        copies of "which sample does this belong to" that drifted apart.
        """
        keys: list[str] = []
        for node in doc.nodes:
            if node.type != "sampling":
                continue
            key = node.config.get("sample_key") or doc.source_key
            if key and key not in keys:
                keys.append(key)
        if not keys and doc.source_key:
            keys = [doc.source_key]
        return [by_key[k] for k in keys if k in by_key]

    def _doc_scope(self, doc, by_key: dict):
        """A scope over every sample a PIPELINE DOCUMENT draws on, or None.

        Returns None for a document resolving to fewer than two samples: one
        sample is already its own entry in the chooser, and a duplicate under
        another name would just be noise in a list that is long already.
        """
        pipelines = self._doc_sample_pipelines(doc, by_key)
        folders = [p.folder for p in pipelines if p.folder]
        if len(pipelines) < 2 or len(folders) < 2:
            return None
        return scope_from_draws(f"pipeline:{doc.id}",
                                f"{doc.name} (whole pipeline)", folders)

    def _rebuild_scope_choices(self) -> None:
        """Rebuild the chooser: the whole library, every drawn sample, then
        every pipeline that combines more than one of them.

        Samples come from `build_pipelines`, so the list is whatever is
        actually on disk under the root. The synthetic "Unsampled work"
        pipeline is excluded by `scope_from_pipeline` — it has no draw folder
        and its episode paths are placeholders.

        **Pipelines are offered as well as samples**, and the distinction is
        the point: this control used to list drawn samples ONLY, so a
        pipeline built from two Sampling nodes could not be expressed here at
        all — picking any entry narrowed to one branch, and the researcher
        saw one show at a time with no way to ask for the study they had
        actually built. A pipeline is a working set in its own right (it is
        what `CLAUDE.md` calls the workflow the user owns); a sample is one
        draw inside it. Both belong in a chooser whose whole job is naming
        the current research context.

        This is the expensive half of the chooser (`build_pipelines` alone
        measured 1524 ms on this working copy, see `TODO.md`), so call it only
        when the discoverable set can actually have changed: the root changes,
        a sample is drawn, or a pipeline's own sample bindings change. Picking
        a *different* entry from an already-built list never changes what is
        discoverable — that path goes through `_select_scope_in_chooser`
        instead, which is O(choices) with no disk I/O.
        """
        if not hasattr(self, "_scope_pick"):
            return
        entries: list[tuple[str, Scope]] = [(LIBRARY_LABEL, library_scope())]
        by_key: dict = {}
        try:
            for pipeline in build_pipelines(self._root):
                by_key[pipeline.key] = pipeline
                scope = scope_from_pipeline(pipeline)
                if scope is not None:
                    entries.append((scope.describe(), scope))
        except Exception:
            pass                      # a scope list is not worth a crash

        # Documents are read from `self._docs` rather than re-listed: the
        # chooser must agree with the pipeline picker beside it, and re-reading
        # disk here could disagree with a document edited but not yet saved.
        for doc in getattr(self, "_docs", None) or []:
            try:
                scope = self._doc_scope(doc, by_key)
            except Exception:
                continue
            if scope is not None:
                entries.append((scope.describe(), scope))

        # Two draws of one show can carry the same sample name — this library
        # has two "Spongebob Squarepants Season 1 (spread)" — so a repeated
        # label gets its draw folder, which is dated and unique. Picking the
        # wrong sample would silently scope a study to the wrong episodes.
        # Keyed on the sample NAME, not on the rendered label: two draws of one
        # show differ only by episode count, so the labels are technically
        # distinct and a naive collision check never fires. "(spread) — 9
        # episodes" against "— 6 episodes" is not something to pick between at
        # a glance, and picking wrong scopes a study to the wrong episodes.
        seen: dict[str, int] = {}
        for _label, scope in entries:
            seen[scope.label] = seen.get(scope.label, 0) + 1
        entries = [
            ((f"{label}  ({scope.folder.name})"
              if seen[scope.label] > 1 and scope.folder else label), scope)
            for label, scope in entries
        ]
        # A scope set before its draw is discoverable — the sample written
        # moments ago — is added rather than dropped. Silently falling back to
        # the whole library here would leave the chooser disagreeing with the
        # tree, which is the one thing this control must never do.
        if not self._scope.is_library and \
                not any(s.key == self._scope.key for _l, s in entries):
            entries.append((self._scope.describe(), self._scope))

        self._scope_choices = [s for _label, s in entries]
        self._scope_pick.blockSignals(True)
        self._scope_pick.clear()
        for label, _scope in entries:
            self._scope_pick.addItem(label)
        self._scope_pick.setCurrentIndex(
            next((i for i, s in enumerate(self._scope_choices)
                  if s.key == self._scope.key), 0))
        self._scope_pick.blockSignals(False)

    def _select_scope_in_chooser(self) -> None:
        """Move the chooser to `self._scope` without rediscovering samples.

        The common case: `_on_scope_picked` already found this scope in
        `self._scope_choices` (it came from the dropdown), so this is just
        setting the combo box's index to match — no `build_pipelines` call.

        Falls back to a full `_rebuild_scope_choices` when the scope is not
        already known, which is the one case rebuilding can't be skipped: a
        sample drawn moments ago (`open_sampler`) or a pipeline's linked
        sample (`_follow_pipeline_scope`) may not be in the list yet. Without
        this fallback the chooser would disagree with the tree, which its own
        comments call the one thing this control must never do.
        """
        if not hasattr(self, "_scope_pick"):
            return
        choices = getattr(self, "_scope_choices", [])
        index = next((i for i, s in enumerate(choices)
                      if s.key == self._scope.key), None)
        if index is None:
            self._rebuild_scope_choices()
            return
        self._scope_pick.blockSignals(True)
        self._scope_pick.setCurrentIndex(index)
        self._scope_pick.blockSignals(False)

    def _on_scope_picked(self, index: int) -> None:
        choices = getattr(self, "_scope_choices", [])
        if 0 <= index < len(choices):
            self.set_scope(choices[index])

    def _sync_scope_note(self, shown: int) -> None:
        """The line beside the chooser: what this scope is, in one sentence.

        *shown* is how many episodes the tree ended up with, which is not
        always how many the sample drew. The Library lists `.mp4` only
        (`show_index.list_episodes`) while the sampler draws six extensions,
        so a draw can legitimately contain a file this screen cannot show. It
        says so rather than displaying a count that disagrees with the rows
        underneath it — see `LEARNINGS.md` on numbers that display correctly.
        """
        if not hasattr(self, "_scope_note"):
            return
        if self._scope.is_library:
            self._scope_note.setText("every episode under the root folder")
            return
        parts = [f"the {self._scope.total_drawn} episodes this sample drew"]
        if self._scope.missing:
            parts.append(f"{len(self._scope.missing)} no longer on disk")
        unlistable = len(self._scope.episodes) - shown
        if unlistable > 0:
            parts.append(f"{unlistable} not shown here — the Library lists "
                         f".mp4 files only")
        self._scope_note.setText(" — ".join(parts))

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
        eps = [ep for ep in list_episodes(show_dir) if self._scope.contains(ep)]
        # A show with nothing in scope is omitted, not shown empty. Under the
        # whole-library scope nothing is filtered, so a genuinely empty show
        # folder still appears and still reads "empty".
        if not eps and not self._scope.is_library:
            return 0, 0
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
        result = self._cached(show_key(self._root, path.parent), path.stem)
        if result is not None:
            self._report.setHtml(episode_html(result))
            self._set_export_source(episode=result)
            self._show_episode_details(path)
            self._tabs.setCurrentWidget(self._library_page)

    def _on_select(self, *_args) -> None:
        idx = self._tree.selectionModel().currentIndex()
        if not idx.isValid():
            return
        item = self._model.itemFromIndex(idx.siblingAtColumn(COL_NAME))
        payload = item.data(Qt.UserRole)
        if not payload:
            show_dir = self._show_dir_for(item)
            self._selected = ("show", show_dir) if show_dir else None
            self._sync_compare()
            self._automated.set_target(show_dir)
            self._show_report(show_dir, item.text())
            return
        ep = Path(payload)
        self._selected = ("episode", ep)
        self._sync_compare()
        self._automated.set_target(ep)
        self._handcoding.set_target(ep)
        result = self._cached(show_key(self._root, ep.parent), ep.stem)
        if result is None:
            self._report.setHtml(
                f"<p style='color:#54595d'><b>{ep.name}</b><br>"
                "Not analyzed yet. Run it from Automated coding; the result "
                "appears here when it finishes.</p>")
            self._set_export_source()
            self._show_episode_details(ep)
            return
        self._chart_source = None
        self._btn_chart.setEnabled(False)
        events = None
        try:
            from analyzer.event_coding import latest_rates_for_stem
            events = latest_rates_for_stem(ep.stem)
        except Exception:
            pass
        self._report.setHtml(episode_html(result, events=events))
        self._set_export_source(episode=result)
        self._show_episode_details(ep)

    def _open_chart(self) -> None:
        """The chart for the selected show. matplotlib is imported here, not
        at module scope: it costs about a second to load and the Library
        should not pay that to show a table."""
        if not self._chart_source:
            return
        show_name, results = self._chart_source
        try:
            from ui.chart import ChartDialog
        except ImportError as exc:
            QMessageBox.information(
                self, "Chart unavailable",
                f"matplotlib is needed for the chart: {exc}\n\n"
                f"Install it with:  pip install matplotlib")
            return
        dialog = ChartDialog(show_name, results, self._cfg, self)
        dialog.show()
        # Held so it is not collected the moment this method returns.
        self._chart_window = dialog

    def _cached(self, skey: str, stem: str):
        """A cached episode, re-scored with the settings in force.

        The composite is a weighted sum over numbers already measured, so it
        is recomputed on read rather than stored. Without this the Settings
        dialog's "Apply & Re-score" changed the weights and every screen went
        on showing the score the cache was written with — the promise that
        button makes is exactly this call.

        The re-derivation itself lives in the engine — `cli.py` reads cached
        results too, and two copies of this rule is how they came to print
        different composites for one episode.
        """
        from analyzer.cache import load_scored
        return load_scored(self._root, skey, stem, self._cfg)

    def _show_report(self, show_dir, label: str) -> None:
        """The aggregate for a show row, from whatever is cached for it."""
        self._chart_source = None
        self._btn_chart.setEnabled(False)
        if show_dir is None:
            self._report.setHtml(
                f"<p style='color:{color('text_dim')}'>{label} groups shows "
                f"rather than episodes. Open one of the shows inside it.</p>")
            self._set_export_source()
            self._show_episode_details(None)
            return
        skey = show_key(self._root, show_dir)
        results = []
        for episode in list_episodes(show_dir):
            result = self._cached(skey, episode.stem)
            if result is not None:
                results.append(result)
        aggregate = compute_show_aggregate(show_dir.name, results)
        # How many episodes the show HAS, so the report can distinguish the
        # three states that matter: measured, failed, and not analysed yet.
        # `results` holds only what is cached, so anything missing from it has
        # simply not been run — reporting that as a failure would describe
        # work that has not been done as work that went wrong.
        aggregate.episode_count = len(list_episodes(show_dir))
        self._report.setHtml(show_html(aggregate, results, show_dir.name))
        self._show_episode_details(None)
        self._set_export_source(
            show=(show_dir.name, results) if results else None)
        if results:
            self._chart_source = (show_dir.name, results)
            self._btn_chart.setEnabled(True)

    def _show_full_series(self) -> None:
        """One aggregate over every analysed episode in the whole library.

        A season is a show folder here, so a series split across season
        folders has no single row in the tree. This is that row: the same
        `compute_show_aggregate` over everything cached under the root, which
        is what makes a cross-season comparison possible at all.

        Nothing is written. The Tk build saved the aggregate to disk as a side
        effect of viewing it; a view should not change the data it is a view
        of.
        """
        if not self._root:
            self.statusBar().showMessage("Choose a root folder first.", 6000)
            return
        shows = list_shows(self._root)
        results, total = [], 0
        for show_dir in shows:
            skey = show_key(self._root, show_dir)
            episodes = list_episodes(show_dir)
            total += len(episodes)
            for episode in episodes:
                result = self._cached(skey, episode.stem)
                if result is not None:
                    results.append(result)

        name = self._root.name
        self._chart_source = None
        self._btn_chart.setEnabled(False)
        if not results:
            self._report.setHtml(
                f"<p style='color:{color('text_dim')}'><b>{name}</b><br>"
                f"{total} episode{'s' if total != 1 else ''} across "
                f"{len(shows)} folder{'s' if len(shows) != 1 else ''}, none "
                f"analysed yet. Run some from Automated coding, then try "
                f"again.</p>")
            self._set_export_source()
            self._tabs.setCurrentWidget(self._library_page)
            return
        aggregate = compute_show_aggregate(name, results)
        aggregate.episode_count = total
        self._report.setHtml(show_html(aggregate, results, name))
        self._show_episode_details(None)
        self._set_export_source(show=(name, results))
        self._chart_source = (name, results)
        self._btn_chart.setEnabled(True)
        self._tabs.setCurrentWidget(self._library_page)
        self.statusBar().showMessage(
            f"{len(results)} of {total} episodes across {len(shows)} folders, "
            f"each weighted equally.", 8000)

    # ---- pin and compare ----

    def _sync_compare(self) -> None:
        self._btn_pin.setEnabled(self._selected is not None)
        # Like with like only: an episode against a show aggregate would put
        # one episode's numbers beside a mean of many and call it a difference.
        self._btn_compare.setEnabled(
            self._selected is not None and self._pinned is not None
            and self._selected[0] == self._pinned[0]
            and self._selected[1] != self._pinned[1])

    def _pin_for_compare(self) -> None:
        if self._selected is None:
            return
        self._pinned = self._selected
        kind, path = self._pinned
        self._btn_pin.setText(f"Pinned: {path.name[:24]}")
        self._sync_compare()
        self.statusBar().showMessage(
            f"Pinned {path.name}. Select another {kind} and press Compare "
            f"with Pinned.", 8000)

    def _open_compare(self) -> None:
        """Two episodes, or two shows, side by side."""
        if self._selected is None or self._pinned is None:
            return
        kind, path = self._selected
        _pin_kind, pin_path = self._pinned

        if kind == "episode":
            left = self._cached(show_key(self._root, pin_path.parent),
                                pin_path.stem)
            right = self._cached(show_key(self._root, path.parent), path.stem)
            if left is None or right is None:
                QMessageBox.information(
                    self, "Compare",
                    "Both episodes have to be analysed before they can be "
                    "compared. Run the missing one from Automated coding.")
                return
            names = (pin_path.name, path.name)
        else:
            left = self._show_aggregate(pin_path)
            right = self._show_aggregate(path)
            if left is None or right is None:
                QMessageBox.information(
                    self, "Compare",
                    "Both shows need at least one analysed episode before "
                    "they can be compared.")
                return
            names = (pin_path.name, path.name)

        from ui.compare import CompareDialog
        dialog = CompareDialog(left, right, names[0], names[1], kind, self)
        dialog.show()
        self._compare_window = dialog      # keep it alive

    def _show_aggregate(self, show_dir: Path):
        key = show_key(self._root, show_dir)
        results = [r for r in
                   (self._cached(key, e.stem) for e in list_episodes(show_dir))
                   if r is not None]
        if not results:
            return None
        aggregate = compute_show_aggregate(show_dir.name, results)
        aggregate.episode_count = len(results)
        return aggregate

    # ---- one drawn sample ----

    def _show_sample_aggregate(self) -> None:
        """The aggregate over exactly the episodes one sample drew.

        A show aggregate answers "what is this show like"; this answers "what
        is the set I actually drew like", which is the set every figure in a
        write-up is really about. They differ whenever the sample is not a
        census, so conflating them would misdescribe the study.
        """
        chosen, _f = QFileDialog.getOpenFileName(
            self, "Open a sample manifest", str(self._root or ""),
            "Sample manifest (manifest.json);;JSON (*.json)")
        if not chosen:
            return
        folder = Path(chosen).parent
        from analyzer.scope import read_selected
        episodes = read_selected(folder)
        if not episodes:
            QMessageBox.information(
                self, "Sample Aggregate",
                f"No selected.csv with episode paths was found beside "
                f"{Path(chosen).name}. The sampler writes the two together.")
            return

        results, missing = [], 0
        for episode in episodes:
            if not episode.exists():
                missing += 1
                continue
            result = self._cached(show_key(self._root, episode.parent),
                                  episode.stem)
            if result is not None:
                results.append(result)

        name = folder.name
        self._chart_source = None
        self._btn_chart.setEnabled(False)
        self._show_episode_details(None)
        if not results:
            self._report.setHtml(
                f"<p style='color:{color('text_dim')}'><b>{name}</b><br>"
                f"{len(episodes)} episode"
                f"{'s' if len(episodes) != 1 else ''} in this sample, none of "
                f"them analysed yet. Send the sample to the analysis queue "
                f"from the Episode Sampler, or analyse them from the "
                f"Library.</p>")
            self._set_export_source()
            self._tabs.setCurrentWidget(self._library_page)
            return
        aggregate = compute_show_aggregate(name, results)
        aggregate.episode_count = len(episodes)
        self._report.setHtml(show_html(aggregate, results, name))
        self._set_export_source(show=(name, results))
        self._chart_source = (name, results)
        self._btn_chart.setEnabled(True)
        self._tabs.setCurrentWidget(self._library_page)
        message = (f"{len(results)} of {len(episodes)} sampled episodes "
                   f"analysed.")
        if missing:
            message += (f" {missing} file"
                        f"{'s are' if missing != 1 else ' is'} named in the "
                        f"sample but not on disk.")
        self.statusBar().showMessage(message, 10000)

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


def run() -> int:
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    theme.apply(app)
    win = MainWindow()
    win.show()
    return app.exec()
