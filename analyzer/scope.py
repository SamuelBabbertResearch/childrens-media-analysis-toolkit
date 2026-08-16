"""
The current research context — which episodes the application is working on.

WHY THIS EXISTS
---------------
Every screen used to answer "which episodes?" for itself, from whatever the
Library tree happened to have selected. A sample could be drawn, documented and
manifested, and no screen was any the wiser: the Library still listed the whole
disk, and the researcher matched `selected.csv` against the tree by hand.

A Scope is the answer to that question, held in one place: either the whole
library, or the episodes one documented draw selected. `design/
CMAT_PIPELINE_INTERACTION_MODEL.md` calls this the research context and is
explicit that the Qt layer must not own it, so it lives here as plain data with
no GUI imports.

WHAT A SCOPE IS NOT
-------------------
It is a *view*, never a filter on the record. Narrowing the scope hides nothing
from disk, deletes nothing, and changes no cached result. Everything outside it
is one click away, and the scope always names itself on screen — a filter the
user cannot see is a filter they will forget.

PATHS
-----
`selected.csv` stores absolute paths written by the sampler; the library is
walked separately. Those are two spellings of one path, which is the shape of
`LEARNINGS.md` § *The sampler's CSV paths did not match the cache's keys*. So
every path entering a Scope is normalised here, at the choke point, and
membership is tested against the normalised form. Do not compare raw paths
against `Scope.episodes` — call `contains()`.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

LIBRARY_KEY = "library"
LIBRARY_LABEL = "Whole library"


def normalize(path: Path | str) -> Path:
    """One spelling of a path, for comparing across the two that exist."""
    try:
        return Path(path).expanduser().resolve()
    except (OSError, ValueError):
        return Path(path)


def read_selected(folder: Path | None) -> list[Path]:
    """Episode paths from a sampler draw's selected.csv, in drawn order.

    Returns [] for a folder with no selected.csv rather than raising: a
    manifest can exist beside a draw whose CSV was moved, and the caller shows
    that as an empty sample, which is the true state.
    """
    if not folder:
        return []
    csv_path = Path(folder) / "selected.csv"
    if not csv_path.exists():
        return []
    out: list[Path] = []
    try:
        with csv_path.open(newline="", encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                fp = (row.get("filepath") or "").strip()
                if fp and fp.lower() != "nan":
                    out.append(Path(fp))
    except Exception:
        return []
    return out


@dataclass(frozen=True)
class Scope:
    """Which episodes the application is currently working on.

    `episodes` and `missing` together are everything the draw selected:
    `episodes` are the ones present on disk now, `missing` the ones that are
    not. Both are reported, because a sample that has lost four of its files
    is a different situation from a sample of twenty, and silently showing
    twenty would misdescribe the study.
    """

    key: str
    label: str
    episodes: tuple[Path, ...] = ()
    missing: tuple[Path, ...] = ()
    folder: Path | None = None
    _index: frozenset = field(default_factory=frozenset, repr=False,
                              compare=False)

    def __post_init__(self) -> None:
        # Built once; contains() is called per library row and would otherwise
        # rebuild this set a few hundred times per refresh.
        object.__setattr__(self, "_index", frozenset(self.episodes))

    # -- identity ---------------------------------------------------------

    @property
    def is_library(self) -> bool:
        return self.key == LIBRARY_KEY

    @property
    def total_drawn(self) -> int:
        """Episodes the draw selected, present or not."""
        return len(self.episodes) + len(self.missing)

    # -- membership -------------------------------------------------------

    def contains(self, path: Path | str) -> bool:
        """Is this episode in scope? Always true for the whole library."""
        return True if self.is_library else normalize(path) in self._index

    # -- description ------------------------------------------------------

    def describe(self) -> str:
        """One line naming the scope and its size, for a header or a status bar."""
        if self.is_library:
            return LIBRARY_LABEL
        n = len(self.episodes)
        line = f"{self.label} — {n} episode{'' if n == 1 else 's'}"
        if self.missing:
            line += f", {len(self.missing)} missing from disk"
        return line


# --- constructors ------------------------------------------------------------

def library_scope() -> Scope:
    """Everything under the root. The state the application opens in."""
    return Scope(key=LIBRARY_KEY, label=LIBRARY_LABEL)


def scope_from_draw(key: str, label: str, folder: Path | None) -> Scope:
    """A scope over exactly the episodes one sampler draw selected.

    Paths that are no longer on disk are kept separately rather than dropped,
    so the interface can say a sample has lost files instead of quietly
    reporting a smaller sample than was drawn.
    """
    present: list[Path] = []
    absent: list[Path] = []
    for raw in read_selected(folder):
        path = normalize(raw)
        (present if path.exists() else absent).append(path)
    return Scope(key=key, label=label, episodes=tuple(present),
                 missing=tuple(absent), folder=Path(folder) if folder else None)


def scope_from_draws(key: str, label: str, folders) -> Scope:
    """A scope over the UNION of several sampler draws.

    A pipeline node fed by more than one Sampling node works on every
    branch's episodes at once, so the Library must show all of them — not
    whichever single draw happened to be resolved first, which made two
    wired-up samples appear one at a time and look like the other had been
    lost.

    `folder` is deliberately None: a union is not any one draw's folder, and
    claiming one would point Reveal-in-Explorer and the exclude action at a
    sample that holds only part of what is on screen. Callers that need the
    underlying draws should keep their own list of them.
    """
    present: list[Path] = []
    absent: list[Path] = []
    seen: set[Path] = set()
    for folder in folders or ():
        for raw in read_selected(folder):
            path = normalize(raw)
            if path in seen:
                continue          # two branches may legitimately draw one episode
            seen.add(path)
            (present if path.exists() else absent).append(path)
    return Scope(key=key, label=label, episodes=tuple(present),
                 missing=tuple(absent), folder=None)


def scope_from_pipeline(pipeline) -> Scope | None:
    """A scope for an `analyzer.pipeline.Pipeline`, or None if it cannot have one.

    The synthetic "Unsampled work" pipeline is deliberately refused: it has no
    draw folder, and `build_pipelines` fabricates `<stem>.mp4` placeholders for
    it that resolve to no real file. Offering it as a scope would produce an
    empty Library and no way to tell that from a sample whose files had gone.
    """
    folder = getattr(pipeline, "folder", None)
    if getattr(pipeline, "is_synthetic", False) or not folder:
        return None
    return scope_from_draw(pipeline.key, pipeline.name, folder)
