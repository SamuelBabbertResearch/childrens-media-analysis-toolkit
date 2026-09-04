# Adult Prediction of Children's Perceived Media Pacing

## Wave 1 plot-scene analysis scope — correction 03

**Document status:** AUTHORITATIVE POST-CODING SCOPE CORRECTION  
**Decision date:** 2026-08-23  
**Applies to:** Wave 1 manual reliability, adjudication, and manual-versus-automated calibration analysis  
**Original selected set:** 12 clips  
**Analysis set:** 11 clips  
**Excluded clip:** W1C010  
**Replacement:** None

## Authority and preserved history

This correction supplements and narrowly supersedes the Wave 1 clip-count and
analysis-denominator clauses in:

- `STUDY_MANUAL_CODING_PLAN_wave1-2_method-manual_recipe-v1_2026-08-22_correction-02.md`;
- `STUDY_CALIBRATION_PLAN_wave1_method-manual-vs-automated_recipe-v1-v2_2026-08-22_correction-02.md`; and
- `.analysis/study_workflow/wave_1_manual/WAVE1_ADJUDICATED_REFERENCE_SYSTEM_method-manual_recipe-v1_2026-08-22_correction-01.md`.

Those frozen documents remain unchanged so that their recorded hashes and the
provenance embedded in existing coding records remain valid. All definitions,
timing rules, blinding requirements, matching tolerances, correction rules,
adjudication requirements, and tuning restrictions in them remain in force
except for the explicit Wave 1 scope changes below.

## Exclusion decision

W1C010 includes end credits. The initial detector fine-tuning analysis is
restricted to plot scenes, so W1C010 is outside the target content domain. It
is excluded without replacement.

This is a content-scope exclusion, not missing data, coder attrition, or a
failed measurement. The original 12-row selection, blind worklist, coding
media, and raw audit records remain preserved. Any W1C010 raw manual event or
automated detection remains provenance-only and must not enter an analysis
quantity.

The machine-readable companion decision is
`.analysis/study_workflow/wave_1_manual/wave1_initial_analysis_exclusions_method-provenance_recipe-v1_2026-08-23.json`.

## Eligible Wave 1 analysis set

The eligible set is exactly:

`W1C001`, `W1C002`, `W1C003`, `W1C004`, `W1C005`, `W1C006`, `W1C007`,
`W1C008`, `W1C009`, `W1C011`, and `W1C012`.

For Wave 1, references in the correction-02 manual plan to both coders coding
“all 12” mean all 11 eligible clips listed above. The required completed set
is those 11 IDs exactly; W1C010 completion must not be fabricated to satisfy a
12-clip software check.

## Manual reliability and adjudication

Inter-coder reliability, event correspondence, corrections, and adjudication
operate only on the 11 eligible clips. The primary ±0.250-second tolerance and
the prespecified ±1.000-second sensitivity tolerance are unchanged.

The adjudicated reference must contain one per-clip count row for each of the
11 eligible clips, including any eligible clip with zero hard cuts. W1C010
must instead appear in the exclusion/provenance record and must not receive an
analysis count of zero, because zero would incorrectly represent an observed
plot-scene hard-cut count.

The two-coder and joint-adjudication requirements remain unchanged. SB01's
first-pass values alone may be summarized descriptively, but the automated
detector must be compared against the adjudicated manual reference—not treated
as validated against a single unadjudicated coder stream.

## Manual-versus-automated comparison

Every Version 1 setting and any eligible tuned setting must be compared with
the same 11-clip analysis mask before any metric is calculated. Filter both
manual and automated event/count tables to the exact eligible ID set first;
then match events and aggregate metrics.

The following must use only the 11 paired eligible clips:

- per-clip automated and adjudicated manual hard-cut counts;
- signed and absolute count error;
- Pearson correlation across 11 paired counts;
- exact-count agreement and its denominator;
- mean absolute and signed mean count error;
- per-clip and pooled TP, FP, FN, precision, recall, and F1 at ±0.250 seconds;
- the prespecified ±1.000-second sensitivity analysis; and
- threshold/setting selection and every aggregate calibration summary.

Reports must state `n=11 of 12 originally selected clips`, identify W1C010 as
the sole exclusion, give the end-credit/plot-scene rationale, and state that no
replacement was selected. No metric may mix an 11-clip manual table with a
12-clip automated table.

## Software gate

Before real comparison output is generated, the finalization, adjudicated-
reference, and calibration code must be made exclusion-aware and qualified.
It must validate the exact 11 eligible IDs against this correction and the
machine-readable exclusion manifest, retain W1C010 provenance, and reject any
attempt to include W1C010 in manual/automated comparison metrics.

Automated output remains sealed until both eligible coder streams are locked,
reliability comparison and joint adjudication are complete, and the verified
11-row adjudicated manual reference exists.
