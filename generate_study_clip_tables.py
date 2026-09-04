"""Generate human-readable study clip inventory and matched-pair tables.

Reads ``selected_clips.csv`` from a CMAT ``study-clips`` output folder and
writes a Markdown document containing the two tables used to organize the
Adult Prediction of Children's Perceived Media Pacing stimulus set.

The script uses only Python's standard library so it can run even when CMAT's
video-analysis dependencies are not active in the current shell.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


PAIR_ORDER = (
    "CUTS_1", "CUTS_2", "MOTION_1", "MOTION_2", "AUDIO_1", "AUDIO_2",
)

EXTREME_MEASURES = (
    ("Cut rate", "cuts_per_min", "cuts/min", 1),
    ("Motion", "motion_mean", "motion mean", 4),
    ("Sound (audio intensity)", "audio_rms_mean", "RMS", 5),
)

FEATURE_TEXT = {
    "cuts": {
        "noun": "cuts",
        "pair_low": "Lower cuts",
        "pair_high": "Higher cuts",
        "comparison": "Cut comparison",
        "exemplar": "Cut exemplar",
        "low": "Lower-cut",
        "high": "Higher-cut",
        "controls": "motion and sound",
    },
    "motion": {
        "noun": "motion",
        "pair_low": "Lower motion",
        "pair_high": "Higher motion",
        "comparison": "Motion comparison",
        "exemplar": "Motion exemplar",
        "low": "Lower-motion",
        "high": "Higher-motion",
        "controls": "cuts and sound",
    },
    "audio": {
        "noun": "sound",
        "pair_low": "Lower sound (audio intensity)",
        "pair_high": "Higher sound (audio intensity)",
        "comparison": "Sound comparison",
        "exemplar": "Sound exemplar",
        "low": "Lower-audio-intensity",
        "high": "Higher-audio-intensity",
        "controls": "cuts and motion",
    },
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"Required CMAT output does not exist: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _short_timecode(value: str) -> str:
    value = (value or "").strip()
    return value[:-4] if value.endswith(".000") else value


def _span(row: dict[str, str]) -> str:
    return f"{_short_timecode(row['start_timecode'])}–{_short_timecode(row['end_timecode'])}"


def _md(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\r\n", "<br>").replace("\n", "<br>")


def _pair_number(pair_id: str) -> int:
    try:
        return int(pair_id.rsplit("_", 1)[1])
    except (IndexError, ValueError) as exc:
        raise ValueError(f"Unrecognized pair id: {pair_id!r}") from exc


def _inventory_role(
    row: dict[str, str],
    partner: dict[str, str],
) -> str:
    feature = row["target_feature"]
    text = FEATURE_TEXT[feature]
    number = _pair_number(row["pair_id"])
    if row["target_level"] == "low":
        return (
            f"{text['comparison']} {number}: {text['low']} clip; "
            f"{text['controls']} matched as closely as possible to "
            f"{partner['study_label']}."
        )
    return (
        f"{text['exemplar']} {number}: {text['high']} clip paired with "
        f"{partner['study_label']}."
    )


def _rating_contrast(feature: str, number: int) -> str:
    if feature == "cuts":
        if number == 1:
            return (
                "Cut rate, exemplar 1: Is the higher-cut clip rated as faster "
                "when motion and sound are similar?"
            )
        return (
            "Cut rate, exemplar 2: Does the cut-rate rating pattern replicate "
            "with a different pair of scenes?"
        )
    if feature == "motion":
        if number == 1:
            return (
                "Motion, exemplar 1: Is the higher-motion clip rated as faster "
                "when cuts and sound are similar?"
            )
        return (
            "Motion, exemplar 2: Does the motion rating pattern replicate with "
            "a different pair of scenes?"
        )
    if feature == "audio":
        if number == 1:
            return (
                "Sound, exemplar 1: Is the higher-audio-intensity clip rated "
                "as faster when cuts and motion are similar?"
            )
        return (
            "Sound, exemplar 2: Does the sound-intensity rating pattern "
            "replicate with a different pair of scenes?"
        )
    raise ValueError(f"Unsupported target feature: {feature!r}")


def _level_columns(row: dict[str, str]) -> tuple[str, str, str]:
    feature = row["target_feature"]
    target = "Low" if row["target_level"] == "low" else "High"
    return (
        target if feature == "cuts" else "Matched",
        target if feature == "motion" else "Matched",
        target if feature == "audio" else "Matched",
    )


def _format_value(value: float, unit: str, decimals: int) -> str:
    rendered = f"{value:.{decimals}f}".rstrip("0").rstrip(".")
    return f"{rendered} {unit}"


def _extreme_cell(
    rows: Iterable[dict[str, str]],
    value_key: str,
    unit: str,
    decimals: int,
    highest: bool,
) -> str:
    measured: list[tuple[float, dict[str, str]]] = []
    for row_number, row in enumerate(rows, 2):
        raw = row.get(value_key)
        if raw in (None, ""):
            continue
        try:
            measured.append((float(raw), row))
        except ValueError as exc:
            raise ValueError(
                f"CSV row {row_number} has nonnumeric {value_key}: {raw!r}"
            ) from exc
    if not measured:
        return "Unavailable"

    extreme = (max if highest else min)(value for value, _row in measured)
    tied = sorted(
        (row for value, row in measured if value == extreme),
        key=lambda row: (
            row.get("study_label", ""), row.get("source_relpath", ""),
            row.get("start_timecode", ""),
        ),
    )
    value_text = _format_value(extreme, unit, decimals)
    details = []
    for row in tied:
        label = f"{row['study_label']} — " if row.get("study_label") else ""
        details.append(
            f"{label}{row.get('source_relpath', 'Unknown source')} — {_span(row)}"
        )
    tie_note = f" ({len(tied)} tied clips)" if len(tied) > 1 else ""
    return f"**{value_text}**{tie_note}<br>" + "<br>".join(details)


def _validate_and_group(
    rows: Iterable[dict[str, str]],
) -> dict[str, dict[str, dict[str, str]]]:
    grouped: dict[str, dict[str, dict[str, str]]] = {}
    required = {
        "pair_id", "study_label", "target_feature", "target_level",
        "source_relpath", "start_timecode", "end_timecode",
    }
    for row_number, row in enumerate(rows, 2):
        missing = sorted(key for key in required if not row.get(key))
        if missing:
            raise ValueError(
                f"selected_clips.csv row {row_number} is missing: "
                f"{', '.join(missing)}"
            )
        if row["target_feature"] not in FEATURE_TEXT:
            raise ValueError(
                f"selected_clips.csv row {row_number} has unsupported feature "
                f"{row['target_feature']!r}"
            )
        if row["target_level"] not in ("low", "high"):
            raise ValueError(
                f"selected_clips.csv row {row_number} has unsupported level "
                f"{row['target_level']!r}"
            )
        pair = grouped.setdefault(row["pair_id"], {})
        if row["target_level"] in pair:
            raise ValueError(
                f"Pair {row['pair_id']} contains more than one "
                f"{row['target_level']} clip"
            )
        pair[row["target_level"]] = row

    absent = [pair_id for pair_id in PAIR_ORDER if pair_id not in grouped]
    extra = sorted(set(grouped) - set(PAIR_ORDER))
    incomplete = [
        pair_id for pair_id in PAIR_ORDER
        if pair_id in grouped and set(grouped[pair_id]) != {"low", "high"}
    ]
    problems = []
    if absent:
        problems.append(f"missing pairs: {', '.join(absent)}")
    if extra:
        problems.append(f"unexpected pairs: {', '.join(extra)}")
    if incomplete:
        problems.append(f"incomplete pairs: {', '.join(incomplete)}")
    if problems:
        raise ValueError("Cannot generate complete study tables; " + "; ".join(problems))
    return grouped


def generate_markdown(
    selected_rows: Iterable[dict[str, str]],
    candidate_rows: Iterable[dict[str, str]],
) -> str:
    """Return both study tables as a Markdown document."""
    selected = list(selected_rows)
    candidates = list(candidate_rows)
    grouped = _validate_and_group(selected)
    lines = [
        "# Adult Prediction of Children's Perceived Media Pacing",
        "",
        "Generated from CMAT's `selected_clips.csv`. Time spans are absolute "
        "positions in the source episode.",
        "",
        "## Clip Inventory",
        "",
        "| Clip | Episode filename | Time span | Cuts | Motion | Sound (audio intensity) | Role |",
        "|---|---|---|---|---|---|---|",
    ]

    for pair_id in PAIR_ORDER:
        pair = grouped[pair_id]
        for level in ("low", "high"):
            row = pair[level]
            partner = pair["high" if level == "low" else "low"]
            cuts, motion, audio = _level_columns(row)
            lines.append(
                "| " + " | ".join(_md(value) for value in (
                    row["study_label"], row["source_relpath"], _span(row),
                    cuts, motion, audio, _inventory_role(row, partner),
                )) + " |"
            )

    lines.extend([
        "",
        "## Candidate-Pool and Selected-Clip Extremes",
        "",
        "“All candidates” refers to every eligible 30-second window in "
        "`candidates.csv`; “selected” refers to the 12 proposed study clips.",
        "",
        "| Measure | Highest among all candidates | Highest among selected clips | Lowest among all candidates | Lowest among selected clips |",
        "|---|---|---|---|---|",
    ])
    for label, value_key, unit, decimals in EXTREME_MEASURES:
        lines.append(
            "| " + " | ".join(_md(value) for value in (
                label,
                _extreme_cell(candidates, value_key, unit, decimals, True),
                _extreme_cell(selected, value_key, unit, decimals, True),
                _extreme_cell(candidates, value_key, unit, decimals, False),
                _extreme_cell(selected, value_key, unit, decimals, False),
            )) + " |"
        )

    lines.extend([
        "",
        "## Clip Pairs",
        "",
        "| Matched pair | Lower / comparison clip | Higher / feature clip | What the rating contrast helps test |",
        "|---|---|---|---|",
    ])
    for overall_number, pair_id in enumerate(PAIR_ORDER, 1):
        pair = grouped[pair_id]
        low, high = pair["low"], pair["high"]
        feature = low["target_feature"]
        if high["target_feature"] != feature:
            raise ValueError(f"Pair {pair_id} has inconsistent target features")
        number = _pair_number(pair_id)
        low_cell = (
            f"{low['study_label']} — {FEATURE_TEXT[feature]['pair_low']}"
            f"<br>{low['source_relpath']}<br>{_span(low)}"
        )
        high_cell = (
            f"{high['study_label']} — {FEATURE_TEXT[feature]['pair_high']}"
            f"<br>{high['source_relpath']}<br>{_span(high)}"
        )
        lines.append(
            "| " + " | ".join(_md(value) for value in (
                f"Pair {overall_number}", low_cell, high_cell,
                _rating_contrast(feature, number),
            )) + " |"
        )

    lines.append("")
    return "\n".join(lines)


def generate_tables(run_folder: Path, output: Path | None = None) -> Path:
    run_folder = Path(run_folder).resolve()
    selected_path = run_folder / "selected_clips.csv"
    candidates_path = run_folder / "candidates.csv"
    selected_rows = _read_csv(selected_path)
    candidate_rows = _read_csv(candidates_path)
    destination = (
        Path(output).resolve() if output else run_folder / "study_clip_tables.md"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        generate_markdown(selected_rows, candidate_rows), encoding="utf-8"
    )
    return destination


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Markdown clip inventory and matched-pair tables from "
            "a CMAT study-clips output folder."
        )
    )
    parser.add_argument(
        "run_folder",
        nargs="?",
        default=(
            ".analysis/study_clips/Curious George Full Season One HD"
        ),
        help=(
            "Folder containing selected_clips.csv (default: the Curious "
            "George HD study run under .analysis/study_clips)"
        ),
    )
    parser.add_argument(
        "--output",
        help="Destination .md file (default: <run folder>/study_clip_tables.md)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        path = generate_tables(Path(args.run_folder), Path(args.output) if args.output else None)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Error: {exc}") from exc
    print(f"Study clip tables generated: {path}")


if __name__ == "__main__":
    main()
