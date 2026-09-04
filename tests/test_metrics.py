"""
Phase 1 tests — real metric values against LittleBear.mp4.

Little Bear is a slow-paced, calm watercolor-style animated show.
Expected rough ranges:
  - shots_per_min: 2–20  (slow cutting)
  - color saturation mean: 0.15–0.60  (soft watercolor palette)
  - motion mean: 0.001–0.10  (gentle animation)
  - flashing events/min: 0–10  (very calm, no strobe effects)
  - FFC score: 0.0–0.50  (below the configured reference midpoint)
"""

from pathlib import Path
import pytest

from analyzer.engine import analyze_episode
from analyzer.metrics_cuts import compute_cut_metrics
from analyzer.metrics_frames import compute_frame_metrics
from analyzer.metrics_sensory import compute_sensory_load, _normalize
from analyzer.config_loader import load_config
from analyzer.schema import ScenePacingMetrics, ColorSaturationMetrics, MotionMetrics, FlashingMetrics, AudioMetrics

ROOT = Path(__file__).parent.parent
LITTLE_BEAR_EP = ROOT / "Little Bear" / "LittleBear.mp4"
SKIP_IF_NO_VIDEO = pytest.mark.skipif(
    not LITTLE_BEAR_EP.exists(), reason="LittleBear.mp4 not present"
)


# ---------------------------------------------------------------------------
# _normalize helper
# ---------------------------------------------------------------------------

def test_normalize_midpoint():
    ref = {"min": 0.0, "max": 10.0}
    assert _normalize(5.0, ref) == pytest.approx(0.5)


def test_normalize_clamps_above():
    ref = {"min": 0.0, "max": 10.0}
    assert _normalize(20.0, ref) == 1.0


def test_normalize_clamps_below():
    ref = {"min": 0.0, "max": 10.0}
    assert _normalize(-5.0, ref) == 0.0


# ---------------------------------------------------------------------------
# Formal-Feature Composite (unit — no video needed)
# ---------------------------------------------------------------------------

def test_sensory_load_zero_inputs():
    cfg = load_config()
    result = compute_sensory_load(
        ScenePacingMetrics(),
        ColorSaturationMetrics(),
        MotionMetrics(),
        FlashingMetrics(),
        AudioMetrics(),
        cfg,
    )
    assert result.score == 0.0
    assert result.components.pacing == 0.0


def test_sensory_load_max_inputs():
    """A value AT each ceiling must normalise to 1.0 and produce a score of 1.0.

    The ceilings are read from the config rather than written in here. They
    were hard-coded as 60/1.0/0.35/1.0/30, which made this test assert against
    a snapshot of `config.json` rather than against the property it describes —
    so retuning the ceilings on 2026-08-14 failed it for the wrong reason. See
    `CEILINGS.md`.
    """
    cfg = load_config()
    ceil = {k: v["max"] for k, v in cfg["normalization_reference_ranges"].items()}
    pacing = ScenePacingMetrics(cuts_per_min=ceil["cuts_per_min"])
    color = ColorSaturationMetrics(mean=ceil["color_saturation_mean"],
                                   contrast_mean=ceil["color_contrast_mean"])
    motion = MotionMetrics(mean=ceil["motion_mean"])
    flashing = FlashingMetrics(
        luminance_delta_events_per_min=ceil["flashing_events_per_min"])
    result = compute_sensory_load(pacing, color, motion, flashing, AudioMetrics(), cfg)
    # Audio weight redistributes to visual metrics when unavailable, so score still hits 1.0
    assert result.score == pytest.approx(1.0)
    assert not result.audio_available
    assert all(
        v == pytest.approx(1.0)
        for v in [
            result.components.pacing,
            result.components.saturation,
            result.components.contrast,
            result.components.motion,
            result.components.flashing,
        ]
    )


def test_sensory_load_weights_sum_to_one():
    cfg = load_config()
    weights = cfg["sensory_load_weights"]
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Full episode analysis — plausible bounds
# ---------------------------------------------------------------------------

@SKIP_IF_NO_VIDEO
def test_full_analysis_returns_ok(little_bear_result):
    assert little_bear_result.status == "ok"
    assert little_bear_result.duration_sec > 60


@SKIP_IF_NO_VIDEO
def test_shot_length_plausible(little_bear_result):
    sl = little_bear_result.metrics.shot_length
    assert sl.count > 10, "Should detect more than 10 shots in a 24-min episode"
    assert 0.5 <= sl.mean_sec <= 30.0, f"Mean shot length out of range: {sl.mean_sec}"
    assert sl.median_sec > 0
    assert 0.0 < sl.shots_per_min <= 60.0


@SKIP_IF_NO_VIDEO
def test_scene_pacing_plausible(little_bear_result):
    sp = little_bear_result.metrics.scene_pacing
    assert 0.0 <= sp.cuts_per_min <= 60.0
    assert sp.shot_length_cv >= 0.0
    assert len(sp.timeline_cuts_per_30s) > 0


@SKIP_IF_NO_VIDEO
def test_color_saturation_plausible(little_bear_result):
    cs = little_bear_result.metrics.color_saturation
    assert 0.0 <= cs.mean <= 1.0, f"Saturation mean out of [0,1]: {cs.mean}"
    assert cs.temporal_var >= 0.0
    assert 0.0 <= cs.contrast_mean <= 0.5, f"Contrast mean out of expected range: {cs.contrast_mean}"


@SKIP_IF_NO_VIDEO
def test_motion_plausible(little_bear_result):
    m = little_bear_result.metrics.motion
    assert 0.0 <= m.mean <= 1.0, f"Motion mean out of [0,1]: {m.mean}"
    assert m.peak >= m.mean


@SKIP_IF_NO_VIDEO
def test_flashing_plausible(little_bear_result):
    f = little_bear_result.metrics.flashing
    assert f.luminance_delta_events_per_min >= 0.0
    # Little Bear should have very few flashing events
    assert f.luminance_delta_events_per_min < 30.0


@SKIP_IF_NO_VIDEO
def test_sensory_load_bounded(little_bear_result):
    sl = little_bear_result.metrics.sensory_load
    assert 0.0 <= sl.score <= 1.0
    for name, val in vars(sl.components).items():
        assert 0.0 <= val <= 1.0, f"Component {name} out of [0,1]: {val}"


@SKIP_IF_NO_VIDEO
def test_little_bear_ffc_is_below_configured_reference_midpoint(little_bear_result):
    """This reference episode remains below the configured FFC midpoint."""
    score = little_bear_result.metrics.sensory_load.score
    assert score < 0.50, f"Expected FFC below 0.50 for Little Bear, got {score:.3f}"


# ---------------------------------------------------------------------------
# Fixture — run analysis once and share across tests in this module
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def little_bear_result():
    return analyze_episode(LITTLE_BEAR_EP)
