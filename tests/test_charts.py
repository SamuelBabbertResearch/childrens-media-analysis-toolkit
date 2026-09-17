"""Regression coverage for chart identity and large-set layout."""

from __future__ import annotations

from analyzer.config_loader import load_config
from analyzer.metrics_sensory import rescore_episode
from analyzer.schema import EpisodeResult
from ui.chart import ChartDialog, _episode_labels


def _result(file_name: str) -> EpisodeResult:
    result = EpisodeResult(file=file_name, duration_sec=600.0)
    result.metrics.scene_pacing.cuts_per_min = 20.0
    result.metrics.color_saturation.mean = 0.5
    result.metrics.color_saturation.contrast_mean = 0.3
    result.metrics.motion.mean = 0.05
    result.metrics.flashing.luminance_delta_events_per_min = 4.0
    result.metrics.audio.available = True
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


def test_large_ffc_chart_has_one_y_position_per_result(qapp):
    """Long/duplicate presentation labels must never merge bar positions."""
    results = [_result(
        "Little Bear 4x02 Sleep Over _ Sand Castle _ Happy Anniversary.mp4"
    ) for _ in range(12)]
    dialog = ChartDialog("Regression set", results, load_config())
    qapp.processEvents()

    canvas = next(child for child in dialog.findChildren(object)
                  if hasattr(child, "figure"))
    axes = canvas.figure.axes[0]
    first_component = axes.patches[:len(results)]

    assert len(first_component) == len(results)
    assert len({round(bar.get_y(), 6) for bar in first_component}) == len(results)
    assert len(axes.get_yticklabels()) == len(results)
    dialog.close()
