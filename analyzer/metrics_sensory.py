"""
Formal-Feature Composite (FFC) score.

Normalizes each sub-metric against fixed, documented reference ranges so
scores are comparable across separate runs (not per-corpus normalization).
Weights are user-editable in config.json.

When audio is unavailable (no FFmpeg, no audio track), the audio weight is
redistributed proportionally among the visual metrics so the score remains
on the same 0–1 scale and is still comparable to audio-enabled results.
"""

from __future__ import annotations
from typing import Any

from .schema import (
    AudioMetrics, ScenePacingMetrics, ColorSaturationMetrics, MotionMetrics,
    FlashingMetrics, SensoryLoadMetrics, SensoryLoadComponents,
    EpisodeMetrics, EpisodeResult,
)


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _normalize(value: float, ref: dict[str, float]) -> float:
    """Min-max normalize against a fixed reference range, clamped to [0, 1]."""
    lo, hi = ref["min"], ref["max"]
    if hi <= lo:
        return 0.0
    return _clamp01((value - lo) / (hi - lo))


VISUAL_KEYS = ["pacing", "saturation", "color_contrast", "motion",
               "flashing"]


def effective_weights(config: dict[str, Any],
                      audio_available: bool) -> dict[str, float]:
    """The weights actually used to produce a score, audio absence included.

    When an episode has no audio track its weight is redistributed
    proportionally across the visual metrics, so the nominal 25/5/10/25/15/20
    in config.json is NOT what produced the number — pacing's 25% becomes
    31.25%. Anything DISPLAYING a weight or a contribution has to use these,
    or it shows a breakdown that does not add up to the score printed above
    it. That was a 0.057 discrepancy on a silent episode, in both the report
    table and the stacked chart whose bar height claims to BE the composite.

    Exposed here rather than recomputed in the interface: `cli.py` and the GUI
    are thin layers over one engine, and redistribution is engine arithmetic.
    """
    weights = dict(config.get("sensory_load_weights", {}))
    audio_weight = weights.get("audio", 0.0)
    if audio_available or audio_weight <= 0:
        return weights
    visual_sum = sum(weights.get(k, 0.0) for k in VISUAL_KEYS)
    if visual_sum > 0:
        for key in VISUAL_KEYS:
            weights[key] = (weights.get(key, 0.0)
                            + audio_weight * (weights.get(key, 0.0) / visual_sum))
    weights["audio"] = 0.0
    return weights


def compute_sensory_load(
    pacing: ScenePacingMetrics,
    color: ColorSaturationMetrics,
    motion: MotionMetrics,
    flashing: FlashingMetrics,
    audio: AudioMetrics,
    config: dict[str, Any],
) -> SensoryLoadMetrics:
    """
    Weighted composite of normalized sub-metrics.

    If audio is unavailable its weight (default 20%) is redistributed
    proportionally across the visual metrics so the total still sums to 1.
    """
    ranges = config["normalization_reference_ranges"]
    w = dict(config["sensory_load_weights"])  # copy — we may mutate

    n_pacing     = _normalize(pacing.cuts_per_min,                      ranges["cuts_per_min"])
    n_saturation = _normalize(color.mean,                               ranges["color_saturation_mean"])
    n_contrast   = _normalize(color.contrast_mean,                      ranges["color_contrast_mean"])
    n_motion     = _normalize(motion.mean,                              ranges["motion_mean"])
    n_flashing   = _normalize(flashing.luminance_delta_events_per_min,  ranges["flashing_events_per_min"])

    audio_weight = w.get("audio", 0.0)
    if audio.available and audio_weight > 0:
        n_audio = _normalize(audio.rms_mean, ranges["audio_rms_mean"])
        audio_available = True
    else:
        n_audio = 0.0
        audio_available = False
    # One implementation of the redistribution, shared with whatever displays
    # the breakdown — see effective_weights().
    w = effective_weights(config, audio_available)

    score = (
        w.get("pacing",        0.0) * n_pacing
        + w.get("saturation",  0.0) * n_saturation
        + w.get("color_contrast", 0.0) * n_contrast
        + w.get("motion",      0.0) * n_motion
        + w.get("flashing",    0.0) * n_flashing
        + w.get("audio",       0.0) * n_audio
    )

    return SensoryLoadMetrics(
        score=round(_clamp01(score), 4),
        audio_available=audio_available,
        components=SensoryLoadComponents(
            pacing=round(n_pacing, 4),
            saturation=round(n_saturation, 4),
            contrast=round(n_contrast, 4),
            motion=round(n_motion, 4),
            flashing=round(n_flashing, 4),
            audio=round(n_audio, 4),
        ),
    )


def rescore_episode(result: EpisodeResult, cfg: dict[str, Any]) -> EpisodeResult:
    """Return a copy of result with the composite recomputed against a new config.

    Raw metrics are unchanged — only the composite is recalculated. This is
    what makes "Apply & Re-score" instant: weights and normalization ceilings
    are scoring settings, so no episode needs re-analysing.

    REBUILT WITH `replace`, NOT BY LISTING FIELDS. It used to construct a fresh
    EpisodeResult naming each field it wanted to keep, which silently dropped
    every field added afterwards. By 2026-09-04 that was `measurement_fingerprint`
    and `measurement_tools` — and this function is reached through
    `analyzer.cache.load_scored()`, THE ONE WAY TO READ A CACHED RESULT. So
    every screen and every export that read a cached episode got a result with
    no fingerprint (nothing to say whether two rows were even measured the same
    way) and an empty tools map (so the report's "not graded against hand
    coding" warning was skipped while the flashing number stayed on screen).
    The provenance fields added on 2026-09-04 would have been the next
    casualties. `replace` keeps everything by construction, so a field added
    tomorrow survives with no edit here.
    """
    from dataclasses import replace

    if result.status != "ok":
        return result
    m = result.metrics
    new_sensory = compute_sensory_load(
        m.scene_pacing, m.color_saturation, m.motion, m.flashing, m.audio, cfg,
    )
    return replace(
        result,
        metrics=replace(m, sensory_load=new_sensory),
        config=cfg,
    )
