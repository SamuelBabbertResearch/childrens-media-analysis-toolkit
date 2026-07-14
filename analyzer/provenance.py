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
REFERENCE_HARD_CUT_F1_RANGE = "0.84–0.96"
REFERENCE_HARD_CUT_F1_AGG = "0.91"


def local_hard_cut_f1(validation_dir: Path | None = None) -> tuple[str, int] | None:
    """Live aggregate hard-cut F1 from this install's comparison CSVs, or None."""
    try:
        from .validation import aggregate_summary
        res = aggregate_summary(validation_dir)
    except Exception:
        return None
    if not res.get("n_files"):
        return None
    for row in res["rows"]:
        if row["type"] == "hard_cut":
            return (f"{row['F1']:.2f}" if isinstance(row["F1"], float)
                    else str(row["F1"])), res["n_files"]
    return None


# Per-metric validation status. status: validated | experimental | deterministic
METRIC_STATUS: dict[str, dict[str, str]] = {
    "scene_pacing": {
        "label": "Scene pacing (cuts/min)",
        "status": "validated",
        "note": f"hard-cut detection agrees with blind human coding at "
                f"F1 {REFERENCE_HARD_CUT_F1_RANGE} across production styles",
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
        return (f"Detection accuracy (preliminary): hard-cut detection (basis "
                f"of the pacing metric) agreed with human coding at F1 {f1} "
                f"({n} comparison run(s), single coder — larger sample and "
                f"inter-rater reliability in progress). Accuracy is "
                f"content-dependent. Dissolve/scene-change detection "
                f"experimental; color/motion/flashing/audio are deterministic "
                f"measurements.")
    return (f"Detection accuracy (preliminary): hard-cut detection (basis of "
            f"the pacing metric) agreed with human coding at F1 "
            f"{REFERENCE_HARD_CUT_F1_RANGE} — content-dependent, weakest on "
            f"dissolve-heavy/low-contrast footage. Single-coder pilot; larger "
            f"sample and inter-rater reliability in progress. Dissolve/"
            f"scene-change detection experimental; color/motion/flashing/audio "
            f"are deterministic measurements.")


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
