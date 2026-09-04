from __future__ import annotations

import csv
import hashlib
import json

import pytest

from study_runner.core import PackageError, ResponseStore, load_package


def _package(tmp_path, *, status="pilot"):
    root = tmp_path / "study"
    clips = root / "clips"
    clips.mkdir(parents=True)
    stimuli = []
    for i in range(12):
        label = f"C{i + 1:02d}"
        path = clips / f"{label}.mp4"
        path.write_bytes(f"test clip {i}".encode())
        stimuli.append({
            "label": label,
            "source_file_id": f"frozen-{label}",
            "pair_id": f"pair-{i // 2 + 1}",
            "file": f"clips/{label}.mp4",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    config = {
        "schema_version": 2,
        "study_id": "pace-pilot",
        "status": status,
        "study_title": "Adult Perceptions of Pacing in Children’s Television",
        "question_id": "adult_pacing_self_v1",
        "participant_question": "How fast did this video feel?",
        "instructions": [
            "Watch 12 clips.",
            "Rate how fast each clip felt to you.",
            "You may skip or stop at any time.",
        ],
        "practice": {
            "prompt": "Which response means neither slow nor fast?",
            "expected_rating": 3,
        },
        "debrief": "Thank you. Please tell the researcher you are finished.",
        "rating_anchors": ["Very slow", "Slow", "In between", "Fast", "Very fast"],
        "stimuli": stimuli,
        "order_conditions": {
            "A": [s["label"] for s in stimuli],
            "B": [s["label"] for s in reversed(stimuli)],
        },
    }
    (root / "study_config.json").write_text(json.dumps(config), encoding="utf-8")
    return root


def test_frozen_package_loads_and_resolves_an_explicit_order(tmp_path):
    package = load_package(_package(tmp_path))
    assert len(package.stimuli) == 12
    assert [s.label for s in package.order("B")] == [
        f"C{i:02d}" for i in range(12, 0, -1)]


def test_draft_refuses_participant_use(tmp_path):
    root = _package(tmp_path, status="draft")
    with pytest.raises(PackageError, match="Draft package"):
        load_package(root)
    assert load_package(root, allow_draft=True).status == "draft"


def test_changed_stimulus_fails_closed(tmp_path):
    root = _package(tmp_path)
    (root / "clips" / "C04.mp4").write_bytes(b"changed after freeze")
    with pytest.raises(PackageError, match="checksum mismatch: C04"):
        load_package(root)


def test_every_order_must_be_a_permutation_of_all_clips(tmp_path):
    root = _package(tmp_path)
    path = root / "study_config.json"
    config = json.loads(path.read_text())
    config["order_conditions"]["A"][-1] = "C01"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(PackageError, match="not a permutation"):
        load_package(root)


def test_duplicate_stimulus_content_is_refused(tmp_path):
    root = _package(tmp_path)
    path = root / "study_config.json"
    config = json.loads(path.read_text())
    config["stimuli"][1]["sha256"] = config["stimuli"][0]["sha256"]
    with pytest.raises(PackageError, match="content is duplicated"):
        path.write_text(json.dumps(config), encoding="utf-8")
        load_package(root, verify_media=False)


def test_response_store_writes_adult_self_row_and_locks_a_response(tmp_path):
    package = load_package(_package(tmp_path))
    store = ResponseStore(tmp_path / "data", package, "A-001")
    stimulus = package.order("A")[0]
    store.append_rating(stimulus=stimulus, trial_order=1, rating=4)
    with pytest.raises(ValueError, match="already locked"):
        store.append_rating(stimulus=stimulus, trial_order=1, rating=3)

    with (tmp_path / "data" / "responses.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [row["block_type"] for row in rows] == ["adult_self"]
    assert rows[0]["package_hash"] == package.package_hash
    assert rows[0]["rating"] == "4"
    assert rows[0]["question_id"] == "adult_pacing_self_v1"


def test_orders_alternate_automatically_and_duplicate_ids_are_refused(tmp_path):
    package = load_package(_package(tmp_path))
    first = ResponseStore(tmp_path / "data", package, "A-001")
    second = ResponseStore(tmp_path / "data", package, "A-002")
    third = ResponseStore(tmp_path / "data", package, "A-003")
    assert [first.condition, second.condition, third.condition] == ["A", "B", "A"]
    with pytest.raises(ValueError, match="already been assigned"):
        ResponseStore(tmp_path / "data", package, "A-002")


def test_skipped_trial_is_explicit_and_has_no_invented_rating(tmp_path):
    package = load_package(_package(tmp_path))
    store = ResponseStore(tmp_path / "data", package, "A-001")
    store.append_skip(stimulus=package.order("A")[0], trial_order=1)
    with (tmp_path / "data" / "responses.csv").open(newline="", encoding="utf-8") as fh:
        row = next(csv.DictReader(fh))
    assert row["completion_status"] == "skipped"
    assert row["rating"] == ""


def test_withdrawal_removes_session_ratings_but_keeps_assignment(tmp_path):
    package = load_package(_package(tmp_path))
    store = ResponseStore(tmp_path / "data", package, "A-001")
    store.append_rating(stimulus=package.order("A")[0], trial_order=1, rating=2)
    store.withdraw()
    with (tmp_path / "data" / "responses.csv").open(newline="", encoding="utf-8") as fh:
        assert list(csv.DictReader(fh)) == []
    with (tmp_path / "data" / "assignments.csv").open(newline="", encoding="utf-8") as fh:
        assert len(list(csv.DictReader(fh))) == 1


def test_superseded_schema_is_refused_even_if_media_are_valid(tmp_path):
    root = _package(tmp_path)
    path = root / "study_config.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config["schema_version"] = 1
    config["target_age_wording"] = "a child"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(PackageError, match="schema_version 2"):
        load_package(root)
