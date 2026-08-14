"""
gui_coding_editor.py — In-app coding sheet editor for CMAT.

A coding FORM, deliberately not a spreadsheet: an entry bar for fast pass-1
logging (type a time, pick a type, Enter — focus returns to the time field and
the type sticks for shot-reverse-shot runs), a sorted grid with dropdown
cell-editing for pass-2 refinement, autosave on by default, and vocabulary
dropdowns populated from the SAME constants the parsers accept — coded values
cannot drift from the codebook.

Handles both sheet types:
  transitions  <episode>_manual.csv   (type, scene_relation, notes)
  events       <episode>_events.csv   (event_type, narrative_relevance,
                                       repeat, duration_sec, notes)

Opening an older sheet upgrades it in place on first save (e.g. adds the
scene_relation column to pre-existing transition sheets).
"""

from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from analyzer.validation import (TRANSITION_TYPES, find_latest,
                                 get_validation_dir, hms_to_sec, sec_to_hms)
from analyzer.event_coding import EVENT_TYPES
from gui_validation import _Tip


# ── Sheet schemas ─────────────────────────────────────────────────────────────
# kind: "time" (validated hms), "choice" (dropdown), "number", "text"

_TRANSITION_CHOICES = ["hard_cut", "dissolve", "fade_in", "fade_out", "other"]
assert set(_TRANSITION_CHOICES) == TRANSITION_TYPES, \
    "editor choices out of sync with analyzer.validation.TRANSITION_TYPES"

SCHEMAS: dict[str, dict] = {
    "transitions": {
        "suffix": "_manual.csv",
        "codebook": "CODEBOOK.md",
        "note_label": "Sheet notes",
        "columns": [
            # key, header shown, width, kind, choices, in entry bar?
            ("timestamp_hms", "Time", 70, "time", None, True),
            ("type", "Type", 100, "choice", _TRANSITION_CHOICES, True),
            ("scene_relation", "Scene rel.", 90, "choice",
             ["", "within", "change"], True),
            ("notes", "Notes", 380, "text", None, True),
        ],
        # written to CSV but not shown (kept for parser compatibility)
        "hidden_keys": ["timestamp_sec"],
    },
    "events": {
        "suffix": "_events.csv",
        "codebook": "EVENT_CODEBOOK.md",
        "note_label": "Show premise / sheet notes",
        "columns": [
            ("timestamp_hms", "Time", 70, "time", None, True),
            ("event_type", "Event type", 120, "choice",
             [t for t, _ in EVENT_TYPES], True),
            ("narrative_relevance", "Relevance", 90, "choice",
             ["", "integral", "incidental"], True),
            ("repeat", "Repeat", 70, "choice", ["", "new", "repeat"], True),
            ("duration_sec", "Dur (s)", 60, "number", None, True),
            ("notes", "Notes", 300, "text", None, True),
        ],
        "hidden_keys": ["timestamp_sec"],
    },
}


def detect_schema(path: Path) -> str:
    return "events" if path.name.endswith("_events.csv") else "transitions"


def _fmt_hms(sec: float) -> str:
    """mm:ss, keeping tenths when the time is sub-second precise.

    Stamped times from the built-in player are millisecond-accurate; rounding
    them to whole seconds would throw away exactly the precision that makes
    tighter compare tolerances meaningful. parse (hms_to_sec) accepts the
    fractional form transparently.
    """
    if sec >= 3600:
        return sec_to_hms(sec)  # >1h: fall back to whole seconds
    m = int(sec // 60)
    s = sec - 60 * m
    if abs(s - round(s)) < 0.05:
        return f"{m:02d}:{int(round(s)):02d}"
    return f"{m:02d}:{s:04.1f}"


# ── Column tooltips (attached to the entry-bar widgets) ───────────────────────

_EVENT_TYPE_TIP = (
    "Pick the CORE violation (one event = one row; if two violations co-occur "
    "in one gag, pick the dominant one and mention the other in notes):\n\n"
    + "\n".join(f"• {t} — {desc}" for t, desc in EVENT_TYPES)
    + "\n\nRemember premise vs event: a STANDING impossibility (talking "
      "animals as the show's premise) is NOT an event — only discrete "
      "impossible occurrences with an onset are. Record the premise in the "
      "sheet-notes field above instead."
)

_RELEVANCE_TIP = (
    "How load-bearing is this event for the story?\n\n"
    "• integral — the plot does not advance without it (the magic that "
    "drives the episode). Test: would a plot summary mention it?\n"
    "• incidental — decorative gag; the story would proceed identically "
    "without it.\n\n"
    "Why it matters: the current mechanism debate (Hinten & Imuta 2026, "
    "SPECT) predicts narrative-disruptive events cost young viewers more "
    "than decorative ones — this column is what lets that be tested. "
    "Leave blank only if genuinely torn, and add a note."
)

_REPEAT_TIP = (
    "Is this impossibility new this episode?\n\n"
    "• new — first time THIS episode that this character/object does this "
    "kind of impossible thing.\n"
    "• repeat — essentially the same impossibility seen earlier this episode "
    "(the fifth time the character flies).\n\n"
    "Why it matters: the schema account predicts children habituate to "
    "repeated impossibilities. Code every occurrence — never skip an event "
    "because it feels expected (Rule 8); this column carries that hypothesis "
    "instead. Easiest to fill in pass 2, when you can see the whole list."
)

_SCENE_REL_TIP = (
    "For hard cuts only — does the viewer's mental model of WHERE we are and "
    "WHO is here survive the cut?\n\n"
    "• within — same scene: shot-reverse-shot dialogue, cutaway to a detail "
    "in the same space, reframing/zoom, POV shot.\n"
    "• change — the viewer must reorient: new location, time jump, different "
    "characters/storyline, cut into a fantasy/imagination insert.\n\n"
    "Judge from CONTENT (place/characters/time), not how visually different "
    "the shots look — a close-up can look very different and still be "
    "'within'; two similar snowy fields can be a 'change'. Leave blank on "
    "non-hard-cut rows."
)

_COLUMN_TIPS: dict[str, str] = {
    "event_type": _EVENT_TYPE_TIP,
    "narrative_relevance": _RELEVANCE_TIP,
    "repeat": _REPEAT_TIP,
    "scene_relation": _SCENE_REL_TIP,
}


class VideoPane(tk.Frame):
    """Minimal embedded transport for coding: play/pause, seek, jumps,
    frame-step, speed — and the STAMP button that logs the current frame's
    timestamp as a new row. Not an editor; a transport with a stamp.

    Uses libVLC (python-vlc) so playback has AUDIO — coders rely on sound
    cues (music changes at scene boundaries, act-break fades). Requires VLC
    installed; the editor degrades gracefully to sheet-only when absent.
    """

    def __init__(self, parent: tk.Misc, video_path: Path, on_stamp) -> None:
        super().__init__(parent)
        import vlc  # guarded by caller
        self._vlc = vlc
        self._on_stamp = on_stamp
        self._instance = vlc.Instance("--quiet")
        self._player = self._instance.media_player_new()
        self._player.set_media(self._instance.media_new(str(video_path)))
        self._dragging = False
        self._duration_ms = 0

        surface = tk.Frame(self, bg="black", height=300)
        surface.pack(fill=tk.BOTH, expand=True)
        surface.update_idletasks()
        self._player.set_hwnd(surface.winfo_id())
        self._player.audio_set_volume(80)

        ctl = tk.Frame(self)
        ctl.pack(fill=tk.X, pady=(4, 0))
        self._btn_play = tk.Button(ctl, text="▶ Play", width=8,
                                   command=self.toggle_play)
        self._btn_play.pack(side=tk.LEFT)
        _Tip(self._btn_play, "Play / pause (Space, when not typing in a "
                             "text field).")
        for label, delta, tip in (
                ("−3s", -3.0, "Jump back 3 seconds (Left arrow)."),
                ("−0.5s", -0.5, "Nudge back half a second. (libVLC seeks by "
                                "keyframe, so backward moves are approximate "
                                "— nudge back, then frame-step forward.)"),
                ("+3s", 3.0, "Jump forward 3 seconds (Right arrow).")):
            b = tk.Button(ctl, text=label, width=5,
                          command=lambda d=delta: self.jump(d))
            b.pack(side=tk.LEFT, padx=2)
            _Tip(b, tip)
        b_back = tk.Button(ctl, text="◂ frame", width=7,
                           command=lambda: self.frame_step(-1))
        b_back.pack(side=tk.LEFT, padx=2)
        _Tip(b_back, "Back exactly one frame, paused (W). Useful when you "
                     "step past the boundary.")
        b_step = tk.Button(ctl, text="frame ▸", width=7,
                           command=lambda: self.frame_step(1))
        b_step.pack(side=tk.LEFT, padx=2)
        _Tip(b_step, "Advance exactly one frame, paused (E, like VLC). Use "
                     "for pinning transition boundaries: nudge back 0.5s, "
                     "then frame-step forward to the first frame of the "
                     "incoming shot.")
        tk.Label(ctl, text="speed:", font=("TkDefaultFont", 8)).pack(
            side=tk.LEFT, padx=(8, 0))
        self._rate_var = tk.StringVar(value="1.0")
        rate = ttk.Combobox(ctl, textvariable=self._rate_var, width=4,
                            state="readonly",
                            values=["0.5", "0.75", "1.0", "1.25", "1.5"])
        rate.pack(side=tk.LEFT, padx=2)
        rate.bind("<<ComboboxSelected>>",
                  lambda e: self._player.set_rate(float(self._rate_var.get())))

        self._clock_var = tk.StringVar(value="00:00.0")
        tk.Label(ctl, textvariable=self._clock_var, font=("Consolas", 11),
                 fg="#003080").pack(side=tk.LEFT, padx=10)

        b_stamp = tk.Button(ctl, text="✚ Stamp row", font=("TkDefaultFont", 9, "bold"),
                            fg="white", bg="#007700", padx=10,
                            command=self.stamp)
        b_stamp.pack(side=tk.RIGHT, padx=4)
        _Tip(b_stamp, "THE button (or press S): logs a new row at the exact "
                      "current frame's timestamp, using whatever the type/"
                      "relation dropdowns currently show — so a run of "
                      "identical cuts is just watch → S → watch → S. "
                      "Millisecond-accurate, no typing, no transcription "
                      "errors.")

        self._slider = ttk.Scale(self, from_=0, to=1000, orient=tk.HORIZONTAL)
        self._slider.pack(fill=tk.X, pady=(2, 0))
        self._slider.bind("<ButtonPress-1>", lambda e: self._set_drag(True))
        self._slider.bind("<ButtonRelease-1>", self._on_slider_release)

        self._poll()

    # -- transport ---------------------------------------------------------

    def toggle_play(self) -> None:
        if self._player.is_playing():
            self._player.pause()
            self._btn_play.config(text="▶ Play")
        else:
            self._player.play()
            self._btn_play.config(text="⏸ Pause")

    def jump(self, delta_sec: float) -> None:
        t = max(self._player.get_time() + int(delta_sec * 1000), 0)
        self._player.set_time(t)
        self._update_clock()

    def frame_duration(self) -> float:
        """Seconds per frame from the media's own rate; 0.0 if unknown."""
        if getattr(self, "_fps", 0.0) <= 0:
            try:
                self._fps = float(self._player.get_fps() or 0.0)
            except Exception:
                self._fps = 0.0
        return 1.0 / self._fps if self._fps > 0 else 0.0

    def frame_step(self, frames: int = 1) -> None:
        """Move by whole frames.

        NOT libvlc's next_frame(). Measured 2026-08-11: next_frame() advances
        the picture but leaves get_time() frozen — three steps from 30.000s
        all still reported 30000ms — so a coder who steps to the first frame
        of the incoming shot and then presses Stamp records the timestamp of
        wherever they paused, silently and always early. It also corrupts the
        next seek (a seek to 45.0s landed at 40.040s and never corrected).

        Seeking one frame duration has neither problem and works backwards.
        See validation/VALIDATION_LOG.md 2026-08-11.
        """
        frame = self.frame_duration()
        if frame <= 0:
            return
        if self._player.is_playing():
            self._player.pause()
            self._btn_play.config(text="▶ Play")
        target = max(self._player.get_time() + int(round(frames * frame * 1000)), 0)
        self._player.set_time(target)
        self.after(60, self._update_clock)

    def seek_to(self, sec: float, pause: bool = True) -> None:
        if self._player.get_state() in (self._vlc.State.NothingSpecial,
                                        self._vlc.State.Stopped):
            self._player.play()
            self.after(150, lambda: self._player.pause())
        self._player.set_time(max(int(sec * 1000), 0))
        if pause and self._player.is_playing():
            self._player.pause()
            self._btn_play.config(text="▶ Play")
        self._update_clock()

    def current_sec(self) -> float:
        return max(self._player.get_time(), 0) / 1000.0

    def stamp(self) -> None:
        self._on_stamp(self.current_sec())

    # -- plumbing ----------------------------------------------------------

    def _set_drag(self, v: bool) -> None:
        self._dragging = v

    def _on_slider_release(self, _e=None) -> None:
        self._dragging = False
        if self._duration_ms > 0:
            self._player.set_time(
                int(self._slider.get() / 1000.0 * self._duration_ms))
            self._update_clock()

    def _update_clock(self) -> None:
        self._clock_var.set(_fmt_hms(self.current_sec())
                            if self.current_sec() else "00:00.0")

    def _poll(self) -> None:
        try:
            if self._duration_ms <= 0:
                self._duration_ms = max(self._player.get_length(), 0)
            if self._player.is_playing():
                self._update_clock()
                if not self._dragging and self._duration_ms > 0:
                    self._slider.set(self._player.get_time()
                                     / self._duration_ms * 1000)
        except Exception:
            pass
        self.after(100, self._poll)

    def shutdown(self) -> None:
        try:
            self._player.stop()
            self._player.release()
            self._instance.release()
        except Exception:
            pass


class CodingSheetEditor(tk.Toplevel):
    """Form-style editor for one coding sheet."""

    def __init__(self, parent: tk.Misc, sheet_path: Path,
                 schema_name: str | None = None,
                 video_path: Path | None = None) -> None:
        super().__init__(parent)
        self._path = Path(sheet_path)
        self._schema = SCHEMAS[schema_name or detect_schema(self._path)]
        self._cols = self._schema["columns"]
        self._rows: list[dict] = []        # data rows (have a timestamp)
        self._sheet_note = ""              # timestamp-less notes row (premise)
        self._dirty = False
        self._video_path = video_path
        self._video: VideoPane | None = None
        self._load()
        self._init_choices()
        self._build_ui()
        self._render()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._update_title()

    # ── data I/O ─────────────────────────────────────────────────────────

    def _init_choices(self) -> None:
        """Per-column option lists = schema defaults + any custom values already
        present in the sheet. Researchers can add their own options at entry time
        (editable dropdowns); a new value sticks for the rest of the session, so
        a custom scheme is type-once-then-pick. The default vocabulary still
        matches the codebook exactly for anyone who wants it."""
        self._choices: dict[str, list[str]] = {}
        for key, _l, _w, kind, choices, _b in self._cols:
            if kind != "choice":
                continue
            opts = list(choices or [])
            for r in self._rows:  # absorb custom values found in the file
                v = (r.get(key) or "").strip()
                if v and v not in opts:
                    opts.append(v)
            self._choices[key] = opts

    def _register_choice(self, key: str, value: str) -> None:
        """Add a newly typed custom value to a column's dropdown for reuse."""
        value = (value or "").strip()
        if not value or key not in self._choices or value in self._choices[key]:
            return
        self._choices[key].append(value)
        # refresh the entry-bar combobox so the new option appears immediately
        w = self._entry_widgets.get(key)
        if isinstance(w, ttk.Combobox):
            w.config(values=self._choices[key])

    def _load(self) -> None:
        if not self._path.exists():
            return
        with self._path.open(newline="", encoding="utf-8-sig") as fh:
            for raw in csv.DictReader(fh):
                t = (raw.get("timestamp_hms") or "").strip()
                t_sec = (raw.get("timestamp_sec") or "").strip()
                if not t and not t_sec:
                    # hint/premise row — harvest real notes, drop template hints
                    note = (raw.get("notes") or "").strip()
                    if note and "|" not in (raw.get("type") or "") \
                            and "<" not in note:
                        self._sheet_note = (self._sheet_note + " " + note).strip()
                    continue
                if not t and t_sec:
                    try:
                        t = sec_to_hms(float(t_sec))
                    except ValueError:
                        continue
                row = {key: (raw.get(key) or "").strip()
                       for key, *_ in self._cols}
                row["timestamp_hms"] = t
                self._rows.append(row)
        self._sort_rows()

    def _sort_rows(self) -> None:
        def _key(r: dict) -> float:
            try:
                return hms_to_sec(r["timestamp_hms"])
            except ValueError:
                return float("inf")
        self._rows.sort(key=_key)

    def _save(self, silent: bool = False) -> None:
        keys = [c[0] for c in self._cols]
        header = list(keys)
        # keep timestamp_sec next to timestamp_hms for parser compatibility
        for hidden in self._schema["hidden_keys"]:
            if hidden not in header:
                header.insert(1, hidden)
        self._sort_rows()
        with self._path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            if self._sheet_note:
                w.writerow(["" if k != "notes" else self._sheet_note
                            for k in header])
            for r in self._rows:
                w.writerow([r.get(k, "") for k in header])
        self._dirty = False
        self._update_title()
        if not silent:
            self._status(f"Saved {len(self._rows)} rows")
        else:
            self._status(f"Autosaved {datetime.now():%H:%M:%S} — "
                         f"{len(self._rows)} rows")

    def _autosave(self) -> None:
        if self._autosave_var.get():
            self._save(silent=True)
        else:
            self._update_title()
            self._update_stats()

    # ── UI ───────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.geometry("880x560")

        hdr = tk.Frame(self, padx=8, pady=6)
        hdr.pack(fill=tk.X)

        # Built-in transport (audio playback + frame-exact stamping) when a
        # video is known and python-vlc/VLC are present; sheet-only otherwise.
        if self._video_path is not None and Path(self._video_path).exists():
            try:
                import vlc  # noqa: F401 — availability probe
                self.geometry("900x920")
                self._video = VideoPane(self, Path(self._video_path),
                                        on_stamp=self._stamp_row)
                self._video.pack(fill=tk.BOTH, expand=False, padx=8,
                                 pady=(0, 4), after=hdr)
                self._bind_transport_keys()
            except Exception as exc:               # noqa: BLE001
                self._video = None
                tk.Label(self, text=f"(built-in player unavailable: {exc} — "
                                    f"install VLC to enable; coding sheet "
                                    f"still fully works)",
                         font=("TkDefaultFont", 8), fg="#884400",
                         wraplength=800, justify="left").pack(fill=tk.X,
                                                              padx=8)
        tk.Label(hdr, text=self._path.name,
                 font=("TkDefaultFont", 9, "bold")).pack(side=tk.LEFT)
        b_cb = tk.Button(hdr, text="Codebook",
                         command=self._open_codebook)
        b_cb.pack(side=tk.RIGHT)
        _Tip(b_cb, "Opens the coding rules for this sheet type. When a "
                   "judgment is unclear, the rule lives there — never guess "
                   "silently.")
        mb = tk.Menubutton(hdr, text="Intro ▾", relief=tk.RAISED, padx=6)
        menu = tk.Menu(mb, tearoff=0)
        menu.add_command(label="Save rows as intro template…",
                         command=self._save_intro_dialog)
        menu.add_command(label="Insert intro template…",
                         command=self._insert_intro_dialog)
        mb.config(menu=menu)
        mb.pack(side=tk.RIGHT, padx=6)
        _Tip(mb, "Code a show's title sequence ONCE, then reuse it: save the "
                 "coded intro rows as a named template ('Little Bear S1', "
                 "'SpongeBob 90s intro' — label by season/era, since intros "
                 "change over a show's run) and insert it into any other "
                 "episode's sheet at the right start time. Inserted rows are "
                 "tagged [intro: name] in notes.\n\nAfter inserting, "
                 "spot-check one or two of the intro's transitions — "
                 "syndication or DVD cuts can shift an intro by a second.")
        self._autosave_var = tk.BooleanVar(value=True)
        chk = tk.Checkbutton(hdr, text="Autosave", variable=self._autosave_var)
        chk.pack(side=tk.RIGHT, padx=8)
        _Tip(chk, "Writes the CSV after every add, edit, and delete — no "
                  "unsaved-buffer surprises. Uncheck only if you want to "
                  "experiment without touching the file (then Ctrl+S to save).")

        # Sheet note / premise
        note_row = tk.Frame(self, padx=8)
        note_row.pack(fill=tk.X)
        tk.Label(note_row, text=self._schema["note_label"] + ":",
                 font=("TkDefaultFont", 8)).pack(side=tk.LEFT)
        self._note_var = tk.StringVar(value=self._sheet_note)
        note_entry = tk.Entry(note_row, textvariable=self._note_var,
                              font=("TkDefaultFont", 8))
        note_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))
        note_entry.bind("<FocusOut>", self._commit_sheet_note)
        note_entry.bind("<Return>", self._commit_sheet_note)
        _Tip(note_row, "Stored as a timestamp-less row in the CSV. For event "
                       "sheets, record the show's standing premise here "
                       "(e.g. 'premise: anthropomorphic sea creatures') — "
                       "premises are NOT coded as events.")

        # Entry bar
        bar = tk.LabelFrame(self, text=" Add row (Enter to log; dropdown "
                                       "values stick for runs) ", padx=6, pady=4)
        bar.pack(fill=tk.X, padx=8, pady=(6, 0))
        self._entry_vars: dict[str, tk.StringVar] = {}
        self._entry_widgets: dict[str, tk.Widget] = {}
        for key, label, width, kind, choices, in_bar in self._cols:
            if not in_bar:
                continue
            lbl = tk.Label(bar, text=label, font=("TkDefaultFont", 8))
            lbl.pack(side=tk.LEFT)
            # Column meaning tips go on the LABEL — ttk.Combobox on Windows is a
            # native control that swallows hover events, so a tip on the
            # dropdown itself never fires (see CLAUDE.md). The label does.
            if key in _COLUMN_TIPS:
                lbl.config(fg="#0055aa", cursor="question_arrow")
                _Tip(lbl, _COLUMN_TIPS[key], wraplength=420)
            var = tk.StringVar(value="")
            self._entry_vars[key] = var
            if kind == "choice":
                # Editable (not readonly) so researchers can type their OWN
                # option; it's registered and reusable from then on.
                wdg = ttk.Combobox(bar, textvariable=var,
                                   values=self._choices.get(key, choices),
                                   width=max(8, min(14, width // 8)))
            else:
                wdg = tk.Entry(bar, textvariable=var,
                               width=8 if kind in ("time", "number")
                               else max(16, width // 12))
            wdg.pack(side=tk.LEFT, padx=(2, 8),
                     fill=tk.X if kind == "text" else tk.NONE,
                     expand=(kind == "text"))
            wdg.bind("<Return>", self._add_row)
            self._entry_widgets[key] = wdg
        b_add = tk.Button(bar, text="Add ⏎", command=self._add_row,
                          fg="#005500")
        b_add.pack(side=tk.LEFT)
        _Tip(b_add, "Pass-1 logging loop: pause VLC → type the time (like "
                    "2:13) → pick the type → Enter. Focus returns to the time "
                    "field and the dropdowns KEEP their values, so a run of "
                    "identical cuts is just time-Enter-time-Enter. Times may "
                    "be entered out of order — the grid stays sorted.\n\n"
                    "Custom schemes: the type/relation dropdowns are editable "
                    "— type your OWN option and it's added to the list for the "
                    "rest of the session. Use the built-in codebook vocabulary "
                    "or your lab's own.\n\n"
                    "Hover the blue column labels for what each field means.")

        # Grid
        grid_fr = tk.Frame(self)
        grid_fr.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6, 0))
        col_ids = [c[0] for c in self._cols]
        self._grid = ttk.Treeview(grid_fr, columns=col_ids, show="headings")
        for key, label, width, *_ in self._cols:
            self._grid.heading(key, text=label)
            self._grid.column(key, width=width,
                              anchor="w" if key == "notes" else "center")
        vsb = ttk.Scrollbar(grid_fr, orient=tk.VERTICAL,
                            command=self._grid.yview)
        self._grid.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._grid.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._grid.bind("<Double-1>", self._edit_cell)
        self._grid.bind("<Delete>", self._delete_selected)
        self._grid.bind("<<TreeviewSelect>>", self._on_row_select)
        self._grid.tag_configure("warn", background="#fff0f0")
        _Tip(self._grid, "Pass-2 refinement: double-click any cell to edit "
                         "(dropdown columns stay dropdown). Delete key "
                         "removes the selected row. Rows missing a type are "
                         "highlighted red — they would be skipped or "
                         "mis-scored by the analysis.")

        foot = tk.Frame(self, padx=8, pady=6)
        foot.pack(fill=tk.X)
        self._stats_var = tk.StringVar(value="")
        tk.Label(foot, textvariable=self._stats_var,
                 font=("TkDefaultFont", 8), fg="#555555").pack(side=tk.LEFT)
        self._status_var = tk.StringVar(value="")
        tk.Label(foot, textvariable=self._status_var,
                 font=("TkDefaultFont", 8), fg="#007700").pack(side=tk.LEFT,
                                                               padx=12)
        b_save = tk.Button(foot, text="Save (Ctrl+S)", command=self._save)
        b_save.pack(side=tk.RIGHT)
        self.bind("<Control-s>", lambda e: self._save())

        # start in the time field
        first = self._cols[0][0]
        self._entry_widgets[first].focus_set()

    # ── rendering & stats ────────────────────────────────────────────────

    def _render(self) -> None:
        self._grid.delete(*self._grid.get_children())
        type_key = self._cols[1][0]  # "type" or "event_type"
        for i, r in enumerate(self._rows):
            tags = () if r.get(type_key) else ("warn",)
            self._grid.insert("", tk.END, iid=str(i),
                              values=[r.get(c[0], "") for c in self._cols],
                              tags=tags)
        self._update_stats()

    def _update_stats(self) -> None:
        n = len(self._rows)
        span_txt = ""
        try:
            times = [hms_to_sec(r["timestamp_hms"]) for r in self._rows]
            if times:
                span = max(times) - min(times)
                span_txt = (f" · {sec_to_hms(min(times))}–"
                            f"{sec_to_hms(max(times))}")
                if span > 30:
                    span_txt += f" · {n / (span / 60.0):.1f}/min"
        except ValueError:
            pass
        type_key = self._cols[1][0]
        n_untyped = sum(1 for r in self._rows if not r.get(type_key))
        warn = f" · ⚠ {n_untyped} row(s) missing a type" if n_untyped else ""
        self._stats_var.set(f"{n} row(s){span_txt}{warn}")

    def _status(self, msg: str) -> None:
        self._status_var.set(msg)

    def _update_title(self) -> None:
        star = " *" if self._dirty else ""
        self.title(f"Coding — {self._path.name}{star}")

    # ── entry bar ────────────────────────────────────────────────────────

    def _add_row(self, _event=None) -> None:
        time_key = self._cols[0][0]
        t_raw = self._entry_vars[time_key].get().strip()
        if not t_raw:
            self._flash(self._entry_widgets[time_key])
            return
        try:
            t_norm = _fmt_hms(hms_to_sec(t_raw))
        except ValueError:
            self._flash(self._entry_widgets[time_key])
            self._status(f"'{t_raw}' is not a valid time — use mm:ss")
            return
        row = {}
        for key, _l, _w, kind, _c, in_bar in self._cols:
            row[key] = self._entry_vars[key].get().strip() if in_bar else ""
        row[time_key] = t_norm
        if err := self._validate_number(row):
            self._status(err)
            return
        self._commit_new_row(row)
        # reset time + notes; KEEP choice values for runs
        self._entry_vars[time_key].set("")
        if "notes" in self._entry_vars:
            self._entry_vars["notes"].set("")
        self._entry_widgets[time_key].focus_set()

    def _commit_new_row(self, row: dict) -> None:
        for key, _l, _w, kind, _c, _b in self._cols:
            if kind == "choice":
                self._register_choice(key, row.get(key, ""))
        self._rows.append(row)
        self._sort_rows()
        self._dirty = True
        self._render()
        self._autosave()
        try:
            idx = self._rows.index(row)
            self._grid.see(str(idx))
            self._grid.selection_set(str(idx))
        except ValueError:
            pass

    def _stamp_row(self, sec: float) -> None:
        """Video-pane stamp: new row at the exact current frame's time,
        using whatever the entry-bar dropdowns currently show."""
        time_key = self._cols[0][0]
        row = {}
        for key, _l, _w, _k, _c, in_bar in self._cols:
            row[key] = self._entry_vars[key].get().strip() if in_bar else ""
        row[time_key] = _fmt_hms(sec)
        row["notes"] = ""  # stamp never carries stale notes text
        type_key = self._cols[1][0]
        self._commit_new_row(row)
        self._status(f"stamped {row[time_key]}"
                     + (f" as {row[type_key]}" if row.get(type_key)
                        else " — ⚠ no type selected, fill it in the grid"))

    # ── transport keys (guarded so typing in fields is never hijacked) ────

    def _bind_transport_keys(self) -> None:
        self.bind("<Key>", self._on_key, add=True)

    def _on_key(self, event) -> None:
        if self._video is None:
            return
        w = self.focus_get()
        if isinstance(w, (tk.Entry, ttk.Combobox, tk.Text)):
            return  # never hijack typing
        key = event.keysym.lower()
        if key == "space":
            self._video.toggle_play()
        elif key == "left":
            self._video.jump(-3.0)
        elif key == "right":
            self._video.jump(3.0)
        elif key == "e":
            self._video.frame_step(1)
        elif key == "w":
            self._video.frame_step(-1)
        elif key == "s":
            self._video.stamp()

    def _validate_number(self, row: dict) -> str | None:
        for key, _l, _w, kind, _c, _b in self._cols:
            if kind == "number" and row.get(key):
                try:
                    float(row[key])
                except ValueError:
                    return f"'{row[key]}' is not a number for {key}"
        return None

    def _flash(self, widget: tk.Widget) -> None:
        try:
            orig = widget.cget("background")
            widget.config(background="#ffcccc")
            widget.after(700, lambda: widget.config(background=orig))
        except tk.TclError:
            pass
        widget.focus_set()

    # ── grid editing ─────────────────────────────────────────────────────

    def _edit_cell(self, event) -> None:
        iid = self._grid.identify_row(event.y)
        col = self._grid.identify_column(event.x)
        if not iid or not col:
            return
        ci = int(col[1:]) - 1
        key, _label, _w, kind, choices, _b = self._cols[ci]
        bbox = self._grid.bbox(iid, col)
        if not bbox:
            return
        x, y, w, h = bbox
        var = tk.StringVar(value=self._grid.set(iid, key))
        if kind == "choice":
            # editable so a custom value can be typed here too
            wdg = ttk.Combobox(self._grid, textvariable=var,
                               values=self._choices.get(key, choices))
        else:
            wdg = tk.Entry(self._grid, textvariable=var)
        wdg.place(x=x, y=y, width=w, height=h)
        wdg.focus_set()

        def commit(_e=None) -> None:
            val = var.get().strip()
            if kind == "time" and val:
                try:
                    val = _fmt_hms(hms_to_sec(val))
                except ValueError:
                    wdg.destroy()
                    self._status(f"'{val}' is not a valid time — edit ignored")
                    return
            if kind == "number" and val:
                try:
                    float(val)
                except ValueError:
                    wdg.destroy()
                    self._status(f"'{val}' is not a number — edit ignored")
                    return
            if kind == "choice":
                self._register_choice(key, val)
            self._rows[int(iid)][key] = val
            self._dirty = True
            wdg.destroy()
            self._sort_rows()
            self._render()
            self._autosave()

        wdg.bind("<Return>", commit)
        wdg.bind("<FocusOut>", commit)
        if kind == "choice":
            wdg.bind("<<ComboboxSelected>>", commit)

    def _delete_selected(self, _event=None) -> None:
        sel = self._grid.selection()
        if not sel:
            return
        if not messagebox.askyesno(
                "Delete", f"Delete {len(sel)} row(s)?", parent=self):
            return
        for iid in sorted(sel, key=int, reverse=True):
            del self._rows[int(iid)]
        self._dirty = True
        self._render()
        self._autosave()

    # ── misc ─────────────────────────────────────────────────────────────

    def _commit_sheet_note(self, _event=None) -> None:
        new = self._note_var.get().strip()
        if new != self._sheet_note:
            self._sheet_note = new
            self._dirty = True
            self._autosave()

    def _open_codebook(self) -> None:
        cb = find_latest(self._schema["codebook"], get_validation_dir())
        if cb is None:
            messagebox.showinfo("Not found",
                                f"{self._schema['codebook']} not found in the "
                                f"validation folder.", parent=self)
            return
        os.startfile(str(cb))

    def _on_row_select(self, _event=None) -> None:
        """Pass-2 review: selecting a row seeks the built-in player to that
        moment (paused) so refining a timestamp is click → look → frame-step."""
        if self._video is None:
            return
        sel = self._grid.selection()
        if not sel:
            return
        t = self._rows[int(sel[0])].get(self._cols[0][0], "")
        try:
            self._video.seek_to(hms_to_sec(t), pause=True)
        except ValueError:
            pass

    # ── intro templates ───────────────────────────────────────────────────

    def _rows_with_abs(self) -> list[dict]:
        out = []
        for r in self._rows:
            try:
                out.append({**r, "_abs_sec": hms_to_sec(r["timestamp_hms"])})
            except ValueError:
                continue
        return out

    def _save_intro_dialog(self) -> None:
        from analyzer.intro_templates import save_template
        schema_name = ("events" if self._schema is SCHEMAS["events"]
                       else "transitions")
        win = tk.Toplevel(self)
        win.title("Save intro template")
        frm = tk.Frame(win, padx=12, pady=10)
        frm.pack(fill=tk.BOTH, expand=True)
        tk.Label(frm, text="Saves the coded rows in a time range as a reusable "
                           "intro template.\nName it by season/era — intros "
                           "change over a show's run.",
                 justify="left", font=("TkDefaultFont", 8),
                 fg="#555555").grid(row=0, column=0, columnspan=2,
                                    sticky="w", pady=(0, 8))
        name_var = tk.StringVar()
        from_var = tk.StringVar(value="0:00")
        to_var = tk.StringVar()
        for i, (lbl, var, hint) in enumerate([
                ("Template name", name_var, "e.g.  Little Bear S1 intro"),
                ("Intro starts at", from_var, "usually 0:00"),
                ("Intro ends at", to_var, "e.g.  1:07")], start=1):
            tk.Label(frm, text=lbl + ":").grid(row=i, column=0, sticky="e",
                                               padx=(0, 6), pady=2)
            e = tk.Entry(frm, textvariable=var, width=28)
            e.grid(row=i, column=1, sticky="w", pady=2)
            tk.Label(frm, text=hint, font=("TkDefaultFont", 8),
                     fg="#888888").grid(row=i, column=2, sticky="w", padx=6)

        def ok() -> None:
            try:
                start = hms_to_sec(from_var.get().strip() or "0:00")
                end = hms_to_sec(to_var.get().strip())
            except ValueError:
                messagebox.showerror("Bad time", "Times must be mm:ss.",
                                     parent=win)
                return
            try:
                tpl = save_template(name_var.get(), schema_name,
                                    self._rows_with_abs(), start, end,
                                    source_sheet=self._path.name)
            except ValueError as exc:
                messagebox.showerror("Cannot save", str(exc), parent=win)
                return
            win.destroy()
            self._status(f"intro template '{name_var.get().strip()}' saved "
                         f"({tpl['n_rows']} rows, {tpl['span_sec']:.0f}s)")

        tk.Button(frm, text="Save template", fg="#007700",
                  command=ok).grid(row=4, column=1, sticky="w", pady=(10, 0))
        win.transient(self)
        win.grab_set()

    def _insert_intro_dialog(self) -> None:
        from analyzer.intro_templates import load_templates, apply_template
        schema_name = ("events" if self._schema is SCHEMAS["events"]
                       else "transitions")
        templates = {n: t for n, t in load_templates().items()
                     if t.get("schema") == schema_name}
        if not templates:
            messagebox.showinfo(
                "No intro templates yet",
                f"No saved {schema_name} intro templates. Code an intro once, "
                f"then Intro ▾ → 'Save rows as intro template…'.", parent=self)
            return

        win = tk.Toplevel(self)
        win.title("Insert intro template")
        frm = tk.Frame(win, padx=12, pady=10)
        frm.pack(fill=tk.BOTH, expand=True)
        tk.Label(frm, text="Template:").grid(row=0, column=0, sticky="e",
                                             padx=(0, 6))
        tpl_var = tk.StringVar(value=next(iter(templates)))
        cb = ttk.Combobox(frm, textvariable=tpl_var, state="readonly",
                          values=list(templates), width=34)
        cb.grid(row=0, column=1, sticky="w")
        detail_var = tk.StringVar()
        tk.Label(frm, textvariable=detail_var, font=("TkDefaultFont", 8),
                 fg="#555555").grid(row=1, column=1, sticky="w", pady=(2, 6))

        def _detail(_e=None) -> None:
            t = templates[tpl_var.get()]
            detail_var.set(f"{t['n_rows']} rows over {t['span_sec']:.0f}s · "
                           f"saved {t['created']} from {t['source_sheet']}")
        cb.bind("<<ComboboxSelected>>", _detail)
        _detail()

        tk.Label(frm, text="Intro starts at:").grid(row=2, column=0,
                                                    sticky="e", padx=(0, 6))
        at_var = tk.StringVar(value="0:00")
        tk.Entry(frm, textvariable=at_var, width=10).grid(row=2, column=1,
                                                          sticky="w")
        tk.Label(frm, text="(this episode — cold opens shift intros)",
                 font=("TkDefaultFont", 8), fg="#888888").grid(
            row=2, column=2, sticky="w", padx=6)

        def ok() -> None:
            try:
                at = hms_to_sec(at_var.get().strip() or "0:00")
            except ValueError:
                messagebox.showerror("Bad time", "Start must be mm:ss.",
                                     parent=win)
                return
            name = tpl_var.get()
            tpl = dict(templates[name])
            tpl["_name"] = name
            span = float(tpl.get("span_sec", 0))
            clash = [r for r in self._rows_with_abs()
                     if at <= r["_abs_sec"] <= at + span]
            if clash and not messagebox.askyesno(
                    "Rows already in that range",
                    f"{len(clash)} coded row(s) already exist between "
                    f"{_fmt_hms(at)} and {_fmt_hms(at + span)}. Insert the "
                    f"template anyway (rows will coexist)?", parent=win):
                return
            new_rows = apply_template(tpl, at)
            self._bulk_insert(new_rows)
            win.destroy()
            self._status(f"inserted intro '{name}' at {_fmt_hms(at)} "
                         f"({len(new_rows)} rows)")

        tk.Button(frm, text="Insert", fg="#005500",
                  command=ok).grid(row=3, column=1, sticky="w", pady=(10, 0))
        win.transient(self)
        win.grab_set()

    def _bulk_insert(self, rows_abs: list[dict]) -> None:
        time_key = self._cols[0][0]
        for r in rows_abs:
            row = {key: (r.get(key) or "") for key, *_ in self._cols}
            row[time_key] = _fmt_hms(r["_abs_sec"])
            for key, _l, _w, kind, _c, _b in self._cols:
                if kind == "choice":
                    self._register_choice(key, row.get(key, ""))
            self._rows.append(row)
        self._sort_rows()
        self._dirty = True
        self._render()
        self._autosave()

    def _on_close(self) -> None:
        if self._dirty and not messagebox.askyesno(
                "Unsaved changes",
                "This sheet has unsaved changes. Close anyway and lose them?",
                parent=self):
            return
        if self._video is not None:
            self._video.shutdown()
        self.destroy()
