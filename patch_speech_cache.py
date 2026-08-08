#!/usr/bin/env python3
"""
patch_speech_cache.py — Back-fill speech metrics into cached episode JSONs.

For every episode that has a .srt or .vtt file alongside the video but whose
cached JSON has no speech data (or speech.available = False), this script reads
the subtitle file, computes the speech metrics, and writes them back into the
cache — without re-running any video analysis.

Usage:
    python patch_speech_cache.py
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT         = Path(__file__).parent
ANALYSIS_DIR = ROOT / ".analysis"

# Import the same CC parser the engine uses
from analyzer.speech import _find_cc_file, _parse_cc


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
        ep_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"  patched: {show_key} / {ep_stem}  "
              f"({speech.words_per_minute:.0f} wpm, source={speech.source})")
        patched += 1

    return patched


def main() -> None:
    if not ANALYSIS_DIR.exists():
        print(f"No .analysis/ directory found at {ROOT}")
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
