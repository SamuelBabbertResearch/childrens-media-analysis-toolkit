"""
gui_trials.py — Trials tab for CMAT.

A registry of every sampling + manual-coding study performed with the tool,
auto-discovered from the provenance manifests each run writes. Rows are
clickable: double-click opens a detail window with full parameters and
buttons to open the underlying files.

UI only — discovery logic lives in analyzer/trials.py.
"""

from __future__ import annotations

import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from analyzer.trials import KIND_EXPLANATIONS, KIND_LABELS, discover_trials
from gui_validation import _Tip


_COLUMNS = [
    ("date",     "Date",      78),
    ("name",     "Trial",     210),
    ("kind",     "Trial type", 130),
    ("sampling", "Sampling",  170),
    ("eps",      "Eps",       36),
    ("window",   "Window",    92),
    ("result",   "Key result", 130),
    ("pub",      "Site",      40),
]


class TrialsTab(tk.Frame):
    """Registry of sampling + manual-coding trials.

    on_select, if given, is called with the trial dict whenever a row is
    selected — the main app uses it to show the trial in the Results panel.
    """

    def __init__(self, parent: tk.Misc, get_root_folder=None,
                 on_select=None, on_aggregate=None) -> None:
        super().__init__(parent)
        self._get_root_folder = get_root_folder or (lambda: None)
        self._on_select = on_select
        self._on_aggregate = on_aggregate
        self._trials: list[dict] = []
        self._sort_col = "date"
        self._sort_desc = True
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        hdr = tk.Frame(self)
        hdr.pack(fill=tk.X, padx=6, pady=(6, 2))
        tk.Label(hdr, text="Every sampling + manual-coding study, discovered "
                           "from its saved provenance. Double-click a row for "
                           "details and files.",
                 font=("TkDefaultFont", 8), fg="#555555",
                 wraplength=430, justify="left").pack(side=tk.LEFT, fill=tk.X,
                                                      expand=True)
        btn = tk.Button(hdr, text="Refresh", command=self.refresh)
        btn.pack(side=tk.RIGHT)
        _Tip(btn, "Re-scans the validation folder for trial manifests. Run "
                  "this after a new compare / rates / sweep / classify run.")

        frame = tk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(2, 6))
        cols = [c for c, _, _ in _COLUMNS]
        self._tree = ttk.Treeview(frame, columns=cols, show="headings")
        for cid, label, width in _COLUMNS:
            self._tree.heading(cid, text=label,
                               command=lambda c=cid: self._sort_by(c))
            self._tree.column(cid, width=width,
                              anchor="w" if cid in ("name", "sampling",
                                                    "kind") else "center")
        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._tree.bind("<Double-1>", self._open_detail)
        self._tree.bind("<<TreeviewSelect>>", self._on_row_selected)
        self._tree.tag_configure("published", background="#e8f5e8")
        self._tree.tag_configure("machine", foreground="#888888")
        _Tip(self._tree,
             "One row per study run. Click a column header to sort.\n\n"
             "Trial types:\n"
             "• Transition validation — your hand coding graded against the "
             "detector (F1)\n"
             "• Event coding — hand-coded fantastical events (events/min)\n"
             "• Dissolve sweep / Classifier grading — parameter tuning against "
             "your coding\n"
             "• Cut classification / Detection run — machine-only runs (grey)\n\n"
             "Green rows are published to the website via "
             "code_events.py publish.")

        self._count_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._count_var,
                 font=("TkDefaultFont", 8), fg="#555555",
                 anchor="w").pack(fill=tk.X, padx=8, pady=(0, 4))

    # ── data ─────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        root = self._get_root_folder()
        self._trials = discover_trials(
            extra_dirs=[root] if root else None)
        self._render()

    def _render(self) -> None:
        self._tree.delete(*self._tree.get_children())
        for i, t in enumerate(self._trials):
            tags = ()
            if t["published"]:
                tags = ("published",)
            elif t["kind"] in ("detection_run", "cut_classification"):
                tags = ("machine",)
            self._tree.insert(
                "", tk.END, iid=str(i),
                values=(t["date"], t.get("name", t["episode"]),
                        KIND_LABELS.get(t["kind"], t["kind"]),
                        t["sampling"], t["n_episodes"], t["window"],
                        t["result"], "✓" if t["published"] else ""),
                tags=tags)
        n = len(self._trials)
        n_manual = sum(1 for t in self._trials
                       if t["kind"] not in ("detection_run",
                                            "cut_classification"))
        self._count_var.set(
            f"{n} trial(s) discovered — {n_manual} involving manual coding. "
            f"Grey = machine-only. Green = published to the site.")

    def _on_row_selected(self, _event=None) -> None:
        if self._on_select is None:
            return
        sel = self._tree.selection()
        if sel:
            self._on_select(self._trials[int(sel[0])])

    def _sort_by(self, col: str) -> None:
        key_map = {"date": "date", "name": "name", "kind": "kind",
                   "sampling": "sampling", "eps": "n_episodes",
                   "window": "window", "result": "result",
                   "pub": "published"}
        key = key_map.get(col, "date")
        if self._sort_col == col:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col, self._sort_desc = col, True
        self._trials.sort(key=lambda t: str(t.get(key, "")),
                          reverse=self._sort_desc)
        self._render()

    # ── detail window ────────────────────────────────────────────────────

    def _open_detail(self, _event=None) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        t = self._trials[int(sel[0])]
        TrialDetailWindow(self, t, on_aggregate=self._on_aggregate)


class TrialDetailWindow(tk.Toplevel):
    def __init__(self, parent: tk.Misc, trial: dict, on_aggregate=None) -> None:
        super().__init__(parent)
        self._trial = trial
        self._on_aggregate = on_aggregate
        kind_label = KIND_LABELS.get(trial["kind"], trial["kind"])
        self.title(f"Trial — {kind_label} — {trial.get('name', trial['episode'])}")
        self.geometry("560x480")

        tk.Label(self, text=f"{kind_label}: {trial['episode']}",
                 font=("TkDefaultFont", 10, "bold"), anchor="w",
                 padx=10, pady=6).pack(fill=tk.X)
        tk.Label(self, text=KIND_EXPLANATIONS.get(trial["kind"], ""),
                 font=("TkDefaultFont", 8), fg="#555555", wraplength=530,
                 justify="left", padx=10).pack(fill=tk.X)

        # Summary rows
        info = tk.Frame(self, padx=10, pady=6)
        info.pack(fill=tk.X)
        rows = [
            ("Date", trial["date"]),
            ("Sampling", trial["sampling"]),
            ("Window", trial["window"]),
            ("Key result", trial["result"]),
            ("Detail", trial["detail"]),
            ("Published to site", "yes" if trial["published"] else "no"),
            ("CMAT commit", trial["git_commit"] or "not recorded"),
        ]
        if trial["kind"] == "episode_sample":
            from analyzer.trials import sample_coverage
            cov = sample_coverage(trial)
            if cov:
                rows.insert(3, (
                    "Coding coverage",
                    f"{cov['n_transition_coded']} of {cov['n_episodes']} sampled "
                    f"episodes transition-coded; "
                    f"{cov['n_event_coded']} event-coded"))
        for r, (k, v) in enumerate(rows):
            tk.Label(info, text=k + ":", font=("TkDefaultFont", 8, "bold"),
                     anchor="ne").grid(row=r, column=0, sticky="ne", padx=(0, 8))
            tk.Label(info, text=str(v), font=("TkDefaultFont", 8),
                     anchor="nw", wraplength=420,
                     justify="left").grid(row=r, column=1, sticky="nw")

        # Full manifest dump
        raw_fr = tk.LabelFrame(self, text=" Full run parameters (manifest) ",
                               padx=6, pady=4)
        raw_fr.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 4))
        txt = tk.Text(raw_fr, font=("Consolas", 8), height=10, wrap=tk.NONE)
        import json as _json
        txt.insert("1.0", _json.dumps(trial["raw"], indent=2))
        txt.config(state=tk.DISABLED)
        txt.pack(fill=tk.BOTH, expand=True)

        foot = tk.Frame(self, padx=10, pady=8)
        foot.pack(fill=tk.X)
        if trial["kind"] == "episode_sample" and self._on_aggregate:
            b_agg = tk.Button(foot, text="Compute trial aggregate",
                              fg="#5500aa", command=self._run_aggregate)
            b_agg.pack(side=tk.LEFT, padx=(0, 6))
            _Tip(b_agg, "Computes the show aggregate over EXACTLY this "
                        "sample's episodes (from cached analyses) and shows "
                        "it in the Results panel. Use this — not the "
                        "corpus-wide show aggregate — when reporting numbers "
                        "for a designed sample.")
        b1 = tk.Button(foot, text="Open trial folder",
                       command=lambda: os.startfile(str(trial["folder"])))
        b1.pack(side=tk.LEFT)
        _Tip(b1, "Opens the folder holding this trial's files (coding sheets, "
                 "detections, comparison CSVs, match details).")
        b2 = tk.Button(foot, text="Open manifest JSON",
                       command=lambda: os.startfile(str(trial["manifest_path"])))
        b2.pack(side=tk.LEFT, padx=6)
        tk.Button(foot, text="Close", command=self.destroy).pack(side=tk.RIGHT)

    def _run_aggregate(self) -> None:
        if self._on_aggregate:
            self._on_aggregate(self._trial)
            self.destroy()
