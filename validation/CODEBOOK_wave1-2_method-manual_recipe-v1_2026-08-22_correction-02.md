# Adult Prediction of Children's Perceived Media Pacing

## Frozen Wave 1 and Wave 2 transition-coding codebook — correction 02

**Document status:** FROZEN METHODOLOGICAL AUTHORITY; SOFTWARE CONFORMANCE AND
PRE-USE QUALIFICATION STILL REQUIRED  
**Decision/freeze date:** 2026-08-22  
**Applies to:** Wave 1 manual calibration coding, Wave 2 prospective-audit
coding, and exact-file finalist verification  
**Method:** Independent manual transition-event coding  
**Recipe context:** Automated Version 1 baseline and the future frozen Version 2  
**Coding performed under this version at freeze:** None  
**Codebook identifier:** `APC-PACING-TRANSITIONS-C02-2026-08-22`

This is the study-specific authority for the correction-02 release. It does
not alter or replace the preserved source file `validation/CODEBOOK.md`, whose
2026-08-18 SHA-256 is
`c15235ebe9b5ba62f0ee5f0217c85ab4339a6ba1c694726d652d89dd110dab53`.
That earlier file remains historical input and is not the coding authority for
new research data.

This document freezes the five methodological decisions Samuel approved on
2026-08-22 and the primary automated-versus-manual boundary tolerance of
plus or minus 0.250 seconds. No authoritative coding may begin until a new
correction-02 tool and package conform to this document and receive a separate
pre-use GO decision.

## Unit of coding

The transition-event table contains only genuine boundaries between shots.
Camera movement, character movement, graphic overlays over a continuing shot,
flashes, and other within-shot changes are not transition events. Potential
non-boundary causes of automated false positives belong in a separate
non-boundary-observation table.

The primary manual cut measurement is the number of verified `hard_cut` events
inside each 30-second clip. Other transition types remain important descriptive
data but do not enter the primary hard-cut count.

## Frozen transition taxonomy

| `transition_type` | Operational definition | Required timing | Counts as a manual hard cut? |
|---|---|---|---:|
| `hard_cut` | The incoming shot fully replaces the outgoing shot between two adjacent decoded frames. There is no genuine optical blend frame. | Record the first frame of the incoming shot. | Yes |
| `single_frame_blend` | Exactly one decoded frame visibly combines the outgoing and incoming shots. Use this category instead of automatically calling the event a clean hard cut. | Record the blended frame and the first fully incoming frame. | No in raw coding; adjudication required |
| `dissolve` | The outgoing and incoming shots are visibly superimposed across two or more decoded frames. | Record the gradual start and end frames; derive, do not hand-enter, the midpoint. | No |
| `fade_out` | The outgoing image gradually changes to a solid color, usually black, without an incoming shot appearing during the fade. | Record the gradual start and end frames. | No |
| `fade_in` | An image gradually emerges from a solid color. | Record the gradual start and end frames. | No |
| `wipe` | A traveling line or shaped edge replaces the outgoing shot with the incoming shot; the two shots occupy separate parts of the frame rather than being optically superimposed. | Record the gradual start and end frames. | No |
| `iris` | A hard-edged aperture expands or contracts to reveal or conceal the image while the remainder is a solid color. | Record the gradual start and end frames. | No |
| `other` | A genuine shot boundary that fits none of the frozen types. | Record a single boundary frame or gradual extent, as observable, and describe it. | No unless a later adjudication explicitly resolves it to `hard_cut` |

Accepted `transition_type` values are therefore exactly:

```text
hard_cut
single_frame_blend
dissolve
fade_out
fade_in
wipe
iris
other
```

### Hard cuts masked by whip pans

A genuine adjacent-frame replacement hidden by rapid motion blur remains
`transition_type=hard_cut`. Record `whip_pan_masking=true`. If frame stepping
shows continuous camera movement with no shot replacement, there is no
transition and no transition-event row.

The masking flag is nonexclusive metadata explaining why a real hard cut may
be difficult for an automated detector. It does not create a new transition
type and does not change the hard-cut count.

### Exactly one blended frame

Exactly one confirmed blended frame is coded
`transition_type=single_frame_blend`, `uncertainty_flag=true`, and
`adjudication_status=pending`. Its raw row has
`counts_as_manual_hard_cut=false`.

Adjudication must determine whether the frame is:

- a genuine one-frame optical transition, which remains
  `single_frame_blend` and does not count as a clean hard cut; or
- a decoding, deinterlacing, or transcoding artifact surrounding an otherwise
  adjacent-frame editorial cut, which is resolved in a separate adjudication
  record to `hard_cut` with the artifact explained.

The raw coder row is never rewritten. A resolved classification is produced
only in the derived adjudicated reference.

### Wipes, irises, and page turns

`wipe` and `iris` are first-class transition types. A page turn/page peel is
recorded as `transition_type=wipe` with
`transition_subtype=page_turn`. A standard wipe uses a blank subtype. An iris
has an expanding or contracting aperture against a solid field; a wipe has a
traveling boundary separating two shots.

For `other`, `transition_subtype=other_described` and a substantive note are
required. A coder must not use `other` merely because a defined case is
difficult to judge.

## Gradual-transition extent rule

For `dissolve`, `fade_out`, `fade_in`, `wipe`, and `iris`, record both ends of
the observable transition:

- `start_frame_index`: the first displayed frame on which the outgoing-only or
  solid-only state has visibly begun to change;
- `end_frame_index`: the first displayed frame on which the destination state
  is fully established—an incoming-only image for a dissolve, wipe, iris-in,
  or fade-in; a solid-only image for a fade-out or iris-out; and
- the corresponding clip-relative and absolute timestamps for both frames.

The derived midpoint is `(start_time + end_time) / 2`. Coders do not replace
the start/end observations with a hand-entered midpoint. If an endpoint falls
outside the clip, retain the visible in-clip endpoint, set the appropriate
boundary-censoring flag, and explain the missing endpoint in notes.

## Fade-pair rule

A fade-out followed by a fade-in through a solid-color interval is preserved
as two observable optical-event rows: one `fade_out` and one `fade_in`.

- Give both rows the same `fade_pair_id` when both are visible in the clip.
- Derive and preserve `black_gap_frames`, meaning the number of decoded frames
  between the fade-out endpoint and fade-in start that show only the solid
  color.
- If only one member is visible because of a clip boundary, leave the pair ID
  blank and record `unpaired_due_to_boundary` in notes.
- For shot-structure reporting, one complete fade-out/fade-in pair represents
  one derived fade-through-color transition. For optical-event reporting, it
  remains two rows. Reports must label which count is being presented.

Neither row is a manual hard cut.

## Non-boundary observations

Do not enter a graphic or text overlay in the transition-event table when the
underlying shot continues unchanged. Record it, if relevant to detector-error
analysis, in a separate non-boundary-observation overlay keyed by `clip_id` and
frame/time.

The frozen observation types are:

```text
graphic_overlay
flash_or_luminance_change
heavy_camera_motion
other_described
```

`other_described` requires notes. If the underlying shot changes while a
graphic is present, record the genuine transition in the transition table and
record or note the overlay separately.

## Clip-boundary rule

Each source interval is half-open: `[absolute_start, absolute_end)`. For the
30-second coding files, an event is eligible only when all of the following are
true:

```text
displayed frame index > 0
clip-relative event timestamp > 0.000 seconds
clip-relative event timestamp < 30.000 seconds
```

Frame index zero is the first displayed frame. It is not codeable because the
outgoing frame immediately before it is not visible in the coding file. The
coding-media frame maps show that this first displayed frame can occur slightly
after nominal time zero; that short head interval is unobservable and must not
be treated as an ordinary detector miss.

An event at or after the exclusive end is not counted. An eligible incoming
frame strictly before the end is counted even when it is very close to the
boundary. Record `boundary_or_range_handling` during error-mechanism review
when an automated/manual discrepancy arises from these rules.

For a point event:

```text
absolute_event_time_sec = source_start_sec + clip_relative_event_time_sec
```

For a gradual event, apply the same arithmetic separately to its recorded
start and end. The same first-frame and exclusive-end principles apply during
exact exported-file verification.

## Uncertainty, correction, and adjudication

Coders retain uncertain observations instead of silently guessing or deleting
them. Raw first-pass rows are immutable after locking. Refinements are stored
as append-only corrections, and coder disagreements are stored in a separate
append-only adjudication overlay.

Valid adjudication states are exactly:

```text
not_compared
agreement
pending
resolved
unresolved
```

`not_adjudicated` is not valid. A final manual-reference count cannot be issued
for a clip while a count-affecting event remains `pending` or `unresolved`.

## Blinding

Before each coder's wave files are locked and hashed, the coder must not see
automated detections, automated cut counts, motion or audio-intensity values,
feature labels, pair assignments, or pair scores. Every session records whether
coding was completed without such exposure. Accidental exposure is retained
and documented rather than concealed.

## Automated/manual boundary matching

The primary detector comparison uses one-to-one matching at plus or minus
**0.250 seconds**. Matching first maximizes the number of matched pairs and
then minimizes their total absolute time difference. One automated detection
cannot match more than one manual boundary, and vice versa.

Plus or minus **1.000 second** is retained only as a prespecified secondary
sensitivity analysis. It is not used to select Version 2. Neither tolerance
may be changed after automated calibration results are viewed.

## Change control

Any later rule change requires a new dated codebook version, an append-only
analysis-log entry, and a documented determination of whether previously coded
clips require recoding. Corrections never overwrite this file or any raw coder
data.
