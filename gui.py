"""
gui.py — Tkinter front-end for the Children's TV Sensory-Load Analyzer.

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
from analyzer.metrics_sensory import rescore_episode
from analyzer.schema import EpisodeResult, ShowAggregate
from analyzer.db import (
    get_db, upsert_episode, upsert_show, query_episodes, query_shows,
    get_note, save_note, get_episode_percentile, remove_stale_episodes,
)
from analyzer.show_index import (
    list_episodes, list_shows, list_top_level, list_category_shows, show_key,
)
from gui_live import LiveAnalysisWindow


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Children's TV Sensory-Load Analyzer")
        self.geometry("1050x680")
        self.minsize(800, 500)

        self._root_folder: Path | None = None
        self._cfg = load_config()
        self._queue: queue.Queue = queue.Queue()
        self._ep_queue: list[Path] = []       # episodes waiting to be analyzed
        self._analyzing: Path | None = None   # episode currently running
        self._watch_live_active = False        # live window open
        self._current_ep_result: EpisodeResult | None = None   # for export/chart
        self._current_ep_path: Path | None = None               # for DB look-ups
        self._current_show_results: list[EpisodeResult] | None = None  # for export
        self._pinned: tuple[str, Path] | None = None            # ("episode"|"show", path)
        self._db_conn = None                                   # SQLite index (opened with root)
        self._idx_ep_sort:   dict = {"col": "analyzed_at", "asc": False}
        self._idx_show_sort: dict = {"col": "avg_load",    "asc": False}
        self._cut_pulse_job: str | None = None  # after() ID for cut-detection animation

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
        episodes = list_episodes(show_dir)
        ok_results = []
        for ep in episodes:
            c = load_cached(self._root_folder, skey, ep.stem)
            if c:
                ok_results.append(rescore_episode(EpisodeResult.from_dict(c), self._cfg))

        if not ok_results:
            self._write_txt(
                f"Show: {show_dir.name}\n\n"
                f"{len(episodes)} episode(s) — none analyzed yet.\n\n"
                "Click  Analyze Show (Batch)  to analyze all episodes."
            )
        else:
            agg = compute_show_aggregate(skey, ok_results)
            self._render_show(agg, ok_results, total_eps=len(episodes))

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
        self._btn_chart.config(state=tk.DISABLED)
        self._file_menu.entryconfig("Export Results as JSON...", state=tk.DISABLED)
        self._file_menu.entryconfig("Export Results as CSV...", state=tk.DISABLED)
        self._file_menu.entryconfig("Export Report as PDF...", state=tk.DISABLED)
        self._notes_text.config(state=tk.NORMAL)
        self._notes_text.delete("1.0", tk.END)
        self._notes_text.config(state=tk.DISABLED)
        self._btn_save_note.config(state=tk.DISABLED)

    def _render_episode(self, result: EpisodeResult) -> None:
        self._current_ep_result = result if result.status == "ok" else None
        self._current_show_results = None
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

    def _render_show(self, agg: ShowAggregate, results: list[EpisodeResult],
                     total_eps: int) -> None:
        self._current_ep_result = None
        self._current_show_results = [r for r in results if r.status == "ok"]
        self._btn_chart.config(state=tk.DISABLED)  # chart is episode-only for now
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
                        upsert_episode(self._db_conn, result,
                                       show_key(self._root_folder, ep_path.parent), str(ep_path))
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

    def _maybe_save_show_aggregate(self, ep_path: Path) -> None:
        """If all episodes of the show are now cached, compute and save the aggregate."""
        show_dir = ep_path.parent
        skey = show_key(self._root_folder, show_dir)
        episodes = list_episodes(show_dir)
        if not episodes:
            return
        all_results = []
        for ep in episodes:
            c = load_cached(self._root_folder, skey, ep.stem)
            if c:
                all_results.append(EpisodeResult.from_dict(c))
        if len(all_results) == len(episodes):
            agg = compute_show_aggregate(skey, all_results)
            save_show_results(self._root_folder, skey, all_results, agg)
            if self._db_conn:
                upsert_show(self._db_conn, agg, skey)

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

    # -----------------------------------------------------------------------
    # Settings
    # -----------------------------------------------------------------------

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
            episodes = list_episodes(show_dir)
            ok_results = []
            for ep in episodes:
                c = load_cached(self._root_folder, skey, ep.stem)
                if c:
                    ok_results.append(rescore_episode(EpisodeResult.from_dict(c), self._cfg))
            if ok_results:
                agg = compute_show_aggregate(skey, ok_results)
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

        _ep_cols   = ("show", "file", "dur", "cpm", "sat", "con", "mot", "flash", "rms", "load", "date", "notes")
        _ep_hdrs   = ("Show", "File", "Dur(s)", "C/min", "Sat", "Contrast", "Motion", "Flash/m", "RMS", "Load", "Date", "Notes")
        _ep_widths = (80, 110, 48, 48, 42, 55, 50, 55, 48, 48, 82, 130)
        self._idx_ep_db_cols = (
            "show_name", "file_name", "duration_sec", "cuts_per_min",
            "color_saturation_mean", "color_contrast_mean", "motion_mean",
            "flashing_events_per_min", "audio_rms_mean",
            "sensory_load_score", "analyzed_at", "notes",
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
            "date":  "Date and time this episode was last analyzed.",
            "notes": "Your saved note for this episode. Hover a row to read the full text.",
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
                    _fmt(r["duration_sec"], "%.0f"),
                    _fmt(r["cuts_per_min"], "%.1f"),
                    _fmt(r["color_saturation_mean"], "%.3f"),
                    _fmt(r["color_contrast_mean"], "%.3f") if r.get("color_contrast_mean") is not None else "",
                    _fmt(r["motion_mean"], "%.3f"),
                    _fmt(r["flashing_events_per_min"], "%.1f") if r["flashing_events_per_min"] is not None else "",
                    _fmt(r["audio_rms_mean"], "%.4f") if r["audio_rms_mean"] is not None else "n/a",
                    _fmt(r["sensory_load_score"], "%.3f"),
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
            show_results = []
            for ep in list_episodes(show_dir):
                c = load_cached(self._root_folder, skey, ep.stem)
                if c:
                    try:
                        result = EpisodeResult.from_dict(c)
                        if result.status == "ok":
                            result = rescore_episode(result, self._cfg)
                            upsert_episode(self._db_conn, result, skey, str(ep))
                            show_results.append(result)
                    except Exception:
                        pass
            if show_results:
                try:
                    agg = compute_show_aggregate(skey, show_results)
                    upsert_show(self._db_conn, agg, skey)
                except Exception:
                    pass

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
    """Simple hover tooltip for any widget."""

    def __init__(self, widget: tk.Widget, text: str, wraplength: int = 300) -> None:
        self._widget = widget
        self._text = text
        self._wraplength = wraplength
        self._win: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, event: tk.Event) -> None:
        if self._win:
            return
        x = self._widget.winfo_rootx() + 20
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._win = tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
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

        self._build()
        self._fill_from_cfg(parent._cfg)
        self._refresh_preset_desc()
        self._update_total()

        self.geometry("480x560")
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
