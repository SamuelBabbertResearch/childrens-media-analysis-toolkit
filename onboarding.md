# CMAT — Onboarding

Previously-on, for a session starting with zero memory. Read this, then
`TODO.md`, then `DECISIONS.md` and `LEARNINGS.md`. `INDEX.md` points at
everything else.

**Last updated:** 2026-08-11

---

## Where the project stands

CMAT has **two front-ends against one engine**. The Qt build (`python
cmat_qt.py`) is now the current application: all six tabs are ported. The Tk
build (`python gui.py`) still runs and is still the only home of two screens.

| Tab | Qt | Notes |
|---|---|---|
| Pipeline | ✅ | node canvas, undo/redo, wiring by dragging ports |
| Library | ✅ | episode report, show aggregate, chart |
| Index | ✅ | sortable, filterable, over the SQLite index |
| Automated coding | ✅ | worker thread, progress, cancel |
| Human coding | ⚠️ | *Code* screen only — VLC embedded. *Validate tool* and *Agreement* still Tk |
| Trials | ✅ | 22 recorded runs in this working copy |
| Settings dialog | ✅ | scoring settings only |
| Episode Sampler | ❌ | Tk only; the Qt button is disabled and says so |

Test suite: **221 passed, 13 skipped**.

## How the project got here (June – August 2026)

Six weeks, three phases. Read `DECISIONS.md` § Foundations for the detail.

1. **Late June — the measure.** Built the analyzer and calibrated it against
   judgement. Audio was added because a dance video scored *below* an episode
   of *Little Bear*; colour contrast because saturation favoured gentle
   animation. Named CMAT on 2026-06-30.
2. **July — the method.** Sampling, trials, metadata importers, the published
   index site, and then fantastical-event hand coding, after the literature
   indicated it may matter as much as pace. This phase included a real stall —
   a fortnight of doubt about whether the automated analysis could ever be
   accurate enough to be worth it.
3. **August — the product.** That doubt resolved into the current positioning:
   CMAT contributes by being **open, accessible and configurable, with its
   error reported**, not by claiming to detect cuts better than anyone else.
   From that followed interchangeable measurement tools, the measurement
   registry, separate automated and hand-coding tracks, the visual pipeline,
   and the move to Qt.

## What happened last session (2026-08-10)

A long UI session that ported the whole interface to Qt. In order:

- Matched the supplied design mockups properly — density, fonts, tables,
  window frame. The turning point was extracting the mockup CSS into
  `ui/reference/` and consuming it rather than re-typing it.
- Ported Pipeline, Settings, Automated coding, Index, Trials and Human coding.
- Replaced the mockups' Mac-style traffic lights with Windows caption
  controls, and settled the design rule: **take the mockups' surfaces, take
  Windows' controls and behaviours**.
- Fixed a real data bug: the index held **24 rows for 13 episodes** because the
  same file was stored under both a relative and an absolute path. Migrated on
  open; now 13 rows.
- Added a Delete Pipeline button with a proper confirmation dialog.
- Added the show aggregate report and wired the previously-dead Show Chart
  button.

## What is in progress

Nothing is half-finished. The working tree is clean apart from four untracked
root files (see `TODO.md` item 5) and this documentation set.

## What is blocked

Nothing is blocked on an external dependency. One item needs a **product
decision, not code**: whether the startup wizard should keep *Create Pipeline*
as its default button (`TODO.md` item 3).

## Next three concrete steps

1. Port Human coding's *Validate tool* and *Agreement* screens.
2. Port the Episode Sampler.
3. Decide the wizard default, then retire the Tk modules that have reached
   parity.

## Things a new session must know immediately

- **Never commit `FOR_PAPER.txt`.** It is gitignored. Do not `git add -f` it,
  do not paste its contents anywhere public. Same for `user_prefs.json` and
  `pipelines/`.
- **`analyzer/` imports no GUI framework.** Enforced by
  `tests/test_engine_isolation.py`. This is the
  property that made the Qt migration cheap; do not spend it.
- **`ui/DESIGN.md` §0 is the recipe for building a screen.** Read it before
  touching the interface. The mockup stylesheets in `ui/reference/` are the
  source of the design and must not be hand-edited.
- **Mockups specify styling only.** Words, columns, figures and states come
  from the engine. Never adopt a mockup's invented label or number.
- **Scoring settings ≠ measurement settings.** See `ARCHITECTURE.md` §3.
- **Know what is validated before quoting a number.** Flashing and scene
  relation are *unvalidated*; dissolves and TransNetV2 are *experimental*. The
  headline hard-cut F1 of 0.85 is type-agnostic, ±2 s, and from a preliminary
  single-coder pilot. `ARCHITECTURE.md` §9 has the full table.
- This working copy has real data: 32 shows, 202 episodes, 13 indexed, 29
  pipeline documents, 22 trials. Tests must not write into it — a previous
  session's manual test created a stray pipeline document that had to be
  removed by hand.
