"""Reproducible 30-second candidate-pool measurement for stimulus studies.

The candidate pass decodes each episode once per measurement family.  It does
not create hundreds of video files.  After the pool has been measured, CMAT
labels relative thirds and proposes the six non-overlapping matched contrasts
specified by the Option 3.5 study design.  Only the twelve selected finalists
need to be exported as standalone clips.
"""

from __future__ import annotations

import csv
import copy
import hashlib
import itertools
import json
import math
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import cv2
import numpy as np

from . import constructs as C
from . import recipes as R
from .config_loader import load_config
from .engine import analyze_episode
from .ffmpeg_path import ffmpeg_exe
from .measurements import (
    describe_selection,
    get_measurement,
    measurement_fingerprint,
    normalize_config,
    selection,
)
from .metrics_audio import compute_windowed_audio_metrics
from .metrics_cuts import detect_cut_times
from .metrics_frames import compute_windowed_motion
from .show_index import VIDEO_EXTENSIONS


WORKFLOW_VERSION = "1.2.0"
FEATURES = ("cuts", "motion", "audio")
STUDY_RECIPE_MEASURES = {
    "cuts": "hard_cuts_per_min",
    "motion": "motion_mean",
    "audio": "audio_rms_mean",
}
FEATURE_VALUE = {
    "cuts": "cuts_per_min",
    "motion": "motion_mean",
    "audio": "audio_rms_mean",
}
FEATURE_LABEL = {
    "cuts": "cuts_level",
    "motion": "motion_level",
    "audio": "audio_level",
}
FEATURE_PERCENTILE = {
    "cuts": "cuts_percentile",
    "motion": "motion_percentile",
    "audio": "audio_percentile",
}
_NO_WINDOW = (
    {"creationflags": subprocess.CREATE_NO_WINDOW}
    if sys.platform == "win32" else {}
)


def config_from_analysis_recipe(
    recipe: R.Recipe,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the exact raw-measurement config pinned by a study recipe.

    The clip selector uses the three measures separately; recipe transforms,
    ranges, weights and missing-data policies do not enter pair selection.
    The method and pinned parameters do. Motion additionally requires the
    namespaced shared-sampling settings recorded by ``recipes.pin_parameters``.
    """
    cfg = normalize_config(copy.deepcopy(config or load_config()))
    missing = [
        measure_key for measure_key in STUDY_RECIPE_MEASURES.values()
        if recipe.binding(measure_key) is None
    ]
    if missing:
        raise ValueError(
            f"Analysis recipe {recipe.citation()} is missing required "
            f"measure binding(s): {', '.join(missing)}"
        )

    for measure_key in STUDY_RECIPE_MEASURES.values():
        binding = recipe.binding(measure_key)
        assert binding is not None
        method = C.get_method(binding.measure_key, binding.method_key)
        if method is None:
            raise ValueError(
                f"Analysis recipe {recipe.citation()} names unavailable method "
                f"{binding.method_key!r} for {binding.measure_key!r}"
            )
        if method.kind != C.AUTOMATED:
            raise ValueError(
                f"Study clip measurement requires an automated method for "
                f"{binding.measure_key!r}; the recipe selects {method.label}"
            )
        spec = get_measurement(method.measurement_key)
        tool = spec.tool(method.tool_key) if spec else None
        if tool is None or not tool.is_available():
            raise ValueError(
                f"Analysis recipe method is not available: {method.label}"
            )

        direct_params = {
            key: value for key, value in binding.parameters.items()
            if "." not in key
        }
        cfg["measurements"][method.measurement_key] = {
            "tool": method.tool_key,
            "params": direct_params,
            **({"enabled": True} if spec and spec.can_disable else {}),
        }

    motion = recipe.binding(STUDY_RECIPE_MEASURES["motion"])
    assert motion is not None
    sampling_tool = motion.parameters.get("sampling.tool")
    sampling_fps = motion.parameters.get("sampling.sample_fps")
    if sampling_tool is None or sampling_fps is None:
        raise ValueError(
            f"Analysis recipe {recipe.citation()} does not pin motion's shared "
            f"sampling.tool and sampling.sample_fps. Open the recipe and "
            f"Re-pin the Motion binding before using it for this study."
        )
    cfg["measurements"]["sampling"] = {
        "tool": sampling_tool,
        "params": {"sample_fps": sampling_fps},
    }
    cfg = normalize_config(cfg)

    # Normalization coerces values to the registry's supported bounds. Refuse
    # a recipe whose requested values did not survive that process rather than
    # silently running a nearby configuration under the recipe's citation.
    for measure_key in STUDY_RECIPE_MEASURES.values():
        binding = recipe.binding(measure_key)
        assert binding is not None
        actual = R.pin_parameters(
            binding.measure_key, binding.method_key, cfg)
        if actual != binding.parameters:
            raise ValueError(
                f"Analysis recipe {recipe.citation()} pins unsupported or "
                f"incomplete parameters for {binding.measure_key}: "
                f"requested {binding.parameters}, usable {actual}"
            )
    return cfg


def list_candidate_videos(source_dir: Path, recursive: bool = True) -> list[Path]:
    """Return supported source videos in stable relative-path order."""
    source_dir = Path(source_dir)
    iterator = source_dir.rglob("*") if recursive else source_dir.iterdir()
    return sorted(
        (p for p in iterator
         if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS),
        key=lambda p: p.relative_to(source_dir).as_posix().lower(),
    )


def _duration(video_path: Path) -> float:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"Could not open video file: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    if fps <= 0 or frames <= 0:
        raise RuntimeError(f"Could not read video duration: {video_path}")
    return frames / fps


def _clock(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _source_key(relative_path: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9]+", "_", Path(relative_path).stem).strip("_")
    digest = hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:8]
    return f"{stem[:48]}_{digest}"


def measure_video_windows(
    video_path: Path,
    source_dir: Path,
    config: dict[str, Any],
    window_sec: float = 30.0,
    include_partial: bool = False,
    exclude_first_sec: float = 0.0,
    exclude_last_sec: float = 0.0,
    status_cb: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    """Measure contiguous windows of one video without materializing clips."""
    if window_sec <= 0:
        raise ValueError("window_sec must be greater than zero")
    if exclude_first_sec < 0 or exclude_last_sec < 0:
        raise ValueError("leading/trailing exclusions cannot be negative")

    cfg = normalize_config(config)
    duration_sec = _duration(video_path)
    analysis_start = min(exclude_first_sec, duration_sec)
    available_end = max(0.0, duration_sec - exclude_last_sec)
    available_duration = available_end - analysis_start
    if available_duration <= 0:
        raise ValueError(
            f"Exclusions remove the entire {duration_sec:.3f}s episode: "
            f"first {exclude_first_sec:g}s + last {exclude_last_sec:g}s"
        )
    full_count = int(available_duration // window_sec)
    remainder = available_duration - full_count * window_sec
    window_count = full_count + (
        1 if include_partial and remainder > 1e-6 else 0
    )
    if window_count == 0:
        return []
    measured_duration = full_count * window_sec + (
        remainder if include_partial and remainder > 1e-6 else 0.0
    )
    analysis_end = analysis_start + measured_duration

    transition_tool, transition_params, _ = selection(cfg, "transitions")
    sampling_tool, sampling_params, _ = selection(cfg, "sampling")
    motion_tool, _motion_params, _ = selection(cfg, "motion")
    if status_cb:
        status_cb(f"{video_path.name}: detecting cuts")
    cut_times = detect_cut_times(
        video_path,
        duration_sec,
        tool=transition_tool.key,
        tool_params=transition_params,
        status_cb=status_cb,
        start_sec=analysis_start,
        end_sec=analysis_end,
    )

    if status_cb:
        status_cb(f"{video_path.name}: measuring motion")
    motion = compute_windowed_motion(
        video_path,
        sample_fps=float(sampling_params.get("sample_fps", 2.0)),
        duration_sec=duration_sec,
        window_sec=window_sec,
        motion_method=motion_tool.key,
        include_partial=include_partial,
        start_sec=analysis_start,
        end_sec=analysis_end,
    )

    if status_cb:
        status_cb(f"{video_path.name}: measuring audio intensity")
    audio = compute_windowed_audio_metrics(
        video_path, window_sec, window_count,
        start_sec=analysis_start, end_sec=analysis_end,
    )

    relpath = video_path.relative_to(source_dir).as_posix()
    source_key = _source_key(relpath)
    fingerprint = measurement_fingerprint(cfg)
    rows: list[dict[str, Any]] = []
    for idx in range(window_count):
        start = analysis_start + idx * window_sec
        end = min(analysis_end, start + window_sec)
        clip_duration = end - start
        # A cut exactly at the first frame is not perceived as a transition in
        # the standalone clip.  A cut before the exclusive end is.
        cut_count = sum(1 for t in cut_times if start + 1e-6 < t < end - 1e-6)
        audio_metrics = audio[idx]
        motion_metrics = motion[idx]
        clip_id = f"{source_key}__{int(round(start * 1000)):09d}ms"
        rows.append({
            "clip_id": clip_id,
            "source_file": video_path.name,
            "source_relpath": relpath,
            "source_path": str(video_path.resolve()),
            "window_index": idx + 1,
            "start_sec": round(start, 3),
            "end_sec": round(end, 3),
            "start_timecode": _clock(start),
            "end_timecode": _clock(end),
            "duration_sec": round(clip_duration, 3),
            "is_full_window": abs(clip_duration - window_sec) < 1e-3,
            "episode_duration_sec": round(duration_sec, 3),
            "excluded_first_sec": round(exclude_first_sec, 3),
            "excluded_last_sec": round(exclude_last_sec, 3),
            "measured_range_start_sec": round(analysis_start, 3),
            "measured_range_end_sec": round(analysis_end, 3),
            "cut_count": cut_count,
            "cuts_per_min": round(cut_count / max(clip_duration / 60.0, 1e-9), 3),
            "motion_mean": motion_metrics.mean,
            "motion_peak": motion_metrics.peak,
            "audio_rms_mean": (
                audio_metrics.rms_mean if audio_metrics.available else None
            ),
            "audio_rms_peak": (
                audio_metrics.rms_peak if audio_metrics.available else None
            ),
            "audio_dynamic_range_db": (
                audio_metrics.dynamic_range_db if audio_metrics.available else None
            ),
            "audio_available": audio_metrics.available,
            "measurement_fingerprint": fingerprint,
            "sampling_method": sampling_tool.key,
            "motion_method": motion_tool.key,
            "transition_method": transition_tool.key,
        })
    return rows


def _average_percentiles(rows: list[dict[str, Any]], key: str) -> dict[str, float]:
    values = sorted(
        ((float(row[key]), row["clip_id"]) for row in rows),
        key=lambda item: (item[0], item[1]),
    )
    n = len(values)
    if n == 1:
        return {values[0][1]: 0.5}
    out: dict[str, float] = {}
    idx = 0
    while idx < n:
        stop = idx + 1
        while stop < n and values[stop][0] == values[idx][0]:
            stop += 1
        average_rank = (idx + stop - 1) / 2.0
        percentile = average_rank / (n - 1)
        for pos in range(idx, stop):
            out[values[pos][1]] = round(percentile, 6)
        idx = stop
    return out


def _relative_level(value: float, low: float, high: float) -> str:
    # When both thresholds collapse onto one tied value, calling that value
    # both low and high would manufacture a contrast that is not in the data.
    if math.isclose(low, high):
        if value < low:
            return "low"
        if value > high:
            return "high"
        return "middle"
    if value <= low:
        return "low"
    if value >= high:
        return "high"
    return "middle"


def assign_relative_profiles(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, float]]:
    """Add thirds, percentiles, and a human-readable profile to each row."""
    usable = [row for row in rows if row.get("audio_rms_mean") is not None]
    if not usable:
        return {}

    thresholds: dict[str, dict[str, float]] = {}
    for feature in FEATURES:
        value_key = FEATURE_VALUE[feature]
        values = np.array([float(row[value_key]) for row in usable])
        low, high = np.quantile(values, [1 / 3, 2 / 3])
        thresholds[feature] = {
            "bottom_third_max": round(float(low), 8),
            "top_third_min": round(float(high), 8),
        }
        percentiles = _average_percentiles(usable, value_key)
        for row in usable:
            row[FEATURE_LABEL[feature]] = _relative_level(
                float(row[value_key]), float(low), float(high)
            )
            row[FEATURE_PERCENTILE[feature]] = percentiles[row["clip_id"]]

    for row in rows:
        if row not in usable:
            row["cuts_level"] = row["motion_level"] = row["audio_level"] = "unavailable"
            row["cuts_percentile"] = row["motion_percentile"] = row["audio_percentile"] = None
        row["feature_profile"] = (
            f"{row['cuts_level']} cuts | {row['motion_level']} motion | "
            f"{row['audio_level']} audio intensity"
        )
    return thresholds


def build_pair_candidates(
    rows: list[dict[str, Any]],
    control_penalty: float = 0.75,
    require_different_source: bool = True,
    limit_per_feature: int = 250,
) -> dict[str, list[dict[str, Any]]]:
    """Rank low/high contrasts for each target feature.

    Scores use relative ranks, so cuts, motion, and RMS can be compared without
    pretending their raw units share a scale.  A large target separation helps;
    differences on the two control features are penalized.
    """
    output: dict[str, list[dict[str, Any]]] = {}
    for feature in FEATURES:
        low_rows = [r for r in rows if r.get(FEATURE_LABEL[feature]) == "low"]
        high_rows = [r for r in rows if r.get(FEATURE_LABEL[feature]) == "high"]
        controls = [f for f in FEATURES if f != feature]
        candidates: list[dict[str, Any]] = []
        for low in low_rows:
            for high in high_rows:
                if require_different_source and low["source_path"] == high["source_path"]:
                    continue
                target_gap = (
                    float(high[FEATURE_PERCENTILE[feature]])
                    - float(low[FEATURE_PERCENTILE[feature]])
                )
                control_gaps = [
                    abs(float(high[FEATURE_PERCENTILE[c]])
                        - float(low[FEATURE_PERCENTILE[c]]))
                    for c in controls
                ]
                score = target_gap - control_penalty * sum(control_gaps)
                candidates.append({
                    "feature": feature,
                    "low": low,
                    "high": high,
                    "score": score,
                    "target_percentile_gap": target_gap,
                    "control_1": controls[0],
                    "control_1_percentile_gap": control_gaps[0],
                    "control_2": controls[1],
                    "control_2_percentile_gap": control_gaps[1],
                })
        candidates.sort(key=lambda p: (
            -p["score"],
            -p["target_percentile_gap"],
            p["low"]["clip_id"],
            p["high"]["clip_id"],
        ))
        output[feature] = candidates[:limit_per_feature]
    return output


def _feature_bundles(
    candidates: list[dict[str, Any]],
    pair_pool: int = 80,
    bundle_limit: int = 350,
) -> list[dict[str, Any]]:
    bundles: list[dict[str, Any]] = []
    for first, second in itertools.combinations(candidates[:pair_pool], 2):
        ids = {
            first["low"]["clip_id"], first["high"]["clip_id"],
            second["low"]["clip_id"], second["high"]["clip_id"],
        }
        if len(ids) != 4:
            continue
        bundles.append({
            "pairs": [first, second],
            "ids": ids,
            "score": first["score"] + second["score"],
        })
    bundles.sort(key=lambda b: -b["score"])
    return bundles[:bundle_limit]


def select_matched_pairs(
    candidates: dict[str, list[dict[str, Any]]],
    max_clips_per_source: int | None = 2,
    beam_width: int = 600,
) -> list[dict[str, Any]]:
    """Choose two independent pairs per feature with no clip reuse."""
    states = [{"pairs": [], "ids": set(), "score": 0.0}]
    for feature in FEATURES:
        bundles = _feature_bundles(candidates.get(feature, []))
        if not bundles:
            return []
        next_states: list[dict[str, Any]] = []
        for state in states:
            for bundle in bundles:
                if state["ids"] & bundle["ids"]:
                    continue
                proposed = state["pairs"] + bundle["pairs"]
                if max_clips_per_source is not None:
                    source_counts = Counter(
                        row["source_path"]
                        for pair in proposed
                        for row in (pair["low"], pair["high"])
                    )
                    if source_counts and max(source_counts.values()) > max_clips_per_source:
                        continue
                next_states.append({
                    "pairs": proposed,
                    "ids": state["ids"] | bundle["ids"],
                    "score": state["score"] + bundle["score"],
                })
        if not next_states:
            return []
        next_states.sort(key=lambda state: -state["score"])
        states = next_states[:beam_width]

    selected = states[0]["pairs"]
    ordered: list[dict[str, Any]] = []
    for feature in FEATURES:
        feature_pairs = [p for p in selected if p["feature"] == feature]
        feature_pairs.sort(key=lambda p: (
            -p["score"], p["low"]["clip_id"], p["high"]["clip_id"]
        ))
        ordered.extend(feature_pairs)
    return ordered


def _cache_signature(
    path: Path,
    config: dict[str, Any],
    window_sec: float,
    include_partial: bool,
    exclude_first_sec: float,
    exclude_last_sec: float,
) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "measurement_fingerprint": measurement_fingerprint(config),
        "window_sec": window_sec,
        "include_partial": include_partial,
        "exclude_first_sec": exclude_first_sec,
        "exclude_last_sec": exclude_last_sec,
        "workflow_version": WORKFLOW_VERSION,
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp.replace(path)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _flat_pair(pair: dict[str, Any], pair_number: int) -> dict[str, Any]:
    feature = pair["feature"]
    low = pair["low"]
    high = pair["high"]
    row: dict[str, Any] = {
        "pair_id": f"{feature.upper()}_{pair_number}",
        "target_feature": feature,
        "match_score": round(pair["score"], 6),
        "target_percentile_gap": round(pair["target_percentile_gap"], 6),
        "control_1": pair["control_1"],
        "control_1_percentile_gap": round(pair["control_1_percentile_gap"], 6),
        "control_2": pair["control_2"],
        "control_2_percentile_gap": round(pair["control_2_percentile_gap"], 6),
    }
    for side, clip in (("low", low), ("high", high)):
        for key in (
            "clip_id", "source_relpath", "source_path", "start_sec",
            "start_timecode", "end_timecode", "cuts_per_min", "motion_mean",
            "audio_rms_mean", "feature_profile",
        ):
            row[f"{side}_{key}"] = clip.get(key)
    return row


def _selected_clip_rows(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels = {
        "cuts": (("Clip A1", "Clip B1"), ("Clip A2", "Clip B2")),
        "motion": (("Clip C1-L", "Clip C1-H"), ("Clip C2-L", "Clip C2-H")),
        "audio": (("Clip D1-L", "Clip D1-H"), ("Clip D2-L", "Clip D2-H")),
    }
    out: list[dict[str, Any]] = []
    counts = Counter()
    for pair in pairs:
        feature = pair["feature"]
        pair_idx = counts[feature]
        counts[feature] += 1
        low_label, high_label = labels[feature][pair_idx]
        for role, label in (("low", low_label), ("high", high_label)):
            row = dict(pair[role])
            row["study_label"] = label
            row["target_feature"] = feature
            row["target_level"] = role
            row["pair_id"] = f"{feature.upper()}_{pair_idx + 1}"
            out.append(row)
    return out


def _candidate_pair_rows(
    candidates: dict[str, list[dict[str, Any]]],
    per_feature: int = 100,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for feature in FEATURES:
        for rank, pair in enumerate(candidates.get(feature, [])[:per_feature], 1):
            row = _flat_pair(pair, rank)
            row["rank_for_feature"] = rank
            rows.append(row)
    return rows


def run_candidate_pool(
    source_dir: Path,
    output_dir: Path,
    config: dict[str, Any] | None = None,
    window_sec: float = 30.0,
    include_partial: bool = False,
    exclude_first_sec: float = 0.0,
    exclude_last_sec: float = 0.0,
    recursive: bool = True,
    resume: bool = True,
    max_files: int | None = None,
    analysis_recipe: R.Recipe | None = None,
    status_cb: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Measure a folder, write browseable outputs, and return the run summary."""
    source_dir = Path(source_dir).resolve()
    output_dir = Path(output_dir).resolve()
    if not source_dir.is_dir():
        raise ValueError(f"Source folder does not exist: {source_dir}")
    if exclude_first_sec < 0 or exclude_last_sec < 0:
        raise ValueError("leading/trailing exclusions cannot be negative")
    base_cfg = normalize_config(config) if config else load_config()
    cfg = (
        config_from_analysis_recipe(analysis_recipe, base_cfg)
        if analysis_recipe is not None else base_cfg
    )
    videos = list_candidate_videos(source_dir, recursive=recursive)
    if max_files is not None:
        videos = videos[:max_files]
    if not videos:
        raise ValueError(f"No supported video files found in {source_dir}")

    cache_dir = output_dir / "episode_measurements"
    cache_dir.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for index, video in enumerate(videos, 1):
        relpath = video.relative_to(source_dir).as_posix()
        if status_cb:
            status_cb(f"Episode {index}/{len(videos)}: {relpath}")
        signature = _cache_signature(
            video, cfg, window_sec, include_partial,
            exclude_first_sec, exclude_last_sec,
        )
        cache_path = cache_dir / f"{_source_key(relpath)}.json"
        payload: dict[str, Any] | None = None
        if resume and cache_path.exists():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                if cached.get("signature") == signature:
                    payload = cached
                    if status_cb:
                        status_cb(f"Episode {index}/{len(videos)}: cache hit")
            except (OSError, ValueError):
                payload = None
        if payload is None:
            try:
                rows = measure_video_windows(
                    video, source_dir, cfg, window_sec, include_partial,
                    exclude_first_sec, exclude_last_sec, status_cb,
                )
                payload = {"signature": signature, "rows": rows, "error": None}
            except Exception as exc:
                payload = {
                    "signature": signature,
                    "rows": [],
                    "error": str(exc),
                }
            _write_json(cache_path, payload)
        all_rows.extend(payload.get("rows") or [])
        if payload.get("error"):
            failures.append({"source_relpath": relpath, "error": payload["error"]})

    thresholds = assign_relative_profiles(all_rows)
    pair_candidates = build_pair_candidates(all_rows)
    selected_pairs = select_matched_pairs(pair_candidates)
    # A smaller pool may be scientifically useful for testing even when the
    # two-clips-per-episode diversity guard cannot be satisfied.
    diversity_relaxed = False
    if not selected_pairs:
        selected_pairs = select_matched_pairs(
            pair_candidates, max_clips_per_source=None
        )
        diversity_relaxed = bool(selected_pairs)

    pair_rows = [
        _flat_pair(pair, idx)
        for feature in FEATURES
        for idx, pair in enumerate(
            (p for p in selected_pairs if p["feature"] == feature), 1
        )
    ]
    selected_rows = _selected_clip_rows(selected_pairs)
    _write_csv(output_dir / "candidates.csv", all_rows)
    _write_csv(
        output_dir / "pair_candidates.csv",
        _candidate_pair_rows(pair_candidates),
    )
    _write_csv(output_dir / "matched_pairs.csv", pair_rows)
    _write_csv(output_dir / "selected_clips.csv", selected_rows)
    _write_csv(output_dir / "failures.csv", failures)

    manifest = {
        "workflow": "CMAT 30-second study clip candidate selection",
        "workflow_version": WORKFLOW_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(source_dir),
        "output_dir": str(output_dir),
        "window_sec": window_sec,
        "include_partial_windows": include_partial,
        "exclude_first_sec_per_episode": exclude_first_sec,
        "exclude_last_sec_per_episode": exclude_last_sec,
        "recursive": recursive,
        "source_file_count": len(videos),
        "candidate_clip_count": len(all_rows),
        "failed_source_count": len(failures),
        "matched_pair_count": len(selected_pairs),
        "selected_clip_count": len(selected_rows),
        "selection_diversity_guard_relaxed": diversity_relaxed,
        "relative_level_definition": (
            "Bottom and top thirds of this measured candidate pool; ties at "
            "the one-third and two-thirds thresholds remain tied."
        ),
        "pair_score_definition": (
            "Target percentile separation minus 0.75 times the sum of the two "
            "control-feature percentile separations."
        ),
        "thresholds": thresholds,
        "measurement_fingerprint": measurement_fingerprint(cfg),
        "measurement_tools": describe_selection(cfg),
        "analysis_recipe": (
            {
                "citation": analysis_recipe.citation(),
                "path": str(analysis_recipe.path.resolve())
                if analysis_recipe.path else None,
                "snapshot": analysis_recipe.to_dict(),
                "used_bindings": list(STUDY_RECIPE_MEASURES.values()),
                "note": (
                    "Clip selection uses each bound raw measure separately; "
                    "recipe transforms, weights, and composite score are not used."
                ),
            }
            if analysis_recipe is not None else None
        ),
        "config": cfg,
        "source_files": [
            {
                "relative_path": video.relative_to(source_dir).as_posix(),
                "absolute_path": str(video.resolve()),
                "size": video.stat().st_size,
                "mtime_ns": video.stat().st_mtime_ns,
            }
            for video in videos
        ],
        "limitations": [
            "Pair suggestions are screening aids and require human scene/content review.",
            "Audio intensity is linear RMS, not perceptual loudness or LUFS.",
            "Naturally occurring clips support associational, not causal, claims.",
            "Final exported clips must be re-measured because transcoding can change values.",
        ],
    }
    _write_json(output_dir / "manifest.json", manifest)
    return {
        "manifest": manifest,
        "candidates": all_rows,
        "pair_candidates": pair_candidates,
        "selected_pairs": selected_pairs,
        "selected_clips": selected_rows,
        "failures": failures,
        "config": cfg,
    }


def export_selected_clips(
    selected_rows: Iterable[dict[str, Any]],
    output_dir: Path,
    config: dict[str, Any] | None = None,
    overwrite: bool = False,
    status_cb: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    """Render exact standalone finalists, then re-measure participant files."""
    cfg = normalize_config(config) if config else load_config()
    output_dir = Path(output_dir).resolve()
    clips_dir = output_dir / "finalists"
    measurements_dir = output_dir / "finalist_measurements"
    clips_dir.mkdir(parents=True, exist_ok=True)
    measurements_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    for row in selected_rows:
        label = str(row["study_label"])
        destination = clips_dir / f"{label}.mp4"
        if destination.exists() and not overwrite:
            if status_cb:
                status_cb(f"{label}: existing export retained")
        else:
            if status_cb:
                status_cb(f"{label}: exporting exact clip")
            command = [
                ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
                "-y" if overwrite else "-n",
                "-ss", f"{float(row['start_sec']):.3f}",
                "-i", str(row["source_path"]),
                "-t", f"{float(row['duration_sec']):.3f}",
                "-map", "0:v:0", "-map", "0:a:0?",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                str(destination),
            ]
            completed = subprocess.run(
                command, capture_output=True, timeout=900, **_NO_WINDOW
            )
            if completed.returncode != 0:
                error = completed.stderr.decode(errors="replace")[-500:]
                results.append({
                    "study_label": label,
                    "export_path": str(destination),
                    "status": "failed",
                    "error": error,
                })
                continue

        if status_cb:
            status_cb(f"{label}: re-measuring exported participant file")
        measured = analyze_episode(destination, config=cfg)
        _write_json(
            measurements_dir / f"{label}.json",
            measured.to_dict(),
        )
        if measured.status == "failed":
            results.append({
                "study_label": label,
                "export_path": str(destination),
                "status": "failed",
                "error": measured.error,
            })
            continue
        metrics = measured.metrics
        results.append({
            "study_label": label,
            "pair_id": row.get("pair_id"),
            "target_feature": row.get("target_feature"),
            "target_level": row.get("target_level"),
            "export_path": str(destination),
            "status": "ok",
            "duration_sec": measured.duration_sec,
            "cuts_per_min": metrics.scene_pacing.cuts_per_min,
            "motion_mean": metrics.motion.mean,
            "audio_rms_mean": (
                metrics.audio.rms_mean if metrics.audio.available else None
            ),
            "measurement_fingerprint": measured.measurement_fingerprint,
        })

    _write_csv(output_dir / "finalist_measurements.csv", results)
    return results
