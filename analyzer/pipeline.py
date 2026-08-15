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

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cache import load_cached
from .scope import read_selected
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

# Canonical stage order. "measurement" is the combined automated+hand track and
# is kept because saved pipelines reference it; new work should use the
# separate tracks, which is what lets a hand-coding-only or language-only study
# be expressed without dragging the automated pass along.
STAGE_KEYS = [
    "sampling", "selection",
    "automated", "language",
    "handcode_transitions", "handcode_events",
    "measurement",
    "validation", "results",
]


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

# selected.csv is read by analyzer/scope.py and nowhere else. It used to be
# read here too, and a sample's episode list now has three consumers — the
# scope, this module and the sample aggregate. Three readers of one file is
# how they drift apart.


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


def _count_with_speech(root: Path | None, episodes: list[Path]) -> int:
    """Episodes whose cached result carries usable speech data."""
    if not root or not episodes:
        return 0
    cache_root = Path(root) / ".analysis"
    if not cache_root.is_dir():
        return 0
    wanted = {ep.stem for ep in episodes}
    found = 0
    try:
        for p in cache_root.rglob("*.json"):
            if p.stem == "aggregate" or p.stem not in wanted:
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if (data.get("metrics", {}).get("speech", {}) or {}).get("available"):
                found += 1
    except Exception:
        return found
    return found


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


def _automated_stage(episodes: list[Path], analyzed: int,
                     trials: list[dict]) -> Stage:
    """The machine pass on its own — separate from human coding."""
    s = Stage(
        key="automated",
        name="Automated coding",
        subtitle="Machine-measured features",
        explanation="Shot transitions, colour, motion, flashing, and audio, "
                    "measured by the tool.",
    )
    total = len(episodes)
    if total == 0:
        s.status = BLOCKED
        s.headline = "Nothing selected"
        s.next_action = "Select episodes first."
        return s
    s.status = _status_from_counts(analyzed, total)
    s.headline = _pct(analyzed, total) + " analyzed"
    s.details = [
        ("Episodes analyzed", _pct(analyzed, total)),
        ("Detector exports",
         _plural(len([t for t in trials if t.get("kind") == "detection_run"]),
                 "run")),
    ]
    if analyzed < total:
        s.next_action = (f"Analyze the remaining "
                         f"{_plural(total - analyzed, 'episode')} "
                         "(Automated coding → Analyze).")
    return s


def _language_stage(root: Path | None, episodes: list[Path]) -> Stage:
    """Speech and vocabulary, which some studies use on their own."""
    s = Stage(
        key="language",
        name="Language",
        subtitle="Speech rate and vocabulary",
        explanation="Words per minute, speech density, and lexical complexity "
                    "from captions or transcripts. English-only.",
    )
    total = len(episodes)
    if total == 0:
        s.status = BLOCKED
        s.headline = "Nothing selected"
        return s
    with_speech = _count_with_speech(root, episodes)
    s.status = _status_from_counts(with_speech, total)
    s.headline = _pct(with_speech, total) + " with speech data"
    s.details = [
        ("Episodes with speech", _pct(with_speech, total)),
        ("Source", "caption files, or Whisper when enabled"),
        ("Language support", "English only"),
    ]
    if with_speech < total:
        s.next_action = ("Episodes without captions have no speech data. Use "
                         "Analyze → Transcribe Missing Subtitles, or enable "
                         "Whisper in Settings.")
    return s


def _handcode_stage(key: str, name: str, subtitle: str, explanation: str,
                    coded: int, total: int, codebook: str) -> Stage:
    """One human-coding track. Deliberately independent of the machine pass.

    Hand coding is a measurement in its own right, not a step on the way to
    validating automation — a study can consist of nothing else.
    """
    s = Stage(key=key, name=name, subtitle=subtitle, explanation=explanation)
    if total == 0:
        s.status = BLOCKED
        s.headline = "Nothing selected"
        return s
    s.status = _status_from_counts(coded, total)
    s.headline = _pct(coded, total) + " coded"
    s.details = [("Episodes coded", _pct(coded, total)),
                 ("Codebook", codebook)]
    if coded < total:
        s.next_action = (f"{_plural(total - coded, 'episode')} still to code "
                         "(Human coding → Code).")
    elif coded >= 2:
        s.next_action = ("Consider a second coder on at least one episode "
                         "(Human coding → Agreement) to report reliability.")
    return s


def rescope_to_target(stage: Stage, target: int, total: int) -> Stage:
    """Re-express a hand-coding stage against a validation subset.

    A stage reports coverage of the whole selection, which is right when the
    coded set IS the study. It is wrong — and actively misleading — when the
    hand coding exists only to estimate the tool's error on a subset: "0/20
    coded, 20 still to code" tells a researcher to do five times the work the
    design calls for, and would make the automated pass redundant if followed.
    """
    if target <= 0:
        return stage
    # You cannot code more episodes than the sample contains. A default target
    # carried in from a preset will often exceed a small sample.
    if total > 0:
        target = min(target, total)
    coded = _coded_count(stage)
    done = min(coded, target)
    out = Stage(
        key=stage.key, name=stage.name, subtitle="Validation subset",
        explanation=stage.explanation,
        status=_status_from_counts(done, target),
        headline=f"{done}/{target} of subset coded",
    )
    out.details = [
        ("Subset target", _plural(target, "episode")),
        ("Coded so far", str(coded)),
        ("Sample size", _plural(total, "episode")),
        ("Why a subset",
         "the error rate measured here is applied to the automated numbers "
         "for the whole sample"),
    ] + [d for d in stage.details if d[0] == "Codebook"]
    if done < target:
        out.next_action = (
            f"Code {_plural(target - done, 'more episode')} to reach the "
            "subset target. Coding beyond it adds little — the point is to "
            "estimate error, not to hand-measure the corpus.")
    else:
        out.next_action = (
            "Subset complete. Run the comparison (Human coding → Validate "
            "tool), and consider a second coder on one episode for "
            "inter-rater reliability.")
    return out


def _coded_count(stage: Stage) -> int:
    """Pull the coded count back out of a hand-coding stage's details."""
    for label, value in stage.details:
        if label == "Episodes coded":
            head = str(value).split("/", 1)[0].strip()
            if head.isdigit():
                return int(head)
    return 0


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

def _all_stages(root, manifest, trial, episodes, analyzed, coverage,
                trials, folder) -> list[Stage]:
    """Every stage a pipeline can report on, in canonical order.

    A document draws on whichever of these its nodes reference, so a
    hand-coding-only study simply never looks at the automated ones.
    """
    hand = coverage.get("n_transition_coded", 0) if coverage else 0
    events = coverage.get("n_event_coded", 0) if coverage else 0
    total = len(episodes)
    return [
        _sampling_stage(manifest, trial),
        _selection_stage(episodes, analyzed, coverage),
        _automated_stage(episodes, analyzed, trials),
        _language_stage(root, episodes),
        _handcode_stage(
            "handcode_transitions", "Hand-code transitions",
            "Human-coded cuts and dissolves",
            "A person logs every transition. A measurement in its own right — "
            "it does not require the automated pass.",
            hand, total, "validation/CODEBOOK.md"),
        _handcode_stage(
            "handcode_events", "Hand-code events",
            "Human-coded fantastical events",
            "A person logs fantastical events — the content variable the "
            "current literature points to, and one no formal-features "
            "measure can see.",
            events, total, "validation/EVENT_CODEBOOK.md"),
        _measurement_stage(episodes, analyzed, coverage, trials),
        _validation_stage(trials, coverage),
        _results_stage(root, analyzed, trials, folder),
    ]


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
        episodes = read_selected(folder) if folder else []
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
            stages=_all_stages(root, manifest, trial, episodes, analyzed,
                               coverage, mine, folder),
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
            stages=_all_stages(root, None, None, episodes,
                               max(analyzed, len(coded)), coverage, orphans,
                               None),
        ))

    return pipelines


def empty_pipeline() -> Pipeline:
    """Placeholder shown when nothing has been done yet.

    A new user opening CMAT for the first time should still see the shape of
    the workflow, with every stage explained — an empty screen teaches nothing.
    """
    stages = _all_stages(None, None, None, [], 0, None, [], None)
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
