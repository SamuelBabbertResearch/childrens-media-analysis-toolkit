"""Assemble the adult-only correction-06 package for CMAT Study Runner.

This copies immutable media; it never edits the study-workflow evidence files.
The output is explicitly status=pilot, not an IRB-approved collection release.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SELECTION = ROOT / (
    ".analysis/study_workflow/stimulus_replacement/"
    "cuts2_low_replacement_method-automated-with-visual-review_recipe-v1_2026-08-23_correction-06/"
    "selected_clips_method-automated-with-visual-review_recipe-v1_2026-08-23_correction-06.csv")
REPLACEMENT = ROOT / (
    ".analysis/study_workflow/stimulus_replacement/"
    "cuts2_low_replacement_method-automated-with-visual-review_recipe-v1_2026-08-23_correction-06/"
    "CUTS2_LOW_REPLACEMENT_stimulus_method-automated_recipe-v1_2026-08-23_correction-06.mp4")
CODING_MEDIA = ROOT / (
    ".analysis/study_workflow/wave_1_manual/"
    "coding_media_wave1_method-manual_recipe-v1_2026-08-22_correction-02")
CODING_MANIFEST = CODING_MEDIA / (
    "wave1_coding_media_manifest_method-manual_recipe-v1_2026-08-22_correction-02.json")

# Pair partners are six positions apart; neither pilot order puts them adjacent.
ORDER_A = [
    "Clip A1", "Clip C1-L", "Clip D1-L", "Clip A2", "Clip C2-L", "Clip D2-L",
    "Clip B1", "Clip C1-H", "Clip D1-H", "Clip B2", "Clip C2-H", "Clip D2-H",
]
ORDER_B = list(reversed(ORDER_A))


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def media_map() -> dict[str, Path]:
    manifest = json.loads(CODING_MANIFEST.read_text(encoding="utf-8"))
    return {item["clip_id"]: CODING_MEDIA / item["media_filename"]
            for item in manifest["clips"]}


def media_for(row: dict[str, str], originals: dict[str, Path]) -> Path:
    if row["study_label"] == "Clip A2":
        return REPLACEMENT
    try:
        return originals[row["clip_id"]]
    except KeyError as exc:
        raise RuntimeError(f"No frozen coding media for {row['clip_id']}") from exc


def assert_orders(labels: set[str], pairs: dict[str, str]) -> None:
    for name, order in (("A", ORDER_A), ("B", ORDER_B)):
        if len(order) != 12 or set(order) != labels:
            raise RuntimeError(f"Order {name} is not a 12-clip permutation")
        for left, right in zip(order, order[1:]):
            if pairs[left] == pairs[right]:
                raise RuntimeError(f"Order {name} places pair {pairs[left]} adjacent")


def build(output: Path) -> Path:
    output = output.resolve()
    clips = output / "clips"
    clips.mkdir(parents=True, exist_ok=True)
    with SELECTION.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != 12:
        raise RuntimeError(f"Correction-06 selection has {len(rows)} rows, not 12")
    originals = media_map()

    stimuli = []
    pairs: dict[str, str] = {}
    for index, row in enumerate(rows, 1):
        source = media_for(row, originals)
        label = row["study_label"]
        filename = f"{index:02d}_{label.replace(' ', '_')}.mp4"
        destination = clips / filename
        shutil.copy2(source, destination)
        actual = digest(destination)
        if digest(source) != actual:
            raise RuntimeError(f"Copy verification failed for {label}")
        pairs[label] = row["pair_id"]
        stimuli.append({
            "label": label,
            "source_file_id": row["clip_id"],
            "pair_id": row["pair_id"],
            "file": f"clips/{filename}",
            "sha256": actual,
        })
    assert_orders({s["label"] for s in stimuli}, pairs)

    config = {
        "schema_version": 2,
        "study_id": "adult-perceptions-pacing-childrens-tv-pilot-correction-06",
        "status": "pilot",
        "study_title": "Adult Perceptions of Pacing in Children’s Television",
        "question_id": "adult_pacing_self_v1",
        "participant_question": "How fast did this video feel?",
        "instructions": [
            "You will watch 12 short clips from a children’s television show.",
            "After each clip, rate how fast or slow the clip felt to you. Use your own impression; there are no correct answers.",
            "Each clip is played once. You may skip a question or stop participating at any time without penalty.",
        ],
        "practice": {
            "prompt": "Practice: Which response means neither slow nor fast?",
            "expected_rating": 3,
        },
        "debrief": (
            "Thank you for participating. Please tell the researcher that "
            "the session is complete. You may ask the researcher any questions."
        ),
        "rating_anchors": ["Very slow", "Slow", "In between", "Fast", "Very fast"],
        "stimuli": stimuli,
        "order_conditions": {"PILOT-A": ORDER_A, "PILOT-B": ORDER_B},
        "provenance": {
            "selection_authority": str(SELECTION.relative_to(ROOT)).replace("\\", "/"),
            "selection_sha256": digest(SELECTION),
            "stimulus_revision": "correction-06",
            "package_purpose": "adult-only software pilot; not approved data collection",
        },
    }
    config_path = output / "study_config.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config_path


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "dist" / "CMAT Study Runner" / "study",
        help="study package folder to create or update",
    )
    return parser.parse_args()


if __name__ == "__main__":
    print(build(_args().output))
