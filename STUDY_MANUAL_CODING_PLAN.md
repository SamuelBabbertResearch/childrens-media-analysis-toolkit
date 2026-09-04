# Adult Prediction of Children's Perceived Media Pacing

## Frozen manual cut-coding plan

**Document status:** FROZEN BEFORE CODING  
**Freeze date:** 2026-08-18  
**Applies to:** Wave 1 calibration and Wave 2 prospective audit  
**Method:** Independent manual transition-event coding with blinded adjudication  
**Recipe context:** Version 1 for Wave 1 sampling; frozen Version 2 for Wave 2 sampling  
**Coding started at freeze:** No  

This plan is the study-specific coding authority. It preserves, and does not
edit, `validation/CODEBOOK.md`. Any later change requires an append-only
amendment in `STUDY_ANALYSIS_LOG.md`, a new dated plan version, and an explicit
decision about whether all previously coded clips must be recoded.

## Authority and frozen definitions

The transition definitions and incoming-shot timestamp convention come from
`validation/CODEBOOK.md`, SHA-256
`c15235ebe9b5ba62f0ee5f0217c85ab4339a6ba1c694726d652d89dd110dab53`,
as present on 2026-08-18. That file is labeled draft and contains inconsistent
wording about graphics over an unchanged shot. This study resolves the issue
without changing the shared codebook:

- The reported manual outcome is the number of genuine adjacent-frame hard
  shot boundaries experienced inside the 30-second interval.
- `hard_cut` means the incoming shot fully replaces the outgoing shot between
  adjacent frames, with no blend frames. Timestamp the first frame of the
  incoming shot.
- A whip-pan-disguised cut is a genuine adjacent-frame join. Record
  `transition_type=other`, `transition_subtype=whip_pan_disguised_cut`, and
  `counts_as_manual_hard_cut=true`.
- Pans, zooms, tilts, camera movement, character movement, and high motion
  within one continuous shot are not transitions and are not counted.
- Dissolves, fades, wipes, irises, and page turns are real transitions but are
  not hard cuts. Record them with their codebook type/subtype and
  `counts_as_manual_hard_cut=false`.
- A graphic or text element appearing over an unchanged underlying shot is not
  a hard cut. It may be recorded as `other` with subtype
  `non_boundary_graphic_overlay` for audit purposes, but it receives
  `counts_as_manual_hard_cut=false`.
- When a background shot changes beneath a graphic, code the underlying shot
  transition and note the graphic.
- If two or more blend frames are visible, code `dissolve`; otherwise code the
  adjacent-frame join as `hard_cut` unless a defined `other` subtype applies.
- An uncertain event is retained, described, and flagged. It is never silently
  guessed or deleted.

Accepted `transition_type` values are `hard_cut`, `dissolve`, `fade_out`,
`fade_in`, and `other`. Accepted study-specific `transition_subtype` values
include blank/not-applicable, `wipe`, `iris`, `whip_pan_disguised_cut`,
`page_turn`, `non_boundary_graphic_overlay`, and `other_described`.

## Frozen clip-boundary rule

Each source interval is half-open: `[absolute_start, absolute_end)`. For a
30-second clip, an event is inside the clip only when its clip-relative incoming
frame timestamp is strictly greater than `0.000` seconds and strictly less than
`30.000` seconds.

- A shot already present on the clip's first frame is not an experienced
  within-clip transition and is not counted, even if the source cut occurs
  exactly at the start boundary.
- An incoming frame at or after the exclusive end boundary is not counted.
- An incoming frame before the end boundary is counted even when it is very
  close to the end.
- `absolute_event_time_sec = source_start_sec + clip_relative_event_time_sec`.
- Record both seconds and `HH:MM:SS.mmm` timecodes. The source timecode is the
  authority if a rounded display value and frame stepping appear to disagree;
  record the frame-level issue in notes.

These same rules apply to source-window coding and later exact-file finalist
verification. In a standalone export, its first frame still cannot constitute
an experienced transition from an unseen prior frame.

## Wave 1 set and blinding

Wave 1 is exactly the 12 Version 1 rows frozen in the 2026-08-17
`selected_clips.csv`, measurement fingerprint `a5714394da4d`. The blind
worklist exposes only a neutral order, stable `clip_id`, source filename, source
hash, and absolute interval. It must not contain:

- automated detections or counts;
- motion or audio-intensity values;
- high/low or feature-profile labels;
- study labels such as A1/B1;
- target-feature labels; or
- pair identities or scores.

Coders must not open `candidates.csv`, `selected_clips.csv`, `matched_pairs.csv`,
`pair_candidates.csv`, generated clip tables, manifests containing automated
values, detection exports, CMAT result screens, or calibration output before
their independent coding and refinement files are locked and hashed.

The worklist order is deterministic: sort ascending by SHA-256 of
`"wave1-manual-blind-v1-2026-08-18|" + clip_id`. This permits exact
regeneration without revealing pair membership.

## Coders and independence

- Primary coder: Samuel Babbert, coder ID `SB01`.
- Reliability coder: Mia, coder ID `MIA01`. Her full identifying information,
  if required for the paper or internal records, belongs in a restricted coder
  crosswalk rather than the event table.
- Both coders independently code all Wave 1 clips and all eligible Wave 2 audit
  clips under the same frozen rules.
- Coders do not compare notes, event times, or counts until each coder's raw
  first-pass and refinement overlays for the entire wave are locked and hashed.
- Each session record states whether the coder saw automated detections,
  automated counts, feature labels, or pair assignments before completion.
  `coding_completed_without_automation=true` is permitted only if neither
  detections nor automated values were seen during coding or refinement.
- Any accidental exposure is logged immediately. The exposed coding is
  retained, flagged, and not silently discarded; an unexposed coder's record
  remains independently interpretable.

## Coding passes and immutable records

1. Verify the source file SHA-256 against the blind manifest.
2. Open only the named HD source and exact interval. Do not generate or inspect
   automated detections.
3. First pass: watch at normal speed, pause as needed, and record every possible
   transition with a rough relative timestamp, type, notes, and uncertainty.
4. Close the first-pass file, compute SHA-256, and record the hash in the
   session record. The first-pass file is then immutable.
5. Refinement pass: frame-step around every first-pass event and record all
   additions, modifications, or deletions in the append-only corrections file.
   Never edit the first-pass row. Every correction names the original event ID,
   original value, corrected value, reason, coder, date/session, and sequence.
6. Create a derived per-coder refined view from raw plus corrections. Label it
   derived; it never replaces either source.
7. Lock and hash all per-coder files before reliability comparison or
   adjudication.

Event IDs use `W1-<coder_id>-<blind_order>-E####` for Wave 1 and the equivalent
`W2-...` form for Wave 2. Correction and adjudication rows have their own IDs
and point back to the affected event IDs.

## Required event fields

Every manual event record contains at least:

- wave and method;
- recipe context/version;
- stable `clip_id` and neutral blind order;
- source filename and source SHA-256;
- absolute source start and end seconds/timecodes;
- clip-relative event seconds/timecode;
- absolute event seconds/timecode;
- transition type and subtype;
- `counts_as_manual_hard_cut`;
- coder ID;
- coding date and session ID;
- codebook path, version date, and SHA-256;
- notes and uncertainty flag;
- raw/correction/adjudication record provenance;
- adjudication status; and
- automation-blinding confirmation.

Valid uncertainty values are `true` and `false`. Valid adjudication states are
`not_compared`, `agreement`, `pending`, `resolved`, and `unresolved`.

## Reliability and adjudication

After both coders' files are locked, construct refined per-coder event sets and
compare them without viewing automated detections.

- Event correspondence uses the same frozen one-to-one matching algorithm and
  ±1.000-second tolerance defined in `STUDY_CALIBRATION_PLAN.md`.
- Preserve per-clip coder counts, exact count agreement, mean absolute count
  difference, signed count difference, and event-level precision/recall/F1
  treating one coder in turn as reference. Report a symmetric event agreement
  summary and the full disagreement table; do not reduce reliability to a
  correlation.
- Samuel and Mia jointly adjudicate all unmatched events, type/subtype
  disagreements, hard-cut-inclusion disagreements, uncertainty flags, and
  boundary cases while still blind to automated results.
- The adjudication table is append-only. It records both original values, the
  resolved value, evidence/reason, participants, date, and status.
- If agreement cannot be reached, set `unresolved`; retain both records. A clip
  cannot receive a final manual-reference count until all count-affecting
  disagreements are resolved. A faculty/methods reviewer may adjudicate an
  unresolved case, with identity and reason recorded.
- The adjudicated manual event set is the reference for detector comparison.
  It is derived from, and never overwrites, either coder's files.

## Frozen Wave 2 carry-forward

The same definitions, coders, boundary rule, fields, tolerance, independence,
correction mechanism, and adjudication procedure apply to Wave 2. Wave 1 clips
must be excluded from the prospective Wave 2 performance audit. If a Wave 1
clip is retained as a final candidate, it keeps its Wave 1 coding provenance
and does not become a Wave 2 audit observation.

## Rule changes and quality checks

No coding rule may change after the first coding session without all of the
following:

1. an append-only log entry describing the old rule, proposed rule, reason, and
   discovery point;
2. a new dated/versioned plan rather than silent editing of this frozen plan;
3. a determination for every completed clip of whether recoding is required;
4. recoding under a new file name if required, while preserving the original;
5. explicit reporting of the deviation.

Before accepting a coding file, verify unique IDs, valid clip IDs, event times
inside the half-open interval, arithmetic agreement between relative and
absolute times, valid types, required provenance, and a completed blinding
statement. Validation errors produce a new correction or derived file; they do
not authorize editing a locked raw file.

