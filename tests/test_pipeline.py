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
# A node fed by more than one Sampling node
# ---------------------------------------------------------------------------

def test_merged_pipeline_unions_coverage_across_samples(tmp_path):
    """The real point of per-node sample binding for Validation: hand-coding
    coverage from BOTH branches must be reflected, not just one."""
    vdir = tmp_path / "validation"
    _write_sample(vdir / "draw_a", "Draw A", ["ep01", "ep02"])
    _write_sample(vdir / "draw_b", "Draw B", ["ep03"])
    (vdir / "ep01_manual.csv").write_text("dummy", encoding="utf-8")
    (vdir / "ep03_manual.csv").write_text("dummy", encoding="utf-8")

    pipelines = P.build_pipelines(root=None, validation_dir=vdir)
    a = next(p for p in pipelines if p.name == "Draw A")
    b = next(p for p in pipelines if p.name == "Draw B")

    # Each sample alone only sees its own coded episode.
    assert dict(a.stage("validation").details)["Hand-coded episodes available"] == "1"
    assert dict(b.stage("validation").details)["Hand-coded episodes available"] == "1"

    merged = P.merged_pipeline([a, b], validation_dir=vdir)
    assert dict(merged.stage("validation").details)["Hand-coded episodes available"] == "2", \
        "the union of both samples' episodes has 2 coded, not 1"


def _same_stem_pipelines(tmp_path):
    root = tmp_path / "Library"
    episodes = [root / "Show A" / "S01 E01.mp4",
                root / "Show B" / "S01 E01.mp4"]
    vdir = tmp_path / "validation"
    for i, episode in enumerate(episodes):
        episode.parent.mkdir(parents=True, exist_ok=True)
        episode.write_bytes(b"")
        draw = vdir / f"draw_{i}"
        _write_sample(draw, f"Draw {i}", ["placeholder"])
        (draw / "selected.csv").write_text(
            f"filepath\n{episode.as_posix()}\n", encoding="utf-8")
    return root, vdir


def test_merged_coverage_does_not_reuse_one_sheet_for_two_shows(tmp_path):
    """A bare S01 E01 sheet cannot prove that both shows' S01 E01 was coded."""
    root, vdir = _same_stem_pipelines(tmp_path)
    (vdir / "S01 E01_manual.csv").write_text("dummy", encoding="utf-8")

    pipelines = P.build_pipelines(root=root, validation_dir=vdir)
    merged = P.merged_pipeline(pipelines, root=root, validation_dir=vdir)

    assert dict(merged.stage("validation").details)[
        "Hand-coded episodes available"] == "0"


def test_merged_coverage_namespaces_same_stem_by_show_key(tmp_path):
    root, vdir = _same_stem_pipelines(tmp_path)
    for show in ("Show A", "Show B"):
        folder = vdir / show
        folder.mkdir(parents=True)
        (folder / "S01 E01_manual.csv").write_text("dummy", encoding="utf-8")

    pipelines = P.build_pipelines(root=root, validation_dir=vdir)
    merged = P.merged_pipeline(pipelines, root=root, validation_dir=vdir)

    assert dict(merged.stage("validation").details)[
        "Hand-coded episodes available"] == "2"


def test_merged_pipeline_unions_episodes_across_samples(tmp_path):
    """The reported symptom, reproduced directly: two Sampling nodes wired
    into one Selection node must show BOTH shows' episodes, not just one."""
    vdir = tmp_path / "validation"
    _write_sample(vdir / "draw_a", "Draw A", ["little_bear_e01", "little_bear_e02"])
    _write_sample(vdir / "draw_b", "Draw B", ["curious_george_e01"])

    pipelines = P.build_pipelines(root=None, validation_dir=vdir)
    a = next(p for p in pipelines if p.name == "Draw A")
    b = next(p for p in pipelines if p.name == "Draw B")
    assert a.episode_count == 2 and b.episode_count == 1

    merged = P.merged_pipeline([a, b], validation_dir=vdir)
    assert merged.episode_count == 3, \
        "merging must show all 3 episodes, not silently only the first branch's"
    selection = merged.stage("selection")
    assert selection is not None and selection.status != P.BLOCKED


def test_merged_pipeline_deduplicates_a_shared_trial_record():
    """Two samples that happen to share a coded episode must not double-count
    its comparison run just because both pipelines' trial lists carry it."""
    shared = {"kind": "transition_validation",
             "manifest_path": Path("shared_manifest.json"), "result": "F1 0.9"}
    only_a = {"kind": "transition_validation",
             "manifest_path": Path("a_manifest.json"), "result": "F1 0.8"}
    a = P.Pipeline(key="sample:a", name="A", description="", stages=[],
                   trials=[shared, only_a], folder=None)
    b = P.Pipeline(key="sample:b", name="B", description="", stages=[],
                   trials=[shared], folder=None)

    merged = P.merged_pipeline([a, b])
    assert dict(merged.stage("validation").details)["Comparison runs"] == "2"


def test_merged_pipeline_deduplicates_a_shared_episode(tmp_path):
    """Two samples that happen to draw the SAME episode must count it once."""
    import csv as _csv

    def _draw(dirpath: Path, episodes: list[str]) -> None:
        dirpath.mkdir(parents=True, exist_ok=True)
        (dirpath / "manifest.json").write_text(json.dumps({
            "method": "systematic", "total_selected": len(episodes),
        }), encoding="utf-8")
        with (dirpath / "selected.csv").open("w", newline="", encoding="utf-8") as fh:
            w = _csv.DictWriter(fh, fieldnames=["filepath"])
            w.writeheader()
            for e in episodes:
                w.writerow({"filepath": f"C:/vids/{e}.mp4"})

    _draw(tmp_path / "a", ["shared_ep", "only_a"])
    _draw(tmp_path / "b", ["shared_ep", "only_b"])
    a = P.Pipeline(key="sample:a", name="A", description="", stages=[],
                   folder=tmp_path / "a")
    b = P.Pipeline(key="sample:b", name="B", description="", stages=[],
                   folder=tmp_path / "b")

    merged = P.merged_pipeline([a, b])
    assert merged.episode_count == 3, "shared_ep counted once, not twice"


# ---------------------------------------------------------------------------
# Validation subsets
# ---------------------------------------------------------------------------

def _hand_stage(coded: int, total: int) -> P.Stage:
    return P._handcode_stage("handcode_transitions", "Hand-code transitions",
                             "sub", "expl", coded, total, "CODEBOOK.md")


def test_subset_target_replaces_whole_sample_arithmetic():
    """'0/20 coded, 20 to go' is wrong advice when only 4 need coding."""
    stage = _hand_stage(coded=0, total=20)
    assert "0/20" in stage.headline

    scoped = P.rescope_to_target(stage, target=4, total=20)
    assert "0/4" in scoped.headline
    assert "20" not in scoped.headline
    assert "4" in scoped.next_action


def test_subset_is_complete_at_the_target_not_at_the_sample_size():
    scoped = P.rescope_to_target(_hand_stage(4, 20), target=4, total=20)
    assert scoped.status == P.COMPLETE
    assert "second coder" in scoped.next_action


def test_subset_progress_is_partial_partway_through():
    scoped = P.rescope_to_target(_hand_stage(2, 20), target=4, total=20)
    assert scoped.status == P.PARTIAL
    assert "2/4" in scoped.headline


def test_coding_past_the_target_does_not_overflow():
    scoped = P.rescope_to_target(_hand_stage(9, 20), target=4, total=20)
    assert scoped.headline.startswith("4/4")
    assert scoped.status == P.COMPLETE
    assert dict(scoped.details)["Coded so far"] == "9"


def test_target_cannot_exceed_the_sample():
    """A preset default of 4 must not ask for 4 of 2 episodes."""
    scoped = P.rescope_to_target(_hand_stage(0, 2), target=4, total=2)
    assert scoped.headline.startswith("0/2")
    assert dict(scoped.details)["Subset target"] == "2 episodes"


def test_no_target_leaves_the_stage_alone():
    stage = _hand_stage(3, 20)
    assert P.rescope_to_target(stage, target=0, total=20) is stage


def test_subset_stage_explains_why_it_is_a_subset():
    scoped = P.rescope_to_target(_hand_stage(0, 20), target=4, total=20)
    assert any("whole sample" in v for _, v in scoped.details)


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
