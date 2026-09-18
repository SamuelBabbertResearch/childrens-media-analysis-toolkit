"""A component-only validation artefact must preserve exact source rows."""

import csv
import json

from analyzer.validation import derive_detection_subset


def test_derive_detection_subset_records_source_and_filter(tmp_path):
    source = tmp_path / "episode__combined_detections.csv"
    with source.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["timestamp_sec", "type"])
        writer.writeheader()
        writer.writerows([
            {"timestamp_sec": "1.0", "type": "hard_cut"},
            {"timestamp_sec": "2.0", "type": "dissolve"},
        ])
    output = tmp_path / "episode__content-solo_detections.csv"

    _, manifest_path = derive_detection_subset(
        source, output, event_type="hard_cut")

    with output.open(newline="", encoding="utf-8") as fh:
        assert list(csv.DictReader(fh)) == [
            {"timestamp_sec": "1.0", "type": "hard_cut"}]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["filter"] == {"type": "hard_cut"}
    assert manifest["source_rows"] == 2
    assert manifest["output_rows"] == 1
    assert len(manifest["source_sha256"]) == 64
