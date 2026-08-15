"""
ui/index_tab.py — the Index tab: everything measured, in one sortable table.

Reads the SQLite index through analyzer.db, which is also what `cli.py db`
reads, so the two cannot disagree. Sorting goes back to the database rather
than sorting the widget: the sanctioned sort columns live in `_EP_SORT_COLS`
and `_SHOW_SORT_COLS`, and a string sort in the view would order "10" before
"9" on every numeric column.

STIMULUS-ONLY GUARDRAIL. The shows table carries `target_age_min` and
`target_age_max`, imported alongside the rest of a show's metadata. They are
deliberately not columns here and must not become ones: a target audience age
is a claim about the viewer, and this tool reports properties of the video.
A test enforces it.

Values unusual for the set on screen are marked with a glyph and a legend
naming that set — never with a colour, which reads as a verdict whatever the
caption says.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFrame, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from analyzer.db import (
    get_db, query_episodes, remove_stale_episodes, summarise_shows,
)
from ui.tokens import OUTLIER_LEGEND

# Database columns produced by a measurement the registry has never graded.
# CLAUDE.md §2.2 requires the flag WHEREVER the numbers appear, and a table is
# where most of them appear. Derived from the registry rather than listed by
# hand, so a tool that gains or loses validation changes this automatically.
UNVALIDATED_MARK = "\u2020"                      # dagger


def unvalidated_columns() -> dict[str, str]:
    """{database column: why it is flagged} for the columns shown here."""
    from analyzer.measurements import MEASUREMENTS, ungraded_measurements
    # Which measurement each database column comes out of.
    produced_by = {
        "cuts_per_min": "transitions",
        "color_saturation_mean": "color",
        "motion_mean": "motion",
        "flashing_events_per_min": "flashing",
        "audio_rms_mean": "audio",
        "avg_cuts_per_min": "transitions",
        "avg_saturation": "color",
        "avg_motion": "motion",
        "avg_flashing": "flashing",
        "avg_audio_rms": "audio",
    }
    reasons = dict(ungraded_measurements())
    by_key = {m.key: m.name for m in MEASUREMENTS}
    out: dict[str, str] = {}
    for column, key in produced_by.items():
        name = by_key.get(key)
        if name in reasons:
            out[column] = reasons[name]
    return out


# (heading, database column, formatter). The database column is also the sort
# key, so a heading cannot be sorted by something it does not show.
EPISODE_COLUMNS = (
    ("Episode", "file_name", None),
    ("Show", "show_name", None),
    ("Duration", "duration_sec", lambda v: f"{v / 60:.1f} min" if v else "—"),
    ("Cuts/min", "cuts_per_min", lambda v: f"{v:.1f}" if v is not None else "—"),
    ("Saturation", "color_saturation_mean",
     lambda v: f"{v:.3f}" if v is not None else "—"),
    ("Motion", "motion_mean", lambda v: f"{v:.4f}" if v is not None else "—"),
    ("Flashing/min", "flashing_events_per_min",
     lambda v: f"{v:.2f}" if v is not None else "—"),
    ("Audio RMS", "audio_rms_mean",
     lambda v: f"{v:.4f}" if v is not None else "—"),
    ("Sensory load", "sensory_load_score",
     lambda v: f"{v:.3f}" if v is not None else "—"),
    ("Analyzed", "analyzed_at", lambda v: str(v)[:10] if v else "—"),
)

SHOW_COLUMNS = (
    ("Show", "show_name", None),
    ("Episodes", "episode_count", lambda v: str(v or 0)),
    ("Mean load", "avg_load", lambda v: f"{v:.3f}" if v is not None else "—"),
    ("Mean cuts/min", "avg_cuts_per_min",
     lambda v: f"{v:.1f}" if v is not None else "—"),
    ("Mean motion", "avg_motion", lambda v: f"{v:.4f}" if v is not None else "—"),
    ("Mean saturation", "avg_saturation",
     lambda v: f"{v:.3f}" if v is not None else "—"),
    ("Mean flashing", "avg_flashing",
     lambda v: f"{v:.2f}" if v is not None else "—"),
    ("Updated", "updated_at", lambda v: str(v)[:10] if v else "—"),
)

# Never a column here. See the guardrail note in the module docstring.
FORBIDDEN_COLUMNS = ("target_age_min", "target_age_max")

HIGH, LOW = "▲", "▽"


def _fences(values: list[float]) -> tuple[float, float] | None:
    """Tukey fences: Q1 − 1.5·IQR and Q3 + 1.5·IQR.

    Returns None below eight values, where a quartile is too thin to call
    anything unusual and the marks would be noise.
    """
    clean = sorted(v for v in values if v is not None)
    if len(clean) < 8:
        return None

    def q(p: float) -> float:
        pos = (len(clean) - 1) * p
        lo = int(pos)
        hi = min(lo + 1, len(clean) - 1)
        return clean[lo] + (clean[hi] - clean[lo]) * (pos - lo)

    q1, q3 = q(0.25), q(0.75)
    iqr = q3 - q1
    return q1 - 1.5 * iqr, q3 + 1.5 * iqr


class IndexTab(QWidget):
    """The indexed corpus, filterable and sortable."""

    episode_chosen = Signal(str)

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self._mode = "episodes"
        self._sort = "analyzed_at"
        self._ascending = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        from ui.main_window import Panel, SubToolBar
        bar = SubToolBar()
        self._scope = QComboBox()
        self._scope.addItems(["Episodes", "Shows"])
        self._scope.currentTextChanged.connect(self._switch_scope)
        bar.row.addWidget(self._scope)
        bar.row.addWidget(QLabel("Filter:"))
        self._filter = QLineEdit()
        self._filter.setPlaceholderText("show name")
        self._filter.setMinimumWidth(180)
        self._filter.textChanged.connect(self.refresh)
        bar.row.addWidget(self._filter)
        bar.row.addStretch(1)
        self._count = QLabel("")
        self._count.setProperty("role", "dim")
        bar.row.addWidget(self._count)
        self._btn_stale = QPushButton("Remove Stale…")
        self._btn_stale.setToolTip(
            "Delete index rows whose video file is no longer on disk.")
        self._btn_stale.clicked.connect(self._remove_stale)
        bar.row.addWidget(self._btn_stale)
        lay.addWidget(bar)

        holder = QWidget()
        hv = QVBoxLayout(holder)
        hv.setContentsMargins(8, 8, 8, 8)
        hv.setSpacing(6)

        self._panel = Panel("Indexed episodes")
        self._table = QTreeWidget()
        self._table.setRootIsDecorated(False)
        self._table.setUniformRowHeights(True)
        self._table.setProperty("inPanel", "true")
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setFrameShape(QFrame.NoFrame)
        self._table.header().setStretchLastSection(False)
        self._table.header().setSectionsClickable(True)
        self._table.header().sectionClicked.connect(self._sort_by_column)
        self._table.itemDoubleClicked.connect(self._open_episode)
        self._panel.body_layout.addWidget(self._table)
        hv.addWidget(self._panel, 1)

        self._legend = QLabel(OUTLIER_LEGEND)
        self._legend.setProperty("role", "dim")
        self._legend.setWordWrap(True)
        hv.addWidget(self._legend)

        lay.addWidget(holder, 1)

    # -- data -------------------------------------------------------------
    def _columns(self):
        return EPISODE_COLUMNS if self._mode == "episodes" else SHOW_COLUMNS

    def _switch_scope(self, text: str) -> None:
        self._mode = "episodes" if text == "Episodes" else "shows"
        self._sort = "analyzed_at" if self._mode == "episodes" else "avg_load"
        self._ascending = False
        self._panel.set_title(f"Indexed {self._mode}")
        self.refresh()

    def _sort_by_column(self, index: int) -> None:
        column = self._columns()[index][1]
        # Clicking the current column reverses it, as a table header does.
        self._ascending = not self._ascending if column == self._sort else True
        self._sort = column
        self.refresh()

    def refresh(self) -> None:
        self._table.clear()
        root = self._window._root
        if root is None:
            self._count.setText("no library loaded")
            return
        # One query, then the research context, then the summary — in that
        # order, so the Shows view is always a summary of exactly the episodes
        # the Episodes view would list. Reading the stored `shows` table
        # instead let the two disagree, and they did: a stored Spongebob row
        # read 2 episodes / 0.3071 mean load while the index held 5 averaging
        # 0.2557, because `upsert_show` only runs on a whole-show analysis.
        # NOTE: `self._scope` on this class is the Episodes/Shows mode combo,
        # which predates the research context and is a different idea. The
        # research context lives on the window.
        context = getattr(self._window, "_scope", None)
        try:
            conn = get_db(root)
            episodes = query_episodes(conn, sort_by=self._sort,
                                      ascending=self._ascending,
                                      filter_show=self._filter.text().strip())
            if context is not None and not context.is_library:
                episodes = [r for r in episodes
                            if r.get("file_path")
                            and context.contains(r["file_path"])]
            rows = episodes if self._mode == "episodes" else summarise_shows(
                episodes, sort_by=self._sort, ascending=self._ascending)
        except Exception as exc:            # noqa: BLE001 - shown, not hidden
            self._count.setText(f"index unavailable: {exc}")
            return

        columns = self._columns()
        flagged = unvalidated_columns()
        self._table.setColumnCount(len(columns))
        self._table.setHeaderLabels([
            (head + (UNVALIDATED_MARK if key in flagged else ""))
            + (f" {'▲' if self._ascending else '▼'}" if key == self._sort
               else "")
            for head, key, _ in columns])
        for index, (_head, key, _fmt) in enumerate(columns):
            if key in flagged:
                self._table.headerItem().setToolTip(index, flagged[key])

        load_key = "sensory_load_score" if self._mode == "episodes" \
            else "avg_load"
        fences = _fences([r.get(load_key) for r in rows])

        for row in rows:
            cells = []
            for _head, key, fmt in columns:
                value = row.get(key)
                cells.append(fmt(value) if fmt else str(value or "—"))
            item = QTreeWidgetItem(cells)
            for col in range(1, len(columns)):
                item.setTextAlignment(col, Qt.AlignRight | Qt.AlignVCenter)
            item.setTextAlignment(1, Qt.AlignLeft | Qt.AlignVCenter)
            if fences is not None and row.get(load_key) is not None:
                low, high = fences
                mark = (HIGH if row[load_key] > high
                        else LOW if row[load_key] < low else "")
                if mark:
                    col = [k for _h, k, _f in columns].index(load_key)
                    item.setText(col, f"{mark} {item.text(col)}")
            item.setData(0, Qt.UserRole, row.get("file_path", ""))
            self._table.addTopLevelItem(item)

        head = self._table.header()
        head.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, len(columns)):
            head.setSectionResizeMode(col, QHeaderView.ResizeToContents)

        noun = "episode" if self._mode == "episodes" else "show"
        # The set is named, not just counted: "6 episodes" over a narrowed
        # index reads as the whole corpus unless it says otherwise.
        where = ("" if context is None or context.is_library
                 else f"  in {context.label}")
        self._count.setText(
            f"{len(rows)} {noun}{'s' if len(rows) != 1 else ''}{where}")
        flagged_here = [head for head, key, _ in columns if key in flagged]
        lines = []
        if fences is not None:
            lines.append(
                f"{HIGH} above and {LOW} below the Tukey fences for the "
                f"{len(rows)} {noun}s listed here. {OUTLIER_LEGEND}")
        if flagged_here:
            plural = len(flagged_here) != 1
            lines.append(
                f"{UNVALIDATED_MARK} {', '.join(flagged_here)} "
                f"{'come' if plural else 'comes'} from "
                f"{'measurements' if plural else 'a measurement'} never "
                f"graded against hand coding. "
                f"{'They compare' if plural else 'It compares'} episodes "
                f"measured the same way; "
                f"{'they are' if plural else 'it is'} not "
                f"{'validated figures' if plural else 'a validated figure'}, "
                f"and flashing in particular is not a safety assessment.")
        self._legend.setVisible(bool(lines))
        self._legend.setText("  ".join(lines))

    # -- actions ----------------------------------------------------------
    def focus_episode(self, file_path: str) -> None:
        """Select and scroll to one episode's row.

        Called when the Library sends an episode here, so "Show in Index"
        lands on the row rather than on the top of a 13-row table.
        """
        if self._mode != "episodes":
            self._scope.setCurrentText("Episodes")
        self.refresh()
        wanted = str(file_path).replace("\\", "/").lower()
        for row in range(self._table.topLevelItemCount()):
            item = self._table.topLevelItem(row)
            stored = str(item.data(0, Qt.UserRole) or "").replace("\\", "/")
            if stored.lower() == wanted:
                self._table.setCurrentItem(item)
                self._table.scrollToItem(item)
                return
        self._window.statusBar().showMessage(
            f"{Path(file_path).name} is not in the index yet — analyse it "
            f"first.", 6000)

    def _open_episode(self, item, _column: int) -> None:
        path = item.data(0, Qt.UserRole)
        if path:
            self.episode_chosen.emit(path)

    def _remove_stale(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        root = self._window._root
        if root is None:
            return
        conn = get_db(root)
        removed = remove_stale_episodes(conn)
        conn.commit()
        QMessageBox.information(
            self, "Remove Stale",
            f"Removed {removed} index row{'s' if removed != 1 else ''} whose "
            f"video file is no longer on disk.\n\nCached analysis files are "
            f"not touched; a renamed show keeps its results and re-indexes "
            f"when it is analysed again.")
        self.refresh()
