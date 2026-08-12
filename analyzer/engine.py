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
from .measurements import (
    describe_selection, measurement_fingerprint, normalize_config, selection,
)
from .metrics_audio import compute_audio_metrics
from .metrics_cuts import compute_cut_metrics
from .metrics_frames import compute_frame_metrics
from .metrics_sensory import compute_sensory_load
from .schema import EpisodeMetrics, EpisodeResult, SpeechMetrics
from .speech import compute_speech_metrics


def _get_duration(video_path: Path) -> float:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"Could not open video file: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 1.0
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    if fps <= 0 or frame_count <= 0:
        raise RuntimeError(f"Could not read video duration: {video_path}")
    return frame_count / fps


def analyze_episode(
    video_path: Path | str,
    config: dict[str, Any] | None = None,
    progress_cb: Callable[[float], None] | None = None,
    frame_cb: Callable | None = None,
    status_cb: Callable[[str], None] | None = None,
) -> EpisodeResult:
    """
    Analyze a single episode and return an EpisodeResult.

    Args:
        video_path: Path to the MP4 file.
        config: Config dict (loaded from config.json if None).
        progress_cb: Optional callback(fraction: float) called during analysis.
        frame_cb: Optional callback(frame, sat, motion, luminance, is_flash) for
                  each sampled frame — used by the live analysis viewer.
        status_cb: Optional callback(text) for stage messages. The neural
                  detector runs for minutes with no progress signal, so it
                  reports through here rather than appearing to hang.

    Returns:
        EpisodeResult with all real metric values.
    """
    video_path = Path(video_path)
    # load_config() normalizes; a caller-supplied dict may not have been through
    # it yet (the GUI holds a live config), so normalize here too. Idempotent.
    cfg = normalize_config(config) if config else load_config()
    fingerprint = measurement_fingerprint(cfg)
    tool_summary = describe_selection(cfg)

    if not video_path.exists():
        return EpisodeResult(
            file=video_path.name,
            status="failed",
            error=f"File not found: {video_path}",
            config=cfg,
            measurement_fingerprint=fingerprint,
            measurement_tools=tool_summary,
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

        trans_tool, trans_params, _ = selection(cfg, "transitions")
        diss_tool, diss_params, diss_enabled = selection(cfg, "dissolves")
        rel_tool, rel_params, rel_enabled = selection(cfg, "scene_relation")

        shot_metrics, pacing_metrics = compute_cut_metrics(
            video_path,
            threshold=trans_params.get("threshold", 27.0),
            duration_sec=duration_sec,
            tool=trans_tool.key,
            tool_params=trans_params,
            status_cb=status_cb,
            detect_dissolves=diss_enabled,
            dissolve_noise_floor=diss_params.get("noise_floor", 3.0),
            dissolve_min_frames=diss_params.get("min_frames", 15),
            classify_cuts_enabled=rel_enabled,
            classify_offset_sec=rel_params.get("offset_sec", 1.0),
            scene_change_similarity_threshold=rel_params.get(
                "similarity_threshold", 0.55),
        )

        # Stage 3: frame sampling (color / motion / flashing)
        if progress_cb:
            progress_cb(0.55)

        def _frame_progress(frac: float) -> None:
            if progress_cb:
                progress_cb(0.55 + frac * 0.33)

        samp_tool, samp_params, _ = selection(cfg, "sampling")
        motion_tool, _motion_params, _ = selection(cfg, "motion")
        flash_tool, flash_params, _ = selection(cfg, "flashing")

        color_metrics, motion_metrics, flashing_metrics = compute_frame_metrics(
            video_path,
            sample_fps=samp_params.get("sample_fps", 2.0),
            flashing_sample_fps=flash_params.get("sample_fps"),
            flashing_threshold=flash_params.get("threshold", 0.1),
            motion_method=motion_tool.key,
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
        _speech_tool, _speech_params, speech_enabled = selection(cfg, "speech")
        speech_metrics = (
            compute_speech_metrics(video_path, duration_sec, cfg)
            if speech_enabled
            else SpeechMetrics(available=False, source="disabled")
        )

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
            measurement_fingerprint=fingerprint,
            measurement_tools=tool_summary,
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
        measurement_fingerprint=fingerprint,
        measurement_tools=tool_summary,
    )
