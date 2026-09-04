# Adult Prediction of Children's Perceived Media Pacing

## Step-by-Step Adult and Child Study Procedure

> **Superseded 2026-08-31.** This document is retained as historical design
> evidence only. The active study recruits adults only, asks one self-perception
> pacing question after each clip, and does not ask adults to predict children's
> responses. Do not implement or pilot the participant flows below. See
> [the redesign decision](STUDY_ADULT_ONLY_REDESIGN_DECISION_2026-08-31.md) and
> [the active adult-only procedure](STUDY_PROCEDURE_ADULT_ONLY.md).

**Current design:** Option 3.5, Replicated Feature Design  
**Stimuli:** 12 unique, 30-second *Curious George* clips  
**Working child age range:** 8–12 years  
**Status:** Working procedural specification. Final consent, assent, recruitment,
demographic, exclusion, and statistical procedures require faculty/methods and
IRB approval before data collection.

## How the questions and rating scale are used

The study uses one repeated outcome question: how fast each clip **felt** to the
person whose perspective is being rated. CMAT measurements are not shown to
participants, and participants are not asked to count cuts, judge motion, or
judge sound.

The response format is a five-point ordered pace-rating scale:

| Response | Verbal anchor |
|---:|---|
| 1 | Very slow |
| 2 | Slow |
| 3 | In between |
| 4 | Fast |
| 5 | Very fast |

This can be described as a **five-point Likert-type item**, but “five-point
ordered rating scale” is more precise. A traditional Likert scale usually
combines several agreement items into one score; this study asks one pace item
repeatedly for different clips. The response records an **ordered level** of
perceived pace. The numbers label ordered categories; the distance from 1 to 2
should not automatically be assumed to equal the distance from 4 to 5 when the
statistical analysis is chosen.

The same response options are used for all three perspectives:

| Perspective | Exact working question | Who answers it? |
|---|---|---|
| Adult self-perception | **How fast did this video feel to you?** | Adults |
| Adult prediction of a child | **How fast do you think this video would feel to a [target-age] child?** | Adults |
| Child self-perception | **How fast did this video feel to you?** | Children |

`[target-age]` must be replaced with one fixed age before data collection—for
example, “a typical 9-year-old”—and that age must fit the children actually
recruited. Every adult must receive identical target-age wording.

The six CMAT-matched pairs are **not** shown as forced-choice trials. Participants
never answer “Which clip was faster?” under Option 3.5. They rate each clip
individually. Adults and children both see all 12 clips, so they see both members
of every analytical pair, but the pairs are not labeled or deliberately presented
back-to-back. The low-versus-high pairings are applied later during analysis.

## Before either phase begins

1. **Freeze the 12 participant-facing clips.** Export and remeasure the exact
   files participants will see after the documented Wave 1 calibration, frozen
   Wave 2 audit, manual cut verification, and final constrained selection.
   Retain the source timecodes, both CMAT recipe versions and fingerprints,
   automated motion/audio values, authoritative manual cut counts, exclusions,
   coding provenance, and manifests.
2. **Finalize the target age.** Replace `[target-age]` in the adult-prediction
   question with one fixed age that matches the recruited child sample.
3. **Finalize the visual scale.** Use the same five response values and verbal
   anchors in both phases. A turtle at the slow end and rabbit at the fast end
   may be piloted, but imagery must clarify pace without implying desirability.
4. **Create the randomization plan.** Randomize or counterbalance clip order.
   Do not group clips by analytical pair; preferably use a frozen ordering rule
   that keeps the two members of a pair from appearing consecutively. Freeze and
   record the plan before examining participant responses.
5. **Program data logging.** Every response must retain an anonymous participant
   ID, participant group, block/perspective, clip label, trial order, rating,
   and clip-order condition.
6. **Pilot the complete procedure.** Confirm that instructions, scale anchors,
   sound level, clip playback, session length, breaks, and data recording work
   as intended. Pilot especially with children near the lower end of the age
   range.

## Phase 1: Adult participants

Adults watch each of the 12 clips once and provide two ratings immediately after
each viewing. The **child-prediction question is always answered first** and that
answer is locked before the adult sees the self-perception question. This makes
the primary prediction response less vulnerable to influence from the adult's
explicit self-rating while avoiding a second viewing of every clip.

The two questions must not be displayed simultaneously. Because the ratings
still share one viewing and occur consecutively, their association may partly
reflect question context or consistency. Adult self-to-prediction anchoring is
therefore exploratory rather than a clean independent test.

### Step 1: Consent and eligibility

1. Present the IRB-approved adult consent information.
2. Confirm the approved adult eligibility requirements.
3. Assign an anonymous participant ID; do not place identifying information in
   the clip-rating data.
4. Administer only the demographic or background questions approved in the
   final protocol. The exact demographic set has not yet been finalized.

### Step 2: Assign the clip-order condition

Assign the adult one of the frozen/randomized clip orders. Record the order
condition with the participant's data. Do not tell the participant which clips
form analytical pairs or identify clips as high or low on any CMAT feature.

### Step 3: Explain and practice the scale

1. Explain that the question concerns how fast the video **feels**, not whether
   it is good, enjoyable, exciting, appropriate, or harmful.
2. Show all five response options and verbal anchors.
3. Explain that after each clip the adult will first predict how fast it would
   feel to a `[target-age]` child and then rate how fast it felt personally.
4. Explain that the prediction answer is final once submitted and that the two
   answers do not have to be the same.
5. Use an IRB-approved practice item that is not one of the 12 study clips.
6. Confirm that the participant understands the direction of the scale. Do not
   coach the participant toward any particular pace judgment.

### Step 4: Complete the adult rating sequence

The sequence contains all 12 clips once.

For every trial:

1. Display the next clip according to the frozen/randomized order.
2. Play the complete 30-second clip with the approved playback settings.
3. Display only the primary prediction question: **How fast do you think this
   video would feel to a [target-age] child?**
4. Record one response from 1 through 5 and lock it against revision.
5. Replace the prediction screen with the self-perception question: **How fast
   did this video feel to you?** Do not show the prediction response.
6. Record one response from 1 through 5.
7. Store two linked response rows with the participant ID, perspective, clip
   label, trial position, response sequence, ratings, and clip-order condition.
8. Continue until all 12 clips have been viewed and both questions answered.

Each adult therefore produces:

- 12 adult self-perception ratings;
- 12 adult child-prediction ratings; and
- 24 total ratings from 12 clip viewings.

The revised working estimate is approximately 10–15 minutes including
instructions and responses. Confirm the actual duration during piloting.

### Step 5: Finish the adult session

1. Confirm that the response file contains 24 expected ratings linked to 12
   clip viewings, or documented missing responses.
2. Present the approved debriefing information.
3. Do not reveal clip feature labels or preliminary group results in a way that
   could be communicated to future participants while recruitment is active.

## Phase 2: Child participants

Children report only their own perception. They do not predict adults, complete
an adult-prediction block, or make forced-choice judgments between paired clips.

### Step 1: Permission, assent, and eligibility

1. Obtain the IRB-approved parent or guardian permission before participation.
2. Present the child assent information in age-appropriate language.
3. Confirm that the child falls within the approved age range.
4. Assign an anonymous participant ID and record the child's exact age for
   descriptive reporting. Age moderation is not currently a planned analysis.

### Step 2: Explain and practice the scale

1. Explain that there are no right or wrong answers; the study asks how fast
   each video feels to the child.
2. Show and read all five anchors: Very slow, Slow, In between, Fast, Very fast.
3. Use an IRB-approved practice item that is not one of the 12 study clips.
4. Ask the child to demonstrate or explain which end means slow and which means
   fast. Repeat the neutral instructions if necessary; do not suggest a rating.
5. Follow a predetermined rule if the child cannot use the scale after the
   approved explanation. That rule must be finalized before data collection.

### Step 3: Complete the child rating block

The child views all 12 clips once in the frozen/randomized order.

For every trial:

1. Display the next clip.
2. Play the complete 30-second clip with the same approved playback settings
   used for adults.
3. Ask: **How fast did this video feel to you?**
4. Display the five response options and record one response from 1 through 5.
5. Store the participant ID, child block, clip label, trial position, response,
   and order condition.
6. Continue until all 12 clips have been rated, using only standardized neutral
   breaks permitted by the protocol.

Each child therefore produces:

- 12 child self-perception ratings; and
- 12 total clip viewings and ratings.

The working estimate is approximately 8–12 minutes including instructions and
responses.

### Step 4: Finish the child session

1. Confirm that the response file contains 12 expected ratings or documented
   missing trials.
2. Thank and debrief the child using the approved age-appropriate wording.
3. Complete any approved parent/guardian closing or compensation procedure.

## How the three sets of ratings answer the study questions

### 1. Adult prediction accuracy

Aggregate children's ratings for each clip according to the final statistical
plan. Those aggregate child judgments are the criterion against which adult
predictions are compared. The analysis asks whether adults correctly estimate
which clips children experience as slower or faster and whether adults
systematically over- or underestimate the magnitude of children's ratings.

### 2. Adult anchoring on their own perception

Compare each adult's self-ratings with that adult's child-prediction ratings.
This tests whether predictions are closely anchored to adults' own experiences
of the same clips. Because both questions follow the same viewing, question
context or a desire to answer consistently could increase the observed
association. The fixed prediction-first sequence protects the primary outcome,
but this anchoring analysis must remain exploratory and acknowledge the shared-
viewing limitation.

### 3. Matched feature contrasts

For each analytical pair, compare ratings for the lower-feature clip with
ratings for its higher-feature partner:

- two rating contrasts primarily test cut rate while matching motion and audio
  intensity;
- two primarily test motion while matching cuts and audio intensity; and
- two primarily test audio intensity while matching cuts and motion.

The two pairs per feature provide a small within-study replication check. If
both motion pairs show a similar pattern, that is more informative than a
result based on one scene. It remains exploratory because naturally occurring
clips differ in content and only two pairs represent each feature.

### 4. Relationship to continuous feature measurements

The clip ratings may also be related to the continuous manually verified cut
counts and frozen automated motion and audio-intensity values. Automated
Version 1 and Version 2 cut values describe the stimulus-search and calibration
workflow rather than replacing the final manual cut measure. This analysis is
exploratory. High/low labels are relative to the candidate pool, and the study
cannot infer that a feature caused a rating difference.

## Data structure expected from the participant application

At minimum, store one row per rating with these fields:

| Field | Purpose |
|---|---|
| `participant_id` | Anonymous link between one participant's trials |
| `participant_group` | Adult or child |
| `block_type` | `adult_self`, `adult_prediction`, or `child_self` |
| `target_age_wording` | Exact age adults were instructed to imagine; blank for children |
| `counterbalance_condition` | Frozen/randomized clip-order condition |
| `response_sequence` | `prediction_then_self` for adults; `child_self` for children |
| `clip_label` | A1, B1, C1-L, and so forth |
| `source_file_id` | Frozen participant-facing stimulus identity |
| `trial_order` | Position in the block |
| `pace_rating` | Integer 1–5 |
| `completed` | Whether the trial produced a usable response |

Do not overwrite raw responses during cleaning. Record exclusions and derived
variables separately so every analysis can be traced to the participant's
original answer.

## Decisions still required before data collection

- the exact child target age used in the adult-prediction wording;
- the final recruited age range if narrower than 8–12;
- the visual presentation of the five anchors and whether turtle/rabbit imagery
  survives child piloting;
- the exact practice item and comprehension rule;
- the adult demographic/background questions and child descriptive fields;
- the clip-order randomization method and whether pair members are prohibited
  from consecutive positions;
- rules for pauses, replay, unanswered items, withdrawal, technical failures,
  and participant exclusion;
- sample size and power justification;
- confirmatory versus exploratory analyses and the statistical model; and
- all consent, permission, assent, recruitment, compensation, privacy,
  debriefing, and data-retention language required by Cedarville University and
  the reviewing IRB.

## Related documents

- [Study aims and stimulus criteria](STUDY_AIMS_AND_STIMULUS_CRITERIA.md)
- [CMAT clip-selection workflow](STUDY_CLIP_SELECTION.md)
