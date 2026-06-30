"""
Sensory load composite score.

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
        # Redistribute the audio weight proportionally among visual metrics
        if audio_weight > 0:
            visual_keys = ["pacing", "saturation", "color_contrast", "motion", "flashing"]
            visual_sum = sum(w.get(k, 0.0) for k in visual_keys)
            if visual_sum > 0:
                for k in visual_keys:
                    w[k] = w.get(k, 0.0) + audio_weight * (w.get(k, 0.0) / visual_sum)
            w["audio"] = 0.0

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
    """Return a copy of result with sensory_load recomputed against a new config.

    Raw metrics are unchanged — only the composite is recalculated.
    Useful for instant re-scoring when the user edits weights or reference ranges.
    """
    if result.status != "ok":
        return result
    m = result.metrics
    new_sensory = compute_sensory_load(
        m.scene_pacing, m.color_saturation, m.motion, m.flashing, m.audio, cfg,
    )
    return EpisodeResult(
        file=result.file,
        status=result.status,
        duration_sec=result.duration_sec,
        metrics=EpisodeMetrics(
            shot_length=m.shot_length,
            scene_pacing=m.scene_pacing,
            color_saturation=m.color_saturation,
            motion=m.motion,
            flashing=m.flashing,
            audio=m.audio,
            speech=m.speech,
            sensory_load=new_sensory,
        ),
        config=cfg,
        error=result.error,
    )
