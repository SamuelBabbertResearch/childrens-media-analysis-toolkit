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

## Priority 1 — Make composites genuinely customizable

**This is the top development priority.** Today users can adjust *weights* and
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

Tracked in the validation log; all affect numbers that would appear in a paper.

- Per-type F1 is currently boundary detection stratified by human label, not
  type classification — relabel it and report a type confusion matrix
- Replace greedy matching with maximum-cardinality assignment
- Manual and automated shot-length definitions differ despite a docstring
  claiming otherwise
- Cohen's kappa returns 0.0 where it is mathematically undefined
- Scene-classifier sampling standoff can cross an adjacent cut on very short shots

---

## Later

- CIELab flicker measure + convergent validity against the published reference
- Edge density (saliency feature from the SPECT literature)
- Multi-language Whisper, with per-language NLP resources (current language
  metrics are English-only)
- Community submission pipeline to the public index
- Per-show detector calibration profiles (only if the validation study shows
  global parameters are insufficient)
