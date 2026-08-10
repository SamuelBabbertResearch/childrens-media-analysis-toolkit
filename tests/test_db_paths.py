"""
The index keys episodes on file_path, so one episode must have one spelling.

Reaching the same file through a relative root and an absolute one used to
produce two rows, which double-counted it in every aggregate read from the
index — and "Remove Stale" could not clear it, because both spellings still
resolved to a file that exists.
"""

from __future__ import annotations

import os

from analyzer.db import canonical_path, get_db, query_episodes, upsert_episode
from analyzer.schema import EpisodeResult


def _result(name: str) -> EpisodeResult:
    r = EpisodeResult(file=name, duration_sec=60.0)
    r.metrics.sensory_load.score = 0.2
    return r


def test_canonical_path_is_absolute():
    assert os.path.isabs(canonical_path("Shows/Demo/ep01.mp4"))


def test_canonical_path_survives_a_path_that_cannot_be_resolved(monkeypatch):
    """A row is not worth losing over a path that will not canonicalise.

    resolve() is forced to fail here: which inputs actually raise is
    platform-specific, so the guard is exercised directly rather than through
    a string that happens to raise on one OS.
    """
    import analyzer.db as db

    def boom(self, *a, **kw):
        raise OSError("cannot resolve")

    monkeypatch.setattr(db.Path, "resolve", boom)
    assert canonical_path("whatever/ep01.mp4") == "whatever/ep01.mp4"


def test_one_episode_reached_two_ways_makes_one_row(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    show = tmp_path / "Shows" / "Demo"
    show.mkdir(parents=True)
    episode = show / "ep01.mp4"
    episode.write_bytes(b"")

    conn = get_db(tmp_path / "Shows")
    upsert_episode(conn, _result("ep01.mp4"), "Demo",
                   "Shows/Demo/ep01.mp4", show_key="Demo")
    upsert_episode(conn, _result("ep01.mp4"), "Demo",
                   str(episode), show_key="Demo")
    conn.commit()

    rows = query_episodes(conn)
    assert len(rows) == 1, "the same episode was indexed twice"
    assert os.path.isabs(rows[0]["file_path"])


def test_migration_folds_an_existing_relative_row_and_keeps_its_note(
        tmp_path, monkeypatch):
    """A note is the only thing in this table a person typed; keep it."""
    monkeypatch.chdir(tmp_path)
    show = tmp_path / "Shows" / "Demo"
    show.mkdir(parents=True)
    episode = show / "ep01.mp4"
    episode.write_bytes(b"")

    conn = get_db(tmp_path / "Shows")
    # Write both spellings behind upsert's back, as older runs did.
    for path in ("Shows/Demo/ep01.mp4", str(episode)):
        conn.execute(
            "INSERT INTO episodes (file_path, show_key, show_name, file_name) "
            "VALUES (?, ?, ?, ?)", (path, "Demo", "Demo", "ep01.mp4"))
    conn.execute("UPDATE episodes SET notes = ? WHERE file_path = ?",
                 ("hand-typed", "Shows/Demo/ep01.mp4"))
    conn.commit()
    conn.close()

    conn = get_db(tmp_path / "Shows")          # migration runs on open
    rows = query_episodes(conn)
    assert len(rows) == 1
    assert rows[0]["notes"] == "hand-typed"
