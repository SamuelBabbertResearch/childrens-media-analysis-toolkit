"""
gui_pipeline.py — the pipeline visualizer.

Answers the question a new user actually has: "what does this program do, in what
order, and where am I in it?" One horizontal flow, five stages, live from disk.

VISUAL LANGUAGE — Snow Leopard / Lion era desktop application (c. 2010)
----------------------------------------------------------------------
Composition, not decoration:

  * A window is chrome + content, not a page. There is no hero heading; the
    window title carries the title. A compact toolbar strip sits under the
    title bar, then the content view, then a thin inspector, then a footer.
  * Content is DENSE. Stage objects are small (about 168x74), sized to their
    text rather than padded out into dashboard cards.
  * Hierarchy comes from typography, alignment, and hairline separators —
    not from drawing a box around every group. The inspector is a property
    list: right-aligned grey labels, left-aligned charcoal values, no border.
  * Blue is an accent. A selected stage gets a blue rim, an outer glow, and a
    faintly blue gradient — it does not become a solid blue slab.
  * Gloss is restrained: a one-pixel white top highlight inside each object,
    a soft one-pixel shadow beneath, 4px corner radius.
  * Type is small: 11-13px through the interface, 15px for the one section
    title. Lucida Grande when present, otherwise tuned Segoe UI.

BEHAVIOUR IS WINDOWS. Only the paint is Mac-flavoured:
  * Tab traversal, arrow keys along the flow, Enter/Space to select, Esc to
    close, Alt+F4, standard title bar and resize, standard file dialogs
  * DPI-aware sizing derived from the real pixels-per-inch
  * Nothing conveyed by colour alone — every status has a text label and a
    distinct glyph, and the whole diagram is mirrored as text in the inspector

Reads from analyzer.pipeline; holds no analysis logic of its own.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from analyzer.pipeline import (
    BLOCKED,
    COMPLETE,
    PARTIAL,
    PENDING,
    Pipeline,
    build_pipelines,
    empty_pipeline,
    trial_rows,
)

# --- palette: cool Snow Leopard greys, restrained Aqua ------------------------
CHROME_TOP = "#f4f5f7"
CHROME_BOT = "#dcdee2"
CHROME_LINE = "#a8abb1"

FLOW_TOP = "#fcfcfd"
FLOW_BOT = "#eceef1"

INSPECTOR_BG = "#f6f7f8"
FOOTER_BG = "#e8eaed"

TEXT = "#2b2d30"
TEXT_DIM = "#6b6f75"
TEXT_FAINT = "#8d9198"
HAIRLINE = "#c8cbd0"

NODE_TOP = "#ffffff"
NODE_BOT = "#e7e9ec"
NODE_BORDER = "#a6a9af"
NODE_GLOSS = "#ffffff"
NODE_SHADOW = "#c2c5ca"

HOV_TOP = "#ffffff"
HOV_BOT = "#eef0f3"

SEL_TOP = "#f6faff"
SEL_BOT = "#d8e6f7"
SEL_BORDER = "#3f76bd"
SEL_GLOW = "#a9c8ea"

ARROW = "#9296a0"

STATUS_COLOR = {
    COMPLETE: "#3c7a36",
    PARTIAL:  "#9a6714",
    PENDING:  "#767b82",
    BLOCKED:  "#8c3a36",
}
# Shape as well as colour, so status survives greyscale and colour blindness.
STATUS_GLYPH = {COMPLETE: "✓", PARTIAL: "▸", PENDING: "·", BLOCKED: "×"}

_FAMILY: str | None = None


def _family(widget) -> str:
    """Lucida Grande if the system has it, otherwise Segoe UI."""
    global _FAMILY
    if _FAMILY is None:
        try:
            fams = set(tkfont.families(widget))
        except Exception:
            fams = set()
        for cand in ("Lucida Grande", "Lucida Sans Unicode", "Segoe UI", "Tahoma"):
            if cand in fams:
                _FAMILY = cand
                break
        else:
            _FAMILY = "Segoe UI"
    return _FAMILY


def _f(widget, px: int, bold: bool = False) -> tuple:
    """Font at an exact pixel height — Tk reads a negative size as pixels."""
    return (_family(widget), -px, "bold") if bold else (_family(widget), -px)


class AquaButton(tk.Canvas):
    """Compact glossy push button — the era's control, not a modern pill."""

    def __init__(self, parent, text: str, command=None, width: int | None = None,
                 bg: str = CHROME_TOP) -> None:
        self._text = text
        self._command = command
        self._pressed = False
        self._enabled = True
        fnt = tkfont.Font(family=_family(parent), size=-11)
        w = width or (fnt.measure(text) + 22)
        super().__init__(parent, width=w, height=19, highlightthickness=0,
                         bd=0, bg=bg, takefocus=True, cursor="hand2")
        self._font = fnt
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Return>", lambda _e: self._fire())
        self.bind("<space>", lambda _e: self._fire())
        self.bind("<FocusIn>", lambda _e: self._paint())
        self.bind("<FocusOut>", lambda _e: self._paint())
        self._paint()

    def _on_press(self, _e) -> None:
        self._pressed = True
        self.focus_set()
        self._paint()

    def _on_release(self, _e) -> None:
        was = self._pressed
        self._pressed = False
        self._paint()
        if was:
            self._fire()

    def _fire(self) -> None:
        if self._command and self._enabled:
            self._command()

    def _paint(self) -> None:
        self.delete("all")
        w = int(self["width"])
        h = int(self["height"])
        top, bot = ("#e3e5e9", "#f3f4f6") if self._pressed else ("#fdfdfe", "#e4e6ea")
        _grad_round(self, 1, 1, w - 1, h - 1, 3, top, bot)
        _outline_round(self, 1, 1, w - 1, h - 1, 3, "#9ea1a7")
        self.create_line(4, 2, w - 4, 2, fill="#ffffff")
        if self.focus_get() is self:
            _outline_round(self, 0, 0, w, h, 4, SEL_BORDER)
        self.create_text(w / 2, h / 2 + (1 if self._pressed else 0),
                         text=self._text, font=self._font, fill=TEXT)


class PipelineView(tk.Frame):
    """The visualizer. Embeddable in a tab or a Toplevel — same widget."""

    NODE_W = 172
    NODE_H = 86
    NODE_GAP = 28

    def __init__(self, parent, app=None, compact: bool = False) -> None:
        super().__init__(parent, bg=INSPECTOR_BG)
        self._app = app
        self._compact = compact
        self._pipelines: list[Pipeline] = []
        self._current: Pipeline | None = None
        self._selected_key: str | None = None
        self._hover_key: str | None = None
        self._nodes: dict[str, tuple[float, float, float, float]] = {}
        self._scale = self._dpi_scale()
        self._prop_rows: list[tk.Widget] = []

        self._build()
        self.refresh()

    # ---- DPI ----

    def _dpi_scale(self) -> float:
        try:
            return max(1.0, min(2.5, self.winfo_fpixels("1i") / 96.0))
        except Exception:
            return 1.0

    def _s(self, n: float) -> int:
        return int(round(n * self._scale))

    # ---- construction ----

    def _build(self) -> None:
        self._build_toolbar()

        self._canvas = tk.Canvas(
            self, bg=FLOW_BOT, highlightthickness=0, bd=0,
            height=self._s(self.NODE_H + 46), takefocus=True)
        self._canvas.pack(fill=tk.BOTH, expand=not self._compact)
        tk.Frame(self, bg=HAIRLINE, height=1).pack(fill=tk.X)

        self._canvas.bind("<Configure>", lambda _e: self._draw())
        self._canvas.bind("<Motion>", self._on_motion)
        self._canvas.bind("<Leave>", self._on_leave)
        self._canvas.bind("<Button-1>", self._on_click)
        self._canvas.bind("<Left>", lambda _e: self._step(-1))
        self._canvas.bind("<Right>", lambda _e: self._step(1))
        self._canvas.bind("<Return>", lambda _e: self._draw())
        self._canvas.bind("<space>", lambda _e: self._draw())
        self._canvas.bind("<FocusIn>", lambda _e: self._draw())
        self._canvas.bind("<FocusOut>", lambda _e: self._draw())

        self._build_inspector()

    def _build_toolbar(self) -> None:
        """Compact strip: gradient, hairline base, small controls."""
        bar = tk.Canvas(self, height=self._s(30), highlightthickness=0, bd=0)
        bar.pack(fill=tk.X)
        self._toolbar = bar

        def _paint(_e=None) -> None:
            bar.delete("bg")
            w = bar.winfo_width() or 800
            h = bar.winfo_height() or self._s(30)
            steps = 14
            for i in range(steps):
                bar.create_rectangle(
                    0, h * i / steps, w, h * (i + 1) / steps + 1, width=0,
                    tags="bg",
                    fill=_blend(CHROME_TOP, CHROME_BOT, i / (steps - 1)))
            bar.create_line(0, h - 1, w, h - 1, fill=CHROME_LINE, tags="bg")
            bar.tag_lower("bg")

        bar.bind("<Configure>", _paint)

        inner = tk.Frame(bar, bg=CHROME_BOT)
        bar.create_window(self._s(10), self._s(15), window=inner, anchor="w")

        tk.Label(inner, text="Pipeline:", bg=CHROME_BOT, fg=TEXT,
                 font=_f(self, 12)).pack(side=tk.LEFT, padx=(0, self._s(5)))

        self._pipe_var = tk.StringVar()
        style = ttk.Style()
        try:
            style.configure("Aqua.TCombobox", arrowsize=11)
        except Exception:
            pass
        self._pipe_cb = ttk.Combobox(inner, textvariable=self._pipe_var,
                                     state="readonly", width=40,
                                     font=_f(self, 12),
                                     style="Aqua.TCombobox")
        self._pipe_cb.pack(side=tk.LEFT)
        self._pipe_cb.bind("<<ComboboxSelected>>", self._on_pipeline_selected)

        AquaButton(inner, "Refresh", command=self.refresh,
                   bg=CHROME_BOT).pack(side=tk.LEFT, padx=(self._s(8), 0))

        self._summary_var = tk.StringVar()
        right = tk.Frame(bar, bg=CHROME_BOT)
        bar.create_window(0, self._s(15), window=right, anchor="e",
                          tags="rightwin")

        def _place_right(_e=None) -> None:
            bar.coords("rightwin", (bar.winfo_width() or 800) - self._s(10),
                       self._s(15))

        bar.bind("<Configure>", _place_right, add="+")
        tk.Label(right, textvariable=self._summary_var, bg=CHROME_BOT,
                 fg=TEXT_DIM, font=_f(self, 11)).pack(side=tk.RIGHT)

    def _build_inspector(self) -> None:
        """Property list — grey labels right, charcoal values left, no boxes."""
        wrap = tk.Frame(self, bg=INSPECTOR_BG)
        wrap.pack(fill=tk.BOTH, expand=True)

        head = tk.Frame(wrap, bg=INSPECTOR_BG)
        head.pack(fill=tk.X, padx=self._s(14), pady=(self._s(9), 0))

        self._detail_title = tk.Label(head, text="", bg=INSPECTOR_BG, fg=TEXT,
                                      font=_f(self, 15, True), anchor="w")
        self._detail_title.pack(side=tk.LEFT)
        self._detail_status = tk.Label(head, text="", bg=INSPECTOR_BG,
                                       font=_f(self, 11, True), anchor="e")
        self._detail_status.pack(side=tk.RIGHT)

        self._detail_expl = tk.Label(
            wrap, text="", bg=INSPECTOR_BG, fg=TEXT_DIM, font=_f(self, 11),
            anchor="w", justify="left")
        self._detail_expl.pack(fill=tk.X, padx=self._s(14),
                               pady=(self._s(1), self._s(7)))

        tk.Frame(wrap, bg=HAIRLINE, height=1).pack(
            fill=tk.X, padx=self._s(14))

        self._props = tk.Frame(wrap, bg=INSPECTOR_BG)
        self._props.pack(fill=tk.BOTH, expand=True, padx=self._s(14),
                         pady=(self._s(7), self._s(8)))
        self._props.columnconfigure(0, minsize=self._s(132))
        self._props.columnconfigure(1, weight=1)

    # ---- data ----

    def refresh(self) -> None:
        root = getattr(self._app, "_root_folder", None) if self._app else None
        try:
            self._pipelines = build_pipelines(root=root)
        except Exception:
            self._pipelines = []
        if not self._pipelines:
            self._pipelines = [empty_pipeline()]

        labels = [self._label_for(p) for p in self._pipelines]
        self._pipe_cb.configure(values=labels)

        keep = self._current.key if self._current else None
        match = next((i for i, p in enumerate(self._pipelines) if p.key == keep), 0)
        self._pipe_var.set(labels[match])
        self._current = self._pipelines[match]
        if self._selected_key is None:
            self._selected_key = self._current.current_stage.key
        self._update_summary()
        self._draw()
        self._show_detail(self._selected_key)

    def _label_for(self, p: Pipeline) -> str:
        n = p.episode_count
        return f"{p.name} — {n} episode{'s' if n != 1 else ''}, {p.progress:.0%}"

    def _on_pipeline_selected(self, _event=None) -> None:
        idx = self._pipe_cb.current()
        if 0 <= idx < len(self._pipelines):
            self._current = self._pipelines[idx]
            self._selected_key = self._current.current_stage.key
            self._update_summary()
            self._draw()
            self._show_detail(self._selected_key)

    def _update_summary(self) -> None:
        p = self._current
        if not p:
            return
        n = len(trial_rows(p))
        self._summary_var.set(
            f"At {p.current_stage.name.lower()} · {n} run{'s' if n != 1 else ''}")

    # ---- drawing ----

    def _draw(self) -> None:
        c = self._canvas
        c.delete("all")
        self._nodes.clear()
        if not self._current:
            return

        w = c.winfo_width() or self._s(900)
        h = c.winfo_height() or self._s(120)
        if w < 50:
            return

        steps = 20
        for i in range(steps):
            c.create_rectangle(0, h * i / steps, w, h * (i + 1) / steps + 1,
                               width=0,
                               fill=_blend(FLOW_TOP, FLOW_BOT, i / (steps - 1)))

        stages = self._current.stages
        n = len(stages)
        nw, nh, gap = self._s(self.NODE_W), self._s(self.NODE_H), self._s(self.NODE_GAP)
        total = nw * n + gap * (n - 1)
        if total > w - self._s(20):                     # shrink to fit, never clip
            nw = max(self._s(104), (w - self._s(20) - gap * (n - 1)) / n)
            total = nw * n + gap * (n - 1)
        x = (w - total) / 2                             # centred, like a content view
        top = (h - nh) / 2

        for i, stage in enumerate(stages):
            self._draw_node(x, top, nw, nh, stage)
            self._nodes[stage.key] = (x, top, x + nw, top + nh)
            if i < n - 1:
                self._draw_arrow(x + nw, top + nh / 2, x + nw + gap)
            x += nw + gap

    def _draw_node(self, x: float, y: float, w: float, h: float, stage) -> None:
        c = self._canvas
        r = self._s(4)
        selected = stage.key == self._selected_key
        hovered = stage.key == self._hover_key and not selected

        if selected:
            _outline_round(c, x - self._s(2), y - self._s(2),
                           x + w + self._s(2), y + h + self._s(2),
                           r + self._s(2), SEL_GLOW)
        c.create_line(x + r, y + h + 1, x + w - r, y + h + 1, fill=NODE_SHADOW)

        if selected:
            top_c, bot_c, border = SEL_TOP, SEL_BOT, SEL_BORDER
        elif hovered:
            top_c, bot_c, border = HOV_TOP, HOV_BOT, NODE_BORDER
        else:
            top_c, bot_c, border = NODE_TOP, NODE_BOT, NODE_BORDER

        _grad_round(c, x, y, x + w, y + h, r, top_c, bot_c)
        _outline_round(c, x, y, x + w, y + h, r, border)
        c.create_line(x + r, y + 1, x + w - r, y + 1, fill=NODE_GLOSS)

        if selected and c.focus_get() is c:
            _outline_round(c, x - self._s(4), y - self._s(4),
                           x + w + self._s(4), y + h + self._s(4),
                           r + self._s(4), SEL_BORDER, dash=(2, 2))

        pad = self._s(9)
        icon_c = SEL_BORDER if selected else TEXT_DIM
        ir = self._s(5)
        icon_cx = x + pad + ir
        _stage_icon(c, stage.key, icon_cx, y + self._s(14), ir, icon_c)

        c.create_text(icon_cx + ir + self._s(7), y + self._s(14), anchor="w",
                      text=stage.name, font=_f(self, 12, True), fill=TEXT)

        # Each text block is placed from the measured extent of the one above,
        # so a subtitle that wraps pushes the rest down instead of colliding
        # with it. Node height is generous enough to absorb one wrap.
        sub = c.create_text(x + pad, y + self._s(29), anchor="nw",
                            text=stage.subtitle, font=_f(self, 11),
                            fill=TEXT_FAINT, width=w - 2 * pad)
        sub_bottom = (c.bbox(sub) or (0, 0, 0, y + self._s(41)))[3]

        c.create_text(x + pad, sub_bottom + self._s(5), anchor="nw",
                      text=stage.headline, font=_f(self, 12, True), fill=TEXT,
                      width=w - 2 * pad)

        col = STATUS_COLOR.get(stage.status, TEXT_DIM)
        c.create_text(x + pad, y + h - self._s(6), anchor="sw",
                      text=f"{STATUS_GLYPH.get(stage.status, '·')} {stage.status_label}",
                      font=_f(self, 11), fill=col, width=w - 2 * pad)

    def _draw_arrow(self, x0: float, y: float, x1: float) -> None:
        c = self._canvas
        c.create_line(x0 + self._s(7), y, x1 - self._s(7), y, fill=ARROW)
        t = self._s(3)
        c.create_polygon(x1 - self._s(7), y - t, x1 - self._s(7), y + t,
                         x1 - self._s(2), y, fill=ARROW, outline=ARROW)

    # ---- interaction ----

    def _hit(self, px: int, py: int) -> str | None:
        for key, (x0, y0, x1, y1) in self._nodes.items():
            if x0 <= px <= x1 and y0 <= py <= y1:
                return key
        return None

    def _on_motion(self, event) -> None:
        key = self._hit(event.x, event.y)
        if key != self._hover_key:
            self._hover_key = key
            self._canvas.configure(cursor="hand2" if key else "")
            self._draw()
            self._show_detail(key or self._selected_key)

    def _on_leave(self, _event) -> None:
        if self._hover_key:
            self._hover_key = None
            self._canvas.configure(cursor="")
            self._draw()
            self._show_detail(self._selected_key)

    def _on_click(self, event) -> None:
        self._canvas.focus_set()
        key = self._hit(event.x, event.y)
        if key:
            self._selected_key = key
            self._draw()
            self._show_detail(key)

    def _step(self, delta: int) -> None:
        if not self._current:
            return
        keys = [s.key for s in self._current.stages]
        try:
            i = keys.index(self._selected_key)
        except ValueError:
            i = 0
        self._selected_key = keys[max(0, min(len(keys) - 1, i + delta))]
        self._draw()
        self._show_detail(self._selected_key)

    # ---- inspector ----

    def _show_detail(self, key: str | None) -> None:
        if not self._current or not key:
            return
        stage = self._current.stage(key)
        if stage is None:
            return

        self._detail_title.configure(text=stage.name)
        self._detail_status.configure(
            text=f"{STATUS_GLYPH.get(stage.status, '·')} {stage.status_label}",
            fg=STATUS_COLOR.get(stage.status, TEXT_DIM))
        self._detail_expl.configure(text=stage.explanation)

        for wdg in self._prop_rows:
            wdg.destroy()
        self._prop_rows.clear()

        row = 0
        for label, value in stage.details:
            lbl = tk.Label(self._props, text=label, bg=INSPECTOR_BG,
                           fg=TEXT_DIM, font=_f(self, 12), anchor="e")
            lbl.grid(row=row, column=0, sticky="e", padx=(0, self._s(10)),
                     pady=self._s(1))
            val = tk.Label(self._props, text=value, bg=INSPECTOR_BG, fg=TEXT,
                           font=_f(self, 12), anchor="w", justify="left")
            val.grid(row=row, column=1, sticky="w", pady=self._s(1))
            self._prop_rows += [lbl, val]
            row += 1

        if stage.next_action:
            sep = tk.Frame(self._props, bg=HAIRLINE, height=1)
            sep.grid(row=row, column=0, columnspan=2, sticky="ew",
                     pady=(self._s(6), self._s(5)))
            nxt_l = tk.Label(self._props, text="Next", bg=INSPECTOR_BG,
                             fg=TEXT_DIM, font=_f(self, 12, True), anchor="e")
            nxt_l.grid(row=row + 1, column=0, sticky="ne",
                       padx=(0, self._s(10)))
            nxt_v = tk.Label(self._props, text=stage.next_action,
                             bg=INSPECTOR_BG, fg=TEXT, font=_f(self, 12),
                             anchor="w", justify="left",
                             wraplength=self._s(560))
            nxt_v.grid(row=row + 1, column=1, sticky="w")
            self._prop_rows += [sep, nxt_l, nxt_v]


class PipelineWindow(tk.Toplevel):
    """Standalone pipeline window — a normal, resizable Windows window."""

    def __init__(self, app, on_close=None) -> None:
        super().__init__(app)
        self._app = app
        self._on_close = on_close
        self.title("Analysis Pipeline")
        self.configure(bg=INSPECTOR_BG)
        self.minsize(720, 400)

        scale = max(1.0, min(2.5, self.winfo_fpixels("1i") / 96.0))
        self.geometry(f"{int(980 * scale)}x{int(468 * scale)}")

        self.view = PipelineView(self, app=app)
        self.view.pack(fill=tk.BOTH, expand=True)

        tk.Frame(self, bg=HAIRLINE, height=1).pack(fill=tk.X)
        footer = tk.Frame(self, bg=FOOTER_BG)
        footer.pack(fill=tk.X)

        self._show_var = tk.BooleanVar(value=_get_show_on_start(app))
        tk.Checkbutton(footer, text="Show at startup", variable=self._show_var,
                       bg=FOOTER_BG, activebackground=FOOTER_BG, fg=TEXT,
                       font=_f(self, 11), command=self._toggle_show_on_start,
                       padx=0).pack(side=tk.LEFT, padx=10, pady=6)
        AquaButton(footer, "Close", command=self._close, width=62,
                   bg=FOOTER_BG).pack(side=tk.RIGHT, padx=10, pady=6)

        self.bind("<Escape>", lambda _e: self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.view._canvas.focus_set()

    def _toggle_show_on_start(self) -> None:
        _set_show_on_start(self._app, self._show_var.get())

    def _close(self) -> None:
        if self._on_close:
            self._on_close()
        self.destroy()


# ---------------------------------------------------------------------------
# "Show at startup" preference — stored in config.json
# ---------------------------------------------------------------------------

def _get_show_on_start(app) -> bool:
    cfg = getattr(app, "_cfg", None) or {}
    return bool(cfg.get("show_pipeline_on_start", True))


def _set_show_on_start(app, value: bool) -> None:
    import json
    from analyzer.config_loader import _base_dir
    if getattr(app, "_cfg", None) is not None:
        app._cfg["show_pipeline_on_start"] = bool(value)
    path = _base_dir() / "config.json"
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
        existing["show_pipeline_on_start"] = bool(value)
        path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Stage icons — small line glyphs, drawn rather than typed, so they stay crisp
# and match the era's 16px toolbar iconography instead of looking like emoji.
# ---------------------------------------------------------------------------

def _stage_icon(c: tk.Canvas, key: str, cx: float, cy: float, r: float,
                color: str) -> None:
    if key == "sampling":                        # a grid with two drawn out
        d = r * 0.72
        for iy in range(3):
            for ix in range(3):
                px, py = cx - d + ix * d, cy - d + iy * d
                on = (ix + iy) % 2 == 0
                c.create_oval(px - r * 0.2, py - r * 0.2, px + r * 0.2,
                              py + r * 0.2, outline=color,
                              fill=color if on else "")
    elif key == "selection":                     # split: two tracks
        c.create_line(cx - r, cy, cx, cy, fill=color)
        c.create_line(cx, cy, cx + r, cy - r * 0.7, fill=color)
        c.create_line(cx, cy, cx + r, cy + r * 0.7, fill=color)
        c.create_oval(cx + r * 0.6, cy - r, cx + r * 1.2, cy - r * 0.4,
                      outline=color, fill=color)
        c.create_oval(cx + r * 0.6, cy + r * 0.4, cx + r * 1.2, cy + r,
                      outline=color, fill=color)
    elif key == "measurement":                   # bar chart
        for i, hgt in enumerate((0.45, 0.95, 0.68)):
            px = cx - r + i * r
            c.create_rectangle(px, cy + r - 2 * r * hgt, px + r * 0.55,
                               cy + r, outline=color, fill=color)
    elif key == "validation":                    # tick in a ring
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color)
        c.create_line(cx - r * 0.45, cy, cx - r * 0.1, cy + r * 0.42,
                      fill=color, width=2)
        c.create_line(cx - r * 0.1, cy + r * 0.42, cx + r * 0.5, cy - r * 0.45,
                      fill=color, width=2)
    else:                                        # results: a small document
        c.create_rectangle(cx - r * 0.7, cy - r, cx + r * 0.7, cy + r,
                           outline=color)
        for i in range(3):
            yy = cy - r * 0.45 + i * r * 0.45
            c.create_line(cx - r * 0.4, yy, cx + r * 0.4, yy, fill=color)


# ---------------------------------------------------------------------------
# Gradient / rounded-rectangle primitives
#
# Tk's canvas has no gradient fill and no clipping, so a gradient rounded
# rectangle is drawn as horizontal slices whose x-inset follows the corner arc.
# Cheap, and it renders identically at any DPI because everything is computed
# from scaled coordinates rather than blitted from a fixed-size image.
# ---------------------------------------------------------------------------

def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _blend(c1: str, c2: str, t: float) -> str:
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return "#%02x%02x%02x" % (int(r1 + (r2 - r1) * t),
                              int(g1 + (g2 - g1) * t),
                              int(b1 + (b2 - b1) * t))


def _corner_inset(dy: float, r: float) -> float:
    if dy >= r or r <= 0:
        return 0.0
    return r - (r * r - (r - dy) * (r - dy)) ** 0.5


def _grad_round(canvas: tk.Canvas, x0: float, y0: float, x1: float, y1: float,
                r: float, top: str, bottom: str) -> None:
    h = max(1.0, y1 - y0)
    steps = max(6, int(min(h, 44)))
    for i in range(steps):
        sy0 = y0 + h * i / steps
        sy1 = y0 + h * (i + 1) / steps
        inset = max(_corner_inset(sy0 - y0, r), _corner_inset(y1 - sy1, r))
        canvas.create_rectangle(x0 + inset, sy0, x1 - inset, sy1 + 0.6,
                                width=0,
                                fill=_blend(top, bottom, i / max(steps - 1, 1)))


def _outline_round(canvas: tk.Canvas, x0: float, y0: float, x1: float,
                   y1: float, r: float, color: str, dash=None) -> None:
    opts = {"outline": color, "style": tk.ARC, "width": 1}
    if dash:
        opts["dash"] = dash
    d = 2 * r
    canvas.create_arc(x0, y0, x0 + d, y0 + d, start=90, extent=90, **opts)
    canvas.create_arc(x1 - d, y0, x1, y0 + d, start=0, extent=90, **opts)
    canvas.create_arc(x0, y1 - d, x0 + d, y1, start=180, extent=90, **opts)
    canvas.create_arc(x1 - d, y1 - d, x1, y1, start=270, extent=90, **opts)
    line = {"fill": color}
    if dash:
        line["dash"] = dash
    canvas.create_line(x0 + r, y0, x1 - r, y0, **line)
    canvas.create_line(x0 + r, y1, x1 - r, y1, **line)
    canvas.create_line(x0, y0 + r, x0, y1 - r, **line)
    canvas.create_line(x1, y0 + r, x1, y1 - r, **line)
