"""
analyzer/youtube_fetch.py — metadata-only YouTube sampling frame, via yt-dlp.

No video is ever downloaded here. `fetch_videos()` asks yt-dlp for a channel
or playlist's video list — title, upload date, duration, channel, playlist —
so a sample can be DESIGNED before a byte of video is fetched. That ordering
is the point: downloading a whole channel to decide what to study is the
waste this exists to avoid.

Ported from the standalone `sample_youtube.py` script (now retired — its
fetch logic lived nowhere the real sampler could use it, and its own spread
algorithm duplicated `analyzer.sampler`'s). This module keeps the same
`--flat-playlist --print` approach and the same `min_duration` filter and
its reason (excludes Shorts/clips), extended to build real `Episode` objects
and to capture playlist membership, which the earlier script did not.

`yt-dlp` is a real external dependency, exactly like VLC is for `ui/player.py`
— `available()` reports its absence rather than letting a fetch fail
half-explained.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .sampler import Episode

DEFAULT_MIN_DURATION = 120   # seconds — excludes Shorts and clips


def _ytdlp_path() -> str | None:
    """The yt-dlp executable, even when it isn't on PATH. None if not found."""
    exe = shutil.which("yt-dlp")
    if exe:
        return exe
    candidates = [
        Path(os.path.expandvars(r"%APPDATA%\Python\Python313\Scripts\yt-dlp.exe")),
        Path(sys.executable).parent / "yt-dlp.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def available() -> tuple[bool, str]:
    """(usable, explanation). Never raises — the caller shows the reason."""
    if _ytdlp_path() is None:
        return False, ("yt-dlp is not installed. Install it with "
                       "`pip install yt-dlp`.")
    return True, ""


def channel_slug(url: str) -> str:
    """A short, filesystem-safe identifier for a channel URL. 'youtube' if
    the URL doesn't name one (e.g. a bare playlist link)."""
    m = re.search(r"@([\w\-]+)", url)
    if m:
        return m.group(1).lower()
    m = re.search(r"/c/([\w\-]+)", url)
    if m:
        return m.group(1).lower()
    m = re.search(r"/channel/([\w\-]+)", url)
    if m:
        return m.group(1).lower()
    return "youtube"


_PRINT_FIELDS = (
    "%(upload_date)s", "%(id)s", "%(duration)s", "%(channel)s",
    "%(playlist)s", "%(playlist_id)s", "%(webpage_url)s", "%(title)s",
)


def _clean(value: str) -> str:
    """yt-dlp prints 'NA' for a template field that doesn't apply."""
    value = value.strip()
    return "" if value in ("", "NA") else value


def fetch_videos(urls: list[str],
                  min_duration: int = DEFAULT_MIN_DURATION) -> list[Episode]:
    """Metadata for one or more channel/playlist URLs, no download.

    Each Episode: filepath=None, title, air_date (YYYY-MM-DD, from the
    upload date), extra={"url", "video_id", "channel"?, "playlist"?}.
    season/episode are left None — nothing here has a season; the caller
    numbers them via the same sequential fallback scan_entry_root() uses.

    A video appearing in more than one sampled URL (e.g. present in two
    playlists sampled together) is kept once, first-seen — this is a single
    sampling frame, not one row per (video, playlist) pair.
    """
    ytdlp = _ytdlp_path()
    if ytdlp is None:
        raise RuntimeError(
            "yt-dlp not found. Install it with `pip install yt-dlp`.")

    seen_ids: set[str] = set()
    episodes: list[Episode] = []
    for url in urls:
        url = url.strip()
        if not url:
            continue
        cmd = [
            ytdlp, "--flat-playlist",
            "--print", "\t".join(_PRINT_FIELDS),
            "--no-warnings",
            "--extractor-args", "youtube:skip=dash,hls",
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
        if result.returncode != 0 and not result.stdout.strip():
            raise RuntimeError(
                f"yt-dlp could not read {url}:\n{result.stderr[:800]}")

        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) < 8:
                continue
            date_str, vid_id, dur_str, channel, playlist, _playlist_id, \
                webpage_url, title_rest = parts[0], parts[1], parts[2], \
                parts[3], parts[4], parts[5], parts[6], parts[7:]
            title = _clean("\t".join(title_rest))
            vid_id = _clean(vid_id)
            if not vid_id or vid_id in seen_ids:
                continue

            try:
                upload_date = datetime.strptime(
                    _clean(date_str), "%Y%m%d").date()
            except ValueError:
                continue   # no date at all — cannot place it on a timeline

            try:
                duration = int(float(_clean(dur_str) or "nan"))
            except ValueError:
                duration = None
            if duration is not None and duration < min_duration:
                continue

            extra: dict[str, str] = {
                "url": _clean(webpage_url) or
                       f"https://www.youtube.com/watch?v={vid_id}",
                "video_id": vid_id,
            }
            channel = _clean(channel)
            if channel:
                extra["channel"] = channel
            playlist = _clean(playlist)
            if playlist:
                extra["playlist"] = playlist

            seen_ids.add(vid_id)
            episodes.append(Episode(
                entry_id=channel or "youtube",
                season=None,
                episode=None,
                title=title or None,
                air_date=upload_date.isoformat(),
                runtime=float(duration) if duration is not None else None,
                filepath=None,
                extra=extra,
            ))

    episodes.sort(key=lambda e: e.air_date or "")
    for i, ep in enumerate(episodes, 1):
        ep.episode = i   # a stable, arbitrary ordinal — matches a folder
                         # scan's sequential fallback for episodes with no
                         # natural number, so sort_key()/label() behave the
                         # same regardless of source
    return episodes
