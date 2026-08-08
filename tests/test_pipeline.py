"""
Pipeline model — grouping, stage status, and progress.

The visualizer is only worth having if it is accurate, so these tests pin the
claims it makes on screen: how many episodes are measured, which stage the user
is actually in, and that nothing silently disappears from view.
"""

from __future__ import annotations
import json
from pathlib import Path

import pytest

from analyzer import pipeline as P


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

def test_empty_pipeline_still_teaches_the_workflow():
    """A first-time user with no data must still see all five stages."""
    p = P.empty_pipeline()
    assert [s.key for s in p.stages] == P.STAGE_KEYS
    assert all(s.explanation for s in p.stages), "every stage explains itself"
    assert p.stages[0].next_action, "the first stage tells them where to start"


def test_every_stage_has_a_human_readable_status():
    for stage in P.empty_pipeline().stages:
        assert stage.status_label
        assert stage.status_label != stage.status, "label is prose, not a key"


def test_progress_counts_partial_stages_as_half():
    p = P.empty_pipeline()
    for s in p.stages:
        s.status = P.COMPLETE
    assert p.progress == 1.0
    p.stages[0].status = P.PARTIAL
    assert p.progress == pytest.approx(1 - 0.5 / len(p.stages))
    for s in p.stages:
        s.status = P.PENDING
    assert p.progress == 0.0


def test_current_stage_is_the_first_unfinished_one():
    p = P.empty_pipeline()
    for s in p.stages:
        s.status = P.COMPLETE
    p.stages[3].status = P.PARTIAL
    assert p.current_stage.key == p.stages[3].key


def test_current_stage_falls_back_to_last_when_all_complete():
    p = P.empty_pipeline()
    for s in p.stages:
        s.status = P.COMPLETE
    assert p.current_stage.key == "results"


# ---------------------------------------------------------------------------
# Cache detection
# ---------------------------------------------------------------------------

def test_cached_stems_globs_nested_show_folders(tmp_path):
    """Cache keys are nested by show and category; stems must be found at depth."""
    cache = tmp_path / ".analysis"
    (cache / "ShowA").mkdir(parents=True)
    (cache / "Category" / "ShowB" / "Season 1").mkdir(parents=True)
    (cache / "ShowA" / "ep01.json").write_text("{}", encoding="utf-8")
    (cache / "Category" / "ShowB" / "Season 1" / "ep99.json").write_text(
        "{}", encoding="utf-8")
    (cache / "ShowA" / "aggregate.json").write_text("{}", encoding="utf-8")

    stems = P.cached_stems(tmp_path)
    assert stems == {"ep01", "ep99"}, "aggregate.json is not an episode"


def test_cached_stems_handles_missing_cache(tmp_path):
    assert P.cached_stems(tmp_path) == set()
    assert P.cached_stems(None) == set()


def test_count_analyzed_matches_on_stem_not_path(tmp_path):
    """Sampler CSVs hold absolute paths that need not match the library layout."""
    episodes = [Path(r"D:\somewhere\else\ep01.mp4"), Path("ep99.mp4")]
    assert P._count_analyzed(tmp_path, episodes, {"ep01", "ep99"}) == 2
    assert P._count_analyzed(tmp_path, episodes, {"ep01"}) == 1
    assert P._count_analyzed(tmp_path, [], {"ep01"}) == 0


# ---------------------------------------------------------------------------
# Stage logic
# ---------------------------------------------------------------------------

def test_sampling_without_a_manifest_is_flagged_not_hidden():
    s = P._sampling_stage(None, None)
    assert s.status == P.PENDING
    assert "No formal sample" in s.headline
    assert s.next_action, "tells the user how to make it reproducible"


def test_sampling_reports_the_seed_and_sample_type():
    s = P._sampling_stage({
        "total_selected": 9, "total_available": 11, "method": "stratified",
        "seed": 42, "probability": True, "generated_at_utc": "2026-08-01T00:00:00",
    }, None)
    assert s.status == P.COMPLETE
    assert s.headline == "9 of 11 episodes"
    detail = dict(s.details)
    assert detail["Random seed"] == "42"
    assert detail["Sample type"] == "probability sample"


def test_non_probability_sample_carries_an_inference_warning():
    s = P._sampling_stage({"total_selected": 3, "total_available": 9,
                           "method": "hand-picked", "probability": False}, None)
    assert "non-probability" in dict(s.details)["Sample type"]
    assert "inference" in s.next_action


def test_validation_is_blocked_without_hand_coding():
    """Validation compares tool to human — with no human coding it cannot start."""
    s = P._validation_stage([], {"n_transition_coded": 0, "n_event_coded": 0})
    assert s.status == P.BLOCKED
    assert "Hand-code at least one episode" in s.next_action


def test_validation_is_pending_when_coding_exists_but_no_run():
    s = P._validation_stage([], {"n_transition_coded": 2, "n_event_coded": 0})
    assert s.status == P.PENDING
    assert "no comparison run" in s.next_action


def test_validation_warns_when_evidence_is_thin():
    trials = [{"kind": "transition_validation", "result": "F1 0.85"}]
    s = P._validation_stage(trials, {"n_transition_coded": 1, "n_event_coded": 0})
    assert s.status == P.PARTIAL
    assert "content-dependent" in s.next_action
    assert "inter-rater" in s.next_action


# ---------------------------------------------------------------------------
# Discovery / grouping
# ---------------------------------------------------------------------------

def _write_sample(dirpath: Path, name: str, episodes: list[str]) -> None:
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / "manifest.json").write_text(json.dumps({
        "trial_name": name, "method": "stratified", "seed": 1,
        "total_selected": len(episodes), "total_available": len(episodes) + 3,
        "probability": True, "entry_id": name,
        "generated_at_utc": "2026-08-01T12:00:00",
    }), encoding="utf-8")
    rows = "filepath\n" + "\n".join(f"C:/vids/{e}.mp4" for e in episodes)
    (dirpath / "selected.csv").write_text(rows, encoding="utf-8")


def test_build_pipelines_groups_a_sample_with_its_episodes(tmp_path):
    vdir = tmp_path / "validation"
    _write_sample(vdir / "draw1", "Draw One", ["ep01", "ep02"])
    pipelines = P.build_pipelines(root=None, validation_dir=vdir)
    named = [p for p in pipelines if p.name == "Draw One"]
    assert len(named) == 1
    assert named[0].episode_count == 2
    assert [s.key for s in named[0].stages] == P.STAGE_KEYS


def test_build_pipelines_never_returns_an_unusable_shape(tmp_path):
    """Whatever is on disk, every pipeline must have the full stage list."""
    for p in P.build_pipelines(root=None, validation_dir=tmp_path / "nope"):
        assert [s.key for s in p.stages] == P.STAGE_KEYS


def test_plural_reads_naturally():
    assert P._plural(1, "episode") == "1 episode"
    assert P._plural(0, "episode") == "0 episodes"
    assert P._plural(2, "episode") == "2 episodes"
    assert P._plural(1, "comparison run") == "1 comparison run"
