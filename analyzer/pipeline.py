"""
Pipeline model — the research workflow as a sequence of stages, derived from
what is actually on disk.

WHY THIS EXISTS
---------------
CMAT accumulated a lot of separate capabilities (sampler, analyzer, hand-coding,
validation, index, export) and each one has its own tab. Nothing told a new user
how they connect, or where a given study currently stands. This module answers
one question: "for this set of episodes, how far along am I?"

TERMINOLOGY
-----------
A PIPELINE is a named episode sample plus everything derived from its episodes.
A TRIAL is one run inside a pipeline (a comparison, a sweep, an event-coding
pass). Previously "trial" was the top-level concept, but trials are
heterogeneous — an episode_sample is the START of a workflow while the others
are artifacts produced partway through it — so they do not belong at the same
level. discover_trials() is unchanged and still backs the Trials view; this
module groups its output.

Episodes worked on without a formal sample draw are not hidden: they appear in
a synthetic "Unsampled work" pipeline, because pretending they don't exist would
misrepresent how much of the corpus is actually documented.

STAGES
------
    Sampling → Selection → Measurement → Validation → Results

Sampling and Selection are genuinely different questions ("how were episodes
chosen" vs "which ones are in the working set, on which track"), and Measurement
is where CMAT's two co-equal halves — automated metrics and hand coding — run in
parallel. Collapsing them would hide the thing the tool is actually about.

Pure functions, zero GUI imports.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cache import load_cached
from .trials import KIND_LABELS, discover_trials, sample_coverage
from .validation import get_validation_dir

# Stage status. Ordered by how much attention it deserves.
COMPLETE = "complete"    # nothing outstanding
PARTIAL = "partial"      # started, work remaining
PENDING = "pending"      # not started, but upstream is ready
BLOCKED = "blocked"      # cannot start until an upstream stage produces something

STATUS_LABEL = {
    COMPLETE: "Complete",
    PARTIAL: "In progress",
    PENDING: "Not started",
    BLOCKED: "Waiting on earlier stage",
}

STAGE_KEYS = ["sampling", "selection", "measurement", "validation", "results"]


@dataclass
class Stage:
    """One box in the pipeline diagram."""
    key: str
    name: str
    subtitle: str                       # one line under the title, always shown
    status: str = PENDING
    headline: str = ""                  # the single number that matters
    details: list[tuple[str, str]] = field(default_factory=list)
    explanation: str = ""               # plain-English "what this step is"
    next_action: str = ""               # what the user should do next, if anything

    @property
    def status_label(self) -> str:
        return STATUS_LABEL.get(self.status, self.status)


@dataclass
class Pipeline:
    """A named sample and everything derived from its episodes."""
    key: str
    name: str
    description: str
    stages: list[Stage]
    episode_count: int = 0
    is_synthetic: bool = False          # the "Unsampled work" catch-all
    manifest_path: Path | None = None
    folder: Path | None = None
    trials: list[dict] = field(default_factory=list)

    def stage(self, key: str) -> Stage | None:
        for s in self.stages:
            if s.key == key:
                return s
        return None

    @property
    def current_stage(self) -> Stage:
        """The stage the user is actually working in right now."""
        for s in self.stages:
            if s.status in (PARTIAL, PENDING):
                return s
        return self.stages[-1]

    @property
    def progress(self) -> float:
        """0.0-1.0 across stages, counting partial stages as half."""
        if not self.stages:
            return 0.0
        score = sum(1.0 if s.status == COMPLETE else 0.5 if s.status == PARTIAL
                    else 0.0 for s in self.stages)
        return score / len(self.stages)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_selected(folder: Path) -> list[Path]:
    """Episode paths from a sampler draw's selected.csv."""
    csv_path = folder / "selected.csv"
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


def cached_stems(root: Path | None) -> set[str]:
    """Every episode stem with a cached result, found by globbing the cache.

    Deliberately does not reconstruct show_key paths. Sampler CSVs store
    absolute paths, the synthetic pipeline has no real paths at all, and a
    library that has been reorganised breaks the arithmetic either way. The
    cache filename IS the episode stem, so matching on that is both simpler
    and more robust.
    """
    if not root:
        return set()
    cache_root = Path(root) / ".analysis"
    if not cache_root.is_dir():
        return set()
    out: set[str] = set()
    try:
        for p in cache_root.rglob("*.json"):
            if p.stem != "aggregate":
                out.add(p.stem)
    except Exception:
        return out
    return out


def _count_analyzed(root: Path | None, episodes: list[Path],
                    stems: set[str] | None = None) -> int:
    """How many of these episodes have a cached automated analysis."""
    if not episodes:
        return 0
    available = cached_stems(root) if stems is None else stems
    return sum(1 for ep in episodes if ep.stem in available)


def _pct(n: int, total: int) -> str:
    return f"{n}/{total}" + (f"  ({n / total:.0%})" if total else "")


def _plural(n: int, singular: str, plural: str | None = None) -> str:
    """'1 episode' / '3 episodes' — reads better than 'episode(s)' everywhere."""
    return f"{n} {singular if n == 1 else (plural or singular + 's')}"


def _status_from_counts(done: int, total: int) -> str:
    if total <= 0:
        return PENDING
    if done >= total:
        return COMPLETE
    return PARTIAL if done > 0 else PENDING


# ---------------------------------------------------------------------------
# Stage builders
# ---------------------------------------------------------------------------

def _sampling_stage(manifest: dict | None, trial: dict | None) -> Stage:
    s = Stage(
        key="sampling",
        name="Sampling",
        subtitle="How episodes were chosen",
        explanation="Which episodes represent a show, and by what documented rule.",
    )
    if not manifest:
        s.status = PENDING
        s.headline = "No formal sample"
        s.details = [
            ("Method", "episodes chosen by hand, not drawn"),
            ("Reproducible", "no — there is no manifest to re-run"),
        ]
        s.next_action = ("Use File → Episode Sampler to draw a documented "
                         "sample if this work is going into a write-up.")
        return s

    total_sel = manifest.get("total_selected", 0)
    total_av = manifest.get("total_available", 0)
    method = manifest.get("method", "unknown")
    s.status = COMPLETE
    s.headline = f"{total_sel} of {total_av} episodes"
    s.details = [
        ("Method", method),
        ("Stratified by", manifest.get("stratify_by") or "not stratified"),
        ("Random seed", str(manifest.get("seed", "—"))),
        ("Sample type", "probability sample" if manifest.get("probability")
         else "non-probability sample"),
        ("Drawn", (manifest.get("generated_at_utc") or "—")[:10]),
        ("Software version", manifest.get("software_version", "—") or "—"),
    ]
    if not manifest.get("probability", True):
        s.next_action = ("Non-probability sample — describe the selection rule "
                         "explicitly when reporting; it does not support "
                         "inference to the whole show.")
    if trial and trial.get("folder"):
        s.details.append(("Manifest", str(trial["folder"])))
    return s


def _selection_stage(episodes: list[Path], analyzed: int, coverage: dict | None) -> Stage:
    s = Stage(
        key="selection",
        name="Selection",
        subtitle="Working set and tracks",
        explanation="The working set, and which of the two measurement tracks each episode is on.",
    )
    total = len(episodes)
    if total == 0:
        s.status = BLOCKED
        s.headline = "No episode list"
        s.details = [("Episodes", "none — the sample has no selected.csv")]
        s.next_action = "Draw a sample first, or add episodes to the library."
        return s

    hand = coverage.get("n_transition_coded", 0) if coverage else 0
    events = coverage.get("n_event_coded", 0) if coverage else 0
    touched = max(analyzed, hand, events)
    s.status = _status_from_counts(touched, total)
    s.headline = f"{total} episode" + ("s" if total != 1 else "")
    s.details = [
        ("Automated track", _pct(analyzed, total) + " analyzed"),
        ("Hand-coding track", _pct(hand, total) + " transition-coded"),
        ("Event coding", _pct(events, total) + " coded"),
        ("Untouched", _plural(total - touched, "episode") + " not yet measured"),
    ]
    if touched < total:
        s.next_action = (f"{_plural(total - touched, 'episode')} have no measurement yet. "
                         "Send them to the analysis queue or the hand-coding "
                         "worklist.")
    return s


def _measurement_stage(episodes: list[Path], analyzed: int,
                       coverage: dict | None, trials: list[dict]) -> Stage:
    s = Stage(
        key="measurement",
        name="Measurement",
        subtitle="Metrics and hand coding",
        explanation="Automated metrics for sensory features; hand coding for what the tool cannot see.",
    )
    total = len(episodes)
    hand = coverage.get("n_transition_coded", 0) if coverage else 0
    events = coverage.get("n_event_coded", 0) if coverage else 0

    detection_runs = [t for t in trials if t.get("kind") == "detection_run"]
    event_runs = [t for t in trials if t.get("kind") == "event_coding"]

    if total == 0:
        s.status = BLOCKED
        s.headline = "Nothing to measure"
        s.next_action = "Select episodes first."
        return s

    s.status = _status_from_counts(min(analyzed, max(hand, 1)), total) \
        if hand else _status_from_counts(analyzed, total)
    s.headline = _pct(analyzed, total) + " analyzed"
    s.details = [
        ("Automated analysis", _pct(analyzed, total) + " episodes cached"),
        ("Transition coding", _plural(hand, "episode") + " hand-coded"),
        ("Event coding", _plural(events, "episode") + " coded"),
        ("Detector exports", _plural(len(detection_runs), "run")),
        ("Event-rate runs", _plural(len(event_runs), "run")),
    ]
    if analyzed < total:
        s.next_action = (f"Analyze the remaining {_plural(total - analyzed, 'episode')} "
                         "to complete the automated track.")
    elif hand == 0:
        s.next_action = ("No hand coding yet. Automated numbers cannot be "
                         "validated without it.")
    return s


def _validation_stage(trials: list[dict], coverage: dict | None) -> Stage:
    s = Stage(
        key="validation",
        name="Validation",
        subtitle="Graded against humans",
        explanation="How closely the automated measure agrees with a human on the same episodes.",
    )
    comparisons = [t for t in trials if t.get("kind") == "transition_validation"]
    gradings = [t for t in trials if t.get("kind") == "classifier_grading"]
    sweeps = [t for t in trials if t.get("kind") == "dissolve_sweep"]
    hand = coverage.get("n_transition_coded", 0) if coverage else 0

    if not comparisons:
        s.status = BLOCKED if hand == 0 else PENDING
        s.headline = "Not yet run"
        s.details = [
            ("Comparison runs", "0"),
            ("Hand-coded episodes available", str(hand)),
        ]
        s.next_action = (
            "Hand-code at least one episode first — validation compares the "
            "tool against a human, so it needs human coding to compare to."
            if hand == 0 else
            "You have hand coding but no comparison run. Open Automated coding "
            "→ Validation to grade the detector against it."
        )
        return s

    scores = [t.get("result", "") for t in comparisons if t.get("result")]
    s.status = PARTIAL if len(comparisons) < 3 else COMPLETE
    s.headline = _plural(len(comparisons), "comparison run")
    s.details = [
        ("Comparison runs", str(len(comparisons))),
        ("Latest result", scores[0] if scores else "—"),
        ("Classifier gradings", str(len(gradings))),
        ("Parameter sweeps", str(len(sweeps))),
        ("Episodes hand-coded", str(hand)),
    ]
    if len(comparisons) < 3:
        s.next_action = (
            "Validated on very few episodes. Accuracy is content-dependent, so "
            "a range across production styles is worth more than a single "
            "number. A second coder on one episode would also give you "
            "inter-rater reliability, which is currently missing."
        )
    return s


def _results_stage(root: Path | None, analyzed: int, trials: list[dict],
                   folder: Path | None) -> Stage:
    s = Stage(
        key="results",
        name="Results",
        subtitle="Outputs and locations",
        explanation="Per-episode metrics, show aggregates, and the index — each tagged with how it was measured.",
    )
    if analyzed == 0:
        s.status = BLOCKED
        s.headline = "No results yet"
        s.next_action = "Analyze at least one episode."
        return s

    s.status = PARTIAL if analyzed else PENDING
    if analyzed and any(t.get("kind") == "transition_validation" for t in trials):
        s.status = COMPLETE

    s.headline = _plural(analyzed, "episode result")
    s.details = [
        ("Per-episode metrics", _plural(analyzed, "cached result")),
        ("Total runs recorded", str(len(trials))),
        ("Index", "searchable in the Index tab"),
        ("Export formats", "JSON · CSV · PDF report"),
    ]
    if root:
        s.details.append(("Cache location", str(Path(root) / ".analysis")))
    if folder:
        s.details.append(("Sample folder", str(folder)))
    s.next_action = ("Export from File → Export Results, or browse everything "
                     "in the Index tab.")
    return s


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def build_pipelines(
    root: Path | None = None,
    validation_dir: Path | None = None,
) -> list[Pipeline]:
    """Group every discovered trial into pipelines, newest sample first.

    *root* is the show library root (for cache look-ups). Safe to call with
    None — the pipeline just reports zero analyzed episodes.
    """
    vdir = validation_dir or get_validation_dir()
    extra = [root] if root else []
    try:
        all_trials = discover_trials(vdir, extra_dirs=extra)
    except Exception:
        all_trials = []

    samples = [t for t in all_trials if t.get("kind") == "episode_sample"]
    others = [t for t in all_trials if t.get("kind") != "episode_sample"]

    pipelines: list[Pipeline] = []
    claimed_stems: set[str] = set()
    analyzed_stems = cached_stems(root)      # globbed once, reused per pipeline

    for trial in samples:
        folder = trial.get("folder")
        episodes = _read_selected(folder) if folder else []
        stems = {e.stem for e in episodes}
        claimed_stems |= stems

        mine = [t for t in others if t.get("episode") in stems]
        analyzed = _count_analyzed(root, episodes, analyzed_stems)
        try:
            coverage = sample_coverage(trial, vdir)
        except Exception:
            coverage = None

        manifest = trial.get("raw") or {}
        pipelines.append(Pipeline(
            key=f"sample:{folder}",
            name=trial.get("name") or "Unnamed sample",
            description=trial.get("result", ""),
            episode_count=len(episodes),
            manifest_path=trial.get("manifest_path"),
            folder=folder,
            trials=mine,
            stages=[
                _sampling_stage(manifest, trial),
                _selection_stage(episodes, analyzed, coverage),
                _measurement_stage(episodes, analyzed, coverage, mine),
                _validation_stage(mine, coverage),
                _results_stage(root, analyzed, mine, folder),
            ],
        ))

    # Everything worked on outside a formal sample draw.
    orphans = [t for t in others if t.get("episode") not in claimed_stems]
    if orphans:
        stems = sorted({t["episode"] for t in orphans})
        episodes = [Path(f"{s}.mp4") for s in stems]
        coded = {t["episode"] for t in orphans
                 if t.get("kind") in ("transition_validation", "event_coding")}
        coverage = {
            "n_episodes": len(stems),
            "n_transition_coded": len({t["episode"] for t in orphans
                                       if t.get("kind") == "transition_validation"}),
            "n_event_coded": len({t["episode"] for t in orphans
                                  if t.get("kind") == "event_coding"}),
        }
        analyzed = _count_analyzed(root, episodes, analyzed_stems)
        pipelines.append(Pipeline(
            key="unsampled",
            name="Unsampled work",
            description="Episodes worked on without a formal sample draw",
            episode_count=len(stems),
            is_synthetic=True,
            trials=orphans,
            stages=[
                _sampling_stage(None, None),
                _selection_stage(episodes, analyzed, coverage),
                _measurement_stage(episodes, analyzed, coverage, orphans),
                _validation_stage(orphans, coverage),
                _results_stage(root, max(analyzed, len(coded)), orphans, None),
            ],
        ))

    return pipelines


def empty_pipeline() -> Pipeline:
    """Placeholder shown when nothing has been done yet.

    A new user opening CMAT for the first time should still see the shape of
    the workflow, with every stage explained — an empty screen teaches nothing.
    """
    stages = [
        _sampling_stage(None, None),
        _selection_stage([], 0, None),
        _measurement_stage([], 0, None, []),
        _validation_stage([], None),
        _results_stage(None, 0, [], None),
    ]
    stages[0].next_action = (
        "Start here: choose a root folder with your video files, then use "
        "File → Episode Sampler to draw a documented sample."
    )
    return Pipeline(
        key="empty",
        name="No pipelines yet",
        description="This is the workflow CMAT follows, start to finish.",
        stages=stages,
        is_synthetic=True,
    )


def trial_rows(pipeline: Pipeline) -> list[tuple[str, str, str, str]]:
    """(date, kind label, episode, result) for the trials inside a pipeline."""
    rows = []
    for t in sorted(pipeline.trials, key=lambda x: x.get("date", ""), reverse=True):
        rows.append((
            t.get("date", "—") or "—",
            KIND_LABELS.get(t.get("kind", ""), t.get("kind", "—")),
            t.get("episode", "—"),
            t.get("result", "—"),
        ))
    return rows
