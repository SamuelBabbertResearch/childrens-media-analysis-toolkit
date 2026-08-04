"""
Color saturation, motion, and flashing metrics via a single frame-sampling pass.

All three are computed together to avoid reading the video file more than once.
Frames are sampled at `sample_fps` using sequential grab() calls for skipped
frames (no decoding cost) and read() only on sampled frames.
"""

from __future__ import annotations
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from .schema import ColorSaturationMetrics, MotionMetrics, FlashingMetrics


def compute_frame_metrics(
    video_path: Path,
    sample_fps: float,
    flashing_threshold: float,
    duration_sec: float,
    flashing_sample_fps: float | None = None,
    motion_method: str = "absdiff",
    progress_cb: Callable[[float], None] | None = None,
    frame_cb: Callable[[np.ndarray, float, float, float, bool], None] | None = None,
) -> tuple[ColorSaturationMetrics, MotionMetrics, FlashingMetrics]:
    """
    Single-pass frame-sampling loop for saturation, motion, and flashing.

    Args:
        video_path: Path to the MP4 file.
        sample_fps: How many frames to decode per second of video (default 2).
        flashing_threshold: Luminance delta (0–1) that counts as a flash event.
        duration_sec: Pre-computed video duration in seconds.
        flashing_sample_fps: Optional higher-rate pass for flashing detection.
        motion_method: "absdiff" (fast, default) or "farneback" (optical flow).
        progress_cb: Optional callback(fraction: float) for UI progress reporting.
        frame_cb: Optional callback(frame, saturation, motion, luminance, is_flash)
                  called for each sampled frame — used by the live analysis viewer.

    Returns:
        (ColorSaturationMetrics, MotionMetrics, FlashingMetrics)
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"Could not open video file: {video_path}")
    video_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = max(1, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))

    # Decode every Nth frame; grab() the rest (fast, no pixel decode)
    frame_interval = max(1, int(round(video_fps / sample_fps)))

    saturation_values: list[float] = []
    contrast_values: list[float] = []    # spatial std-dev of V per frame
    motion_values: list[float] = []
    flashing_events = 0

    prev_gray: np.ndarray | None = None
    prev_luminance: float | None = None

    frame_idx = 0
    while True:
        if frame_idx % frame_interval == 0:
            ret, frame = cap.read()
            if not ret:
                break

            # --- Color saturation (HSV S-channel) and contrast (std-dev of V-channel) ---
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            s_mean = float(np.mean(hsv[:, :, 1])) / 255.0
            saturation_values.append(s_mean)
            v_std = float(np.std(hsv[:, :, 2])) / 255.0   # spatial spread of brightness
            contrast_values.append(v_std)

            # --- Luminance for flashing detection ---
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            luminance = float(np.mean(gray)) / 255.0

            is_flash = (
                prev_luminance is not None
                and abs(luminance - prev_luminance) > flashing_threshold
            )
            if is_flash:
                flashing_events += 1
            prev_luminance = luminance

            # --- Motion ---
            motion = 0.0
            if prev_gray is not None:
                if motion_method == "farneback":
                    flow = cv2.calcOpticalFlowFarneback(
                        prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
                    )
                    mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
                    # Typical max displacement per sampled-frame gap ≈ 20 px; clamp to [0,1]
                    motion = min(1.0, float(np.mean(mag)) / 20.0)
                else:
                    diff = cv2.absdiff(gray, prev_gray)
                    motion = float(np.mean(diff)) / 255.0
                motion_values.append(motion)

            prev_gray = gray

            if frame_cb:
                frame_cb(frame, s_mean, motion, luminance, is_flash)

            if progress_cb:
                progress_cb(frame_idx / total_frames)
        else:
            ret = cap.grab()
            if not ret:
                break

        frame_idx += 1

    cap.release()

    duration_min = max(duration_sec / 60.0, 1e-6)

    sat_arr = np.array(saturation_values) if saturation_values else np.array([0.0])
    con_arr = np.array(contrast_values)   if contrast_values   else np.array([0.0])
    mot_arr = np.array(motion_values)     if motion_values     else np.array([0.0])

    if flashing_sample_fps and flashing_sample_fps > sample_fps:
        flashing_events = _count_flashing_events(
            video_path, video_fps, flashing_sample_fps, flashing_threshold
        )

    return (
        ColorSaturationMetrics(
            mean=round(float(np.mean(sat_arr)), 4),
            temporal_var=round(float(np.var(sat_arr)), 4),
            contrast_mean=round(float(np.mean(con_arr)), 4),
        ),
        MotionMetrics(
            mean=round(float(np.mean(mot_arr)), 4),
            peak=round(float(np.max(mot_arr)), 4),
        ),
        FlashingMetrics(
            luminance_delta_events_per_min=round(flashing_events / duration_min, 3),
        ),
    )


def _count_flashing_events(
    video_path: Path,
    video_fps: float,
    sample_fps: float,
    flashing_threshold: float,
) -> int:
    """Count luminance jumps in a dedicated higher-rate pass."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"Could not open video file: {video_path}")

    frame_interval = max(1, int(round(video_fps / sample_fps)))
    events = 0
    prev_luminance: float | None = None
    frame_idx = 0

    while True:
        if frame_idx % frame_interval == 0:
            ret, frame = cap.read()
            if not ret:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            luminance = float(np.mean(gray)) / 255.0
            if prev_luminance is not None and abs(luminance - prev_luminance) > flashing_threshold:
                events += 1
            prev_luminance = luminance
        else:
            ret = cap.grab()
            if not ret:
                break
        frame_idx += 1

    cap.release()
    return events
