from __future__ import annotations

import csv

import pytest

from ui.pair_cut_marker import build_pair_cut_marker


def _write_selected(run, video):
    fields = [
        "pair_id", "target_feature", "study_label", "target_level", "clip_id",
        "source_relpath", "source_path", "start_sec", "end_sec", "duration_sec",
        "start_timecode", "end_timecode", "cuts_per_min",
    ]
    rows = [
        ["AUDIO_1", "audio", "Clip D1-L", "low", "low-id", video.name,
         str(video), 455, 485, 30, "00:07:35", "00:08:05", 8],
        ["AUDIO_1", "audio", "Clip D1-H", "high", "high-id", video.name,
         str(video), 1265, 1295, 30, "00:21:05", "00:21:35", 8],
    ]
    with (run / "selected_clips.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)
        writer.writerows(rows)


def test_browser_marker_contains_both_windows_and_timestamp_controls(tmp_path):
    video = tmp_path / "episode.mp4"
    video.touch()
    _write_selected(tmp_path, video)

    page = build_pair_cut_marker(tmp_path)
    html = page.read_text(encoding="utf-8")

    assert page.name == "hand_code_matched_pairs.html"
    assert "Mark hard cut (M)" in html
    assert "Download coding CSV" in html
    assert '"studyLabel": "Clip D1-L"' in html
    assert '"start": 455.0' in html
    assert "cut_timestamp_within_clip_sec" in html
    assert "contentStatus" in html


def test_browser_marker_refuses_missing_source_video(tmp_path):
    missing = tmp_path / "missing.mp4"
    _write_selected(tmp_path, missing)
    with pytest.raises(FileNotFoundError, match="Source episode not found"):
        build_pair_cut_marker(tmp_path)
