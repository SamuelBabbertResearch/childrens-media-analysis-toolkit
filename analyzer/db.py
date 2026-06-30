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

        CREATE TABLE IF NOT EXISTS show_eras (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            show_name  TEXT NOT NULL,
            era_name   TEXT NOT NULL,
            start_date TEXT,
            end_date   TEXT,
            color      TEXT
        );
    """)
    conn.commit()
    # Migrate existing DBs
    for sql in [
        "ALTER TABLE episodes ADD COLUMN color_contrast_mean REAL",
        "ALTER TABLE shows ADD COLUMN avg_contrast REAL",
        "ALTER TABLE shows ADD COLUMN avg_flashing REAL",
        "ALTER TABLE episodes ADD COLUMN notes TEXT",
        # Phase 1: longitudinal metadata
        "ALTER TABLE episodes ADD COLUMN air_date TEXT",
        "ALTER TABLE episodes ADD COLUMN season_num INTEGER",
        "ALTER TABLE episodes ADD COLUMN episode_num INTEGER",
        "ALTER TABLE shows ADD COLUMN format TEXT",
        "ALTER TABLE shows ADD COLUMN target_age_min INTEGER",
        "ALTER TABLE shows ADD COLUMN target_age_max INTEGER",
        "ALTER TABLE shows ADD COLUMN show_notes TEXT",
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
    "sensory_load_score", "analyzed_at", "notes",
    "air_date", "season_num", "episode_num",
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

def remove_stale_episodes(conn: sqlite3.Connection) -> int:
    """Delete episode rows whose file_path no longer exists on disk.

    Also removes show rows that are left with zero episodes.
    Returns the number of episode rows deleted.
    """
    rows = conn.execute("SELECT file_path FROM episodes").fetchall()
    stale = [r["file_path"] for r in rows if not Path(r["file_path"]).exists()]
    if not stale:
        return 0
    conn.executemany("DELETE FROM episodes WHERE file_path = ?", [(p,) for p in stale])
    conn.execute("""
        DELETE FROM shows
        WHERE show_name NOT IN (SELECT DISTINCT show_name FROM episodes)
    """)
    conn.commit()
    return len(stale)


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
# Episode metadata (longitudinal)
# ---------------------------------------------------------------------------

def get_episode_metadata(conn: sqlite3.Connection, file_path: str) -> dict:
    """Return air_date, season_num, episode_num for an episode, or empty strings/None."""
    row = conn.execute(
        "SELECT air_date, season_num, episode_num FROM episodes WHERE file_path = ?",
        (file_path,),
    ).fetchone()
    if row is None:
        return {"air_date": "", "season_num": None, "episode_num": None}
    return {
        "air_date":    row["air_date"] or "",
        "season_num":  row["season_num"],
        "episode_num": row["episode_num"],
    }


def upsert_episode_metadata(
    conn: sqlite3.Connection,
    file_path: str,
    air_date: str | None,
    season_num: int | None,
    episode_num: int | None,
) -> None:
    """Save longitudinal metadata fields for an episode row."""
    conn.execute(
        """UPDATE episodes
           SET air_date = ?, season_num = ?, episode_num = ?
           WHERE file_path = ?""",
        (air_date or None, season_num, episode_num, file_path),
    )
    conn.commit()


def get_show_metadata(conn: sqlite3.Connection, show_name: str) -> dict:
    """Return format, target_age_min/max, show_notes for a show."""
    row = conn.execute(
        "SELECT format, target_age_min, target_age_max, show_notes FROM shows WHERE show_name = ?",
        (show_name,),
    ).fetchone()
    if row is None:
        return {"format": "", "target_age_min": None, "target_age_max": None, "show_notes": ""}
    return {
        "format":         row["format"] or "",
        "target_age_min": row["target_age_min"],
        "target_age_max": row["target_age_max"],
        "show_notes":     row["show_notes"] or "",
    }


def auto_set_season(conn: sqlite3.Connection, file_path: str, season_num: int) -> None:
    """Set season_num only if the row doesn't already have one (won't overwrite manual entry)."""
    conn.execute(
        "UPDATE episodes SET season_num = ? WHERE file_path = ? AND season_num IS NULL",
        (season_num, file_path),
    )
    conn.commit()


def upsert_show_metadata(
    conn: sqlite3.Connection,
    show_name: str,
    format: str | None,
    target_age_min: int | None,
    target_age_max: int | None,
    show_notes: str | None,
) -> None:
    """Save metadata fields for a show row (no-op if show not yet indexed)."""
    conn.execute(
        """UPDATE shows
           SET format = ?, target_age_min = ?, target_age_max = ?, show_notes = ?
           WHERE show_name = ?""",
        (format or None, target_age_min, target_age_max, show_notes or None, show_name),
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


# ---------------------------------------------------------------------------
# Era stratification
# ---------------------------------------------------------------------------

def get_show_eras(conn: sqlite3.Connection, show_name: str) -> list[dict]:
    """Return era definitions for a show, ordered by start date."""
    rows = conn.execute(
        "SELECT era_name, start_date, end_date, color FROM show_eras "
        "WHERE show_name = ? ORDER BY COALESCE(start_date, '0') ASC",
        (show_name,),
    ).fetchall()
    return [dict(r) for r in rows]


def save_show_eras(
    conn: sqlite3.Connection,
    show_name: str,
    eras: list[dict],
) -> None:
    """Replace all era definitions for a show."""
    conn.execute("DELETE FROM show_eras WHERE show_name = ?", (show_name,))
    for era in eras:
        conn.execute(
            "INSERT INTO show_eras (show_name, era_name, start_date, end_date, color) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                show_name,
                era.get("era_name", ""),
                era.get("start_date") or None,
                era.get("end_date") or None,
                era.get("color") or None,
            ),
        )
    conn.commit()
