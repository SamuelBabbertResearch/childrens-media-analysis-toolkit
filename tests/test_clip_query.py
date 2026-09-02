"""Finding windows in a candidate pool: the properties a found set relies on.

Each test here guards a way a result set could be wrong while looking right —
strings compared as strings, an unmeasured window sorting as the quietest one,
a filter nobody can state afterwards.
"""

from __future__ import annotations

import codecs
import json

import pytest

from analyzer.study_clips import _write_csv
from analyzer.clip_query import (
    CandidatePool,
    ClipQuery,
    PoolError,
    Range,
    coerce_row,
    export_manifest,
    label_for_export,
    load_pool,
    sort_rows,
)

FIELDS = [
    "clip_id", "source_file", "source_relpath", "source_path", "window_index",
    "start_sec", "end_sec", "start_timecode", "end_timecode", "duration_sec",
    "is_full_window", "cut_count", "cuts_per_min", "motion_mean",
    "audio_rms_mean", "audio_available", "cuts_level", "motion_level",
    "audio_level", "cuts_percentile", "motion_percentile", "audio_percentile",
]


def _row(n: int, *, cuts=10.0, motion=0.05, audio=0.03, episode="E01.mp4",
         cuts_level="middle", motion_level="middle", audio_level="middle",
         full=True, audio_available=True, start=0.0):
    return {
        "clip_id": f"clip_{n}",
        "source_file": episode,
        "source_relpath": episode,
        "source_path": f"C:/shows/{episode}",
        "window_index": n,
        "start_sec": start,
        "end_sec": start + 30.0,
        "start_timecode": "00:00:00.000",
        "end_timecode": "00:00:30.000",
        "duration_sec": 30.0,
        "is_full_window": full,
        "cut_count": 5,
        "cuts_per_min": cuts,
        "motion_mean": motion,
        "audio_rms_mean": audio,
        "audio_available": audio_available,
        "cuts_level": cuts_level,
        "motion_level": motion_level,
        "audio_level": audio_level,
        "cuts_percentile": 0.5,
        "motion_percentile": 0.5,
        "audio_percentile": 0.5,
    }


def _write_run(tmp_path, rows, manifest=None):
    """Write a run folder using the engine's OWN writer.

    Hand-rolling the CSV here is what hid a real defect: `_write_csv` emits a
    byte-order mark and a fixture written with plain utf-8 does not, so the
    loader read the first column fine in every test and lost it against every
    real run. A fixture that does not go through the production writer is not
    a fixture of the artefact.
    """
    run = tmp_path / "run"
    run.mkdir(exist_ok=True)
    _write_csv(run / "candidates.csv",
               [{k: row.get(k) for k in FIELDS} for row in rows])
    if manifest is not None:
        (run / "manifest.json").write_text(json.dumps(manifest),
                                           encoding="utf-8")
    return run


# --- loading ----------------------------------------------------------------

def test_csv_numbers_come_back_as_numbers(tmp_path):
    run = _write_run(tmp_path, [_row(1, cuts=9.0), _row(2, cuts=10.0)])
    pool = load_pool(run)
    values = [row["cuts_per_min"] for row in pool.rows]
    assert values == [9.0, 10.0]
    assert all(isinstance(v, float) for v in values)
    # The string comparison this prevents: "10.0" < "9.0" is True.
    assert max(values) == 10.0


def test_booleans_survive_the_round_trip(tmp_path):
    run = _write_run(tmp_path, [_row(1, full=False, audio_available=False)])
    row = load_pool(run).rows[0]
    assert row["is_full_window"] is False
    assert row["audio_available"] is False


def test_an_empty_measurement_is_none_not_zero():
    row = coerce_row({"audio_rms_mean": "", "cuts_per_min": "4"})
    assert row["audio_rms_mean"] is None
    assert row["cuts_per_min"] == 4.0


def test_a_folder_that_is_not_a_run_says_so(tmp_path):
    with pytest.raises(PoolError, match="not a measured candidate pool"):
        load_pool(tmp_path)


def test_an_empty_pool_is_refused(tmp_path):
    run = _write_run(tmp_path, [])
    with pytest.raises(PoolError, match="no measured windows"):
        load_pool(run)


def test_the_pool_states_how_it_was_measured(tmp_path):
    manifest = {
        "source_dir": "C:/shows/Season 1",
        "source_file_count": 3,
        "window_sec": 30.0,
        "exclude_first_sec_per_episode": 5,
        "exclude_last_sec_per_episode": 0,
        "include_partial_windows": False,
        "measurement_fingerprint": "abc123",
        "relative_level_definition": "Bottom and top thirds of this pool.",
        "analysis_recipe": {"citation": "Pacing — conservative v2"},
    }
    pool = load_pool(_write_run(tmp_path, [_row(1)], manifest))
    labels = dict(pool.provenance())
    assert labels["Measurement fingerprint"] == "abc123"
    assert labels["Window length"] == "30 s"
    assert labels["Analysis recipe"] == "Pacing — conservative v2"
    # The definition is the run's own words, not this module's.
    assert labels["Level definition"] == "Bottom and top thirds of this pool."


def test_a_run_with_no_manifest_still_loads(tmp_path):
    pool = load_pool(_write_run(tmp_path, [_row(1)]))
    assert len(pool.rows) == 1
    assert pool.fingerprint == ""
    assert pool.level_definition == ""


# --- querying ---------------------------------------------------------------

def test_an_empty_query_matches_everything():
    rows = [_row(1), _row(2, cuts=40.0)]
    assert len(ClipQuery().apply(rows)) == 2


def test_a_range_is_inclusive_at_both_ends():
    rows = [_row(1, cuts=4.0), _row(2, cuts=10.0), _row(3, cuts=26.0)]
    found = ClipQuery(ranges={"cuts": Range(4.0, 10.0)}).apply(rows)
    assert [r["cuts_per_min"] for r in found] == [4.0, 10.0]


def test_an_open_ended_range_works_from_either_side():
    rows = [_row(1, cuts=4.0), _row(2, cuts=26.0)]
    assert len(ClipQuery(ranges={"cuts": Range(low=20.0)}).apply(rows)) == 1
    assert len(ClipQuery(ranges={"cuts": Range(high=10.0)}).apply(rows)) == 1


def test_an_unmeasured_value_never_satisfies_a_bound():
    rows = [_row(1, audio=None, audio_available=False)]
    assert ClipQuery(ranges={"audio": Range(high=1.0)}).apply(rows) == []
    # ...and is not silently treated as zero by an open range either.
    assert len(ClipQuery().apply(rows)) == 1


def test_levels_filter_and_an_empty_set_means_any():
    rows = [_row(1, cuts_level="low"), _row(2, cuts_level="high")]
    assert len(ClipQuery(levels={"cuts": frozenset({"high"})}).apply(rows)) == 1
    assert len(ClipQuery(levels={"cuts": frozenset()}).apply(rows)) == 2


def test_filters_combine_as_and():
    rows = [
        _row(1, cuts=30.0, motion_level="low"),
        _row(2, cuts=30.0, motion_level="high"),
        _row(3, cuts=4.0, motion_level="low"),
    ]
    query = ClipQuery(ranges={"cuts": Range(low=20.0)},
                      levels={"motion": frozenset({"low"})})
    assert [r["clip_id"] for r in query.apply(rows)] == ["clip_1"]


def test_episode_match_is_a_case_insensitive_substring():
    rows = [_row(1, episode="S01E03 Zoo.mp4"), _row(2, episode="S01E04.mp4")]
    assert len(ClipQuery(episode="zoo").apply(rows)) == 1


def test_partial_windows_and_missing_audio_can_be_excluded():
    rows = [_row(1, full=False), _row(2, audio_available=False), _row(3)]
    assert len(ClipQuery(full_windows_only=True).apply(rows)) == 2
    assert len(ClipQuery(audio_available_only=True).apply(rows)) == 2


def test_an_unknown_feature_is_refused():
    with pytest.raises(ValueError, match="unknown feature"):
        ClipQuery(ranges={"saturation": Range(1.0, 2.0)})


def test_an_unknown_level_is_refused():
    with pytest.raises(ValueError, match="unknown level"):
        ClipQuery(levels={"cuts": frozenset({"fast"})})


def test_an_inverted_range_is_refused():
    with pytest.raises(ValueError, match="above high"):
        Range(30.0, 4.0)


def test_a_query_states_itself_in_one_line():
    query = ClipQuery(ranges={"cuts": Range(low=20.0)},
                      levels={"motion": frozenset({"low"})},
                      episode="Zoo", full_windows_only=True)
    described = query.describe()
    assert "cuts ≥ 20 cuts/min" in described
    assert "motion level low" in described
    assert "Zoo" in described
    assert "whole windows only" in described


def test_an_empty_query_says_so_rather_than_saying_nothing():
    assert ClipQuery().describe() == "every window in the pool"


# --- sorting ----------------------------------------------------------------

def test_unmeasured_values_sort_last_in_both_directions():
    rows = [_row(1, audio=None), _row(2, audio=0.09), _row(3, audio=0.01)]
    ascending = sort_rows(rows, "audio_rms_mean")
    descending = sort_rows(rows, "audio_rms_mean", descending=True)
    assert [r["clip_id"] for r in ascending] == ["clip_3", "clip_2", "clip_1"]
    assert [r["clip_id"] for r in descending] == ["clip_2", "clip_3", "clip_1"]


# --- export -----------------------------------------------------------------

def test_labelling_does_not_edit_the_pool():
    rows = [_row(1)]
    labelled = label_for_export(rows)
    assert "study_label" in labelled[0]
    assert "study_label" not in rows[0]


def test_labels_are_unique_and_carry_episode_and_start():
    rows = [_row(1, episode="S01E03 Zoo.mp4", start=0.0),
            _row(2, episode="S01E03 Zoo.mp4", start=90.0)]
    labels = [r["study_label"] for r in label_for_export(rows)]
    assert len(set(labels)) == 2
    assert labels[0] == "F01_S01E03_Zoo_00000s"
    assert labels[1] == "F02_S01E03_Zoo_00090s"


def test_the_export_manifest_records_the_question_and_the_method(tmp_path):
    pool = load_pool(_write_run(
        tmp_path, [_row(1, cuts=30.0)],
        {"measurement_fingerprint": "abc123",
         "source_dir": "C:/shows/Season 1",
         "relative_level_definition": "Thirds of this pool."}))
    query = ClipQuery(ranges={"cuts": Range(low=20.0)})
    found = label_for_export(query.apply(pool.rows))
    manifest = export_manifest(pool, query, found)
    assert manifest["measurement_fingerprint"] == "abc123"
    assert manifest["query"] == "cuts ≥ 20 cuts/min"
    assert manifest["pool_window_count"] == 1
    assert manifest["matched_window_count"] == 1
    assert manifest["clips"][0]["cuts_per_min"] == 30.0


def test_export_rows_carry_what_the_exporter_needs(tmp_path):
    """`study_clips.export_selected_clips` reads these four keys."""
    rows = label_for_export([_row(1)])
    for key in ("study_label", "start_sec", "duration_sec", "source_path"):
        assert rows[0].get(key) is not None


def test_a_byte_order_mark_does_not_eat_the_first_column(tmp_path):
    """The engine writes candidates.csv as utf-8-sig.

    Read as plain utf-8 the first header keeps the mark: every row
    silently loses its clip_id, and the Window column renders empty in
    the finder rather than wrong. Checked against the bytes on disk, not
    against a fixture that happens to agree.
    """
    run = _write_run(tmp_path, [_row(1)])
    assert (run / "candidates.csv").read_bytes().startswith(codecs.BOM_UTF8)
    row = load_pool(run).rows[0]
    assert row["clip_id"] == "clip_1"
    assert not any(key.startswith("﻿") for key in row)
