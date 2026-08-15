"""
Eras — named date ranges that group a show's run by production period.

WHY THIS MODULE EXISTS
----------------------
A long-running show is not one thing. Forty years of *Sesame Street* averaged
into a single row describes nothing that exists, which is why the published
corpus policy splits long runs into **eras** rather than averaging them whole
(`DECISIONS.md`, 2026-07-01). Stratifying a sample by era is how a study gets
comparable coverage of the 1980s and the 2000s instead of a draw dominated by
whichever period has more episodes on disk.

The era DEFINITIONS have lived in the index (`show_eras`) since July, and the
sampler has always accepted `stratify_by="<any column>"`. What did not exist
was the path between them: `Episode.extra` is never populated by
`scan_entry_root` or `load_registry_csv`, and a folder scan leaves `air_date`
as None. So "stratify by era" resolved every episode to the `(none)` stratum —
one group, which is the same as not stratifying at all.

This module is that missing path, in two steps:

    attach_air_dates()   index air dates  -> Episode.air_date
    assign_eras()        air date + eras  -> Episode.extra["era"]

after which `sample(..., stratify_by="era")` works like any other column.

Pure functions; no GUI imports, and the database handle is passed in rather
than opened here so the engine stays testable without one.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

# The key `Episode.extra` is tagged under, and therefore the value passed to
# `sample(stratify_by=...)`. Named once so the two cannot drift.
ERA_KEY = "era"

# Episodes with an air date outside every defined era, or with no air date at
# all. Kept as a real stratum rather than dropped: an episode that exists is
# part of the run whether or not someone has drawn a box around its year, and
# silently excluding it would shrink the sampling frame without saying so.
UNASSIGNED = "(no era)"

# Date spellings accepted from a person typing into the era editor, and from
# the metadata importers. ISO first because that is what everything stores.
DATE_FORMATS = (
    "%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%m-%d-%Y",
    "%d %B %Y", "%B %d, %Y", "%B %d %Y",
    "%d-%b-%Y", "%d %b %Y", "%b %d, %Y", "%b %d %Y",
    "%Y",
)


def normalise_date(raw: str | None) -> str:
    """A date in any accepted spelling as ISO `YYYY-MM-DD`, or "".

    Returns "" rather than raising: an unparseable date in one era row must
    not stop the other rows working, and the caller shows what it could not
    read.
    """
    if not raw:
        return ""
    text = str(raw).strip()
    if not text:
        return ""
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        # A bare year means the whole year, starting at its first day.
        return parsed.strftime("%Y-%m-%d")
    return ""


def era_for_date(air_date: str | None, eras: Iterable[dict]) -> str:
    """The name of the first era whose range contains *air_date*.

    Bounds are inclusive, and an empty bound is open — an era with no end
    date runs to the present, which is how "2010s–present" is expressed. The
    first match wins, so overlapping ranges resolve in the order the eras are
    stored (the index returns them by start date).
    """
    date = normalise_date(air_date)
    if not date:
        return UNASSIGNED
    for era in eras:
        name = (era.get("era_name") or "").strip()
        if not name:
            continue
        start = normalise_date(era.get("start_date"))
        end = normalise_date(era.get("end_date"))
        if start and date < start:
            continue
        if end and date > end:
            continue
        return name
    return UNASSIGNED


def attach_air_dates(episodes: list, conn: Any) -> int:
    """Fill `Episode.air_date` from the index. Returns how many were filled.

    A folder scan cannot know an air date — it is metadata a person imported
    or typed, and it lives in the index keyed by file path. Episodes already
    carrying an air date (from a registry CSV) are left alone.
    """
    if conn is None:
        return 0
    from .db import get_episode_metadata
    filled = 0
    for episode in episodes:
        if episode.air_date or not episode.filepath:
            continue
        try:
            meta = get_episode_metadata(conn, str(episode.filepath))
        except Exception:
            continue
        air_date = (meta or {}).get("air_date") or ""
        if air_date:
            episode.air_date = air_date
            filled += 1
    return filled


def assign_eras(episodes: list, eras: Iterable[dict],
                overwrite: bool = True) -> dict[str, int]:
    """Tag every episode with its era. Returns {era name: episode count}.

    Writes `Episode.extra[ERA_KEY]`, which is what `sample(stratify_by="era")`
    partitions on. The returned counts are what the interface shows before the
    draw: a stratum with one episode in it is a stratum the design cannot
    really sample from, and the researcher should see that first.

    *overwrite* False keeps an era the episode already carries. A registry CSV
    can name each episode's era outright, and that is data the researcher
    typed; deriving one from date ranges and writing over it turned eight
    correctly-labelled episodes into a single "(no era)" stratum. An explicit
    value beats a derived one.
    """
    era_list = list(eras)
    counts: dict[str, int] = {}
    for episode in episodes:
        if episode.extra is None:
            episode.extra = {}
        existing = str(episode.extra.get(ERA_KEY) or "").strip()
        if existing and not overwrite:
            name = existing
        else:
            name = era_for_date(episode.air_date, era_list)
            episode.extra[ERA_KEY] = name
        counts[name] = counts.get(name, 0) + 1
    return counts


def has_declared_eras(episodes: list) -> bool:
    """True when the episodes arrived already carrying an era of their own."""
    return any(str((e.extra or {}).get(ERA_KEY) or "").strip()
               and str((e.extra or {}).get(ERA_KEY)).strip() != UNASSIGNED
               for e in episodes)


def coverage_note(counts: dict[str, int]) -> str:
    """One line saying whether these strata can actually carry a sample."""
    if not counts:
        return "No episodes to group."
    unassigned = counts.get(UNASSIGNED, 0)
    named = {k: v for k, v in counts.items() if k != UNASSIGNED}
    parts = [f"{len(named)} era{'s' if len(named) != 1 else ''} with episodes"]
    thin = sorted(k for k, v in named.items() if v < 2)
    if thin:
        parts.append(
            f"{len(thin)} of them ha{'ve' if len(thin) != 1 else 's'} fewer "
            f"than 2 episodes ({', '.join(thin)}) — a stratum that small is "
            f"censused, not sampled")
    if unassigned:
        parts.append(
            f"{unassigned} episode{'s have' if unassigned != 1 else ' has'} "
            f"no air date in the index or no matching era, so "
            f"{'they are' if unassigned != 1 else 'it is'} grouped as "
            f"“{UNASSIGNED}”. Import metadata to place "
            f"{'them' if unassigned != 1 else 'it'}")
    return ".  ".join(parts) + "."
