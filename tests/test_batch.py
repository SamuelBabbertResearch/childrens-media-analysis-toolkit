"""
Phase 2 tests — batch runner, aggregation, cache, and corrupt-file handling.
"""

from __future__ import annotations
import json
import shutil
from pathlib import Path

import pytest

from analyzer.batch import analyze_show_batch
from analyzer.aggregate import compute_show_aggregate, save_show_results, results_to_dataframe
from analyzer.cache import load_cached, save_cache, cache_path
from analyzer.schema import EpisodeResult, ShowAggregate

ROOT = Path(__file__).parent.parent
LITTLE_BEAR_DIR = ROOT / "Little Bear"
SKIP_IF_NO_SHOW = pytest.mark.skipif(
    not LITTLE_BEAR_DIR.exists(), reason="Little Bear folder not present"
)


# ---------------------------------------------------------------------------
# Aggregate stats — unit tests (no video)
# ---------------------------------------------------------------------------

def _fake_result(name: str, cuts: float, sat: float, motion: float,
                 flash: float, load: float) -> EpisodeResult:
    r = EpisodeResult(file=name, duration_sec=600.0)
    r.metrics.scene_pacing.cuts_per_min = cuts
    r.metrics.color_saturation.mean = sat
    r.metrics.motion.mean = motion
    r.metrics.flashing.luminance_delta_events_per_min = flash
    r.metrics.sensory_load.score = load
    return r


def test_aggregate_mean_correct():
    results = [
        _fake_result("ep1.mp4", cuts=10.0, sat=0.3, motion=0.05, flash=2.0, load=0.2),
        _fake_result("ep2.mp4", cuts=20.0, sat=0.5, motion=0.10, flash=4.0, load=0.4),
    ]
    agg = compute_show_aggregate("TestShow", results)
    assert agg.cuts_per_min.mean == pytest.approx(15.0)
    assert agg.sensory_load_score.mean == pytest.approx(0.3)
    assert agg.episode_count == 2
    assert agg.failed_count == 0


def test_aggregate_excludes_failed_episodes():
    ok = _fake_result("ep1.mp4", cuts=10.0, sat=0.3, motion=0.05, flash=2.0, load=0.2)
    bad = EpisodeResult(file="corrupt.mp4", status="failed", error="unreadable")
    agg = compute_show_aggregate("TestShow", [ok, bad])
    assert agg.episode_count == 2
    assert agg.failed_count == 1
    # Stats computed only from ok episode
    assert agg.cuts_per_min.mean == pytest.approx(10.0)


def test_aggregate_to_dict_has_all_fields():
    agg = ShowAggregate(show_name="X", episode_count=1)
    d = agg.to_dict()
    for key in ["show_name", "episode_count", "failed_count",
                "sensory_load_score", "cuts_per_min"]:
        assert key in d


def test_results_to_dataframe_columns():
    results = [_fake_result("ep1.mp4", 10, 0.3, 0.05, 2.0, 0.2)]
    results[0].metrics.motion.source_fps = 24.0
    results[0].metrics.motion.requested_sample_fps = 10.0
    results[0].metrics.motion.effective_sample_fps = 12.0
    results[0].metrics.motion.frame_interval = 2
    results[0].metrics.flashing.source_fps = 24.0
    results[0].metrics.sensory_load.input_variant = "audio_visual"
    df = results_to_dataframe(results)
    assert "file" in df.columns
    assert "sensory_load_score" in df.columns
    assert "cuts_per_min" in df.columns
    assert df.loc[0, "frame_effective_sample_fps"] == 12.0
    assert df.loc[0, "frame_interval"] == 2
    assert df.loc[0, "flashing_source_fps"] == 24.0
    assert df.loc[0, "ffc_input_variant"] == "audio_visual"
    assert len(df) == 1


# ---------------------------------------------------------------------------
# Cache round-trip — unit tests (no video)
# ---------------------------------------------------------------------------

def test_cache_save_and_load(tmp_path):
    result = EpisodeResult(file="ep.mp4", duration_sec=300.0)
    save_cache(tmp_path, "MyShow", "ep", result.to_dict())
    loaded = load_cached(tmp_path, "MyShow", "ep")
    assert loaded is not None
    assert loaded["file"] == "ep.mp4"
    assert loaded["duration_sec"] == pytest.approx(300.0)


def test_cache_miss_returns_none(tmp_path):
    assert load_cached(tmp_path, "NoShow", "ep") is None


def test_episode_result_from_dict_roundtrip():
    original = EpisodeResult(file="ep.mp4", duration_sec=500.0)
    original.metrics.scene_pacing.cuts_per_min = 12.5
    original.metrics.sensory_load.score = 0.25
    reconstructed = EpisodeResult.from_dict(original.to_dict())
    assert reconstructed.file == "ep.mp4"
    assert reconstructed.duration_sec == pytest.approx(500.0)
    assert reconstructed.metrics.scene_pacing.cuts_per_min == pytest.approx(12.5)
    assert reconstructed.metrics.sensory_load.score == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# Corrupt file — must be skipped, not fatal
# ---------------------------------------------------------------------------

def test_corrupt_file_skipped_not_fatal(tmp_path):
    """A deliberately corrupt MP4 must not crash the batch runner."""
    show_dir = tmp_path / "TestShow"
    show_dir.mkdir()
    corrupt = show_dir / "corrupt.mp4"
    corrupt.write_bytes(b"this is not a valid video file")

    results = analyze_show_batch(show_dir, root=tmp_path)

    assert len(results) == 1
    assert results[0].status == "failed"
    assert results[0].file == "corrupt.mp4"


# ---------------------------------------------------------------------------
# Batch runner — against real Little Bear folder
# ---------------------------------------------------------------------------

@SKIP_IF_NO_SHOW
def test_batch_uses_cache(tmp_path):
    """Second run should use cache and return identical results faster."""
    # First run — writes cache
    results1 = analyze_show_batch(LITTLE_BEAR_DIR, root=tmp_path)
    assert all(r.status in ("ok", "failed") for r in results1)

    # Second run — patch load_cached where batch.py imported it (not on the module)
    import analyzer.batch as batch_mod
    from analyzer.cache import load_cached as real_load

    hits: list[str] = []

    def spy_load(root, show, stem):
        result = real_load(root, show, stem)
        if result is not None:
            hits.append(stem)
        return result

    batch_mod.load_cached = spy_load
    try:
        results2 = analyze_show_batch(LITTLE_BEAR_DIR, root=tmp_path)
    finally:
        batch_mod.load_cached = real_load

    assert len(hits) == len(results1), "Expected all episodes to be served from cache"
    assert len(results2) == len(results1)


@SKIP_IF_NO_SHOW
def test_batch_and_aggregate_e2e(tmp_path):
    """Full end-to-end: batch analyze → aggregate → write files."""
    results = analyze_show_batch(LITTLE_BEAR_DIR, root=tmp_path)
    ok = [r for r in results if r.status == "ok"]
    assert len(ok) >= 1

    agg = compute_show_aggregate("Little Bear", results)
    assert agg.episode_count >= 1
    assert 0.0 <= agg.sensory_load_score.mean <= 1.0

    json_path, csv_path = save_show_results(tmp_path, "Little Bear", results, agg)
    assert json_path.exists()
    assert csv_path.exists()

    # Verify CSV has the right number of rows
    import pandas as pd
    df = pd.read_csv(csv_path)
    assert len(df) == len(results)
    assert "sensory_load_score" in df.columns
