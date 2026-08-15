# CMAT — Onboarding

Previously-on, for a session starting with zero memory. Read this, then
`TODO.md`, then `DECISIONS.md` and `LEARNINGS.md`. `INDEX.md` points at
everything else.

**Last updated:** 2026-08-17, later still (TODO.md item 0 closed — the
Spongebob show-level aggregate is recomputed, and a real bug that was
silently defeating the fix is found and closed in all three places it lived.
Suite green at 400 passed, 13 skipped)

---

## What changed on 2026-08-17, latest of all: closing TODO.md item 0 found a third bug

Item 0 asked for one thing — recompute Spongebob's show-level aggregate now
that the duplicate `S01E08B Squeaky Boots` copy is gone — and said it needed
no re-analysis, just reading the cache correctly. `cli.py db shows Shows`
(which backfills the index from cache before printing) should have produced
that number. It produced **"1 episode, avg_load 0.292"** instead — worse
than either number the entries below already knew was wrong.

**Root cause, distinct from the duplicate-count and raw-path bugs already on
record:** `cli.py _db_backfill`, `ui/main_window.py MainWindow.rescore_index`
and `gui.py`'s own `_backfill_index` all looped `for show_dir in
list_shows(root)` and called `upsert_show` once per `show_dir`. Spongebob's
episodes sit under `Season 1/` and `Season 2/` subfolders, so `list_shows()`
returns **one entry per season** — and `db_show_key` deliberately collapses
every season's key to the same parent show, so all three functions'
`upsert_show` calls kept **overwriting** the previous season's aggregate
instead of merging with it. Only the season walked last ever survived a
backfill. This is why the raw-path fix and the de-duplication below were
never actually visible as a corrected number: whichever fix landed, the next
backfill silently discarded all but one season before anyone could read the
result.

**Fixed in all three places** (the fourth reader, `ui/index_tab.py`'s
`summarise_shows`, was never affected — it derives from the episode rows
already on screen rather than reading the stored table, exactly the design
`DECISIONS.md` records for it). Each now accumulates results keyed by
`db_show_key` across every `show_dir` that shares one, and upserts once per
key after the full walk. Two regression tests build a synthetic show split
across two season folders and check the merged count and mean survive a
backfill — `tests/test_derived_consistency.py::test_backfill_merges_a_show_split_across_season_folders`
and `tests/test_scope.py::test_rescore_index_merges_a_show_split_across_seasons`
(the third instance, `gui.py`'s `_backfill_index`, is exercised by neither —
the Tk build has no test harness for it; read the source alongside the other
two if it is ever touched again).

**Verified against the real library**: Spongebob Squarepants Season 1, 6
episodes analysed (of 8 on disk in `Shows/`), avg_load **0.2668** — not the
stale duplicate-inflated 0.3071 nor the season-overwrite artifact's 0.292.
The raw-path show-name defect is also fixed for free, since the same
backfill re-keys every episode from `db_show_key` on every run. Full detail,
including why the public site's own published Spongebob figures were never
affected (a different, older, unsplit cache — `TODO.md` item 5), is in
`FOR_PAPER.txt`. Suite: 400 passed (2 new), 13 skipped.

**Left alone:** `gui.py`'s `_maybe_save_show_aggregate` (the incremental
save that fires after a season's episodes finish analysing, distinct from
the backfill sweep above) still computes an aggregate from one `show_dir`'s
episodes only, so it can still write a single-season aggregate between one
analysis run and the next backfill. Narrower and shorter-lived than the bug
above, and the Tk build is being retired (`TODO.md` item 7) rather than
extended — noted here so it isn't mistaken for new if `gui.py` is audited
again.

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
| Automated coding | ✅ | Analyze, **analysis queue** (staged from the scope), **Transcribe Missing Subtitles** |
| Language | ✅ | Speech (filters to the scope) and Vocabulary (stages from it) |
| Human coding | ✅ | Code, **Validate tool**, **Agreement**; both coding screens carry a **worklist** |
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

Run the tests with `python -m pytest -q` from the repo root: **383 passed,
13 skipped**. `tests/test_eras.py` asserts on drawn strata and
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

## What changed on 2026-08-17, latest: the sampler fetches a live channel

Following the day's other sampler work, the user asked to think through how
a new user would actually sample a channel like Game Theory — and pushed on
two more things directly: playlists, and time eras for a channel with no
downloaded folder. Walking through the real scenario found the actual gap:
today's sampler could only draw from a folder already on disk or a
hand-built registry CSV — neither helps someone who wants to sample *before*
downloading, which is the whole point of sampling.

**What shipped**: `analyzer/youtube_fetch.py` (new) — retargets the
now-deleted `sample_youtube.py` script's `yt-dlp --flat-playlist` fetch at
real `Episode` objects instead of its own duplicated spread algorithm and ad
hoc CSV. `ui/youtube_fetch.py` (new) — a small dialog accepting several
channel/playlist URLs at once, run on a worker thread (a real channel takes
30-60s; the interface must not freeze). Content type = YouTube now shows
three source buttons together — Fetch, Choose Downloaded Folder, Load
Registry CSV — so a new user finds live fetching without needing to already
know it exists.

**Playlists**: each fetched video is tagged `extra["playlist"]` when the
source URL is a real playlist (not a bare channel listing) — sampling across
several playlists at once turns this into a real, usable "By playlist"
stratify option, through the same generic mechanism `channel` already used.

**Eras, for free**: investigated `analyzer/eras.py` before writing anything
new — `assign_eras()` was already a pure function needing no database or
folder, and the DB's `show_eras` table already treats its key as an
arbitrary string. So a live-fetched channel just needed `_show_key()` to
return `f"youtube:{fetch_id}"` instead of falling back to `""` — the entire
existing `ErasDialog`/persistence system works unchanged, and a channel
fetched again next session gets its eras back automatically. Verified the
namespace can't collide with a real show: folder-derived keys are always
POSIX relative paths and never contain `:`.

**Explicitly declined, per discussion**: download automation. The drawn
`selected.csv` (each row carrying its URL) is the complete deliverable this
pass — actually fetching the sampled videos is left to the researcher.
`sample_youtube.py` is deleted, its logic fully absorbed. `DECISIONS.md` §
*Live YouTube fetch reuses the eras system unchanged…* has the full
reasoning. 12 new tests in `tests/test_sampler_youtube.py` (fetch parsing
against canned yt-dlp output, no network call; dialog wiring against a
stubbed fetch dialog). Suite: 398 passed (12 new), 13 skipped.

## What changed on 2026-08-17, later still: the sampler stops reading as TV-only

The user asked for the sampler to support movies and YouTube, not just TV
shows. Investigating `analyzer/sampler.py` in full found the engine already
did: `Episode.season`/`.episode` are nullable, `scan_entry_root()` already
degrades to a flat folder with sequential numbering when there's no season
structure, every sampling method is already generic over `list[Episode]`, and
`load_registry_csv()` already tolerates a blank `filepath` (metadata with no
downloaded file yet). **Nothing in the engine needed to change** — the
confusion was entirely `ui/sampler.py`'s copy ("Choose Show Folder…", "Pick
the show's top folder… each season subfolder… each video as one episode")
and two fixed preview columns.

There's also a standalone `sample_youtube.py` at the repo root — a working
`yt-dlp` channel/playlist fetcher, entirely disconnected from the real
sampler (its own duplicated algorithm, its own CSV format, no manifest, no
queue integration). Discussed with the user: this session ships the
folder-of-already-downloaded-videos path for YouTube (cheap, reuses the
engine unmodified); absorbing `sample_youtube.py`'s live fetch into the real
engine is real, separate work, now `TODO.md` item 9.

**What shipped**: a Content type selector (TV show / Movies / YouTube videos)
in `ui/sampler.py` that changes the browse button's text and tooltip, the
folder-dialog title, the preview table's "Season"/"Episode" headers ("Group"/
"#" for non-TV — the underlying `ep.season`/`ep.episode` data is unchanged,
just relabelled), the "By season" stratify option's label ("By group"), and
the post-scan status line (no more "12 episodes across 0 seasons" for a flat
folder). The preview table's File column now falls back to a registry row's
`url` extra column when there's no local file. The written manifest records
which content type a draw was, appended to `SampleManifest.notes` — no schema
change. Verified headless against the real `Shows/Arthur` folder (TV,
unchanged: 6 episodes, season {1}) and synthetic movies/YouTube fixtures (flat
scan, no seasons, correct headers, URL fallback, manifest note, and switching
content type mid-session clears stale episodes rather than leaving them under
new headers). `DECISIONS.md` § *The sampler's content-type selector is
presentation only…* has the reasoning and what was deliberately not touched
(the dialog's own title, the toolbar button, the Sampling pipeline node —
wider blast radius for no functional gain).

**Corrected within the hour**, pointed out directly: "YouTube (downloaded)"
called the identical `scan_entry_root()` as Movies, so it extracted nothing a
generic flat-folder scan couldn't — YouTube in name only. Checked this
project's own real YouTube content first (`Shows/Game Theory/`,
`Shows/iShowSpeed/`): plain filenames, no metadata sidecars, nothing on disk
beyond a filename to extract. So a relabeled "Upload date" column would have
just always been blank for the library this project actually holds — a
smaller version of the same hollow-label problem.

**What's real**: yt-dlp's `--write-info-json` (a standard option) writes a
`<file>.info.json` sidecar carrying upload date, title, channel, video id and
URL. `analyzer.sampler.scan_youtube_folder()` is new: identical to
`scan_entry_root()` when no sidecar exists (verified against the real `Shows/
Game Theory/` folder — field-for-field identical result), and fills real
metadata from the sidecar when one does. `extra["channel"]` falls out of this
for free and becomes a real "By channel" stratify option through the
mechanism already built for registry CSVs; `video_id`/`url` are deliberately
excluded from that list (unique per row, not a group). The preview table's
date column is now content-type-specific — "Air date" / "Release date" /
"Upload date" — on the same `Episode.air_date` field, the direct part of what
was asked. **Explicitly not done**: inferring an upload date from the file's
mtime — that is the download date, not the upload date, and CLAUDE.md's core
anti-pattern is exactly a wrong-but-plausible number that displays correctly.
`DECISIONS.md` § *YouTube gets a real scan function after all* has the
reasoning; `TODO.md` item 9 (the deferred live channel fetch) now notes the
two loaders should agree on the same sidecar shape when it's built.

## What changed on 2026-08-17, later the same day: marking now guarantees an exact timestamp

Following straight on from the counter fix below, the user asked why the
playing-state display still "isn't live and accurate." Measuring it against
wall-clock time (not just watching the window) found something more
consequential than a display lag: `ui/player.py`'s own docstring claimed
*"Pause before marking; the coding UI enforces that"* — and nothing did.
`handcoding.py`'s `_mark()` read `player.position()` unconditionally, and
libvlc's live clock only refreshes every 0.2–0.5s during playback (measured,
independent of the file's real frame rate — confirmed 23.976fps via
`ffprobe`, not a polling artifact). A mark taken while playing could
therefore be stamped up to ~0.5s stale relative to what the coder just saw.

**Fixed with a new `VideoPlayer.stamp(callback)`** (`ui/player.py`): already
paused, calls back immediately with today's exact value; playing, pauses
first and waits for libvlc to confirm it (bounded settle, ~20ms in the
measured steady-state case) before calling back. `_mark()` now routes
through it instead of reading `position()` directly, capturing every
dropdown value at the click so nothing changes during the settle. Verified
with a real (non-offscreen — the offscreen QApplication turned out to give
unreliable playback state, a separate finding) VLC window: a mark taken
while playing now pauses the video and stamps the exact post-settle value,
not the stale pre-pause one.

**Also smoothed, cosmetic only:** `_sync()`'s digital counter now
extrapolates between libvlc's real ticks using wall-clock time, snapping back
in sync on every real tick — so a coder watching playback sees the number
move continuously instead of sitting frozen for 3–5 ticks at a stretch. This
never feeds a stamp; `position()`/`stamp()` are untouched by it.

**Documented for the coder, not just the code**: the "Mark at playhead"
button now carries a tooltip explaining that it pauses the video first on
purpose, and that the moving counter during playback is an estimate, not
what gets written. `DECISIONS.md` § *Marking auto-pauses the video…* records
why auto-pause was chosen over blocking the click, and why switching away
from VLC was considered and declined (`LEARNINGS.md` has the measurement
detail; both explain the coarse live clock is a general property of how
media libraries throttle position reporting, not a VLC weakness).

**Not fixed:** the identical gap in `gui_coding_editor.py` (Tk) — noted in
`LEARNINGS.md` so it isn't rediscovered as new when that build is eventually
audited. Suite: 386 passed (three new), 13 skipped.

## What changed on 2026-08-17: the video time counter, characterised and fixed

`TODO.md` item 1 (the oldest open real defect, reported 2026-08-14 as "the time
readout in the Qt player is wrong", uncharacterised) is closed. Measured
`ui/player.py`'s `VideoPlayer` headless against a real episode rather than
watching the window, per `LEARNINGS.md`'s method:

- **Seeking, frame-stepping and the playing-state clock jumps all measured
  correct** — `position()` and the displayed label agreed with `get_time()`
  and `get_position()` to the millisecond in every case tried.
- **The real defect was narrower: the counter froze during a seek-bar drag.**
  `_sync()` wrote the slider from the player's position only when *not*
  scrubbing, but always wrote the digital *label* from the player's position
  regardless of scrubbing — so while the player itself is not moving, the bar
  tracks the mouse and the label stays stale until release. Measured: dragging
  to 764.4s left the counter reading `00:00:10.00`, the pre-drag position,
  for the whole drag.
- **The written mark was never affected.** `handcoding.py`'s `_mark()` reads
  `player.position()` directly, never the label text, so no hand-coded
  timestamp was ever corrupted by this — it was a display-only defect, and the
  ~0.55 s early bias and the ±2 s floor documented in the earlier timestamp
  assessment stand as they were.
- **Fix:** `_sync()` now derives the displayed time from the slider's own
  value while scrubbing, so the counter previews where the thumb points; the
  real seek still happens on release, unchanged.

See `LEARNINGS.md` § *The Qt counter froze during a scrub drag* for the
measurement method and numbers. Suite: 383 passed, 13 skipped, unchanged.

## What changed on 2026-08-16: the measurement tabs obey the context

Three commits, one per tab, each verified against the real library before the
next was started. The rule they settled into is in `DECISIONS.md` § *A view
narrows to the scope; a workbench stages from it*, and it is the thing to read
before giving a seventh screen a scope:

> A screen that **reports on work already done** filters to the scope. A screen
> where **work is started** stages the scope's episodes and gets out of the way.

- **Automated coding** stages the sample into the analysis queue — the list
  `_start` actually hands the worker — and the queue says which sample, how
  many already have a cached result, and how many of the draw are off disk.
  **Queue Scope (N)** re-stages after a run; disabled, with the reason, under
  the whole library.
- **Human coding** grew the **worklist** `TODO.md` item 6 had been asking for,
  on Code *and* Validate tool, each row carrying that episode's coding state
  read from the engine.
- **Language** takes it both ways in one tab: Speech filters, Vocabulary
  stages the caption files beside the sample's episodes.

Three rules every staging screen follows, because a half-staged screen is worse
than an empty one: the whole library stages nothing; a scope change withdraws
only its *own* staging, so a hand-queued episode survives; and the screen says
what it staged **and what it could not**.

### Three real defects found on the way, all invisible from the interface

1. **The analysis queue de-duplicated on the literal path**, so the same
   episode reaching it through the library walk and through `selected.csv`
   would have been measured twice in one run. It now normalises.
2. **Five readers looked for a coding sheet; one looked in one place.**
   `code_events.py`, `trials.py` and both Tk screens search the validation
   folder recursively with a prefix fallback; the Qt Code screen built
   `<validation>/<stem>_events.csv` and asked whether it existed. A sheet filed
   one folder down read as "not coded" on screen while the command line scored
   it. `event_coding.find_event_sheet` / `event_sheet_status` are now the one
   answer.
3. **Opening a second episode kept the first one's marks.** `_open_episode`
   never cleared the events list, so Save Sheet would have written one
   episode's hand-placed timestamps into another episode's file.

### One thing surfaced and deliberately not changed

**An unlinked pipeline inherits whatever scope was current.** Six of the eleven
pipeline documents here have no `source_key`, and `_follow_pipeline_scope`
leaves the scope alone for those on the stated grounds that an unlinked
pipeline has "no opinion about which episodes". That was cheap when the scope
only hid Library rows; it now pre-fills a run queue from another study's
sample. Nothing is mis-attributed — the Showing: control and the queue's own
note both name the sample — but it is a live question in `TODO.md`.

## What changed on 2026-08-15: the research context

The pipeline could *navigate* to a screen but handed it nothing, and every
screen worked out "which episodes?" for itself from the Library tree. A sample
could be drawn, documented and manifested with no screen any the wiser.

`analyzer/scope.py` is now the answer to that question: a `Scope` is either the
whole library or exactly the episodes one draw selected, and the **Showing:**
chooser on the toolbar always names which. Drawing a sample makes it current;
so does choosing a pipeline. It is **not persisted** — the application always
opens on the whole library, deliberately.

**All six screens now obey it** — the measurement tabs were done on
2026-08-16, one at a time, each verified against the real library. See *What
changed on 2026-08-16* below.

The chooser sits on the **main toolbar**, beside Root folder and Preset, so it
is visible from every tab. It moved there the moment a second screen obeyed it:
a control that narrows the Index while hidden inside the Library is a filter
you cannot see from the screen it is filtering.

Scoping the Index turned up a live wrong number worth knowing about: the stored
`shows` table goes stale, because `upsert_show` only runs on a whole-show
analysis. The Qt Index now derives its Shows view from the episode rows on
screen, so the two views cannot disagree — but **`cli.py db --shows` and the Tk
build still read the stored table**. See `LEARNINGS.md` and `TODO.md`.

Two things worth knowing before touching it:

- The scope is a **view**. It hides rows; it deletes nothing and re-measures
  nothing. Because it can hide things it is always visible and always one click
  from *Whole library*.
- Building it surfaced a real inconsistency: the sampler drew six video
  extensions while the library walk read `.mp4` only, so a draw could contain
  episodes the Library could not list. **Resolved**: `analyzer/show_index.py`'s
  `VIDEO_EXTENSIONS` is now the one definition both modules share, so the
  Library lists everything the sampler can draw. Recorded in `FOR_PAPER.txt`
  because it changed N for at least one existing draw.

Everything else in `TODO.md` is real but blocks nothing. The **F1
contradiction is now closed** (2026-08-14, see below); the composite rationale
remains a **paper** blocker, not a code blocker.

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
   reads `validation_short()`, so the site follows automatically.
   **Settled 2026-08-14** — see *The F1 contradiction, closed* below. The site
   now publishes F1 **0.85**, sourced from local validation runs.
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
so changing it needs a migration decision. Both are in `TODO.md` item 6.

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
`TODO.md` item 6 is now a re-audit by *output*, with the specific fields a
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
results), offscreen. **The library is 137 episodes since the 2026-08-15
de-duplication** — the figures below are not re-measured, so treat them as the
shape of the cost rather than current absolutes:

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

**Re-measured 2026-08-16 and it has grown: `build_pipelines()` is now 1524 ms.**
A whole scope change is ~2.0 s and **1761 ms of it is `_sync_scope_choices`**,
which calls `build_pipelines` every time. Everything else is small and flat in
sample size: Library + Index + Trials 353 ms, the analysis queue 92 ms, both
hand-coding worklists 293 ms, both Language views 261 ms. So the toolbar's
Showing: control costs two seconds, and 87% of that is one pre-existing call
that cannot change as a result of choosing a scope. See `TODO.md`.

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

## The F1 contradiction, closed (2026-08-14, later session)

The number the product's honesty claim rests on is **resolved**, by
recomputation rather than by picking a side — and as of the 2026-08-14 rename
below, the identifiers no longer contradict it either. This item is **closed
and off `TODO.md`**, which is why the list now starts at the composite
rationale.

**What was wrong:** `analyzer/provenance.py` carried a comment quoting
"0.84–0.96, aggregate ~0.91" directly above constants saying "0.75–0.91,
aggregate 0.85", with no record of which pass produced either.

**How it was settled:** re-scored the comparison CSVs already on disk, using
the project's own `_latest_comparisons` / `prf` helpers. Result, for the
shipped `content-t27-diss` detector, `ALL` row, ±2 s:

| Episode | TP | FP | FN | F1 |
|---|---|---|---|---|
| A Charlie Brown Christmas 1965 | 32 | 10 | 11 | 0.753 |
| Little Bear 1x01 | 71 | 4 | 10 | 0.910 |
| **pooled** | **103** | **14** | **21** | **0.855** |

That is the constants, exactly. `local_hard_cut_f1()` returns `('0.85', 2)`.

**The finding that actually explains it:** the two figures were never rival
measurements. "0.84–0.96" is the **hard_cut-type-only** basis for the *same two
runs* (0.841 and 0.964); "0.75–0.91" is the **`ALL`-row** basis for those runs.
Both are correct; they answer different questions. The 2026-08-08 log entry had
already moved the published basis to `ALL` and said it superseded earlier
entries — the code comment had simply never been updated. `LEARNINGS.md` §4
independently records the same pooled 0.855 / 0.928.

Updated: `analyzer/provenance.py`, `ARCHITECTURE.md` §9 (now names which runs
the aggregate covers), `build_site.py` comment, `DECISIONS.md`, `TODO.md`,
`FOR_PAPER.txt`. Tests: 322 passed, 13 skipped.

### Public wording brought in line with the evidence

The last thread from the composite finding. Four public claims asserted a
grounding that does not exist, and all four are now corrected:

- **The site's landing page** said "empirically grounded database of
  **sensory-load profiles**" — the profile *is* the composite, so this was the
  strongest live overclaim. Now "a transparent database of formal-feature
  measurements … the composite that combines them is a configurable summary,
  not a validated construct."
- **`README.md`** said "Grounded in Huston & Wright … Lang's LC4MP …" without
  qualification. Now attributes the grounding to the **measurement set** and
  states plainly that nothing specifies how to combine them.
- **`README.md` also claimed a "literature-grounded default vocabulary"** for
  the coding dropdowns. Found by grepping for the *shape* rather than the three
  known instances. `CODEBOOK.md` contains **zero citations** — confirmed — so
  this contradicted `TODO.md`'s own open item about the typology. Now says the
  typology is the study's own working scheme.
- **`DECISIONS.md`** said "`Toddler (0-2)` names the literature the ceilings
  come from". No such literature exists anywhere in the repo. The entry now
  carries a dated correction; the underlying decision (age names denote the
  study population, not suitability) is unaffected and stands.

A test now fails if "empirically grounded", "scientifically validated" or
"literature-grounded" reappears in `README.md` or `build_site.py`.

**The wording is mine and should be reviewed.** Samuel raised that AI-generated
text carries an embedded watermark and that paper prose must be his own; these
edits were kept deliberately subtractive for that reason, but they are
public-facing copy and deserve a human pass.

### The ceilings were retuned, and the site was republishing frozen scores

Following directly from the finding below — that nominal weights are not
effective weights — the normalization ceilings were fitted to observed content
on 2026-08-14. **Every composite score in the project moved.** Component
metrics did not: raw measurements are unchanged, only the 0–1 rescaling.

- **Five of six ceilings changed**, from 78 analysed episodes: `cuts_per_min`
  60→45, saturation 1.0→0.85, `motion_mean` 1.0→**0.35**, flashing 30→**40**,
  audio RMS 0.2→**0.35**. Contrast stays 0.35, already well matched.
- **Two opposite defects were live at once.** Motion's ceiling was its
  *theoretical* maximum against a real range of ~0.09, so a 25% weight
  delivered 7%. Flashing and audio ceilings sat *below* real content, clamping
  the most intense episodes to an identical 1.0. Neither is visible from a
  score; both are visible from the distribution.
- **Motion was corrected in every preset** (0.5/0.7/0.85/1.0 →
  0.18/0.25/0.30/0.35) — a scale error rather than a design choice. The age
  presets keep their deliberate ladder otherwise.
- **`CEILINGS.md` is new** and is the home for this: what a ceiling is, how the
  current values were set, their limitations, and explicit triggers for
  revisiting (~150 episodes, materially different content, any metric clamping
  >5%, or before any submission quoting composite scores). Registered in
  `INDEX.md`. The basis is **provisional** — n=78, not random, thin on
  live-action and fast-cut content.
- **Settings now shows the evidence.** Each ceiling field carries its metric's
  observed median and maximum for the current library, and warns when episodes
  are clamping. `analyzer.db.ceiling_distributions()` computes it; the dialog
  only displays it.

**A fifth reader of a frozen composite, and the only one that publishes.**
`build_site.py` read the stored score straight from the cache and the show
aggregate from a stored `aggregate.json`. The index re-scored to 0.2654 for one
episode while the site kept publishing 0.2241 — and rebuilding changed nothing,
because the rebuild republished the stale number faithfully. The same one-line
mistake had been fixed in four places, but the sweep looked for callers of
`load_scored()` and this file opens the JSON itself. **Grep for the shape, not
the fix.** Both now re-derive; verified against the built HTML, not the build
log. The methodology page also generates the ceilings table from `config.json`,
because it claims every result is reproducible from the parameters it documents.

**`<project>/.analysis` MUST NOT BE DELETED.** `TODO.md` previously called it a
stale duplicate to archive. `build_site.py` reads it, and **7 of the 15
published shows exist only there** — including every baseline comparison.
`TODO.md` item 6 now says so.

The site is **built to `_site/` but not pushed**; pushing is manual.

### The composite's defaults have no derivation — settled, not open

`TODO.md`'s long-standing item ("write down why the composite is shaped as it
is") is **answered**, and the answer is that nobody derived it. Put to the
author, the reply was that they did not know, because the code — including the
weights, the ceilings and the additive form — was written by an AI coding
assistant. The author is a psychology researcher, not the implementer.

**Do not treat this as a gap to be filled.** For weeks the record said "no
recorded rationale", which reads as *a human decided this and forgot to write it
down*, and invites the next reader to reconstruct a plausible justification into
a space that was never occupied. `ARCHITECTURE.md` §8.1a now says the defaults
are underived, in those words.

Three things follow, all recorded:

- **The theory citations cover the measurement set, not the composite.** Huston
  & Wright and Lang justify measuring cuts, motion, saturation, contrast,
  luminance change and audio. Neither says how to combine them into one number.
- **Nominal weights are not effective weights.** Measured over the 15 indexed
  episodes: motion is nominally 25% and contributes **7%**; colour contrast is
  nominally 10% and contributes **24%** — motion reaches 8.6% of its ceiling,
  contrast 62%. This quantifies the ceiling-compression effect `LEARNINGS.md`
  already recorded for pacing. Report both columns or neither.
- **Do not change the defaults.** Arbitrary is not the same as wrong, and
  rewriting them breaks comparability with every score already computed while
  buying no justification. Disclosure is the fix, and it is written.

What is left is `TODO.md` item 1: three public wordings that are stronger than
the evidence, including the site's "empirically grounded database of
sensory-load profiles". A product decision, not code.

**Also fixed on the way:** the shipped `Toddler (0-2)` preset described flashing
as "weighted higher (safety)" — an interface string, rendered in Settings,
claiming a photosensitivity safety assessment the tool explicitly does not
make. Rewritten; a test now fails if any preset mentions safety without
disclaiming it.

### The timestamp question, closed the same day

Whether the frame-step defect (libvlc's frozen clock, fixed 2026-08-11) had
biased the timestamps **already collected**. It had not, and the evidence is
decisive rather than a judgement call.

- **The marks were never stamped.** The defect can only reach a timestamp
  through the Stamp button, and `_fmt_hms()` writes tenths unless the clock is
  within 0.05 s of a whole second. Charlie Brown is 44 of 45 whole seconds;
  Little Bear is 86 of 86. Under a stamped hypothesis that is P ≈ 10⁻⁴⁴ and
  10⁻⁸⁶. They were hand-typed in `mm:ss` while watching.
- **A larger bias is real, from a different cause.** Second-truncation, mean
  −0.523 s (CB) and −0.610 s (LB), with 29/32 and 64/71 marks early — about 12×
  a single frame, so frame-stepping was never the dominant term.
- **It does not move the headline.** Re-scored with the project's own
  `compare_detections` in a scratch directory: correcting the full bias takes
  pooled F1 from 0.855 to **0.863**, one true positive. The uncorrected row
  reproduced the published 0.753 / 0.910 exactly, which is what makes the rest
  of the column trustworthy.
- **The limitation that matters:** ±2 s is a *floor*, not a free parameter. Any
  tolerance below ~1 s measures the whole-second coding resolution rather than
  the detector, so a sub-second claim needs frame-resolution recoding first.

**And a coverage claim that was overstated where it was published.** Every
comparison manifest records a window — CB 0–300 s, LB 0–320 s — so "two
episodes" is really **~10 min 20 s of video**, the first ~5 minutes of each.
`FOR_PAPER.txt` had this right all along; `ARCHITECTURE.md` §9, `CLAUDE.md`
§2.2 and `analyzer/provenance.py` did not, and provenance.py feeds the PDF, the
CSV sidecar, the JSON export and the public site. Same shape as the flashing and
F1 defects: the private notes were correct while the published claim was not.
All three now state the window, as does the exported `boundary_f1_basis`. **No
number changed.**

### The rename that followed (2026-08-14, same day)

The prose was already correct everywhere; **only the identifiers lied**, and
they lied in the worst available way — `REFERENCE_HARD_CUT_F1_*`,
`local_hard_cut_f1()` and the exported `"hard_cut_f1"` key all said *hard-cut*
for a type-agnostic ALL-row figure, while the hard_cut-only numbers for the
same two runs really exist (0.841 / 0.964). The name pointed at a real but
different quantity, so a reader who trusted it had nothing to catch them.

- Now `REFERENCE_BOUNDARY_F1_RANGE` / `_AGG`, `local_boundary_f1()`, and
  `boundary_f1` / `boundary_f1_source` in `validation_dict()`. **The number did
  not move**: `local_boundary_f1()` still returns `('0.85', 2)`.
- **`boundary_f1_basis`** is new and is the durable half of the fix: the
  exported file now *states* the estimand ("ALL row … ±2 s … detector
  content-t27-diss … single coder, PRELIMINARY") instead of encoding it in a
  field name. When the figure is computed live it names the run count for
  *this install*, not the reference study's two episodes.
- **`provenance_schema` is now 2.** A file with no such key is schema 1, and
  its `hard_cut_f1` field holds this same ALL-row figure despite its name — the
  one thing anyone re-reading an old export needs to know.
- **No deprecated alias.** Emitting both keys would have re-published the
  misnomer in every new export, which is what the item existed to stop. Safe
  because nothing in CMAT parses the block back: all four sites are writes, and
  no exported JSON carrying the old key exists in this working copy.

Rationale and rejected options in `DECISIONS.md`; the old-file caveat is in
`FOR_PAPER.txt` because it bears on any number quoted from a pre-rename export.
Tests: **325 passed, 13 skipped** — three new ones pin the key name, the basis
string, and that the basis describes the run that produced the figure.

## What happened before that (2026-08-10 → 08-11)

Late additions, after the Qt port:

- **Documentation layer built** — the nine files `INDEX.md` points at,
  reconstructed from six weeks of transcripts.
- **Three timestamp defects found and fixed in both coding editors.** libvlc's
  `next_frame()` advances the picture but freezes the clock, and corrupts the
  next seek. Frame-stepping is now a seek of one frame duration in both
  `ui/player.py` and `gui_coding_editor.py`; backward stepping now works.
  **Timestamps already collected are unaffected by the fix**, and were
  confirmed unaffected by the DEFECT too — assessed 2026-08-14, see below.
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

Nothing is half-finished. The seven formerly-untracked root files are sorted
(2026-08-14): four specs and a positioning brief into the new **`design/`**
folder, the Qt stylesheet sample into `ui/reference/`, and `preview_ui.py`
deleted — it opened `GeminiPipeline.qss`, a filename that has never existed in
this repo, so it could not have run. `docs/` was deliberately not used: it is
gitignored, so moving a document there would have silently untracked it,
including the north-star spec. What remains is `TODO.md` item 12 — folding the
two overlapping positioning documents into `ROADMAP.md`.

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
  headline **boundary** F1 of 0.85 is type-agnostic (the `ALL` row), ±2 s, and
  from a preliminary single-coder pilot. `ARCHITECTURE.md` §9 has the full
  table. **It is not a hard-cut figure** — that is a different, real number
  (0.841 / 0.964), and calling it hard-cut is the mistake that cost this
  project a published contradiction.
- **The research context is a thing now.** `analyzer/scope.py` decides which
  episodes a screen is showing. `CLAUDE.md` §3 rules on *scope* vs *selection*
  — they are not synonyms and the difference matters. `ARCHITECTURE.md` §1 has
  the concept.
- This working copy has real data: **32 shows, 137 episodes, 14 indexed**, 29
  pipeline documents, 22 trials. (It was 203 episodes until 2026-08-15, when
  66 duplicates were moved out — see below.) Tests must not write into it — a
  previous session's manual test created a stray pipeline document that had to
  be removed by hand.

## Picking this up cold on 2026-08-17 or later

The research context is **finished as a feature**: five commits across
2026-08-15 and 2026-08-16 built it and gave it to all six screens.
**Everything is committed and the suite is green (383 passed, 13 skipped).**
Nothing is half-finished.

The three things most worth knowing before choosing what to do next:

1. **The scope work is done; the wires are not.** The last bullet of `TODO.md`
   § *The research context, continued* — making a pipeline's connections carry
   the working set from stage to stage — is the north-star spec's "output
   produced here becomes input there", and it is the first thing that would
   make *drawing* the graph matter. `doc.connections` is still only counted and
   `node.config` is still written by the templates and read by nothing. It is
   a bigger piece of work than any of the five so far; do not start it in a
   session that has other goals.
2. **A root cause is still open, though its known symptoms are now fixed.**
   The sampler's analysis path does not go through `analyzer/show_index.py`,
   so anything it touches is named and listed by different rules. It produced
   two defects: a drawn `.mkv` invisible in the Library (fixed by unifying the
   extension set) and an index row whose show name was a raw relative path
   (fixed 2026-08-17, as a side effect of the backfill bug below, not by
   routing the sampler through `show_index` — that root cause is still open).
3. **The stored `shows` table's staleness is fixed where it mattered, plus a
   second bug found on the way.** `cli.py db --shows`, `ui/main_window.py`'s
   `rescore_index` and `gui.py`'s `_backfill_index` all shared one bug: a show
   split across season subfolders had its aggregate overwritten by whichever
   season was walked last, rather than merged. Fixed in all three 2026-08-17 —
   see *What changed on 2026-08-17, latest of all* above. `ui/index_tab.py`'s
   `summarise_shows` was never affected; it derives from the episodes on
   screen instead of reading the stored table.

All three items above are closed as of 2026-08-17 — this section is kept as a
record of what "picking it up cold" looked like that day, not as live status.
For current status read the top of this file.
