"""
gui_sampler.py — Episode Sampling panel for CMAT.

Opened as a Toplevel window from the main GUI or standalone.
Flow (top to bottom, matching the decision logic):
  1. Input (folder or registry CSV)
  2. Stratification (Axis A)
  3. Selection method (Axis B)
  4. Method parameters (progressive disclosure)
  5. Allocation (enabled when stratified)
  6. Sort key
  7. Seed
  8. Preview dry-run table
  9. Run / Export
"""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from analyzer.sampler import (
    TOOLTIPS,
    Episode,
    SampleResult,
    scan_entry_root,
    load_registry_csv,
    sample,
    write_outputs,
)


# ---------------------------------------------------------------------------
# Reusable tooltip (mirrors _WidgetTooltip in gui.py)
# ---------------------------------------------------------------------------

class _Tip:
    def __init__(self, widget: tk.Widget, text: str, wraplength: int = 360) -> None:
        self._w = widget
        self._text = text
        self._wl = wraplength
        self._win: tk.Toplevel | None = None
        self._timer: str | None = None
        widget.bind("<Enter>", self._enter)
        widget.bind("<Motion>", self._enter)
        widget.bind("<Leave>", self._leave)
        widget.after_idle(self._bind_children)

    def _bind_children(self) -> None:
        for c in self._w.winfo_children():
            c.bind("<Enter>", self._enter)
            c.bind("<Motion>", self._enter)
            c.bind("<Leave>", self._leave)

    def _enter(self, _e=None) -> None:
        if self._win:
            return
        if self._timer:
            self._w.after_cancel(self._timer)
        self._timer = self._w.after(500, self._show)

    def _leave(self, _e=None) -> None:
        if self._timer:
            self._w.after_cancel(self._timer)
            self._timer = None
        if self._win:
            self._win.destroy()
            self._win = None

    def _show(self) -> None:
        self._timer = None
        if self._win:
            return
        x = self._w.winfo_rootx() + 20
        y = self._w.winfo_rooty() + self._w.winfo_height() + 4
        self._win = tw = tk.Toplevel(self._w)
        tw.wm_overrideredirect(True)
        tw.attributes("-topmost", True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(
            tw, text=self._text, justify=tk.LEFT,
            background="#ffffcc", relief=tk.SOLID, borderwidth=1,
            font=("TkDefaultFont", 8), wraplength=self._wl, padx=6, pady=4,
        ).pack()


def _tip_btn(parent: tk.Widget, key: str) -> tk.Label:
    """Small (?) label beside an option that shows the tooltip on hover."""
    lbl = tk.Label(parent, text="(?)", fg="#0055aa",
                   font=("TkDefaultFont", 8), cursor="question_arrow")
    _Tip(lbl, TOOLTIPS.get(key, ""), wraplength=360)
    return lbl


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class SamplerWindow(tk.Toplevel):
    def __init__(self, parent: tk.Misc | None = None, app_ref=None) -> None:
        super().__init__(parent)
        self.title("Episode Sampler — CMAT")
        self.geometry("760x820")
        self.minsize(680, 600)
        self.resizable(True, True)

        self._app = app_ref          # reference to the main App, may be None
        self._episodes: list[Episode] = []
        self._last_result: SampleResult | None = None

        self._build_ui()
        self._refresh_disclosure()

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = tk.Frame(self)
        outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        # Scrollable canvas so the panel is accessible at small heights
        canvas = tk.Canvas(outer, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._scroll_frame = tk.Frame(canvas)
        self._scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self._scroll_frame, anchor="nw")
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        f = self._scroll_frame

        # 1. Input
        self._build_section_input(f)
        ttk.Separator(f, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)

        # 2. Stratification
        self._build_section_stratify(f)
        ttk.Separator(f, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)

        # 3. Selection method
        self._build_section_method(f)
        ttk.Separator(f, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)

        # 4. Method parameters (progressive disclosure)
        self._build_section_method_params(f)
        ttk.Separator(f, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)

        # 5. Allocation
        self._build_section_allocation(f)
        ttk.Separator(f, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)

        # 6 & 7. Sort + Seed
        self._build_section_sort_seed(f)
        ttk.Separator(f, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)

        # 8. Preview
        self._build_section_preview(f)
        ttk.Separator(f, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)

        # 9. Run / Export
        self._build_section_run(f)

    # --- Section 1: Input ---

    def _build_section_input(self, parent: tk.Frame) -> None:
        lf = tk.LabelFrame(parent, text="1. Input", padx=6, pady=4)
        lf.pack(fill=tk.X, pady=(0, 2))

        # Folder row
        row = tk.Frame(lf)
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text="Entry root folder:", width=20, anchor="w").pack(side=tk.LEFT)
        self._folder_var = tk.StringVar(value="(none)")
        tk.Label(row, textvariable=self._folder_var, anchor="w",
                 fg="navy", wraplength=400).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(row, text="Browse...", command=self._browse_folder,
                  padx=4).pack(side=tk.RIGHT, padx=(4, 0))
        _tip_btn(row, "entry_root").pack(side=tk.RIGHT)

        # Registry CSV row
        row2 = tk.Frame(lf)
        row2.pack(fill=tk.X, pady=2)
        tk.Label(row2, text="  or registry CSV:", width=20, anchor="w").pack(side=tk.LEFT)
        self._csv_var = tk.StringVar(value="(none)")
        tk.Label(row2, textvariable=self._csv_var, anchor="w",
                 fg="navy", wraplength=400).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(row2, text="Load CSV...", command=self._load_csv,
                  padx=4).pack(side=tk.RIGHT, padx=(4, 0))
        _tip_btn(row2, "load_registry").pack(side=tk.RIGHT)

        # Summary label
        self._scan_summary_var = tk.StringVar(value="No episodes loaded.")
        tk.Label(lf, textvariable=self._scan_summary_var,
                 fg="#335500", font=("TkDefaultFont", 9, "italic"),
                 anchor="w").pack(fill=tk.X, pady=(4, 2))

        # Advanced expander
        self._adv_open = tk.BooleanVar(value=False)
        adv_toggle = tk.Checkbutton(
            lf, text="Advanced (regex / file types)",
            variable=self._adv_open, command=self._toggle_advanced,
            fg="#555555", font=("TkDefaultFont", 8),
        )
        adv_toggle.pack(anchor="w")
        self._adv_frame = tk.Frame(lf)

        def _adv_row(label: str, default: str, tip_key: str) -> tk.StringVar:
            r = tk.Frame(self._adv_frame)
            r.pack(fill=tk.X, pady=1)
            tk.Label(r, text=label, width=22, anchor="w",
                     font=("TkDefaultFont", 8)).pack(side=tk.LEFT)
            var = tk.StringVar(value=default)
            tk.Entry(r, textvariable=var, width=36,
                     font=("Consolas", 8)).pack(side=tk.LEFT)
            _tip_btn(r, tip_key).pack(side=tk.LEFT, padx=2)
            return var

        self._season_regex_var = _adv_row(
            "Season folder regex:", r"(?i)(?:season\s*|s)(\d+)", "season_regex")
        self._episode_regex_var = _adv_row(
            "Episode file regex:", r"(?i)s(\d+)e(\d+)", "episode_regex")
        self._ext_var = _adv_row(
            "Video extensions:", ".mp4 .mkv .avi .mov .wmv .m4v", "video_extensions")

    def _toggle_advanced(self) -> None:
        if self._adv_open.get():
            self._adv_frame.pack(fill=tk.X, padx=4, pady=4)
        else:
            self._adv_frame.pack_forget()

    # --- Section 2: Stratification ---

    def _build_section_stratify(self, parent: tk.Frame) -> None:
        lf = tk.LabelFrame(parent, text="2. Stratification (Axis A)", padx=6, pady=4)
        lf.pack(fill=tk.X, pady=(0, 2))

        self._stratify_var = tk.StringVar(value="season")
        options = [
            ("none",   "None — sample the whole run at once", "stratify_none"),
            ("season", "By season (recommended)",             "stratify_season"),
            ("column", "By era / custom column",              "stratify_column"),
        ]
        for val, label, tip_key in options:
            row = tk.Frame(lf)
            row.pack(fill=tk.X, pady=1)
            tk.Radiobutton(
                row, text=label, variable=self._stratify_var, value=val,
                command=self._refresh_disclosure,
            ).pack(side=tk.LEFT)
            _tip_btn(row, tip_key).pack(side=tk.LEFT, padx=2)

        self._col_frame = tk.Frame(lf)
        tk.Label(self._col_frame, text="Column name:", width=14, anchor="w").pack(side=tk.LEFT)
        self._col_var = tk.StringVar()
        tk.Entry(self._col_frame, textvariable=self._col_var, width=20).pack(side=tk.LEFT)

    # --- Section 3: Selection method ---

    def _build_section_method(self, parent: tk.Frame) -> None:
        lf = tk.LabelFrame(parent, text="3. Selection method (Axis B)", padx=6, pady=4)
        lf.pack(fill=tk.X, pady=(0, 2))

        self._method_var = tk.StringVar(value="spread")
        options = [
            ("census",     "Census — all episodes",                   "method_census"),
            ("srs",        "Simple random (SRS)",                     "method_srs"),
            ("systematic", "Systematic / interval",                   "method_systematic"),
            ("spread",     "Spread / chunked (recommended default)",  "method_spread"),
            ("manual",     "Manual / convenience",                    "method_manual"),
        ]
        for val, label, tip_key in options:
            row = tk.Frame(lf)
            row.pack(fill=tk.X, pady=1)
            tk.Radiobutton(
                row, text=label, variable=self._method_var, value=val,
                command=self._refresh_disclosure,
            ).pack(side=tk.LEFT)
            _tip_btn(row, tip_key).pack(side=tk.LEFT, padx=2)

    # --- Section 4: Method parameters ---

    def _build_section_method_params(self, parent: tk.Frame) -> None:
        lf = tk.LabelFrame(parent, text="4. Method parameters", padx=6, pady=4)
        lf.pack(fill=tk.X, pady=(0, 2))
        self._params_frame = lf

        # Systematic: interval k
        self._sys_frame = tk.Frame(lf)
        row = tk.Frame(self._sys_frame)
        row.pack(fill=tk.X)
        tk.Label(row, text="Interval k:", width=18, anchor="w").pack(side=tk.LEFT)
        self._interval_k_var = tk.StringVar(value="")
        tk.Entry(row, textvariable=self._interval_k_var, width=8).pack(side=tk.LEFT)
        tk.Label(row, text="(blank = derive from n)", fg="#666",
                 font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=4)
        _tip_btn(row, "interval_k").pack(side=tk.LEFT)

        # Manual: episode list
        self._manual_frame = tk.Frame(lf)
        tk.Label(self._manual_frame, text="Episodes to include:",
                 anchor="w").pack(fill=tk.X)
        _tip_btn(self._manual_frame, "manual_list").pack(anchor="w")
        self._manual_text = tk.Text(
            self._manual_frame, height=5, width=50,
            font=("Consolas", 9), relief=tk.SUNKEN, bd=1,
        )
        self._manual_text.pack(fill=tk.X, pady=2)
        tk.Label(self._manual_frame,
                 text="One entry per line: SxxExx, title, or episode number.",
                 fg="#666", font=("TkDefaultFont", 8), anchor="w").pack(fill=tk.X)

        # Placeholder when no extra params needed
        self._no_params_label = tk.Label(
            lf, text="No additional parameters for this method.",
            fg="#888", font=("TkDefaultFont", 9, "italic"),
        )

    # --- Section 5: Allocation ---

    def _build_section_allocation(self, parent: tk.Frame) -> None:
        lf = tk.LabelFrame(parent, text="5. Allocation (when stratified)", padx=6, pady=4)
        lf.pack(fill=tk.X, pady=(0, 2))
        self._alloc_frame = lf

        self._alloc_var = tk.StringVar(value="equal")
        for val, label, tip_key in [
            ("equal",        "Equal — same quota per stratum",               "allocation_equal"),
            ("proportional", "Proportional — fixed total, D'Hondt division", "allocation_proportional"),
        ]:
            row = tk.Frame(lf)
            row.pack(fill=tk.X, pady=1)
            tk.Radiobutton(
                row, text=label, variable=self._alloc_var, value=val,
                command=self._refresh_disclosure,
            ).pack(side=tk.LEFT)
            _tip_btn(row, tip_key).pack(side=tk.LEFT, padx=2)

        # Equal params
        self._equal_frame = tk.Frame(lf)
        row = tk.Frame(self._equal_frame)
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text="Episodes per stratum:", width=22, anchor="w").pack(side=tk.LEFT)
        self._per_n_var = tk.StringVar(value="2")
        tk.Spinbox(row, from_=1, to=9999, textvariable=self._per_n_var,
                   width=6).pack(side=tk.LEFT)
        _tip_btn(row, "per_stratum_n").pack(side=tk.LEFT, padx=2)

        # Proportional params
        self._prop_frame = tk.Frame(lf)
        for label, var_name, default, tip_key in [
            ("Total sample size:", "_total_n_var", "10", "total_n"),
            ("Minimum per stratum:", "_floor_var",  "1",  "floor"),
        ]:
            r = tk.Frame(self._prop_frame)
            r.pack(fill=tk.X, pady=2)
            tk.Label(r, text=label, width=22, anchor="w").pack(side=tk.LEFT)
            var = tk.StringVar(value=default)
            setattr(self, var_name, var)
            tk.Spinbox(r, from_=1, to=9999, textvariable=var, width=6).pack(side=tk.LEFT)
            _tip_btn(r, tip_key).pack(side=tk.LEFT, padx=2)

    # --- Section 6 & 7: Sort key + Seed ---

    def _build_section_sort_seed(self, parent: tk.Frame) -> None:
        lf = tk.LabelFrame(parent, text="6 & 7. Ordering and seed", padx=6, pady=4)
        lf.pack(fill=tk.X, pady=(0, 2))

        row = tk.Frame(lf)
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text="Sort key:", width=16, anchor="w").pack(side=tk.LEFT)
        self._sort_var = tk.StringVar(value="episode")
        for val, label in [("episode", "Episode number"), ("air_date", "Air date")]:
            tk.Radiobutton(row, text=label, variable=self._sort_var, value=val).pack(side=tk.LEFT, padx=4)
        _tip_btn(row, "sort_col").pack(side=tk.LEFT)

        row2 = tk.Frame(lf)
        row2.pack(fill=tk.X, pady=2)
        tk.Label(row2, text="Random seed:", width=16, anchor="w").pack(side=tk.LEFT)
        self._seed_var = tk.StringVar(value="42")
        tk.Spinbox(row2, from_=0, to=999999999, textvariable=self._seed_var,
                   width=12).pack(side=tk.LEFT)
        _tip_btn(row2, "seed").pack(side=tk.LEFT, padx=2)

    # --- Section 8: Preview ---

    def _build_section_preview(self, parent: tk.Frame) -> None:
        lf = tk.LabelFrame(parent, text="8. Preview", padx=6, pady=4)
        lf.pack(fill=tk.X, pady=(0, 2))

        row = tk.Frame(lf)
        row.pack(fill=tk.X, pady=(0, 4))
        tk.Button(row, text="Preview sample (dry run)", command=self._run_preview,
                  padx=8, bg="#e8f0ff").pack(side=tk.LEFT)
        _tip_btn(row, "preview").pack(side=tk.LEFT, padx=4)
        self._preview_summary_var = tk.StringVar(value="")
        tk.Label(row, textvariable=self._preview_summary_var,
                 fg="#336600", font=("TkDefaultFont", 9, "italic")).pack(side=tk.LEFT, padx=8)

        # Treeview preview table
        tree_frame = tk.Frame(lf)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        cols = ("season", "episode", "title", "filepath")
        self._preview_tree = ttk.Treeview(
            tree_frame, columns=cols, show="headings", height=10,
        )
        for col, width in [("season", 60), ("episode", 60), ("title", 180), ("filepath", 320)]:
            self._preview_tree.heading(col, text=col.capitalize())
            self._preview_tree.column(col, width=width, anchor="w")
        psb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                             command=self._preview_tree.yview)
        self._preview_tree.configure(yscrollcommand=psb.set)
        psb.pack(side=tk.RIGHT, fill=tk.Y)
        self._preview_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # --- Section 9: Send to Queue / Export ---

    def _build_section_run(self, parent: tk.Frame) -> None:
        lf = tk.LabelFrame(parent, text="9. Load into CMAT", padx=6, pady=6)
        lf.pack(fill=tk.X, pady=(0, 2))

        # Primary action
        primary_row = tk.Frame(lf)
        primary_row.pack(fill=tk.X, pady=(2, 4))
        self._btn_queue = tk.Button(
            primary_row, text="Send to Analysis Queue",
            command=self._send_to_queue,
            padx=14, pady=4, bg="#c8e6c9",
            font=("TkDefaultFont", 10, "bold"),
            state=tk.NORMAL if self._app else tk.DISABLED,
        )
        self._btn_queue.pack(side=tk.LEFT)
        tk.Label(
            primary_row,
            text="Queues the selected episodes for analysis in the main window.",
            fg="#444", font=("TkDefaultFont", 8),
        ).pack(side=tk.LEFT, padx=10)

        self._queue_status_var = tk.StringVar(value="")
        tk.Label(lf, textvariable=self._queue_status_var,
                 fg="#003300", font=("TkDefaultFont", 9, "italic"),
                 anchor="w").pack(fill=tk.X, pady=(0, 4))

        ttk.Separator(lf, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=4)

        # Secondary: export manifest / CSV
        export_row = tk.Frame(lf)
        export_row.pack(fill=tk.X, pady=2)
        tk.Button(export_row, text="Export CSV + Manifest...",
                  command=self._run_export, padx=8).pack(side=tk.LEFT)
        tk.Label(export_row,
                 text="Save selected.csv, manifest.json, and worklist.txt for your paper.",
                 fg="#666", font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=8)

        # Gather option (under export)
        gather_row = tk.Frame(lf)
        gather_row.pack(fill=tk.X, pady=(4, 0), padx=20)
        self._gather_var = tk.BooleanVar(value=False)
        self._copy_var = tk.BooleanVar(value=False)
        tk.Checkbutton(gather_row, text="Also gather video files into output folder",
                       variable=self._gather_var,
                       command=self._refresh_disclosure).pack(side=tk.LEFT)
        _tip_btn(gather_row, "gather_files").pack(side=tk.LEFT, padx=2)
        self._copy_cb = tk.Checkbutton(gather_row, text="Full copies (not symlinks)",
                                        variable=self._copy_var)
        self._copy_cb.pack(side=tk.LEFT, padx=12)

        self._export_status_var = tk.StringVar(value="")
        tk.Label(lf, textvariable=self._export_status_var,
                 fg="#003300", font=("TkDefaultFont", 9, "italic"),
                 anchor="w").pack(fill=tk.X, pady=(2, 0))

    # -----------------------------------------------------------------------
    # Progressive disclosure
    # -----------------------------------------------------------------------

    def _refresh_disclosure(self) -> None:
        method = self._method_var.get()
        stratify = self._stratify_var.get()
        alloc = self._alloc_var.get()

        # Stratification: column entry
        if stratify == "column":
            self._col_frame.pack(fill=tk.X, pady=2, padx=20)
        else:
            self._col_frame.pack_forget()

        # Method params
        for frame in (self._sys_frame, self._manual_frame, self._no_params_label):
            try:
                frame.pack_forget()
            except Exception:
                pass
        if method == "systematic":
            self._sys_frame.pack(fill=tk.X, pady=2)
        elif method == "manual":
            self._manual_frame.pack(fill=tk.X, pady=2)
        else:
            if method in ("census",):
                self._no_params_label.pack(fill=tk.X, pady=4)

        # Allocation block: only when stratified
        if stratify == "none":
            for w in self._alloc_frame.winfo_children():
                if isinstance(w, (tk.Radiobutton, tk.Frame)):
                    w.configure(state=tk.DISABLED) if hasattr(w, "configure") else None
        else:
            for w in self._alloc_frame.winfo_children():
                if hasattr(w, "configure"):
                    try:
                        w.configure(state=tk.NORMAL)
                    except tk.TclError:
                        pass

        # Equal / proportional param frames
        self._equal_frame.pack_forget()
        self._prop_frame.pack_forget()
        if stratify != "none":
            if alloc == "equal":
                self._equal_frame.pack(fill=tk.X, pady=2, padx=20)
            else:
                self._prop_frame.pack(fill=tk.X, pady=2, padx=20)

        # Gather: copy checkbox enabled only when gather is checked
        self._copy_cb.configure(
            state=tk.NORMAL if self._gather_var.get() else tk.DISABLED
        )

    # -----------------------------------------------------------------------
    # Input handlers
    # -----------------------------------------------------------------------

    def _browse_folder(self) -> None:
        path = filedialog.askdirectory(title="Select entry root folder", parent=self)
        if not path:
            return
        self._folder_var.set(path)
        self._csv_var.set("(none)")
        self._load_episodes_from_folder(Path(path))

    def _load_csv(self) -> None:
        path = filedialog.askopenfilename(
            title="Load registry CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            parent=self,
        )
        if not path:
            return
        self._csv_var.set(path)
        self._folder_var.set("(none)")
        try:
            self._episodes = load_registry_csv(Path(path))
            self._update_scan_summary()
        except Exception as exc:
            messagebox.showerror("Load error", str(exc), parent=self)

    def _load_episodes_from_folder(self, root: Path) -> None:
        ext_raw = self._ext_var.get()
        exts = {e.strip() if e.strip().startswith(".") else f".{e.strip()}"
                for e in ext_raw.replace(",", " ").split()}
        try:
            self._episodes = scan_entry_root(
                root,
                season_regex=self._season_regex_var.get() or None,
                episode_regex=self._episode_regex_var.get() or None,
                video_extensions=exts or None,
            )
            self._update_scan_summary()
        except Exception as exc:
            messagebox.showerror("Scan error", str(exc), parent=self)

    def _update_scan_summary(self) -> None:
        eps = self._episodes
        if not eps:
            self._scan_summary_var.set("No episodes found.")
            return
        seasons = {e.season for e in eps if e.season is not None}
        if seasons:
            self._scan_summary_var.set(
                f"Detected {len(seasons)} season(s), {len(eps)} episode(s)."
            )
        else:
            self._scan_summary_var.set(f"Detected {len(eps)} episode(s) (no seasons).")

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(title="Choose output folder", parent=self)
        if path:
            self._outdir_var.set(path)

    # -----------------------------------------------------------------------
    # Sampling helpers
    # -----------------------------------------------------------------------

    def _collect_params(self) -> dict:
        method = self._method_var.get()
        stratify = self._stratify_var.get()
        alloc = self._alloc_var.get()

        stratify_by: str | None = (
            None if stratify == "none"
            else "season" if stratify == "season"
            else self._col_var.get().strip() or "season"
        )

        per_n = int(self._per_n_var.get() or 2)
        total_n_s = getattr(self, "_total_n_var", None)
        total_n = int(total_n_s.get()) if total_n_s and total_n_s.get() else None
        floor_s = getattr(self, "_floor_var", None)
        floor = int(floor_s.get()) if floor_s and floor_s.get() else 1
        k_s = self._interval_k_var.get().strip()
        interval_k = int(k_s) if k_s else None
        seed = int(self._seed_var.get() or 42)
        sort_col = self._sort_var.get()

        manual_lines = None
        if method == "manual":
            raw = self._manual_text.get("1.0", tk.END)
            manual_lines = [l.strip() for l in raw.splitlines() if l.strip()]

        return dict(
            stratify_by=stratify_by,
            method=method,
            allocation=alloc,
            per_stratum_n=per_n,
            total_n=total_n,
            floor=floor,
            interval_k=interval_k,
            sort_col=sort_col,
            seed=seed,
            manual_list=manual_lines,
        )

    def _run_sample(self) -> SampleResult | None:
        if not self._episodes:
            messagebox.showwarning("No episodes", "Load a folder or CSV first.", parent=self)
            return None
        try:
            params = self._collect_params()
            eid = (
                Path(self._folder_var.get()).name
                if self._folder_var.get() not in ("(none)", "")
                else Path(self._csv_var.get()).stem
            )
            result = sample(self._episodes, entry_id=eid, **params)
            return result
        except Exception as exc:
            messagebox.showerror("Sampling error", str(exc), parent=self)
            return None

    # -----------------------------------------------------------------------
    # Preview
    # -----------------------------------------------------------------------

    def _run_preview(self) -> None:
        result = self._run_sample()
        if result is None:
            return
        self._last_result = result
        self._populate_preview(result)

    # -----------------------------------------------------------------------
    # Send to Queue / Export
    # -----------------------------------------------------------------------

    def _send_to_queue(self) -> None:
        if not self._app:
            messagebox.showwarning(
                "No main window",
                "The sampler has no reference to the main CMAT window.",
                parent=self,
            )
            return

        result = self._run_sample()
        if result is None:
            return
        self._last_result = result
        self._populate_preview(result)

        # Enqueue every episode that has a filepath
        queued, skipped, no_path = 0, 0, 0
        for ep in result.selected:
            if ep.filepath is None:
                no_path += 1
                continue
            added = self._app._enqueue(ep.filepath, silent=True)
            if added:
                queued += 1
            else:
                skipped += 1

        # Auto-save manifest beside the entry folder for reproducibility
        folder = self._folder_var.get()
        if folder and folder != "(none)":
            base = Path(folder).parent
        elif self._csv_var.get() not in ("(none)", ""):
            base = Path(self._csv_var.get()).parent
        else:
            base = None

        if base:
            outdir = self._make_outdir(base, result.manifest.method, result.manifest.entry_id)
            try:
                write_outputs(result, outdir)
            except Exception:
                pass  # manifest save failure is non-fatal

        parts = [f"{queued} episode(s) added to the queue"]
        if skipped:
            parts.append(f"{skipped} already queued")
        if no_path:
            parts.append(f"{no_path} had no file path")
        self._queue_status_var.set("  ".join(parts))

        self._show_notes(result)

    def _run_export(self) -> None:
        result = self._run_sample()
        if result is None:
            return
        self._last_result = result
        self._populate_preview(result)

        folder = self._folder_var.get()
        if folder and folder != "(none)":
            base = Path(folder).parent
        elif self._csv_var.get() not in ("(none)", ""):
            base = Path(self._csv_var.get()).parent
        else:
            base = Path.home()
        outdir = self._make_outdir(base, result.manifest.method, result.manifest.entry_id)

        try:
            paths = write_outputs(
                result, outdir,
                gather=self._gather_var.get(),
                copy_files=self._copy_var.get(),
            )
        except Exception as exc:
            messagebox.showerror("Export error", str(exc), parent=self)
            return

        n = result.manifest.total_selected
        self._export_status_var.set(f"Exported {n} episodes → {outdir.name}/")
        self._show_notes(result)

    # -----------------------------------------------------------------------
    # Shared helpers
    # -----------------------------------------------------------------------

    def _make_outdir(self, base: Path, method: str, entry_id: str) -> Path:
        """Build a descriptive output folder name, adding a counter if it already exists."""
        safe_id = re.sub(r"[^\w\-]", "_", entry_id).strip("_") or "sample"
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        stem = f"{safe_id}_{method}_{date_str}"
        outdir = base / stem
        counter = 2
        while outdir.exists():
            outdir = base / f"{stem}_{counter}"
            counter += 1
        return outdir

    def _populate_preview(self, result: SampleResult) -> None:
        for row in self._preview_tree.get_children():
            self._preview_tree.delete(row)
        for ep in result.selected:
            self._preview_tree.insert("", tk.END, values=(
                ep.season if ep.season is not None else "",
                ep.episode if ep.episode is not None else "",
                ep.title or "",
                str(ep.filepath) if ep.filepath else "",
            ))
        n = result.manifest.total_selected
        avail = result.manifest.total_available
        prob = "probability" if result.manifest.probability else "NON-PROBABILITY"
        notes_count = len(result.manifest.notes)
        msg = f"{n} of {avail} episodes selected ({prob} sample)"
        if notes_count:
            msg += f" — {notes_count} note(s)"
        self._preview_summary_var.set(msg)

    def _show_notes(self, result: SampleResult) -> None:
        notes = result.manifest.notes
        if notes:
            note_text = "\n".join(f"• {note}" for note in notes)
            messagebox.showinfo(
                "Sampling notes",
                f"The following notes were recorded:\n\n{note_text}",
                parent=self,
            )


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

def main() -> None:
    root = tk.Tk()
    root.withdraw()
    win = SamplerWindow(root)
    win.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
