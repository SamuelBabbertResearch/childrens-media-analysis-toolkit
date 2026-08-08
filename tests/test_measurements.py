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


# ---------------------------------------------------------------------------
# Dispatch — every declared tool must map to a real implementation
# ---------------------------------------------------------------------------
# The registry is a promise the engine has to keep. A tool key that no dispatch
# branch recognises would silently fall through to the default detector, so the
# user would select TransNetV2, see no error, and get ContentDetector numbers
# labelled as TransNetV2.

def test_every_transition_tool_has_a_dispatch_branch():
    import inspect
    from analyzer import metrics_cuts
    source = inspect.getsource(metrics_cuts._detect_shots)
    spec = M.get_measurement("transitions")
    for tool in spec.tools:
        if tool.key == "pyscenedetect_content":
            continue          # the else-branch default
        assert tool.key in source, f"no dispatch branch for {tool.key}"


def test_motion_tool_keys_match_metrics_frames():
    """motion_method is passed straight through as the tool key."""
    import inspect
    from analyzer import metrics_frames
    source = inspect.getsource(metrics_frames.compute_frame_metrics)
    for tool in M.get_measurement("motion").tools:
        assert tool.key in source, f"metrics_frames does not handle {tool.key}"


def test_transition_params_match_detector_signatures():
    """Registry parameter names must be real constructor arguments."""
    import inspect
    from scenedetect import AdaptiveDetector, ContentDetector

    spec = M.get_measurement("transitions")
    content = spec.tool("pyscenedetect_content")
    adaptive = spec.tool("pyscenedetect_adaptive")

    content_args = inspect.signature(ContentDetector.__init__).parameters
    for p in content.params:
        assert p.key in content_args

    adaptive_args = inspect.signature(AdaptiveDetector.__init__).parameters
    for p in adaptive.params:
        assert p.key in adaptive_args


def test_speech_is_enabled_by_default_with_captions_only(cfg):
    """Captions are parsed whenever present, so speech is on but Whisper is not."""
    tool, _params, enabled = M.selection(cfg, "speech")
    assert enabled is True
    assert tool.key == "captions_only"
    assert cfg["speech_transcription_enabled"] is False


def test_speech_tool_choice_round_trips_to_legacy_flag(cfg):
    cfg["measurements"]["speech"]["tool"] = "captions_then_whisper"
    M.normalize_config(cfg)
    assert cfg["speech_transcription_enabled"] is True
    cfg["measurements"]["speech"]["tool"] = "captions_only"
    M.normalize_config(cfg)
    assert cfg["speech_transcription_enabled"] is False


def test_provenance_map_survives_cache_round_trip(tmp_path, cfg):
    """Validation status must reach exports, not just the live UI."""
    tools = M.describe_selection(cfg)
    result = EpisodeResult(file="ep.mp4", measurement_tools=tools)
    save_cache(tmp_path, "MyShow", "ep", result.to_dict())
    loaded = EpisodeResult.from_dict(load_cached(tmp_path, "MyShow", "ep"))
    assert loaded.measurement_tools == tools
    assert "[unvalidated]" in loaded.measurement_tools["scene_relation"]


def test_provenance_map_covers_every_measurement(cfg):
    described = M.describe_selection(cfg)
    assert set(described) == {m.key for m in M.MEASUREMENTS}


def test_flat_speech_keys_alone_do_not_survive_normalization(cfg):
    """Regression: the measurements block wins, so UI must write into it.

    Setting only the legacy flat key against a config that already has a
    measurements block is silently reverted — which is exactly how the Settings
    dialog's Whisper toggle broke. Anything editing speech must set the tool.
    """
    flat_only = copy.deepcopy(cfg)
    flat_only["speech_transcription_enabled"] = True
    assert M.normalize_config(flat_only)["speech_transcription_enabled"] is False

    via_block = copy.deepcopy(cfg)
    via_block["measurements"]["speech"]["tool"] = "captions_then_whisper"
    assert M.normalize_config(via_block)["speech_transcription_enabled"] is True


def test_transnet_declares_its_optional_dependency():
    """Selecting a tool with a missing dependency must be detectable up front."""
    tool = M.get_measurement("transitions").tool("transnetv2")
    assert tool.optional_tool_key == "transnetv2"
    assert isinstance(tool.is_available(), bool)
