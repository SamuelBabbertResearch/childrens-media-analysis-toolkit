"""
Analysis engine — coordinates metric computation for a single episode.

Stages (reported via progress_cb):
  0.00–0.05  duration probe
  0.05–0.55  cut detection (PySceneDetect, most expensive)
  0.55–0.88  frame sampling (color / motion / flashing)
  0.88–0.93  audio extraction & loudness (FFmpeg)
  0.93–0.97  speech metrics (CC file parse or Whisper — fast when CC exists)
  0.97–1.00  sensory-load composite + return
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, Callable

import cv2

from .config_loader import load_config
from .metrics_audio import compute_audio_metrics
from .metrics_cuts import compute_cut_metrics
from .metrics_frames import compute_frame_metrics
from .metrics_sensory import compute_sensory_load
from .schema import EpisodeMetrics, EpisodeResult
from .speech import compute_speech_metrics


def _get_duration(video_path: Path) -> float:
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 1.0
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    return frame_count / fps


def analyze_episode(
    video_path: Path | str,
    config: dict[str, Any] | None = None,
    progress_cb: Callable[[float], None] | None = None,
    frame_cb: Callable | None = None,
) -> EpisodeResult:
    """
    Analyze a single episode and return an EpisodeResult.

    Args:
        video_path: Path to the MP4 file.
        config: Config dict (loaded from config.json if None).
        progress_cb: Optional callback(fraction: float) called during analysis.
        frame_cb: Optional callback(frame, sat, motion, luminance, is_flash) for
                  each sampled frame — used by the live analysis viewer.

    Returns:
        EpisodeResult with all real metric values.
    """
    video_path = Path(video_path)
    cfg = config or load_config()

    if not video_path.exists():
        return EpisodeResult(
            file=video_path.name,
            status="failed",
            error=f"File not found: {video_path}",
            config=cfg,
        )

    try:
        # Stage 1: duration probe
        if progress_cb:
            progress_cb(0.02)
        duration_sec = _get_duration(video_path)

        # Stage 2: cut detection — PySceneDetect provides no progress callback.
        # Signal -1.0 tells the UI to switch to an animated indeterminate bar
        # so the user can see something is happening even during the long wait.
        if progress_cb:
            progress_cb(-1.0)   # → UI enters indeterminate mode

        shot_metrics, pacing_metrics = compute_cut_metrics(
            video_path,
            threshold=cfg["cut_detection_threshold"],
            duration_sec=duration_sec,
        )

        # Stage 3: frame sampling (color / motion / flashing)
        if progress_cb:
            progress_cb(0.55)

        def _frame_progress(frac: float) -> None:
            if progress_cb:
                progress_cb(0.55 + frac * 0.33)

        color_metrics, motion_metrics, flashing_metrics = compute_frame_metrics(
            video_path,
            sample_fps=cfg["sample_fps"],
            flashing_threshold=cfg["flashing_luminance_threshold"],
            duration_sec=duration_sec,
            progress_cb=_frame_progress,
            frame_cb=frame_cb,
        )

        # Stage 4: audio
        if progress_cb:
            progress_cb(0.88)
        audio_metrics = compute_audio_metrics(video_path)

        # Stage 5: speech (CC file — fast; Whisper — slow; skipped by default)
        if progress_cb:
            progress_cb(0.93)
        speech_metrics = compute_speech_metrics(video_path, duration_sec, cfg)

        # Stage 6: composite
        if progress_cb:
            progress_cb(0.97)
        sensory_metrics = compute_sensory_load(
            pacing_metrics, color_metrics, motion_metrics,
            flashing_metrics, audio_metrics, cfg,
        )

    except Exception as exc:
        return EpisodeResult(
            file=video_path.name,
            status="failed",
            error=str(exc),
            config=cfg,
        )

    if progress_cb:
        progress_cb(1.0)

    return EpisodeResult(
        file=video_path.name,
        duration_sec=round(duration_sec, 2),
        metrics=EpisodeMetrics(
            shot_length=shot_metrics,
            scene_pacing=pacing_metrics,
            color_saturation=color_metrics,
            motion=motion_metrics,
            flashing=flashing_metrics,
            audio=audio_metrics,
            speech=speech_metrics,
            sensory_load=sensory_metrics,
        ),
        config=cfg,
    )
