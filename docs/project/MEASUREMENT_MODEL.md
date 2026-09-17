# CMAT — The measurement model

The next phase of CMAT: turning the pipeline from a workflow picture into a
**scientific measurement system**. This document is the plan of record for that
phase — the vocabulary, what each capability means *here* rather than in the
abstract, what already exists to build it on, and what has to be decided before
any of it is coded.

> **Status: IN BUILD. §4.1, §4.2 and §4.3 are built; §4.4 and §4.7 are partly
> built; §4.5, §4.6 and §4.8–§4.10 are not.**
> Every status line in this document is maintained per capability. Do not read
> a section as a description of shipped behaviour unless its status says
> **Built**. When a capability ships, update its status here in the same commit,
> and move the description of what actually runs into `ARCHITECTURE.md`.
>
> **§7's six open decisions are answered** (2026-08-16) and are recorded in
> `DECISIONS.md` § *The measurement model's six shaping decisions, answered*.
> §7 below now states the answers, not the questions.

---

## 1. Why this exists

`ARCHITECTURE.md` §8.1a records the gap this phase closes, and it is worth
quoting because it was written before this phase was planned:

> The theoretical grounding is named — Huston & Wright's formal features,
> Lang's LC4MP — but **nothing maps a specific metric to a specific
> construct**, which is the step that would justify [the composite's weights
> and ceilings].

CMAT today measures things well and records how it measured them. What it
cannot yet express is the step *before* measurement: **what the researcher
thinks they are measuring, and why these numbers stand in for it.**

Pacing is not a value stored in an MP4. It is a theoretical construct, and
`cuts_per_min` is one operationalization of it — produced by one detector, at
one threshold, over one sampling window. A tool that presents `cuts_per_min`
as "the pacing" has silently made a scientific decision on the researcher's
behalf and hidden it in an algorithm.

The rule this phase is built to satisfy:

> CMAT should never imply *"Transitions = Algorithm X"*. It should say
> *"Transitions have been operationalized using Method X with Parameters Y"* —
> and let the researcher choose a different X.

Two consequences that shape everything below:

- **Where several defensible methods exist, CMAT offers the choice** rather
  than picking one and calling it the measurement. Automated detector A,
  automated detector B, and human coding are three methods for one measure,
  and none of them is privileged by being the default.
- **Automated is not more valid than hand coding.** `CLAUDE.md` §3 already
  says hand coding is a measurement in its own right. The measurement model
  has to encode that, not merely repeat it in prose.

## 2. The vocabulary

Six words. They are additive to `CLAUDE.md` §3, not a replacement for it — the
stage names (Sampling, Selection, Measurement, Validation, Results) still name
the *workflow*. These name the *operationalization*.

| Term | Means | Example |
|---|---|---|
| **Construct** | The theoretical thing being studied. Not observable, not in the file. | Pacing |
| **Aspect** | A facet of a construct, when one is needed to keep measures honest. | Visual pacing; linguistic pacing |
| **Measure** | An observable quantity offered as an operationalization of a construct. | Hard cuts per minute |
| **Method** | A concrete implementation that produces a measure's value, with its parameters. | PySceneDetect ContentDetector at threshold 27; TransNetV2 at 0.5; hand coding |
| **Recipe** | A saved, named, versioned operationalization: measures, methods, parameters, transformations, weighting, missing-data behaviour. | "Pacing — conservative, hand-validated" |
| **Recipe version** | An immutable record of what a recipe was at a point in time, with what changed and why. | v3, 2026-08-20 |

**A recipe is not a preset.** A preset is a bundle of settings. A recipe is a
claim about how a construct was operationalized, and it must be inspectable
down to the parameter — the point is not to hide the settings behind a name but
to make the whole choice citable as one object.

### Two pipelines, both real, and they are not the same pipeline

`ROADMAP.md` § *Public positioning* already names three views of one research
process, and this phase builds the second:

| View | Chain | Answers |
|---|---|---|
| Study workflow | Sampling → Selection → Measurement → Validation → Results | "What are the stages of my study?" |
| **Measurement** | **Construct → Aspect → Measure → Method → Raw measurement → Transformation → Composite** | **"How did I operationalize what I wanted to study?"** |
| Provenance | Source media → Observation → Transformation → Composite → Result | "Where did this number come from?" |

Say **stage** for the first, **measure/method** for the second. The word
*Measurement* is already taken by the stage; use **measure** for the quantity
and **method** for the implementation, and never use "measurement" loosely when
one of the two precise words will do.

### How the vocabulary maps onto what is already in the engine

This phase does **not** start from nothing, and it must not build a parallel
model beside the one that already works.

| Model term | Where it lives today | Gap |
|---|---|---|
| Construct | **Nowhere.** | The whole gap — see §1 |
| Aspect | Nowhere | Same |
| Measure | Implicit, in `analyzer/schema.py`'s field names (`metrics.scene_pacing.cuts_per_min`) and in `MeasurementSpec.feeds` | Never named as a first-class object; no definition, unit, or construct link |
| Method | `analyzer/measurements.py` — `ToolSpec`, with `ParamSpec` parameters and a `status` (validated / experimental / unvalidated) | Hand coding is not represented as a method at all, though `validation.manual_pacing_metrics()` computes hand-coded counterparts and already documents which of them are engine-comparable |
| Parameters | `ParamSpec`, with coercion and bounds | Fine as-is |
| Recipe | Partially, as `config.json` presets + the `measurements` block | Not named, not versioned, not portable, not per-construct |
| Version | `measurement_fingerprint()` — a hash of the measurement settings | A hash detects *that* something changed. It cannot say what, when, or why |
| Dependency | Implicit in `cache.is_stale()` (measurement settings → cached results) | One hop only, and only for the automated cache |

**The measurement registry is the foundation, not a competitor.** Anything that
enumerates methods must read `analyzer/measurements.py` rather than restate it —
that is `LEARNINGS.md` shape 3, and this phase is exactly where a second list of
detectors would get written by accident. A detector added to the registry must
appear as an available method with no other edit.

## 3. What already exists to build on

Read this before designing any of §4. Most of these were built for another
reason and are load-bearing here.

| Existing | What it gives this phase |
|---|---|
| `analyzer/measurements.py` | The method registry: tools per measurement, typed parameters with bounds, per-tool validation status, `fingerprint_payload()`, `diff_fingerprints()` (already produces human-readable change lists), `ungraded_measurements()` |
| `analyzer/cache.py` | `is_stale()` and `stale_entries()` — the existing, working staleness check for one dependency edge, including the deliberate grandfathering rule for results written before fingerprinting |
| `analyzer/validation.py` | `manual_pacing_metrics()` — hand coding's counterpart values, and, importantly, an explicit split between the fields that **are** comparable to the engine and the fields that have no automated counterpart. Method comparison must not re-derive that distinction; it must read it |
| `analyzer/event_coding.py` | `compute_event_metrics()`, inter-coder agreement, and the publish guard that refuses to report an uncoded episode as a zero rate |
| `analyzer/validation.py` comparison scoring | Tool-vs-human agreement per detector, already reported per detector rather than blended |
| `analyzer/trials.py` | The run registry — a recorded sampling plus coding pass, already keyed by detector tag |
| `analyzer/provenance.py` | The single source for what leaves the tool as an accuracy claim; `provenance_schema` versioning already exists there |
| `analyzer/sampler.py` + `analyzer/selection.py` | Sampling and selection are already recorded as manifests on disk — the corpus half of a reproducibility report is largely already written |
| `analyzer/pipeline_graph.py` | Documents that round-trip through plain dicts, are saved atomically, re-home themselves into the library, and duplicate with fresh ids. Recipe storage should follow this file's conventions rather than invent new ones |
| `analyzer/metrics_sensory.py` | `effective_weights()` — the existing answer to "the nominal weights are not what the components contribute" |

## 4. The capabilities, in build order

Build in this order. Later items depend on earlier ones being *sound*, not
merely present. Do not skip to reports and exports before the model underneath
them is right — an export of a wrong model is a faster way to publish a wrong
claim, not a feature.

### 4.1 The data model — constructs, measures, methods, recipes, versions
**Status: BUILT 2026-08-16**, in `analyzer/constructs.py`, for the
construct / aspect / measure / method half. **Recipes and versions are not
built** — they are §4.2 and §4.4 and depend on this being sound first.

> **Extended 2026-08-16: "researchers add their own" now exists.** This
> section's requirement that CMAT "ships a small starting set; researchers add
> their own" was unbuilt until the construct store — constructs were seven
> hardcoded tuples. A researcher's own construct is now saved in
> `<root>/.analysis/constructs/`, is content-hashed over its **meaning**
> (definition, grounding, aspects — not its name), and is returned by the
> ordinary `get_construct` lookup, so nothing downstream needed editing.
> `tests/test_construct_store.py` (33 tests). The four decisions this required
> are in `DECISIONS.md` § *Authoring on the canvas*.
>
> **Extended again 2026-08-16: the door exists.** The store had no screen until
> `ui/construct_editor.py` — `ConstructEditor` and `ConstructPicker`, reached
> from the Constructs tab's **Constructs…** button and from the Recipes New
> menu — with `tests/test_ui_construct_editor.py` (12 tests). A construct is
> created, renamed, redefined, duplicated from a shipped one and deleted from
> the interface, and the dialog **states what a redefinition will do**, naming
> the recipes that will report it, before it does it.
>
> **Measures remain NOT user-definable, by rule rather than by omission.** A
> construct is a theoretical claim; a measure must resolve to a real number
> from real data, and one that does not is `LEARNINGS.md` shape 2 — the defect
> this phase exists to remove. A researcher's own construct is operationalized
> by binding shipped measures to it in a recipe, exactly as the shipped
> composite binds six measures owned by five other constructs.
>
> **A redefinition is reported, not folded into the recipe's hash.** A recipe
> records the construct hash it was authored against, beside its own content
> hash and deliberately outside `canonical()`: inside, editing one construct
> would version every recipe citing it without the reason `bump_version`
> requires. `construct_divergence()` reports current / redefined / missing /
> unknown, and an unrecorded baseline is **unknown, not current** —
> `cache.is_stale`'s grandfathering rule carried forward.

What runs: **seven constructs and sixteen measures**, and methods generated
from `analyzer/measurements.py` — one per `ToolSpec`, plus hand coding as a
first-class method. Pacing (with visual-transitions, rhythm and
scene-structure aspects) and Speech shipped first; Colour, Motion, Luminance
change, Loudness and Sensory load arrived with §4.3's composite. Sensory load
has **no measures of its own** — it is operationalized by a recipe drawing on
the others.

A measure may gate on an availability flag (`AutomatedSource.available_path`):
`audio.rms_mean` counts only when `audio.available` is true, and the speech
measures only when `speech.available` is, because the 0.0 otherwise sitting in
those blocks is a schema default rather than a measurement. `resolve(measure, method, episode)` returns that method's
real number or a refusal naming its reason; `resolve_measure()` returns one
row per method and offers no aggregate over them. The seven refusal states are
in the module's header. Verified against real cached episodes and real coding
sheets in this working copy — every automated and hand-coded value reproduced
the existing engine and `manual_pacing_metrics()` paths exactly, and the run
found a real defect in the data (`LEARNINGS.md` § *A coded segment divided by
the whole runtime*).

> **Superseded, same day.** When §4.1 first shipped it deliberately held to
> two constructs per §4.3's instruction not to generalize past two, leaving
> saturation, contrast, motion, flashing and audio unexpressed. §4.3's
> composite brought all five in. The instruction was right and was followed —
> pacing and speech were finished before anything else was attempted — and
> this note is kept so the sequencing is legible rather than looking like the
> limit was ignored.

The original specification of this capability follows, unchanged.

Define, in `analyzer/`, with zero GUI imports (`CLAUDE.md` §2.4):

- **Constructs** with a name, a definition, and an honest grounding note. CMAT
  ships a small starting set; researchers add their own. A shipped construct is
  a starting point, never a claim that CMAT has validated that mapping.
- **Measures**, each naming: its construct, its aspect where one is needed, its
  unit, its definition, and — critically — **where its value actually comes
  from**, as a real path into an `EpisodeResult` or a real key of a hand-coding
  metrics dict. A measure that cannot resolve to a number is a label, and
  `LEARNINGS.md` shape 2 is exactly the failure of shipping one.
- **Methods**, derived from the existing registry wherever the method is
  automated, plus explicit hand-coding methods. A method carries its status by
  *reading* the registry, never by restating it.
- **Recipes and versions**, per §4.2 and §4.4.

**Done looks like:** given a real cached episode and a real coding sheet from
this working copy, the model can name a construct, list its measures, list each
measure's available methods, and return the actual number each method produced
— including refusing to return one where the method was not run.

**Verify by:** resolving every shipped measure against a real cached result and
a real hand-coding sheet, and printing the values beside the numbers the
existing report shows for the same episode. Not by asserting the registry has
the right number of entries.

### 4.2 Recipe save / load
**Status: BUILT 2026-08-16**, in `analyzer/recipes.py`, with
`tests/test_recipes.py` (34 tests).

What runs: `Recipe` over `MeasureBinding`s, each carrying its measure, method,
**pinned parameters**, transform and reference range, weight and missing-data
policy. Create (`new_recipe`, pinning from the live config), save, load, list,
duplicate (fresh id, unlocked, history not inherited), delete, export, import.
Storage is `<root>/.analysis/recipes/`, following `pipeline_graph.py`'s
conventions including its re-homing rule. `evaluate()` applies a recipe to an
episode and returns every part — including the refused ones — with the
**effective** weights that produced the score, so the breakdown reconciles with
the headline.

**Pinning is enforced, not merely stored**, which is what makes decision 4 real
rather than decorative:
- `evaluate()` refuses a part whose pinned parameters differ from the
  parameters that actually produced the cached number. The number is real; it
  is not what the recipe operationalizes.
- `divergences()` reports where a recipe's pinned values differ from the live
  Measurement settings — the accepted cost of pinning, as a function a screen
  is expected to call.
- Dependencies that change a bound measure are pinned too. Motion and colour
  carry the shared frame-sampling tool and sample rate as namespaced parameters,
  so a sampling-rate change cannot leave an old recipe appearing current.

**Verified as this section asks**: a recipe saved in one library, moved, and
reopened in another resolved to identical scores for three real episodes, read
back from the written JSON each time. Verification also found a real defect —
see `LEARNINGS.md` § *Attribution read off a rescored copy*.

**Authoring shipped 2026-08-16** — the Constructs tab's **Edit** mode. A
recipe's bindings are added and removed from a palette of shipped measures,
each with its method and weight; a changed operationalization goes through
`bump_version` and will not save without a reason; the shipped composite's
bindings are fixed and it says why. Node positions persist in
`<recipe id>.view.json` beside the recipe — `save_view` / `load_view` /
`delete_view` — never inside `content_hash()`, and allowed for the locked
composite because a layout is not part of the operationalization. See
`ARCHITECTURE.md` §3c.

**A visual view shipped 2026-08-16** — the **Constructs tab**
(`ui/constructs_tab.py`), beside Pipeline, drawing a recipe as the graph it
already is. Read-only when it shipped; see the paragraph above. It is the §2
table's *measurement* row given a screen,
and it is where "nominal weights are not effective weights" (`ARCHITECTURE.md`
§8.1a) finally became something you can see. See `ARCHITECTURE.md` §3c.

**The editor shipped 2026-08-16** — `ui/recipes.py`, reached from
**File → Recipes…**. It lists recipes (the shipped composite first, generated
rather than stored), shows each one down to the pinned parameter, reports
divergences, edits method / transform / range / weight / missing-data policy,
records a version with its reason, applies a recipe to the current scope on a
worker thread, and duplicates / deletes / exports / imports. See
`ARCHITECTURE.md` §3b.

The original specification of this capability follows, unchanged.

Create, save, duplicate, modify, reuse in another pipeline, export, import.
Recipes stay inspectable: every screen that names a recipe can show what it
actually does, down to the parameter values.

A recipe stores: construct, measures, methods, parameters, transformation and
normalization settings, weighting rules, missing-data behaviour, validation
linkage where relevant, and version information.

**Done looks like:** a recipe saved in one pipeline, reopened in another, still
resolves to the same numbers.

**Verify by:** reading the written file, not the dialog that wrote it.

### 4.3 One or two worked measurement examples
**Status: BUILT 2026-08-16.** Pacing and speech, then the composite.

**Pacing**, completely: five measures across three aspects, every registry
detector as a method, and hand coding as a first-class method — including
`transitions_per_min` and the hand-coded scene-change rate, both marked as
having **no automated counterpart** rather than quietly compared. The two
scene-change measures are deliberately separate objects because the engine and
the hand-coding analysis emit the same field name for different quantities.

**Speech**, carrying the rule that tests the model's expressiveness: words per
minute declares `reported_with = ("speech_density",)`, and the pairing is
declared from both sides so a screen cannot obey it in one direction only.

**Then the composite**, which was the real test: `recipes.shipped_composite()`
expresses the existing sensory-load score — six measures across five
constructs, their ceilings, weights, additive form, rounding, clamping and
audio-redistribution rule — and **reproduces `compute_sensory_load` exactly**
on all 14 cached episodes in the author's library and on the no-audio path no
real episode there exercises. That is what says the model is expressive
enough: not that it can hold pacing, but that it can hold a composite the
project already depends on without changing it.

The original specification of this capability follows, unchanged.

Do **pacing** first, and completely: several measures, several automated
methods from the registry, and hand coding as a first-class method — including
the measures that hand coding can produce and automation cannot, marked as
having no automated counterpart rather than quietly compared anyway.

**Speech** is the natural second, because it carries a rule the model must be
able to express: words per minute is reported with speech density or not at all
(`CLAUDE.md` §2.2). If the model cannot represent "these two measures are
reported together", the model is not yet expressive enough.

Do not generalize past two until both are genuinely right.

### 4.4 Version tracking
**Status: PARTLY BUILT 2026-08-16** — recipe versioning is built; the
"which results depend on the old version, and what is now stale" half is
§4.5 and is not.

What runs: `VersionRecord` (version, content hash, date, **reason**, derived
changes) stored in the recipe file, `diff_recipes()` producing the
human-readable change list, `bump_version()` which **requires a reason** and
returns None when the operationalization did not change — so **renaming is not
a new version** by arithmetic rather than by convention. `citation()` returns
the friendly version plus the content hash, per decision 6.

Version 1 is the recipe **as first saved**: `save_recipe` finalises the v1
hash while the recipe is still at v1, because a recipe is normally created,
then configured, then saved, and nobody can cite a version that never left
memory.

A version answers: what changed, when, why, which results depend on the old
version, and what is now stale. Versioning applies to recipes, measures,
constructs, pipeline configurations, validation settings, composites, and
exports where relevant.

**The version history lives in the data model, not in the interface.** A
version visible only on screen is a label; the file has to carry it, or nothing
downstream can depend on it.

Two things already point the way: `diff_fingerprints()` produces exactly the
kind of human-readable change list a version record needs, and
`measurement_fingerprint()` shows the shape of content-addressing. What neither
has is *when* and *why* — a version record must capture the researcher's reason
for the change, because the record of why a number moved is itself paper
material.

**Renaming a recipe is not a new version.** Version on the operationalization's
content; a name is not part of the measurement.

### 4.5 Dependency invalidation and stale detection
**Status: not built.** (One edge of it — measurement settings → cached
episode results — is built, in `cache.is_stale()`.)

Downstream results depend on upstream decisions: a changed threshold, a swapped
method, a re-weighted composite, changed exclusions, changed normalization,
changed validation criteria. CMAT must be able to show what changed, what
depends on it, what is now stale, and what needs recomputing.

Stale status is stored explicitly in the data model and is obvious in the
interface. **A researcher must never have to guess whether a displayed number
still matches the current pipeline definition.**

Carry forward the existing grandfathering rule and its reasoning: results
predating a mechanism are treated as *unknown*, not as stale, and the count of
unknowns is reported beside the count of stale — the Measurement settings
dialog already does this, and it exists because "1 episode goes stale" was
sitting on top of eleven whose settings nobody knew.

**Verify by:** changing an upstream parameter and reading what the *stored*
state says, on disk, about every downstream artefact — not by checking that a
badge appeared.

### 4.6 Method comparison
**Status: not built.**

Compare defensible methods for one measure: automated detector A, automated
detector B, human coding. Compare raw outputs, disagreement patterns, agreement
statistics where appropriate, the downstream effect on composites and results,
and performance across episodes, shows, or subsamples.

**The point is not to run several methods. It is to show how the choice of
method changes the result.**

Three constraints inherited from things this project has already got wrong:

- **Never average across methods.** An aggregate over two detectors is not a
  measurement of either (`LEARNINGS.md` shape 4 — a published F1 that was two
  detectors summed). Report per method, always.
- **Never compare quantities the engine and hand coding define differently.**
  `manual_pacing_metrics()` already documents which of its fields mirror the
  engine and which count things the detector does not produce. Read that
  distinction; do not re-derive it, and do not offer a comparison it forbids.
- **A tolerance is a floor, not a free parameter.** The hand coding is quantised
  to whole seconds, so any comparison tolerance tighter than that measures the
  coding resolution rather than the method (`CLAUDE.md` §2.2).

### 4.7 Import / export of measurement specifications
**Status: PARTLY BUILT 2026-08-16** — recipes export and import; constructs,
validation configurations and composite definitions as separate portable
objects do not.

`export_recipe()` writes a self-describing form carrying human-readable
construct, measure and method descriptions **alongside** the keys, so a machine
whose registry differs can still tell what a reference meant.
`import_recipe()` returns `(recipe, gaps)` and **never substitutes a default**
for something it cannot resolve: an unresolvable binding is kept intact and
reported as a named `ImportGap`, because a substituted method changes what a
recipe measures while leaving its name and version untouched.

Constructs, recipes, methods, parameter sets, validation configurations,
composite definitions and version metadata move between projects as structured,
reproducible files — for reuse, replication, collaboration, and archival.

An exported spec must be self-describing enough to be read on a machine whose
registry differs, and an import must **report** what it could not resolve
rather than silently accepting it. A recipe that references a detector the
importing install does not have is a real and expected case; it must produce a
named, visible gap, not a default substitution.

### 4.8 Reproducibility reports
**Status: not built.**

One report describing: corpus and source media, sampling method, constructs
measured, measures used, methods and parameters, transformations, validation
setup, composite definitions, version information, key outputs, and anything
stale or recomputed.

It answers: **what exactly did CMAT do, and how was this result produced?**
This is a core scientific feature, not an optional export.

Most of the corpus half already exists on disk as sampling and selection
manifests, trial records and provenance blocks. The report should *assemble*
those, and where a section has no evidence it must say so rather than omit the
heading — a silently missing section reads as "not applicable".

### 4.9 Methods-section generation
**Status: not built.**

Draft methods text, generated from the actual saved configuration: how media
were sampled, what was operationalized and how, whether methods were automated,
hand-coded or hybrid, how validation was handled, how composites were built,
what transformations were applied, and the versioning details.

Constraints, and they are not optional here:

- **Every accuracy figure carries its qualifiers** — basis, tolerance, coder
  count, preliminary status (`CLAUDE.md` §2.2). Generated prose is the single
  easiest place in this project to publish an unqualified number.
- **Correlational language only. No causal claim about any feature.**
- **No verdict** — no appropriateness, target age, educational value or quality
  (`CLAUDE.md` §2.1).
- **It helps the researcher write; it does not replace their judgement.** The
  output is a clearly-labelled editable draft.
- **The prose is generated, and the author has said paper prose must be his
  own.** Present it as material to rewrite, never as text to paste.

### 4.10 Citation support
**Status: not built.**

A researcher can cite a recipe, a method, a pipeline version, a composite
definition, or a reproducibility report, and tie a published result back to the
exact configuration that produced it. Start simply; design for stable version
identifiers, stable references, exportable metadata, and traceability across
revisions.

## 5. Invariants

These must remain true of whatever gets built. They are the phase's acceptance
criteria as much as any feature list.

- Constructs are not raw values in media files.
- Measures are operationalizations; methods are implementations of measures.
- A construct can have several reasonable operationalizations, and CMAT does
  not rank them.
- Automated measurement is not inherently more valid than human coding.
- Validation is part of measurement, not an afterthought.
- Provenance matters. Version history matters.
- Downstream results reflect upstream changes.
- Everything above holds under `CLAUDE.md` §2 unchanged: no verdict, no causal
  language, no unqualified accuracy figure, unvalidated measures flagged
  wherever their numbers appear.

## 6. What this phase must not do

- **Do not hard-code one "correct" measurement for a construct.**
- **Do not hide parameters inside the UI**, and do not let a recipe become an
  opaque name.
- **Do not let old results silently look current.**
- **Do not put versioning in the interface without real data-model support.**
- **Do not build a generic node editor.** This is a measurement system; the
  canvas already exists and is not the thing being extended.
- **Do not overgeneralize before the specific cases work** (§4.3).
- **Do not expand into unrelated product areas while this is being built.**
  `TODO.md`'s existing items stay where they are.

## 7. The six shaping decisions — ANSWERED 2026-08-16

Answered by the author before any of §4 was written, which is what stopped the
data model being written twice. Reasoning and what was rejected are in
`DECISIONS.md` § *The measurement model's six shaping decisions, answered*;
this is the summary the rest of this document depends on.

1. **Recipes live with the library** — `<root>/.analysis/recipes/`, travelling
   with the data as pipelines do, reusing `analyzer/pipeline_graph.py`'s
   conventions including its re-homing rule. Portability across projects comes
   from §4.7's export/import, not from the storage location.
2. **The existing composite becomes a recipe, locked.** "Sensory load (as
   shipped)" must reproduce today's numbers exactly and is not editable in
   place. Expressing it is not changing it; the public index depends on it,
   and its defaults remain underived.
3. **A stale flag attaches to one episode result per recipe version** — the
   unit `cache.is_stale()` already works at, so a recipe reports "12 current,
   5 stale, 3 predate fingerprinting" rather than one red light. The existing
   grandfathering rule carries forward unchanged.
4. **A recipe PINS its parameters.** Its own frozen copy of every value. The
   accepted cost: a threshold can live in two places, so **a recipe must say
   plainly when its pinned value differs from the live Measurement settings** —
   this is a requirement on §4.2, not an afterthought.
5. **Presets stay scoring-only; recipes own measurement.** Presets keep
   weights and normalization ceilings, re-scorable from cache. Recipes own
   which detector, what parameters, and the composite definition. This is the
   boundary `ARCHITECTURE.md` §3 already draws.
6. **A citable identifier is a friendly sequential version PLUS a content
   hash, both stored** — `Pacing — conservative v3 (a7f3c9d1e204)`. The
   version goes in prose; the hash proves two installs hold the same thing.

## 8. Proposed file layout

Proposed, not settled — recorded so the first implementation session has a
starting point to argue with rather than a blank page.

| File | Role | Status |
|---|---|---|
| `analyzer/constructs.py` | Construct, aspect and measure registries; resolution of a measure's value from a real result or coding sheet; **the library store for a researcher's own constructs** | **Built** 2026-08-16 |
| `analyzer/recipes.py` | Recipe and version data model, save/load/duplicate, diffing, import/export, evaluation | **Built** 2026-08-16 |
| `analyzer/staleness.py` | The dependency graph and stale computation (only if §4.5 proves too big for `cache.py`) | Not built |
| `ui/recipes.py` | The recipe editor — inspectable by construction | **Built** 2026-08-16 |
| `ui/constructs_tab.py` | The canvas: a recipe drawn, and authored | **Built** 2026-08-16 |
| `ui/construct_editor.py` | Defining a construct; the picker both screens open | **Built** 2026-08-16 |
| `tests/test_constructs.py` | Artefact-level tests: real cached episodes, real coding sheets | **Built** — 27 tests |
| `tests/test_recipes.py` | Same, for written recipe files re-read from disk | **Built** — 34 tests |
| `tests/test_construct_store.py` | Same, for written construct files and the divergence a redefinition causes | **Built** — 33 tests |
| `tests/test_ui_constructs_tab.py` | The drawn scene, and what authoring writes | **Built** — 35 tests |
| `tests/test_ui_construct_editor.py` | The construct dialog, read back off the written files | **Built** — 12 tests |

Nothing here changes `analyzer/measurements.py`'s role. It stays the registry
of methods and parameters; the new modules read it.

---

*Sources: the phase specification agreed with the project author (2026-08-16);
`design/CMAT_PIPELINE_INTERACTION_MODEL.md`, which named the
construct/aspect/measure/method chain first and is an input, not authority;
and `ARCHITECTURE.md` §8.1a, which identified the gap.*
