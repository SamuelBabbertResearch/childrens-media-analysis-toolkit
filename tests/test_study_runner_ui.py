from __future__ import annotations

import csv

import pytest

pytest.importorskip("PySide6")
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QMessageBox

from study_runner.core import load_package
from study_runner.window import StudyRunnerWindow
from tests.test_study_runner import _package


def _start(window: StudyRunnerWindow, participant_id: str):
    window.participant_id.setText(participant_id)
    window.age_confirmed.setChecked(True)
    window.consent_confirmed.setChecked(True)
    window._start_session()
    assert window.stack.currentWidget() is window.instructions_page
    window._show_practice()
    window.practice_scale.set_value(window.package.practice_expected_rating)
    assert window.practice_continue.isEnabled()
    window._begin_trials()
    assert window.stack.currentWidget() is window.video_page


def _finish_video(window: StudyRunnerWindow):
    window._media_status(QMediaPlayer.EndOfMedia)
    assert window.stack.currentWidget() is window.rating_page


def _rate(window: StudyRunnerWindow, value: int):
    window._rating_selected(value)
    window._lock_rating()


def test_adult_only_flow_writes_one_self_rating_per_clip(qapp, tmp_path):
    package = load_package(_package(tmp_path))
    data_dir = tmp_path / "adult_data"
    window = StudyRunnerWindow(package, data_dir)
    _start(window, "A-100")

    for trial in range(12):
        _finish_video(window)
        assert window.block_type == "adult_self"
        assert window.question.text() == "How fast did this video feel?"
        _rate(window, 3)
        if trial < 11:
            assert window.stack.currentWidget() is window.video_page

    assert window.stack.currentWidget() is window.done_page
    with (data_dir / "responses.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 12
    assert {row["block_type"] for row in rows} == {"adult_self"}
    assert {row["response_sequence"] for row in rows} == {"adult_self"}
    assert [int(row["trial_order"]) for row in rows] == list(range(1, 13))
    window.close()


def test_participant_interface_exposes_no_group_or_order_choice(qapp, tmp_path):
    window = StudyRunnerWindow(load_package(_package(tmp_path)), tmp_path / "d")
    assert not hasattr(window, "group")
    assert not hasattr(window, "condition")
    assert "child" not in window.package.question.lower()
    window.close()


def test_skip_records_missing_rating_and_advances(qapp, tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    window = StudyRunnerWindow(load_package(_package(tmp_path)), data_dir)
    _start(window, "A-101")
    _finish_video(window)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Yes)
    window._skip_rating()
    assert window.trial_index == 1
    with (data_dir / "responses.csv").open(newline="", encoding="utf-8") as fh:
        row = next(csv.DictReader(fh))
    assert row["completion_status"] == "skipped"
    assert row["rating"] == ""
    window.stack.setCurrentWidget(window.done_page)
    window.close()


def test_withdrawal_removes_prior_ratings(qapp, tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    window = StudyRunnerWindow(load_package(_package(tmp_path)), data_dir)
    _start(window, "A-102")
    _finish_video(window)
    _rate(window, 4)
    _finish_video(window)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Yes)
    window._withdraw_session()
    with (data_dir / "responses.csv").open(newline="", encoding="utf-8") as fh:
        assert list(csv.DictReader(fh)) == []
    assert window.stack.currentWidget() is window.done_page
    window.close()


def test_playback_error_is_the_only_route_to_restart(qapp, tmp_path,
                                                     monkeypatch):
    window = StudyRunnerWindow(load_package(_package(tmp_path)), tmp_path / "d")
    _start(window, "A-103")
    window._play()
    assert window.play_started
    assert not window.play_button.isEnabled()
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: None)
    window._media_error(None, "test interruption")
    assert window.technical_restart_allowed
    assert window.play_button.isEnabled()
    assert "technical interruption" in window.play_button.text().lower()
    window.stack.setCurrentWidget(window.done_page)
    window.close()


def test_one_backend_failure_is_handled_only_once(qapp, tmp_path, monkeypatch):
    """Stopping a failed Qt media backend can emit the same error again."""
    window = StudyRunnerWindow(load_package(_package(tmp_path)), tmp_path / "d")
    _start(window, "A-104")
    shown = []
    monkeypatch.setattr(
        QMessageBox, "critical", lambda *args: shown.append(args))

    window._media_error(None, "decoder failed")
    window._media_error(None, "decoder failed again")

    assert len(shown) == 1
    assert window.technical_restart_allowed
    window.stack.setCurrentWidget(window.done_page)
    window.close()
