"""
Validation provenance — the single source of truth for CMAT's self-reported
accuracy, shown on every results view, export, and the public site.

This is the claim NVivo and every other coding tool structurally cannot make:
CMAT states how far to trust its own automated detection, measured against
blind human coding. The statement is honest per-metric — validated,
experimental, unvalidated, or "deterministic (no detection step to validate)"
— never a single blanket F1.

KEEP THIS IN STEP WITH THE REGISTRY. `analyzer/measurements.py` holds each
tool's validation status and is the authority; `METRIC_STATUS` below is the
prose the reader sees. When the two disagreed — flashing was described here as
deterministic while the registry marked it unvalidated — the wrong claim went
into every PDF, every CSV provenance sidecar and the public site, because this
is the module all of them read. `tests/test_provenance.py` now pins them
together.

When local validation runs exist (comparison CSVs under validation/), the
boundary figure is computed live from them; otherwise the reference figure from
CMAT's validation study is used.

NAMING. The headline figure is BOUNDARY detection scored on the `ALL` row — was
a transition found here, across every transition type a human coded. It is not
hard-cut-only, and the hard_cut-only figures for the same runs exist and differ
(0.841 / 0.964). Everything here is named `boundary` for that reason; the old
`hard_cut` spelling survives only in JSON files written before 2026-08-14, which
are schema 1. See `PROVENANCE_SCHEMA`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Reference figures from CMAT's validation study (see validation/VALIDATION_LOG.md).
#
# RESOLVED 2026-08-14 by recomputing from the comparison CSVs on disk. The
# constants below are current. They cover TWO episodes scored against the
# SHIPPED detector (`content-t27-diss`), ALL row, type-agnostic boundary
# matching at +/-2s:
#
#   A Charlie Brown Christmas 1965   TP  32 FP 10 FN 11  -> F1 0.753
#   Little Bear 1x01                 TP  71 FP  4 FN 10  -> F1 0.910
#   pooled                           TP 103 FP 14 FN 21  -> F1 0.855
#
# That is the 0.75-0.91 range and the 0.85 aggregate exactly. TransNetV2
# (`transnet-t0.5-solo`) scores 0.902 / 0.942, pooled 0.928, and is reported
# separately - never blended into these.
#
# The superseded "0.84 to 0.96, aggregate ~0.91" figure was NOT a different
# measurement of the same thing. It was the hard_cut-TYPE-ONLY basis for the
# same two runs (CB 0.841, LB 0.964), and its aggregate additionally
# double-counted reruns across mixed detector configs. The 2026-08-08 log entry
# changed the published basis to the clean ALL row and says it supersedes the
# earlier entries; this comment had simply not been updated to match.
#
# RENAMED 2026-08-14 from REFERENCE_HARD_CUT_F1_*. The old name was the trap
# that produced the contradiction above: it says hard_cut for a figure scored
# type-agnostically, and the hard_cut-only figures for these same two runs
# really exist (0.841 / 0.964). A name pointing at a real but different number
# is worse than a vague one — a reader has no way to notice.
REFERENCE_BOUNDARY_F1_RANGE = "0.75–0.91"
REFERENCE_BOUNDARY_F1_AGG = "0.85"

# What those numbers are, in one string, so no consumer has to infer it from a
# field name. Exported alongside the figure for exactly that reason.
REFERENCE_BOUNDARY_F1_BASIS = (
    "transition-boundary detection, ALL row (every coded transition type), "
    "matched type-agnostically within ±2 s, detector content-t27-diss, "
    "2 episodes scored over their FIRST ~5 MINUTES ONLY (0–300 s and 0–320 s; "
    "~10 min of video in total), hand coding quantised to whole seconds and "
    "biased ~0.55 s early, single coder, PRELIMINARY")


def local_boundary_f1(validation_dir: Path | None = None,
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
                f"{REFERENCE_BOUNDARY_F1_RANGE} across production styles; "
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
    "color_motion_audio": {
        "label": "Color, motion, audio",
        "status": "deterministic",
        "note": "direct signal measurements — no detection/classification step "
                "to validate. Motion is deterministic with the shipped "
                "frame-differencing tool; the optional Farneback optical-flow "
                "tool is unvalidated",
    },
    # Flashing was lumped in with colour and audio as "deterministic — no
    # detection step to validate". The COMPUTATION is deterministic, but that
    # phrasing claims the measure needs no validation, and this one does: it
    # is a whole-frame luminance mean that implements neither the area
    # threshold nor the red-flash criterion broadcast photosensitivity
    # guidance specifies. `analyzer/measurements.py` marks it UNVALIDATED and
    # `CLAUDE.md` §2.2 names it as such; this module feeds every PDF, every
    # CSV provenance sidecar and the public site, so the mismatch was
    # published rather than merely internal.
    "flashing": {
        "label": "Flashing",
        "status": "unvalidated",
        "note": "a whole-frame luminance mean, never graded against human "
                "coding. It implements NEITHER the area threshold NOR the "
                "red-flash criterion that broadcast photosensitivity guidance "
                "specifies, so it is not a safety assessment and must not be "
                "read as one. It compares episodes measured the same way — "
                "nothing more",
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
    live = local_boundary_f1(validation_dir)
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
                f"experimental. Colour, motion and audio are deterministic "
                f"measurements; FLASHING is unvalidated and is not a safety "
                f"assessment.")
    return (f"Detection accuracy (preliminary): transition-BOUNDARY detection "
            f"on human-coded hard cuts — whether a transition was found there, "
            f"not whether it was labelled correctly — agreed with human coding "
            f"at F1 {REFERENCE_BOUNDARY_F1_RANGE} (±2s match). "
            f"Content-dependent, weakest on dissolve-heavy/low-contrast "
            f"footage. Single-coder pilot; larger sample and inter-rater "
            f"reliability in progress. Type classification is scored "
            f"separately and is lower. Dissolve/scene-change detection "
            f"experimental. Colour, motion and audio are deterministic "
            f"measurements; FLASHING is unvalidated and is not a safety "
            f"assessment.")


def validation_statement(validation_dir: Path | None = None) -> str:
    """Full multi-line honest statement for results views and reports."""
    live = local_boundary_f1(validation_dir)
    if live:
        f1, n = live
        pacing = (f"F1 {f1} vs human coding (this install, {n} comparison "
                  f"run(s), single coder)")
    else:
        pacing = (f"F1 {REFERENCE_BOUNDARY_F1_RANGE} vs blind human coding "
                  f"(single-coder pilot)")
    return (
        "How far to trust this measurement (CMAT reports its own accuracy — "
        "PRELIMINARY; small single-coder pilot, inter-rater reliability and a "
        "larger sample in progress):\n"
        f"  • Scene pacing (cuts/min): {pacing}. Content-dependent — weakest "
        "on dissolve-heavy / low-contrast / visually noisy footage.\n"
        "  • Dissolve detection & within-scene/scene-change classification: "
        "EXPERIMENTAL, not yet validated — exploratory only.\n"
        "  • Colour, motion, audio: deterministic signal measurements (no "
        "detection step to validate).\n"
        "  • Flashing: UNVALIDATED. A whole-frame luminance mean that "
        "implements neither the area threshold nor the red-flash criterion "
        "broadcast photosensitivity guidance specifies. It is NOT a safety "
        "assessment; it compares episodes measured the same way.\n"
        "  • Fantastical events: human-coded (the tool structures coding, it "
        "does not detect fantasy)."
    )


# Bumped when the shape or the MEANING of a key in validation_dict() changes,
# so a file written by an older build is identifiable by inspection rather than
# by guessing which era it came from.
#   1  (unversioned) — `hard_cut_f1` / `hard_cut_f1_source`. The figure was
#      never hard-cut-only; the key was a misnomer for a type-agnostic ALL-row
#      score. A file with no `provenance_schema` key is schema 1.
#   2  2026-08-14 — renamed to `boundary_f1` / `boundary_f1_source`, and
#      `boundary_f1_basis` added. Same number, honest name, and the file now
#      states what the figure is instead of implying it in a field name.
PROVENANCE_SCHEMA = 2


def validation_dict(validation_dir: Path | None = None) -> dict[str, Any]:
    """Machine-readable provenance for JSON exports.

    The key is `boundary_f1`, NOT `hard_cut_f1` (schema 1, superseded): the
    figure is scored on the ALL row, so the old name pointed at a real but
    different pair of numbers (0.841 / 0.964). Nothing in CMAT reads this block
    back — it exists for whoever opens the exported file — which is why
    `boundary_f1_basis` travels with the number rather than living only here.
    """
    live = local_boundary_f1(validation_dir)
    return {
        "provenance_schema": PROVENANCE_SCHEMA,
        "statement": "CMAT reports its own detection accuracy against human "
                     "coding. PRELIMINARY — small single-coder pilot; accuracy "
                     "is content-dependent. See validation/VALIDATION_LOG.md.",
        "boundary_f1": (live[0] if live else REFERENCE_BOUNDARY_F1_AGG),
        "boundary_f1_source": ("local validation runs" if live
                               else "CMAT reference study"),
        # The basis must describe the figure ACTUALLY exported. A live figure
        # is pooled over however many comparison runs this install has, which
        # is not the reference study's two episodes.
        "boundary_f1_basis": (
            f"transition-boundary detection, ALL row (every coded transition "
            f"type), matched type-agnostically within ±2 s, detector "
            f"content-t27-diss, pooled over {live[1]} comparison run(s) in "
            f"this install — each scored over a WINDOW recorded in its own "
            f"comparison manifest, not necessarily a whole episode; hand "
            f"coding may be quantised to whole seconds, single coder, "
            f"PRELIMINARY"
            if live else REFERENCE_BOUNDARY_F1_BASIS),
        "metric_status": {k: {"status": v["status"], "note": v["note"]}
                          for k, v in METRIC_STATUS.items()},
    }
