"""Human coding under the research context: the worklist, and one sheet lookup.

These assert on the ROWS the worklist builds and on the sheet the Code screen
actually opens — not on whether a worklist widget exists. The two defects
pinned here were both invisible from the interface: a coding sheet filed in a
subfolder read as "not coded" on screen while `code_events.py` scored it, and
opening a second episode kept the first one's marks in the table.

Nothing here touches the working copy's `validation/` folder. That is real
research data.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from analyzer.event_coding import (
    event_sheet_status, find_event_sheet, write_event_template,
)
from analyzer.scope import library_scope, scope_from_draw


# --- fixtures ----------------------------------------------------------------

def _write_sheet(path: Path, timestamps: list[str]) -> Path:
    """An event sheet with real coded rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp_hms", "timestamp_sec", "event_type",
                         "narrative_relevance", "repeat", "duration_sec",
                         "notes"])
        for i, hms in enumerate(timestamps):
            writer.writerow([hms, 10 * (i + 1), "physical", "integral", "new",
                             "", ""])
    return path


def _library(tmp_path: Path, names: list[str]) -> tuple[Path, list[Path]]:
    root = tmp_path / "Library"
    show = root / "Little Bear"
    show.mkdir(parents=True)
    episodes = []
    for name in names:
        ep = show / f"{name}.mp4"
        ep.write_bytes(b"")
        episodes.append(ep)
    return root, episodes


def _draw(tmp_path: Path, episodes: list[Path], name: str = "draw") -> Path:
    folder = tmp_path / name
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "selected.csv").open("w", newline="",
                                        encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["entry_id", "season",
                                                "episode", "title",
                                                "air_date", "filepath"])
        writer.writeheader()
        for i, ep in enumerate(episodes, start=1):
            writer.writerow({"entry_id": "Little Bear", "season": 1,
                             "episode": i, "title": "", "air_date": "",
                             "filepath": str(ep)})
    return folder


# --- one lookup for "where is this episode's sheet?" -------------------------

def test_a_sheet_filed_in_a_subfolder_is_still_found(tmp_path):
    """The Qt Code screen looked only at `<validation>/<stem>_events.csv`.

    `code_events.py`, `trials.py` and both Tk screens search recursively. So a
    sheet filed one folder down read as "not coded" on screen while the
    command line scored it — and the screen would have started a fresh empty
    sheet over the top of a real coding pass.
    """
    vdir = tmp_path / "validation"
    sheet = _write_sheet(vdir / "little-bear" / "S01 E01_events.csv",
                         ["00:00:10", "00:00:20"])

    assert find_event_sheet(Path("S01 E01.mp4"), vdir) == sheet
    assert event_sheet_status(Path("S01 E01.mp4"), vdir)["n_events"] == 2


def test_a_shortened_sheet_name_is_matched_by_prefix(tmp_path):
    """Coders shorten long filenames — the rule `find_manual` already uses."""
    vdir = tmp_path / "validation"
    sheet = _write_sheet(vdir / "Little Bear 1x01_events.csv", ["00:00:05"])
    episode = Path("Little Bear 1x01 Up All Night _ A Kiss for Little Bear.mp4")

    assert find_event_sheet(episode, vdir) == sheet


def test_too_short_a_prefix_is_not_matched(tmp_path):
    """Eight characters minimum, or every sheet matches every episode."""
    vdir = tmp_path / "validation"
    _write_sheet(vdir / "Lit_events.csv", ["00:00:05"])
    assert find_event_sheet(Path("Little Bear 1x01.mp4"), vdir) is None


def test_a_template_with_no_rows_is_started_not_coded(tmp_path):
    """Someone created it and has not coded yet. A different state from none."""
    vdir = tmp_path / "validation"
    vdir.mkdir()
    write_event_template(Path("S01 E01.mp4"), vdir)

    status = event_sheet_status(Path("S01 E01.mp4"), vdir)
    assert status["exists"] is True
    assert status["n_events"] == 0
    assert status["step"] == "started"


def test_no_sheet_is_reported_as_uncoded_not_as_an_error(tmp_path):
    vdir = tmp_path / "validation"
    vdir.mkdir()
    status = event_sheet_status(Path("Never Coded.mp4"), vdir)
    assert status == {"sheet": None, "exists": False, "n_events": 0,
                      "step": "uncoded"}


def test_the_trials_summary_uses_the_same_lookup(tmp_path):
    """It had its own copy of the rule, with the same fallback written twice.

    Asserted on BEHAVIOUR — a sheet filed one folder down, counted through the
    real `sample_coverage` — rather than on the source text. A source-text
    check here would pass with a broken function-local import, which is
    exactly how `_read_selected` was moved and missed.
    """
    from analyzer.trials import sample_coverage

    root = tmp_path / "Library"
    show = root / "Little Bear"
    show.mkdir(parents=True)
    episodes = []
    for name in ("S01 E01", "S01 E02"):
        ep = show / f"{name}.mp4"
        ep.write_bytes(b"")
        episodes.append(ep)
    folder = _draw(tmp_path, episodes)
    vdir = tmp_path / "validation"
    _write_sheet(vdir / "filed-away" / "S01 E01_events.csv", ["00:00:10"])

    progress = sample_coverage(
        {"kind": "episode_sample", "folder": folder}, validation_dir=vdir)

    assert progress is not None
    assert progress["n_episodes"] == 2
    assert progress["n_event_coded"] == 1, \
        "a sheet filed in a subfolder was not counted"


# --- the worklist ------------------------------------------------------------

@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from analyzer import prefs
    monkeypatch.setattr(prefs, "get_pref", lambda k, d=None: None)
    monkeypatch.setattr(prefs, "set_pref", lambda k, v: None)
    import ui.main_window as mw
    monkeypatch.setattr(mw, "get_pref", lambda k, d=None: None)
    monkeypatch.setattr(mw, "set_pref", lambda k, v: None)
    # NEVER the working copy's validation folder — it is research data.
    vdir = tmp_path / "validation"
    vdir.mkdir()
    import ui.handcoding as hc
    monkeypatch.setattr(hc, "get_validation_dir", lambda: vdir)
    win = mw.MainWindow()
    win._test_vdir = vdir
    yield win
    win.close()


def _rows(worklist) -> list[tuple[str, str]]:
    table = worklist._table
    return [(table.topLevelItem(i).text(0), table.topLevelItem(i).text(1))
            for i in range(table.topLevelItemCount())]


def test_the_worklist_shows_the_sample_with_each_episodes_coding_state(
        window, tmp_path):
    root, episodes = _library(tmp_path, ["S01 E01", "S01 E02", "S01 E03"])
    window.set_root(root)
    _write_sheet(window._test_vdir / "S01 E01_events.csv",
                 ["00:00:10", "00:00:20", "00:00:31"])
    folder = _draw(tmp_path, episodes[:2])

    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))

    worklist = window._handcoding.code.worklist
    assert _rows(worklist) == [("S01 E01.mp4", "3 events"),
                               ("S01 E02.mp4", "not coded")]
    assert worklist._count.text() == "1 of 2 with coding"
    # The episode that was not drawn does not appear, coded or not.
    assert "S01 E03.mp4" not in [name for name, _ in _rows(worklist)]


def test_the_worklist_says_why_it_is_empty_under_the_whole_library(
        window, tmp_path):
    """A worklist of the whole library is a library. It has to end."""
    root, episodes = _library(tmp_path, ["S01 E01", "S01 E02"])
    window.set_root(root)
    folder = _draw(tmp_path, episodes)
    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))
    assert len(_rows(window._handcoding.code.worklist)) == 2

    window.set_scope(library_scope())

    worklist = window._handcoding.code.worklist
    assert _rows(worklist) == []
    assert "Showing:" in worklist._note.text()


def test_the_worklist_accounts_for_a_draw_that_lost_files(window, tmp_path):
    """listed + missing must equal drawn, or the coder plans the wrong pass."""
    root, episodes = _library(tmp_path, ["S01 E01"])
    gone = root / "Little Bear" / "S01 E99.mp4"          # never created
    window.set_root(root)
    folder = _draw(tmp_path, episodes + [gone])

    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))

    worklist = window._handcoding.code.worklist
    assert len(_rows(worklist)) == 1
    note = worklist._note.text()
    assert "2 episodes drawn" in note
    assert "1 no longer on disk, so 1 can be coded" in note


def test_the_validate_worklist_reports_transition_coding_not_events(
        window, tmp_path):
    """Two different sheets. Reading the wrong one would say "coded" for an
    episode with no transition coding at all, which is what Validate grades."""
    root, episodes = _library(tmp_path, ["S01 E01"])
    window.set_root(root)
    _write_sheet(window._test_vdir / "S01 E01_events.csv", ["00:00:10"])
    folder = _draw(tmp_path, episodes)

    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))

    assert _rows(window._handcoding.code.worklist) == [("S01 E01.mp4",
                                                        "1 event")]
    # An event sheet is not transition coding, and Validate must not claim it.
    assert _rows(window._handcoding.validate.worklist) == [("S01 E01.mp4",
                                                            "no sheet")]


# --- switching episodes ------------------------------------------------------

class _StubPlayer:
    """Enough of ui.player.VideoPlayer to drive the load path without VLC.

    `playing` and `stamp_at` let a test choose which of VideoPlayer.stamp()'s
    two paths to exercise: paused (synchronous callback with `stamp_at`) or
    playing (deferred — `settle()` must be called to fire the callback,
    mirroring the real settle loop needing the Qt event loop pumped).
    """

    def __init__(self) -> None:
        self.opened: list[Path] = []
        self.playing = False
        self.stamp_at = 0.0
        self._pending: list = []

    def open(self, path):
        self.opened.append(Path(path))

    def position(self) -> float:
        return self.stamp_at

    def seek(self, _seconds) -> None:
        pass

    def is_playing(self) -> bool:
        return self.playing

    def stamp(self, callback) -> None:
        if not self.playing:
            callback(self.stamp_at)
            return
        self._pending.append(callback)

    def settle(self) -> None:
        """Simulates the real pause-settle completing: flips to paused and
        fires every stamp() call that was waiting on it."""
        self.playing = False
        pending, self._pending = self._pending, []
        for callback in pending:
            callback(self.stamp_at)


def test_marking_while_paused_records_immediately(window, tmp_path):
    """The common case: no settle needed, the event is there right away."""
    root, episodes = _library(tmp_path, ["S01 E01"])
    window.set_root(root)
    folder = _draw(tmp_path, episodes)
    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))

    code = window._handcoding.code
    code._player = _StubPlayer()
    code._player.stamp_at = 12.5
    code._load_episode(episodes[0])

    code._btn_mark.click()

    assert len(code._events) == 1
    assert code._events[0]["timestamp_sec"] == 12.5


def test_marking_while_playing_waits_for_the_pause_to_settle(
        window, tmp_path):
    """_mark() must never record the coarse live clock. While playing, the
    event must not appear until the stub's pause-settle actually completes
    — proving _mark() goes through stamp() rather than reading position()
    at the moment of the click."""
    root, episodes = _library(tmp_path, ["S01 E01"])
    window.set_root(root)
    folder = _draw(tmp_path, episodes)
    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))

    code = window._handcoding.code
    code._player = _StubPlayer()
    code._player.playing = True
    code._player.stamp_at = 75.25
    code._load_episode(episodes[0])

    code._btn_mark.click()
    assert code._events == [], \
        "recorded a mark before the pause was confirmed"

    code._player.settle()
    assert len(code._events) == 1
    assert code._events[0]["timestamp_sec"] == 75.25


def test_a_mark_taken_while_playing_keeps_the_fields_from_the_click(
        window, tmp_path):
    """The dropdowns are read at click time, not when the settle callback
    fires, so nothing the coder changes during the (usually ~20ms, capped
    at 300ms) settle window can leak into the mark still in flight."""
    root, episodes = _library(tmp_path, ["S01 E01"])
    window.set_root(root)
    folder = _draw(tmp_path, episodes)
    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))

    code = window._handcoding.code
    code._player = _StubPlayer()
    code._player.playing = True
    code._player.stamp_at = 5.0
    code._load_episode(episodes[0])

    code._type.setCurrentIndex(code._type.findData("transformation"))
    code._btn_mark.click()
    code._type.setCurrentIndex(code._type.findData("physical"))  # changed
    code._player.settle()

    assert code._events[0]["event_type"] == "transformation"


def test_opening_a_second_episode_does_not_carry_the_first_ones_events(
        window, tmp_path):
    """It did. The second episode's sheet would have been SAVED holding them.

    Marks are hand-placed timestamps for one video; writing them under another
    episode's name is silent data corruption of the only measurement in this
    tool a person makes themselves.
    """
    root, episodes = _library(tmp_path, ["S01 E01", "S01 E02"])
    window.set_root(root)
    _write_sheet(window._test_vdir / "S01 E01_events.csv",
                 ["00:00:10", "00:00:20"])
    folder = _draw(tmp_path, episodes)
    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))

    code = window._handcoding.code
    code._player = _StubPlayer()

    code._load_episode(episodes[0])
    assert len(code._events) == 2

    code._load_episode(episodes[1])          # no sheet of its own
    assert code._events == [], \
        "the previous episode's marks survived into an uncoded episode"
    assert code._sheet.name == "S01 E02_events.csv"
    assert code._dirty is False, \
        "a freshly opened episode was marked dirty, so Save would write it"


def test_the_code_screen_opens_the_sheet_the_command_line_scores(
        window, tmp_path):
    """Not a new empty one beside it. Same lookup, one sheet per episode."""
    root, episodes = _library(tmp_path, ["S01 E01"])
    window.set_root(root)
    filed = _write_sheet(
        window._test_vdir / "session-2026-08" / "S01 E01_events.csv",
        ["00:00:10", "00:00:20", "00:00:30"])

    code = window._handcoding.code
    code._player = _StubPlayer()
    code._load_episode(episodes[0])

    assert code._sheet == filed
    assert len(code._events) == 3


def test_the_worklist_row_follows_a_save(window, tmp_path):
    """Otherwise the coder finishes an episode and the list still says 0."""
    root, episodes = _library(tmp_path, ["S01 E01"])
    window.set_root(root)
    folder = _draw(tmp_path, episodes)
    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))

    code = window._handcoding.code
    code._player = _StubPlayer()
    code._load_episode(episodes[0])
    assert _rows(code.worklist) == [("S01 E01.mp4", "not coded")]

    code._events = [{"timestamp_sec": 12.0, "timestamp_hms": "00:00:12",
                     "event_type": "physical",
                     "narrative_relevance": "integral", "repeat": "new",
                     "duration_sec": None, "notes": ""}]
    code._dirty = True
    code._save_sheet()

    assert _rows(code.worklist) == [("S01 E01.mp4", "1 event")]
    # And the file on disk is what the engine reads back.
    assert event_sheet_status(episodes[0], window._test_vdir)["n_events"] == 1
