# Adult Prediction of Children's Perceived Media Pacing

## Frozen manual cut-coding plan — correction 02

**Document status:** FROZEN METHODOLOGICAL AUTHORITY; CORRECTION-02 SOFTWARE,
PACKAGE, AND PRE-USE GO STILL REQUIRED  
**Freeze date:** 2026-08-22  
**Applies to:** Wave 1 calibration and Wave 2 prospective audit  
**Method:** Independent manual transition-event coding with blinded
reliability coding and adjudication  
**Recipe context:** Version 1 for Wave 1 sampling; future frozen Version 2 for
Wave 2 sampling  
**Coding started under this plan at freeze:** No

This document supersedes `STUDY_MANUAL_CODING_PLAN.md` only for the future
correction-02 package. The 2026-08-18 plan remains preserved unchanged with
SHA-256
`e0e86d1a4ce2df8294944a6023ae6b79105cd38e22cf4f6319135d85c39dbe28`.
The empty correction-01 session pins the earlier authority and must not be
resumed or rewritten.

The transition authority is
`validation/CODEBOOK_wave1-2_method-manual_recipe-v1_2026-08-22_correction-02.md`,
SHA-256
`b46bdaab419d1e33138d2bf3a6e98a5b6bf80f7fa97fcf311c2c18b905906f90`.
No coding tool or package is conformant merely because these documents exist.
The correction-02 package must pin and verify their exact hashes and receive a
new pre-use qualification result before real coding.

## Frozen manual outcome and definitions

The primary manual outcome is the adjudicated number of genuine
adjacent-frame `hard_cut` shot boundaries experienced inside each 30-second
interval. The following frozen rules apply:

- A clean adjacent-frame replacement is `hard_cut` and counts as one manual
  hard cut.
- A cut hidden by a whip pan remains `hard_cut`; store
  `whip_pan_masking=true` as separate nonexclusive metadata.
- Pans, zooms, tilts, heavy camera motion, character movement, and other motion
  within a continuous shot are not transitions.
- A graphic or text overlay over a continuing shot is not a transition and is
  recorded, when relevant, only in the separate non-boundary-observation
  overlay.
- Exactly one confirmed blended frame is `single_frame_blend`, uncertain and
  pending adjudication; it is not automatically counted as a clean hard cut.
- Two or more blend frames are `dissolve`.
- Dissolves, fades, wipes, irises, and page turns are genuine gradual
  transitions but are not manual hard cuts.
- A page turn is `transition_type=wipe` with
  `transition_subtype=page_turn`.
- Every gradual transition retains start and end frames/timestamps; its
  midpoint is derived.
- A fade-out/fade-in through a solid color remains two optical-event rows with
  one shared `fade_pair_id`; the derived shot-structure count treats a complete
  pair as one fade-through-color transition.
- Uncertain observations are retained, described, and resolved through a
  separate adjudication record. Raw coding is never silently changed.

The accepted transition types, timing definitions, fade rules, observation
types, and adjudication vocabulary are exactly those in the frozen
correction-02 codebook.

## Frozen clip-boundary rule

Each source interval is half-open: `[absolute_start, absolute_end)`. An event in
a 30-second coding file is eligible only when:

```text
displayed frame index > 0
clip-relative event timestamp > 0.000 seconds
clip-relative event timestamp < 30.000 seconds
```

Frame index zero is the first displayed frame. It cannot establish a
within-clip transition because its preceding outgoing frame is not available.
The frame maps show first-frame offsets of approximately 0.002–0.041 seconds,
so that short head interval is explicitly unobservable. An incoming frame at
or after the exclusive end is not counted. An eligible frame strictly before
the end is counted.

For point events:

```text
absolute_event_time_sec = source_start_sec + clip_relative_event_time_sec
```

For gradual events, calculate start and end absolute timestamps separately.
The exact decoded-frame map, not a rounded playback display, controls the
recorded timestamp. Record any decoder, mapping, or range ambiguity in notes.
The same rule applies to the later exact participant-facing exports.

## Wave 1 calibration set

Wave 1 remains exactly the 12 Version 1 rows frozen in the original
2026-08-17 `selected_clips.csv`, with measurement fingerprint
`a5714394da4d`. These are calibration candidates, not participant finalists.
Their clip IDs and absolute source intervals do not change in correction-02.

The authoritative stimulus pool remains the 30 Season One HD files and 1,320
eligible windows. Season Two remains an excluded exploratory feasibility run.

## Blinding and browser disclosure

The coder-facing browser display may expose only the neutral `blind_id`, blind
order, coding media, and information needed to operate the coding interface.
The source-derived stable `clip_id` is retained in private saved records but is
not displayed because it contains an episode identifier. The browser must not
display:

- source episode filename or source timecode;
- automated detections or automated cut counts;
- motion or audio-intensity values;
- high/low or feature-profile labels;
- study labels such as A1/B1;
- target-feature labels; or
- pair identities or pair scores.

Source filename, source hash, and absolute interval remain required research
provenance. The correction-02 server obtains them from its verified private
manifest and writes them into event records without exposing them in the
browser bootstrap. A coder may receive a neutral troubleshooting code that
does not reveal episode identity.

Coders must not open the automated candidate tables, selected-clip tables,
generated tables, automated manifests, detection exports, CMAT result screens,
or calibration output before their complete wave files are locked and hashed.

Each session records separate attestations that the coder did not see
automated detections, counts, feature labels, pair assignments, or pair scores.
An accidental exposure is logged immediately; the affected record is retained
and flagged rather than discarded.

## Coders and independence

- Primary coder: Samuel Babbert, coder ID `SB01`.
- Reliability coder: Mia, coder ID `MIA01`.
- A restricted crosswalk may retain additional identifying information; event
  tables use only coder IDs.
- Both coders independently code all 12 Wave 1 clips and all eligible Wave 2
  audit clips under this same authority.
- Coders do not compare notes, events, or counts until both coders' complete
  raw and correction records for the wave are locked and hashed.
- Automated outputs remain sealed until reliability comparison and manual
  adjudication are complete.

## Coding passes and immutable records

1. Verify the correction-02 contract and media-manifest hashes before a session
   can start.
2. Watch each clip once from beginning to end at normal speed before marking
   the clip complete. Pause or replay only under the documented coding
   procedure; participant replay rules are separate.
3. During the first pass, record every possible shot transition with its frame,
   timing information, type, subtype, notes, uncertainty, and approved
   auxiliary fields.
4. Record graphic overlays and other relevant non-boundary phenomena in a
   separate non-boundary-observation file, never the transition-event table.
5. Lock and hash the first-pass event and observation files. They are then
   immutable.
6. Frame-step every first-pass event. Put additions, modifications, and
   deletions in an append-only correction overlay referencing the original
   event ID; never edit the raw row.
7. Generate a clearly labeled derived per-coder refined view from raw plus
   corrections. It never replaces its source records.
8. Lock and hash all per-coder records for the whole wave before reliability
   comparison or adjudication.

Event IDs use `W1-<coder_id>-<blind_order>-E####` for Wave 1 and `W2-...` for
Wave 2. Observation, correction, fade-pair, and adjudication records have their
own IDs and reference the affected event IDs.

## Required transition-event fields

Every raw transition event contains at least:

- wave, method, and recipe context/version;
- stable `clip_id` and neutral blind order;
- source filename and source SHA-256, populated from the verified private
  manifest;
- absolute source start and end seconds/timecodes;
- point-event frame index, clip-relative timestamp, and absolute timestamp,
  where applicable;
- gradual start/end frame indexes, clip-relative timestamps, and absolute
  timestamps, where applicable;
- derived midpoint, labeled as derived, for gradual transitions;
- transition type and subtype;
- `whip_pan_masking`;
- `fade_pair_id` and boundary-censoring flags where applicable;
- `counts_as_manual_hard_cut`;
- coder ID, coding date, and session ID;
- codebook identifier, path, freeze date, and SHA-256;
- coding-plan path, freeze date, and SHA-256;
- notes and uncertainty flag;
- raw/correction/adjudication provenance;
- adjudication status; and
- automation-blinding confirmations.

Valid uncertainty values are `true` and `false`. Valid adjudication states are
exactly `not_compared`, `agreement`, `pending`, `resolved`, and `unresolved`.
`not_adjudicated` is invalid.

## Required non-boundary-observation and fade-pair records

The non-boundary file is a separate overlay keyed by `clip_id`, coder, session,
frame/time, and codebook provenance. Its accepted observation types are
`graphic_overlay`, `flash_or_luminance_change`, `heavy_camera_motion`, and
`other_described`. Notes are required for `other_described`.

The derived fade-pair table links the two raw optical-event IDs, stores the
shared `fade_pair_id`, `black_gap_frames`, boundary-censoring status, and the
rule used to derive one shot-structure transition. It does not delete or merge
the two raw event rows.

## Reliability and adjudication

After both coders' wave files are locked, create refined per-coder event sets
and compare them while automated results remain sealed.

- Primary event correspondence uses the frozen one-to-one matcher and
  **plus or minus 0.250-second tolerance** in the correction-02 calibration
  plan.
- Plus or minus 1.000 second is a prespecified sensitivity analysis only.
- Preserve per-clip coder hard-cut counts, exact count agreement, mean absolute
  count difference, signed count difference, event-level TP/FP/FN, precision,
  recall, and F1 in both reference directions.
- Report a symmetric event-agreement summary and the complete disagreement
  table; correlation alone is insufficient.
- Separately summarize type/subtype agreement, whip-pan flags, gradual extents,
  single-frame-blend cases, non-boundary observations, and fade pairing.

Samuel and Mia jointly adjudicate unmatched events, timing differences,
type/subtype disagreements, hard-cut inclusion, one-blend-frame cases,
whip-pan masking, uncertainty, fade pairing, gradual extents, and boundary
cases while still blind to automated output.

The adjudication overlay is append-only and preserves both original values,
the resolved value, evidence/reason, participants, date, and status. A clip
cannot receive a final manual-reference count while any count-affecting case is
`pending` or `unresolved`. A faculty or methods reviewer may resolve an
otherwise unresolved case, with identity and reasoning recorded.

## Frozen Wave 2 carry-forward

Wave 2 uses the same definitions, coders, boundary rules, fields, tolerances,
independence, corrections, and adjudication. Wave 1 clips cannot contribute to
prospective Wave 2 performance metrics. A Wave 1 clip retained for final
consideration keeps its Wave 1 provenance and is not relabeled as a Wave 2
audit observation.

## Rule changes and acceptance checks

No coding rule may change after the first correction-02 session without:

1. an append-only log entry describing the old rule, new rule, reason, and
   discovery point;
2. a new dated codebook and plan rather than silent editing;
3. a determination for every completed clip of whether recoding is required;
4. recoding under new filenames when required, while preserving originals; and
5. explicit reporting of the deviation.

Before accepting a coding file, verify unique IDs, valid clip IDs, exact frozen
vocabularies, valid frame indexes and timestamps, relative/absolute arithmetic,
required provenance, fade-pair consistency, separation of non-boundary
observations, and completed blinding attestations. A validation error produces
an append-only correction or a new derived file; it never authorizes editing a
locked raw file.
