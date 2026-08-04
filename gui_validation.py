"""
gui_validation.py — Validation tab for CMAT.

Walks the user through validating the transition detector against their own
hand-coded ground truth:

    1. pick an episode        2. hand-code it blind (VLC + CSV)
    3. run tool detection     4. compare -> P/R/F1 + error list
    5. annotate failure reasons (the error taxonomy)
    6. (advanced) parameter sweep on tuning episodes

All logic lives in analyzer/validation.py — this file is UI only.
Long operations run on a daemon worker thread posting to a Queue that the
main thread drains via after(), per the app-wide threading rule.
"""

from __future__ import annotations

import os
import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from analyzer.validation import (
    FAILURE_TAGS, aggregate_summary, compare_detections, episode_status,
    export_detections, find_latest, find_manual, get_validation_dir,
    load_match_detail, run_sweep, save_match_detail, sec_to_hms,
    write_template,
)


# ---------------------------------------------------------------------------
# Tooltip (self-contained copy so this module never imports gui.py)
# ---------------------------------------------------------------------------

class _Tip:
    """Hover tooltip. Same behavior as gui.py's _WidgetTooltip."""

    def __init__(self, widget: tk.Widget, text: str, wraplength: int = 320) -> None:
        self._widget = widget
        self._text = text
        self._wraplength = wraplength
        self._win: tk.Toplevel | None = None
        self._timer: str | None = None
        widget.bind("<Enter>", self._on_enter)
        widget.bind("<Motion>", self._on_enter)
        widget.bind("<Leave>", self._on_leave)
        widget.after_idle(self._bind_children)

    def _bind_children(self) -> None:
        try:
            for child in self._widget.winfo_children():
                child.bind("<Enter>", self._on_enter)
                child.bind("<Motion>", self._on_enter)
                child.bind("<Leave>", self._on_leave)
        except tk.TclError:
            pass

    def _on_enter(self, _e=None) -> None:
        if self._win:
            return
        if self._timer:
            self._widget.after_cancel(self._timer)
        self._timer = self._widget.after(600, self._show)

    def _on_leave(self, _e=None) -> None:
        if self._timer:
            self._widget.after_cancel(self._timer)
            self._timer = None
        self._hide()

    def _show(self) -> None:
        self._timer = None
        if self._win:
            return
        try:
            x = self._widget.winfo_rootx() + 20
            y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        except tk.TclError:
            return
        self._win = tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.attributes("-topmost", True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self._text, justify=tk.LEFT, background="#ffffcc",
                 relief=tk.SOLID, borderwidth=1, font=("TkDefaultFont", 8),
                 wraplength=self._wraplength, padx=6, pady=4).pack()

    def _hide(self, _e=None) -> None:
        if self._win:
            self._win.destroy()
            self._win = None


_STEP_LABELS = {
    "start":     ("Not started", "#888888"),
    "template":  ("Template created — code it in VLC", "#aa6600"),
    "coded":     ("Hand-coded — ready to run detection", "#0066aa"),
    "detected":  ("Detected — ready to compare", "#5500aa"),
    "compared":  ("Compared — annotate the errors", "#aa0055"),
    "annotated": ("Fully annotated ✓", "#007700"),
}


GUIDE_TEXT = """\
VALIDATION — STEP BY STEP GUIDE

WHAT THIS TAB IS FOR
You are the answer key. The tool claims "there's a cut at 0:37" — the only
way to know if it's right is for a human to watch the episode and write down
where the transitions really are. This tab grades the tool against your
answers and helps you document WHY it fails when it fails. The results
(precision / recall / F1) are what make the pacing metrics defensible in a
paper or on the website.

THE GOLDEN RULE — CODE BLIND
Never look at the tool's detections before your hand-coding is finished and
saved. If you peek first, you'll unconsciously agree with the tool and the
whole test grades itself. Order matters: create the coding sheet FIRST, code
the episode, THEN run detection.

────────────────────────────────────────────────────────
STEP 1 — PICK THE EPISODE
Choose the video file you want to validate. The status line shows where this
episode is in the workflow (template → coded → detected → compared →
annotated).

STEP 2 — CREATE THE CODING SHEET & HAND-CODE IT
"Create coding sheet" writes a blank CSV named <episode>_manual.csv into the
validation folder. Open it (any editor or Excel) side-by-side with VLC and
log every transition:

    timestamp_hms  = when it happens, like 02:13 (or use timestamp_sec)
    type           = hard_cut | dissolve | fade_in | fade_out | other
    notes          = anything useful, required for "other"

Codebook quick rules (full rules: "View codebook" button):
  • hard_cut  — instant shot change, no blend frames. Time = first frame of
    the NEW shot.
  • dissolve  — two SHOTS visibly overlap for 2+ frames. Time = midpoint.
    Frame-step with VLC's E key to check: 2+ blended frames = dissolve.
  • fade_out / fade_in — to/from a solid color. A fade-out then fade-in
    across black = TWO rows.
  • other    — wipes, iris transitions, graphic overlays. Always add a note.
  • Camera movement (pans, zooms) and things moving on screen are NOT
    transitions. Don't code them.
  • A title/graphic fading in over an unchanged shot is "other", not a
    dissolve (the underlying SHOT must change for a dissolve).

Useful VLC keys:  E = step one frame   Shift+←/→ = jump 3s   Ctrl+T = go to time

Tip — code in two passes: first pass at normal speed jotting rough times,
second pass frame-stepping each one to pin the exact moment.

Coding part of an episode is fine (e.g. first story only), but decide the
window BEFORE watching and enter it in Step 4 so the tool isn't blamed for
detections outside what you coded.

STEP 3 — RUN THE TOOL'S DETECTION
Runs the same detector the analysis engine uses (plus the experimental
dissolve pass) and saves a detections CSV. The first run decodes the whole
video (a few minutes); after that, cached results make re-runs instant.
Do this AFTER your coding is saved (golden rule).

STEP 4 — COMPARE (THE GRADE)
Matches your coding against the tool's detections within the tolerance
window (±2s default; use ±1s for fast-cut shows where cuts come quicker
than 2s apart). You get:
  • TP (true positive)  — you both found it
  • FN (miss)           — you found it, the tool didn't
  • FP (false alarm)    — the tool "found" something that isn't there
  • Type mismatch       — matched in time but labeled differently
Precision = of what the tool found, how much was real.
Recall    = of what was really there, how much the tool found.
F1        = balance of both (1.0 is perfect).

STEP 5 — ANNOTATE THE ERRORS (most important step)
In the results window, give every miss and false alarm a failure reason from
the dropdown (e.g. missed_dissolve_snow, false_cut_zoom). Re-watch the
moment in VLC first — the "Copy time" button puts the timestamp on your
clipboard for Ctrl+T. If the tool found a REAL transition you missed, that's
a coding omission: fix your manual CSV and re-compare (your annotations are
preserved).
These tags are the error taxonomy — they turn "F1 = 0.17" into "the detector
misses gentle dissolves under snowfall", which is the publishable finding.

STEP 6 (ADVANCED) — PARAMETER SWEEP
Tries many dissolve-detection settings against your coding and shows which
scores best. ONLY sweep on designated TUNING episodes. Never tune on the
held-out test episodes — tuning on the episodes you report results from is
overfitting, and a reviewer will catch it. Decide the tuning/test split
before comparing anything, and log it in VALIDATION_LOG.md.

FILES (all in the validation folder)
  <ep>_manual.csv            your hand-coding (the answer key)
  <ep>__<config>_detections.csv   what the tool found
  <ep>__<config>_comparison_<date>.csv   the score table
  <ep>__<config>_match_detail_<date>.csv  every TP/FP/FN + your annotations
  *_manifest.json            parameters + code version for every run
  *_framescores.npz / *_cuts_*.json    caches — keep them, they save minutes
  CODEBOOK.md                the coding rules   VALIDATION_LOG.md   lab notebook

Log every session in VALIDATION_LOG.md: date, episode, time spent, decisions.
"""


# ---------------------------------------------------------------------------
# The tab
# ---------------------------------------------------------------------------

class ValidationTab(tk.Frame):
    """Validation workflow tab. Parent is the left Notebook in gui.py."""

    def __init__(self, parent: tk.Misc, get_root_folder=None) -> None:
        super().__init__(parent)
        self._get_root_folder = get_root_folder or (lambda: None)
        self._video: Path | None = None
        self._busy = False
        self._q: queue.Queue = queue.Queue()
        self._build_ui()
        self.after(100, self._poll_queue)

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Scrollable content: the step stack is taller than most windows, and
        # Tkinter's packer clips later-packed widgets to zero height when it
        # runs out of room (Step 4 would vanish). Canvas + interior frame is
        # the standard fix; the mouse wheel scrolls while the cursor is here.
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

        def _on_wheel(e) -> None:
            canvas.yview_scroll(int(-e.delta / 120), "units")

        canvas.bind("<Enter>",
                    lambda e: canvas.bind_all("<MouseWheel>", _on_wheel))
        canvas.bind("<Leave>",
                    lambda e: canvas.unbind_all("<MouseWheel>"))

        # Header: guide button + folder button
        hdr = tk.Frame(outer)
        hdr.pack(fill=tk.X)
        guide_btn = tk.Button(hdr, text="📖 Step-by-step guide",
                              command=self._show_guide, fg="#0055aa")
        guide_btn.pack(side=tk.LEFT)
        _Tip(guide_btn, "Opens the full walkthrough: what validation is, the "
                        "blind-coding rule, the coding rules, what the scores "
                        "mean, and which files end up where.")
        folder_btn = tk.Button(hdr, text="Open validation folder",
                               command=self._open_folder)
        folder_btn.pack(side=tk.RIGHT)
        _Tip(folder_btn, "Opens the validation folder in Explorer. All coding "
                         "sheets, detections, comparisons, and the codebook "
                         "live here.")

        # Step 1 — episode
        s1 = tk.LabelFrame(outer, text=" Step 1 — Pick the episode ", padx=6, pady=6)
        s1.pack(fill=tk.X, pady=(8, 0))
        pick = tk.Button(s1, text="Choose video…", command=self._choose_video)
        pick.pack(fill=tk.X)
        b_samp = tk.Button(s1, text="Choose from a sample draw…",
                           command=self._choose_from_sample)
        b_samp.pack(fill=tk.X, pady=(2, 0))
        _Tip(b_samp, "Pick an episode from an Episode Sampler draw "
                     "(manifest.json) instead of browsing the filesystem — so "
                     "you validate exactly the episodes that sample selected.")
        _Tip(pick, "Pick the episode video file (.mp4/.mkv) you want to "
                   "validate. Nothing is analyzed yet — this just selects "
                   "which episode the buttons below act on.")
        self._video_var = tk.StringVar(value="(no episode selected)")
        tk.Label(s1, textvariable=self._video_var, fg="#333333",
                 font=("TkDefaultFont", 8), wraplength=260,
                 anchor="w", justify="left").pack(fill=tk.X, pady=(4, 0))
        self._status_var = tk.StringVar(value="")
        self._status_lbl = tk.Label(s1, textvariable=self._status_var,
                                    font=("TkDefaultFont", 8, "bold"),
                                    anchor="w")
        self._status_lbl.pack(fill=tk.X)
        _Tip(self._status_lbl,
             "Workflow status for this episode:\n"
             "template → you still need to hand-code it\n"
             "coded → ready to run detection\n"
             "detected → ready to compare\n"
             "compared → annotate the errors\n"
             "annotated → done. Next episode!")

        # Step 2 — hand-code
        s2 = tk.LabelFrame(outer, text=" Step 2 — Hand-code it (blind!) ",
                           padx=6, pady=6)
        s2.pack(fill=tk.X, pady=(8, 0))
        tk.Label(s2, text="Watch in VLC, log every transition in the coding "
                          "sheet. Do NOT run Step 3 first.",
                 font=("TkDefaultFont", 8), fg="#aa4400",
                 wraplength=260, justify="left").pack(fill=tk.X)
        b_tmpl = tk.Button(s2, text="Create coding sheet",
                           command=self._create_template)
        b_tmpl.pack(fill=tk.X, pady=2)
        _Tip(b_tmpl, "Creates a blank <episode>_manual.csv in the validation "
                     "folder with columns: timestamp_hms, timestamp_sec, type, "
                     "notes.\n\nFill one row per transition while watching in "
                     "VLC. Types: hard_cut, dissolve, fade_in, fade_out, other.\n\n"
                     "Refuses to overwrite an existing sheet, so your work is safe.")
        b_open = tk.Button(s2, text="Open coding sheet (in-app editor)",
                           command=self._open_manual)
        b_open.pack(fill=tk.X, pady=2)
        _Tip(b_open, "Opens this episode's transition coding sheet in CMAT's "
                     "coding editor: an entry bar for fast logging (type a "
                     "time like 2:13, pick the type, Enter — dropdown values "
                     "stick for shot-reverse-shot runs), dropdowns everywhere "
                     "so vocabulary can't drift from the codebook, autosave, "
                     "and timestamp validation.\n\nOlder sheets gain the "
                     "scene_relation column automatically on first save.\n\n"
                     "You can still edit the CSV in Excel/VS Code if you "
                     "prefer — just not both at once.")
        b_events = tk.Button(s2, text="Open event coding sheet (fantasy)",
                             command=self._open_events_sheet, fg="#884400")
        b_events.pack(fill=tk.X, pady=2)
        _Tip(b_events, "Opens (creating if needed) this episode's fantastical-"
                       "event coding sheet in the same editor, with dropdowns "
                       "for the 7 event types, narrative relevance "
                       "(integral/incidental), and repeat (new/repeat).\n\n"
                       "Rules: EVENT_CODEBOOK.md — remember premise vs event "
                       "(a talking dog is premise, not an event).")
        b_code = tk.Button(s2, text="View codebook (coding rules)",
                           command=self._open_codebook)
        b_code.pack(fill=tk.X, pady=2)
        _Tip(b_code, "Opens CODEBOOK.md — the frozen rules for what counts as "
                     "each transition type, timestamp conventions, and the "
                     "decision rules for tricky cases (title overlays, "
                     "fade-out+fade-in pairs, zooms are-not-cuts, etc.).")

        # Step 3 — detection
        s3 = tk.LabelFrame(outer, text=" Step 3 — Run tool detection ",
                           padx=6, pady=6)
        s3.pack(fill=tk.X, pady=(8, 0))
        row = tk.Frame(s3); row.pack(fill=tk.X)
        tk.Label(row, text="Detector:", font=("TkDefaultFont", 8)).pack(side=tk.LEFT)
        self._detector_var = tk.StringVar(value="content")
        det_cb = ttk.Combobox(row, textvariable=self._detector_var,
                              values=["content", "adaptive"],
                              state="readonly", width=9)
        det_cb.pack(side=tk.LEFT, padx=(4, 8))
        tk.Label(row, text="Threshold:", font=("TkDefaultFont", 8)).pack(side=tk.LEFT)
        self._threshold_var = tk.StringVar(value="27.0")
        tk.Entry(row, textvariable=self._threshold_var, width=6).pack(side=tk.LEFT, padx=4)
        _Tip(row, "Detector: 'content' is what the analysis engine ships "
                  "(threshold 27 default). 'adaptive' compares each frame to a "
                  "rolling average — better at gradual transitions; use "
                  "threshold ~3 with it.\n\nChanging these creates a separate "
                  "detections file per configuration, so you can compare "
                  "configurations against the same hand-coding.")
        row2 = tk.Frame(s3); row2.pack(fill=tk.X, pady=(4, 0))
        self._dissolves_var = tk.BooleanVar(value=True)
        chk = tk.Checkbutton(row2, text="Dissolve pass", variable=self._dissolves_var,
                             font=("TkDefaultFont", 8))
        chk.pack(side=tk.LEFT)
        _Tip(chk, "The experimental second pass that hunts for dissolves "
                  "(gradual cross-fades) the hard-cut detector misses. Uncheck "
                  "to test the hard-cut detector alone (the configuration the "
                  "public index currently uses).")
        tk.Label(row2, text="floor:", font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(8, 0))
        self._floor_var = tk.StringVar(value="3.0")
        tk.Entry(row2, textvariable=self._floor_var, width=5).pack(side=tk.LEFT, padx=2)
        tk.Label(row2, text="min frames:", font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(6, 0))
        self._minframes_var = tk.StringVar(value="15")
        tk.Entry(row2, textvariable=self._minframes_var, width=5).pack(side=tk.LEFT, padx=2)
        _Tip(row2, "Dissolve pass settings.\n\nfloor = how much frame-to-frame "
                   "change counts as 'something happening' (lower = more "
                   "sensitive).\nmin frames = how many consecutive frames of "
                   "change are needed to call it a dissolve (15 ≈ half a second "
                   "at 30fps).\n\nThese are the knobs the parameter sweep tunes.")
        self._btn_detect = tk.Button(s3, text="Run detection",
                                     command=self._run_detection, fg="#5500aa")
        self._btn_detect.pack(fill=tk.X, pady=(6, 2))
        _Tip(self._btn_detect,
             "Runs the detector on the whole episode and writes a detections "
             "CSV + a manifest recording every setting (for reproducibility).\n\n"
             "First run decodes the full video — takes a few minutes. Caches "
             "make later runs (and sweeps) near-instant.\n\n"
             "⚠ Only run this AFTER your hand-coding is saved. Never open the "
             "detections file until your coding is done (blind-coding rule).")
        self._progress = ttk.Progressbar(s3, mode="determinate", maximum=1.0)
        self._progress.pack(fill=tk.X, pady=(2, 0))
        self._detect_status = tk.StringVar(value="")
        tk.Label(s3, textvariable=self._detect_status,
                 font=("TkDefaultFont", 8), fg="#555555",
                 wraplength=260, anchor="w", justify="left").pack(fill=tk.X)

        # Step 4 — compare
        s4 = tk.LabelFrame(outer, text=" Step 4 — Compare & annotate ",
                           padx=6, pady=6)
        s4.pack(fill=tk.X, pady=(8, 0))
        rowc = tk.Frame(s4); rowc.pack(fill=tk.X)
        tk.Label(rowc, text="Coded window:", font=("TkDefaultFont", 8)).pack(side=tk.LEFT)
        self._start_var = tk.StringVar(value="")
        tk.Entry(rowc, textvariable=self._start_var, width=6).pack(side=tk.LEFT, padx=2)
        tk.Label(rowc, text="to", font=("TkDefaultFont", 8)).pack(side=tk.LEFT)
        self._end_var = tk.StringVar(value="")
        tk.Entry(rowc, textvariable=self._end_var, width=6).pack(side=tk.LEFT, padx=2)
        tk.Label(rowc, text="tol ±", font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(6, 0))
        self._tol_var = tk.StringVar(value="2.0")
        tk.Entry(rowc, textvariable=self._tol_var, width=4).pack(side=tk.LEFT, padx=2)
        _Tip(rowc, "Coded window: if you only hand-coded part of the episode "
                   "(e.g. the first story), enter the range here — like 0:00 "
                   "to 8:12 — so tool detections outside what you coded aren't "
                   "counted as false alarms. Leave empty if you coded the "
                   "whole episode. Decide the window BEFORE watching.\n\n"
                   "Tolerance: how close (seconds) a tool detection must be to "
                   "your timestamp to count as the same event. ±2s default; "
                   "use ±1s for fast-cut shows where cuts come closer together "
                   "than 2s.")
        self._btn_compare = tk.Button(s4, text="Compare  →  scores + error list",
                                      command=self._run_compare, fg="#aa0055")
        self._btn_compare.pack(fill=tk.X, pady=(6, 2))
        _Tip(self._btn_compare,
             "Grades the tool against your hand-coding:\n"
             "TP = both found it · FN = tool missed it · FP = tool invented "
             "it · type mismatch = right time, wrong label.\n\n"
             "Opens a results window with the score table and an annotation "
             "grid where you give every error a failure reason — that's the "
             "error taxonomy, the most valuable output of the whole exercise.\n\n"
             "Safe to re-run after fixing your coding: existing annotations "
             "are preserved.")

        # Step 5 — advanced
        s5 = tk.LabelFrame(outer, text=" Advanced ", padx=6, pady=6)
        s5.pack(fill=tk.X, pady=(8, 0))
        b_sweep = tk.Button(s5, text="Parameter sweep (tuning episodes only)",
                            command=self._open_sweep)
        b_sweep.pack(fill=tk.X, pady=2)
        _Tip(b_sweep, "Tries a grid of dissolve settings (floor × min frames) "
                      "against this episode's hand-coding and shows which "
                      "combination scores best.\n\n⚠ Methodology rule: only "
                      "sweep on episodes you designated as TUNING episodes. "
                      "Tuning on the episodes you report results from is "
                      "overfitting — decide the tuning/test split before "
                      "looking at any results, and log it in VALIDATION_LOG.md.")
        b_sum = tk.Button(s5, text="Cross-episode summary",
                          command=self._show_summary)
        b_sum.pack(fill=tk.X, pady=2)
        _Tip(b_sum, "Combines every comparison you've run (all episodes, all "
                    "shows) into one precision/recall/F1 table — the numbers "
                    "that go in the paper's validation section.")

    # ── Helpers ──────────────────────────────────────────────────────────

    def _vdir(self) -> Path:
        return get_validation_dir()

    def _need_video(self) -> Path | None:
        if self._video is None:
            messagebox.showinfo(
                "Pick an episode first",
                "Choose the episode video in Step 1 first — the other steps "
                "act on that episode.", parent=self)
            return None
        return self._video

    def _refresh_status(self) -> None:
        if self._video is None:
            self._status_var.set("")
            return
        st = episode_status(self._video, self._vdir())
        label, color = _STEP_LABELS.get(st["step"], ("?", "#000000"))
        extra = ""
        if st["step"] == "coded":
            extra = f"  ({st['coded_rows']} transitions coded)"
        elif st["step"] in ("compared", "annotated") and st["errors_total"]:
            extra = f"  (errors annotated: {st['errors_annotated']}/{st['errors_total']})"
        self._status_var.set(f"Status: {label}{extra}")
        self._status_lbl.config(fg=color)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self._btn_detect.config(state=state)
        self._btn_compare.config(state=state)

    # ── Step handlers ────────────────────────────────────────────────────

    def _choose_video(self) -> None:
        root = self._get_root_folder()
        initial = str(root) if root else str(Path.home())
        path = filedialog.askopenfilename(
            parent=self, title="Choose the episode to validate",
            initialdir=initial,
            filetypes=[("Video files", "*.mp4 *.mkv *.avi *.mov"),
                       ("All files", "*.*")])
        if not path:
            return
        self._video = Path(path)
        self._video_var.set(self._video.name)
        self._refresh_status()

    def _choose_from_sample(self) -> None:
        """Pick an episode out of an Episode Sampler draw."""
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

        win = tk.Toplevel(self)
        win.title(f"Sample: {Path(path).parent.name}")
        win.geometry("620x340")
        tk.Label(win, text=f"{len(eps)} episode(s) in this sample — "
                           f"pick one to validate:",
                 padx=10, pady=6, anchor="w").pack(fill=tk.X)
        lb = tk.Listbox(win, font=("Consolas", 8), activestyle="none")
        for p in eps:
            mark = "" if p.exists() else "  [file missing]"
            lb.insert(tk.END, f"{p.name}{mark}")
        lb.pack(fill=tk.BOTH, expand=True, padx=10)
        lb.selection_set(0)

        def ok() -> None:
            sel = lb.curselection()
            if sel:
                self._video = eps[sel[0]]
                self._video_var.set(self._video.name)
                self._refresh_status()
            win.destroy()

        tk.Button(win, text="Use this episode", command=ok,
                  width=18).pack(pady=8)
        win.transient(self.winfo_toplevel())
        win.grab_set()

    def _create_template(self) -> None:
        video = self._need_video()
        if not video:
            return
        try:
            out = write_template(video, self._vdir())
        except FileExistsError as exc:
            messagebox.showinfo(
                "Coding sheet already exists",
                f"A coding sheet for this episode already exists:\n\n{exc}\n\n"
                "It was NOT overwritten (your coding is safe). Use 'Open "
                "coding sheet' to continue working on it.", parent=self)
            self._refresh_status()
            return
        messagebox.showinfo(
            "Coding sheet created",
            f"Blank coding sheet created:\n\n{out}\n\nNow watch the episode "
            "in VLC and log every transition — one row each.\n\nRemember the "
            "golden rule: finish and save your coding BEFORE running Step 3, "
            "and never open the tool's detections file while coding.",
            parent=self)
        self._refresh_status()

    def _open_manual(self) -> None:
        video = self._need_video()
        if not video:
            return
        manual = find_manual(video, self._vdir())
        if manual is None:
            messagebox.showinfo(
                "No coding sheet yet",
                "There's no coding sheet for this episode yet — click "
                "'Create coding sheet' first.", parent=self)
            return
        from gui_coding_editor import CodingSheetEditor
        CodingSheetEditor(self, manual, schema_name="transitions",
                          video_path=video)

    def _open_events_sheet(self) -> None:
        video = self._need_video()
        if not video:
            return
        from analyzer.event_coding import write_event_template
        from gui_coding_editor import CodingSheetEditor
        sheet = find_latest(f"{video.stem}_events.csv", self._vdir())
        if sheet is None:
            # prefix fallback for shortened names
            suffix = "_events.csv"
            cands = [p for p in self._vdir().rglob(f"*{suffix}")
                     if len(p.name) - len(suffix) >= 8
                     and video.stem.lower().startswith(
                         p.name[:-len(suffix)].lower())]
            sheet = (sorted(cands, key=lambda p: p.stat().st_mtime)[-1]
                     if cands else None)
        if sheet is None:
            try:
                sheet = write_event_template(video, self._vdir())
            except FileExistsError as exc:
                sheet = Path(str(exc))
        CodingSheetEditor(self, sheet, schema_name="events",
                          video_path=video)

    def _open_codebook(self) -> None:
        cb = find_latest("CODEBOOK.md", self._vdir())
        if cb is None:
            messagebox.showinfo(
                "No codebook found",
                "CODEBOOK.md was not found in the validation folder.\n\n"
                "The codebook holds your frozen coding rules — definitions "
                "of each transition type and the decision rules for tricky "
                "cases. Create one before your first coding session so your "
                "rules stay consistent across episodes.", parent=self)
            return
        os.startfile(str(cb))

    def _open_folder(self) -> None:
        vdir = self._vdir()
        vdir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(vdir))

    def _show_guide(self) -> None:
        win = tk.Toplevel(self)
        win.title("Validation — step-by-step guide")
        win.geometry("560x640")
        frame = tk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(frame, orient=tk.VERTICAL)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        txt = tk.Text(frame, wrap=tk.WORD, font=("Consolas", 9),
                      yscrollcommand=sb.set, padx=10, pady=8)
        txt.insert("1.0", GUIDE_TEXT)
        txt.config(state=tk.DISABLED)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=txt.yview)

    # ── Detection (worker thread) ────────────────────────────────────────

    def _run_detection(self) -> None:
        video = self._need_video()
        if not video or self._busy:
            return
        st = episode_status(video, self._vdir())
        if st["coded_rows"] == 0:
            if not messagebox.askyesno(
                    "Coding not found",
                    "No hand-coding found for this episode yet.\n\nRunning "
                    "detection now is allowed — but do NOT open the "
                    "detections file until your coding is finished and saved "
                    "(blind-coding rule).\n\nRun detection anyway?",
                    parent=self):
                return
        try:
            threshold = float(self._threshold_var.get())
            floor = float(self._floor_var.get())
            minframes = int(self._minframes_var.get())
        except ValueError:
            messagebox.showerror("Bad settings",
                                 "Threshold, floor, and min frames must be "
                                 "numbers.", parent=self)
            return
        self._set_busy(True)
        self._progress.config(mode="indeterminate")
        self._progress.start(12)
        self._detect_status.set("Starting…")

        def worker() -> None:
            try:
                res = export_detections(
                    video, self._vdir(),
                    detector=self._detector_var.get(), threshold=threshold,
                    noise_floor=floor, min_frames=minframes,
                    dissolves_on=self._dissolves_var.get(),
                    progress_cb=lambda f: self._q.put(("progress", f)),
                    status_cb=lambda m: self._q.put(("status", m)))
                self._q.put(("done_export", res))
            except Exception as exc:                       # noqa: BLE001
                self._q.put(("error", f"Detection failed: {exc}"))

        threading.Thread(target=worker, daemon=True).start()

    # ── Compare ──────────────────────────────────────────────────────────

    def _run_compare(self) -> None:
        video = self._need_video()
        if not video or self._busy:
            return
        manual = find_manual(video, self._vdir())
        if manual is None:
            messagebox.showinfo(
                "No coding sheet",
                "No hand-coding found for this episode. Create the coding "
                "sheet (Step 2) and code the episode first — the comparison "
                "needs your answer key.", parent=self)
            return
        detections = sorted(self._vdir().rglob(f"{video.stem}__*_detections.csv"))
        if not detections:
            messagebox.showinfo(
                "No detections",
                "The tool hasn't been run on this episode yet — run Step 3 "
                "first.", parent=self)
            return
        det_path = detections[-1]
        if len(detections) > 1:
            # Let the user pick which configuration to grade.
            det_path = self._pick_detections(detections) or det_path
        try:
            tol = float(self._tol_var.get())
        except ValueError:
            messagebox.showerror("Bad tolerance",
                                 "Tolerance must be a number of seconds.",
                                 parent=self)
            return
        warns: list[str] = []
        try:
            res = compare_detections(
                det_path, manual, tolerance=tol,
                start=self._start_var.get() or None,
                end=self._end_var.get() or None,
                warn_cb=warns.append)
        except Exception as exc:                            # noqa: BLE001
            messagebox.showerror("Compare failed", str(exc), parent=self)
            return
        if warns:
            messagebox.showwarning("Check your coding sheet",
                                   "\n".join(warns), parent=self)
        ComparisonWindow(self, res, on_saved=self._refresh_status)
        self._refresh_status()

    def _pick_detections(self, options: list[Path]) -> Path | None:
        win = tk.Toplevel(self)
        win.title("Which detection run?")
        tk.Label(win, text="Multiple detection configurations exist for this "
                           "episode.\nPick the one to grade:",
                 justify="left", padx=10, pady=6).pack(anchor="w")
        var = tk.StringVar(value=str(options[-1]))
        for p in options:
            tag = p.stem.split("__", 1)[1].replace("_detections", "") \
                if "__" in p.stem else p.name
            tk.Radiobutton(win, text=tag, value=str(p), variable=var,
                           padx=14).pack(anchor="w")
        chosen: list[Path | None] = [None]

        def ok() -> None:
            chosen[0] = Path(var.get())
            win.destroy()

        tk.Button(win, text="OK", command=ok, width=12).pack(pady=8)
        win.transient(self.winfo_toplevel())
        win.grab_set()
        self.wait_window(win)
        return chosen[0]

    # ── Sweep & summary ──────────────────────────────────────────────────

    def _open_sweep(self) -> None:
        video = self._need_video()
        if not video:
            return
        manual = find_manual(video, self._vdir())
        if manual is None:
            messagebox.showinfo(
                "No coding sheet",
                "The sweep grades every parameter combination against your "
                "hand-coding, so the episode must be coded first.",
                parent=self)
            return
        SweepWindow(self, video, manual,
                    start=self._start_var.get(), end=self._end_var.get(),
                    tolerance=self._tol_var.get(),
                    detector=self._detector_var.get(),
                    threshold=self._threshold_var.get())

    def _show_summary(self) -> None:
        res = aggregate_summary(self._vdir())
        if not res["n_files"]:
            messagebox.showinfo(
                "Nothing to summarize",
                "No comparison results found yet. Run Step 4 on at least one "
                "episode first.", parent=self)
            return
        win = tk.Toplevel(self)
        win.title(f"Validation summary — {res['n_files']} comparison(s)")
        tk.Label(win, text=f"Aggregated over {res['n_files']} comparison "
                           f"file(s), all episodes:",
                 padx=10, pady=6).pack(anchor="w")
        tree = _score_tree(win, res["rows"])
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        tk.Label(win, text="Report these numbers with the raw TP/FP/FN counts "
                           "— an F1 of 0.9 on 10 events means far less than "
                           "on 300 events.",
                 font=("TkDefaultFont", 8), fg="#555555",
                 wraplength=420, justify="left", padx=10).pack(anchor="w",
                                                               pady=(0, 8))

    # ── Queue polling ────────────────────────────────────────────────────

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "status":
                    self._detect_status.set(payload)
                elif kind == "progress":
                    if str(self._progress.cget("mode")) != "determinate":
                        self._progress.stop()
                        self._progress.config(mode="determinate")
                    self._progress["value"] = payload
                    self._detect_status.set(
                        f"Scoring frames… {payload*100:.0f}%")
                elif kind == "done_export":
                    self._progress.stop()
                    self._progress.config(mode="determinate")
                    self._progress["value"] = 0
                    self._set_busy(False)
                    res = payload
                    n_d = res["n_dissolves"]
                    self._detect_status.set(
                        f"Done — {res['n_hard_cuts']} hard cuts"
                        + (f", {n_d} dissolve candidates" if self._dissolves_var.get() else "")
                        + f"  [{res['tag']}]")
                    self._refresh_status()
                elif kind == "error":
                    self._progress.stop()
                    self._progress.config(mode="determinate")
                    self._progress["value"] = 0
                    self._set_busy(False)
                    self._detect_status.set("")
                    messagebox.showerror("Validation", payload, parent=self)
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)


# ---------------------------------------------------------------------------
# Comparison results window (scores + annotation grid)
# ---------------------------------------------------------------------------

def _score_tree(parent: tk.Misc, rows: list[dict]) -> ttk.Treeview:
    cols = ("type", "TP", "FP", "FN", "precision", "recall", "F1")
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                        height=min(len(rows) + 1, 8))
    widths = {"type": 90, "TP": 40, "FP": 40, "FN": 40,
              "precision": 70, "recall": 70, "F1": 60}
    for c in cols:
        tree.heading(c, text=c)
        tree.column(c, width=widths[c], anchor="center")
    for r in rows:
        tags = ("total",) if r["type"] in ("ALL", "AGGREGATE") else ()
        tree.insert("", tk.END, values=[r[c] for c in cols], tags=tags)
    tree.tag_configure("total", font=("TkDefaultFont", 9, "bold"))
    return tree


class ComparisonWindow(tk.Toplevel):
    """Score table + error-annotation grid for one comparison run."""

    def __init__(self, parent: tk.Misc, res: dict, on_saved=None) -> None:
        super().__init__(parent)
        self._res = res
        self._on_saved = on_saved
        self._dirty = False
        self.title(f"Validation results — {res['ep_stem']}  [{res['tag']}]")
        self.geometry("760x640")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        hdr = tk.Frame(self, padx=10, pady=6)
        hdr.pack(fill=tk.X)
        window = res["window"]
        win_txt = (f"   window {sec_to_hms(window[0])}–{sec_to_hms(window[1])}"
                   if window else "")
        tk.Label(hdr, text=f"Tool found {res['n_detections']} transitions; "
                           f"you coded {res['n_manual']}.   "
                           f"Tolerance ±{res['tolerance']}s{win_txt}",
                 font=("TkDefaultFont", 9)).pack(anchor="w")

        # Scores
        score_fr = tk.LabelFrame(self, text=" Scores ", padx=8, pady=4)
        score_fr.pack(fill=tk.X, padx=10, pady=(4, 0))
        tree = _score_tree(score_fr, res["summary_rows"])
        tree.pack(fill=tk.X)
        _Tip(tree, "Precision = of what the tool found, how much was real.\n"
                   "Recall = of what was really there, how much it found.\n"
                   "F1 = balance of both; 1.0 is perfect.\n\nRead per-type "
                   "rows, not just ALL: hard cuts and dissolves can behave "
                   "very differently. Note: TP counts a temporal match even "
                   "if the type label differs — label errors show in the "
                   "annotation grid below as 'wrong label'.")

        # Annotation grid
        ann_fr = tk.LabelFrame(
            self, text=" Errors — give each one a failure reason "
                       "(double-click the reason cell) ", padx=8, pady=4)
        ann_fr.pack(fill=tk.BOTH, expand=True, padx=10, pady=(8, 0))

        cols = ("time", "what", "manual", "tool", "reason")
        self._grid = ttk.Treeview(ann_fr, columns=cols, show="headings")
        headings = {"time": "Time", "what": "What happened",
                    "manual": "You coded", "tool": "Tool said",
                    "reason": "Failure reason (double-click)"}
        widths = {"time": 60, "what": 110, "manual": 90, "tool": 90,
                  "reason": 260}
        for c in cols:
            self._grid.heading(c, text=headings[c])
            self._grid.column(c, width=widths[c],
                              anchor="w" if c == "reason" else "center")
        gsb = ttk.Scrollbar(ann_fr, orient=tk.VERTICAL,
                            command=self._grid.yview)
        self._grid.configure(yscrollcommand=gsb.set)
        gsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._grid.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._grid.tag_configure("FN", background="#ffe8e8")
        self._grid.tag_configure("FP", background="#fff4e0")
        self._grid.tag_configure("MM", background="#eef")
        self._grid.bind("<Double-1>", self._edit_reason)
        _Tip(self._grid,
             "Every tool error, one per row:\n"
             "red = miss (you coded it, tool didn't find it)\n"
             "orange = false alarm (tool found it, you didn't code it)\n"
             "blue = wrong label (right time, wrong type)\n\n"
             "Workflow: select a row → 'Copy time' → Ctrl+T in VLC → watch "
             "the moment → double-click the reason cell and pick the tag "
             "that explains the error. If the tool actually found a REAL "
             "transition you missed, fix your coding sheet instead and "
             "re-run Compare (annotations are kept).")

        # Load rows: all detail rows, but grid shows only error rows.
        self._detail_rows = load_match_detail(res["detail_path"])
        self._row_index: dict[str, int] = {}
        for i, r in enumerate(self._detail_rows):
            match = r.get("match", "")
            is_mm = match == "TP" and r.get("type_match") == "no"
            if match not in ("FP", "FN") and not is_mm:
                continue
            t = r.get("manual_hms") or sec_to_hms(float(r["tool_ts"])) \
                if (r.get("manual_hms") or r.get("tool_ts")) else "?"
            what = {"FN": "MISS — tool missed it",
                    "FP": "FALSE ALARM — not real"}.get(match, "wrong label")
            tag = "MM" if is_mm else match
            iid = self._grid.insert(
                "", tk.END,
                values=(t, what, r.get("manual_type") or "—",
                        r.get("tool_type") or "—",
                        r.get("failure_reason") or ""),
                tags=(tag,))
            self._row_index[iid] = i

        # Footer buttons (packed before nothing expands below them)
        foot = tk.Frame(self, padx=10, pady=8)
        foot.pack(fill=tk.X)
        b_copy = tk.Button(foot, text="Copy time (for VLC Ctrl+T)",
                           command=self._copy_time)
        b_copy.pack(side=tk.LEFT)
        _Tip(b_copy, "Copies the selected row's timestamp so you can paste "
                     "it into VLC's go-to-time box (Ctrl+T) and watch the "
                     "moment before deciding the failure reason.")
        self._save_lbl_var = tk.StringVar(value="")
        tk.Label(foot, textvariable=self._save_lbl_var, fg="#007700",
                 font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=10)
        b_save = tk.Button(foot, text="Save annotations", fg="#007700",
                           command=self._save)
        b_save.pack(side=tk.RIGHT)
        _Tip(b_save, "Writes your failure reasons into the match-detail CSV "
                     "on disk. Save before closing — unsaved edits exist "
                     "only in this window.")

    # -- grid editing --------------------------------------------------------

    def _edit_reason(self, event) -> None:
        iid = self._grid.identify_row(event.y)
        col = self._grid.identify_column(event.x)
        if not iid or col != "#5":
            return
        x, y, w, h = self._grid.bbox(iid, col)
        var = tk.StringVar(value=self._grid.set(iid, "reason"))
        combo = ttk.Combobox(self._grid, textvariable=var,
                             values=[t for t, _ in FAILURE_TAGS])
        combo.place(x=x, y=y, width=w, height=h)
        combo.focus_set()

        tip_lbl = tk.Label(self, text="", font=("TkDefaultFont", 8),
                           fg="#333333", bg="#ffffcc", wraplength=700,
                           justify="left", padx=6, pady=3)
        tip_lbl.place(x=10, rely=1.0, y=-34, relwidth=0.97)

        def update_tip(_e=None) -> None:
            tag = var.get()
            desc = next((d for t, d in FAILURE_TAGS if t == tag), "")
            tip_lbl.config(text=f"{tag}: {desc}" if desc else
                           "Custom tag — keep spelling consistent so tags "
                           "aggregate across episodes.")

        def commit(_e=None) -> None:
            self._grid.set(iid, "reason", var.get().strip())
            self._detail_rows[self._row_index[iid]]["failure_reason"] = \
                var.get().strip()
            self._dirty = True
            self._save_lbl_var.set("(unsaved changes)")
            combo.destroy()
            tip_lbl.destroy()

        combo.bind("<<ComboboxSelected>>", lambda e: (update_tip(), commit()))
        combo.bind("<Return>", commit)
        combo.bind("<FocusOut>", commit)
        combo.bind("<KeyRelease>", update_tip)
        update_tip()

    def _copy_time(self) -> None:
        sel = self._grid.selection()
        if not sel:
            return
        t = self._grid.set(sel[0], "time")
        self.clipboard_clear()
        self.clipboard_append(t)
        self._save_lbl_var.set(f"copied {t} — Ctrl+T in VLC to jump there")

    def _save(self) -> None:
        save_match_detail(self._res["detail_path"], self._detail_rows)
        self._dirty = False
        self._save_lbl_var.set("Saved ✓")
        if self._on_saved:
            self._on_saved()

    def _on_close(self) -> None:
        if self._dirty and not messagebox.askyesno(
                "Unsaved annotations",
                "You have unsaved failure-reason annotations. Close anyway "
                "and lose them?", parent=self):
            return
        self.destroy()


# ---------------------------------------------------------------------------
# Sweep window
# ---------------------------------------------------------------------------

class SweepWindow(tk.Toplevel):
    def __init__(self, parent: tk.Misc, video: Path, manual: Path,
                 start: str = "", end: str = "", tolerance: str = "2.0",
                 detector: str = "content", threshold: str = "27.0") -> None:
        super().__init__(parent)
        self._video, self._manual = video, manual
        self.title(f"Parameter sweep — {video.stem}")
        self.geometry("640x520")
        self._q: queue.Queue = queue.Queue()

        warn = tk.Label(
            self, fg="#aa4400", justify="left", wraplength=600, padx=10,
            pady=6, font=("TkDefaultFont", 8),
            text="⚠ Sweep only on TUNING episodes. Using the sweep on episodes "
                 "you plan to report results from is overfitting — the "
                 "reported numbers must come from held-out episodes scored "
                 "once with frozen settings.")
        warn.pack(fill=tk.X)

        row = tk.Frame(self, padx=10)
        row.pack(fill=tk.X)
        tk.Label(row, text="floors:", font=("TkDefaultFont", 8)).pack(side=tk.LEFT)
        self._floors_var = tk.StringVar(value="2,3,4,5")
        tk.Entry(row, textvariable=self._floors_var, width=14).pack(side=tk.LEFT, padx=4)
        tk.Label(row, text="min frames:", font=("TkDefaultFont", 8)).pack(side=tk.LEFT)
        self._frames_var = tk.StringVar(value="6,8,12,15,20")
        tk.Entry(row, textvariable=self._frames_var, width=14).pack(side=tk.LEFT, padx=4)
        _Tip(row, "Comma-separated values to try. Every floor × min-frames "
                  "combination is graded against your hand-coding (dissolve "
                  "F1). Caches make this fast — seconds, not minutes.")
        self._start, self._end, self._tol = start, end, tolerance
        self._detector, self._threshold = detector, threshold

        self._btn = tk.Button(self, text="Run sweep", fg="#5500aa",
                              command=self._run)
        self._btn.pack(padx=10, pady=6, fill=tk.X)

        self._status = tk.StringVar(value="")
        tk.Label(self, textvariable=self._status,
                 font=("TkDefaultFont", 8), fg="#555").pack(anchor="w", padx=10)

        cols = ("floor", "min_frames", "found", "TP", "FP", "FN", "P", "R", "F1")
        self._tree = ttk.Treeview(self, columns=cols, show="headings")
        for c in cols:
            self._tree.heading(c, text=c)
            self._tree.column(c, width=60, anchor="center")
        self._tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 4))
        self._tree.tag_configure("best", background="#e0ffe0")
        _Tip(self._tree, "One row per configuration, graded on dissolve "
                         "detection. Green = best F1. Look for a *region* of "
                         "good settings, not a single lucky cell — a result "
                         "that only works at exactly one value is fragile.")
        self._best_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._best_var,
                 font=("TkDefaultFont", 9, "bold")).pack(anchor="w", padx=10,
                                                         pady=(0, 8))
        self.after(100, self._poll)

    def _run(self) -> None:
        try:
            floors = [float(x) for x in self._floors_var.get().split(",")]
            frames = [int(x) for x in self._frames_var.get().split(",")]
            tol = float(self._tol)
        except ValueError:
            messagebox.showerror("Bad values",
                                 "floors/min frames must be comma-separated "
                                 "numbers.", parent=self)
            return
        self._btn.config(state=tk.DISABLED)
        self._status.set("Running sweep…")

        def worker() -> None:
            try:
                res = run_sweep(
                    self._video, self._manual,
                    detector=self._detector, threshold=float(self._threshold),
                    tolerance=tol, floors=floors, frames=frames,
                    start=self._start or None, end=self._end or None,
                    status_cb=lambda m: self._q.put(("status", m)))
                self._q.put(("done", res))
            except Exception as exc:                        # noqa: BLE001
                self._q.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "status":
                    self._status.set(payload)
                elif kind == "done":
                    self._btn.config(state=tk.NORMAL)
                    self._status.set(f"Grid written to {payload['csv_path'].name}")
                    self._tree.delete(*self._tree.get_children())
                    best = payload["best"]
                    for r in payload["grid_rows"]:
                        is_best = (r["noise_floor"] == best["noise_floor"]
                                   and r["min_frames"] == best["min_frames"])
                        self._tree.insert(
                            "", tk.END,
                            values=(r["noise_floor"], r["min_frames"],
                                    r["n_dissolves_detected"], r["diss_TP"],
                                    r["diss_FP"], r["diss_FN"],
                                    r["diss_precision"], r["diss_recall"],
                                    r["diss_F1"]),
                            tags=("best",) if is_best else ())
                    self._best_var.set(
                        f"Best dissolve F1 = {best['diss_F1']:.3f} at "
                        f"floor {best['noise_floor']}, "
                        f"min frames {best['min_frames']}  "
                        f"(P {best['diss_precision']:.3f} / "
                        f"R {best['diss_recall']:.3f})")
                elif kind == "error":
                    self._btn.config(state=tk.NORMAL)
                    self._status.set("")
                    messagebox.showerror("Sweep failed", payload, parent=self)
        except queue.Empty:
            pass
        self.after(100, self._poll)
