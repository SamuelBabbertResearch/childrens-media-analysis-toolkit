"""
Qt front-end — tokens, stylesheet, and the HTML report.

These run without a display. ui.tokens imports no framework at all and
ui.report imports no Qt, so the parts that carry the design decisions and the
scientific guardrails are testable headless — which is also why ui.report can
later back the PDF export and the static site.
"""

from __future__ import annotations

import re

import pytest

from analyzer.schema import EpisodeResult
from ui import report, tokens


# ---------------------------------------------------------------------------
# Shared tokens
# ---------------------------------------------------------------------------

def test_tokens_import_no_framework():
    """The palette must not pull in Tk or Qt — both front-ends read it."""
    import ast
    import pathlib
    src = pathlib.Path(tokens.__file__).read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not (imported & {"tkinter", "PySide6", "PyQt5", "PyQt6"})


def test_both_front_ends_share_one_palette():
    import gui_theme
    assert gui_theme.COLORS is tokens.COLORS
    assert gui_theme.FONT_PT is tokens.FONT_PT


def test_every_colour_is_a_hex_triplet():
    bad = [k for k, v in tokens.COLORS.items()
           if not re.fullmatch(r"#[0-9a-fA-F]{6}", v)]
    assert bad == []


def test_unknown_token_raises():
    with pytest.raises(KeyError):
        tokens.color("no_such_token")


def test_no_token_names_a_judgement():
    """Whole words, not substrings — 'bad' is inside 'badge'."""
    forbidden = {"good", "bad", "safe", "unsafe", "harm", "risk", "age",
                 "appropriate", "suitable", "educational", "quality", "rating"}
    offenders = [k for k in tokens.COLORS
                 if forbidden & set(k.lower().split("_"))]
    assert offenders == []


# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------

def test_stylesheet_builds_without_a_qapplication():
    """Font lookup needs a live QApplication and ABORTS the process without
    one — a crash with no traceback. The guard must hold."""
    from ui import theme
    css = theme.stylesheet()
    assert len(css) > 1000
    assert "{" in css and "}" in css


def test_stylesheet_uses_the_shared_accent():
    from ui import theme
    assert tokens.color("accent") in theme.stylesheet()


def test_stylesheet_has_no_unresolved_placeholders():
    from ui import theme
    css = theme.stylesheet()
    assert "{c[" not in css and "None" not in css


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def _result(**kw) -> EpisodeResult:
    r = EpisodeResult(file="Demo 1x01.mp4", duration_sec=600.0, **kw)
    r.metrics.sensory_load.score = 0.262
    r.metrics.sensory_load.audio_available = True
    r.metrics.sensory_load.components.pacing = 0.328
    r.metrics.scene_pacing.cuts_per_min = 13.2
    r.metrics.shot_length.mean_sec = 4.55
    r.metrics.shot_length.count = 523
    return r


def test_report_needs_no_qt():
    import ast
    import pathlib
    src = pathlib.Path(report.__file__).read_text(encoding="utf-8")
    assert "PySide6" not in src, "report must stay renderable headless"
    ast.parse(src)


def test_report_renders_a_document():
    html = report.episode_html(_result())
    assert html.startswith("<html>") and html.endswith("</html>")
    assert "Demo 1x01.mp4" in html
    assert "wikitable" in html


def test_report_shows_contribution_not_just_normalised():
    """A bar showed the normalised value, which cannot explain the composite."""
    html = report.episode_html(_result())
    assert "Contribution" in html
    # pacing 0.328 x weight 0.25 = 0.082
    assert "0.082" in html


def test_failed_analysis_reports_the_error_and_stops():
    r = EpisodeResult(file="broken.mp4", status="failed", error="moov atom missing")
    html = report.episode_html(r)
    assert "moov atom missing" in html
    assert "Measured features" not in html


def test_report_escapes_filenames():
    r = _result()
    r.file = "<script>alert(1)</script>.mp4"
    html = report.episode_html(r)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_ungraded_components_are_called_out():
    r = _result()
    r.measurement_tools = {"transitions": "ContentDetector [validated]",
                           "flashing": "Luminance delta [unvalidated]"}
    html = report.episode_html(r)
    assert "Not graded against hand coding" in html
    assert "Flashing" in html


def test_report_states_no_verdict():
    """No appropriateness, audience, or educational claim anywhere."""
    html = report.episode_html(_result()).lower()
    for banned in ("target audience", "educational content", "appropriate for",
                   "suitable for", "age rating"):
        assert banned not in html


def test_percentile_reads_naturally_at_the_bottom():
    """'0th percentile' is not how anyone says 'lowest'."""
    html = report.episode_html(
        _result(), percentile={"percentile": 0, "global_total": 24,
                               "show_total": 1, "show_rank": 1})
    assert "0th" not in html
    assert "lowest of 24" in html
