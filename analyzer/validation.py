"""
Transition-detection validation logic — pure functions, zero GUI imports.

This module is the single source of truth for the validation workflow:

  write_template()      blank manual-coding CSV (refuses to overwrite)
  export_detections()   hard cuts + dissolves -> detections CSV + manifest
  compare_detections()  score detections against manual coding (P/R/F1)
  run_sweep()           grid-search dissolve params against manual coding
  aggregate_summary()   combine comparison CSVs across episodes
  episode_status()      where an episode is in the workflow
  load/save_match_detail()  read + write failure_reason annotations

The CLI (validate_cuts.py) and the GUI Validation tab are both thin layers
over these functions. Detection itself is imported from metrics_cuts so
validation always measures the same detector the analysis engine ships.
"""

from __future__ import annotations

import csv
import json
import math
import subprocess
from datetime import date
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

# PySceneDetect is imported inside load_hard_cuts, not here. It costs ~0.64s to
# load and is needed only when detection actually runs, but this module is
# reached from analyzer.pipeline (via trials) while the interface builds its
# first screen — so a module-level import made it part of application STARTUP.
# The optional TransNetV2 detector in the same function is deferred for the
# same reason.

from .metrics_cuts import (_compute_frame_scores, _find_dissolves,
                           classify_cut_transitions)
from .config_loader import _base_dir


TRANSITION_TYPES = {"hard_cut", "dissolve", "fade_in", "fade_out", "other"}

# scene_relation column: within-scene vs scene-change (cut-classifier ground truth)
_SCENE_WITHIN = {"within", "within_scene", "in", "in_scene", "same", "same_scene"}
_SCENE_CHANGE = {"change", "scene_change", "scene", "new", "new_scene",
                 "out", "out_scene"}


def _norm_scene_relation(value: str) -> str:
    """Normalize a scene_relation cell to 'within' | 'change' | '' (blank/unknown)."""
    v = (value or "").strip().lower()
    if not v:
        return ""
    if v in _SCENE_WITHIN:
        return "within"
    if v in _SCENE_CHANGE:
        return "change"
    return v  # unrecognized — leave as-is so a warning can surface it

# Controlled vocabulary for failure_reason annotation.
# (tag, human explanation) — keep tags EXACTLY these strings so they
# aggregate across episodes. See validation/VALIDATION_LOG.md.
FAILURE_TAGS: list[tuple[str, str]] = [
    ("no_fade_class",          "Fade found by the tool but labeled hard_cut — the detector has no fade category. Expected, not a bug."),
    ("post_cut_motion",        "Residual motion just after a real hard cut, mislabeled as a dissolve (~1-2s offset)."),
    ("double_fire",            "The detector fired twice for one real transition."),
    ("missed_dissolve",        "A real dissolve the detector failed to find."),
    ("missed_dissolve_snow",   "Missed dissolve in a snow-heavy scene (snow raises the baseline so the blend never clears the noise floor)."),
    ("missed_dissolve_gradual","Missed dissolve that is very slow/gentle."),
    ("missed_cut",             "A real hard cut the detector failed to find."),
    ("missed_cut_lowcontrast", "Missed cut between visually similar shots (same background/palette) — frame change stayed under threshold."),
    ("missed_cut_highcontrast","Missed cut despite a clear shot change — anomaly worth investigating."),
    ("false_dissolve_pan",     "Phantom dissolve caused by a camera pan / foreground parallax."),
    ("false_dissolve_zoom",    "Phantom dissolve caused by a zoom."),
    ("false_dissolve_snow",    "Phantom dissolve where snowfall alone was the trigger."),
    ("false_cut_zoom",         "Phantom hard cut caused by a smooth zoom."),
    ("false_cut_motion",       "Phantom hard cut caused by on-screen motion."),
    ("false_cut_pan",          "Phantom hard cut caused by a camera pan."),
    ("false_cut_snow",         "Phantom hard cut triggered by snowfall between real cuts."),
    ("overlay_under_threshold","Graphic/title overlay fade too gradual to detect (codebook Rule 6 case)."),
    ("coding_omission",        "The manual coding missed a real transition — fix the manual CSV and re-compare instead of tagging the tool."),
]


def get_validation_dir() -> Path:
    """Default validation folder: <app base>/validation (created on demand)."""
    return _base_dir() / "validation"


# ── Time helpers ──────────────────────────────────────────────────────────────

def sec_to_hms(s: float) -> str:
    s = int(round(s))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def hms_to_sec(hms: str) -> float:
    parts = [float(p) for p in hms.strip().split(":")]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    raise ValueError(f"Cannot parse timestamp: {hms!r}")


def parse_time_arg(value: str | float | None) -> float | None:
    """Accept 95, '95', '95.5', '1:35', '0:01:35', '' or None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return hms_to_sec(value)


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=_base_dir(), timeout=5,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


# ── Manual-coding CSV ─────────────────────────────────────────────────────────

def parse_manual_csv(path: Path, warn_cb: Callable[[str], None] | None = None) -> list[dict]:
    """Load a manually coded CSV. Accepts timestamp_hms or timestamp_sec."""
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader, 2):
            t_hms = (row.get("timestamp_hms") or "").strip()
            t_sec = (row.get("timestamp_sec") or "").strip()
            if not t_hms and not t_sec:
                continue
            try:
                ts = float(t_sec) if t_sec else hms_to_sec(t_hms)
            except ValueError as exc:
                if warn_cb:
                    warn_cb(f"row {i} skipped — {exc}")
                continue
            t_type = (row.get("type") or "").strip().lower()
            if t_type not in TRANSITION_TYPES and warn_cb:
                warn_cb(f"row {i} — unknown type {t_type!r}, kept as-is")
            rel = _norm_scene_relation(row.get("scene_relation", ""))
            if rel and rel not in ("within", "change") and warn_cb:
                warn_cb(f"row {i} — unrecognized scene_relation {rel!r} "
                        f"(use within/change)")
            rows.append({
                "timestamp_sec": round(ts, 3),
                "timestamp_hms": sec_to_hms(ts),
                "type":          t_type or "unknown",
                "notes":         (row.get("notes") or "").strip(),
                "scene_relation": rel,
            })
    return sorted(rows, key=lambda r: r["timestamp_sec"])


def coded_episode_map(validation_dir: Path | None = None) -> dict[str, dict]:
    """One pass over the coding folder -> {sheet_base: {...}}.

    Built once and reused across many rows (Library tree, Index table) so
    provenance markers don't cost a filesystem glob per episode.
    Values: {"transitions": Path|None, "events": Path|None, "metrics": Path|None}
    """
    vdir = validation_dir or get_validation_dir()
    out: dict[str, dict] = {}
    if not vdir.exists():
        return out

    def _slot(base: str) -> dict:
        return out.setdefault(base, {"transitions": None, "events": None,
                                     "metrics": None})

    for p in vdir.rglob("*_manual.csv"):
        _slot(p.name[: -len("_manual.csv")])["transitions"] = p
    for p in vdir.rglob("*_events.csv"):
        _slot(p.name[: -len("_events.csv")])["events"] = p
    for p in sorted(vdir.rglob("*__handcoded_*.json"),
                    key=lambda q: q.stat().st_mtime):
        _slot(p.name.split("__handcoded_")[0])["metrics"] = p  # newest wins
    return out


def coding_for_stem(stem: str, cmap: dict[str, dict]) -> dict:
    """Look up an episode's coding in a coded_episode_map.

    Exact stem first, then prefix (coders shorten long episode filenames).
    Returns the empty slot shape when nothing is coded.
    """
    if stem in cmap:
        return cmap[stem]
    low = stem.lower()
    best, best_len = None, 0
    for base, slot in cmap.items():
        if len(base) >= 8 and low.startswith(base.lower()) and len(base) > best_len:
            best, best_len = slot, len(base)
    return best or {"transitions": None, "events": None, "metrics": None}


def write_manual_metrics(
    video: Path,
    kind: str,
    metrics: dict[str, Any],
    validation_dir: Path | None = None,
) -> Path:
    """Persist hand-coded metrics so they can be browsed in the Index.

    Kept in the coding folder (never in the .analysis cache) — the cache is
    machine-generated and re-analysis would overwrite human work.
    """
    vdir = episode_dir(video, validation_dir)
    vdir.mkdir(parents=True, exist_ok=True)
    out = vdir / f"{video.stem}__handcoded_{date.today()}.json"
    payload: dict[str, Any] = {}
    if out.exists():  # keep the other kind's metrics from the same day
        try:
            payload = json.loads(out.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
    payload.update({
        "episode": video.name,
        "source": "hand-coded",
        "date": str(date.today()),
        "git_commit": _git_commit(),
        kind: metrics,
    })
    out.write_text(json.dumps(payload, indent=2, default=str),
                   encoding="utf-8")
    return out


def manual_pacing_metrics(
    rows: "list[dict] | Path",
    duration_sec: float = 0.0,
    start: float | str | None = None,
    end: float | str | None = None,
    warn_cb: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Descriptive pacing metrics computed FROM hand coding, not detection.

    The hand-coding path's analysis step. Two families of number are returned
    and they are NOT interchangeable:

    COMPARABLE TO THE AUTOMATED ENGINE (hard cuts only, ceil-binned timeline):
        hard_cuts_per_min, mean_shot_sec, median_shot_sec, shot_length_cv,
        timeline_per_30s
      These mirror compute_cut_metrics(): intervals are measured between HARD
      CUTS, matching PySceneDetect's scene list, and the timeline uses ceil so
      a final partial 30s window is retained.

    HAND-CODING ONLY (no automated counterpart):
        transitions_per_min, inter_transition_* , by_type, scene_* fields
      These count ALL coded transition types, which the automated detector
      does not produce. Do not compare them to automated figures.

    ``rows`` may be a parsed coding list or a path to a coding CSV. When a
    window is given, rates use the window length as the denominator (these
    users typically code a segment, not a whole episode).

    Interval stats use gaps BETWEEN coded events only — the first and last
    shots in a window are truncated by the window edges, so including them
    would bias the mean downward. NOTE this differs from the engine, which
    includes its first and last scene; on a fully coded episode the two will
    therefore differ slightly at the edges.
    """
    if isinstance(rows, (str, Path)):
        rows = parse_manual_csv(Path(rows), warn_cb=warn_cb)

    lo = parse_time_arg(start)
    hi = parse_time_arg(end)
    window = None
    if lo is not None or hi is not None:
        lo = lo if lo is not None else 0.0
        hi = hi if hi is not None else (duration_sec or float("inf"))
        window = (lo, hi)
        rows = [r for r in rows if lo <= r["timestamp_sec"] <= hi]
        span_sec = max(hi - lo, 1e-6)
    else:
        span_sec = max(duration_sec, 1e-6)
    span_min = span_sec / 60.0

    by_type: dict[str, int] = {}
    for r in rows:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1

    n_all = len(rows)
    n_hard = by_type.get("hard_cut", 0)

    def _stats_of(gaps: list[float]) -> tuple[float, float, float]:
        if not gaps:
            return 0.0, 0.0, 0.0
        mean_g = sum(gaps) / len(gaps)
        srt = sorted(gaps)
        mid = len(srt) // 2
        median_g = (srt[mid] if len(srt) % 2 else (srt[mid - 1] + srt[mid]) / 2)
        var = sum((g - mean_g) ** 2 for g in gaps) / len(gaps)   # population SD,
        cv_ = (var ** 0.5) / mean_g if mean_g > 0 else 0.0       # as the engine uses
        return mean_g, median_g, cv_

    def _interval_stats(ts: list[float]) -> tuple[float, float, float]:
        return _stats_of([b - a for a, b in zip(ts, ts[1:])] if len(ts) > 1 else [])

    times = [r["timestamp_sec"] for r in rows]                  # all transitions
    cut_times = [r["timestamp_sec"] for r in rows
                 if r["type"] == "hard_cut"]                    # engine-comparable

    # Engine-comparable SHOT durations. compute_cut_metrics() measures the
    # C+1 scenes PySceneDetect produces for C cuts, INCLUDING the first and
    # last. Measuring only the C-1 interior gaps is not a small difference:
    # one cut at 10s in a 100s episode gives interior mean 0.0 where the
    # engine gives 50.0. So bound the shots by the span edges.
    lo_b = window[0] if window else 0.0
    hi_b = window[1] if window else (duration_sec if duration_sec > 0 else None)
    if hi_b is not None and hi_b != float("inf"):
        bounds = [lo_b] + cut_times + [hi_b]
        shot_durs = [b - a for a, b in zip(bounds, bounds[1:]) if b > a]
        edges_included = True
    else:
        # Span end unknown — cannot bound the final shot. Fall back to interior
        # gaps and say so, rather than silently reporting a different quantity.
        shot_durs = [b - a for a, b in zip(cut_times, cut_times[1:])]
        edges_included = False
    mean_gap, median_gap, cv = _stats_of(shot_durs)

    # Hand-coding only: intervals between transitions of ANY type (interior
    # only; no automated counterpart exists, so edge handling is moot).
    it_mean, it_median, it_cv = _interval_stats(times)

    base = window[0] if window else 0.0
    # ceil, matching compute_cut_metrics — floor would silently drop the cuts
    # in a final partial 30s window.
    n_windows = max(1, math.ceil(span_sec / 30.0))
    timeline = [
        sum(1 for t in cut_times
            if base + i * 30.0 <= t < base + (i + 1) * 30.0)
        for i in range(n_windows)
    ]
    timeline_all = [
        sum(1 for t in times
            if base + i * 30.0 <= t < base + (i + 1) * 30.0)
        for i in range(n_windows)
    ]

    # Scene-relation summary (only over hard cuts that carry a label).
    labeled = [r for r in rows
               if r["type"] == "hard_cut"
               and r.get("scene_relation") in ("within", "change")]
    n_change = sum(1 for r in labeled if r["scene_relation"] == "change")
    n_within = len(labeled) - n_change

    return {
        "n_transitions": n_all,
        "n_hard_cuts": n_hard,
        "by_type": by_type,
        # --- comparable to the automated engine (hard cuts only) ---
        "hard_cuts_per_min": round(n_hard / span_min, 3),
        "mean_shot_sec": round(mean_gap, 3),
        "median_shot_sec": round(median_gap, 3),
        "shot_length_cv": round(cv, 3),
        "shot_edges_included": edges_included,
        "timeline_per_30s": timeline,
        # --- hand-coding only (all transition types; no automated counterpart) ---
        "transitions_per_min": round(n_all / span_min, 3),
        "inter_transition_mean_sec": round(it_mean, 3),
        "inter_transition_median_sec": round(it_median, 3),
        "inter_transition_cv": round(it_cv, 3),
        "timeline_all_types_per_30s": timeline_all,
        "n_scene_labeled": len(labeled),
        "scene_changes_per_min": (round(n_change / span_min, 3)
                                  if labeled else None),
        "within_scene_fraction": (round(n_within / len(labeled), 3)
                                  if labeled else None),
        "window": window,
        "span_min": round(span_min, 3),
    }


def write_template(video: Path | str, validation_dir: Path | None = None) -> Path:
    """Create a blank manual-coding CSV. Raises FileExistsError if present."""
    vdir = validation_dir or get_validation_dir()
    vdir.mkdir(parents=True, exist_ok=True)
    out = vdir / f"{Path(video).stem}_manual.csv"
    if out.exists():
        raise FileExistsError(str(out))
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["timestamp_hms", "timestamp_sec", "type",
                    "scene_relation", "notes"])
        w.writerow(["", "", "hard_cut | dissolve | fade_in | fade_out | other",
                    "within | change  (hard_cut only)", ""])
    return out


# ── Cached detection primitives ───────────────────────────────────────────────

def load_frame_scores(
    video_path: Path,
    validation_dir: Path | None = None,
    use_cache: bool = True,
    progress_cb: Callable[[float], None] | None = None,
    status_cb: Callable[[str], None] | None = None,
) -> list[tuple[float, float]]:
    vdir = validation_dir or get_validation_dir()
    cache = vdir / f"{video_path.stem}_framescores.npz"
    if use_cache:
        if not cache.exists():  # search the WHOLE tree so moves never re-decode
            moved = find_latest(f"{video_path.stem}_framescores.npz",
                                get_validation_dir())
            if moved:
                cache = moved
        if cache.exists():
            data = np.load(cache)
            return list(zip(data["t"].tolist(), data["s"].tolist()))
    if status_cb:
        status_cb("Computing per-frame content scores (full decode — a few minutes)…")
    scores = _compute_frame_scores(video_path, progress_cb=progress_cb)
    vdir.mkdir(parents=True, exist_ok=True)
    np.savez(cache,
             t=np.array([x[0] for x in scores]),
             s=np.array([x[1] for x in scores]))
    return scores


def load_hard_cuts(
    video_path: Path,
    detector: str,
    threshold: float,
    validation_dir: Path | None = None,
    use_cache: bool = True,
    status_cb: Callable[[str], None] | None = None,
) -> list[float]:
    vdir = validation_dir or get_validation_dir()
    tag = f"{detector}_t{threshold:g}"
    cache = vdir / f"{video_path.stem}_cuts_{tag}.json"
    if use_cache:
        if not cache.exists():  # search the WHOLE tree so moves never re-detect
            moved = find_latest(f"{video_path.stem}_cuts_{tag}.json",
                                get_validation_dir())
            if moved:
                cache = moved
        if cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))["cut_times"]
    if status_cb:
        status_cb(f"Detecting hard cuts ({detector}, threshold={threshold:g})…")
    if detector == "transnet":
        # Optional neural detector — see analyzer/detector_transnet.py.
        from .detector_transnet import detect_cuts as _tn_cuts
        cut_times = _tn_cuts(video_path, threshold=threshold,
                             status_cb=status_cb)
    else:
        from scenedetect import AdaptiveDetector, ContentDetector, detect
        det = (ContentDetector(threshold=threshold) if detector == "content"
               else AdaptiveDetector(adaptive_threshold=threshold))
        scene_list = detect(str(video_path), det)
        cut_times = [round(start.seconds, 3) for start, _end in scene_list[1:]]
    vdir.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({
        "video": video_path.name, "detector": detector,
        "threshold": threshold, "cut_times": cut_times,
    }, indent=2), encoding="utf-8")
    return cut_times


def merge_detections(cut_times: list[float], dissolves: list[dict]) -> list[dict]:
    hard = [{
        "timestamp_sec": t, "timestamp_hms": sec_to_hms(t),
        "type": "hard_cut", "peak_score": None, "duration_sec": None,
    } for t in cut_times]
    diss = [{
        "timestamp_sec": d["timestamp_sec"],
        "timestamp_hms": sec_to_hms(d["timestamp_sec"]),
        "type": "dissolve",
        "peak_score": d["peak_score"], "duration_sec": d["duration_sec"],
    } for d in dissolves]
    return sorted(hard + diss, key=lambda r: r["timestamp_sec"])


# ── Export ────────────────────────────────────────────────────────────────────

def export_detections(
    video_path: Path,
    validation_dir: Path | None = None,
    detector: str = "content",
    threshold: float = 27.0,
    noise_floor: float = 3.0,
    min_frames: int = 15,
    dissolves_on: bool = True,
    use_cache: bool = True,
    progress_cb: Callable[[float], None] | None = None,
    status_cb: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Run detection and write detections CSV + manifest. Returns paths/counts."""
    vdir = episode_dir(video_path, validation_dir)
    vdir.mkdir(parents=True, exist_ok=True)
    stem = video_path.stem
    tag = f"{detector}-t{threshold:g}" + ("-diss" if dissolves_on else "-solo")

    cut_times = load_hard_cuts(video_path, detector, threshold, vdir,
                               use_cache=use_cache, status_cb=status_cb)
    dissolve_list: list[dict] = []
    if dissolves_on:
        frame_scores = load_frame_scores(video_path, vdir, use_cache=use_cache,
                                         progress_cb=progress_cb, status_cb=status_cb)
        dissolve_list = _find_dissolves(
            frame_scores, hard_cut_times_sec=cut_times,
            noise_floor=noise_floor, hard_threshold=threshold,
            min_frames=min_frames)

    transitions = merge_detections(cut_times, dissolve_list)

    det_path = vdir / f"{stem}__{tag}_detections.csv"
    with det_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "timestamp_sec", "timestamp_hms", "type", "peak_score", "duration_sec"])
        w.writeheader()
        w.writerows(transitions)

    manifest = {
        "video": str(video_path), "date": str(date.today()),
        "git_commit": _git_commit(), "detector": detector,
        "threshold": threshold, "dissolve_pass": dissolves_on,
        "noise_floor": noise_floor if dissolves_on else None,
        "min_frames": min_frames if dissolves_on else None,
        "n_hard_cuts": len(cut_times), "n_dissolves": len(dissolve_list),
    }
    man_path = vdir / f"{stem}__{tag}_manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {"detections_path": det_path, "manifest_path": man_path,
            "tag": tag, "n_hard_cuts": len(cut_times),
            "n_dissolves": len(dissolve_list)}


# ── Matching + scoring ────────────────────────────────────────────────────────

def _max_cardinality_match(
    manual: list[dict],
    detections: list[dict],
    tolerance: float,
) -> dict[int, int]:
    """Maximum-cardinality matching between coded and detected events.

    Replaces the earlier greedy nearest-unclaimed pass, which was order
    dependent and could strand a valid pair: with manual events at 10.0/11.7
    and detections at 10.75/9.0 (tolerance 1s), greedy scores TP=1 where the
    optimal assignment scores TP=2. That understated recall on closely spaced
    transitions — exactly the fast-cut case.

    Kuhn's augmenting-path algorithm; no new dependency (scipy is not a CMAT
    requirement and would bloat the packaged build). Candidate edges are
    visited nearest-first, but that alone does NOT minimise total offset —
    an augmenting path can displace an earlier good pairing (manual 0,1 vs
    detections 0,2 at tolerance 2 yields total offset 3 where 1 is possible).
    A swap-refinement pass afterwards fixes that without changing cardinality.

    Returns {manual_index: detection_index}.
    """
    adj: list[list[int]] = []
    for m in manual:
        cands = [(abs(d["timestamp_sec"] - m["timestamp_sec"]), di)
                 for di, d in enumerate(detections)
                 if abs(d["timestamp_sec"] - m["timestamp_sec"]) <= tolerance]
        cands.sort()
        adj.append([di for _dist, di in cands])

    det_to_man: dict[int, int] = {}

    def _augment(mi: int, seen: set[int]) -> bool:
        for di in adj[mi]:
            if di in seen:
                continue
            seen.add(di)
            if di not in det_to_man or _augment(det_to_man[di], seen):
                det_to_man[di] = mi
                return True
        return False

    for mi in range(len(manual)):
        _augment(mi, set())

    pairs = {mi: di for di, mi in det_to_man.items()}

    # Swap refinement: cardinality is already maximal, so improve total offset
    # by exchanging partners between matched pairs where that helps and both
    # stay within tolerance. Converges to a local optimum; O(n^2) per pass.
    def _d(mi: int, di: int) -> float:
        return abs(detections[di]["timestamp_sec"] - manual[mi]["timestamp_sec"])

    improved = True
    while improved:
        improved = False
        items = list(pairs.items())
        for a, (mi, di) in enumerate(items):
            for mj, dj in items[a + 1:]:
                if mi not in pairs or mj not in pairs:
                    continue
                cur = _d(mi, di) + _d(mj, dj)
                swp = _d(mi, dj) + _d(mj, di)
                if (swp < cur - 1e-9
                        and _d(mi, dj) <= tolerance
                        and _d(mj, di) <= tolerance):
                    pairs[mi], pairs[mj] = dj, di
                    di, dj = dj, di
                    improved = True
    return pairs


def match_transitions(
    detections: list[dict],
    manual: list[dict],
    tolerance: float,
) -> tuple[list[dict], list[dict]]:
    """Match coded events to detections. Returns (results, false_positives).

    A match is TEMPORAL only — it records whether the tool flagged a transition
    at that moment, not whether it labeled the type correctly. `type_match`
    carries that separately, and score_by_type() reports both views.
    """
    pairs = _max_cardinality_match(manual, detections, tolerance)
    results: list[dict] = []

    for mi, m in enumerate(manual):
        di = pairs.get(mi)
        if di is not None:
            d = detections[di]
            results.append({
                "manual_ts": m["timestamp_sec"], "manual_hms": m["timestamp_hms"],
                "manual_type": m["type"],
                "tool_ts": d["timestamp_sec"], "tool_type": d["type"],
                "offset_sec": round(d["timestamp_sec"] - m["timestamp_sec"], 2),
                "match": "TP",
                "type_match": "yes" if d["type"] == m["type"] else "no",
            })
        else:
            results.append({
                "manual_ts": m["timestamp_sec"], "manual_hms": m["timestamp_hms"],
                "manual_type": m["type"],
                "tool_ts": None, "tool_type": None, "offset_sec": None,
                "match": "FN", "type_match": "—",
            })

    claimed = set(pairs.values())
    false_positives = [d for di, d in enumerate(detections) if di not in claimed]
    return results, false_positives


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return p, r, f


def score_by_type(results: list[dict], false_positives: list[dict],
                  require_type_match: bool = False) -> list[dict]:
    """Score detection performance, stratified by the HUMAN-coded type.

    Two distinct questions, and they must not be conflated:

    require_type_match=False (default) — BOUNDARY DETECTION. A TP means the
        tool flagged a transition at that moment, whatever it called it. Rows
        are stratified by the human label, so "hard_cut" here reads as "human-
        coded hard cuts the tool located", NOT "hard cuts the tool correctly
        identified as hard cuts". This is the right measure for transition
        RATES (cuts/min), and the only fair measure for detectors that emit
        untyped boundaries (e.g. TransNetV2).

    require_type_match=True — TYPE-CONDITIONAL. A TP additionally requires the
        tool's label to equal the human label; temporal matches with the wrong
        label become FN for the human type and FP for the tool's type. This is
        classification performance.

    Report both. See type_confusion() for where the labels actually go.
    """
    all_types = sorted(
        {r["manual_type"] for r in results} | {d["type"] for d in false_positives}
    )
    if require_type_match:
        all_types = sorted(set(all_types)
                           | {r["tool_type"] for r in results
                              if r["match"] == "TP" and r["tool_type"]})

    rows = []
    total_tp = total_fp = total_fn = 0
    for t in all_types:
        if require_type_match:
            tp = sum(1 for r in results if r["match"] == "TP"
                     and r["manual_type"] == t and r["type_match"] == "yes")
            # missed outright, plus found-but-mislabelled
            fn = sum(1 for r in results
                     if r["manual_type"] == t
                     and (r["match"] == "FN"
                          or (r["match"] == "TP" and r["type_match"] == "no")))
            # invented, plus this type wrongly asserted on another type's event
            fp = (sum(1 for d in false_positives if d["type"] == t)
                  + sum(1 for r in results if r["match"] == "TP"
                        and r["type_match"] == "no" and r["tool_type"] == t))
        else:
            tp = sum(1 for r in results
                     if r["match"] == "TP" and r["manual_type"] == t)
            fn = sum(1 for r in results
                     if r["match"] == "FN" and r["manual_type"] == t)
            fp = sum(1 for d in false_positives if d["type"] == t)
        total_tp += tp; total_fp += fp; total_fn += fn
        p, r, f = prf(tp, fp, fn)
        rows.append({"type": t, "TP": tp, "FP": fp, "FN": fn,
                     "precision": round(p, 3), "recall": round(r, 3), "F1": round(f, 3)})
    p, r, f = prf(total_tp, total_fp, total_fn)
    rows.append({"type": "ALL", "TP": total_tp, "FP": total_fp, "FN": total_fn,
                 "precision": round(p, 3), "recall": round(r, 3), "F1": round(f, 3)})
    return rows


def type_confusion(results: list[dict],
                   false_positives: list[dict] | None = None
                   ) -> dict[str, dict[str, int]]:
    """Confusion matrix: human type → tool type, over matched events.

    Answers "when the tool found the transition, did it label it correctly?" —
    the question boundary-detection F1 cannot answer.

    Includes a `<missed>` column (human events with no detection) and, when
    false_positives are supplied, a `<spurious>` row (detections with no human
    event). Without those the table is not self-contained: a detector could
    look perfect here while missing most of the episode.
    """
    matrix: dict[str, dict[str, int]] = {}
    for r in results:
        h = r["manual_type"] or "unknown"
        matrix.setdefault(h, {})
        if r["match"] == "TP":
            t = r["tool_type"] or "unknown"
            matrix[h][t] = matrix[h].get(t, 0) + 1
        elif r["match"] == "FN":
            matrix[h]["<missed>"] = matrix[h].get("<missed>", 0) + 1
    if false_positives:
        row = matrix.setdefault("<spurious>", {})
        for d in false_positives:
            t = d.get("type") or "unknown"
            row[t] = row.get(t, 0) + 1
    return matrix


# ── Compare ───────────────────────────────────────────────────────────────────

def compare_detections(
    det_path: Path,
    manual_path: Path,
    tolerance: float = 2.0,
    start: float | str | None = None,
    end: float | str | None = None,
    warn_cb: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Score detections against manual coding; write comparison + match-detail CSVs.

    Returns a dict with summary_rows, results, false_positives, mismatches,
    window, and the written file paths.
    """
    with det_path.open(newline="", encoding="utf-8") as fh:
        detections = list(csv.DictReader(fh))
    for d in detections:
        d["timestamp_sec"] = float(d["timestamp_sec"])
    manual = parse_manual_csv(manual_path, warn_cb=warn_cb)

    lo = parse_time_arg(start)
    hi = parse_time_arg(end)
    window = None
    if lo is not None or hi is not None:
        lo = lo if lo is not None else 0.0
        hi = hi if hi is not None else float("inf")
        window = (lo, hi)
        detections = [d for d in detections if lo <= d["timestamp_sec"] <= hi]
        n_before = len(manual)
        manual = [m for m in manual if lo <= m["timestamp_sec"] <= hi]
        if len(manual) != n_before and warn_cb:
            warn_cb(f"{n_before - len(manual)} manual rows outside the window were excluded")

    det_stem = det_path.stem.replace("_detections", "")
    tag = det_stem.split("__", 1)[1] if "__" in det_stem else "untagged"
    ep_stem = det_stem.split("__", 1)[0]

    results, false_positives = match_transitions(detections, manual, tolerance)
    summary_rows = score_by_type(results, false_positives)             # boundary
    typed_rows = score_by_type(results, false_positives,
                               require_type_match=True)                # classification
    confusion = type_confusion(results, false_positives)
    mismatches = [r for r in results if r["match"] == "TP" and r["type_match"] == "no"]

    # Rate calibration — a DIFFERENT estimand from boundary localisation, and
    # the one CMAT actually publishes (cuts/min). False positives and false
    # negatives partly cancel in a count, so a rate can be accurate while
    # individual detections are not (and vice versa). Both must be reported.
    #
    # Exact identity: predicted/actual == recall/precision. So recall >
    # precision predicts an OVERCOUNT, precision > recall an UNDERCOUNT.
    # "Error" for a single episode; "bias" only across a held-out sample.
    count_ratio = (len(detections) / len(manual)) if manual else None
    rel_count_error = (count_ratio - 1.0) if count_ratio is not None else None

    out_dir = manual_path.parent
    out_path = out_dir / f"{ep_stem}__{tag}_comparison_{date.today()}.csv"
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["scoring", "type", "TP", "FP", "FN",
                                           "precision", "recall", "F1"])
        w.writeheader()
        # "boundary" = found a transition here (rate-relevant; the figure to
        # quote for cuts/min). "typed" = also labelled it correctly.
        for row in summary_rows:
            w.writerow({"scoring": "boundary", **row})
        for row in typed_rows:
            w.writerow({"scoring": "typed", **row})

    detail_path = out_dir / f"{ep_stem}__{tag}_match_detail_{date.today()}.csv"
    detail_rows = list(results)
    for d in false_positives:
        detail_rows.append({
            "manual_ts": None, "manual_hms": None, "manual_type": None,
            "tool_ts": d["timestamp_sec"], "tool_type": d["type"],
            "offset_sec": None, "match": "FP", "type_match": "—",
        })
    detail_rows.sort(key=lambda r: r["manual_ts"] if r["manual_ts"] is not None
                     else r["tool_ts"])
    # Preserve any existing failure_reason annotations for identical rows so a
    # re-compare does not wipe completed annotation work. Carry forward from the
    # most recent match-detail for this episode+tag, whatever its date.
    existing = {}
    prior_details = sorted(out_dir.glob(f"{ep_stem}__{tag}_match_detail_*.csv"),
                           key=lambda p: p.stat().st_mtime)
    for prior in prior_details:  # oldest first; newer non-empty values win
        for r in load_match_detail(prior):
            if r.get("failure_reason"):
                key = (r.get("manual_ts") or "", r.get("tool_ts") or "")
                existing[key] = r["failure_reason"]
    with detail_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "manual_ts", "manual_hms", "manual_type", "tool_ts", "tool_type",
            "offset_sec", "match", "type_match", "failure_reason"])
        w.writeheader()
        for r in detail_rows:
            key = (str(r["manual_ts"]) if r["manual_ts"] is not None else "",
                   str(r["tool_ts"]) if r["tool_ts"] is not None else "")
            w.writerow({**r, "failure_reason": existing.get(key, "")})

    cmp_manifest = {
        "date": str(date.today()), "git_commit": _git_commit(),
        "detections_file": det_path.name, "manual_file": manual_path.name,
        "tolerance_sec": tolerance,
        "window": [window[0], window[1]] if window else None,
        "n_detections": len(detections), "n_manual": len(manual),
        # Rate calibration (see compare_detections): a separate estimand from
        # boundary localisation. Single-episode figure — an ERROR, not a bias.
        "count_ratio": (round(count_ratio, 4)
                        if count_ratio is not None else None),
        "signed_relative_count_error": (round(rel_count_error, 4)
                                        if rel_count_error is not None else None),
    }
    man_path = out_dir / f"{ep_stem}__{tag}_comparison_manifest_{date.today()}.json"
    man_path.write_text(json.dumps(cmp_manifest, indent=2), encoding="utf-8")

    return {
        "summary_rows": summary_rows, "typed_rows": typed_rows,
        "confusion": confusion, "results": results,
        "count_ratio": (round(count_ratio, 4)
                        if count_ratio is not None else None),
        "rel_count_error": (round(rel_count_error, 4)
                            if rel_count_error is not None else None),
        "false_positives": false_positives, "mismatches": mismatches,
        "n_detections": len(detections), "n_manual": len(manual),
        "window": window, "tolerance": tolerance,
        "comparison_path": out_path, "detail_path": detail_path,
        "manifest_path": man_path, "tag": tag, "ep_stem": ep_stem,
    }


# ── Sweep ─────────────────────────────────────────────────────────────────────

def run_sweep(
    video_path: Path,
    manual_path: Path,
    validation_dir: Path | None = None,
    detector: str = "content",
    threshold: float = 27.0,
    tolerance: float = 2.0,
    floors: list[float] | None = None,
    frames: list[int] | None = None,
    start: float | str | None = None,
    end: float | str | None = None,
    status_cb: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Grid-search noise_floor x min_frames against manual coding (uses caches)."""
    vdir = episode_dir(video_path, validation_dir)
    floors = floors or [2.0, 3.0, 4.0, 5.0]
    frames = frames or [8, 12, 15, 20]

    frame_scores = load_frame_scores(video_path, vdir, use_cache=True,
                                     status_cb=status_cb)
    cut_times = load_hard_cuts(video_path, detector, threshold, vdir,
                               use_cache=True, status_cb=status_cb)
    manual = parse_manual_csv(manual_path)

    lo = parse_time_arg(start)
    hi = parse_time_arg(end)
    window = None
    if lo is not None or hi is not None:
        lo = lo if lo is not None else 0.0
        hi = hi if hi is not None else float("inf")
        window = (lo, hi)
        manual = [m for m in manual if lo <= m["timestamp_sec"] <= hi]

    grid_rows = []
    for floor in floors:
        for mf in frames:
            dissolves = _find_dissolves(
                frame_scores, hard_cut_times_sec=cut_times,
                noise_floor=floor, hard_threshold=threshold, min_frames=mf)
            detections = merge_detections(cut_times, dissolves)
            if window is not None:
                detections = [d for d in detections
                              if window[0] <= d["timestamp_sec"] <= window[1]]
            results, fps = match_transitions(detections, manual, tolerance)
            rows = score_by_type(results, fps)
            diss = next((r for r in rows if r["type"] == "dissolve"),
                        {"precision": 0.0, "recall": 0.0, "F1": 0.0,
                         "TP": 0, "FP": 0, "FN": 0})
            all_row = next(r for r in rows if r["type"] == "ALL")
            grid_rows.append({
                "noise_floor": floor, "min_frames": mf,
                "n_dissolves_detected": len(dissolves),
                "diss_TP": diss["TP"], "diss_FP": diss["FP"], "diss_FN": diss["FN"],
                "diss_precision": diss["precision"], "diss_recall": diss["recall"],
                "diss_F1": diss["F1"], "all_F1": all_row["F1"],
            })

    best = max(grid_rows, key=lambda r: r["diss_F1"])

    stem = video_path.stem
    out = vdir / f"{stem}__sweep_{date.today()}.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(grid_rows[0].keys()))
        w.writeheader()
        w.writerows(grid_rows)
    (vdir / f"{stem}__sweep_manifest_{date.today()}.json").write_text(
        json.dumps({
            "date": str(date.today()), "git_commit": _git_commit(),
            "video": str(video_path), "manual_file": manual_path.name,
            "detector": detector, "threshold": threshold,
            "tolerance_sec": tolerance, "floors": floors, "frames": frames,
            "window": [window[0], window[1]] if window else None,
        }, indent=2), encoding="utf-8")

    return {"grid_rows": grid_rows, "best": best, "csv_path": out,
            "floors": floors, "frames": frames, "window": window}


# ── Cut classification (within-scene vs scene-change) ────────────────────────

def classify_cuts_for_video(
    video_path: Path,
    validation_dir: Path | None = None,
    detector: str = "content",
    threshold: float = 27.0,
    offset_sec: float = 1.0,
    similarity_threshold: float = 0.55,
    status_cb: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Classify every hard cut as within_scene / scene_change and write a CSV.

    Uses the cached cut list when available. Output CSV is designed to be
    eyeballed side-by-side with the manual coding notes ("back to mama bear"
    vs "new scene…") — that comparison is the classifier's validation path.
    """
    vdir = episode_dir(video_path, validation_dir)
    cut_times = load_hard_cuts(video_path, detector, threshold, vdir,
                               use_cache=True, status_cb=status_cb)

    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    cap.release()
    duration_sec = frames / fps if fps else 0.0

    if status_cb:
        status_cb(f"Classifying {len(cut_times)} cuts "
                  f"(2 frame seeks per cut)…")
    rows = classify_cut_transitions(
        video_path, cut_times, duration_sec,
        offset_sec=offset_sec, similarity_threshold=similarity_threshold)

    n_within = sum(1 for r in rows if r["label"] == "within_scene")
    n_change = sum(1 for r in rows if r["label"] == "scene_change")
    n_unknown = sum(1 for r in rows if r["label"] == "unknown")
    duration_min = max(duration_sec / 60.0, 1e-6)

    tag = f"{detector}-t{threshold:g}"
    out = vdir / f"{video_path.stem}__cutclass_{tag}_{date.today()}.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["timestamp_sec", "timestamp_hms", "label", "similarity"])
        for r in rows:
            w.writerow([r["timestamp_sec"], sec_to_hms(r["timestamp_sec"]),
                        r["label"],
                        "" if r["similarity"] is None else r["similarity"]])

    (vdir / f"{video_path.stem}__cutclass_{tag}_manifest_{date.today()}.json"
     ).write_text(json.dumps({
        "video": str(video_path), "date": str(date.today()),
        "git_commit": _git_commit(), "detector": detector,
        "threshold": threshold, "offset_sec": offset_sec,
        "similarity_threshold": similarity_threshold,
        "n_cuts": len(rows), "n_within_scene": n_within,
        "n_scene_change": n_change, "n_unknown": n_unknown,
        "note": "similarity_threshold is UNVALIDATED — tune against "
                "hand-coded within/change labels before trusting.",
    }, indent=2), encoding="utf-8")

    return {
        "rows": rows, "csv_path": out,
        "n_cuts": len(rows), "n_within_scene": n_within,
        "n_scene_change": n_change, "n_unknown": n_unknown,
        "scene_changes_per_min": round(n_change / duration_min, 3),
        "within_scene_fraction": round(n_within / (n_within + n_change), 3)
                                 if (n_within + n_change) else 0.0,
    }


# ── Cut-classifier grading (against hand-labeled scene_relation) ─────────────

def _cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's kappa for binary (human, predicted) label pairs.

    Returns None where kappa is UNDEFINED rather than 0.0: with no pairs, or
    when chance agreement is 1 (both raters used a single identical class).
    Reporting 0.0 there would read as "no agreement beyond chance" for what is
    actually perfect unanimity — the opposite of the truth.
    """
    n = len(pairs)
    if n == 0:
        return None
    agree = sum(1 for h, p in pairs if h == p) / n
    hw = sum(1 for h, _ in pairs if h == "within") / n
    pw = sum(1 for _, p in pairs if p == "within") / n
    p_e = hw * pw + (1 - hw) * (1 - pw)
    if (1 - p_e) <= 1e-9:
        return None
    return (agree - p_e) / (1 - p_e)


def grade_cut_classifier(
    video_path: Path,
    manual_path: Path,
    validation_dir: Path | None = None,
    detector: str = "content",
    threshold: float = 27.0,
    tolerance: float = 2.0,
    offset_sec: float = 1.0,
    start: float | str | None = None,
    end: float | str | None = None,
    sweep_thresholds: list[float] | None = None,
    warn_cb: Callable[[str], None] | None = None,
    status_cb: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Grade the within/scene-change classifier against hand-labeled cuts.

    Uses each cut's raw similarity score (independent of any label threshold),
    matches it to a human `scene_relation` label, then sweeps the similarity
    threshold reporting accuracy + Cohen's kappa at each, plus the confusion
    matrix at the best (max-kappa) threshold.
    """
    vdir = episode_dir(video_path, validation_dir)
    cut_times = load_hard_cuts(video_path, detector, threshold, vdir,
                               use_cache=True, status_cb=status_cb)

    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    cap.release()
    duration_sec = frames / fps if fps else 0.0

    if status_cb:
        status_cb(f"Scoring {len(cut_times)} cuts for similarity…")
    clf = classify_cut_transitions(video_path, cut_times, duration_sec,
                                   offset_sec=offset_sec,
                                   similarity_threshold=0.5)  # threshold unused here
    clf = [c for c in clf if c["similarity"] is not None]

    manual = parse_manual_csv(manual_path, warn_cb=warn_cb)
    lo = parse_time_arg(start)
    hi = parse_time_arg(end)
    window = None
    if lo is not None or hi is not None:
        lo = lo if lo is not None else 0.0
        hi = hi if hi is not None else float("inf")
        window = (lo, hi)

    labeled = [m for m in manual
               if m["type"] == "hard_cut"
               and m.get("scene_relation") in ("within", "change")
               and (window is None or window[0] <= m["timestamp_sec"] <= window[1])]

    n_labeled_total = sum(1 for m in manual if m["type"] == "hard_cut"
                          and m.get("scene_relation") in ("within", "change"))

    # Match each labeled human cut to nearest unclaimed classifier cut.
    used: set[int] = set()
    pairs: list[dict] = []
    for m in labeled:
        best_i, best_d = None, float("inf")
        for i, c in enumerate(clf):
            if i in used:
                continue
            d = abs(c["timestamp_sec"] - m["timestamp_sec"])
            if d <= tolerance and d < best_d:
                best_d, best_i = d, i
        if best_i is not None:
            used.add(best_i)
            pairs.append({"human": m["scene_relation"],
                          "similarity": clf[best_i]["similarity"],
                          "timestamp_sec": m["timestamp_sec"],
                          "timestamp_hms": m["timestamp_hms"]})

    sweep = sweep_thresholds or [round(0.30 + 0.025 * k, 3) for k in range(21)]
    sweep_rows = []
    for T in sweep:
        lp = [(p["human"], "within" if p["similarity"] >= T else "change")
              for p in pairs]
        acc = (sum(1 for h, pr in lp if h == pr) / len(lp)) if lp else 0.0
        sweep_rows.append({"threshold": T, "accuracy": round(acc, 3),
                           "kappa": (round(k, 3)
                                     if (k := _cohen_kappa(lp)) is not None
                                     else None),
                           "n": len(lp)})

    # Undefined kappa (None) must not win the sweep — sort it below any real value.
    best = max(sweep_rows,
               key=lambda r: (r["kappa"] if r["kappa"] is not None else -2.0,
                              r["accuracy"])) \
        if sweep_rows else {"threshold": 0.55, "accuracy": 0.0, "kappa": None}

    # Confusion at best threshold.
    T = best["threshold"]
    confusion = {"within_within": 0, "within_change": 0,
                 "change_within": 0, "change_change": 0}
    for p in pairs:
        pred = "within" if p["similarity"] >= T else "change"
        confusion[f"{p['human']}_{pred}"] += 1

    # Write per-cut detail + a manifest.
    tag = f"{detector}-t{threshold:g}"
    out = vdir / f"{video_path.stem}__cutgrade_{tag}_{date.today()}.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["timestamp_hms", "similarity", "human_label",
                    f"predicted@{T}"])
        for p in sorted(pairs, key=lambda x: x["timestamp_sec"]):
            w.writerow([p["timestamp_hms"], p["similarity"], p["human"],
                        "within" if p["similarity"] >= T else "change"])
    (vdir / f"{video_path.stem}__cutgrade_{tag}_manifest_{date.today()}.json"
     ).write_text(json.dumps({
        "date": str(date.today()), "git_commit": _git_commit(),
        "video": str(video_path), "manual_file": manual_path.name,
        "detector": detector, "threshold": threshold, "tolerance": tolerance,
        "offset_sec": offset_sec,
        "window": [window[0], window[1]] if window else None,
        "n_human_labeled": n_labeled_total, "n_matched": len(pairs),
        "best_threshold": best["threshold"], "best_kappa": best["kappa"],
        "best_accuracy": best["accuracy"], "confusion_at_best": confusion,
    }, indent=2), encoding="utf-8")

    return {
        "pairs": pairs, "sweep_rows": sweep_rows, "best": best,
        "confusion": confusion, "csv_path": out,
        "n_human_labeled": n_labeled_total, "n_matched": len(pairs),
        "n_unmatched": len(labeled) - len(pairs), "window": window,
    }


# ── Aggregate summary ─────────────────────────────────────────────────────────

def parse_comparison_name(path: Path) -> tuple[str, str] | None:
    """(episode_stem, detector_config_tag) from a comparison CSV filename.

    Filenames are `<stem>__<tag>_comparison_<date>.csv`. Parsed structurally
    rather than by substring search: `"content" in filename` would also match
    an episode titled "Contentment", and would merge different thresholds and
    dissolve settings into one supposedly-single configuration.
    """
    name = path.name
    marker = "_comparison_"
    if "__" not in name or marker not in name:
        return None
    stem, rest = name.split("__", 1)
    tag = rest.split(marker, 1)[0]
    return stem, tag


def _latest_comparisons(vdir: Path,
                        detector_tag: str | None = None) -> list[Path]:
    """Newest comparison CSV per (episode, config), optionally one config."""
    newest: dict[tuple[str, str], Path] = {}
    for cf in vdir.rglob("*_comparison_*.csv"):
        parsed = parse_comparison_name(cf)
        if not parsed:
            continue
        stem, tag = parsed
        if detector_tag is not None and tag != detector_tag:
            continue
        key = (stem, tag)
        prev = newest.get(key)
        if prev is None or cf.stat().st_mtime > prev.stat().st_mtime:
            newest[key] = cf
    return sorted(newest.values())


def available_detector_tags(vdir: Path | None = None) -> list[str]:
    """Detector-config tags that have comparison results on disk."""
    vdir = vdir or get_validation_dir()
    tags = {t for p in vdir.rglob("*_comparison_*.csv")
            if (r := parse_comparison_name(p)) for t in (r[1],)}
    return sorted(tags)


def aggregate_summary(directory: Path | None = None,
                      detector_tag: str | None = None) -> dict[str, Any]:
    """Combine comparison CSVs into one P/R/F1 table, for ONE detector config.

    *detector_tag* None means "every config on disk", which is almost never
    what a reader wants: this working copy holds runs of ContentDetector and
    TransNetV2 over the same two episodes, and summing them produced a single
    "AGGREGATE F1 0.891" describing no detector that exists.
    `local_hard_cut_f1` has always filtered for exactly this reason — its
    docstring calls the unfiltered version "one meaningless average" — but
    this function, which the CLI's `summary` command and the Validate tool
    screen both display, did not.

    The returned dict now carries `detector_tag` and `detector_tags` so a
    caller cannot show the number without being able to say what it is OF.
    """
    vdir = directory or get_validation_dir()
    # Keep only the LATEST comparison per (episode, detector-config). Summing
    # every dated rerun double-counts episodes and silently over-weights
    # whichever one was re-run most often.
    comparison_files = _latest_comparisons(vdir, detector_tag=detector_tag)
    totals: dict[str, dict] = {}
    for cf in comparison_files:
        with cf.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                t = row["type"]
                if t == "ALL":
                    continue
                # Newer files carry both scorings; aggregate the boundary view
                # only, or the two would be summed together. A MISSING column
                # means a legacy boundary-scored file; a PRESENT but blank or
                # unrecognised value means a malformed file and is skipped
                # rather than silently assumed to be boundary.
                if "scoring" in row:
                    if (row.get("scoring") or "").strip() != "boundary":
                        continue
                # else: legacy file, boundary by definition
                totals.setdefault(t, {"TP": 0, "FP": 0, "FN": 0})
                totals[t]["TP"] += int(row["TP"])
                totals[t]["FP"] += int(row["FP"])
                totals[t]["FN"] += int(row["FN"])
    rows = []
    all_tp = all_fp = all_fn = 0
    for t in sorted(totals):
        tp, fp, fn = totals[t]["TP"], totals[t]["FP"], totals[t]["FN"]
        all_tp += tp; all_fp += fp; all_fn += fn
        p, r, f = prf(tp, fp, fn)
        rows.append({"type": t, "TP": tp, "FP": fp, "FN": fn,
                     "precision": round(p, 3), "recall": round(r, 3),
                     "F1": round(f, 3)})
    p, r, f = prf(all_tp, all_fp, all_fn)
    rows.append({"type": "AGGREGATE", "TP": all_tp, "FP": all_fp, "FN": all_fn,
                 "precision": round(p, 3), "recall": round(r, 3), "F1": round(f, 3)})
    return {"rows": rows, "n_files": len(comparison_files),
            "files": comparison_files,
            "detector_tag": detector_tag,
            "detector_tags": available_detector_tags(vdir)}


# ── Match-detail annotation I/O ───────────────────────────────────────────────

_DETAIL_FIELDS = ["manual_ts", "manual_hms", "manual_type", "tool_ts", "tool_type",
                  "offset_sec", "match", "type_match", "failure_reason"]


def load_match_detail(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def save_match_detail(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=_DETAIL_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in _DETAIL_FIELDS})


def find_latest(pattern: str, validation_dir: Path | None = None) -> Path | None:
    """Most recently modified file matching pattern (searched recursively)."""
    vdir = validation_dir or get_validation_dir()
    matches = sorted(vdir.rglob(pattern), key=lambda p: p.stat().st_mtime)
    return matches[-1] if matches else None


def find_manual(video_path: Path, validation_dir: Path | None = None) -> Path | None:
    """Locate the manual-coding CSV for a video.

    Tries the exact video stem first, then falls back to any *_manual.csv
    whose base name is a prefix of the video stem (users shorten long
    filenames, e.g. 'Little Bear 1x01_manual.csv' for a three-story episode
    file with a very long name). Minimum 8-char prefix to avoid junk matches.
    """
    vdir = validation_dir or get_validation_dir()
    stem = video_path.stem
    exact = find_latest(f"{stem}_manual.csv", vdir)
    if exact:
        return exact
    if not vdir.exists():
        return None
    suffix = "_manual.csv"
    candidates = [
        p for p in vdir.rglob(f"*{suffix}")
        if len(p.name) - len(suffix) >= 8
        and stem.lower().startswith(p.name[:-len(suffix)].lower())
    ]
    if candidates:
        return sorted(candidates, key=lambda p: p.stat().st_mtime)[-1]
    return None


def episode_dir(video_path: Path, validation_dir: Path | None = None) -> Path:
    """Folder where this episode's coding + outputs should live.

    Outputs follow the manual sheet: whatever folder the researcher put the
    episode's coding in (a per-episode subfolder, typically) is where its
    detections, classification, grading, sweep, rates, and caches also land —
    so one episode's files stay together instead of scattering to the root.
    Falls back to the validation root when the episode has no coding yet.
    """
    vdir = validation_dir or get_validation_dir()
    manual = find_manual(video_path, vdir)
    if manual is not None:
        return manual.parent
    ev = find_latest(f"{video_path.stem}_events.csv", vdir)
    if ev is not None:
        return ev.parent
    hits = sorted(vdir.rglob(f"{video_path.stem}__*_detections.csv"),
                  key=lambda p: p.stat().st_mtime)
    if hits:
        return hits[-1].parent
    return vdir


# ── Episode workflow status ───────────────────────────────────────────────────

def episode_status(video_path: Path, validation_dir: Path | None = None) -> dict[str, Any]:
    """Where is this episode in the validation workflow?

    Steps: template -> coded -> detected -> compared -> annotated.
    Searches the validation dir recursively so per-episode subfolders work.
    """
    vdir = validation_dir or get_validation_dir()
    stem = video_path.stem
    st: dict[str, Any] = {
        "stem": stem, "manual_path": None, "coded_rows": 0,
        "detections": [], "latest_detail": None,
        "errors_total": 0, "errors_annotated": 0, "step": "start",
    }
    if not vdir.exists():
        return st

    manual = find_manual(video_path, vdir)
    if manual:
        st["manual_path"] = manual
        try:
            st["coded_rows"] = len(parse_manual_csv(manual))
        except Exception:
            st["coded_rows"] = 0

    st["detections"] = sorted(vdir.rglob(f"{stem}__*_detections.csv"))

    detail = find_latest(f"{stem}__*_match_detail_*.csv", vdir)
    if detail:
        st["latest_detail"] = detail
        try:
            rows = load_match_detail(detail)
            need = [r for r in rows
                    if r.get("match") in ("FP", "FN")
                    or (r.get("match") == "TP" and r.get("type_match") == "no")]
            st["errors_total"] = len(need)
            st["errors_annotated"] = sum(1 for r in need if r.get("failure_reason"))
        except Exception:
            pass

    if st["latest_detail"]:
        st["step"] = ("annotated" if st["errors_total"] > 0
                      and st["errors_annotated"] >= st["errors_total"]
                      else "compared")
    elif st["detections"]:
        st["step"] = "detected"
    elif st["coded_rows"] > 0:
        st["step"] = "coded"
    elif st["manual_path"]:
        st["step"] = "template"
    return st
