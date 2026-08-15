#!/usr/bin/env python3
"""
patch_speech_cache.py — Back-fill speech metrics into cached episode JSONs.

For every episode that has a .srt or .vtt file alongside the video but whose
cached JSON has no speech data (or speech.available = False), this script reads
the subtitle file, computes the speech metrics, and writes them back into the
cache — without re-running any video analysis.

WHICH LIBRARY IT PATCHES
------------------------
The root is the folder that CONTAINS your show folders — the same one the
interface asks for — and the cache lives at `<root>/.analysis`. This script
used to assume the root was its own directory, which stopped being true once
the library moved into `Shows/`: it then patched a stale project-level cache
of 82 episodes while the application read a different one of 28, and reported
success either way.

It now defaults to the remembered root (`analyzer.prefs`), the same folder the
interface last opened, and prints which one it is before touching anything.

Usage:
    python patch_speech_cache.py                 # the remembered library root
    python patch_speech_cache.py <root>          # an explicit root
    python patch_speech_cache.py <root> --dry-run
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

# Import the same CC parser the engine uses
from analyzer.speech import _find_cc_file, _parse_cc

# Set by main() from the command line or the remembered root.
ROOT: Path = Path(".")
ANALYSIS_DIR: Path = Path(".analysis")
DRY_RUN: bool = False


def _patch_show(show_key: str, cache_dir: Path, show_dir: Path) -> int:
    patched = 0
    for ep_json in sorted(cache_dir.glob("*.json")):
        if ep_json.stem == "aggregate":
            continue
        try:
            data = json.loads(ep_json.read_text(encoding="utf-8"))
        except Exception:
            continue

        if data.get("status") != "ok":
            continue

        # Skip if speech data already present and available
        spe = data.get("metrics", {}).get("speech", {})
        if spe and spe.get("available"):
            continue

        # Find the video file matching this cache entry
        ep_stem = ep_json.stem
        video = None
        for ext in (".mp4", ".mkv", ".avi", ".mov"):
            # Try in the show dir and one level of season subfolders
            for candidate in [
                show_dir / f"{ep_stem}{ext}",
                *show_dir.rglob(f"{ep_stem}{ext}"),
            ]:
                if candidate.exists():
                    video = candidate
                    break
            if video:
                break

        if video is None:
            continue

        cc = _find_cc_file(video)
        if cc is None:
            continue

        duration_sec = data.get("duration_sec", 0.0)
        speech = _parse_cc(cc, duration_sec)
        if not speech.available:
            continue

        # Patch the cache
        data.setdefault("metrics", {})["speech"] = {
            "available":        True,
            "source":           speech.source,
            "words_per_minute": speech.words_per_minute,
            "speech_density":   speech.speech_density,
            "total_words":      speech.total_words,
        }
        if not DRY_RUN:
            ep_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"  {'would patch' if DRY_RUN else 'patched'}: "
              f"{show_key} / {ep_stem}  "
              f"({speech.words_per_minute:.0f} wpm, source={speech.source})")
        patched += 1

    return patched


def _resolve_root(argv: list[str]) -> tuple[Path, bool]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=None,
                        help="Folder containing your show folders. "
                             "Defaults to the one the interface last opened.")
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would change without writing.")
    args = parser.parse_args(argv)
    if args.root:
        return Path(args.root).resolve(), args.dry_run
    try:
        from analyzer.prefs import get_pref
        remembered = get_pref("last_root_folder")
    except Exception:
        remembered = None
    if not remembered:
        parser.error(
            "No root given and none remembered. Pass the folder that "
            "CONTAINS your show folders.")
    return Path(remembered).resolve(), args.dry_run


def main() -> None:
    global ROOT, ANALYSIS_DIR, DRY_RUN
    ROOT, DRY_RUN = _resolve_root(sys.argv[1:])
    ANALYSIS_DIR = ROOT / ".analysis"

    print(f"Library root : {ROOT}")
    print(f"Cache        : {ANALYSIS_DIR}")
    if DRY_RUN:
        print("DRY RUN — nothing will be written.")
    if not ANALYSIS_DIR.exists():
        print(f"No .analysis/ directory found under {ROOT}. "
              f"Is that the folder that contains your show folders?")
        return

    total = 0
    for entry in sorted(ANALYSIS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        # Flat show (e.g. .analysis/Little Bear/)
        json_files = list(entry.glob("*.json"))
        if any(f.stem != "aggregate" for f in json_files):
            show_dir = ROOT / "Shows" / entry.name
            if not show_dir.exists():
                show_dir = ROOT / entry.name
            n = _patch_show(entry.name, entry, show_dir)
            total += n
        else:
            # Category nesting (e.g. .analysis/Category/ShowName/)
            for sub in sorted(entry.iterdir()):
                if not sub.is_dir():
                    continue
                show_dir = ROOT / "Shows" / entry.name / sub.name
                if not show_dir.exists():
                    show_dir = ROOT / entry.name / sub.name
                n = _patch_show(f"{entry.name}/{sub.name}", sub, show_dir)
                total += n

    print(f"\nDone — {total} cache entries updated.")
    if total == 0:
        print("(Either all episodes already have speech data, "
              "or no SRT/VTT files were found alongside the videos.)")


if __name__ == "__main__":
    main()
