"""
Show-level aggregation: per-metric summary statistics across all episodes.

Writes:
  <root>/.analysis/<show>/aggregate.json  — full structured stats
  <root>/.analysis/<show>/aggregate.csv   — one row per episode, flat metrics
"""

from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from .schema import EpisodeResult, MetricStats, ShowAggregate

if TYPE_CHECKING:                       # only for the annotation below
    import pandas as pd

# pandas is imported inside results_to_dataframe, not here. It costs ~1.1s to
# load and is needed only for CSV export, but this module also holds
# compute_show_aggregate — which the interface calls while building the Library
# — so a module-level import made pandas part of application STARTUP. Deferring
# it took the Qt build's import time from 2.2s to 1.1s.


def _stats(values: list[float]) -> MetricStats:
    if not values:
        return MetricStats()
    a = np.array(values, dtype=float)
    return MetricStats(
        mean=round(float(np.mean(a)), 4),
        median=round(float(np.median(a)), 4),
        std=round(float(np.std(a)), 4),
        min=round(float(np.min(a)), 4),
        max=round(float(np.max(a)), 4),
    )


def compute_show_aggregate(
    show_name: str,
    results: list[EpisodeResult],
) -> ShowAggregate:
    """
    Compute per-metric summary statistics across all successful episodes.

    Failed episodes are counted but excluded from metric stats.
    """
    ok = [r for r in results if r.status == "ok"]

    audio_ok = [r for r in ok if r.metrics.audio.available]

    return ShowAggregate(
        show_name=show_name,
        episode_count=len(results),
        failed_count=len(results) - len(ok),
        shot_length_mean_sec=_stats([r.metrics.shot_length.mean_sec for r in ok]),
        cuts_per_min=_stats([r.metrics.scene_pacing.cuts_per_min for r in ok]),
        color_saturation_mean=_stats([r.metrics.color_saturation.mean for r in ok]),
        color_contrast_mean=_stats([r.metrics.color_saturation.contrast_mean for r in ok]),
        motion_mean=_stats([r.metrics.motion.mean for r in ok]),
        flashing_events_per_min=_stats([r.metrics.flashing.luminance_delta_events_per_min for r in ok]),
        audio_rms_mean=_stats([r.metrics.audio.rms_mean for r in audio_ok]),
        sensory_load_score=_stats([r.metrics.sensory_load.score for r in ok]),
    )


def results_to_dataframe(results: list[EpisodeResult]) -> "pd.DataFrame":
    """Flatten episode results into a tidy DataFrame (one row per episode)."""
    import pandas as pd
    rows = []
    for r in results:
        m = r.metrics
        rows.append({
            "file": r.file,
            "status": r.status,
            "duration_sec": r.duration_sec,
            "shot_length_mean_sec": m.shot_length.mean_sec,
            "shot_length_median_sec": m.shot_length.median_sec,
            "shots_per_min": m.shot_length.shots_per_min,
            "shot_count": m.shot_length.count,
            "cuts_per_min": m.scene_pacing.cuts_per_min,
            "shot_length_cv": m.scene_pacing.shot_length_cv,
            "color_saturation_mean": m.color_saturation.mean,
            "color_saturation_temporal_var": m.color_saturation.temporal_var,
            "color_contrast_mean": m.color_saturation.contrast_mean,
            "motion_mean": m.motion.mean,
            "motion_peak": m.motion.peak,
            "flashing_events_per_min": m.flashing.luminance_delta_events_per_min,
            "audio_rms_mean": m.audio.rms_mean if m.audio.available else None,
            "audio_rms_peak": m.audio.rms_peak if m.audio.available else None,
            "audio_rms_temporal_var": m.audio.rms_temporal_var if m.audio.available else None,
            "audio_dynamic_range_db": m.audio.dynamic_range_db if m.audio.available else None,
            "audio_available": m.audio.available,
            "sensory_load_score": m.sensory_load.score,
            "sensory_load_audio_available": m.sensory_load.audio_available,
            "sensory_load_pacing": m.sensory_load.components.pacing,
            "sensory_load_saturation": m.sensory_load.components.saturation,
            "sensory_load_contrast": m.sensory_load.components.contrast,
            "sensory_load_motion": m.sensory_load.components.motion,
            "sensory_load_flashing": m.sensory_load.components.flashing,
            "sensory_load_audio": m.sensory_load.components.audio,
        })
    return pd.DataFrame(rows)


def save_show_results(
    root: Path,
    show_name: str,
    results: list[EpisodeResult],
    aggregate: ShowAggregate,
) -> tuple[Path, Path]:
    """
    Write aggregate.json and aggregate.csv to <root>/.analysis/<show>/.

    Returns:
        (json_path, csv_path)
    """
    out_dir = root / ".analysis" / show_name
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "aggregate.json"
    csv_path = out_dir / "aggregate.csv"

    json_path.write_text(aggregate.to_json(), encoding="utf-8")

    df = results_to_dataframe(results)
    df.to_csv(csv_path, index=False)

    return json_path, csv_path
