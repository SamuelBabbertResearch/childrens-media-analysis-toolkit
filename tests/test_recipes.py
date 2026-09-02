"""
Recipes: saved, versioned, citable operationalizations.

`MEASUREMENT_MODEL.md` §4.2 states its own verification and these follow it
literally: **read the written file, not the dialog that wrote it**, and a
recipe saved in one place, reopened in another, must still resolve to the same
numbers. So the round-trip tests go through the real disk and re-read JSON
rather than comparing two objects in memory.

The decisions being held here (`DECISIONS.md`):

  * a recipe PINS its parameters — and the pin is enforced, not just stored;
  * renaming a recipe is not a new version;
  * a citation is a friendly version plus a content hash;
  * an import reports what it cannot resolve and never substitutes a default.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from analyzer import constructs as C
from analyzer import measurements as reg
from analyzer import recipes as R
from analyzer.schema import EpisodeResult


SHOW, STEM = "Test Show", "S01E01 Something"


def _write_cache(root: Path, *, threshold=27.0, cuts=12.0) -> Path:
    cfg = reg.normalize_config({"cut_detection_threshold": threshold,
                                "sample_fps": 2.0})
    result = EpisodeResult(file=f"{STEM}.mp4", duration_sec=600.0, config=cfg)
    result.metrics.scene_pacing.cuts_per_min = cuts
    result.metrics.shot_length.mean_sec = 4.8
    result.metrics.shot_length.median_sec = 4.2
    result.metrics.scene_pacing.shot_length_cv = 0.5
    result.metrics.speech.words_per_minute = 120.0
    result.metrics.speech.speech_density = 0.5
    result.metrics.speech.total_words = 900
    path = root / ".analysis" / SHOW / f"{STEM}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict()), encoding="utf-8")
    return path


@pytest.fixture
def config():
    return reg.normalize_config({"cut_detection_threshold": 27.0,
                                 "sample_fps": 2.0})


@pytest.fixture
def pacing_recipe(config):
    """Two automated pacing measures, min-max normalised and weighted.

    Built with fully-formed bindings so the v1 content hash describes the
    finished operationalization rather than a half-configured one.
    """
    tool = "auto:transitions:pyscenedetect_content"
    return R.new_recipe(
        "Pacing — conservative", "pacing", config, reason="Worked example",
        measures=[
            R.MeasureBinding(
                "hard_cuts_per_min", tool,
                parameters=R.pin_parameters("hard_cuts_per_min", tool, config),
                transform=R.TRANSFORM_MINMAX, range_max=45.0, weight=0.6),
            R.MeasureBinding(
                "shot_length_cv", tool,
                parameters=R.pin_parameters("shot_length_cv", tool, config),
                transform=R.TRANSFORM_MINMAX, range_max=2.0, weight=0.4),
        ])


@pytest.fixture
def ref(tmp_path):
    _write_cache(tmp_path / "lib")
    return C.EpisodeRef(root=tmp_path / "lib", show_name=SHOW, stem=STEM,
                        duration_sec=600.0,
                        validation_dir=tmp_path / "validation")


# ---------------------------------------------------------------------------
# Save / load — verified by reading the file
# ---------------------------------------------------------------------------

def test_a_saved_recipe_lands_in_the_library_not_the_app_folder(tmp_path,
                                                                pacing_recipe):
    root = tmp_path / "lib"
    path = R.save_recipe(pacing_recipe, root)
    assert path.parent == root / ".analysis" / "recipes"
    assert path.exists()


def test_the_written_file_carries_every_parameter_inspectably(tmp_path,
                                                              pacing_recipe):
    """A recipe is inspectable or it is not a recipe (`CLAUDE.md` §2.5). The
    file itself has to show the parameters — not a name standing in for them."""
    path = R.save_recipe(pacing_recipe, tmp_path / "lib")
    written = json.loads(path.read_text(encoding="utf-8"))

    assert written["construct"] == "pacing"
    assert written["version"] == 1
    assert written["content_hash"]
    binding = next(b for b in written["bindings"]
                   if b["measure"] == "hard_cuts_per_min")
    assert binding["method"] == "auto:transitions:pyscenedetect_content"
    assert binding["parameters"]["threshold"] == 27.0      # PINNED, in the file
    assert binding["transform"] == "minmax"
    assert binding["range_max"] == 45.0
    assert binding["weight"] == 0.6
    assert binding["missing"] == "refuse"


def test_a_recipe_saved_in_one_library_reopens_in_another_with_the_same_numbers(
        tmp_path, pacing_recipe, config):
    """§4.2's own done-criterion, taken literally: saved here, reopened there,
    still resolves to the same numbers."""
    here, there = tmp_path / "a", tmp_path / "b"
    _write_cache(here / "lib")
    _write_cache(there / "lib")

    path = R.save_recipe(pacing_recipe, here / "lib")
    first = R.evaluate(R.load_recipe(path),
                       C.EpisodeRef(root=here / "lib", show_name=SHOW,
                                    stem=STEM, duration_sec=600.0,
                                    validation_dir=here / "validation"),
                       config)

    # Move the file, as copying a study to another machine would.
    moved = R.load_recipe(path)
    moved.path = None
    R.save_recipe(moved, there / "lib")
    second = R.evaluate(R.load_recipe(moved.path),
                        C.EpisodeRef(root=there / "lib", show_name=SHOW,
                                     stem=STEM, duration_sec=600.0,
                                     validation_dir=there / "validation"),
                        config)

    assert first.status == R.COMPLETE
    assert second.score == first.score
    assert second.content_hash == first.content_hash


def test_a_recipe_first_saved_with_no_root_rehomes_into_the_library(
        tmp_path, pacing_recipe, monkeypatch):
    """The exact defect `pipeline_graph.save_doc` had to grow a rule for: saved
    before a library root was known, then written forever to a folder the
    loader never reads. It saved fine and reloaded as nothing."""
    monkeypatch.setattr(R, "_base_dir", lambda: tmp_path / "app")

    fallback = R.save_recipe(pacing_recipe, None)
    assert fallback.parent == tmp_path / "app" / "recipes"

    root = tmp_path / "lib"
    rehomed = R.save_recipe(pacing_recipe, root)
    assert rehomed.parent == root / ".analysis" / "recipes"
    assert not fallback.exists(), "the old file must be MOVED, not copied"
    assert [r.id for r in R.list_recipes(root)] == [pacing_recipe.id]


def test_listing_skips_an_unreadable_file_instead_of_failing(tmp_path,
                                                             pacing_recipe):
    root = tmp_path / "lib"
    R.save_recipe(pacing_recipe, root)
    (root / ".analysis" / "recipes" / "broken.json").write_text(
        "{not json", encoding="utf-8")
    assert len(R.list_recipes(root)) == 1


def test_duplicating_gives_a_fresh_id_and_does_not_inherit_the_history(
        tmp_path, pacing_recipe):
    R.bump_version(pacing_recipe, "widened the pacing ceiling")
    copy = R.duplicate_recipe(pacing_recipe)

    assert copy.id != pacing_recipe.id
    assert copy.path is None
    assert copy.version == 1
    assert len(copy.history) == 1
    assert pacing_recipe.citation() in copy.history[0].reason
    # Same operationalization, so the same content hash — that is the point of
    # hashing content rather than identity.
    assert copy.content_hash() == pacing_recipe.content_hash()


def test_a_locked_recipe_refuses_to_be_overwritten_or_deleted(tmp_path,
                                                              pacing_recipe):
    """The shipped composite's numbers are what every published score was
    computed under."""
    root = tmp_path / "lib"
    R.save_recipe(pacing_recipe, root)
    pacing_recipe.locked = True

    with pytest.raises(PermissionError):
        R.save_recipe(pacing_recipe, root)
    with pytest.raises(PermissionError):
        R.delete_recipe(pacing_recipe)

    # Duplicating is the sanctioned route, and the copy is not locked.
    copy = R.duplicate_recipe(pacing_recipe)
    assert copy.locked is False
    assert R.save_recipe(copy, root).exists()


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

def test_renaming_a_recipe_is_not_a_new_version(pacing_recipe):
    """`MEASUREMENT_MODEL.md` §4.4, held by what content_hash() excludes
    rather than by anyone remembering the rule."""
    before = pacing_recipe.content_hash()
    pacing_recipe.name = "Pacing — renamed entirely"
    pacing_recipe.notes = "and re-annotated"
    assert pacing_recipe.content_hash() == before
    assert R.bump_version(pacing_recipe, "renamed it") is None
    assert pacing_recipe.version == 1


def test_reordering_the_same_bindings_is_not_a_new_version(pacing_recipe):
    before = pacing_recipe.content_hash()
    pacing_recipe.bindings.reverse()
    assert pacing_recipe.content_hash() == before


def test_changing_a_pinned_parameter_is_a_new_version_with_a_reason(
        pacing_recipe):
    import copy as copymod
    previous = copymod.deepcopy(pacing_recipe)

    pacing_recipe.bindings[0].parameters["threshold"] = 30.0
    record = R.bump_version(pacing_recipe, "27 over-fired on snowfall",
                            previous=previous)

    assert record is not None
    assert pacing_recipe.version == 2
    assert record.reason == "27 over-fired on snowfall"
    assert any("threshold: 27.0 → 30.0" in c for c in record.changes)
    assert record.content_hash == pacing_recipe.content_hash()


def test_a_version_cannot_be_recorded_without_a_reason(pacing_recipe):
    """What changed can be derived; why it changed cannot, and it is the half
    that is paper material."""
    pacing_recipe.bindings[0].weight = 0.9
    with pytest.raises(ValueError):
        R.bump_version(pacing_recipe, "   ")


def test_the_version_history_survives_a_save_and_reload(tmp_path,
                                                        pacing_recipe):
    """Versioning lives in the data model, not the interface (`CLAUDE.md`
    §2.5). A version visible only on screen is a label."""
    pacing_recipe.bindings[0].range_max = 60.0
    R.bump_version(pacing_recipe, "matched the published ceiling")
    path = R.save_recipe(pacing_recipe, tmp_path / "lib")

    written = json.loads(path.read_text(encoding="utf-8"))
    assert [h["version"] for h in written["history"]] == [1, 2]
    assert written["history"][1]["reason"] == "matched the published ceiling"

    reloaded = R.load_recipe(path)
    assert reloaded.version == 2
    assert reloaded.history[1].reason == "matched the published ceiling"


def test_a_citation_carries_both_the_friendly_version_and_the_hash(
        pacing_recipe):
    citation = pacing_recipe.citation()
    assert "v1" in citation
    assert pacing_recipe.content_hash() in citation
    assert pacing_recipe.name in citation


def test_two_installs_holding_the_same_operationalization_agree_on_the_hash(
        config):
    a = R.new_recipe("Mine", "pacing", config,
                     measures=[("hard_cuts_per_min",
                                "auto:transitions:pyscenedetect_content")])
    b = R.new_recipe("Theirs", "pacing", config,
                     measures=[("hard_cuts_per_min",
                                "auto:transitions:pyscenedetect_content")])
    assert a.id != b.id
    assert a.content_hash() == b.content_hash()


# ---------------------------------------------------------------------------
# Pinning is enforced, not merely stored
# ---------------------------------------------------------------------------

def test_a_pinned_parameter_is_read_from_the_registry_not_guessed(config):
    config["measurements"]["transitions"]["params"]["threshold"] = 31.0
    recipe = R.new_recipe("x", "pacing", config,
                          measures=[("hard_cuts_per_min",
                                     "auto:transitions:pyscenedetect_content")])
    assert recipe.bindings[0].parameters["threshold"] == 31.0


def test_pinning_a_method_the_config_does_not_select_uses_that_methods_defaults(
        config):
    """A threshold of 27 means something different to ContentDetector than to
    TransNetV2; copying one tool's numbers onto another pins a value that never
    applied."""
    recipe = R.new_recipe("x", "pacing", config,
                          measures=[("hard_cuts_per_min",
                                     "auto:transitions:transnetv2")])
    assert recipe.bindings[0].parameters["threshold"] == 0.5


def test_a_result_measured_at_a_different_threshold_is_refused(tmp_path,
                                                               pacing_recipe,
                                                               config):
    """THE thing that makes pinning real. The cached number is a real number;
    it is not what this recipe operationalizes."""
    root = tmp_path / "lib"
    _write_cache(root, threshold=30.0, cuts=9.0)     # recipe pins 27.0
    ref = C.EpisodeRef(root=root, show_name=SHOW, stem=STEM, duration_sec=600.0,
                       validation_dir=tmp_path / "validation")

    ev = R.evaluate(pacing_recipe, ref, config)
    assert ev.status == R.REFUSED
    assert ev.score is None
    part = next(p for p in ev.parts if p.binding.measure_key == "hard_cuts_per_min")
    assert part.status == R.PARAMS_DIFFER
    assert "recipe pins 27.0" in part.detail
    assert "measured at 30.0" in part.detail
    assert part.raw == 9.0, "the real number is still reported, just not scored"


def test_divergences_report_a_recipe_pinned_before_a_settings_change(
        pacing_recipe, config):
    """The accepted cost of pinning, as a function. A divergence is not an
    error — it means the recipe still describes what it always described."""
    assert R.divergences(pacing_recipe, config) == []

    changed = reg.normalize_config(dict(config))
    changed["measurements"]["transitions"]["params"]["threshold"] = 33.0

    found = R.divergences(pacing_recipe, changed)
    assert len(found) == 2                    # both bindings use this tool
    assert found[0].pinned == 27.0 and found[0].live == 33.0
    assert "pins threshold = 27.0" in found[0].describe()


def test_divergences_report_a_swapped_tool(pacing_recipe, config):
    changed = reg.normalize_config(dict(config))
    changed["measurements"]["transitions"]["tool"] = "transnetv2"
    found = R.divergences(pacing_recipe, changed)
    assert found and found[0].parameter == "tool"
    assert "TransNetV2" in found[0].describe()


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def test_a_complete_evaluation_reconciles_with_its_own_breakdown(ref,
                                                                 pacing_recipe,
                                                                 config):
    """`LEARNINGS.md` shape 1: does the breakdown add up to the headline? On a
    silent episode the old composite's contributions summed 0.057 short of the
    score printed above them."""
    ev = R.evaluate(pacing_recipe, ref, config)
    assert ev.status == R.COMPLETE
    assert ev.score == pytest.approx(ev.breakdown_total())
    assert ev.scale == pytest.approx(1.0)

    # And the arithmetic is the one the file describes: 12/45 * 0.6 + 0.5/2 * 0.4
    assert ev.score == pytest.approx((12.0 / 45.0) * 0.6 + (0.5 / 2.0) * 0.4)


def test_the_evaluation_reports_effective_weights_not_nominal_ones(ref, config):
    """When a part is missing under a redistribute policy the weights that
    produced the score are not the ones in the file. Showing the nominal pair
    is the defect that made a breakdown 0.057 short."""
    recipe = R.new_recipe(
        "partial", "pacing", config,
        measures=[("hard_cuts_per_min", "auto:transitions:pyscenedetect_content"),
                  ("dissolves_per_min", "auto:dissolves:cmat_plateau")])
    for b, w in zip(recipe.bindings, [0.6, 0.4]):
        b.transform, b.range_min, b.range_max, b.weight = R.TRANSFORM_MINMAX, 0.0, 45.0, w
    recipe.binding("dissolves_per_min").missing = R.MISSING_REDISTRIBUTE

    ev = R.evaluate(recipe, ref, config)          # dissolves ship disabled
    assert ev.status == R.PARTIAL
    weights = ev.effective_weights()
    assert weights["hard_cuts_per_min"] == pytest.approx(1.0)
    assert weights["hard_cuts_per_min"] != 0.6
    assert ev.score == pytest.approx(ev.breakdown_total())
    assert ev.scale == pytest.approx(1.0)


def test_omitting_a_part_shrinks_the_scale_and_says_so(ref, config):
    """An omitted part without redistribution leaves the score on a smaller
    scale. That is defensible only if it is stated."""
    recipe = R.new_recipe(
        "omitting", "pacing", config,
        measures=[("hard_cuts_per_min", "auto:transitions:pyscenedetect_content"),
                  ("dissolves_per_min", "auto:dissolves:cmat_plateau")])
    for b, w in zip(recipe.bindings, [0.6, 0.4]):
        b.transform, b.range_min, b.range_max, b.weight = R.TRANSFORM_MINMAX, 0.0, 45.0, w
    recipe.binding("dissolves_per_min").missing = R.MISSING_OMIT

    ev = R.evaluate(recipe, ref, config)
    assert ev.status == R.PARTIAL
    assert ev.scale == pytest.approx(0.6)
    assert "scale of 0.6" in ev.detail
    assert ev.score == pytest.approx(ev.breakdown_total())


def test_the_default_missing_policy_refuses_rather_than_scoring_a_gap(ref,
                                                                      config):
    """A composite missing one of its parts is not that composite."""
    recipe = R.new_recipe(
        "strict", "pacing", config,
        measures=[("hard_cuts_per_min", "auto:transitions:pyscenedetect_content"),
                  ("dissolves_per_min", "auto:dissolves:cmat_plateau")])
    for b in recipe.bindings:
        b.transform, b.range_max, b.weight = R.TRANSFORM_MINMAX, 45.0, 0.5
    assert recipe.binding("dissolves_per_min").missing == R.MISSING_REFUSE

    ev = R.evaluate(recipe, ref, config)
    assert ev.status == R.REFUSED
    assert ev.score is None
    assert "Dissolves per minute" in ev.detail


def test_a_refused_part_still_appears_in_the_breakdown(ref, config):
    """A composite that silently drops what it could not measure is how
    'five failed' got reported for a show where nothing had failed."""
    recipe = R.new_recipe(
        "strict", "pacing", config,
        measures=[("hard_cuts_per_min", "auto:transitions:pyscenedetect_content"),
                  ("dissolves_per_min", "auto:dissolves:cmat_plateau")])
    ev = R.evaluate(recipe, ref, config)
    assert {p.binding.measure_key for p in ev.parts} == {
        "hard_cuts_per_min", "dissolves_per_min"}
    assert any(not p.ok and p.detail for p in ev.parts)


def test_an_evaluation_carries_the_unvalidated_flags_of_its_methods(ref, config):
    """`CLAUDE.md` §2.2: flagged wherever the numbers appear. A composite is
    exactly where an ungraded component stops being visible."""
    recipe = R.new_recipe(
        "flagged", "pacing", config,
        measures=[("scene_changes_per_min_detected",
                   "auto:scene_relation:frame_similarity")])
    recipe.bindings[0].weight = 1.0
    ev = R.evaluate(recipe, ref, config)
    assert any("unvalidated" in f for f in ev.flags)


def test_an_evaluation_names_the_exact_recipe_version_that_produced_it(
        ref, pacing_recipe, config):
    """Tying a result back to the configuration that produced it is the whole
    point of citation support."""
    ev = R.evaluate(pacing_recipe, ref, config)
    assert ev.content_hash == pacing_recipe.content_hash()
    assert ev.version == pacing_recipe.version
    assert ev.citation == pacing_recipe.citation()


def test_hand_coding_can_be_a_recipes_method(tmp_path, config):
    """Hand coding is a method, not a validation step — a recipe must be able
    to operationalize a construct entirely by human coding."""
    import csv
    root, vdir = tmp_path / "lib", tmp_path / "validation"
    _write_cache(root)
    vdir.mkdir(parents=True)
    with (vdir / f"{STEM}_manual.csv").open("w", newline="",
                                            encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["timestamp_hms", "timestamp_sec", "type",
                    "scene_relation", "notes"])
        for sec in (10, 20, 40, 55, 80, 95):
            w.writerow([f"00:{sec:02d}", "", "hard_cut", "within", ""])
    (vdir / f"{STEM}__handcoded_2026-08-16.json").write_text(
        json.dumps({"transitions": {"window": [0.0, 180.0]}}), encoding="utf-8")

    recipe = R.new_recipe("Hand-coded pacing", "pacing", config,
                          measures=[("hard_cuts_per_min", "hand:transitions")])
    recipe.bindings[0].weight = 1.0
    assert recipe.bindings[0].parameters == {}, "hand coding has no tunables"

    ev = R.evaluate(recipe, C.EpisodeRef(root=root, show_name=SHOW, stem=STEM,
                                         duration_sec=600.0,
                                         validation_dir=vdir), config)
    assert ev.status == R.COMPLETE
    assert ev.score == pytest.approx(2.0)          # 6 cuts over 3 minutes
    assert ev.flags == (), "hand coding is not flagged as unvalidated"


# ---------------------------------------------------------------------------
# Export / import
# ---------------------------------------------------------------------------

def test_an_export_is_self_describing(pacing_recipe):
    """It must be readable on a machine whose registry differs."""
    payload = R.export_recipe(pacing_recipe)
    describes = payload["describes"]
    assert describes["construct"]["name"] == "Pacing"
    assert describes["construct"]["definition"]
    binding = next(b for b in describes["bindings"]
                   if b["measure"] == "hard_cuts_per_min")
    assert binding["measure_name"] == "Hard cuts per minute"
    assert binding["unit"] == "cuts/min"
    assert binding["method_label"] == "PySceneDetect — ContentDetector"
    assert binding["method_status"] == reg.VALIDATED


def test_an_export_round_trips_through_json_with_the_same_hash(pacing_recipe):
    payload = json.loads(json.dumps(R.export_recipe(pacing_recipe)))
    imported, gaps = R.import_recipe(payload)
    assert gaps == []
    assert imported.content_hash() == pacing_recipe.content_hash()
    assert imported.id != pacing_recipe.id, "an import is a new object here"


def test_importing_a_recipe_naming_an_absent_detector_reports_a_named_gap(
        pacing_recipe):
    """A recipe referencing a detector this install does not have is a real and
    expected case. It must produce a visible gap, never a substitution."""
    payload = R.export_recipe(pacing_recipe)
    payload["bindings"][0]["method"] = "auto:transitions:some_other_detector"
    payload["describes"]["bindings"][0]["method"] = "auto:transitions:some_other_detector"
    payload["describes"]["bindings"][0]["method_label"] = "Somebody Else's Detector"

    imported, gaps = R.import_recipe(payload)
    assert len(gaps) == 1
    assert gaps[0].kind == "method"
    assert gaps[0].described_as == "Somebody Else's Detector"
    assert "NOT substituted" in gaps[0].detail

    # The binding is kept, not silently repaired or dropped.
    assert imported.bindings[0].method_key == "auto:transitions:some_other_detector"


def test_an_unresolvable_binding_is_never_quietly_swapped_for_a_default(
        pacing_recipe, ref, config):
    payload = R.export_recipe(pacing_recipe)
    payload["bindings"][0]["method"] = "auto:transitions:some_other_detector"
    imported, _gaps = R.import_recipe(payload)

    with pytest.raises(KeyError):
        C.resolve("hard_cuts_per_min", "auto:transitions:some_other_detector",
                  ref, config)
    assert imported.bindings[0].method_key != \
        "auto:transitions:pyscenedetect_content"


def test_importing_a_recipe_for_an_unknown_construct_reports_that_too(
        pacing_recipe):
    payload = R.export_recipe(pacing_recipe)
    payload["construct"] = "narrative_complexity"
    payload["describes"]["construct"] = {"key": "narrative_complexity",
                                         "name": "Narrative complexity"}
    _imported, gaps = R.import_recipe(payload)
    assert any(g.kind == "construct" and g.described_as == "Narrative complexity"
               for g in gaps)


# ---------------------------------------------------------------------------
# Engine isolation
# ---------------------------------------------------------------------------

def test_recipes_import_no_gui_framework():
    src = Path(R.__file__).read_text(encoding="utf-8")
    for framework in ("PySide6", "PyQt", "tkinter", "import ui."):
        assert framework not in src, framework


def test_recipe_storage_follows_the_pipeline_document_conventions():
    """`MEASUREMENT_MODEL.md` §3: follow that file's conventions rather than
    invent new ones. Asserted on behaviour, not on source text — a source-text
    test passed here once while the import it asserted on was broken."""
    import inspect
    src = inspect.getsource(R.save_recipe)
    assert ".tmp" in src and "replace(" in src, "atomic write"
    assert "unlink" in src, "move, not copy, when re-homing"
    assert R.recipes_dir(Path("/lib")).name == "recipes"
    assert R.recipes_dir(Path("/lib")).parent.name == ".analysis"
