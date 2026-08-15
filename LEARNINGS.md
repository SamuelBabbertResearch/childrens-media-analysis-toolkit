# CMAT — Learnings

Things that went wrong, why, and how to avoid them. Architecture choices belong
in `DECISIONS.md`, not here.

Format: **what went wrong** · why · how to avoid it.

---

## The shape most of these share

Read this before adding to the list, and before believing a piece of work is
finished.

Nineteen defects were found in four audit passes on 2026-08-14, two of them
already published to OpenChildrensMediaIndex.org. They look unrelated — a
crash, a sampler, an F1, a startup cost — but almost all of them are one of
five shapes, and every one was **invisible from the interface**. The control
was present, the button worked, the tests passed, and the record described the
design that was *asked for* rather than the one that ran.

**1. The display and the calculation disagreed.**
The composite is derived. Four separate readers took the stored copy instead
of re-deriving it, so the Library, the CLI, the index backfill and the batch
runner gave four answers for one episode. The report and the chart read
nominal weights while the engine used redistributed ones, so a silent
episode's breakdown was 0.057 short of the score printed above it.
*Test:* does the breakdown add up to the headline?

**2. The control existed; the data path did not.**
"Stratify by era" was offered for months while `Episode.extra` was populated by
nothing. `load_registry_csv` dropped every column it did not recognise, so the
documented "group by any column" could never work.
*Test:* run it and look at the strata, not at the dropdown.

**3. A claim was restated instead of read.**
`provenance.py` calls itself the single source of truth for accuracy;
`build_site.py` hard-coded its own F1 and its own validation statuses, and
published both. The registry marks flashing unvalidated; provenance called it
deterministic. Five surfaces each decided independently whether to flag
unvalidated measures and most decided "not at all".
*Test:* grep for the claim's text, not for the function name.

**4. Two things were averaged that are not comparable.**
"AGGREGATE F1 0.891" was ContentDetector and TransNetV2 summed over the same
episodes; the real figures are 0.855 and 0.928. `local_hard_cut_f1` guards
against exactly this and says so in its docstring — its neighbour in the same
module did not.
*Test:* when one function in a module guards against a mistake, that guard is
a specification for its neighbours.

**5. The same one-line mistake, repeated.**
Because each site was written by reasoning locally, and each was correct on
its own reading. Fixing the first instance is the least useful response.
*Test:* grep for the shape before fixing the instance.

### Why they survived

- **Verification stopped at "it ran".** Rendering, passing tests and a
  responsive button are all compatible with a wrong number.
- **The port was audited by SCREEN.** That finds a missing screen. It cannot
  find a control whose data path is empty, and it scores a feature broken in
  *both* builds as present in both.
- **The tests were written alongside the code, so they shared its blind
  spots.** The suite went 221 → 315 passing while every one of these was
  live. The tests that actually caught things assert on artefacts — drawn
  strata, manifest notes, whether a breakdown reconciles — not on which
  widgets exist.
- **Completion was declared from the builder's side** three times: "migration
  complete", then "feature gap closed", then "closed" again. Each time it
  meant "I finished what I set out to build", which is a different claim.

### What to do instead

Run the thing and read what it produced. For anything that makes a research
artefact — a sample, an export, a report, a published page — the test is the
artefact. `tests/test_eras.py`, `tests/test_provenance.py`,
`tests/test_composite_display.py` and `tests/test_derived_consistency.py` are
written that way and exist because nothing else caught these.

---

## Measurement and calibration

These are the recurring ways the numbers have been wrong. Every one was caught
by a result disagreeing with obvious judgement — which is the main quality
control this project has, and worth using deliberately.

### Metric names that mislead
**What.** Four numbers read as something other than what they measure.
**Why.** Each is a reasonable name for a slightly different quantity:

| Reads as | Actually is |
|---|---|
| `words_per_minute` — talkativeness | speech rate **while speaking** (divides by dialogue time, not runtime) |
| `contrast_mean` — change between frames | **spatial** brightness spread *within* a frame, averaged |
| `dynamic_range_db` — peak to noise floor | **peak-to-mean** ratio |
| `temporal_var` — a standard deviation | a **variance** |

**Avoid.** Check `ARCHITECTURE.md` §8 before interpreting any of them, and pair
WPM with `speech_density` whenever it is shown.

### The composite silently ignores most of what is measured
**What.** Assuming "sensory load" summarises everything CMAT measures.
**Why.** Only six inputs are scored. Shot length, `shot_length_cv`, motion
peak, audio peak and variance, dynamic range, all speech and vocabulary
metrics, dissolves, scene relation and hand-coded events are **reported and not
scored**.
**Avoid.** Two episodes with identical composites can differ enormously on
things the composite never looked at. Name the metric rather than the composite
when the metric is what matters.

### Values above the ceiling are indistinguishable
**What.** Under a tight preset, very different shows post identical component
scores.
**Why.** Normalization is min-max against a fixed range and **clamped to
[0,1]** — everything above the ceiling is 1.0.
**Avoid.** Expected behaviour of a fixed range, not a bug. When a comparison
looks flat, re-read it under a broader preset before concluding the shows are
alike. See also the ceiling entry below.

### A no-audio episode is scored differently, not just differently sourced
**What.** Comparing a 0.30 with audio against a 0.30 without.
**Why.** Missing audio redistributes its weight proportionally across the five
visual metrics. The score stays on 0–1 but is not composed the same way.
**Avoid.** Check `sensory_load.audio_available` before any comparison.

### Zero cuts can mean a slow episode or a failed detection
**What.** `cuts_per_min` 0.0 with `shot_length_cv` 0.0 looks like a valid
measurement of very slow content.
**Why.** No detected cuts yields one shot spanning the whole file.
**Avoid.** Treat an exact zero as suspect and check the video before believing
it.

### Rankings invert when a show has too few episodes
**What.** *Little Bear* ranked above *SpongeBob*; lectures ranked above
*Bluey*; *Franklin* looked wrong.
**Why.** Small-N artifacts. A handful of episodes from one show against a full
season of another is not a comparison. Adding more *Franklin* episodes made the
ordering resolve itself with no code change.
**Avoid.** Before believing a cross-show ranking, check the episode counts on
both sides. Treat a corpus-wide index as provisional until the shows in it are
sampled comparably.

### A ceiling can compress the difference it exists to show
**What.** Under the General preset, *Bluey* at 11.1 cuts/min read as only 18.5%
of the pacing scale, so its pacing advantage over a lecture almost vanished.
**Why.** The 60 cuts/min ceiling is set for the fastest content that exists, so
ordinary children's television sits in the bottom fifth of it.
**Avoid.** This is a real property of fixed reference ranges, not a bug — it is
why presets exist and why tight presets carry an explicit note. When a
comparison looks flat, check which ceiling is in force before changing weights.

### Feature-length films do not belong in an episode ranking untagged
**What.** *Ocean Waves* (72 minutes) ranked implausibly high.
**Why.** Format confound: a film is not an episode, and per-minute rates plus
equal weighting do not make it one.
**Avoid.** Keep films and episodes distinguishable in the corpus, and be
suspicious of any ranking where a feature sits among half-hour episodes.

### Renaming a show folder silently invalidated its data
**What.** A folder renamed from the show's title to a studio name kept showing
the old title in the index, with figures "way off".
**Why.** The cache is keyed on the path (`.analysis/<show_key>/<stem>.json`) and
the index row is keyed on the file path. Renaming orphans the cache and leaves
the old index rows behind — first hit **2026-06-28**, and the same root cause
as the duplicate-rows bug below.
**Avoid.** Re-analyse after moving or renaming anything. The durable fix is to
key the cache on a content hash (size + duration) — still open, see
`ROADMAP.md`.

### Seasons in subfolders get treated as separate shows
**What.** Season folders inside a show folder were repeatedly conflated with
shows — "it is still conflating season files within a show file as different
shows", and full-series aggregates would not produce.
**Why.** Two layers disagree, and both are working as written. Folder
discovery sees one level of nesting, so `Show/Season 1/*.mp4` reads as category
`Show` containing show `Season 1` — that is what `show_key` and the cache path
use. But `show_index.show_name_for_db()` recognises season folders and files
them under the **parent** name, so the index shows one show with a season
number.
**Avoid.** Know which layer you are looking at. Selecting `Arthur` in the
Library reporting "groups shows" is the tree layer; the Index showing one
`Arthur` is the database layer. **Full Series Aggregate** is the cross-season
view, and as of 2026-08-14 it exists in both builds — it goes around the tree
layer entirely, aggregating every cached episode under the root.

### The sampler's CSV paths did not match the cache's keys
**What.** Loading a sampling template failed to find already-analysed episodes;
it recurred after a restart.
**Why.** The sampler wrote paths in one form and `show_key()` derived another.
**Avoid.** The same class of defect as the duplicate index rows: **one spelling
of a path, normalised at the choke point.** Any new component that writes a
path into a file is a candidate for this bug.

### The video clock lies in three different ways
**What.** The coding timer visibly stuttered — 00:01.0 → 00:01.2 → 00:01.4 →
00:01.7 — which turned out to be the least of it. Measured on 23.976fps
material:

| | Behaviour |
|---|---|
| **Playing** | libvlc's clock advances in jumps of **0.25–0.5s**, not per frame. A mark made while playing can be half a second stale. |
| **Frame stepping** | `next_frame()` advances the picture but **leaves the clock frozen** — three steps from 30.000s all still reported 30000ms. Every step was invisible to the recorded timestamp. |
| **Seeking after a step** | The next seek is applied wrongly and **never corrects**: a seek to 45.0s landed at 40.040s and stayed there through 1.4s of polling. |

**Why it mattered.** The codebook's timestamp target is **±1 second**, tightening
to ±1.0s tolerance for fast-cut content. The playback lag alone spends half that
budget, and the frame-step bug is silent and systematic — the coder sees the
right frame and records a different time.

**The fix.** Do not use `next_frame()`. Step by seeking one frame duration:
`seek(position + 1/fps)`. Verified — steps land within a millisecond of the
frame boundary, the clock follows, later seeks stay exact in both directions,
and stepping *backwards* becomes possible, which `next_frame()` cannot do.

**Avoid.** Never trust a media library's clock without measuring it. "The player
shows the right frame" and "the API reports the right time" are different
claims, and the gap between them is invisible from the interface.

## Reporting and correctness

### Unanalysed episodes were reported as failures
**What.** The first show-aggregate report read "1 of 6 measured; 5 failed" for a
show where nothing had failed — the five had simply never been analysed.
**Why.** `failed_count` was computed as `episode_count - len(ok)`. The cache
holds only what has been run, so everything absent from it looked like a
failure. A comment in the same function warned against exactly this.
**Avoid.** Three states, not two: measured, failed, not analysed. Anything
missing from `results` has not been run. A comment warning about a trap is not
the same as handling it — check the code does what the comment says.

### The index held two rows per episode
**What.** 24 rows for 13 episodes. Every show aggregate read from the index
double-counted them, and "Remove Stale" could not clear it.
**Why.** `file_path` is the primary key, and the same episode reached through a
relative root and an absolute one produced two rows. Both spellings still
resolved to a file that exists, so nothing looked wrong from inside the app.
**Avoid.** Normalise at the choke point, not in the callers. It also closes the
subtler half: a note saved under one spelling was invisible under the other.

### A cancel would have been recorded as a failed episode
**What.** Cancelling a batch run raised an exception from the progress callback.
**Why.** `analyze_show_batch` wraps each episode in `except Exception`, so the
cancel would have been swallowed and the episode marked *failed* — a cancel that
silently corrupts the record.
**Avoid.** The cancel signal derives from `BaseException`. A test pins the base
class, because making it an ordinary `Exception` later would reintroduce the
bug quietly.

### The video kept playing under a button reading "Pause"
**What.** After opening an episode, a seek to 30s recorded 31.02s.
**Why.** The arrival pause used `pause()`, which **toggles** — and a toggle sent
before playback has actually begun does nothing. Every mark would have been late
by however long the coder took to notice.
**Avoid.** `set_pause(1)`, retried until the player reports stopped. Measure the
timestamp rather than watching the window: the defect was invisible on screen.

### A PySide6 wrapper can read as "already deleted" while the object is fine
**What.** `menubar.actions()[0].menu()` raised "Internal C++ object
(QMenu) already deleted", which looked like the File menu had been destroyed —
a serious bug, since it would mean the menu stopped working after startup.
**Why.** It had not. `actions()` returns a temporary Python list of QAction
wrappers; indexing it and immediately calling `.menu()` lets the temporary go
before the returned QMenu wrapper is used. Holding the list first —
`acts = list(bar.actions())` — works, and the menu had all 14 items.
**Avoid.** Before believing a Qt lifetime error, re-test holding every
intermediate wrapper in a named variable. Chasing this one also produced a
*wrong* fix — stashing the QMenu on `self`, which creates a second wrapper
that really does go stale when the bar is reparented. The wrong fix reproduced
the same error, which made it look confirmed.

### Dropping a QThread reference inside its own signal handler crashes Qt
**What.** Three new screens — Vocabulary, Validate tool, Optional tools — set
`self._worker = None` in the slot connected to that worker's finished signal.
**Why.** That drops the last Python reference to the QThread while it is still
inside `emit`, so the C++ object is freed underneath itself. The process dies
with **no traceback and no Python exception** — it just disappears, which is
why it does not look like a code bug at all.
**Avoid.** Never rebind or delete a QThread from a slot connected to it. Keep
the reference and let `isRunning()` answer "is it busy" — the pattern
`AutomatedTab` already used correctly, and which the three new screens were
written without looking at. When adding a worker, copy the existing one.

### An import at module scope is a cost paid on every launch
**What.** `python cmat_qt.py` took 2.4s to import its main window before
drawing anything, and Measurement settings took **4.2 seconds** to open.
**Why.** Three module-level imports of heavy libraries, none of them needed to
start:

| Cost | Import | Reached from | Needed for |
|---|---|---|---|
| ~1.13s | `pandas` in `analyzer/aggregate.py` | `compute_show_aggregate`, used building the Library | CSV export only |
| ~0.64s | `scenedetect` in `metrics_cuts.py` and `validation.py` | `analyzer.pipeline` -> `trials` -> `validation` | running detection only |
| ~3.6s | PyTorch, via `OptionalTool.is_available()` calling `import_module` | greying out a combo-box entry | never, for that question |

**Avoid.** A module that the interface touches at startup must not import a
heavy dependency at module scope — put it inside the function that needs it,
as `analyzer/validation.py` already did for the optional TransNetV2 detector.
And to ask "is this package installed", use `importlib.util.find_spec`, which
answers without executing the package. Measured after: import 2362ms -> 433ms,
Measurement settings 4179ms -> 93ms.

### An aggregate F1 was averaged across two different detectors
**What.** `validate_cuts.py summary` and the Validate tool screen both showed
"AGGREGATE F1 0.891" over four comparison files. Those four were two episodes
scored twice — once with ContentDetector, once with TransNetV2. The real
figures are 0.855 and 0.928; 0.891 describes no detector that exists. It also
hid the most interesting number in the set: dissolve F1 is **0.133** for the
shipped detector and **1.000** for TransNetV2.
**Why.** `provenance.local_hard_cut_f1` filters by detector tag and its
docstring explains exactly why — "aggregating across detectors would blend …
into one meaningless average". `aggregate_summary`, written for the same data,
did not, and it is what the CLI and the interface display.
**Avoid.** When one function in a module already guards against a mistake, the
guard is a specification for its neighbours, not a local detail. `aggregate_summary`
now takes a `detector_tag` and returns which one it used, so a caller cannot
show the number without being able to say what it is OF.

### The estimand lived in a field name, and the field name was wrong
**What.** The headline accuracy figure was carried as `REFERENCE_HARD_CUT_F1_*`,
`local_hard_cut_f1()` and an exported JSON key `hard_cut_f1` — for a figure
scored type-agnostically on the `ALL` row. Every piece of *prose* around it was
correct; only the identifiers lied. Renamed to `boundary_f1` on 2026-08-14.
**Why it was worse than a vague name.** The hard_cut-only F1 for the same two
runs exists and differs: 0.841 / 0.964 against the exported 0.85. So the name
did not merely under-describe the number — it named a different, real quantity,
and a reader who trusted it would get a wrong figure with nothing in the file to
catch them. A vague name prompts a question; a plausible wrong name does not.
**Avoid.** **Do not encode an estimand in a key.** A machine-readable export
should state what a number is *as a value* next to it — `boundary_f1_basis` now
carries "ALL row … ±2 s … detector content-t27-diss … single coder,
PRELIMINARY" — because a field name cannot be qualified, cannot be dated, and
is the one part of the file nobody re-reads. And version the block
(`provenance_schema`) the moment a key's *meaning* changes, so an old artefact
is identifiable by inspection rather than by remembering which era wrote it.
**Related.** This is the same defect family as the published F1 contradiction
that preceded it — see §4 and `DECISIONS.md`. Both came from a number and its
description drifting apart while each looked fine alone.

### The fifth reader of a cached composite — and the only one that publishes
**What.** `build_site.py` read `ep["metrics"]["sensory_load"]["score"]`
straight from the cache file, and built each show's aggregate from a stored
`aggregate.json`. Both are DERIVED values frozen at analysis time. When the
normalization ceilings were retuned on 2026-08-14 the index re-scored to 0.2654
for one episode while the site went on publishing 0.2241 — and a rebuild
changed nothing, because the rebuild was faithfully republishing a stale number.
**Why.** The identical one-line mistake had already been found and fixed in four
places (Qt Library, `cli._analyze_single`, `cli._db_backfill`, `batch.py`), and
`analyzer.cache.load_scored()` was created as the one sanctioned reader with a
docstring naming all four. `build_site.py` was not in that sweep — it does not
call `load_scored`, it opens the JSON itself, so a grep for the function name
could never have found it.
**Avoid.** **When you fix a repeated shape, grep for the SHAPE, not the fix.**
The sweep looked for callers of the cache API; this reader bypassed the API
entirely. Searching for `["sensory_load"]["score"]` — the *access pattern* —
would have found it immediately. The general rule: after centralising a rule
into a function, search for the raw operation that function wraps, because
anything still doing it by hand is exactly what you missed.
**Also.** A page that claims "every result is reproducible from the parameters
documented here" must generate those parameters from the config it actually
ran with. The methodology page listed sample rate and preset but not the
ceilings, so the claim was false the moment the ceilings changed. It is now
generated from `config.json`.

### A maintenance script pointed at a stale copy of the data
**What.** `patch_speech_cache.py` set `ROOT = Path(__file__).parent` and looked
for `<project>/.analysis`. That stopped being the library when the shows moved
into `Shows/`. Both directories exist here — 82 cached episodes in the stale
one, 28 in the live one — so the script ran happily against data the
application never reads, and reported success.
**Also, on process:** I ran it before inspecting it. It is additive and did no
damage, but "look at the target before writing" applies to running someone
else's script as much as to a delete.
**Avoid.** A script that mutates research data should name the directory it is
about to touch, take the root as an argument, default to the same remembered
root the interface uses, and offer `--dry-run`. It now does all four.

### The same one-line mistake, in four independent places
**What.** Reading a cached episode without re-deriving its composite. Found in
the Qt Library (fixed first), then `cli.py _analyze_single` (printed the
cached JSON verbatim), `cli.py _db_backfill` (wrote stale scores into the
index — it would have silently undone the index re-score fix), and
`analyzer/batch.py`'s cached-episode skip (so a batch that re-analysed some
episodes and skipped others mixed two scoring scales in one run).
**Why.** Each site was written at a different time by someone reasoning
locally, and each is correct on its own reading: "load the cache, use it". The
rule that makes it wrong — the composite is derived, so a stored one is a
cache of a derivation — lived only in a comment in `metrics_sensory.py`.
**Avoid.** When a rule has to hold at every call site, put it IN the call, not
in a comment near it. `analyzer.cache.load_scored()` is now the only sanctioned
way to read a cached result, and a test enumerates every reader. Fixing one
instance of a repeated mistake is the least useful response to finding it —
grep for the shape.

### A derived value stored in two places drifted between them
**What.** After "Apply & Re-score" the Library showed 0.107 for an episode and
the Index showed 0.132, with nothing marking either as stale.
**Why.** The composite is derived, and the SQLite index stores it. Fixing the
Library to re-score on read — correct in itself — made the two disagree,
because nothing rewrote the stored copy. The Index is the cross-episode
comparison screen, so its Tukey outlier fences were also being computed over
scores from a mix of weightings. The Tk build has `_backfill_index` for
exactly this; the Qt port never got it.
**Avoid.** When a derived value is cached anywhere, list every cache before
changing how it is derived. Fixing one reader is not fixing the derivation.

### Two trials of one episode looked like a contradiction
**What.** The Trials tab listed the same episode on the same date with F1 0.91
and F1 0.942, and no way to tell them apart.
**Why.** They graded DIFFERENT DETECTORS — ContentDetector and TransNetV2. The
tag was in the manifest filename and in the manifest's `detections_file` all
along; `discover_trials` never extracted it, so the registry whose whole
purpose is answering "where did this number come from?" could not answer it.
**Avoid.** When two records can legitimately disagree, the field that explains
the disagreement is not optional metadata — it is the point of the record.

### The provenance module contradicted the registry, and it was published
**What.** `analyzer/provenance.py` described flashing as a "deterministic
signal measurement — no detection step to validate", while
`analyzer/measurements.py` marked it UNVALIDATED and `CLAUDE.md` §2.2 names it
explicitly as unvalidated and *not a safety assessment*. Provenance is read by
the PDF export, the CSV sidecar, the JSON export and the public site, so the
wrong claim was not internal — it was published on 14 show pages.
**Also found.** `build_site.py` hard-coded a THIRD variant of the headline F1
("~0.84 … ~0.96") that contradicts the constants `CLAUDE.md` and
`ARCHITECTURE.md` quote — the very contradiction `TODO.md` item 1 exists to
settle — while the provenance docstring called itself "the single source of
truth … shown on every results view, export, and the public site".
**Why.** Prose describing status was written in one module and the machine
status in another, with nothing tying them. A module that CLAIMS to be the
single source of truth is not one until the other places actually read it.
**Avoid.** Derive the prose from the registry, and make the consumers call the
source rather than restate it. `tests/test_provenance.py` now fails if a tool
the registry marks unvalidated is described here as deterministic, and if
`build_site.py` restates a figure instead of reading it.

### The composite's own breakdown did not add up to the composite
**What.** On an episode with no audio track, the report's contribution column
summed to 0.2265 under a headline score of 0.2832 — and the stacked chart,
whose docstring promises "the bar's height is the composite", was short by the
same amount.
**Why.** `compute_sensory_load` redistributes audio's weight across the visual
metrics when there is no audio, but it redistributes into a LOCAL copy and
returns only the score and the normalised components. The report and the chart
read the nominal weights from `config`, so they explained the number with
weights that had not produced it.
**Avoid.** If a calculation adjusts its own inputs, the adjusted inputs are
part of the result — expose them. `effective_weights()` is now the single
implementation, called by the engine to compute and by the interface to
explain, and a test asserts the breakdown reconciles in both the audio and
no-audio cases.

### Auditing by output found four more defects in one pass
**What.** Told to re-check the sampler by running it rather than by comparing
controls, one afternoon turned up four:

1. **`sort_key` crashed on a partial timeline.** It returned `(season,
   air_date)` for dated episodes and `(season, episode)` for undated ones, so
   sorting a mixed list raised `TypeError: '<' not supported between int and
   str`. The normal case after a metadata import is *some* episodes dated —
   and the crash only became reachable because the era fix had just started
   filling air dates.
2. **A silent fallback where a date was missing.** With no dates at all,
   "order by air date" quietly became episode order while the manifest still
   recorded `sort_col: air_date`.
3. **`load_registry_csv` dropped every column it did not recognise**, so the
   documented `stratify_by = any column in Episode.extra` could never work
   from a registry.
4. **A derived era overwrote a declared one.** Once registry columns were
   read, the date-range pass ran over the top of them and collapsed eight
   correctly-labelled episodes into one `(no era)` stratum.

**Why they survived so long.** Every one of them is invisible from the
interface: the control is present, the button works, and the manifest still
describes the design that was *asked for* rather than the one that ran. Only
looking at the drawn strata shows the difference.
**Avoid.** For anything producing a research artefact, the test is the
artefact: draw the sample and read the strata, export the CSV and read the
columns. Write the test at that level too — `tests/test_eras.py` asserts on
`manifest.strata`, not on which widgets exist.

### A control that exists is not a feature that works
**What.** The Tk sampler offers "By era / custom column" and a column-name
box. Porting the screen, that option was dropped as "season or nothing" — and
the omission was only caught when it was pointed out. Checking properly then
showed the Tk control had never worked either: `Episode.extra` is populated by
neither `scan_entry_root` nor `load_registry_csv`, and a folder scan leaves
`air_date` as None, so stratifying by any column put every episode in one
`(none)` stratum. The design line still read "stratified", and the manifest
still recorded a stratified design.
**Why.** The audit that found the other sixteen gaps compared MENUS AND
BUTTONS between the two builds. That finds missing controls; it cannot find a
control whose data path is empty, and it scores a broken feature as present on
both sides.
**Avoid.** For anything that produces a research artefact, check the OUTPUT,
not the control: draw the sample and look at the strata. A feature is working
when its result is right, and "the button is there in both builds" is not
evidence about the result. The same question is worth asking of every other
`Episode.extra` consumer and every field a folder scan cannot fill.

### "Every screen is ported" was true and still left sixteen gaps
**What.** The Qt migration was reported complete on the basis that every Tk
SCREEN had a Qt equivalent. Asked to keep going, an audit of `gui.py`'s menus
and buttons against `ui/` found sixteen missing FEATURES — including all three
exports, both settings axes' second half, the optional-tools registry, episode
notes and metadata, and the analysis queue.
**Why.** The migration was tracked by screen because the screens were the
visible unit of work. Menu commands, per-panel buttons and dialogs opened from
other dialogs are not screens, so they were never on the list — and a
tab-by-tab comparison shows all six tabs present and reveals none of them.
**Avoid.** Track a port by the ENTRY POINTS the old build offers — every menu
item, every button, every dialog — not by the screens it draws. The audit that
found these was one `grep` over `add_command` and `tk.Button` and took a
minute; it should have been the first thing done, not the fourteenth.

### A staleness count can be honest and still mislead
**What.** Measurement settings reported "1 cached episode would become stale"
for a threshold change, in a working copy with 12 cached episodes.
**Why.** Correct, and incomplete. `analyzer.cache.is_stale` GRANDFATHERS
results written before measurement fingerprinting existed — with no
fingerprint to compare it returns False. That is the right engine default, or
one upgrade would invalidate an entire corpus. But only 1 of the 12 cached
results here carries a fingerprint, so the honest-looking "1" sat on top of 11
whose settings cannot be determined at all.
**Avoid.** When a check can return "no" and "cannot tell", report both. The
dialog now says "1 would become stale; 11 predate fingerprinting and cannot be
checked" — the second number is the one that actually describes this library.

### "Apply & Re-score" re-scored nothing in the Qt build
**What.** The Settings dialog's primary button promises to re-score every
episode from cache with the new weights. In the Qt build it changed the
weights, called `populate()`, and every screen went on showing the composite
the cache file had been written with.
**Why.** `rescore_episode` exists in `analyzer/metrics_sensory.py` and the Tk
build calls it on every read. The Qt build was written by porting the *screens*
and each one loaded `EpisodeResult.from_dict(cached)` directly, so the call
was never carried across. Nothing looked wrong: the numbers were real numbers,
just scored under the previous weights.
**Avoid.** A derived value must be derived at one choke point —
`MainWindow._cached` — and a test now fails if a screen calls `load_cached`
around it. More generally: when porting, list the *transformations* the old
code applied on read, not only the screens it drew.

### A source-text test passed while the import it asserted on was broken
**What.** `analyzer.pipeline._read_selected` was moved to `analyzer/scope.py`
so one module reads `selected.csv`. `MainWindow._show_sample_aggregate` imports
its reader *inside* the function, and that line still said
`from analyzer.pipeline import _read_selected`. **Sample Aggregate… would have
raised ImportError on click.** The full suite passed — 345 tests — because the
test for that method asserts `"_read_selected" in inspect.getsource(...)`, and
the string was still there. The rename had made the assertion true and the
feature broken at the same time.
**Why.** A function-local import is invisible to import-time checking, and a
test that greps source text cannot tell a name that resolves from a name that
does not. This is shape 3 — *a claim was restated instead of read* — with the
test doing the restating.
**Avoid.** Where a test must assert on source, assert that the symbols
**resolve**: parse the function, walk its `ImportFrom` nodes, and `hasattr` the
module. `tests/test_ui_qt.py::test_sample_aggregate_can_actually_import_its_
episode_reader` does this, and was confirmed by reverting the fix and watching
it fail. Grepping for a moved symbol (`grep -rn "_read_selected"`) found it in
two seconds; the suite never would have.

### Three settings each looked like they painted the widget black; none did
**What.** The coding screen showed the **Trials tab's list and "Trial detail"
panel** where the video should be, with the transport controls beneath it —
reported 2026-08-15 as "this screen is messed up". Nothing was mis-parented and
no view had switched: those were **stale pixels**. Before an episode is opened,
nothing ever painted the video surface, so whatever had been on screen
previously survived underneath it.
**Why.** `VideoSurface` set three things that each read as "this widget is
black": `setAutoFillBackground(True)`, `setStyleSheet("background:#000000;")`,
and `WA_OpaquePaintEvent`. The third defeats the first — it tells Qt to skip
erasing the background because the widget paints every pixel itself — and the
second does nothing on a plain QWidget, which does not draw its own stylesheet
background without `WA_StyledBackground` and a paintEvent. libvlc keeps the
`WA_OpaquePaintEvent` promise once a media is loaded; nothing kept it before.
**Avoid.** `WA_OpaquePaintEvent` is a *promise*, and the widget owes a
`paintEvent` that keeps it in **every** state, not just the one the author was
thinking about. More generally: when several settings all appear to specify the
same thing and the thing is not happening, they are probably cancelling rather
than reinforcing — read what each one does to the others. **Test by reading
pixels**: render the widget over a known background and check the colour back.
Every attribute involved was set correctly, so nothing short of the pixels
would have caught it (`tests/test_ui_qt.py::test_the_video_surface_paints_its_
own_pixels`).

### A count can reconcile in the model and still disagree with the rows
**What.** With a sample scope selected, the Library header read "9 episodes"
above **8** rows. Both numbers were correct: the draw selected nine files, all
nine exist on disk, and the tree can only show eight of them.
**Why.** `analyzer/sampler.py` draws six video extensions
(`.mp4 .mkv .avi .mov .wmv .m4v`); `show_index.list_episodes` is
`sorted(show_dir.glob("*.mp4"))`. A sample can therefore contain an episode the
Library cannot list — here one `.mkv`. Pre-existing and invisible until a
count was put beside the rows.
**Avoid.** Two layers that enumerate "episodes" by different rules will
disagree eventually; when one displays a total for the other's rows, say what
is not shown rather than showing a number that fails to add up.
**Fixed the same day** by giving both layers one definition —
`show_index.VIDEO_EXTENSIONS`, which `sampler.py` imports rather than restating,
with a test asserting the two sets stay equal. The four `glob("*.mp4")` sites
in `show_index.py` were shape 5 in miniature: each correct locally, and the set
they encoded was only wrong when compared with another module's.
**What it exposed.** The invisible `.mkv` had already been **measured and
indexed** — the sampler's own path does not go through the library walk — so a
file could be in the corpus, in the index, and absent from the screen that
lists the corpus. When two enumerators disagree, suspect that the *other* one
has already acted on what yours cannot see.

### The pipeline's derived status was not undisplayed — it was unreachable
**What.** `TODO.md` item 7 read "`analyzer/pipeline.py` already computes
`Stage.headline`, `Stage.details` and `Stage.next_action` and nothing displays
any of them". Displaying them showed nothing: every node of every *linked*
pipeline still reported "no derived status".
**Why.** *Link to Episode Sample* wrote a **show** key (`Show/Season 1`) into
`PipelineDoc.source_key`, while `build_pipelines()` keys its results
`sample:<folder>`. Two namespaces that can never match, so
`self._derived.get(doc.source_key)` was always `None`. The failure had an
honest message on every node card — "no derived status" — which read as "there
is nothing to report yet" rather than "this look-up cannot succeed".
**Avoid.** When a feature is described as *built but not shown*, run the
look-up before writing the display. And when two halves of a system are joined
by a string key, check a real value from each side against the other — the
comment in `pipeline_graph.py` says the two meet at `NodeType.stage_key`, and
they do; what did not meet was the key naming the *sample*.

---

## Working from design mockups

### Re-deriving the CSS by hand lost something every round
**What.** Several rounds of "it still doesn't match", each fixing some values
and missing others.
**Why.** The mockup CSS was being read and re-typed into the stylesheet each
time. The losses were invisible until the two were put side by side.
**Avoid.** Extract the stylesheets verbatim into `ui/reference/` and consume
them. Where Qt cannot use them directly, translate from a committed file that
can be diffed — never from a screenshot or from memory.

### Built the wrong mockup for a whole screen
**What.** The starting-layout wizard was built from `GeminiStartingLayoutAlternative.html`
when the intended file was `GeminiStartingLayoutAndSettings.html` — two
different designs of the same dialog.
**Why.** Both had been supplied at different times and were not compared.
**Avoid.** The supplied references agree on every value they share
(`#ECECEC`, `#7A7A7A`, `#B8B8B8`, `#2B73DE`, 20px buttons, 11px text). **That
agreement is the design.** A mockup departing from it is the thing to question,
not the thing to build.

### Chrome was right, density was wrong
**What.** "Looks nothing like the files I've sent", with the colours and layout
apparently correct.
**Why.** Every control was 20–50% taller than specified. Qt's defaults are
considerably airier than a dense desktop utility.
**Avoid.** Measure before theorising: row 23→19, header 30→20, button 27→20,
font 12→11. Every box metric must be stated or the interface drifts.

### Named a font for the wrong reason
**What.** Every string in the application had the wrong texture.
**Why.** A Lucida was named first because it was the closer period reference.
The mockup's stack resolves to **Segoe UI** on Windows, and Lucida Sans Unicode
is wide and softly hinted at 11px.
**Avoid.** Resolve a font stack for the actual platform rather than picking the
most authentic-sounding name in it.

---

## Qt behaviours that look like styling failures

Each of these cost real time and none is guessable. Also in `ui/DESIGN.md` §0.4.

### `QTextDocument` overrides heading sizes
A 13px rule on an `h1` still rendered near 24px: Qt's HTML importer applies its
own font-size *adjustment* that survives the stylesheet. **Use classed
paragraphs.** A test enforces it.

### QSS selectors do not match up an inheritance chain
A rule written for `QTreeWidget` does **not** apply to a `QTreeView`. Style the
class actually instantiated.

### `transparent` is not a valid gradient stop
Qt substitutes **white**, so a fade-to-nothing becomes a fade-to-white disc.
Use `rgba(255,255,255,0)`. This survived two attempts to remove a white ring
inside a selected radio button.

### A bare `QWidget` ignores a stylesheet background
Needs `setAttribute(Qt.WA_StyledBackground, True)`. `QFrame` does not. This is
why the inspector and the zoom pill first rendered untinted.

### Do not style a `QRadioButton` indicator into a circle
It is drawn as a small bevelled box that takes the widget background — stamping
a pale slab over a filled row — and reshaping it needs a radial gradient for the
dot, which runs into the `transparent` trap above. **Paint the mark instead**;
`Dot` in `ui/welcome.py` is twenty lines and exact.

### Qt focuses the first widget in the tab order
If that is a text field, any key the field consumes looks dead on a freshly
opened dialog — which is why the wizard's arrow keys only worked after closing
and reopening it. Set the intended focus in `showEvent`, **not** `__init__`:
focus set before a widget is shown does not stick.

### Bordering an item *and* setting `gridline-color` draws both
That is the doubled rule between cells. Items take `border: none`.

### `max-height` on a header section clips it
It cannot then grow to fit its text.

### `ResizeToContents` pins a column after sizing it
Good initial widths, but the user cannot widen it and long names stay elided.
Hand columns back as `Interactive` once sized.

### A `QProgressBar` draws nothing without a `::chunk` rule
Once the application carries a stylesheet, the bar renders as an empty trough
at any value — which reads as a hung run.

### `setStretchLastSection` is on by default
It parks a trailing column's figures an inch from their heading.

---

## Validation and external review

### The published hard-cut F1 was not type-correct
**What.** An external code review (Codex, 2026-08-05) found `score_by_type()`
credited a true positive by the *manual* type whenever any tool transition
matched, regardless of the tool's own type. Follow-up review found a further
matcher issue: correct cardinality, incorrect offset claim.
**Why.** The scorer conflated "a transition was detected here" with "the right
*kind* of transition was detected here".
**Avoid.** Validation code is the code most worth having someone else read: it
is the part that decides whether every other number can be believed, and it
fails silently by reporting a number that is merely too kind. Any published
accuracy figure should be re-derived after a scorer change, and the superseded
value kept in `FOR_PAPER.txt` with what changed.

### Event-level accuracy and count accuracy are different claims
**What.** A tool can produce a dependable episode-level cut *count* while
misplacing individual transitions, because false positives and false negatives
cancel.
**Why.** They are different estimands.
**Avoid.** Report both, and frame the count result as an estimand-specific
accuracy check — never as a substitute for event-level validation.

### Speech metrics reported "not available" while the analysis had the words
**What.** The console reported 1,297 words; the interface said speech was
unavailable. Separately, episodes with `.srt` files present were counted as
lacking them.
**Why.** The speech result was not reaching the same place the interface read
from, and caption discovery disagreed with what was on disk.
**Avoid.** When a metric is "missing", check whether it was *computed* before
assuming it was not — the gap between the engine and the display is a real
failure mode, and it looks identical to a measurement failure.

## Tooling and process

### A patch script failed silently and the work looked done
**What.** `ConfirmDialog` was imported but never called; the old message box
was still live. Caught only because a test hung on the real modal dialog.
**Why.** A string-replacement patch script whose anchor did not match the source
escaping — twice, both times with `\n` inside an f-string.
**Avoid.** Use the editing tools for anything containing escapes. After any
scripted edit, **grep for the new symbol actually being called**, not just
imported. Verifying a button exists is not verifying it does anything.

### Documentation described a build several commits out of date
**What.** `cmat_qt.py` announced "Screens ported so far: Library" long after
every tab was ported.
**Why.** Docstrings and `CLAUDE.md` were not part of the change that made them
false.
**Avoid.** A file that overstates progress is worse than one that says nothing.
When a screen lands, the sentence describing what is ported changes with it.

### Tkinter pack order (historical — does not apply to `ui/`)
`side=BOTTOM`/`side=RIGHT` widgets must be packed **before** any `expand=True`
sibling or they get zero size. This silently hid the Episode Sampler's Browse
buttons, three controls in Language → Vocabulary, and the Speech status note.
Found by walking the live widget tree and measuring every mapped control —
invisible to tests and to code review.

### Cache is path-based
`cache_path = root/.analysis/<show_key>/<stem>.json`. Renaming a show folder,
moving it into a category, or renaming episode files orphans the cache and the
analysis appears to vanish. "Remove Stale" finds the reverse. *Future
improvement:* key on a content hash (size + duration).

### A missing rationale was assumed to be a lost one
**What.** `ARCHITECTURE.md` §8.1a recorded that the composite's weights,
ceilings and additive form had "no recorded rationale anywhere", and `TODO.md`
framed the fix as a question only the author could answer from memory. Asked
directly, the author — a psychology researcher, not the implementer — said they
did not know, because the code and those values had been produced by an AI
coding assistant during development. There was never a rationale to recover.
**Why it matters.** For weeks the record described the gap in a way that
implied a human decision had simply gone unwritten. That framing is an
invitation to reconstruct: a later reader, human or model, fills a
plausible-looking justification into a space that was never occupied, and the
result is indistinguishable from a real derivation. The theory citations sitting
next to the composite (Huston & Wright, Lang) made this worse — they justify
which properties are *measured* and say nothing about how to combine them, but
proximity reads as derivation.
**Avoid.** **Distinguish "undocumented" from "underived" in the record itself.**
When a parameter has no source, write that it *has* no source, not that the
source is missing. And on a project where an assistant writes the code and a
domain expert owns the claims, treat every generated constant as underived until
someone states otherwise — the expert cannot audit a number they never chose,
and the assistant will not remember choosing it.
**Related.** Same family as the misnamed F1 and the flashing claim: a
description and a number drifting apart, each looking fine alone.
