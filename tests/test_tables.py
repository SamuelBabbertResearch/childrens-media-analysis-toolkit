"""
Data tables — column rendering and the rule for marking unusual values.

The marking rule carries scientific weight: CMAT does not rank shows, so an
"unusual" mark must be defensible, stated, and impossible to read as a verdict.
These pin the arithmetic and the wording.
"""

from __future__ import annotations

import pytest

import gui_tables as G

tk = pytest.importorskip("tkinter")

# `root` comes from tests/conftest.py — one shared Tk root for the session.


# ---------------------------------------------------------------------------
# Tukey fences
# ---------------------------------------------------------------------------

def test_too_few_rows_produces_no_fences():
    """Quartiles over six values are noise; the table says so instead."""
    assert G.tukey_fences([1, 2, 3, 4, 5, 6]) is None


def test_threshold_is_the_documented_one():
    below = list(range(G.MIN_ROWS_FOR_EMPHASIS - 1))
    at = list(range(G.MIN_ROWS_FOR_EMPHASIS))
    assert G.tukey_fences([float(v) for v in below]) is None
    assert G.tukey_fences([float(v) for v in at]) is not None


def test_zero_spread_produces_no_fences():
    """Identical values have IQR 0, which would mark every distinct value."""
    assert G.tukey_fences([5.0] * 12) is None


def test_fences_are_robust_to_the_outliers_they_detect():
    """A mean/SD rule is dragged by the extreme value; quartiles are not."""
    tight = [6.3, 6.4, 6.5, 6.5, 6.6, 6.6, 6.7, 6.8]
    with_extreme = tight + [400.0]
    a = G.tukey_fences(tight)
    b = G.tukey_fences(with_extreme)
    assert abs(a[1] - b[1]) < 2.0, "one extreme value must not move the fence far"
    assert G.mark(400.0, b) == G.MARK_HIGH


def test_mark_distinguishes_high_low_and_ordinary():
    fences = (0.0, 10.0)
    assert G.mark(11.0, fences) == G.MARK_HIGH
    assert G.mark(-1.0, fences) == G.MARK_LOW
    assert G.mark(5.0, fences) == ""


def test_mark_handles_missing_values_and_no_fences():
    assert G.mark(None, (0.0, 1.0)) == ""
    assert G.mark(5.0, None) == ""


def test_marks_are_not_colour_dependent():
    """Must survive greyscale and colour blindness — hence glyphs."""
    assert G.MARK_HIGH != G.MARK_LOW
    assert G.MARK_HIGH.strip() and G.MARK_LOW.strip()


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------

def test_missing_numeric_renders_as_na():
    col = G.Column("audio", "Audio", numeric=True)
    assert col.render(None) == "n/a"


def test_numeric_columns_use_their_format():
    assert G.Column("x", "X", numeric=True, fmt="{:.1f}").render(6.44) == "6.4"
    assert G.Column("x", "X", numeric=True).render(0.1234) == "0.123"


def test_text_column_passes_values_through():
    assert G.Column("name", "Name").render("Episode 1") == "Episode 1"


# ---------------------------------------------------------------------------
# Table behaviour
# ---------------------------------------------------------------------------

def _table(root, n_rows, emphasis=True):
    cols = [G.Column("name", "Name"),
            G.Column("v", "Value", numeric=True, fmt="{:.1f}")]
    t = G.WikiTable(root, cols, emphasis=emphasis)
    rows = [{"name": f"ep{i}", "v": 5.0 + (i % 3) * 0.1} for i in range(n_rows)]
    if n_rows:
        rows[0]["v"] = 900.0                    # an unmistakable outlier
    t.set_rows(rows)
    return t


def test_table_renders_every_row(root):
    t = _table(root, 10)
    assert len(t.tree.get_children()) == 10


def test_outlier_row_carries_a_marker(root):
    t = _table(root, 12)
    texts = [t.tree.item(i, "values")[1] for i in t.tree.get_children()]
    assert any(G.MARK_HIGH in v for v in texts)


def test_small_table_marks_nothing_and_explains_why(root):
    t = _table(root, 5)
    texts = [t.tree.item(i, "values")[1] for i in t.tree.get_children()]
    assert not any(G.MARK_HIGH in v or G.MARK_LOW in v for v in texts)
    legend = t._legend.cget("text").lower()
    assert "at least" in legend and "meaningful" in legend


def test_legend_names_the_comparison_set_and_disclaims_a_verdict(root):
    t = _table(root, 12)
    legend = t._legend.cget("text").lower()
    assert "n=12" in legend
    assert "iqr" in legend
    assert "not a judgement" in legend


def test_legend_reports_when_nothing_is_unusual(root):
    cols = [G.Column("v", "Value", numeric=True)]
    t = G.WikiTable(root, cols)
    t.set_rows([{"v": 5.0 + i * 0.01} for i in range(12)])
    assert "no values" in t._legend.cget("text").lower()


def test_emphasis_can_be_switched_off(root):
    t = _table(root, 12, emphasis=False)
    texts = [t.tree.item(i, "values")[1] for i in t.tree.get_children()]
    assert not any(G.MARK_HIGH in v for v in texts)
    assert t._legend.cget("text") == ""


def test_failed_rows_are_flagged_not_dropped(root):
    cols = [G.Column("name", "Name"), G.Column("v", "Value", numeric=True)]
    t = G.WikiTable(root, cols)
    t.set_rows([{"name": "broken.mp4", "_failed": True},
                {"name": "ok.mp4", "v": 1.0}])
    assert len(t.tree.get_children()) == 2


# ---------------------------------------------------------------------------
# Property table
# ---------------------------------------------------------------------------

def test_property_table_builds_a_cell_per_column(root):
    p = G.PropertyTable(root, [("Cuts per minute", "6.4"),
                               ("Mean shot", "9.32 s", "seconds")])
    assert len(p._cells) == 6            # label, value, note on both rows


def test_property_table_replaces_rather_than_appends(root):
    p = G.PropertyTable(root, [("a", "1")])
    p.set_rows([("a", "1"), ("b", "2")])
    assert len(p._cells) == 6


def test_property_table_is_content_width(root):
    """A wikitable is content-width; stretching a column strands the value."""
    p = G.PropertyTable(root, [("k", "v")])
    for col in (0, 1, 2):
        assert p.grid_columnconfigure(col)["weight"] == 0


def test_property_table_accepts_rows_without_notes(root):
    p = G.PropertyTable(root, [("k", "v")])
    assert len(p._cells) == 3


# ---------------------------------------------------------------------------
# Infobox and badges
# ---------------------------------------------------------------------------

def test_infobox_renders_key_value_pairs(root):
    p = G.InfoboxPanel(root, "Ep 1")
    p.set_rows("Ep 1", [("Series", "Little Bear"), ("Duration", "11:45")])
    assert len(p._widgets) == 4          # a key and a value per row


def test_infobox_replaces_rather_than_appends(root):
    p = G.InfoboxPanel(root)
    p.set_rows("A", [("k", "v")])
    p.set_rows("B", [("k", "v"), ("k2", "v2")])
    assert len(p._widgets) == 4
    assert p._title.cget("text") == "B"


def test_infobox_shows_a_placeholder_when_empty(root):
    p = G.InfoboxPanel(root)
    p.set_rows("", [])
    assert "nothing selected" in p._title.cget("text").lower()


def test_badge_value_renders_as_a_pill(root):
    p = G.InfoboxPanel(root)
    p.set_rows("Ep", [("Automated", ("Analyzed", "analyzed"))])
    pills = [w for w in p._widgets
             if isinstance(w, tk.Frame)
             for c in w.winfo_children() if isinstance(c, G.Badge)]
    assert pills, "a (text, kind) value must render as a Badge"


def test_badge_kinds_are_visually_distinct(root):
    ready = G.Badge(root, "Ready", "ready")
    analyzed = G.Badge(root, "Analyzed", "analyzed")
    assert ready.cget("background") != analyzed.cget("background")


def test_unknown_badge_kind_degrades_quietly(root):
    b = G.Badge(root, "Whatever", "not_a_kind")
    assert b.cget("background") == __import__("gui_theme").color("badge_none_bg")


def test_badges_describe_work_state_not_the_programme():
    """A badge is the loudest thing in a panel; it must not carry a verdict."""
    forbidden = ("good", "bad", "safe", "age", "suitable", "educational",
                 "quality", "recommend")
    for kind, (bg, fg) in G.BADGE_STYLES.items():
        assert not any(w in kind.lower() for w in forbidden)


def test_data_table_selection_keeps_numbers_readable(root):
    """White-on-blue is right for a list, wrong for a table of figures."""
    import gui_theme as T
    style = T.apply_theme(root)
    fg = dict(style.map("CMAT.Treeview", "foreground"))
    assert fg["selected"] == T.color("text")
    assert fg["selected"] != T.color("text_on_accent")


def test_sorting_toggles_and_orders_numerically(root):
    cols = [G.Column("v", "Value", numeric=True, fmt="{:.0f}")]
    t = G.WikiTable(root, cols, emphasis=False)
    t.set_rows([{"v": 2.0}, {"v": 10.0}, {"v": 1.0}])
    t._sort_by("v")
    first = t.tree.item(t.tree.get_children()[0], "values")[0]
    assert first == "10", "numeric sort, not lexicographic"
    t._sort_by("v")
    first = t.tree.item(t.tree.get_children()[0], "values")[0]
    assert first == "1"
