# Adult Prediction of Children's Perceived Media Pacing

## CUTS_2 low-member stimulus replacement — correction 06

**Document status:** AUTHORITATIVE STIMULUS-SET CORRECTION  
**Decision date:** 2026-08-23  
**Applies to:** the 12 participant-facing stimuli only  
**Replaced clip:** Clip A2 / W1C010 — S01 E04 at 00:11:51  
**Replacement clip:** S01 E28 at 00:04:21  
**Selection rule:** frozen Version 1 rule, unchanged  
**Manual coding affected:** none

## Authority and scope

This correction changes **which clip fills the CUTS_2 low-member slot in the
participant stimulus set**. It changes nothing else. Specifically it does not
touch:

- the detector, its threshold, or any measurement setting — Version 1 and
  `CD_T27_V1` remain authoritative under correction-05;
- the selection rule, its control penalty, or its constraints;
- the closed correction-04 single-coder calibration, which stays on its frozen
  11-clip mask;
- the other eleven stimuli, their identities, media files or measurements.

`STUDY_WAVE1_ANALYSIS_SCOPE_..._correction-03.md` excluded W1C010 from the
**calibration analysis** while explicitly preserving the 12-row selection. That
left W1C010 still slated for participant viewing. This correction closes that
gap.

## Reason

W1C010 contains the inter-story title card. Its thirty seconds run:
approximately six seconds of story, a black gap, roughly five seconds of static
credit text (*"Roller Monkey — Written by Lazar Saric / Directed by Frank
Marino"*), then the opening of the second story.

The defect is substantive, not cosmetic. W1C010 is the **low-cut member of the
pair whose entire purpose is to isolate cut rate**. Its low count of 4 cuts per
minute is produced partly by a motionless card rather than by slow plot pacing,
so the confound sits precisely in the feature the pair exists to test. It is
also not comparable with the other eleven clips, which are plot scenes.

## Structural cause — a standing method limitation

The candidate windowing rule trims the first 51 s and last 38 s of each episode
but nothing mid-episode. These are two-story episodes, so each contains a
title/credit card near its midpoint, and windows landing there entered the
candidate pool — on the order of one to two windows per episode, roughly 2–5%
of the 1,320.

Because a static card suppresses the cut count, such windows are systematically
**over-represented among low-cut candidates**. This was confirmed during the
replacement search: the two highest-scoring candidates both sat at 00:11:51 —
the same structural position as the clip being replaced — and both were
visually confirmed as non-plot content.

**Consequence:** any low-cut selection drawn from this pool must be screened
visually. Score alone is not sufficient, and this limitation should be reported.

## Replacement procedure

The frozen Version 1 selection rule was applied unchanged:

- score = target percentile gap − 0.75 × (sum of the two control percentile gaps)
- candidate must be in the bottom third on cuts
- pair members must come from different source episodes
- no episode may contribute more than two clips to the twelve
- no clip already used elsewhere in the set may be reused

492 candidates were eligible. The replaced pair scored 0.9492.

| Rank | Score | Position | Outcome |
|---|---|---|---|
| 1 | 0.9189 | 00:11:51 | **rejected** — non-plot content on visual review |
| 2 | 0.8898 | 00:11:51 | **rejected** — non-plot content on visual review |
| 3 | 0.8497 | 00:04:21 | **adopted** — confirmed continuous plot content |

The adopted clip is the highest-scoring candidate passing content review, which
preserves the original workflow's stated division of labour: the score proposes,
human scene review disposes.

## Measurements

Exported with the same encoder settings as the existing eleven files —
libx264 preset medium CRF 18, yuv420p, `fps_mode passthrough`, AAC 192k,
`+faststart`.

| | Cuts/min | Motion | Audio RMS |
|---|---|---|---|
| Source window | 8.0 | 0.0718 | 0.03612 |
| Exported file | 8.0 | 0.0694 | 0.03608 |
| Partner Clip B2 (exported) | 26.0 | 0.0682 | 0.03685 |
| Replaced Clip A2 (exported) | 4.0 | 0.0691 | 0.03707 |

Cut count is identical between source and export, so this clip shows none of
the near-start boundary loss observed on four other clips.

**Resulting CUTS_2 pair:** cuts 8.0 vs 26.0; motion differs by 0.0012; audio by
0.00069. Control matching is as tight as the pair replaced (0.0009 and 0.0003).

**Cost, stated plainly:** the target contrast narrows from 4 vs 26 to 8 vs 26.
Against that, the surviving contrast compares two plot scenes rather than a plot
scene against a title card, and is therefore the truer test of the question.

## Manual coding

This replacement removes no manual data: W1C010 was already outside the coded
set under correction-03, so no hand coding is lost and the correction-04
calibration is untouched.

The replacement clip has **no manual cut count**. If one is produced, it is a
descriptive stimulus-property count only. It must not enter the closed
correction-04 comparison, and it cannot be blind in the original sense, because
the automated result for this clip is already known. Any such count must be
recorded as post-hoc, non-blind and single-coder.

## Artifacts

`.analysis/study_workflow/stimulus_replacement/cuts2_low_replacement_method-automated-with-visual-review_recipe-v1_2026-08-23_correction-06/`

- the exported stimulus file, with SHA-256
- its measurement JSON under the frozen configuration
- a **new** twelve-row selection record — the frozen `selected_clips.csv` was
  not edited
- a provenance manifest recording the rule, the rejected candidates, the source
  hashes and the resulting pair
- detached checksums

The search tool is
`.analysis/study_workflow/tools/find_cuts2_replacement_method-automated_recipe-v1_2026-08-23_correction-06.py`.
