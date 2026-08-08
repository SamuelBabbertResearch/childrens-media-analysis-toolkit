"""
Shot length and scene pacing metrics via PySceneDetect + dissolve detection.

Hard cuts  — detected by PySceneDetect ContentDetector (abrupt luminance spike).
Dissolves  — detected by a secondary frame-score pass that finds sustained
             moderate-change plateaus that ContentDetector misses because no
             single frame exceeds the spike threshold.

Shot length  = duration between consecutive hard cuts.
Scene pacing = cut rate, shot CV, rolling 30s timeline, plus optional dissolve rate.
"""

from __future__ import annotations
import math
from pathlib import Path

import cv2
import numpy as np
from scenedetect import detect, ContentDetector

from .schema import ShotLengthMetrics, ScenePacingMetrics


# ---------------------------------------------------------------------------
# Dissolve detection helpers
# ---------------------------------------------------------------------------

def _compute_frame_scores(
    video_path: Path,
    max_dim: int = 320,
    progress_cb=None,
) -> list[tuple[float, float]]:
    """
    Read every frame and return (timestamp_sec, content_score) pairs.

    Score formula mirrors PySceneDetect ContentDetector's HSV weighted diff
    so the numeric scale is comparable to the hard-cut threshold (default 27.0).
    Frames are downscaled to max_dim on the longer axis for speed.
    progress_cb, if given, is called with a 0.0-1.0 fraction every ~100 frames.
    """
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0

    scale = min(1.0, max_dim / max(w, h, 1))
    dw, dh = max(1, int(w * scale)), max(1, int(h * scale))

    prev_hsv: np.ndarray | None = None
    scores: list[tuple[float, float]] = []
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        small = cv2.resize(frame, (dw, dh), interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV).astype(np.float32)

        if prev_hsv is not None:
            # H channel wraps at 180 — take the shorter angular distance
            dh_chan = np.minimum(
                np.abs(hsv[:, :, 0] - prev_hsv[:, :, 0]),
                180.0 - np.abs(hsv[:, :, 0] - prev_hsv[:, :, 0]),
            )
            ds = np.abs(hsv[:, :, 1] - prev_hsv[:, :, 1])
            dv = np.abs(hsv[:, :, 2] - prev_hsv[:, :, 2])
            # Normalise channels to [0,100] then weight
            score = float(
                (dh_chan.mean() / 180.0) * 0.28 * 100.0
                + (ds.mean()    / 255.0) * 0.45 * 100.0
                + (dv.mean()    / 255.0) * 0.27 * 100.0
            )
            scores.append((frame_idx / fps, score))

        prev_hsv = hsv
        frame_idx += 1
        if progress_cb and total_frames and frame_idx % 100 == 0:
            progress_cb(min(frame_idx / total_frames, 1.0))

    cap.release()
    return scores


def _find_dissolves(
    frame_scores: list[tuple[float, float]],
    hard_cut_times_sec: list[float],
    noise_floor: float,
    hard_threshold: float,
    min_frames: int,
    exclusion_radius_sec: float = 1.5,
) -> list[dict]:
    """
    Find dissolves: runs of >= min_frames consecutive frames where the content
    score is in [noise_floor, hard_threshold).

    Runs that overlap within exclusion_radius_sec of a hard cut are discarded
    (they are likely edge-ringing around the cut, not a separate dissolve).

    Returns list of dicts: {timestamp_sec, duration_sec, peak_score}
    """
    if not frame_scores:
        return []

    dissolves: list[dict] = []
    run: list[tuple[float, float]] = []

    def _flush(run: list[tuple[float, float]]) -> None:
        if len(run) < min_frames:
            return
        peak_t, peak_score = max(run, key=lambda x: x[1])
        duration = run[-1][0] - run[0][0]
        too_close = any(abs(peak_t - hc) < exclusion_radius_sec for hc in hard_cut_times_sec)
        if not too_close:
            dissolves.append({
                "timestamp_sec": round(peak_t, 3),
                "duration_sec":  round(duration, 3),
                "peak_score":    round(peak_score, 3),
            })

    for t, score in frame_scores:
        if noise_floor <= score < hard_threshold:
            run.append((t, score))
        else:
            _flush(run)
            run = []

    _flush(run)
    return dissolves


# ---------------------------------------------------------------------------
# Cut classification: within-scene vs scene-change
# ---------------------------------------------------------------------------
# Rationale (Lang / LC4MP): a shot-reverse-shot cut inside one scene costs the
# viewer little processing; a cut that relocates to a new scene forces the
# mental model to be rebuilt. Raw cuts/min conflates the two. We approximate
# the distinction by comparing a frame shortly BEFORE the cut with one shortly
# AFTER it: high similarity (same background/palette/layout) -> within_scene,
# low similarity -> scene_change.
# NOTE: the similarity threshold default is UNVALIDATED — it is tunable against
# hand-coded ground truth (see validation/VALIDATION_LOG.md, 2026-07-05).

def _grab_frame(cap: "cv2.VideoCapture", t_sec: float) -> np.ndarray | None:
    cap.set(cv2.CAP_PROP_POS_MSEC, max(t_sec, 0.0) * 1000.0)
    ret, frame = cap.read()
    return frame if ret else None


def _frame_similarity(a: np.ndarray, b: np.ndarray, max_dim: int = 160) -> float:
    """Similarity in [0,1]: 0.5 * HSV hue/sat histogram correlation
    + 0.5 * grayscale 32x32 structural agreement."""
    def _prep(img: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]
        scale = min(1.0, max_dim / max(h, w, 1))
        return cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))),
                          interpolation=cv2.INTER_AREA)

    a, b = _prep(a), _prep(b)
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]))

    hsv_a = cv2.cvtColor(a, cv2.COLOR_BGR2HSV)
    hsv_b = cv2.cvtColor(b, cv2.COLOR_BGR2HSV)
    hist_a = cv2.calcHist([hsv_a], [0, 1], None, [18, 16], [0, 180, 0, 256])
    hist_b = cv2.calcHist([hsv_b], [0, 1], None, [18, 16], [0, 180, 0, 256])
    cv2.normalize(hist_a, hist_a)
    cv2.normalize(hist_b, hist_b)
    hist_sim = max(float(cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL)), 0.0)

    ga = cv2.resize(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), (32, 32),
                    interpolation=cv2.INTER_AREA).astype(np.float32)
    gb = cv2.resize(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), (32, 32),
                    interpolation=cv2.INTER_AREA).astype(np.float32)
    struct_sim = 1.0 - float(np.mean(np.abs(ga - gb))) / 255.0

    return 0.5 * hist_sim + 0.5 * struct_sim


def classify_cut_transitions(
    video_path: Path,
    cut_times: list[float],
    duration_sec: float,
    offset_sec: float = 1.0,
    similarity_threshold: float = 0.55,
) -> list[dict]:
    """Label each hard cut as within_scene or scene_change.

    For every cut, compare a frame ~offset_sec before with one ~offset_sec
    after. The window is clamped to half the distance to the neighboring cuts
    so the sampled frames belong to the shots adjacent to THIS cut, with a
    0.15s minimum standoff from the cut itself to avoid transition frames.

    Returns [{timestamp_sec, similarity, label}], label in
    {"within_scene", "scene_change", "unknown"}.
    """
    if not cut_times:
        return []
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return []

    prev_bounds = [0.0] + list(cut_times[:-1])
    next_bounds = list(cut_times[1:]) + [max(duration_sec, cut_times[-1] + 1.0)]
    results: list[dict] = []

    for t, pb, nb in zip(cut_times, prev_bounds, next_bounds):
        # Stay strictly inside the adjacent shots. The 0.15s standoff avoids
        # sampling transition frames, but must never exceed half the distance
        # to the neighbouring cut — otherwise on shots under ~0.3s it would
        # sample ACROSS that cut and compare the wrong pair of shots.
        # Clamp order matters: staying inside the shot wins over the standoff.
        half_b = max((t - pb) / 2.0, 0.0)
        half_a = max((nb - t) / 2.0, 0.0)
        off_b = min(max(min(offset_sec, half_b), 0.15), half_b)
        off_a = min(max(min(offset_sec, half_a), 0.15), half_a)
        try:
            fa = _grab_frame(cap, t - off_b)
            fb = _grab_frame(cap, t + off_a)
            if fa is None or fb is None:
                results.append({"timestamp_sec": round(t, 3),
                                "similarity": None, "label": "unknown"})
                continue
            sim = _frame_similarity(fa, fb)
        except cv2.error:
            results.append({"timestamp_sec": round(t, 3),
                            "similarity": None, "label": "unknown"})
            continue
        results.append({
            "timestamp_sec": round(t, 3),
            "similarity": round(sim, 3),
            "label": "within_scene" if sim >= similarity_threshold
                     else "scene_change",
        })

    cap.release()
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_cut_metrics(
    video_path: Path,
    threshold: float,
    duration_sec: float,
    detect_dissolves: bool = False,
    dissolve_noise_floor: float = 3.0,
    dissolve_min_frames: int = 15,
    classify_cuts_enabled: bool = False,
    classify_offset_sec: float = 1.0,
    scene_change_similarity_threshold: float = 0.55,
) -> tuple[ShotLengthMetrics, ScenePacingMetrics]:
    """
    Detect scene cuts and return shot-length and pacing metrics.

    Args:
        video_path:           Path to the video file.
        threshold:            ContentDetector sensitivity (lower = more hard cuts).
        duration_sec:         Pre-computed video duration in seconds.
        detect_dissolves:     If True, run the secondary dissolve detection pass.
        dissolve_noise_floor: Minimum content score to consider as a dissolve frame.
        dissolve_min_frames:  Minimum consecutive frames required to call it a dissolve.
        classify_cuts_enabled: If True, label each cut within_scene vs scene_change.
        classify_offset_sec:  How far from the cut to sample comparison frames.
        scene_change_similarity_threshold: Below this similarity = scene_change.

    Returns:
        (ShotLengthMetrics, ScenePacingMetrics)
    """
    scene_list = detect(str(video_path), ContentDetector(threshold=threshold))

    duration_min = max(duration_sec / 60.0, 1e-6)

    if not scene_list:
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

    durations = np.array([end.seconds - start.seconds for start, end in scene_list])
    cut_times = [start.seconds for start, _end in scene_list[1:]]

    mean_sec      = float(np.mean(durations))
    shots_per_min = len(durations) / duration_min
    cuts_per_min  = len(cut_times) / duration_min
    shot_length_cv = float(np.std(durations) / mean_sec) if mean_sec > 0 else 0.0

    window_sec = 30.0
    n_windows = max(1, math.ceil(duration_sec / window_sec))
    timeline = [
        float(sum(1 for t in cut_times if i * window_sec <= t < (i + 1) * window_sec))
        for i in range(n_windows)
    ]

    dissolve_list: list[dict] = []
    dissolves_per_min = 0.0

    if detect_dissolves:
        frame_scores  = _compute_frame_scores(video_path)
        dissolve_list = _find_dissolves(
            frame_scores,
            hard_cut_times_sec=cut_times,
            noise_floor=dissolve_noise_floor,
            hard_threshold=threshold,
            min_frames=dissolve_min_frames,
        )
        dissolves_per_min = len(dissolve_list) / duration_min

    classifications: list[dict] = []
    scene_changes_per_min = 0.0
    within_scene_cut_fraction = 0.0

    if classify_cuts_enabled and cut_times:
        classifications = classify_cut_transitions(
            video_path, cut_times, duration_sec,
            offset_sec=classify_offset_sec,
            similarity_threshold=scene_change_similarity_threshold,
        )
        n_change = sum(1 for c in classifications if c["label"] == "scene_change")
        n_within = sum(1 for c in classifications if c["label"] == "within_scene")
        labeled  = n_change + n_within
        scene_changes_per_min = n_change / duration_min
        within_scene_cut_fraction = n_within / labeled if labeled else 0.0

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
            dissolves_per_min=round(dissolves_per_min, 3),
            dissolve_timestamps=dissolve_list,
            scene_changes_per_min=round(scene_changes_per_min, 3),
            within_scene_cut_fraction=round(within_scene_cut_fraction, 3),
            cut_classifications=classifications,
        ),
    )
