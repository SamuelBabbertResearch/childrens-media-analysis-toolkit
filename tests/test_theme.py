"""
Theme tokens — one source of truth, and no token that implies a verdict.

The GUI is hard to test, but the theme is data. These pin the two properties
that actually caused problems: colours defined in more than one place, and
type sizes that disagree between the widget chrome and the canvas.
"""

from __future__ import annotations
import re

import pytest

tk = pytest.importorskip("tkinter")
import gui_theme as T  # noqa: E402

# `root` comes from tests/conftest.py — one shared Tk root for the session.


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

def test_every_colour_is_a_valid_hex_triplet():
    bad = [k for k, v in T.COLORS.items()
           if not re.fullmatch(r"#[0-9a-fA-F]{6}", v)]
    assert bad == []


def test_unknown_token_raises_rather_than_rendering_black():
    """A silent fallback is how a typo becomes a black-on-black label."""
    with pytest.raises(KeyError):
        T.color("not_a_real_token")


def test_status_colours_cover_every_pipeline_state():
    from analyzer.pipeline import BLOCKED, COMPLETE, PARTIAL, PENDING
    for state in (COMPLETE, PARTIAL, PENDING, BLOCKED):
        assert T.color(f"status_{state}")


def test_pipeline_palette_comes_from_the_theme():
    """gui_pipeline must alias the theme, not keep a second copy."""
    import gui_pipeline as P
    assert P.SEL_BORDER == T.color("accent")
    assert P.TEXT == T.color("text")
    assert P.HAIRLINE == T.color("hairline")
    assert P.CHROME_TOP == T.color("chrome_top")


def test_only_one_accent_blue():
    """Five competing blues is what this file exists to prevent."""
    import gui_pipeline as P
    accents = {T.color("accent"), P.SEL_BORDER, P.WIRE_HOT, P.PORT_HOT}
    assert len(accents) == 1, f"more than one accent in use: {accents}"


# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

def test_widget_fonts_use_points(root):
    """Positive size = points, which Tk scales for the display."""
    for role in T.FONT_PT:
        size = T.font(root, role)[1]
        assert size > 0, f"{role} must be point-sized for widgets"


def test_canvas_fonts_use_pixels(root):
    """Negative size = pixels, so each zoom level renders natively."""
    assert T.canvas_font(root, "body")[1] < 0


def test_chrome_and_canvas_agree_at_100_percent(root):
    """The two conventions must describe the same size, or they drift."""
    scale = T.dpi_scale(root)
    for role, pt in T.FONT_PT.items():
        px = -T.canvas_font(root, role, zoom=1.0, scale=scale)[1]
        expected = max(7, round(pt * (96.0 / 72.0) * scale))
        assert px == expected, f"{role}: {px}px vs {expected}px"


def test_canvas_font_scales_with_zoom(root):
    small = -T.canvas_font(root, "body", zoom=0.5)[1]
    normal = -T.canvas_font(root, "body", zoom=1.0)[1]
    large = -T.canvas_font(root, "body", zoom=2.0)[1]
    assert small < normal < large


def test_canvas_font_never_becomes_unreadable(root):
    """Zooming far out must floor the size, not produce a 1px smear."""
    assert -T.canvas_font(root, "body", zoom=0.01)[1] >= 7


def test_body_type_is_not_the_units_error(root):
    """9pt, not 9px.

    Copying "11" from a Snow Leopard spec as pixels rather than points is the
    standard retro-UI mistake and produces text a third too small.
    """
    scale = T.dpi_scale(root)
    px = -T.canvas_font(root, "body", zoom=1.0, scale=scale)[1]
    assert px >= 12, f"body resolved to {px}px, too small to read"


# ---------------------------------------------------------------------------
# The stimulus-only guardrail
# ---------------------------------------------------------------------------

def test_no_token_names_a_judgement():
    """CMAT measures the stimulus; the palette must not imply a rating."""
    forbidden = ("good", "bad", "safe", "unsafe", "harm", "risk",
                 "appropriate", "suitable", "age_", "educational", "quality")
    offenders = [k for k in T.COLORS
                 if any(word in k.lower() for word in forbidden)]
    assert offenders == [], f"verdict-flavoured tokens: {offenders}"


def test_emphasis_defaults_to_weight_not_colour(root):
    """Red beside a high number reads as 'bad' whatever the caption says."""
    tree = tk.Text(root)
    high, _low = T.outlier_tags(tree, T.EMPHASIS_NEUTRAL)
    assert tree.tag_cget(high, "background") in ("", None)
    assert tree.tag_cget(high, "font")


def test_colour_emphasis_is_available_when_asked_for(root):
    tree = tk.Text(root)
    high, low = T.outlier_tags(tree, T.EMPHASIS_COLOR)
    assert tree.tag_cget(high, "background") == T.color("emphasis_high_bg")
    assert tree.tag_cget(low, "background") == T.color("emphasis_low_bg")


def test_legend_disclaims_a_verdict():
    text = T.OUTLIER_LEGEND.lower()
    assert "not" in text
    assert any(w in text for w in ("judgement", "judgment", "quality"))


# ---------------------------------------------------------------------------
# ttk styling
# ---------------------------------------------------------------------------

def test_apply_theme_is_idempotent(root):
    first = T.apply_theme(root)
    second = T.apply_theme(root)
    assert first.theme_use() == second.theme_use()


def test_treeview_is_styled_for_data(root):
    style = T.apply_theme(root)
    assert style.lookup("CMAT.Treeview", "background") == T.color("mw_bg")
    assert style.lookup("CMAT.Treeview.Heading",
                        "background") == T.color("mw_header_bg")


def test_unselected_tabs_are_styled_not_left_to_clam(root):
    """A map for only the selected state leaves every other tab default."""
    style = T.apply_theme(root)
    assert style.lookup("TNotebook.Tab", "background") == T.color("tab_bg")
    assert style.lookup("TNotebook.Tab", "foreground") == T.color("tab_fg")


def test_selected_tab_uses_panel_colour_and_near_black(root):
    style = T.apply_theme(root)
    bg = dict(style.map("TNotebook.Tab", "background"))
    fg = dict(style.map("TNotebook.Tab", "foreground"))
    assert bg["selected"] == T.color("panel_bg")
    assert fg["selected"] == T.color("text")
    assert fg["selected"] != "#000000", "pure black is harsher than the ink token"


def test_tab_padding_scales_with_display(root):
    style = T.apply_theme(root)
    pad = style.lookup("TNotebook.Tab", "padding")
    values = [int(v) for v in (pad if isinstance(pad, (list, tuple))
                               else str(pad).split())]
    assert values[0] >= int(round(10 * T.dpi_scale(root)))


def test_mono_is_never_the_ui_face(root):
    """Consolas is for fixed-pitch content, not for labels or body text."""
    assert T.font(root, "body")[0] != T.mono_family(root)
    assert T.font(root, "table")[0] != T.mono_family(root)
    assert T.font(root, "body", mono=True)[0] == T.mono_family(root)


def test_digits_are_uniform_width_in_the_ui_face(root):
    """Why numeric columns need right-alignment, not a mono font."""
    from tkinter import font as tkfont
    f = tkfont.Font(root=root, font=T.font(root, "table"))
    widths = {f.measure(d) for d in "0123456789"}
    assert len(widths) == 1, f"digits are not tabular in {T.family(root)}"


def test_row_height_scales_with_display(root):
    style = T.apply_theme(root)
    height = int(style.lookup("CMAT.Treeview", "rowheight"))
    assert height >= 18
