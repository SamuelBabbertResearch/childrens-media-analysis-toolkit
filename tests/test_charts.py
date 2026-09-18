"""Regression coverage for chart identity and large-set layout."""

from __future__ import annotations

import numpy as np
import pytest

from analyzer.config_loader import load_config
from analyzer.metrics_sensory import rescore_episode
from analyzer.schema import EpisodeResult
from ui.chart import ChartDialog, SpeechChartDialog, _episode_labels


def _result(file_name: str, audio_available: bool = True) -> EpisodeResult:
    result = EpisodeResult(file=file_name, duration_sec=600.0)
    result.metrics.scene_pacing.cuts_per_min = 20.0
    result.metrics.color_saturation.mean = 0.5
    result.metrics.color_saturation.contrast_mean = 0.3
    result.metrics.motion.mean = 0.05
    result.metrics.flashing.luminance_delta_events_per_min = 4.0
    result.metrics.audio.available = audio_available
    result.metrics.audio.rms_mean = 0.03
    return rescore_episode(result, load_config())


def test_episode_labels_keep_duplicate_short_titles_distinct():
    labels = _episode_labels([
        "Little Bear 4x02 Sleep Over _ Sand Castle _ Happy Anniversary.mp4",
        "Little Bear 4x06 Sleep Over _ Sand Castle _ Happy Anniversary.mp4",
        "Little Bear 4x02 Sleep Over _ Sand Castle _ Happy Anniversary.mp4",
    ])

    assert labels == [
        "S04E02 — Sleep Over _ Sand Castle _…",
        "S04E06 — Sleep Over _ Sand Castle _…",
        "S04E02 — Sleep Over _ Sand Castle _… [2]",
    ]
    assert len(labels) == len(set(labels))


@pytest.mark.parametrize("count", [3, 12, 200])
def test_ffc_chart_keeps_episode_geometry_and_component_totals(qapp, count):
    """Both orientations retain every episode, including redistributed audio."""
    results = [_result(
        "Little Bear 4x02 Sleep Over _ Sand Castle _ Happy Anniversary.mp4",
        audio_available=index % 2 == 0,
    ) for index in range(count)]
    dialog = ChartDialog("Regression set", results, load_config())
    qapp.processEvents()

    canvas = next(child for child in dialog.findChildren(object)
                  if hasattr(child, "figure"))
    axes = canvas.figure.axes[0]
    horizontal = count > 10
    category_axis, value_axis = (1, 0) if horizontal else (0, 1)
    assert len(axes.collections) == 6
    assert not axes.patches
    first_component = axes.collections[0].get_paths()
    assert len(first_component) == count
    centers = [(path.vertices[:, category_axis].min()
                + path.vertices[:, category_axis].max()) / 2
               for path in first_component]
    assert centers == pytest.approx(range(count))
    ticks = axes.get_yticklabels() if horizontal else axes.get_xticklabels()
    assert len({tick.get_text() for tick in ticks}) == count
    tops = [path.vertices[:, value_axis].max()
            for path in axes.collections[-1].get_paths()]
    assert tops == pytest.approx(
        sorted(result.metrics.sensory_load.score for result in results), abs=0.0001)
    assert axes.yaxis_inverted() == horizontal
    dialog.close()


def test_timed_text_chart_aligns_rates_and_density_with_duplicate_names(qapp):
    dialog = SpeechChartDialog([
        {"file": "Same episode.mp4", "wpm": 120, "density": 0.4},
        {"file": "Same episode.mp4", "wpm": 60, "density": 0.2},
    ])
    canvas = next(child for child in dialog.findChildren(object)
                  if hasattr(child, "figure"))
    rates, density = canvas.figure.axes
    assert rates.get_ylabel() == "Words per timed-text minute"
    assert density.get_ylabel() == "Timed-text density"
    bars = rates.collections[0].get_paths()
    assert [path.vertices[:, 1].max() for path in bars] == [60, 120]
    np.testing.assert_array_equal(density.lines[0].get_xdata(), [0, 1])
    np.testing.assert_array_equal(density.lines[0].get_ydata(), [0.2, 0.4])
    assert len({tick.get_text() for tick in rates.get_xticklabels()}) == 2
    dialog.close()
