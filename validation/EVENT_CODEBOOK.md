# Fantastical Event Coding Codebook — CMAT

**Status: DRAFT — finalize before the first coding session, then freeze.**
Changes after coding begins must be logged in VALIDATION_LOG.md with date and
whether previously coded episodes were re-checked.

Coder: Samuel Babbert (single coder; second coder needed for inter-rater
reliability — the tool supports two-coder agreement).

---

## What this measures and why

The current literature (Hinten, Scarf & Imuta 2025 meta-analysis; Lillard 2026;
Hinten & Imuta 2026, all *Developmental Science*) converged on fantastical
content — not editing pace — as the driver of short-term executive-function
effects in young children. Studies operationalize fantasy as **fantastical
events per minute**, but no published taxonomy or coding scheme exists, and the
one property the mechanism debate says should be measured (narrative relevance;
Hinten & Imuta 2026) is measured nowhere. This codebook is CMAT's instrument
for that gap. Fantasy is a semantic judgment — it is coded by humans, by design.

**Operational anchor (Essex et al. 2025):** fantastical content involves
"characters or objects which undergo impossible physical or identity
transformations or exhibit impossible attributes such as violations of
continuity."

## The unit: a discrete EVENT, not a premise

Code discrete impossible OCCURRENCES — something impossible *happens* at a
moment. A standing impossible PREMISE (a sponge that talks, a bear family in
clothes, anthropomorphic animals living in houses) is NOT an event. The premise
is constant background; events have onsets.

- Talking animals conversing → premise, not coded.
- The talking animal suddenly detaches its head → event (`body`).
- Rule of thumb: if you could put a timestamp on "the moment it happened,"
  it's an event. If it was already true when the scene started and stays true,
  it's premise.

Record the show's premise once in the coding sheet's first row notes
(e.g., "premise: anthropomorphic sea creatures") — not as events.

## Event types

| Type | Definition | Examples |
|---|---|---|
| `physical` | Violates intuitive physics: gravity, support, solidity, trajectory. | Character floats/flies unaided; walks through a wall; runs through a painted tunnel; hangs in midair before falling. |
| `transformation` | Impossible change of identity, shape, or size. | Character morphs into another creature; object turns into a different object; body inflates to room size. |
| `continuity` | Violates object continuity/cohesion: appearing, vanishing, teleporting, splitting, multiplying. | Character multiplies into five copies (Essex's Daffy example); item pops into existence; teleportation. |
| `body` | Impossible body event (body stays "itself" but does something anatomically impossible). | Eyes pop out of head (Hinten & Imuta's example); neck stretches across a room; character is flattened and re-inflates. |
| `animacy` | An INANIMATE object begins acting as an animate agent. NOT for talking animals — animals are already animate (see Rule 7). | Food gets up and dances; furniture talks (onset — if it talked from scene start, it's premise). |
| `causal` | Impossible causation: effects without physical mechanism. | Magic spells; snapping fingers changes the weather; action at an impossible distance. |
| `other_impossible` | Clearly impossible but fits none of the above. Note required. | — |

Pick the type describing the CORE violation. If two violations co-occur as one
gag, code ONE event with the dominant type and mention the second in notes.
If genuinely distinct impossibilities happen in sequence, code separate events.

## Per-event properties (the columns)

| Column | Values | Rule |
|---|---|---|
| `timestamp_hms` | e.g. `02:13` | Event ONSET — the moment the impossibility begins. |
| `event_type` | one of the 7 types | Core violation. |
| `narrative_relevance` | `integral` / `incidental` | `integral` = the plot does not advance without this event (the magic that drives the story). `incidental` = decorative gag; the story would proceed identically without it. When torn, ask: would a plot summary mention it? (Motivated by Hinten & Imuta 2026 — SPECT predicts narrative-disruptive events cost more.) |
| `repeat` | `new` / `repeat` | `repeat` = essentially the same impossibility by the same character/object seen earlier THIS episode (e.g., the fifth time the character flies). First instance is `new`. (Motivated by Lillard's schema account — repetition may habituate.) |
| `duration_sec` | optional number | Only for extended events (a 20s flying sequence). Leave blank for momentary gags. A continuous sequence is ONE event, not one per second. |
| `notes` | free text | Required for `other_impossible`; encouraged everywhere. |

## Decision rules

1. **Premise vs event** — see above. When unsure, ask "did it just HAPPEN, or
   was it already the case?"
2. **Cartoon exaggeration vs impossibility:** exaggerated-but-possible
   (a very long fall, a huge sandwich, super speed lines) is NOT fantastical.
   Impossible-in-kind (floating in defiance of gravity) is. When torn: could any
   real creature/object do a version of this? If yes → not an event.
3. **Off-screen impossibilities implied by dialogue** are not coded; code what
   is shown.
4. **Fantasy-within-fantasy** (dream/imagination sequences): code events
   normally and add `imagination sequence` to notes — analysis can filter later.
5. **Blind coding:** no tool output exists for events (nothing to peek at), but
   code independently of your transition sheets — don't reuse timestamps from
   the transition pass; watch fresh.
6. **Ambiguity:** best call + note. Consistency across episodes beats any single
   borderline decision.
7. **Consistent impossible capabilities (talking pets, etc.).** A species-atypical
   capability a character holds STABLY (Martha the talking dog, a flying horse
   that always flies) is PREMISE in every episode where it is already true at the
   start — do not code its routine exercise as events. Code it only when:
   (a) the capability's ONSET is shown (origin story: the dog eats the soup and
   starts talking = one event, `causal` or `body` per the mechanism shown), or
   (b) it appears sporadically in an otherwise realistic world with no
   established premise.
   NOTE this rule is about the UNIT OF COUNTING, not about cognitive cost:
   Lillard et al. (2015, Study 2) found Martha Speaks — whose fantasy is largely
   premise-level — still depleted 4-year-olds' EF. Whether consistent premises
   are "cheaper" than sporadic events is an OPEN question; do not let an
   assumption either way leak into what you count.
8. **Do not skip events because they feel expected or habituated.** If an
   impossible OCCURRENCE has an onset, code it — even the fifteenth flight of
   the same character — and mark it `repeat`. Habituation is a hypothesis the
   `repeat` column exists to test at analysis time; it is not a coding-time
   judgment. Skipping "expected" events would bake the hypothesis into the data.
9. **Coding standpoint.** Impossibility is judged against ACTUAL-WORLD
   regularities from an adult standpoint (the field's convention), not against
   what a child might believe possible. That fantasy may be child-relative
   (young children's reality schemas are still forming) is a documented
   limitation and a future research question — not a coding rule.

## Procedure (per episode)

1. `python code_events.py template "<video path>"` → blank event sheet.
2. Pass 1 realtime: log onset + type roughly.
3. Pass 2: frame-step to fix onsets; fill narrative_relevance and repeat
   (repeat requires knowing earlier events — do it in pass 2 when you have the
   full list).
4. Log the session in VALIDATION_LOG.md.

## Outputs (via code_events.py)

- `rates` — fantastical events/min (the literature's moderator variable),
  per-type rates, % integral, % repeat, events-per-30s timeline.
- `agreement` — two-coder inter-rater reliability: event-detection agreement
  within a time tolerance, type agreement, and multi-class Cohen's kappa.
  (No study in the meta-analysis published IRR for event coding — supporting it
  is part of the instrument's contribution.)
- `summary` — aggregate rates across episodes (the norms table).
