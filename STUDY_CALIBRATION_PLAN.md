# Adult Prediction of Children's Perceived Media Pacing

## Frozen cut-detector calibration plan

**Document status:** FROZEN BEFORE WAVE 1 CODING AND BEFORE TUNING  
**Freeze date:** 2026-08-18  
**Calibration count allowed:** One  
**Calibration set:** Frozen 12-clip Wave 1 Version 1 proposal  
**Eligible change:** Cut detection only  
**Ineligible changes:** Motion method, motion sampling method/rate, audio-intensity method, corpus, windows, exclusions, and pair-selection rule  
**Tuning run performed at freeze:** No  

## Preserved baseline

Version 1 remains unchanged:

- recipe ID `r_apc_media_pacing`;
- citation `Adult Prediction of Children's Perceived Media Pacing - Feature Extraction v1 (0d233950c561)`;
- recipe file SHA-256
  `689b8d7bdf6970f862651ca4fd5478aecf6240858632b106e2d53d4b71d60545`;
- cut method PySceneDetect `ContentDetector`, threshold `27.0`;
- motion absolute frame differencing with uniform sampling at `2.0 fps`;
- audio intensity FFmpeg linear RMS;
- measurement fingerprint `a5714394da4d`;
- Season One HD, 30 files, 1,320 eligible 30-second windows, exclusions 51
  seconds first and 38 seconds last.

No automated value is overwritten by a manual value. Manual events and counts
are a separate overlay keyed by `clip_id`.

## Frozen tuning grid

The single calibration tests exactly seven settings of the same cut detector:

| Setting ID | Detector | Threshold | Other detector behavior |
|---|---|---:|---|
| `CD_T18` | PySceneDetect ContentDetector | 18.0 | Library/default behavior otherwise unchanged |
| `CD_T21` | PySceneDetect ContentDetector | 21.0 | Library/default behavior otherwise unchanged |
| `CD_T24` | PySceneDetect ContentDetector | 24.0 | Library/default behavior otherwise unchanged |
| `CD_T27_V1` | PySceneDetect ContentDetector | 27.0 | Exact Version 1 baseline |
| `CD_T30` | PySceneDetect ContentDetector | 30.0 | Library/default behavior otherwise unchanged |
| `CD_T33` | PySceneDetect ContentDetector | 33.0 | Library/default behavior otherwise unchanged |
| `CD_T36` | PySceneDetect ContentDetector | 36.0 | Library/default behavior otherwise unchanged |

No AdaptiveDetector, TransNetV2, dissolve detector, scene-classification
parameter, minimum-scene-length variation, post-hoc debounce, or unscheduled
threshold is eligible. The grid changes only the ContentDetector threshold and
symmetrically brackets Version 1.

For calibration, run cut detection only on the exact 12 Wave 1 source intervals.
Do not recalculate motion or audio intensity. Preserve event-level detections,
counts, settings, software/library versions, commands, stdout/stderr, run time,
input hashes, and output hashes for every setting, including unsuccessful ones.

## Reference and event matching

The adjudicated manual hard-cut event set produced under
`STUDY_MANUAL_CODING_PLAN.md` is the reference. The detector comparison remains
sealed until both coders' raw/refinement files and adjudication are complete and
hashed.

For each clip and setting, match automated and manual hard-cut timestamps using
a one-to-one assignment with absolute time difference at most **1.000 second**.
Choose the assignment that first maximizes the number of matches and then
minimizes the total absolute timestamp difference. This prevents one detection
from matching multiple manual events. The 1-second tolerance matches the
codebook's timestamp-accuracy target and is tighter than its general 2-second
default, reducing ambiguous matches in short animated shots. The tolerance may
not change after results are viewed.

Definitions:

- `TP`: matched automated/manual boundary pair;
- `FP`: unmatched automated boundary;
- `FN`: unmatched manual hard-cut boundary;
- precision = `TP / (TP + FP)`;
- recall = `TP / (TP + FN)`;
- F1 = harmonic mean of precision and recall;
- per-clip count error = automated hard-cut count minus manual hard-cut count;
- positive signed error means overcounting; negative means undercounting.

If a denominator is zero, report the metric as not defined and report the raw
counts; do not substitute a favorable value. Pearson's `r` is also reported as
not defined if either series has zero variance.

## Required Wave 1 results

For Version 1 and every tested setting, preserve and report:

- per-clip automated count, manual count, and signed/absolute count error;
- Pearson's `r` across the 12 clip counts;
- exact-count agreement as number and proportion of clips;
- mean absolute count error per 30-second clip;
- signed mean count error;
- pooled boundary precision, recall, and F1 at ±1.000 second;
- per-clip TP, FP, FN, precision, recall, and F1;
- pooled TP, FP, and FN counts;
- timestamp differences for every match;
- all unmatched automated and manual events; and
- observed error mechanisms.

After unsealing automated results, classify each FP/FN using a standardized,
nonexclusive mechanism table: `pan`, `zoom`, `tilt_or_camera_motion`,
`high_within_shot_motion`, `low_contrast_hard_cut`, `double_detection`,
`gradual_transition_not_hard_cut`, `graphic_overlay`, `flash_or_luminance_change`,
`boundary_or_range_handling`, `decoder_or_timestamp_issue`, or
`other_described`. Preserve notes and event/clip links. Do not modify manual
events to improve detector performance.

## Frozen parameter-selection rule

Select exactly one Version 2 setting using this lexicographic rule:

1. highest pooled boundary F1 at ±1.000 second;
2. if tied to the displayed precision of six decimals, lowest mean absolute
   count error;
3. if still tied, smallest absolute signed mean count error;
4. if still tied, highest exact-count agreement;
5. if still tied, threshold closest to `27.0`;
6. if equally distant from `27.0`, choose the higher threshold to favor fewer
   false positive pseudo-cuts.

Pearson correlation is descriptive and is never a selection criterion. No
subjective impression of pacing is a selection criterion. The rule is applied
once to the complete frozen grid. If threshold 27.0 wins, Version 2 documents
that the calibration retained the baseline operationalization; it is still
saved as a new Version 2 recipe/citation with a written calibration reason and
complete snapshot.

## Stopping rule and reruns

After all seven scheduled settings have one valid result, apply the frozen rule
and stop. Do not add settings, narrow the grid, change tolerance, change metrics,
exclude difficult clips, or retune after Wave 2.

A failed or corrupt run may be repeated only with identical code, inputs, and
parameters. Log the error, partial output, reason for rerun, and both attempts.
Such a rerun is a technical recovery within the same calibration, not a new
tuning round. If a setting cannot be obtained reproducibly, retain the failure
and do not replace it with an unscheduled setting.

## Version 2 freeze

The selected setting is duplicated into a new recipe; Version 1 is never edited.
Version 2 must have:

- version number 2 and a distinct recipe citation;
- a new content hash and recipe-file SHA-256;
- `locked: true` before Wave 2;
- the selected detector setting and complete configuration snapshot;
- unchanged motion binding (`absdiff`, uniform `2.0 fps`);
- unchanged audio-intensity binding (FFmpeg linear RMS);
- a history/reason entry naming this Wave 1 calibration, its plan hash, result
  manifest, and selection-rule outcome.

Wave 1 Version 2 results are labeled **calibration-set performance**, never
independent validation.

## Frozen Wave 2 comparison

After Version 2 is locked, run the complete 30-file Season One HD corpus with
the same 30-second windows and 51/38-second exclusions. Preserve Version 2
manifest, fingerprint, candidates, proposed pairs, alternatives, tables, and
caches separately from Version 1.

Construct a new blind Wave 2 shortlist from Version 2 output. No Wave 1 clip may
contribute to prospective Wave 2 performance metrics. Both Version 1 and
Version 2 are then run on the exact same adjudicated Wave 2 manual-reference
events and compared with the same ±1.000-second matcher and all metrics above.
The Version 2 recipe remains frozen regardless of Wave 2 performance.

Report Wave 2 as a **prospective audit of newly selected clips produced by the
intended workflow**, not validation of all Season One scenes and not validation
of CMAT as a whole. Preserve per-clip values and paired Version 2-minus-Version
1 changes in count error, TP, FP, and FN.

## Final measurement hierarchy

- Cut pairs: manual cuts determine target contrast; frozen automated motion and
  RMS determine control matching.
- Motion pairs: frozen automated motion determines target contrast; manual cuts
  and frozen automated RMS determine control matching.
- Audio pairs: frozen automated RMS determines target contrast; manual cuts and
  frozen automated motion determine control matching.

Final cut measurements are manually verified hard-cut counts. Automated cut
results remain preserved as calibration/audit measurements and never replace
the manual overlay.

