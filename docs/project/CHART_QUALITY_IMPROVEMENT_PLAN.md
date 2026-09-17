# CMAT chart-quality improvement plan

## Purpose

Make CMAT's current charts accurate, readable, and useful for real
episode-level comparisons without changing the underlying measurements or
turning the Formal-Feature Composite (FFC) into a viewer-effect, safety, or
appropriateness measure.

This plan covers the three current chart families in `ui/chart.py`:

- FFC component composition by episode;
- speech rate (WPM) and speech density by episode; and
- vocabulary/readability measures and vocabulary-tier composition.

No work in this plan changes a cached measurement, an FFC weight, an FFC
normalisation range, or a research interpretation.

## Audit finding

The charts have a sound conceptual basis, but the current rendering is not
safe for a medium or large result set.

The blocking defect is **duplicate category labels**. `_short()` removes the
beginning of long filenames, leaving a shared tail. The chart passes those
strings directly to `matplotlib.axes.Axes.bar()`. Matplotlib treats equal
strings as one categorical x-position, so distinct episodes can be drawn on
top of each other.

This occurred in the local 20-result Little Bear Season 4 cache: the chart
received 20 results but produced only 11 distinct visible x-axis categories.
The plot therefore cannot be relied on to represent every result. The same
pattern is available to FFC, speech, and vocabulary charts.

## What already works well

- The FFC view shows each component's weighted contribution instead of a
  single opaque score.
- It uses per-episode effective weights, including the no-audio path, so a
  stacked bar sums to the displayed FFC rather than to a nominal-weight
  approximation.
- The FFC figure retains its validation and stimulus-only qualification.
- Speech rate is paired with speech density, preventing WPM from being shown
  as if it described how dialogue-heavy an episode is.
- The palette, horizontal gridlines, and legends are restrained and readable
  for small sets of uniquely named episodes.

## Required changes

### P0 — preserve one visible mark per result

**Target:** `ui/chart.py`

**Progress — implemented 2026-09-07.** FFC, speech, and vocabulary charts now
use numeric plot positions rather than display text, and their labels retain a
stable episode identifier plus a duplicate suffix where needed. The FFC chart
also switches to a taller horizontal ranked layout above ten results. The
remaining items in this section concern episode-key presentation and further
visual QA.

1. Never use a display label as the categorical coordinate.
   
   Use explicit integer positions (`range(len(rows))`) for bars and line
   points, then set tick positions and display labels separately. This alone
   prevents Matplotlib from merging equal labels.

2. Give each visible result a stable, unique chart label.

   Prefer a parsed episode identifier such as `S04E02`, with a compact title
   only where space permits. If a filename cannot yield an episode identifier,
   use a short title plus an unambiguous sequence number. Do not depend on the
   final 28 characters of a filename for identity.

3. Preserve the complete filename and source path in a chart-adjacent episode
   key or table. A compact axis label must not make it impossible to identify
   the underlying result.

4. Apply the same helper and identity rule to FFC, speech, single-measure
   vocabulary, and vocabulary-tier charts. Do not fix FFC only.

**Acceptance criteria**

- Twenty input results always yield twenty bar positions, even when every
  display title is identical.
- No bar or line point is hidden by another result because of a shared label.
- Every plotted result can be resolved to exactly one episode/cache record.

### P1 — make charts scale beyond a small comparison set

**Target:** `ui/chart.py`, and the callers in `ui/main_window.py` and
`ui/language.py` as needed.

1. Define a small-set layout and a large-set layout.

   A sensible starting policy is vertical bars for 1–10 results, then a
   horizontal ranked chart for 11–25 results. Above that, paginate or offer a
   filtered/top-N view alongside a complete export/table; do not silently omit
   labels or marks.

2. Size the figure and margins from result count and label length instead of
   permanently using 880–900 × 520 dialogs with fixed bottom margins.

3. Keep ranking explicit. FFC and single-value vocabulary charts may retain
   score-ordering, but the axis/title or adjacent text should say that the
   episodes are ordered by the displayed measure.

4. For an aggregate or whole-library selection, state the number plotted and
   the scope (for example, “20 measured episodes in Little Bear — Season 4”).

**Acceptance criteria**

- A 20-result chart has readable labels and one distinguishable mark per
  episode at ordinary window size.
- A larger result set remains navigable without relying on an unreadable mass
  of rotated text.
- The chart makes clear whether it shows all results, a page, or a filtered
  subset.

### P1 — improve FFC comparison without weakening its guardrails

**Target:** `ui/chart.py`

1. Retain a full 0–1 FFC scale as the honest absolute view. It is useful for
   comparing figures produced with the same configuration.

2. Add an explicitly labelled comparison-zoom option, or a companion view,
   for tightly clustered values. Typical cached FFC values around 0.14–0.27
   currently occupy only a small fraction of the plot height. A zoomed view
   must state its actual y-range prominently and must not be presented as the
   default absolute scale.

3. Consider a total-score marker or value label at the end of each stacked bar
   in the comparison layout. It improves ranking while keeping component
   contributions visible.

4. Keep the existing text that says the figure is a configurable composite,
   carries ungraded components, compares consistently measured episodes, and
   is not a safety assessment.

**Acceptance criteria**

- The default figure still communicates the 0–1 composite scale and all
  existing qualification text.
- A user can compare small score differences without estimating stacked-bar
  totals by eye.
- No chart introduces threshold bands, “high/low” judgement colours, or a
  viewer-effect interpretation.

### P2 — reduce ambiguity in the speech chart

**Target:** `ui/chart.py`

The paired measures are appropriate, but bars on one y-axis and a line on a
second y-axis can imply a relationship based on arbitrary axis scaling.

Evaluate one of these designs with real data:

- two vertically aligned plots sharing the same unique episode axis; or
- a dot/bar layout with both values directly labelled and a plain-language
  explanation retained under the figure.

If the dual-axis view remains, label both scales prominently, retain the
legend, and ensure users can identify the exact WPM and density values for an
episode.

**Acceptance criteria**

- WPM remains described as words per minute of dialogue time.
- Speech density remains described as the fraction of runtime with dialogue.
- An episode can be identified and its two values read without inferring one
  from the other’s scale.

### P2 — represent missing vocabulary measures honestly

**Target:** `ui/chart.py`, `ui/language.py`

Single-measure vocabulary charts currently filter rows with a missing value.
Keep the plot to valid values, but visibly report `n measured / N analysed`
and name missingness as missing rather than as a zero. The vocabulary-tier
chart should also identify its plotted denominator.

**Acceptance criteria**

- A reader can tell how many analysed caption files contributed to a chart.
- Missing AoA/readability/diversity values are never visually indistinguishable
  from zero or from an absent episode.

### P3 — make figures usable outside the immediate dialog

**Target:** `ui/chart.py` and the relevant dialog/action-bar helpers

Add a clear way to export the displayed figure as PNG and SVG/PDF, plus the
exact plotted rows as CSV. Exports should retain the complete episode identity,
configuration/scope statement, and existing research qualification text where
applicable.

This is an enhancement, not a prerequisite for fixing the overlap defect.

## Test and review plan

### Automated tests

Add focused tests for chart preparation/rendering. They should not rely only
on Matplotlib pixels or on an available desktop font.

- Construct results whose long names shorten to the same display string;
  assert that the generated axes contain one distinct x/y position per input
  result.
- Cover 1, 6, 11, 20, and more-than-page-size results.
- Cover silent/no-audio FFC results and assert stacked contributions still sum
  to the rescored composite.
- Cover duplicate labels for speech and vocabulary as well as FFC.
- Assert the scope/count and qualification text appear where required.
- Assert missing vocabulary values change the reported denominator rather than
  appearing as zero.

### Visual QA in the real application

Review the current PySide UI—not the older packaged interface—with real fonts
at normal Windows DPI. Inspect at least:

- a 6-episode Arthur set;
- the 20-result Little Bear Season 4 set that exposed the collision;
- a set with long, similar episode names;
- a silent/no-audio episode; and
- vocabulary data with at least one missing metric.

Check labels, legend wrapping, footnote size, resizing/maximising, keyboard
focus, and exported output. The offscreen Qt environment may render window
chrome text as missing glyphs, so it is useful for plot geometry but not final
font/appearance approval.

## Suggested implementation order

1. Add a shared plot-row/unique-label helper and fix categorical-coordinate
   collisions in every chart family.
2. Add tests reproducing the Little Bear collision before changing layouts.
3. Implement the small/large-set responsive layouts and plotted-scope count.
4. Add FFC comparison zoom/total labels while preserving the full-scale view.
5. Rework or validate the speech dual-axis treatment and expose vocabulary
   denominators.
6. Add export after the correctness and readability work is complete.

## Out of scope

- Changing detector outputs, cached results, FFC weights, or normalisation
  ceilings.
- Adding developmental, safety, appropriateness, or viewer-outcome claims.
- Treating chart polish as evidence that an ungraded measurement is validated.
