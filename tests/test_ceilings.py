"""Normalization ceilings — the scale every composite score sits on.

A ceiling is the denominator that turns a raw metric into a 0–1 component. Two
ways it goes wrong, and BOTH were live in this project until 2026-08-14:

- set far above what real content produces, the metric barely moves and
  contributes far less than its weight implies (motion: ceiling 1.0 against a
  real range of ~0.09, so a 25% weight delivered ~7% of the score);
- set below real content, everything above it clamps to exactly 1.0 and the
  most intense episodes become indistinguishable (flashing at 30/min and audio
  RMS at 0.2 were each clamping real episodes).

Neither is visible from the score. Both are visible from the distribution,
which is why `ceiling_distributions()` exists and why Settings shows it.
See `CEILINGS.md`.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from analyzer.db import CEILING_METRIC_COLUMN, ceiling_distributions


def _index(tmp_path: Path, rows: list[dict]) -> sqlite3.Connection:
    """A minimal episodes table holding just the scaled metrics."""
    conn = sqlite3.connect(":memory:")
    cols = ", ".join(f"{c} real" for c in CEILING_METRIC_COLUMN.values())
    conn.execute(f"create table episodes (file_path text, {cols})")
    for i, row in enumerate(rows):
        keys = list(row)
        conn.execute(
            "insert into episodes (file_path, %s) values (?, %s)"
            % (", ".join(keys), ", ".join("?" * len(keys))),
            [f"ep{i}.mp4", *[row[k] for k in keys]])
    conn.commit()
    return conn


def test_a_ceiling_far_above_the_content_is_visible_as_unused_scale(tmp_path):
    """The motion defect: nothing clamps, so nothing looks wrong — until you
    see that the maximum sits at a fraction of the ceiling."""
    conn = _index(tmp_path, [{"motion_mean": v} for v in (0.04, 0.06, 0.09)])
    d = ceiling_distributions(conn, {"motion_mean": {"max": 1.0}})["motion_mean"]
    assert d["n_clamped"] == 0            # no clamping — the silent failure
    assert d["pct_of_ceiling"] < 10       # and yet 90%+ of the scale is unused


def test_a_ceiling_below_the_content_is_reported_as_clamping(tmp_path):
    """The flashing/audio defect: episodes above the ceiling all score 1.0."""
    conn = _index(tmp_path, [{"flashing_events_per_min": v}
                             for v in (5.0, 12.0, 45.0, 67.0)])
    d = ceiling_distributions(
        conn, {"flashing_events_per_min": {"max": 30.0}})["flashing_events_per_min"]
    assert d["n_clamped"] == 2
    assert d["max"] == 67.0


def test_distributions_survive_an_empty_or_partial_index(tmp_path):
    """Settings must open on a fresh install with nothing analysed."""
    conn = _index(tmp_path, [])
    assert ceiling_distributions(conn, {}) == {}
    # A metric with no values is absent rather than zero — reporting a median
    # of 0 for an unmeasured metric would be a fabricated figure.
    conn = _index(tmp_path, [{"cuts_per_min": 12.0}])
    out = ceiling_distributions(conn, {})
    assert "cuts_per_min" in out
    assert "motion_mean" not in out


def test_every_shipped_ceiling_has_a_distribution_lookup():
    """A ceiling with no column mapping would silently show no guidance."""
    cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))
    for key in cfg["normalization_reference_ranges"]:
        assert key in CEILING_METRIC_COLUMN, (
            f"ceiling {key!r} has no metric column, so Settings can show no "
            f"observed figures for it")


def test_no_shipped_preset_keeps_the_motion_scale_error():
    """Motion's practical range is ~0.09 and its theoretical max is 1.0. Every
    preset shipped the theoretical value, so motion under-contributed
    everywhere. Corrected 2026-08-14; a preset added later must not reintroduce
    it."""
    cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))
    for name, preset in cfg.get("presets", {}).items():
        ranges = preset.get("normalization_reference_ranges", {})
        ceiling = ranges.get("motion_mean", {}).get("max")
        if ceiling is None:
            continue
        assert ceiling <= 0.5, (
            f"preset {name!r} sets motion_mean max to {ceiling}; real content "
            f"reaches ~0.25, so this wastes most of the scale (see CEILINGS.md)")


@pytest.mark.parametrize("entry,expect", [
    (None, "not analysed"),
    ({"median": 0.066, "max": 0.086, "pct_of_ceiling": 24.0, "n_clamped": 0}, "% of scale"),
    ({"median": 5.0, "max": 67.0, "pct_of_ceiling": 100.0, "n_clamped": 2}, "at ceiling"),
])
def test_the_hint_tells_the_user_which_failure_they_have(entry, expect):
    from ui.settings import _observed_hint
    assert expect in _observed_hint(entry)
