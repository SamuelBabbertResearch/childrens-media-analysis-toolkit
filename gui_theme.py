"""
gui_theme.py — the single source of truth for CMAT's visual tokens.

Everything the interface draws takes its colours, type sizes, and ttk styling
from here. Before this existed the pipeline editor carried its own palette and
the rest of the app used ad-hoc literals, which is how two different greys and
two different blues ended up meaning "selected".

INFLUENCES
----------
Early OS X (Snow Leopard / Lion era) for the window chrome: cool greys, hairline
separators, a one-pixel gloss, restrained accent. MediaWiki for the data
presentation: `wikitable` borders, `infobox` property lists, `ambox` callouts.
The first gives a desktop tool that feels like an instrument; the second gives
tables a researcher already knows how to read.

TWO FONT CONVENTIONS, ON PURPOSE
--------------------------------
Widgets use POINT sizes. Tk scales points by `tk scaling`, which main() sets to
dpi/72, so 9pt is 12px at 100% and 18px at 150% — correct on any display.

Canvas text uses PIXEL sizes (negative), because the pipeline editor recomputes
its fonts at every zoom level so the font engine renders each size natively
rather than stretching a bitmap. canvas_font() derives those pixels from the
same point values, so chrome and canvas agree at 100% zoom instead of drifting.

STIMULUS-ONLY GUARDRAIL
-----------------------
No token here encodes a judgement, and none should be added. CMAT measures
properties of the video and its audio; it does not rate appropriateness,
target age, or educational value. That constraint reaches the theme in one
concrete place — see OUTLIER_LEGEND and outlier_tags() — because a red cell
beside a high number is read as "bad" whatever the documentation says.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

# ---------------------------------------------------------------------------
# Colour tokens
# ---------------------------------------------------------------------------

COLORS: dict[str, str] = {
    # --- window chrome (early OS X) ---------------------------------------
    "chrome_top":     "#f4f5f7",
    "chrome_bottom":  "#dcdee2",
    "chrome_line":    "#a8abb1",
    "window_bg":      "#ececec",
    "surface_top":    "#fbfbfc",
    "surface_bottom": "#eef0f3",
    "inspector_bg":   "#f6f7f8",
    "footer_bg":      "#e8eaed",

    # --- panels and separators --------------------------------------------
    "panel_bg":     "#ffffff",
    "panel_border": "#b8b8b8",
    "panel_header": "#e2e2e2",
    "tab_bg":       "#e1e1e1",   # unselected tab
    "tab_fg":       "#4a4d52",
    "tab_active":   "#eaebed",   # hover
    "hairline":     "#c8cbd0",
    "grid_dot":     "#d7dade",

    # --- type --------------------------------------------------------------
    "text":          "#202122",   # MediaWiki near-black; reads as ink, not pure
    "text_dim":      "#54595d",
    "text_faint":    "#8d9198",
    "text_disabled": "#a9adb3",
    "text_on_accent": "#ffffff",
    "link":          "#3366cc",

    # --- one accent, used only for selection and focus ---------------------
    "accent":        "#2b73de",
    "accent_dark":   "#1255b8",
    "accent_glow":   "#a9c8ea",
    "accent_fill_top":    "#f6faff",
    "accent_fill_bottom": "#dbe8f8",

    # --- controls ----------------------------------------------------------
    "control_top":      "#fdfdfe",
    "control_bottom":   "#e4e6ea",
    "control_border":   "#9ea1a7",
    "control_gloss":    "#ffffff",
    "control_shadow":   "#c2c5ca",
    "control_disabled_top":    "#f2f3f4",
    "control_disabled_bottom": "#e9eaec",

    # --- MediaWiki data presentation ---------------------------------------
    "mw_bg":        "#ffffff",
    "mw_subtle_bg": "#f8f9fa",
    "mw_header_bg": "#eaecf0",
    "mw_border":    "#a2a9b1",
    "mw_row_line":  "#eaecf0",

    # --- callouts (ambox) ---------------------------------------------------
    "info_bg":     "#f0f6ff",
    "info_border": "#a3c7ee",
    "info_rule":   "#3366cc",
    "info_text":   "#0f4f96",
    "warn_bg":     "#fffbe6",
    "warn_border": "#e8d9a0",
    "warn_rule":   "#a76a00",
    "warn_text":   "#5c4400",

    # --- pipeline stage status ---------------------------------------------
    # Load-bearing: every node shows one of these, always with a word and a
    # glyph beside it so the state never depends on colour alone.
    "status_complete": "#3c7a36",
    "status_partial":  "#9a6714",
    "status_pending":  "#767b82",
    "status_blocked":  "#8c3a36",

    # --- emphasis for values that stand out from a comparison set ----------
    # NOT a verdict. See OUTLIER_LEGEND.
    "emphasis_high_bg": "#fde8e8",
    "emphasis_high_fg": "#9b1c1c",
    "emphasis_low_bg":  "#e1effe",
    "emphasis_low_fg":  "#1e429f",
}


def color(name: str) -> str:
    """Look up a token. Unknown names raise rather than silently rendering black."""
    try:
        return COLORS[name]
    except KeyError:
        raise KeyError(
            f"Unknown theme colour {name!r}. Add it to gui_theme.COLORS rather "
            f"than using a literal — two sources of truth is how the app ended "
            f"up with two different blues meaning 'selected'."
        ) from None


# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

# Point sizes. 9pt is the Windows system default and the density this kind of
# instrument wants; the earlier draft's "11px" was a units error — Snow
# Leopard's 11 was POINTS, which is ~15px at today's densities.
FONT_PT: dict[str, int] = {
    "tiny":    8,
    "small":   8,
    "body":    9,
    "table":   9,
    "heading": 11,
    "title":   13,
}

# First available wins. Worth knowing what this actually resolves to on
# Windows: Lucida Grande is Mac-only, so the real pick is Lucida Sans Unicode —
# a genuine Lucida face, closest to the OS X reference, but wide and softly
# hinted at small sizes. Put "Segoe UI" first for a crisper, more modern face
# at the cost of the period character. One line, deliberately visible.
UI_FAMILY_PREFERENCE = ("Lucida Grande", "Lucida Sans Unicode",
                        "Segoe UI", "Tahoma")
MONO_FAMILY_PREFERENCE = ("Consolas", "Menlo", "DejaVu Sans Mono",
                          "Courier New")

_FAMILY: str | None = None
_MONO: str | None = None


def _first_available(widget: tk.Misc, preference: tuple[str, ...],
                     fallback: str) -> str:
    try:
        available = set(tkfont.families(widget))
    except Exception:
        return fallback
    for candidate in preference:
        if candidate in available:
            return candidate
    return fallback


def family(widget: tk.Misc) -> str:
    """Preferred UI face — see UI_FAMILY_PREFERENCE."""
    global _FAMILY
    if _FAMILY is None:
        _FAMILY = _first_available(widget, UI_FAMILY_PREFERENCE, "Segoe UI")
    return _FAMILY


def mono_family(widget: tk.Misc) -> str:
    """Fixed-pitch face — for content that needs column-exact CHARACTERS.

    Reserved for things like timestamps in the coding editor and raw
    provenance output. NOT for table numbers: every face in the UI stack
    renders digits at one fixed advance width, so right-alignment already
    aligns a numeric column, and a mono face there would only make the
    surrounding text look like source code.

    Never use this for UI body text or labels.
    """
    global _MONO
    if _MONO is None:
        _MONO = _first_available(widget, MONO_FAMILY_PREFERENCE, "Courier")
    return _MONO


def font(widget: tk.Misc, role: str = "body", bold: bool = False,
         mono: bool = False) -> tuple:
    """Widget font in POINTS — Tk scales these by tk scaling for the display."""
    size = FONT_PT.get(role, FONT_PT["body"])
    name = mono_family(widget) if mono else family(widget)
    return (name, size, "bold") if bold else (name, size)


def dpi_scale(widget: tk.Misc) -> float:
    """Display density relative to 96 DPI, clamped to a sane range."""
    try:
        return max(1.0, min(3.0, widget.winfo_fpixels("1i") / 96.0))
    except Exception:
        return 1.0


def canvas_font(widget: tk.Misc, role: str = "body", zoom: float = 1.0,
                bold: bool = False, mono: bool = False,
                scale: float | None = None) -> tuple:
    """Canvas font in PIXELS, derived from the same point sizes.

    A negative Tk size is pixels, which is what canvas text needs: the pipeline
    editor rebuilds its fonts on every zoom change so each size is rendered
    natively instead of being scaled up from one bitmap.
    """
    pt = FONT_PT.get(role, FONT_PT["body"])
    factor = dpi_scale(widget) if scale is None else scale
    px = max(7, int(round(pt * (96.0 / 72.0) * factor * zoom)))
    name = mono_family(widget) if mono else family(widget)
    return (name, -px, "bold") if bold else (name, -px)


# ---------------------------------------------------------------------------
# Emphasis that is not a verdict
# ---------------------------------------------------------------------------

OUTLIER_LEGEND = (
    "Highlighted values are unusual for the comparison set shown — not "
    "judgements of quality, suitability, or effect on a viewer."
)

# Default to weight, not colour. Red beside a high number reads as "bad" to
# every user regardless of what the caption says, and CMAT does not rank shows.
EMPHASIS_NEUTRAL = "neutral"
EMPHASIS_COLOR = "color"


def outlier_tags(widget, mode: str = EMPHASIS_NEUTRAL,
                 role: str = "table") -> tuple[str, str]:
    """Configure high/low emphasis tags on a Text or Treeview.

    Returns the two tag names. Callers MUST display OUTLIER_LEGEND wherever
    these are used — an unexplained coloured cell is an implied verdict.
    """
    high, low = "cmat_high", "cmat_low"
    if mode == EMPHASIS_COLOR:
        high_opts = {"background": color("emphasis_high_bg"),
                     "foreground": color("emphasis_high_fg")}
        low_opts = {"background": color("emphasis_low_bg"),
                    "foreground": color("emphasis_low_fg")}
    else:
        bold = font(widget, role, bold=True)
        high_opts = {"font": bold}
        low_opts = {"font": bold, "foreground": color("text_dim")}

    if isinstance(widget, ttk.Treeview):
        widget.tag_configure(high, **high_opts)
        widget.tag_configure(low, **low_opts)
    else:
        widget.tag_configure(high, **high_opts)
        widget.tag_configure(low, **low_opts)
    return high, low


# ---------------------------------------------------------------------------
# ttk styling
# ---------------------------------------------------------------------------

def apply_theme(root: tk.Misc) -> ttk.Style:
    """Style ttk widgets to match. Safe to call more than once.

    Uses the 'clam' theme as the base because the native Windows theme ignores
    most colour options — you cannot restyle a native Treeview header on Win32,
    and a half-styled table looks worse than an unstyled one.
    """
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    body = font(root, "body")
    table = font(root, "table")
    header = font(root, "table", bold=True)

    style.configure(".", font=body, background=color("window_bg"),
                    foreground=color("text"))

    # --- wikitable-flavoured Treeview -------------------------------------
    style.configure(
        "CMAT.Treeview",
        background=color("mw_bg"), fieldbackground=color("mw_bg"),
        foreground=color("text"), font=table,
        bordercolor=color("mw_border"), borderwidth=1, relief="solid",
        rowheight=max(18, int(round(19 * dpi_scale(root)))),
    )
    style.configure(
        "CMAT.Treeview.Heading",
        background=color("mw_header_bg"), foreground=color("text"),
        font=header, relief="flat", borderwidth=1,
        bordercolor=color("mw_border"),
    )
    style.map(
        "CMAT.Treeview.Heading",
        background=[("active", color("panel_header"))],
    )
    style.map(
        "CMAT.Treeview",
        background=[("selected", color("accent"))],
        foreground=[("selected", color("text_on_accent"))],
    )

    # --- notebook ----------------------------------------------------------
    # Unselected tabs are styled explicitly: with only a `map` for the
    # selected state, the clam defaults show through for every other tab and
    # the strip does not match the surrounding chrome.
    pad_x, pad_y = (int(round(10 * dpi_scale(root))),
                    int(round(4 * dpi_scale(root))))
    style.configure("TNotebook", background=color("window_bg"), borderwidth=0,
                    tabmargins=(2, 2, 2, 0))
    style.configure("TNotebook.Tab", font=body, padding=(pad_x, pad_y),
                    background=color("tab_bg"), foreground=color("tab_fg"),
                    borderwidth=1, bordercolor=color("chrome_line"))
    style.map(
        "TNotebook.Tab",
        # Selected uses the panel colour so the tab reads as continuous with
        # the content below it, and the near-black ink rather than pure black.
        background=[("selected", color("panel_bg")),
                    ("active", color("tab_active"))],
        foreground=[("selected", color("text")),
                    ("active", color("text"))],
        expand=[("selected", (0, 0, 0, 1))],
    )

    # --- scrollbars and controls -------------------------------------------

    style.configure("TCombobox", font=body, arrowsize=12)
    style.configure("Vertical.TScrollbar", background=color("chrome_bottom"),
                    troughcolor=color("surface_bottom"),
                    bordercolor=color("chrome_line"), arrowsize=12)
    style.configure("Horizontal.TScrollbar", background=color("chrome_bottom"),
                    troughcolor=color("surface_bottom"),
                    bordercolor=color("chrome_line"), arrowsize=12)
    style.configure("TSeparator", background=color("hairline"))
    return style


def zebra_tags(tree: ttk.Treeview) -> tuple[str, str]:
    """Alternating row shading, MediaWiki style. Returns (odd, even) tag names."""
    tree.tag_configure("cmat_odd", background=color("mw_bg"))
    tree.tag_configure("cmat_even", background=color("mw_subtle_bg"))
    return "cmat_odd", "cmat_even"
