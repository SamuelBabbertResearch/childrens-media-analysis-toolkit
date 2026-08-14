# CMAT — Onboarding

Previously-on, for a session starting with zero memory. Read this, then
`TODO.md`, then `DECISIONS.md` and `LEARNINGS.md`. `INDEX.md` points at
everything else.

**Last updated:** 2026-08-14 (four output audits: nineteen defects, two published)

---

## Where the project stands

CMAT has **two front-ends against one engine**.

**`python gui.py` (Tkinter) is still the software that has been USED.**
**`python cmat_qt.py` (Qt) now has every screen the Tk build has** — as of
2026-08-14 nothing is Tk-only. It is a substitute in coverage, not yet in
mileage: everything new has been driven headless only. Do not
describe the Qt build as battle-tested, and do not delete a `gui*.py` module
until its Qt screen has done real work (`TODO.md` items 9 and 11).

**Branch:** work happens on `feature/language-analysis`, **pushed** and backed
up on GitHub. It is ~75 commits ahead of `master`, whose last commit is
2026-06-30 — and `master` is what GitHub shows visitors. Merging forward is a
clean fast-forward and is still an open decision (`TODO.md`).

| Screen | In Qt yet? | Notes |
|---|---|---|
| Pipeline | ✅ | node canvas, undo/redo, wiring by dragging ports; nodes show derived status and double-click through to their screen |
| Library | ✅ | episode report, show aggregate, **Full Series Aggregate**, **Sample Aggregate**, **Pin/Compare**, metadata + notes, chart; **right-click sends a selection to any tab**, multi-select for batch queueing |
| Index | ✅ | sortable, filterable, over the SQLite index |
| Automated coding | ✅ | Analyze, **analysis queue**, **Transcribe Missing Subtitles** |
| Language | ✅ | **new tab** — Speech and Vocabulary sub-views |
| Human coding | ✅ | Code, **Validate tool**, **Agreement** sub-views |
| Trials | ✅ | 22 recorded runs in this working copy |
| Settings dialog | ✅ | scoring; **Measurement settings** and **Optional tools** are separate dialogs |
| Exports | ✅ | **JSON / CSV / PDF** from File, each carrying its provenance |
| Metadata import | ✅ | **new dialog** — Wikipedia and TVMaze in one |
| Episode Sampler | ✅ | **new dialog**, from the toolbar or the Sampling node; stratify by season **or era** |
| Eras | ✅ | **new dialog** — named date ranges per show, from the sampler |

**Every Tk screen AND every Tk feature now has a Qt equivalent.** The gap
was audited by walking `gui.py`'s menus and buttons against `ui/`, and closed;
two items were left deliberately because they need a product decision rather
than a port (`TODO.md` item 7). Coverage is still not mileage: everything new
has been driven headless against the real library, not used for real work.

Run the tests with `python -m pytest -q` from the repo root: **315 passed,
13 skipped** (328 collected). `tests/test_eras.py` asserts on drawn strata and
manifest notes rather than on which widgets exist — the level the sampler
defects were only visible at. `tests/conftest.py` now offers a session-scoped
`qapp` fixture — an offscreen `QApplication` — so Qt widgets can be tested for
real rather than by reading their source.

## Before you build anything: how work gets checked here

The Qt migration was messy, and the mess had one cause worth carrying
forward. Nineteen defects were found in four audit passes on 2026-08-14 — two
of them already published to the public site — and **every one was invisible
from the interface**. The control was present, the button worked, the tests
passed, and the record described the design that was asked for rather than the
one that ran.

So the standard here is not "does it run". It is:

> **Run it and read what it produced.** Draw the sample and read the strata.
> Export the CSV and read the columns. Extract the PDF's text and check it
> against the screen. Rebuild the site and grep it for the claim.

Three specific habits that caused most of the damage, in case they feel
tempting:

1. **Auditing a port by SCREEN.** It finds a missing screen. It cannot find a
   control whose data path is empty, and it scores a feature broken in *both*
   builds as present in both. Audit by entry point — every menu item, every
   button, every dialog.
2. **Trusting the test suite.** It went 221 → 315 passing while all nineteen
   were live, because tests written alongside the code share its blind spots.
   The ones that caught things assert on artefacts.
3. **Declaring completion from the builder's side.** "Migration complete",
   "feature gap closed", "closed" — each meant "I finished what I set out to
   build", which is a different claim from "it works".

`LEARNINGS.md` opens with the five recurring shapes and how to test for each.
Read it before debugging, and before believing a piece of work is done.

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

## The plan agreed at the end of this session

**Finish the GUI transition first, then build the new pipeline system in Qt** —
rather than building the pipeline in the Tk build and then porting it. That is
a deliberate ordering decision: doing it the other way means building something
new and immediately migrating it.

**That transition is now complete** — every screen exists in Qt, and the
pipeline is a control surface rather than a picture. What is left is not
porting but proving: use the Qt build for real work, then retire the Tk
modules and decide what `master` and `README.md` should say.

Everything else in `TODO.md` is real but blocks nothing: the F1 contradiction
and the composite rationale are **paper** blockers, not code blockers.

## What happened in this session (2026-08-14)

Two parts: the pipeline became a control surface, then the remaining screens
were ported.

### Part 10 — the CLI, the scripts, and a blended F1

- **The same one-line mistake in four independent places.** Reading a cached
  episode without re-deriving its composite: the Qt Library (fixed earlier),
  `cli.py _analyze_single` (printed the cache verbatim), `cli.py _db_backfill`
  (wrote stale scores into the index — it would have silently undone the
  index re-score fix), and `analyzer/batch.py`'s cached-episode skip (so a
  batch mixing re-analysed and skipped episodes mixed two scoring scales).
  `analyzer.cache.load_scored()` is now the only sanctioned way to read a
  cached result, and a test enumerates every reader.
- **An aggregate F1 averaged across two detectors.** `validate_cuts.py
  summary` and the Validate tool both showed 0.891 over "4 comparison files"
  — two episodes scored twice, once with ContentDetector and once with
  TransNetV2. Real figures: **0.855** and **0.928**. The blend also hid the
  sharpest number in the set: dissolve F1 **0.133** for the shipped detector
  against **1.000** for TransNetV2. Both now report per detector.
- **`patch_speech_cache.py` pointed at a stale copy of the data.** It assumed
  the library root was its own directory; both `.analysis` directories exist
  here (82 stale episodes, 28 live), so it patched data the application never
  reads and reported success. It now takes a root, defaults to the remembered
  one, names it before writing, and has `--dry-run`.
- **The PDF reconciles with the on-screen report** — checked field by field.
  It carries the corrected flashing statement. One cosmetic fix: the accuracy
  heading was printed twice.

### Part 9 — the four paths before that

- **The index and the Library disagreed after a weights change** — 0.132 vs
  0.107 for one episode, and the Index's outlier fences were computed over a
  mix of weightings. My own re-score fix caused it: the composite is stored in
  SQLite and nothing rewrote it. `MainWindow.rescore_index()` now does, from
  cache, exactly as the Tk build's `_backfill_index` always did.
- **The Trials tab could not tell two runs apart.** The same episode on the
  same date showed F1 0.91 and F1 0.942 — different *detectors*
  (`content-t27-diss` vs `transnet-t0.5-solo`), with the tag sitting unread in
  the manifest filename. `discover_trials` now extracts it and there is a
  Detector column. For a registry whose purpose is "where did this number come
  from?", that was the one field that mattered.
- **`code_events.py publish` writes 0.0 events/min for an uncoded episode**,
  indistinguishable from one watched and found event-free. It now warns before
  publishing. Nothing has ever been published here, so no rate is affected.
- **`ARCHITECTURE.md` §8/§9 turned out to be RIGHT** where the code was wrong:
  §8.3 documents the audio redistribution and §9 already carried the flashing
  nuance provenance.py had lost. Its wording is now aligned with the fix.

Also recorded in `FOR_PAPER.txt`: TransNetV2 beat ContentDetector on both
coded episodes (0.910→0.942 and 0.753→0.902 boundary F1). n=2, single coder,
and animation is exactly where TransNetV2 is unverified — an observation to
pursue, not a result.

### Part 8 — the reporting audit, and two published errors

Same method, applied to how results are *reported* rather than drawn. Six more
defects:

1. **A published contradiction.** `analyzer/provenance.py` called flashing a
   "deterministic signal measurement — no detection step to validate", while
   the registry marks it UNVALIDATED and `CLAUDE.md` §2.2 names it explicitly
   as unvalidated and not a safety assessment. Provenance feeds the PDF, the
   CSV sidecar, the JSON export and the public site — the wrong claim was on
   14 show pages.
2. **A third F1 figure, also published.** `build_site.py` hard-coded
   "~0.84 … ~0.96", contradicting the constants `CLAUDE.md` quotes. It now
   reads `validation_short()`, so the site follows automatically when
   `TODO.md` item 1 settles which figure is current. **No number was chosen
   here** — that decision is still yours.
3. **The report's unvalidated flag never fired on real data.** It keyed off
   `measurement_tools`, which 11 of 13 cached results do not carry. It now
   falls back to the registry and says the tool selection was not recorded.
4. **The Index table, the comparison and the component chart** all showed
   flashing figures with no flag at all. All three now derive it from
   `analyzer.measurements.ungraded_measurements()` — one source.
5. **The composite's breakdown did not add up to the composite.** On a silent
   episode the report's contributions summed to 0.2265 under a headline of
   0.2832, and the stacked chart was short by the same amount, because the
   engine redistributes audio's weight into a local copy and the displays read
   the nominal weights. `effective_weights()` is now shared by both.
6. **A silent episode now says its score is composed differently**, so two
   0.28s are not mistaken for the same 0.28.

### Part 7 — the sampler audit

Asked to re-check by running things rather than comparing controls. Four more
real defects in the sampler, all fixed:

1. **`sort_key` crashed on a partial timeline** — `TypeError: '<' not
   supported between int and str` when some episodes had air dates and some
   did not, which is the normal case after a metadata import. Newly reachable
   because the era fix had just started filling air dates. Now a total
   ordering: dated first in date order, undated after by episode number.
2. **A silent fallback.** With no dates at all, "order by air date" quietly
   became episode order while the manifest still recorded
   `sort_col: air_date`. Both cases now write a manifest note.
3. **`load_registry_csv` dropped unrecognised columns**, so the documented
   `stratify_by = any column in Episode.extra` could never work from a
   registry. Extra columns now become grouping options, and the Qt sampler
   regained the **Load Registry CSV…** button I had also dropped.
4. **A derived era overwrote a declared one** — once registry columns were
   read, the date-range pass ran over the top and collapsed eight
   correctly-labelled episodes into one `(no era)` stratum. An explicit value
   now beats a derived one.

Also documented rather than changed: `Episode.runtime` is read by nothing, and
`Episode.label()` concatenates without a separator (`S01E02Birthday Soup`) —
it is the manual-lookup key *and* the episode list in every written manifest,
so changing it needs a migration decision. Both are in `TODO.md` item 7.

### Part 6 — era stratification, which had never worked

Pointed out after the "feature gap closed" claim: the Qt sampler could only
stratify by season, while the Tk one offers "By era / custom column". Checking
properly showed the Tk control had never worked either — **`Episode.extra` is
populated by nothing**, and a folder scan leaves `air_date` as None, so
stratifying by any column put every episode in one `(none)` stratum while the
design line and the manifest both still said "stratified".

- **`analyzer/eras.py`** is the missing join: `attach_air_dates()` fills
  `Episode.air_date` from the index, `assign_eras()` tags
  `Episode.extra["era"]` from the show's date ranges. Pure functions, no GUI,
  no database handle of their own.
- **`ui/eras.py`** defines a show's eras and counts how many episodes land in
  each *as you type*, because an era with one episode is censused rather than
  sampled and an empty one is not a stratum at all.
- **The sampler** offers season / era / none, renames "Per season" to "Per
  era" with the axis, and refuses to pretend: with no eras defined it says
  the draw would be "the same as not stratifying".
- Undated episodes group as `(no era)` — a real stratum, so they stay in the
  frame and the shortfall is visible instead of silently shrinking the sample.

Verified end to end on a real 15-episode folder: three eras, two drawn from
each, all three represented, `stratify_by: era` recorded in the manifest.

**The method lesson is in `LEARNINGS.md`:** the audit that found the other
sixteen gaps compared menus and buttons, which cannot detect a control whose
data path is empty — and scores a feature broken in both builds as present.
`TODO.md` item 7 is now a re-audit by *output*, with the specific fields a
folder scan cannot fill listed.

### Part 5 — the rest of the feature gap

- **`ui/metadata_import.py`** — one dialog for Wikipedia and TVMaze, because
  after the fetch they are the same job: both return a `WikiEpisode` list,
  both go through `match_to_files`, both end at `upsert_episode_metadata`.
  Matching falls back to title similarity down to 0.45, which is a *guess*, so
  fuzzy rows are counted in a warning, show their score, and can be unchecked
  — nothing unchecked is written. Air dates feed era stratification in the
  sampler and the Language screen's air-date column.
- **`ui/compare.py` + `report.compare_html`** — Pin for Compare / Compare with
  Pinned, for two episodes or two shows. Two value columns and a signed
  difference; no ordering, no colour, no arrow. It refuses to mix an episode
  with a show aggregate, and warns when one side has no audio, because missing
  audio redistributes its weight and the composites are then not composed the
  same way.
- **Transcribe Missing Subtitles** on Automated coding — Whisper only on
  episodes with no `.srt`/`.vtt`, over the queue or the selection. It patches
  the cached speech block and does not re-measure the video.
- **Sample Aggregate…** in the Library — the aggregate over exactly the
  episodes one drawn sample selected, which is the set a write-up is actually
  about. Counts the whole sample, not just the analysed part.

**A latent bug fixed on the way:** `_build_title_bar` created `self._menubar`
before testing whether the Win32 frame hook attached, and on the failure path
returned without clearing it. On any platform where the hook does not attach,
`_build_menu` would then fill a menu bar that is never added to the window —
no File menu, no Help menu at all. Not observed here (the hook attaches on
this machine), so it is a fix to the documented fallback path.

### Part 4 — a crash, and what the app actually costs

- **Crash fixed.** Vocabulary, Validate tool and Optional tools each set
  `self._worker = None` inside the slot connected to that worker's own
  finished signal, freeing a live QThread from under itself. That kills the
  process with no traceback. `AutomatedTab` already had the correct pattern;
  the three new screens were written without copying it. See `LEARNINGS.md`.
- **Startup is 3.7x faster.** Three heavy libraries were imported at module
  scope on paths the interface touches while starting: `pandas` (1.13s) via
  `analyzer/aggregate.py`, `scenedetect` (0.64s) via
  `metrics_cuts`/`validation`, and PyTorch (3.6s) via
  `OptionalTool.is_available()`. All three are now imported where they are
  used. `import ui.main_window` 2362ms -> 433ms; Measurement settings
  4179ms -> 93ms.

Measured on this working copy (32 show folders, 202 episodes, 12 cached
results), offscreen:

| Operation | Cost |
|---|---|
| import + window + set_root (cold start) | ~1.6 s |
| rebuild the Library tree | 107 ms |
| `build_pipelines()` — derived pipeline status | 420 ms |
| Full Series Aggregate | 49 ms |
| Language -> Speech refresh | 47 ms |
| Index / Trials refresh | 5 / 34 ms |

`build_pipelines()` at 420ms is the slowest thing that runs on an ordinary
interaction — it walks the validation folder and globs the cache, and it runs
on every pipeline refresh. Not yet a problem at this corpus size; it is the
first thing to look at if the library grows.

### Part 3 — the feature audit

Screens were ported; features had not been checked. Walking `gui.py`'s menus
and buttons against `ui/` found sixteen gaps. Closed this session:

- **Exports** — JSON, CSV and PDF from the File menu, over whichever episode
  or show the Results pane is showing. JSON embeds the provenance block; CSV
  writes a `_PROVENANCE.txt` sidecar so the data file stays machine-readable.
  The pipeline's Results stage tells the user to come here, so they had to
  exist.
- **`ui/measurements.py` — Measurement settings**, the second settings axis
  (`ARCHITECTURE.md` §3). Built from the `MEASUREMENTS` registry, so a tool
  added to the engine appears without editing the dialog. Every tool's name
  carries its validation status.
- **`ui/optional_tools.py` — Optional tools**, with benefits, costs and
  caveats given equal weight and the exact pip command shown before it runs.
- **Episode metadata and notes** in the Library, stored in the index rather
  than the cache so re-analysing does not erase what a person typed. Air date
  feeds era stratification and the Language screen's air-date column, which
  had nothing to fill it before.
- **The analysis queue** — Automated coding now takes a list of episodes and
  shows, not one selection. The Episode Sampler can send a draw straight to
  it. A queued target that vanishes is reported as a failed row rather than
  ending the run.

**Found while building: the staleness count was honest but incomplete.**
`analyzer.cache.is_stale` grandfathers results written before measurement
fingerprinting existed — correct, or one upgrade would invalidate a whole
corpus. But this working copy has 12 cached episodes and **1** fingerprint, so
"1 episode goes stale" was sitting on top of 11 whose settings are simply
unknown. Measurement settings now reports both numbers.

### Part 2 — the last four screens

- **`ui/language.py` — a new Language tab**, not a screen inside Automated
  coding: the pipeline gives `language` its own stage and a "Language only"
  template, because a language study needs no sensory pass. Two sub-views.
  *Speech* reads WPM and speech density from the cache (and picks up a caption
  file added after analysis). *Vocabulary* runs `vocab_complexity` over chosen
  caption files on a worker thread.
- **`ui/handcoding.py` — Validate tool and Agreement**, alongside the existing
  Code screen. Validate runs the detector and scores it against that episode's
  hand coding, and shows the aggregate across every comparison on disk.
  Agreement runs `inter_coder_agreement` between two coders' sheets.
- **`ui/sampler.py` — the Episode Sampler dialog.** Its toolbar button is live
  and the Sampling node opens it. Explanations come from
  `analyzer.sampler.TOOLTIPS`, which that module calls the authoritative
  source.
- **Full Series Aggregate** in the Library: one aggregate over every analysed
  episode under the root, across season folders. Unlike the Tk version it does
  not write the aggregate to disk — a view should not change the data it is a
  view of.
- **Sub-views are a group of checkable buttons in the `.sub-toolbar`**
  (`SubViews` in `ui/main_window.py`), not a second row of tabs: the reference
  has a sub-bar and no nested tab strip.
- **A real defect found while porting: the Qt build never re-scored from
  cache.** Settings' "Apply & Re-score" changed the weights and every screen
  went on showing the score the cache was written with. `MainWindow._cached`
  now calls `rescore_episode`, and a test fails if any screen reads the cache
  around it.

### Part 1 — the pipeline as a control surface

- **Double-clicking a node opens the screen that does its stage's work**, and
  the inspector carries the same as a button. The map is `STAGE_TABS` /
  `STAGE_ACTIONS` in `ui/main_window.py`. `STAGE_UNPORTED` is now empty; the
  mechanism stays for the next stage type added before its screen exists.
- **The inspector shows derived state** — `Stage.status_label`,
  `Stage.headline`, every `Stage.details` row and `Stage.next_action`, which
  leads in the info banner. It scrolls, because a sampling stage reports nine
  rows into a 240px panel.
- **A real defect behind the item: the derived status was unreachable, not
  merely undisplayed.** *Link to Episode Sample* wrote a **show** key into
  `PipelineDoc.source_key` while `build_pipelines()` keys its results
  `sample:<folder>` — two namespaces that never matched, so every node of every
  linked pipeline had always read "no derived status". The action now offers
  the discovered samples. See `LEARNINGS.md` and `DECISIONS.md`.
- **Two saved pipelines in this working copy still carry the old show keys**
  ("Language only", "New Pipeline 2"). They now say so and name the fix; relink
  them from Manage → Link to Episode Sample. Nothing measured is affected.

## What happened before that (2026-08-10 → 08-11)

Late additions, after the Qt port:

- **Documentation layer built** — the nine files `INDEX.md` points at,
  reconstructed from six weeks of transcripts.
- **Three timestamp defects found and fixed in both coding editors.** libvlc's
  `next_frame()` advances the picture but freezes the clock, and corrupts the
  next seek. Frame-stepping is now a seek of one frame duration in both
  `ui/player.py` and `gui_coding_editor.py`; backward stepping now works.
  **Timestamps already collected are unaffected by the fix** — assessing them
  is `TODO.md` item 3.
- **Codebook `other` subtypes defined** — wipe, iris, whip-pan cut, page turn.
- **`ARCHITECTURE.md` §8 rewritten from the metric source**, plus §8.1a naming
  the composite's unjustified choices, §9 validation status, §10 config
  defaults, §11 test inventory.

## What happened before that (2026-08-10)

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

Nothing is half-finished. The working tree is clean apart from seven untracked
root files (see `TODO.md` item 12) and this documentation set.

## What is blocked

Nothing is blocked on an external dependency. One item needs a **product
decision, not code**: whether the startup wizard should keep *Create Pipeline*
as its default button (`TODO.md` item 10).

## Next three concrete steps

1. Use the Qt build for a real coding or sampling session — every screen now
   exists, but only the Tk build has mileage.
2. Decide what `master` and `README.md` should say now that the Qt build has
   full coverage.
3. Retire the `gui*.py` modules whose screens have been proven, and decide the
   wizard default.

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
