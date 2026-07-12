# Transition Coding Codebook — CMAT Validation Study

**Status: DRAFT — finalize before the first coding session, then freeze.**
Any change after coding begins must be logged in VALIDATION_LOG.md with the date
and a note on whether previously coded episodes were re-checked under the new rule.

Coder: Samuel Babbert (single coder; see Limitations in VALIDATION_LOG.md)

---

## Transition types and operational definitions

| Type | Definition | Timestamp convention |
|---|---|---|
| `hard_cut` | Instantaneous shot change: the new shot fully replaces the old between two adjacent frames (no blend frames). | The first frame of the **incoming** shot. (Matches PySceneDetect's convention.) |
| `dissolve` | Gradual cross-fade: two shots are visibly superimposed for 2+ frames. | Approximate **midpoint** of the blend (the moment both shots are roughly equally visible). |
| `fade_out` | Image transitions to a solid color (usually black), no incoming shot during the fade. | Midpoint of the fade. |
| `fade_in` | Image emerges from a solid color. | Midpoint of the fade. |
| `other` | Anything else: wipes, iris transitions, whip-pan disguised cuts, page turns. Always add a note describing it. | Best-judgment center of the transition. |

## Decision rules

1. **Fade-out followed by fade-in across black = TWO events** (one `fade_out`, one `fade_in`),
   even when they feel like a single act break.
2. **Unsure whether it's a hard cut or a very short dissolve?** Frame-step through it
   (VLC: `E` key). If you can see 2 or more blend frames, code `dissolve`; otherwise `hard_cut`.
3. **Camera movement within a shot** (pans, zooms, character motion) is NOT a transition.
   Do not code it, even if the whole frame changes appearance.
4. **Ambiguous beyond resolution:** code `other`, describe it in the notes column,
   and flag it in the session log. Never silently guess.
5. **Do not consult the tool's detections CSV before or during coding.**
   Coding must be blind. Run `template` before `export`, and do not open any
   `*_detections.csv` for an episode until its manual CSV is complete and saved.
6. **Graphic / text overlays.** A title card, caption, or lower-third that fades or
   slides in *over an unchanging background shot* is coded `other` with a note — NOT
   `dissolve`. `dissolve` requires the underlying **shot** to change (two shots
   superimposed). A graphic animating on top of a held shot is not a shot boundary.
   If the background shot *also* changes during the overlay, code the underlying
   transition (`hard_cut` / `dissolve`) and mention the overlay in the note.
   (Added 2026-07-04 while coding the *A Charlie Brown Christmas* title card at ~02:11.)

## Scene-relation labeling (within-scene vs scene-change cuts)

For each `hard_cut` row, optionally fill a `scene_relation` column with `within`
or `change`. This is the ground truth for the cut-classifier (which distinguishes
low-cost shot-reverse-shot cuts from scene relocations — Lang's related vs
unrelated cuts). Only `hard_cut` rows are graded; leave it blank for other types.

**The core test:** does the viewer's mental model of *where we are* and *who is
here* survive the cut? If yes → `within`. If the viewer must reorient → `change`.

**`within` (in-scene, "related" cut — low processing cost):**
- Shot-reverse-shot dialogue: A talking → B talking → A. Same room, same
  conversation, same moment ("back to mama bear").
- Cutaway to a detail in the same space (close-up of hands, an object on the
  table) and back.
- Reframing the same location: wide shot → close-up of a character standing in
  that same place; a zoom rendered as a cut.
- POV shot: a character looks → what they see (still the same scene, their angle).

**`change` (out-of-scene, "unrelated" cut — high processing cost):**
- New location: inside the house → outside; kitchen → bedroom; home → landscape.
- Time jump: day → night, "meanwhile…", a later moment the viewer must place.
- Cut to a different set of characters or a different storyline thread.
- Cut to a fantasy / imagination / dream insert (a new mental space) — common in
  fantastical shows; relevant for the SpongeBob comparison.

**Decision rules:**
a. Establishing shot → a detail *within* that established place = `within`.
b. Same physical location but a clear time jump = `change` (temporal reorientation
   still forces a model update). Note it.
c. Genuinely unsure → make your best call and add a note. Consistency across the
   episode matters more than any single borderline decision.
d. This is judged from CONTENT (place/characters/time), not from how visually
   different the two shots look. A close-up reverse shot can look very different
   yet still be `within`; two similar-looking snowy fields can be a `change`.
   (This is exactly where the pixel-based classifier is expected to disagree —
   which is what the grading measures.)

Accepted cell values (normalized on load): `within` / `in` / `same` all map to
within; `change` / `scene` / `new` / `out` all map to change.

## Coding procedure (per episode)

1. `python validate_cuts.py template "<video path>"` → creates `validation/<stem>_manual.csv`.
2. **Pass 1 — realtime:** watch the episode at normal speed in VLC, pausing to log each
   transition with a rough timestamp (`Ctrl+T` shows current time) and type.
3. **Pass 2 — refinement:** jump to each logged timestamp (`Ctrl+T` to seek), frame-step
   (`E`) to pin down the exact moment per the timestamp conventions above, correct types.
4. Record the session in VALIDATION_LOG.md: date, episode, time spent, count of
   transitions coded, any ambiguous cases.

Useful VLC keys: `E` = frame-step forward · `Shift+←/→` = 3s jump · `Ctrl+T` = go to time.

## Timestamp accuracy target

Within ±1 second of the true frame. The comparison tolerance (default ±2.0s) absorbs
small errors; for fast-cut content (YouTube baselines) use `--tolerance 1.0` and be
correspondingly more careful, since cuts can be less than 2s apart.

## Coding-window rule (segment-based coding)

Full episodes are preferred. If an episode is too dense to code in full (e.g., MrBeast),
a contiguous segment is acceptable **only if the segment bounds are chosen and written
into VALIDATION_LOG.md before watching the episode** (e.g., "minutes 5:00–10:00").
Pass the same bounds to `compare --start --end` so false positives outside the window
are excluded from scoring.
