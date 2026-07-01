#!/usr/bin/env python3
"""
sample_youtube.py — Generate a spread sample of YouTube videos by upload date.

Does NOT download any videos. Fetches metadata only (title, date, duration, URL)
and applies the same spread-sampling algorithm used by CMAT for TV shows.

Usage:
    python sample_youtube.py <channel_or_playlist_url>
    python sample_youtube.py https://www.youtube.com/@MrBeast/videos
    python sample_youtube.py https://www.youtube.com/@MrBeast/videos --n 20
    python sample_youtube.py https://www.youtube.com/@MrBeast/videos --min-duration 300

Options:
    --n N              Number of videos to sample (default: 10)
    --seed SEED        Random seed (default: 42)
    --min-duration S   Minimum duration in seconds to include (default: 120)
                       Filters out Shorts and clips.
    --output FILE      Output CSV (default: <channel>_sample.csv)

Requires yt-dlp:
    pip install yt-dlp
"""

from __future__ import annotations
import argparse
import csv
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from random import Random


# ── Spread sampler (identical algorithm to analyzer/sampler.py) ──────────────

def _spread(items: list, n: int, seed: int) -> list:
    N = len(items)
    n = min(n, N)
    chunk = N / n
    rng   = Random(seed)
    return [rng.choice(items[int(i * chunk): max(int((i + 1) * chunk), int(i * chunk) + 1)])
            for i in range(n)]


# ── yt-dlp fetch ─────────────────────────────────────────────────────────────

def _ytdlp_path() -> str:
    """Find yt-dlp even when it isn't on PATH."""
    import shutil, os
    exe = shutil.which("yt-dlp")
    if exe:
        return exe
    # Common pip --user install location on Windows
    scripts = Path(os.path.expandvars(r"%APPDATA%\Python\Python313\Scripts\yt-dlp.exe"))
    if scripts.exists():
        return str(scripts)
    scripts2 = Path(sys.executable).parent / "yt-dlp.exe"
    if scripts2.exists():
        return str(scripts2)
    sys.exit(
        "yt-dlp not found. Install it with:  pip install yt-dlp\n"
        "Then either add its Scripts folder to PATH or re-run this script."
    )


def fetch_videos(url: str, min_duration: int = 120) -> list[dict]:
    ytdlp = _ytdlp_path()
    print(f"Fetching video list from:\n  {url}")
    print("(This may take 30–60 s for large channels — metadata only, no downloads)\n")

    cmd = [
        ytdlp,
        "--flat-playlist",
        "--print", "%(upload_date)s\t%(id)s\t%(title)s\t%(duration)s",
        "--no-warnings",
        "--extractor-args", "youtube:skip=dash,hls",
        url,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0 and not result.stdout.strip():
        print(f"yt-dlp error:\n{result.stderr[:800]}")
        sys.exit(1)

    videos: list[dict] = []
    skipped_short = 0
    skipped_nodate = 0

    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        date_str, vid_id, title, dur_str = parts[0], parts[1], "\t".join(parts[2:-1]) or parts[2], parts[-1]

        try:
            upload_date = datetime.strptime(date_str.strip(), "%Y%m%d").date()
        except (ValueError, TypeError):
            skipped_nodate += 1
            continue

        try:
            duration = int(float(dur_str))
        except (ValueError, TypeError):
            duration = None

        if duration is not None and duration < min_duration:
            skipped_short += 1
            continue

        videos.append({
            "id":          vid_id,
            "title":       title.strip(),
            "upload_date": upload_date,
            "duration":    duration,
            "url":         f"https://www.youtube.com/watch?v={vid_id}",
        })

    if skipped_short:
        print(f"  Skipped {skipped_short} video(s) under {min_duration}s (Shorts / clips)")
    if skipped_nodate:
        print(f"  Skipped {skipped_nodate} video(s) with no upload date")
    return videos


# ── Formatting ────────────────────────────────────────────────────────────────

def _fmt_dur(seconds: int | None) -> str:
    if seconds is None:
        return "—"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _channel_slug(url: str) -> str:
    import re
    m = re.search(r"@([\w\-]+)", url)
    if m:
        return m.group(1).lower()
    m = re.search(r"/c/([\w\-]+)", url)
    if m:
        return m.group(1).lower()
    return "youtube"


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="YouTube spread sampler (metadata only)")
    ap.add_argument("url",           help="YouTube channel /videos URL or playlist URL")
    ap.add_argument("--n",           type=int, default=10,  help="Sample size (default 10)")
    ap.add_argument("--seed",        type=int, default=42,  help="RNG seed (default 42)")
    ap.add_argument("--min-duration",type=int, default=120, help="Min duration seconds (default 120)")
    ap.add_argument("--output",      default="",            help="Output CSV filename")
    args = ap.parse_args()

    videos = fetch_videos(args.url, min_duration=args.min_duration)

    if not videos:
        print("No qualifying videos found. Try --min-duration 0.")
        sys.exit(1)

    # Sort oldest → newest
    videos.sort(key=lambda v: v["upload_date"])

    year_range = f"{videos[0]['upload_date'].year}–{videos[-1]['upload_date'].year}"
    print(f"Total qualifying videos: {len(videos)}  ({year_range})\n")

    sample = _spread(videos, args.n, args.seed)
    sample.sort(key=lambda v: v["upload_date"])

    # ── Print results ──
    print(f"Spread sample  (n={args.n}, seed={args.seed}, min_duration={args.min_duration}s)\n")
    print(f"  {'#':<3}  {'Date':<12}  {'Dur':<8}  Title")
    print("  " + "─" * 72)
    for i, v in enumerate(sample, 1):
        title = v["title"]
        if len(title) > 52:
            title = title[:51] + "…"
        print(f"  {i:<3}  {v['upload_date']!s:<12}  {_fmt_dur(v['duration']):<8}  {title}")

    print()
    print("Download URLs:")
    for v in sample:
        print(f"  {v['url']}")

    # ── Write sample CSV ──
    slug    = _channel_slug(args.url)
    out_csv = Path(args.output) if args.output else Path(f"{slug}_sample_n{args.n}.csv")
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["index", "title", "url", "upload_date", "duration_fmt", "duration_sec"])
        for i, v in enumerate(sample, 1):
            w.writerow([i, v["title"], v["url"], v["upload_date"],
                        _fmt_dur(v["duration"]), v["duration"] or ""])
    print(f"\nSample saved to: {out_csv}")

    # ── Write full list (with selected flag) ──
    full_csv = out_csv.with_name(out_csv.stem.replace("_sample", "_full") + ".csv")
    sample_ids = {v["id"] for v in sample}
    with full_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["selected", "title", "url", "upload_date", "duration_fmt", "duration_sec"])
        for v in videos:
            w.writerow([
                "YES" if v["id"] in sample_ids else "",
                v["title"], v["url"], v["upload_date"],
                _fmt_dur(v["duration"]), v["duration"] or "",
            ])
    print(f"Full list saved to: {full_csv}")
    print(f"\nSampling protocol: spread, seed={args.seed}, "
          f"n={args.n}, min_duration={args.min_duration}s")


if __name__ == "__main__":
    main()
