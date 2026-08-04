"""
gui_handcoding.py — Hand-coding tab for CMAT.

The manual measurement path, for researchers who want human-coded metrics as
their PRIMARY method rather than as validation input:

    pick episode → code transitions and/or fantastical events → metrics

No automated detection is involved. Metrics are computed from the coding using
the same definitions as the automated engine, so a hand-coded rate is directly
comparable to an automated one.

Distinct from the Validation tab, which exists to grade the automated detector
against coding (and therefore requires blind coding, detection runs, and F1).
Here there is nothing to be biased by, so none of that applies.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from analyzer.event_coding import (compute_event_metrics, parse_event_csv,
                                   write_event_template)
from analyzer.validation import (episode_dir, find_latest, find_manual,
                                 get_validation_dir, manual_pacing_metrics,
                                 sec_to_hms, write_manual_metrics,
                                 write_template)
from gui_validation import _Tip


GUIDE_TEXT = """\
HAND-CODING — WHAT THIS TAB IS FOR

Use this tab when human coding IS your measurement — for example, when you are
characterizing specific episodes (or short segments) as stimuli for a study
with children, and you want coded-by-hand numbers rather than automated ones.

This is a different workflow from the Validation tab:

  Hand-coding (this tab)      "What is in this content?"
                              Your coding -> descriptive metrics.
                              No detection is run. Nothing is compared.

  Validation tab              "How accurate is the automated tool?"
                              Your coding + tool detections -> precision,
                              recall, F1, error taxonomy.

Because nothing here is being compared to the tool, the blind-coding rule from
the validation workflow does NOT apply. Code however suits your study.

────────────────────────────────────────────────────────
STEP 1 - PICK THE EPISODE
Choose the video file. The status line shows what has already been coded for it.

STEP 2 - CODE IT
Two independent coding sheets, each opening in CMAT's coding editor with a
built-in video player:

  Transitions  - cuts, dissolves, fades, wipes/other, and optionally whether
                 each hard cut stays within a scene or changes scene.
  Events       - fantastical events (impossible occurrences), with event type,
                 narrative relevance, and repetition.

In the editor: play the video, press S (or the Stamp button) to log a row at
the exact current frame. Dropdown values persist between rows, so a run of
similar transitions is just watch -> S -> watch -> S. Every dropdown is
editable, so you can use your own category scheme instead of the defaults.

STEP 3 - SET THE CODED WINDOW
If you coded only part of the episode (common - e.g. a 5-minute segment),
enter the range. Rates are then computed over that window rather than the full
runtime. Leave both blank if you coded the whole episode.

STEP 4 - COMPUTE METRICS
Results appear in the Results panel on the right:

  Transitions  - hard cuts per minute, all transitions per minute, counts by
                 type, mean/median shot length, shot-length variability (CV),
                 a per-30-second timeline, and - if you labeled scene relation -
                 scene changes per minute and the within-scene fraction.
  Events       - fantastical events per minute, per-type rates, and the
                 integral/incidental and new/repeat breakdowns.

Export writes the metrics to CSV for your own analysis.

────────────────────────────────────────────────────────
NOTES ON THE METRICS

Shot lengths use the gaps BETWEEN coded transitions. The first and last shots
in a coded window are cut off by the window edges, so including them would
bias the mean downward.

"Hard cuts per minute" is the figure comparable to "camera cuts per minute" as
normally reported in the media-effects literature. "Transitions per minute"
additionally counts dissolves, fades and wipes.

Scene changes per minute requires the optional scene_relation column
(within / change) on hard-cut rows. It separates shot-reverse-shot cutting
inside one scene from cuts that relocate the viewer - a distinction raw cut
rate hides.
"""


class HandCodingTab(tk.Frame):
    """Manual measurement path: code content, get metrics from the coding."""

    def __init__(self, parent: tk.Misc, get_root_folder=None,
                 on_results=None) -> None:
        super().__init__(parent)
        self._get_root_folder = get_root_folder or (lambda: None)
        self._on_results = on_results
        self._video: Path | None = None
        self._last_metrics: dict | None = None
        self._last_kind = ""
        self._build_ui()

    # ── UI ───────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        canvas = tk.Canvas(self, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0), pady=6)
        outer = tk.Frame(canvas)
        win_id = canvas.create_window((0, 0), window=outer, anchor="nw")
        outer.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfigure(win_id, width=e.width))

        def _wheel(e):
            canvas.yview_scroll(int(-e.delta / 120), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        hdr = tk.Frame(outer)
        hdr.pack(fill=tk.X)
        b_guide = tk.Button(hdr, text="📖 What this tab is for",
                            command=self._show_guide, fg="#0055aa")
        b_guide.pack(side=tk.LEFT)
        _Tip(b_guide, "Explains the hand-coding workflow and how it differs "
                      "from the Validation tab, plus exactly how each metric "
                      "is defined.")
        b_folder = tk.Button(hdr, text="Open coding folder",
                             command=self._open_folder)
        b_folder.pack(side=tk.RIGHT)

        tk.Label(outer,
                 text="Human coding as the measurement — no automated "
                      "detection is used here. For grading the automated "
                      "tool instead, use the Validation tab.",
                 font=("TkDefaultFont", 8), fg="#555555",
                 wraplength=430, justify="left").pack(fill=tk.X, pady=(4, 0))

        # Step 1 — episode
        s1 = tk.LabelFrame(outer, text=" Step 1 — Pick the episode ",
                           padx=6, pady=6)
        s1.pack(fill=tk.X, pady=(8, 0))
        tk.Button(s1, text="Choose video…",
                  command=self._choose_video).pack(fill=tk.X)

        # Coding worklist — episodes to work through, e.g. from a sample draw
        wl = tk.LabelFrame(s1, text=" Coding worklist ", padx=4, pady=4)
        wl.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        wl_btns = tk.Frame(wl)
        wl_btns.pack(fill=tk.X)
        b_load = tk.Button(wl_btns, text="Load sample…",
                           command=self._load_sample)
        b_load.pack(side=tk.LEFT)
        _Tip(b_load, "Load an Episode Sampler draw (manifest.json) so you can "
                     "work through exactly the episodes that sample selected, "
                     "one at a time.\n\nThe sampler can also push a draw "
                     "straight here — choose \"Hand-coding worklist\" as the "
                     "destination in the sampler's Load into CMAT step.")
        tk.Button(wl_btns, text="Clear",
                  command=self._clear_worklist).pack(side=tk.RIGHT)

        lb_frame = tk.Frame(wl)
        lb_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self._worklist_lb = tk.Listbox(lb_frame, height=6,
                                       font=("Consolas", 8),
                                       activestyle="none",
                                       selectmode=tk.SINGLE)
        wsb = ttk.Scrollbar(lb_frame, orient=tk.VERTICAL,
                            command=self._worklist_lb.yview)
        self._worklist_lb.configure(yscrollcommand=wsb.set)
        wsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._worklist_lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._worklist_lb.bind("<<ListboxSelect>>", self._on_worklist_select)
        _Tip(self._worklist_lb,
             "Click an episode to make it the current one for coding. The "
             "prefix shows coding progress:\n"
             "  ·  not yet coded\n"
             "  T  transitions coded\n"
             "  E  events coded\n"
             "  TE both coded")
        self._worklist: list[Path] = []
        self._worklist_var = tk.StringVar(value="")
        tk.Label(wl, textvariable=self._worklist_var,
                 font=("TkDefaultFont", 8), fg="#555555",
                 anchor="w").pack(fill=tk.X)
        self._video_var = tk.StringVar(value="(no episode selected)")
        tk.Label(s1, textvariable=self._video_var, fg="#333333",
                 font=("TkDefaultFont", 8), wraplength=400,
                 anchor="w", justify="left").pack(fill=tk.X, pady=(4, 0))
        self._status_var = tk.StringVar(value="")
        tk.Label(s1, textvariable=self._status_var,
                 font=("TkDefaultFont", 8, "bold"), fg="#006633",
                 anchor="w", justify="left").pack(fill=tk.X)

        # Step 2 — code
        s2 = tk.LabelFrame(outer, text=" Step 2 — Code it ", padx=6, pady=6)
        s2.pack(fill=tk.X, pady=(8, 0))
        b_tr = tk.Button(s2, text="Code transitions (cuts, dissolves, fades)",
                         command=lambda: self._open_sheet("transitions"),
                         fg="#0055aa")
        b_tr.pack(fill=tk.X, pady=2)
        _Tip(b_tr, "Opens the transitions coding sheet in the coding editor "
                   "with a built-in player.\n\nPlay the video and press S to "
                   "stamp a row at the exact current frame. Dropdowns keep "
                   "their values between rows, and every dropdown is editable "
                   "— type your own category to use your lab's scheme.\n\n"
                   "Optionally label each hard cut within / change to get "
                   "scene-change rates.")
        b_ev = tk.Button(s2, text="Code fantastical events",
                         command=lambda: self._open_sheet("events"),
                         fg="#884400")
        b_ev.pack(fill=tk.X, pady=2)
        _Tip(b_ev, "Opens the fantastical-event coding sheet (event type, "
                   "narrative relevance, repetition).\n\nRemember the premise "
                   "rule: a standing impossibility such as talking animals is "
                   "the show's premise, not a coded event. Discrete impossible "
                   "occurrences are events.")
        b_cb = tk.Button(s2, text="View codebooks",
                         command=self._open_codebook)
        b_cb.pack(fill=tk.X, pady=2)

        # Step 3 — window
        s3 = tk.LabelFrame(outer, text=" Step 3 — Coded window ",
                           padx=6, pady=6)
        s3.pack(fill=tk.X, pady=(8, 0))
        row = tk.Frame(s3)
        row.pack(fill=tk.X)
        tk.Label(row, text="from", font=("TkDefaultFont", 8)).pack(side=tk.LEFT)
        self._start_var = tk.StringVar(value="")
        tk.Entry(row, textvariable=self._start_var, width=7).pack(side=tk.LEFT,
                                                                  padx=3)
        tk.Label(row, text="to", font=("TkDefaultFont", 8)).pack(side=tk.LEFT)
        self._end_var = tk.StringVar(value="")
        tk.Entry(row, textvariable=self._end_var, width=7).pack(side=tk.LEFT,
                                                                padx=3)
        tk.Label(row, text="(blank = whole episode)",
                 font=("TkDefaultFont", 8), fg="#666666").pack(side=tk.LEFT,
                                                               padx=4)
        _Tip(s3, "If you coded only part of the episode — a 5-minute segment, "
                 "say — enter the range here (seconds or MM:SS). Rates are "
                 "then computed over that window instead of the full runtime, "
                 "which is what makes segment coding valid.")

        # Step 4 — metrics
        s4 = tk.LabelFrame(outer, text=" Step 4 — Compute metrics ",
                           padx=6, pady=6)
        s4.pack(fill=tk.X, pady=(8, 0))
        b_m1 = tk.Button(s4, text="Transition metrics  →  Results",
                         command=lambda: self._compute("transitions"),
                         fg="#0055aa")
        b_m1.pack(fill=tk.X, pady=2)
        _Tip(b_m1, "Computes, from YOUR coding: hard cuts per minute, all "
                   "transitions per minute, counts by type, mean/median shot "
                   "length, shot-length variability, a per-30s timeline, and "
                   "scene-change rates if you labeled scene relation.\n\n"
                   "Same metric definitions as the automated engine, so the "
                   "numbers are directly comparable.")
        b_m2 = tk.Button(s4, text="Event metrics  →  Results",
                         command=lambda: self._compute("events"),
                         fg="#884400")
        b_m2.pack(fill=tk.X, pady=2)
        b_x = tk.Button(s4, text="Export last metrics to CSV…",
                        command=self._export)
        b_x.pack(fill=tk.X, pady=(6, 2))

    # ── helpers ──────────────────────────────────────────────────────────

    def _vdir(self) -> Path:
        return get_validation_dir()

    def _need_video(self) -> Path | None:
        if self._video is None:
            messagebox.showinfo("Pick an episode first",
                                "Choose the episode video in Step 1 first.",
                                parent=self)
            return None
        return self._video

    def _choose_video(self) -> None:
        root = self._get_root_folder()
        path = filedialog.askopenfilename(
            parent=self, title="Choose the episode to hand-code",
            initialdir=str(root) if root else str(Path.home()),
            filetypes=[("Video files", "*.mp4 *.mkv *.avi *.mov"),
                       ("All files", "*.*")])
        if not path:
            return
        self._video = Path(path)
        self._video_var.set(self._video.name)
        self._refresh_status()

    # ── worklist ─────────────────────────────────────────────────────────

    def add_episodes(self, paths: "list[Path]", source: str = "") -> int:
        """Add episodes to the coding worklist (used by the Episode Sampler)."""
        added = 0
        for p in paths:
            p = Path(p)
            if p not in self._worklist:
                self._worklist.append(p)
                added += 1
        self._render_worklist()
        if added and self._video is None and self._worklist:
            self._video = self._worklist[0]
            self._video_var.set(self._video.name)
            self._refresh_status()
        if source:
            self._worklist_var.set(f"{added} episode(s) added from {source}")
        return added

    def _render_worklist(self) -> None:
        self._worklist_lb.delete(0, tk.END)
        n_done = 0
        for p in self._worklist:
            has_t = find_manual(p, self._vdir()) is not None
            has_e = self._find_events_sheet(p) is not None
            flag = ("TE" if (has_t and has_e) else
                    "T " if has_t else "E " if has_e else "· ")
            if has_t or has_e:
                n_done += 1
            self._worklist_lb.insert(tk.END, f"{flag} {p.name[:60]}")
        if self._worklist:
            self._worklist_var.set(
                f"{n_done} of {len(self._worklist)} episode(s) have coding")
        else:
            self._worklist_var.set("")

    def _on_worklist_select(self, _event=None) -> None:
        sel = self._worklist_lb.curselection()
        if not sel:
            return
        self._video = self._worklist[sel[0]]
        self._video_var.set(self._video.name)
        self._refresh_status()

    def _clear_worklist(self) -> None:
        self._worklist = []
        self._render_worklist()

    def _load_sample(self) -> None:
        from analyzer.trials import read_sample_episodes
        root = self._get_root_folder()
        path = filedialog.askopenfilename(
            parent=self, title="Open Episode Sampler manifest",
            initialdir=str(root) if root else str(Path.home()),
            filetypes=[("Sample manifest", "manifest.json"),
                       ("JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        eps = read_sample_episodes(Path(path))
        if not eps:
            messagebox.showwarning(
                "No episodes found",
                "Couldn't read episode paths from that sample. Expected a "
                "selected.csv with a 'filepath' column beside manifest.json.",
                parent=self)
            return
        missing = [p for p in eps if not p.exists()]
        n = self.add_episodes(eps, source=Path(path).parent.name)
        if missing:
            messagebox.showinfo(
                "Some files not found",
                f"{len(missing)} of {len(eps)} episode file(s) in this sample "
                f"aren't on disk at the recorded path. They were still added "
                f"to the worklist — coding them will need the files present.",
                parent=self)

    def _find_events_sheet(self, video: Path) -> Path | None:
        vdir = self._vdir()
        hit = find_latest(f"{video.stem}_events.csv", vdir)
        if hit:
            return hit
        suffix = "_events.csv"
        cands = [p for p in vdir.rglob(f"*{suffix}")
                 if len(p.name) - len(suffix) >= 8
                 and video.stem.lower().startswith(p.name[:-len(suffix)].lower())]
        return sorted(cands, key=lambda p: p.stat().st_mtime)[-1] if cands else None

    def _refresh_status(self) -> None:
        if self._video is None:
            self._status_var.set("")
            return
        parts = []
        man = find_manual(self._video, self._vdir())
        if man:
            try:
                from analyzer.validation import parse_manual_csv
                parts.append(f"{len(parse_manual_csv(man))} transitions coded")
            except Exception:
                parts.append("transitions sheet exists")
        ev = self._find_events_sheet(self._video)
        if ev:
            try:
                parts.append(f"{len(parse_event_csv(ev))} events coded")
            except Exception:
                parts.append("events sheet exists")
        self._status_var.set("  ·  ".join(parts) if parts
                             else "nothing coded yet")
        if self._worklist:
            self._render_worklist()

    def _open_sheet(self, kind: str) -> None:
        video = self._need_video()
        if not video:
            return
        from gui_coding_editor import CodingSheetEditor
        if kind == "transitions":
            sheet = find_manual(video, self._vdir())
            if sheet is None:
                try:
                    sheet = write_template(video, episode_dir(video))
                except FileExistsError as exc:
                    sheet = Path(str(exc))
        else:
            sheet = self._find_events_sheet(video)
            if sheet is None:
                try:
                    sheet = write_event_template(video, episode_dir(video))
                except FileExistsError as exc:
                    sheet = Path(str(exc))
        ed = CodingSheetEditor(self, sheet, schema_name=kind, video_path=video)
        ed.bind("<Destroy>", lambda e: self._refresh_status(), add=True)

    def _open_codebook(self) -> None:
        cb = find_latest("CODEBOOK.md", self._vdir())
        if cb is None:
            messagebox.showinfo("Not found",
                                "No codebook found in the coding folder.",
                                parent=self)
            return
        os.startfile(str(cb))

    def _open_folder(self) -> None:
        d = self._vdir()
        d.mkdir(parents=True, exist_ok=True)
        os.startfile(str(d))

    def _show_guide(self) -> None:
        win = tk.Toplevel(self)
        win.title("Hand-coding — guide")
        win.geometry("620x640")
        fr = tk.Frame(win)
        fr.pack(fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(fr, orient=tk.VERTICAL)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        txt = tk.Text(fr, wrap=tk.WORD, font=("Consolas", 9),
                      yscrollcommand=sb.set, padx=10, pady=8)
        txt.insert("1.0", GUIDE_TEXT)
        txt.config(state=tk.DISABLED)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=txt.yview)

    def _duration(self, video: Path) -> float:
        try:
            import cv2
            cap = cv2.VideoCapture(str(video))
            fps = cap.get(cv2.CAP_PROP_FPS) or 0
            n = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
            cap.release()
            return n / fps if fps else 0.0
        except Exception:
            return 0.0

    # ── metrics ──────────────────────────────────────────────────────────

    def _compute(self, kind: str) -> None:
        video = self._need_video()
        if not video:
            return
        start = self._start_var.get().strip() or None
        end = self._end_var.get().strip() or None

        if kind == "transitions":
            sheet = find_manual(video, self._vdir())
            if sheet is None:
                messagebox.showinfo("Not coded yet",
                                    "No transitions coding sheet for this "
                                    "episode — code it in Step 2 first.",
                                    parent=self)
                return
            dur = self._duration(video) if not (start or end) else 0.0
            if dur <= 0 and not (start or end):
                messagebox.showwarning(
                    "Duration unknown",
                    "Could not read the episode duration, so rates can't be "
                    "computed. Enter the coded window in Step 3.", parent=self)
                return
            m = manual_pacing_metrics(sheet, duration_sec=dur,
                                      start=start, end=end)
        else:
            sheet = self._find_events_sheet(video)
            if sheet is None:
                messagebox.showinfo("Not coded yet",
                                    "No event coding sheet for this episode — "
                                    "code it in Step 2 first.", parent=self)
                return
            dur = self._duration(video) if not (start or end) else 0.0
            if dur <= 0 and not (start or end):
                messagebox.showwarning(
                    "Duration unknown",
                    "Could not read the episode duration. Enter the coded "
                    "window in Step 3.", parent=self)
                return
            m = compute_event_metrics(parse_event_csv(sheet),
                                      duration_sec=dur, start=start, end=end)

        self._last_metrics, self._last_kind = m, kind
        # Persist so hand-coded results are browsable in the Index tab,
        # clearly separated from automated results.
        try:
            write_manual_metrics(video, kind, m)
        except Exception:
            pass
        if self._on_results:
            self._on_results(video, kind, m)

    def _export(self) -> None:
        if not self._last_metrics:
            messagebox.showinfo("Nothing to export",
                                "Compute metrics first (Step 4).", parent=self)
            return
        default = f"{self._video.stem}_handcoded_{self._last_kind}.csv"
        path = filedialog.asksaveasfilename(
            parent=self, title="Export hand-coded metrics",
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile=default)
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["metric", "value"])
            w.writerow(["source", "hand-coded (no automated detection)"])
            w.writerow(["episode", self._video.name])
            for k, v in self._last_metrics.items():
                if isinstance(v, dict):
                    for k2, v2 in v.items():
                        w.writerow([f"{k}[{k2}]", v2])
                elif isinstance(v, list):
                    w.writerow([k, " ".join(str(x) for x in v)])
                else:
                    w.writerow([k, v])
        messagebox.showinfo("Exported", f"Saved:\n{path}", parent=self)
