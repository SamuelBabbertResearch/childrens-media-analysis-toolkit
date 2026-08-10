"""
ui/tokens.py — the design tokens, with no framework imports at all.

Deliberately free of both tkinter and Qt so the two front-ends share ONE
palette during the migration. gui_theme.py (Tk) and ui/theme.py (Qt) both read
from here; when the Tk front-end is retired this file stays exactly as it is.

STIMULUS-ONLY GUARDRAIL
-----------------------
No token encodes a judgement, and none should be added. CMAT measures
properties of the video and its audio; it does not rate appropriateness,
target age, or educational value.
"""

from __future__ import annotations

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
    "hairline":     "#c8cbd0",
    "grid_dot":     "#d7dade",
    "tab_bg":       "#e1e1e1",
    "tab_fg":       "#444444",
    "tab_active":   "#eaebed",

    # --- type --------------------------------------------------------------
    "text":           "#202122",
    "text_dim":       "#54595d",
    "text_faint":     "#8d9198",
    "text_disabled":  "#a9adb3",
    "text_on_accent": "#ffffff",
    "link":           "#3366cc",

    # --- one accent, used only for selection and focus ---------------------
    "accent":             "#2b73de",
    "accent_dark":        "#1255b8",
    "accent_glow":        "#a9c8ea",
    "accent_fill_top":    "#f6faff",
    "accent_fill_bottom": "#dbe8f8",

    # --- controls ----------------------------------------------------------
    "control_top":             "#ffffff",
    "control_bottom":          "#e2e2e2",
    "control_border":          "#999999",
    # Darker top edge only — how a sunken control is drawn when the toolkit
    # has no inset shadow.
    "control_border_dark":     "#666666",
    "control_gloss":           "#ffffff",
    "control_fg":              "#222222",
    "control_shadow":          "#c2c5ca",
    "control_disabled_top":    "#f2f3f4",
    "control_disabled_bottom": "#e9eaec",
    "control_hover_top":       "#ffffff",
    "control_hover_bottom":    "#eaecf0",
    "control_pressed_top":     "#d0d0d0",
    "control_pressed_bottom":  "#e6e6e6",

    # --- MediaWiki data presentation ---------------------------------------
    "mw_bg":           "#ffffff",
    "mw_subtle_bg":    "#f8f9fa",
    "mw_header_bg":    "#eaecf0",
    "mw_label_bg":     "#f2f2f2",
    "mw_border":       "#a2a9b1",
    "mw_row_line":     "#eaecf0",
    "row_selected_bg": "#e8f2ff",

    # --- menu bar and tab strip (see ui/DESIGN.md §8) -----------------------
    "menu_bg":       "#e5e5e5",
    "menu_line":     "#c0c0c0",
    "tabstrip_top":    "#d5d5d5",
    "tabstrip_bottom": "#c0c0c0",
    "tab_inactive_top":    "#cecece",
    "tab_inactive_bottom": "#b8b8b8",

    # --- sub-toolbar: per-tab controls, below the tab strip -----------------
    "subbar_top":    "#ececec",
    "subbar_bottom": "#d8d8d8",

    # --- toolbar ------------------------------------------------------------
    "toolbar_top":    "#e6e6e6",
    "toolbar_bottom": "#d5d5d5",

    # --- status bar ---------------------------------------------------------
    "statusbar_top":    "#e2e2e2",
    "statusbar_bottom": "#cccccc",
    "statusbar_line":   "#a6a6a6",
    "statusbar_fg":     "#333333",

    # --- graph canvas -------------------------------------------------------
    "canvas_bg":   "#eaeaea",
    "canvas_grid": "#e0e0e0",
    "node_bg":     "#ffffff",
    "node_border": "#999999",
    "node_rule":   "#ececec",
    "node_status": "#888888",
    "port_fill":   "#ffffff",
    "port_border": "#666666",
    "wire":        "#666666",

    # --- default (Aqua) button ---------------------------------------------
    "aqua_top":     "#429ce3",
    "aqua_bottom":  "#1066c7",
    "aqua_border":  "#0f4f96",
    "aqua_pressed_top":    "#0d56aa",
    "aqua_pressed_bottom": "#257ecb",

    # --- inspector key/value grid -------------------------------------------
    "kv_key_bg":   "#f0f0f0",
    "kv_key_fg":   "#444444",
    "kv_val_fg":   "#222222",
    "kv_key_line": "#e0e0e0",
    "kv_row_line": "#e5e5e5",

    # --- report typography and note boxes -----------------------------------
    "section_title": "#0f4f96",   # section headings, same blue as the ambox
    "note_bg":       "#f8f9fa",
    "note_border":   "#e0e0e0",
    "rule_soft":     "#d9d9d9",

    # --- views --------------------------------------------------------------
    "row_hover":      "#f0f4f9",
    "table_header":   "#eaeaea",
    "table_alt_row":  "#f9f9f9",
    "table_cell_line": "#d0d0d0",
    "table_gridline":  "#d8d8d8",

    # --- path display -------------------------------------------------------
    "path_text": "#003a70",

    # --- modal framing (see ui/DESIGN.md §1) --------------------------------
    "window_ring":   "#7a7a7a",
    "dialog_seam":   "#b0b0b0",
    "action_bar_top":    "#e2e2e2",
    "action_bar_bottom": "#d0d0d0",
    # The application draws its own title bar (ui/native_frame.py) while the
    # window keeps its real Win32 frame styles, so snap, edge resizing, the
    # system menu and the maximise animation still come from Windows.
    "titlebar_top":    "#e6e6e6",
    "titlebar_bottom": "#d1d1d1",
    "titlebar_line":   "#a6a6a6",
    "titlebar_fg":     "#333333",
    "light_close": "#ff5f56",
    "light_min":   "#ffbd2e",
    "light_max":   "#27c93f",

    # --- list views (see ui/DESIGN.md §3) -----------------------------------
    "list_divider":     "#f0f0f0",
    "list_sunken_edge": "#666666",
    # Secondary text on a selected row, where the fill is the solid accent.
    "text_on_accent_dim": "#e0ecff",

    # --- form validation ----------------------------------------------------
    # Paired with a word or glyph, never colour alone.
    "valid_ok": "#1b7a2b",

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
    "status_complete": "#3c7a36",
    "status_partial":  "#9a6714",
    "status_pending":  "#767b82",
    "status_blocked":  "#8c3a36",

    # --- status badges ------------------------------------------------------
    "badge_ready_bg":    "#e6f4ea",
    "badge_ready_fg":    "#137333",
    "badge_analyzed_bg": "#e8f0fe",
    "badge_analyzed_fg": "#1a73e8",
    "badge_none_bg":     "#f0f1f3",
    "badge_none_fg":     "#54595d",

    # --- emphasis for values unusual within a comparison set ---------------
    # NOT a verdict. Always shown with a legend naming the comparison set.
    "emphasis_high_bg": "#fde8e8",
    "emphasis_high_fg": "#9b1c1c",
    "emphasis_low_bg":  "#e1effe",
    "emphasis_low_fg":  "#1e429f",
}

# Sizes in DEVICE-INDEPENDENT PIXELS.
#
# This is safe in Qt and would not have been in Tk. Qt 6 scales the whole UI by
# the display's device-pixel ratio, so a "px" in a stylesheet is a logical unit
# that becomes 1.5 physical pixels at 150% — the same scaling a point size
# gets. In Tk a pixel was a physical pixel, which is why the equivalent Tk
# tokens are points and why copying a pixel value from a period specification
# was a units error there.
#
# The reference layouts are a dense desktop utility: 11px text against 19-20px
# controls. Qt's own defaults are considerably airier, so every box metric has
# to be stated explicitly or the interface drifts 20-50% taller than intended.
FONT_PX: dict[str, int] = {
    "tiny":    9,
    "small":   10,
    "body":    11,
    "table":   11,
    "grid":    11,   # library grid rows; .tree-row in the reference
    "heading": 12,
    "title":   13,
}

# Control geometry, likewise from the reference layouts.
METRICS: dict[str, int] = {
    "control_h":   20,   # buttons, inputs, combos
    "row_h":       19,   # tree and table rows
    "header_h":    20,   # view header sections
    "titlebar_h":  24,
    "tab_pad_x":   10,
    "tab_pad_y":   3,
    "radius":      3,
    "radius_tight": 2,
}

# Retained for the Tkinter front-end, which measures in points. Do not use for
# Qt — see FONT_PX above.
FONT_PT: dict[str, int] = {
    "tiny":    8,
    "small":   8,
    "body":    9,
    "table":   9,
    "heading": 11,
    "title":   13,
}

# First available wins, and this order is the reference stack resolved for
# Windows. The reference asks for
#     -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto,
#     Helvetica, Arial
# in which every face ahead of Segoe UI is a macOS system font, so on Windows
# it renders in Segoe UI. Naming a Lucida first was a mistake: it is the
# closer period reference, but it is wide and softly hinted at 11px, and it
# changed the texture of every string in the application away from the
# reference rather than towards it.
UI_FAMILY_PREFERENCE = ("Segoe UI", "Roboto", "Helvetica", "Arial", "Tahoma")

# Fixed-pitch, for content needing column-exact CHARACTERS: coding-sheet
# timestamps, raw provenance. NOT for table numbers — every face above renders
# digits at one fixed advance width, so right-alignment already aligns a
# numeric column.
MONO_FAMILY_PREFERENCE = ("Consolas", "Menlo", "DejaVu Sans Mono",
                          "Courier New")

OUTLIER_LEGEND = (
    "Highlighted values are unusual for the comparison set shown — not "
    "judgements of quality, suitability, or effect on a viewer."
)


def color(name: str) -> str:
    """Look up a token. Unknown names raise rather than rendering black."""
    try:
        return COLORS[name]
    except KeyError:
        raise KeyError(
            f"Unknown theme colour {name!r}. Add it to ui.tokens.COLORS rather "
            f"than using a literal — two sources of truth is how the app ended "
            f"up with two different blues meaning 'selected'."
        ) from None
