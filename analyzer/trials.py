"""
Trials registry — discovers sampling + manual-coding studies from their
provenance manifests. Pure functions, zero GUI imports.

Every validation/coding run CMAT performs writes a *_manifest_*.json next to
its outputs. This module scans the validation folder (recursively) and
synthesizes one "trial" record per run:

  transition_validation  compare run (manual coding vs detections)
  event_coding           fantastical-event rates run
  dissolve_sweep         dissolve parameter grid search
  classifier_grading     within/scene-change classifier vs human labels
  cut_classification     within/scene-change classification run
  detection_run          detector export (machine-only, no manual coding)

Published event-coding trials are flagged via manual_coding.json.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .config_loader import _base_dir
from .validation import get_validation_dir


def _detector_tag(data: dict, manifest_path: Path) -> str:
    """The detector configuration a comparison graded, e.g. "content-t27-diss".

    Read from the detections filename the manifest records, falling back to the
    manifest's own name. Both encode it as `<episode>__<tag>_...`.
    """
    for candidate in (data.get("detections_file"), manifest_path.name):
        if not candidate:
            continue
        stem = Path(str(candidate)).stem
        for suffix in ("_detections", "_comparison"):
            if suffix in stem:
                stem = stem.split(suffix)[0]
                break
        if "__" in stem:
            return stem.split("__", 1)[1]
    return "unrecorded"


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _stem_of(manifest_name: str) -> str:
    """Episode stem = filename part before the double-underscore tag."""
    return manifest_name.split("__", 1)[0] if "__" in manifest_name else manifest_name


def _comparison_result(manifest_path: Path) -> str:
    """ALL-row F1 from the sibling comparison CSV."""
    csv_path = manifest_path.with_name(
        manifest_path.name.replace("comparison_manifest_", "comparison_")
    ).with_suffix(".csv")
    if not csv_path.exists():
        return "—"
    try:
        with csv_path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row["type"] == "ALL":
                    return f"F1 {row['F1']}"
    except Exception:
        pass
    return "—"


def _sweep_result(manifest_path: Path) -> str:
    csv_path = manifest_path.with_name(
        manifest_path.name.replace("sweep_manifest_", "sweep_")
    ).with_suffix(".csv")
    if not csv_path.exists():
        return "—"
    try:
        best = 0.0
        with csv_path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                best = max(best, float(row.get("diss_F1", 0) or 0))
        return f"best diss F1 {best:.3f}"
    except Exception:
        return "—"


def _fmt_window(window) -> str:
    if not window:
        return "full episode"
    def _hms(s: float) -> str:
        s = int(round(float(s)))
        m, sec = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"
    try:
        return f"{_hms(window[0])}–{_hms(window[1])}"
    except Exception:
        return str(window)


def _discover_sample_trials(search_dirs: list[Path]) -> list[dict[str, Any]]:
    """Find Episode Sampler manifest.json files (named sampling trials)."""
    trials: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for root in search_dirs:
        if not root or not root.exists():
            continue
        for mf in root.rglob("manifest.json"):
            if mf in seen:
                continue
            seen.add(mf)
            data = _read_json(mf)
            if not data or "method" not in data or "total_selected" not in data:
                continue  # not a sampler manifest
            name = data.get("trial_name") or f"{data.get('entry_id','?')} ({data.get('method','?')})"
            seed = data.get("seed")
            sampling = data.get("method", "?")
            if data.get("stratify_by"):
                sampling += f", stratified by {data['stratify_by']}"
            if seed is not None:
                sampling += f", seed {seed}"
            date_str = (data.get("generated_at_utc") or "")[:10]
            trials.append({
                "name": name,
                "episode": data.get("entry_id", "?"),
                "kind": "episode_sample",
                "date": date_str,
                "git_commit": data.get("software_version", ""),
                "n_episodes": data.get("total_selected", 0),
                "sampling": sampling,
                "window": "—",
                "result": (f"{data.get('total_selected','?')} of "
                           f"{data.get('total_available','?')} episodes"),
                "detail": ("probability sample" if data.get("probability")
                           else "non-probability sample"),
                "published": False,
                "manifest_path": mf,
                "folder": mf.parent,
                "raw": data,
            })
    return trials


def discover_trials(
    validation_dir: Path | None = None,
    extra_dirs: list[Path] | None = None,
) -> list[dict[str, Any]]:
    """Scan for provenance manifests and return trial records, newest first.

    extra_dirs (e.g. the show root folder) are searched for Episode Sampler
    manifest.json files so named sampling trials appear in the registry.
    """
    vdir = validation_dir or get_validation_dir()
    trials_from_samples = _discover_sample_trials(
        [vdir] + [d for d in (extra_dirs or []) if d])
    if not vdir.exists():
        return trials_from_samples

    # Published event coding (show sampling descriptions), keyed by episode stem.
    published: dict[str, dict] = {}
    mc = _read_json(_base_dir() / "manual_coding.json") or {}
    for show_key, show in mc.get("fantastical_events", {}).items():
        for ep in show.get("episodes", []):
            published[ep["episode"]] = {
                "show_key": show_key,
                "sampling": show.get("sampling_method", ""),
            }

    trials: list[dict[str, Any]] = []

    for mf in sorted(vdir.rglob("*_manifest*.json")):
        data = _read_json(mf)
        if data is None:
            continue
        name = mf.name
        stem = _stem_of(name)
        base: dict[str, Any] = {
            "name": stem,
            "episode": stem,
            "date": data.get("date", ""),
            "git_commit": data.get("git_commit", ""),
            "n_episodes": 1,
            "manifest_path": mf,
            "folder": mf.parent,
            "raw": data,
            "sampling": "manual selection",
            "published": False,
        }

        if "comparison_manifest_" in name:
            trials.append({**base,
                "kind": "transition_validation",
                "window": _fmt_window(data.get("window")),
                "result": _comparison_result(mf),
                # WHICH DETECTOR produced this. Without it the registry lists
                # two runs of the same episode on the same date with different
                # F1s and no way to tell them apart — 0.91 from ContentDetector
                # and 0.942 from TransNetV2 read as a contradiction rather than
                # a comparison. The tag was in the filename all along.
                "detector": _detector_tag(data, mf),
                "detail": (f"±{data.get('tolerance_sec','?')}s tolerance · "
                           f"{data.get('n_manual','?')} manual vs "
                           f"{data.get('n_detections','?')} detected"),
            })
        elif "__eventrates_manifest_" in name:
            pub = published.get(stem)
            trials.append({**base,
                "kind": "event_coding",
                "window": _fmt_window(data.get("window")),
                "result": f"{data.get('events_per_min','?')} events/min",
                "detail": f"{data.get('n_events','?')} fantastical events coded",
                "sampling": (pub["sampling"] if pub else "manual selection"),
                "published": bool(pub),
            })
        elif "__sweep_manifest_" in name:
            trials.append({**base,
                "kind": "dissolve_sweep",
                "window": _fmt_window(data.get("window")),
                "result": _sweep_result(mf),
                "detail": (f"floors {data.get('floors','?')} × "
                           f"frames {data.get('frames','?')}"),
            })
        elif "__cutgrade_" in name:
            trials.append({**base,
                "kind": "classifier_grading",
                "window": _fmt_window(data.get("window")),
                "result": (f"κ {data.get('best_kappa','?')} "
                           f"@ thr {data.get('best_threshold','?')}"),
                "detail": (f"{data.get('n_matched','?')} labeled cuts matched "
                           f"(acc {data.get('best_accuracy','?')})"),
            })
        elif "__cutclass_" in name:
            n_w = data.get("n_within_scene", 0)
            n_c = data.get("n_scene_change", 0)
            frac = f"{n_w/(n_w+n_c):.0%}" if (n_w + n_c) else "?"
            trials.append({**base,
                "kind": "cut_classification",
                "window": "full episode",
                "result": f"{frac} within-scene",
                "detail": (f"{data.get('n_cuts','?')} cuts · "
                           f"sim threshold {data.get('similarity_threshold','?')} "
                           f"(unvalidated)"),
            })
        elif name.endswith("_manifest.json") and "detector" in data:
            trials.append({**base,
                "kind": "detection_run",
                "window": "full episode",
                "result": (f"{data.get('n_hard_cuts','?')} cuts, "
                           f"{data.get('n_dissolves','?')} dissolves"),
                "detail": (f"{data.get('detector','?')} "
                           f"t={data.get('threshold','?')} · dissolve pass "
                           f"{'on' if data.get('dissolve_pass') else 'off'}"),
            })

    trials.extend(trials_from_samples)
    trials.sort(key=lambda t: (t["date"], t["episode"]), reverse=True)
    return trials


def sampling_text_from_manifest(data: dict) -> str:
    """Human-readable sampling description derived from a sampler manifest.

    Used by `code_events.py publish --trial` so the website's sampling
    description is generated from provenance rather than typed by hand.
    """
    parts = [data.get("method", "unknown method")]
    if data.get("stratify_by"):
        parts.append(f"stratified by {data['stratify_by']}")
    if data.get("seed") is not None:
        parts.append(f"seed {data['seed']}")
    text = ", ".join(parts)
    tot_sel = data.get("total_selected")
    tot_av = data.get("total_available")
    if tot_sel is not None and tot_av is not None:
        text += f" — {tot_sel} of {tot_av} episodes"
    if not data.get("probability", True):
        text += " (non-probability sample)"
    name = data.get("trial_name")
    if name:
        text = f"{name}: {text}"
    return text


def read_sample_episodes(manifest_path: Path) -> list[Path]:
    """Episode file paths from an Episode Sampler draw.

    Accepts the manifest.json or the folder containing it, and reads the
    sibling selected.csv. Shared by every destination a sample can be sent to
    (automated queue, hand-coding worklist, validation worklist) so a drawn
    sample flows into whichever measurement path the researcher is using.
    """
    p = Path(manifest_path)
    folder = p if p.is_dir() else p.parent
    csv_path = folder / "selected.csv"
    if not csv_path.exists():
        cands = [c for c in folder.glob("*.csv")]
        if len(cands) != 1:
            return []
        csv_path = cands[0]
    out: list[Path] = []
    try:
        with csv_path.open(newline="", encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                fp = (row.get("filepath") or "").strip()
                if fp and fp.lower() != "nan":
                    out.append(Path(fp))
    except Exception:
        return []
    return out


def sample_coverage(trial: dict, validation_dir: Path | None = None) -> dict | None:
    """For an episode_sample trial: how many sampled episodes have manual coding.

    Reads selected.csv beside the manifest; returns counts of episodes with a
    transition-coding sheet and with an event-coding sheet, or None if the
    episode list can't be read.
    """
    from .validation import find_manual
    if trial.get("kind") != "episode_sample":
        return None
    vdir = validation_dir or get_validation_dir()
    csv_path = trial["folder"] / "selected.csv"
    if not csv_path.exists():
        return None
    stems: list[str] = []
    try:
        with csv_path.open(newline="", encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                fp = (row.get("filepath") or "").strip()
                if fp:
                    stems.append(Path(fp).stem)
    except Exception:
        return None
    if not stems:
        return None

    def _has_events_sheet(stem: str) -> bool:
        if list(vdir.rglob(f"{stem}_events.csv")):
            return True
        suffix = "_events.csv"
        for p in vdir.rglob(f"*{suffix}"):
            base = p.name[:-len(suffix)]
            if len(base) >= 8 and stem.lower().startswith(base.lower()):
                return True
        return False

    n_manual = sum(1 for s in stems
                   if find_manual(Path(f"{s}.mp4"), vdir) is not None)
    n_events = sum(1 for s in stems if _has_events_sheet(s))
    return {"n_episodes": len(stems), "n_transition_coded": n_manual,
            "n_event_coded": n_events}


KIND_LABELS = {
    "transition_validation": "Transition validation",
    "event_coding":          "Event coding",
    "dissolve_sweep":        "Dissolve sweep",
    "classifier_grading":    "Classifier grading",
    "cut_classification":    "Cut classification",
    "detection_run":         "Detection run",
    "episode_sample":        "Episode sample",
}

KIND_EXPLANATIONS = {
    "transition_validation": "Hand-coded transitions graded against the tool's "
                             "detections (precision/recall/F1).",
    "event_coding":          "Human-coded fantastical events — the content "
                             "variable the current literature points to.",
    "dissolve_sweep":        "Grid search of dissolve-detection settings against "
                             "hand coding. Tuning episodes only.",
    "classifier_grading":    "Within-scene vs scene-change classifier graded "
                             "against hand-labeled cuts (Cohen's kappa).",
    "cut_classification":    "Automated within-scene vs scene-change labeling "
                             "of every detected cut (threshold unvalidated).",
    "detection_run":         "Machine-only detector export — no manual coding "
                             "involved.",
    "episode_sample":        "A named episode sample drawn with the Episode "
                             "Sampler — the documented selection of which "
                             "episodes represent a show.",
}
