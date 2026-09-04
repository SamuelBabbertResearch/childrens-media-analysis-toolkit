# Adult Perception Study: Clip Features and Pairing Guide

**Status:** This table describes the proposed 12-clip Wave 1 calibration set,
not final participant-facing stimuli. Every clip is 30 seconds from *Curious
George* Season One. Values come from the Version 1 automated measurement run;
manual hard-cut counts will be authoritative for final cut-based contrasts.

Participants watch and rate all 12 clips individually on the five-point
question, “How fast did this video feel?” They are not told which clips form a
pair. Pair comparisons are made later during analysis.

| Analytical pair | Lower / comparison clip | Higher / feature clip | Feature contrast (low → high) | What the paired ratings can show |
|---|---|---|---|---|
| **Cuts 1** | **A1** — *E10*, 09:51–10:21<br>4 cuts/min; motion **0.0430**; audio intensity **0.03673 RMS** | **B1** — *E19*, 20:51–21:21<br>30 cuts/min; motion **0.0437**; audio intensity **0.03719 RMS** | **Cut rate:** 4 → 30 cuts/min.<br>Motion and audio intensity are closely matched. | Whether the clip with much more frequent editing is rated as faster when the measured visual change and audio intensity are nearly the same. |
| **Cuts 2** | **A2** — *E04*, 11:51–12:21<br>4 cuts/min; motion **0.0699**; audio intensity **0.03713 RMS** | **B2** — *E16*, 09:51–10:21<br>28 cuts/min; motion **0.0693**; audio intensity **0.03685 RMS** | **Cut rate:** 4 → 28 cuts/min.<br>Motion and audio intensity are closely matched. | Whether the Cut 1 pattern appears again with different scenes—an independent, within-set replication of the cut-rate contrast. |
| **Motion 1** | **C1-L** — *E10*, 16:51–17:21<br>18 cuts/min; motion **0.0331**; audio intensity **0.04117 RMS** | **C1-H** — *E13*, 13:21–13:51<br>18 cuts/min; motion **0.1082**; audio intensity **0.04109 RMS** | **Visual motion:** 0.0331 → 0.1082 mean frame difference.<br>Cut rate is identical and audio intensity is closely matched. | Whether substantially more frame-to-frame visual change is associated with higher perceived pace, apart from measured editing frequency and audio intensity. |
| **Motion 2** | **C2-L** — *E13*, 05:21–05:51<br>16 cuts/min; motion **0.0356**; audio intensity **0.03933 RMS** | **C2-H** — *E23*, 18:21–18:51<br>16 cuts/min; motion **0.1032**; audio intensity **0.03934 RMS** | **Visual motion:** 0.0356 → 0.1032 mean frame difference.<br>Cut rate is identical and audio intensity is closely matched. | Whether the Motion 1 pattern replicates in a second pair of scenes. |
| **Audio intensity 1** | **D1-L** — *E05*, 06:21–06:51<br>16 cuts/min; motion **0.0884**; audio intensity **0.03043 RMS** | **D1-H** — *E06*, 09:51–10:21<br>16 cuts/min; motion **0.0882**; audio intensity **0.04294 RMS** | **Audio intensity:** 0.03043 → 0.04294 RMS.<br>Cut rate is identical and motion is closely matched. | Whether a higher-amplitude soundtrack is associated with higher perceived pace when the measured editing and visual motion are nearly the same. |
| **Audio intensity 2** | **D2-L** — *E05*, 17:51–18:21<br>16 cuts/min; motion **0.0734**; audio intensity **0.02829 RMS** | **D2-H** — *E14*, 06:51–07:21<br>16 cuts/min; motion **0.0758**; audio intensity **0.04442 RMS** | **Audio intensity:** 0.02829 → 0.04442 RMS.<br>Cut rate is identical and motion is closely matched. | Whether the Audio intensity 1 pattern replicates in a second pair of scenes. |

## What the features mean

| Feature | What CMAT measures | Why it may relate to perceived pace |
|---|---|---|
| **Cut rate** | The number of detected editing transitions per minute. | Frequent changes of shot may make a scene feel faster even when activity inside each shot is limited. |
| **Visual motion** | Mean frame-to-frame visual change in sampled video frames. | Character, object, camera, or scene movement may make a clip feel more active even without extra cuts. |
| **Audio intensity** | Mean linear RMS signal amplitude. This is not a measure of perceived loudness or LUFS. | More intense audio may contribute to an overall impression of activity or speed. |

## How to interpret the results

The pairwise comparisons can describe whether ratings move in the expected
direction in each contrast, and whether the two pairs for a feature show a
similar pattern. Together with continuous clip-level measures, they support
exploratory associations between measured media features and adults’ perceived
pace within this selected clip set.

They cannot show that any one feature *caused* the rating: the clips are
naturally occurring scenes and can still differ in story, dialogue, music,
humor, or other unmeasured qualities. Findings also do not generalize by
themselves beyond these clips, this program, or the adult sample.

**Source:** Version 1 `selected_clips.csv` and its generated clip tables in
`.analysis/study_clips/Curious George Full Season One HD/` (measurement
fingerprint `a5714394da4d`).
