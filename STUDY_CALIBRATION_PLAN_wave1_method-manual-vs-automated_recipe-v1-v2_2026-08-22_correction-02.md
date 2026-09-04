# Adult Prediction of Children's Perceived Media Pacing

## Frozen cut-detector calibration plan — correction 02

**Document status:** FROZEN BEFORE WAVE 1 CODING AND BEFORE TUNING;
CORRECTION-02 SOFTWARE/PACKAGE QUALIFICATION STILL REQUIRED  
**Freeze date:** 2026-08-22  
**Calibration count allowed:** One  
**Calibration set:** Frozen 12-clip Wave 1 Version 1 proposal  
**Eligible change:** Cut-detection operationalization only  
**Ineligible changes:** Motion method, motion sampling method/rate,
audio-intensity method, corpus, windows, exclusions, and pair-selection rule  
**Tuning run performed at freeze:** No

This document supersedes `STUDY_CALIBRATION_PLAN.md` only for correction-02 and
later study work. The 2026-08-18 plan remains preserved unchanged with SHA-256
`8228088550ab66c08309f230be611f00f9a1b313bbf5c9c62a77ebe4f6933dcb`.

The manual reference must be produced under:

- codebook
  `validation/CODEBOOK_wave1-2_method-manual_recipe-v1_2026-08-22_correction-02.md`,
  SHA-256
  `b46bdaab419d1e33138d2bf3a6e98a5b6bf80f7fa97fcf311c2c18b905906f90`;
  and
- coding plan
  `STUDY_MANUAL_CODING_PLAN_wave1-2_method-manual_recipe-v1_2026-08-22_correction-02.md`,
  SHA-256
  `c4e8f709c474703a377b6abce4333c2741d016201104d369566dac3ed6486f7c`.

No tuning command may run until a new correction-02 blind-coding package has
passed pre-use qualification and both coders' Wave 1 files and adjudication are
complete, locked, and hashed.

## Preserved Version 1 baseline

Version 1 remains unchanged:

- recipe ID `r_apc_media_pacing`;
- citation `Adult Prediction of Children's Perceived Media Pacing - Feature Extraction v1 (0d233950c561)`;
- recipe file SHA-256
  `689b8d7bdf6970f862651ca4fd5478aecf6240858632b106e2d53d4b71d60545`;
- PySceneDetect `ContentDetector`, threshold `27.0`;
- motion by absolute frame differencing with uniform sampling at `2.0 fps`;
- audio intensity by FFmpeg linear RMS;
- measurement fingerprint `a5714394da4d`;
- 30 Season One HD files and 1,320 eligible 30-second windows; and
- per-episode exclusions of the first 51 seconds and last 38 seconds.

Manual values remain in separate overlays keyed by `clip_id`. No automated
candidate value is overwritten.

## Frozen tuning grid

The one calibration tests exactly seven settings of the same detector:

| Setting ID | Detector | Threshold | Other detector behavior |
|---|---|---:|---|
| `CD_T18` | PySceneDetect ContentDetector | 18.0 | Library/default behavior otherwise unchanged |
| `CD_T21` | PySceneDetect ContentDetector | 21.0 | Library/default behavior otherwise unchanged |
| `CD_T24` | PySceneDetect ContentDetector | 24.0 | Library/default behavior otherwise unchanged |
| `CD_T27_V1` | PySceneDetect ContentDetector | 27.0 | Exact Version 1 baseline |
| `CD_T30` | PySceneDetect ContentDetector | 30.0 | Library/default behavior otherwise unchanged |
| `CD_T33` | PySceneDetect ContentDetector | 33.0 | Library/default behavior otherwise unchanged |
| `CD_T36` | PySceneDetect ContentDetector | 36.0 | Library/default behavior otherwise unchanged |

No alternate detector, dissolve detector, minimum-scene-length variation,
post-hoc debounce, scene-classification change, or unscheduled threshold is
eligible. The grid changes only the ContentDetector threshold and
symmetrically brackets Version 1.

Run cut detection only on the exact 12 Wave 1 intervals. Do not recalculate or
alter motion or audio intensity. Preserve every setting's event detections,
counts, complete parameters, software/library versions, commands,
stdout/stderr, run time, input hashes, and output hashes, including failed or
unsuccessful settings.

## Manual reference

The reference is the adjudicated manual `hard_cut` event set. It contains clean
hard cuts and genuine hard cuts with `whip_pan_masking=true`. It excludes
unresolved events, genuine `single_frame_blend` events, gradual transitions,
and non-boundary observations.

A raw one-frame-blend case may enter the hard-cut reference only when the
separate adjudication record establishes that the blended decoded frame was an
artifact surrounding an otherwise adjacent-frame editorial cut. The raw row
is preserved unchanged.

Automated results remain sealed until both coders' files, reliability results,
and manual adjudication are complete and hashed. Manual events are never
changed to improve detector performance.

## Frozen boundary matching

### Primary matcher

For each clip and setting, match automated and manual hard-cut timestamps using
a one-to-one assignment with an absolute difference of no more than
**0.250 seconds**. Choose the assignment that:

1. maximizes the number of matched pairs; then
2. minimizes the total absolute timestamp difference.

This prevents either an automated or manual event from being reused. The
0.250-second tolerance is frozen before coding and calibration because the
manual interface uses decoded-frame maps rather than approximate whole-second
VLC timestamps.

### Prespecified sensitivity matcher

Repeat the same metrics at **plus or minus 1.000 second** as a secondary
sensitivity analysis. This wider tolerance is descriptive only. It never
selects Version 2, breaks a tie, justifies a retune, or replaces the primary
results.

Neither tolerance may change after automated results are viewed.

### Definitions

- `TP`: one matched automated/manual hard-cut pair;
- `FP`: an unmatched automated boundary;
- `FN`: an unmatched manual hard-cut boundary;
- precision = `TP / (TP + FP)`;
- recall = `TP / (TP + FN)`;
- F1 = harmonic mean of precision and recall;
- per-clip count error = automated count minus manual hard-cut count;
- positive signed error = automated overcounting; and
- negative signed error = automated undercounting.

If a denominator is zero, report the metric as not defined and retain the raw
counts. Pearson's `r` is not defined when either count series has zero variance.

## Required Wave 1 results

For Version 1 and every tested setting, preserve and report:

- per-clip automated and adjudicated manual hard-cut counts;
- per-clip signed and absolute count error;
- Pearson's `r` across the 12 counts;
- exact-count agreement as number and proportion of clips;
- mean absolute count error per 30-second clip;
- signed mean count error;
- per-clip and pooled TP, FP, FN, precision, recall, and F1 at the primary
  plus or minus 0.250-second tolerance;
- the same boundary metrics at plus or minus 1.000 second, labeled sensitivity;
- timestamps and absolute differences for every match;
- every unmatched automated and manual event;
- primary performance both with all manual hard cuts and descriptively after
  excluding `whip_pan_masking=true` events, with the all-hard-cut result
  remaining authoritative for parameter selection; and
- standardized error-mechanism annotations.

Error mechanisms are nonexclusive and use this frozen vocabulary:

```text
pan
zoom
tilt_or_camera_motion
whip_pan_masked_hard_cut
high_within_shot_motion
low_contrast_hard_cut
single_frame_blend
double_detection
gradual_transition_not_hard_cut
graphic_overlay
flash_or_luminance_change
boundary_or_range_handling
decoder_or_timestamp_issue
other_described
```

Preserve notes and links to the relevant clip, automated event, manual event,
and non-boundary observation. `other_described` requires notes.

## Frozen Version 2 selection rule

Select exactly one Version 2 setting lexicographically using only the primary
plus or minus 0.250-second results:

1. highest pooled boundary F1;
2. if tied to six displayed decimals, lowest mean absolute count error;
3. if still tied, smallest absolute signed mean count error;
4. if still tied, highest exact-count agreement;
5. if still tied, threshold closest to `27.0`; and
6. if equally distant from `27.0`, the higher threshold, favoring fewer false
   positive pseudo-cuts.

Pearson correlation, the 1-second sensitivity result, the whip-pan-excluded
descriptive result, and subjective impressions of pacing are never selection
criteria.

The rule is applied once to the complete frozen grid. If threshold 27.0 wins,
Version 2 still receives a new recipe citation, snapshot, content hash, and
written reason documenting that calibration retained the baseline threshold.

## Stopping rule and technical reruns

After all seven scheduled settings have one valid result, apply the frozen rule
and stop. Do not add settings, narrow the grid, change tolerance or metrics,
exclude difficult clips, or retune after Wave 2.

A failed or corrupt run may be repeated only with identical code, inputs, and
parameters. Log the error, partial output, reason, and every attempt. A technical
recovery is not a second calibration. If a setting cannot be reproduced,
retain the failure and do not substitute an unscheduled setting.

## Version 2 freeze

The selected operationalization is saved separately; Version 1 is never
edited. Version 2 must contain:

- version number 2 and a distinct citation;
- a new content hash and recipe-file SHA-256;
- `locked: true` before Wave 2;
- the selected cut setting and complete configuration snapshot;
- unchanged motion binding (`absdiff`, uniform `2.0 fps`);
- unchanged audio-intensity binding (FFmpeg linear RMS); and
- a history/reason entry naming the Wave 1 calibration, this plan and its
  eventual SHA-256, the result manifest, and the selection-rule outcome.

Wave 1 Version 2 performance is labeled **calibration-set performance**, never
independent validation.

## Frozen Wave 2 prospective audit

After Version 2 is locked, run the complete 30-file Season One HD corpus with
the same windows and exclusions. Preserve its manifest, fingerprint,
candidates, proposed pairs, alternatives, tables, and caches separately from
Version 1.

Construct a new blind Wave 2 shortlist from Version 2 output. Wave 1 clips do
not contribute to prospective Wave 2 metrics. Both Version 1 and Version 2 are
then compared with the exact same adjudicated Wave 2 manual reference, using
the same primary and sensitivity matchers and the complete metrics above.
Version 2 remains frozen regardless of the outcome.

Wave 2 is reported as a **prospective audit of newly selected clips produced by
the intended workflow**, not validation of every Season One scene and not
validation of CMAT as a whole. Preserve per-clip values and paired
Version-2-minus-Version-1 changes in count error, TP, FP, and FN.

## Final measurement hierarchy

- Cut pairs: adjudicated manual hard cuts determine the target contrast;
  frozen automated motion and RMS determine control matching.
- Motion pairs: frozen automated motion determines the target contrast;
  adjudicated manual hard cuts and frozen automated RMS determine control
  matching.
- Audio pairs: frozen automated RMS determines the target contrast;
  adjudicated manual hard cuts and frozen automated motion determine control
  matching.

Final cut measurements are manually verified hard-cut counts. Automated cut
measurements remain preserved as calibration/audit results and never replace
the manual overlay.
