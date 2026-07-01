"""
gui.py — Tkinter front-end for the Children's Media Analysis Toolkit (CMAT).

Architecture:
  - All analysis runs on a daemon worker thread.
  - The worker posts messages into a Queue; the main thread drains it every 50ms
    via root.after() — the only safe way to update Tkinter from another thread.
  - No analysis logic lives here; everything delegates to analyzer/.
"""

from __future__ import annotations
import copy
import json
import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from analyzer.aggregate import compute_show_aggregate, save_show_results
from analyzer.cache import load_cached, save_cache
from analyzer.config_loader import load_config, _base_dir
from analyzer.engine import analyze_episode
from analyzer.speech import transcribe_only, _find_cc_file
from analyzer.metrics_sensory import rescore_episode
from analyzer.schema import EpisodeResult, ShowAggregate
from analyzer.db import (
    get_db, upsert_episode, upsert_show, query_episodes, query_shows,
    get_note, save_note, get_episode_percentile, remove_stale_episodes,
    get_episode_metadata, upsert_episode_metadata, auto_set_season,
    get_show_metadata, upsert_show_metadata,
    get_show_eras, save_show_eras,
)
from analyzer.show_index import (
    list_episodes, list_shows, list_top_level, list_category_shows,
    show_key, display_show_name,
)
from gui_live import LiveAnalysisWindow
from gui_sampler import SamplerWindow
from gui_wiki_import import WikiImportDialog
from gui_tvmaze_import import TVMazeImportDialog


# ---------------------------------------------------------------------------
# Era editor dialog
# ---------------------------------------------------------------------------

class EraEditorDialog(tk.Toplevel):
    """Define named date-range eras for chart colour stratification.

    Eras are stored per-show in the index DB (show_eras table).
    The ``on_apply`` callback fires immediately when the user clicks Apply,
    so the chart redraws without closing the window first.
    """

    _DATE_FMTS = [
        "%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%Y/%m/%d",
        "%d %B %Y", "%B %d, %Y", "%B %d %Y",
        "%d-%b-%Y", "%d %b %Y", "%b %d, %Y", "%b %d %Y",
    ]

    def __init__(
        self,
        parent: tk.Misc,
        show_name: str,
        initial_eras: list[dict],
        db_conn=None,
        on_apply=None,
    ) -> None:
        super().__init__(parent)
        self.title(f"Define Eras — {show_name}")
        self.resizable(True, False)
        self._show_name = show_name
        self._db_conn   = db_conn
        self._on_apply  = on_apply
        self._eras: list[dict] = [dict(e) for e in initial_eras]

        self._build_ui()
        self._populate_tree()
        self.transient(parent)
        self.grab_set()
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2 - self.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2 - self.winfo_height() // 2
        self.geometry(f"+{max(0, px)}+{max(0, py)}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _norm_date(raw: str) -> str:
        from datetime import datetime
        raw = raw.strip()
        if not raw:
            return ""
        for fmt in EraEditorDialog._DATE_FMTS:
            try:
                return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
            except ValueError:
                pass
        return raw

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        pad = dict(padx=10, pady=4)

        tk.Label(
            self,
            text=(
                "Define date ranges to colour episodes by production era instead of season.\n"
                "Leave Start or End blank for open-ended ranges.  "
                "Colour is optional (hex, e.g. #E05C00)."
            ),
            justify=tk.LEFT, anchor="w", bg="#eef4ff", relief=tk.GROOVE,
            padx=8, pady=6, font=("TkDefaultFont", 9),
        ).pack(fill=tk.X, padx=10, pady=(10, 4))

        # treeview
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 4))
        cols   = ("name", "start", "end", "color")
        hdrs   = ("Era Name", "Start Date", "End Date", "Colour")
        widths = (190, 90, 90, 80)
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                   selectmode="browse", height=6)
        for col, hdr, w in zip(cols, hdrs, widths):
            self._tree.heading(col, text=hdr)
            self._tree.column(col, width=w, minwidth=30, stretch=(col == "name"))
        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Button(self, text="Remove Selected", command=self._remove_selected,
                  padx=6).pack(anchor="w", padx=10, pady=(0, 2))

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=6)

        # add-era form
        form = tk.Frame(self)
        form.pack(fill=tk.X, **pad)
        for col, lbl in enumerate(["Era Name *", "Start Date", "End Date", "Colour (optional)"]):
            tk.Label(form, text=lbl, anchor="w").grid(row=0, column=col, padx=4, sticky="w")
        self._ent_name  = tk.Entry(form, width=24)
        self._ent_start = tk.Entry(form, width=12)
        self._ent_end   = tk.Entry(form, width=12)
        self._ent_color = tk.Entry(form, width=10)
        for col, ent in enumerate([self._ent_name, self._ent_start,
                                    self._ent_end, self._ent_color]):
            ent.grid(row=1, column=col, padx=4, pady=2, sticky="w")
        tk.Label(form, text="(any date format — blank = open-ended)",
                 fg="#666666", font=("TkDefaultFont", 8),
                 ).grid(row=2, column=0, columnspan=4, sticky="w", padx=4)

        tk.Button(self, text="Add Era", command=self._add_era, padx=8,
                  ).pack(anchor="w", **pad)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=6)

        # bottom buttons
        btn_row = tk.Frame(self)
        btn_row.pack(fill=tk.X, padx=10, pady=(0, 10))
        tk.Button(btn_row, text="Cancel", command=self.destroy,
                  padx=8).pack(side=tk.RIGHT, padx=4)
        tk.Button(btn_row, text="Apply", command=self._apply,
                  fg="white", bg="#225522", padx=8).pack(side=tk.RIGHT, padx=4)
        if self._db_conn:
            tk.Button(btn_row, text="Save to Database", command=self._save_to_db,
                      padx=8).pack(side=tk.LEFT)

    def _populate_tree(self) -> None:
        self._tree.delete(*self._tree.get_children())
        for era in self._eras:
            self._tree.insert("", tk.END, values=(
                era.get("era_name", ""),
                era.get("start_date") or "",
                era.get("end_date") or "",
                era.get("color") or "",
            ))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _add_era(self) -> None:
        name = self._ent_name.get().strip()
        if not name:
            messagebox.showwarning("Era Name Required",
                                   "Please enter an era name.", parent=self)
            return
        self._eras.append({
            "era_name":   name,
            "start_date": self._norm_date(self._ent_start.get()),
            "end_date":   self._norm_date(self._ent_end.get()),
            "color":      self._ent_color.get().strip() or "",
        })
        self._populate_tree()
        for ent in (self._ent_name, self._ent_start, self._ent_end, self._ent_color):
            ent.delete(0, tk.END)

    def _remove_selected(self) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        del self._eras[self._tree.index(sel[0])]
        self._populate_tree()

    def _apply(self) -> None:
        if self._on_apply:
            self._on_apply(list(self._eras))
        self.destroy()

    def _save_to_db(self) -> None:
        save_show_eras(self._db_conn, self._show_name, self._eras)
        messagebox.showinfo(
            "Saved",
            f"{len(self._eras)} era(s) saved for '{self._show_name}'.",
            parent=self,
        )


# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Children's Media Analysis Toolkit (CMAT)")
        self.geometry("1050x680")
        self.minsize(800, 500)

        self._root_folder: Path | None = None
        self._cfg = load_config()
        self._queue: queue.Queue = queue.Queue()
        self._ep_queue: list[Path] = []       # episodes waiting to be analyzed
        self._analyzing: Path | None = None   # episode currently running
        self._srt_queue: list[tuple[Path, float]] = []  # (video_path, duration_sec) for transcription-only
        self._srt_active = False               # transcription worker running
        self._watch_live_active = False        # live window open
        self._current_ep_result: EpisodeResult | None = None   # for export/chart
        self._current_ep_path: Path | None = None               # for DB look-ups
        self._current_show_results: list[EpisodeResult] | None = None  # for export
        self._pinned: tuple[str, Path] | None = None            # ("episode"|"show", path)
        self._db_conn = None                                   # SQLite index (opened with root)
        self._idx_ep_sort:   dict = {"col": "analyzed_at", "asc": False}
        self._idx_show_sort: dict = {"col": "avg_load",    "asc": False}
        self._cut_pulse_job: str | None = None  # after() ID for cut-detection animation
        self._lang_speech_rows: list[dict] = []
        self._lang_speech_sort: dict = {"col": "wpm", "asc": False}
        self._vocab_results: list = []
        self._vocab_analysis_running = False

        self._build_ui()
        self._poll_queue()

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self) -> None:
        self._build_menu()
        self._build_toolbar()
        # Status bar must be packed BEFORE the expand=True main pane.
        # In Tkinter pack, a side=BOTTOM widget packed after expand=True gets zero height.
        self._build_status_bar()
        self._build_main_pane()

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Choose Root Folder...", command=self._choose_folder)
        file_menu.add_command(label="Episode Sampler...", command=self._open_sampler)
        file_menu.add_command(label="Import Episode Metadata from Wikipedia...",
                              command=self._open_wiki_import)
        file_menu.add_command(label="Import Episode Metadata from TVMaze...",
                              command=self._open_tvmaze_import)
        file_menu.add_separator()
        self._menu_export_json = file_menu.add_command(
            label="Export Results as JSON...", command=self._export_json, state=tk.DISABLED)
        self._menu_export_csv = file_menu.add_command(
            label="Export Results as CSV...", command=self._export_csv, state=tk.DISABLED)
        self._menu_export_pdf = file_menu.add_command(
            label="Export Report as PDF...", command=self._export_pdf, state=tk.DISABLED)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        self._file_menu = file_menu

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About metrics...", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    def _build_toolbar(self) -> None:
        bar = tk.Frame(self, bd=1, relief=tk.SUNKEN)
        bar.pack(side=tk.TOP, fill=tk.X, padx=2, pady=(2, 0))
        # RIGHT-side widgets must be packed BEFORE the expand=True left label,
        # otherwise Tkinter allocates all horizontal space to the label first.
        tk.Button(bar, text="Settings...", command=self._open_settings,
                  padx=6).pack(side=tk.RIGHT, padx=4, pady=2)
        tk.Button(bar, text="Choose...", command=self._choose_folder,
                  padx=6).pack(side=tk.RIGHT, padx=(0, 4), pady=2)
        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.RIGHT, fill=tk.Y, pady=3)
        self._toolbar_preset_var = tk.StringVar()
        self._toolbar_preset_cb = ttk.Combobox(
            bar, textvariable=self._toolbar_preset_var,
            state="readonly", width=22,
        )
        self._toolbar_preset_cb.pack(side=tk.RIGHT, padx=(0, 4), pady=2)
        self._toolbar_preset_cb.bind("<<ComboboxSelected>>", self._on_toolbar_preset_change)
        _WidgetTooltip(
            self._toolbar_preset_cb,
            "Scoring preset — sets the reference-range ceilings used to normalize "
            "each metric before weighting.\n\n"
            "Use Preschool or Early Childhood when your library contains only "
            "children's content. The General / All Ages preset is calibrated for "
            "a wide range of content (e.g., 60 cuts/min max), which can make "
            "fast-paced animation look mild and allow high-contrast or loud "
            "lecture content to rank unexpectedly high.\n\n"
            "Changing the preset rescores the current results instantly from cache. "
            "Re-analyze episodes to store updated scores in the index.",
            wraplength=320,
        )
        tk.Label(bar, text="Preset:").pack(side=tk.RIGHT, padx=(6, 2), pady=3)
        # Left-side label with expand=True packs last so it fills only the remainder
        tk.Label(bar, text="Root folder:").pack(side=tk.LEFT, padx=(6, 2), pady=3)
        self._folder_var = tk.StringVar(value="(none chosen)")
        tk.Label(bar, textvariable=self._folder_var, anchor="w",
                 fg="navy").pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._refresh_toolbar_presets()

    def _build_main_pane(self) -> None:
        pane = tk.PanedWindow(self, orient=tk.HORIZONTAL,
                              sashrelief=tk.RAISED, sashwidth=5)
        pane.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # --- Left: Notebook with Library and Index tabs ---
        left = tk.Frame(pane, width=300)
        pane.add(left, minsize=200)

        left_nb = ttk.Notebook(left)
        left_nb.pack(fill=tk.BOTH, expand=True)

        # ---- Library tab ----
        lib_tab = tk.Frame(left_nb)
        left_nb.add(lib_tab, text="Library")

        tree_frame = tk.Frame(lib_tab)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self._tree = ttk.Treeview(tree_frame, selectmode="browse")
        self._tree.heading("#0", text="Shows / Episodes")
        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        btn_frame = tk.Frame(lib_tab)
        btn_frame.pack(fill=tk.X, padx=4, pady=6)
        self._btn_ep = tk.Button(btn_frame, text="Analyze Episode",
                                  command=self._analyze_episode, state=tk.DISABLED)
        self._btn_ep.pack(fill=tk.X, pady=2)
        self._btn_show = tk.Button(btn_frame, text="Analyze Show (Batch)",
                                    command=self._analyze_show, state=tk.DISABLED)
        self._btn_show.pack(fill=tk.X, pady=2)
        self._btn_watch = tk.Button(btn_frame, text="Watch Analysis (Live)",
                                     command=self._watch_live, state=tk.DISABLED,
                                     fg="navy")
        self._btn_watch.pack(fill=tk.X, pady=2)
        self._btn_full_series = tk.Button(btn_frame, text="Full Series Aggregate",
                                           command=self._show_full_series_aggregate,
                                           state=tk.DISABLED, fg="#5500aa")
        self._btn_full_series.pack(fill=tk.X, pady=2)
        self._btn_sample_agg = tk.Button(btn_frame, text="View Sample Aggregate...",
                                          command=self._load_sample_results,
                                          fg="#884400")
        self._btn_sample_agg.pack(fill=tk.X, pady=2)
        _WidgetTooltip(
            self._btn_sample_agg,
            "Load a saved sampling manifest (manifest.json) to see the aggregate "
            "sensory profile for only the episodes that sample selected.\n\n"
            "Use this to run stabilization tests: sample at n=2, n=3, n=4, etc., "
            "analyze each set, then load each manifest here to compare the aggregates. "
            "The scores are computed in isolation — only the sampled episodes count, "
            "regardless of what else is in the index.\n\n"
            "Browse to the manifest.json file in your sample output folder "
            "(e.g. Little_Bear_spread_2026-06-30/). The episodes CSV is found "
            "automatically.",
            wraplength=300,
        )

        ttk.Separator(btn_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(6, 4))
        self._btn_transcribe_show = tk.Button(
            btn_frame, text="Transcribe Missing Subtitles",
            command=self._transcribe_show_subtitles, state=tk.DISABLED, fg="#006633",
        )
        self._btn_transcribe_show.pack(fill=tk.X, pady=2)
        _WidgetTooltip(
            self._btn_transcribe_show,
            "Runs Whisper AI transcription only on episodes that have already been\n"
            "analyzed but have no .srt or .vtt subtitle file yet.\n\n"
            "Skips episodes that already have subtitles. Does not re-run the full\n"
            "video/audio analysis — transcription only.",
            wraplength=280,
        )

        ttk.Separator(btn_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(6, 4))
        self._btn_pin = tk.Button(btn_frame, text="Pin for Compare",
                                   command=self._pin_for_compare, state=tk.DISABLED)
        self._btn_pin.pack(fill=tk.X, pady=2)
        self._pinned_var = tk.StringVar(value="")
        tk.Label(btn_frame, textvariable=self._pinned_var,
                 font=("TkDefaultFont", 8), fg="#555555",
                 wraplength=190, anchor="w", justify="left").pack(fill=tk.X, padx=2)
        self._btn_compare = tk.Button(btn_frame, text="Compare with Pinned",
                                       command=self._open_compare, state=tk.DISABLED)
        self._btn_compare.pack(fill=tk.X, pady=2)

        # Queue panel
        queue_outer = tk.LabelFrame(lib_tab, text="Analysis Queue", padx=4, pady=4)
        queue_outer.pack(fill=tk.BOTH, expand=True, padx=4, pady=(6, 0))

        list_frame = tk.Frame(queue_outer)
        list_frame.pack(fill=tk.BOTH, expand=True)
        self._queue_lb = tk.Listbox(list_frame, height=6,
                                     font=("Consolas", 8), activestyle="none",
                                     selectmode=tk.SINGLE)
        qs = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                            command=self._queue_lb.yview)
        self._queue_lb.configure(yscrollcommand=qs.set)
        qs.pack(side=tk.RIGHT, fill=tk.Y)
        self._queue_lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._btn_clear = tk.Button(queue_outer, text="Clear Queue",
                                     command=self._clear_queue, state=tk.DISABLED)
        self._btn_clear.pack(fill=tk.X, pady=(4, 0))

        # ---- Index tab ----
        idx_tab = tk.Frame(left_nb)
        left_nb.add(idx_tab, text="Index")
        self._build_index_tab(idx_tab)

        # ---- Language tab ----
        lang_tab = tk.Frame(left_nb)
        left_nb.add(lang_tab, text="Language")
        self._build_language_tab(lang_tab)

        # --- Right: results ---
        right = tk.Frame(pane)
        pane.add(right, minsize=420)

        results_hdr = tk.Frame(right)
        results_hdr.pack(fill=tk.X, padx=4, pady=(2, 0))
        tk.Label(results_hdr, text="Results", font=("TkDefaultFont", 9, "bold"),
                 anchor="w").pack(side=tk.LEFT)
        self._btn_chart = tk.Button(results_hdr, text="Show Chart",
                                     command=self._show_chart, state=tk.DISABLED,
                                     padx=6)
        self._btn_chart.pack(side=tk.RIGHT)

        txt_frame = tk.Frame(right)
        txt_frame.pack(fill=tk.BOTH, expand=True)

        self._txt = tk.Text(txt_frame, wrap=tk.WORD, state=tk.DISABLED,
                             bg="white", relief=tk.SUNKEN, bd=1,
                             font=("Consolas", 9), padx=10, pady=8)
        vsb2 = ttk.Scrollbar(txt_frame, orient=tk.VERTICAL, command=self._txt.yview)
        self._txt.configure(yscrollcommand=vsb2.set)
        vsb2.pack(side=tk.RIGHT, fill=tk.Y)
        self._txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._txt.tag_configure("h1",    font=("TkDefaultFont", 11, "bold"))
        self._txt.tag_configure("h2",    font=("TkDefaultFont", 9, "bold"), foreground="#003080")
        self._txt.tag_configure("score", font=("TkDefaultFont", 14, "bold"), foreground="#005500")
        self._txt.tag_configure("dim",   foreground="#666666")
        self._txt.tag_configure("pct",   foreground="#336633", font=("TkDefaultFont", 8))
        self._txt.tag_configure("err",   foreground="red")
        self._txt.tag_configure("mono",  font=("Consolas", 9))

        # Episode Metadata panel — air date, season, episode number
        meta_frame = tk.LabelFrame(right, text="Episode Metadata", padx=4, pady=4)
        meta_frame.pack(fill=tk.X, padx=4, pady=(0, 2))
        self._meta_air_date = tk.StringVar()
        self._meta_season   = tk.StringVar()
        self._meta_ep_num   = tk.StringVar()
        tk.Label(meta_frame, text="Air Date:").pack(side=tk.LEFT)
        self._entry_air_date = tk.Entry(
            meta_frame, textvariable=self._meta_air_date, width=11,
            state=tk.DISABLED, bg="#f5f5f5",
        )
        self._entry_air_date.pack(side=tk.LEFT, padx=(2, 8))
        tk.Label(meta_frame, text="Season:").pack(side=tk.LEFT)
        self._entry_season = tk.Entry(
            meta_frame, textvariable=self._meta_season, width=4,
            state=tk.DISABLED, bg="#f5f5f5",
        )
        self._entry_season.pack(side=tk.LEFT, padx=(2, 8))
        tk.Label(meta_frame, text="Ep #:").pack(side=tk.LEFT)
        self._entry_ep_num = tk.Entry(
            meta_frame, textvariable=self._meta_ep_num, width=4,
            state=tk.DISABLED, bg="#f5f5f5",
        )
        self._entry_ep_num.pack(side=tk.LEFT, padx=(2, 8))
        self._btn_save_meta = tk.Button(
            meta_frame, text="Save", command=self._save_metadata,
            padx=6, state=tk.DISABLED,
        )
        self._btn_save_meta.pack(side=tk.LEFT)
        tk.Label(
            meta_frame, text="(any date format)", fg="#888888",
            font=("TkDefaultFont", 8),
        ).pack(side=tk.LEFT, padx=(6, 0))

        # Notes panel — below results text, always visible
        notes_frame = tk.LabelFrame(right, text="Episode Notes", padx=4, pady=4)
        notes_frame.pack(fill=tk.X, padx=4, pady=(0, 4))
        self._notes_text = tk.Text(
            notes_frame, height=3, wrap=tk.WORD,
            font=("TkDefaultFont", 9), state=tk.DISABLED,
            bg="#f5f5f5", relief=tk.SUNKEN, bd=1,
        )
        self._notes_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._btn_save_note = tk.Button(
            notes_frame, text="Save", command=self._save_note,
            padx=6, state=tk.DISABLED,
        )
        self._btn_save_note.pack(side=tk.RIGHT, padx=(6, 0), anchor="n", pady=2)

    def _build_status_bar(self) -> None:
        bar = tk.Frame(self, bd=1, relief=tk.SUNKEN)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        self._status_var = tk.StringVar(value="Ready.  Choose a root folder to begin.")
        tk.Label(bar, textvariable=self._status_var,
                 anchor="w").pack(side=tk.LEFT, padx=6, pady=2)
        self._progress = ttk.Progressbar(bar, mode="determinate", length=220)
        self._progress.pack(side=tk.RIGHT, padx=6, pady=3)

    # -----------------------------------------------------------------------
    # Folder & tree
    # -----------------------------------------------------------------------

    def _choose_folder(self) -> None:
        messagebox.showinfo(
            "Choose Root Folder",
            "Select the folder that CONTAINS your show folders.\n\n"
            "Example:\n"
            "  Child Development Television Index Project\\   <-- select this\n"
            "      Little Bear\\\n"
            "          episode01.mp4\n"
            "      Another Show\\\n"
            "          episode01.mp4\n\n"
            "Do NOT navigate into a show folder — select its parent.",
        )
        folder = filedialog.askdirectory(
            title="Select the ROOT folder (the one containing show sub-folders)"
        )
        if folder:
            self._root_folder = Path(folder)
            self._folder_var.set(str(self._root_folder))
            self._populate_tree()
            self._btn_full_series.config(state=tk.NORMAL)
            if list_top_level(self._root_folder):
                self._write_txt("Choose a show or episode in the library to see results.\n\n"
                                "Cached results load instantly; new episodes need to be analyzed.")
            # If nothing found, _populate_tree already writes an explanation
            # Open (or create) the index DB and seed it from existing cached results
            if self._db_conn:
                self._db_conn.close()
            self._db_conn = get_db(self._root_folder)
            self._backfill_index()
            self._refresh_index()

    def _populate_tree(self) -> None:
        self._tree.delete(*self._tree.get_children())
        if not self._root_folder:
            return
        items = list_top_level(self._root_folder)
        for kind, d in items:
            if kind == "category":
                cat_node = self._tree.insert(
                    "", tk.END, text=f"  [{d.name}]",
                    values=("category", str(d)), open=True,
                )
                for show_dir in list_category_shows(d):
                    self._insert_show_node(cat_node, show_dir)
            else:
                self._insert_show_node("", d)
        if not items:
            self._write_txt(
                "No show folders found under:\n"
                f"  {self._root_folder}\n\n"
                "Expected layout:\n"
                "  Root Folder/\n"
                "    Show Name/\n"
                "      episode01.mp4\n"
                "  OR with categories:\n"
                "    Category Name/\n"
                "      Show Name/\n"
                "        episode01.mp4\n"
            )

    def _insert_show_node(self, parent_iid: str, show_dir: Path) -> None:
        """Insert a show and its episodes into the library tree."""
        skey = show_key(self._root_folder, show_dir)
        show_node = self._tree.insert(
            parent_iid, tk.END, text=f"  {show_dir.name}",
            values=("show", str(show_dir)), open=True,
        )
        for ep in list_episodes(show_dir):
            cached = load_cached(self._root_folder, skey, ep.stem)
            label = f"    {ep.name}" + ("  [analyzed]" if cached else "")
            self._tree.insert(show_node, tk.END, text=label,
                               values=("episode", str(ep)))

    # -----------------------------------------------------------------------
    # Tree selection
    # -----------------------------------------------------------------------

    def _on_tree_select(self, _event=None) -> None:
        sel = self._tree.selection()
        self._btn_ep.config(state=tk.DISABLED)
        self._btn_show.config(state=tk.DISABLED)
        self._btn_watch.config(state=tk.DISABLED)
        self._btn_transcribe_show.config(state=tk.DISABLED)
        self._btn_pin.config(state=tk.DISABLED)
        self._btn_compare.config(state=tk.DISABLED)
        if not sel:
            return
        queue_busy = self._analyzing is not None or self._watch_live_active
        kind, path = self._selected_item()
        if kind == "episode":
            self._btn_ep.config(state=tk.NORMAL)
            if not queue_busy:
                self._btn_watch.config(state=tk.NORMAL)
            self._show_episode_cached(Path(path))
        elif kind == "show":
            self._btn_show.config(state=tk.NORMAL)
            if not self._srt_active:
                self._btn_transcribe_show.config(state=tk.NORMAL)
            self._show_show_cached(Path(path))
        elif kind == "category":
            return  # category selected — no actions available
        # Pin is available for shows and episodes
        if kind in ("show", "episode"):
            self._btn_pin.config(state=tk.NORMAL)
        # Compare is available when pin exists and selection is same type, different item
        if kind in ("show", "episode") and self._pinned:
            pin_kind, pin_path = self._pinned
            if kind == pin_kind and Path(path) != pin_path:
                self._btn_compare.config(state=tk.NORMAL)

    def _selected_item(self) -> tuple[str, str]:
        sel = self._tree.selection()
        if not sel:
            return "", ""
        values = self._tree.item(sel[0], "values")
        return (values[0], values[1]) if values else ("", "")

    # -----------------------------------------------------------------------
    # Display cached results (instant, no worker)
    # -----------------------------------------------------------------------

    def _show_episode_cached(self, ep_path: Path) -> None:
        show_dir = ep_path.parent
        cached = load_cached(self._root_folder, show_key(self._root_folder, show_dir), ep_path.stem)
        if cached:
            self._current_ep_path = ep_path
            result = rescore_episode(EpisodeResult.from_dict(cached), self._cfg)
            self._render_episode(result)
        else:
            self._write_txt(
                f"Episode: {ep_path.name}\n\n"
                "Not yet analyzed.\n\n"
                "Click  Analyze Episode  to run analysis.\n"
                "(Analysis takes 2-5 minutes per episode.)"
            )

    def _show_show_cached(self, show_dir: Path) -> None:
        skey = show_key(self._root_folder, show_dir)
        dname, _ = display_show_name(self._root_folder, show_dir)
        episodes = list_episodes(show_dir)
        ok_results = []
        for ep in episodes:
            c = load_cached(self._root_folder, skey, ep.stem)
            if c:
                ok_results.append(rescore_episode(EpisodeResult.from_dict(c), self._cfg))

        if not ok_results:
            self._write_txt(
                f"Show: {dname}\n\n"
                f"{len(episodes)} episode(s) — none analyzed yet.\n\n"
                "Click  Analyze Show (Batch)  to analyze all episodes."
            )
        else:
            agg = compute_show_aggregate(dname, ok_results)
            self._render_show(agg, ok_results, total_eps=len(episodes))

    def _load_sample_results(self) -> None:
        if not self._root_folder:
            messagebox.showwarning(
                "No root folder",
                "Choose a root folder first so CMAT knows where to find the cache.",
                parent=self,
            )
            return
        manifest_path = filedialog.askopenfilename(
            title="Open sample manifest",
            filetypes=[("Manifest JSON", "manifest.json"), ("JSON files", "*.json"),
                       ("All files", "*.*")],
        )
        if not manifest_path:
            return

        import json as _json
        import pandas as _pd

        manifest_path = Path(manifest_path)
        try:
            manifest = _json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            messagebox.showerror("Read error", f"Could not read manifest:\n{exc}", parent=self)
            return

        csv_path = manifest_path.parent / "selected.csv"
        if not csv_path.exists():
            # Fall back to any CSV in the same folder
            candidates = list(manifest_path.parent.glob("*.csv"))
            if len(candidates) == 1:
                csv_path = candidates[0]
            elif len(candidates) > 1:
                chosen = filedialog.askopenfilename(
                    title="Select the episodes CSV for this sample",
                    initialdir=str(manifest_path.parent),
                    filetypes=[("CSV files", "*.csv")],
                )
                if not chosen:
                    return
                csv_path = Path(chosen)
            else:
                messagebox.showerror(
                    "Missing CSV",
                    f"No CSV file found beside the manifest in:\n{manifest_path.parent}",
                    parent=self,
                )
                return

        try:
            df = _pd.read_csv(csv_path)
        except Exception as exc:
            messagebox.showerror("Read error", f"Could not read selected.csv:\n{exc}", parent=self)
            return

        if "filepath" not in df.columns:
            messagebox.showerror(
                "Missing column",
                "selected.csv has no 'filepath' column — cannot locate cached results.",
                parent=self,
            )
            return

        analysis_root = self._root_folder / ".analysis"

        def _find_cached(fp: Path) -> dict | None:
            # Primary: derive show_key from the filepath relative to root
            try:
                skey = show_key(self._root_folder, fp.parent)
                result = load_cached(self._root_folder, skey, fp.stem)
                if result:
                    return result
            except ValueError:
                pass
            # Fallback: search all .analysis/ subdirectories for the stem
            if analysis_root.exists():
                for candidate in analysis_root.rglob(f"{fp.stem}.json"):
                    try:
                        import json as _json2
                        return _json2.loads(candidate.read_text(encoding="utf-8"))
                    except Exception:
                        pass
            return None

        ok_results: list[EpisodeResult] = []
        missing: list[str] = []
        for fp_str in df["filepath"]:
            if not fp_str or str(fp_str) == "nan":
                continue
            fp = Path(str(fp_str))
            cached = _find_cached(fp)
            if cached:
                ok_results.append(rescore_episode(EpisodeResult.from_dict(cached), self._cfg))
            else:
                missing.append(fp.name)

        entry_id = manifest.get("entry_id", manifest_path.parent.name)
        total_selected = manifest.get("total_selected", len(df))

        if not ok_results:
            self._write_txt(
                f"Sample: {entry_id}\n\n"
                "No cached results found for any episode in this sample.\n\n"
                "Analyze the episodes first, then reload the sample manifest."
            )
            return

        if missing:
            messagebox.showwarning(
                "Some episodes not cached",
                f"{len(missing)} episode(s) not found in the cache and were skipped:\n"
                + "\n".join(f"  • {n}" for n in missing[:10])
                + ("\n  …" if len(missing) > 10 else ""),
                parent=self,
            )

        agg = compute_show_aggregate(entry_id, ok_results)
        self._render_show(agg, ok_results, total_eps=total_selected,
                          sample_info=manifest)

    def _show_full_series_aggregate(self) -> None:
        if not self._root_folder:
            return
        all_shows = list_shows(self._root_folder)
        ok_results = []
        total_eps = 0
        for show_dir in all_shows:
            skey = show_key(self._root_folder, show_dir)
            episodes = list_episodes(show_dir)
            total_eps += len(episodes)
            for ep in episodes:
                c = load_cached(self._root_folder, skey, ep.stem)
                if c:
                    ok_results.append(rescore_episode(EpisodeResult.from_dict(c), self._cfg))

        series_name = self._root_folder.name
        if not ok_results:
            self._write_txt(
                f"Full Series: {series_name}\n\n"
                f"{total_eps} episode(s) across {len(all_shows)} season(s) — none analyzed yet.\n\n"
                "Analyze some episodes first, then click Full Series Aggregate."
            )
            return
        agg = compute_show_aggregate(series_name, ok_results)
        save_show_results(self._root_folder, series_name, ok_results, agg)
        self._render_show(agg, ok_results, total_eps=total_eps)

    # -----------------------------------------------------------------------
    # Result rendering
    # -----------------------------------------------------------------------

    def _write_txt(self, text: str) -> None:
        self._txt.config(state=tk.NORMAL)
        self._txt.delete("1.0", tk.END)
        self._txt.insert(tk.END, text)
        self._txt.config(state=tk.DISABLED)
        self._current_ep_result = None
        self._current_ep_path = None
        self._current_show_results = None
        self._current_show_name = None
        self._btn_chart.config(state=tk.DISABLED)
        self._file_menu.entryconfig("Export Results as JSON...", state=tk.DISABLED)
        self._file_menu.entryconfig("Export Results as CSV...", state=tk.DISABLED)
        self._file_menu.entryconfig("Export Report as PDF...", state=tk.DISABLED)
        self._notes_text.config(state=tk.NORMAL)
        self._notes_text.delete("1.0", tk.END)
        self._notes_text.config(state=tk.DISABLED)
        self._btn_save_note.config(state=tk.DISABLED)
        self._clear_metadata_fields()

    def _clear_metadata_fields(self) -> None:
        for entry in (self._entry_air_date, self._entry_season, self._entry_ep_num):
            entry.config(state=tk.NORMAL)
            entry.delete(0, tk.END)
            entry.config(state=tk.DISABLED, bg="#f5f5f5")
        self._btn_save_meta.config(state=tk.DISABLED)

    def _render_episode(self, result: EpisodeResult) -> None:
        self._current_ep_result = result if result.status == "ok" else None
        self._current_show_results = None
        self._current_show_name = None
        can_chart = result.status == "ok"
        self._btn_chart.config(state=tk.NORMAL if can_chart else tk.DISABLED)
        self._file_menu.entryconfig("Export Results as JSON...",
                                     state=tk.NORMAL if can_chart else tk.DISABLED)
        self._file_menu.entryconfig("Export Results as CSV...",
                                     state=tk.NORMAL if can_chart else tk.DISABLED)
        self._file_menu.entryconfig("Export Report as PDF...",
                                     state=tk.NORMAL if can_chart else tk.DISABLED)
        t = self._txt
        t.config(state=tk.NORMAL)
        t.delete("1.0", tk.END)

        t.insert(tk.END, f"Episode: {result.file}\n", "h1")
        if result.duration_sec:
            t.insert(tk.END,
                     f"Duration: {result.duration_sec / 60:.1f} min  "
                     f"({result.duration_sec:.0f} s)\n\n", "dim")

        if result.status == "failed":
            t.insert(tk.END, f"Analysis failed:\n{result.error}\n", "err")
            t.config(state=tk.DISABLED)
            self._notes_text.config(state=tk.NORMAL)
            self._notes_text.delete("1.0", tk.END)
            self._notes_text.config(state=tk.DISABLED)
            self._btn_save_note.config(state=tk.DISABLED)
            return

        m = result.metrics

        # Sensory load — lead with the composite score
        t.insert(tk.END, "Sensory Load Score\n", "h2")
        t.insert(tk.END, f"  {m.sensory_load.score:.3f}", "score")
        t.insert(tk.END, "  (0 = low stimulation  ·  1 = high)")
        if not m.sensory_load.audio_available:
            t.insert(tk.END, "  [visual only — no audio]", "dim")
        t.insert(tk.END, "\n")

        # Percentile ranking (only when this episode is indexed in DB)
        if self._db_conn and self._current_ep_path:
            pct = get_episode_percentile(self._db_conn, str(self._current_ep_path))
            if pct:
                def _ordinal(n: int) -> str:
                    sfx = {1: "st", 2: "nd", 3: "rd"}.get(
                        n % 10 if n % 100 not in (11, 12, 13) else 0, "th"
                    )
                    return f"{n}{sfx}"
                line = (f"  {_ordinal(pct['percentile'])} percentile  "
                        f"({pct['global_total']} episodes indexed)")
                if pct["show_total"] >= 3:
                    line += (f"  ·  {_ordinal(pct['show_rank'])} highest "
                             f"of {pct['show_total']} in {pct['show_name']}")
                t.insert(tk.END, line + "\n", "pct")
        t.insert(tk.END, "\n")

        cfg = result.config.get("sensory_load_weights", {})
        c = m.sensory_load.components
        components = [
            ("Pacing",     c.pacing,     cfg.get("pacing",         0.25)),
            ("Saturation", c.saturation, cfg.get("saturation",     0.05)),
            ("Contrast",   c.contrast,   cfg.get("color_contrast", 0.10)),
            ("Motion",     c.motion,     cfg.get("motion",         0.25)),
            ("Flashing",   c.flashing,   cfg.get("flashing",       0.15)),
            ("Audio",      c.audio,      cfg.get("audio",          0.20)),
        ]
        for label, val, wt in components:
            if label == "Audio" and not m.sensory_load.audio_available:
                t.insert(tk.END, f"  {'Audio':<12} n/a   (weight {wt:.0%}, no audio track)\n", "dim")
                continue
            self._bar(t, val)
            t.insert(tk.END, f"  {label:<12} {val:.3f}  (weight {wt:.0%})\n")

        t.insert(tk.END, "\n")

        # Shot length
        t.insert(tk.END, "Shot Length\n", "h2")
        sl = m.shot_length
        t.insert(tk.END, f"  Mean shot:    {sl.mean_sec:.2f} s\n")
        t.insert(tk.END, f"  Median shot:  {sl.median_sec:.2f} s\n")
        t.insert(tk.END, f"  Shots/min:    {sl.shots_per_min:.1f}\n")
        t.insert(tk.END, f"  Total shots:  {sl.count}\n\n")

        # Scene pacing
        t.insert(tk.END, "Scene Pacing\n", "h2")
        sp = m.scene_pacing
        t.insert(tk.END, f"  Cuts/min:        {sp.cuts_per_min:.1f}\n")
        t.insert(tk.END,
                 f"  Shot-length CV:  {sp.shot_length_cv:.3f}  "
                 "(rhythm variability: higher = burstier)\n\n")

        # Color saturation & contrast
        t.insert(tk.END, "Color\n", "h2")
        cs = m.color_saturation
        self._bar(t, cs.mean)
        t.insert(tk.END, f"  Saturation mean:   {cs.mean:.3f}\n")
        t.insert(tk.END, f"  Saturation var:    {cs.temporal_var:.4f}\n")
        self._bar(t, min(1.0, cs.contrast_mean / 0.35))
        t.insert(tk.END, f"  Contrast mean:     {cs.contrast_mean:.3f}  "
                         "(spatial brightness spread)\n\n")

        # Motion
        t.insert(tk.END, "Motion\n", "h2")
        mo = m.motion
        self._bar(t, mo.mean)
        t.insert(tk.END, f"  Mean: {mo.mean:.4f}\n")
        t.insert(tk.END, f"  Peak: {mo.peak:.4f}\n\n")

        # Flashing
        t.insert(tk.END, "Flashing\n", "h2")
        fl = m.flashing
        t.insert(tk.END,
                 f"  Luminance-delta events/min:  "
                 f"{fl.luminance_delta_events_per_min:.2f}\n\n")

        # Audio
        t.insert(tk.END, "Audio Loudness\n", "h2")
        au = m.audio
        if au.available:
            self._bar(t, min(1.0, au.rms_mean / 0.20))
            t.insert(tk.END, f"  RMS mean:          {au.rms_mean:.4f}\n")
            t.insert(tk.END, f"  RMS peak:          {au.rms_peak:.4f}\n")
            t.insert(tk.END, f"  Temporal variance: {au.rms_temporal_var:.6f}  "
                             "(volume variation over time)\n")
            t.insert(tk.END, f"  Dynamic range:     {au.dynamic_range_db:.1f} dB  "
                             "(peak-to-mean ratio)\n")
        else:
            t.insert(tk.END, "  Not available (FFmpeg not found or no audio track)\n", "dim")

        # Speech
        t.insert(tk.END, "\nSpeech\n", "h2")
        sp = m.speech
        if sp.available:
            _src = {"srt": "SRT subtitle file", "vtt": "VTT subtitle file",
                    "whisper": "Whisper AI transcription"}.get(sp.source, sp.source)
            t.insert(tk.END, f"  Source:            {_src}\n", "dim")
            t.insert(tk.END, f"  Words per minute:  {sp.words_per_minute:.1f}\n")
            t.insert(tk.END, f"  Speech density:    {sp.speech_density:.1%}  "
                             "(fraction of episode with dialogue)\n")
            t.insert(tk.END, f"  Total words:       {sp.total_words:,}\n")
        else:
            _src = sp.source
            if _src == "disabled" or _src == "none":
                _msg = "enable auto-transcription in Settings, or place an .srt / .vtt file alongside the video"
            elif _src == "not_installed":
                _msg = "faster-whisper is not installed — open a terminal and run:  pip install faster-whisper"
            elif _src.startswith("error:"):
                _msg = f"transcription failed: {_src[6:]}"
            else:
                _msg = "no CC file found and auto-transcription is disabled"
            t.insert(tk.END, f"  Not available — {_msg}\n", "dim")

        t.config(state=tk.DISABLED)

        # Load saved note into the notes panel
        note = ""
        if self._db_conn and self._current_ep_path:
            note = get_note(self._db_conn, str(self._current_ep_path))
        self._notes_text.config(state=tk.NORMAL)
        self._notes_text.delete("1.0", tk.END)
        if note:
            self._notes_text.insert("1.0", note)
        self._btn_save_note.config(state=tk.NORMAL)

        # Load saved metadata into the metadata panel
        meta = {}
        if self._db_conn and self._current_ep_path:
            meta = get_episode_metadata(self._db_conn, str(self._current_ep_path))
        for entry in (self._entry_air_date, self._entry_season, self._entry_ep_num):
            entry.config(state=tk.NORMAL, bg="white")
        self._meta_air_date.set(meta.get("air_date") or "")
        self._meta_season.set(str(meta["season_num"]) if meta.get("season_num") is not None else "")
        self._meta_ep_num.set(str(meta["episode_num"]) if meta.get("episode_num") is not None else "")
        self._btn_save_meta.config(state=tk.NORMAL)

    def _render_show(self, agg: ShowAggregate, results: list[EpisodeResult],
                     total_eps: int, sample_info: dict | None = None) -> None:
        self._current_ep_result = None
        self._current_ep_path = None
        self._current_show_results = [r for r in results if r.status == "ok"]
        self._current_show_name = agg.show_name
        self._clear_metadata_fields()
        self._btn_chart.config(
            state=tk.NORMAL if bool(self._current_show_results) else tk.DISABLED
        )
        has = bool(self._current_show_results)
        self._file_menu.entryconfig("Export Results as JSON...",
                                     state=tk.NORMAL if has else tk.DISABLED)
        self._file_menu.entryconfig("Export Results as CSV...",
                                     state=tk.NORMAL if has else tk.DISABLED)
        self._file_menu.entryconfig("Export Report as PDF...",
                                     state=tk.NORMAL if has else tk.DISABLED)

        t = self._txt
        t.config(state=tk.NORMAL)
        t.delete("1.0", tk.END)

        t.insert(tk.END, f"Show: {agg.show_name}\n", "h1")
        analyzed = agg.episode_count - agg.failed_count
        t.insert(tk.END,
                 f"{analyzed} of {total_eps} episode(s) analyzed"
                 + (f"  |  {agg.failed_count} failed" if agg.failed_count else "")
                 + "\n\n", "dim")

        if sample_info:
            t.insert(tk.END, "Sample design\n", "h2")
            method      = sample_info.get("method", "?")
            stratify    = sample_info.get("stratify_by") or "none"
            params      = sample_info.get("params", {})
            seed        = sample_info.get("seed", "?")
            probability = sample_info.get("probability", True)
            generated   = sample_info.get("generated_at_utc", "")[:10]
            per_n       = params.get("per_stratum_n", "?")
            alloc       = sample_info.get("allocation") or "—"
            t.insert(tk.END,
                     f"  Method: {method}   Stratification: {stratify}   "
                     f"Allocation: {alloc}   n/stratum: {per_n}   "
                     f"Seed: {seed}   Generated: {generated}\n", "mono")
            if not probability:
                t.insert(tk.END,
                         "  ⚠  Non-probability sample (manual selection) — "
                         "no external-validity claim.\n", "err")
            notes = sample_info.get("notes", [])
            for note in notes:
                t.insert(tk.END, f"  • {note}\n", "dim")
            t.insert(tk.END, "\n")

        t.insert(tk.END, "Aggregate across episodes\n", "h2")
        t.insert(tk.END, "  Each episode weighted equally regardless of length.\n", "dim")
        t.insert(tk.END,
                 f"\n{'Metric':<28} {'Mean':>8} {'Median':>8} "
                 f"{'Std':>8} {'Min':>8} {'Max':>8}\n", "mono")
        t.insert(tk.END, "-" * 70 + "\n", "dim")

        def row(label: str, s) -> None:
            t.insert(tk.END,
                     f"  {label:<26} {s.mean:>8.3f} {s.median:>8.3f} "
                     f"{s.std:>8.3f} {s.min:>8.3f} {s.max:>8.3f}\n", "mono")

        row("Sensory load score", agg.sensory_load_score)
        row("Cuts / min",         agg.cuts_per_min)
        row("Shot length mean (s)", agg.shot_length_mean_sec)
        row("Color saturation",   agg.color_saturation_mean)
        row("Motion mean",        agg.motion_mean)
        row("Flashing events/min", agg.flashing_events_per_min)
        if agg.audio_rms_mean.mean > 0:
            row("Audio RMS mean",     agg.audio_rms_mean)
        else:
            t.insert(tk.END, f"  {'Audio RMS mean':<26} {'n/a':>8}\n", "dim")

        ok = [r for r in results if r.status == "ok"]
        if ok:
            t.insert(tk.END, "\n\nPer-episode breakdown\n", "h2")
            t.insert(tk.END,
                     f"\n{'Episode':<28} {'Cut/m':>6} {'Sat':>6} "
                     f"{'Mot':>6} {'Flash':>7} {'Audio':>7} {'Load':>7}\n", "mono")
            t.insert(tk.END, "-" * 73 + "\n", "dim")
            for r in results:
                if r.status == "failed":
                    t.insert(tk.END, f"  {r.file:<26}  FAILED\n", "err")
                else:
                    m = r.metrics
                    audio_str = f"{m.audio.rms_mean:>7.4f}" if m.audio.available else f"{'n/a':>7}"
                    t.insert(tk.END,
                             f"  {r.file:<26} "
                             f"{m.scene_pacing.cuts_per_min:>6.1f} "
                             f"{m.color_saturation.mean:>6.3f} "
                             f"{m.motion.mean:>6.3f} "
                             f"{m.flashing.luminance_delta_events_per_min:>7.1f} "
                             f"{audio_str} "
                             f"{m.sensory_load.score:>7.3f}\n", "mono")

        t.config(state=tk.DISABLED)

    def _bar(self, t: tk.Text, value: float, width: int = 28) -> None:
        filled = int(max(0.0, min(1.0, value)) * width)
        bar = "[" + "#" * filled + "-" * (width - filled) + "]"
        t.insert(tk.END, f"  {bar} {value:.0%}\n", "dim")

    # -----------------------------------------------------------------------
    # Analysis actions (dispatch to worker thread)
    # -----------------------------------------------------------------------

    def _analyze_episode(self) -> None:
        kind, path = self._selected_item()
        if kind != "episode":
            return
        self._enqueue(Path(path))

    def _analyze_show(self) -> None:
        kind, path = self._selected_item()
        if kind != "show":
            return
        show_dir = Path(path)
        added = 0
        for ep in list_episodes(show_dir):
            if self._enqueue(ep, silent=True):
                added += 1
        if added == 0:
            self._status_var.set(
                f"All episodes of '{show_dir.name}' are already analyzed or queued."
            )
        else:
            self._status_var.set(
                f"Added {added} episode(s) from '{show_dir.name}' to the queue."
            )

    def _transcribe_show_subtitles(self) -> None:
        """Queue Whisper transcription for analyzed episodes that have no subtitle file."""
        kind, path = self._selected_item()
        if kind != "show":
            return
        show_dir = Path(path)
        skey = show_key(self._root_folder, show_dir)

        items: list[tuple[Path, float]] = []
        for ep in list_episodes(show_dir):
            # Only episodes that have already been analyzed
            cached = load_cached(self._root_folder, skey, ep.stem)
            if not cached or cached.get("status") != "ok":
                continue
            # Skip if subtitle file already exists
            if _find_cc_file(ep) is not None:
                continue
            duration_sec = cached.get("duration_sec", 0.0)
            items.append((ep, duration_sec))

        if not items:
            self._status_var.set(
                f"'{show_dir.name}': all analyzed episodes already have subtitles."
            )
            return

        self._srt_queue = items
        self._srt_active = True
        self._btn_transcribe_show.config(state=tk.DISABLED)
        self._status_var.set(
            f"Transcription queued: {len(items)} episode(s) from '{show_dir.name}'."
        )
        threading.Thread(target=self._worker_transcribe, daemon=True).start()

    def _worker_transcribe(self) -> None:
        """Background thread: transcribe each queued episode in order."""
        while self._srt_queue:
            ep_path, duration_sec = self._srt_queue.pop(0)
            remaining = len(self._srt_queue)
            self._queue.put({
                "t": "srt_progress",
                "s": f"Transcribing {ep_path.name}  ({remaining} remaining after this)…",
            })
            result = transcribe_only(ep_path, duration_sec, self._cfg)
            self._queue.put({
                "t": "srt_ep_done",
                "ep_path": ep_path,
                "available": result.available,
                "source": result.source,
                "remaining": remaining,
            })
        self._queue.put({"t": "srt_all_done"})

    def _watch_live(self) -> None:
        kind, path = self._selected_item()
        if kind != "episode":
            return
        self._watch_live_active = True
        self._btn_watch.config(state=tk.DISABLED)

        def on_complete() -> None:
            self._watch_live_active = False
            self._populate_tree()
            self._on_tree_select()

        LiveAnalysisWindow(
            self,
            ep_path=Path(path),
            root_folder=self._root_folder,
            cfg=self._cfg,
            on_complete=on_complete,
        )

    def _enqueue(self, ep_path: Path, silent: bool = False) -> bool:
        """Add episode to the queue. Returns True if added, False if already queued/running."""
        if ep_path == self._analyzing or ep_path in self._ep_queue:
            if not silent:
                self._status_var.set(f"'{ep_path.name}' is already in the queue.")
            return False
        self._ep_queue.append(ep_path)
        self._update_queue_display()
        if self._analyzing is None:
            self._start_next()
        return True

    def _start_next(self) -> None:
        """Pop the next episode from the queue and start a worker thread."""
        if not self._ep_queue:
            self._analyzing = None
            self._update_queue_display()
            self._on_tree_select()   # re-enable Watch Live
            self._stop_cut_pulse()
            self._progress["value"] = 0
            if not self._watch_live_active:
                self._status_var.set("Ready.")
            return
        self._analyzing = self._ep_queue.pop(0)
        self._update_queue_display()
        self._progress["value"] = 0
        # Collect unreferenced Tkinter Variable objects now, on the main thread,
        # so the worker's GC cannot trigger Variable.__del__ from the wrong thread
        # (which causes "main thread is not in main loop" / Tcl_AsyncDelete errors).
        import gc; gc.collect()
        threading.Thread(target=self._worker_episode,
                         args=(self._analyzing,), daemon=True).start()

    def _update_queue_display(self) -> None:
        self._queue_lb.delete(0, tk.END)
        if self._analyzing:
            self._queue_lb.insert(tk.END, f"● {self._analyzing.name}")
        for ep in self._ep_queue:
            self._queue_lb.insert(tk.END, f"  {ep.name}")
        has_items = self._analyzing is not None or bool(self._ep_queue)
        self._btn_clear.config(state=tk.NORMAL if has_items else tk.DISABLED)

    def _clear_queue(self) -> None:
        self._ep_queue.clear()
        self._analyzing = None      # abandon any stuck worker (daemon thread will exit)
        self._stop_cut_pulse()
        self._progress["value"] = 0
        self._update_queue_display()
        self._on_tree_select()
        self._status_var.set("Queue cleared.")

    # -----------------------------------------------------------------------
    # Worker thread targets (never touch Tkinter directly)
    # -----------------------------------------------------------------------

    def _worker_episode(self, ep_path: Path) -> None:
        show_dir = ep_path.parent
        skey = show_key(self._root_folder, show_dir)

        def cb(frac: float) -> None:
            remaining = len(self._ep_queue)
            tail = f"  |  {remaining} waiting" if remaining else ""
            if frac < 0:
                s = f"Detecting cuts — {ep_path.name}{tail}"
            else:
                s = f"Analyzing {ep_path.name}  ({int(frac * 100)}%){tail}"
            self._queue.put({"t": "progress", "v": frac, "s": s})

        print(f"[worker] starting analysis: {ep_path.name}", flush=True)
        try:
            result = analyze_episode(ep_path, config=self._cfg, progress_cb=cb)
            print(f"[worker] analysis done: status={result.status}", flush=True)
            if result.status == "ok":
                save_cache(self._root_folder, skey, ep_path.stem, result.to_dict())
                print(f"[worker] cache saved", flush=True)
            else:
                print(f"[worker] analysis failed: {result.error}", flush=True)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            result = EpisodeResult(file=ep_path.name, status="failed",
                                   error=f"Unexpected worker error: {exc}")
        print(f"[worker] posting ep_done", flush=True)
        self._queue.put({"t": "ep_done", "result": result, "ep_path": ep_path})

    # -----------------------------------------------------------------------
    # Queue polling — runs on the main thread every 50 ms
    # -----------------------------------------------------------------------
    # Cut-detection progress animation (timer-based, avoids indeterminate mode)
    # -----------------------------------------------------------------------

    def _start_cut_pulse(self) -> None:
        """Begin a 5→50% looping animation while PySceneDetect runs."""
        self._stop_cut_pulse()
        self._progress["value"] = 5
        self._cut_pulse_job = self.after(250, self._cut_pulse_tick)

    def _cut_pulse_tick(self) -> None:
        v = self._progress["value"]
        next_v = (v + 1) if v < 50 else 5
        self._progress["value"] = next_v
        self._cut_pulse_job = self.after(250, self._cut_pulse_tick)

    def _stop_cut_pulse(self) -> None:
        if self._cut_pulse_job is not None:
            self.after_cancel(self._cut_pulse_job)
            self._cut_pulse_job = None

    # -----------------------------------------------------------------------

    def _poll_queue(self) -> None:
        try:
            while True:
                try:
                    self._handle(self._queue.get_nowait())
                except queue.Empty:
                    break
                except Exception as exc:
                    import traceback
                    traceback.print_exc()
                    self._status_var.set(f"UI error: {exc}")
        finally:
            # always reschedule so the loop never dies permanently
            self.after(50, self._poll_queue)

    def _handle(self, msg: dict) -> None:
        kind = msg["t"]

        if kind == "progress":
            v = msg["v"]
            if v < 0:
                # Cut detection phase: PySceneDetect gives no callbacks, so
                # animate via a repeating after() timer (5→50%, looping).
                self._start_cut_pulse()
                self._status_var.set(msg["s"])
            else:
                self._stop_cut_pulse()
                self._progress["value"] = v * 100
                self._status_var.set(msg["s"])

        elif kind == "ep_done":
            result: EpisodeResult = msg["result"]
            ep_path: Path = msg["ep_path"]
            try:
                if result.status == "ok":
                    # Show result if this episode is currently selected
                    sel_kind, sel_path = self._selected_item()
                    if sel_kind == "episode" and Path(sel_path) == ep_path:
                        self._current_ep_path = ep_path
                        self._render_episode(rescore_episode(result, self._cfg))
                    self._maybe_save_show_aggregate(ep_path)
                    if self._db_conn:
                        dname, auto_s = display_show_name(self._root_folder, ep_path.parent)
                        upsert_episode(self._db_conn, result, dname, str(ep_path))
                        if auto_s is not None:
                            auto_set_season(self._db_conn, str(ep_path), auto_s)
                        self._refresh_index()
                else:
                    messagebox.showerror(
                        "Analysis failed",
                        f"{ep_path.name}:\n{result.error}",
                    )
                self._populate_tree()
            except Exception as exc:
                import traceback
                traceback.print_exc()
                self._status_var.set(f"Display error after analysis: {exc}")
            finally:
                self._start_next()

        elif kind == "vocab_progress":
            n, total = msg["n"], msg["total"]
            self._vocab_progress_var.set(f"Analyzing {n} / {total}…")

        elif kind == "srt_progress":
            self._status_var.set(msg["s"])

        elif kind == "srt_ep_done":
            ep_path = msg["ep_path"]
            if msg["available"]:
                print(f"[transcribe] done: {ep_path.name}", flush=True)
            else:
                print(f"[transcribe] failed ({msg['source']}): {ep_path.name}", flush=True)

        elif kind == "srt_all_done":
            self._srt_active = False
            self._status_var.set("Transcription complete.")
            self._on_tree_select()   # re-enable button

        elif kind == "vocab_done":
            self._vocab_analysis_running = False
            self._btn_vocab_analyze.config(state=tk.NORMAL)
            results = msg["results"]
            self._vocab_results = results
            self._vocab_tree.delete(*self._vocab_tree.get_children())
            for r in results:
                cc_name = Path(r.cc_path).name if r.cc_path else r.episode_id
                if r.status == "ok":
                    row  = r.to_flat_row()
                    fle  = row.get("read_flesch_reading_ease")
                    fkg  = row.get("read_flesch_kincaid_grade")
                    t1   = row.get("vocab_tier1_proportion")
                    t2   = row.get("vocab_tier2_proportion")
                    t3   = row.get("vocab_tier3_proportion")
                    aoa  = row.get("vocab_aoa_mean")
                    mtld = row.get("div_mtld")
                    self._vocab_tree.insert("", tk.END, values=(
                        cc_name, "ok",
                        f"{fle:.1f}"  if fle  is not None else "",
                        f"{fkg:.1f}"  if fkg  is not None else "",
                        f"{t1:.0%}"   if t1   is not None else "",
                        f"{t2:.0%}"   if t2   is not None else "",
                        f"{t3:.0%}"   if t3   is not None else "",
                        f"{aoa:.1f}"  if aoa  is not None else "",
                        f"{mtld:.0f}" if mtld is not None else "",
                    ))
                else:
                    self._vocab_tree.insert("", tk.END,
                        values=(cc_name, r.status, "", "", "", "", "", "", ""))
            ok_count = sum(1 for r in results if r.status == "ok")
            self._vocab_progress_var.set(
                f"Done — {ok_count} / {len(results)} analyzed successfully."
            )
            if ok_count > 0:
                self._btn_vocab_export.config(state=tk.NORMAL)

    def _maybe_save_show_aggregate(self, ep_path: Path) -> None:
        """If all episodes of the show are now cached, compute and save the aggregate."""
        show_dir = ep_path.parent
        skey = show_key(self._root_folder, show_dir)
        dname, _ = display_show_name(self._root_folder, show_dir)
        episodes = list_episodes(show_dir)
        if not episodes:
            return
        all_results = []
        for ep in episodes:
            c = load_cached(self._root_folder, skey, ep.stem)
            if c:
                all_results.append(EpisodeResult.from_dict(c))
        if len(all_results) == len(episodes):
            agg = compute_show_aggregate(dname, all_results)
            save_show_results(self._root_folder, skey, all_results, agg)
            if self._db_conn:
                upsert_show(self._db_conn, agg, dname)

    # -----------------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------------

    def _export_json(self) -> None:
        if self._current_ep_result:
            default = Path(self._current_ep_result.file).stem + "_analysis.json"
            path = filedialog.asksaveasfilename(
                title="Export episode JSON",
                defaultextension=".json",
                filetypes=[("JSON", "*.json")],
                initialfile=default,
            )
            if path:
                Path(path).write_text(
                    json.dumps(self._current_ep_result.to_dict(), indent=2),
                    encoding="utf-8",
                )
                self._status_var.set(f"Exported JSON: {Path(path).name}")
        elif self._current_show_results:
            show_name = self._current_show_results[0].file.split("/")[0] if "/" in \
                self._current_show_results[0].file else "show"
            default = "show_analysis.json"
            path = filedialog.asksaveasfilename(
                title="Export show JSON",
                defaultextension=".json",
                filetypes=[("JSON", "*.json")],
                initialfile=default,
            )
            if path:
                data = [r.to_dict() for r in self._current_show_results]
                Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
                self._status_var.set(f"Exported JSON: {Path(path).name}")

    def _export_csv(self) -> None:
        from analyzer.aggregate import results_to_dataframe
        results = []
        if self._current_ep_result:
            results = [self._current_ep_result]
            default = Path(self._current_ep_result.file).stem + "_analysis.csv"
        elif self._current_show_results:
            results = self._current_show_results
            default = "show_analysis.csv"
        else:
            return
        path = filedialog.asksaveasfilename(
            title="Export CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=default,
        )
        if path:
            df = results_to_dataframe(results)
            df.to_csv(path, index=False)
            self._status_var.set(f"Exported CSV: {Path(path).name}")

    def _export_pdf(self) -> None:
        from analyzer.report_pdf import export_episode_pdf, export_show_pdf
        if self._current_ep_result:
            result = self._current_ep_result
            default = Path(result.file).stem + "_report.pdf"
            path = filedialog.asksaveasfilename(
                title="Export Episode Report as PDF",
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf")],
                initialfile=default,
            )
            if path:
                try:
                    export_episode_pdf(result, self._cfg, Path(path))
                    self._status_var.set(f"PDF saved: {Path(path).name}")
                except Exception as exc:
                    messagebox.showerror("PDF export failed", str(exc))
        elif self._current_show_results:
            show_name = self._current_show_results[0].file.split("/")[0] \
                        if "/" in self._current_show_results[0].file else "show"
            default = f"{show_name}_report.pdf"
            path = filedialog.asksaveasfilename(
                title="Export Show Report as PDF",
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf")],
                initialfile=default,
            )
            if path:
                try:
                    # Reload the aggregate from cache so we have the full object
                    from analyzer.aggregate import compute_show_aggregate
                    agg = compute_show_aggregate(show_name, self._current_show_results)
                    export_show_pdf(agg, self._current_show_results, self._cfg, Path(path))
                    self._status_var.set(f"PDF saved: {Path(path).name}")
                except Exception as exc:
                    messagebox.showerror("PDF export failed", str(exc))

    # -----------------------------------------------------------------------
    # Chart
    # -----------------------------------------------------------------------

    def _show_chart(self) -> None:
        if self._current_show_results:
            self._show_series_chart()
        elif self._current_ep_result:
            self._show_episode_chart()

    def _show_episode_chart(self) -> None:
        result = self._current_ep_result
        if not result:
            return
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        win = tk.Toplevel(self)
        win.title(f"Chart: {result.file}")
        win.geometry("560x400")
        win.resizable(True, True)

        fig = Figure(figsize=(5.6, 4.0), dpi=100)
        ax = fig.add_subplot(111)
        fig.subplots_adjust(left=0.10, right=0.97, top=0.88, bottom=0.10)

        c = result.metrics.sensory_load.components
        w = self._cfg.get("sensory_load_weights", {})
        labels = ["Pacing", "Saturation", "Contrast", "Motion", "Flashing", "Audio"]
        keys   = ["pacing", "saturation", "contrast", "motion", "flashing", "audio"]
        # Weight keys in config use "color_contrast"; component attribute is "contrast"
        weight_keys = ["pacing", "saturation", "color_contrast", "motion", "flashing", "audio"]
        norm_vals     = [getattr(c, k) for k in keys]
        weighted_vals = [getattr(c, k) * w.get(wk, 0) for k, wk in zip(keys, weight_keys)]

        x = list(range(len(labels)))
        ax.bar(x, norm_vals, color="#5b9bd5", alpha=0.55, label="Normalized (raw component)")
        ax.bar(x, weighted_vals, color="#1f497d", alpha=0.90, label="Weighted contribution")
        ax.axhline(result.metrics.sensory_load.score, color="#c00000",
                   linestyle="--", linewidth=1.2,
                   label=f"Composite score: {result.metrics.sensory_load.score:.3f}")

        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("Value (0–1)")
        title = result.file if len(result.file) <= 50 else "..." + result.file[-47:]
        ax.set_title(title, fontsize=9)
        ax.legend(fontsize=8)

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _show_series_chart(self) -> None:
        """Bar chart: one bar per episode. User picks x-axis, y-axis, and colour mode."""
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.patches import Patch
        from matplotlib.lines import Line2D
        import statistics as _stats
        from analyzer.db import query_episodes
        from analyzer.wiki_importer import extract_season_ep

        results = self._current_show_results
        if not results:
            return

        _PALETTE = [
            "#4472C4", "#ED7D31", "#70AD47", "#FFC000", "#7030A0",
            "#00B0F0", "#FF0000", "#92D050", "#FF7C80", "#002060",
        ]

        # -- metric definitions -----------------------------------------------
        def _safe(fn, r):
            try:
                v = fn(r)
                return float(v) if v is not None else None
            except (AttributeError, TypeError):
                return None

        _METRIC_DEFS = [
            ("Sensory Load Score",
             lambda r: r.metrics.sensory_load.score,
             "Sensory Load Score (0–1)"),
            ("Cuts per Minute",
             lambda r: r.metrics.scene_pacing.cuts_per_min,
             "Cuts per Minute"),
            ("Color Saturation",
             lambda r: r.metrics.color_saturation.mean,
             "Saturation (mean, 0–1)"),
            ("Color Contrast",
             lambda r: r.metrics.color_saturation.contrast_mean,
             "Contrast (mean, 0–1)"),
            ("Motion",
             lambda r: r.metrics.motion.mean,
             "Motion (mean, 0–1)"),
            ("Flashing / min",
             lambda r: r.metrics.flashing.luminance_delta_events_per_min,
             "Flashing Events per Minute"),
            ("Audio RMS",
             lambda r: r.metrics.audio.rms_mean if r.metrics.audio.available else None,
             "Audio RMS (dBFS)"),
        ]
        metric_names  = [m[0] for m in _METRIC_DEFS]
        metric_lookup = {m[0]: (m[1], m[2]) for m in _METRIC_DEFS}

        # per-file metric values (extracted once)
        data_by_file: dict[str, dict[str, float | None]] = {}
        for r in results:
            data_by_file[r.file] = {name: _safe(fn, r) for name, fn, _ in _METRIC_DEFS}

        # -- build x-axis orderings and collect air dates ---------------------
        ordering_by_date: list[tuple[str, str, int]] = []  # (label, file_name, season_num)
        ordering_by_ep:   list[tuple[str, str, int]] = []
        air_date_by_file: dict[str, str] = {}
        has_dates = False

        db_joined: list[dict] = []
        if self._db_conn and self._current_show_name:
            rows = query_episodes(
                self._db_conn,
                filter_show=self._current_show_name,
                sort_by="season_num",
                ascending=True,
            )
            db_joined = [
                {
                    "file_name":   r["file_name"],
                    "air_date":    r.get("air_date") or "",
                    "season_num":  r.get("season_num") or 0,
                    "episode_num": r.get("episode_num") or 0,
                }
                for r in rows
                if r["file_name"] in data_by_file
            ]
            for d in db_joined:
                air_date_by_file[d["file_name"]] = d["air_date"]

        if db_joined:
            with_date = sum(1 for d in db_joined if d["air_date"])
            has_dates = with_date >= len(db_joined) * 0.8
            for d in sorted(db_joined, key=lambda d: d["air_date"] or "9999-99-99"):
                ordering_by_date.append((d["air_date"] or "—", d["file_name"], d["season_num"]))
            for d in sorted(db_joined, key=lambda d: (d["season_num"], d["episode_num"])):
                lbl = (f"S{d['season_num']}E{d['episode_num']:02d}"
                       if (d["season_num"] or d["episode_num"]) else d["file_name"][:14])
                ordering_by_ep.append((lbl, d["file_name"], d["season_num"]))

        if not ordering_by_ep:
            for r in sorted(results, key=lambda r: extract_season_ep(r.file) or (99, 99)):
                pair   = extract_season_ep(r.file)
                lbl    = f"S{pair[0]}E{pair[1]:02d}" if pair else r.file[:14]
                season = pair[0] if pair else 0
                ordering_by_ep.append((lbl, r.file, season))
            if not ordering_by_date:
                ordering_by_date = list(ordering_by_ep)

        if not ordering_by_ep:
            return

        # -- load saved eras from DB ------------------------------------------
        _state: dict = {"eras": []}
        if self._db_conn and self._current_show_name:
            _state["eras"] = get_show_eras(self._db_conn, self._current_show_name)

        # -- era colour helper ------------------------------------------------
        def _era_color(air_date: str, eras: list[dict]) -> str:
            if not air_date or not eras:
                return "#AAAAAA"
            for i, era in enumerate(eras):
                start = era.get("start_date") or "0000-00-00"
                end   = era.get("end_date")   or "9999-99-99"
                if start <= air_date <= end:
                    return era.get("color") or _PALETTE[i % len(_PALETTE)]
            return "#CCCCCC"

        # -- window -----------------------------------------------------------
        n = len(ordering_by_ep)
        fig_w = max(8.0, min(22.0, n * 0.15 + 2.5))
        win_w = int(fig_w * 100)

        win = tk.Toplevel(self)
        win.title(f"Chart: {self._current_show_name}")
        win.geometry(f"{win_w}x620")
        win.resizable(True, True)

        # -- control bar ------------------------------------------------------
        ctrl = tk.Frame(win, bd=1, relief=tk.GROOVE)
        ctrl.pack(fill=tk.X, padx=8, pady=(6, 2))

        tk.Label(ctrl, text="X-axis:").pack(side=tk.LEFT, padx=(8, 4))
        mode_var = tk.StringVar()
        mode_options = (["Air Date"] if has_dates else []) + ["Episode Number"]
        mode_cb = ttk.Combobox(ctrl, textvariable=mode_var, values=mode_options,
                               state="readonly", width=16)
        mode_cb.pack(side=tk.LEFT, padx=(0, 14), pady=4)
        mode_var.set(mode_options[0])

        tk.Label(ctrl, text="Y-axis:").pack(side=tk.LEFT, padx=(0, 4))
        yaxis_var = tk.StringVar()
        yaxis_cb = ttk.Combobox(ctrl, textvariable=yaxis_var, values=metric_names,
                                state="readonly", width=20)
        yaxis_cb.pack(side=tk.LEFT, padx=(0, 14), pady=4)
        yaxis_var.set(metric_names[0])

        tk.Label(ctrl, text="Colour by:").pack(side=tk.LEFT, padx=(0, 4))
        colby_var = tk.StringVar(value="Season")
        colby_cb = ttk.Combobox(ctrl, textvariable=colby_var,
                                values=["Season", "Era"],
                                state="readonly", width=10)
        colby_cb.pack(side=tk.LEFT, padx=(0, 8), pady=4)

        era_btn = tk.Button(ctrl, text="Edit Eras…", padx=6,
                            command=lambda: _open_era_editor())
        era_btn.pack(side=tk.LEFT, padx=(0, 8), pady=4)

        # -- figure / canvas --------------------------------------------------
        bottom_pad = 0.24 if n > 15 else 0.12
        fig = Figure(figsize=(fig_w, 5.0), dpi=100)
        ax  = fig.add_subplot(111)
        fig.subplots_adjust(left=0.09, right=0.97, top=0.90, bottom=bottom_pad)

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # -- draw / redraw ----------------------------------------------------
        def _redraw(*_):
            xmode   = mode_var.get()
            ymetric = yaxis_var.get()
            colby   = colby_var.get()
            ordering = ordering_by_date if xmode == "Air Date" else ordering_by_ep
            _, y_axis_label = metric_lookup[ymetric]

            x_labels = [t[0] for t in ordering]
            files    = [t[1] for t in ordering]
            seasons  = [t[2] for t in ordering]
            raw_vals = [data_by_file.get(f, {}).get(ymetric) for f in files]
            scores   = [v if v is not None else 0.0 for v in raw_vals]
            n_ep     = len(scores)

            # -- colour assignment -------------------------------------------
            handles_extra: list = []
            if colby == "Era":
                eras = _state["eras"]
                bar_colors = [_era_color(air_date_by_file.get(f, ""), eras)
                              for f in files]
                used_era_indices = []
                outside = any(c == "#CCCCCC" for c in bar_colors)
                no_date = any(c == "#AAAAAA" for c in bar_colors)
                for i, era in enumerate(eras):
                    era_color = era.get("color") or _PALETTE[i % len(_PALETTE)]
                    if era_color in bar_colors:
                        handles_extra.append(
                            Patch(color=era_color, label=era["era_name"])
                        )
                        used_era_indices.append(i)
                if outside:
                    handles_extra.append(Patch(color="#CCCCCC", label="Outside all eras"))
                if no_date:
                    handles_extra.append(Patch(color="#AAAAAA", label="No air date"))
            else:
                unique_seasons = sorted(set(seasons))
                season_colors  = {s: _PALETTE[i % len(_PALETTE)]
                                  for i, s in enumerate(unique_seasons)}
                bar_colors = [season_colors[s] for s in seasons]
                if len(unique_seasons) > 1:
                    for s in unique_seasons:
                        handles_extra.append(
                            Patch(color=season_colors[s],
                                  label=f"Season {s}" if s else "Unknown season")
                        )

            valid = [v for v in scores if v > 0]
            mean_score   = sum(valid) / len(valid) if valid else 0.0
            median_score = _stats.median(valid) if valid else 0.0

            ax.clear()
            ax.bar(list(range(n_ep)), scores, color=bar_colors, width=0.8, zorder=2)
            ax.axhline(mean_score,   color="#c00000", linestyle="--", linewidth=1.3, zorder=3)
            ax.axhline(median_score, color="#e07000", linestyle=":",  linewidth=1.3, zorder=3)

            step  = max(1, n_ep // 60)
            ticks = list(range(0, n_ep, step))
            rot   = 90 if n_ep > 15 else 45
            fsize = max(5, 9 - n_ep // 15)
            ax.set_xticks(ticks)
            ax.set_xticklabels([x_labels[i] for i in ticks], rotation=rot,
                               ha="right" if rot < 90 else "center", fontsize=fsize)

            ax.set_xlim(-0.6, n_ep - 0.4)
            y_max = max(scores) if scores else 1.0
            ax.set_ylim(0, y_max * 1.25 if y_max > 0 else 1.0)
            ax.set_ylabel(y_axis_label)
            ax.set_xlabel(xmode, labelpad=4)
            ax.set_title(
                f"{self._current_show_name}  —  {ymetric}  ({n_ep} episodes)",
                fontsize=10,
            )
            ax.yaxis.grid(True, alpha=0.35, zorder=1)
            ax.set_axisbelow(True)

            handles = [
                Line2D([0], [0], color="#c00000", linestyle="--", linewidth=1.3,
                       label=f"Mean: {mean_score:.3f}"),
                Line2D([0], [0], color="#e07000", linestyle=":",  linewidth=1.3,
                       label=f"Median: {median_score:.3f}"),
            ] + handles_extra
            ax.legend(handles=handles, fontsize=8, loc="upper right")
            canvas.draw()

        # -- era editor launcher ----------------------------------------------
        def _open_era_editor() -> None:
            def _on_apply(new_eras: list[dict]) -> None:
                _state["eras"] = new_eras
                _redraw()

            EraEditorDialog(
                win,
                show_name=self._current_show_name or "",
                initial_eras=_state["eras"],
                db_conn=self._db_conn,
                on_apply=_on_apply,
            )

        mode_cb.bind("<<ComboboxSelected>>", _redraw)
        yaxis_cb.bind("<<ComboboxSelected>>", _redraw)
        colby_cb.bind("<<ComboboxSelected>>", _redraw)
        _redraw()

    # -----------------------------------------------------------------------
    # Settings
    # -----------------------------------------------------------------------

    def _open_sampler(self) -> None:
        SamplerWindow(self, app_ref=self)

    def _open_wiki_import(self) -> None:
        WikiImportDialog(self, app_ref=self)

    def _open_tvmaze_import(self) -> None:
        TVMazeImportDialog(self, app_ref=self)

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self)
        self.wait_window(dlg)
        self._refresh_toolbar_presets()

    def _refresh_current_view(self) -> None:
        """Re-render whatever is currently selected, rescoring from cache with self._cfg."""
        kind, path = self._selected_item()
        if kind == "episode":
            ep_path = Path(path)
            skey = show_key(self._root_folder, ep_path.parent)
            cached = load_cached(self._root_folder, skey, ep_path.stem)
            if cached:
                self._current_ep_path = ep_path
                result = rescore_episode(EpisodeResult.from_dict(cached), self._cfg)
                self._render_episode(result)
        elif kind == "show":
            show_dir = Path(path)
            skey = show_key(self._root_folder, show_dir)
            dname, _ = display_show_name(self._root_folder, show_dir)
            episodes = list_episodes(show_dir)
            ok_results = []
            for ep in episodes:
                c = load_cached(self._root_folder, skey, ep.stem)
                if c:
                    ok_results.append(rescore_episode(EpisodeResult.from_dict(c), self._cfg))
            if ok_results:
                agg = compute_show_aggregate(dname, ok_results)
                self._render_show(agg, ok_results, total_eps=len(episodes))

    # -----------------------------------------------------------------------
    # Toolbar preset helpers
    # -----------------------------------------------------------------------

    def _refresh_toolbar_presets(self) -> None:
        """Update combobox values and select whichever preset matches current cfg."""
        presets = list(self._cfg.get("presets", {}).keys()) + ["Custom"]
        self._toolbar_preset_cb.config(values=presets)
        self._toolbar_preset_var.set(self._detect_toolbar_preset())

    def _detect_toolbar_preset(self) -> str:
        cur_w = self._cfg.get("sensory_load_weights", {})
        cur_r = self._cfg.get("normalization_reference_ranges", {})
        for name, p in self._cfg.get("presets", {}).items():
            if (p.get("sensory_load_weights") == cur_w
                    and p.get("normalization_reference_ranges") == cur_r):
                return name
        return "Custom"

    def _on_toolbar_preset_change(self, _event=None) -> None:
        name = self._toolbar_preset_var.get()
        presets = self._cfg.get("presets", {})
        if name == "Custom" or name not in presets:
            return
        p = presets[name]
        self._cfg["sensory_load_weights"] = copy.deepcopy(p["sensory_load_weights"])
        self._cfg["normalization_reference_ranges"] = copy.deepcopy(
            p["normalization_reference_ranges"]
        )
        self._refresh_current_view()
        # Update DB index scores and refresh the Index tab
        if self._db_conn and self._root_folder:
            self._backfill_index()
            self._refresh_index()
        self._status_var.set(f"Preset '{name}' applied — displayed scores updated.")

    # -----------------------------------------------------------------------
    # Notes
    # -----------------------------------------------------------------------

    def _save_note(self) -> None:
        if not self._db_conn or not self._current_ep_path:
            return
        note = self._notes_text.get("1.0", tk.END).rstrip("\n")
        save_note(self._db_conn, str(self._current_ep_path), note)
        self._status_var.set(f"Note saved for {self._current_ep_path.name}.")

    @staticmethod
    def _parse_air_date(raw: str) -> str | None:
        """Accept many date formats; return normalized YYYY-MM-DD or None if unparseable."""
        from datetime import datetime
        raw = raw.strip()
        if not raw:
            return None
        _fmts = [
            "%Y-%m-%d",    # 1995-09-04
            "%m/%d/%Y",    # 9/4/1995  or  11/8/1995
            "%m-%d-%Y",    # 09-04-1995
            "%Y/%m/%d",    # 1995/09/04
            "%-m/%-d/%Y",  # single-digit m/d (Linux)
            "%d %B %Y",    # 4 September 1995
            "%B %d, %Y",   # September 4, 1995
            "%B %d %Y",    # September 4 1995
            "%d-%b-%Y",    # 04-Sep-1995
            "%d %b %Y",    # 8 Nov 1995
            "%b %d, %Y",   # Sep 4, 1995
            "%b %d %Y",    # Sep 4 1995
            "%d/%m/%Y",    # European: 8/11/1995
        ]
        for fmt in _fmts:
            try:
                return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return False  # sentinel: unparseable but non-empty

    def _save_metadata(self) -> None:
        if not self._db_conn or not self._current_ep_path:
            return
        air_date_raw = self._meta_air_date.get().strip()
        air_date = self._parse_air_date(air_date_raw) if air_date_raw else None
        if air_date is False:
            messagebox.showwarning(
                "Invalid date",
                f"Could not parse \"{air_date_raw}\" as a date.\n\n"
                "Accepted formats include:\n"
                "  11/8/1995   •   1995-11-08\n"
                "  November 8, 1995   •   8 Nov 1995",
                parent=self,
            )
            return
        if air_date:
            # Reflect the normalized form back into the field
            self._meta_air_date.set(air_date)
        season_raw = self._meta_season.get().strip()
        ep_raw     = self._meta_ep_num.get().strip()
        try:
            season_num = int(season_raw) if season_raw else None
            episode_num = int(ep_raw) if ep_raw else None
        except ValueError:
            messagebox.showwarning(
                "Invalid value",
                "Season and Episode # must be whole numbers.",
                parent=self,
            )
            return
        upsert_episode_metadata(
            self._db_conn, str(self._current_ep_path),
            air_date, season_num, episode_num,
        )
        self._status_var.set(f"Metadata saved for {self._current_ep_path.name}.")
        self._refresh_index()

    def _pin_for_compare(self) -> None:
        kind, path = self._selected_item()
        if not kind:
            return
        self._pinned = (kind, Path(path))
        name = Path(path).name
        self._pinned_var.set(f"Pinned: {name}")
        self._on_tree_select()   # re-evaluate compare button state

    def _open_compare(self) -> None:
        if not self._pinned or not self._root_folder:
            return
        kind, path = self._selected_item()
        if not kind:
            return
        pin_kind, pin_path = self._pinned

        if kind == "episode" and pin_kind == "episode":
            def _load_ep(ep: Path) -> EpisodeResult | None:
                c = load_cached(self._root_folder, show_key(self._root_folder, ep.parent), ep.stem)
                return rescore_episode(EpisodeResult.from_dict(c), self._cfg) if c else None
            a = _load_ep(pin_path)
            b = _load_ep(Path(path))
            if not a or not b:
                messagebox.showinfo("Not analyzed",
                                    "Both episodes must be analyzed before comparing.",
                                    parent=self)
                return
            CompareWindow(self, a, b)

        elif kind == "show" and pin_kind == "show":
            def _load_show(show_dir: Path) -> ShowAggregate | None:
                skey = show_key(self._root_folder, show_dir)
                results = []
                for ep in list_episodes(show_dir):
                    c = load_cached(self._root_folder, skey, ep.stem)
                    if c:
                        results.append(rescore_episode(EpisodeResult.from_dict(c), self._cfg))
                return compute_show_aggregate(skey, results) if results else None
            a = _load_show(pin_path)
            b = _load_show(Path(path))
            if not a or not b:
                messagebox.showinfo("Not analyzed",
                                    "Both shows need at least one analyzed episode.",
                                    parent=self)
                return
            CompareWindow(self, a, b)

    def _remove_stale_index(self) -> None:
        """Delete DB rows whose files no longer exist (e.g. after a folder rename)."""
        if not self._db_conn:
            return
        n = remove_stale_episodes(self._db_conn)
        self._refresh_index()
        if n:
            self._status_var.set(
                f"Removed {n} stale entr{'y' if n == 1 else 'ies'} "
                f"(files no longer on disk). Re-analyze to re-index them."
            )
        else:
            self._status_var.set("No stale entries found — all indexed files still exist.")

    # -----------------------------------------------------------------------
    # Index tab (Phase 5)
    # -----------------------------------------------------------------------

    def _build_index_tab(self, parent: tk.Frame) -> None:
        # Filter bar
        filter_frame = tk.Frame(parent)
        filter_frame.pack(fill=tk.X, padx=4, pady=(4, 2))
        tk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT)
        self._idx_filter_var = tk.StringVar()
        self._idx_filter_var.trace_add("write", lambda *_: self._refresh_index())
        tk.Entry(filter_frame, textvariable=self._idx_filter_var,
                 width=15).pack(side=tk.LEFT, padx=(4, 6), fill=tk.X, expand=True)
        tk.Button(filter_frame, text="Refresh", command=self._refresh_index,
                  padx=4).pack(side=tk.RIGHT)
        tk.Button(filter_frame, text="Remove Stale",
                  command=self._remove_stale_index,
                  padx=4).pack(side=tk.RIGHT, padx=(0, 4))

        # Sub-notebook: Episodes / Shows
        sub_nb = ttk.Notebook(parent)
        sub_nb.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # ---- Episodes sub-tab ----
        ep_tab = tk.Frame(sub_nb)
        sub_nb.add(ep_tab, text="Episodes")

        _ep_cols   = ("show", "file", "airdate", "seas", "epn", "dur", "load", "cpm", "sat", "con", "mot", "flash", "rms", "date", "notes")
        _ep_hdrs   = ("Show", "File", "Air Date", "S", "Ep", "Dur(s)", "Load", "C/min", "Sat", "Contrast", "Motion", "Flash/m", "RMS", "Date", "Notes")
        _ep_widths = (80, 110, 72, 26, 30, 48, 48, 48, 42, 55, 50, 55, 48, 82, 130)
        self._idx_ep_db_cols = (
            "show_name", "file_name", "air_date", "season_num", "episode_num",
            "duration_sec", "sensory_load_score",
            "cuts_per_min", "color_saturation_mean", "color_contrast_mean",
            "motion_mean", "flashing_events_per_min", "audio_rms_mean",
            "analyzed_at", "notes",
        )

        ep_tree_frame = tk.Frame(ep_tab)
        ep_tree_frame.pack(fill=tk.BOTH, expand=True)

        self._idx_ep_tree = ttk.Treeview(
            ep_tree_frame, columns=_ep_cols, show="headings", selectmode="browse"
        )
        for col, hdr, w, db_col in zip(_ep_cols, _ep_hdrs, _ep_widths, self._idx_ep_db_cols):
            self._idx_ep_tree.heading(
                col, text=hdr,
                command=lambda c=db_col: self._on_idx_ep_col_click(c),
            )
            self._idx_ep_tree.column(col, width=w, minwidth=28, stretch=False)

        ep_vsb = ttk.Scrollbar(ep_tree_frame, orient=tk.VERTICAL,
                                command=self._idx_ep_tree.yview)
        ep_hsb = ttk.Scrollbar(ep_tree_frame, orient=tk.HORIZONTAL,
                                command=self._idx_ep_tree.xview)
        self._idx_ep_tree.configure(yscrollcommand=ep_vsb.set, xscrollcommand=ep_hsb.set)
        ep_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        ep_hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self._idx_ep_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._idx_ep_tree.bind("<Double-1>", lambda _e: self._idx_view_details())

        ep_btn_row = tk.Frame(ep_tab)
        ep_btn_row.pack(fill=tk.X, padx=4, pady=(2, 4))
        tk.Button(ep_btn_row, text="View Details",
                  command=self._idx_view_details, padx=6).pack(side=tk.LEFT)

        # ---- Shows sub-tab ----
        sh_tab = tk.Frame(sub_nb)
        sub_nb.add(sh_tab, text="Shows")

        _sh_cols   = ("show", "eps", "load", "cpm", "mot", "sat", "con", "flash", "rms")
        _sh_hdrs   = ("Show", "Eps", "Avg Load", "C/min", "Motion", "Sat", "Contrast", "Flash/m", "Audio RMS")
        _sh_widths = (110, 32, 62, 52, 52, 46, 58, 55, 65)
        _sh_db_cols = (
            "show_name", "episode_count", "avg_load",
            "avg_cuts_per_min", "avg_motion", "avg_saturation",
            "avg_contrast", "avg_flashing", "avg_audio_rms",
        )

        sh_tree_frame = tk.Frame(sh_tab)
        sh_tree_frame.pack(fill=tk.BOTH, expand=True)

        self._idx_sh_tree = ttk.Treeview(
            sh_tree_frame, columns=_sh_cols, show="headings", selectmode="browse"
        )
        for col, hdr, w, db_col in zip(_sh_cols, _sh_hdrs, _sh_widths, _sh_db_cols):
            self._idx_sh_tree.heading(
                col, text=hdr,
                command=lambda c=db_col: self._on_idx_show_col_click(c),
            )
            self._idx_sh_tree.column(col, width=w, minwidth=28, stretch=False)

        sh_vsb = ttk.Scrollbar(sh_tree_frame, orient=tk.VERTICAL,
                                command=self._idx_sh_tree.yview)
        sh_hsb = ttk.Scrollbar(sh_tree_frame, orient=tk.HORIZONTAL,
                                command=self._idx_sh_tree.xview)
        self._idx_sh_tree.configure(yscrollcommand=sh_vsb.set, xscrollcommand=sh_hsb.set)
        sh_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        sh_hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self._idx_sh_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Column-header tooltips
        _IndexTooltip(self._idx_ep_tree, {
            "show":  "Show name",
            "file":  "Episode filename",
            "dur":   "Duration in seconds",
            "cpm":   "Cuts per minute — how often the camera cuts to a new shot.\nHigher = faster-paced.",
            "sat":   "Color saturation mean (0-1) — how vivid and pure the colors are.\nTypically higher in cartoons, lower in live-action.",
            "con":   "Color contrast mean (0-1) — spatial spread of brightness within frames.\n"
                     "High for stark dark/light content such as presentation slides or whiteboards.\n"
                     "Can push live-action/lecture scores up unexpectedly relative to animation.",
            "mot":   "Motion mean (0-1) — average frame-to-frame movement across the episode.",
            "flash": "Flashing events per minute — luminance changes above threshold.\nRelevant to photosensitivity and overstimulation.",
            "rms":   "Audio RMS loudness mean — average volume level.\n"
                     "Spoken-word content (lectures, narration) often scores higher here\n"
                     "than music-backed animation with quieter dialogue.\n"
                     "'n/a' if no audio track detected.",
            "load":  "Sensory load composite score (0-1) — weighted combination of all metrics.\n"
                     "Higher = more stimulating.\n\n"
                     "Scores are calibrated to the preset active when each episode was analyzed.\n"
                     "Cross-genre comparisons (e.g., cartoons vs. lectures) may be misleading\n"
                     "under the General preset — see Help → About metrics for details.",
            "airdate": "Original broadcast / air date (YYYY-MM-DD).\nEnter this in the Episode Metadata panel after analyzing.",
            "seas":    "Season number (entered in Episode Metadata panel).",
            "epn":     "Episode number within the season (entered in Episode Metadata panel).",
            "date":    "Date and time this episode was last analyzed by CMAT.",
            "notes":   "Your saved note for this episode. Hover a row to read the full text.",
        })
        _CellTooltip(self._idx_ep_tree, "notes")
        _IndexTooltip(self._idx_sh_tree, {
            "show":  "Show name",
            "eps":   "Number of analyzed episodes in the index",
            "load":  "Average sensory load score across all episodes (0-1).\n\n"
                     "Scores are calibrated to the preset used at analysis time.\n"
                     "A lecture with high-contrast slides and loud speech can\n"
                     "score above an animated show under the General preset because\n"
                     "contrast and audio don't scale with genre expectations.\n"
                     "Use Preschool or Early Childhood presets for children's-only libraries.",
            "cpm":   "Average cuts per minute across all episodes.",
            "mot":   "Average motion mean across all episodes.",
            "sat":   "Average color saturation mean across all episodes.",
            "con":   "Average color contrast mean across all episodes.\n"
                     "High for content with stark bright/dark frames (slides, whiteboards).",
            "flash": "Average flashing events per minute across all episodes.",
            "rms":   "Average audio RMS loudness across all episodes.\n"
                     "Spoken-word content typically scores higher than animation.",
        })

        # Genre/preset guidance note below the Shows table
        note_text = (
            "Tip: scores are most meaningful when comparing content of the same genre "
            "analyzed under the same preset. Lectures with high-contrast slides or loud "
            "speech may outscore animated shows under General/All Ages — this is "
            "mathematically correct but not always intuitive. Use the Preschool or Early "
            "Childhood preset for a children's-content-only library, or see "
            "Help → About metrics for a full explanation."
        )
        tk.Label(
            sh_tab, text=note_text, justify=tk.LEFT,
            fg="#555555", font=("TkDefaultFont", 8),
            wraplength=260, anchor="w",
        ).pack(side=tk.BOTTOM, fill=tk.X, padx=4, pady=(2, 4))

    def _refresh_index(self) -> None:
        """Re-query the DB and repopulate both index Treeviews."""
        if not self._db_conn:
            return
        filter_str = getattr(self, "_idx_filter_var", None)
        filter_str = filter_str.get() if filter_str else ""

        # Episodes
        ep_rows = query_episodes(
            self._db_conn,
            sort_by=self._idx_ep_sort["col"],
            ascending=self._idx_ep_sort["asc"],
            filter_show=filter_str,
        )
        self._idx_ep_tree.delete(*self._idx_ep_tree.get_children())
        for r in ep_rows:
            def _fmt(v, fmt):
                return fmt % v if v is not None else ""
            note_full = r.get("notes") or ""
            note_disp = (note_full[:28] + "…") if len(note_full) > 28 else note_full
            self._idx_ep_tree.insert("", tk.END,
                values=(
                    r["show_name"],
                    r["file_name"],
                    r.get("air_date") or "",
                    str(r["season_num"]) if r.get("season_num") is not None else "",
                    str(r["episode_num"]) if r.get("episode_num") is not None else "",
                    _fmt(r["duration_sec"], "%.0f"),
                    _fmt(r["sensory_load_score"], "%.3f"),
                    _fmt(r["cuts_per_min"], "%.1f"),
                    _fmt(r["color_saturation_mean"], "%.3f"),
                    _fmt(r["color_contrast_mean"], "%.3f") if r.get("color_contrast_mean") is not None else "",
                    _fmt(r["motion_mean"], "%.3f"),
                    _fmt(r["flashing_events_per_min"], "%.1f") if r["flashing_events_per_min"] is not None else "",
                    _fmt(r["audio_rms_mean"], "%.4f") if r["audio_rms_mean"] is not None else "n/a",
                    r["analyzed_at"] or "",
                    note_disp,
                ),
                tags=(r["file_path"],),
            )

        # Shows
        sh_rows = query_shows(
            self._db_conn,
            sort_by=self._idx_show_sort["col"],
            ascending=self._idx_show_sort["asc"],
        )
        self._idx_sh_tree.delete(*self._idx_sh_tree.get_children())
        def _sv(r, key, fmt):
            v = r.get(key)
            return fmt % v if v is not None else ""

        for r in sh_rows:
            self._idx_sh_tree.insert("", tk.END,
                values=(
                    r["show_name"],
                    r["episode_count"],
                    _sv(r, "avg_load",         "%.3f"),
                    _sv(r, "avg_cuts_per_min", "%.1f"),
                    _sv(r, "avg_motion",       "%.3f"),
                    _sv(r, "avg_saturation",   "%.3f"),
                    _sv(r, "avg_contrast",     "%.3f"),
                    _sv(r, "avg_flashing",     "%.1f"),
                    _sv(r, "avg_audio_rms",    "%.4f"),
                ),
                tags=(r["show_name"],),
            )

    def _on_idx_ep_col_click(self, col: str) -> None:
        if self._idx_ep_sort["col"] == col:
            self._idx_ep_sort["asc"] = not self._idx_ep_sort["asc"]
        else:
            self._idx_ep_sort = {"col": col, "asc": True}
        self._refresh_index()

    def _on_idx_show_col_click(self, col: str) -> None:
        if self._idx_show_sort["col"] == col:
            self._idx_show_sort["asc"] = not self._idx_show_sort["asc"]
        else:
            self._idx_show_sort = {"col": col, "asc": True}
        self._refresh_index()

    def _idx_view_details(self) -> None:
        """Load the cached result for the selected index episode into the results panel."""
        sel = self._idx_ep_tree.selection()
        if not sel:
            return
        tags = self._idx_ep_tree.item(sel[0], "tags")
        if not tags:
            return
        file_path = tags[0]
        ep_path = Path(file_path)
        if not self._root_folder:
            messagebox.showinfo("No root folder",
                                "Choose a root folder first.", parent=self)
            return
        cached = load_cached(self._root_folder, show_key(self._root_folder, ep_path.parent), ep_path.stem)
        if cached:
            self._current_ep_path = ep_path
            result = rescore_episode(EpisodeResult.from_dict(cached), self._cfg)
            self._render_episode(result)
        else:
            self._status_var.set(
                f"Cache not found for {ep_path.name} — may belong to a different root folder."
            )

    def _backfill_index(self) -> None:
        """Seed the DB from all existing cached episode JSONs, rescored with current config."""
        if not self._db_conn or not self._root_folder:
            return
        for show_dir in list_shows(self._root_folder):
            skey = show_key(self._root_folder, show_dir)
            dname, auto_s = display_show_name(self._root_folder, show_dir)
            show_results = []
            for ep in list_episodes(show_dir):
                c = load_cached(self._root_folder, skey, ep.stem)
                if c:
                    try:
                        result = EpisodeResult.from_dict(c)
                        if result.status == "ok":
                            result = rescore_episode(result, self._cfg)
                            upsert_episode(self._db_conn, result, dname, str(ep))
                            if auto_s is not None:
                                auto_set_season(self._db_conn, str(ep), auto_s)
                            show_results.append(result)
                    except Exception:
                        pass
            if show_results:
                try:
                    agg = compute_show_aggregate(dname, show_results)
                    upsert_show(self._db_conn, agg, dname)
                except Exception:
                    pass

    # -----------------------------------------------------------------------
    # Language tab
    # -----------------------------------------------------------------------

    def _build_language_tab(self, parent: tk.Frame) -> None:
        sub_nb = ttk.Notebook(parent)
        sub_nb.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # ---- Speech sub-tab ----
        sp_tab = tk.Frame(sub_nb)
        sub_nb.add(sp_tab, text="Speech")

        bar = tk.Frame(sp_tab)
        bar.pack(fill=tk.X, padx=4, pady=(4, 2))
        tk.Button(bar, text="Refresh", command=self._refresh_speech_data,
                  padx=4).pack(side=tk.LEFT)
        tk.Button(bar, text="Chart WPM...", command=self._chart_wpm_for_show,
                  padx=4).pack(side=tk.LEFT, padx=(4, 0))

        _sp_cols   = ("show", "file", "airdate", "wpm", "density", "words", "source")
        _sp_hdrs   = ("Show", "File", "Air Date", "WPM", "Density", "Total Words", "Source")
        _sp_widths = (90, 120, 72, 55, 62, 78, 60)

        sp_tree_frame = tk.Frame(sp_tab)
        sp_tree_frame.pack(fill=tk.BOTH, expand=True)

        self._lang_sp_tree = ttk.Treeview(
            sp_tree_frame, columns=_sp_cols, show="headings", selectmode="browse",
        )
        for col, hdr, w in zip(_sp_cols, _sp_hdrs, _sp_widths):
            self._lang_sp_tree.heading(
                col, text=hdr, command=lambda c=col: self._lang_sp_col_click(c),
            )
            self._lang_sp_tree.column(col, width=w, minwidth=28, stretch=False)

        sp_vsb = ttk.Scrollbar(sp_tree_frame, orient=tk.VERTICAL,
                                command=self._lang_sp_tree.yview)
        sp_hsb = ttk.Scrollbar(sp_tree_frame, orient=tk.HORIZONTAL,
                                command=self._lang_sp_tree.xview)
        self._lang_sp_tree.configure(yscrollcommand=sp_vsb.set, xscrollcommand=sp_hsb.set)
        sp_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        sp_hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self._lang_sp_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._lang_sp_note = tk.Label(
            sp_tab, text="Choose a root folder, then click Refresh.",
            fg="#555555", font=("TkDefaultFont", 8), anchor="w",
        )
        self._lang_sp_note.pack(fill=tk.X, padx=4, pady=(2, 4))

        # ---- Vocabulary sub-tab ----
        vc_tab = tk.Frame(sub_nb)
        sub_nb.add(vc_tab, text="Vocabulary")

        self._vocab_norm_label_var = tk.StringVar()
        tk.Label(
            vc_tab, textvariable=self._vocab_norm_label_var,
            fg="#444444", font=("TkDefaultFont", 8),
            anchor="w", justify=tk.LEFT, wraplength=260,
        ).pack(fill=tk.X, padx=4, pady=(4, 2))
        self._update_vocab_norm_label()

        pick_frame = tk.Frame(vc_tab)
        pick_frame.pack(fill=tk.X, padx=4, pady=(2, 2))
        tk.Button(pick_frame, text="Browse CC Files...",
                  command=self._vocab_browse_files, padx=4).pack(side=tk.LEFT)
        tk.Button(pick_frame, text="Browse Folder...",
                  command=self._vocab_browse_folder, padx=4).pack(side=tk.LEFT, padx=(4, 0))

        list_outer = tk.Frame(vc_tab)
        list_outer.pack(fill=tk.X, padx=4, pady=(2, 0))
        lb_vsb = ttk.Scrollbar(list_outer, orient=tk.VERTICAL)
        lb_hsb = ttk.Scrollbar(list_outer, orient=tk.HORIZONTAL)
        self._vocab_file_lb = tk.Listbox(
            list_outer, height=4, font=("Consolas", 8), selectmode=tk.EXTENDED,
            yscrollcommand=lb_vsb.set, xscrollcommand=lb_hsb.set,
        )
        lb_vsb.config(command=self._vocab_file_lb.yview)
        lb_hsb.config(command=self._vocab_file_lb.xview)
        lb_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        lb_hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self._vocab_file_lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        lb_btn_row = tk.Frame(vc_tab)
        lb_btn_row.pack(fill=tk.X, padx=4, pady=(2, 4))
        tk.Button(lb_btn_row, text="Remove Selected",
                  command=self._vocab_remove_selected, padx=4).pack(side=tk.LEFT)
        tk.Button(lb_btn_row, text="Clear All",
                  command=lambda: self._vocab_file_lb.delete(0, tk.END),
                  padx=4).pack(side=tk.LEFT, padx=(4, 0))

        analyze_frame = tk.Frame(vc_tab)
        analyze_frame.pack(fill=tk.X, padx=4, pady=(2, 2))
        self._btn_vocab_analyze = tk.Button(
            analyze_frame, text="Analyze",
            command=self._run_vocab_analysis,
            padx=6, fg="white", bg="#225522",
        )
        self._btn_vocab_analyze.pack(side=tk.LEFT)
        self._vocab_progress_var = tk.StringVar(value="")
        tk.Label(
            analyze_frame, textvariable=self._vocab_progress_var,
            fg="#333333", font=("TkDefaultFont", 8),
        ).pack(side=tk.LEFT, padx=(8, 0))

        _vc_cols   = ("file", "status", "flesch", "fk", "t1", "t2", "t3", "aoa", "mtld")
        _vc_hdrs   = ("File", "Status", "Flesch", "F-K Gr", "T1%", "T2%", "T3%", "AoA", "MTLD")
        _vc_widths = (130, 52, 50, 50, 42, 42, 42, 44, 55)

        vc_tree_frame = tk.Frame(vc_tab)
        vc_tree_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(2, 0))

        self._vocab_tree = ttk.Treeview(
            vc_tree_frame, columns=_vc_cols, show="headings", selectmode="browse",
        )
        for col, hdr, w in zip(_vc_cols, _vc_hdrs, _vc_widths):
            self._vocab_tree.heading(col, text=hdr)
            self._vocab_tree.column(col, width=w, minwidth=28, stretch=(col == "file"))

        vc_vsb = ttk.Scrollbar(vc_tree_frame, orient=tk.VERTICAL,
                                command=self._vocab_tree.yview)
        vc_hsb = ttk.Scrollbar(vc_tree_frame, orient=tk.HORIZONTAL,
                                command=self._vocab_tree.xview)
        self._vocab_tree.configure(yscrollcommand=vc_vsb.set, xscrollcommand=vc_hsb.set)
        vc_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        vc_hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self._vocab_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        action_row = tk.Frame(vc_tab)
        action_row.pack(fill=tk.X, padx=4, pady=(4, 4))
        self._vocab_chart_var = tk.StringVar(value="Stacked Tiers")
        ttk.Combobox(
            action_row, textvariable=self._vocab_chart_var,
            values=[
                "Stacked Tiers",
                "Flesch Reading Ease",
                "F-K Grade Level",
                "Age of Acquisition",
                "MTLD (Lexical Diversity)",
            ],
            state="readonly", width=22,
        ).pack(side=tk.LEFT)
        tk.Button(action_row, text="Show Chart",
                  command=self._show_vocab_chart, padx=6).pack(side=tk.LEFT, padx=(4, 0))
        self._btn_vocab_export = tk.Button(
            action_row, text="Export CSV...",
            command=self._vocab_export_csv, padx=6, state=tk.DISABLED,
        )
        self._btn_vocab_export.pack(side=tk.RIGHT)

        _IndexTooltip(self._vocab_tree, {
            "file":   "Caption file that was analyzed.",
            "status": "ok — analysis succeeded\n"
                      "skipped — file was empty or contained only stage directions\n"
                      "failed — an error occurred (check the console for details)",
            "flesch": "Flesch Reading Ease (0–100).\n"
                      "Higher = simpler language.\n"
                      "90–100: very easy (picture-book level)\n"
                      "60–70:  standard (average adult prose)\n"
                      "0–30:   very difficult (academic/legal text)\n\n"
                      "Based on sentence length and syllable count.\n"
                      "Treat as a relative index across shows, not a grade-level claim.",
            "fk":     "Flesch-Kincaid Grade Level.\n"
                      "Approximates the U.S. school grade needed to read the text comfortably.\n"
                      "Grade 1 ≈ first grade; Grade 12 ≈ senior year of high school.\n\n"
                      "Derived from sentence length and syllable count.\n"
                      "Validated on written prose — use as a relative index, not a literal grade.",
            "t1":     "Tier 1 — everyday words (Zipf frequency ≥ 4.5).\n"
                      "Words heard and used constantly: 'go', 'big', 'dog', 'want'.\n"
                      "Higher T1% = more familiar, high-frequency vocabulary.\n\n"
                      "Zipf scale: log₁₀(occurrences per billion words) + 3.\n"
                      "Only NOUN, VERB, ADJ, ADV tokens counted; proper nouns excluded.",
            "t2":     "Tier 2 — academic / cross-domain words (Zipf 3.0–4.5).\n"
                      "Words that appear across many subjects but aren't everyday: "
                      "'transform', 'examine', 'curious'.\n"
                      "High T2% often signals richer, more instructional dialogue.",
            "t3":     "Tier 3 — rare / domain-specific words (Zipf < 3.0).\n"
                      "Infrequent or technical vocabulary: 'metamorphosis', 'photosynthesis'.\n"
                      "High T3% can indicate specialized content or invented proper nouns\n"
                      "(proper nouns are excluded from counting, but very rare terms remain).",
            "aoa":    "Mean Age of Acquisition in years (Kuperman et al. norms).\n"
                      "Average age at which speakers first learn each content word.\n"
                      "Lower AoA = vocabulary learned earlier in childhood.\n\n"
                      "Only covers words present in the Kuperman norm list.\n"
                      "Blank if the norm file is not installed or coverage is zero.",
            "mtld":   "MTLD — Measure of Textual Lexical Diversity.\n"
                      "Higher MTLD = greater variety of unique words used.\n"
                      "Less sensitive to text length than raw type-token ratio.\n\n"
                      "Computed on lemmatized content tokens (NOUN, VERB, ADJ, ADV).\n"
                      "Blank if fewer than 50 content tokens were extracted.",
        })

    def _update_vocab_norm_label(self) -> None:
        norm_dir = Path(__file__).parent / "data" / "norms"
        aoa_ok  = (norm_dir / "kuperman_aoa.csv").exists()
        conc_ok = (norm_dir / "brysbaert_concreteness.csv").exists()
        self._vocab_norm_label_var.set(
            f"AoA norms: {'found' if aoa_ok else 'not found — AoA scores will be blank'}"
            f"   |   "
            f"Concreteness: {'found' if conc_ok else 'not found — scores will be blank'}"
        )

    def _refresh_speech_data(self) -> None:
        if not self._root_folder:
            self._lang_sp_note.config(text="Choose a root folder first.")
            return
        rows: list[dict] = []
        for show_dir in list_shows(self._root_folder):
            skey  = show_key(self._root_folder, show_dir)
            dname, _ = display_show_name(self._root_folder, show_dir)
            for ep in list_episodes(show_dir):
                c = load_cached(self._root_folder, skey, ep.stem)
                if not c:
                    continue
                try:
                    result = EpisodeResult.from_dict(c)
                    sp = result.metrics.speech
                    if not sp.available:
                        continue
                    air_date = ""
                    if self._db_conn:
                        meta = get_episode_metadata(self._db_conn, str(ep))
                        if meta:
                            air_date = meta.get("air_date") or ""
                    rows.append({
                        "show_name":   dname,
                        "file_name":   ep.name,
                        "file_path":   str(ep),
                        "air_date":    air_date,
                        "wpm":         sp.words_per_minute,
                        "density":     sp.speech_density,
                        "total_words": sp.total_words,
                        "source":      sp.source,
                    })
                except Exception:
                    continue
        self._lang_speech_rows = rows
        self._populate_lang_speech_tree()
        n = len(rows)
        note = f"{n} episode{'s' if n != 1 else ''} with speech data."
        if n == 0:
            note += "  Analyze episodes with CC files or enable Whisper in Settings."
        self._lang_sp_note.config(text=note)

    def _populate_lang_speech_tree(self) -> None:
        col = self._lang_speech_sort["col"]
        asc = self._lang_speech_sort["asc"]

        def _key(r):
            v = r.get(col, "")
            return v if isinstance(v, str) else (v or 0.0)

        sorted_rows = sorted(self._lang_speech_rows, key=_key, reverse=not asc)
        self._lang_sp_tree.delete(*self._lang_sp_tree.get_children())
        for r in sorted_rows:
            self._lang_sp_tree.insert("", tk.END,
                values=(
                    r["show_name"],
                    r["file_name"],
                    r.get("air_date") or "",
                    f"{r['wpm']:.1f}",
                    f"{r['density']:.1%}",
                    f"{r['total_words']:,}",
                    r["source"],
                ),
                tags=(r["file_path"],),
            )

    def _lang_sp_col_click(self, col: str) -> None:
        if self._lang_speech_sort["col"] == col:
            self._lang_speech_sort["asc"] = not self._lang_speech_sort["asc"]
        else:
            self._lang_speech_sort = {"col": col, "asc": True}
        self._populate_lang_speech_tree()

    def _chart_wpm_for_show(self) -> None:
        sel = self._lang_sp_tree.selection()
        if sel:
            show_filter = self._lang_sp_tree.item(sel[0], "values")[0]
        elif self._lang_speech_rows:
            from collections import Counter
            show_filter = Counter(
                r["show_name"] for r in self._lang_speech_rows
            ).most_common(1)[0][0]
        else:
            messagebox.showinfo("No Data",
                                "No speech data loaded — click Refresh first.",
                                parent=self)
            return

        rows = [r for r in self._lang_speech_rows if r["show_name"] == show_filter]
        if len(rows) < 2:
            messagebox.showinfo(
                "Not Enough Data",
                f"Need at least 2 episodes with speech data for \"{show_filter}\".",
                parent=self,
            )
            return

        rows = sorted(rows, key=lambda r: (r.get("air_date") or "", r["file_name"]))

        import matplotlib
        matplotlib.use("TkAgg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        win = tk.Toplevel(self)
        win.title(f"Speech Metrics — {show_filter}")
        win.geometry("700x420")

        fig, ax1 = plt.subplots(figsize=(8, 4.5), tight_layout=True)
        ax2 = ax1.twinx()

        labels   = [r.get("air_date") or r["file_name"] for r in rows]
        wpm_vals = [r["wpm"] for r in rows]
        den_vals = [r["density"] * 100 for r in rows]
        x = list(range(len(labels)))

        ax1.bar(x, wpm_vals, color="#3070b3", alpha=0.8, label="Words per Minute")
        ax2.plot(x, den_vals, "o-", color="#cc4400", linewidth=1.5,
                 markersize=4, label="Speech Density %")
        ax1.set_xticks(x)
        ax1.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
        ax1.set_ylabel("Words per Minute")
        ax2.set_ylabel("Speech Density (%)", color="#cc4400")
        ax2.tick_params(axis="y", labelcolor="#cc4400")
        ax1.set_title(f"Speech Metrics — {show_filter}")

        h1, l1 = ax1.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        ax1.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8)

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        win.protocol("WM_DELETE_WINDOW", lambda: (plt.close(fig), win.destroy()))

    def _vocab_browse_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select caption files",
            filetypes=[("Caption files", "*.srt *.vtt"), ("All files", "*.*")],
        )
        existing = set(self._vocab_file_lb.get(0, tk.END))
        for p in paths:
            if p not in existing:
                self._vocab_file_lb.insert(tk.END, p)
                existing.add(p)

    def _vocab_browse_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select folder containing CC files")
        if not folder:
            return
        folder_path = Path(folder)
        existing = set(self._vocab_file_lb.get(0, tk.END))
        cc_files = sorted(
            list(folder_path.rglob("*.srt")) + list(folder_path.rglob("*.vtt"))
        )
        added = 0
        for p in cc_files:
            s = str(p)
            if s not in existing:
                self._vocab_file_lb.insert(tk.END, s)
                existing.add(s)
                added += 1
        self._vocab_progress_var.set(f"Added {added} file(s) from folder.")

    def _vocab_remove_selected(self) -> None:
        for i in reversed(self._vocab_file_lb.curselection()):
            self._vocab_file_lb.delete(i)

    def _run_vocab_analysis(self) -> None:
        if self._vocab_analysis_running:
            return
        files = list(self._vocab_file_lb.get(0, tk.END))
        if not files:
            messagebox.showinfo("No Files", "Add CC files to analyze first.", parent=self)
            return

        try:
            import spacy
            spacy.load("en_core_web_sm")
        except Exception:
            messagebox.showerror(
                "spaCy Not Ready",
                "spaCy or the en_core_web_sm model is not installed.\n\n"
                "Run these commands in a terminal:\n"
                "  pip install spacy\n"
                "  python -m spacy download en_core_web_sm",
                parent=self,
            )
            return

        try:
            from analyzer.vocab_complexity import analyze_caption_file, load_norms, NormTables
        except ImportError as exc:
            messagebox.showerror("Import Error",
                                 f"Could not import vocab_complexity: {exc}", parent=self)
            return

        norm_dir = Path(__file__).parent / "data" / "norms"
        try:
            norms = load_norms(norm_dir)
        except Exception:
            norms = NormTables(
                aoa={}, concreteness={},
                aoa_path="(not found)", conc_path="(not found)",
                aoa_n=0, conc_n=0,
            )

        self._vocab_analysis_running = True
        self._btn_vocab_analyze.config(state=tk.DISABLED)
        self._vocab_progress_var.set(f"Analyzing 0 / {len(files)}…")
        self._vocab_tree.delete(*self._vocab_tree.get_children())
        self._btn_vocab_export.config(state=tk.DISABLED)

        _q     = self._queue
        _files = list(files)

        def _worker():
            _results: list = []
            for i, fpath in enumerate(_files, 1):
                _q.put({"t": "vocab_progress", "n": i, "total": len(_files)})
                try:
                    r = analyze_caption_file(Path(fpath), norms=norms)
                except Exception as exc:
                    from analyzer.vocab_complexity import VocabResult
                    r = VocabResult(
                        episode_id=Path(fpath).stem,
                        cc_path=fpath,
                        status="failed",
                        error=str(exc),
                    )
                _results.append(r)
            _q.put({"t": "vocab_done", "results": _results})

        threading.Thread(target=_worker, daemon=True).start()

    def _vocab_export_csv(self) -> None:
        rows = [r.to_flat_row() for r in self._vocab_results if r.status == "ok"]
        if not rows:
            messagebox.showinfo("Nothing to Export",
                                "No successful analyses to export.", parent=self)
            return
        path = filedialog.asksaveasfilename(
            title="Save vocabulary complexity CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="vocab_complexity.csv",
        )
        if not path:
            return
        import csv
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        self._status_var.set(f"Exported {len(rows)} row(s) to {Path(path).name}")

    def _show_vocab_chart(self) -> None:
        ok_results = [r for r in self._vocab_results if r.status == "ok"]
        if not ok_results:
            messagebox.showinfo("No Data",
                                "Analyze some CC files first.", parent=self)
            return

        chart_type = self._vocab_chart_var.get()
        raw_labels = [Path(r.cc_path).stem for r in ok_results]
        rows       = [r.to_flat_row() for r in ok_results]
        x          = list(range(len(raw_labels)))

        # Strip common prefix (usually the show name) so labels are just episode IDs
        def _strip_common_prefix(strs: list[str]) -> list[str]:
            if len(strs) < 2:
                return strs
            words = [s.split() for s in strs]
            n = min(len(w) for w in words)
            cut = 0
            for i in range(n):
                if len({w[i] for w in words}) == 1:
                    cut = i + 1
                else:
                    break
            return [" ".join(w[cut:]) if cut else s for w, s in zip(words, strs)]

        labels = _strip_common_prefix(raw_labels)
        # Truncate anything still too long
        MAX_LABEL = 38
        labels = [l if len(l) <= MAX_LABEL else l[:MAX_LABEL - 1] + "…" for l in labels]

        import matplotlib
        matplotlib.use("TkAgg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

        n_eps    = len(labels)
        fig_w    = max(9, min(n_eps * 0.35, 28))   # 0.35 in per bar, capped at 28 in
        fig_h    = 5.5

        win = tk.Toplevel(self)
        win.title(f"Vocabulary — {chart_type}")
        win.geometry("900x520")

        # Scrollable canvas so wide charts don't get clipped
        outer = tk.Frame(win)
        outer.pack(fill=tk.BOTH, expand=True)
        h_scroll = tk.Scrollbar(outer, orient=tk.HORIZONTAL)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        tk_canvas = tk.Canvas(outer, xscrollcommand=h_scroll.set)
        tk_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        h_scroll.config(command=tk_canvas.xview)

        fig, ax = plt.subplots(figsize=(fig_w, fig_h), tight_layout=True)

        if chart_type == "Stacked Tiers":
            t1 = [r.get("vocab_tier1_proportion") or 0.0 for r in rows]
            t2 = [r.get("vocab_tier2_proportion") or 0.0 for r in rows]
            t3 = [r.get("vocab_tier3_proportion") or 0.0 for r in rows]
            b2 = t1
            b3 = [a + b for a, b in zip(t1, t2)]
            ax.bar(x, t1, label="Tier 1 — everyday",  color="#4a90d9")
            ax.bar(x, t2, bottom=b2, label="Tier 2 — academic", color="#f5a623")
            ax.bar(x, t3, bottom=b3, label="Tier 3 — rare",     color="#d0021b")
            ax.set_ylabel("Proportion of content words")
            ax.set_ylim(0, 1.08)
            ax.yaxis.set_major_formatter(
                plt.FuncFormatter(lambda v, _: f"{v:.0%}")
            )
            ax.legend(loc="upper right", fontsize=8)

        elif chart_type == "Flesch Reading Ease":
            vals = [r.get("read_flesch_reading_ease") for r in rows]
            bars = ax.bar(x, [v if v is not None else 0.0 for v in vals],
                          color="#5b9bd5")
            for bar, v in zip(bars, vals):
                if v is None:
                    bar.set_color("#cccccc")
            ax.axhline(90, color="#27ae60", linestyle="--", linewidth=0.9,
                       label="90 — very easy")
            ax.axhline(60, color="#f39c12", linestyle="--", linewidth=0.9,
                       label="60 — standard")
            ax.axhline(30, color="#c0392b", linestyle="--", linewidth=0.9,
                       label="30 — difficult")
            ax.set_ylabel("Flesch Reading Ease")
            ax.set_ylim(0, 115)
            ax.legend(loc="upper right", fontsize=8)

        elif chart_type == "F-K Grade Level":
            vals = [r.get("read_flesch_kincaid_grade") for r in rows]
            bars = ax.bar(x, [v if v is not None else 0.0 for v in vals],
                          color="#8e6bbf")
            for bar, v in zip(bars, vals):
                if v is None:
                    bar.set_color("#cccccc")
            for grade, lbl in [(2, "Grade 2"), (5, "Grade 5"), (8, "Grade 8")]:
                ax.axhline(grade, color="#888888", linestyle=":",
                           linewidth=0.9, label=lbl)
            ax.set_ylabel("Flesch-Kincaid Grade Level")
            ax.legend(loc="upper right", fontsize=8)

        elif chart_type == "Age of Acquisition":
            vals = [r.get("vocab_aoa_mean") for r in rows]
            bars = ax.bar(x, [v if v is not None else 0.0 for v in vals],
                          color="#e67e22")
            for bar, v in zip(bars, vals):
                if v is None:
                    bar.set_color("#cccccc")
            ax.axhline(6.0, color="#2980b9", linestyle="--", linewidth=0.9,
                       label="6 yrs — early childhood boundary")
            ax.set_ylabel("Mean Age of Acquisition (years)")
            ax.legend(loc="upper right", fontsize=8)

        elif chart_type == "MTLD (Lexical Diversity)":
            vals = [r.get("div_mtld") for r in rows]
            bars = ax.bar(x, [v if v is not None else 0.0 for v in vals],
                          color="#27ae60")
            for bar, v in zip(bars, vals):
                if v is None:
                    bar.set_color("#cccccc")
            ax.set_ylabel("MTLD")

        ax.set_xticks(x)
        rot = 45 if n_eps <= 20 else 60
        ax.set_xticklabels(labels, rotation=rot, ha="right", fontsize=7)
        ax.set_title(chart_type)

        mpl_canvas = FigureCanvasTkAgg(fig, master=tk_canvas)
        mpl_canvas.draw()
        widget = mpl_canvas.get_tk_widget()
        # Embed matplotlib widget inside the scrollable tk.Canvas
        widget_id = tk_canvas.create_window(0, 0, anchor="nw", window=widget)

        def _on_configure(event):
            # Update scroll region to match the matplotlib widget's actual size
            tk_canvas.configure(scrollregion=tk_canvas.bbox("all"))
        widget.bind("<Configure>", _on_configure)

        NavigationToolbar2Tk(mpl_canvas, win)
        win.protocol("WM_DELETE_WINDOW", lambda: (plt.close(fig), win.destroy()))

    # -----------------------------------------------------------------------
    # About
    # -----------------------------------------------------------------------

    def _show_about(self) -> None:
        win = tk.Toplevel(self)
        win.title("About Metrics")
        win.geometry("580x640")
        win.resizable(True, True)
        txt = tk.Text(win, wrap=tk.WORD, font=("TkDefaultFont", 9),
                      padx=12, pady=10, relief=tk.FLAT, bg=win.cget("bg"))
        vsb = ttk.Scrollbar(win, orient=tk.VERTICAL, command=txt.yview)
        txt.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        txt.pack(fill=tk.BOTH, expand=True)

        txt.tag_configure("h1",  font=("TkDefaultFont", 10, "bold"))
        txt.tag_configure("h2",  font=("TkDefaultFont", 9,  "bold"))
        txt.tag_configure("tip", foreground="#003080")

        def h1(s):  txt.insert(tk.END, s + "\n", "h1")
        def h2(s):  txt.insert(tk.END, s + "\n", "h2")
        def tip(s): txt.insert(tk.END, s + "\n", "tip")
        def p(s):   txt.insert(tk.END, s + "\n")
        def br():   txt.insert(tk.END, "\n")

        h1("About these metrics")
        p("This tool measures formal/structural features of video — not content.")
        br()

        h2("SHOT LENGTH & SCENE PACING")
        p("  Faster cutting triggers more frequent orienting responses and higher\n"
          "  processing load (Lillard & Peterson, 2011; Lang LC4MP model).")
        br()

        h2("MOTION")
        p("  High on-screen motion is a pre-attentive attention magnet and\n"
          "  a repeated arousal trigger (Itti & Koch, visual saliency).")
        br()

        h2("COLOR SATURATION & CONTRAST")
        p("  High saturation draws attention bottom-up and is associated with arousal.\n"
          "  Contrast captures the brightness spread within frames — it is high for\n"
          "  content with stark dark/light regions (presentation slides, whiteboards,\n"
          "  whiteboard-style animation). Unlike saturation, contrast can be elevated\n"
          "  in live-action and lecture footage even when the content is calm.")
        br()

        h2("FLASHING")
        p("  Rapid luminance changes are a photosensitivity concern and\n"
          "  an overstimulation marker.")
        br()

        h2("SENSORY LOAD COMPOSITE")
        p("  Weighted combination of normalized sub-metrics using fixed reference\n"
          "  ranges — comparable across shows and runs. Each metric is divided by\n"
          "  the preset's reference-range ceiling before weighting, so the ceiling\n"
          "  choice matters (see Presets below).")
        br()

        h2("PRESETS & CROSS-GENRE COMPARISON")
        tip("  Scores are only directly comparable when content was analyzed\n"
            "  under the same preset with the same reference ranges.")
        p("\n"
          "  Each preset sets a ceiling for each metric. The General / All Ages\n"
          "  preset uses wide ceilings calibrated for all content types — for example,\n"
          "  60 cuts/min. Against that ceiling, even a fast children's cartoon at\n"
          "  11 cuts/min looks like only 18% of the scale. A children's-only preset\n"
          "  (Preschool: 15 cuts/min max) would score that same 11 cuts/min at 74%,\n"
          "  making pacing differences between shows far more visible.\n\n"
          "  Cross-genre comparison can also produce counterintuitive rankings.\n"
          "  A lecture video with high-contrast slides (bright text, dark background)\n"
          "  and louder speech audio may score above an animated children's show\n"
          "  under the General preset — because contrast and audio are absolute\n"
          "  measurements that do not adjust for genre. This is mathematically correct\n"
          "  but may not match your intuition about which content is more stimulating\n"
          "  for a child.")
        br()
        tip("  Best practice: use Preschool or Early Childhood presets when your\n"
            "  library contains only children's content. Use General only when you\n"
            "  intentionally want to compare across all content types on a single scale.")
        br()

        h2("IMPORTANT LIMITATIONS")
        p("  This tool measures the stimulus, not the viewer. It cannot account\n"
          "  for the child's age, temperament, or sensory-processing profile.\n"
          "  The evidence base is largely correlational. Output is a transparent\n"
          "  profile to inform caregiver judgment — not a rating or verdict.")

        txt.config(state=tk.DISABLED)
        tk.Button(win, text="Close", command=win.destroy,
                  padx=20).pack(pady=8)


class _IndexTooltip:
    """Shows a small popup when the cursor hovers over a Treeview column header."""

    def __init__(self, tree: ttk.Treeview, tips: dict[str, str]) -> None:
        self._tree = tree
        self._tips = tips          # column id -> description text
        self._win: tk.Toplevel | None = None
        self._current_col: str = ""
        tree.bind("<Motion>", self._on_motion)
        tree.bind("<Leave>",  self._hide)

    def _on_motion(self, event: tk.Event) -> None:
        if self._tree.identify_region(event.x, event.y) != "heading":
            self._hide()
            return
        col_tag = self._tree.identify_column(event.x)   # e.g. "#2"
        try:
            col_id = self._tree["columns"][int(col_tag.lstrip("#")) - 1]
        except (ValueError, IndexError):
            self._hide()
            return
        text = self._tips.get(col_id)
        if not text:
            self._hide()
            return
        if col_id == self._current_col:
            return   # already showing for this column
        self._hide()
        self._current_col = col_id
        x = self._tree.winfo_rootx() + event.x + 14
        y = self._tree.winfo_rooty() + event.y + 18
        self._win = tw = tk.Toplevel(self._tree)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(
            tw, text=text, justify=tk.LEFT,
            background="#ffffcc", relief=tk.SOLID, borderwidth=1,
            font=("TkDefaultFont", 8), wraplength=240, padx=5, pady=4,
        ).pack()

    def _hide(self, _event=None) -> None:
        self._current_col = ""
        if self._win:
            self._win.destroy()
            self._win = None


class _CellTooltip:
    """Shows full cell content as a tooltip when hovering over a specific Treeview column."""

    def __init__(self, tree: ttk.Treeview, col_id: str) -> None:
        self._tree = tree
        self._col_id = col_id
        self._col_idx: int = -1
        self._win: tk.Toplevel | None = None
        self._current_item: str = ""
        tree.bind("<Motion>", self._on_motion, add=True)
        tree.bind("<Leave>",  self._hide,      add=True)

    def _get_col_idx(self) -> int:
        if self._col_idx < 0:
            try:
                self._col_idx = list(self._tree["columns"]).index(self._col_id)
            except ValueError:
                pass
        return self._col_idx

    def _on_motion(self, event: tk.Event) -> None:
        if self._tree.identify_region(event.x, event.y) != "cell":
            self._hide()
            return
        col_tag = self._tree.identify_column(event.x)
        try:
            col_id = self._tree["columns"][int(col_tag.lstrip("#")) - 1]
        except (ValueError, IndexError):
            self._hide()
            return
        if col_id != self._col_id:
            self._hide()
            return
        item = self._tree.identify_row(event.y)
        if not item or item == self._current_item:
            return
        self._hide()
        idx = self._get_col_idx()
        if idx < 0:
            return
        try:
            text = str(self._tree.item(item, "values")[idx])
        except IndexError:
            return
        if not text:
            return
        self._current_item = item
        x = self._tree.winfo_rootx() + event.x + 14
        y = self._tree.winfo_rooty() + event.y + 18
        self._win = tw = tk.Toplevel(self._tree)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(
            tw, text=text, justify=tk.LEFT,
            background="#ffffcc", relief=tk.SOLID, borderwidth=1,
            font=("TkDefaultFont", 9), wraplength=340, padx=6, pady=4,
        ).pack()

    def _hide(self, _event=None) -> None:
        self._current_item = ""
        if self._win:
            self._win.destroy()
            self._win = None


class _WidgetTooltip:
    """Simple hover tooltip for any widget.

    Uses both <Enter> and <Motion>/<Leave> polling so it works on
    ttk.Combobox on Windows, where mouse events route to the native
    control subwindow rather than the Python widget frame.
    """

    def __init__(self, widget: tk.Widget, text: str, wraplength: int = 300) -> None:
        self._widget = widget
        self._text = text
        self._wraplength = wraplength
        self._win: tk.Toplevel | None = None
        self._timer: str | None = None
        widget.bind("<Enter>", self._on_enter)
        widget.bind("<Motion>", self._on_enter)
        widget.bind("<Leave>", self._on_leave)
        # Also bind to internal children (ttk compound widgets on Windows)
        widget.after_idle(self._bind_children)

    def _bind_children(self) -> None:
        for child in self._widget.winfo_children():
            child.bind("<Enter>", self._on_enter)
            child.bind("<Motion>", self._on_enter)
            child.bind("<Leave>", self._on_leave)

    def _on_enter(self, _event=None) -> None:
        if self._win:
            return
        if self._timer:
            self._widget.after_cancel(self._timer)
        self._timer = self._widget.after(600, self._show)

    def _on_leave(self, _event=None) -> None:
        if self._timer:
            self._widget.after_cancel(self._timer)
            self._timer = None
        self._hide()

    def _show(self) -> None:
        self._timer = None
        if self._win:
            return
        x = self._widget.winfo_rootx() + 20
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._win = tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.attributes("-topmost", True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(
            tw, text=self._text, justify=tk.LEFT,
            background="#ffffcc", relief=tk.SOLID, borderwidth=1,
            font=("TkDefaultFont", 8), wraplength=self._wraplength, padx=6, pady=4,
        ).pack()

    def _hide(self, _event=None) -> None:
        if self._win:
            self._win.destroy()
            self._win = None


class SettingsDialog(tk.Toplevel):
    """Modal dialog for editing age presets, weights, and normalization ceilings."""

    _WEIGHT_KEYS   = ["pacing", "saturation", "color_contrast", "motion", "flashing", "audio"]
    _WEIGHT_LABELS = ["Pacing", "Saturation", "Contrast", "Motion", "Flashing", "Audio"]
    _RANGE_KEYS    = [
        "cuts_per_min", "color_saturation_mean", "color_contrast_mean",
        "motion_mean", "flashing_events_per_min", "audio_rms_mean",
    ]
    _RANGE_LABELS  = [
        "Cuts/min max", "Saturation max", "Contrast max",
        "Motion max", "Flashing events/min max", "Audio RMS max",
    ]
    _CAVEAT = (
        "Note on tight presets (e.g. Toddler): Low ceilings mean many shows will "
        "exceed the maximum on one or more metrics, compressing score differences at "
        "the top. This is intentional — the preset flags both as over-threshold for "
        "this age rather than ranking between them. For fine-grained comparison, use "
        "a broader preset such as General / All Ages."
    )

    def __init__(self, parent: App) -> None:
        super().__init__(parent)
        self._app = parent
        self.title("Settings — Presets & Weights")
        self.resizable(False, False)
        self.grab_set()
        self.transient(parent)

        self._presets: dict = parent._cfg.get("presets", {})
        self._building = False

        self._preset_var  = tk.StringVar(value=self._detect_active_preset())
        self._weight_vars = {k: tk.StringVar() for k in self._WEIGHT_KEYS}
        self._range_vars  = {k: tk.StringVar() for k in self._RANGE_KEYS}
        self._total_var   = tk.StringVar()
        self._desc_var    = tk.StringVar()
        self._speech_enabled_var = tk.BooleanVar(
            value=parent._cfg.get("speech_transcription_enabled", False))
        self._speech_model_var   = tk.StringVar(
            value=parent._cfg.get("speech_whisper_model", "small"))

        self._build()
        self._fill_from_cfg(parent._cfg)
        self._refresh_preset_desc()
        self._update_total()

        self.geometry("480x660")
        self.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        w, h   = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + (pw - w)//2}+{py + (ph - h)//2}")

    # ---- build UI ----

    def _build(self) -> None:
        pad = {"padx": 10, "pady": 4}

        # Preset row
        top = tk.Frame(self)
        top.pack(fill=tk.X, **pad)
        tk.Label(top, text="Preset:", width=10, anchor="w").pack(side=tk.LEFT)
        self._preset_cb = ttk.Combobox(
            top, textvariable=self._preset_var,
            values=self._preset_list(), state="readonly", width=26,
        )
        self._preset_cb.pack(side=tk.LEFT)
        self._preset_cb.bind("<<ComboboxSelected>>", self._on_preset_selected)

        self._btn_delete = tk.Button(top, text="Delete", command=self._delete_preset,
                                      padx=4)
        self._btn_delete.pack(side=tk.LEFT, padx=(6, 0))

        tk.Label(self, textvariable=self._desc_var, wraplength=440,
                 fg="#555555", font=("TkDefaultFont", 8),
                 justify="left", anchor="w").pack(fill=tk.X, padx=10, pady=(0, 2))

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=6, pady=2)

        # Two-column layout: weights | ceilings
        columns = tk.Frame(self)
        columns.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        wf = tk.LabelFrame(columns, text="Sensory Load Weights", padx=8, pady=6)
        wf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        for label, key in zip(self._WEIGHT_LABELS, self._WEIGHT_KEYS):
            row = tk.Frame(wf)
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=label, width=11, anchor="w").pack(side=tk.LEFT)
            tk.Entry(row, textvariable=self._weight_vars[key], width=6).pack(side=tk.LEFT)
            tk.Label(row, text="%").pack(side=tk.LEFT)
            self._weight_vars[key].trace_add("write", self._on_field_changed)
        self._total_lbl = tk.Label(wf, textvariable=self._total_var,
                                    font=("TkDefaultFont", 8))
        self._total_lbl.pack(anchor="e", pady=(6, 0))

        rf = tk.LabelFrame(columns, text="Normalization Ceilings (max)", padx=8, pady=6)
        rf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        for label, key in zip(self._RANGE_LABELS, self._RANGE_KEYS):
            row = tk.Frame(rf)
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=label, width=18, anchor="w",
                     font=("TkDefaultFont", 8)).pack(side=tk.LEFT)
            tk.Entry(row, textvariable=self._range_vars[key], width=7).pack(side=tk.LEFT)
            self._range_vars[key].trace_add("write", self._on_field_changed)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=6, pady=4)

        # Caveat note
        tk.Label(self, text=self._CAVEAT, wraplength=450, justify="left",
                 fg="#7a5c00", bg="#fffbe6",
                 font=("TkDefaultFont", 8), relief=tk.FLAT,
                 padx=6, pady=4).pack(fill=tk.X, padx=10, pady=(0, 4))

        # Speech Analysis section
        sf = tk.LabelFrame(self, text="Speech Analysis", padx=8, pady=6)
        sf.pack(fill=tk.X, padx=10, pady=(0, 4))

        try:
            import faster_whisper as _fw  # noqa: F401
            _fw_installed = True
        except ImportError:
            _fw_installed = False

        chk_row = tk.Frame(sf)
        chk_row.pack(fill=tk.X)
        tk.Checkbutton(
            chk_row,
            text="Enable auto-transcription with Whisper AI  (slow — ~2–5 min/episode on CPU)",
            variable=self._speech_enabled_var,
            font=("TkDefaultFont", 9),
        ).pack(side=tk.LEFT)

        if not _fw_installed:
            tk.Label(
                sf,
                text="⚠  faster-whisper is not installed. Open a terminal and run:\n"
                     "    pip install faster-whisper",
                fg="#cc0000", font=("TkDefaultFont", 9),
                anchor="w", justify="left",
            ).pack(fill=tk.X, pady=(2, 0))

        model_row = tk.Frame(sf)
        model_row.pack(fill=tk.X, pady=(4, 0))
        tk.Label(model_row, text="Model size:", width=11, anchor="w").pack(side=tk.LEFT)
        ttk.Combobox(
            model_row, textvariable=self._speech_model_var,
            values=["tiny", "base", "small", "medium", "large"],
            state="readonly", width=8,
        ).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(
            model_row,
            text="tiny = fastest · small = balanced · large = most accurate",
            fg="#555555", font=("TkDefaultFont", 8),
        ).pack(side=tk.LEFT)

        tk.Label(
            sf,
            text="CC files (.srt / .vtt) alongside the video are always used first and are instant — "
                 "Whisper only runs when no CC file is found. "
                 "For words-per-minute and speech density, tiny or base is usually sufficient: "
                 "occasional word errors (e.g. hearing 'ship' as 'shift') have almost no effect on the word count. "
                 "Larger models only help if you need readable transcription text.\n\n"
                 "Note: episodes already in the cache must be re-analyzed after enabling this setting — "
                 "select the episode and click Analyze Episode again.",
            fg="#555555", font=("TkDefaultFont", 8),
            wraplength=440, anchor="w", justify="left",
        ).pack(fill=tk.X, pady=(4, 0))

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=6, pady=2)

        # Buttons
        bf = tk.Frame(self)
        bf.pack(pady=(4, 10))
        tk.Button(bf, text="Apply & Re-score", command=self._apply,
                  padx=8).pack(side=tk.LEFT, padx=4)
        tk.Button(bf, text="Save as Preset...", command=self._save_as_preset,
                  padx=8).pack(side=tk.LEFT, padx=4)
        tk.Button(bf, text="Save as Default", command=self._save_default,
                  padx=8).pack(side=tk.LEFT, padx=4)
        tk.Button(bf, text="Close", command=self.destroy,
                  padx=8).pack(side=tk.LEFT, padx=4)

    # ---- preset helpers ----

    def _preset_list(self) -> list[str]:
        return list(self._presets.keys()) + ["Custom"]

    def _detect_active_preset(self) -> str:
        cfg = self._app._cfg
        for name, p in self._presets.items():
            if (p.get("sensory_load_weights") == cfg.get("sensory_load_weights")
                    and p.get("normalization_reference_ranges")
                        == cfg.get("normalization_reference_ranges")):
                return name
        return "Custom"

    def _refresh_preset_desc(self) -> None:
        name = self._preset_var.get()
        p = self._presets.get(name)
        self._desc_var.set(p.get("description", "") if p else "")
        is_builtin = p.get("builtin", False) if p else True
        self._btn_delete.config(
            state=tk.DISABLED if (name == "Custom" or is_builtin) else tk.NORMAL
        )

    def _on_preset_selected(self, _event=None) -> None:
        name = self._preset_var.get()
        if name != "Custom" and name in self._presets:
            self._building = True
            self._fill_from_cfg(self._presets[name])
            self._building = False
            self._update_total()
        self._refresh_preset_desc()

    def _on_field_changed(self, *_) -> None:
        if self._building:
            return
        self._preset_var.set("Custom")
        self._refresh_preset_desc()
        self._update_total()

    def _reload_presets(self) -> None:
        """Re-read config from disk and refresh the combobox."""
        self._app._cfg = load_config()
        self._presets = self._app._cfg.get("presets", {})
        self._preset_cb.config(values=self._preset_list())

    # ---- fill / read ----

    def _fill_from_cfg(self, cfg: dict) -> None:
        self._building = True
        weights = cfg.get("sensory_load_weights", {})
        for key in self._WEIGHT_KEYS:
            self._weight_vars[key].set(f"{weights.get(key, 0.0) * 100:.1f}")
        ranges = cfg.get("normalization_reference_ranges", {})
        for key in self._RANGE_KEYS:
            self._range_vars[key].set(str(ranges.get(key, {}).get("max", 1.0)))
        self._building = False

    def _read_fields(self) -> tuple[dict | None, dict | None]:
        try:
            weights = {k: float(self._weight_vars[k].get()) / 100.0
                       for k in self._WEIGHT_KEYS}
        except ValueError:
            messagebox.showerror("Invalid input", "All weight fields must be numbers.",
                                 parent=self)
            return None, None
        total = sum(weights.values())
        if abs(total - 1.0) > 0.005:
            messagebox.showerror(
                "Weights don't sum to 100%",
                f"Current total: {total * 100:.1f}%\nAdjust so they sum to 100%.",
                parent=self)
            return None, None
        try:
            ranges = {k: {"min": 0.0, "max": float(self._range_vars[k].get())}
                      for k in self._RANGE_KEYS}
        except ValueError:
            messagebox.showerror("Invalid input", "All ceiling fields must be numbers.",
                                 parent=self)
            return None, None
        for k, r in ranges.items():
            if r["max"] <= 0:
                messagebox.showerror("Invalid input",
                                     f"Ceiling for '{k}' must be > 0.", parent=self)
                return None, None

        return weights, ranges

    def _update_total(self) -> None:
        try:
            total = sum(float(self._weight_vars[k].get()) for k in self._WEIGHT_KEYS)
            ok = abs(total - 100.0) < 0.6
            self._total_var.set(f"Total: {total:.1f}%" + (" ✓" if ok else "  ← must be 100%"))
            self._total_lbl.config(fg="green" if ok else "red")
        except ValueError:
            self._total_var.set("Total: —")
            self._total_lbl.config(fg="red")

    # --- actions ---

    def _build_new_cfg(self) -> dict | None:
        weights, ranges = self._read_fields()
        if weights is None:
            return None
        new_cfg = copy.deepcopy(self._app._cfg)
        new_cfg["sensory_load_weights"] = weights
        new_cfg["normalization_reference_ranges"] = ranges
        new_cfg["speech_transcription_enabled"] = self._speech_enabled_var.get()
        new_cfg["speech_whisper_model"] = self._speech_model_var.get()
        return new_cfg

    def _apply(self) -> None:
        new_cfg = self._build_new_cfg()
        if new_cfg is None:
            return
        self._app._cfg = new_cfg

        # Count every cached episode across all shows so the user sees a total
        rescored = 0
        root = self._app._root_folder
        if root:
            for show_dir in list_shows(root):
                skey = show_key(root, show_dir)
                for ep in list_episodes(show_dir):
                    if load_cached(root, skey, ep.stem):
                        rescored += 1

        self._app._refresh_current_view()
        preset = self._preset_var.get()
        label = f"Preset: {preset}" if preset != "Custom" else "Custom weights"
        ep_word = "episode" if rescored == 1 else "episodes"
        self._app._status_var.set(
            f"Settings applied — {label}. "
            f"{rescored} cached {ep_word} will now display updated scores."
        )

    def _save_as_preset(self) -> None:
        from tkinter import simpledialog
        new_cfg = self._build_new_cfg()
        if new_cfg is None:
            return
        name = simpledialog.askstring(
            "Save Preset", "Enter a name for this preset:", parent=self,
        )
        if not name or not name.strip():
            return
        name = name.strip()
        if self._presets.get(name, {}).get("builtin"):
            messagebox.showerror("Cannot overwrite",
                                 f"'{name}' is a built-in preset and cannot be overwritten.",
                                 parent=self)
            return
        config_path = _base_dir() / "config.json"
        try:
            existing = json.loads(config_path.read_text(encoding="utf-8"))
            existing["presets"][name] = {
                "description": "Custom preset",
                "sensory_load_weights": new_cfg["sensory_load_weights"],
                "normalization_reference_ranges": new_cfg["normalization_reference_ranges"],
            }
            config_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
            self._reload_presets()
            self._preset_var.set(name)
            self._refresh_preset_desc()
            self._app._status_var.set(f"Preset '{name}' saved.")
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc), parent=self)

    def _delete_preset(self) -> None:
        name = self._preset_var.get()
        if name == "Custom" or self._presets.get(name, {}).get("builtin"):
            return
        if not messagebox.askyesno("Delete preset",
                                    f"Delete preset '{name}'?", parent=self):
            return
        config_path = _base_dir() / "config.json"
        try:
            existing = json.loads(config_path.read_text(encoding="utf-8"))
            existing["presets"].pop(name, None)
            config_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
            self._reload_presets()
            self._preset_var.set("Custom")
            self._refresh_preset_desc()
            self._app._status_var.set(f"Preset '{name}' deleted.")
        except Exception as exc:
            messagebox.showerror("Delete failed", str(exc), parent=self)

    def _save_default(self) -> None:
        new_cfg = self._build_new_cfg()
        if new_cfg is None:
            return
        config_path = _base_dir() / "config.json"
        try:
            existing = json.loads(config_path.read_text(encoding="utf-8"))
            existing["sensory_load_weights"] = new_cfg["sensory_load_weights"]
            existing["normalization_reference_ranges"] = new_cfg["normalization_reference_ranges"]
            existing["speech_transcription_enabled"] = new_cfg["speech_transcription_enabled"]
            existing["speech_whisper_model"] = new_cfg["speech_whisper_model"]
            config_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
            messagebox.showinfo("Saved", f"Default settings saved to:\n{config_path}",
                                parent=self)
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc), parent=self)


class CompareWindow(tk.Toplevel):
    """Side-by-side metric comparison for two episodes or two shows."""

    def __init__(self, parent: "App",
                 item_a: "EpisodeResult | ShowAggregate",
                 item_b: "EpisodeResult | ShowAggregate") -> None:
        super().__init__(parent)
        self.resizable(True, True)
        is_ep = isinstance(item_a, EpisodeResult)
        name_a = item_a.file if is_ep else item_a.show_name
        name_b = item_b.file if is_ep else item_b.show_name
        self.title(f"Compare — {name_a[:40]}  vs  {name_b[:40]}")
        self.geometry("700x560")
        self._build(item_a, item_b, is_ep, name_a, name_b)

    def _build(self, a, b, is_ep: bool, name_a: str, name_b: str) -> None:
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(8, 0))

        tree = ttk.Treeview(tree_frame, columns=("metric", "a", "b"),
                             show="headings", selectmode="none")
        tree.heading("metric", text="Metric")
        tree.heading("a", text=name_a[:38])
        tree.heading("b", text=name_b[:38])
        tree.column("metric", width=210, minwidth=140, anchor="w")
        tree.column("a",      width=220, minwidth=100, anchor="center")
        tree.column("b",      width=220, minwidth=100, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True)

        tree.tag_configure("section",  font=("TkDefaultFont", 9, "bold"),
                           background="#e8e8e8")
        tree.tag_configure("a_better", foreground="#003080")
        tree.tag_configure("b_better", foreground="#006600")

        def row(label: str, va, vb,
                lower_better: bool = True, fmt: str = ".3f",
                section: bool = False) -> None:
            if section:
                tree.insert("", tk.END, values=(label, "", ""), tags=("section",))
                return
            if not isinstance(va, (int, float)) or not isinstance(vb, (int, float)):
                tree.insert("", tk.END, values=(
                    label,
                    str(va) if va is not None else "n/a",
                    str(vb) if vb is not None else "n/a",
                ))
                return
            sa, sb = format(va, fmt), format(vb, fmt)
            tag = None
            diff = va - vb
            tol = max(abs(va), abs(vb)) * 0.002 + 1e-9   # 0.2% relative tolerance
            if lower_better:
                if diff < -tol:
                    sa, tag = sa + "  ◀", "a_better"
                elif diff > tol:
                    sb, tag = sb + "  ◀", "b_better"
            else:
                if diff > tol:
                    sa, tag = sa + "  ◀", "a_better"
                elif diff < -tol:
                    sb, tag = sb + "  ◀", "b_better"
            tree.insert("", tk.END, values=(label, sa, sb),
                        tags=(tag,) if tag else ())

        if is_ep:
            self._fill_episode(row, a, b)
        else:
            self._fill_show(row, a, b)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=6, pady=(6, 2))
        tk.Label(self, text="◀  =  calmer / less stimulating on this metric",
                 font=("TkDefaultFont", 8), fg="#555555").pack()
        tk.Button(self, text="Close", command=self.destroy,
                  padx=20).pack(pady=(4, 10))

    @staticmethod
    def _fill_episode(row, a: EpisodeResult, b: EpisodeResult) -> None:
        ma, mb = a.metrics, b.metrics
        row("Duration (min)", a.duration_sec / 60, b.duration_sec / 60,
            lower_better=False, fmt=".1f")

        row("Sensory Load", section=True, va=None, vb=None)
        row("Composite score", ma.sensory_load.score, mb.sensory_load.score)
        ca, cb = ma.sensory_load.components, mb.sensory_load.components
        row("  Pacing",     ca.pacing,     cb.pacing)
        row("  Saturation", ca.saturation, cb.saturation)
        row("  Contrast",   ca.contrast,   cb.contrast)
        row("  Motion",     ca.motion,     cb.motion)
        row("  Flashing",   ca.flashing,   cb.flashing)
        if ma.sensory_load.audio_available or mb.sensory_load.audio_available:
            row("  Audio",  ca.audio,      cb.audio)

        row("Scene Pacing", section=True, va=None, vb=None)
        row("Cuts / min", ma.scene_pacing.cuts_per_min, mb.scene_pacing.cuts_per_min, fmt=".1f")
        row("Mean shot length (s)", ma.shot_length.mean_sec, mb.shot_length.mean_sec,
            lower_better=False)
        row("Shot-length CV", ma.scene_pacing.shot_length_cv, mb.scene_pacing.shot_length_cv)

        row("Color", section=True, va=None, vb=None)
        row("Saturation mean", ma.color_saturation.mean,        mb.color_saturation.mean)
        row("Contrast mean",   ma.color_saturation.contrast_mean, mb.color_saturation.contrast_mean)

        row("Motion", section=True, va=None, vb=None)
        row("Motion mean", ma.motion.mean, mb.motion.mean)
        row("Motion peak", ma.motion.peak, mb.motion.peak)

        row("Flashing", section=True, va=None, vb=None)
        row("Events / min", ma.flashing.luminance_delta_events_per_min,
            mb.flashing.luminance_delta_events_per_min, fmt=".1f")

        if ma.audio.available or mb.audio.available:
            row("Audio", section=True, va=None, vb=None)
            va = ma.audio.rms_mean        if ma.audio.available else None
            vb = mb.audio.rms_mean        if mb.audio.available else None
            row("RMS loudness mean", va, vb, fmt=".4f")
            va = ma.audio.dynamic_range_db if ma.audio.available else None
            vb = mb.audio.dynamic_range_db if mb.audio.available else None
            row("Dynamic range (dB)", va, vb, lower_better=False, fmt=".1f")

    @staticmethod
    def _fill_show(row, a: ShowAggregate, b: ShowAggregate) -> None:
        row("Episodes analyzed",
            float(a.episode_count - a.failed_count),
            float(b.episode_count - b.failed_count),
            lower_better=False, fmt=".0f")

        row("Sensory Load", section=True, va=None, vb=None)
        row("Mean score",   a.sensory_load_score.mean,   b.sensory_load_score.mean)
        row("Median score", a.sensory_load_score.median, b.sensory_load_score.median)
        row("Std dev",      a.sensory_load_score.std,    b.sensory_load_score.std)
        row("Min score",    a.sensory_load_score.min,    b.sensory_load_score.min)
        row("Max score",    a.sensory_load_score.max,    b.sensory_load_score.max)

        row("Scene Pacing", section=True, va=None, vb=None)
        row("Avg cuts / min",      a.cuts_per_min.mean,        b.cuts_per_min.mean,        fmt=".1f")
        row("Avg shot length (s)", a.shot_length_mean_sec.mean, b.shot_length_mean_sec.mean,
            lower_better=False)

        row("Color", section=True, va=None, vb=None)
        row("Avg saturation", a.color_saturation_mean.mean, b.color_saturation_mean.mean)
        row("Avg contrast",   a.color_contrast_mean.mean,   b.color_contrast_mean.mean)

        row("Motion", section=True, va=None, vb=None)
        row("Avg motion mean", a.motion_mean.mean, b.motion_mean.mean)

        row("Flashing", section=True, va=None, vb=None)
        row("Avg events / min", a.flashing_events_per_min.mean,
            b.flashing_events_per_min.mean, fmt=".1f")

        if a.audio_rms_mean.mean > 0 or b.audio_rms_mean.mean > 0:
            row("Audio", section=True, va=None, vb=None)
            va = a.audio_rms_mean.mean if a.audio_rms_mean.mean > 0 else None
            vb = b.audio_rms_mean.mean if b.audio_rms_mean.mean > 0 else None
            row("Avg RMS loudness", va, vb, fmt=".4f")


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
