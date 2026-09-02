"""
The measurement model must resolve to real numbers, and must refuse rather
than guess.

Written at the artefact level the project's other useful tests are written at:
these build a real cache file and a real coding sheet on disk and read what
the model returns from them, rather than asserting the registry has the right
number of entries. `MEASUREMENT_MODEL.md` §4.1 is explicit that counting
registry entries is not verification.

The two failures being guarded against, both of which this project has already
had in other forms:

  * a construct that names a measure resolving to nothing — a control whose
    data path is empty (`LEARNINGS.md` shape 2);
  * a second list of detectors written beside the registry
    (`LEARNINGS.md` shape 3).
"""

from __future__ import annotations

import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest

from analyzer import constructs as C
from analyzer import measurements as reg
from analyzer.schema import EpisodeResult


# ---------------------------------------------------------------------------
# Fixtures — a real cached result and a real coding sheet, on disk
# ---------------------------------------------------------------------------

SHOW, STEM = "Test Show", "S01E01 Something"


def _write_cache(root: Path, *, tool="pyscenedetect_content", cuts=12.5,
                 legacy_only=False, no_config=False, audio=True,
                 speech=True) -> Path:
    cfg: dict = {}
    if not no_config:
        cfg = {"cut_detection_threshold": 27.0, "sample_fps": 2.0}
        if not legacy_only:
            cfg = reg.normalize_config(dict(cfg))
            cfg["measurements"]["transitions"]["tool"] = tool
            # Dissolves ship disabled; switch them on so the fixture exercises
            # that measure's path instead of excusing it.
            cfg["measurements"]["dissolves"]["enabled"] = True
    result = EpisodeResult(file=f"{STEM}.mp4", duration_sec=600.0, config=cfg)
    result.metrics.scene_pacing.cuts_per_min = cuts
    result.metrics.scene_pacing.dissolves_per_min = 1.4
    result.metrics.scene_pacing.shot_length_cv = 0.62
    result.metrics.scene_pacing.scene_changes_per_min = 5.1
    result.metrics.shot_length.mean_sec = 4.8
    result.metrics.shot_length.median_sec = 4.2
    result.metrics.color_saturation.mean = 0.4
    result.metrics.color_saturation.contrast_mean = 0.2
    result.metrics.motion.mean = 0.1
    result.metrics.flashing.luminance_delta_events_per_min = 5.0
    # `available` gates resolution: without it the 0.0 defaults in these blocks
    # would resolve as if they had been measured.
    result.metrics.audio.available = audio
    result.metrics.audio.rms_mean = 0.15 if audio else 0.0
    result.metrics.speech.available = speech
    result.metrics.speech.words_per_minute = 120.0 if speech else 0.0
    result.metrics.speech.speech_density = 0.5 if speech else 0.0
    result.metrics.speech.total_words = 900 if speech else 0
    path = root / ".analysis" / SHOW / f"{STEM}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict()), encoding="utf-8")
    return path


def _write_sheet(vdir: Path, *, window: tuple[float, float] | None) -> Path:
    vdir.mkdir(parents=True, exist_ok=True)
    sheet = vdir / f"{STEM}_manual.csv"
    with sheet.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["timestamp_hms", "timestamp_sec", "type",
                    "scene_relation", "notes"])
        # scene_relation is labelled: without it the hand-coded scene-change
        # rate legitimately has no value, which is correct behaviour but does
        # not exercise the path.
        for i, sec in enumerate((10, 20, 40, 55, 80, 95, 130, 160)):
            w.writerow([f"00:{sec:02d}", "", "hard_cut",
                        "change" if i % 2 else "within", ""])
        w.writerow(["00:50", "", "dissolve", "", ""])
    if window is not None:
        (vdir / f"{STEM}__handcoded_2026-08-16.json").write_text(
            json.dumps({"episode": f"{STEM}.mp4", "source": "hand-coded",
                        "transitions": {"window": list(window)}}),
            encoding="utf-8")
    return sheet


@pytest.fixture
def ref(tmp_path):
    """An episode with a cached automated result and a fully recorded sheet."""
    root, vdir = tmp_path / "lib", tmp_path / "validation"
    _write_cache(root)
    _write_sheet(vdir, window=(0.0, 180.0))
    return C.EpisodeRef(root=root, show_name=SHOW, stem=STEM,
                        duration_sec=600.0, validation_dir=vdir)


# ---------------------------------------------------------------------------
# Every shipped measure resolves — or names a method that could
# ---------------------------------------------------------------------------

def test_every_measure_belongs_to_a_shipped_construct():
    keys = {c.key for c in C.CONSTRUCTS}
    for m in C.MEASURES:
        assert m.construct_key in keys, m.key


def test_every_aspect_named_by_a_measure_exists_on_its_construct():
    for m in C.MEASURES:
        if not m.aspect_key:
            continue
        construct = C.get_construct(m.construct_key)
        assert construct is not None
        assert m.aspect_key in {a.key for a in construct.aspects}, m.key


def test_every_automated_value_path_exists_in_the_schema():
    """A measure whose value_path does not exist would silently resolve to
    nothing — a label, not a measure. Checked against a real EpisodeResult
    rather than against a hand-copied list of field names, so renaming a
    schema field fails here instead of going quiet."""
    blank = EpisodeResult().to_dict()
    for m in C.MEASURES:
        if m.automated is None:
            continue
        assert C._dig(blank, m.automated.value_path) is not None, (
            f"{m.key}: {m.automated.value_path} is not a field of EpisodeResult")


def test_every_automated_measure_names_a_real_registry_measurement():
    for m in C.MEASURES:
        if m.automated is None:
            continue
        assert reg.get_measurement(m.automated.measurement_key) is not None, m.key


def test_every_hand_field_is_a_real_key_of_the_hand_coding_analysis(ref):
    """Not a hand-copied field list: run the real analysis and look."""
    from analyzer.validation import manual_pacing_metrics, parse_manual_csv
    sheet = Path(ref.validation_dir) / f"{STEM}_manual.csv"
    produced = manual_pacing_metrics(parse_manual_csv(sheet), duration_sec=600.0,
                                     start=0.0, end=180.0)
    for m in C.MEASURES:
        if m.hand is None or m.hand.kind != "transitions":
            continue
        assert m.hand.field_key in produced, (
            f"{m.key} reads {m.hand.field_key}, which manual_pacing_metrics "
            f"does not produce")


def test_every_measure_resolves_to_a_number_by_at_least_one_method(ref):
    """The whole point. A construct naming measures that all refuse is a
    picture of a measurement system, not one."""
    unresolved = []
    for m in C.MEASURES:
        results = C.resolve_measure(m.key, ref)
        if not any(r.ok for r in results):
            unresolved.append((m.key, [(r.method_label, r.status) for r in results]))
    assert not unresolved, unresolved


# ---------------------------------------------------------------------------
# The registry is read, never restated
# ---------------------------------------------------------------------------

def test_a_detector_added_to_the_registry_appears_as_a_method(monkeypatch):
    """The trap `MEASUREMENT_MODEL.md` names for this phase by name: a second
    list of detectors. Adding a tool to the registry must be the only edit."""
    before = {m.key for m in C.methods_for("hard_cuts_per_min")}

    invented = reg.ToolSpec(key="invented_detector", name="Invented detector",
                            summary="only exists in this test",
                            status=reg.EXPERIMENTAL)
    patched = replace(reg.TRANSITIONS, tools=[*reg.TRANSITIONS.tools, invented])
    monkeypatch.setattr(reg, "MEASUREMENTS",
                        [patched if m.key == "transitions" else m
                         for m in reg.MEASUREMENTS])

    after = {m.key for m in C.methods_for("hard_cuts_per_min")}
    assert after - before == {"auto:transitions:invented_detector"}


def test_a_methods_status_comes_from_the_registry_not_from_this_module(monkeypatch):
    """Regrading a tool in measurements.py must change the flag here with no
    edit — otherwise the flag is a restated claim (`LEARNINGS.md` shape 3)."""
    original = reg.TRANSITIONS.tools[0]
    assert original.status == reg.VALIDATED
    method = C.get_method("hard_cuts_per_min", f"auto:transitions:{original.key}")
    assert method is not None
    assert C._flag_for(method) == ""

    downgraded = replace(original, status=reg.UNVALIDATED)
    patched = replace(reg.TRANSITIONS,
                      tools=[downgraded, *reg.TRANSITIONS.tools[1:]])
    monkeypatch.setattr(reg, "MEASUREMENTS",
                        [patched if m.key == "transitions" else m
                         for m in reg.MEASUREMENTS])

    method = C.get_method("hard_cuts_per_min", f"auto:transitions:{original.key}")
    assert method is not None
    assert "unvalidated" in C._flag_for(method)


def test_an_unvalidated_method_carries_its_flag_onto_the_resolved_value(ref):
    """`CLAUDE.md` §2.2: flagged wherever the numbers appear — including here,
    which is where every later screen will get them from."""
    results = C.resolve_measure("scene_changes_per_min_detected", ref)
    assert results, "the detected scene-change measure has no methods"
    for r in results:
        assert r.flag, f"{r.method_label} is unvalidated but carries no flag"


def test_hand_coding_is_not_labelled_unvalidated():
    """`CLAUDE.md` §2.5: automated measurement is not inherently more valid
    than human coding. Reusing the registry's word for it would say otherwise."""
    method = C.get_method("hard_cuts_per_min", "hand:transitions")
    assert method is not None
    assert method.status == C.HUMAN_CODED_STATUS
    assert method.status not in (reg.VALIDATED, reg.EXPERIMENTAL, reg.UNVALIDATED)
    assert C._flag_for(method) == ""


# ---------------------------------------------------------------------------
# Refusals — the model must decline rather than produce a plausible number
# ---------------------------------------------------------------------------

def test_a_block_marked_unavailable_refuses_rather_than_reporting_its_zero(
        tmp_path):
    """An episode with no audio track carries `audio.rms_mean == 0.0` and
    `audio.available == False`. An episode with no captions carries
    `speech.words_per_minute == 0.0`. Those zeroes are schema defaults, not
    measurements, and reporting them makes a silent episode and an unmeasured
    one indistinguishable — the same distinction `event_coding`'s publish guard
    protects on the hand-coding side.

    Four of the fourteen cached episodes in the author's library have no speech
    block at all, so this is the ordinary case, not an edge one.
    """
    root = tmp_path / "lib"
    _write_cache(root, audio=False, speech=False)
    ref = C.EpisodeRef(root=root, show_name=SHOW, stem=STEM,
                       validation_dir=tmp_path / "validation")

    for key in ("audio_rms_mean", "words_per_minute", "speech_density",
                "total_words"):
        results = [r for r in C.resolve_measure(key, ref)
                   if r.method_key.startswith("auto:")]
        assert results
        for r in results:
            assert r.status != C.MEASURED, (key, r.method_label, r.value)
        assert any(r.status == C.NOT_RUN for r in results), key

    # And the measures that do not depend on an availability flag still work.
    assert C.resolve("hard_cuts_per_min",
                     "auto:transitions:pyscenedetect_content", ref).ok


def test_an_unanalysed_episode_refuses_instead_of_returning_zero(tmp_path):
    ref = C.EpisodeRef(root=tmp_path / "lib", show_name=SHOW, stem=STEM,
                       validation_dir=tmp_path / "validation")
    r = C.resolve("hard_cuts_per_min", "auto:transitions:pyscenedetect_content", ref)
    assert r.status == C.NOT_RUN
    assert r.value is None


def test_a_method_that_did_not_produce_the_cached_number_refuses(tmp_path):
    """Asking what TransNetV2 gave for an episode measured with ContentDetector
    must not hand back ContentDetector's number under TransNetV2's name."""
    root = tmp_path / "lib"
    _write_cache(root, tool="pyscenedetect_content", cuts=12.5)
    ref = C.EpisodeRef(root=root, show_name=SHOW, stem=STEM,
                       validation_dir=tmp_path / "validation")

    used = C.resolve("hard_cuts_per_min", "auto:transitions:pyscenedetect_content", ref)
    assert used.status == C.MEASURED and used.value == 12.5

    other = C.resolve("hard_cuts_per_min", "auto:transitions:transnetv2", ref)
    assert other.status == C.METHOD_NOT_USED
    assert other.value is None
    assert "ContentDetector" in other.detail


def test_attribution_describes_the_cache_not_the_settings_in_force(tmp_path):
    """The parameters reported for a cached number must be the ones that
    PRODUCED it, not the ones currently configured.

    `cache.load_scored` returns a result rebuilt by `rescore_episode`, which
    attaches the config it was rescored WITH. Reading attribution off that copy
    reports today's settings as the settings that measured the episode — right
    whenever the two agree, wrong exactly when they differ, which is the only
    situation anyone asks in. Found by changing a live threshold and watching
    a recipe pinned to the cache's own value refuse its own episode.
    """
    root = tmp_path / "lib"
    _write_cache(root, cuts=12.5)                     # measured at 27.0
    ref = C.EpisodeRef(root=root, show_name=SHOW, stem=STEM,
                       validation_dir=tmp_path / "validation")

    live = reg.normalize_config({"cut_detection_threshold": 33.0})
    live["sensory_load_weights"] = {"pacing": 1.0}
    live["normalization_reference_ranges"] = {
        k: {"min": 0.0, "max": 1.0} for k in
        ("cuts_per_min", "color_saturation_mean", "color_contrast_mean",
         "motion_mean", "flashing_events_per_min", "audio_rms_mean")}

    r = C.resolve("hard_cuts_per_min",
                  "auto:transitions:pyscenedetect_content", ref, live)
    assert r.status == C.MEASURED
    assert r.value == 12.5
    assert r.parameters["threshold"] == 27.0, (
        "reported the live threshold as the one that produced the number")


def test_a_result_that_cannot_say_which_tool_produced_it_refuses(tmp_path):
    """Eleven of the results in the author's working copy predate the
    measurements block. A number that cannot be attributed must not be
    attributed — the three-state answer, not two."""
    root = tmp_path / "lib"
    _write_cache(root, no_config=True)
    ref = C.EpisodeRef(root=root, show_name=SHOW, stem=STEM,
                       validation_dir=tmp_path / "validation")
    r = C.resolve("hard_cuts_per_min", "auto:transitions:pyscenedetect_content", ref)
    assert r.status == C.TOOL_UNRECORDED
    assert r.value is None
    assert r.attribution == C.UNRECORDED


def test_a_legacy_config_attributes_the_tool_but_says_it_inferred_it(tmp_path):
    root = tmp_path / "lib"
    _write_cache(root, legacy_only=True, cuts=9.0)
    ref = C.EpisodeRef(root=root, show_name=SHOW, stem=STEM,
                       validation_dir=tmp_path / "validation")
    r = C.resolve("hard_cuts_per_min", "auto:transitions:pyscenedetect_content", ref)
    assert r.status == C.MEASURED and r.value == 9.0
    assert r.attribution == C.INFERRED_LEGACY, (
        "a tool read out of migrated legacy keys must not claim to be recorded")


def test_an_uncoded_episode_refuses_instead_of_reporting_zero_transitions(tmp_path):
    """`event_coding` already refuses to publish an uncoded episode as a zero
    rate. The same distinction has to hold here."""
    root = tmp_path / "lib"
    _write_cache(root)
    ref = C.EpisodeRef(root=root, show_name=SHOW, stem=STEM, duration_sec=600.0,
                       validation_dir=tmp_path / "validation")
    r = C.resolve("hard_cuts_per_min", "hand:transitions", ref)
    assert r.status == C.NOT_RUN
    assert r.value is None


def test_a_sheet_with_no_recorded_window_refuses_every_span_dependent_value(tmp_path):
    """THE defect this model found in the author's own data on 2026-08-16.

    A sheet covering the first ten seconds of a twenty-four minute episode,
    divided by the full runtime, reported 0.084 cuts/min against a detected
    17.785 — and a mean shot length of 473 seconds. Both looked like
    measurements. Knowing the episode's duration must not be mistaken for
    knowing what was coded.
    """
    root, vdir = tmp_path / "lib", tmp_path / "validation"
    _write_cache(root)
    _write_sheet(vdir, window=None)
    ref = C.EpisodeRef(root=root, show_name=SHOW, stem=STEM,
                       duration_sec=1420.0,          # known, and no help
                       validation_dir=vdir)

    for key in ("hard_cuts_per_min", "transitions_per_min", "mean_shot_length",
                "median_shot_length", "shot_length_cv"):
        r = C.resolve(key, "hand:transitions", ref)
        assert r.status == C.WINDOW_UNKNOWN, (key, r.status, r.value)
        assert r.value is None


def test_a_caller_supplied_window_resolves_but_never_overrides_a_recorded_one(tmp_path):
    root, vdir = tmp_path / "lib", tmp_path / "validation"
    _write_cache(root)
    _write_sheet(vdir, window=None)

    supplied = C.EpisodeRef(root=root, show_name=SHOW, stem=STEM,
                            duration_sec=600.0, validation_dir=vdir,
                            coded_window=(0.0, 180.0))
    r = C.resolve("hard_cuts_per_min", "hand:transitions", supplied)
    assert r.status == C.MEASURED
    assert r.parameters["window_recorded_in"] == "supplied by the caller"

    # Now record a DIFFERENT window on disk; the recorded one must win.
    _write_sheet(vdir, window=(0.0, 90.0))
    r2 = C.resolve("hard_cuts_per_min", "hand:transitions", supplied)
    assert r2.status == C.MEASURED
    assert r2.parameters["coded_window_sec"] == [0.0, 90.0]
    assert r2.value != r.value


# ---------------------------------------------------------------------------
# Never average, never compare unlike quantities
# ---------------------------------------------------------------------------

def test_resolve_measure_reports_one_row_per_method_and_no_aggregate(ref):
    """An aggregate over two detectors is not a measurement of either, and this
    project published one such figure once (`LEARNINGS.md` shape 4)."""
    results = C.resolve_measure("hard_cuts_per_min", ref)
    assert len(results) == len(C.methods_for("hard_cuts_per_min"))
    assert len({r.method_key for r in results}) == len(results)
    assert not hasattr(C, "average_across_methods")
    assert not hasattr(C, "combined_value")


def test_the_two_scene_change_measures_are_not_comparable():
    """They carry the same field name in their two sources and are different
    quantities: one an unvalidated similarity threshold, one a human's label."""
    ok, why = C.comparable("scene_changes_per_min_detected",
                           "scene_changes_per_min_coded")
    assert ok is False
    assert "different quantities" in why


def test_one_measure_is_comparable_with_itself_across_methods():
    ok, _ = C.comparable("hard_cuts_per_min", "hard_cuts_per_min")
    assert ok is True


def test_hand_coding_only_measures_declare_themselves_and_offer_no_comparison():
    for key in ("transitions_per_min", "scene_changes_per_min_coded"):
        measure = C.get_measure(key)
        assert measure is not None
        assert measure.hand_coding_only
        assert not measure.has_automated_counterpart
        ok, _ = C.methods_comparable(key)
        assert ok is False


def test_the_comparability_split_is_read_from_validation_not_restated():
    """`CLAUDE.md` §2.5 names this module as the place that must READ
    manual_pacing_metrics' engine-comparable split."""
    import inspect

    from analyzer import validation

    assert hasattr(validation, "ENGINE_COMPARABLE_FIELDS")
    src = inspect.getsource(C.hand_field_is_engine_comparable)
    assert "ENGINE_COMPARABLE_FIELDS" in src

    # And it must agree with the split, measure by measure.
    for m in C.MEASURES:
        if m.hand is None or m.hand.kind != "transitions":
            continue
        expected = m.hand.field_key in validation.ENGINE_COMPARABLE_FIELDS
        ok, _ = C.methods_comparable(m.key)
        assert ok == (expected and m.automated is not None), m.key


def test_no_hand_coding_only_field_is_in_the_engine_comparable_set():
    from analyzer.validation import (ENGINE_COMPARABLE_FIELDS,
                                     HAND_CODING_ONLY_FIELDS)
    assert not (ENGINE_COMPARABLE_FIELDS & HAND_CODING_ONLY_FIELDS)


# ---------------------------------------------------------------------------
# The paired-reporting rule
# ---------------------------------------------------------------------------

def test_words_per_minute_cannot_be_reported_without_speech_density():
    """`CLAUDE.md` §2.2. Expressing this rule is the reason speech is the
    second worked example — a model that cannot say "report these together"
    is not expressive enough (`MEASUREMENT_MODEL.md` §4.3)."""
    companions = C.companions("words_per_minute")
    assert [c.key for c in companions] == ["speech_density"]


def test_the_pairing_is_declared_from_both_sides():
    """A one-way declaration lets a screen show density alone and think it has
    obeyed the rule, or show WPM through the other measure's page."""
    assert "speech_density" in C.get_measure("words_per_minute").reported_with
    assert "words_per_minute" in C.get_measure("speech_density").reported_with


def test_every_reported_with_names_a_real_measure():
    for m in C.MEASURES:
        for key in m.reported_with:
            assert C.get_measure(key) is not None, f"{m.key} -> {key}"


# ---------------------------------------------------------------------------
# Engine isolation
# ---------------------------------------------------------------------------

def test_the_model_imports_no_gui_framework():
    """`CLAUDE.md` §2.4. tests/test_engine_isolation.py enumerates analyzer/;
    this is the same assertion stated where the new module lives."""
    src = Path(C.__file__).read_text(encoding="utf-8")
    for framework in ("PySide6", "PyQt", "tkinter", "import ui."):
        assert framework not in src, framework
