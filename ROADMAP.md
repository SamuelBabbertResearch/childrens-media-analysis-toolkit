# CMAT Roadmap

Direction and priorities. For what has already been built and validated, see
[`validation/VALIDATION_LOG.md`](validation/VALIDATION_LOG.md).

---

## Guiding identity

CMAT is a **general toolkit for analyzing children's media**, not a fixed
scoring system. Two co-equal halves:

1. **Automated audio-visual measurement** — a customizable pipeline where the
   researcher chooses the measurements, the tools that produce them, and how
   they combine.
2. **Structured hand-coding** — pacing (transitions, scene changes) and
   **fantastical events**, the two variables the current literature is actually
   arguing about.

The composite score is a *lens the user configures*, not a claim CMAT makes.
CMAT's job is to make measurement transparent, customizable, and validated —
not to declare what "sensory load" is.

---

## Positioning against existing tools

The nearest neighbours are **QualCoder**, BORIS, ELAN, Datavyu, and NVivo:
mature qualitative-coding environments. The temptation is to compete with them
feature for feature. That is the wrong move, and worth writing down so it does
not get relitigated.

**Why not to compete head-on.** QualCoder is a general-purpose QDA application
— text, image, audio and video coding, hierarchical code trees, memos,
journals, cases and attributes, co-occurrence queries, REFI-QDA exchange —
built over roughly a decade with that as its entire goal. Reaching parity means
years of generic qualitative infrastructure, ending as the worse choice, while
starving the thing nothing else does.

**What none of them do.** Automated measurement of formal features; validation
of that automation against human coding on the same episodes; reproducible
sampling with manifests; measurement fingerprints that make results
comparable. A QualCoder user who wants to know whether their impression of a
show's pace matches its actual cut rate has no path at all. That gap is the
reason CMAT exists and the reason anyone cites it.

**The actual defection risk is narrower than "their coding is better".** CMAT's
A/V coding is already competitive: `gui_coding_editor.py` embeds libVLC, has a
fast pass-1 entry bar, dropdown vocabularies bound to the parser constants, and
autosave. The problem is that the coding *schemes* are hardcoded —
`_TRANSITION_CHOICES` asserted against `analyzer.validation.TRANSITION_TYPES`,
and `EVENT_TYPES` for events. Excellent for data integrity, fatal for
adoption: a researcher coding prosocial behaviour, gender representation, or
advertising breaks cannot express their scheme and has to leave. That is one
contained fix, not a decade of catch-up.

### Ordered response

1. **User-definable codebooks.** Coding schemes become data rather than Python:
   the researcher declares codes, categories, and allowed values, and the
   editor, parsers, and agreement maths all read from that declaration. Keep
   the current integrity guarantee — coded values still cannot drift from the
   declared vocabulary — but let the vocabulary be theirs. This is the only
   item that stops real defection.
2. **REFI-QDA import/export.** The QDA world's interchange standard. Turns the
   competitor into a distribution channel: code the measurement layer in CMAT,
   hand off to QualCoder/NVivo/ATLAS.ti for thematic work. "Use both" is a
   stronger story than "pick one", and CMAT is the only side that can produce
   the automated measures.
3. **Keep widening the moat** — validation, sampling, provenance, norms
   (Priorities 2 and 4 below).

### Deliberately not building

Memos, journals, code co-occurrence matrices, text-document coding, image
coding. Each is a re-implementation of something QualCoder already does better,
and none of them is why a media researcher would choose this tool.

---

## Public positioning

Folded in from `design/POSITIONING_BRIEF.md` and
`design/CMAT_GITHUB_PIPELINE_POSITIONING.md`, both now deleted — this section
is their content, not a pointer to it.

**The pipeline is the organizing metaphor, not a feature in a list.** The
README and the app should teach the same structure:
Sampling → Selection → Measurement → Validation → Results for the study,
Construct → Aspect → Measure → Method for how a construct was operationalized,
Source → Observation → Transformation → Result for where a number came from.
Do not describe CMAT as "a sampling tool + video analyzer + hand coding +
validation + exports" — describe it as one workflow that preserves the
methodological decisions between those stages.

**Identity: scientific workflow software for children's media research, not
generic AI tooling.** Avoid startup language ("AI-powered", "supercharge",
"next-gen"). The positioning line that has held up: *rigorous enough for
publication, accessible enough for an undergraduate research assistant.*
Consistent with `CLAUDE.md` §1's product principles — this is the same claim
applied to how the project presents itself externally, not a separate brand
exercise.

**Be precise about what's built.** Any public-facing description of a
not-yet-implemented capability (full provenance tracing, composite-as-data,
user-definable codebooks) must say so — "CMAT is being designed around X,"
not "CMAT provides X." Three tiers: Available now / In development / Long-term
vision. This is `CLAUDE.md` §2.2's qualifier discipline extended to marketing
copy, not a new rule.

**README structure:** lead with what CMAT is, the formal media features it can
measure, its integrated workflow, and its stimulus-only / corpus-specific
validation limits. Then explain the five-stage pipeline, provenance ("where did
this number come from?"), constructs/measures/methods, automated measurement
and human validation, research use cases, current capabilities, installation,
documentation, contribution, citation, and licence. Treat a sensory-load
composite as an optional researcher-defined operationalization after the
individual measures and their research context—not as CMAT's identity.

Not carried forward from the source documents: the SEO keyword lists and
suggested `/sampling`, `/human-coding` etc. documentation-site page structure.
Those describe a marketing site CMAT doesn't have; revisit only if one gets
built.

---

## Priority 0 — The measurement model (current phase)

**Agreed 2026-08-16 and now the top development priority.** The full plan,
build order, invariants and open decisions are in
[`MEASUREMENT_MODEL.md`](MEASUREMENT_MODEL.md); this section says only what it
is and why it displaces the priorities below.

The pipeline exists and is intuitive enough. What CMAT still cannot express is
the step *before* measurement: **what the researcher thinks they are measuring,
and why these particular numbers stand in for it.** `ARCHITECTURE.md` §8.1a
named the gap before this phase was planned — nothing maps a specific metric to
a specific construct — and it is the same gap that makes the composite's
defaults undefendable rather than merely undocumented.

Nine capabilities, in this order:

1. the data model — constructs, measures, methods, recipes, versions
2. recipe save / load
3. one or two worked measurement examples (pacing first, then speech)
4. version tracking
5. dependency invalidation and stale detection
6. method comparison
7. import / export of measurement specifications
8. reproducibility reports
9. methods-section generation, then citation support

**Scope discipline while this is being built:** no expansion into unrelated
product areas, and no jumping to the exports at the end before the model
underneath them is sound. An export of a wrong model is a faster way to publish
a wrong claim, not a feature.

**This absorbs Priority 1c below.** "Composite definition as data" is the same
idea reached from the settings side rather than the science side; its
guardrails carry over unchanged and are restated in `MEASUREMENT_MODEL.md` §5
and §6.

---

## Priority 1 — Make composites genuinely customizable

**Status: 1a and 1b are built** (`analyzer/measurements.py` registry, engine
dispatch, and the Measurement Settings editor, with cache fingerprinting so a
settings change marks affected episodes stale). **1c is not, and is now part of
Priority 0** — see `MEASUREMENT_MODEL.md`.

Today users can adjust *weights* and
normalization ranges per preset. That is the shallowest of the three axes that
actually matter, and it is not enough for the tool to be usable by other labs
running their own designs.

### 1a. Per-measurement sensitivity / threshold editing

Every measurement in the composite has detection parameters buried in config
that the user cannot reach from the UI:

| Measurement | Parameters that should be user-editable |
|---|---|
| Scene pacing | cut-detection threshold, detector choice |
| Flashing | `flashing_luminance_threshold`, `flashing_sample_fps` |
| Dissolves | `dissolve_noise_floor`, `dissolve_min_frames` |
| Scene change | `scene_change_similarity_threshold`, comparison offset |
| Motion / color | sampling rate, any future method options |

A researcher studying photosensitivity needs a different flashing threshold
than one studying pacing. Right now that means hand-editing `config.json`.
These belong in the composite editor, **saved as part of the preset**, so a
"preset" captures *how each measurement was made*, not just how the results
were weighted.

### 1b. Per-measurement tool selection

Where more than one tool can produce a measurement, the user should pick:

- Transitions: PySceneDetect ContentDetector · AdaptiveDetector · **TransNetV2**
  (optional; measured F1 0.902 vs 0.753 on the hardest coded episode)
- Flicker/saliency: CMAT's luminance-delta measure · a CIELab flicker measure
  matching the published reference implementation (planned)
- Speech: subtitle files · Whisper (with selectable model and language)

The optional-tools registry (`analyzer/optional_tools.py`) is the foundation;
what is missing is letting a composite *declare which tool produced each
component*, and recording that in the result's provenance.

### 1c. Composite definition as data

**Superseded by Priority 0 — a composite definition is a recipe.** Kept here
because the guardrails below were written first and still bind; they are
restated in `MEASUREMENT_MODEL.md` §5–§6, and the open question of whether the
*existing* composite becomes a recipe is §7 item 2 there.

Generalize a composite from a fixed metric list to a declarative spec —
components of *(metric path, tool, parameters, normalization range, weight)* —
so researchers can build their own (e.g. a saliency-only composite, or a
pacing composite using scene changes rather than raw cuts) without touching
code.

**Guardrails to build in, not bolt on:**
- The public index stays on the frozen default composite; custom composites are
  clearly labeled and never silently swapped into published data.
- Components that are unvalidated or experimental must be flagged in the editor
  and in any output that uses them.
- Missing components (no audio track, uncoded events) renormalize with explicit
  disclosure, as the current composite already does.
- Human-coded and automated channels stay separable and never silently mixed.

---

## Priority 2 — Finish the validation study

Detector thresholds cannot be tuned honestly without more coded episodes, and
composite *weights* cannot be validated by coding at all (that needs an
external criterion). See the validation log for the current state.

- Retro-label `scene_relation` on already-coded hard cuts (unlocks classifier
  tuning; no re-watching required)
- Code SpongeBob and 2+ further episodes spanning production styles
- One episode double-coded for inter-rater reliability
- Then: tune thresholds on a tuning set, report on a held-out set

---

## Priority 3 — Correctness fixes from code review

**Status: all done.** Kept here as a record of what changed and why, since each
affected numbers that would appear in a paper. Details in the validation log.

- ~~Per-type F1 was boundary detection stratified by human label, not type
  classification~~ — relabelled, with a type confusion matrix reported
- ~~Greedy matching~~ — replaced with maximum-cardinality assignment plus a
  swap refinement that minimises total offset
- ~~Manual and automated shot-length definitions differed despite a docstring
  claiming otherwise~~ — manual now includes the window edges, matching the
  engine
- ~~Cohen's kappa returned 0.0 where it is mathematically undefined~~ — returns
  None, and callers report "not defined"
- ~~Scene-classifier standoff could cross an adjacent cut on very short shots~~
  — clamped, returns `unknown` when no interior standoff exists

---

## Priority 4 — The study spine

Two independent first-use audits reached the same conclusion: the capabilities
are there but the *study* that joins them is not. A researcher can find
folders, sampling, analysis, coding, validation, and export without being able
to tell how they relate, or protect themselves from scope mistakes.

- **Cohort / study export.** One analysis-ready package — episode table, show
  table, sample membership, metadata, protocol and fingerprint columns,
  validation evidence, data dictionary, checksums — instead of exports scoped
  to whatever result happens to be selected. Currently the largest gap between
  "CMAT computed it" and "the data are in R".
- **Sampler → run handoff.** `Send Sample to CMAT` reports routing, not
  whether anything is running. Lock the manifest, queue, start, and record the
  run as one continuous flow with a single run manifest tying selected files to
  settings and outcomes.
- **Metadata as a pre-analysis stage.** Air dates and season/episode numbers
  determine sampling and chronology but are currently edited after analysis, so
  longitudinal work is built on an appendix.
- **Library import review.** Filesystem layout silently defines what a "show"
  and a "season" are. Historical and multi-part holdings do not fit that, and
  a registry-first import should be a first-class route, not a sampler option.

## Later

- CIELab flicker measure + convergent validity against the published reference
- Edge density (saliency feature from the SPECT literature)
- Multi-language Whisper, with per-language NLP resources (current language
  metrics are English-only)
- Community submission pipeline to the public index
- Per-show detector calibration profiles (only if the validation study shows
  global parameters are insufficient)
