"""Finding 30-second windows in a measured candidate pool, by attribute.

`analyzer.study_clips` measures every contiguous window of every episode in a
folder and writes the pool to `candidates.csv`. This module is the *reading*
half: load such a run, ask questions of it, and label a chosen set for export.

It measures nothing and re-derives nothing. Every number a query touches was
produced by the candidate pass under one pinned configuration, and the pool
carries that configuration's fingerprint so a result set can say what its
numbers are numbers *about*.

Three properties this module exists to hold:

* **A filter is inspectable.** `ClipQuery.describe()` states the whole query in
  one line, in the same units the columns are in. A found set with no statement
  of how it was found is not a finding.
* **A level is relative to the pool that produced it.** `low`, `middle` and
  `high` are thirds of *this* measured pool, not properties of a clip, and
  `CandidatePool.level_definition` is read from the run's own manifest rather
  than restated here — the definition lives where the numbers were made.
* **No verdict.** Nothing ranks a window as good, suitable, or appropriate for
  anyone. A query orders and filters; it does not judge.
"""

from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Sequence

# The features the candidate pass measures per window, and the column each one
# lives in. Same three as `study_clips.FEATURES`; imported rather than retyped
# so a change there cannot leave this module quietly describing the old set.
from .study_clips import (
    FEATURE_LABEL,
    FEATURE_PERCENTILE,
    FEATURE_VALUE,
    FEATURES,
)

LEVELS = ("low", "middle", "high", "unavailable")

# Columns worth showing a researcher, with the unit spelled out. The finder
# renders these in order; nothing here decides what they mean.
COLUMNS: tuple[tuple[str, str], ...] = (
    ("clip_id", "Window"),
    ("source_relpath", "Episode"),
    ("start_timecode", "Start"),
    ("end_timecode", "End"),
    ("duration_sec", "Length (s)"),
    ("cuts_per_min", "Cuts / min"),
    ("cuts_level", "Cuts level"),
    ("motion_mean", "Motion mean"),
    ("motion_level", "Motion level"),
    ("audio_rms_mean", "Audio RMS mean"),
    ("audio_level", "Audio level"),
)

_FLOAT_FIELDS = (
    "start_sec", "end_sec", "duration_sec", "episode_duration_sec",
    "cuts_per_min", "motion_mean", "motion_peak", "audio_rms_mean",
    "audio_rms_peak", "audio_dynamic_range_db",
    "cuts_percentile", "motion_percentile", "audio_percentile",
    "excluded_first_sec", "excluded_last_sec",
    "measured_range_start_sec", "measured_range_end_sec",
)
_INT_FIELDS = ("window_index", "cut_count")
_BOOL_FIELDS = ("is_full_window", "audio_available")


class PoolError(Exception):
    """A run folder that cannot be read as a candidate pool."""


# --- loading -----------------------------------------------------------------

def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes")


def coerce_row(row: dict[str, Any]) -> dict[str, Any]:
    """CSV gives back strings; the columns are numbers. Restore the types.

    Reading a pool with `cuts_per_min` as text is the failure that compares
    "9.0" against "10.0" as strings and reports the wrong windows without ever
    looking wrong on screen.
    """
    out = dict(row)
    for key in _FLOAT_FIELDS:
        if key in out:
            out[key] = _to_float(out[key])
    for key in _INT_FIELDS:
        if key in out:
            number = _to_float(out[key])
            out[key] = None if number is None else int(number)
    for key in _BOOL_FIELDS:
        if key in out:
            out[key] = _to_bool(out[key])
    return out


@dataclass(frozen=True)
class CandidatePool:
    """One completed candidate run, as read from disk."""

    run_dir: Path
    rows: tuple[dict[str, Any], ...]
    manifest: dict[str, Any] = field(default_factory=dict)

    # -- what these numbers are ----------------------------------------------

    @property
    def source_dir(self) -> str:
        return str(self.manifest.get("source_dir") or "")

    @property
    def window_sec(self) -> float | None:
        return _to_float(self.manifest.get("window_sec"))

    @property
    def fingerprint(self) -> str:
        return str(self.manifest.get("measurement_fingerprint") or "")

    @property
    def level_definition(self) -> str:
        """The run's own words for what low/middle/high mean. Not restated."""
        return str(self.manifest.get("relative_level_definition") or "")

    @property
    def recipe_citation(self) -> str:
        recipe = self.manifest.get("analysis_recipe") or {}
        return str(recipe.get("citation") or "")

    def provenance(self) -> list[tuple[str, str]]:
        """Label/value rows stating how the pool was measured.

        Every screen showing these numbers shows this too, or it is showing
        figures with no statement of the method that produced them.
        """
        window = self.window_sec
        excluded = (
            f"first {self.manifest.get('exclude_first_sec_per_episode', 0)}s, "
            f"last {self.manifest.get('exclude_last_sec_per_episode', 0)}s"
        )
        rows = [
            ("Source", self.source_dir),
            ("Episodes", str(self.manifest.get("source_file_count", ""))),
            ("Windows", str(len(self.rows))),
            ("Window length", f"{window:g} s" if window else ""),
            ("Excluded per episode", excluded),
            ("Partial windows",
             "included" if self.manifest.get("include_partial_windows")
             else "excluded"),
            ("Measurement fingerprint", self.fingerprint),
        ]
        if self.recipe_citation:
            rows.append(("Analysis recipe", self.recipe_citation))
        if self.level_definition:
            rows.append(("Level definition", self.level_definition))
        return [(k, v) for k, v in rows if v]

    # -- ranges, for populating a filter without inventing bounds ------------

    def bounds(self, column: str) -> tuple[float, float] | None:
        values = [
            row[column] for row in self.rows
            if isinstance(row.get(column), (int, float))
        ]
        if not values:
            return None
        return (min(values), max(values))

    def episodes(self) -> list[str]:
        seen: list[str] = []
        for row in self.rows:
            name = str(row.get("source_relpath") or "")
            if name and name not in seen:
                seen.append(name)
        return sorted(seen)


def load_pool(run_dir: Path | str) -> CandidatePool:
    """Read a `study-clips` run folder. Raises `PoolError` if it is not one."""
    run_dir = Path(run_dir)
    candidates = run_dir / "candidates.csv"
    if not candidates.is_file():
        raise PoolError(
            f"No candidates.csv in {run_dir} — this is not a measured "
            f"candidate pool. Run the candidate pass over a source folder "
            f"first."
        )
    try:
        # utf-8-sig, because study_clips._write_csv writes a BOM. Read as
        # plain utf-8 the first header becomes "﻿clip_id", every row
        # loses its clip_id, and the column renders empty rather than wrong —
        # which is how it survived a full set of passing fixture tests.
        with candidates.open(newline="", encoding="utf-8-sig") as handle:
            rows = [coerce_row(row) for row in csv.DictReader(handle)]
    except OSError as exc:
        raise PoolError(f"Could not read {candidates}: {exc}") from exc
    if not rows:
        raise PoolError(f"{candidates} contains no measured windows.")

    manifest: dict[str, Any] = {}
    manifest_path = run_dir / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            manifest = {}
    return CandidatePool(run_dir.resolve(), tuple(rows), manifest)


# --- querying ----------------------------------------------------------------

@dataclass(frozen=True)
class Range:
    """An inclusive numeric range; either end may be open."""

    low: float | None = None
    high: float | None = None

    def __post_init__(self) -> None:
        if (self.low is not None and self.high is not None
                and self.low > self.high):
            raise ValueError(
                f"range low {self.low} is above high {self.high}")

    @property
    def open(self) -> bool:
        return self.low is None and self.high is None

    def contains(self, value: Any) -> bool:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            # A window with no measurement cannot satisfy a bound on it. An
            # unmeasured value is not a zero.
            return self.open
        if self.low is not None and value < self.low:
            return False
        if self.high is not None and value > self.high:
            return False
        return True

    def describe(self, unit: str = "") -> str:
        suffix = f" {unit}" if unit else ""
        if self.open:
            return "any"
        if self.low is None:
            return f"≤ {self.high:g}{suffix}"
        if self.high is None:
            return f"≥ {self.low:g}{suffix}"
        return f"{self.low:g}–{self.high:g}{suffix}"


@dataclass(frozen=True)
class ClipQuery:
    """A question asked of a pool. Empty everywhere means "every window"."""

    ranges: dict[str, Range] = field(default_factory=dict)      # by feature
    levels: dict[str, frozenset[str]] = field(default_factory=dict)
    episode: str = ""                 # case-insensitive substring
    full_windows_only: bool = False
    audio_available_only: bool = False

    def __post_init__(self) -> None:
        for feature in list(self.ranges) + list(self.levels):
            if feature not in FEATURES:
                raise ValueError(
                    f"unknown feature {feature!r}; the candidate pass measures "
                    f"{', '.join(FEATURES)}")
        for feature, chosen in self.levels.items():
            unknown = set(chosen) - set(LEVELS)
            if unknown:
                raise ValueError(f"unknown level(s) {sorted(unknown)}")

    # -- matching -------------------------------------------------------------

    def matches(self, row: dict[str, Any]) -> bool:
        for feature, bound in self.ranges.items():
            if not bound.contains(row.get(FEATURE_VALUE[feature])):
                return False
        for feature, chosen in self.levels.items():
            if chosen and str(row.get(FEATURE_LABEL[feature])) not in chosen:
                return False
        if self.episode:
            haystack = str(row.get("source_relpath") or "").lower()
            if self.episode.lower() not in haystack:
                return False
        if self.full_windows_only and not row.get("is_full_window"):
            return False
        if self.audio_available_only and not row.get("audio_available"):
            return False
        return True

    def apply(self, rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        return [row for row in rows if self.matches(row)]

    # -- saying what was asked ------------------------------------------------

    def describe(self) -> str:
        """The whole query in one line, in the columns' own units."""
        parts: list[str] = []
        units = {"cuts": "cuts/min", "motion": "", "audio": ""}
        for feature in FEATURES:
            bound = self.ranges.get(feature)
            if bound is not None and not bound.open:
                parts.append(f"{feature} {bound.describe(units[feature])}")
            chosen = self.levels.get(feature)
            if chosen:
                parts.append(f"{feature} level {'/'.join(sorted(chosen))}")
        if self.episode:
            parts.append(f"episode contains “{self.episode}”")
        if self.full_windows_only:
            parts.append("whole windows only")
        if self.audio_available_only:
            parts.append("audio measured")
        return "; ".join(parts) if parts else "every window in the pool"

    def with_range(self, feature: str, bound: Range) -> "ClipQuery":
        ranges = dict(self.ranges)
        ranges[feature] = bound
        return replace(self, ranges=ranges)

    def with_levels(self, feature: str, chosen: Iterable[str]) -> "ClipQuery":
        levels = dict(self.levels)
        levels[feature] = frozenset(chosen)
        return replace(self, levels=levels)


def sort_rows(rows: Sequence[dict[str, Any]], column: str,
              descending: bool = False) -> list[dict[str, Any]]:
    """Sort on one column, with unmeasured values last in either direction.

    Sorting `None` to the top as if it were the smallest number is how an
    unmeasured window comes to look like the quietest one.
    """
    def key(row: dict[str, Any]):
        value = row.get(column)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return (1, str(value if value is not None else ""))
        return (0, value)

    missing = [r for r in rows if key(r)[0] == 1]
    present = [r for r in rows if key(r)[0] == 0]
    present.sort(key=lambda r: r.get(column), reverse=descending)
    missing.sort(key=lambda r: str(r.get(column) or ""))
    return present + missing


# --- handing a found set to the exporter -------------------------------------

def _label_stem(row: dict[str, Any]) -> str:
    stem = re.sub(r"[^A-Za-z0-9]+", "_",
                  Path(str(row.get("source_relpath") or "clip")).stem)
    return stem.strip("_")[:40] or "clip"


def label_for_export(rows: Sequence[dict[str, Any]],
                     prefix: str = "F") -> list[dict[str, Any]]:
    """Add the `study_label` that `study_clips.export_selected_clips` needs.

    Labels are positional and carry the episode and start time, so an exported
    file says where it came from without a lookup. The rows are copies: a
    found set is a view of the pool, and labelling one must not edit the pool.
    """
    labelled: list[dict[str, Any]] = []
    for index, row in enumerate(rows, 1):
        start = row.get("start_sec")
        stamp = f"{int(round(float(start or 0.0))):05d}s"
        copy = dict(row)
        copy["study_label"] = f"{prefix}{index:02d}_{_label_stem(row)}_{stamp}"
        labelled.append(copy)
    return labelled


def export_manifest(pool: CandidatePool, query: ClipQuery,
                    rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """What was exported, and the question that produced it.

    Written beside the exported clips. A folder of clips with no record of the
    filter that chose them is a selection nobody can reproduce or challenge.
    """
    return {
        "workflow": "CMAT clip finder export",
        "run_dir": str(pool.run_dir),
        "source_dir": pool.source_dir,
        "measurement_fingerprint": pool.fingerprint,
        "analysis_recipe": pool.recipe_citation,
        "level_definition": pool.level_definition,
        "query": query.describe(),
        "pool_window_count": len(pool.rows),
        "matched_window_count": len(rows),
        "clips": [
            {
                "study_label": row.get("study_label"),
                "clip_id": row.get("clip_id"),
                "source_relpath": row.get("source_relpath"),
                "start_sec": row.get("start_sec"),
                "duration_sec": row.get("duration_sec"),
                **{FEATURE_VALUE[f]: row.get(FEATURE_VALUE[f])
                   for f in FEATURES},
                **{FEATURE_LABEL[f]: row.get(FEATURE_LABEL[f])
                   for f in FEATURES},
                **{FEATURE_PERCENTILE[f]: row.get(FEATURE_PERCENTILE[f])
                   for f in FEATURES},
            }
            for row in rows
        ],
    }
