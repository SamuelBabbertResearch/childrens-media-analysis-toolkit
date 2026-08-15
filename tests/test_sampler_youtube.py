"""YouTube in the sampler: live fetch, playlists, and channel eras.

`analyzer.youtube_fetch.fetch_videos()` is tested against canned yt-dlp-shaped
output (subprocess mocked) — no network call, no real yt-dlp dependency for
the test itself. `ui.sampler.SamplerDialog`'s wiring is tested against a
stubbed fetch dialog, the same way `_StubPlayer` stands in for VideoPlayer
elsewhere in this suite.

Nothing here touches the working copy's `validation/` or `Shows/` folders.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from analyzer import youtube_fetch as yf
from analyzer.eras import assign_eras
from analyzer.sampler import Episode
from analyzer.show_index import show_key as real_show_key


# --- analyzer.youtube_fetch.fetch_videos() -----------------------------------

class _FakeResult:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout
        self.stderr = ""
        self.returncode = 0


CHANNEL_OUTPUT = "\n".join([
    "20230101\tvid1\t300\tGame Theorists\tUploads from Game Theorists\t"
    "UUxyz\thttps://www.youtube.com/watch?v=vid1\tFirst Video",
    "20230615\tvid2\t45\tGame Theorists\tUploads from Game Theorists\t"
    "UUxyz\thttps://www.youtube.com/watch?v=vid2\tA Short",     # too short
    "20231010\tvid3\t600\tGame Theorists\tNA\tNA\t"
    "https://www.youtube.com/watch?v=vid3\tThird Video",
    "NA\tvid4\t400\tGame Theorists\tNA\tNA\t"
    "https://www.youtube.com/watch?v=vid4\tNo Date Video",      # no date
])


def _mock_ytdlp(stdout_by_call):
    """Patches subprocess.run and _ytdlp_path; stdout_by_call is either a
    fixed string or a callable(call_index) -> string."""
    calls = {"n": 0}

    def fake_run(cmd, **kwargs):
        out = (stdout_by_call(calls["n"]) if callable(stdout_by_call)
               else stdout_by_call)
        calls["n"] += 1
        return _FakeResult(out)
    return patch.object(subprocess, "run", side_effect=fake_run), \
        patch.object(yf, "_ytdlp_path", return_value="yt-dlp")


def test_fetch_videos_filters_short_and_dateless_entries():
    run_patch, path_patch = _mock_ytdlp(CHANNEL_OUTPUT)
    with run_patch, path_patch:
        episodes = yf.fetch_videos(
            ["https://www.youtube.com/@GameTheorists/videos"],
            min_duration=120)
    ids = {e.extra["video_id"] for e in episodes}
    assert ids == {"vid1", "vid3"}, \
        "vid2 (too short) and vid4 (no date) must be excluded"


def test_fetch_videos_builds_real_episode_fields():
    run_patch, path_patch = _mock_ytdlp(CHANNEL_OUTPUT)
    with run_patch, path_patch:
        episodes = yf.fetch_videos(
            ["https://www.youtube.com/@GameTheorists/videos"],
            min_duration=120)
    v1 = next(e for e in episodes if e.extra["video_id"] == "vid1")
    assert v1.air_date == "2023-01-01"
    assert v1.title == "First Video"
    assert v1.extra["channel"] == "Game Theorists"
    assert v1.extra["url"] == "https://www.youtube.com/watch?v=vid1"
    assert v1.filepath is None
    assert v1.episode is not None, \
        "needs a sequential ordinal, same fallback scan_entry_root() uses"


def test_fetch_videos_tags_playlist_membership():
    playlist_output = "\n".join([
        "20220505\tp1\t500\tGame Theorists\tFilm Theory Classics\tPLabc\t"
        "https://www.youtube.com/watch?v=p1\tPlaylist Video One",
        "20220606\tp2\t500\tGame Theorists\tFilm Theory Classics\tPLabc\t"
        "https://www.youtube.com/watch?v=p2\tPlaylist Video Two",
    ])
    run_patch, path_patch = _mock_ytdlp(playlist_output)
    with run_patch, path_patch:
        episodes = yf.fetch_videos(
            ["https://www.youtube.com/playlist?list=PLabc"], min_duration=0)
    assert all(e.extra.get("playlist") == "Film Theory Classics"
              for e in episodes)


def test_fetch_videos_dedupes_a_video_seen_in_two_urls():
    dup_line = ("20230101\tvid1\t300\tGame Theorists\tSomething\tPLxyz\t"
               "https://www.youtube.com/watch?v=vid1\tFirst Video (dup)")

    def by_call(n):
        return CHANNEL_OUTPUT if n == 0 else dup_line

    run_patch, path_patch = _mock_ytdlp(by_call)
    with run_patch, path_patch:
        episodes = yf.fetch_videos(
            ["https://www.youtube.com/@GameTheorists/videos",
             "https://www.youtube.com/playlist?list=PLxyz"],
            min_duration=120)
    ids = [e.extra["video_id"] for e in episodes]
    assert ids.count("vid1") == 1, \
        "a video present in two sampled sources must be kept once"


def test_channel_slug_from_a_handle_url():
    assert yf.channel_slug(
        "https://www.youtube.com/@GameTheorists/videos") == "gametheorists"


def test_channel_slug_falls_back_for_a_bare_playlist_url():
    assert yf.channel_slug(
        "https://www.youtube.com/playlist?list=PLxyz") == "youtube"


# --- ui.sampler.SamplerDialog wiring -----------------------------------------

@pytest.fixture
def dialog(qapp):
    from PySide6.QtWidgets import QWidget
    from ui.sampler import SamplerDialog

    class _FakeWindow(QWidget):
        _root = Path(r"C:\Users\Samuel\Child Development Television Index Project\Shows")
        def _db(self):
            return None

    win = _FakeWindow()
    d = SamplerDialog(win, win)
    yield d
    d.close()


def test_fetch_button_only_shows_for_youtube_content_type(dialog):
    assert dialog._btn_fetch.isHidden() is True

    dialog._content_type.setCurrentIndex(dialog._content_type.findData("movies"))
    assert dialog._btn_fetch.isHidden() is True

    dialog._content_type.setCurrentIndex(dialog._content_type.findData("youtube"))
    assert dialog._btn_fetch.isHidden() is False


def test_choose_fetch_adopts_the_dialogs_result(dialog):
    from PySide6.QtWidgets import QDialog

    fake_episodes = [
        Episode(entry_id="Game Theorists", season=None, episode=1,
                title="Vid A", air_date="2023-01-01", runtime=300.0,
                filepath=None,
                extra={"url": "https://youtube.com/watch?v=a",
                      "video_id": "a", "channel": "Game Theorists"}),
    ]

    class _FakeFetchDialog:
        def __init__(self, parent=None):
            self.episodes = fake_episodes
            self.channel_id = "gametheorists"
        def exec(self):
            return QDialog.Accepted

    with patch("ui.youtube_fetch.YouTubeFetchDialog", _FakeFetchDialog):
        dialog._choose_fetch()

    assert dialog._episodes == fake_episodes
    assert dialog._fetch_id == "gametheorists"
    assert dialog._folder is None
    assert dialog._registry is None


def test_show_key_namespaces_a_live_fetch_away_from_real_shows(dialog):
    dialog._fetch_id = "gametheorists"
    assert dialog._show_key() == "youtube:gametheorists"

    # A real folder-derived key is always a POSIX relative path and can
    # never contain ':' — so the synthetic namespace cannot collide with it.
    real_key = real_show_key(dialog._window._root, dialog._window._root / "Arthur")
    assert ":" not in real_key


def test_choosing_a_folder_clears_a_previous_fetch_source(dialog):
    dialog._fetch_id = "gametheorists"
    dialog._folder = None
    dialog._registry = None
    from analyzer.sampler import scan_entry_root
    dialog._folder = dialog._window._root / "Arthur"
    dialog._episodes = scan_entry_root(dialog._folder)
    dialog._registry = None
    dialog._fetch_id = None    # what _choose_folder() does on a real click
    assert dialog._show_key() != "youtube:gametheorists"


def test_eras_persist_and_apply_under_the_synthetic_youtube_key(dialog, tmp_path):
    from analyzer.db import get_db, save_show_eras, get_show_eras

    dialog._fetch_id = "gametheorists"
    key = dialog._show_key()
    conn = get_db(tmp_path)
    save_show_eras(conn, key, [
        {"era_name": "Early", "start_date": "2020-01-01",
         "end_date": "2023-03-01"},
        {"era_name": "Later", "start_date": "2023-03-02",
         "end_date": "2030-01-01"},
    ])
    eras = get_show_eras(conn, key)
    assert [e["era_name"] for e in eras] == ["Early", "Later"]

    episodes = [
        Episode(entry_id="x", season=None, episode=1, title="A",
               air_date="2023-01-01", runtime=None, filepath=None),
        Episode(entry_id="x", season=None, episode=2, title="B",
               air_date="2023-06-01", runtime=None, filepath=None),
    ]
    assign_eras(episodes, eras)
    assert episodes[0].extra["era"] == "Early"
    assert episodes[1].extra["era"] == "Later"


def test_stratify_offers_channel_and_playlist_but_not_ids(dialog):
    dialog._episodes = [
        Episode(entry_id="x", season=None, episode=1, title="A",
               air_date="2023-01-01", runtime=None, filepath=None,
               extra={"channel": "Game Theorists", "playlist": "Theory",
                     "video_id": "a", "url": "https://youtube.com/watch?v=a"}),
    ]
    dialog._refresh_stratify()
    offered = [dialog._stratify.itemData(i)
              for i in range(dialog._stratify.count())]
    assert "channel" in offered
    assert "playlist" in offered
    assert "video_id" not in offered
    assert "url" not in offered
