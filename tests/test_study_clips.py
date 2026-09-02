from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import analyzer.metrics_audio as metrics_audio
import analyzer.metrics_cuts as metrics_cuts
import analyzer.recipes as recipes
import analyzer.study_clips as study_clips
from analyzer.config_loader import load_config
from analyzer.measurements import normalize_config, selection
from analyzer.schema import AudioMetrics, MotionMetrics
from analyzer.study_clips import (
    assign_relative_profiles,
    build_pair_candidates,
    config_from_analysis_recipe,
    measure_video_windows,
    select_matched_pairs,
)
from cli import build_parser


def _pool() -> list[dict]:
    rows = []
    idx = 0
    for cuts in (0.0, 1.0, 2.0):
        for motion in (0.01, 0.05, 0.09):
            for audio in (0.02, 0.06, 0.10):
                idx += 1
                rows.append({
                    "clip_id": f"clip-{idx:02d}",
                    "source_path": str(Path(f"episode-{idx:02d}.mp4")),
                    "source_relpath": f"episode-{idx:02d}.mp4",
                    "start_sec": 0.0,
                    "start_timecode": "00:00:00.000",
                    "end_timecode": "00:00:30.000",
                    "duration_sec": 30.0,
                    "cuts_per_min": cuts,
                    "motion_mean": motion,
                    "audio_rms_mean": audio,
                    "audio_available": True,
                })
    return rows


def test_relative_profiles_use_pool_thirds():
    rows = _pool()
    thresholds = assign_relative_profiles(rows)

    assert set(thresholds) == {"cuts", "motion", "audio"}
    assert {row["cuts_level"] for row in rows} == {"low", "middle", "high"}
    assert {row["motion_level"] for row in rows} == {"low", "middle", "high"}
    assert {row["audio_level"] for row in rows} == {"low", "middle", "high"}
    assert any(
        row["feature_profile"]
        == "high cuts | low motion | low audio intensity"
        for row in rows
    )


def test_tied_third_threshold_keeps_values_above_and_below_distinct():
    rows = []
    for idx, cuts in enumerate((18.0, 22.0, 22.0, 34.0), 1):
        rows.append({
            "clip_id": f"tied-{idx}",
            "source_path": f"episode-{idx}.mp4",
            "cuts_per_min": cuts,
            "motion_mean": float(idx),
            "audio_rms_mean": float(idx),
        })
    assign_relative_profiles(rows)
    assert [row["cuts_level"] for row in rows] == [
        "low", "middle", "middle", "high"
    ]


def test_option_35_selection_has_six_pairs_and_twelve_unique_clips():
    rows = _pool()
    assign_relative_profiles(rows)
    candidates = build_pair_candidates(rows)
    selected = select_matched_pairs(candidates)

    assert len(selected) == 6
    assert [pair["feature"] for pair in selected] == [
        "cuts", "cuts", "motion", "motion", "audio", "audio"
    ]
    ids = [
        clip["clip_id"]
        for pair in selected
        for clip in (pair["low"], pair["high"])
    ]
    assert len(ids) == len(set(ids)) == 12
    for pair in selected:
        level_key = f"{pair['feature']}_level"
        assert pair["low"][level_key] == "low"
        assert pair["high"][level_key] == "high"


def test_windowed_audio_decodes_once_and_splits_exact_windows(monkeypatch):
    sample_rate = metrics_audio._SAMPLE_RATE
    first = np.full(sample_rate * 30, 0.1, dtype=np.float32)
    second = np.full(sample_rate * 30, 0.5, dtype=np.float32)
    calls = []

    def fake_extract(_path, **_kwargs):
        calls.append(True)
        return np.concatenate([first, second])

    monkeypatch.setattr(metrics_audio, "_extract_audio", fake_extract)
    measured = metrics_audio.compute_windowed_audio_metrics(
        Path("unused.mp4"), 30.0, 2
    )

    assert len(calls) == 1
    assert measured[0].rms_mean == pytest.approx(0.1, abs=1e-5)
    assert measured[1].rms_mean == pytest.approx(0.5, abs=1e-5)


def test_cli_exposes_study_clip_workflow():
    args = build_parser().parse_args([
        "study-clips", "season", "--window-sec", "30",
        "--exclude-first", "45", "--exclude-last", "75",
        "--recipe", "Study analysis", "--export-selected",
    ])
    assert args.command == "study-clips"
    assert args.window_sec == 30.0
    assert args.exclude_first == 45.0
    assert args.exclude_last == 75.0
    assert args.recipe == "Study analysis"
    assert args.export_selected is True


def _study_recipe(config):
    return recipes.new_recipe(
        "Study analysis", "sensory_load", config,
        measures=[
            ("hard_cuts_per_min", "auto:transitions:pyscenedetect_content"),
            ("motion_mean", "auto:motion:absdiff"),
            ("audio_rms_mean", "auto:audio:ffmpeg_rms"),
        ],
        reason="Freeze the feature-extraction methods for the study",
    )


def test_analysis_recipe_drives_cut_motion_sampling_and_audio_settings():
    pinned_cfg = normalize_config({
        "cut_detection_threshold": 19.0,
        "sample_fps": 3.5,
    })
    recipe = _study_recipe(pinned_cfg)
    live_cfg = normalize_config({
        "cut_detection_threshold": 41.0,
        "sample_fps": 1.0,
    })

    actual = config_from_analysis_recipe(recipe, live_cfg)

    transition_tool, transition_params, _ = selection(actual, "transitions")
    sampling_tool, sampling_params, _ = selection(actual, "sampling")
    motion_tool, _motion_params, _ = selection(actual, "motion")
    audio_tool, _audio_params, _ = selection(actual, "audio")
    assert transition_tool.key == "pyscenedetect_content"
    assert transition_params == {"threshold": 19.0}
    assert sampling_tool.key == "uniform"
    assert sampling_params == {"sample_fps": 3.5}
    assert motion_tool.key == "absdiff"
    assert audio_tool.key == "ffmpeg_rms"


def test_analysis_recipe_refuses_motion_without_pinned_sampling():
    recipe = _study_recipe(load_config())
    motion = recipe.binding("motion_mean")
    assert motion is not None
    motion.parameters = {}

    with pytest.raises(ValueError, match="does not pin motion's shared"):
        config_from_analysis_recipe(recipe, load_config())


def test_episode_exclusions_define_absolute_windows_and_measurement_range(
    tmp_path, monkeypatch
):
    source = tmp_path / "season"
    source.mkdir()
    video = source / "episode.mp4"
    video.write_bytes(b"placeholder")
    calls = {}

    monkeypatch.setattr(study_clips, "_duration", lambda _path: 200.0)

    def fake_cuts(_path, _duration, **kwargs):
        calls["cuts"] = (kwargs["start_sec"], kwargs["end_sec"])
        return [61.0, 89.0, 91.0, 121.0, 149.0]

    def fake_motion(_path, **kwargs):
        calls["motion"] = (kwargs["start_sec"], kwargs["end_sec"])
        return [MotionMetrics(mean=0.1, peak=0.2) for _ in range(3)]

    def fake_audio(_path, _window, _count, **kwargs):
        calls["audio"] = (kwargs["start_sec"], kwargs["end_sec"])
        return [
            AudioMetrics(rms_mean=0.05, rms_peak=0.1, available=True)
            for _ in range(3)
        ]

    monkeypatch.setattr(study_clips, "detect_cut_times", fake_cuts)
    monkeypatch.setattr(study_clips, "compute_windowed_motion", fake_motion)
    monkeypatch.setattr(study_clips, "compute_windowed_audio_metrics", fake_audio)

    rows = measure_video_windows(
        video,
        source,
        load_config(),
        window_sec=30.0,
        exclude_first_sec=60.0,
        exclude_last_sec=50.0,
    )

    assert calls == {
        "cuts": (60.0, 150.0),
        "motion": (60.0, 150.0),
        "audio": (60.0, 150.0),
    }
    assert [row["start_sec"] for row in rows] == [60.0, 90.0, 120.0]
    assert [row["end_sec"] for row in rows] == [90.0, 120.0, 150.0]
    assert [row["cut_count"] for row in rows] == [2, 1, 2]
    assert all(row["excluded_first_sec"] == 60.0 for row in rows)
    assert all(row["excluded_last_sec"] == 50.0 for row in rows)


def test_episode_exclusions_cannot_remove_entire_episode(tmp_path, monkeypatch):
    source = tmp_path / "season"
    source.mkdir()
    video = source / "episode.mp4"
    video.write_bytes(b"placeholder")
    monkeypatch.setattr(study_clips, "_duration", lambda _path: 100.0)

    with pytest.raises(ValueError, match="remove the entire"):
        measure_video_windows(
            video,
            source,
            load_config(),
            exclude_first_sec=60.0,
            exclude_last_sec=40.0,
        )


def test_trimmed_cut_range_uses_seconds_and_preroll(monkeypatch):
    import scenedetect

    captured = {}

    def fake_detect(_path, _detector, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(scenedetect, "detect", fake_detect)
    metrics_cuts._detect_shots(
        Path("unused.mp4"),
        duration_sec=1000.0,
        tool="pyscenedetect_content",
        params={"threshold": 27.0},
        start_sec=60,
        end_sec=420,
    )

    assert captured["start_time"] == 58.0
    assert captured["end_time"] == 420.0
    assert isinstance(captured["end_time"], float)
