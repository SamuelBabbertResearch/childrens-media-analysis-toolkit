"""
Shot length and scene pacing metrics via PySceneDetect.

Shot length  = duration between consecutive cuts (raw rate).
Scene pacing = derived from the same cut series but captures *rhythm*:
               CV (std/mean of shot lengths) tells you whether cuts are
               evenly spaced or arrive in bursts, which is distinct from
               how fast cutting happens on average.
"""

from __future__ import annotations
import math
from pathlib import Path

import numpy as np
from scenedetect import detect, ContentDetector

from .schema import ShotLengthMetrics, ScenePacingMetrics


def compute_cut_metrics(
    video_path: Path,
    threshold: float,
    duration_sec: float,
) -> tuple[ShotLengthMetrics, ScenePacingMetrics]:
    """
    Detect scene cuts and return shot-length and pacing metrics.

    Args:
        video_path: Path to the MP4 file.
        threshold: ContentDetector sensitivity (lower = more cuts detected).
        duration_sec: Pre-computed video duration in seconds.

    Returns:
        (ShotLengthMetrics, ScenePacingMetrics)
    """
    scene_list = detect(str(video_path), ContentDetector(threshold=threshold))

    duration_min = max(duration_sec / 60.0, 1e-6)

    if not scene_list:
        # No cuts detected — treat entire video as a single shot
        return (
            ShotLengthMetrics(
                mean_sec=round(duration_sec, 3),
                median_sec=round(duration_sec, 3),
                shots_per_min=round(1.0 / duration_min, 3),
                count=1,
            ),
            ScenePacingMetrics(
                cuts_per_min=0.0,
                shot_length_cv=0.0,
                timeline_cuts_per_30s=[0.0] * max(1, math.ceil(duration_sec / 30.0)),
            ),
        )

    durations = np.array([
        end.seconds - start.seconds
        for start, end in scene_list
    ])

    # Cuts occur at the start of every scene after the first (scene 0 starts at t=0)
    cut_times = [start.seconds for start, _end in scene_list[1:]]

    mean_sec = float(np.mean(durations))
    shots_per_min = len(durations) / duration_min
    cuts_per_min = len(cut_times) / duration_min

    # CV = std/mean — captures burstiness/rhythm, distinct from raw cut rate
    shot_length_cv = float(np.std(durations) / mean_sec) if mean_sec > 0 else 0.0

    # Rolling cut count in 30-second windows across the episode
    window_sec = 30.0
    n_windows = max(1, math.ceil(duration_sec / window_sec))
    timeline = [
        float(sum(1 for t in cut_times if i * window_sec <= t < (i + 1) * window_sec))
        for i in range(n_windows)
    ]

    return (
        ShotLengthMetrics(
            mean_sec=round(mean_sec, 3),
            median_sec=round(float(np.median(durations)), 3),
            shots_per_min=round(shots_per_min, 3),
            count=int(len(durations)),
        ),
        ScenePacingMetrics(
            cuts_per_min=round(cuts_per_min, 3),
            shot_length_cv=round(shot_length_cv, 3),
            timeline_cuts_per_30s=timeline,
        ),
    )
