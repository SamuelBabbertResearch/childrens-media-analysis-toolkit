# Adult Perceptions of Pacing in Children’s Television

## Step-by-Step Adult-Only Study Procedure

**Decision date:** 2026-08-31  
**Status:** Working procedural specification with an adult-only software-pilot
implementation dated 2026-09-01. Final consent wording and IRB approval remain
required before data collection.  
**Governing decision:**
[STUDY_ADULT_ONLY_REDESIGN_DECISION_2026-08-31.md](STUDY_ADULT_ONLY_REDESIGN_DECISION_2026-08-31.md)

This document replaces
`STUDY_PROCEDURE_ADULT_AND_CHILD_PHASES.md` as the active participant procedure.

## 1. Design summary

- Participants: adults age 18 or older only.
- Session: one session of approximately 8–12 minutes.
- Stimuli: 12 unique 30-second *Curious George* clips.
- Structure: six analytical pairs, with two contrasts primarily in cut rate,
  two in visual motion, and two in audio intensity.
- Rating burden: one own-perception rating after each clip.
- Outcome: adult perceived pacing.
- Interpretation: associational; no inference about children's perceptions.

Adults are not asked to predict how a child would respond. No children are
recruited, and no parent/guardian permission or child assent process is used.

## 2. Participant-facing question and scale

After every study clip, the participant answers:

> How fast did this video feel?

The ordered response options are:

1. Very slow
2. Slow
3. In between
4. Fast
5. Very fast

No response is selected by default. A participant may revise a selection until
confirming it. After confirmation, the response is locked and the next trial
begins.

The participant never sees:

- the source episode title or timecode;
- the analytical pair assignment;
- cut, motion, or audio measurements;
- high/low feature labels;
- a statement that one clip is expected to feel faster; or
- language asking the participant to imagine a child's response.

## 3. Recruitment and eligibility

### Inclusion criteria

- Age 18 or older.
- Current undergraduate or graduate student at Cedarville University.
- Able to understand the approved English-language consent and task
  instructions.
- Able to see and hear the clips with approved accommodations.

### Frozen recruitment decisions

- Target enrollment: 50 Cedarville University students.
- Recruitment: posters and voluntary QR-code sign-up; classroom announcements
  may be used only when instructors cannot see who volunteers.
- No extra credit, grade-based incentive, or effect on grades.
- An instructor will not be told whether an individual student participates.

## 4. Session procedure

### Step 1: Consent and eligibility

1. Present the IRB-approved adult informed-consent information before any study
   activity.
2. Provide an opportunity to ask questions and sufficient time to decide.
3. Confirm that participation is voluntary and that declining or stopping has
   no penalty.
4. Confirm age eligibility and any approved technical eligibility criteria.
5. Assign an anonymous participant ID. Keep consent and scheduling records
   separate from response data.

### Step 2: Instructions and practice

1. Explain that the study asks how fast or slow each clip feels to the
   participant.
2. State that there are no correct answers and that the participant should use
   their own impression.
3. Demonstrate all five verbal response options without preselecting one.
4. Present the approved practice item using the same scale as the study trials.
5. Use the unrecorded direction check, “Which response means neither slow nor
   fast?” The participant continues after selecting `3. In between`.
6. Do not retain the practice response as an analyzed study rating.

### Step 3: Study trials

For each of the 12 clips:

1. Present the clip once under the approved display and volume settings.
2. Present the single adult self-perception question.
3. Do not preload or highlight a default. A participant may make an active
   response or use the explicit skip control.
4. Allow revision until the participant confirms.
5. Lock the confirmed response and append the trial record.
6. Continue according to the frozen clip order.

Normal replay is prohibited. If playback is technically interrupted, the clip
may be restarted from the beginning after the interruption is documented.

### Step 4: Close

1. Record completion, withdrawal, or technical termination status without a
   direct identifier in the rating file.
2. Present the approved debriefing language.
3. Handle questions without describing an individual rating as diagnostic or
   evaluative.

## 5. Ordering and masking

Use two fixed orders. Order B is the exact reverse of Order A. Assign Order A to
the first enrolled participant, Order B to the second, and alternate thereafter
in enrollment order. The software performs this assignment and retains a
rating-free assignment ledger. Both orders are explicit permutations of all 12
clip IDs and do not place members of an analytical pair consecutively.

Participants rate each clip independently. They are not asked to compare the
two members of a pair directly.

## 6. Pauses, withdrawal, and technical failures

- A participant may wait before starting the next clip, skip a rating, or stop
  at any time without penalty.
- A skipped rating remains missing and is recorded with `completion_status` =
  `skipped`; no scale value is imputed by the runner.
- Normal replay is unavailable. A clip can restart from the beginning only
  after the software detects a playback error.
- Closing an active session marks technical termination; the runner does not
  silently resume it.
- Reuse of an assigned anonymous participant code is refused. Researchers must
  keep the code/linking file separate from the response data.
- When a participant stops before the linking code has been deleted and the
  data have become fully de-identified, the session's rating rows are removed.
  Once data are fully de-identified, an individual participant's rows can no
  longer be identified for removal.
- Exclude ineligible participants, incomplete consent, withdrawal before
  de-identification, duplicate participation, and sessions made unusable by a
  technical failure. Freeze any additional analysis exclusions before
  inspecting outcome patterns.

## 7. Minimum response record

Each confirmed study rating should include at least:

| Field | Active adult-only value or meaning |
|---|---|
| `study_id` | Frozen study package identifier |
| `participant_id` | Anonymous session identifier |
| `block_type` | `adult_self` only |
| `question_id` | Adult own-perception pace item |
| `clip_id` | Frozen participant-facing clip label |
| `source_file_id` | Exact-file identifier or checksum-backed reference |
| `trial_order` | Presented position 1–12 |
| `counterbalance_condition` | Approved order identifier |
| `rating` | Integer 1–5 |
| `response_sequence` | `adult_self` |
| `session_status` | Separate restricted session-state record: `complete`, `withdrawn`, or `technical_termination` |
| `completion_status` | Per-rating value: `completed` or `skipped` |

No active row needs a child target age, adult-prediction response, child-self
response, parent field, or assent field.

## 8. Analysis alignment

The final analysis plan should distinguish:

- associations between continuous clip measurements and adult pace ratings;
- within-pair contrasts for cut rate, visual motion, and audio intensity;
- replication or inconsistency across the two pairs representing each feature;
  and
- participant- and clip-level variation in a repeated-measures model.

The plan must not contain adult-child agreement, prediction accuracy, or a
comparison between adult prediction and adult self-ratings.

## 9. OSF data sharing and persistent link

After the anonymized publication dataset, data dictionary, and analysis
materials are released publicly through the Open Science Framework, the
Principal Investigator can generate an OSF DOI for the public project or
registration. The resulting persistent DOI link can be used when sharing or
citing the dataset. The DOI must point only to the approved public materials
and must not expose restricted records, identifiers, copyrighted clips, or the
participant-linking file.

## 10. Implementation status

The 2026-09-01 Study Runner rewrite and schema-version-2 pilot package:

1. expose no participant-group selector, child block, prediction question, or
   target-age wording;
2. collect exactly one `adult_self` response opportunity for each of 12 clips;
3. use two fixed reverse orders and alternate assignment in enrollment order;
4. include researcher confirmation of adult eligibility and completed consent,
   participant instructions, an unrecorded direction-check practice item, skip
   and withdrawal controls, and technical-interruption-only restart;
5. record the minimum adult-only fields in the response export, with a blank
   rating and `skipped` status rather than an invented value; and
6. remove an identifiable session's response rows when the participant stops.

On 2026-09-01, 30 focused automated tests passed, the staged executable opened,
all 12 frozen media hashes validated, and Qt Multimedia loaded and advanced
playback for all 12 clips. Before participant use, a researcher must still
complete one visible and audible end-to-end session on the collection computer
and verify the configured consent-adjacent instructions, practice wording, and
debrief against the final IRB-approved materials.

No pilot or participant data collected under the old flow may be combined with
the revised adult-only study.

## 11. Related documents

- [Adult-only redesign decision](STUDY_ADULT_ONLY_REDESIGN_DECISION_2026-08-31.md)
- [Study aims and stimulus criteria](STUDY_AIMS_AND_STIMULUS_CRITERIA.md)
- [Participant pace-scale design](STUDY_RATING_SCALE_DESIGN.md)
- [Clip-selection workflow](STUDY_CLIP_SELECTION.md)
- [Study handover](STUDY_HANDOVER.md)
