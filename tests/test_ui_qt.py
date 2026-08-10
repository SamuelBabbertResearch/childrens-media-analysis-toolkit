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
    # The reference's own class names, so the reference's own CSS applies.
    assert 'class="data-table"' in html
    assert 'class="kv"' not in html


def test_report_uses_the_reference_stylesheet_not_a_copy_of_it():
    """The reference CSS is loaded, not transcribed.

    Hand-copying values out of ui/reference/ is what repeatedly lost or
    changed them, so the rules must arrive from the file itself.
    """
    from ui import reference_css
    html = report.episode_html(_result())
    for rule in (".data-table", ".section-title", ".sub-text"):
        assert rule in html, f"{rule} missing from the report stylesheet"
    # A value only the reference file carries.
    assert "#0F4F96" in reference_css.rules((".section-title",))


def test_report_avoids_h1_h6():
    """Qt's HTML importer applies its own font-size adjustment to headings.

    It survives the stylesheet — a 13px rule on an h1 still rendered near 24px —
    so headings are classed paragraphs and must stay that way.
    """
    html = report.episode_html(_result())
    for tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        assert f"<{tag}>" not in html and f"<{tag} " not in html


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


def test_welcome_offers_every_template_not_just_the_illustrated_four():
    """The reference draws four cards; the registry has seven.

    Showing only the illustrated ones would make the wizard a worse map of
    the tool than the tool is, and would hide Blank canvas entirely.
    """
    from analyzer.pipeline_graph import TEMPLATES
    from ui import welcome
    assert len(TEMPLATES) > 4
    for template in TEMPLATES:
        assert template.key in welcome.TEMPLATE_KEYS, template.key


def test_welcome_builds_a_real_document():
    """Create Pipeline must produce a document the Pipeline tab can open."""
    from analyzer.pipeline_graph import TEMPLATES
    full = next(t for t in TEMPLATES if t.key == "full")
    doc = full.build("Test study")
    assert doc.name == "Test study"
    assert doc.nodes and doc.connections


def test_settings_labels_cover_every_configured_metric():
    """A metric added to the engine must not silently lose its label.

    The dialog builds its rows from config.json, so an unlabelled key still
    appears — but as a raw identifier. This keeps the labels honest.
    """
    from analyzer.config_loader import load_config
    from ui import settings
    cfg = load_config()
    for key in cfg.get("sensory_load_weights", {}):
        assert key in settings.WEIGHT_LABEL, key
    for key in cfg.get("normalization_reference_ranges", {}):
        assert key in settings.CEILING_LABEL, key


def test_settings_is_scoring_only():
    """Nothing in the dialog may change how a measurement is taken.

    Scoring settings re-score from cache; measurement settings make cached
    results stale. Mixing them would break the promise Apply & Re-score makes.
    """
    import inspect
    from ui import settings
    src = inspect.getsource(settings)
    for measurement_key in ("cut_detection_threshold", "sample_fps",
                            "flashing_luminance_threshold", "measurements"):
        assert measurement_key not in src, measurement_key


def test_cancel_signal_survives_the_engine_exception_handler():
    """Cancellation must not be recorded as a failed episode.

    analyze_show_batch wraps each episode in `except Exception`, so an
    ordinary exception raised from the progress callback would be swallowed
    and the episode marked failed. The cancel signal therefore derives from
    BaseException, which that clause does not catch.
    """
    from ui.automated import _Cancelled
    assert issubclass(_Cancelled, BaseException)
    assert not issubclass(_Cancelled, Exception)
