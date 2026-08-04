"""Phase 0 tests — schema validity and show/episode discovery."""

import json
from pathlib import Path

import pytest

from analyzer.schema import EpisodeResult, ShowAggregate
from analyzer.show_index import list_shows, list_episodes
from analyzer.engine import analyze_episode

# ---------------------------------------------------------------------------
# Locate test assets
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent
LITTLE_BEAR = ROOT / "Little Bear"
LITTLE_BEAR_EP = LITTLE_BEAR / "LittleBear.mp4"
SKIP_IF_NO_SHOW = pytest.mark.skipif(
    not LITTLE_BEAR.exists(), reason="Little Bear folder not present"
)


# ---------------------------------------------------------------------------
# Schema round-trip tests (no video required)
# ---------------------------------------------------------------------------

def test_episode_result_to_dict_has_required_keys():
    result = EpisodeResult(file="test.mp4", duration_sec=600.0)
    d = result.to_dict()
    assert "file" in d
    assert "duration_sec" in d
    assert "metrics" in d
    assert "config" in d
    assert "status" in d


def test_episode_result_json_is_valid():
    result = EpisodeResult(file="test.mp4", duration_sec=600.0)
    parsed = json.loads(result.to_json())
    assert parsed["file"] == "test.mp4"


def test_show_aggregate_to_dict_has_required_keys():
    agg = ShowAggregate(show_name="TestShow", episode_count=3)
    d = agg.to_dict()
    assert d["show_name"] == "TestShow"
    assert "sensory_load_score" in d


# ---------------------------------------------------------------------------
# Show / episode discovery
# ---------------------------------------------------------------------------

@SKIP_IF_NO_SHOW
def test_list_shows_finds_little_bear():
    shows = list_shows(ROOT)
    names = [s.name for s in shows]
    assert "Little Bear" in names


@SKIP_IF_NO_SHOW
def test_list_episodes_finds_mp4():
    eps = list_episodes(LITTLE_BEAR)
    assert len(eps) >= 1
    assert all(ep.suffix == ".mp4" for ep in eps)


# ---------------------------------------------------------------------------
# Stub engine smoke test (requires the actual file)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not LITTLE_BEAR_EP.exists(), reason="LittleBear.mp4 not present")
def test_analyze_episode_stub_returns_valid_schema():
    result = analyze_episode(LITTLE_BEAR_EP)
    assert result.status == "ok"
    assert result.duration_sec > 0
    d = result.to_dict()
    # All stub metric values should be numeric (0.0 is fine for Phase 0)
    assert isinstance(d["metrics"]["sensory_load"]["score"], float)
    assert isinstance(d["metrics"]["shot_length"]["count"], int)


def test_analyze_episode_missing_file_returns_failed():
    result = analyze_episode(Path("nonexistent.mp4"))
    assert result.status == "failed"
    assert result.error != ""
