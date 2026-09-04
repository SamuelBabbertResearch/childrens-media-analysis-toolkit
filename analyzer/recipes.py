"""
Recipes — a saved, versioned, citable operationalization.

A preset bundles settings. A RECIPE is a claim about how a construct was
operationalized: which measures stand in for it, by which methods, with which
parameters, how each was transformed, how they were weighted, and what happens
when one is missing. It stays inspectable down to the parameter, because the
point is not to hide the settings behind a name — it is to make the whole
choice citable as one object.

WHAT "PINS ITS PARAMETERS" ACTUALLY MEANS HERE

`DECISIONS.md` records the settled answer: a recipe stores its own frozen copy
of every parameter value rather than referencing the Measurement settings in
force. That decision is only real if the pin is *enforced*, so:

  * `evaluate()` compares the recipe's pinned parameters against the parameters
    that actually produced the cached number, and REFUSES the part when they
    differ. A recipe pinned to ContentDetector at threshold 27 does not get to
    report a number measured at threshold 30 — that number is not what the
    recipe describes.
  * `divergences()` reports where a recipe's pinned values differ from the live
    Measurement settings. This is the accepted cost of pinning written down as
    a function: a threshold can now live in two places, so a recipe has to be
    able to say so out loud rather than leaving the researcher to notice.

A recipe that could not do those two things would be a preset with a version
number on it.

VERSIONING

The version is over the OPERATIONALIZATION'S CONTENT — construct, bindings,
parameters, transforms, weights, missing-data policy. Deliberately not over the
name, the notes, the id or the history: **renaming a recipe is not a new
version** (`MEASUREMENT_MODEL.md` §4.4). `content_hash()` is what decides, so
the rule is arithmetic rather than a convention someone has to follow.

Each version record carries what changed, when, and WHY. The why is the part
that cannot be reconstructed later and is itself paper material — a hash can
tell you two things differ, and only a person can say what made the difference
worth making.

A citable identifier is the friendly version plus the content hash, both
stored: `Pacing — conservative v3 (a7f3c9d1e204)`. The version is what goes in
prose; the hash is what proves two installs hold the same thing.

STORAGE

`<root>/.analysis/recipes/`, travelling with the research data. This file
follows `analyzer/pipeline_graph.py`'s conventions rather than inventing new
ones — atomic write through a temp file, re-homing on save, plain-dict round
trip, fresh ids on duplicate — including the re-homing rule that file had to
grow after documents saved before a library root was known reloaded as
nothing. Portability across projects is `export_recipe`/`import_recipe`, not
the storage location.

Zero GUI imports, per `CLAUDE.md` §2.4.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from . import constructs as C
from . import measurements as reg
from .config_loader import _base_dir

SCHEMA_VERSION = 1


# --- transforms --------------------------------------------------------------
# How a raw measured value becomes the number that enters a composite. Named
# rather than implied, because "normalised" on its own does not say against
# what, and a reference range IS part of the operationalization — retuning the
# ceilings on 2026-08-14 moved every composite score in the project.

TRANSFORM_NONE = "none"        # use the raw value as-is
TRANSFORM_MINMAX = "minmax"    # min-max against a fixed range, clamped to [0,1]

TRANSFORMS = (TRANSFORM_NONE, TRANSFORM_MINMAX)


# --- missing-data behaviour ---------------------------------------------------
# What a recipe does when one of its measures does not resolve. Three real
# behaviours, because the difference between them changes the number.

MISSING_REFUSE = "refuse"
"""The whole composite refuses. The strictest and the default: a composite
missing one of its parts is not that composite."""

MISSING_OMIT = "omit"
"""Drop the part and DO NOT redistribute its weight, so the score sits on a
smaller scale. Honest only if the smaller scale is reported with it, which is
why `Evaluation.scale` exists and is never silently 1.0."""

MISSING_REDISTRIBUTE = "redistribute"
"""Spread the missing part's weight proportionally across the parts that did
resolve, keeping the score on its original scale. This is what the existing
composite does for a silent episode — and `LEARNINGS.md` records that reading
the NOMINAL weights while the engine used redistributed ones made a breakdown
0.057 short of the score printed above it. `Evaluation` therefore carries the
effective weights, not the nominal ones."""

MISSING_POLICIES = (MISSING_REFUSE, MISSING_OMIT, MISSING_REDISTRIBUTE)


# --- evaluation outcomes ------------------------------------------------------

# Reported precision for a composite score and its breakdown. One constant, so
# the two cannot round differently and stop reconciling.
SCORE_DECIMALS = 6

COMPLETE = "complete"      # every part resolved
PARTIAL = "partial"        # some parts missing, and the policy allowed going on
REFUSED = "refused"        # no score; the detail says why

# An extra refusal reason beyond constructs.py's, specific to pinning.
PARAMS_DIFFER = "params_differ"


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# The model
# ---------------------------------------------------------------------------

@dataclass
class MeasureBinding:
    """One measure, by one method, with its parameters pinned.

    `parameters` is the frozen copy. For an automated method these are the
    registry's parameter values (threshold, sample rate...); for hand coding
    the method has no tunable parameters and this is empty, which is not the
    same as unpinned — hand coding's analogous "parameters" are the codebook
    and the coded window, and those live with the sheet.
    """
    measure_key: str
    method_key: str
    parameters: dict[str, Any] = field(default_factory=dict)
    transform: str = TRANSFORM_NONE
    range_min: float = 0.0
    range_max: float = 1.0
    weight: float = 0.0
    missing: str = MISSING_REFUSE

    def to_dict(self) -> dict[str, Any]:
        return {"measure": self.measure_key, "method": self.method_key,
                "parameters": dict(self.parameters),
                "transform": self.transform,
                "range_min": self.range_min, "range_max": self.range_max,
                "weight": self.weight, "missing": self.missing}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MeasureBinding":
        transform = str(d.get("transform") or TRANSFORM_NONE)
        missing = str(d.get("missing") or MISSING_REFUSE)
        return cls(
            measure_key=str(d.get("measure", "")),
            method_key=str(d.get("method", "")),
            parameters=dict(d.get("parameters") or {}),
            transform=transform if transform in TRANSFORMS else TRANSFORM_NONE,
            range_min=float(d.get("range_min", 0.0) or 0.0),
            range_max=float(d.get("range_max", 1.0) or 1.0),
            weight=float(d.get("weight", 0.0) or 0.0),
            missing=missing if missing in MISSING_POLICIES else MISSING_REFUSE,
        )

    def canonical(self) -> dict[str, Any]:
        """The part of this binding the content hash is taken over."""
        return self.to_dict()


@dataclass
class VersionRecord:
    """What a recipe was at a point in time, what changed, and why.

    `reason` is required by `bump_version` and is the field that cannot be
    reconstructed afterwards. `changes` is derived; `reason` is not.
    """
    version: int
    content_hash: str
    created: str
    reason: str = ""
    changes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "content_hash": self.content_hash,
                "created": self.created, "reason": self.reason,
                "changes": list(self.changes)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "VersionRecord":
        return cls(version=int(d.get("version", 1) or 1),
                   content_hash=str(d.get("content_hash", "")),
                   created=str(d.get("created", "")),
                   reason=str(d.get("reason", "")),
                   changes=[str(c) for c in (d.get("changes") or [])])


@dataclass
class Recipe:
    """A saved operationalization of one construct."""
    id: str
    name: str
    construct_key: str
    bindings: list[MeasureBinding] = field(default_factory=list)
    version: int = 1
    notes: str = ""
    # How the composite is REPORTED. Both are part of the operationalization,
    # not display preferences: a score rounded to 4 decimals and one rounded to
    # 6 are different published numbers, and clamping decides what happens when
    # the weights do not sum to 1. They are inside `canonical()` for that
    # reason, so changing either is a new version.
    score_decimals: int = SCORE_DECIMALS
    clamp_score: bool = False
    # A locked recipe is one whose numbers other things already depend on —
    # the shipped composite is the case this exists for. Locking is advisory in
    # the data model and enforced by `save_recipe`, which refuses to overwrite
    # one; nothing stops a researcher duplicating it and editing the copy,
    # which is the intended route.
    locked: bool = False
    history: list[VersionRecord] = field(default_factory=list)
    path: Path | None = None
    # The construct's content hash AS THIS RECIPE WAS AUTHORED. Recorded beside
    # the recipe's own hash and deliberately NOT inside `canonical()`.
    #
    # It is recorded because redefining a construct changes what this recipe
    # claims to measure, and `MEASUREMENT_MODEL.md` §6 forbids letting old
    # results silently look current. It is outside `canonical()` because if it
    # were inside, editing one construct would bump the version of every recipe
    # citing it — without the reason `bump_version` requires, which is the one
    # field that cannot be reconstructed afterwards. So the divergence is
    # REPORTED (`construct_divergence`) rather than folded into the hash, which
    # is the same shape pinned parameters already use.
    #
    # Empty means UNKNOWN, not "matches" — a recipe written before this existed
    # has no baseline to compare against, and reporting it as current would be
    # a guess. Carries forward `cache.is_stale`'s grandfathering rule: results
    # predating a mechanism are unknown, not stale.
    construct_hash: str = ""

    # -- identity ------------------------------------------------------------

    def canonical(self) -> dict[str, Any]:
        """The operationalization, and nothing else.

        Name, notes, id, history, path and lock state are all excluded on
        purpose: they are not part of how the construct was measured, so
        changing them must not produce a new version.
        """
        return {
            "schema": SCHEMA_VERSION,
            "construct": self.construct_key,
            "score_decimals": self.score_decimals,
            "clamp_score": self.clamp_score,
            # Sorted so that reordering the same bindings is not a change.
            "bindings": sorted((b.canonical() for b in self.bindings),
                               key=lambda d: (d["measure"], d["method"])),
        }

    def content_hash(self) -> str:
        payload = json.dumps(self.canonical(), sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]

    def citation(self) -> str:
        """The citable identifier: friendly version plus content hash."""
        return f"{self.name} v{self.version} ({self.content_hash()})"

    def binding(self, measure_key: str) -> MeasureBinding | None:
        return next((b for b in self.bindings if b.measure_key == measure_key),
                    None)

    def total_weight(self) -> float:
        return sum(b.weight for b in self.bindings)

    # -- serialisation -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_VERSION,
            "id": self.id,
            "name": self.name,
            "construct": self.construct_key,
            "construct_hash": self.construct_hash,
            "version": self.version,
            "content_hash": self.content_hash(),
            "locked": self.locked,
            "notes": self.notes,
            "score_decimals": self.score_decimals,
            "clamp_score": self.clamp_score,
            "bindings": [b.to_dict() for b in self.bindings],
            "history": [h.to_dict() for h in self.history],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any], path: Path | None = None) -> "Recipe":
        return cls(
            id=str(d.get("id") or _new_id("r")),
            name=str(d.get("name") or "Untitled recipe"),
            construct_key=str(d.get("construct", "")),
            construct_hash=str(d.get("construct_hash", "") or ""),
            bindings=[MeasureBinding.from_dict(b)
                      for b in (d.get("bindings") or [])],
            version=int(d.get("version", 1) or 1),
            notes=str(d.get("notes", "")),
            locked=bool(d.get("locked", False)),
            score_decimals=int(d.get("score_decimals", SCORE_DECIMALS)),
            clamp_score=bool(d.get("clamp_score", False)),
            history=[VersionRecord.from_dict(h) for h in (d.get("history") or [])],
            path=path,
        )


# ---------------------------------------------------------------------------
# Building a recipe from the live configuration
# ---------------------------------------------------------------------------

def pin_parameters(measure_key: str, method_key: str,
                   config: dict[str, Any] | None) -> dict[str, Any]:
    """The parameter values to freeze into a binding for this method.

    Read from the registry through `measurements.selection`, so the pinned
    values are the ones actually in force rather than a second opinion about
    what the defaults are. Hand-coded methods have none.
    """
    method = C.get_method(measure_key, method_key)
    if method is None or method.kind != C.AUTOMATED:
        return {}
    def _defaults() -> dict[str, Any]:
        spec = reg.get_measurement(method.measurement_key)
        tool = spec.tool(method.tool_key) if spec else None
        return dict(tool.defaults()) if tool else {}

    params = _defaults()
    if config is not None:
        # The live config's parameters belong to the tool the config SELECTS.
        # When this binding names a different tool, that tool's own defaults
        # are the honest pin — copying the selected tool's numbers across would
        # pin values that never applied to this method.
        selected, selected_params, _enabled = reg.selection(
            dict(config), method.measurement_key)
        if selected.key == method.tool_key:
            params = dict(selected_params)

    # Motion and colour share a separate frame-sampling measurement. Motion's
    # value changes when that rate changes, even though the selected motion
    # method itself has no parameters. Keep the dependency namespaced in the
    # binding so a recipe cannot claim to pin motion while silently following
    # whichever sampling rate happens to be live later.
    if method.measurement_key in ("motion", "color"):
        dependency_cfg = dict(config) if config is not None else {}
        sampling_tool, sampling_params, _enabled = reg.selection(
            dependency_cfg, "sampling")
        params["sampling.tool"] = sampling_tool.key
        for key, value in sampling_params.items():
            params[f"sampling.{key}"] = value

    return params


def new_recipe(name: str, construct_key: str,
               config: dict[str, Any] | None = None,
               measures: "list[tuple[str, str] | MeasureBinding] | None" = None,
               reason: str = "Created") -> Recipe:
    """A recipe over a construct, with every parameter pinned from *config*.

    *measures* accepts either `(measure_key, method_key)` pairs — whose
    parameters are pinned from *config* — or fully-formed `MeasureBinding`s,
    for a caller that already knows its transforms and weights. When omitted,
    every measure of the construct is bound to its first available method.

    Nothing is invented: a measure with no method is left out rather than bound
    to a placeholder, because a binding that cannot resolve is exactly the
    empty data path `LEARNINGS.md` shape 2 describes.
    """
    # The construct is checked for the same reason the measure and the method
    # are, a few lines down: this is the constructor an AUTHORING screen calls,
    # so it is where a key that resolves to nothing has to stop. A recipe over
    # a construct this install cannot name has no definition behind it — the
    # screen shows a blank where the claim should be — while carrying a
    # perfectly ordinary name, version, hash and citation.
    #
    # Deliberately NOT applied to `Recipe.from_dict`, which must keep reading a
    # recipe whose construct came from another library: `import_recipe` reports
    # that as a named gap and keeps the key intact, and refusing to AUTHOR one
    # is a different question from refusing to READ one.
    construct = C.get_construct(construct_key)
    if construct is None:
        raise KeyError(
            f"No such construct: {construct_key!r}. Define it first — a "
            f"construct of your own is stored with the library, beside the "
            f"recipes that cite it.")

    recipe = Recipe(id=_new_id("r"), name=name, construct_key=construct_key)
    # The construct's meaning as it stands right now is what this recipe is
    # being written against. Recorded once, here; never refreshed silently —
    # `reaffirm_construct` is the explicit act, matching Re-pin.
    recipe.construct_hash = construct.content_hash()

    if measures is None:
        measures = []
        for measure in C.measures_for(construct_key):
            methods = C.methods_for(measure.key)
            if methods:
                measures.append((measure.key, methods[0].key))

    for entry in measures:
        # `new_binding`, so both routes into a recipe — this one and the
        # canvas palette — agree about transforms. Left as two different
        # defaults, a measure would be scaled or raw depending on which screen
        # bound it, and the recipe would not say which had happened.
        binding = (entry if isinstance(entry, MeasureBinding) else
                   new_binding(entry[0], entry[1], config))
        # A measure or method this install does not have is refused HERE, at
        # the moment of authoring, rather than left to surface as a refusal on
        # every episode later. A binding that can never resolve is
        # `LEARNINGS.md` shape 2 — a control whose data path is empty — and
        # this is the constructor an authoring screen calls, so this is where
        # a typo'd or stale key has to stop.
        #
        # Deliberately NOT applied to `Recipe.from_dict`: a recipe imported
        # from an install that has a detector this one lacks must stay
        # readable with its binding intact, which is `import_recipe`'s whole
        # contract. Refusing to author one is a different question from
        # refusing to read one.
        if C.get_measure(binding.measure_key) is None:
            raise KeyError(
                f"No such measure: {binding.measure_key!r}. Measures are not "
                f"user-definable — a measure has to resolve to a real number "
                f"from real data.")
        if C.get_method(binding.measure_key, binding.method_key) is None:
            available = [m.key for m in C.methods_for(binding.measure_key)]
            raise KeyError(
                f"No such method {binding.method_key!r} for "
                f"{binding.measure_key!r}. Available: {available}")
        recipe.bindings.append(binding)

    recipe.history.append(VersionRecord(
        version=1, content_hash=recipe.content_hash(),
        created=str(date.today()), reason=reason,
        changes=[f"created with {len(recipe.bindings)} measures"]))
    return recipe


# ---------------------------------------------------------------------------
# The shipped composite, expressed as a recipe
# ---------------------------------------------------------------------------
# Which weight key and which normalization range each of the composite's six
# inputs uses. Read from `config.json` at build time, never restated here — the
# ceilings were retuned on 2026-08-14 and every composite score in the project
# moved, so a second copy of these numbers would be wrong within one edit
# (`LEARNINGS.md` shape 3).
#
# (measure key, weight key in sensory_load_weights, key in
#  normalization_reference_ranges, missing-data policy)
_COMPOSITE_INPUTS: tuple[tuple[str, str, str, str], ...] = (
    ("hard_cuts_per_min",       "pacing",         "cuts_per_min",            MISSING_REFUSE),
    ("saturation_mean",         "saturation",     "color_saturation_mean",   MISSING_REFUSE),
    ("contrast_mean",           "color_contrast", "color_contrast_mean",     MISSING_REFUSE),
    ("motion_mean",             "motion",         "motion_mean",             MISSING_REFUSE),
    ("flashing_events_per_min", "flashing",       "flashing_events_per_min", MISSING_REFUSE),
    # Audio is the one input that legitimately goes missing — no audio track,
    # or no FFmpeg — and the engine redistributes its weight proportionally
    # across the visual metrics rather than scoring it as zero. Expressing that
    # as this binding's missing-data policy is what lets the recipe reproduce
    # `metrics_sensory.effective_weights()` instead of reimplementing it.
    ("audio_rms_mean",          "audio",          "audio_rms_mean",          MISSING_REDISTRIBUTE),
)

# Which measures the configuration has a normalization ceiling for, derived
# from the table above rather than restated — there is one mapping from a
# measure to its range key and this is it.
_RANGE_KEYS: dict[str, str] = {m: r for m, _w, r, _p in _COMPOSITE_INPUTS}


def reference_range_for(measure_key: str,
                        config: dict[str, Any] | None) -> tuple[float, float] | None:
    """The configured reference range for *measure_key*, or None if there is none.

    Only the six composite inputs have one; the other ten measures in the model
    have never had a ceiling chosen for them, and this returns None rather than
    inventing one. An invented ceiling is a scoring decision made on the
    researcher's behalf and hidden in a default, which is the thing this whole
    phase exists to stop (`ARCHITECTURE.md` §8.1a — the existing ceilings are
    already underived, and that is a known problem, not a pattern to extend).
    """
    key = _RANGE_KEYS.get(measure_key)
    if not key:
        return None
    entry = ((config or {}).get("normalization_reference_ranges") or {}).get(key)
    if not entry:
        return None
    return float(entry.get("min", 0.0)), float(entry.get("max", 1.0))


def new_binding(measure_key: str, method_key: str,
                config: dict[str, Any] | None) -> MeasureBinding:
    """A binding as an authoring screen should create it.

    **Why this is not just `MeasureBinding(...)` with defaults.** A binding's
    default transform is `none`, which feeds the RAW value into the weighted
    sum. Raw values are in wildly different units — cuts per minute runs around
    15, colour saturation around 0.46 — so two measures added with equal
    weights and no transform produce a composite dominated by whichever
    happens to have the larger units, silently, with both weights on screen
    reading as equal. Every measure in the shipped composite is min-max scaled
    for exactly this reason.

    So where the configuration HAS a reference range for the measure, that is
    the honest default and it is applied. Where it has none, the transform
    stays `none` and the screen says so out loud rather than leaving a raw
    value to be summed against a normalised one — see the Constructs tab's
    unit warning. Nothing is invented: an unconfigured ceiling stays
    unconfigured.
    """
    reference = reference_range_for(measure_key, config)
    binding = MeasureBinding(
        measure_key=measure_key, method_key=method_key,
        parameters=pin_parameters(measure_key, method_key, config))
    if reference is not None:
        binding.transform = TRANSFORM_MINMAX
        binding.range_min, binding.range_max = reference
    return binding


def mixed_scales(recipe: Recipe) -> list[str]:
    """Weighted bindings whose values do not share a scale, if any.

    A composite adds its parts. Adding a value normalised to 0–1 to one in
    cuts per minute is adding two different things, and the weights on screen
    then describe none of it. Reported rather than blocked — a single-measure
    recipe with no transform is perfectly reasonable, and so is one where the
    researcher knows exactly what they are summing.
    """
    weighted = [b for b in recipe.bindings if b.weight]
    if len(weighted) < 2:
        return []
    if len({b.transform for b in weighted}) == 1 and \
            all(b.transform == TRANSFORM_MINMAX for b in weighted):
        return []
    raw = [b.measure_key for b in weighted if b.transform == TRANSFORM_NONE]
    return raw if len(weighted) > len(raw) or len(raw) > 1 else []


SHIPPED_COMPOSITE_NAME = f"{C.FORMAL_FEATURE_COMPOSITE_SHORT_NAME} (as shipped)"

# The shipped composite is GENERATED on every call rather than read from disk,
# so without this its id would be a fresh uuid each time. That is invisible
# everywhere the id is only used to re-select a row within one dialog — and
# wrong for the layout sidecar, which is keyed by recipe id and has to be found
# again next session. `DECISIONS.md`'s decisive argument for putting layout in a
# sidecar was precisely that `save_recipe` refuses this recipe, so this is the
# one diagram most likely to become a methods figure and the one whose
# arrangement most needs to survive. A generated object still needs a stable
# identity to hang anything off.
#
# Not part of `canonical()`, so this changes no hash and no citation.
SHIPPED_COMPOSITE_ID = "r_shipped_composite"


def shipped_composite(config: dict[str, Any]) -> Recipe:
    """The existing Formal-Feature Composite, expressed in the measurement model.

    **Expressing it is not changing it.** This recipe must reproduce
    `metrics_sensory.compute_sensory_load` exactly, for every episode, and
    `tests/test_shipped_composite.py` asserts that against real cached results.
    The public index is built on this composite, so an edit would break
    comparability with every score already computed and published — which is
    why the recipe is returned `locked=True` and `save_recipe` refuses to
    overwrite it.

    What expressing it BUYS, given it changes nothing: the composite stops
    being an algorithm and becomes an inspectable claim. Its six inputs, their
    ceilings, their weights, its additive form, its rounding and its
    audio-redistribution rule are all readable in one object, and it carries a
    content hash — so the 2026-08-14 ceiling retune would today be a visible
    version change rather than a silent movement of every score.

    What it does NOT buy, and must never be read as buying: any justification.
    The weights, the ceilings and the additive form remain underived
    (`ARCHITECTURE.md` §8.1a). Naming a construct does not derive a weight.

    Built from *config* rather than from constants, so it follows the preset in
    force. That means its content hash CHANGES when the weights or ceilings
    change — which is correct and is the point: a differently-weighted
    composite is a different operationalization and should not be citable under
    the same identifier.
    """
    weights = config.get("sensory_load_weights") or {}
    ranges = config.get("normalization_reference_ranges") or {}

    bindings: list[MeasureBinding] = []
    for measure_key, weight_key, range_key, missing in _COMPOSITE_INPUTS:
        method = C.selected_method(measure_key, config)
        if method is None:
            continue                      # no method: leave it out, do not fake one
        reference = ranges.get(range_key) or {}
        bindings.append(MeasureBinding(
            measure_key=measure_key,
            method_key=method.key,
            parameters=pin_parameters(measure_key, method.key, config),
            transform=TRANSFORM_MINMAX,
            range_min=float(reference.get("min", 0.0)),
            range_max=float(reference.get("max", 1.0)),
            weight=float(weights.get(weight_key, 0.0)),
            missing=missing,
        ))

    recipe = new_recipe(
        SHIPPED_COMPOSITE_NAME, "sensory_load", config, measures=bindings,
        reason=("Expresses the composite CMAT has always computed. Reproduces "
                "it exactly; derives none of it."))
    recipe.id = SHIPPED_COMPOSITE_ID
    recipe.locked = True
    # Match compute_sensory_load's reporting exactly: it rounds to 4 decimals
    # and clamps to [0, 1]. Both are part of the published number.
    recipe.score_decimals = 4
    recipe.clamp_score = True
    recipe.notes = (
        "The weights, normalization ceilings and additive form of this "
        "composite have NO recorded derivation — they were authored during "
        "implementation, not fitted or theorised (ARCHITECTURE.md §8.1a). "
        "Huston & Wright and Lang justify measuring these features; neither "
        "says how to combine them. This recipe makes that choice inspectable. "
        "It does not make it justified. Locked because the published index is "
        "built on it: duplicate it to explore alternatives."
    )
    # The notes and lock are outside the content hash, so setting them here
    # does not change the identity the history entry above recorded.
    recipe.history[0].content_hash = recipe.content_hash()
    return recipe


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

def diff_recipes(old: Recipe, new: Recipe) -> list[str]:
    """Human-readable list of what changed between two recipes.

    The shape `measurements.diff_fingerprints` already produces for configs,
    applied to an operationalization. A version record needs this; a hash can
    only say THAT something moved.
    """
    changes: list[str] = []
    if old.construct_key != new.construct_key:
        changes.append(f"construct: {old.construct_key} → {new.construct_key}")

    old_map = {b.measure_key: b for b in old.bindings}
    new_map = {b.measure_key: b for b in new.bindings}

    for key in sorted(set(old_map) - set(new_map)):
        measure = C.get_measure(key)
        changes.append(f"removed measure: {measure.name if measure else key}")
    for key in sorted(set(new_map) - set(old_map)):
        measure = C.get_measure(key)
        changes.append(f"added measure: {measure.name if measure else key}")

    for key in sorted(set(old_map) & set(new_map)):
        o, n = old_map[key], new_map[key]
        measure = C.get_measure(key)
        label = measure.name if measure else key
        if o.method_key != n.method_key:
            o_m = C.get_method(key, o.method_key)
            n_m = C.get_method(key, n.method_key)
            changes.append(
                f"{label} — method: {o_m.label if o_m else o.method_key} → "
                f"{n_m.label if n_m else n.method_key}")
        for p_key in sorted(set(o.parameters) | set(n.parameters)):
            o_v, n_v = o.parameters.get(p_key), n.parameters.get(p_key)
            if o_v != n_v:
                changes.append(f"{label} — {p_key}: {o_v} → {n_v}")
        if o.weight != n.weight:
            changes.append(f"{label} — weight: {o.weight} → {n.weight}")
        if o.transform != n.transform:
            changes.append(f"{label} — transform: {o.transform} → {n.transform}")
        if (o.range_min, o.range_max) != (n.range_min, n.range_max):
            changes.append(
                f"{label} — reference range: [{o.range_min}, {o.range_max}] → "
                f"[{n.range_min}, {n.range_max}]")
        if o.missing != n.missing:
            changes.append(f"{label} — missing-data: {o.missing} → {n.missing}")
    return changes


def bump_version(recipe: Recipe, reason: str,
                 previous: Recipe | None = None) -> VersionRecord | None:
    """Record a new version, or return None when nothing about the
    operationalization changed.

    Returning None for an unchanged hash is the mechanism behind "renaming a
    recipe is not a new version" — the rule is not a convention anyone has to
    remember, it is what `content_hash()` excludes.

    *reason* is required. A version history whose entries say only what changed
    is a diff; the record of WHY a number moved is the part that is itself
    paper material and cannot be recovered later.
    """
    if not reason.strip():
        raise ValueError(
            "a version needs a reason — what changed can be derived, why it "
            "changed cannot")

    digest = recipe.content_hash()
    if recipe.history and recipe.history[-1].content_hash == digest:
        return None

    record = VersionRecord(
        version=recipe.version + 1 if recipe.history else recipe.version,
        content_hash=digest,
        created=str(date.today()),
        reason=reason.strip(),
        changes=diff_recipes(previous, recipe) if previous else [],
    )
    recipe.version = record.version
    recipe.history.append(record)
    return record


# ---------------------------------------------------------------------------
# Pinned versus live — the accepted cost of pinning, made visible
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Divergence:
    measure_key: str
    measure_name: str
    method_label: str
    parameter: str
    pinned: Any
    live: Any

    def describe(self) -> str:
        return (f"{self.measure_name} — {self.method_label}: this recipe pins "
                f"{self.parameter} = {self.pinned}, the current Measurement "
                f"settings say {self.live}")


def divergences(recipe: Recipe,
                config: dict[str, Any]) -> list[Divergence]:
    """Where this recipe's pinned parameters differ from the live settings.

    Pinning was chosen so a saved operationalization cannot change behind the
    researcher's back. The price is that a threshold now lives in two places,
    and the agreed condition of paying it was that a recipe must SAY when the
    two disagree rather than leaving it to be noticed. This is that function;
    a screen showing a recipe is expected to call it.

    A divergence is not an error. It is the ordinary state of a recipe saved
    before a settings change, and it means the recipe still describes what it
    always described.
    """
    out: list[Divergence] = []
    for binding in recipe.bindings:
        method = C.get_method(binding.measure_key, binding.method_key)
        if method is None or method.kind != C.AUTOMATED:
            continue
        measure = C.get_measure(binding.measure_key)
        live_tool, live_params, _enabled = reg.selection(
            dict(config), method.measurement_key)
        if live_tool.key != method.tool_key:
            out.append(Divergence(
                measure_key=binding.measure_key,
                measure_name=measure.name if measure else binding.measure_key,
                method_label=method.label, parameter="tool",
                pinned=method.label, live=live_tool.name))
            continue
        live_snapshot = pin_parameters(
            binding.measure_key, binding.method_key, config)
        for p_key, pinned in binding.parameters.items():
            if live_snapshot.get(p_key) != pinned:
                out.append(Divergence(
                    measure_key=binding.measure_key,
                    measure_name=measure.name if measure else binding.measure_key,
                    method_label=method.label, parameter=p_key,
                    pinned=pinned, live=live_snapshot.get(p_key)))
    return out


# ---------------------------------------------------------------------------
# The construct a recipe was authored against, versus the one that is there now
# ---------------------------------------------------------------------------

CONSTRUCT_CURRENT = "current"        # the definition has not moved
CONSTRUCT_REDEFINED = "redefined"    # same key, different meaning
CONSTRUCT_MISSING = "missing"        # nothing here defines it
CONSTRUCT_UNKNOWN = "unknown"        # no baseline recorded — not a mismatch


@dataclass(frozen=True)
class ConstructDivergence:
    """What happened to the construct this recipe operationalizes.

    A separate object from `Divergence` on purpose. That one is about a
    parameter differing from the live settings; this is about the meaning of
    the thing being measured having moved underneath a saved claim. They are
    different questions and a screen may want to say very different things
    about them.
    """
    status: str
    construct_key: str
    construct_name: str
    recorded_hash: str
    current_hash: str

    @property
    def is_divergent(self) -> bool:
        """Redefined or missing. UNKNOWN is not divergence, and neither is current."""
        return self.status in (CONSTRUCT_REDEFINED, CONSTRUCT_MISSING)

    def describe(self) -> str:
        if self.status == CONSTRUCT_CURRENT:
            return (f"{self.construct_name} is defined here as it was when "
                    f"this recipe was written.")
        if self.status == CONSTRUCT_REDEFINED:
            return (f"{self.construct_name} has been REDEFINED since this "
                    f"recipe was written — its definition, grounding or "
                    f"aspects have changed. The recipe still measures exactly "
                    f"what it always measured; what has moved is the "
                    f"construct those measures are offered as standing in "
                    f"for. Recorded {self.recorded_hash}, now "
                    f"{self.current_hash}.")
        if self.status == CONSTRUCT_MISSING:
            return (f"Nothing in this install defines {self.construct_key!r}, "
                    f"the construct this recipe operationalizes. The recipe is "
                    f"readable and its measures still resolve, but what they "
                    f"are claimed to stand in for is not recorded here.")
        return (f"This recipe predates construct hashing, so there is no "
                f"record of how {self.construct_name} was defined when it was "
                f"written. Not a mismatch — unknown.")


def construct_divergence(recipe: Recipe) -> ConstructDivergence:
    """Has the construct this recipe cites been redefined since it was written?

    A divergence is NOT an error and nothing auto-updates, exactly as with a
    pinned parameter. It means the recipe still describes what it always
    described, and the construct it points at no longer does.

    An empty recorded hash reports UNKNOWN rather than a match: a recipe saved
    before this mechanism existed has no baseline, and calling that "current"
    would be a guess dressed as a fact. That is `cache.is_stale`'s
    grandfathering rule, and the reason it exists — "1 episode goes stale"
    once sat on top of eleven whose settings nobody knew.
    """
    construct = C.get_construct(recipe.construct_key)
    if construct is None:
        return ConstructDivergence(
            status=CONSTRUCT_MISSING, construct_key=recipe.construct_key,
            construct_name=recipe.construct_key,
            recorded_hash=recipe.construct_hash, current_hash="")
    current = construct.content_hash()
    if not recipe.construct_hash:
        status = CONSTRUCT_UNKNOWN
    elif recipe.construct_hash == current:
        status = CONSTRUCT_CURRENT
    else:
        status = CONSTRUCT_REDEFINED
    return ConstructDivergence(
        status=status, construct_key=construct.key,
        construct_name=construct.name,
        recorded_hash=recipe.construct_hash, current_hash=current)


def reaffirm_construct(recipe: Recipe) -> str:
    """Re-record the construct's current meaning as this recipe's baseline.

    The deliberate, named act — the construct-level equivalent of Re-pin, and
    named rather than automatic for the same reason: silently re-baselining on
    save would mean a recipe saved for an unrelated edit quietly adopts a
    redefinition the researcher never read. It is NOT a version bump, because
    the operationalization did not change: the bindings, methods and parameters
    are all untouched, so `content_hash()` does not move and `bump_version`
    would correctly refuse it.
    """
    construct = C.get_construct(recipe.construct_key)
    if construct is None:
        raise KeyError(
            f"Nothing defines {recipe.construct_key!r} here, so there is no "
            f"definition to affirm.")
    recipe.construct_hash = construct.content_hash()
    return recipe.construct_hash


# ---------------------------------------------------------------------------
# Evaluation — applying a recipe to an episode
# ---------------------------------------------------------------------------

def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


@dataclass(frozen=True)
class EvaluatedPart:
    """One binding's contribution, or its refusal."""
    binding: MeasureBinding
    measure_name: str
    resolved: C.Resolved
    status: str                       # C.MEASURED, C.NOT_RUN, PARAMS_DIFFER, ...
    raw: Any = None
    transformed: float | None = None
    effective_weight: float = 0.0
    contribution: float = 0.0
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == C.MEASURED


@dataclass(frozen=True)
class Evaluation:
    """What a recipe produced for one episode.

    `parts` carries every binding including the refused ones — a composite that
    silently drops what it could not measure is how "1 of 6 measured; 5 failed"
    became a report about a show where nothing had failed.

    `effective_weights` are the weights that ACTUALLY produced `score`, after
    any redistribution. Displaying nominal weights beside a redistributed score
    is a defect this project has already shipped and corrected, so the numbers
    that explain the score travel with it.

    `scale` is the sum of the effective weights. It is 1.0 for a complete
    composite over weights that sum to 1, and less when parts were omitted
    without redistribution — in which case the score is on that smaller scale
    and must be read as such.
    """
    recipe_id: str
    recipe_name: str
    version: int
    content_hash: str
    citation: str
    construct_key: str
    parts: tuple[EvaluatedPart, ...]
    status: str
    score_decimals: int = SCORE_DECIMALS
    score: float | None = None
    scale: float = 0.0
    detail: str = ""
    flags: tuple[str, ...] = ()

    def effective_weights(self) -> dict[str, float]:
        return {p.binding.measure_key: p.effective_weight for p in self.parts}

    def breakdown_total(self) -> float:
        """Sum of the contributions. Must equal `score`; a test asserts it.

        Rounded to the same precision as `score` deliberately. A breakdown that
        reconciles only at a precision neither number is reported at does not
        reconcile where anyone can see it, which is the whole complaint in
        `LEARNINGS.md` § *The composite's own breakdown did not add up*.
        """
        return round(sum(p.contribution for p in self.parts),
                     self.score_decimals)


def _transform(binding: MeasureBinding, raw: Any) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if binding.transform == TRANSFORM_MINMAX:
        lo, hi = binding.range_min, binding.range_max
        if hi <= lo:
            return None
        return _clamp01((value - lo) / (hi - lo))
    return value


def evaluate(recipe: Recipe, ref: C.EpisodeRef,
             config: dict[str, Any] | None = None) -> Evaluation:
    """Apply *recipe* to one episode.

    Resolution goes through `constructs.resolve`, so every refusal that module
    makes is inherited — a method that was not run, a cached number produced by
    a different tool, a hand-coding sheet with no recorded window. On top of
    those, this adds the refusal that makes pinning real: a part whose PINNED
    parameters do not match the parameters that produced the cached number is
    refused, because that number is not what this recipe describes.
    """
    parts: list[EvaluatedPart] = []
    flags: list[str] = []

    for binding in recipe.bindings:
        measure = C.get_measure(binding.measure_key)
        name = measure.name if measure else binding.measure_key
        resolved = C.resolve(binding.measure_key, binding.method_key, ref, config)

        if resolved.flag and resolved.flag not in flags:
            flags.append(resolved.flag)

        if not resolved.ok:
            parts.append(EvaluatedPart(
                binding=binding, measure_name=name, resolved=resolved,
                status=resolved.status, detail=resolved.detail))
            continue

        mismatched = {
            k: (v, resolved.parameters.get(k))
            for k, v in binding.parameters.items()
            if k in resolved.parameters and resolved.parameters[k] != v
        }
        if mismatched:
            described = "; ".join(
                f"{k}: recipe pins {pin}, this result was measured at {got}"
                for k, (pin, got) in sorted(mismatched.items()))
            parts.append(EvaluatedPart(
                binding=binding, measure_name=name, resolved=resolved,
                status=PARAMS_DIFFER, raw=resolved.value, detail=(
                    f"{described}. The cached number is real, but it is not "
                    f"what this recipe operationalizes — re-analyse the "
                    f"episode with the pinned parameters.")))
            continue

        transformed = _transform(binding, resolved.value)
        if transformed is None:
            parts.append(EvaluatedPart(
                binding=binding, measure_name=name, resolved=resolved,
                status=C.NO_VALUE, raw=resolved.value, detail=(
                    f"{resolved.value!r} could not be transformed by "
                    f"{binding.transform}.")))
            continue

        parts.append(EvaluatedPart(
            binding=binding, measure_name=name, resolved=resolved,
            status=C.MEASURED, raw=resolved.value, transformed=transformed))

    missing = [p for p in parts if not p.ok]
    refusing = [p for p in missing if p.binding.missing == MISSING_REFUSE]

    base = dict(recipe_id=recipe.id, recipe_name=recipe.name,
                version=recipe.version, content_hash=recipe.content_hash(),
                citation=recipe.citation(), construct_key=recipe.construct_key,
                parts=tuple(parts), flags=tuple(flags),
                score_decimals=recipe.score_decimals)

    if refusing:
        names = ", ".join(sorted(p.measure_name for p in refusing))
        return Evaluation(**base, status=REFUSED, score=None, detail=(
            f"No score: {names} did not resolve, and this recipe's "
            f"missing-data policy for it is 'refuse'. A composite missing one "
            f"of its parts is not that composite."))

    present = [p for p in parts if p.ok]
    if not present:
        return Evaluation(**base, status=REFUSED, score=None, detail=(
            "No score: none of this recipe's measures resolved for this "
            "episode."))

    if sum(p.binding.weight for p in present) <= 0:
        # A brand-new recipe has every weight at zero until the researcher
        # sets them. Summing that gives 0.0, which is a real number in the
        # score's own range and reads as "measured, and very low" — the exact
        # plausible-wrong-number shape this project keeps having to correct.
        # There is no composite here yet; say so.
        return Evaluation(**base, status=REFUSED, score=None, detail=(
            "No score: every weight in this recipe is zero, so there is "
            "nothing to combine. A total of 0.0 would look like a measured "
            "score rather than an unset one. Set the weights first."))

    redistributed = sum(p.binding.weight for p in missing
                        if p.binding.missing == MISSING_REDISTRIBUTE)
    present_weight = sum(p.binding.weight for p in present)

    scored: list[EvaluatedPart] = []
    for part in parts:
        if not part.ok:
            scored.append(part)
            continue
        weight = part.binding.weight
        if redistributed > 0 and present_weight > 0:
            weight += redistributed * (part.binding.weight / present_weight)
        scored.append(EvaluatedPart(
            binding=part.binding, measure_name=part.measure_name,
            resolved=part.resolved, status=part.status, raw=part.raw,
            transformed=part.transformed, effective_weight=weight,
            contribution=weight * (part.transformed or 0.0)))

    base["parts"] = tuple(scored)
    scale = sum(p.effective_weight for p in scored if p.ok)
    score = sum(p.contribution for p in scored if p.ok)
    if recipe.clamp_score:
        score = _clamp01(score)

    omitted = [p for p in scored if not p.ok
               and p.binding.missing == MISSING_OMIT]
    detail = ""
    if omitted:
        names = ", ".join(sorted(p.measure_name for p in omitted))
        detail = (
            f"{names} did not resolve and was omitted without redistributing "
            f"its weight, so this score sits on a scale of {scale:.4g}, not "
            f"{recipe.total_weight():.4g}. It is not comparable with a "
            f"complete score without saying so.")

    return Evaluation(**base,
                      status=PARTIAL if missing else COMPLETE,
                      score=round(score, recipe.score_decimals),
                      scale=round(scale, SCORE_DECIMALS),
                      detail=detail)


# ---------------------------------------------------------------------------
# Storage — following analyzer/pipeline_graph.py's conventions
# ---------------------------------------------------------------------------

def recipes_dir(root: Path | None = None) -> Path:
    """Where recipes live: with the library, so they travel with the data.

    Same shape and same fallback as `pipeline_graph.pipelines_dir`, and
    `save_recipe` re-homes for the same reason that one has to.
    """
    if root:
        return Path(root) / ".analysis" / "recipes"
    return _base_dir() / "recipes"


def _safe_stem(name: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip() or "recipe"
    return stem[:60]


VIEW_SUFFIX = ".view.json"


def list_recipes(root: Path | None = None) -> list[Recipe]:
    """Every saved recipe, newest first. Unreadable files are skipped.

    Layout sidecars are skipped BY NAME rather than left to fail parsing:
    `Recipe.from_dict` is deliberately permissive — it has to be, so an
    imported recipe naming a detector this install lacks stays readable — so a
    sidecar would not raise. It would parse into a nameless recipe over no
    construct and appear in the list as a real one.
    """
    d = recipes_dir(root)
    if not d.is_dir():
        return []
    out: list[Recipe] = []
    for p in sorted((q for q in d.glob("*.json")
                     if not q.name.endswith(VIEW_SUFFIX)),
                    key=lambda q: q.stat().st_mtime, reverse=True):
        try:
            out.append(Recipe.from_dict(
                json.loads(p.read_text(encoding="utf-8")), path=p))
        except Exception:
            continue
    return out


def save_recipe(recipe: Recipe, root: Path | None = None) -> Path:
    """Write *recipe* into *root*'s recipes folder, re-homing it if needed.

    Re-homing, atomic write and move-not-copy are all carried over from
    `pipeline_graph.save_doc`, where they exist because a document first saved
    before a library root was known kept being written to the application
    folder while the loader only ever read the library's — it saved fine and
    reloaded as nothing. A recipe has exactly the same lifecycle.

    Refuses to overwrite a locked recipe: the shipped composite's numbers are
    what every published score was computed under. Duplicate it and edit the
    copy.
    """
    # Refused on the LOCK alone. This used to also require an existing file,
    # which made the guard miss the case it exists for: the shipped composite
    # is generated rather than loaded, so its `path` is None and a save would
    # have been accepted, writing a stored copy of a recipe whose whole point
    # is that it is derived from the config in force. That copy would then sit
    # in the library going stale the next time a ceiling was retuned. Found by
    # driving canvas authoring against a real library and trying it.
    if recipe.locked:
        raise PermissionError(
            f"{recipe.name} is locked because results already depend on it. "
            f"Duplicate it and edit the copy.")

    # Version 1 is the recipe AS FIRST SAVED. A recipe is normally created,
    # then configured (transforms, ranges, weights), then saved, so the hash
    # recorded at creation is a snapshot of a half-built object that was never
    # citable — nobody can cite a version that never left memory. Finalising it
    # here keeps that editing from showing up as a phantom v2. Only ever while
    # the recipe is still at v1 with its single creation record.
    if recipe.version == 1 and len(recipe.history) == 1:
        recipe.history[0].content_hash = recipe.content_hash()

    d = recipes_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    previous = recipe.path
    if recipe.path is None or recipe.path.parent != d:
        recipe.path = d / f"{_safe_stem(recipe.name)}_{recipe.id}.json"
    tmp = recipe.path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(recipe.to_dict(), indent=2), encoding="utf-8")
    tmp.replace(recipe.path)                 # atomic; never a half-written file
    if previous is not None and previous != recipe.path and previous.exists():
        # The layout follows the recipe. `view_path` derives its folder from
        # `recipe.path`, so a re-homed recipe would otherwise look to the new
        # folder while its arrangement sat in the old one — the same silent loss
        # re-homing exists to prevent, one file over.
        old_view = previous.parent / f"{recipe.id}{VIEW_SUFFIX}"
        if old_view.exists():
            try:
                old_view.replace(recipe.path.parent / f"{recipe.id}{VIEW_SUFFIX}")
            except OSError:                                   # pragma: no cover
                pass
        try:
            previous.unlink()
        except OSError:
            pass
    return recipe.path


def load_recipe(path: Path) -> Recipe:
    return Recipe.from_dict(json.loads(Path(path).read_text(encoding="utf-8")),
                            path=Path(path))


def delete_recipe(recipe: Recipe) -> None:
    if recipe.locked:
        raise PermissionError(f"{recipe.name} is locked and cannot be deleted.")
    if recipe.path and recipe.path.exists():
        recipe.path.unlink()
    # The layout goes with the recipe it describes. A stranded sidecar would be
    # claimed by nothing, and — because the key is the recipe id — could be
    # re-adopted by a later recipe only if that id were reused, which it is not.
    delete_view(recipe)
    recipe.path = None


# ---------------------------------------------------------------------------
# The layout sidecar — where the boxes sit, and nothing else
# ---------------------------------------------------------------------------
# `<recipe id>.view.json`, beside the recipe, deleted with it, and NEVER inside
# the recipe file or `content_hash()`. `DECISIONS.md` § *Authoring on the
# canvas*, decision 3, and the reasoning is worth keeping next to the code:
#
#   * Dragging a box must not create a version or demand a written reason. A
#     separate file gets that by construction rather than by remembering to
#     exclude a block from `canonical()`.
#   * `save_recipe` REFUSES the shipped composite. A layout stored inside the
#     recipe file therefore could not be saved at all for the one diagram most
#     likely to become a methods figure. The sidecar can, and does.
#
# A missing sidecar means auto-layout. That is the normal state, not a broken
# one, so nothing here reports its absence as a problem.

VIEW_SCHEMA_VERSION = 1


def view_path(recipe: Recipe, root: Path | None = None) -> Path:
    """Where *recipe*'s layout lives — beside the recipe wherever that is.

    Derived from `recipe.path` when the recipe has one, so a recipe re-homed by
    `save_recipe` does not leave its layout in the old folder. Falls back to
    `recipes_dir(root)`, which is where a generated recipe (the shipped
    composite) belongs and where a saved one would land.
    """
    d = recipe.path.parent if recipe.path is not None else recipes_dir(root)
    return d / f"{recipe.id}{VIEW_SUFFIX}"


def load_view(recipe: Recipe, root: Path | None = None) -> dict[str, tuple[float, float]]:
    """Stored node positions, keyed by the canvas's own node keys.

    Returns {} for a missing, unreadable or malformed file, and skips any
    single entry that is not a numeric pair. A layout is a convenience: a bad
    one must degrade to auto-layout rather than take the diagram down, and it
    can never change a number.
    """
    p = view_path(recipe, root)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, tuple[float, float]] = {}
    for key, value in (data.get("nodes") or {}).items():
        try:
            x, y = value
            out[str(key)] = (float(x), float(y))
        except (TypeError, ValueError):
            continue
    return out


def save_view(recipe: Recipe, positions: dict[str, tuple[float, float]],
              root: Path | None = None) -> Path:
    """Write *positions* for *recipe*. Deliberately no lock check.

    `save_recipe` refuses a locked recipe because its numbers are what
    published scores were computed under. A layout is not one of those numbers —
    it enters no hash, no citation and no export — so refusing here would
    protect nothing and would lose the arrangement of the very diagram the
    sidecar exists for.
    """
    p = view_path(recipe, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": VIEW_SCHEMA_VERSION,
        "recipe": recipe.id,
        "recipe_name": recipe.name,          # for a human reading the folder
        "modified": str(date.today()),
        "nodes": {str(k): [float(v[0]), float(v[1])]
                  for k, v in positions.items()},
    }
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(p)                           # atomic; never a half-written file
    return p


def delete_view(recipe: Recipe, root: Path | None = None) -> None:
    p = view_path(recipe, root)
    if p.exists():
        try:
            p.unlink()
        except OSError:                                       # pragma: no cover
            pass


def duplicate_recipe(recipe: Recipe, new_name: str | None = None) -> Recipe:
    """Copy with a fresh id, unlocked, and its history restarted.

    The history is NOT carried over: it records versions of the original
    operationalization, and attaching it to a new recipe would let a copy claim
    a provenance it does not have. The first record names the source.
    """
    copy = Recipe.from_dict(recipe.to_dict())
    copy.id = _new_id("r")
    copy.name = new_name or f"{recipe.name} copy"
    copy.path = None
    copy.locked = False
    copy.version = 1
    # The notes are carried over, because the most important thing they can
    # contain is a caveat about what the operationalization does not justify —
    # the shipped composite's "these defaults are underived" is exactly that,
    # and a copy that quietly drops it is worse than one with a stale sentence.
    # But a locked recipe's notes say it is locked, and the copy is not, so the
    # copy says which it is rather than inheriting a false claim.
    if recipe.locked:
        copy.notes = (
            f"Copied from {recipe.citation()}, which is locked. THIS COPY IS "
            f"NOT LOCKED and can be edited freely — nothing published depends "
            f"on it. The original's notes follow, and any caveat in them "
            f"about what the operationalization does not justify still "
            f"applies here.\n\n{recipe.notes}").strip()
    copy.history = [VersionRecord(
        version=1, content_hash=copy.content_hash(), created=str(date.today()),
        reason=f"duplicated from {recipe.citation()}",
        changes=[])]
    return copy


def unique_name(existing: list[str], base: str = "New recipe") -> str:
    if base not in existing:
        return base
    i = 2
    while f"{base} {i}" in existing:
        i += 1
    return f"{base} {i}"


# ---------------------------------------------------------------------------
# Export / import
# ---------------------------------------------------------------------------

def export_recipe(recipe: Recipe) -> dict[str, Any]:
    """A self-describing form, readable on a machine whose registry differs.

    The stored form references measures and methods by key, which is right for
    this install and useless to another one that does not have them. So the
    export carries the human-readable descriptions ALONGSIDE the keys —
    construct definition, measure names, units, method labels and statuses —
    so a reader can tell what a reference meant even when it cannot be
    resolved. `MEASUREMENT_MODEL.md` §4.7.

    The descriptions are documentation, not a fallback: `import_recipe` never
    reconstructs a missing method from them.
    """
    payload = recipe.to_dict()
    construct = C.get_construct(recipe.construct_key)
    payload["exported"] = str(date.today())
    payload["describes"] = {
        "construct": {
            "key": recipe.construct_key,
            "name": construct.name if construct else recipe.construct_key,
            "definition": construct.definition if construct else "",
            "grounding": construct.grounding if construct else "",
            # Aspects and the hash travel too. A researcher's own construct
            # does NOT follow its recipe to another install — constructs live
            # with the library — so this description is the only account of it
            # the receiving machine will ever have. The hash lets that machine
            # tell "the same construct" from "a construct that happens to share
            # a key", which is the case worth catching: two libraries can both
            # hold a "narrative_complexity" meaning different things.
            "aspects": [{"key": a.key, "name": a.name,
                         "definition": a.definition}
                        for a in (construct.aspects if construct else ())],
            "content_hash": construct.content_hash() if construct else "",
            "source": construct.source if construct else "",
        },
        "bindings": [],
    }
    for binding in recipe.bindings:
        measure = C.get_measure(binding.measure_key)
        method = C.get_method(binding.measure_key, binding.method_key)
        payload["describes"]["bindings"].append({
            "measure": binding.measure_key,
            "measure_name": measure.name if measure else "",
            "unit": measure.unit if measure else "",
            "definition": measure.definition if measure else "",
            "method": binding.method_key,
            "method_label": method.label if method else "",
            "method_status": method.status if method else "",
        })
    return payload


@dataclass(frozen=True)
class ImportGap:
    """Something an imported recipe references that this install cannot resolve."""
    kind: str                 # "construct" | "measure" | "method"
    key: str
    described_as: str
    detail: str


def import_recipe(payload: dict[str, Any],
                  new_name: str | None = None) -> tuple[Recipe, list[ImportGap]]:
    """Read an exported recipe, REPORTING what it could not resolve.

    A recipe referencing a detector this install does not have is a real and
    expected case. It must produce a named, visible gap — never a default
    substitution, because a substituted method silently changes what the recipe
    operationalizes while leaving its name and version intact, which is the
    most damaging thing this module could do.

    The recipe is returned with its unresolvable bindings INTACT rather than
    stripped, so nothing is lost and re-exporting on a machine that does have
    the detector round-trips. Callers must check the gaps before evaluating;
    `evaluate` refuses an unresolvable binding on its own account.
    """
    recipe = Recipe.from_dict(payload)
    recipe.id = _new_id("r")
    recipe.path = None
    # An import arrives UNLOCKED whatever the file says. A lock is a statement
    # about THIS install — "results here already depend on this" — and no
    # published number here was produced by a recipe that has just arrived from
    # somewhere else. Carrying a foreign lock in would also make an imported
    # copy of another install's shipped composite unsaveable, which is the one
    # thing an import has to be able to do.
    recipe.locked = False
    if new_name:
        recipe.name = new_name

    described = {b.get("measure"): b
                 for b in ((payload.get("describes") or {}).get("bindings") or [])}
    gaps: list[ImportGap] = []

    described_construct = ((payload.get("describes") or {})
                           .get("construct") or {})
    construct = C.get_construct(recipe.construct_key)
    if construct is None:
        gaps.append(ImportGap(
            kind="construct", key=recipe.construct_key,
            described_as=str(described_construct.get("name")
                             or recipe.construct_key),
            detail=("This install has no such construct. The recipe is "
                    "readable but nothing here defines what it measures. "
                    "The exported description of it is kept alongside.")))
    else:
        # The key resolves — but to the same construct? Constructs live with
        # the library, so a recipe arriving from elsewhere may cite a key this
        # install also has under a different definition. That is a worse case
        # than a missing construct, because it resolves silently and reads as
        # agreement. Named as a gap for the same reason a substituted method
        # is: it changes what the recipe is understood to measure while
        # leaving its name and version intact.
        exported_hash = str(described_construct.get("content_hash") or "")
        if exported_hash and exported_hash != construct.content_hash():
            gaps.append(ImportGap(
                kind="construct_definition", key=recipe.construct_key,
                described_as=str(described_construct.get("name")
                                 or construct.name),
                detail=(f"This install defines {construct.name!r} differently "
                        f"from the install that exported this recipe "
                        f"({exported_hash} there, {construct.content_hash()} "
                        f"here). The measures and methods are unaffected; what "
                        f"differs is what they are claimed to stand in for. "
                        f"Neither definition has been changed — compare them "
                        f"and decide.")))

    for binding in recipe.bindings:
        desc = described.get(binding.measure_key) or {}
        measure = C.get_measure(binding.measure_key)
        if measure is None:
            gaps.append(ImportGap(
                kind="measure", key=binding.measure_key,
                described_as=str(desc.get("measure_name")
                                 or binding.measure_key),
                detail=("This install has no such measure, so this binding "
                        "cannot produce a number here.")))
            continue
        if C.get_method(binding.measure_key, binding.method_key) is None:
            gaps.append(ImportGap(
                kind="method", key=binding.method_key,
                described_as=str(desc.get("method_label")
                                 or binding.method_key),
                detail=(f"{measure.name} was operationalized with a method "
                        f"this install does not have — most likely a detector "
                        f"that is not installed. NOT substituted with a "
                        f"default: that would change what the recipe measures "
                        f"while keeping its name and version.")))

    return recipe, gaps
