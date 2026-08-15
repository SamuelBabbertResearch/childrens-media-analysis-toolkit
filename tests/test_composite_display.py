"""
The composite's breakdown must add up to the composite.

A silent episode has audio's weight redistributed proportionally across the
visual metrics, so the nominal 25/5/10/25/15/20 in config.json is NOT what
produced its score. The report table and the stacked chart both read the
nominal weights, so on a no-audio episode the breakdown disagreed with the
headline figure printed directly above it — by 0.057 on a real case.

`analyzer.metrics_sensory.effective_weights` is now the one implementation,
used by the engine to compute and by the interface to explain.
"""

from __future__ import annotations

from analyzer.config_loader import load_config
from analyzer.metrics_sensory import (
    VISUAL_KEYS, effective_weights, rescore_episode,
)
from analyzer.schema import EpisodeResult


def _episode(audio: bool) -> EpisodeResult:
    r = EpisodeResult(file="e.mp4", duration_sec=600.0)
    r.metrics.scene_pacing.cuts_per_min = 20.0
    r.metrics.color_saturation.mean = 0.5
    r.metrics.color_saturation.contrast_mean = 0.3
    r.metrics.motion.mean = 0.05
    r.metrics.flashing.luminance_delta_events_per_min = 4.0
    r.metrics.audio.available = audio
    r.metrics.audio.rms_mean = 0.03
    return rescore_episode(r, load_config())


def _breakdown_sums_to_score(result) -> tuple[float, float]:
    sl = result.metrics.sensory_load
    weights = effective_weights(result.config, sl.audio_available)
    c = sl.components
    total = (c.pacing * weights.get("pacing", 0.0)
             + c.saturation * weights.get("saturation", 0.0)
             + c.contrast * weights.get("color_contrast", 0.0)
             + c.motion * weights.get("motion", 0.0)
             + c.flashing * weights.get("flashing", 0.0)
             + c.audio * weights.get("audio", 0.0))
    return sl.score, total


def test_the_breakdown_reconciles_with_audio():
    score, total = _breakdown_sums_to_score(_episode(True))
    assert abs(score - total) < 0.001


def test_the_breakdown_reconciles_without_audio():
    """The regression: nominal weights left the table 0.057 short."""
    score, total = _breakdown_sums_to_score(_episode(False))
    assert abs(score - total) < 0.001


def test_effective_weights_still_total_one_without_audio():
    weights = effective_weights(load_config(), audio_available=False)
    assert abs(sum(weights[k] for k in VISUAL_KEYS) - 1.0) < 1e-9
    assert weights["audio"] == 0.0


def test_effective_weights_are_the_nominal_ones_when_audio_is_present():
    config = load_config()
    assert effective_weights(config, True) == config["sensory_load_weights"]


def test_the_engine_and_the_display_share_one_implementation():
    """Redistribution is engine arithmetic; a second copy in the interface
    is how the two drifted in the first place."""
    import inspect
    from analyzer import metrics_sensory
    from ui import chart, report
    assert "effective_weights(config, audio_available)" in inspect.getsource(
        metrics_sensory.compute_sensory_load)
    assert "effective_weights" in inspect.getsource(report.episode_html)
    assert "effective_weights" in inspect.getsource(chart.ChartDialog.__init__)


def test_a_silent_episode_says_its_score_is_composed_differently():
    """Two 0.28s are not the same 0.28 if one excluded audio."""
    from ui.report import episode_html
    html = episode_html(_episode(False))
    assert "redistributed across the visual metrics" in html
    assert "not directly comparable" in html
