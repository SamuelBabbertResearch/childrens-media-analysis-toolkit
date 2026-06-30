"""Discovers shows (folders) and episodes (MP4 files) under a root directory.

Supports one level of category folders:
  Root/
    ShowName/          ← flat show (MP4s directly inside)
      ep.mp4
    CategoryName/      ← category (no direct MP4s, but contains show sub-dirs)
      ShowName/
        ep.mp4
"""

from __future__ import annotations
import re
from pathlib import Path

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


def _is_show(d: Path) -> bool:
    """True if d is a non-hidden directory that directly contains MP4 files."""
    return d.is_dir() and not d.name.startswith(".") and any(d.glob("*.mp4"))


def list_top_level(root: Path) -> list[tuple[str, Path]]:
    """Return top-level items as (kind, path) pairs, sorted by name.

    kind is 'show' for directories that contain MP4 files directly,
    or 'category' for directories that contain show sub-directories.
    """
    result: list[tuple[str, Path]] = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        if any(d.glob("*.mp4")):
            result.append(("show", d))
        elif any(_is_show(sub) for sub in d.iterdir() if sub.is_dir()):
            result.append(("category", d))
    return result


def list_shows(root: Path) -> list[Path]:
    """Return all show directories under root (including those inside categories)."""
    shows: list[Path] = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        if any(d.glob("*.mp4")):
            shows.append(d)
        else:
            for sub in sorted(d.iterdir()):
                if _is_show(sub):
                    shows.append(sub)
    return shows


def list_category_shows(cat_dir: Path) -> list[Path]:
    """Return show directories directly inside a category folder, sorted."""
    return sorted(sub for sub in cat_dir.iterdir() if _is_show(sub))


def show_key(root: Path, show_dir: Path) -> str:
    """Return the show's cache/DB identifier as a POSIX relative path from root.

    For flat shows: 'ShowName'
    For categorized shows: 'CategoryName/ShowName'
    """
    return show_dir.relative_to(root).as_posix()


def list_episodes(show_dir: Path) -> list[Path]:
    """Return MP4 files inside show_dir, sorted by name."""
    return sorted(show_dir.glob("*.mp4"))
