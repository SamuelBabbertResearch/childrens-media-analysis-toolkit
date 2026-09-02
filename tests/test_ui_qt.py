"""
Qt front-end — tokens, stylesheet, and the HTML report.

These run without a display. ui.tokens imports no framework at all and
ui.report imports no Qt, so the parts that carry the design decisions and the
scientific guardrails are testable headless — which is also why ui.report can
later back the PDF export and the static site.
"""

from __future__ import annotations

import inspect
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


def test_index_never_shows_a_target_age():
    """The shows table carries target_age_min/max; the Index must not.

    A target audience age is a claim about the viewer. CMAT reports properties
    of the video, so those columns are excluded on purpose and the exclusion
    is pinned here rather than left to whoever edits the column list next.
    """
    from ui import index_tab
    shown = {key for _h, key, _f in
             index_tab.EPISODE_COLUMNS + index_tab.SHOW_COLUMNS}
    for forbidden in index_tab.FORBIDDEN_COLUMNS:
        assert forbidden not in shown


def test_index_sorts_only_by_columns_the_database_sanctions():
    """A sort key the database rejects silently falls back to its default."""
    from analyzer.db import _EP_SORT_COLS, _SHOW_SORT_COLS
    from ui import index_tab
    for _h, key, _f in index_tab.EPISODE_COLUMNS:
        assert key in _EP_SORT_COLS, key
    for _h, key, _f in index_tab.SHOW_COLUMNS:
        assert key in _SHOW_SORT_COLS or key == "updated_at", key


def test_outlier_fences_need_enough_values():
    """Below eight values a quartile is too thin to call anything unusual."""
    from ui.index_tab import _fences
    assert _fences([1, 2, 3, 4, 5, 6, 7]) is None
    assert _fences([1, 2, 3, 4, 5, 6, 7, 100]) is not None


def test_coding_sheet_columns_match_the_parser():
    """A sheet written here must be one code_events.py can read.

    The writer keeps its own column list so a mismatch is one obvious edit
    rather than a silently malformed sheet; this checks the two agree.
    """
    import analyzer.event_coding as ec
    from ui import handcoding
    assert handcoding.COLUMNS == ec._COLUMNS


def test_coding_offers_exactly_the_registered_vocabulary():
    """The codebook is the registry; the screen must not add or drop a term.

    Compared as sets: the engine holds these as sets, so their order carries
    no meaning and asserting on it would only test the assertion.
    """
    import analyzer.event_coding as ec
    from ui import handcoding
    assert set(handcoding.RELEVANCE) == set(ec._RELEVANCE)
    assert set(handcoding.REPEAT) == set(ec._REPEAT)
    assert {t for t, _ in ec.EVENT_TYPES} == set(ec._EVENT_TYPE_SET)


def _ok(name: str, load: float = 0.2):
    r = EpisodeResult(file=name, duration_sec=600.0)
    r.metrics.sensory_load.score = load
    return r


def test_show_report_distinguishes_not_analysed_from_failed():
    """An episode never analysed is not a failure.

    `results` holds only what is cached, so anything missing from it simply
    has not been run. Reporting that as a failure describes work that has not
    been done as work that went wrong.
    """
    from analyzer.aggregate import compute_show_aggregate
    from ui.report import show_html
    failed = EpisodeResult(file="b.mp4", status="failed", error="moov atom")
    results = [_ok("a.mp4"), failed]
    aggregate = compute_show_aggregate("Demo", results)
    aggregate.episode_count = 5          # five on disk, two attempted
    html = show_html(aggregate, results, "Demo")
    assert "1 of 5 episodes measured" in html
    assert "1 failed" in html
    assert "3 not analysed yet" in html


def test_show_report_says_so_when_nothing_is_measured():
    from analyzer.aggregate import compute_show_aggregate
    from ui.report import show_html
    aggregate = compute_show_aggregate("Demo", [])
    aggregate.episode_count = 4
    html = show_html(aggregate, [], "Demo")
    assert "Nothing measured yet" in html
    assert "Mean" not in html.split("<body>")[1]


def test_show_report_states_the_weighting():
    """Equal weighting per episode is a choice, so it is stated, not implied."""
    from analyzer.aggregate import compute_show_aggregate
    from ui.report import show_html
    results = [_ok("a.mp4", 0.2), _ok("b.mp4", 0.4)]
    aggregate = compute_show_aggregate("Demo", results)
    aggregate.episode_count = 2
    html = show_html(aggregate, results, "Demo")
    assert "weighted equally" in html


# ---------------------------------------------------------------------------
# Pipeline as a control surface
# ---------------------------------------------------------------------------

def test_every_stage_type_can_reach_a_screen_or_says_why_not():
    """A node the user can select must lead somewhere, or state its reason.

    The pipeline's job is to show what the software is doing; a stage that
    silently does nothing when opened is the failure this mapping exists to
    prevent. A new node type with a stage_key therefore has to be routed here
    or explicitly listed as unported.
    """
    from analyzer.pipeline_graph import NODE_TYPES
    from ui.main_window import STAGE_ACTIONS, STAGE_TABS, STAGE_UNPORTED
    for kind in NODE_TYPES.values():
        if not kind.stage_key:
            continue
        routes = [kind.stage_key in d
                  for d in (STAGE_TABS, STAGE_ACTIONS, STAGE_UNPORTED)]
        assert any(routes), kind.stage_key
        assert sum(routes) == 1, f"{kind.stage_key} is routed twice"


def test_stage_actions_name_methods_that_exist():
    """A dialog route calls a MainWindow method by name."""
    from ui.main_window import STAGE_ACTIONS, MainWindow
    for _label, method in STAGE_ACTIONS.values():
        assert callable(getattr(MainWindow, method, None)), method


def test_stage_routes_name_tabs_that_are_actually_built():
    """A route to a tab title that no longer exists would open nothing."""
    import inspect
    from ui.main_window import STAGE_TABS, MainWindow
    src = inspect.getsource(MainWindow._build_tabs)
    for title, _view in STAGE_TABS.values():
        assert f'"{title}"' in src, title


def test_stage_routes_name_sub_views_that_exist():
    """A route may name a screen inside a tab; that name must be real."""
    from ui.handcoding import HandCodingTab
    from ui.language import LanguageTab
    from ui.main_window import STAGE_TABS
    known = {
        "Human coding": {"Code", "Validate tool", "Agreement"},
        "Language": {"Speech", "Vocabulary"},
    }
    for title, view in STAGE_TABS.values():
        if view is not None:
            assert title in known, title
            assert view in known[title], (title, view)
    # And the names the tabs actually register, so the map above cannot rot.
    import inspect
    for cls, title in ((HandCodingTab, "Human coding"),
                       (LanguageTab, "Language")):
        src = inspect.getsource(cls.__init__)
        for name in known[title]:
            assert f'"{name}"' in src, (title, name)


def test_unported_stage_routes_name_a_stage_that_exists():
    """Each entry disappears when its screen is ported; none may go stale."""
    from analyzer.pipeline import STAGE_KEYS
    from ui.main_window import STAGE_ACTIONS, STAGE_TABS, STAGE_UNPORTED
    for key in list(STAGE_TABS) + list(STAGE_ACTIONS) + list(STAGE_UNPORTED):
        assert key in STAGE_KEYS, key


def test_double_clicking_a_node_asks_for_its_screen():
    """Without this the canvas treats the second click as another drag."""
    import inspect
    from ui.pipeline_view import Canvas
    assert hasattr(Canvas, "node_activated")
    assert "node_activated.emit" in inspect.getsource(
        Canvas.mouseDoubleClickEvent)


def test_a_pipeline_links_to_a_sample_not_a_show():
    """`source_key` (and a Sampling node's own `sample_key`) must be a key
    `build_pipelines()` actually produces.

    A show key ("Show/Season 1") and a derived pipeline key
    ("sample:<folder>") are different namespaces. Link to Episode Sample
    offered SHOWS, so the look-up never matched and every node of every
    linked pipeline reported "no derived status" — which is why the derived
    state looked like it was merely undisplayed. `_link_to_sample` (the
    document's default) and `_link_node_to_sample` (one Sampling node's own
    key) both go through `_pick_sample`, which is the one place this must
    hold — see `LEARNINGS.md` on the two used to be one method that inferred
    which was meant.
    """
    import inspect
    from ui.main_window import MainWindow
    src = (inspect.getsource(MainWindow._link_to_sample)
          + inspect.getsource(MainWindow._link_node_to_sample)
          + inspect.getsource(MainWindow._pick_sample))
    assert "build_pipelines" in src
    assert "show_key" not in src


def _inspector_rows(insp) -> dict:
    """The key/value grid as a dict, read back off the widget."""
    grid = insp._grid
    rows: dict[str, str] = {}
    for r in range(grid.rowCount()):
        k = grid.itemAtPosition(r, 0)
        v = grid.itemAtPosition(r, 1)
        if k is not None and v is not None:
            rows[k.widget().text()] = v.widget().text()
    return rows


def test_inspector_shows_the_derived_stage_not_the_registry_entry(qapp):
    """analyzer/pipeline.py computes headline, details and next_action.

    Nothing displayed any of them, which is what made the node a picture: the
    inspector showed the same static description for a stage not started and a
    stage complete.
    """
    from analyzer.pipeline import empty_pipeline
    from analyzer.pipeline_graph import default_doc
    from ui.inspector import Inspector

    doc = default_doc("Test study")
    node = next(n for n in doc.nodes if n.type == "sampling")
    stage = empty_pipeline().stage("sampling")

    insp = Inspector()
    insp.show_node(node, stage, "", ("Library", None))
    rows = _inspector_rows(insp)

    assert rows["Status"] == stage.status_label
    assert rows["Summary"] == stage.headline
    assert rows["Next step"] == stage.next_action
    for key, value in stage.details:
        assert rows[key] == value
    # The one thing the researcher can act on leads.
    assert insp._banner.text() == stage.next_action


def test_inspector_says_why_a_node_has_no_derived_state(qapp):
    """An unlinked pipeline must not show a plausible figure instead."""
    from analyzer.pipeline_graph import default_doc
    from ui.inspector import Inspector

    node = next(n for n in default_doc().nodes if n.type == "sampling")
    insp = Inspector()
    insp.show_node(node, None, "this pipeline is not linked", None)
    rows = _inspector_rows(insp)
    assert rows["Current state"] == "this pipeline is not linked"
    assert "Summary" not in rows


def test_an_unported_stages_button_is_disabled_and_says_why(qapp):
    """An unavailable control must not look like a broken one."""
    from ui.inspector import Inspector
    insp = Inspector()
    insp._set_open_target((None, "still on the Tkinter build"))
    assert not insp._open.isHidden()               # present, not silently gone
    assert not insp._open.isEnabled()
    assert insp._open.toolTip() == "still on the Tkinter build"


# ---------------------------------------------------------------------------
# The ported screens
# ---------------------------------------------------------------------------

def test_every_tk_only_screen_is_now_in_qt():
    """The migration is finished when nothing is Tk-only.

    Each of these was a screen the Qt build did not have. The check is that
    the module and the entry point exist, so deleting one without replacing
    it fails here rather than at the next person's first click.
    """
    from ui.handcoding import AgreementView, CodeView, ValidateView
    from ui.language import SpeechView, VocabularyView
    from ui.main_window import MainWindow
    from ui.sampler import SamplerDialog
    assert all((AgreementView, CodeView, ValidateView, SpeechView,
                VocabularyView, SamplerDialog))
    assert callable(MainWindow.open_sampler)
    assert callable(MainWindow._show_full_series)


def test_speech_is_never_reported_without_density():
    """WPM divides by dialogue time, so alone it invites the wrong reading.

    CLAUDE.md §2.2: "Words per minute is reported with speech density, or not
    at all." Both the column and the explanation are pinned here.
    """
    from ui import language
    headers = [h for h, _w, _r in language.SPEECH_COLUMNS]
    assert "Words per minute" in headers
    assert "Speech density" in headers
    note = inspect.getsource(language.SpeechView._write_note)
    assert "DIALOGUE time, not runtime" in note


def test_the_sampler_uses_the_engine_s_own_explanations():
    """analyzer/sampler.py calls TOOLTIPS the authoritative source.

    Re-wording a method's meaning in the interface is how the interface and
    the manifest come to describe different things.
    """
    from analyzer.sampler import TOOLTIPS
    from ui import sampler
    used = {tip for _v, _l, tip in
            sampler.METHODS + sampler.STRATIFY + sampler.ALLOCATION}
    for key in used:
        assert key in TOOLTIPS, key


def test_the_sampler_distinguishes_probability_from_not():
    """A hand-picked set is not a sample, and the screen must not blur it."""
    src = inspect.getsource(__import__("ui.sampler", fromlist=["x"]))
    assert "NON-PROBABILITY" in src
    assert "does not support inference to the whole show" in src


def test_agreement_reports_kappa_as_a_property_of_the_coders():
    """Cohen's kappa here grades the coding, not the programme."""
    from ui.handcoding import AgreementView
    src = inspect.getsource(AgreementView)
    assert "says nothing about the" in src
    # Landis & Koch's bands are a convention and are named as one.
    reading = inspect.getsource(AgreementView._kappa_reading)
    assert "Landis & Koch" in reading and "not a threshold" in reading


def test_validation_never_shows_a_bare_f1():
    """An accuracy figure without its qualifiers is the thing §2.2 forbids."""
    from ui.handcoding import ValidateView
    src = inspect.getsource(ValidateView)
    # Tolerance is stated with the per-episode scores…
    assert "self._tolerance.value():g} s" in src
    # …and the aggregate says how many comparisons it covers, FOR WHICH
    # detector. Blending configurations produced 0.891 where the two real
    # detectors score 0.855 and 0.928.
    assert "comparison file" in src
    assert "detector_tag" in src
    assert "their scores are not combined" in src


def test_the_composite_is_rescored_on_read(qapp):
    """Settings' "Apply & Re-score" must actually change the score.

    The composite is a weighted sum over numbers already measured, so it is
    recomputed on read. The Qt build loaded results straight from the cache,
    which meant new weights changed nothing anywhere on screen.
    """
    from analyzer.config_loader import load_config
    from analyzer.metrics_sensory import rescore_episode
    from ui.main_window import MainWindow
    # The re-derivation lives in the engine so `cli.py` shares it; the window
    # must go through it rather than reading the cache raw.
    assert "load_scored" in inspect.getsource(MainWindow._cached)
    for method in (MainWindow._show_report, MainWindow._on_select,
                   MainWindow._show_indexed_episode,
                   MainWindow._show_full_series):
        src = inspect.getsource(method)
        assert "load_cached(" not in src, (
            f"{method.__name__} reads the cache directly, so it skips the "
            f"re-score")

    # And the engine call itself does what the screen relies on.
    config = load_config()
    result = _result()
    before = result.metrics.sensory_load.score
    config = dict(config)
    config["sensory_load_weights"] = {
        k: (1.0 if k == "pacing" else 0.0)
        for k in config.get("sensory_load_weights", {})}
    after = rescore_episode(result, config).metrics.sensory_load.score
    assert after != before


def test_every_export_carries_its_provenance():
    """A CSV of numbers with no qualifiers is the artefact §2.2 forbids.

    JSON embeds the provenance block; CSV writes a sidecar so the data file
    stays machine-readable. Neither may become optional.
    """
    from ui.main_window import MainWindow
    assert "validation_dict" in inspect.getsource(MainWindow.export_json)
    csv_src = inspect.getsource(MainWindow.export_csv)
    assert "validation_statement" in csv_src
    assert "_PROVENANCE.txt" in csv_src


def test_export_actions_are_disabled_with_nothing_to_export():
    """Otherwise they export whatever was last on screen."""
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow._set_export_source)
    assert "setEnabled(episode is not None or show is not None)" in src


def test_the_two_settings_axes_stay_separate():
    """Scoring re-scores from cache; measurement invalidates it.

    Mixing them would let someone change a detector threshold and see scores
    that blend old detections with a new configuration label.
    """
    from ui import measurements, settings
    scoring = inspect.getsource(settings)
    for measurement_key in ("cut_detection_threshold", "sample_fps",
                            "flashing_luminance_threshold", "measurements"):
        assert measurement_key not in scoring, measurement_key
    # And the measurement dialog must not edit weights or ceilings.
    measuring = inspect.getsource(measurements)
    for scoring_key in ("sensory_load_weights",
                        "normalization_reference_ranges"):
        assert scoring_key not in measuring, scoring_key


def test_measurement_settings_are_built_from_the_registry():
    """A tool added to the engine must appear without editing the dialog."""
    from ui import measurements
    src = inspect.getsource(measurements)
    assert "for spec in MEASUREMENTS" in src
    assert "for tool in spec.tools" in src


def test_a_tools_validation_status_travels_with_its_name():
    """CLAUDE.md §2.2: unvalidated measures are flagged wherever they appear."""
    from analyzer.measurements import MEASUREMENTS, STATUS_LABEL
    from ui.measurements import _status_text
    for spec in MEASUREMENTS:
        for tool in spec.tools:
            shown = _status_text(tool)
            assert tool.name in shown
            assert STATUS_LABEL[tool.status] in shown


def test_staleness_reports_what_it_cannot_check():
    """`is_stale` grandfathers results written before fingerprinting.

    That is the right engine default — one upgrade must not invalidate a
    corpus — but reporting only the detectable count understates the cost in
    the direction that flatters the change. This working copy has 12 cached
    episodes and 1 fingerprint, so the gap is not hypothetical.
    """
    from ui.measurements import MeasurementsDialog
    src = inspect.getsource(MeasurementsDialog._count_stale)
    assert "cached_fingerprint" in src
    assert "-> tuple[int, int]" in inspect.getsource(
        MeasurementsDialog._count_stale).splitlines()[0]


def test_optional_tools_shows_costs_and_caveats_not_just_benefits():
    """TransNetV2's caveats include "unverified on animation".

    For a children's-television tool that outranks its benchmark scores, so a
    panel that rendered only `benefits` would be selling the download.
    """
    from ui.optional_tools import ToolPanel
    src = inspect.getsource(ToolPanel.__init__)
    for field in ("tool.benefits", "tool.costs", "tool.caveats"):
        assert field in src, field
    assert "install_command" in src, "the exact pip command must be shown"


def test_episode_notes_and_metadata_live_in_the_index_not_the_cache():
    """Re-analysing an episode must not erase what a person typed."""
    from ui.main_window import MainWindow
    for method in (MainWindow._save_metadata, MainWindow._save_note,
                   MainWindow._show_episode_details):
        src = inspect.getsource(method)
        assert "analyzer.db" in src or "self._db()" in src
        assert "save_cache" not in src


def test_the_analysis_queue_holds_paths_not_results():
    """A queued result would be stale before its turn came.

    The queue can sit for an hour while earlier entries run; anything derived
    stored in it would describe the library as it was when queued.
    """
    from ui.automated import AutomatedTab
    src = inspect.getsource(AutomatedTab.enqueue)
    assert "Path(path)" in src
    assert "self._queue.append(path)" in src


def test_a_missing_queued_target_does_not_end_the_run():
    """Queue twenty, delete one, and the other nineteen still get measured."""
    from ui.automated import AnalysisWorker
    src = inspect.getsource(AnalysisWorker.run)
    assert "target.exists()" in src
    assert "no longer on disk" in src
    assert "continue" in src


def test_queue_progress_spans_the_whole_queue():
    """Per-target progress would reset the bar to zero on every entry."""
    from ui.automated import AnalysisWorker
    src = inspect.getsource(AnalysisWorker._tick)
    assert "(self._index + overall) / total" in src


def test_the_sampler_can_hand_a_draw_to_the_measurement_pass():
    """A sample that only prints a list leaves the bookkeeping to the user.

    That is the reason sampling was made a first-class module rather than a
    CSV export — see DECISIONS.md, 2026-06-30.
    """
    from ui.automated import AutomatedTab
    from ui.sampler import SamplerDialog
    assert callable(AutomatedTab.enqueue)
    src = inspect.getsource(SamplerDialog._send_to_queue)
    assert "_automated.enqueue" in src
    # And it must not be mistaken for recording the draw.
    assert "did not write the sample" in src


# ---------------------------------------------------------------------------
# Crash and cost regressions
# ---------------------------------------------------------------------------

def test_no_screen_drops_its_worker_reference_in_a_slot():
    """Freeing a live QThread from its own signal handler kills the process.

    The C++ object is deleted while still inside emit, so it dies with no
    traceback and no Python exception. Guards must use isRunning() and keep
    the reference — the pattern AutomatedTab has always used.

    Checked by PARSING rather than by matching the line's text. The text check
    this replaced looked for exactly `self._worker = None`, which meant every
    screen that wrote `self._worker: SomeWorker | None = None` slipped past it
    — including inside a slot, where it is fatal — while a perfectly safe
    initialiser in `__init__` failed it. It was wrong in both directions at
    once. This walks the AST instead: any assignment of None to a
    worker-shaped attribute, annotated or not, outside `__init__`.
    """
    import ast
    import pathlib

    import ui

    def _worker_attr(target) -> str | None:
        if isinstance(target, ast.Attribute) and                 isinstance(target.value, ast.Name) and target.value.id == "self":
            name = target.attr
            if "worker" in name.lower() or "transcriber" in name.lower():
                return name
        return None

    offenders = []
    for path in sorted(pathlib.Path(ui.__file__).parent.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if func.name == "__init__":
                continue          # setting up the attribute is not freeing it
            for node in ast.walk(func):
                targets = []
                if isinstance(node, ast.Assign):
                    targets = node.targets
                elif isinstance(node, ast.AnnAssign) and node.value is not None:
                    targets = [node.target]
                for target in targets:
                    attr = _worker_attr(target)
                    if attr and isinstance(node.value, ast.Constant)                             and node.value.value is None:
                        offenders.append(f"{path.name}:{node.lineno} ({func.name})")

    assert offenders == [], (
        "these free a QThread outside __init__, which is fatal if the method "
        "is connected to that worker's own signal: " + ", ".join(offenders))

def test_startup_path_imports_no_heavy_library_at_module_scope():
    """A module-level import is a cost paid on every launch.

    pandas (~1.1s) and scenedetect (~0.6s) are needed for CSV export and for
    running detection. Neither is needed to draw the first screen, and all
    three modules below are reached while the interface starts.
    """
    import ast
    import pathlib
    import analyzer
    heavy = {"pandas", "scenedetect", "torch", "matplotlib"}
    root = pathlib.Path(analyzer.__file__).parent
    for name in ("aggregate.py", "metrics_cuts.py", "validation.py",
                 "pipeline.py", "trials.py"):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        for node in tree.body:                      # module scope only
            names = set()
            if isinstance(node, ast.Import):
                names = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = {node.module.split(".")[0]}
            assert not (names & heavy), f"{name} imports {names & heavy}"


def test_asking_whether_a_tool_is_installed_does_not_import_it():
    """`is_available()` decides whether to grey out a control.

    Importing the package to answer that pulled PyTorch into the process —
    3.6 seconds, for a tooltip.
    """
    import inspect
    from analyzer.optional_tools import OptionalTool
    src = inspect.getsource(OptionalTool.is_available)
    assert "find_spec" in src
    assert "import_module" not in src
    assert "import_module" not in inspect.getsource(OptionalTool.version)


# ---------------------------------------------------------------------------
# Compare, import, transcribe, sample aggregate
# ---------------------------------------------------------------------------

def test_a_comparison_issues_no_verdict():
    """A side-by-side is the easiest place to imply a ranking.

    Two value columns and a signed difference — no ordering, no arrow, no
    wording that makes one side the winner. CLAUDE.md §2.1.
    """
    from ui.report import compare_html
    a, b = _result(), _result()
    b.metrics.sensory_load.score = 0.481
    a.metrics.audio.available = b.metrics.audio.available = True
    html = compare_html(a, b, "A", "B")
    assert html.startswith("<html>")
    assert "+0.219" in html                     # 0.481 - 0.262, signed
    body = html.lower()
    for banned in ("higher risk", "too fast", "winner", "best", "worst",
                   "recommended", "unsuitable"):
        assert banned not in body, banned
    # The one place a comparative word may appear is the guardrail itself.
    assert "not a worse programme" in body


def test_a_comparison_warns_when_audio_is_missing_on_one_side():
    """Missing audio redistributes its weight, so the composites differ in
    composition as well as value — the difference is not like for like."""
    from ui.report import compare_html
    a, b = _result(), _result()
    a.metrics.audio.available = True            # b keeps the default False
    assert "not composed the same way" in compare_html(a, b, "A", "B")


def test_comparison_covers_the_same_metrics_the_report_does():
    """A comparison quietly covering fewer metrics than the report it sits
    beside would look like agreement where none was checked."""
    from ui.report import AGGREGATE_ROWS, COMPARE_EPISODE_ROWS
    compared = {h for h, _read, _p in COMPARE_EPISODE_ROWS}
    aggregated = {h for h, _attr, _p in AGGREGATE_ROWS}
    assert aggregated <= compared, aggregated - compared


def test_metadata_import_flags_matches_it_guessed():
    """`match_to_files` falls back to title similarity down to 0.45.

    Applying a wrong fuzzy match writes an air date that nothing downstream
    questions — and air dates drive era stratification in the sampler. So the
    count is warned about and every row can be unchecked.
    """
    from ui.metadata_import import MetadataImportDialog
    src = inspect.getsource(MetadataImportDialog._fill)
    assert "TITLE SIMILARITY" in src
    assert "match.score" in src
    assert "Qt.ItemIsUserCheckable" in src
    assert callable(MetadataImportDialog._uncheck_fuzzy)
    # Nothing unchecked may be written.
    apply_src = inspect.getsource(MetadataImportDialog._apply)
    assert "checkState(0) != Qt.Checked" in apply_src


def test_transcription_skips_episodes_that_already_have_captions():
    """Whisper costs minutes per episode; a caption file is already exact."""
    from ui.automated import AutomatedTab
    src = inspect.getsource(AutomatedTab._needs_captions)
    assert "_find_cc_file" in src
    assert "continue" in src


def test_transcription_does_not_re_measure_the_video():
    """It patches the cached speech block, nothing else.

    Re-running the full analysis to pick up a transcript would recompute
    minutes of colour, motion and flashing figures that have not changed.
    """
    from ui.automated import TranscribeWorker
    src = inspect.getsource(TranscribeWorker.run)
    assert "transcribe_only" in src
    assert "analyze_episode" not in src
    assert '"speech"' in src


def test_sample_aggregate_counts_the_whole_sample_not_just_the_analysed():
    """Otherwise "10 episodes" means the ten that happen to be cached."""
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow._show_sample_aggregate)
    assert "aggregate.episode_count = len(episodes)" in src


def test_sample_aggregate_can_actually_import_its_episode_reader():
    """The text version of this test passed while the import was broken.

    `_show_sample_aggregate` imports its selected.csv reader inside the
    function, so a rename leaves the source string intact and the button
    raising ImportError on click. Asserting the symbol resolves is the
    cheapest thing that would have caught it.
    """
    import ast
    import importlib
    import inspect as _inspect
    from ui.main_window import MainWindow

    tree = ast.parse(_inspect.getsource(MainWindow._show_sample_aggregate)
                     .lstrip())
    imports = [node for node in ast.walk(tree)
               if isinstance(node, ast.ImportFrom)]
    assert imports, "the reader is expected to be imported inside the function"
    for node in imports:
        module = importlib.import_module(node.module)
        for alias in node.names:
            assert hasattr(module, alias.name), \
                f"{node.module}.{alias.name} does not exist"


def test_compare_refuses_to_mix_an_episode_with_a_show():
    """One episode's numbers beside a mean of many is not a difference."""
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow._sync_compare)
    assert "self._selected[0] == self._pinned[0]" in src


def test_the_sampler_offers_era_as_well_as_season():
    """Stratifying a long run by production period is the reason eras exist.

    The Qt sampler shipped with season and none only, which quietly dropped
    a whole axis the engine has always supported.
    """
    from ui import sampler
    values = {value for value, _label, _tip in sampler.STRATIFY}
    assert {"season", "era", None} <= values


def test_the_sampler_fills_the_era_column_before_stratifying_on_it():
    """`Episode.extra` is populated by nothing in the engine.

    A folder scan cannot know an air date either, so without this step
    "stratify by era" reports a stratified design and draws one stratum.
    """
    from ui.sampler import SamplerDialog
    src = inspect.getsource(SamplerDialog._apply_eras)
    assert "attach_air_dates" in src
    assert "assign_eras" in src
    assert "get_show_eras" in src


def test_the_sampler_says_when_era_stratification_would_do_nothing():
    """No eras defined means one "(no era)" group — not a stratified draw."""
    from ui.sampler import SamplerDialog
    src = inspect.getsource(SamplerDialog._sync_enabled)
    assert "UNASSIGNED" in src
    assert "same as not" in src


def test_era_labels_follow_the_chosen_axis():
    """"Per season" is wrong when the draw is grouped by era."""
    from ui.sampler import SamplerDialog
    src = inspect.getsource(SamplerDialog._sync_enabled)
    assert '"Per era:" if by_era else "Per season:"' in src


def test_the_era_editor_shows_how_many_episodes_land_in_each():
    """An era with one episode is censused; an empty one is not a stratum."""
    from ui.eras import ErasDialog
    src = inspect.getsource(ErasDialog._refresh)
    assert "assign_eras" in src
    assert "coverage_note" in src


def test_chart_plots_components_not_the_composite_alone():
    """A bar of the composite alone hides how two equal scores were reached."""
    from ui import chart
    from analyzer.config_loader import load_config
    weights = load_config().get("sensory_load_weights", {})
    for _label, _attr, weight_key in chart.COMPONENTS:
        assert weight_key in weights, weight_key


# ---------------------------------------------------------------------------
# Sending a Library selection to another tab
# ---------------------------------------------------------------------------

def test_the_library_offers_a_context_menu():
    """Right-click is the platform's "act on this item" gesture, and it was
    the missing way to get an episode from the Library to the tab that works
    on it — selection pushed the target silently and left you to find the tab.
    """
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow._build_library)
    assert "CustomContextMenu" in src
    assert "customContextMenuRequested" in src


def test_the_library_allows_selecting_several_episodes():
    """Queueing a batch was one-at-a-time because the tree was SingleSelection."""
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow._build_library)
    assert "ExtendedSelection" in src


def test_the_menu_is_built_separately_from_being_shown():
    """So which destinations are offered for which selection is testable."""
    from ui.main_window import MainWindow
    assert callable(MainWindow.build_library_menu)
    assert "return menu" in inspect.getsource(MainWindow.build_library_menu)


def test_hand_coding_destinations_require_exactly_one_episode():
    """Hand coding is per episode. A show folder or a multi-selection has no
    single video to open, so those entries are disabled rather than absent —
    an unavailable control must not look like a broken one."""
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow.build_library_menu)
    assert "act.setEnabled(len(files) == 1)" in src
    assert "hand coding is per" in src


def test_every_destination_routes_through_one_send_path():
    """The menu, the pipeline nodes and anything added later must agree about
    what "send to Human coding" means."""
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow.build_library_menu)
    # Every action delegates; none reaches into a tab itself.
    assert src.count("self._send_to(") >= 6
    assert "setCurrentWidget" not in src, (
        "the menu must not switch tabs itself — that belongs in _send_to")


def test_sending_a_selection_deduplicates():
    """Selecting a show and one of its episodes must not queue it twice."""
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow._selected_paths)
    assert "seen" in src and "unique" in src


def test_show_in_index_lands_on_the_row():
    """Landing on the top of the table is not "show in index"."""
    from ui.index_tab import IndexTab
    src = inspect.getsource(IndexTab.focus_episode)
    assert "scrollToItem" in src and "setCurrentItem" in src
    # And it says so when the episode was never analysed.
    assert "not in the index yet" in src


def test_the_video_surface_paints_its_own_pixels(qapp):
    """WA_OpaquePaintEvent promises Qt this widget covers every pixel.

    It did not: with no media loaded nothing painted the surface at all, and
    whatever was on screen before survived underneath — the Trials list showed
    through the coding screen. Rendering it over a known background and reading
    the pixels back is the only check that would have caught it; every
    attribute involved was set correctly.
    """
    import pytest
    from PySide6.QtGui import QPixmap
    import ui.player as player_mod

    ok, reason = player_mod.available()
    if not ok:
        pytest.skip(f"no libvlc: {reason}")

    surface = player_mod.VideoSurface()
    surface.resize(400, 300)

    for idle in (True, False):
        surface.set_idle(idle)
        canvas = QPixmap(400, 300)
        canvas.fill()                      # white, so a no-op paint shows up
        surface.render(canvas)
        corner = canvas.toImage().pixelColor(5, 5)
        assert corner.name() == "#000000", \
            f"surface left its background unpainted when idle={idle}"
