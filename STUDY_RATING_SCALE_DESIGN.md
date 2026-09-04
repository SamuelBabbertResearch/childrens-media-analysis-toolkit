# The participant pace scale: design and evidence

**Written:** 2026-08-29. **Updated:** 2026-09-01. **Status:** adult-only pilot
implementation. The active runner now uses this scale only for an unrecorded
practice direction check and one adult self-perception rating after each clip;
the superseded prediction and child-participant flows are refused by package
schema validation. Participant wording still requires faculty and IRB approval
before collection.

The participant-design change is governed by
[STUDY_ADULT_ONLY_REDESIGN_DECISION_2026-08-31.md](STUDY_ADULT_ONLY_REDESIGN_DECISION_2026-08-31.md).
Child-focused evidence below is retained as design provenance; it is not a
reason to recruit children or ask adults to estimate children's perceptions.

This document exists so that the paper can say *why* the response format looks
the way it does, and so that a later reader — a reviewer, a replicator, or a
future version of this project — can tell which parts of the screen are
findings-driven and which are taste. Every constraint below changed something
in the software; nothing here is decoration.

The response format itself is not decided here. It is fixed by
[STUDY_PROCEDURE_ADULT_ONLY.md](STUDY_PROCEDURE_ADULT_ONLY.md): one repeated
five-point ordered pace item asking how fast the clip felt to the adult, with
verbal anchors *Very slow / Slow / In between / Fast / Very fast*. What is
decided here is how those five options are presented.

---

## 1. What was built

A horizontal labelled ramp, 1 on the left and 5 on the right, with a turtle
outside the left end and a rabbit outside the right end.

- Five equal cells. Each carries **its number and its word**.
- A **single-hue lightness ramp**, pale at 1 and deep at 5.
- The turtle and rabbit are **end anchors beside the scale**, not response
  options, and no creature appears on any of the five cells.
- **Nothing is selected** until the participant selects something.
- The selected cell is marked with a **heavy outline and an underline** under
  its number. Its fill does not change.
- Answers stay revisable until the participant confirms, then lock.

It is implemented in [`study_runner/scale.py`](study_runner/scale.py); the
colours live in [`ui/tokens.py`](ui/tokens.py) as `PACE_SCALE`, and the
properties this document asserts are tested in
[`tests/test_study_runner_scale.py`](tests/test_study_runner_scale.py).

Screenshots of the built screen, unanswered and answered, are in `output/`.

## 2. The six constraints, and what each one changed

**1. Five points, and no more.** Response quality in children improves as the
number of options falls toward four or five; longer scales add unreliable
variance rather than resolution, and the effect is strongest in the youngest
respondents. The protocol had already fixed five, so this changed nothing —
but it is the reason five is not revisited when the scale next gets edited.
*Borgers, de Leeuw & Hox (2000); Borgers, Hox & Sikkel (2004).*

**2. Every point is worded, not only the ends.** Fully labelled scales are
more reliable than end-labelled ones, and the advantage is largest for less
practised respondents — which children are. **Consequence:** the turtle and
the rabbit sit *outside* the scale as end anchors. They are a mnemonic for the
direction of the scale; the five words carry the meaning. A version with
creatures instead of words was rejected.
*Krosnick & Fabrigar (1997); Weng (2004).*

**3. Low left, high right, horizontal.** Respondents read scale space, not
just scale text: position on the screen carries meaning independently of the
labels, and ascending left-to-right matches reading order for this sample.
**Consequence:** the layout is horizontal and ascending, and the practice item
includes an explicit direction check ("show me which end means slow"), because
a reversed reading produces a rating that is wrong and undetectable downstream.
*Tourangeau, Couper & Conrad (2004).*

**4. Colour carries order, never approval.** Colour on a response scale is
interpreted. A red-to-green ramp is read as bad-to-good and shifts responses
even when the wording is neutral. **Consequence:** one hue, varying only in
lightness. A traffic-light ramp was designed, looked at, and rejected: it would
mean a child rating a cartoon they enjoyed as "very fast" had to put it in the
red. It would also be the stimulus-only guardrail (`CLAUDE.md` §2.1) broken in
front of a participant — CMAT issues no verdict, and a participant screen that
implies one is the same failure wearing a different coat.
*Tourangeau, Couper & Conrad (2007).*

**5. The creatures are plain, and there are only two.** Imagery on a child
scale imports whatever it depicts. In pain measurement, faces scales whose
neutral anchor smiles pull ratings toward affect rather than toward the
construct being measured. A turtle and a rabbit are safer than faces because
they denote *speed* rather than feeling. **Consequence:** both are drawn flat,
without faces, expressions or motion lines, and neither appears on a response
cell. A five-creature ramp — snail, turtle, cat, rabbit, hare — was rejected:
it requires the child to already rank five animals by speed, and a child who
ranks them differently produces an error nothing downstream can detect. Two
creatures are a mnemonic; five are a quiz.
*Chambers & Craig (1998); Chambers et al. (2005).*

**6. No single channel carries the answer.** Position, number, word and
lightness all encode the same order, and the *selected* state is an outline
plus a mark rather than a change of colour. **Consequence:** the scale still
reads correctly in greyscale, on a washed-out projector, and for a colour-blind
participant — roughly one boy in twelve has a red-green deficiency, so a child
sample of any size contains some. The cells are also painted rather than
styled, so a high-contrast Windows theme on the study computer cannot silently
change what participants see.
*WCAG 2.1 success criterion 1.4.1; Birch (2012) on red-green deficiency
prevalence.*

## 3. Interaction rules

These are behaviour, not appearance, and each is a way the data could be wrong
without the screen looking wrong.

| Rule | Why |
|---|---|
| No default and no pre-highlighted midpoint | A pre-set 3 is an anchor the participant has to argue with |
| The whole cell is the target, at least 78 × 64 px | A generous target reduces mis-clicks and remains usable with a trackpad |
| Number keys 1–5, arrows, Home / End | Adults answer 12 times; the keys work while focus is on the confirm button |
| Revisable until confirm, then locked | Matches the "final once submitted" rule in the procedure; a mis-click must not become data |
| No countdown, no auto-advance | Latency may be logged; it must not be pressured |
| The practice item uses this same widget | No participant meets a scale that differs from the one their answers are recorded on |
| Question and scale only on screen | No clip title, no "7 of 12" counter, no CMAT numbers anywhere a participant can see them |

## 4. What is still open

- **The active adult-only scale has not been piloted with participants.** The practice item must
  test whether the wording, anchors, and direction are clear to adults.
- **Whether the turtle and rabbit remain.** They are not necessary for an adult
  sample. Retain or remove them only through a documented pilot/faculty decision;
  either choice must leave the five verbal anchors unchanged.
- **The direction-check wording is frozen:** “Which response means neither slow
  nor fast?” The participant continues after selecting `3. In between`; the
  practice response is not retained as study data.
- **Nothing about response latency is recorded yet.**

## 5. Sources

Listed for retrieval, not yet verified against the primary text. **Check each
one before it reaches a methods section or a reference list** — this list was
assembled to support a design decision, which is a lower bar than citation.

- Borgers, N., de Leeuw, E., & Hox, J. (2000). Children as respondents in
  survey research: Cognitive development and response quality. *Bulletin de
  Méthodologie Sociologique*.
- Borgers, N., Hox, J., & Sikkel, D. (2004). Response effects in surveys on
  children and adolescents: The effect of number of response options, negative
  wording, and neutral mid-point. *Quality & Quantity*.
- Krosnick, J. A., & Fabrigar, L. R. (1997). Designing rating scales for
  effective measurement in surveys. In *Survey Measurement and Process
  Quality*.
- Weng, L.-J. (2004). Impact of the number of response categories and anchor
  labels on coefficient alpha and test-retest reliability. *Educational and
  Psychological Measurement*.
- Tourangeau, R., Couper, M. P., & Conrad, F. (2004). Spacing, position, and
  order: Interpretive heuristics for visual features of survey questions.
  *Public Opinion Quarterly*.
- Tourangeau, R., Couper, M. P., & Conrad, F. (2007). Color, labels, and
  interpretive heuristics for response scales. *Public Opinion Quarterly*.
- Chambers, C. T., & Craig, K. D. (1998). An intrusive impact of anchors in
  children's faces pain scales. *Pain*.
- Chambers, C. T., et al. (2005). Faces scales for the measurement of
  postoperative pain intensity in children. *Clinical Journal of Pain*.
- Mellor, D., & Moore, K. A. (2014). The use of Likert scales with children.
  *Journal of Pediatric Psychology*.
- W3C. Web Content Accessibility Guidelines 2.1, success criterion 1.4.1 (Use
  of Color).
- Birch, J. (2012). Worldwide prevalence of red-green colour deficiency.
  *Journal of the Optical Society of America A*.
