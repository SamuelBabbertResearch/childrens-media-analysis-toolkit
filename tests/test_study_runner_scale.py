"""The participant pace scale: the properties the study depends on.

These are not styling tests. Each one guards a design constraint that came out
of STUDY_RATING_SCALE_DESIGN.md, and each would fail silently in the data
rather than on screen — a carried-over answer, a pre-selected midpoint, or a
ramp that implies one end is the bad answer.
"""

from __future__ import annotations

import colorsys

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QRadioButton
from PySide6.QtTest import QTest

from study_runner.core import load_package
from study_runner.scale import MIN_STEP_HEIGHT, MIN_STEP_WIDTH, PaceScale
from study_runner.window import StudyRunnerWindow
from tests.test_study_runner import _package
from ui.tokens import PACE_SCALE, PACE_STEP_COLORS

ANCHORS = ("Very slow", "Slow", "In between", "Fast", "Very fast")


def _key(text: str, key=None) -> QKeyEvent:
    return QKeyEvent(QEvent.KeyPress, key or 0, Qt.NoModifier, text)


def _rgb(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _luminance(value: str) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in _rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# --- the widget ------------------------------------------------------------

def test_five_steps_carry_the_package_anchors_in_order(qapp):
    scale = PaceScale(ANCHORS)
    assert [s.value for s in scale.steps] == [1, 2, 3, 4, 5]
    assert [s.anchor for s in scale.steps] == list(ANCHORS)


def test_every_point_is_worded_not_only_the_ends(qapp):
    scale = PaceScale(ANCHORS)
    for step in scale.steps:
        assert step.anchor.strip(), "a labelled ramp labels all five points"


def test_a_scale_that_is_not_five_points_is_refused(qapp):
    with pytest.raises(ValueError):
        PaceScale(("Slow", "Fast"))


def test_nothing_is_selected_until_the_participant_answers(qapp):
    scale = PaceScale(ANCHORS)
    assert scale.value() is None
    assert not any(step.isChecked() for step in scale.steps)


def test_clear_removes_the_previous_answer(qapp):
    scale = PaceScale(ANCHORS)
    scale.set_value(5)
    scale.clear()
    assert scale.value() is None
    assert not any(step.isChecked() for step in scale.steps)


def test_selecting_is_exclusive_and_reports_the_value(qapp):
    scale = PaceScale(ANCHORS)
    seen: list[int] = []
    scale.valueChanged.connect(seen.append)
    scale.steps[2].click()
    scale.steps[0].click()
    assert seen == [3, 1]
    assert scale.value() == 1
    assert [s.isChecked() for s in scale.steps] == [True, False, False, False, False]


def test_mouse_press_selects_without_waiting_for_button_release(qapp):
    """The rating cards acknowledge a tap immediately, before mouse release."""
    scale = PaceScale(ANCHORS)
    scale.show()
    qapp.processEvents()
    QTest.mousePress(scale.steps[3], Qt.LeftButton)
    assert scale.value() == 4
    assert scale.steps[3].isChecked()
    QTest.mouseRelease(scale.steps[3], Qt.LeftButton)
    scale.close()


def test_number_keys_answer_directly(qapp):
    scale = PaceScale(ANCHORS)
    assert scale.handle_key(_key("4")) is True
    assert scale.value() == 4


def test_arrow_keys_move_and_stop_at_the_ends(qapp):
    scale = PaceScale(ANCHORS)
    scale.handle_key(_key("", Qt.Key_Right))
    assert scale.value() == 1, "the first arrow enters the scale, not the middle"
    for _ in range(9):
        scale.handle_key(_key("", Qt.Key_Right))
    assert scale.value() == 5
    scale.handle_key(_key("", Qt.Key_Home))
    assert scale.value() == 1
    scale.handle_key(_key("", Qt.Key_Left))
    assert scale.value() == 1


def test_unrelated_keys_are_left_alone(qapp):
    scale = PaceScale(ANCHORS)
    assert scale.handle_key(_key("q")) is False
    assert scale.handle_key(_key("9")) is False
    assert scale.value() is None


def test_the_whole_step_is_a_large_accessible_target(qapp):
    scale = PaceScale(ANCHORS)
    assert (MIN_STEP_WIDTH, MIN_STEP_HEIGHT) >= (64, 78)
    for step in scale.steps:
        assert step.minimumWidth() >= MIN_STEP_WIDTH
        assert step.minimumHeight() >= MIN_STEP_HEIGHT


def test_the_answer_is_visible_without_colour(qapp):
    """The selected step keeps its ramp colour; the signal is the outline."""
    scale = PaceScale(ANCHORS)
    scale.set_value(3)
    checked = [s for s in scale.steps if s.isChecked()]
    assert len(checked) == 1
    # Nothing repaints a step's fill on selection: the ramp is positional, so
    # a colour-blind participant reads the answer from the border and mark.
    assert PACE_STEP_COLORS[2] == PACE_SCALE["step_3"]


# --- the ramp itself -------------------------------------------------------

def test_the_ramp_is_ordinal_lightness_not_a_traffic_light(qapp):
    lums = [_luminance(c) for c in PACE_STEP_COLORS]
    assert lums == sorted(lums, reverse=True), "light to dark, in one direction"
    hues = [colorsys.rgb_to_hsv(*_rgb(c))[0] for c in PACE_STEP_COLORS]
    assert max(hues) - min(hues) < 0.06, (
        "one hue only — a red-to-green ramp reads as bad-to-good and would "
        "put a verdict on a participant screen")


def test_step_text_is_legible_on_every_step(qapp):
    ink = _luminance(PACE_SCALE["step_ink"])
    for colour in PACE_STEP_COLORS:
        contrast = (max(ink, _luminance(colour)) + 0.05) / (
            min(ink, _luminance(colour)) + 0.05)
        assert contrast >= 4.5, f"{colour} fails contrast against the step ink"


# --- the rating page -------------------------------------------------------

def test_the_rating_page_uses_the_scale_and_no_radio_column(qapp, tmp_path):
    package = load_package(_package(tmp_path))
    window = StudyRunnerWindow(package, tmp_path / "d")
    assert isinstance(window.scale, PaceScale)
    assert window.rating_page.findChildren(QRadioButton) == []
    assert [s.anchor for s in window.scale.steps] == list(package.anchors)
    window.close()


def test_no_answer_is_carried_from_one_trial_to_the_next(qapp, tmp_path):
    window = StudyRunnerWindow(load_package(_package(tmp_path)), tmp_path / "d")
    window.participant_id.setText("A-200")
    window.age_confirmed.setChecked(True)
    window.consent_confirmed.setChecked(True)
    window._start_session()
    window._show_practice()
    window.practice_scale.set_value(3)
    window._begin_trials()

    window._media_status(QMediaPlayer.EndOfMedia)
    window.scale.steps[4].click()
    assert window.lock_button.isEnabled()
    window._lock_rating()

    window._media_status(QMediaPlayer.EndOfMedia)
    assert window.scale.value() is None, "trial 2 must start with no answer"
    assert not window.lock_button.isEnabled(), (
        "continuing without an answer would record the previous trial's rating")
    # Closing part-way through a session raises the modal "end this session?"
    # question, which would block the run; leave from the finished page.
    window.stack.setCurrentWidget(window.done_page)
    window.close()
