"""
Persistent SQLite index for all analyzed episodes and shows.

Lives at <root>/.analysis/index.db and accumulates results across sessions.
Re-analyzing an episode upserts its row — never duplicates.
No GUI imports; pure data layer.
"""

from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .schema import EpisodeResult, ShowAggregate


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_db(root: Path) -> sqlite3.Connection:
    """Open (creating if needed) the index DB for a root folder."""
    db_path = root / ".analysis" / "index.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    _init_db(conn)
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS episodes (
            file_path               TEXT PRIMARY KEY,
            show_name               TEXT NOT NULL,
            file_name               TEXT NOT NULL,
            duration_sec            REAL,
            shots_per_min           REAL,
            cuts_per_min            REAL,
            shot_length_cv          REAL,
            color_saturation_mean   REAL,
            color_contrast_mean     REAL,
            motion_mean             REAL,
            motion_peak             REAL,
            flashing_events_per_min REAL,
            audio_rms_mean          REAL,
            audio_dynamic_range_db  REAL,
            audio_available         INTEGER,
            sensory_load_score      REAL,
            analyzed_at             TEXT
        );

        CREATE TABLE IF NOT EXISTS shows (
            show_name        TEXT PRIMARY KEY,
            episode_count    INTEGER,
            avg_load         REAL,
            median_load      REAL,
            avg_cuts_per_min REAL,
            avg_motion       REAL,
            avg_saturation   REAL,
            avg_contrast     REAL,
            avg_flashing     REAL,
            avg_audio_rms    REAL,
            updated_at       TEXT
        );
    """)
    conn.commit()
    # Migrate existing DBs
    for sql in [
        "ALTER TABLE episodes ADD COLUMN color_contrast_mean REAL",
        "ALTER TABLE shows ADD COLUMN avg_contrast REAL",
        "ALTER TABLE shows ADD COLUMN avg_flashing REAL",
        "ALTER TABLE episodes ADD COLUMN notes TEXT",
    ]:
        try:
            conn.execute(sql)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists


# ---------------------------------------------------------------------------
# Upserts
# ---------------------------------------------------------------------------

def upsert_episode(
    conn: sqlite3.Connection,
    result: EpisodeResult,
    show_name: str,
    file_path: str,
) -> None:
    """Insert or replace a single episode row."""
    m = result.metrics
    conn.execute("""
        INSERT INTO episodes (
            file_path, show_name, file_name, duration_sec,
            shots_per_min, cuts_per_min, shot_length_cv,
            color_saturation_mean, color_contrast_mean, motion_mean, motion_peak,
            flashing_events_per_min, audio_rms_mean, audio_dynamic_range_db,
            audio_available, sensory_load_score, analyzed_at
        ) VALUES (
            :file_path, :show_name, :file_name, :duration_sec,
            :shots_per_min, :cuts_per_min, :shot_length_cv,
            :color_saturation_mean, :color_contrast_mean, :motion_mean, :motion_peak,
            :flashing_events_per_min, :audio_rms_mean, :audio_dynamic_range_db,
            :audio_available, :sensory_load_score, :analyzed_at
        )
        ON CONFLICT(file_path) DO UPDATE SET
            show_name               = excluded.show_name,
            file_name               = excluded.file_name,
            duration_sec            = excluded.duration_sec,
            shots_per_min           = excluded.shots_per_min,
            cuts_per_min            = excluded.cuts_per_min,
            shot_length_cv          = excluded.shot_length_cv,
            color_saturation_mean   = excluded.color_saturation_mean,
            color_contrast_mean     = excluded.color_contrast_mean,
            motion_mean             = excluded.motion_mean,
            motion_peak             = excluded.motion_peak,
            flashing_events_per_min = excluded.flashing_events_per_min,
            audio_rms_mean          = excluded.audio_rms_mean,
            audio_dynamic_range_db  = excluded.audio_dynamic_range_db,
            audio_available         = excluded.audio_available,
            sensory_load_score      = excluded.sensory_load_score,
            analyzed_at             = excluded.analyzed_at
    """, {
        "file_path":               file_path,
        "show_name":               show_name,
        "file_name":               result.file,
        "duration_sec":            result.duration_sec,
        "shots_per_min":           m.shot_length.shots_per_min,
        "cuts_per_min":            m.scene_pacing.cuts_per_min,
        "shot_length_cv":          m.scene_pacing.shot_length_cv,
        "color_saturation_mean":   m.color_saturation.mean,
        "color_contrast_mean":     m.color_saturation.contrast_mean,
        "motion_mean":             m.motion.mean,
        "motion_peak":             m.motion.peak,
        "flashing_events_per_min": m.flashing.luminance_delta_events_per_min,
        "audio_rms_mean":          m.audio.rms_mean if m.audio.available else None,
        "audio_dynamic_range_db":  m.audio.dynamic_range_db if m.audio.available else None,
        "audio_available":         int(m.audio.available),
        "sensory_load_score":      m.sensory_load.score,
        "analyzed_at":             datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
    })
    conn.commit()


def upsert_show(
    conn: sqlite3.Connection,
    aggregate: ShowAggregate,
    show_name: str,
) -> None:
    """Insert or replace a show aggregate row."""
    audio_mean = aggregate.audio_rms_mean.mean if aggregate.audio_rms_mean.mean else None
    conn.execute("""
        INSERT INTO shows (
            show_name, episode_count, avg_load, median_load,
            avg_cuts_per_min, avg_motion, avg_saturation, avg_contrast,
            avg_flashing, avg_audio_rms, updated_at
        ) VALUES (
            :show_name, :episode_count, :avg_load, :median_load,
            :avg_cuts_per_min, :avg_motion, :avg_saturation, :avg_contrast,
            :avg_flashing, :avg_audio_rms, :updated_at
        )
        ON CONFLICT(show_name) DO UPDATE SET
            episode_count    = excluded.episode_count,
            avg_load         = excluded.avg_load,
            median_load      = excluded.median_load,
            avg_cuts_per_min = excluded.avg_cuts_per_min,
            avg_motion       = excluded.avg_motion,
            avg_saturation   = excluded.avg_saturation,
            avg_contrast     = excluded.avg_contrast,
            avg_flashing     = excluded.avg_flashing,
            avg_audio_rms    = excluded.avg_audio_rms,
            updated_at       = excluded.updated_at
    """, {
        "show_name":        show_name,
        "episode_count":    aggregate.episode_count,
        "avg_load":         aggregate.sensory_load_score.mean,
        "median_load":      aggregate.sensory_load_score.median,
        "avg_cuts_per_min": aggregate.cuts_per_min.mean,
        "avg_motion":       aggregate.motion_mean.mean,
        "avg_saturation":   aggregate.color_saturation_mean.mean,
        "avg_contrast":     aggregate.color_contrast_mean.mean,
        "avg_flashing":     aggregate.flashing_events_per_min.mean,
        "avg_audio_rms":    audio_mean,
        "updated_at":       datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
    })
    conn.commit()


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

_EP_SORT_COLS = {
    "show_name", "file_name", "duration_sec", "cuts_per_min",
    "color_saturation_mean", "color_contrast_mean", "motion_mean",
    "flashing_events_per_min", "audio_rms_mean",
    "sensory_load_score", "analyzed_at",
}
_SHOW_SORT_COLS = {
    "show_name", "episode_count", "avg_load",
    "avg_cuts_per_min", "avg_motion", "avg_saturation",
    "avg_contrast", "avg_flashing", "avg_audio_rms",
}


def query_episodes(
    conn: sqlite3.Connection,
    sort_by: str = "analyzed_at",
    ascending: bool = False,
    filter_show: str = "",
) -> list[dict]:
    col = sort_by if sort_by in _EP_SORT_COLS else "analyzed_at"
    direction = "ASC" if ascending else "DESC"
    if filter_show:
        rows = conn.execute(
            f"SELECT * FROM episodes WHERE show_name LIKE ? ORDER BY {col} {direction}",
            (f"%{filter_show}%",),
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT * FROM episodes ORDER BY {col} {direction}"
        ).fetchall()
    return [dict(r) for r in rows]


def query_shows(
    conn: sqlite3.Connection,
    sort_by: str = "avg_load",
    ascending: bool = False,
) -> list[dict]:
    col = sort_by if sort_by in _SHOW_SORT_COLS else "avg_load"
    direction = "ASC" if ascending else "DESC"
    rows = conn.execute(
        f"SELECT * FROM shows ORDER BY {col} {direction}"
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

def get_note(conn: sqlite3.Connection, file_path: str) -> str:
    """Return the saved note for an episode, or '' if none."""
    row = conn.execute(
        "SELECT notes FROM episodes WHERE file_path = ?", (file_path,)
    ).fetchone()
    if row is None:
        return ""
    return row["notes"] or ""


def save_note(conn: sqlite3.Connection, file_path: str, note: str) -> None:
    """Persist a note for an episode (no-op if file_path not yet in DB)."""
    conn.execute(
        "UPDATE episodes SET notes = ? WHERE file_path = ?",
        (note, file_path),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Percentile / rank
# ---------------------------------------------------------------------------

def get_episode_percentile(conn: sqlite3.Connection, file_path: str) -> dict:
    """Return rank and percentile info for an episode by sensory_load_score.

    Returns {} if the episode is not in the DB or has no score.
    Returned dict keys:
      percentile   — 0-100: % of all indexed episodes that score lower
      global_total — total episodes with a score in the DB
      show_rank    — 1-based rank within the show (1 = most stimulating)
      show_total   — episodes from this show in the DB
      show_name    — show the episode belongs to
    """
    row = conn.execute(
        "SELECT show_name, sensory_load_score FROM episodes WHERE file_path = ?",
        (file_path,),
    ).fetchone()
    if row is None or row["sensory_load_score"] is None:
        return {}

    score: float = row["sensory_load_score"]
    show_name: str = row["show_name"]

    below = conn.execute(
        "SELECT COUNT(*) FROM episodes WHERE sensory_load_score < ?",
        (score,),
    ).fetchone()[0]
    total = conn.execute(
        "SELECT COUNT(*) FROM episodes WHERE sensory_load_score IS NOT NULL"
    ).fetchone()[0]

    # Within-show rank: 1 = most stimulating (highest score)
    show_above = conn.execute(
        "SELECT COUNT(*) FROM episodes WHERE show_name = ? AND sensory_load_score > ?",
        (show_name, score),
    ).fetchone()[0]
    show_total = conn.execute(
        "SELECT COUNT(*) FROM episodes "
        "WHERE show_name = ? AND sensory_load_score IS NOT NULL",
        (show_name,),
    ).fetchone()[0]

    percentile = int(round(below / total * 100)) if total > 1 else 0

    return {
        "percentile":   percentile,
        "global_total": total,
        "show_rank":    show_above + 1,
        "show_total":   show_total,
        "show_name":    show_name,
    }
