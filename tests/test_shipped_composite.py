"""
The shipped sensory-load composite, expressed as a recipe.

`DECISIONS.md`: **expressing it is not changing it.** The public index is built
on this composite, so the binding requirement is that
`recipes.shipped_composite(config)` reproduces
`metrics_sensory.compute_sensory_load` EXACTLY — same rounding, same clamping,
same audio redistribution — for every episode.

These tests compare the two implementations directly rather than asserting the
recipe has the right shape. A recipe that looks correct and scores differently
would be the worst possible outcome here: every published score would silently
acquire a second, disagreeing definition.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from analyzer import constructs as C
from analyzer import measurements as reg
from analyzer import recipes as R
from analyzer.metrics_sensory import compute_sensory_load, effective_weights
from analyzer.schema import EpisodeResult

SHOW = "Composite Show"


@pytest.fixture
def config():
    """The real shipped config, so the test is about the shipped composite."""
    root = Path(__file__).resolve().parent.parent
    cfg = json.loads((root / "config.json").read_text(encoding="utf-8"))
    return reg.normalize_config(cfg)


# A spread of episodes chosen to exercise the ends of every reference range,
# including values ABOVE a ceiling (which normalization clamps) and a silent
# episode (which triggers redistribution).
EPISODES = [
    # (stem, cuts, saturation, contrast, motion, flashing, rms, audio?)
    ("quiet",      2.0,  0.10, 0.05, 0.01,  0.0, 0.02, True),
    ("typical",   12.0,  0.40, 0.20, 0.10,  5.0, 0.15, True),
    ("busy",      31.5,  0.72, 0.31, 0.28, 22.0, 0.30, True),
    ("over_ceil", 90.0,  0.99, 0.60, 0.90, 80.0, 0.90, True),
    ("zeroes",     0.0,  0.00, 0.00, 0.00,  0.0, 0.00, True),
    ("silent",    12.0,  0.40, 0.20, 0.10,  5.0, 0.00, False),
]


def _write(root: Path, spec, config) -> EpisodeResult:
    stem, cuts, sat, con, mot, flash, rms, audio = spec
    result = EpisodeResult(file=f"{stem}.mp4", duration_sec=600.0,
                           config=json.loads(json.dumps(config)))
    m = result.metrics
    m.scene_pacing.cuts_per_min = cuts
    m.color_saturation.mean = sat
    m.color_saturation.contrast_mean = con
    m.motion.mean = mot
    m.flashing.luminance_delta_events_per_min = flash
    m.audio.available = audio
    m.audio.rms_mean = rms
    path = root / ".analysis" / SHOW / f"{stem}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict()), encoding="utf-8")
    return result


# ---------------------------------------------------------------------------
# The binding requirement
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("spec", EPISODES, ids=[e[0] for e in EPISODES])
def test_the_recipe_reproduces_the_engine_exactly(tmp_path, config, spec):
    root = tmp_path / "lib"
    result = _write(root, spec, config)
    m = result.metrics

    engine = compute_sensory_load(m.scene_pacing, m.color_saturation, m.motion,
                                  m.flashing, m.audio, config)
    ev = R.evaluate(
        R.shipped_composite(config),
        C.EpisodeRef(root=root, show_name=SHOW, stem=spec[0],
                     duration_sec=600.0, validation_dir=tmp_path / "validation"),
        config)

    assert ev.score == engine.score, (
        f"{spec[0]}: recipe {ev.score} vs engine {engine.score}")


@pytest.mark.parametrize("spec", EPISODES, ids=[e[0] for e in EPISODES])
def test_the_recipe_uses_the_same_effective_weights_as_the_engine(
        tmp_path, config, spec):
    """`effective_weights()` is the existing single answer to "the nominal
    weights are not what the components contributed". The recipe must
    reproduce it, not reimplement it — especially in the no-audio case."""
    root = tmp_path / "lib"
    result = _write(root, spec, config)
    audio_available = result.metrics.audio.available

    ev = R.evaluate(
        R.shipped_composite(config),
        C.EpisodeRef(root=root, show_name=SHOW, stem=spec[0],
                     duration_sec=600.0, validation_dir=tmp_path / "validation"),
        config)

    expected = effective_weights(config, audio_available)
    weight_key = {"hard_cuts_per_min": "pacing", "saturation_mean": "saturation",
                  "contrast_mean": "color_contrast", "motion_mean": "motion",
                  "flashing_events_per_min": "flashing",
                  "audio_rms_mean": "audio"}
    for measure_key, got in ev.effective_weights().items():
        assert got == pytest.approx(expected[weight_key[measure_key]]), measure_key


def test_a_silent_episode_redistributes_rather_than_scoring_audio_as_zero(
        tmp_path, config):
    """Scoring a missing audio track as 0.0 would drag the composite down by
    audio's whole weight. The engine redistributes; so must the recipe."""
    root = tmp_path / "lib"
    _write(root, ("silent", 12.0, 0.40, 0.20, 0.10, 5.0, 0.00, False), config)
    _write(root, ("typical", 12.0, 0.40, 0.20, 0.10, 5.0, 0.15, True), config)

    def score(stem):
        return R.evaluate(
            R.shipped_composite(config),
            C.EpisodeRef(root=root, show_name=SHOW, stem=stem,
                         duration_sec=600.0,
                         validation_dir=tmp_path / "validation"),
            config)

    silent, typical = score("silent"), score("typical")
    assert silent.status == R.PARTIAL
    assert typical.status == R.COMPLETE
    # Both still sit on the full 0–1 scale, which is what redistribution buys.
    assert silent.scale == pytest.approx(1.0)
    assert typical.scale == pytest.approx(1.0)
    audio_part = next(p for p in silent.parts
                      if p.binding.measure_key == "audio_rms_mean")
    assert not audio_part.ok
    assert audio_part.effective_weight == 0.0


@pytest.mark.parametrize("spec", EPISODES, ids=[e[0] for e in EPISODES])
def test_the_breakdown_adds_up_to_the_headline(tmp_path, config, spec):
    """`LEARNINGS.md` shape 1, the defect that put a 0.2265 breakdown under a
    0.2832 headline on a silent episode."""
    root = tmp_path / "lib"
    _write(root, spec, config)
    ev = R.evaluate(
        R.shipped_composite(config),
        C.EpisodeRef(root=root, show_name=SHOW, stem=spec[0],
                     duration_sec=600.0, validation_dir=tmp_path / "validation"),
        config)
    if spec[0] == "over_ceil":
        # Every component clamps to 1.0 here, so the recipe clamps the total.
        assert ev.score == 1.0
        return
    assert ev.score == pytest.approx(ev.breakdown_total())


# ---------------------------------------------------------------------------
# It is built FROM the config, not restated
# ---------------------------------------------------------------------------

def test_the_recipe_covers_exactly_the_weights_the_config_declares(config):
    """A seventh component added to `sensory_load_weights` must not leave the
    recipe silently scoring six. This is the structural half of shape 3."""
    recipe = R.shipped_composite(config)
    weight_key = {"hard_cuts_per_min": "pacing", "saturation_mean": "saturation",
                  "contrast_mean": "color_contrast", "motion_mean": "motion",
                  "flashing_events_per_min": "flashing",
                  "audio_rms_mean": "audio"}
    covered = {weight_key[b.measure_key] for b in recipe.bindings}
    assert covered == set(config["sensory_load_weights"])


def test_the_weights_and_ceilings_come_from_the_config(config):
    """Retuning a ceiling in config.json must move the recipe with no edit to
    recipes.py — the ceilings were retuned once already and every score moved."""
    changed = json.loads(json.dumps(config))
    changed["normalization_reference_ranges"]["cuts_per_min"]["max"] = 60.0
    changed["sensory_load_weights"]["pacing"] = 0.40

    recipe = R.shipped_composite(changed)
    pacing = recipe.binding("hard_cuts_per_min")
    assert pacing.range_max == 60.0
    assert pacing.weight == 0.40


def test_retuning_a_ceiling_is_a_visible_version_change(config):
    """The point of expressing the composite. The 2026-08-14 retune moved every
    score in the project silently; under a recipe it changes the content hash,
    so two numbers computed either side are no longer citable as the same
    operationalization."""
    before = R.shipped_composite(config).content_hash()
    changed = json.loads(json.dumps(config))
    changed["normalization_reference_ranges"]["motion_mean"]["max"] = 1.0
    assert R.shipped_composite(changed).content_hash() != before


def test_the_recipe_follows_the_configs_selected_detector(config):
    changed = json.loads(json.dumps(config))
    changed["measurements"]["transitions"]["tool"] = "transnetv2"
    recipe = R.shipped_composite(changed)
    assert recipe.binding("hard_cuts_per_min").method_key == \
        "auto:transitions:transnetv2"


# ---------------------------------------------------------------------------
# It is locked, and it says what it is not
# ---------------------------------------------------------------------------

def test_the_shipped_composite_cannot_be_written_to_the_library_at_all(
        tmp_path, config):
    """Refused on the LOCK, not on there already being a file.

    This asserted the opposite until 2026-08-16 — the first save was allowed,
    because the guard also required an existing path, and the composite is
    GENERATED so its path is None. That let the one recipe the guard exists for
    walk straight through it. A stored copy is worse than pointless: this
    recipe is built from the weights and ceilings in force, so a file of it is
    a snapshot that stops following them, and the 2026-08-14 ceiling retune
    would have left it describing scores nothing computes any more.

    Nothing in the interface ever did this. It was found by trying it while
    driving canvas authoring, which is the only reason it is on record.
    """
    recipe = R.shipped_composite(config)
    assert recipe.locked is True
    with pytest.raises(PermissionError):
        R.save_recipe(recipe, tmp_path / "lib")
    assert not (tmp_path / "lib" / ".analysis" / "recipes").exists()
    with pytest.raises(PermissionError):
        R.delete_recipe(recipe)


def test_an_imported_recipe_arrives_unlocked(tmp_path, config):
    """A lock is a claim about THIS install — that results here depend on it.

    Without this, exporting the shipped composite and importing it produced a
    recipe that could never be saved, which is the one thing an import has to
    be able to do.
    """
    payload = R.export_recipe(R.shipped_composite(config))
    imported, _gaps = R.import_recipe(payload, new_name="Someone else's")
    assert imported.locked is False
    assert R.save_recipe(imported, tmp_path / "lib").exists()


def test_duplicating_it_is_the_route_to_exploring_alternatives(tmp_path, config):
    copy = R.duplicate_recipe(R.shipped_composite(config), "My composite")
    assert copy.locked is False
    copy.binding("motion_mean").weight = 0.10
    assert R.save_recipe(copy, tmp_path / "lib").exists()


def test_it_states_that_its_defaults_are_underived(config):
    """`ARCHITECTURE.md` §8.1a. The one thing that must travel with this recipe
    everywhere it goes: naming a construct does not derive a weight."""
    recipe = R.shipped_composite(config)
    assert "no recorded derivation" in recipe.notes.lower()

    construct = C.get_construct("sensory_load")
    assert construct is not None
    grounding = construct.grounding.lower()
    assert "neither says how to combine them" in grounding
    assert "does not" in grounding


def test_it_carries_the_unvalidated_flashing_flag(tmp_path, config):
    """`CLAUDE.md` §2.2: flagged wherever the numbers appear. A composite is
    exactly where an ungraded component stops being separately visible."""
    root = tmp_path / "lib"
    _write(root, EPISODES[1], config)
    ev = R.evaluate(
        R.shipped_composite(config),
        C.EpisodeRef(root=root, show_name=SHOW, stem="typical",
                     duration_sec=600.0, validation_dir=tmp_path / "validation"),
        config)
    assert any("unvalidated" in f.lower() for f in ev.flags)


def test_it_reports_to_the_same_precision_the_engine_publishes(config):
    """4 decimals, clamped — both are part of the published number, so both are
    inside the content hash rather than being display preferences."""
    recipe = R.shipped_composite(config)
    assert recipe.score_decimals == 4
    assert recipe.clamp_score is True
    assert recipe.canonical()["score_decimals"] == 4
    assert recipe.canonical()["clamp_score"] is True
