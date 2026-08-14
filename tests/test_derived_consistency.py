"""
Derived values must agree across every place that stores or shows them.

The composite is DERIVED from raw metrics plus the current weights. It is
stored in the SQLite index and recomputed on read in the Library, so a scoring
change made the two disagree: 0.107 in the Library, 0.132 in the Index, for
the same episode, with nothing marking either as stale — and the Index is the
cross-episode comparison screen, so its outlier fences were computed over a
mix of weightings.
"""

from __future__ import annotations

import inspect


def test_a_scoring_change_rewrites_the_index_too():
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow.open_settings)
    assert "rescore_index" in src, (
        "Apply & Re-score updates the Library but leaves the index holding "
        "scores computed under the old weights")


def test_rescoring_the_index_reads_through_the_rescoring_cache():
    """It must not read `load_cached` directly or it rewrites stale scores."""
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow.rescore_index)
    assert "self._cached(" in src
    assert "load_cached(" not in src


def test_rescoring_the_index_touches_no_raw_metric():
    """Only the composite is recomputed — that is what makes it instant."""
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow.rescore_index)
    for forbidden in ("analyze_episode", "analyze_show_batch", "save_cache"):
        assert forbidden not in src, forbidden


def test_a_validation_trial_records_which_detector_it_graded():
    """Two runs of one episode on one date with different F1s are a detector
    comparison, not a contradiction — but only if the tag is carried."""
    from analyzer.trials import _detector_tag
    from pathlib import Path
    tag = _detector_tag(
        {"detections_file": "Ep__content-t27-diss_detections.csv"},
        Path("Ep__content-t27-diss_comparison_manifest_2026-08-08.json"))
    assert tag == "content-t27-diss"
    # Falls back to the manifest name when the field is absent.
    assert _detector_tag(
        {}, Path("Ep__transnet-t0.5-solo_comparison_manifest_2026-01-01.json")
    ) == "transnet-t0.5-solo"
    assert _detector_tag({}, Path("nothing-useful.json")) == "unrecorded"


def test_the_trials_table_shows_the_detector():
    from ui import trials_tab
    assert "Detector" in trials_tab.COLUMNS


def test_publishing_zero_events_warns_that_it_looks_like_uncoded():
    """An empty template rates out at 0.0 events/min exactly as a genuinely
    event-free episode does, and publishing puts that on the public site."""
    from analyzer.event_coding import publish_manual_metrics
    src = inspect.getsource(publish_manual_metrics)
    assert "ZERO coded events" in src
    assert "indistinguishable from an episode nobody" in src


def test_publishing_still_requires_a_sampling_statement():
    """Provenance is not optional; the warning above must not have relaxed it."""
    from analyzer.event_coding import publish_manual_metrics
    src = inspect.getsource(publish_manual_metrics)
    assert "Provide sampling_method text or a trial_manifest." in src


def test_every_reader_of_a_cached_result_re_derives_the_composite():
    """The same mistake was made independently in four places.

    The cache stores the composite as it stood when the episode was analysed.
    Reading it without re-deriving reports a score under weights no longer in
    force — and with four readers that meant four answers for one episode.
    """
    import cli
    from analyzer import batch
    from ui.main_window import MainWindow
    readers = {
        "MainWindow._cached": inspect.getsource(MainWindow._cached),
        "MainWindow.rescore_index": inspect.getsource(
            MainWindow.rescore_index),
        "cli._analyze_single": inspect.getsource(cli._analyze_single),
        "cli._db_backfill": inspect.getsource(cli._db_backfill),
        "batch.analyze_show_batch": inspect.getsource(
            batch.analyze_show_batch),
    }
    for name, src in readers.items():
        assert "load_scored" in src or "self._cached(" in src, name


def test_load_scored_leaves_a_failed_result_alone():
    """There is no composite to derive for a failure, and rescoring one
    would invent numbers for an episode that produced none."""
    import tempfile
    from pathlib import Path
    from analyzer.cache import load_scored, save_cache
    from analyzer.config_loader import load_config
    from analyzer.schema import EpisodeResult
    root = Path(tempfile.mkdtemp())
    failed = EpisodeResult(file="b.mp4", status="failed", error="moov atom")
    save_cache(root, "Show", "b", failed.to_dict())
    out = load_scored(root, "Show", "b", load_config())
    assert out.status == "failed"
    assert out.error == "moov atom"


def test_load_scored_returns_none_when_nothing_is_cached():
    import tempfile
    from pathlib import Path
    from analyzer.cache import load_scored
    assert load_scored(Path(tempfile.mkdtemp()), "Show", "nope", None) is None


def test_the_speech_backfill_script_targets_the_library_root():
    """It assumed the root was its own directory.

    Once the library moved into `Shows/`, it patched a stale project-level
    cache of 82 episodes while the application read a different one of 28 —
    and reported success either way.
    """
    import pathlib
    src = pathlib.Path("patch_speech_cache.py").read_text(encoding="utf-8")
    assert "last_root_folder" in src
    assert "ROOT         = Path(__file__).parent" not in src
    assert "--dry-run" in src


def test_the_speech_backfill_script_can_report_without_writing():
    """A script that mutates research data should be inspectable first."""
    import pathlib
    src = pathlib.Path("patch_speech_cache.py").read_text(encoding="utf-8")
    assert "if not DRY_RUN:" in src
    assert "Library root :" in src, "it must say which library it is about to touch"


def test_the_pdf_states_the_accuracy_figure_once():
    """`validation_short()` opens with its own heading; a second one stuttered."""
    import pathlib
    src = pathlib.Path("analyzer/report_pdf.py").read_text(encoding="utf-8")
    assert '"<b>Detection accuracy.</b> " + validation_short()' not in src
