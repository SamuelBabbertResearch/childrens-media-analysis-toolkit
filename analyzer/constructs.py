"""
The measurement model — constructs, aspects, measures, methods, and the
resolution of a measure to a real number from real data on disk.

WHAT THIS MODULE IS FOR

`analyzer/measurements.py` answers "which tool produced this number, with what
parameters". It does not answer the question before that one: *what does the
researcher think they are measuring, and why does this number stand in for it?*

Pacing is not a value stored in an MP4. It is a construct. `cuts_per_min` is
one operationalization of it, produced by one detector at one threshold. A tool
that presents `cuts_per_min` as "the pacing" has made a scientific decision on
the researcher's behalf and hidden it in an algorithm. So CMAT never says
"transitions = algorithm X"; it says "transitions were operationalized using
method X with parameters Y", and offers a different X.

    Construct   Pacing                    theoretical; not in the file
      Aspect    Visual pacing             a facet, where one keeps measures honest
        Measure Hard cuts per minute      an observable quantity, with a unit
          Method ContentDetector @ 27     one implementation that produces it
          Method TransNetV2 @ 0.5         another
          Method Hand coding              also a method, not a lesser one

THREE RULES THIS MODULE EXISTS TO ENFORCE, not merely to describe:

1. **It never restates the registry.** Automated methods are GENERATED from
   `measurements.MEASUREMENTS` — one method per ToolSpec. A detector added
   there appears here as an available method with no edit to this file, and its
   validation status is read from its ToolSpec every time it is asked for. A
   second list of detectors written beside the registry is `LEARNINGS.md`
   shape 3, and this module is exactly where one would get written by accident.

2. **It refuses rather than guesses.** Every measure resolves to a real path
   into a cached `EpisodeResult` or a real key of a hand-coding metrics dict.
   Where the method was not run, where the cache cannot say WHICH tool produced
   a number, or where a hand-coded rate has no recorded window to divide by,
   the answer is a refusal carrying its reason — never a plausible number.
   `LEARNINGS.md` shape 2 is a control whose data path is empty; a construct
   naming a measure that resolves to nothing is the same defect one layer up.

3. **It never averages across methods, and never compares quantities that are
   not the same quantity.** `resolve_measure` returns one result PER METHOD and
   provides no aggregate over them. Whether two measures may be set side by
   side is decided by `comparable()`, which reads
   `validation.ENGINE_COMPARABLE_FIELDS` rather than re-deriving that split.

WHAT IT STORES, AND WHAT IT DOES NOT

Constructs a RESEARCHER writes are stored, in `<root>/.analysis/constructs/`,
with the library — see the library store at the foot of this file. That is
the only thing here that touches disk, and it is deliberately in this file
rather than a neighbouring one: `get_construct` has to return shipped and
library constructs through ONE call, or there are two answers to "what
constructs exist" and the second one drifts (`LEARNINGS.md` shape 3).

MEASURES ARE NOT USER-DEFINABLE, and that is a rule rather than an omission.
A construct is a theoretical claim and costs nothing to be wrong about in the
data model; a measure has to resolve to a real number from real data, and one
that does not is `LEARNINGS.md` shape 2 — a control whose data path is empty —
which is the defect this entire phase exists to remove. A researcher's own
construct is operationalized by binding the SHIPPED measures to it in a recipe,
exactly as the shipped composite already binds six measures owned by five other
constructs.

Recipes, versions and staleness live in `analyzer/recipes.py`
(`MEASUREMENT_MODEL.md` §4.2, §4.4, §4.5).

Zero GUI imports, per `CLAUDE.md` §2.4.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from . import measurements as reg
from .config_loader import _base_dir


# ---------------------------------------------------------------------------
# Method kinds and resolution outcomes
# ---------------------------------------------------------------------------

CONSTRUCT_SCHEMA_VERSION = 1

AUTOMATED = "automated"
HAND_CODED = "hand_coded"

# Hand coding gets its own status word, deliberately outside the registry's
# validated/experimental/unvalidated vocabulary. Those three grade an automated
# tool against hand coding, which is a meaningless question to ask OF hand
# coding — and calling it "unvalidated" would read as "worse than validated",
# contradicting `CLAUDE.md` §2.5: automated measurement is not inherently more
# valid than human coding. Both are methods.
HUMAN_CODED_STATUS = "human-coded"

# Resolution outcomes. Anything other than MEASURED carries no value.
MEASURED = "measured"
NOT_RUN = "not_run"                  # nothing cached / no coding sheet
METHOD_NOT_USED = "method_not_used"  # measured, but by a different tool
TOOL_UNRECORDED = "tool_unrecorded"  # measured, but the cache cannot say by what
UNAVAILABLE = "unavailable"          # optional dependency absent
WINDOW_UNKNOWN = "window_unknown"    # coded, but the coded window is unrecorded
NO_VALUE = "no_value"                # the method ran; this field is legitimately absent

# How confidently the tool attribution is known. The three-state answer
# `LEARNINGS.md` § *A staleness count can be honest and still mislead* asks
# for: a check that can return "no" and "cannot tell" must report both.
RECORDED = "recorded"            # the result carries its measurements block
INFERRED_LEGACY = "inferred_legacy"  # migrated from pre-registry flat config keys
UNRECORDED = "unrecorded"        # nothing in the result identifies the tool


@dataclass(frozen=True)
class Resolved:
    """One method's answer for one measure on one episode — or its refusal."""
    measure_key: str
    method_key: str
    method_label: str
    status: str
    value: Any = None
    unit: str = ""
    detail: str = ""              # why, when status is not MEASURED
    method_status: str = ""       # registry status, or HUMAN_CODED_STATUS
    flag: str = ""                # unvalidated-measure warning; "" when validated
    attribution: str = ""         # RECORDED | INFERRED_LEGACY | UNRECORDED
    parameters: dict[str, Any] = field(default_factory=dict)
    source: str = ""              # the file the number came from

    @property
    def ok(self) -> bool:
        return self.status == MEASURED


# ---------------------------------------------------------------------------
# The model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Aspect:
    key: str
    name: str
    definition: str


@dataclass(frozen=True)
class AutomatedSource:
    """Where an automated measure's value sits, and which registry entry owns it.

    `measurement_key` names a `MeasurementSpec`; every ToolSpec under it becomes
    one available method. `value_path` is a dotted path into a cached
    `EpisodeResult.to_dict()`, checked against the schema by
    `tests/test_constructs.py` so a renamed field fails loudly instead of
    silently resolving to nothing.

    `available_path` is a dotted path to a boolean that must be true for the
    value to count as measured. Some blocks in the schema carry a default of
    0.0 whether or not the pass ever ran — an episode with no audio track has
    `audio.rms_mean == 0.0` and `audio.available == False`, and an episode with
    no captions has `speech.words_per_minute == 0.0` and
    `speech.available == False`. Reading the number without the flag reports a
    silent episode and an unmeasured one as the same measurement, which is the
    "zero rate or no coding?" distinction `event_coding`'s publish guard
    already exists to protect on the hand-coding side.
    """
    measurement_key: str
    value_path: str
    available_path: str = ""


@dataclass(frozen=True)
class HandSource:
    """Where a hand-coded measure's value sits.

    `kind` is "transitions" (a `*_manual.csv`, analysed by
    `validation.manual_pacing_metrics`) or "events" (a `*_events.csv`, analysed
    by `event_coding.compute_event_metrics`). `field_key` is a real key of that
    function's returned dict.

    `needs_window` marks a value that depends on the length of the coded span
    — every rate, and also every shot-length statistic, because
    manual_pacing_metrics bounds the first and last shot by the span edges.
    Such a value CANNOT be resolved without knowing what window was coded, and
    knowing the episode's duration is not a substitute: a coder who stopped
    after ten seconds of a twenty-four minute episode leaves a sheet that
    divides to 0.084 cuts/min against a detected 17.8, and to a mean shot
    length of 473 seconds. Both are wrong; both display perfectly. That is the
    failure this flag exists to refuse, and it was found by running the model
    over this working copy's real sheets rather than by a passing test.

    Only span-independent values (raw counts) may set this False.
    """
    kind: str
    field_key: str
    needs_window: bool = True


@dataclass(frozen=True)
class Measure:
    """An observable quantity offered as an operationalization of a construct."""
    key: str
    name: str
    construct_key: str
    unit: str
    definition: str
    aspect_key: str = ""
    automated: AutomatedSource | None = None
    hand: HandSource | None = None
    # Measures that must be reported together or not at all. `CLAUDE.md` §2.2:
    # words per minute divides by dialogue time, not runtime, so alone it
    # invites the wrong reading. Declared here so the rule is data a screen can
    # obey, rather than prose a screen author has to have read.
    reported_with: tuple[str, ...] = ()
    notes: str = ""

    @property
    def has_automated_counterpart(self) -> bool:
        return self.automated is not None

    @property
    def hand_coding_only(self) -> bool:
        return self.automated is None and self.hand is not None


SHIPPED = "shipped"
LIBRARY = "library"


@dataclass(frozen=True)
class Construct:
    """The theoretical thing being studied. Not observable, not in the file.

    `source` is SHIPPED for the starting set defined below, or LIBRARY for one
    a researcher wrote, which lives in `<root>/.analysis/constructs/` and is
    loaded by `set_library`. A shipped construct is a starting point, never a
    claim that CMAT validated the mapping; a library one is the researcher's
    own claim and CMAT has validated it even less.

    `content_hash` covers the construct's MEANING — definition, grounding, and
    each aspect's key and definition. It deliberately excludes `name`, and each
    aspect's name, because those are labels: renaming a construct is not
    redefining it, exactly as `Recipe.canonical()` excludes a recipe's name for
    the same reason. It excludes `key` because the key IS the identity — a
    changed key is a different construct, not a changed one.

    Recipes record the hash they were authored against and report a
    **divergence** when it moves (`recipes.construct_divergence`). Redefining a
    construct changes what every citing recipe claims to measure, and
    `MEASUREMENT_MODEL.md` §6 forbids letting old results silently look
    current.
    """
    key: str
    name: str
    definition: str
    grounding: str
    aspects: tuple[Aspect, ...] = ()
    source: str = SHIPPED
    path: Path | None = None

    def content_hash(self) -> str:
        payload = json.dumps({
            "definition": self.definition,
            "grounding": self.grounding,
            # Sorted, so reordering aspects is not a redefinition.
            "aspects": sorted(({"key": a.key, "definition": a.definition}
                               for a in self.aspects),
                              key=lambda d: d["key"]),
        }, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]

    @property
    def is_editable(self) -> bool:
        """Shipped constructs are read-only; a researcher's own are not.

        A shipped construct is cited by the shipped composite and by anything
        built on it, so editing one in place would move what a published score
        claims to measure. Duplicating into a library construct is the route,
        matching the locked-recipe rule.
        """
        return self.source == LIBRARY

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": CONSTRUCT_SCHEMA_VERSION,
            "key": self.key,
            "name": self.name,
            "definition": self.definition,
            "grounding": self.grounding,
            "aspects": [{"key": a.key, "name": a.name,
                         "definition": a.definition} for a in self.aspects],
            "content_hash": self.content_hash(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any],
                  path: Path | None = None) -> "Construct":
        return cls(
            key=str(d.get("key", "")),
            name=str(d.get("name") or d.get("key") or "Untitled construct"),
            definition=str(d.get("definition", "")),
            grounding=str(d.get("grounding", "")),
            aspects=tuple(
                Aspect(key=str(a.get("key", "")),
                       name=str(a.get("name") or a.get("key") or ""),
                       definition=str(a.get("definition", "")))
                for a in (d.get("aspects") or [])),
            source=LIBRARY,
            path=path,
        )


@dataclass(frozen=True)
class Method:
    """One concrete implementation that produces a measure's value.

    Generated, not declared — see `methods_for`. `status` and `label` are read
    from the registry's ToolSpec at generation time, so this object cannot
    disagree with the registry.
    """
    key: str
    label: str
    kind: str
    status: str
    measure_key: str
    summary: str = ""
    notes: str = ""
    available: bool = True
    measurement_key: str = ""     # registry MeasurementSpec key, automated only
    tool_key: str = ""            # registry ToolSpec key, automated only


# ---------------------------------------------------------------------------
# The shipped starting set
# ---------------------------------------------------------------------------
# A shipped construct is a STARTING POINT, never a claim that CMAT has
# validated the mapping from construct to measure. Researchers add their own.
#
# Deliberately only two constructs. `MEASUREMENT_MODEL.md` §4.3 says do pacing
# first and completely, speech second because it carries the paired-reporting
# rule, and do not generalize past two until both are genuinely right. The
# composite's other four inputs (saturation, contrast, motion, flashing, audio)
# are measured and reported by the engine today and are NOT yet expressed here.

PACING = Construct(
    key="pacing",
    name="Pacing",
    definition=(
        "How rapidly the audiovisual stream changes — the rate at which a "
        "viewer is required to reorient to new visual information."
    ),
    grounding=(
        "Huston & Wright's formal features treat pace as a structural property "
        "of the stimulus; Lang's LC4MP motivates it as a demand on limited "
        "processing capacity. Neither specifies a measure, a threshold, or a "
        "detector — the choice of operationalization below is CMAT's, not "
        "theirs, and is not validated by citing them."
    ),
    aspects=(
        Aspect("visual_transitions", "Visual transitions",
               "How often the image is replaced by a different shot."),
        Aspect("rhythm", "Rhythm",
               "How evenly or unevenly those transitions are spaced. Two "
               "episodes with one cuts/min figure can differ entirely here."),
        Aspect("scene_structure", "Scene structure",
               "Whether a cut stays inside one scene or relocates to a new "
               "one. Lang's related vs unrelated cuts: raw cuts/min conflates "
               "a cheap cut with an expensive one."),
    ),
)

SPEECH = Construct(
    key="speech",
    name="Speech",
    definition=(
        "The spoken-language stream: how much is said, and how densely it "
        "occupies the episode."
    ),
    grounding=(
        "Language exposure is the outcome literature's usual interest in "
        "children's television. CMAT measures the stimulus's speech, which is "
        "not a measure of what a child hears, attends to, or learns."
    ),
)

COLOUR = Construct(
    key="colour",
    name="Colour",
    definition=(
        "The colour properties of the image: how saturated it is, and how "
        "widely brightness varies within a frame."
    ),
    grounding=(
        "Huston & Wright treat visual salience as a formal feature. Which "
        "colour statistic stands in for salience is CMAT's choice, not "
        "theirs, and neither measure below has been validated against any "
        "perceptual criterion."
    ),
)

MOTION = Construct(
    key="motion",
    name="Motion",
    definition=(
        "How much the image changes from one sampled frame to the next."
    ),
    grounding=(
        "Motion is a pre-attentive, bottom-up attention magnet (Itti & Koch). "
        "The measures below cannot separate object motion from camera motion "
        "from a cut, so they measure change, not movement."
    ),
)

LUMINANCE_CHANGE = Construct(
    key="luminance_change",
    name="Luminance change",
    definition=(
        "Abrupt frame-to-frame changes in the overall brightness of the image."
    ),
    grounding=(
        "NOT a photosensitivity safety assessment. The measure below is a "
        "whole-frame luminance mean and implements neither the area threshold "
        "nor the red-flash criterion broadcast guidance specifies. It compares "
        "episodes measured the same way; nothing more."
    ),
)

LOUDNESS = Construct(
    key="loudness",
    name="Loudness",
    definition="How loud the episode's audio is.",
    grounding=(
        "Linear RMS, not a perceptual loudness standard — not LUFS or EBU "
        "R128. An episode with no audio track has no value here, which is not "
        "the same as a value of zero."
    ),
)

SENSORY_LOAD = Construct(
    key="sensory_load",
    name="Sensory load",
    definition=(
        "The overall perceptual demand a programme places on a viewer, taken "
        "as a single summary quantity."
    ),
    grounding=(
        "READ THIS BEFORE USING IT. Huston & Wright's formal features and "
        "Lang's LC4MP justify MEASURING pacing, colour, motion, luminance "
        "change and loudness. **Neither says how to combine them into one "
        "number**, and nothing in CMAT derives the combination: the shipped "
        "composite's weights, its normalization ceilings and its additive form "
        "were authored during implementation and have no recorded derivation "
        "(`ARCHITECTURE.md` §8.1a). Expressing that composite as a recipe "
        "makes the choice explicit and inspectable. It does not justify it, "
        "and naming this construct does not retroactively derive a weight."
    ),
)

CONSTRUCTS: tuple[Construct, ...] = (
    PACING, SPEECH, COLOUR, MOTION, LUMINANCE_CHANGE, LOUDNESS, SENSORY_LOAD,
)


MEASURES: tuple[Measure, ...] = (
    # --- Pacing / visual transitions ---------------------------------------
    Measure(
        key="hard_cuts_per_min",
        name="Hard cuts per minute",
        construct_key="pacing",
        aspect_key="visual_transitions",
        unit="cuts/min",
        definition=(
            "Instantaneous shot boundaries per minute of running time. The "
            "engine's detectors produce boundaries of this kind only; hand "
            "coding restricts to rows typed hard_cut so the two describe the "
            "same quantity."
        ),
        automated=AutomatedSource("transitions", "metrics.scene_pacing.cuts_per_min"),
        hand=HandSource("transitions", "hard_cuts_per_min"),
    ),
    Measure(
        key="transitions_per_min",
        name="All transitions per minute",
        construct_key="pacing",
        aspect_key="visual_transitions",
        unit="transitions/min",
        definition=(
            "Every coded transition per minute — hard cuts, dissolves, fades, "
            "wipes and the rest, counted together."
        ),
        hand=HandSource("transitions", "transitions_per_min"),
        notes=(
            "NO AUTOMATED COUNTERPART. The detectors do not produce a typed "
            "transition inventory, so there is nothing to set this beside. It "
            "is not a version of hard cuts per minute measured differently — "
            "it counts different things, and will always read higher."
        ),
    ),
    Measure(
        key="mean_shot_length",
        name="Mean shot length",
        construct_key="pacing",
        aspect_key="visual_transitions",
        unit="sec",
        definition="Mean duration of a shot, in seconds.",
        automated=AutomatedSource("transitions", "metrics.shot_length.mean_sec"),
        hand=HandSource("transitions", "mean_shot_sec"),
        notes=(
            "The two differ slightly at the edges by construction: the engine "
            "includes its first and last scene, hand coding bounds shots by "
            "the coded window. Documented in manual_pacing_metrics()."
        ),
    ),
    Measure(
        key="median_shot_length",
        name="Median shot length",
        construct_key="pacing",
        aspect_key="visual_transitions",
        unit="sec",
        definition="Median duration of a shot, in seconds.",
        automated=AutomatedSource("transitions", "metrics.shot_length.median_sec"),
        hand=HandSource("transitions", "median_shot_sec"),
    ),
    Measure(
        key="dissolves_per_min",
        name="Dissolves per minute",
        construct_key="pacing",
        aspect_key="visual_transitions",
        unit="dissolves/min",
        definition=(
            "Gradual transitions, where two shots blend over many frames "
            "rather than switching in one."
        ),
        automated=AutomatedSource("dissolves", "metrics.scene_pacing.dissolves_per_min"),
        notes=(
            "Hand coding records dissolves as a transition type, but "
            "manual_pacing_metrics() reports them as a count inside by_type "
            "rather than as a rate, so no hand-coded rate is offered here "
            "rather than one being derived. Deriving it would be this module "
            "computing a quantity the hand-coding analysis deliberately does "
            "not publish."
        ),
    ),

    # --- Pacing / rhythm ----------------------------------------------------
    Measure(
        key="shot_length_cv",
        name="Shot-length variability",
        construct_key="pacing",
        aspect_key="rhythm",
        unit="ratio",
        definition=(
            "Coefficient of variation (SD/mean) of shot durations. High values "
            "mean bursty, uneven cutting; low values mean metronomic."
        ),
        automated=AutomatedSource("transitions", "metrics.scene_pacing.shot_length_cv"),
        hand=HandSource("transitions", "shot_length_cv"),
    ),

    # --- Pacing / scene structure ------------------------------------------
    # Two measures, not one, and the split is the point. The engine and the
    # hand-coding analysis both emit a field called `scene_changes_per_min`,
    # and they are NOT the same quantity — one is unvalidated frame-similarity
    # classification, the other a human's scene_relation label.
    # `validation.HAND_CODING_ONLY_FIELDS` is where that is recorded; keeping
    # them as one measure would invite exactly the comparison it forbids.
    Measure(
        key="scene_changes_per_min_detected",
        name="Scene changes per minute (detected)",
        construct_key="pacing",
        aspect_key="scene_structure",
        unit="changes/min",
        definition=(
            "Cuts classified as relocating to a new scene, by comparing a "
            "frame shortly before the cut with one shortly after."
        ),
        automated=AutomatedSource("scene_relation",
                                  "metrics.scene_pacing.scene_changes_per_min"),
        notes=(
            "Not the same measure as the hand-coded scene-change rate, despite "
            "the identical field name in each source. The similarity threshold "
            "has never been calibrated against hand-coded scene relations."
        ),
    ),
    Measure(
        key="scene_changes_per_min_coded",
        name="Scene changes per minute (hand-coded)",
        construct_key="pacing",
        aspect_key="scene_structure",
        unit="changes/min",
        definition=(
            "Cuts a human coder labelled as relocating to a new scene, per "
            "minute of coded window."
        ),
        hand=HandSource("transitions", "scene_changes_per_min"),
        notes=(
            "NO AUTOMATED COUNTERPART, notwithstanding the detected measure "
            "above sharing its field name. A coder labels by understanding the "
            "scene; the detector thresholds a similarity score."
        ),
    ),

    # --- Speech -------------------------------------------------------------
    Measure(
        key="words_per_minute",
        name="Words per minute",
        construct_key="speech",
        unit="words/min",
        definition=(
            "Speech rate WHILE SPEAKING — total words divided by dialogue "
            "time, not by runtime. It is how fast characters speak when they "
            "speak, not how talkative an episode is."
        ),
        automated=AutomatedSource("speech", "metrics.speech.words_per_minute",
                                  available_path="metrics.speech.available"),
        reported_with=("speech_density",),
        notes=(
            "`CLAUDE.md` §2.2: reported with speech density, or not at all. "
            "A quiet episode of fast talkers and a chatty episode of slow "
            "talkers are not distinguishable from this number alone."
        ),
    ),
    Measure(
        key="speech_density",
        name="Speech density",
        construct_key="speech",
        unit="fraction",
        definition=(
            "Fraction of the episode's duration containing speech, 0–1. The "
            "denominator words per minute does not use."
        ),
        automated=AutomatedSource("speech", "metrics.speech.speech_density",
                                  available_path="metrics.speech.available"),
        reported_with=("words_per_minute",),
    ),
    Measure(
        key="total_words",
        name="Total words",
        construct_key="speech",
        unit="words",
        definition="Words in the caption file or transcript for the episode.",
        automated=AutomatedSource("speech", "metrics.speech.total_words",
                                  available_path="metrics.speech.available"),
    ),

    # --- Colour -------------------------------------------------------------
    Measure(
        key="saturation_mean",
        name="Colour saturation",
        construct_key="colour",
        unit="fraction",
        definition=(
            "Mean HSV saturation across sampled frames, 0–1. How intensely "
            "coloured the image is on average."
        ),
        automated=AutomatedSource("color", "metrics.color_saturation.mean"),
        notes=(
            "Unreliable on blown-out live-action production styles, which is "
            "why the Live-Action preset near-zeroes its weight."
        ),
    ),
    Measure(
        key="contrast_mean",
        name="Colour contrast",
        construct_key="colour",
        unit="fraction",
        definition=(
            "SPATIAL spread of brightness WITHIN a frame — the standard "
            "deviation of the V channel, averaged over sampled frames. It is "
            "not change between frames, which the name invites."
        ),
        automated=AutomatedSource("color",
                                  "metrics.color_saturation.contrast_mean"),
    ),

    # --- Motion -------------------------------------------------------------
    Measure(
        key="motion_mean",
        name="Motion",
        construct_key="motion",
        unit="fraction",
        definition=(
            "Mean absolute difference between consecutive sampled frames, "
            "0–1. Depends on the frame sampling rate, because it measures the "
            "gap between the frames that were sampled."
        ),
        automated=AutomatedSource("motion", "metrics.motion.mean"),
    ),

    # --- Luminance change ---------------------------------------------------
    Measure(
        key="flashing_events_per_min",
        name="Flashing",
        construct_key="luminance_change",
        unit="events/min",
        definition=(
            "Frame-to-frame jumps in mean brightness exceeding a threshold, "
            "per minute."
        ),
        automated=AutomatedSource(
            "flashing", "metrics.flashing.luminance_delta_events_per_min"),
        notes=(
            "Never present this as a safety assessment. Whole-frame luminance "
            "mean, so a flash confined to part of the screen is diluted, and "
            "the tool is unvalidated."
        ),
    ),

    # --- Loudness -----------------------------------------------------------
    Measure(
        key="audio_rms_mean",
        name="Audio loudness",
        construct_key="loudness",
        unit="RMS",
        definition=(
            "Mean per-window RMS loudness, linear 0–1. Absent, not zero, when "
            "the episode has no audio track or FFmpeg was unavailable."
        ),
        automated=AutomatedSource("audio", "metrics.audio.rms_mean",
                                  available_path="metrics.audio.available"),
    ),
)


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------

def all_constructs() -> list[Construct]:
    """Every construct this install can offer: shipped first, then the library's.

    Callers must use this rather than iterating `CONSTRUCTS`, which is only the
    shipped starting set. A shipped key always wins over a library one of the
    same name — `save_construct` refuses the collision at write time, and this
    is the second line of that defence, because a file can arrive in the folder
    by other routes than `save_construct` (a copied library, a hand-edited
    folder, an older CMAT that had no such rule). Shadowing `pacing` with a
    local redefinition would silently move what the shipped composite means.
    """
    shipped_keys = {c.key for c in CONSTRUCTS}
    return list(CONSTRUCTS) + [c for c in _LIBRARY_CONSTRUCTS
                               if c.key not in shipped_keys]


def get_construct(key: str) -> Construct | None:
    return next((c for c in all_constructs() if c.key == key), None)


def get_measure(key: str) -> Measure | None:
    return next((m for m in MEASURES if m.key == key), None)


def measures_for(construct_key: str, aspect_key: str | None = None) -> list[Measure]:
    out = [m for m in MEASURES if m.construct_key == construct_key]
    if aspect_key is not None:
        out = [m for m in out if m.aspect_key == aspect_key]
    return out


def companions(measure_key: str) -> list[Measure]:
    """Measures that must be reported alongside this one, or it is not reported.

    Returns the companions themselves rather than their keys so a caller cannot
    display the rule without being able to display what it requires.
    """
    measure = get_measure(measure_key)
    if measure is None:
        return []
    return [c for c in (get_measure(k) for k in measure.reported_with) if c]


def comparable(measure_a: str, measure_b: str) -> tuple[bool, str]:
    """May these two measures be set side by side? (verdict, reason).

    Comparison belongs BETWEEN METHODS OF ONE MEASURE — automated detector A
    against detector B against a human coder. That is method comparison, and it
    is the point of the model. Two *different* measures are two different
    quantities even when they share a field name, and this project has already
    published one number that came from ignoring such a difference
    (`LEARNINGS.md` shape 4).
    """
    a, b = get_measure(measure_a), get_measure(measure_b)
    if a is None or b is None:
        return False, "unknown measure"
    if a.key == b.key:
        return True, (
            f"the same measure, so its methods may be compared with each other")
    return False, (
        f"{a.name} and {b.name} are different quantities, not two methods of "
        f"one measure. Report them separately.")


def methods_comparable(measure_key: str) -> tuple[bool, str]:
    """May this measure's automated and hand-coded methods be set side by side?

    Reads `validation.ENGINE_COMPARABLE_FIELDS` for the hand-coding half rather
    than re-deriving the split (`CLAUDE.md` §2.5). A measure whose hand-coded
    field is in the hand-coding-only set has no automated counterpart to
    compare against, however similar the two field names look.
    """
    measure = get_measure(measure_key)
    if measure is None:
        return False, "unknown measure"
    if measure.hand is None or measure.automated is None:
        return False, (
            f"{measure.name} has only one kind of method, so there is nothing "
            f"to compare it against.")
    if not hand_field_is_engine_comparable(measure.hand.field_key):
        return False, (
            f"the hand-coded {measure.hand.field_key} counts something the "
            f"detectors do not produce, so it is not a second method of the "
            f"automated figure.")
    return True, (
        f"the hand-coded {measure.hand.field_key} mirrors the engine's "
        f"definition, so the two are methods of one measure.")


def hand_field_is_engine_comparable(field_key: str) -> bool:
    """Whether a hand-coding field may be set beside an automated figure.

    Reads `validation.ENGINE_COMPARABLE_FIELDS`. `CLAUDE.md` §2.5: read that
    distinction, do not re-derive it.
    """
    from .validation import ENGINE_COMPARABLE_FIELDS
    return field_key in ENGINE_COMPARABLE_FIELDS


# ---------------------------------------------------------------------------
# Methods — generated from the registry, never listed here
# ---------------------------------------------------------------------------

def methods_for(measure_key: str) -> list[Method]:
    """Every method that can produce this measure, automated and hand-coded.

    Automated methods come from the registry: one per ToolSpec under the
    measure's MeasurementSpec. Adding a detector to `analyzer/measurements.py`
    makes it appear here with no edit to this file — which is the whole point,
    and is asserted by `tests/test_constructs.py`.
    """
    measure = get_measure(measure_key)
    if measure is None:
        return []

    out: list[Method] = []

    if measure.automated is not None:
        spec = reg.get_measurement(measure.automated.measurement_key)
        if spec is not None:
            for tool in spec.tools:
                out.append(Method(
                    key=f"auto:{spec.key}:{tool.key}",
                    label=tool.name,
                    kind=AUTOMATED,
                    status=tool.status,          # read, never restated
                    measure_key=measure.key,
                    summary=tool.summary,
                    notes=tool.notes,
                    available=tool.is_available(),
                    measurement_key=spec.key,
                    tool_key=tool.key,
                ))

    if measure.hand is not None:
        out.append(Method(
            key=f"hand:{measure.hand.kind}",
            label="Hand coding",
            kind=HAND_CODED,
            status=HUMAN_CODED_STATUS,
            measure_key=measure.key,
            summary=(
                "A human coder watching the episode and marking each "
                "transition against the codebook."
            ),
            notes=(
                "A measurement in its own right, not a step towards validating "
                "automation. Its own limits: timestamps are quantised to whole "
                "seconds, so any comparison tolerance tighter than ~1 s "
                "measures the coding resolution rather than the method; and "
                "the coding here is single-coder unless an agreement figure "
                "says otherwise."
            ),
        ))

    return out


def get_method(measure_key: str, method_key: str) -> Method | None:
    return next((m for m in methods_for(measure_key) if m.key == method_key), None)


def selected_method(measure_key: str,
                    config: dict[str, Any] | None) -> Method | None:
    """The automated method *config* currently selects for this measure.

    Asked of the registry rather than answered here, so this cannot disagree
    with what the engine would actually run. Returns None for a measure with no
    automated source — hand coding is not something a config selects.
    """
    measure = get_measure(measure_key)
    if measure is None or measure.automated is None:
        return None
    if config is None:
        methods = [m for m in methods_for(measure_key) if m.kind == AUTOMATED]
        return methods[0] if methods else None
    tool, _params, _enabled = reg.selection(
        dict(config), measure.automated.measurement_key)
    return get_method(measure_key,
                      f"auto:{measure.automated.measurement_key}:{tool.key}")


def _flag_for(method: Method) -> str:
    """The unvalidated-measure warning for a method, or '' when validated.

    Derived from the registry's status rather than written out, so a tool
    regraded in `measurements.py` changes this string with no edit here.
    `CLAUDE.md` §2.2 requires the flag wherever the number appears.
    """
    if method.kind == HAND_CODED:
        return ""
    if method.status == reg.VALIDATED:
        return ""
    label = reg.STATUS_LABEL.get(method.status, method.status)
    return f"{method.label} is {label} — never graded against hand coding"


# ---------------------------------------------------------------------------
# Resolution — a measure, a method, an episode, a number
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EpisodeRef:
    """Everything needed to find one episode's measurements on disk.

    `show_name` and `stem` are the cache's own coordinates
    (`<root>/.analysis/<show_name>/<stem>.json`), taken rather than re-derived
    so this module does not become a fourth place that decides how a show
    folder maps to a cache key.
    """
    root: Path
    show_name: str
    stem: str
    video: Path | None = None
    duration_sec: float = 0.0
    validation_dir: Path | None = None
    # The window a hand-coding sheet covers, when the researcher knows it and
    # the files do not record it. Used only as a fallback behind what is
    # recorded on disk, so supplying one can never override a real record.
    coded_window: tuple[float, float] | None = None


def _has_scoring_settings(config: dict[str, Any] | None) -> bool:
    """Whether *config* can re-derive a composite.

    Scoring and measurement are two axes (`ARCHITECTURE.md` §3) and a config
    holding only one of them is normal, not malformed.
    """
    return bool(config
                and config.get("normalization_reference_ranges")
                and config.get("sensory_load_weights"))


def _dig(data: dict, dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _tool_attribution(cached: dict, measurement_key: str
                      ) -> tuple[str | None, dict[str, Any], bool, str]:
    """Which tool produced this cached result? -> (tool_key, params, enabled, attribution)

    Three answers, not two. A result written since the measurements block
    existed RECORDS its tool. A result written before it carries only the
    legacy flat config keys, which `measurements.normalize_config` migrates —
    faithful, because those keys were what ran, but INFERRED. A result carrying
    neither cannot be attributed at all, and saying otherwise would put a
    number under a detector's name on no evidence.
    """
    cfg = cached.get("config")
    if not isinstance(cfg, dict) or not cfg:
        return None, {}, True, UNRECORDED

    recorded = isinstance(cfg.get("measurements"), dict) and bool(cfg["measurements"])
    try:
        tool, params, enabled = reg.selection(dict(cfg), measurement_key)
    except KeyError:
        return None, {}, True, UNRECORDED
    return (tool.key, params, enabled,
            RECORDED if recorded else INFERRED_LEGACY)


def _resolve_automated(measure: Measure, method: Method, ref: EpisodeRef,
                       config: dict[str, Any] | None) -> Resolved:
    # TWO reads, and the split is load-bearing.
    #
    # VALUES come from `load_scored`, the documented one sanctioned way to read
    # a cached result: the composite in the file is a derivation that goes
    # stale against the current weights, and a reader that opens the JSON its
    # own way is how the last of those defects reached the public site
    # (`LEARNINGS.md` § *The fifth reader of a cached composite*).
    #
    # ATTRIBUTION comes from `load_cached`, the RAW file, because
    # `rescore_episode` returns a new EpisodeResult carrying the config it was
    # rescored WITH — the live one — not the config that produced the numbers.
    # Reading attribution off the scored copy therefore reports the settings in
    # force now and calls them the settings that measured the episode. It looks
    # correct whenever the two agree, and is wrong precisely when they differ,
    # which is the only case anyone asks the question in.
    from .cache import cache_path, load_cached, load_scored

    base = dict(
        measure_key=measure.key, method_key=method.key,
        method_label=method.label, unit=measure.unit,
        method_status=method.status, flag=_flag_for(method),
    )
    path = cache_path(ref.root, ref.show_name, ref.stem)

    # `load_scored` re-derives the composite, which needs the SCORING half of a
    # config (weights and reference ranges). A measurement-only config — which
    # is a perfectly ordinary thing to hold, and what a recipe carries — has
    # neither, and passing it would raise rather than resolve. No measure here
    # reads a composite-derived field, so passing None costs nothing today; the
    # call still goes through load_scored so that when one does, it is already
    # reading through the one sanctioned reader rather than opening the file.
    scoring_config = config if _has_scoring_settings(config) else None
    result = load_scored(ref.root, ref.show_name, ref.stem, scoring_config)
    if result is None:
        if not method.available:
            return Resolved(**base, status=UNAVAILABLE, detail=(
                f"{method.label} needs an optional dependency that is not "
                f"installed, and there is no cached result to read."))
        return Resolved(**base, status=NOT_RUN, detail=(
            f"No cached result for this episode at {path}."))
    if result.status != "ok":
        return Resolved(**base, status=NOT_RUN, detail=(
            f"The cached result is a failure, not a measurement: "
            f"{result.error or 'no error recorded'}."))
    cached = result.to_dict()

    assert measure.automated is not None
    # From the RAW file — see the two-reads note above.
    raw = load_cached(ref.root, ref.show_name, ref.stem) or {}
    tool_key, params, enabled, attribution = _tool_attribution(
        raw, measure.automated.measurement_key)

    # Motion and colour are produced by their named method *and* by the shared
    # frame-sampling pass. Recipes pin both parts. Include the dependency in
    # the resolved provenance so evaluation can refuse a cached motion value
    # measured at a different sampling rate instead of treating it as a match.
    if measure.automated.measurement_key in ("motion", "color"):
        sampling_tool, sampling_params, _sampling_enabled, _sampling_attr = (
            _tool_attribution(raw, "sampling")
        )
        params = dict(params)
        params["sampling.tool"] = sampling_tool
        for key, value in sampling_params.items():
            params[f"sampling.{key}"] = value

    if attribution == UNRECORDED:
        return Resolved(**base, status=TOOL_UNRECORDED, source=str(path), detail=(
            "This episode was measured before CMAT recorded which tool it "
            "used, so the number in the cache cannot be attributed to this "
            "method or to any other. Re-analyse the episode to attribute it."),
            attribution=UNRECORDED)

    if not enabled:
        return Resolved(**base, status=NOT_RUN, source=str(path),
                        attribution=attribution, detail=(
            f"{measure.name} was switched off in the measurement settings "
            f"this result was produced under."))

    if tool_key != method.tool_key:
        used = reg.get_measurement(measure.automated.measurement_key)
        used_tool = used.tool(tool_key) if used else None
        return Resolved(**base, status=METHOD_NOT_USED, source=str(path),
                        attribution=attribution, detail=(
            f"This episode was measured with "
            f"{used_tool.name if used_tool else tool_key}, not {method.label}. "
            f"Re-analyse it with {method.label} to get this method's number."))

    available_path = measure.automated.available_path
    if available_path and not _dig(cached, available_path):
        return Resolved(**base, status=NOT_RUN, source=str(path),
                        attribution=attribution, parameters=params, detail=(
            f"This episode carries no {measure.name.lower()} measurement — "
            f"{available_path} is false or absent, so the 0.0 sitting in the "
            f"cache is a schema default rather than a measured value. An "
            f"episode with no audio track, or none with captions, is not an "
            f"episode measured at zero."))

    value = _dig(cached, measure.automated.value_path)
    if value is None:
        return Resolved(**base, status=NO_VALUE, source=str(path),
                        attribution=attribution, parameters=params, detail=(
            f"{method.label} ran, but the cached result carries no "
            f"{measure.automated.value_path}."))

    return Resolved(**base, status=MEASURED, value=value, source=str(path),
                    attribution=attribution, parameters=params)


def _coded_window(slot: dict) -> tuple[tuple[float, float] | None, str]:
    """The window a hand-coding sheet actually covers -> (window, where it came from).

    Coders here code a segment, not a whole episode — the two coded episodes
    are the first ~5 minutes of each. So a rate needs the coded span as its
    denominator, and the span is recorded in two places: the persisted
    hand-coded metrics file, and a comparison manifest. Read one; do not fall
    back to the runtime, which would divide five minutes of coding by
    twenty-five minutes of episode and report a fifth of the true rate.
    """
    import json

    metrics_path = slot.get("metrics")
    if metrics_path:
        try:
            data = json.loads(Path(metrics_path).read_text(encoding="utf-8"))
            window = (data.get("transitions") or {}).get("window")
            if isinstance(window, list) and len(window) == 2:
                return (float(window[0]), float(window[1])), Path(metrics_path).name
        except (OSError, ValueError, TypeError):
            pass

    sheet = slot.get("transitions") or slot.get("events")
    if sheet:
        folder = Path(sheet).parent
        manifests = sorted(folder.glob("*comparison_manifest*.json"),
                           key=lambda p: p.stat().st_mtime, reverse=True)
        for man in manifests:
            try:
                data = json.loads(man.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            window = data.get("window")
            if isinstance(window, list) and len(window) == 2:
                return (float(window[0]), float(window[1])), man.name

    return None, ""


def _resolve_hand(measure: Measure, method: Method, ref: EpisodeRef) -> Resolved:
    from .validation import (coded_episode_map, coding_for_stem,
                             manual_pacing_metrics, parse_manual_csv)

    base = dict(
        measure_key=measure.key, method_key=method.key,
        method_label=method.label, unit=measure.unit,
        method_status=method.status, flag="",
        attribution=RECORDED,
    )
    assert measure.hand is not None

    cmap = coded_episode_map(ref.validation_dir)
    slot = coding_for_stem(ref.stem, cmap)
    sheet = slot.get(measure.hand.kind)
    if sheet is None:
        return Resolved(**base, status=NOT_RUN, detail=(
            f"No {measure.hand.kind} coding sheet for this episode. Hand "
            f"coding is a method that has not been run, not a zero."))

    window, window_source = _coded_window(slot)
    if window is None and ref.coded_window is not None:
        window, window_source = ref.coded_window, "supplied by the caller"
    if measure.hand.needs_window and window is None:
        return Resolved(**base, status=WINDOW_UNKNOWN, source=str(sheet), detail=(
            "This sheet exists, but nothing records which part of the episode "
            "it covers, so there is no honest span to compute against. The "
            "episode's duration is NOT a substitute: a partially coded sheet "
            "divided by the full runtime yields a number that looks like a "
            "measurement and is not one. Record the coded window (compute "
            "metrics for this episode in Human coding, which writes it) or "
            "supply it on the EpisodeRef."))

    try:
        if measure.hand.kind == "events":
            from .event_coding import compute_event_metrics, parse_event_csv
            metrics = compute_event_metrics(
                parse_event_csv(Path(sheet)), ref.duration_sec,
                start=window[0] if window else None,
                end=window[1] if window else None)
        else:
            metrics = manual_pacing_metrics(
                parse_manual_csv(Path(sheet)), duration_sec=ref.duration_sec,
                start=window[0] if window else None,
                end=window[1] if window else None)
    except (OSError, ValueError) as exc:
        return Resolved(**base, status=NO_VALUE, source=str(sheet),
                        detail=f"The coding sheet could not be read: {exc}")

    value = metrics.get(measure.hand.field_key)
    params: dict[str, Any] = {"sheet": Path(sheet).name}
    if window is not None:
        params["coded_window_sec"] = list(window)
        params["window_recorded_in"] = window_source
    params["span_min"] = metrics.get("span_min")

    if value is None:
        return Resolved(**base, status=NO_VALUE, source=str(sheet),
                        parameters=params, detail=(
            f"The sheet is coded, but carries nothing for "
            f"{measure.hand.field_key} — for a scene-relation field this means "
            f"the coder did not label scene relations."))

    return Resolved(**base, status=MEASURED, value=value, source=str(sheet),
                    parameters=params)


def resolve(measure_key: str, method_key: str, ref: EpisodeRef,
            config: dict[str, Any] | None = None) -> Resolved:
    """One method's value for one measure on one episode — or its refusal."""
    measure = get_measure(measure_key)
    if measure is None:
        raise KeyError(f"Unknown measure: {measure_key}")
    method = get_method(measure_key, method_key)
    if method is None:
        raise KeyError(f"Unknown method {method_key!r} for measure {measure_key!r}")

    if method.kind == HAND_CODED:
        return _resolve_hand(measure, method, ref)
    return _resolve_automated(measure, method, ref, config)


def resolve_measure(measure_key: str, ref: EpisodeRef,
                    config: dict[str, Any] | None = None) -> list[Resolved]:
    """Every method's answer for one measure — one row each, never combined.

    There is deliberately no aggregate here and no "best" method. An average
    over two detectors is not a measurement of either, and CMAT published one
    such figure once already (`LEARNINGS.md` shape 4).
    """
    return [resolve(measure_key, m.key, ref, config)
            for m in methods_for(measure_key)]


# ---------------------------------------------------------------------------
# The library store — constructs a researcher wrote
# ---------------------------------------------------------------------------
# They live WITH THE LIBRARY, in `<root>/.analysis/constructs/`, beside the
# recipes that cite them and following the conventions `pipeline_graph.py`
# established — including its re-homing rule, which exists because a document
# first saved before a library root was known kept being written to the
# application folder while the loader only ever read the library's: it saved
# fine and reloaded as nothing.
#
# Why with the library and not with the application: a construct is referenced
# BY recipes, and recipes already live with the library. Splitting the two is
# how a library handed to a collaborator arrives with every construct key
# dangling. Portability stays export/import's job (`MEASUREMENT_MODEL.md`
# §4.7): an exported recipe embeds its construct's definition alongside the
# key, and an unresolvable one is reported as a named gap, never substituted.
# `DECISIONS.md` § *Authoring on the canvas: the four shaping decisions*.

_LIBRARY_CONSTRUCTS: list[Construct] = []
_ACTIVE_ROOT: Path | None = None


def constructs_dir(root: Path | None = None) -> Path:
    """Where library constructs live. Same shape as `recipes.recipes_dir`."""
    if root:
        return Path(root) / ".analysis" / "constructs"
    return _base_dir() / "constructs"


def set_library(root: Path | None) -> list[Construct]:
    """Load *root*'s constructs and make them visible to every lookup.

    This is why no call site needed editing. `get_construct`, `all_constructs`
    and everything downstream of them — `recipes.export_recipe`, the recipe
    editor, the Constructs canvas — go on asking the same question and start
    getting the researcher's own constructs back. Putting the merge in the ONE
    call rather than threading a `root` argument through fifteen call sites is
    `CLAUDE.md` §6: when a rule must hold at every call site, put it in the
    call.

    Replaces the previously loaded set wholesale rather than adding to it, so
    opening library B cannot leave library A's constructs visible. Call with
    None when closing a library.
    """
    global _LIBRARY_CONSTRUCTS, _ACTIVE_ROOT
    _ACTIVE_ROOT = Path(root) if root else None
    _LIBRARY_CONSTRUCTS = list_library_constructs(root) if root else []
    return list(_LIBRARY_CONSTRUCTS)


def active_library() -> Path | None:
    return _ACTIVE_ROOT


def library_constructs() -> list[Construct]:
    """The loaded library constructs alone, without the shipped set."""
    return list(_LIBRARY_CONSTRUCTS)


def list_library_constructs(root: Path | None = None) -> list[Construct]:
    """Read every construct file under *root*. Unreadable files are skipped.

    A file with no key is skipped rather than given a generated one: a
    construct whose key does not match what recipes cite is not that construct,
    and inventing a key would make it silently unreferenced.
    """
    d = constructs_dir(root)
    if not d.is_dir():
        return []
    out: list[Construct] = []
    for p in sorted(d.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            construct = Construct.from_dict(data, path=p)
        except Exception:
            continue
        if construct.key:
            out.append(construct)
    return out


def load_construct(path: Path) -> Construct:
    return Construct.from_dict(
        json.loads(Path(path).read_text(encoding="utf-8")), path=Path(path))


def construct_key_for(name: str, existing: list[str] | None = None) -> str:
    """A stable key derived from a name, unique against *existing*.

    The key is the identity recipes cite, so it is generated once at creation
    and never re-derived from a later name — renaming a construct must not
    orphan the recipes that reference it.
    """
    base = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    base = base[:48] or "construct"
    taken = set(existing or []) | {c.key for c in CONSTRUCTS}
    if base not in taken:
        return base
    i = 2
    while f"{base}_{i}" in taken:
        i += 1
    return f"{base}_{i}"


def new_construct(name: str, definition: str = "", grounding: str = "",
                  aspects: tuple[Aspect, ...] = (),
                  root: Path | None = None) -> Construct:
    """A researcher's own construct, unsaved. `save_construct` writes it."""
    existing = [c.key for c in list_library_constructs(root)]
    return Construct(
        key=construct_key_for(name, existing),
        name=name.strip() or "Untitled construct",
        definition=definition,
        grounding=grounding,
        aspects=tuple(aspects),
        source=LIBRARY,
    )


def _safe_stem(name: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip() or "construct"
    return stem[:60]


def save_construct(construct: Construct, root: Path | None = None) -> Path:
    """Write *construct* into *root*'s constructs folder, re-homing if needed.

    Refuses a SHIPPED construct, and refuses a library construct whose key
    collides with a shipped one. Both refusals protect the same thing: the
    shipped composite and every published score are computed under the shipped
    constructs' meanings, and a local redefinition of `pacing` would move what
    those scores claim to measure while leaving every name and version intact.
    Duplicating into a construct of your own is the route, matching the
    locked-recipe rule.

    Reloads the active set afterwards, so a construct saved here is visible to
    `get_construct` immediately rather than at the next library open — a screen
    that writes a construct and then cannot find it is the kind of gap this
    project keeps finding by driving the artefact.
    """
    if construct.source != LIBRARY:
        raise PermissionError(
            f"{construct.name} is a shipped construct and cannot be edited. "
            f"Duplicate it into a construct of your own.")
    if any(c.key == construct.key for c in CONSTRUCTS):
        raise PermissionError(
            f"{construct.key!r} is the key of a shipped construct. A library "
            f"construct cannot shadow one — recipes citing that key would "
            f"change meaning silently. Give this one its own key.")

    d = constructs_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    target = d / f"{_safe_stem(construct.name)}_{construct.key}.json"
    previous = construct.path

    payload = construct.to_dict()
    payload["modified"] = str(date.today())
    if previous is not None and previous.exists():
        try:
            payload["created"] = str(json.loads(
                previous.read_text(encoding="utf-8")).get("created")
                or payload["modified"])
        except Exception:
            payload["created"] = payload["modified"]
    else:
        payload["created"] = payload["modified"]

    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(target)                  # atomic; never a half-written file
    if previous is not None and previous != target and previous.exists():
        try:
            previous.unlink()
        except OSError:
            pass

    if root is not None and _ACTIVE_ROOT is not None \
            and Path(root) == _ACTIVE_ROOT:
        set_library(root)
    elif root is None and _ACTIVE_ROOT is None:
        set_library(None)
    return target


def delete_construct(construct: Construct, root: Path | None = None) -> None:
    """Delete a library construct. Shipped constructs are refused.

    Deleting one a recipe cites is ALLOWED and is not silently repaired: the
    recipe keeps its construct key and `recipes.construct_divergence` reports
    that the construct is missing. That is the same choice `import_recipe`
    already makes for an unresolvable reference — keep the binding intact and
    name the gap, because substituting or stripping changes what the recipe
    measures while leaving its name and version looking authoritative.
    """
    if construct.source != LIBRARY:
        raise PermissionError(
            f"{construct.name} is a shipped construct and cannot be deleted.")
    if construct.path and construct.path.exists():
        construct.path.unlink()
    if _ACTIVE_ROOT is not None:
        set_library(_ACTIVE_ROOT)
    elif root is not None:
        set_library(root)
