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
    # --- modern scientific desktop surfaces ------------------------------
    "chrome_top":     "#fbfcfd",
    "chrome_bottom":  "#f4f6f8",
    "chrome_line":    "#d5dbe3",
    "window_bg":      "#f3f5f7",
    "surface_top":    "#ffffff",
    "surface_bottom": "#f8fafc",
    "inspector_bg":   "#f8fafc",
    "footer_bg":      "#f1f4f7",

    # --- panels and separators --------------------------------------------
    "panel_bg":     "#ffffff",
    "panel_border": "#d5dbe3",
    "panel_header": "#f4f6f8",
    "hairline":     "#e1e5ea",
    "grid_dot":     "#dde3e9",
    "tab_bg":       "#eef1f4",
    "tab_fg":       "#52606d",
    "tab_active":   "#f8fafc",

    # --- type --------------------------------------------------------------
    "text":           "#1f2933",
    "text_dim":       "#52606d",
    "text_faint":     "#7b8794",
    "text_disabled":  "#a6afb9",
    "text_on_accent": "#ffffff",
    "link":           "#2563eb",

    # --- one accent, used only for selection and focus ---------------------
    "accent":             "#2563eb",
    "accent_dark":        "#1d4ed8",
    "accent_glow":        "#bfdbfe",
    "accent_fill_top":    "#eff6ff",
    "accent_fill_bottom": "#dbeafe",

    # --- controls ----------------------------------------------------------
    "control_top":             "#ffffff",
    "control_bottom":          "#ffffff",
    "control_border":          "#c3cad3",
    # Darker top edge only — how a sunken control is drawn when the toolkit
    # has no inset shadow.
    "control_border_dark":     "#aeb7c2",
    "control_gloss":           "#ffffff",
    "control_fg":              "#273444",
    "control_shadow":          "#d9dee5",
    "control_disabled_top":    "#f4f6f8",
    "control_disabled_bottom": "#f4f6f8",
    "control_hover_top":       "#f8fafc",
    "control_hover_bottom":    "#f8fafc",
    "control_pressed_top":     "#e8edf3",
    "control_pressed_bottom":  "#e8edf3",

    # --- MediaWiki data presentation ---------------------------------------
    "mw_bg":           "#ffffff",
    "mw_subtle_bg":    "#f8f9fa",
    "mw_header_bg":    "#f3f5f7",
    "mw_label_bg":     "#f6f8fa",
    "mw_border":       "#d5dbe3",
    "mw_row_line":     "#e7ebef",
    "row_selected_bg": "#eaf2ff",

    # --- menu bar and tab strip (see ui/DESIGN.md §8) -----------------------
    "menu_bg":       "#ffffff",
    "menu_line":     "#e1e5ea",
    "tabstrip_top":    "#f8fafc",
    "tabstrip_bottom": "#f8fafc",
    "tab_inactive_top":    "#f8fafc",
    "tab_inactive_bottom": "#f8fafc",

    # --- sub-toolbar: per-tab controls, below the tab strip -----------------
    "subbar_top":    "#f8fafc",
    "subbar_bottom": "#f8fafc",

    # --- toolbar ------------------------------------------------------------
    "toolbar_top":    "#ffffff",
    "toolbar_bottom": "#ffffff",

    # --- status bar ---------------------------------------------------------
    "statusbar_top":    "#ffffff",
    "statusbar_bottom": "#ffffff",
    "statusbar_line":   "#dfe4ea",
    "statusbar_fg":     "#52606d",

    # --- graph canvas -------------------------------------------------------
    "canvas_bg":   "#eef2f6",
    "canvas_grid": "#dce3ea",
    "node_bg":     "#ffffff",
    "node_border": "#cbd3dc",
    "node_rule":   "#e7ebef",
    "node_status": "#6b7785",
    "port_fill":   "#ffffff",
    "port_border": "#7b8794",
    "wire":        "#7b8794",

    # --- default (Aqua) button ---------------------------------------------
    "aqua_top":     "#2563eb",
    "aqua_bottom":  "#2563eb",
    "aqua_border":  "#1d4ed8",
    "aqua_pressed_top":    "#1d4ed8",
    "aqua_pressed_bottom": "#1d4ed8",

    # --- inspector key/value grid -------------------------------------------
    "kv_key_bg":   "#f6f8fa",
    "kv_key_fg":   "#52606d",
    "kv_val_fg":   "#1f2933",
    "kv_key_line": "#e1e5ea",
    "kv_row_line": "#e7ebef",

    # --- report typography and note boxes -----------------------------------
    "section_title": "#1d4ed8",   # section headings, same blue as the ambox
    "note_bg":       "#f8f9fa",
    "note_border":   "#e0e0e0",
    "rule_soft":     "#d9d9d9",

    # --- dialogs (ui/reference/dialogs.css) ---------------------------------
    # A dialog is a small window, not a differently-styled object: it uses the
    # window chrome, the window colour and the one accent. An earlier mockup
    # gave dialogs their own #F0F0F0 ground, 22px buttons and a second blue;
    # that file was the odd one out of the three and is superseded.
    "dialog_content_bg": "#f3f5f7",
    "fieldset_bg":       "#ffffff",
    "legend_fg":         "#273444",
    "total_ok_fg":       "#1b7a2b",

    # --- views --------------------------------------------------------------
    "row_hover":      "#f3f7fc",
    "scroll_handle":       "#c6ced8",
    "scroll_handle_hover": "#9eabb8",
    "table_header":   "#f3f5f7",
    "table_alt_row":  "#fafbfc",
    "table_cell_line": "#e2e7ec",
    "table_gridline":  "#e2e7ec",

    # --- categorical chart series ----------------------------------------
    # Identity only: order and legend name each component; no hue is a verdict.
    "chart_1": "#2563eb",
    "chart_2": "#0f766e",
    "chart_3": "#7c3aed",
    "chart_4": "#b45309",
    "chart_5": "#be4b74",
    "chart_6": "#475569",

    # --- video surface ------------------------------------------------------
    # The letterbox libvlc draws into. Black because that is what a video
    # surface is, not because it is chrome — it does not follow the palette.
    "video_surface":      "#000000",
    "video_surface_text": "#8a8a8a",

    # --- path display -------------------------------------------------------
    "path_text": "#1e40af",

    # --- modal framing (see ui/DESIGN.md §1) --------------------------------
    "window_ring":   "#cbd3dc",
    "dialog_seam":   "#d5dbe3",
    "action_bar_top":    "#f8fafc",
    "action_bar_bottom": "#f8fafc",
    # The application draws its own title bar (ui/native_frame.py) while the
    # window keeps its real Win32 frame styles, so snap, edge resizing, the
    # system menu and the maximise animation still come from Windows.
    # The caption CONTROLS are Windows' own — minimise, maximise, close, left
    # to right — not the reference's three round lights. This is a Windows
    # application; see the note at the top of ui/modal.py.
    "titlebar_top":    "#ffffff",
    "titlebar_bottom": "#f7f9fb",
    "titlebar_line":   "#dfe4ea",
    "titlebar_fg":     "#1f2933",
    # Windows caption-button hover, its red close included.
    "caption_hover":       "#e9edf2",
    "caption_close_hover": "#c42b1c",

    # --- list views (see ui/DESIGN.md §3) -----------------------------------
    "list_divider":     "#e7ebef",
    "list_sunken_edge": "#aeb7c2",
    # Secondary text on a selected row, where the fill is the solid accent.
    "text_on_accent_dim": "#e0ecff",

    # --- form validation ----------------------------------------------------
    # Paired with a word or glyph, never colour alone.
    "valid_ok": "#1b7a2b",

    # --- callouts (ambox) ---------------------------------------------------
    "info_bg":     "#eff6ff",
    "info_border": "#bfdbfe",
    "info_rule":   "#2563eb",
    "info_text":   "#1e40af",
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
    "tiny":    11,
    "small":   12,
    "body":    14,
    "table":   14,
    "grid":    14,
    "heading": 16,
    "title":   18,
    "caption": 13,   # window title, the platform caption size
}

# Control geometry, likewise from the reference layouts.
METRICS: dict[str, int] = {
    "control_h":   30,   # compact, with room for the readable type scale
    "row_h":       29,   # dense research tables still fit many rows
    "header_h":    30,
    "titlebar_h":  38,
    "caption_btn_w": 50,
    "dialog_input_h":  30,
    "tab_pad_x":   12,
    "tab_pad_y":   7,
    "radius":      6,
    "radius_tight": 4,
}

# Retained for the Tkinter front-end, which measures in points. Do not use for
# Qt — see FONT_PX above.
FONT_PT: dict[str, int] = {
    "tiny":    9,
    "small":   9,
    "body":    10,
    "table":   10,
    "heading": 12,
    "title":   14,
    "caption": 12,   # window title, the platform caption size
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
UI_FAMILY_PREFERENCE = ("Segoe UI Variable", "Segoe UI", "Roboto",
                        "Helvetica", "Arial", "Tahoma")

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

# --- participant-facing pace rating scale (Study Runner) --------------------
# A five-step ORDINAL ramp in ONE hue, light to dark. It is not part of the
# analyst palette above, it never renders a CMAT measurement, and nothing in
# the application proper should read it.
#
# Single hue varying only in lightness, for three reasons that are constraints
# rather than preferences. See STUDY_RATING_SCALE_DESIGN.md for the sources.
#   1. A red-to-green ramp is read as bad-to-good and shifts responses even
#      when the wording is neutral (Tourangeau, Couper & Conrad, 2007). The
#      scale must carry ORDER, not approval — and a participant screen that
#      implied "very fast = bad" would be the stimulus-only guardrail broken
#      in front of a child.
#   2. Lightness survives the common colour-vision deficiencies, a greyscale
#      printout and a washed-out projector. Hue alone survives none of them,
#      and a child sample of any size contains a few colour-blind children.
#   3. The step colour is never the only signal. Position, number and word all
#      carry the same order, and the SELECTED state is an outline plus a mark,
#      never a change of fill — so it survives a high-contrast Windows theme.
# step_ink clears 4.5:1 against every step including step_5.
PACE_SCALE: dict[str, str] = {
    "step_1":   "#e9eff1",
    "step_2":   "#cfe0e5",
    "step_3":   "#afccd6",
    "step_4":   "#8ab4c3",
    "step_5":   "#639bae",
    "step_ink": "#12242c",   # number and word, on every step
    "selected": "#16211f",   # the outline and underline mark of the answer
    "creature": "#4c5a57",   # turtle and rabbit anchors — flat, unemotional
    "screen":   "#f6f7f4",   # participant screen ground
}

PACE_STEP_COLORS: tuple[str, ...] = tuple(
    PACE_SCALE[f"step_{n}"] for n in range(1, 6))


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
