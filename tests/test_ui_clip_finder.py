"""The Clip Finder screen: that the controls reach the query and the data.

A control that exists is not a feature that works, so these drive the widgets
and read what came back — the filter the engine would be given, the rows the
table actually holds, and what an unmeasured value renders as.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt

from analyzer.clip_query import COLUMNS
from tests.test_clip_query import _row, _write_run
from ui.clip_finder import NO_BOUND, ClipFinderDialog, PoolWorker, _Cancelled

MANIFEST = {
    "source_dir": "C:/shows/Season 1",
    "source_file_count": 2,
    "window_sec": 30.0,
    "exclude_first_sec_per_episode": 0,
    "exclude_last_sec_per_episode": 0,
    "measurement_fingerprint": "fp-abc123",
    "relative_level_definition": "Bottom and top thirds of this pool.",
}


def _pool_dialog(qapp, tmp_path, rows=None):
    rows = rows or [
        _row(1, cuts=4.0, cuts_level="low", episode="S01E01.mp4", start=0.0),
        _row(2, cuts=18.0, cuts_level="middle", episode="S01E01.mp4", start=30.0),
        _row(3, cuts=30.0, cuts_level="high", episode="S01E02 Zoo.mp4", start=0.0),
    ]
    run = _write_run(tmp_path, rows, MANIFEST)
    dialog = ClipFinderDialog(run_dir=run)
    return dialog


# --- loading and display ----------------------------------------------------

def test_a_measured_run_fills_the_table(qapp, tmp_path):
    dialog = _pool_dialog(qapp, tmp_path)
    assert dialog._table.rowCount() == 3
    assert "3 of 3 measured windows match" in dialog._count.text()
    dialog.close()


def test_the_screen_states_how_the_numbers_were_made(qapp, tmp_path):
    dialog = _pool_dialog(qapp, tmp_path)
    shown = dialog._provenance.text()
    assert "fp-abc123" in shown
    assert "Bottom and top thirds of this pool." in shown
    dialog.close()


def test_an_unmeasured_value_is_not_drawn_as_a_number(qapp, tmp_path):
    dialog = _pool_dialog(qapp, tmp_path, rows=[
        _row(1, audio=None, audio_available=False)])
    column = [key for key, _ in COLUMNS].index("audio_rms_mean")
    assert dialog._table.item(0, column).text() == "—"
    dialog.close()


def test_a_folder_with_no_pool_leaves_the_screen_empty(qapp, tmp_path):
    dialog = ClipFinderDialog(source_dir=tmp_path)
    assert dialog._pool is None
    assert dialog._table.rowCount() == 0
    assert not dialog._btn_export.isEnabled()
    dialog.close()


# --- the filter reaching the query ------------------------------------------

def test_an_untouched_filter_asks_for_everything(qapp, tmp_path):
    dialog = _pool_dialog(qapp, tmp_path)
    dialog._whole_only.setChecked(False)
    assert dialog.query().describe() == "every window in the pool"
    dialog.close()


def test_a_minimum_reaches_the_query_and_the_table(qapp, tmp_path):
    dialog = _pool_dialog(qapp, tmp_path)
    dialog._mins["cuts"].setValue(20.0)
    assert dialog.query().ranges["cuts"].low == 20.0
    assert dialog._table.rowCount() == 1
    assert "1 of 3" in dialog._count.text()
    dialog.close()


def test_a_level_choice_reaches_the_query(qapp, tmp_path):
    dialog = _pool_dialog(qapp, tmp_path)
    combo = dialog._levels["cuts"]
    combo.setCurrentIndex(combo.findData("low"))
    assert dialog.query().levels["cuts"] == frozenset({"low"})
    assert dialog._table.rowCount() == 1
    dialog.close()


def test_the_episode_filter_reaches_the_table(qapp, tmp_path):
    dialog = _pool_dialog(qapp, tmp_path)
    dialog._episode.setText("zoo")
    assert dialog._table.rowCount() == 1
    dialog.close()


def test_the_query_line_says_what_was_asked(qapp, tmp_path):
    dialog = _pool_dialog(qapp, tmp_path)
    dialog._mins["cuts"].setValue(20.0)
    assert "cuts ≥ 20 cuts/min" in dialog._query_line.text()
    dialog.close()


def test_an_empty_result_says_so_rather_than_looking_broken(qapp, tmp_path):
    dialog = _pool_dialog(qapp, tmp_path)
    dialog._mins["cuts"].setValue(500.0)
    assert dialog._table.rowCount() == 0
    assert "No window in this pool" in dialog._count.text()
    dialog.close()


def test_reset_clears_every_filter(qapp, tmp_path):
    dialog = _pool_dialog(qapp, tmp_path)
    dialog._mins["cuts"].setValue(20.0)
    dialog._episode.setText("zoo")
    dialog._levels["cuts"].setCurrentIndex(1)
    dialog._reset_filters()
    assert dialog._mins["cuts"].value() == NO_BOUND
    assert dialog._episode.text() == ""
    assert dialog._levels["cuts"].currentData() == ""
    assert dialog._table.rowCount() == 3
    dialog.close()


def test_a_reversed_pair_of_bounds_is_read_the_way_round_that_can_match(
        qapp, tmp_path):
    """Typing 30 into "at least" and 4 into "at most" must not silently
    produce an empty screen that looks like an empty pool."""
    dialog = _pool_dialog(qapp, tmp_path)
    dialog._mins["cuts"].setValue(30.0)
    dialog._maxes["cuts"].setValue(4.0)
    bound = dialog.query().ranges["cuts"]
    assert (bound.low, bound.high) == (4.0, 30.0)
    dialog.close()


# --- ordering ---------------------------------------------------------------

def test_clicking_a_header_sorts_and_clicking_again_reverses(qapp, tmp_path):
    dialog = _pool_dialog(qapp, tmp_path)
    column = [key for key, _ in COLUMNS].index("cuts_per_min")
    dialog._on_sort(column)
    assert [r["cuts_per_min"] for r in dialog._shown] == [4.0, 18.0, 30.0]
    dialog._on_sort(column)
    assert [r["cuts_per_min"] for r in dialog._shown] == [30.0, 18.0, 4.0]
    dialog.close()


# --- export -----------------------------------------------------------------

def test_export_is_disabled_until_rows_are_chosen(qapp, tmp_path):
    dialog = _pool_dialog(qapp, tmp_path)
    assert not dialog._btn_export.isEnabled()
    dialog._table.selectRow(0)
    assert dialog._btn_export.isEnabled()
    assert "Export 1 Selected Clip…" == dialog._btn_export.text()
    dialog.close()


def test_selected_rows_are_the_rows_on_screen_not_the_pool(qapp, tmp_path):
    dialog = _pool_dialog(qapp, tmp_path)
    dialog._mins["cuts"].setValue(20.0)          # leaves one row shown
    dialog._table.selectRow(0)
    chosen = dialog.selected_rows()
    assert len(chosen) == 1
    assert chosen[0]["cuts_per_min"] == 30.0
    dialog.close()


def test_nothing_is_exported_before_a_pool_exists(qapp, tmp_path):
    dialog = ClipFinderDialog(source_dir=tmp_path)
    assert dialog.selected_rows() == []
    assert dialog.exported_dir is None
    dialog.close()


def test_the_loaded_pool_names_itself_for_the_node_to_record(qapp, tmp_path):
    dialog = _pool_dialog(qapp, tmp_path)
    assert dialog.pool_dir == (tmp_path / "run").resolve()
    dialog.close()


def test_no_pool_means_nothing_to_record(qapp, tmp_path):
    dialog = ClipFinderDialog(source_dir=tmp_path)
    assert dialog.pool_dir is None
    dialog.close()


# --- cancelling a measurement -----------------------------------------------

def test_cancelling_is_not_catchable_as_an_ordinary_exception(qapp, tmp_path):
    """`run_candidate_pool` wraps each episode in `except Exception` and
    CACHES the outcome. A cancel raised as an ordinary exception would be
    caught there, written to the episode cache as a permanent failure, and
    believed by every later resumed run — stopping a run would silently
    poison the pool. ARCHITECTURE.md §7 records the same rule for the
    analysis worker.
    """
    assert issubclass(_Cancelled, BaseException)
    assert not issubclass(_Cancelled, Exception)

    worker = PoolWorker(tmp_path, tmp_path / "out", {})
    worker.cancel()
    try:
        worker._tick("measuring motion")
    except Exception:                     # noqa: BLE001 - the point of the test
        raise AssertionError("the engine's except Exception would swallow this")
    except _Cancelled:
        pass
    else:
        raise AssertionError("a cancelled worker must stop the run")


def test_a_running_worker_passes_its_message_through(qapp, tmp_path):
    worker = PoolWorker(tmp_path, tmp_path / "out", {})
    seen = []
    worker.progress.connect(seen.append)
    worker._tick("Episode 1/12")
    assert seen == ["Episode 1/12"]
