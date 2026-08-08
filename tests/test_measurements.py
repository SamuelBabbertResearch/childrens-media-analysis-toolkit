"""
Measurement registry — config migration, fingerprinting, and cache staleness.

The core invariant these tests protect: SCORING settings (weights, normalization
ceilings) must never invalidate cached analysis, and MEASUREMENT settings
(detector, thresholds, sample rates) always must. Getting that backwards either
forces needless re-analysis of a whole corpus or — much worse — silently mixes
detections made under different settings inside one comparison.
"""

from __future__ import annotations
import copy

import pytest

from analyzer import measurements as M
from analyzer.cache import is_stale, load_cached, save_cache
from analyzer.config_loader import load_config
from analyzer.schema import EpisodeResult


@pytest.fixture
def cfg():
    return load_config()


# ---------------------------------------------------------------------------
# Config normalization / legacy migration
# ---------------------------------------------------------------------------

def test_load_config_builds_measurements_block(cfg):
    assert "measurements" in cfg
    for spec in M.MEASUREMENTS:
        assert spec.key in cfg["measurements"]


def test_legacy_flat_keys_seed_the_block():
    """A config with only old-style flat keys migrates without losing values."""
    legacy = {
        "cut_detection_threshold": 31.5,
        "sample_fps": 4,
        "flashing_luminance_threshold": 0.25,
        "cut_classification_enabled": False,
        "dissolve_detection_enabled": True,
        "dissolve_min_frames": 20,
    }
    out = M.normalize_config(dict(legacy))
    assert out["measurements"]["transitions"]["params"]["threshold"] == 31.5
    assert out["measurements"]["sampling"]["params"]["sample_fps"] == 4.0
    assert out["measurements"]["flashing"]["params"]["threshold"] == 0.25
    assert out["measurements"]["scene_relation"]["enabled"] is False
    assert out["measurements"]["dissolves"]["enabled"] is True
    assert out["measurements"]["dissolves"]["params"]["min_frames"] == 20


def test_legacy_keys_stay_derived_from_the_block(cfg):
    """Old call sites read flat keys; the block is authoritative and syncs them."""
    cfg["measurements"]["transitions"]["params"]["threshold"] = 33.0
    cfg["measurements"]["sampling"]["params"]["sample_fps"] = 5.0
    M.normalize_config(cfg)
    assert cfg["cut_detection_threshold"] == 33.0
    assert cfg["sample_fps"] == 5.0


def test_legacy_whisper_flag_maps_to_tool_choice():
    out = M.normalize_config({
        "speech_transcription_enabled": True,
        "speech_whisper_model": "small",
    })
    assert out["measurements"]["speech"]["tool"] == "captions_then_whisper"
    assert out["measurements"]["speech"]["params"]["model"] == "small"


def test_normalize_is_idempotent(cfg):
    once = M.measurement_fingerprint(M.normalize_config(copy.deepcopy(cfg)))
    twice = M.measurement_fingerprint(
        M.normalize_config(M.normalize_config(copy.deepcopy(cfg)))
    )
    assert once == twice


def test_unknown_tool_falls_back_to_default(cfg):
    cfg["measurements"]["transitions"]["tool"] = "not_a_real_detector"
    M.normalize_config(cfg)
    assert cfg["measurements"]["transitions"]["tool"] == "pyscenedetect_content"


def test_out_of_range_param_is_clamped_not_rejected(cfg):
    cfg["measurements"]["transitions"]["params"]["threshold"] = 9999.0
    M.normalize_config(cfg)
    assert cfg["measurements"]["transitions"]["params"]["threshold"] == 100.0


# ---------------------------------------------------------------------------
# Fingerprint — what counts as a measurement change
# ---------------------------------------------------------------------------

def test_weight_change_does_not_change_fingerprint(cfg):
    """Weights are re-scorable from cache — they must never invalidate it."""
    before = M.measurement_fingerprint(cfg)
    other = copy.deepcopy(cfg)
    other["sensory_load_weights"]["pacing"] = 0.9
    other["normalization_reference_ranges"]["cuts_per_min"] = [0, 99]
    assert M.measurement_fingerprint(other) == before


def test_threshold_change_changes_fingerprint(cfg):
    before = M.measurement_fingerprint(cfg)
    other = copy.deepcopy(cfg)
    other["measurements"]["transitions"]["params"]["threshold"] = 30.0
    assert M.measurement_fingerprint(other) != before


def test_tool_change_changes_fingerprint(cfg):
    before = M.measurement_fingerprint(cfg)
    other = copy.deepcopy(cfg)
    other["measurements"]["transitions"]["tool"] = "transnetv2"
    assert M.measurement_fingerprint(other) != before


def test_disabled_measurement_params_are_ignored(cfg):
    """Fiddling with a switched-off measurement is not a change."""
    cfg["measurements"]["dissolves"]["enabled"] = False
    before = M.measurement_fingerprint(cfg)
    other = copy.deepcopy(cfg)
    other["measurements"]["dissolves"]["params"]["noise_floor"] = 12.0
    assert M.measurement_fingerprint(other) == before


def test_enabling_a_measurement_changes_fingerprint(cfg):
    cfg["measurements"]["dissolves"]["enabled"] = False
    before = M.measurement_fingerprint(cfg)
    other = copy.deepcopy(cfg)
    other["measurements"]["dissolves"]["enabled"] = True
    assert M.measurement_fingerprint(other) != before


def test_diff_fingerprints_names_the_changes(cfg):
    other = copy.deepcopy(cfg)
    other["measurements"]["transitions"]["tool"] = "transnetv2"
    other["measurements"]["flashing"]["params"]["sample_fps"] = 20.0
    changes = M.diff_fingerprints(cfg, other)
    assert len(changes) == 2
    joined = " | ".join(changes)
    assert "TransNetV2" in joined
    assert "20.0" in joined


def test_describe_selection_reports_validation_status(cfg):
    described = M.describe_selection(cfg)
    assert "[validated]" in described["transitions"]
    # The scene-relation threshold has never been calibrated; the UI and
    # provenance output must keep saying so.
    assert "[unvalidated]" in described["scene_relation"]


# ---------------------------------------------------------------------------
# Cache staleness
# ---------------------------------------------------------------------------

def _cache_a_result(tmp_path, cfg) -> None:
    result = EpisodeResult(
        file="ep.mp4",
        duration_sec=100.0,
        measurement_fingerprint=M.measurement_fingerprint(cfg),
    )
    save_cache(tmp_path, "MyShow", "ep", result.to_dict())


def test_fingerprint_survives_cache_round_trip(tmp_path, cfg):
    _cache_a_result(tmp_path, cfg)
    loaded = EpisodeResult.from_dict(load_cached(tmp_path, "MyShow", "ep"))
    assert loaded.measurement_fingerprint == M.measurement_fingerprint(cfg)


def test_matching_config_is_not_stale(tmp_path, cfg):
    _cache_a_result(tmp_path, cfg)
    assert is_stale(load_cached(tmp_path, "MyShow", "ep"), cfg) is False


def test_changed_measurement_is_stale(tmp_path, cfg):
    _cache_a_result(tmp_path, cfg)
    other = copy.deepcopy(cfg)
    other["measurements"]["transitions"]["params"]["threshold"] = 30.0
    assert is_stale(load_cached(tmp_path, "MyShow", "ep"), other) is True


def test_changed_weights_are_not_stale(tmp_path, cfg):
    _cache_a_result(tmp_path, cfg)
    other = copy.deepcopy(cfg)
    other["sensory_load_weights"]["pacing"] = 0.9
    assert is_stale(load_cached(tmp_path, "MyShow", "ep"), other) is False


def test_unfingerprinted_cache_is_grandfathered(tmp_path, cfg):
    """Results predating fingerprinting must not invalidate an existing corpus."""
    result = EpisodeResult(file="ep.mp4", duration_sec=100.0)
    data = result.to_dict()
    data.pop("measurement_fingerprint")
    save_cache(tmp_path, "MyShow", "old", data)
    other = copy.deepcopy(cfg)
    other["measurements"]["transitions"]["params"]["threshold"] = 30.0
    assert is_stale(load_cached(tmp_path, "MyShow", "old"), other) is False


def test_missing_cache_is_not_stale(cfg):
    assert is_stale(None, cfg) is False
