"""
gui_welcome.py — the first screen: what are you trying to do?

CMAT exposes a lot of capability, and a new user previously had to translate
their research design into tabs. This asks the question directly and routes
accordingly:

    Create a pipeline  ->  choose a workflow preset  ->  named, editable graph
    Quick explore      ->  straight to the library, no pipeline at all

The presets are starting layouts, not modes. Every one produces an ordinary
editable graph, and "Blank canvas" produces nothing at all — a researcher who
only hand-codes, or only measures language, is a first-class case rather than
a subset of the automated workflow.

Visual language matches the pipeline editor: cool Snow Leopard greys, hairline
separators, restrained Aqua blue for the selected row, compact glossy buttons.
Behaviour stays Windows — Tab traversal, arrows to move the selection, Enter to
continue, Escape to cancel.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from analyzer.pipeline_graph import TEMPLATES, list_docs, save_doc, unique_name
from gui_pipeline import (
    AquaButton, CHROME_BOT, CHROME_LINE, CHROME_TOP, HAIRLINE, INSPECTOR_BG,
    SEL_BORDER, SEL_BOT, SEL_TOP, TEXT, TEXT_DIM, TEXT_FAINT, _blend, _f,
    _grad_round, _icon, _outline_round,
)

_TEMPLATE_ICON = {
    "full": "validation", "automated": "measurement",
    "handcoding": "handcode", "language": "language",
    "mixed": "selection", "validation": "validation", "blank": "note",
}


class WelcomeWindow(tk.Toplevel):
    """Modal first-run chooser. Returns via callbacks, never blocks the app."""

    def __init__(self, app, on_done=None) -> None:
        super().__init__(app)
        self._app = app
        self._on_done = on_done
        self.title("Welcome to CMAT")
        self.configure(bg=INSPECTOR_BG)
        self.resizable(False, False)
        self.transient(app)

        self._scale = max(1.0, min(3.0, self.winfo_fpixels("1i") / 96.0))
        self._choice: str | None = None
        self._template_key = TEMPLATES[0].key

        self._build()
        self._show_page(0)
        self._centre()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())
        self.grab_set()

    def _s(self, n: float) -> int:
        return int(round(n * self._scale))

    def _centre(self) -> None:
        self.update_idletasks()
        p = self._app
        px, py = p.winfo_rootx(), p.winfo_rooty()
        pw, ph = max(p.winfo_width(), 400), max(p.winfo_height(), 300)
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{max(px + (pw - w) // 2, 0)}+{max(py + (ph - h) // 3, 0)}")

    # ---- construction ----

    def _build(self) -> None:
        # Fixed comfortable width; height follows content.
        self._body_width = self._s(640)
        head = tk.Canvas(self, height=self._s(66), width=self._body_width,
                         highlightthickness=0, bd=0)
        head.pack(fill=tk.X)

        def _paint(_e=None):
            head.delete("bg")
            w = head.winfo_width() or self._s(560)
            h = head.winfo_height() or self._s(62)
            for i in range(16):
                head.create_rectangle(0, h * i / 16, w, h * (i + 1) / 16 + 1,
                                      width=0, tags="bg",
                                      fill=_blend(CHROME_TOP, CHROME_BOT, i / 15))
            head.create_line(0, h - 1, w, h - 1, fill=CHROME_LINE, tags="bg")
            head.tag_lower("bg")

        # Header text is drawn onto the gradient, not placed in a frame — a
        # frame carries its own flat background and shows as a pale block.
        self._head = head
        self._head_title = "What would you like to do?"
        self._head_sub = ("CMAT measures features of the video and its "
                          "dialogue — not whether a programme is suitable "
                          "for a child.")

        def _paint_text(_e=None):
            head.delete("txt")
            w = head.winfo_width() or self._s(600)
            head.create_text(self._s(18), self._s(21), anchor="w", tags="txt",
                             text=self._head_title, font=_f(self, 16, True),
                             fill=TEXT)
            head.create_text(self._s(18), self._s(38), anchor="nw", tags="txt",
                             text=self._head_sub, font=_f(self, 11),
                             fill=TEXT_DIM, width=w - self._s(34))

        head.bind("<Configure>", _paint)
        head.bind("<Configure>", _paint_text, add="+")
        self._repaint_head = _paint_text

        self._body = tk.Frame(self, bg=INSPECTOR_BG)
        self._body.pack(fill=tk.BOTH, expand=True)

        self._page0 = self._build_page_choice(self._body)
        self._page1 = self._build_page_templates(self._body)

        tk.Frame(self, bg=HAIRLINE, height=1).pack(fill=tk.X)
        foot = tk.Frame(self, bg=INSPECTOR_BG)
        foot.pack(fill=tk.X)

        from analyzer.prefs import get_pref
        self._show_var = tk.BooleanVar(
            value=bool(get_pref("show_welcome_on_start", True)))
        tk.Checkbutton(foot, text="Show this when CMAT starts",
                       variable=self._show_var, bg=INSPECTOR_BG,
                       activebackground=INSPECTOR_BG, fg=TEXT,
                       font=_f(self, 11), command=self._save_pref,
                       padx=0).pack(side=tk.LEFT, padx=self._s(16),
                                    pady=self._s(9))

        self._btn_next = AquaButton(foot, "Create Pipeline", self._next,
                                    bg=INSPECTOR_BG, scale=self._scale)
        self._btn_next.pack(side=tk.RIGHT, padx=(0, self._s(16)),
                            pady=self._s(9))
        self._btn_back = AquaButton(foot, "Back", self._back, bg=INSPECTOR_BG,
                                    width=self._s(66), scale=self._scale)
        self._btn_back.pack(side=tk.RIGHT, padx=(0, self._s(6)),
                            pady=self._s(9))

    def _build_page_choice(self, parent) -> tk.Frame:
        page = tk.Frame(parent, bg=INSPECTOR_BG)
        self._choice_rows: list[_Row] = []
        opts = [
            ("pipeline", "workflow", "Create a pipeline",
             "Plan a study as a diagram: how episodes are chosen, how they are "
             "measured, and what comes out. Choose a starting layout next; "
             "everything stays editable."),
            ("explore", "measurement", "Quick explore",
             "Skip the planning and go straight to the library. Analyse a few "
             "episodes to see what the measures look like. You can create a "
             "pipeline later."),
        ]
        for key, icon, title, body in opts:
            row = _Row(page, self, icon, title, body,
                       lambda k=key: self._pick_choice(k),
                       lambda: self._next())
            row.pack(fill=tk.X, padx=self._s(16), pady=self._s(5))
            self._choice_rows.append(row)
        self._pick_choice("pipeline")
        return page

    def _build_page_templates(self, parent) -> tk.Frame:
        page = tk.Frame(parent, bg=INSPECTOR_BG)

        wrap = tk.Frame(page, bg=INSPECTOR_BG)
        wrap.pack(fill=tk.BOTH, expand=True, padx=self._s(16),
                  pady=(self._s(8), 0))
        canvas = tk.Canvas(wrap, bg=INSPECTOR_BG, highlightthickness=0, bd=0,
                           height=self._s(300))
        vs = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vs.set)
        vs.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        holder = tk.Frame(canvas, bg=INSPECTOR_BG)
        win = canvas.create_window((0, 0), window=holder, anchor="nw")
        holder.bind("<Configure>",
                    lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfigure(win, width=e.width))

        self._template_rows: list[_Row] = []
        for t in TEMPLATES:
            row = _Row(holder, self, _TEMPLATE_ICON.get(t.key, "note"),
                       t.name, f"{t.summary}. {t.detail}",
                       lambda k=t.key: self._pick_template(k),
                       lambda: self._next())
            row.pack(fill=tk.X, pady=self._s(3))
            self._template_rows.append(row)

        name_row = tk.Frame(page, bg=INSPECTOR_BG)
        name_row.pack(fill=tk.X, padx=self._s(16), pady=self._s(9))
        tk.Label(name_row, text="Pipeline name:", bg=INSPECTOR_BG, fg=TEXT,
                 font=_f(self, 12)).pack(side=tk.LEFT, padx=(0, self._s(7)))
        self._name_var = tk.StringVar()
        tk.Entry(name_row, textvariable=self._name_var, font=_f(self, 12),
                 width=34).pack(side=tk.LEFT, fill=tk.X, expand=True)
        return page

    # ---- selection ----

    def _pick_choice(self, key: str) -> None:
        self._choice = key
        for row, (k, *_rest) in zip(self._choice_rows,
                                    [("pipeline",), ("explore",)]):
            row.set_selected(k == key)

    def _pick_template(self, key: str) -> None:
        self._template_key = key
        for row, t in zip(self._template_rows, TEMPLATES):
            row.set_selected(t.key == key)
        existing = [d.name for d in self._safe_docs()]
        current = self._name_var.get().strip()
        known = {t.name for t in TEMPLATES}
        # Keep a name the user typed; replace one that came from a preset.
        if not current or current in known or current.rstrip(" 23456789") in known:
            self._name_var.set(unique_name(existing,
                                           next(t.name for t in TEMPLATES
                                                if t.key == key)))

    def _safe_docs(self):
        try:
            return list_docs(getattr(self._app, "_root_folder", None))
        except Exception:
            return []

    # ---- navigation ----

    def _show_page(self, index: int) -> None:
        self._page = index
        for p in (self._page0, self._page1):
            p.pack_forget()
        (self._page0 if index == 0 else self._page1).pack(
            fill=tk.BOTH, expand=True, pady=(self._s(10), 0))
        if index == 0:
            self._head_title = "What would you like to do?"
            self._head_sub = ("CMAT measures features of the video and its "
                              "dialogue — not whether a programme is suitable "
                              "for a child.")
            self._btn_back.set_enabled(False)
            self._btn_next.set_text("Continue")
        else:
            self._head_title = "Choose a starting layout"
            self._head_sub = ("A starting point, not a restriction — add, "
                              "remove, and rewire stages at any time.")
            self._btn_back.set_enabled(True)
            self._btn_next.set_text("Create Pipeline")
            self._pick_template(self._template_key)
        self._repaint_head()

    def _back(self) -> None:
        if self._page == 1:
            self._show_page(0)

    def _next(self) -> None:
        if self._page == 0:
            if self._choice == "explore":
                self._finish("explore", None)
            else:
                self._show_page(1)
            return
        self._finish("pipeline", self._create_doc())

    def _create_doc(self):
        from analyzer.pipeline_graph import template
        existing = [d.name for d in self._safe_docs()]
        name = unique_name(existing, self._name_var.get().strip()
                           or template(self._template_key).name)
        doc = template(self._template_key).build(name)
        try:
            save_doc(doc, getattr(self._app, "_root_folder", None))
        except Exception:
            pass
        return doc

    def _save_pref(self) -> None:
        from analyzer.prefs import set_pref
        set_pref("show_welcome_on_start", bool(self._show_var.get()))

    def _finish(self, choice: str, doc) -> None:
        self.destroy()
        if self._on_done:
            self._on_done(choice, doc)

    def _cancel(self) -> None:
        self.destroy()
        if self._on_done:
            self._on_done(None, None)


class _Row(tk.Canvas):
    """One selectable option — icon, title, wrapped description.

    Drawn rather than assembled from widgets so the selected state can use the
    same gradient, hairline, and Aqua rim as a pipeline node.
    """

    def __init__(self, parent, owner, icon, title, body, on_click,
                 on_double) -> None:
        self._owner = owner
        self._icon, self._title, self._body = icon, title, body
        self._selected = False
        self._last_w = -1
        super().__init__(parent, height=owner._s(64), highlightthickness=0,
                         bd=0, bg=INSPECTOR_BG, cursor="hand2", takefocus=True)
        self.bind("<Configure>", self._on_configure)
        self.bind("<Button-1>", lambda _e: (self.focus_set(), on_click()))
        self.bind("<Double-Button-1>", lambda _e: on_double())
        self.bind("<Return>", lambda _e: on_double())
        self.bind("<space>", lambda _e: on_click())
        self.bind("<FocusIn>", lambda _e: self._paint())
        self.bind("<FocusOut>", lambda _e: self._paint())

    def _on_configure(self, event) -> None:
        """Re-measure height only when the WIDTH changes.

        Setting the height inside a <Configure> handler re-fires <Configure>,
        so measuring on every event is an infinite resize loop. Width is the
        only thing that changes how tall the wrapped description needs to be.
        """
        grew = event.width != self._last_w
        self._last_w = event.width
        self._paint(measure=grew)

    def set_selected(self, on: bool) -> None:
        if on != self._selected:
            self._selected = on
            self._paint(measure=False)

    def _paint(self, measure: bool = True) -> None:
        self.delete("all")
        s = self._owner._s
        w = self.winfo_width() or s(500)
        h = self.winfo_height() or s(64)
        r = s(5)
        if self._selected:
            _grad_round(self, 1, 1, w - 2, h - 2, r, SEL_TOP, SEL_BOT)
            _outline_round(self, 1, 1, w - 2, h - 2, r, SEL_BORDER)
            self.create_line(1 + r, 2, w - 2 - r, 2, fill="#ffffff")
        elif self.focus_get() is self:
            _outline_round(self, 1, 1, w - 2, h - 2, r, SEL_BORDER,
                           dash=(2, 2))

        ir = s(8)
        _icon(self, self._icon, s(22), h / 2, ir,
              SEL_BORDER if self._selected else TEXT_DIM)
        left = s(42)
        self.create_text(left, s(17), anchor="w", text=self._title,
                         font=_f(self, 13, True), fill=TEXT)
        self.create_text(left, s(32), anchor="nw", text=self._body,
                         font=_f(self, 11),
                         fill=TEXT_DIM if self._selected else TEXT_FAINT,
                         width=max(s(180), w - left - s(14)))

        # Grow to fit the wrapped description rather than clipping it.
        if measure:
            items = self.find_all()
            if items:
                need = max(self.bbox(i)[3] for i in items) + s(9)
                if abs(need - h) > 2:
                    self.configure(height=int(need))
