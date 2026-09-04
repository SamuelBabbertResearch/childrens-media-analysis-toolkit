from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from generate_study_clip_tables import generate_markdown, generate_tables


PAIR_FIXTURES = (
    ("CUTS_1", "cuts", "Clip A1", "Clip B1"),
    ("CUTS_2", "cuts", "Clip A2", "Clip B2"),
    ("MOTION_1", "motion", "Clip C1-L", "Clip C1-H"),
    ("MOTION_2", "motion", "Clip C2-L", "Clip C2-H"),
    ("AUDIO_1", "audio", "Clip D1-L", "Clip D1-H"),
    ("AUDIO_2", "audio", "Clip D2-L", "Clip D2-H"),
)


def _rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, (pair_id, feature, low_label, high_label) in enumerate(
        PAIR_FIXTURES, 1
    ):
        for level, label, episode in (
            ("low", low_label, f"Episode {index} lower.mp4"),
            ("high", high_label, f"Episode {index} higher.mp4"),
        ):
            rows.append({
                "pair_id": pair_id,
                "study_label": label,
                "target_feature": feature,
                "target_level": level,
                "source_relpath": episode,
                "start_timecode": f"00:0{index}:01.000",
                "end_timecode": f"00:0{index}:31.000",
                "cuts_per_min": str(index * 2 + (1 if level == "high" else 0)),
                "motion_mean": str(index / 100 + (0.005 if level == "high" else 0)),
                "audio_rms_mean": str(index / 1000 + (0.0005 if level == "high" else 0)),
            })
    return rows


class StudyClipTableTests(unittest.TestCase):
    def test_markdown_contains_filenames_spans_and_rating_questions(self):
        candidates = _rows() + [{
            **_rows()[0],
            "study_label": "",
            "source_relpath": "Extreme candidate.mp4",
            "start_timecode": "00:20:00.000",
            "end_timecode": "00:20:30.000",
            "cuts_per_min": "42",
            "motion_mean": "0.25",
            "audio_rms_mean": "0.09",
        }]
        document = generate_markdown(_rows(), candidates)

        self.assertIn("## Clip Inventory", document)
        self.assertIn("## Clip Pairs", document)
        self.assertIn("## Candidate-Pool and Selected-Clip Extremes", document)
        self.assertIn("Episode 1 lower.mp4", document)
        self.assertIn("00:01:01–00:01:31", document)
        self.assertIn(
            "Is the higher-cut clip rated as faster when motion and sound are similar?",
            document,
        )
        self.assertIn(
            "Does the sound-intensity rating pattern replicate", document
        )
        self.assertIn("Clip C1-L — Lower motion", document)
        self.assertNotIn("Lower-motion motion", document)
        self.assertIn("**42 cuts/min**", document)
        self.assertIn("Extreme candidate.mp4", document)

    def test_generate_tables_reads_selected_csv_and_writes_next_to_it(self):
        with tempfile.TemporaryDirectory() as temp:
            run_folder = Path(temp)
            selected = run_folder / "selected_clips.csv"
            candidates = run_folder / "candidates.csv"
            with selected.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(_rows()[0]))
                writer.writeheader()
                writer.writerows(_rows())
            with candidates.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(_rows()[0]))
                writer.writeheader()
                writer.writerows(_rows())

            destination = generate_tables(run_folder)

            self.assertEqual(destination, run_folder / "study_clip_tables.md")
            self.assertTrue(destination.is_file())
            self.assertIn(
                "What the rating contrast helps test",
                destination.read_text(encoding="utf-8"),
            )

    def test_incomplete_selection_refuses_to_make_a_plausible_partial_table(self):
        with self.assertRaisesRegex(ValueError, "missing pairs"):
            generate_markdown(_rows()[:2], _rows())


if __name__ == "__main__":
    unittest.main()
