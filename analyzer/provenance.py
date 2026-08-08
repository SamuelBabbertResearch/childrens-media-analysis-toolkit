"""
Validation provenance — the single source of truth for CMAT's self-reported
accuracy, shown on every results view, export, and the public site.

This is the claim NVivo and every other coding tool structurally cannot make:
CMAT states how far to trust its own automated detection, measured against
blind human coding. The statement is honest per-metric — validated, experimental,
or "deterministic (no detection step to validate)" — never a single blanket F1.

When local validation runs exist (comparison CSVs under validation/), the
hard-cut figure is computed live from them; otherwise the reference figure from
CMAT's validation study is used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Reference figures from CMAT's validation study (see validation/VALIDATION_LOG.md).
# Per-episode hard-cut F1 spanned 0.84 (dissolve-heavy 1960s cel under snowfall)
# to 0.96 (clean modern cel); aggregate ~0.91 across coded episodes.
REFERENCE_HARD_CUT_F1_RANGE = "0.75–0.91"
REFERENCE_HARD_CUT_F1_AGG = "0.85"


def local_hard_cut_f1(validation_dir: Path | None = None,
                      detector_tag: str = "content") -> tuple[str, int] | None:
    """Live boundary-detection F1 for one detector, from local comparison CSVs.

    Filtered to a single detector configuration: aggregating across detectors
    would blend, say, ContentDetector and TransNetV2 runs into one meaningless
    average. Defaults to the shipped detector, which is what an unmodified
    install produces.

    This is BOUNDARY detection (did the tool flag a transition here), scored
    type-agnostically — not type classification. See METRIC_STATUS.
    """
    import csv
    vdir = validation_dir
    try:
        from .validation import (get_validation_dir, _latest_comparisons,
                                 available_detector_tags)
        vdir = vdir or get_validation_dir()
    except Exception:
        return None
    if not vdir or not vdir.exists():
        return None

    # Match the detector config by parsed tag, and take only the newest run per
    # episode — substring matching on filenames merged different thresholds and
    # double-counted reruns.
    tags = [t for t in available_detector_tags(vdir) if t.startswith(detector_tag)]
    if not tags:
        return None
    files: list[Path] = []
    for t in tags:
        files.extend(_latest_comparisons(vdir, detector_tag=t))

    tp = fp = fn = 0
    n_files = 0
    for cf in sorted(set(files)):
        try:
            with cf.open(newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
        except Exception:
            continue
        used = False
        for row in rows:
            # The ALL row is the only clean detector-level figure. Per-type
            # boundary rows are hybrids: TPs are stratified by the HUMAN label
            # while FPs are stratified by the TOOL's label, so their precision
            # mixes denominators and must not be published as a headline.
            if row.get("type") != "ALL":
                continue
            if "scoring" in row and (row.get("scoring") or "").strip() != "boundary":
                continue
            tp += int(row["TP"]); fp += int(row["FP"]); fn += int(row["FN"])
            used = True
        if used:
            n_files += 1
    if not n_files or (tp + fp + fn) == 0:
        return None
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return f"{f1:.2f}", n_files


# Per-metric validation status. status: validated | experimental | deterministic
METRIC_STATUS: dict[str, dict[str, str]] = {
    "scene_pacing": {
        "label": "Scene pacing (cuts/min)",
        "status": "validated",
        "note": f"transition-boundary detection (type-agnostic, ±2s match) "
                f"agrees with human coding at F1 "
                f"{REFERENCE_HARD_CUT_F1_RANGE} across production styles; "
                f"type classification is scored separately and is lower",
    },
    "dissolves": {
        "label": "Dissolve detection",
        "status": "experimental",
        "note": "not yet validated — treat as exploratory; dissolve-heavy shows "
                "may have undercounted transition rates",
    },
    "cut_classification": {
        "label": "Within-scene vs scene-change",
        "status": "experimental",
        "note": "similarity threshold not yet validated against human labels",
    },
    "color_motion_flashing_audio": {
        "label": "Color, motion, flashing, audio",
        "status": "deterministic",
        "note": "direct signal measurements — no detection/classification step "
                "to validate",
    },
    "fantastical_events": {
        "label": "Fantastical events",
        "status": "human",
        "note": "hand-coded by a human; the tool structures the coding, it does "
                "not detect fantasy",
    },
}


def validation_short(validation_dir: Path | None = None) -> str:
    """One-line accuracy statement for compact placements. Deliberately hedged:
    the evidence base is a small, single-coder pilot."""
    live = local_hard_cut_f1(validation_dir)
    if live:
        f1, n = live
        return (f"Detection accuracy (preliminary): transition-BOUNDARY "
                f"detection across all coded transition types — i.e. whether a "
                f"transition was found there, not whether it was labelled "
                f"correctly — agreed with human coding at F1 {f1} "
                f"(±2s match, {n} comparison run(s), single coder; larger "
                f"sample and inter-rater reliability in progress). This is the "
                f"figure the pacing RATE depends on; type classification is "
                f"scored separately and is lower. Accuracy is "
                f"content-dependent. Dissolve/scene-change detection "
                f"experimental; color/motion/flashing/audio are deterministic "
                f"measurements.")
    return (f"Detection accuracy (preliminary): transition-BOUNDARY detection "
            f"on human-coded hard cuts — whether a transition was found there, "
            f"not whether it was labelled correctly — agreed with human coding "
            f"at F1 {REFERENCE_HARD_CUT_F1_RANGE} (±2s match). "
            f"Content-dependent, weakest on dissolve-heavy/low-contrast "
            f"footage. Single-coder pilot; larger sample and inter-rater "
            f"reliability in progress. Type classification is scored "
            f"separately and is lower. Dissolve/scene-change detection "
            f"experimental; color/motion/flashing/audio are deterministic "
            f"measurements.")


def validation_statement(validation_dir: Path | None = None) -> str:
    """Full multi-line honest statement for results views and reports."""
    live = local_hard_cut_f1(validation_dir)
    if live:
        f1, n = live
        pacing = (f"F1 {f1} vs human coding (this install, {n} comparison "
                  f"run(s), single coder)")
    else:
        pacing = (f"F1 {REFERENCE_HARD_CUT_F1_RANGE} vs blind human coding "
                  f"(single-coder pilot)")
    return (
        "How far to trust this measurement (CMAT reports its own accuracy — "
        "PRELIMINARY; small single-coder pilot, inter-rater reliability and a "
        "larger sample in progress):\n"
        f"  • Scene pacing (cuts/min): {pacing}. Content-dependent — weakest "
        "on dissolve-heavy / low-contrast / visually noisy footage.\n"
        "  • Dissolve detection & within-scene/scene-change classification: "
        "EXPERIMENTAL, not yet validated — exploratory only.\n"
        "  • Color, motion, flashing, audio: deterministic signal measurements "
        "(no detection step to validate).\n"
        "  • Fantastical events: human-coded (the tool structures coding, it "
        "does not detect fantasy)."
    )


def validation_dict(validation_dir: Path | None = None) -> dict[str, Any]:
    """Machine-readable provenance for JSON exports."""
    live = local_hard_cut_f1(validation_dir)
    return {
        "statement": "CMAT reports its own detection accuracy against human "
                     "coding. PRELIMINARY — small single-coder pilot; accuracy "
                     "is content-dependent. See validation/VALIDATION_LOG.md.",
        "hard_cut_f1": (live[0] if live else REFERENCE_HARD_CUT_F1_AGG),
        "hard_cut_f1_source": ("local validation runs" if live
                               else "CMAT reference study"),
        "metric_status": {k: {"status": v["status"], "note": v["note"]}
                          for k, v in METRIC_STATUS.items()},
    }
