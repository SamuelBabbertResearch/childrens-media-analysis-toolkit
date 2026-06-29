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
from pathlib import Path


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
