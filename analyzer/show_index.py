"""Discovers shows (folders) and episodes (video files) under a root directory.

Supports one level of category folders:
  Root/
    ShowName/          ← flat show (videos directly inside)
      ep.mp4
    CategoryName/      ← category (no direct videos, but contains show sub-dirs)
      ShowName/
        ep.mp4

WHAT COUNTS AS AN EPISODE
-------------------------
`VIDEO_EXTENSIONS` is the single answer, and `analyzer/sampler.py` imports it
rather than keeping its own. It used to keep its own: the sampler drew six
extensions while this module globbed `*.mp4` in four separate places, so a
documented sample could contain episodes the library never listed. Found
2026-08-15 with one `.mkv` live in a drawn sample and invisible in the Library
— it had been measured and indexed through the sampler's own path, which does
not go through here.

Widening this set makes more files count as episodes. It does not invalidate
anything: the cache is keyed on show folder plus filename stem, so existing
results keep their keys and only the "n of m analyzed" denominators move.
"""

from __future__ import annotations
import os
import re
from functools import lru_cache
from pathlib import Path

# Every container the tool treats as an episode. One definition, because four
# copies of `glob("*.mp4")` is how this drifted from the sampler in the first
# place — `LEARNINGS.md` § *The same one-line mistake, in four places*.
VIDEO_EXTENSIONS = frozenset(
    {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".m4v"})


@lru_cache(maxsize=4096)
def _scan_directory(path: str, mtime_ns: int, ctime_ns: int
                    ) -> tuple[tuple[str, bool, bool], ...]:
    """One directory revision as ``(name, is_dir, is_file)`` records."""
    del mtime_ns, ctime_ns             # revision fields belong in cache key
    try:
        with os.scandir(path) as entries:
            return tuple((entry.name, entry.is_dir(), entry.is_file())
                         for entry in entries)
    except OSError:
        return ()


def _entries(directory: Path) -> tuple[tuple[str, bool, bool], ...]:
    """Read a directory once until its on-disk revision changes."""
    try:
        stat = directory.stat()
    except OSError:
        return ()
    return _scan_directory(str(directory), stat.st_mtime_ns, stat.st_ctime_ns)


def list_videos(directory: Path) -> list[Path]:
    """Video files directly inside *directory*, sorted by name.

    Matches on the lowercased suffix rather than by globbing each extension:
    `glob` is case-sensitive on Linux, so `*.mp4` silently skips `EP.MP4`
    there while finding it on Windows — a library that lists differently
    depending on the platform it is opened on.
    """
    return sorted(directory / name for name, _is_dir, is_file in
                  _entries(directory)
                  if is_file and Path(name).suffix.lower() in VIDEO_EXTENSIONS)


def _has_video(d: Path) -> bool:
    """True if *d* directly contains at least one video file."""
    return any(is_file and Path(name).suffix.lower() in VIDEO_EXTENSIONS
               for name, _is_dir, is_file in _entries(d))

# Matches "Season 1", "S2", "Series 3", "Part 4" etc.
_SEASON_RE = re.compile(r"^(?:[Ss]eason|[Ss]eries|[Ss]|[Pp]art)\s*(\d+)$")


def parse_season_folder(name: str) -> int | None:
    """Return the season number if *name* looks like a season folder, else None."""
    m = _SEASON_RE.match(name.strip())
    return int(m.group(1)) if m else None


def display_show_name(root: Path, show_dir: Path) -> tuple[str, int | None]:
    """Return (show_name_for_db, auto_season_num) for a show directory.

    When show_dir is a season folder (Season 1, S2, …), the parent folder is
    used as the show name so all seasons appear under one show in the index.
    Returns (show_dir.name, None) for normal (non-season) folders.
    """
    season_num = parse_season_folder(show_dir.name)
    if season_num is not None:
        parent = show_dir.parent
        # parent == root when the user set root to the show folder itself
        return parent.name, season_num
    return show_dir.name, None


def db_show_key(root: Path, show_dir: Path) -> str:
    """Return the stable DB key for a show directory.

    Flat and categorized shows use the same relative key as the cache. Season
    folders are grouped under their parent show so all seasons share metadata,
    era definitions, and show-level index rows.
    """
    if parse_season_folder(show_dir.name) is not None:
        parent = show_dir.parent
        if parent == root:
            return parent.name
        return parent.relative_to(root).as_posix()
    return show_key(root, show_dir)


def _is_show(d: Path) -> bool:
    """True if d is a non-hidden directory that directly contains video files."""
    return d.is_dir() and not d.name.startswith(".") and _has_video(d)


def list_top_level(root: Path) -> list[tuple[str, Path]]:
    """Return top-level items as (kind, path) pairs, sorted by name.

    kind is 'show' for directories that contain video files directly,
    or 'category' for directories that contain show sub-directories.
    """
    result: list[tuple[str, Path]] = []
    for name, is_dir, _is_file in sorted(_entries(root)):
        if not is_dir or name.startswith("."):
            continue
        d = root / name
        if _has_video(d):
            result.append(("show", d))
        elif any(_is_show(d / sub_name)
                 for sub_name, sub_is_dir, _sub_is_file in _entries(d)
                 if sub_is_dir):
            result.append(("category", d))
    return result


def list_shows(root: Path) -> list[Path]:
    """Return all show directories under root (including those inside categories)."""
    shows: list[Path] = []
    for name, is_dir, _is_file in sorted(_entries(root)):
        if not is_dir or name.startswith("."):
            continue
        d = root / name
        if _has_video(d):
            shows.append(d)
        else:
            for sub_name, sub_is_dir, _sub_is_file in sorted(_entries(d)):
                if not sub_is_dir:
                    continue
                sub = d / sub_name
                if _is_show(sub):
                    shows.append(sub)
    return shows


def list_category_shows(cat_dir: Path) -> list[Path]:
    """Return show directories directly inside a category folder, sorted."""
    return sorted(cat_dir / name for name, is_dir, _is_file in
                  _entries(cat_dir) if is_dir and _is_show(cat_dir / name))


def show_key(root: Path, show_dir: Path) -> str:
    """Return the show's cache/DB identifier as a POSIX relative path from root.

    For flat shows: 'ShowName'
    For categorized shows: 'CategoryName/ShowName'
    """
    return show_dir.relative_to(root).as_posix()


def list_episodes(show_dir: Path) -> list[Path]:
    """Return the video files inside show_dir, sorted by name."""
    return list_videos(show_dir)
