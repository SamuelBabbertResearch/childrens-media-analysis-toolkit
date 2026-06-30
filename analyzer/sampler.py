"""
analyzer/sampler.py — Episode sampling engine for CMAT.

Two orthogonal axes compose into a full sampling design:
  Axis A (stratification): none | by_season | by_column
  Axis B (method): census | srs | systematic | spread | manual

A researcher's full design is one sentence:
  "Stratified by season, spread within stratum, n=2, seed=20260629."
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Any

import pandas as pd

__version__ = "1.0.0"

# ---------------------------------------------------------------------------
# Regex defaults
# ---------------------------------------------------------------------------

_DEFAULT_SEASON_REGEX = r"(?i)(?:season\s*|s)(\d+)"
_DEFAULT_EPISODE_REGEX = r"(?i)s(\d+)e(\d+)"
_DEFAULT_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".m4v"}

# ---------------------------------------------------------------------------
# Tooltip strings (authoritative source — imported by GUI and docs)
# ---------------------------------------------------------------------------

TOOLTIPS: dict[str, str] = {
    "entry_root": (
        "Pick the show's top folder. Each season subfolder is read as a group "
        "and each video inside as one episode. One folder = one show-era — "
        "keep reboots and eras in separate folders."
    ),
    "load_registry": (
        "Advanced: load a prepared episode list instead of scanning folders. "
        "Use this if your files aren't in season folders."
    ),
    "season_regex": (
        "How season numbers are read from folder names. Default reads "
        '"Season 01", "Season 1", "S01". Change only if your folders are named differently.'
    ),
    "episode_regex": (
        "How episode numbers are read from file names. Default reads names like "
        '"S01E12". Change only if your files are named differently.'
    ),
    "video_extensions": (
        "Which file types count as episodes. Other files (subtitles, thumbnails) are ignored."
    ),
    "stratify_none": (
        "Sample from the whole show at once, ignoring seasons. Simplest, but "
        "may miss changes that happen across a show's run."
    ),
    "stratify_season": (
        "Sample separately from each season so every season is represented. "
        "Best for catching animation or pacing changes over time. Recommended."
    ),
    "stratify_column": (
        "Group by a custom label instead of season. Use if you've tagged "
        "episodes by production era or format."
    ),
    "method_census": (
        "Use every episode in the group. Best for short shows or when you want the complete picture."
    ),
    "method_srs": (
        "Pick episodes purely at random. The most bias-free choice, but a "
        "small sample can miss whole stretches of a run by chance."
    ),
    "method_systematic": (
        "Take every Nth episode from a random start. Even coverage with little "
        "setup — but can land on a repeating pattern (e.g. every finale), so "
        "avoid it for shows with regular special episodes."
    ),
    "method_spread": (
        "Divide the run into equal chunks and pick one episode at random from "
        "each. Even coverage, but the randomness avoids locking onto repeating "
        "patterns. Recommended default."
    ),
    "method_manual": (
        "Hand-pick specific episodes. Use for case studies. Note: this is not "
        "a representative sample and is flagged as such in the results."
    ),
    "allocation_equal": (
        "Take the same number of episodes from every season. Each season "
        "equally represented; total grows with the number of seasons."
    ),
    "allocation_proportional": (
        "Spread a fixed total across seasons by their length, with at least one "
        "from each. Use when you want a set total sample size."
    ),
    "per_stratum_n": "How many episodes to take from each season.",
    "total_n": "How many episodes to take across the whole show.",
    "floor": "Every season gets at least this many, even short ones, so no era is left out.",
    "sort_col": (
        'Which order defines the timeline within a group. "Episode" uses '
        "numbering order; \"air date\" uses when episodes aired. They can differ "
        "— pick the one matching the changes you're studying."
    ),
    "seed": (
        "A number that fixes the random draw so you or a reviewer can reproduce "
        "the exact same sample. Change it for a different sample; keep it to repeat one."
    ),
    "gather_files": (
        "Off by default — the tool just lists the chosen files. Turn on to "
        "collect them into a sample folder (links by default; full copies only "
        "if you also check \"copy\")."
    ),
    "preview": "Show which episodes would be selected without writing anything yet.",
    "interval_k": (
        "Take every Nth episode. Leave blank to derive N automatically from "
        "the target sample size."
    ),
    "manual_list": (
        "Enter the episode identifiers to include (one per line, season×episode "
        'or title). Must match values in the "episode" or "title" column.'
    ),
}

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Episode:
    entry_id: str
    season: int | None
    episode: int | None
    title: str | None
    air_date: str | None
    runtime: float | None
    filepath: Path | None
    extra: dict = field(default_factory=dict)

    def sort_key(self, col: str = "episode") -> tuple:
        if col == "air_date" and self.air_date:
            return (self.season or 0, self.air_date)
        return (self.season or 0, self.episode or 0)

    def label(self) -> str:
        parts = []
        if self.season is not None:
            parts.append(f"S{self.season:02d}")
        if self.episode is not None:
            parts.append(f"E{self.episode:02d}")
        if self.title:
            parts.append(self.title)
        if not parts and self.filepath:
            return self.filepath.name
        return "".join(parts) if parts else "(unknown)"


@dataclass
class StratumRecord:
    stratum_key: str
    available: int
    allocated: int
    selected: int
    census_flag: bool
    episodes: list[str]  # labels of chosen episodes


@dataclass
class SampleManifest:
    entry_id: str
    generated_at_utc: str
    software_version: str
    method: str
    allocation: str | None
    stratify_by: str | None
    params: dict
    seed: int | None
    probability: bool
    frame_definition: dict
    strata: list[StratumRecord]
    total_available: int
    total_selected: int
    notes: list[str]

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "generated_at_utc": self.generated_at_utc,
            "software_version": self.software_version,
            "method": self.method,
            "allocation": self.allocation,
            "stratify_by": self.stratify_by,
            "params": self.params,
            "seed": self.seed,
            "probability": self.probability,
            "frame_definition": self.frame_definition,
            "strata": [
                {
                    "stratum_key": s.stratum_key,
                    "available": s.available,
                    "allocated": s.allocated,
                    "selected": s.selected,
                    "census_flag": s.census_flag,
                    "episodes": s.episodes,
                }
                for s in self.strata
            ],
            "total_available": self.total_available,
            "total_selected": self.total_selected,
            "notes": self.notes,
        }


@dataclass
class SampleResult:
    selected: list[Episode]
    manifest: SampleManifest
    worklist: list[Path]


# ---------------------------------------------------------------------------
# Directory scan
# ---------------------------------------------------------------------------

def scan_entry_root(
    root: Path,
    entry_id: str | None = None,
    season_regex: str = _DEFAULT_SEASON_REGEX,
    episode_regex: str = _DEFAULT_EPISODE_REGEX,
    video_extensions: set[str] | None = None,
) -> list[Episode]:
    """Scan a folder tree and return one Episode per video file found."""
    if video_extensions is None:
        video_extensions = _DEFAULT_VIDEO_EXTENSIONS
    eid = entry_id or root.name
    episodes: list[Episode] = []
    notes_log: list[str] = []

    season_re = re.compile(season_regex)
    episode_re = re.compile(episode_regex)

    def _parse_episode(path: Path, season_num: int | None) -> Episode:
        m = episode_re.search(path.stem)
        if m:
            ep_num = int(m.group(2)) if m.lastindex and m.lastindex >= 2 else int(m.group(1))
        else:
            ep_num = None
        return Episode(
            entry_id=eid,
            season=season_num,
            episode=ep_num,
            title=None,
            air_date=None,
            runtime=None,
            filepath=path,
        )

    # Check if there are season subfolders
    season_dirs = []
    flat_videos = []
    for item in sorted(root.iterdir()):
        if item.is_dir():
            m = season_re.search(item.name)
            if m:
                season_dirs.append((int(m.group(1)), item))
            else:
                notes_log.append(
                    f"Skipped folder '{item.name}' — season number not parseable."
                )
        elif item.is_file() and item.suffix.lower() in video_extensions:
            flat_videos.append(item)

    if season_dirs:
        for season_num, sdir in sorted(season_dirs):
            vids = sorted(
                f for f in sdir.iterdir()
                if f.is_file() and f.suffix.lower() in video_extensions
            )
            if not vids:
                notes_log.append(f"Season {season_num} folder '{sdir.name}' is empty — skipped.")
                continue
            for v in vids:
                episodes.append(_parse_episode(v, season_num))
    else:
        # Flat layout — assign season=None, parse season from filename if present
        for v in sorted(flat_videos):
            sm = season_re.search(v.stem)
            season_num = int(sm.group(1)) if sm else None
            episodes.append(_parse_episode(v, season_num))

    # Assign sequential index for episodes whose number didn't parse
    by_season: dict[int | None, list[Episode]] = {}
    for ep in episodes:
        by_season.setdefault(ep.season, []).append(ep)
    for grp in by_season.values():
        unparsed = [e for e in grp if e.episode is None]
        if unparsed:
            notes_log.append(
                f"Season {grp[0].season}: {len(unparsed)} episode(s) had unparseable "
                "filenames — assigned sequential indices."
            )
            for i, e in enumerate(unparsed, 1):
                e.episode = i

    return episodes


# ---------------------------------------------------------------------------
# Registry CSV loader
# ---------------------------------------------------------------------------

def load_registry_csv(path: Path, entry_id: str | None = None) -> list[Episode]:
    df = pd.read_csv(path)
    required = {"episode"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Registry CSV missing required columns: {missing}")

    eid = entry_id or df["entry_id"].iloc[0] if "entry_id" in df.columns else path.stem
    episodes: list[Episode] = []
    for _, row in df.iterrows():
        fp = Path(row["filepath"]) if "filepath" in df.columns and pd.notna(row.get("filepath")) else None
        episodes.append(Episode(
            entry_id=str(row.get("entry_id", eid)),
            season=int(row["season"]) if "season" in df.columns and pd.notna(row.get("season")) else None,
            episode=int(row["episode"]) if pd.notna(row["episode"]) else None,
            title=str(row["title"]) if "title" in df.columns and pd.notna(row.get("title")) else None,
            air_date=str(row["air_date"]) if "air_date" in df.columns and pd.notna(row.get("air_date")) else None,
            runtime=float(row["runtime"]) if "runtime" in df.columns and pd.notna(row.get("runtime")) else None,
            filepath=fp,
        ))
    return episodes


# ---------------------------------------------------------------------------
# Reproducibility: per-stratum seeding
# ---------------------------------------------------------------------------

def _stratum_seed(base_seed: int, entry_id: str, stratum_key: str) -> int:
    """Derive a deterministic per-stratum seed from (base, entry, stratum).

    Adding a new stratum later does not disturb seeds of existing strata.
    """
    raw = f"{base_seed}:{entry_id}:{stratum_key}".encode()
    digest = hashlib.sha256(raw).digest()
    return int.from_bytes(digest[:8], "little")


# ---------------------------------------------------------------------------
# Axis B: selection methods (operate on a plain list of Episodes)
# ---------------------------------------------------------------------------

def _census(frame: list[Episode]) -> tuple[list[Episode], bool]:
    return list(frame), True


def _srs(frame: list[Episode], n: int, rng: Random) -> list[Episode]:
    k = min(n, len(frame))
    return rng.sample(frame, k)


def _systematic(
    frame: list[Episode], k: int | None, n: int | None, rng: Random
) -> tuple[list[Episode], list[str]]:
    N = len(frame)
    warnings: list[str] = []
    if k is None:
        if n is None:
            raise ValueError("systematic requires either interval_k or n")
        k = max(1, N // n)
    if k <= 2:
        warnings.append(
            f"Systematic interval k={k} is very small — high aliasing risk if the show "
            "has repeating episode types. Consider using spread instead."
        )
    start = rng.randint(0, k - 1)
    selected = frame[start::k]
    return selected, warnings


def _spread(frame: list[Episode], n: int, rng: Random) -> list[Episode]:
    N = len(frame)
    n = min(n, N)
    chunk_size = N / n
    selected: list[Episode] = []
    for i in range(n):
        lo = int(i * chunk_size)
        hi = int((i + 1) * chunk_size)
        hi = max(hi, lo + 1)
        selected.append(rng.choice(frame[lo:hi]))
    return selected


def _manual(frame: list[Episode], episode_list: list[str]) -> tuple[list[Episode], list[str]]:
    """Select episodes by matching label(), title, or episode number string."""
    lookup: dict[str, Episode] = {}
    for ep in frame:
        lookup[ep.label()] = ep
        if ep.title:
            lookup[ep.title.strip()] = ep
        if ep.episode is not None:
            lookup[str(ep.episode)] = ep

    chosen: list[Episode] = []
    warnings: list[str] = []
    for item in episode_list:
        item = item.strip()
        if not item:
            continue
        if item in lookup:
            chosen.append(lookup[item])
        else:
            warnings.append(f"Manual list: '{item}' not found in frame.")
    return chosen, warnings


# ---------------------------------------------------------------------------
# Axis A: allocation helpers
# ---------------------------------------------------------------------------

def _equal_allocation(strata_keys: list[str], per_n: int) -> dict[str, int]:
    return {k: per_n for k in strata_keys}


def _proportional_allocation(
    stratum_sizes: dict[str, int],
    total_n: int,
    floor: int,
) -> tuple[dict[str, int], list[str]]:
    """D'Hondt / highest-averages with a per-stratum floor and capacity cap."""
    notes: list[str] = []
    alloc = {k: floor for k in stratum_sizes}
    remaining = total_n - floor * len(stratum_sizes)

    if remaining < 0:
        notes.append(
            f"Floors ({floor} × {len(stratum_sizes)} strata = {floor * len(stratum_sizes)}) "
            f"exceed total_n={total_n}. Floors win — every stratum gets {floor}."
        )
        return alloc, notes

    # D'Hondt: highest quotient gets the next seat
    quotients = {k: stratum_sizes[k] / (alloc[k] + 1) for k in stratum_sizes}
    for _ in range(remaining):
        eligible = {k: q for k, q in quotients.items() if alloc[k] < stratum_sizes[k]}
        if not eligible:
            notes.append("Total_n exceeds total available episodes — censusing everything.")
            break
        winner = max(eligible, key=lambda k: eligible[k])
        alloc[winner] += 1
        quotients[winner] = stratum_sizes[winner] / (alloc[winner] + 1)

    return alloc, notes


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def sample(
    episodes: list[Episode],
    entry_id: str = "",
    stratify_by: str | None = "season",
    method: str = "spread",
    allocation: str = "equal",
    per_stratum_n: int = 2,
    total_n: int | None = None,
    floor: int = 1,
    interval_k: int | None = None,
    sort_col: str = "episode",
    seed: int = 42,
    manual_list: list[str] | None = None,
) -> SampleResult:
    """
    Core sampling function. Compose Axis A (stratification) with Axis B (method).

    Parameters
    ----------
    episodes      : flat list from scan_entry_root() or load_registry_csv()
    stratify_by   : None | "season" | any column name present in Episode.extra
    method        : "census" | "srs" | "systematic" | "spread" | "manual"
    allocation    : "equal" | "proportional"  (ignored when stratify_by is None)
    per_stratum_n : quota per stratum for equal allocation
    total_n       : total quota for proportional allocation
    floor         : minimum per stratum for proportional allocation
    interval_k    : explicit interval for systematic (derives from per_stratum_n if None)
    sort_col      : "episode" | "air_date"
    seed          : base RNG seed (per-stratum seeds are derived from this)
    manual_list   : explicit episode identifiers (method="manual" only)
    """
    if not episodes:
        raise ValueError("No episodes to sample from.")

    eid = entry_id or (episodes[0].entry_id if episodes else "entry")
    notes: list[str] = []
    all_strata: list[StratumRecord] = []
    selected_all: list[Episode] = []
    probability = method != "manual"

    # Sort episodes within each partition
    episodes = sorted(episodes, key=lambda e: e.sort_key(sort_col))

    # --- Build strata ---
    if stratify_by is None:
        partitions: dict[str, list[Episode]] = {"(all)": episodes}
    elif stratify_by == "season":
        partitions = {}
        no_season = []
        for ep in episodes:
            if ep.season is not None:
                partitions.setdefault(str(ep.season), []).append(ep)
            else:
                no_season.append(ep)
        if no_season:
            notes.append(
                f"{len(no_season)} episode(s) have no season — placed in stratum '(none)'."
            )
            partitions["(none)"] = no_season
    else:
        partitions = {}
        for ep in episodes:
            key = str(ep.extra.get(stratify_by, "(none)"))
            partitions.setdefault(key, []).append(ep)

    # --- Compute allocation per stratum ---
    if stratify_by is None or allocation == "equal":
        alloc_map = _equal_allocation(list(partitions.keys()), per_stratum_n)
    else:
        sizes = {k: len(v) for k, v in partitions.items()}
        tn = total_n if total_n is not None else per_stratum_n * len(partitions)
        alloc_map, alloc_notes = _proportional_allocation(sizes, tn, floor)
        notes.extend(alloc_notes)

    # --- Apply Axis B within each stratum ---
    for stratum_key, frame in sorted(partitions.items()):
        n_want = alloc_map.get(stratum_key, per_stratum_n)
        rng = Random(_stratum_seed(seed, eid, stratum_key))
        census_flag = False
        stratum_warnings: list[str] = []

        if method == "census" or n_want >= len(frame):
            if method != "census" and n_want >= len(frame):
                notes.append(
                    f"Stratum '{stratum_key}': requested {n_want} but only "
                    f"{len(frame)} available — censusing."
                )
            chosen, census_flag = _census(frame)
        elif method == "srs":
            chosen = _srs(frame, n_want, rng)
        elif method == "systematic":
            chosen, stratum_warnings = _systematic(frame, interval_k, n_want, rng)
        elif method == "spread":
            chosen = _spread(frame, n_want, rng)
        elif method == "manual":
            if manual_list is None:
                raise ValueError("method='manual' requires manual_list")
            chosen, stratum_warnings = _manual(frame, manual_list)
        else:
            raise ValueError(f"Unknown method: {method!r}")

        notes.extend(
            f"Stratum '{stratum_key}': {w}" for w in stratum_warnings
        )

        chosen_sorted = sorted(chosen, key=lambda e: e.sort_key(sort_col))
        selected_all.extend(chosen_sorted)

        all_strata.append(StratumRecord(
            stratum_key=stratum_key,
            available=len(frame),
            allocated=n_want,
            selected=len(chosen),
            census_flag=census_flag,
            episodes=[e.label() for e in chosen_sorted],
        ))

    worklist = [ep.filepath for ep in selected_all if ep.filepath is not None]

    manifest = SampleManifest(
        entry_id=eid,
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        software_version=__version__,
        method=method,
        allocation=allocation if stratify_by is not None else None,
        stratify_by=stratify_by,
        params={
            "per_stratum_n": per_stratum_n,
            "total_n": total_n,
            "floor": floor,
            "interval_k": interval_k,
            "sort_col": sort_col,
        },
        seed=seed if probability else None,
        probability=probability,
        frame_definition={"sort_col": sort_col, "total_available": len(episodes)},
        strata=all_strata,
        total_available=len(episodes),
        total_selected=len(selected_all),
        notes=notes,
    )

    return SampleResult(selected=selected_all, manifest=manifest, worklist=worklist)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def write_outputs(
    result: SampleResult,
    output_dir: Path,
    gather: bool = False,
    copy_files: bool = False,
) -> dict[str, Path]:
    """Write selected.csv, manifest.json, worklist.txt to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # selected.csv
    rows = []
    for ep in result.selected:
        rows.append({
            "entry_id": ep.entry_id,
            "season": ep.season,
            "episode": ep.episode,
            "title": ep.title or "",
            "air_date": ep.air_date or "",
            "filepath": str(ep.filepath) if ep.filepath else "",
        })
    csv_path = output_dir / "selected.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    # manifest.json
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(result.manifest.to_dict(), indent=2), encoding="utf-8"
    )

    # worklist.txt
    worklist_path = output_dir / "worklist.txt"
    worklist_path.write_text(
        "\n".join(str(p) for p in result.worklist), encoding="utf-8"
    )

    out = {"csv": csv_path, "manifest": manifest_path, "worklist": worklist_path}

    if gather and result.worklist:
        import shutil
        gather_dir = output_dir / "files"
        gather_dir.mkdir(exist_ok=True)
        for src in result.worklist:
            dest = gather_dir / src.name
            if copy_files:
                shutil.copy2(src, dest)
            else:
                try:
                    dest.symlink_to(src)
                except OSError:
                    shutil.copy2(src, dest)
        out["files"] = gather_dir

    return out
