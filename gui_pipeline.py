"""
gui_pipeline.py — pipeline editor: a pannable, zoomable node graph.

The canvas is the application's primary workspace, not a picture of one. Nodes
are independently positioned objects on an unbounded plane; the window is a
viewport onto it. Resizing the window moves the viewport and never the diagram.

RENDERING
---------
Everything is drawn from world coordinates through a single transform
(`_wx`/`_wy`), so there are no hardcoded screen positions and no layout that
depends on window size. Text is drawn with pixel-sized fonts recomputed per
zoom level, which means the font rasteriser renders each size natively — type
stays crisp at every zoom and at 100/125/150/200% display scaling rather than
being a stretched bitmap. Icons, borders, shadows and connectors are vector
primitives scaled by the same transform.

VISUAL LANGUAGE — Snow Leopard / Lion era (c. 2010)
---------------------------------------------------
Cool grey chrome with a hairline base, a faint dotted work surface, nodes with
a one-pixel gloss and a soft shadow at 5px radius, restrained Aqua blue used
only for selection and focus, and compact glossy controls. Type is 11-15px.

BEHAVIOUR IS WINDOWS
--------------------
Ctrl+Z / Ctrl+Y undo and redo, Delete removes the selection, Ctrl+A selects
all, arrow keys nudge, Tab traversal, Esc closes, standard title bar, resize
and maximise. Nothing is conveyed by colour alone: every status carries a
glyph and a word, and the selected node is mirrored as text in the inspector.
"""

from __future__ import annotations

import copy
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, simpledialog, ttk

from analyzer.pipeline import (
    BLOCKED, COMPLETE, PARTIAL, PENDING, build_pipelines,
)
from analyzer.pipeline_graph import (
    NODE_TYPES, TEMPLATES, PipelineDoc, blank_doc, default_doc, delete_doc,
    duplicate_doc, list_docs, node_type, save_doc, unique_name,
)

# --- palette -----------------------------------------------------------------
CHROME_TOP, CHROME_BOT, CHROME_LINE = "#f4f5f7", "#dcdee2", "#a8abb1"
SURFACE_TOP, SURFACE_BOT = "#fbfbfc", "#eef0f3"
GRID_DOT = "#d7dade"
INSPECTOR_BG, FOOTER_BG = "#f6f7f8", "#e8eaed"

TEXT, TEXT_DIM, TEXT_FAINT, HAIRLINE = "#2b2d30", "#6b6f75", "#8d9198", "#c8cbd0"

NODE_TOP, NODE_BOT, NODE_BORDER = "#ffffff", "#e7e9ec", "#a6a9af"
NODE_GLOSS, NODE_SHADOW = "#ffffff", "#c2c5ca"
HOV_TOP, HOV_BOT = "#ffffff", "#eef0f3"
SEL_TOP, SEL_BOT, SEL_BORDER, SEL_GLOW = "#f6faff", "#dbe8f8", "#3f76bd", "#a9c8ea"

WIRE, WIRE_HOT, PORT, PORT_HOT = "#9296a0", "#3f76bd", "#b7bbc2", "#3f76bd"

STATUS_COLOR = {COMPLETE: "#3c7a36", PARTIAL: "#9a6714",
                PENDING: "#767b82", BLOCKED: "#8c3a36"}
STATUS_GLYPH = {COMPLETE: "✓", PARTIAL: "▸", PENDING: "·", BLOCKED: "×"}

MIN_ZOOM, MAX_ZOOM = 0.3, 3.0
_FAMILY: str | None = None


def _family(widget) -> str:
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


def _f(widget, px: float, bold: bool = False) -> tuple:
    """Pixel-sized font — Tk treats a negative size as pixels, so each zoom
    level is rendered natively by the font engine rather than scaled."""
    size = -max(7, int(round(px)))
    return (_family(widget), size, "bold") if bold else (_family(widget), size)


# --- small Aqua-era controls -------------------------------------------------

class AquaButton(tk.Canvas):
    """Compact glossy push button. Width tracks its label; height is fixed."""

    def __init__(self, parent, text, command=None, bg=CHROME_TOP,
                 width=None, tooltip: str = "", scale: float = 1.0) -> None:
        self._text, self._command = text, command
        self._pressed = self._disabled = False
        self._scale = scale
        self._fnt = tkfont.Font(family=_family(parent), size=-int(11 * scale))
        w = width or (self._fnt.measure(text) + int(22 * scale))
        super().__init__(parent, width=w, height=int(20 * scale),
                         highlightthickness=0, bd=0, bg=bg, takefocus=True,
                         cursor="hand2")
        self.bind("<Button-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Return>", lambda _e: self._fire())
        self.bind("<space>", lambda _e: self._fire())
        self.bind("<FocusIn>", lambda _e: self._paint())
        self.bind("<FocusOut>", lambda _e: self._paint())
        if tooltip:
            _Tip(self, tooltip)
        self._paint()

    def set_text(self, text: str) -> None:
        """Relabel and resize. The width is measured from the label, so a
        longer caption set after construction would otherwise be clipped."""
        self._text = text
        self.configure(width=self._fnt.measure(text) + int(22 * self._scale))
        self._paint()

    def set_enabled(self, on: bool) -> None:
        if self._disabled == (not on):
            return
        self._disabled = not on
        self.configure(cursor="" if self._disabled else "hand2")
        self._paint()

    def _press(self, _e):
        if self._disabled:
            return
        self._pressed = True
        self.focus_set()
        self._paint()

    def _release(self, _e):
        was, self._pressed = self._pressed, False
        self._paint()
        if was:
            self._fire()

    def _fire(self):
        if self._command and not self._disabled:
            self._command()

    def _paint(self):
        self.delete("all")
        w, h = int(self["width"]), int(self["height"])
        if self._disabled:
            top, bot, fg, edge = "#f2f3f4", "#e9eaec", "#a9adb3", "#c4c7cc"
        elif self._pressed:
            top, bot, fg, edge = "#dfe1e6", "#f0f1f3", TEXT, "#9ea1a7"
        else:
            top, bot, fg, edge = "#fdfdfe", "#e4e6ea", TEXT, "#9ea1a7"
        _grad_round(self, 1, 1, w - 1, h - 1, 3, top, bot)
        _outline_round(self, 1, 1, w - 1, h - 1, 3, edge)
        if not self._disabled:
            self.create_line(4, 2, w - 4, 2, fill="#ffffff")
        if self.focus_get() is self and not self._disabled:
            _outline_round(self, 0, 0, w, h, 4, SEL_BORDER)
        self.create_text(w / 2, h / 2 + (1 if self._pressed else 0),
                         text=self._text, font=self._fnt, fill=fg)


class _Tip:
    """Plain tooltip. Toolbar controls are compact, so labels need backup."""

    def __init__(self, widget, text: str) -> None:
        self.w, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<Button-1>", self._hide, add="+")

    def _show(self, _e=None):
        if self.tip:
            return
        x = self.w.winfo_rootx() + 6
        y = self.w.winfo_rooty() + self.w.winfo_height() + 4
        self.tip = tk.Toplevel(self.w)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, bg="#fbfbe6", fg=TEXT,
                 font=_f(self.w, 11), bd=1, relief=tk.SOLID,
                 padx=5, pady=2).pack()

    def _hide(self, _e=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class ToolSeparator(tk.Canvas):
    def __init__(self, parent, bg, scale=1.0):
        super().__init__(parent, width=int(9 * scale), height=int(20 * scale),
                         highlightthickness=0, bd=0, bg=bg)
        h = int(20 * scale)
        self.create_line(int(4 * scale), 3, int(4 * scale), h - 3,
                         fill="#c2c5ca")


# --- the editor --------------------------------------------------------------

class PipelineView(tk.Frame):
    """Editor: toolbar, graph canvas, inspector. Embeddable anywhere."""

    def __init__(self, parent, app=None, compact: bool = False) -> None:
        super().__init__(parent, bg=INSPECTOR_BG)
        self._app = app
        self._compact = compact
        self._scale = self._dpi_scale()

        self._docs: list[PipelineDoc] = []
        self._doc: PipelineDoc | None = None
        self._discovered: list = []                # samples found on disk
        self._derived: dict[str, object] = {}      # stage_key -> Stage
        self._source_name: str | None = None

        self._sel: set[str] = set()
        self._hover: str | None = None
        self._hover_port: tuple[str, str] | None = None
        self._drag: dict | None = None
        self._wire: dict | None = None
        self._marquee: tuple[float, float, float, float] | None = None
        self._undo: list[dict] = []
        self._redo: list[dict] = []
        self._prop_rows: list[tk.Widget] = []
        self._dirty = False
        self._save_job: str | None = None

        self._build()
        self.refresh()

    # ---- DPI ----

    def _dpi_scale(self) -> float:
        try:
            return max(1.0, min(3.0, self.winfo_fpixels("1i") / 96.0))
        except Exception:
            return 1.0

    def _s(self, n: float) -> int:
        return int(round(n * self._scale))

    # ---- construction ----

    def _build(self) -> None:
        self._build_toolbar()

        # A paned split: the canvas owns the space, the inspector is
        # user-resizable and collapsible, and neither is positioned by
        # hardcoded coordinates.
        self._pane = tk.PanedWindow(self, orient=tk.VERTICAL, sashwidth=self._s(5),
                                    sashrelief=tk.FLAT, bg=CHROME_BOT,
                                    bd=0, showhandle=False)
        self._pane.pack(fill=tk.BOTH, expand=True)

        holder = tk.Frame(self._pane, bg=SURFACE_BOT)
        self._pane.add(holder, minsize=self._s(140), stretch="always")

        self.canvas = tk.Canvas(holder, bg=SURFACE_BOT, highlightthickness=0,
                                bd=0, takefocus=True)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self._insp = tk.Frame(self._pane, bg=INSPECTOR_BG)
        self._pane.add(self._insp, minsize=self._s(60),
                       height=self._s(150), stretch="never")
        self._build_inspector(self._insp)

        self._bind_canvas()
        self._build_zoom_controls()

    def _build_toolbar(self) -> None:
        bar = tk.Canvas(self, height=self._s(32), highlightthickness=0, bd=0)
        bar.pack(fill=tk.X)
        self._bar = bar

        left = tk.Frame(bar, bg=CHROME_BOT)
        right = tk.Frame(bar, bg=CHROME_BOT)
        bar.create_window(self._s(9), self._s(16), window=left, anchor="w",
                          tags="left")
        bar.create_window(0, self._s(16), window=right, anchor="e", tags="right")

        def _paint(_e=None):
            bar.delete("bg")
            w = bar.winfo_width() or 900
            h = bar.winfo_height() or self._s(32)
            for i in range(14):
                bar.create_rectangle(0, h * i / 14, w, h * (i + 1) / 14 + 1,
                                     width=0, tags="bg",
                                     fill=_blend(CHROME_TOP, CHROME_BOT, i / 13))
            bar.create_line(0, h - 1, w, h - 1, fill=CHROME_LINE, tags="bg")
            bar.tag_lower("bg")
            bar.coords("right", w - self._s(9), self._s(16))
            # The status text is the first thing to go when the window is too
            # narrow to hold both groups — otherwise it draws straight through
            # the Redo button. The same information stays in the inspector.
            need = left.winfo_reqwidth() + right.winfo_reqwidth() + self._s(30)
            bar.itemconfigure("right",
                              state=("hidden" if w < need else "normal"))
            self._reflow_toolbar(w, left)

        bar.bind("<Configure>", _paint)

        sc = self._scale
        tk.Label(left, text="Pipeline:", bg=CHROME_BOT, fg=TEXT,
                 font=_f(self, 12)).pack(side=tk.LEFT, padx=(0, self._s(5)))

        self._doc_var = tk.StringVar()
        self._doc_cb = ttk.Combobox(left, textvariable=self._doc_var,
                                    state="readonly", width=26,
                                    font=_f(self, 12))
        self._doc_cb.pack(side=tk.LEFT)
        self._doc_cb.bind("<<ComboboxSelected>>", self._on_doc_selected)

        self._btn_manage = AquaButton(left, "Manage ▾", self._show_manage_menu,
                                      bg=CHROME_BOT, scale=sc,
                                      tooltip="New, rename, duplicate, delete")
        self._btn_manage.pack(side=tk.LEFT, padx=(self._s(6), 0))

        ToolSeparator(left, CHROME_BOT, sc).pack(side=tk.LEFT)

        AquaButton(left, "Add ▾", self._show_add_menu, bg=CHROME_BOT, scale=sc,
                   tooltip="Add a stage node").pack(side=tk.LEFT)
        self._btn_del = AquaButton(left, "Delete", self._delete_selection,
                                   bg=CHROME_BOT, scale=sc,
                                   tooltip="Delete selection (Del)")
        self._btn_del.pack(side=tk.LEFT, padx=(self._s(4), 0))

        sep_undo = ToolSeparator(left, CHROME_BOT, sc)
        sep_undo.pack(side=tk.LEFT)

        self._btn_undo = AquaButton(left, "Undo", self.undo, bg=CHROME_BOT,
                                    scale=sc, tooltip="Undo (Ctrl+Z)")
        self._btn_undo.pack(side=tk.LEFT)
        self._btn_redo = AquaButton(left, "Redo", self.redo, bg=CHROME_BOT,
                                    scale=sc, tooltip="Redo (Ctrl+Y)")
        self._btn_redo.pack(side=tk.LEFT, padx=(self._s(4), 0))

        sep_fit = ToolSeparator(left, CHROME_BOT, sc)
        sep_fit.pack(side=tk.LEFT)
        btn_fit = AquaButton(left, "Fit", self.fit_to_view, bg=CHROME_BOT,
                             scale=sc, tooltip="Fit the whole graph in view")
        btn_fit.pack(side=tk.LEFT)

        # Progressive disclosure, lowest value first. Fit is also in the zoom
        # control and on Ctrl+0; undo/redo remain on Ctrl+Z / Ctrl+Y. Nothing
        # becomes unreachable when hidden — it just stops clipping.
        self._optional = [(sep_fit, btn_fit), (sep_undo, self._btn_undo,
                                               self._btn_redo)]

        self._status_var = tk.StringVar()
        tk.Label(right, textvariable=self._status_var, bg=CHROME_BOT,
                 fg=TEXT_DIM, font=_f(self, 11)).pack(side=tk.RIGHT)

    def _reflow_toolbar(self, width: int, left: tk.Frame) -> None:
        """Hide optional control groups until the toolbar fits its width."""
        groups = getattr(self, "_optional", None)
        if not groups:
            return
        for grp in groups:                       # restore, then trim as needed
            for wdg in grp:
                if not wdg.winfo_ismapped():
                    wdg.pack(side=tk.LEFT)
        left.update_idletasks()
        for grp in groups:
            if left.winfo_reqwidth() + self._s(22) <= width:
                break
            for wdg in grp:
                wdg.pack_forget()
            left.update_idletasks()

    def _build_inspector(self, parent: tk.Frame) -> None:
        head = tk.Frame(parent, bg=INSPECTOR_BG)
        head.pack(fill=tk.X, padx=self._s(14), pady=(self._s(8), 0))
        self._i_title = tk.Label(head, text="", bg=INSPECTOR_BG, fg=TEXT,
                                 font=_f(self, 15, True), anchor="w")
        self._i_title.pack(side=tk.LEFT)
        self._i_status = tk.Label(head, text="", bg=INSPECTOR_BG,
                                  font=_f(self, 11, True), anchor="e")
        self._i_status.pack(side=tk.RIGHT)

        self._i_expl = tk.Label(parent, text="", bg=INSPECTOR_BG, fg=TEXT_DIM,
                                font=_f(self, 11), anchor="w", justify="left")
        self._i_expl.pack(fill=tk.X, padx=self._s(14),
                          pady=(self._s(1), self._s(6)))
        tk.Frame(parent, bg=HAIRLINE, height=1).pack(fill=tk.X,
                                                     padx=self._s(14))

        # Scrollable so a long property list never clips at small heights.
        body = tk.Frame(parent, bg=INSPECTOR_BG)
        body.pack(fill=tk.BOTH, expand=True)
        self._i_canvas = tk.Canvas(body, bg=INSPECTOR_BG, highlightthickness=0,
                                   bd=0)
        vs = ttk.Scrollbar(body, orient=tk.VERTICAL,
                           command=self._i_canvas.yview)
        self._i_canvas.configure(yscrollcommand=vs.set)
        vs.pack(side=tk.RIGHT, fill=tk.Y)
        self._i_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._props = tk.Frame(self._i_canvas, bg=INSPECTOR_BG)
        self._props_win = self._i_canvas.create_window(
            (0, 0), window=self._props, anchor="nw")
        self._props.bind(
            "<Configure>",
            lambda _e: self._i_canvas.configure(
                scrollregion=self._i_canvas.bbox("all")))
        def _on_insp_resize(e) -> None:
            self._i_canvas.itemconfigure(self._props_win, width=e.width)
            self._reflow_props()

        self._i_canvas.bind("<Configure>", _on_insp_resize)
        self._props.columnconfigure(0, minsize=self._s(128))
        self._props.columnconfigure(1, weight=1)

    def _build_zoom_controls(self) -> None:
        """Unobtrusive, bottom-right, floating over the canvas."""
        sc = self._scale
        box = tk.Frame(self.canvas, bg=CHROME_BOT, highlightthickness=1,
                       highlightbackground=CHROME_LINE)
        self._zoom_box = box
        AquaButton(box, "−", lambda: self.zoom_by(1 / 1.25), bg=CHROME_BOT,
                   width=int(24 * sc), scale=sc, tooltip="Zoom out").pack(
                       side=tk.LEFT, padx=1, pady=1)
        self._zoom_lbl = tk.Label(box, text="100%", bg=CHROME_BOT, fg=TEXT,
                                  font=_f(self, 11), width=5)
        self._zoom_lbl.pack(side=tk.LEFT)
        AquaButton(box, "+", lambda: self.zoom_by(1.25), bg=CHROME_BOT,
                   width=int(24 * sc), scale=sc, tooltip="Zoom in").pack(
                       side=tk.LEFT, padx=1, pady=1)
        AquaButton(box, "Fit", self.fit_to_view, bg=CHROME_BOT, scale=sc,
                   tooltip="Fit to view").pack(side=tk.LEFT, padx=(1, 2), pady=1)

        def _place(_e=None):
            self.canvas.coords(self._zoom_win,
                               self.canvas.winfo_width() - self._s(10),
                               self.canvas.winfo_height() - self._s(10))

        self._zoom_win = self.canvas.create_window(0, 0, window=box,
                                                   anchor="se")
        self.canvas.bind("<Configure>", _place, add="+")

    # ---- canvas bindings ----

    def _bind_canvas(self) -> None:
        c = self.canvas
        c.bind("<Configure>", lambda _e: self._draw(), add="+")
        c.bind("<Motion>", self._on_motion)
        c.bind("<Button-1>", self._on_press)
        c.bind("<B1-Motion>", self._on_drag)
        c.bind("<ButtonRelease-1>", self._on_release)
        c.bind("<Button-2>", self._pan_start)
        c.bind("<B2-Motion>", self._pan_move)
        c.bind("<Button-3>", self._pan_start)
        c.bind("<B3-Motion>", self._pan_move)
        c.bind("<MouseWheel>", self._on_wheel)
        c.bind("<Double-Button-1>", self._on_double)
        c.bind("<Leave>", lambda _e: self._set_hover(None, None))

        c.bind("<Delete>", lambda _e: self._delete_selection())
        c.bind("<BackSpace>", lambda _e: self._delete_selection())
        c.bind("<Control-z>", lambda _e: self.undo())
        c.bind("<Control-y>", lambda _e: self.redo())
        c.bind("<Control-Shift-Z>", lambda _e: self.redo())
        c.bind("<Control-a>", lambda _e: self._select_all())
        c.bind("<Control-0>", lambda _e: self.fit_to_view())
        for key, dx, dy in (("Left", -1, 0), ("Right", 1, 0),
                            ("Up", 0, -1), ("Down", 0, 1)):
            c.bind(f"<{key}>", lambda _e, a=dx, b=dy: self._nudge(a, b))
            c.bind(f"<Shift-{key}>",
                   lambda _e, a=dx, b=dy: self._nudge(a * 10, b * 10))
        c.bind("<FocusIn>", lambda _e: self._draw())
        c.bind("<FocusOut>", lambda _e: self._draw())

    # ---- transform ----

    @property
    def zoom(self) -> float:
        return self._doc.zoom if self._doc else 1.0

    def _wx(self, x: float) -> float:
        return (x + self._doc.pan_x) * self.zoom * self._scale

    def _wy(self, y: float) -> float:
        return (y + self._doc.pan_y) * self.zoom * self._scale

    def _ux(self, sx: float) -> float:
        return sx / (self.zoom * self._scale) - self._doc.pan_x

    def _uy(self, sy: float) -> float:
        return sy / (self.zoom * self._scale) - self._doc.pan_y

    def zoom_by(self, factor: float, cx: float | None = None,
                cy: float | None = None) -> None:
        """Zoom about a screen point, keeping the world point under it fixed."""
        if not self._doc:
            return
        old = self._doc.zoom
        new = max(MIN_ZOOM, min(MAX_ZOOM, old * factor))
        if abs(new - old) < 1e-6:
            return
        if cx is None:
            cx = self.canvas.winfo_width() / 2
            cy = self.canvas.winfo_height() / 2
        wx, wy = self._ux(cx), self._uy(cy)
        self._doc.zoom = new
        self._doc.pan_x = cx / (new * self._scale) - wx
        self._doc.pan_y = cy / (new * self._scale) - wy
        self._update_zoom_label()
        self._draw()
        self._touch(save_only=True)

    def _on_wheel(self, event) -> None:
        self.canvas.focus_set()
        step = 1.0 + (0.14 if event.delta > 0 else -0.14)
        self.zoom_by(step, event.x, event.y)

    def fit_to_view(self) -> None:
        if not self._doc or not self._doc.nodes:
            return
        x0, y0, x1, y1 = self._doc.bounds()
        cw = max(self.canvas.winfo_width(), 50)
        ch = max(self.canvas.winfo_height(), 50)
        m = 40.0
        zx = cw / (self._scale * max(x1 - x0 + m * 2, 1))
        zy = ch / (self._scale * max(y1 - y0 + m * 2, 1))
        self._doc.zoom = max(MIN_ZOOM, min(MAX_ZOOM, min(zx, zy)))
        z = self._doc.zoom * self._scale
        self._doc.pan_x = (cw - (x1 - x0) * z) / (2 * z) - x0
        self._doc.pan_y = (ch - (y1 - y0) * z) / (2 * z) - y0
        self._update_zoom_label()
        self._draw()
        self._touch(save_only=True)

    def _update_zoom_label(self) -> None:
        self._zoom_lbl.configure(text=f"{self.zoom * 100:.0f}%")

    # ---- documents ----

    def refresh(self) -> None:
        """Reload documents and live status. Safe to call repeatedly."""
        root = getattr(self._app, "_root_folder", None) if self._app else None
        try:
            self._discovered = build_pipelines(root=root)
        except Exception:
            self._discovered = []

        keep = self._doc.id if self._doc else None
        self._docs = list_docs(root)
        if not self._docs:
            doc = default_doc("My Pipeline")
            try:
                save_doc(doc, root)
            except Exception:
                pass
            self._docs = [doc]
        self._doc = next((d for d in self._docs if d.id == keep), self._docs[0])
        self._rebind_derived()

        self._sync_doc_list()
        self._update_zoom_label()
        self._draw()
        self._show_inspector()

    def select_document(self, doc_id: str) -> bool:
        """Bring a document to the front by id. Used after the welcome screen."""
        self.refresh()
        for i, d in enumerate(self._docs):
            if d.id == doc_id:
                self._doc_cb.current(i)
                self._on_doc_selected()
                self.after(40, self.fit_to_view)
                return True
        return False

    def _rebind_derived(self) -> None:
        """Bind the open document to the sample whose status it reports.

        Without this the nodes showed whichever discovered project happened to
        come first, so a document could display a completely unrelated study's
        numbers — including on a machine with no library open at all. A
        document reports status only for the sample it is explicitly linked to;
        unlinked documents show structure with no figures, which is honest.
        """
        self._derived = {}
        self._source_name = None
        doc = self._doc
        if not doc or not getattr(self, "_discovered", None):
            return
        match = next((p for p in self._discovered if p.key == doc.source_key), None)
        if match is None:
            return
        self._source_name = match.name
        for st in match.stages:
            self._derived[st.key] = st

    def available_sources(self) -> list[tuple[str, str]]:
        """(key, label) for every discovered sample a document can bind to."""
        return [(p.key, f"{p.name} — {p.episode_count} episodes")
                for p in getattr(self, "_discovered", [])]

    def _choose_source(self) -> None:
        """Link the open document to a discovered sample."""
        if not self._doc:
            return
        options = self.available_sources()
        if not options:
            messagebox.showinfo(
                "No data sources",
                "No episode samples were found yet.\n\n"
                "Choose a library folder, then draw a sample with "
                "Episode Sampler. The pipeline can then report live progress "
                "for that sample.", parent=self)
            return
        SourcePicker(self, options, self._doc.source_key, self._apply_source)

    def _apply_source(self, key: str | None) -> None:
        if not self._doc:
            return
        self._push_undo()
        self._doc.source_key = key
        self._rebind_derived()
        self._draw()
        self._show_inspector()
        self._touch()

    def _sync_doc_list(self) -> None:
        names = [d.name for d in self._docs]
        self._doc_cb.configure(values=names)
        if self._doc:
            self._doc_var.set(self._doc.name)
        self._status_var.set(
            f"{len(self._doc.nodes)} nodes · {len(self._doc.connections)} links"
            if self._doc else "")
        self._btn_undo.set_enabled(bool(self._undo))
        self._btn_redo.set_enabled(bool(self._redo))
        self._btn_del.set_enabled(bool(self._sel))

    def _on_doc_selected(self, _e=None) -> None:
        i = self._doc_cb.current()
        if 0 <= i < len(self._docs):
            self._flush_save()
            self._doc = self._docs[i]
            self._sel.clear()
            self._undo.clear()
            self._redo.clear()
            self._rebind_derived()
            self._sync_doc_list()
            self._update_zoom_label()
            self._draw()
            self._show_inspector()

    def _show_manage_menu(self) -> None:
        m = tk.Menu(self, tearoff=0)
        presets = tk.Menu(m, tearoff=0)
        for t in TEMPLATES:
            presets.add_command(label=t.name,
                                command=lambda k=t.key: self._new_from_template(k))
        m.add_cascade(label="New Pipeline from preset", menu=presets)
        m.add_command(label="New Pipeline...", command=self._new_doc)
        m.add_separator()
        m.add_command(label="Link to Episode Sample...",
                      command=self._choose_source)
        m.add_separator()
        m.add_command(label="Rename...", command=self._rename_doc)
        m.add_command(label="Duplicate", command=self._duplicate_doc)
        m.add_separator()
        m.add_command(label="Delete...", command=self._delete_doc)
        m.add_separator()
        m.add_command(label="Save Now", command=self._flush_save)
        self._popup(m, self._btn_manage)

    def _show_add_menu(self) -> None:
        m = tk.Menu(self, tearoff=0)
        for t in NODE_TYPES.values():
            m.add_command(label=t.name,
                          command=lambda k=t.key: self._add_node(k))
        self._popup(m, self.nametowidget(self._btn_manage.winfo_parent()))

    def _popup(self, menu: tk.Menu, near: tk.Widget) -> None:
        try:
            menu.tk_popup(near.winfo_rootx(),
                          near.winfo_rooty() + near.winfo_height())
        finally:
            menu.grab_release()

    def _root(self):
        return getattr(self._app, "_root_folder", None) if self._app else None

    def _new_from_template(self, key: str) -> None:
        from analyzer.pipeline_graph import template
        t = template(key)
        name = simpledialog.askstring(
            "New Pipeline", f"Name for the new “{t.name}” pipeline:",
            parent=self,
            initialvalue=unique_name([d.name for d in self._docs], t.name))
        if not name or not name.strip():
            return
        self._adopt(t.build(unique_name([d.name for d in self._docs],
                                        name.strip())))

    def _new_doc(self, standard: bool = False) -> None:
        name = simpledialog.askstring(
            "New Pipeline", "Name for the new pipeline:", parent=self,
            initialvalue=unique_name([d.name for d in self._docs]))
        if not name or not name.strip():
            return
        name = unique_name([d.name for d in self._docs], name.strip())
        self._adopt(default_doc(name) if standard else blank_doc(name))

    def _adopt(self, doc) -> None:
        """Save a freshly created pipeline and make it the open one."""
        try:
            save_doc(doc, self._root())
        except Exception as exc:                        # noqa: BLE001
            messagebox.showerror("Could not save", str(exc), parent=self)
            return
        self._docs.insert(0, doc)
        self._doc = doc
        self._sel.clear()
        self._undo.clear()
        self._redo.clear()
        # A single obvious sample is linked automatically; with several, ask,
        # because guessing wrong would show the wrong study's numbers.
        sources = self.available_sources()
        if len(sources) == 1:
            doc.source_key = sources[0][0]
        self._rebind_derived()
        self._sync_doc_list()
        self.fit_to_view()
        self._show_inspector()
        if len(sources) > 1:
            self.after(60, self._choose_source)

    def _rename_doc(self) -> None:
        if not self._doc:
            return
        name = simpledialog.askstring("Rename Pipeline", "Pipeline name:",
                                      parent=self, initialvalue=self._doc.name)
        if not name or not name.strip():
            return
        others = [d.name for d in self._docs if d is not self._doc]
        self._push_undo()
        self._doc.name = unique_name(others, name.strip())
        self._sync_doc_list()
        self._touch()

    def _duplicate_doc(self) -> None:
        if not self._doc:
            return
        copy_doc = duplicate_doc(
            self._doc, unique_name([d.name for d in self._docs],
                                   f"{self._doc.name} copy"))
        try:
            save_doc(copy_doc, self._root())
        except Exception as exc:
            messagebox.showerror("Could not save", str(exc), parent=self)
            return
        self._docs.insert(0, copy_doc)
        self._doc = copy_doc
        self._sel.clear()
        self._undo.clear()
        self._redo.clear()
        self._sync_doc_list()
        self._draw()

    def _delete_doc(self) -> None:
        if not self._doc:
            return
        if not messagebox.askyesno(
                "Delete Pipeline",
                f"Delete “{self._doc.name}”?\n\n"
                "This removes the pipeline layout only. Episodes, analysis "
                "results, and coding are not touched.", parent=self):
            return
        try:
            delete_doc(self._doc)
        except Exception as exc:
            messagebox.showerror("Could not delete", str(exc), parent=self)
            return
        self._docs = [d for d in self._docs if d is not self._doc]
        self._doc = None
        self._sel.clear()
        self._undo.clear()
        self._redo.clear()
        self.refresh()

    # ---- undo / persistence ----

    def _push_undo(self) -> None:
        if self._doc:
            self._undo.append(self._doc.snapshot())
            del self._undo[:-60]
            self._redo.clear()

    def undo(self) -> None:
        if not (self._doc and self._undo):
            return
        self._redo.append(self._doc.snapshot())
        self._doc.restore(self._undo.pop())
        self._sel &= {n.id for n in self._doc.nodes}
        self._sync_doc_list()
        self._draw()
        self._show_inspector()
        self._touch(save_only=True)

    def redo(self) -> None:
        if not (self._doc and self._redo):
            return
        self._undo.append(self._doc.snapshot())
        self._doc.restore(self._redo.pop())
        self._sel &= {n.id for n in self._doc.nodes}
        self._sync_doc_list()
        self._draw()
        self._show_inspector()
        self._touch(save_only=True)

    def _touch(self, save_only: bool = False) -> None:
        """Mark dirty and coalesce writes — dragging must not hit the disk."""
        self._dirty = True
        if not save_only:
            self._sync_doc_list()
        if self._save_job:
            try:
                self.after_cancel(self._save_job)
            except Exception:
                pass
        self._save_job = self.after(700, self._flush_save)

    def _flush_save(self) -> None:
        self._save_job = None
        if self._doc and self._dirty:
            try:
                save_doc(self._doc, self._root())
                self._dirty = False
            except Exception:
                pass

    # ---- editing ----

    def _add_node(self, type_key: str) -> None:
        if not self._doc:
            return
        cx = self._ux(self.canvas.winfo_width() / 2)
        cy = self._uy(self.canvas.winfo_height() / 2)
        self._push_undo()
        n = self._doc.add_node(type_key, cx - 98, cy - 48)
        self._sel = {n.id}
        self._draw()
        self._show_inspector()
        self._touch()

    def _delete_selection(self) -> None:
        if not (self._doc and self._sel):
            return
        self._push_undo()
        for nid in list(self._sel):
            self._doc.remove_node(nid)
        self._sel.clear()
        self._draw()
        self._show_inspector()
        self._touch()

    def _select_all(self) -> None:
        if self._doc:
            self._sel = {n.id for n in self._doc.nodes}
            self._draw()
            self._sync_doc_list()

    def _nudge(self, dx: int, dy: int) -> None:
        if not (self._doc and self._sel):
            return
        self._push_undo()
        for nid in self._sel:
            n = self._doc.node(nid)
            if n:
                n.x += dx
                n.y += dy
        self._draw()
        self._touch()

    # ---- hit testing ----

    def _node_at(self, sx: float, sy: float):
        if not self._doc:
            return None
        for n in reversed(self._doc.nodes):
            if (self._wx(n.x) <= sx <= self._wx(n.x + n.w)
                    and self._wy(n.y) <= sy <= self._wy(n.y + n.h)):
                return n
        return None

    def _port_at(self, sx: float, sy: float):
        """(node_id, 'in'|'out') when the cursor is over a connection point."""
        if not self._doc:
            return None
        r = self._s(9) * self.zoom
        for n in self._doc.nodes:
            t = node_type(n.type)
            for side, has in (("in", t.inputs), ("out", t.outputs)):
                if not has:
                    continue
                px, py = self._port_pos(n, side)
                if abs(sx - px) <= r and abs(sy - py) <= r:
                    return (n.id, side)
        return None

    def _port_pos(self, n, side: str) -> tuple[float, float]:
        y = self._wy(n.y + n.h / 2)
        return (self._wx(n.x) if side == "in" else self._wx(n.x + n.w), y)

    # ---- mouse ----

    def _set_hover(self, node_id, port) -> None:
        if (node_id, port) != (self._hover, self._hover_port):
            self._hover, self._hover_port = node_id, port
            self.canvas.configure(
                cursor="hand2" if (node_id or port) else "")
            self._draw()

    def _on_motion(self, e) -> None:
        port = self._port_at(e.x, e.y)
        node = None if port else self._node_at(e.x, e.y)
        self._set_hover(node.id if node else None, port)

    def _on_press(self, e) -> None:
        self.canvas.focus_set()
        if not self._doc:
            return
        port = self._port_at(e.x, e.y)
        if port and port[1] == "out":
            self._wire = {"src": port[0], "x": e.x, "y": e.y}
            return
        node = self._node_at(e.x, e.y)
        if node:
            if e.state & 0x0001:                      # Shift toggles
                self._sel ^= {node.id}
            elif node.id not in self._sel:
                self._sel = {node.id}
            self._drag = {
                "moved": False,
                "start": (e.x, e.y),
                "origin": {nid: (self._doc.node(nid).x, self._doc.node(nid).y)
                           for nid in self._sel if self._doc.node(nid)},
            }
            self._draw()
            self._show_inspector()
            self._sync_doc_list()
            return
        if e.state & 0x0001:
            self._marquee = (e.x, e.y, e.x, e.y)
        else:
            self._drag = {"pan": True, "start": (e.x, e.y),
                          "origin": (self._doc.pan_x, self._doc.pan_y)}
            self.canvas.configure(cursor="fleur")

    def _on_drag(self, e) -> None:
        if not self._doc:
            return
        if self._wire:
            self._wire["x"], self._wire["y"] = e.x, e.y
            self._draw()
            return
        if self._marquee:
            self._marquee = (self._marquee[0], self._marquee[1], e.x, e.y)
            self._draw()
            return
        if not self._drag:
            return
        sx, sy = self._drag["start"]
        if self._drag.get("pan"):
            z = self.zoom * self._scale
            ox, oy = self._drag["origin"]
            self._doc.pan_x = ox + (e.x - sx) / z
            self._doc.pan_y = oy + (e.y - sy) / z
            self._draw()
            return
        if not self._drag["moved"]:
            if abs(e.x - sx) < 3 and abs(e.y - sy) < 3:
                return
            self._drag["moved"] = True
            self._push_undo()
        z = self.zoom * self._scale
        for nid, (ox, oy) in self._drag["origin"].items():
            n = self._doc.node(nid)
            if n:
                n.x = ox + (e.x - sx) / z
                n.y = oy + (e.y - sy) / z
        self._draw()

    def _on_release(self, e) -> None:
        if self._wire and self._doc:
            target = self._port_at(e.x, e.y) or (
                (self._node_at(e.x, e.y).id, "in") if self._node_at(e.x, e.y)
                else None)
            if target and target[1] == "in":
                self._push_undo()
                if self._doc.connect(self._wire["src"], target[0]) is None:
                    self._undo.pop()          # refused — do not bank the step
                else:
                    self._touch()
            self._wire = None
            self._draw()
        if self._marquee and self._doc:
            x0, y0, x1, y1 = self._marquee
            lo_x, hi_x = min(x0, x1), max(x0, x1)
            lo_y, hi_y = min(y0, y1), max(y0, y1)
            for n in self._doc.nodes:
                if (self._wx(n.x) < hi_x and self._wx(n.x + n.w) > lo_x
                        and self._wy(n.y) < hi_y and self._wy(n.y + n.h) > lo_y):
                    self._sel.add(n.id)
            self._marquee = None
            self._draw()
            self._show_inspector()
            self._sync_doc_list()
        if self._drag:
            if self._drag.get("moved"):
                self._touch()
            elif self._drag.get("pan"):
                self._touch(save_only=True)
            self.canvas.configure(cursor="")
            self._drag = None

    def _pan_start(self, e) -> None:
        self.canvas.focus_set()
        if self._doc:
            self._drag = {"pan": True, "start": (e.x, e.y),
                          "origin": (self._doc.pan_x, self._doc.pan_y)}
            self.canvas.configure(cursor="fleur")

    def _pan_move(self, e) -> None:
        self._on_drag(e)

    def _on_double(self, e) -> None:
        node = self._node_at(e.x, e.y)
        if not node:
            return
        name = simpledialog.askstring("Rename Node", "Node title:",
                                      parent=self, initialvalue=node.title)
        if name and name.strip():
            self._push_undo()
            node.title = name.strip()
            self._draw()
            self._show_inspector()
            self._touch()

    # ---- painting ----

    def _draw(self) -> None:
        c = self.canvas
        c.delete("gfx")
        if not self._doc:
            return
        w = c.winfo_width() or 900
        h = c.winfo_height() or 500
        if w < 20 or h < 20:
            return

        self._paint_surface(w, h)
        for conn in self._doc.connections:
            self._paint_wire(conn)
        if self._wire:
            src = self._doc.node(self._wire["src"])
            if src:
                x0, y0 = self._port_pos(src, "out")
                self._curve(x0, y0, self._wire["x"], self._wire["y"], WIRE_HOT)
        for n in self._doc.nodes:
            self._paint_node(n)
        if self._marquee:
            x0, y0, x1, y1 = self._marquee
            c.create_rectangle(x0, y0, x1, y1, outline=SEL_BORDER,
                               dash=(3, 2), tags="gfx")
        c.tag_raise(self._zoom_win)

    def _paint_surface(self, w: int, h: int) -> None:
        c = self.canvas
        for i in range(18):
            c.create_rectangle(0, h * i / 18, w, h * (i + 1) / 18 + 1, width=0,
                               fill=_blend(SURFACE_TOP, SURFACE_BOT, i / 17),
                               tags="gfx")
        # Dotted work surface: signals an editable canvas, and gives panning
        # and zooming something to register against. Spacing tracks zoom, so
        # the dot field never becomes a moiré at small scales.
        step = 28.0 * self.zoom * self._scale
        while step < 14:
            step *= 2
        ox = (self._wx(0)) % step
        oy = (self._wy(0)) % step
        y = oy
        while y < h:
            x = ox
            while x < w:
                c.create_rectangle(x, y, x + 1, y + 1, width=0, fill=GRID_DOT,
                                   outline=GRID_DOT, tags="gfx")
                x += step
            y += step

    def _paint_wire(self, conn) -> None:
        a = self._doc.node(conn.src)
        b = self._doc.node(conn.dst)
        if not a or not b:
            return
        x0, y0 = self._port_pos(a, "out")
        x1, y1 = self._port_pos(b, "in")
        hot = bool(self._sel & {a.id, b.id})
        self._curve(x0, y0, x1, y1, WIRE_HOT if hot else WIRE)

    def _curve(self, x0, y0, x1, y1, color) -> None:
        """Cubic-ish connector with an arrowhead, drawn as a smooth spline."""
        dx = max(abs(x1 - x0) * 0.45, 28 * self.zoom * self._scale)
        head = self._s(7) * max(self.zoom, 0.6)
        self.canvas.create_line(
            x0, y0, x0 + dx, y0, x1 - dx - head, y1, x1 - head, y1,
            smooth=True, splinesteps=24, fill=color,
            width=max(1, 1.4 * self.zoom * self._scale), tags="gfx")
        self.canvas.create_polygon(
            x1 - head, y1 - head * 0.62, x1 - head, y1 + head * 0.62, x1, y1,
            fill=color, outline=color, tags="gfx")

    def _paint_node(self, n) -> None:
        c = self.canvas
        t = node_type(n.type)
        z = self.zoom * self._scale
        x0, y0 = self._wx(n.x), self._wy(n.y)
        x1, y1 = self._wx(n.x + n.w), self._wy(n.y + n.h)
        r = 5 * z
        selected = n.id in self._sel
        hovered = n.id == self._hover and not selected

        if selected:
            _outline_round(c, x0 - 2 * z, y0 - 2 * z, x1 + 2 * z, y1 + 2 * z,
                           r + 2 * z, SEL_GLOW, tags="gfx")
        c.create_line(x0 + r, y1 + 1, x1 - r, y1 + 1, fill=NODE_SHADOW,
                      tags="gfx")

        top, bot, edge = ((SEL_TOP, SEL_BOT, SEL_BORDER) if selected else
                          (HOV_TOP, HOV_BOT, NODE_BORDER) if hovered else
                          (NODE_TOP, NODE_BOT, NODE_BORDER))
        _grad_round(c, x0, y0, x1, y1, r, top, bot, tags="gfx")
        _outline_round(c, x0, y0, x1, y1, r, edge, tags="gfx")
        c.create_line(x0 + r, y0 + 1, x1 - r, y0 + 1, fill=NODE_GLOSS,
                      tags="gfx")
        if selected and c.focus_get() is c:
            _outline_round(c, x0 - 4 * z, y0 - 4 * z, x1 + 4 * z, y1 + 4 * z,
                           r + 4 * z, SEL_BORDER, dash=(2, 2), tags="gfx")

        stage = self._derived.get(t.stage_key) if t.stage_key else None
        status = getattr(stage, "status", None)
        headline = getattr(stage, "headline", "") if stage else ""
        pad = 10 * z
        avail = (x1 - x0) - 2 * pad

        if z > 0.42:                       # below this, labels are illegible
            ir = 5 * z
            icx = x0 + pad + ir
            _icon(c, t.icon, icx, y0 + 15 * z, ir,
                  SEL_BORDER if selected else TEXT_DIM)
            c.create_text(icx + ir + 7 * z, y0 + 15 * z, anchor="w",
                          text=n.title, font=_f(self, 12 * z, True), fill=TEXT,
                          width=avail - (ir * 2 + 7 * z), tags="gfx")
            sub = c.create_text(x0 + pad, y0 + 29 * z, anchor="nw",
                                text=t.description, font=_f(self, 11 * z),
                                fill=TEXT_FAINT, width=avail, tags="gfx")
            bottom = (c.bbox(sub) or (0, 0, 0, y0 + 42 * z))[3]
            if headline:
                c.create_text(x0 + pad, bottom + 5 * z, anchor="nw",
                              text=headline, font=_f(self, 12 * z, True),
                              fill=TEXT, width=avail, tags="gfx")
            if status:
                c.create_text(
                    x0 + pad, y1 - 8 * z, anchor="sw",
                    text=f"{STATUS_GLYPH.get(status, '·')} {stage.status_label}",
                    font=_f(self, 11 * z), fill=STATUS_COLOR.get(status, TEXT_DIM),
                    width=avail, tags="gfx")
            elif t.stage_key:
                # This node COULD report progress but the document is not bound
                # to a sample. Say so rather than leaving a blank that reads as
                # "nothing to do here".
                c.create_text(x0 + pad, y1 - 8 * z, anchor="sw",
                              text="· no data source", font=_f(self, 11 * z),
                              fill=TEXT_FAINT, width=avail, tags="gfx")
        else:
            c.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=n.title,
                          font=_f(self, max(9, 12 * z), True), fill=TEXT,
                          width=avail, tags="gfx")

        for side, has in (("in", t.inputs), ("out", t.outputs)):
            if not has:
                continue
            px, py = self._port_pos(n, side)
            hot = self._hover_port == (n.id, side)
            pr = (5 if hot else 3.5) * z
            c.create_oval(px - pr, py - pr, px + pr, py + pr,
                          fill=PORT_HOT if hot else "#ffffff",
                          outline=PORT_HOT if hot else PORT,
                          width=max(1, z), tags="gfx")

    # ---- inspector ----

    def _show_inspector(self) -> None:
        for w in self._prop_rows:
            w.destroy()
        self._prop_rows.clear()

        if not self._doc:
            self._i_title.configure(text="No pipeline")
            self._i_status.configure(text="")
            self._i_expl.configure(text="")
            return

        if len(self._sel) != 1:
            self._i_title.configure(text=self._doc.name)
            src = getattr(self, "_source_name", None)
            self._i_status.configure(
                text=("Linked: " + src) if src else "Not linked to a sample",
                fg=STATUS_COLOR[COMPLETE] if src else TEXT_DIM)
            self._i_expl.configure(
                text=f"{len(self._sel)} nodes selected." if self._sel else
                     "Select a node to inspect it. Drag the canvas to pan, "
                     "scroll to zoom, drag from a right-hand port to connect.")
            rows = [
                ("Data source", src or "none — nodes show no figures"),
                ("Nodes", str(len(self._doc.nodes))),
                ("Connections", str(len(self._doc.connections))),
            ]
            self._add_props(
                rows,
                next_action=(None if src else
                             "Manage ▾ → Link to Episode Sample, to show live "
                             "progress for a set of episodes."))
            return

        n = self._doc.node(next(iter(self._sel)))
        if n is None:
            return
        t = node_type(n.type)
        stage = self._derived.get(t.stage_key) if t.stage_key else None

        self._i_title.configure(text=n.title)
        if stage is not None:
            self._i_status.configure(
                text=f"{STATUS_GLYPH.get(stage.status, '·')} {stage.status_label}",
                fg=STATUS_COLOR.get(stage.status, TEXT_DIM))
            self._i_expl.configure(text=stage.explanation)
        else:
            self._i_status.configure(text="not linked", fg=TEXT_DIM)
            self._i_expl.configure(text=t.description)

        rows = [("Type", t.name),
                ("Position", f"{n.x:.0f}, {n.y:.0f}"),
                ("Inputs", str(t.inputs)), ("Outputs", str(t.outputs))]
        if stage is not None:
            rows = [("Status", stage.status_label)] + list(stage.details) + rows
        self._add_props(rows, next_action=getattr(stage, "next_action", ""))

    def _add_props(self, rows, next_action: str = "") -> None:
        # Value labels reflow against the CONTAINER width, never their own.
        # Deriving wraplength from a label's own <Configure> is a feedback
        # loop: wrapping shrinks the label, which re-fires Configure, which
        # shrinks it again until the text is one word per line.
        self._value_labels: list[tk.Label] = []
        row = 0
        for label, value in rows:
            a = tk.Label(self._props, text=label, bg=INSPECTOR_BG, fg=TEXT_DIM,
                         font=_f(self, 12), anchor="e")
            a.grid(row=row, column=0, sticky="ne",
                   padx=(self._s(14), self._s(10)), pady=self._s(1))
            b = tk.Label(self._props, text=value, bg=INSPECTOR_BG, fg=TEXT,
                         font=_f(self, 12), anchor="w", justify="left")
            b.grid(row=row, column=1, sticky="w", padx=(0, self._s(14)),
                   pady=self._s(1))
            self._prop_rows += [a, b]
            self._value_labels.append(b)
            row += 1
        if next_action:
            sep = tk.Frame(self._props, bg=HAIRLINE, height=1)
            sep.grid(row=row, column=0, columnspan=2, sticky="ew",
                     padx=self._s(14), pady=(self._s(6), self._s(5)))
            a = tk.Label(self._props, text="Next", bg=INSPECTOR_BG, fg=TEXT_DIM,
                         font=_f(self, 12, True), anchor="e")
            a.grid(row=row + 1, column=0, sticky="ne",
                   padx=(self._s(14), self._s(10)))
            b = tk.Label(self._props, text=next_action, bg=INSPECTOR_BG,
                         fg=TEXT, font=_f(self, 12), anchor="w",
                         justify="left")
            b.grid(row=row + 1, column=1, sticky="w", padx=(0, self._s(14)))
            self._prop_rows += [sep, a, b]
            self._value_labels.append(b)
        self._reflow_props()

    def _reflow_props(self, _event=None) -> None:
        """Set every value label's wrap width from the available column."""
        labels = getattr(self, "_value_labels", None)
        if not labels:
            return
        avail = (self._i_canvas.winfo_width() or self._s(600))
        wrap = max(self._s(140), avail - self._s(128) - self._s(38))
        for lb in labels:
            try:
                lb.configure(wraplength=wrap)
            except tk.TclError:
                pass


class SourcePicker(tk.Toplevel):
    """Pick which episode sample a pipeline document reports progress for."""

    def __init__(self, parent, options, current, on_pick) -> None:
        super().__init__(parent)
        self.title("Link to Episode Sample")
        self.configure(bg=INSPECTOR_BG)
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.resizable(False, False)
        self._on_pick = on_pick

        tk.Label(self, text="Report live progress for:", bg=INSPECTOR_BG,
                 fg=TEXT, font=_f(self, 12), anchor="w").pack(
                     fill=tk.X, padx=14, pady=(12, 2))
        tk.Label(self,
                 text="The pipeline shows how far along this sample is. "
                      "Unlinked pipelines show the workflow shape only.",
                 bg=INSPECTOR_BG, fg=TEXT_DIM, font=_f(self, 11),
                 wraplength=380, justify="left", anchor="w").pack(
                     fill=tk.X, padx=14, pady=(0, 8))

        self._var = tk.StringVar()
        self._keys = [None] + [k for k, _ in options]
        labels = ["(not linked)"] + [lbl for _, lbl in options]
        self._cb = ttk.Combobox(self, textvariable=self._var, values=labels,
                                state="readonly", width=46, font=_f(self, 12))
        self._cb.current(self._keys.index(current) if current in self._keys else 0)
        self._cb.pack(padx=14, pady=(0, 12))

        row = tk.Frame(self, bg=INSPECTOR_BG)
        row.pack(fill=tk.X, padx=14, pady=(0, 12))
        AquaButton(row, "Link", self._ok, bg=INSPECTOR_BG, width=70).pack(
            side=tk.RIGHT)
        AquaButton(row, "Cancel", self.destroy, bg=INSPECTOR_BG,
                   width=70).pack(side=tk.RIGHT, padx=(0, 6))
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self._ok())

    def _ok(self) -> None:
        idx = self._cb.current()
        key = self._keys[idx] if 0 <= idx < len(self._keys) else None
        self.destroy()
        self._on_pick(key)


class PipelineWindow(tk.Toplevel):
    """Standalone editor window — a normal, resizable Windows window."""

    def __init__(self, app, on_close=None) -> None:
        super().__init__(app)
        self._app, self._on_close = app, on_close
        self.configure(bg=INSPECTOR_BG)
        self.minsize(720, 420)
        sc = max(1.0, min(3.0, self.winfo_fpixels("1i") / 96.0))
        self.geometry(f"{int(1020 * sc)}x{int(620 * sc)}")

        self.view = PipelineView(self, app=app)
        self.view.pack(fill=tk.BOTH, expand=True)

        tk.Frame(self, bg=HAIRLINE, height=1).pack(fill=tk.X)
        footer = tk.Frame(self, bg=FOOTER_BG)
        footer.pack(fill=tk.X)
        self._show_var = tk.BooleanVar(value=_get_show_on_start(app))
        tk.Checkbutton(footer, text="Show at startup", variable=self._show_var,
                       bg=FOOTER_BG, activebackground=FOOTER_BG, fg=TEXT,
                       font=_f(self, 11), command=self._toggle,
                       padx=0).pack(side=tk.LEFT, padx=10, pady=6)
        AquaButton(footer, "Close", self._close, bg=FOOTER_BG,
                   width=int(64 * sc), scale=sc).pack(side=tk.RIGHT, padx=10,
                                                      pady=6)

        self._retitle()
        self.view._doc_cb.bind("<<ComboboxSelected>>",
                               lambda _e: self.after(10, self._retitle),
                               add="+")
        self.bind("<Escape>", lambda _e: self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(60, self.view.fit_to_view)
        self.view.canvas.focus_set()

    def _retitle(self) -> None:
        doc = self.view._doc
        self.title(f"{doc.name} — Analysis Pipeline" if doc
                   else "Analysis Pipeline")

    def _toggle(self) -> None:
        _set_show_on_start(self._app, self._show_var.get())

    def _close(self) -> None:
        try:
            self.view._flush_save()
        except Exception:
            pass
        if self._on_close:
            self._on_close()
        self.destroy()


# --- startup preference ------------------------------------------------------

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


# --- vector icons ------------------------------------------------------------
# Drawn from primitives rather than loaded as bitmaps, so they stay sharp at
# any zoom and any display scaling.

def _icon(c: tk.Canvas, kind: str, cx: float, cy: float, r: float,
          color: str) -> None:
    w = max(1, r / 5)
    if kind == "sampling":
        d = r * 0.72
        for iy in range(3):
            for ix in range(3):
                px, py = cx - d + ix * d, cy - d + iy * d
                on = (ix + iy) % 2 == 0
                c.create_oval(px - r * .2, py - r * .2, px + r * .2, py + r * .2,
                              outline=color, fill=color if on else "",
                              tags="gfx")
    elif kind == "selection":
        c.create_line(cx - r, cy, cx, cy, fill=color, width=w, tags="gfx")
        c.create_line(cx, cy, cx + r * .8, cy - r * .7, fill=color, width=w,
                      tags="gfx")
        c.create_line(cx, cy, cx + r * .8, cy + r * .7, fill=color, width=w,
                      tags="gfx")
        for sy in (-1, 1):
            c.create_oval(cx + r * .7, cy + sy * r - (r * .3 if sy > 0 else 0),
                          cx + r * 1.2, cy + sy * r * .4, outline=color,
                          fill=color, tags="gfx")
    elif kind == "measurement":
        for i, hgt in enumerate((.45, .95, .68)):
            px = cx - r + i * r
            c.create_rectangle(px, cy + r - 2 * r * hgt, px + r * .55, cy + r,
                               outline=color, fill=color, tags="gfx")
    elif kind == "validation":
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color, width=w,
                      tags="gfx")
        c.create_line(cx - r * .45, cy, cx - r * .1, cy + r * .42, fill=color,
                      width=w * 1.6, tags="gfx")
        c.create_line(cx - r * .1, cy + r * .42, cx + r * .5, cy - r * .45,
                      fill=color, width=w * 1.6, tags="gfx")
    elif kind == "language":                     # speech bubble with a line
        c.create_oval(cx - r, cy - r * .85, cx + r, cy + r * .5,
                      outline=color, width=w, tags="gfx")
        c.create_polygon(cx - r * .35, cy + r * .4, cx - r * .05, cy + r * .4,
                         cx - r * .45, cy + r, fill=color, outline=color,
                         tags="gfx")
        c.create_line(cx - r * .45, cy - r * .2, cx + r * .45, cy - r * .2,
                      fill=color, tags="gfx")
    elif kind == "handcode":                     # pencil on a ruled sheet
        c.create_rectangle(cx - r, cy - r * .8, cx + r * .25, cy + r * .9,
                           outline=color, width=w, tags="gfx")
        for i in range(2):
            yy = cy - r * .3 + i * r * .5
            c.create_line(cx - r * .7, yy, cx - r * .05, yy, fill=color,
                          tags="gfx")
        c.create_line(cx + r * .35, cy + r * .8, cx + r * 1.05, cy - r * .5,
                      fill=color, width=w * 1.6, tags="gfx")
        c.create_polygon(cx + r * .25, cy + r, cx + r * .5, cy + r * .85,
                         cx + r * .3, cy + r * .72, fill=color, outline=color,
                         tags="gfx")
    elif kind == "export":
        c.create_rectangle(cx - r * .8, cy - r * .3, cx + r * .8, cy + r,
                           outline=color, width=w, tags="gfx")
        c.create_line(cx, cy - r, cx, cy + r * .3, fill=color, width=w * 1.4,
                      tags="gfx")
        c.create_polygon(cx - r * .35, cy - r * .5, cx + r * .35, cy - r * .5,
                         cx, cy - r, fill=color, outline=color, tags="gfx")
    elif kind == "note":
        c.create_rectangle(cx - r * .8, cy - r * .8, cx + r * .8, cy + r * .8,
                           outline=color, width=w, tags="gfx")
        for i in range(2):
            yy = cy - r * .25 + i * r * .5
            c.create_line(cx - r * .45, yy, cx + r * .45, yy, fill=color,
                          tags="gfx")
    else:                                     # results
        c.create_rectangle(cx - r * .7, cy - r, cx + r * .7, cy + r,
                           outline=color, width=w, tags="gfx")
        for i in range(3):
            yy = cy - r * .45 + i * r * .45
            c.create_line(cx - r * .4, yy, cx + r * .4, yy, fill=color,
                          tags="gfx")


# --- vector primitives -------------------------------------------------------

def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _blend(c1: str, c2: str, t: float) -> str:
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return "#%02x%02x%02x" % (int(r1 + (r2 - r1) * t), int(g1 + (g2 - g1) * t),
                              int(b1 + (b2 - b1) * t))


def _corner_inset(dy: float, r: float) -> float:
    """Horizontal inset of the rounded corner at vertical distance *dy*.

    dy is clamped to [0, r]: a widget that has not been mapped yet reports a
    height of 1, which makes the caller pass a negative dy, and a negative
    value under ** 0.5 returns a COMPLEX number in Python rather than raising —
    which then blows up on the next comparison.
    """
    if r <= 0:
        return 0.0
    dy = min(max(dy, 0.0), r)
    inner = max(r * r - (r - dy) * (r - dy), 0.0)
    return r - inner ** 0.5


def _grad_round(canvas, x0, y0, x1, y1, r, top, bottom, tags=None) -> None:
    if x1 <= x0 or y1 <= y0:            # degenerate box: nothing to draw
        return
    r = max(0.0, min(r, (y1 - y0) / 2, (x1 - x0) / 2))
    h = max(1.0, y1 - y0)
    steps = max(6, int(min(h, 48)))
    kw = {"tags": tags} if tags else {}
    for i in range(steps):
        sy0 = y0 + h * i / steps
        sy1 = y0 + h * (i + 1) / steps
        inset = max(_corner_inset(sy0 - y0, r), _corner_inset(y1 - sy1, r))
        canvas.create_rectangle(x0 + inset, sy0, x1 - inset, sy1 + 0.6,
                                width=0,
                                fill=_blend(top, bottom, i / max(steps - 1, 1)),
                                **kw)


def _outline_round(canvas, x0, y0, x1, y1, r, color, dash=None, tags=None) -> None:
    opts = {"outline": color, "style": tk.ARC, "width": 1}
    if dash:
        opts["dash"] = dash
    if tags:
        opts["tags"] = tags
    d = 2 * r
    canvas.create_arc(x0, y0, x0 + d, y0 + d, start=90, extent=90, **opts)
    canvas.create_arc(x1 - d, y0, x1, y0 + d, start=0, extent=90, **opts)
    canvas.create_arc(x0, y1 - d, x0 + d, y1, start=180, extent=90, **opts)
    canvas.create_arc(x1 - d, y1 - d, x1, y1, start=270, extent=90, **opts)
    line = {"fill": color}
    if dash:
        line["dash"] = dash
    if tags:
        line["tags"] = tags
    canvas.create_line(x0 + r, y0, x1 - r, y0, **line)
    canvas.create_line(x0 + r, y1, x1 - r, y1, **line)
    canvas.create_line(x0, y0 + r, x0, y1 - r, **line)
    canvas.create_line(x1, y0 + r, x1, y1 - r, **line)
