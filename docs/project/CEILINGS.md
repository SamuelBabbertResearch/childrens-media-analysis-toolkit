# Normalization ceilings — how they were set, and when to revisit

**Status:** provisional. Set 2026-08-14 from 78 analysed episodes.
**This file exists because that number is small.** Read it before quoting a
composite score in a write-up, and revisit the ceilings whenever the corpus
grows materially — see *When to revisit* at the bottom.

---

## What a ceiling does, in one paragraph

Every component of the Formal-Feature Composite (FFC) is rescaled to 0–1 before it is
weighted, using `(value − min) / (max − min)`, clamped into [0, 1]. The `max` is
the **ceiling**. It defines what counts as "the top of the scale" for that
metric. It is not a threshold, not a limit, and carries no judgement about the
content — it is the denominator that makes six differently-shaped numbers
addable.

Two failure modes, and both were live in this project:

- **A ceiling far above what real content produces wastes the scale.** Motion's
  ceiling was 1.0 — its theoretical maximum — but real video produces about
  0.09. Every episode scored near zero on motion, so a component nominally
  weighted 25% contributed about 7% of the composite. The weight said one thing
  and the arithmetic did another.
- **A ceiling below what real content produces flattens the top.** Flashing's
  ceiling was 30/min and audio RMS 0.2; episodes existed above both. Everything
  above a ceiling clamps to exactly 1.0, so the most intense episodes became
  indistinguishable from each other.

**The consequence to remember: a weight only means what its ceiling lets it
mean.** Nominal weights and effective contributions are different numbers, and
both belong in any write-up. `ARCHITECTURE.md` §8.1a carries the current table.

## What was changed on 2026-08-14, and why

Evidence base: **78 analysed episodes** — 15 in the live index plus 63 in the
older cache at `<project>/.analysis`. The older set is stale *as cache* but its
measurements are real, and it covers more shows, so it was used for range.

| Metric | Was | Now | Observed median | Observed max | Reason |
|---|---|---|---|---|---|
| `cuts_per_min` | 60 | **45** | 14.0 | 37.5 | 60 was set for the fastest content imaginable; nothing observed approaches it |
| `color_saturation_mean` | 1.0 | **0.85** | 0.43 | 0.67 | 1.0 is the theoretical bound, not a realistic one |
| `color_contrast_mean` | 0.35 | **0.35** | 0.19 | 0.34 | already well matched — deliberately left alone |
| `motion_mean` | 1.0 | **0.35** | 0.064 | 0.247 | the scale error above; 1.0 was ~10× the practical range |
| `flashing_events_per_min` | 30 | **40** | 5.9 | 67.7 | was clamping real episodes |
| `audio_rms_mean` | 0.2 | **0.35** | 0.039 | 0.354 | was clamping real episodes |

Every ceiling sits **above the observed maximum** except flashing and audio,
where a single extreme episode each remains clamped. That is deliberate: both
metrics are heavily skewed (median far below max), so a ceiling set at the
extreme would push all ordinary content into the bottom tenth of the scale.

The age-named presets keep their own ceiling ladder. `Toddler (0-2)` is tight
so that small differences between quiet programmes stay visible instead of
collapsing near zero on a broad scale — a **scaling** choice about resolution
at the bottom of the range, made in exchange for clamping at the top.

**Corrected 2026-09-04.** This paragraph previously justified the ladder as
"because a few cuts per minute is a meaningful difference at that age". **No
source supports that**, no study establishes it, and it is a developmental
claim standing in for a scaling decision — the same error, in a different
place, as the withdrawn "Calibrated for preschoolers" preset description
(`DECISIONS.md`). The ladder is a convenience for keeping a corpus spread
across the scale. It says nothing about any age group.

**Only their motion ceilings were corrected** (0.5/0.7/0.85/1.0 →
0.18/0.25/0.30/0.35), because the motion scale error was present in every
preset and is a mistake rather than a design.

## What these ceilings are NOT

- **Not derived from theory.** No framework specifies them. Huston & Wright and
  Lang motivate *which properties are measured*, never how to scale or combine
  them. See `ARCHITECTURE.md` §8.1a.
- **Not validated.** No study grades them. They are a scaling convention chosen
  to fit observed content, and the composite remains a descriptive summary
  rather than a validated construct.
- **Not thresholds.** Exceeding a ceiling means "at or above the top of this
  scale", never "too much".
- **Not a verdict.** `CLAUDE.md` §2.1 — CMAT measures the stimulus. A ceiling
  is a denominator.
- **Not age-specific.** An age-named preset's ceilings are not a measured
  property of that age group, and no published source specifies them. The name
  says which population a study using the preset is about. Each preset carries
  `"illustrative": true` and `"derivation": "none recorded"` in `config.json`
  so the caveat travels with the values into any configuration they are saved
  to.

## Known limitations of the current values

1. **n = 78 episodes, and not a random sample.** They are the shows that
   happened to be analysed, weighted heavily toward *SpongeBob*, *Arthur*,
   *Curious George* and *Little Bear*. Ordinary preschool animation is well
   represented; fast-cut action, live-action, and anything for older children
   are barely represented at all.
2. **The fastest content in the corpus is not the fastest content that
   exists.** `cuts_per_min` tops out at 37.5 here. Music-video-styled or
   action programming can exceed that, and would clamp.
3. **Flashing and audio are skewed, and a linear scale serves skew badly.** The
   chosen ceilings are a compromise; a different corpus would justify a
   different compromise.
4. **Scores are not comparable across ceiling changes.** Any figure computed
   before 2026-08-14 sits on the old scale. See the migration note below.

## When to revisit

Re-check the ceilings — rerun the measurement below — whenever **any** of these
becomes true:

- [ ] The corpus passes **~150 analysed episodes** (roughly double the current
      basis).
- [ ] A materially different kind of content is added: live-action, YouTube,
      anything for 8+, or anything with a reputation for fast cutting.
- [ ] **Any metric starts clamping more than ~5% of episodes** — that means the
      ceiling is now below the content and the top of the scale is flattening.
- [ ] More than about a quarter of a metric's range sits unused across the whole
      corpus, as motion did at 8.6%.
- [ ] Before submitting any paper that quotes composite scores. State the
      ceilings used, in a table, with the corpus they were set from.

**How to check.** In the Qt build, open **Settings → Normalization Ceilings**;
each field shows the median and maximum for the current library beside it, so a
mismatch is visible without leaving the dialog. The underlying numbers come
from the index, so analyse first, then look.

## If you change them again

Changing a ceiling changes **every composite score already computed**, because
the composite is derived rather than stored raw. The procedure:

1. Edit the ceilings (Settings, or `config.json` for the shipped defaults).
2. Re-score the index so stored scores match — the Qt build's *Apply &
   Re-score*, or any `python cli.py db …` command, which backfills first.
3. **Check for rows that did not re-score.** Any episode outside the library
   root, or without a cache entry, keeps its old score and silently mixes two
   scales in one comparison table. Two such rows existed on 2026-08-14.
4. Rebuild the public site if the figures are published.
5. Record the change here, with the date, the corpus it was set from, and the
   old values — a superseded ceiling is how a superseded score is explained.

## History

| Date | Change | Basis |
|---|---|---|
| initial commit `62d402f` | original values, all six | none recorded — AI-generated defaults, never derived (`ARCHITECTURE.md` §8.1a) |
| 2026-08-14 | retuned five of six; motion corrected in every preset | 78 analysed episodes, this working copy |
