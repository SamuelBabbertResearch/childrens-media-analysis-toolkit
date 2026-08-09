"""
gui_tables.py — MediaWiki-flavoured data tables for CMAT.

Replaces space-padded monospace blocks inside a Text widget with real tables:
sortable, selectable, aligned by column type, and readable at any DPI. Visual
language follows `wikitable` — hairline borders, a shaded header, alternating
row fill — because that is a convention researchers already read fluently.

MARKING UNUSUAL VALUES
----------------------
Two constraints shaped this, and the result is deliberately not what a web
mockup would do.

First, mechanics: a Tk Treeview applies tags per ROW, not per cell. Shading a
whole row because one of its seven columns is unusual misattributes which
measure was actually unusual, so cell-level shading is simply not expressible
here.

Second, and more important: CMAT does not rank shows. A red cell beside a high
flashing rate is read as "bad" by every user, whatever the caption says. So an
unusual value gets a MARKER GLYPH next to the number — ▲ above the set, ▽ below
it — which is per-cell, survives greyscale and colour blindness, and reads as
"unusual here" rather than "wrong".

The rule is Tukey's fences (outside Q1 − 1.5·IQR or Q3 + 1.5·IQR), which is
robust, assumes no distribution, and is standard enough to state in a methods
section. It is applied only when there are enough rows for the quartiles to
mean anything; below that the table says so instead of silently marking
nothing.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from gui_theme import apply_theme, color, dpi_scale, font, zebra_tags

# Below this many rows, quartiles are not worth computing: with 6 episodes a
# single value is 17% of the sample and the fences are meaningless.
MIN_ROWS_FOR_EMPHASIS = 8

MARK_HIGH = "▲"
MARK_LOW = "▽"


def tukey_fences(values: list[float]) -> tuple[float, float] | None:
    """(low, high) fences, or None when there is too little data to bother.

    Q1 − 1.5·IQR and Q3 + 1.5·IQR, using the common linear-interpolation
    definition of quartiles. Robust to the outliers it is trying to find,
    unlike a mean-and-SD rule.
    """
    clean = sorted(v for v in values if v is not None)
    if len(clean) < MIN_ROWS_FOR_EMPHASIS:
        return None

    def q(p: float) -> float:
        pos = p * (len(clean) - 1)
        lo = int(pos)
        hi = min(lo + 1, len(clean) - 1)
        return clean[lo] + (clean[hi] - clean[lo]) * (pos - lo)

    q1, q3 = q(0.25), q(0.75)
    iqr = q3 - q1
    if iqr <= 0:
        return None
    return q1 - 1.5 * iqr, q3 + 1.5 * iqr


def mark(value: float | None, fences: tuple[float, float] | None) -> str:
    """Glyph for a value against its column's fences; empty when ordinary."""
    if value is None or fences is None:
        return ""
    low, high = fences
    if value > high:
        return MARK_HIGH
    if value < low:
        return MARK_LOW
    return ""


class Column:
    """One table column.

    Numeric columns are right-aligned and are the only ones eligible for
    unusual-value marking. They are NOT monospaced: a ttk.Treeview applies one
    font to every column, and monospace is not needed anyway — Lucida Sans
    Unicode, Segoe UI and Consolas all render digits at a single fixed advance
    width, so right-alignment already makes a column of numbers scan cleanly.
    Forcing a mono face would only make episode titles look like source code.
    """

    def __init__(self, key: str, heading: str, width: int = 90,
                 numeric: bool = False, fmt: str = "{:.3f}",
                 stretch: bool = False) -> None:
        self.key = key
        self.heading = heading
        self.width = width
        self.numeric = numeric
        self.fmt = fmt
        self.stretch = stretch

    def render(self, value) -> str:
        if value is None:
            return "n/a"
        if self.numeric and isinstance(value, (int, float)):
            return self.fmt.format(value)
        return str(value)


class WikiTable(tk.Frame):
    """A styled, sortable data table with an optional caption and legend."""

    def __init__(self, parent, columns: list[Column], caption: str = "",
                 height: int = 8, emphasis: bool = True,
                 comparison_set: str = "the episodes listed here",
                 scrollbars: bool = True) -> None:
        super().__init__(parent, bg=color("panel_bg"))
        self._columns = columns
        self._emphasis = emphasis
        self._comparison_set = comparison_set
        self._rows: list[dict] = []
        self._sort: tuple[str, bool] | None = None
        apply_theme(self)

        if caption:
            tk.Label(self, text=caption, bg=color("panel_bg"),
                     fg=color("text"), font=font(self, "table", bold=True),
                     anchor="w").pack(fill=tk.X, pady=(0, 2))

        holder = tk.Frame(self, bg=color("mw_border"))
        holder.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(
            holder, style="CMAT.Treeview", show="headings", height=height,
            columns=[c.key for c in columns], selectmode="browse")
        # Column widths are declared at 96 DPI and scaled here. Raw pixel
        # widths truncate every heading on a 150% display — the text scales
        # with the font, the column does not.
        scale = dpi_scale(self)
        heading_font = font(self, "table", bold=True)
        measure = tkfont.Font(root=self, font=heading_font).measure
        for c in columns:
            wanted = int(round(c.width * scale))
            # Never narrower than the heading itself plus the sort affordance.
            wanted = max(wanted, measure(c.heading) + int(round(22 * scale)))
            self.tree.heading(c.key, text=c.heading,
                              command=lambda k=c.key: self._sort_by(k))
            self.tree.column(c.key, width=wanted,
                             minwidth=int(round(40 * scale)),
                             anchor="e" if c.numeric else "w",
                             stretch=c.stretch)
        # Scrollbars for a browsable table; suppressed for a short embedded
        # one, where a scrollbar beside six rows that all fit is pure noise.
        if scrollbars:
            # A seven-column metric table at 150% scaling needs roughly 900px
            # and the results pane can be half that, so horizontal scrolling
            # is what keeps the right-hand columns reachable at all.
            vsb = ttk.Scrollbar(holder, orient=tk.VERTICAL,
                                command=self.tree.yview)
            hsb = ttk.Scrollbar(holder, orient=tk.HORIZONTAL,
                                command=self.tree.xview)
            self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
            vsb.pack(side=tk.RIGHT, fill=tk.Y)
            hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1, pady=1)

        self._odd, self._even = zebra_tags(self.tree)
        self.tree.tag_configure("cmat_failed", foreground=color("status_blocked"))

        self._legend = tk.Label(
            self, bg=color("panel_bg"), fg=color("text_faint"),
            font=font(self, "small"), anchor="w", justify="left")
        self._legend.pack(fill=tk.X, pady=(2, 0))

    # ---- data ----

    def set_rows(self, rows: list[dict]) -> None:
        """Replace the contents. Each row is {column key: value}."""
        self._rows = list(rows)
        self._repopulate()

    def _fences(self) -> dict[str, tuple[float, float] | None]:
        if not self._emphasis:
            return {}
        out = {}
        for c in self._columns:
            if not c.numeric:
                continue
            values = [r.get(c.key) for r in self._rows]
            numeric = [v for v in values if isinstance(v, (int, float))]
            out[c.key] = tukey_fences(numeric)
        return out

    def _repopulate(self) -> None:
        self.tree.delete(*self.tree.get_children())
        fences = self._fences()

        rows = list(self._rows)
        if self._sort:
            key, desc = self._sort
            col = next((c for c in self._columns if c.key == key), None)

            def sort_key(r):
                v = r.get(key)
                if col and col.numeric:
                    return v if isinstance(v, (int, float)) else float("-inf")
                return str(v or "").lower()

            rows.sort(key=sort_key, reverse=desc)

        marked = 0
        for i, r in enumerate(rows):
            values = []
            for c in self._columns:
                text = c.render(r.get(c.key))
                if c.numeric:
                    glyph = mark(r.get(c.key), fences.get(c.key))
                    if glyph:
                        marked += 1
                        text = f"{text} {glyph}"
                values.append(text)
            tags = [self._even if i % 2 else self._odd]
            if r.get("_failed"):
                tags.append("cmat_failed")
            self.tree.insert("", tk.END, values=values, tags=tags)

        self._update_legend(fences, marked)

    def _update_legend(self, fences: dict, marked: int) -> None:
        if not self._emphasis:
            self._legend.configure(text="")
            return
        n = len(self._rows)
        if n < MIN_ROWS_FOR_EMPHASIS:
            self._legend.configure(
                text=f"Unusual-value marking needs at least "
                     f"{MIN_ROWS_FOR_EMPHASIS} rows to be meaningful "
                     f"({n} here), so nothing is marked.")
        elif marked:
            self._legend.configure(
                text=f"{MARK_HIGH} above / {MARK_LOW} below 1.5×IQR for "
                     f"{self._comparison_set} (n={n}). Unusual for this set — "
                     f"not a judgement of quality or suitability.")
        else:
            self._legend.configure(
                text=f"No values fall outside 1.5×IQR for "
                     f"{self._comparison_set} (n={n}).")

    def _sort_by(self, key: str) -> None:
        if self._sort and self._sort[0] == key:
            self._sort = (key, not self._sort[1])
        else:
            self._sort = (key, True)
        self._repopulate()

    # ---- embedding ----

    def embed_in(self, text: tk.Text) -> None:
        """Place this table at the end of a Text widget.

        The results panel is a narrative report with a few tabular sections;
        embedding keeps the prose and gives the tables real columns, instead of
        rebuilding the whole panel.
        """
        text.window_create(tk.END, window=self, padx=4, pady=4)
        text.insert(tk.END, "\n")


# ---------------------------------------------------------------------------
# Status badges
# ---------------------------------------------------------------------------

BADGE_STYLES = {
    "ready":    ("badge_ready_bg", "badge_ready_fg"),
    "analyzed": ("badge_analyzed_bg", "badge_analyzed_fg"),
    "none":     ("badge_none_bg", "badge_none_fg"),
}


class Badge(tk.Label):
    """A small pill showing the state of the WORK on an item.

    Deliberately limited to workflow state — analyzed, coded, not yet
    measured. A badge is the most eye-catching thing in a panel, so it must
    never carry a property of the programme itself: "Analyzed" means a
    measurement exists, not that the measurement found anything good.
    """

    def __init__(self, parent, text: str, kind: str = "none", **kw) -> None:
        bg_token, fg_token = BADGE_STYLES.get(kind, BADGE_STYLES["none"])
        super().__init__(parent, text=f" {text} ", bg=color(bg_token),
                         fg=color(fg_token), font=font(parent, "small", bold=True),
                         padx=int(round(4 * dpi_scale(parent))), **kw)


class PropertyTable(tk.Frame):
    """A bordered label/value grid in the MediaWiki `wikitable` idiom.

    Deliberately built from Labels rather than a Treeview: these rows are
    key/value facts, not records. They never need sorting or selection, they
    should size to their content rather than scroll, and a dozen embedded
    Treeviews in one report is a great deal of machinery for what is really
    a definition list.
    """

    def __init__(self, parent, rows=(), value_width: int = 0, **kw) -> None:
        super().__init__(parent, bg=color("mw_border"), **kw)
        self._pad = int(round(5 * dpi_scale(self)))
        self._value_width = value_width
        self._cells: list[tk.Widget] = []
        # No column stretches: the table is content-width, as a wikitable is
        # unless it explicitly asks for 100%. Stretching the value column
        # flings a two-character number to the far edge of the pane, and
        # stretching the notes leaves a wide empty box on every row without one.
        if rows:
            self.set_rows(rows)

    def set_rows(self, rows) -> None:
        """rows: [(label, value)] or [(label, value, note)]."""
        for c in self._cells:
            c.destroy()
        self._cells.clear()

        for i, row in enumerate(rows):
            label, value = row[0], row[1]
            note = row[2] if len(row) > 2 else ""

            k = tk.Label(self, text=label, bg=color("mw_label_bg"),
                         fg=color("text"), font=font(self, "table", bold=True),
                         anchor="w", padx=self._pad,
                         pady=int(self._pad * 0.55))
            k.grid(row=i, column=0, sticky="nsew", padx=(1, 0),
                   pady=(1 if i == 0 else 0, 1))

            v = tk.Label(self, text=str(value), bg=color("mw_bg"),
                         fg=color("text"), font=font(self, "table"),
                         anchor="e", padx=self._pad,
                         pady=int(self._pad * 0.55),
                         width=self._value_width or 0)
            v.grid(row=i, column=1, sticky="nsew", padx=(1, 0),
                   pady=(1 if i == 0 else 0, 1))
            self._cells += [k, v]

            n = tk.Label(self, text=note, bg=color("mw_bg"),
                         fg=color("text_dim"), font=font(self, "small"),
                         anchor="w", justify="left", padx=self._pad,
                         pady=int(self._pad * 0.55))
            n.grid(row=i, column=2, sticky="nsew", padx=(1, 1),
                   pady=(1 if i == 0 else 0, 1))
            self._cells.append(n)

    def embed_in(self, text: tk.Text) -> None:
        text.window_create(tk.END, window=self, padx=6, pady=3)
        text.insert(tk.END, "\n")


class InfoboxPanel(tk.Frame):
    """MediaWiki-style key/value inspector: shaded key column, boxed values.

    Values may be plain strings or (text, badge_kind) pairs, which render as a
    pill instead of text.
    """

    def __init__(self, parent, title: str = "", **kw) -> None:
        super().__init__(parent, bg=color("mw_subtle_bg"),
                         highlightthickness=1,
                         highlightbackground=color("mw_border"), **kw)
        s = dpi_scale(self)
        self._pad = int(round(5 * s))

        self._title = tk.Label(
            self, text=title or "Nothing selected", bg=color("mw_header_bg"),
            fg=color("text"), font=font(self, "heading", bold=True),
            pady=int(round(3 * s)), highlightthickness=1,
            highlightbackground=color("mw_border"))
        self._title.pack(fill=tk.X, padx=self._pad, pady=(self._pad, self._pad))

        self._rows = tk.Frame(self, bg=color("mw_subtle_bg"))
        self._rows.pack(fill=tk.BOTH, expand=True,
                        padx=self._pad, pady=(0, self._pad))
        self._rows.columnconfigure(1, weight=1)
        self._widgets: list[tk.Widget] = []

    def set_rows(self, title: str, pairs) -> None:
        """Replace the contents. pairs is [(key, value_or_(text, badge_kind))]."""
        self._title.configure(text=title or "Nothing selected")
        for w in self._widgets:
            w.destroy()
        self._widgets.clear()

        for i, (key, value) in enumerate(pairs):
            k = tk.Label(self._rows, text=key, bg=color("mw_label_bg"),
                         fg=color("text"), font=font(self, "body", bold=True),
                         anchor="w", padx=self._pad, pady=int(self._pad * 0.6),
                         highlightthickness=1,
                         highlightbackground=color("mw_border"))
            k.grid(row=i, column=0, sticky="nsew")

            if isinstance(value, tuple):
                holder = tk.Frame(self._rows, bg=color("mw_bg"),
                                  highlightthickness=1,
                                  highlightbackground=color("mw_border"))
                Badge(holder, value[0], value[1]).pack(
                    anchor="w", padx=self._pad, pady=int(self._pad * 0.5))
                holder.grid(row=i, column=1, sticky="nsew")
                self._widgets.append(holder)
            else:
                v = tk.Label(self._rows, text=str(value), bg=color("mw_bg"),
                             fg=color("text"), font=font(self, "body"),
                             anchor="w", justify="left", padx=self._pad,
                             pady=int(self._pad * 0.6), highlightthickness=1,
                             highlightbackground=color("mw_border"))
                v.grid(row=i, column=1, sticky="nsew")
                self._widgets.append(v)
            self._widgets.append(k)
