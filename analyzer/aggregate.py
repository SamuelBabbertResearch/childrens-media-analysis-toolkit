"""
Show-level aggregation: per-metric summary statistics across all episodes.

Writes:
  <root>/.analysis/<show>/aggregate.json  — full structured stats
  <root>/.analysis/<show>/aggregate.csv   — one row per episode, flat metrics
"""

from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from .schema import EpisodeResult, MetricStats, ShowAggregate

if TYPE_CHECKING:                       # only for the annotation below
    import pandas as pd

# pandas is imported inside results_to_dataframe, not here. It costs ~1.1s to
# load and is needed only for CSV export, but this module also holds
# compute_show_aggregate — which the interface calls while building the Library
# — so a module-level import made pandas part of application STARTUP. Deferring
# it took the Qt build's import time from 2.2s to 1.1s.


def _stats(values: list[float]) -> MetricStats:
    if not values:
        return MetricStats()
    a = np.array(values, dtype=float)
    return MetricStats(
        mean=round(float(np.mean(a)), 4),
        median=round(float(np.median(a)), 4),
        std=round(float(np.std(a)), 4),
        min=round(float(np.min(a)), 4),
        max=round(float(np.max(a)), 4),
    )


def compute_show_aggregate(
    show_name: str,
    results: list[EpisodeResult],
) -> ShowAggregate:
    """
    Compute per-metric summary statistics across all successful episodes.

    Failed episodes are counted but excluded from metric stats.
    """
    ok = [r for r in results if r.status == "ok"]

    audio_ok = [r for r in ok if r.metrics.audio.available]

    return ShowAggregate(
        show_name=show_name,
        episode_count=len(results),
        failed_count=len(results) - len(ok),
        shot_length_mean_sec=_stats([r.metrics.shot_length.mean_sec for r in ok]),
        cuts_per_min=_stats([r.metrics.scene_pacing.cuts_per_min for r in ok]),
        color_saturation_mean=_stats([r.metrics.color_saturation.mean for r in ok]),
        color_contrast_mean=_stats([r.metrics.color_saturation.contrast_mean for r in ok]),
        motion_mean=_stats([r.metrics.motion.mean for r in ok]),
        flashing_events_per_min=_stats([r.metrics.flashing.luminance_delta_events_per_min for r in ok]),
        audio_rms_mean=_stats([r.metrics.audio.rms_mean for r in audio_ok]),
        sensory_load_score=_stats([r.metrics.sensory_load.score for r in ok]),
    )


def results_to_dataframe(results: list[EpisodeResult]) -> "pd.DataFrame":
    """Flatten episode results into a tidy DataFrame (one row per episode).

    MISSING IS NOT ZERO. Three cases have to stay apart in a research export
    and used to collapse into one:

      * a FAILED episode {D} the decode threw, or the file was not there.
        Every metric on it was left at its dataclass default of 0.0, so the row
        exported `cuts_per_min = 0.0`: a plausible figure for a slow programme,
        indistinguishable from one, and silently poolable into a mean. Those
        cells are now EMPTY, and `error` says what happened.
      * an UNAVAILABLE measurement on an otherwise fine episode {D} a silent
        film has no audio to measure. Empty, with `audio_available` False and
        `audio_unavailable_reason` naming the cause.
      * a MEASURED ZERO {D} an episode with no detected flash really does have
        `flashing_events_per_min = 0.0`, and that zero is data.

    Speech, provenance and the measurement fingerprint are exported too: a
    row that cannot be traced to a build and a configuration cannot be
    replicated, and the fingerprint is what says whether two rows were even
    measured the same way.
    """
    import pandas as pd
    rows = []
    for r in results:
        m = r.metrics
        ok = r.status == "ok"

        def _v(value, available: bool = True):
            """A measured value, or empty when there is nothing to report."""
            return value if (ok and available) else None

        rows.append({
            "file": r.file,
            "status": r.status,
            "error": r.error or None,
            "duration_sec": _v(r.duration_sec),
            "shot_length_mean_sec": _v(m.shot_length.mean_sec),
            "shot_length_median_sec": _v(m.shot_length.median_sec),
            "shots_per_min": _v(m.shot_length.shots_per_min),
            "shot_count": _v(m.shot_length.count),
            "cuts_per_min": _v(m.scene_pacing.cuts_per_min),
            "shot_length_cv": _v(m.scene_pacing.shot_length_cv),
            "color_saturation_mean": _v(m.color_saturation.mean),
            "color_saturation_temporal_var": _v(m.color_saturation.temporal_var),
            "color_contrast_mean": _v(m.color_saturation.contrast_mean),
            "motion_mean": _v(m.motion.mean),
            "motion_peak": _v(m.motion.peak),
            "flashing_events_per_min": _v(
                m.flashing.luminance_delta_events_per_min),
            "audio_rms_mean": _v(m.audio.rms_mean, m.audio.available),
            "audio_rms_peak": _v(m.audio.rms_peak, m.audio.available),
            "audio_rms_temporal_var": _v(m.audio.rms_temporal_var,
                                         m.audio.available),
            "audio_dynamic_range_db": _v(m.audio.dynamic_range_db,
                                         m.audio.available),
            "audio_available": m.audio.available,
            # Which of "silent programme", "no FFmpeg here" and "the decode
            # threw" produced the empty cells above. Blank when audio was
            # measured.
            "audio_unavailable_reason": m.audio.unavailable_reason or None,
            # --- speech: exported from 2026-09-04. It was measured, stored and
            # charted, and then left out of the CSV, so the file a researcher
            # analysed had no words-per-minute column in it at all.
            "speech_available": m.speech.available,
            # "srt" | "vtt" | "whisper" | "none" | "disabled". WPM from a
            # caption file and WPM from a Whisper transcript are different
            # measurements and must not be pooled without saying so.
            "speech_source": m.speech.source,
            "words_per_minute": _v(m.speech.words_per_minute,
                                   m.speech.available),
            # WPM divides by DIALOGUE TIME, not runtime. Reported together or
            # not at all (CLAUDE.md §2.2): alone, WPM invites "how talkative
            # is this episode", which is the question density answers.
            "speech_density": _v(m.speech.speech_density, m.speech.available),
            "total_words": _v(m.speech.total_words, m.speech.available),
            "ffc_score": _v(m.sensory_load.score),
            # Legacy spelling of ffc_score, kept so scripts written against
            # earlier exports keep working. Same number, both columns.
            "sensory_load_score": _v(m.sensory_load.score),
            "sensory_load_audio_available": m.sensory_load.audio_available,
            "sensory_load_pacing": _v(m.sensory_load.components.pacing),
            "sensory_load_saturation": _v(m.sensory_load.components.saturation),
            "sensory_load_contrast": _v(m.sensory_load.components.contrast),
            "sensory_load_motion": _v(m.sensory_load.components.motion),
            "sensory_load_flashing": _v(m.sensory_load.components.flashing),
            "sensory_load_audio": _v(m.sensory_load.components.audio),
            # --- provenance. Empty on rows cached before 2026-09-04. --------
            "measurement_fingerprint": r.measurement_fingerprint or None,
            "analyzed_at_utc": r.analyzed_at_utc or None,
            "cmat_version": r.cmat_version or None,
            "git_commit": r.git_commit or None,
            "source_bytes": r.source_bytes or None,
            "source_sha256": r.source_sha256 or None,
        })
    return pd.DataFrame(rows)


def save_show_results(
    root: Path,
    show_name: str,
    results: list[EpisodeResult],
    aggregate: ShowAggregate,
) -> tuple[Path, Path]:
    """
    Write aggregate.json and aggregate.csv to <root>/.analysis/<show>/.

    Returns:
        (json_path, csv_path)
    """
    out_dir = root / ".analysis" / show_name
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "aggregate.json"
    csv_path = out_dir / "aggregate.csv"

    json_path.write_text(aggregate.to_json(), encoding="utf-8")

    df = results_to_dataframe(results)
    df.to_csv(csv_path, index=False)

    return json_path, csv_path
