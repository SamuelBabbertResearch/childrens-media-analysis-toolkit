# Adult-Only Participant Redesign Decision

**Decision date:** 2026-08-31  
**Researchers:** Samuel Babbert and Mia Engert  
**Current study title:** *Adult Perceptions of Pacing in Children’s Television*  
**Status:** Governing participant-design decision; faculty, statistical, and
IRB review are still required before recruitment or data collection.

## Decision

The participant study will recruit adults age 18 or older only. Each adult will
view the selected children's-television clips and rate the adult's own
perception of pacing. The participant task will not:

- recruit children;
- obtain parent or guardian permission or child assent;
- ask adults to predict how a child would perceive a clip; or
- treat adult judgments as substitutes for children's responses.

The working participant question remains:

> How fast did this video feel?

The five ordered response options remain *Very slow*, *Slow*, *In between*,
*Fast*, and *Very fast* unless faculty or piloting requires a later amendment.

## Why the design changed

Recruiting children would require additional review, permission, assent,
supervision, and recruitment protections. Samuel and Mia concluded that the
resulting approval and recruitment burden threatened the feasibility and
timeline of the study.

Asking adults to estimate children's perceptions was considered but rejected
as the replacement primary outcome. Such a response measures an adult's belief
about children, not children's actual perception. Without child ratings, the
accuracy of that belief could not be evaluated. Removing the prediction item
therefore produces a narrower and more defensible construct: adults' own
perceived pacing.

The revised design remains scientifically useful because it can test how adult
pace judgments are associated with measured formal characteristics of the
clips. It also reduces participant burden from two ratings after every clip to
one.

## What remains unchanged

- The stimulus domain remains short clips from *Curious George*, a single
  children's television program.
- The planned stimulus set remains 12 unique 30-second clips arranged as six
  matched analytical pairs.
- The matching dimensions remain manually verified cut rate, frozen automated
  visual motion, and frozen automated audio intensity.
- Participants rate clips individually and are not shown pair identities,
  feature labels, high/low labels, or CMAT measurements.
- Interpretation remains associational because naturally occurring clips do
  not isolate one feature experimentally.
- The existing measurement, calibration, manual-coding, and correction records
  remain valid for stimulus selection.

## What changes downstream

### IRB materials

The proposal, consent materials, recruitment language, task instructions,
risks, data fields, and appendices must describe one adult participant group and
one own-perception rating. Child permission, assent, parent-presence, target-age,
and adult child-prediction materials are removed.

### Participant software

At the time of this decision, the Study Runner and pilot package implemented
the superseded adult-prediction and child design and were barred from use.
**Implementation update (2026-09-01):** schema version 2 now exposes only the
adult self-perception flow and fails closed on the former schema. The staged
pilot build passed focused automated, package, launch, and technical playback
checks. It remains a software pilot—not an IRB-approved collection release—and
still requires a visible and audible manual pre-use session with final approved
wording on the collection computer.

### Rating scale

The five fully labelled verbal anchors remain appropriate. Child-oriented
evidence and the turtle/rabbit imagery are no longer necessary to justify an
adult-only scale. Whether the imagery is retained is an interface decision to
be settled before the adult pilot; it is not part of this participant-design
decision.

### Analysis

The primary analysis will model adult perceived-pace ratings as a function of
cut rate, visual motion, and audio intensity while accounting for repeated
ratings by participant and clip. Pairwise feature contrasts and replication
across the two pairs per feature remain useful, but no adult-child agreement or
prediction-accuracy analysis remains.

## Interpretation boundary

The revised study may describe adults' pacing judgments for the selected clips
and their associations with the measured clip characteristics. It cannot
establish how children perceive the clips, whether adult perceptions match
children's perceptions, or whether the findings generalize across children's
television beyond the selected program and clips.

## Provenance rule

The frozen recipe ID, recipe filename, recipe citation, manifests, inventories,
and dated correction records retain the earlier phrase *Adult Prediction of
Children's Perceived Media Pacing*. Those strings are historical identifiers
bound to existing hashes and outputs. They must not be silently renamed. Active
documents must label them as legacy names and use the new study title for the
current participant protocol.

## Superseded design

This decision supersedes the participant-design portions of
`STUDY_PROCEDURE_ADULT_AND_CHILD_PHASES.md`, the adult-prediction and child-flow
portions of `STUDY_HANDOVER.md`, and any undated prose elsewhere that describes
adult prediction ratings or child participants as part of the current study.
Frozen historical and measurement records remain unchanged.
