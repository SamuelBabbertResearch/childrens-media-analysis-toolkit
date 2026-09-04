# Adult Prediction of Children's Perceived Media Pacing

## Wave 1 single-coder manual-versus-automated analysis plan — correction 04

**Document status:** AUTHORITATIVE REVISED WAVE 1 ANALYSIS PLAN  
**Decision date:** 2026-08-23  
**Manual coder:** SB01  
**Independent second coder:** Not required  
**Original selected set:** 12 clips  
**Analysis set:** 11 clips  
**Excluded clip:** W1C010  
**Replacement:** None

## Supersession and preserved provenance

This correction supersedes the Wave 1 requirements for MIA01 independent
coding, inter-coder reliability, and joint adjudication in:

- `STUDY_MANUAL_CODING_PLAN_wave1-2_method-manual_recipe-v1_2026-08-22_correction-02.md`;
- `STUDY_CALIBRATION_PLAN_wave1_method-manual-vs-automated_recipe-v1-v2_2026-08-22_correction-02.md`;
- `STUDY_WAVE1_ANALYSIS_SCOPE_method-manual-vs-automated_recipe-v1_2026-08-23_correction-03.md`; and
- `.analysis/study_workflow/wave_1_manual/WAVE1_ADJUDICATED_REFERENCE_SYSTEM_method-manual_recipe-v1_2026-08-22_correction-01.md`.

The superseded files remain unchanged to preserve their hashes and the
provenance embedded in existing coding records. The correction-02 codebook,
transition definitions, frame/timing rules, clip-boundary rule, append-only
correction principle, automation blinding during first-pass coding, and single
permitted Wave 1 calibration remain in force unless explicitly changed here.

## Revised manual-reference design

SB01 is the sole manual coder for Wave 1. MIA01 coding, inter-coder reliability
statistics, and joint adjudication are not required. After SB01's eligible
first pass is complete, SB01 reviews the manual records, records any changes in
an append-only correction file, and finalizes and hashes the corrected stream.

The corrected and finalized SB01 hard-cut stream is the Wave 1 single-coder
manual reference. It is not described as an adjudicated reference, consensus
ground truth, or independently reliability-verified reference.

No included SB01 event currently carries an uncertainty flag or the
`single_frame_blend` type. If self-review identifies an ambiguous or
count-affecting event that SB01 cannot resolve under the frozen codebook, that
event must remain excluded from a definitive manual hard-cut reference or be
referred for external methodological review; it must not be silently resolved
by software.

## Eleven-clip analysis population

The included set is exactly:

`W1C001`, `W1C002`, `W1C003`, `W1C004`, `W1C005`, `W1C006`, `W1C007`,
`W1C008`, `W1C009`, `W1C011`, and `W1C012`.

W1C010 includes end credits and is outside the plot-scene-only fine-tuning
scope. It is excluded without replacement. Its source/worklist row and any raw
manual or automated event remain provenance-only. W1C010 must not be coded as
zero, imputed, or included in any comparison denominator.

The machine-readable exclusion authority is
`.analysis/study_workflow/wave_1_manual/wave1_initial_analysis_exclusions_method-provenance_recipe-v1_2026-08-23.json`.

## Manual-versus-automated analysis

Automated results may be unsealed only after SB01 review/corrections and
immutable exclusion-aware finalization are complete. Apply the exact 11-ID
analysis mask independently to both the manual and automated tables before
joining, matching, counting, or calculating any metric. Reject missing,
duplicate, or extra clip IDs and reject any result containing W1C010.

For Version 1 and every eligible candidate setting, preserve and report:

- the 11 paired per-clip automated and SB01 manual hard-cut counts;
- per-clip signed and absolute count error;
- Pearson correlation across the 11 paired counts, when defined;
- exact-count agreement as a number and proportion with denominator 11;
- mean absolute count error and signed mean count error;
- per-clip and pooled TP, FP, FN, precision, recall, and F1 using the frozen
  one-to-one matcher at the primary ±0.250-second tolerance; and
- the same boundary metrics at ±1.000 second, labeled sensitivity analysis.

Threshold or operationalization selection must follow the preserved
correction-02 calibration criteria and use only these 11 paired clips. The same
11-clip mask must be used for the Version 1 baseline and every candidate; no
setting may gain an advantage from a different inclusion set.

Every output must state: `single-coder manual reference (SB01); n=11 of 12
originally selected clips; W1C010 excluded for end-credit content outside the
plot-scene scope; no replacement`.

## Required limitation

Every methods description and results report must disclose that the manual
reference was produced by one coder and therefore has no independent
inter-coder reliability estimate or consensus adjudication. Detector agreement
with SB01 estimates agreement with this coded reference; it does not establish
error-free ground truth or general human-coder reliability.

Wave 2 or later confirmatory work should use an independent coder or a
prespecified reliability subset if resources permit. That recommendation does
not block the revised Wave 1 single-coder calibration.

## Software gate

Before comparison, the qualified finalization and calibration code must be
updated so that it:

1. accepts exactly the 11 eligible SB01 completions;
2. preserves W1C010 raw provenance while excluding it from the reference;
3. creates an 11-row single-coder manual count table, including genuine
   zero-count eligible clips if any;
4. does not require MIA01 files or adjudication artifacts;
5. applies and verifies the same 11-ID mask on automated data; and
6. labels all outputs as single-coder rather than adjudicated.

The revised workflow must be tested before real automated results are unsealed.
