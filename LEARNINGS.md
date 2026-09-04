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

**6. A many-to-one key's writer was never audited alongside its reader.**
Added 2026-08-17, from a defect outside the original nineteen. `db_show_key`
deliberately collapses `Show/Season 1` and `Show/Season 2` into one key so
the Index shows one show, not two — itself the fix for the defect below,
*Seasons in subfolders get treated as separate shows*. Three functions
re-derive the `shows` table from cache by looping over `list_shows()` (one
entry per season folder) and upserting once per loop iteration, so each
season's aggregate silently overwrote the one before it instead of merging.
The collapsing key had been applied everywhere results are *read*; nobody
had checked everywhere they are *written*, so the same show kept producing a
plausible, wrong, single-season number through two unrelated fixes that both
looked complete.
*Test:* when a key merges many sources into one, grep every writer of that
key, not just its readers — see *The fix for one season-collapsing defect
became the cause of the next*, below.

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

### The fix for one season-collapsing defect became the cause of the next
**What.** The entry above records the fix: `db_show_key` deliberately collapses
`Show/Season 1` and `Show/Season 2` to the same parent key, so the index shows
one `Show` rather than two. Three places re-derive the whole `shows` table
from cache — `cli.py _db_backfill`, `ui/main_window.py MainWindow
.rescore_index`, `gui.py _backfill_index` — and all three looped `for
show_dir in list_shows(root): ... upsert_show(...)`, once per `show_dir`.
Reported 2026-08-17 while closing `TODO.md` item 0 (recompute Spongebob's
aggregate after de-duplication): `cli.py db shows` read "1 episode,
avg_load 0.292" — worse than either number already on record as wrong.
**Why.** `list_shows()` returns one entry **per season folder**, not per
show. Grouping by `db_show_key` was the fix for the *display* layer (one
`Show` row, not two); it was never applied to the *write* layer. Each
season's `upsert_show` call is a full replace (`INSERT OR REPLACE` keyed by
`show_key`), so the season walked last silently overwrote every earlier
season's aggregate rather than merging with it. A show that fits in one
folder never exercises this path — it was invisible on Curious George and
Arthur, both single-folder in this library, and would stay invisible on any
show until it happened to be the one laid out with season subfolders.
**The trap.** Two entries above this one already record a duplicate-count bug
and a raw-path show-name bug on this exact show. Both looked fixed after
their own commits. Neither ever produced a *visible*, correct number,
because every backfill after either fix silently threw away all but one
season's episodes before anyone read the result — a fix downstream of an
unrelated bug can look like it didn't work, when the real fault is a third
thing neither fix touched.
**Fix.** All three functions now accumulate `(EpisodeResult, dname)` keyed by
`db_show_key` across every `show_dir` sharing one, and call `upsert_show`
once per key after the whole walk — not once per `show_dir`. Two regression
tests build a synthetic show split across two season folders and assert the
merged count and mean survive a backfill/rescore:
`tests/test_derived_consistency.py::test_backfill_merges_a_show_split_across_season_folders`,
`tests/test_scope.py::test_rescore_index_merges_a_show_split_across_seasons`.
`ui/index_tab.py`'s `summarise_shows` was never affected — it derives from
episode rows already on screen rather than reading the stored table, which
is exactly why `DECISIONS.md` gives it that design.
**Avoid.** When a stable key intentionally maps many source groupings to one
target row (a season-collapsing key, a normalised name, a content hash),
grep every writer of that key for a loop that upserts once per *source*
grouping rather than once per *target* key. A reader that derives on demand
cannot have this bug by construction; a writer that caches an aggregate can,
silently, and will keep looking plausible — a valid, if wrong, count and
mean, not a crash.

### Three patched copies of the season-overwrite fix became one function
**What.** The entry above fixed the season-overwrite bug identically in all
three call sites — `cli.py _db_backfill`, `ui/main_window.py MainWindow
.rescore_index`, `gui.py _backfill_index` — each patched separately. Per
`CLAUDE.md` §6 ("when a rule must hold at every call site, put it IN the
call"), three copies of one loop is a standing invitation for a fourth (a
future export script, a batch tool) to reintroduce the bug from scratch.
**Fix.** Factored the walk-`list_shows`/accumulate-by-`db_show_key`/upsert-once
logic into `analyzer.db.rebuild_show_aggregates(conn, root, fetch_result,
*, set_season=False)`. Only the part that genuinely differs between callers —
how to resolve one episode's scored `EpisodeResult` — stays with each caller,
passed in as `fetch_result(show_dir, skey, episode_path)`: `cli.py` rescoring
via `load_scored` + a loaded config, `gui.py` via `load_cached` +
`EpisodeResult.from_dict` + `rescore_episode`, `ui/main_window.py` via
`self._cached`. `set_season=True` reproduces the `auto_set_season` call that
`gui.py` and `ui/main_window.py` made per episode and `cli.py` never did.
Regression tests from the original fix (`test_derived_consistency.py`,
`test_scope.py`) needed no changes — they exercise the call sites, and the
call sites now share one implementation instead of three.
**Avoid.** When the same shape gets patched at multiple call sites for the
same bug, that's the signal to factor immediately, not to move on once the
bug is gone — the drift risk survives the fix.

### Two copies of "which sample does this node belong to" existed before either was extended
**What.** Building per-node sample binding (`TODO.md`'s "wires carry the set",
large slice) meant every node's derived status had to resolve via
`doc.upstream_sample_keys` instead of always `doc.source_key`. There were two
places doing that resolution: `MainWindow._stage_for` (feeds the Inspector)
and `MainWindow._stage_status` (feeds the canvas box subtitle) — the same
three-line `doc.source_key` → `self._derived.get(...)` → `.stage(key)` lookup,
independently.
**Why it mattered here specifically.** Extending only `_stage_for` would have
left the Inspector correctly showing a branch's own sample while the canvas
box beside it kept showing the document-default sample's status — the two
halves of one screen disagreeing about the same node, which is a worse defect
than either being wrong alone, because neither reading looks broken on its
own.
**Fix.** Factored both into one lookup in `MainWindow._stage_for(node)`;
`_stage_status` now calls `_stage_for` instead of re-deriving the same
pipeline lookup, and keeps only the formatting that differs (a status
suffix string vs. Inspector rows). (`_stage_for` absorbed what was briefly a
separate `_upstream_pipeline` helper once it also had to grow the Validation-
merge special case below — one lookup function, not two, stayed the rule
even as its body grew.)
**Avoid.** Per `CLAUDE.md` §6, this is the same shape as the season-overwrite
fix above, caught before it drifted rather than after: before extending logic
that resolves "which sample/pipeline does this node belong to," grep for
every other reader of `doc.source_key` first — a second copy found while
already mid-edit is cheap to fold in; one found later, after both have
diverged, is the harder fix.

### A document saved to one folder and reloaded from another looked like it never saved
**What.** "It doesn't save and I have to do the sampling again every time I
open the pipeline." Every write succeeded; nothing was lost or corrupted;
`save_doc` returned a real path each time. The work simply never came back.
**Why.** `save_doc` assigned `doc.path` only when it was `None`, and
`pipelines_dir(root)` returns `<root>/.analysis/pipelines` with a
`<app folder>/pipelines` fallback for when no library root is known yet. A
document first saved before a root was chosen — the startup wizard on a
first run, where `set_root` is never scheduled because there is no
`last_root_folder` preference — got its path pinned to the fallback. Every
later save, root or no root, kept writing there. `list_docs(root)` only
ever reads the library's own folder, so it found nothing and
`_discover_pipelines` fell back to `[default_doc()]` — a blank pipeline,
indistinguishable from "your work was never saved."
**Fix.** `save_doc` re-homes: it keeps `doc.path` only while that path is
already inside the target folder, otherwise it re-assigns into the target
and unlinks the old file after the new one is safely written (moved, not
copied — two files sharing one doc id would both be discovered and diverge).
**Avoid.** A save path cached on first write is a bug whenever the
destination can legitimately change later. The tell here was that the write
and the read used the same helper (`pipelines_dir`) with **different
arguments** at different times — `save_doc(doc, None)` early, then
`list_docs(root)` after. When a path helper takes a parameter that varies
over a session, check every caller passes the same value at every point in
the lifecycle, or make the later call re-derive rather than reuse. Also:
"it saves but reloads empty" is a *path* symptom far more often than a
serialisation one — check WHERE before debugging WHAT.

### The control for choosing a working set could not express the thing the user had built
**What.** Three rounds of fixes to "only one sample shows in the Library"
each found a real bug — merge scoped to Validation, then `_follow_node_scope`
using one key, then the scope union — and the symptom survived all of them.
The user identified the actual cause: "the library displays sampling rather
than pipelines (which can include two samples together)."
**Why.** The Showing: chooser was built entirely from `build_pipelines`,
which returns one entry per *drawn sample*. A pipeline combining two samples
had **no entry in the list at all**. So the ordinary way to change what the
Library shows could only ever express one branch — every fix upstream was
correct and none of them could reach the symptom, because the symptom was
that the control offered no such option to pick.
**Fix.** `_doc_scope` adds one chooser entry per pipeline document that
draws on more than one sample. See `DECISIONS.md`.
**Avoid.** Three fixes in a row that each verify green and leave the user's
symptom unchanged is itself the diagnostic: it means the bug is not on the
path being fixed. The tests passing were honest — they drove
`_open_stage_screen`, which *is* fixed — while the user was using the
Showing: dropdown, which was never in any test. When a report survives a
fix, ask **which control the user actually touched** before fixing the same
area again; a test that reaches the right outcome by a path the user never
takes proves the outcome is reachable, not that it is reachable *by them*.
Also: `build_pipelines` returning samples rather than pipelines is a naming
trap this project set for itself, and it hid the gap in plain sight — the
line read "for pipeline in build_pipelines" and looked exhaustive.

### One resolved sample fed the Library while the node above it reported two
**What.** With two Sampling nodes wired into one node, the Inspector
correctly reported the merged set, but the Library tab showed only one
show's episodes at a time — the other looked lost.
**Why.** `_stage_for` was fixed to merge across every upstream branch
(`merged_pipeline`), but `_follow_node_scope` — which decides what the
Library actually displays — still did `derived[keys[0]]` and built a scope
from that single draw. The two answers to "which episodes does this node
work on" were computed in different places from different amounts of the
available information.
**Fix.** `analyzer.scope.scope_from_draws` unions episodes across several
draw folders (de-duplicating by normalised path, `folder=None` because a
union is not any one draw's folder); `_follow_node_scope` uses it whenever
more than one upstream sample resolves.
**Avoid.** Fixing "which sample(s) feed this node" in the *status* path
without fixing it in the *scope* path left the interface self-contradictory
— the panel said two, the Library showed one. When a question has more than
one consumer, grep for every consumer as part of the same change; this is
the same shape as the two-copies entry below, and it recurred within one
session of it being written down.

### Drawing a NEW sample from a node never told the node about it
**What.** After the linking bug below was fixed, the user reported two more
symptoms from the same session's feature: editing (drawing) one Sampling
node's episodes looked like it changed "the overall sampling list for the
pipeline" instead of that node alone, and nothing was ever saved — redrawing
was required every time the pipeline was reopened.
**Why.** Two different actions look similar but are not: `_link_to_sample`
picks an EXISTING sample from a list (fixed below); `open_sampler` draws a
BRAND NEW one via the Episode Sampler dialog. Double-clicking a Sampling
node on the canvas opens the sampler through `STAGE_ACTIONS["sampling"]`,
but that dispatch called `open_sampler()` with **no arguments at all** — the
method had no way to know which node, if any, it was opened from. On a
successful draw it only ever called `self.set_scope(...)` (the ephemeral,
never-persisted session scope) and never touched `node.config["sample_key"]`
or called `save_doc`. So every draw, from either Sampling node, only ever
changed the session's current view — both nodes kept falling back to
whatever `doc.source_key` happened to be (or nothing), and since neither
node's own config was ever written, there was nothing to save or reload —
explaining both complaints as one cause.
**Fix.** `open_sampler(self, node=None)`: passed the triggering node when
opened from a Sampling node on the canvas (`_open_stage_screen` now calls
`STAGE_ACTIONS[...][1])(node)`, not `()`); on a successful draw with a node
given, writes `node.config["sample_key"]` and calls `save_doc` directly,
the same write `_link_node_to_sample` makes. The two other call sites
(File menu, toolbar button) have no node context and keep the old
behavior — rewired through a `lambda: self.open_sampler()` shim so Qt's
`triggered`/`clicked` signal's boolean `checked` argument does not leak
into the new `node` parameter via auto arity-matching.
**Avoid.** When a dispatch table calls a handler with zero arguments
(`getattr(self, name)()`), and that handler later needs to know WHICH
caller invoked it, check every dispatch site, not just the one you're
adding — this table had exactly one entry and was still trivial to miss
because the call site read as boilerplate ("just invoke the method"),
not as something that needed updating for the new feature.

### One "Link to Sample" method inferred which of two things it was doing from canvas selection state
**What.** After the merge fix below shipped, the user's exact reported case
(two Sampling nodes wired into one Selection node) *still* showed only one
show. The merge logic itself was correct — verified by a test that builds
the doc directly and calls `_stage_for` — so the bug had to be in how the
document actually GOT into that state through real clicking, which no test
exercised: every test set `node.config["sample_key"]` directly, never
through the real "Link to Sample" button or dialog.
**Why.** `_link_to_sample` was one method, reachable from two places —
`Manage → Link to Episode Sample…` (a menu item, no per-node meaning) and
the Inspector's button (shown per-node when a Sampling node is selected).
It decided which one to do by checking `self._canvas.selected_node()` at
click-time: if a Sampling node happened to be selected, it silently wrote
that node's `sample_key`; otherwise it wrote the document's `source_key`.
The likely real sequence: link Sampling node A (node selected, correct),
click over to link Sampling node B (correct), then reach for the familiar
`Manage` menu item to double check or relink — with node A (or B) still
selected from browsing. That menu click silently overwrote the DOCUMENT's
`source_key` instead of doing nothing, or worse, if a node was selected, it
looked like it worked but wrote to a different place than the user expected.
With both Sampling nodes still unbound at the node level after such a
sequence, both would fall back to the same single `doc.source_key` —
collapsing two branches into one, exactly the reported symptom.
**Fix.** Split into two signals and two methods:
`Inspector.link_requested`/`MainWindow._link_to_sample` always sets the
document default; `Inspector.link_node_requested`/`MainWindow
._link_node_to_sample` always sets the selected node's own key. Which one
fires is decided by which button was shown/pressed (`Inspector` sets an
internal flag when it builds the button, in `show_doc` vs. `show_node`), not
re-derived from canvas state when the click lands.
**Avoid.** A UI action that infers "which of two operations does the user
mean" from incidental, mutable state (what else happens to be selected right
now) rather than from which control was actually invoked is a bug waiting
for the exact sequence of clicks that makes the inference wrong — and by
its nature, that bug cannot be caught by a test that sets state directly
instead of driving the real control. When two conceptually different
actions share one handler, check whether the handler can tell them apart by
construction (which signal fired) before trusting it to infer correctly
from context.

### A merge tested on Validation shipped untested on the node type a user actually tried first
**What.** The multi-Sampling-node merge (`TODO.md`'s "wires carry the set")
was built and tested against Validation only, on the reasoning that
Validation was the one node type with real "compare two things" semantics.
Shipped, described in `TODO.md` as done. The first real use — a user wiring
two Sampling nodes into one *Selection* node, the more natural topology for
"combine two draws into one working set" — showed only one of the two shows.
`_stage_for` special-cased `kind.stage_key == "validation"` before falling
through to `pipelines[0].stage(kind.stage_key)` for every other stage type,
silently.
**Why the scoping was wrong.** Validation being the one node type that
*compares* two things does not imply it is the one node type that needs
*merging* — merging is just "union the episode sets," which every stage type
downstream of more than one Sampling node needs equally. The comparison
question ("does A's automated pass agree with B's hand coding") is a
separate, harder, and genuinely Validation-specific question this project
correctly still refuses to answer (see `DECISIONS.md`) — but refusing that
one hard question is not a reason to also refuse the easy, safe union for
every other stage type.
**Fix.** Generalized `merged_validation_view` into
`analyzer.pipeline.merged_pipeline`, which builds one synthetic Pipeline
over the union and lets `.stage(kind.stage_key)` answer for whichever stage
type is asking — Selection, Automated coding, Language, Validation, all the
same code path. `analyzer.selection.write_narrowed_selection_from_sources`
got the matching fix for the Selection node's exclude action.
**Avoid.** When a fix is demonstrated on one example of a general problem
("a node fed by more than one Sampling node"), check whether the reasoning
for *why that example needed fixing* actually justifies restricting the fix
to it, or whether it was just the first/easiest example to reach for. Here
the tell was in the TODO/DECISIONS write-up itself: it named the *comparison*
question as the reason to scope to Validation, but the fix being built
didn't do any comparing — it only ever unioned, which is exactly what every
other multi-input node type needed too. A test for the general case (any
node type, not just Validation) would have caught this before a user did.

### Hand-coding coverage is keyed by bare episode stem, not by show
**What.** Building the merge (`analyzer.pipeline.merged_pipeline`, unioning
two samples' episodes for coverage counting) used a test fixture with two
different shows whose episodes both
happened to be named "S01 E01.mp4", "S01 E02.mp4", etc. The union of their
stems collapsed to the smaller show's episode count — one coded episode
disappeared from the count entirely, silently.
**Why.** `coverage_for_stems` (and the `sample_coverage` it was factored out
of) keys hand-coding lookups by `Path(fp).stem` alone. A stem is not a
globally unique episode identifier — only `db_show_key`-plus-stem is, which
is exactly why the index and cache already key on the compound form
(`LEARNINGS.md` § *the season-overwrite* entries, `analyzer/show_index.py`).
Coverage counting never picked up that convention.
**Fixed later.** `coverage_for_episodes` now carries full episode paths and the
library root, deriving the same `db_show_key`-plus-stem identity as the cache
and index. For a colliding stem, coding is accepted only from the matching show
subfolder. An old top-level sheet is ambiguous and counts for neither episode,
instead of being reused as evidence for both. Unique stems keep the permissive
legacy lookup, so existing projects do not need a filing migration.
**Avoid.** A bare filename stem is not a safe unique key anywhere in this
codebase; this is at least the third module (index, cache, now coverage) that
assumed it was one before finding out the collision the hard way. Any new
code keying anything by episode identity should use `db_show_key` + stem, or
grep for an existing helper, before reaching for `Path(x).stem` alone.

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

### The Qt counter froze during a scrub drag
**What.** Reported 2026-08-14 as "the time readout in the Qt player is wrong",
uncharacterised. Measured 2026-08-17 by driving `ui/player.py`'s `VideoPlayer`
headless: dragging the seek bar to 764.4s (50%) while the player sat paused at
10.0s left the digital counter reading `00:00:10.00` — the pre-drag position —
for the whole drag, only snapping to the real value on release.
**Why.** `_sync()` only wrote the slider from the player's position when
**not** scrubbing, but always wrote the *label* from the player's position
regardless. During a drag the player has not moved yet, so the label was
stale by however far the thumb had travelled, while the bar itself tracked the
mouse correctly.
**The fix.** While scrubbing, derive the displayed time from the slider's own
value instead of the (unmoved) player position, so the counter previews where
the thumb points; `_end_scrub()` already performs the real seek on release.
**What it did not affect.** `handcoding.py`'s `_mark()` calls
`player.position()` directly, never the label text, so no hand-coded
timestamp was ever written from the stale display — this was a display-only
defect. Seeking, frame-stepping and the playing-state jumps documented above
all measured correct, both before and after this fix.
**Avoid.** A widget with two derived displays (bar position and digital
readout) fed by two different guards is a standing invitation for exactly one
of them to forget the drag-in-progress case. Check both, not the one that
looked wrong.
**Superseded 2026-08-17.** `_mark()` no longer calls `player.position()`
directly — see the next entry. The observation above is still accurate as a
description of *that day's* code; it is not a description of today's.

### `player.py` claimed pause-before-marking was enforced; nothing enforced it
**What.** Following the scrub-drag fix above, the user asked why the playing
state counter still "isn't live and accurate." Measuring `_sync()` against
wall-clock time (not just watching the window) showed the displayed number
updates every 0.2–0.5s during playback against a real frame duration of
0.042s (23.976fps, confirmed independently with `ffprobe` — not a polling
artifact, not the file's fault). `position()`'s own docstring said
*"Pause before marking; the coding UI enforces that."* Grepping
`handcoding.py` for `is_playing`/`pause` found nothing. `_mark()` read
`player.position()` unconditionally — so a mark taken while playing could be
stamped with a value up to ~0.5s stale, the exact gap the docstring claimed
did not exist.
**Why the claim went unnoticed.** `frame_step()` and `seek()` (the *other*
precision operations on this player) do the right thing implicitly — a seek
always leaves the player in an exact state, so nothing about their behaviour
would have surfaced the missing enforcement. Only marking *while playing*
exercises the gap, and the codebook's own procedure (`EVENT_CODEBOOK.md`,
`CODEBOOK.md`) has a coder pause to consider each transition anyway, so the
gap rarely fires in practice — which is exactly the shape of defect this
project's `LEARNINGS.md` intro warns about: invisible from normal use.
**The fix.** `VideoPlayer.stamp(callback)` is now the one path to an exact
mark: paused -> calls back immediately (today's behaviour, unchanged);
playing -> pauses first (`set_pause(1)`, the same idiom `_hold_first_frame`
already uses and for the same reason — not `toggle()`, which assumes the
caller already knows the state being toggled away from), waits in a bounded
20ms-interval retry (measured: steady-state pause settles in ~20ms, the
15-try/300ms cap is a safety margin, not the normal path) until libvlc
confirms it, then calls back with the now-exact `position()`. `_mark()`
routes through it instead of reading `position()` directly, capturing
`etype`/`relevance`/`repeat`/`note` at the click so nothing the coder changes
during the (usually imperceptible) settle window can leak into a mark still
in flight.
**Also fixed, cosmetic only.** `_sync()`'s digital counter is now smoothed
during playback — extrapolated from the last real libvlc tick using
wall-clock elapsed time, snapping back into sync the instant a new real tick
arrives. This never touches `position()` or a stamped value; it exists only
so a coder watching playback gets live feedback instead of a number that
visibly sits still for 3-5 ticks at a time. Verified: display advances by
~0.1s every 100ms tick (previously frozen most ticks), never drifts more
than ~0.4s from the true value before resyncing.
**Not fixed here.** `gui_coding_editor.py` (Tk)'s `stamp()` has the identical
gap — `current_sec()` with no pause check, unlike that file's own
`frame_step()`/`seek_to()`, which already pause first. Out of scope for this
session (Qt is the active build per `TODO.md`); recorded here so it is not
mistaken for new when the Tk build is eventually audited (`TODO.md` item 9).
**Avoid.** A docstring that describes a guarantee is a claim, not a fact —
grep for whatever it says enforces the guarantee before trusting it. This is
the second time on this project a comment described the intended design
rather than the code that shipped (see *Unanalysed episodes were reported as
failures* below, "a comment in the same function warned against exactly
this").

## Reporting and correctness

### A coded segment divided by the whole runtime
**What.** Building the measurement model (`analyzer/constructs.py`,
2026-08-16), the first run over this working copy's real data resolved
Curious George S01 E01's hand-coded pacing as **0.084 hard cuts/min** against
a detected **17.785**, and a **mean shot length of 473 seconds** against a
detected 3.366. The sheet is four rows covering the first ten seconds of a
23.7-minute episode.
**Why.** `manual_pacing_metrics()` takes `duration_sec` and an optional
window, and uses the window as the denominator when given one. Hand coding
here is *segment* coding — the two validated episodes are the first ~5 minutes
of each — so without a window the whole runtime becomes the denominator and
the rate collapses by whatever fraction of the episode was actually watched.
Shot-length statistics are corrupted the same way and worse: the function
bounds the first and last shot by the span edges, so an unwindowed sheet
stretches its final shot to the end of the episode.
**The part worth keeping.** I had written the guard for exactly this and the
guard did not fire, because I made it conditional on the duration being
*unknown* — `if needs_window and window is None and duration_sec <= 0`.
Knowing the duration feels like knowing enough. It is not: the duration tells
you how long the episode is, and the question is how much of it was coded.
Those are different facts and only one of them was on disk. The condition is
now simply `window is None`.
**How it was found.** Not by a test — the tests I had written at that point
passed. By running the model over the real library and reading the numbers
next to the engine's numbers for the same episode, which is this file's
standing instruction and which took about ninety seconds to do.
**Scope in this working copy.** Three of five transition-coding sheets have no
recorded window: Curious George S01 E01, Little Bear 1x02, SpongeBob S01E01A.
The two that do — Charlie Brown and Little Bear 1x01 — are the two the
published accuracy figures come from, so **nothing published is affected**.
**Avoid.** When a computation needs the extent of what was *observed*, do not
accept the extent of what *exists* as a stand-in, however available it is. And
when writing a guard against a known trap, check what the guard actually
requires to be true — a guard with an extra condition on it is a guard that
does not fire, and it reads as protection at the call site.
*Test:* `tests/test_constructs.py
::test_a_sheet_with_no_recorded_window_refuses_every_span_dependent_value`,
which sets a known duration precisely so the duration cannot rescue it.

### A guard was wrong in both directions and nobody could tell
**What.** `test_no_screen_drops_its_worker_reference_in_a_slot` protects
against the fatal pattern in *Dropping a QThread reference inside its own
signal handler* below. It matched the literal line `self._worker = None`
anywhere in `ui/*.py`. Adding the Constructs tab tripped it — on the
initialiser in `__init__`, which is completely safe.
**Why it was wrong the OTHER way too, which matters more.** Every existing
screen passes it only because they happen to write
`self._worker: SomeWorker | None = None` with a type annotation, and the
annotated form does not match the string. So the guard would have waved
through the genuinely fatal `self._worker: SomeWorker | None = None` *inside a
slot* — the exact thing it exists to catch. It failed safe code and passed
dangerous code, and both directions were invisible because it had never had to
fire.
**Fix.** Parse instead of matching text: walk the AST for an assignment of
None to a worker-shaped attribute in any method that is not `__init__`,
annotated or not. Confirmed by re-introducing the annotated free-in-a-slot and
watching the new guard catch what the old one had not.
**Avoid.** A guard that has never fired is untested code with unusual
authority. When one finally does fire, check whether it is right before making
the code fit it — and check the case it is *supposed* to catch still fails,
not only that your own case now passes. A text match over source is the
weakest possible form of this and should be an AST walk wherever the thing
being matched has more than one spelling. Same family as *A source-text test
passed while the import it asserted on was broken*.

### One recipe's computed numbers were drawn under another recipe's name
**What.** The Constructs tab computes mean contributions across the scope and
keys them by measure. Selecting a different recipe redrew the canvas but kept
those numbers, and two recipes routinely share a measure — so switching from
the shipped composite to a hand-coding pacing recipe put **15.3763 cuts/min**,
the composite's ContentDetector mean, on a card whose method line read
**"Hand coding"**.
**Why.** The chooser was wired straight to `_redraw`, which rebuilds the scene
from whatever `self._parts` currently holds. Nothing tied the computed values
to the recipe they were computed for.
**Why it is worse than it looks.** The number was real, the card was real, and
the attribution was false — an automated detector's output presented as a
human coder's. That is the precise failure the measurement model exists to
prevent, reappearing in the first screen that draws the model.
**Fix.** The chooser goes through `_recipe_changed`, which clears computed
contributions first. A scope change does the same, for the same reason: they
were means over a different set of episodes.
**Avoid.** Derived display state keyed by something COARSER than the thing it
was derived from (measure key, when it was computed per recipe) will attach
itself to the wrong parent the moment that parent changes. Key it by what
produced it, or clear it when that changes.

### A dirty check ran one edit behind, so the rule the screen enforced could be skipped
**What.** The Recipes dialog disables Save until a reason is given, whenever
the operationalization changed — the screen's half of `bump_version`'s rule
that a version needs a reason. Driving it headlessly: change a weight, and the
status line said **"Nothing about the operationalization has changed"** and
**Save was enabled**. Give an unrelated keystroke afterwards and it corrected
itself.
**Why.** `_sync_buttons` builds a throwaway copy of the recipe and fills it
from the form, then compares its content hash against the baseline. Filling it
called `BindingBox.apply_to_binding()`, which wrote into `self.binding` — the
LIVE recipe's binding object — and never touched the copy it had been handed.
So the copy always described the state before the current edit: the check was
one edit behind, and the first edit after selecting a recipe was always
reported as no change at all. The version rule could be walked straight past.
**Why it was invisible.** Every control worked, the label was a plausible
sentence, and the *second* edit made it correct — so casual use looks fine and
the failure only shows on the first change after selection. The engine-side
rule was never wrong; only the screen's reading of it.
**Fix.** `BindingBox.values()` returns a dict and mutates nothing;
`_read_form_into(recipe)` matches bindings by measure key and writes only into
the recipe it was given, so it is correct for the live object and a copy alike.
**Avoid.** A method named `apply_to_X` that reads a widget and writes to a
fixed destination cannot be reused against a different destination, and the
caller that passes one has no way to find out — it silently gets the old
values. When a dirty check needs "what would this be if applied", the reader
must return values, not perform the application. Also: *a check whose answer is
correct one event later is indistinguishable from a working check in casual
use.* Drive the first interaction after a selection, not the third.
*Test:* `tests/test_ui_recipes.py
::test_changing_a_weight_demands_a_reason_before_save`, confirmed by
reintroducing the mutation and watching it fail.

### A composite with every weight still at zero scored 0.0
**What.** A brand-new recipe created from a construct has every weight at 0.0
until the researcher sets them. Evaluating one returned **score 0.0, status
complete** — a real number in the composite's own 0–1 range, sitting in the
results table next to genuine scores, reading as "measured, and very low".
**Why.** `Σ(weight × value)` over all-zero weights is 0.0, and nothing
distinguished that from a legitimately low score. The scale was 0.0 too, which
was the only clue, and it was not one anybody would read.
**Fix.** `recipes.evaluate` refuses when the total weight of the resolving
parts is zero, and says why: "every weight in this recipe is zero, so there is
nothing to combine … set the weights first".
**Avoid.** This is the same family as `code_events.py publish` writing 0.0
events/min for an uncoded episode, and as the audio and speech blocks whose
schema-default 0.0 now gates on an `available` flag — **an arithmetic identity
that lands inside the valid range of the thing being reported.** Whenever a
sum, a rate or a mean can be produced from nothing at all, check whether its
empty answer is distinguishable from a real one. If it is not, refuse.
*Test:* `tests/test_ui_recipes.py
::test_a_recipe_with_no_weights_set_refuses_rather_than_scoring_zero`.

### Attribution read off a rescored copy described today's settings, not the measurement's
**What.** Building recipes (2026-08-16), a recipe pinned to ContentDetector at
threshold 27 **refused its own episode** — one whose cache was measured at
exactly 27 — as soon as the live Measurement settings were changed to 33. The
refusal message said the result "was measured at 33.0". It had not been.
**Why.** `constructs._resolve_automated` read the tool attribution off the
result returned by `cache.load_scored`. That result is not the cached one: it
is rebuilt by `metrics_sensory.rescore_episode`, which constructs a fresh
`EpisodeResult` with `config=cfg` — **the config it was rescored WITH**. So the
"config that produced these numbers" field held the config in force *now*.
Using it for attribution reported current settings as the settings that
measured the episode.
**Why it was invisible.** It is correct whenever the live config and the
cache's config agree, which is the normal state and every state the tests had.
It is wrong exactly when they differ — which is the only situation in which
anyone asks what a number was measured with, and the entire reason pinning was
chosen over referencing. A defect that hides in the case you never ask about
and appears in the case the feature exists for.
**Fix.** Two reads, with the split documented at the call site: VALUES from
`load_scored` (still the one sanctioned reader, because the composite is a
derivation), ATTRIBUTION from `load_cached` (the raw file, because only it
carries the config that actually ran).
**Avoid.** When a function returns a *derived* copy of a record, check which
of that record's fields describe the original and which describe the
derivation. `rescore_episode`'s job is to recompute a composite; carrying the
new config forward is right for its purpose and wrong for anyone reading
provenance off the result. A field named `config` on a returned object does not
say *whose* config it is, and this codebase already has a rule for that shape —
`LEARNINGS.md` § *The estimand lived in a field name, and the field name was
wrong*.
*Test:* `tests/test_constructs.py
::test_attribution_describes_the_cache_not_the_settings_in_force`, which
deliberately sets a live threshold different from the cached one.

### `new_recipe` accepted a method key that does not exist, and only an export noticed
**What.** Building the construct store (2026-08-16), a test bound
`hard_cuts_per_min` to a method called `"content"` — a guess at the key, which
is really `auto:transitions:pyscenedetect_content`. `new_recipe` accepted it,
`save_recipe` wrote it, and the recipe file on disk looked entirely normal. The
only thing that ever complained was `import_recipe`, and only because the test
happened to round-trip through an export.
**Why.** `new_recipe`'s docstring says "nothing is invented: a measure with no
method is left out rather than bound to a placeholder" — and that is true of
the path it was written for, where the caller passes `measures=None` and the
methods are looked up. The *explicit pairs* path trusted its caller completely.
Both readings are locally correct, which is why nobody noticed the asymmetry.
**Why it matters more now than it did.** Until this phase, the only callers
were `shipped_composite` (which gets its method from `selected_method`, so it
is always real) and the recipe editor's New button (which uses the
`measures=None` path). Canvas authoring is about to make the explicit path the
main one, driven by user choices — so the permissive path was about to become
the common path.
**What it produces.** A binding that can never resolve: a recipe with a
plausible name, a version, a content hash and a citation, that refuses on every
episode with a reason naming a method nobody recognises. That is
`LEARNINGS.md` shape 2 — a control whose data path is empty — arriving through
the data model rather than through a dropdown.
**Fix.** `new_recipe` validates both paths and raises, naming the available
methods. Deliberately **not** applied to `Recipe.from_dict`: a recipe imported
from an install that has a detector this one lacks must stay readable with its
binding intact, which is `import_recipe`'s entire contract. Refusing to
*author* an unresolvable binding and refusing to *read* one are different
questions, and conflating them would have broken the import gap.
**Avoid.** When one function offers two ways in — a looked-up path and a
caller-supplied path — check whether a guarantee stated in the docstring holds
on both. This one held on the path it was written for and was silent on the
other.
*Tests:* `tests/test_construct_store.py
::test_authoring_a_binding_to_an_unknown_measure_is_refused`,
`::test_authoring_a_binding_to_an_unknown_method_is_refused`,
`::test_a_prebuilt_binding_is_checked_too`, and
`::test_reading_an_unresolvable_recipe_is_still_allowed` for the half that must
stay permissive.

### Two weights, entered for two measures, both written onto the first one
**What.** Building canvas authoring (2026-08-16). The Edit panel's bound-measures
list is refilled after every edit — add, remove, method change, weight change.
`QListWidget.clear()` drops the current row to **−1**, and the refill restored
the selection with `min(max(currentRow(), 0), n - 1)`, which turns −1 into 0. So
after each edit the selection silently snapped back to the first binding. Adding
`hard_cuts_per_min` at 0.6 and then `words_per_minute` at 0.4 wrote 0.6 and then
0.4 **both onto hard cuts**, leaving words per minute at weight 0.
**Why it was invisible.** Nothing on screen was wrong. The list showed both
measures with their real weights, the canvas drew both boxes, the wires took
their thicknesses from the same objects, and Save reported a new version with a
correct derived change list. The only artefact that disagreed was the recipe
file, and only because it was read.
**What it produces.** A composite whose declared weighting is not the weighting
the researcher entered — the exact quantity `ARCHITECTURE.md` §8.1a is about,
wrong in the stored operationalization, under a name, a version and a content
hash that all look authoritative.
**Fix.** The selection is carried by **measure key**, not by row, and the caller
that adds a binding names the measure it wants selected.
**Avoid.** When a list is rebuilt after every edit, restoring "the same row" is
not restoring the same thing — rows are positions and the contents moved. Carry
the identity, not the index. And the general form: **a control that edits
whichever item is selected needs a test that edits two of them**, because every
single-item test passes whether the selection is right or not.
*Test:* `tests/test_ui_constructs_tab.py
::test_a_weight_lands_on_the_measure_that_was_selected`, which enters two
weights and then reads the written recipe.

### `save_recipe`'s lock guard missed the one recipe it exists for
**What.** `save_recipe` refused a locked recipe only when it already had a file
on disk. The shipped composite is **generated** from the config rather than
loaded, so its `path` is None — and the first save of it was accepted, writing
`Sensory load _as shipped__r_shipped_composite.json` into the library.
**Why.** The rule was written as "refuses to *overwrite* a locked recipe", and
overwriting is what the code checked. For every recipe that comes off disk the
two readings agree. They diverge only for a recipe that never came off disk,
which is exactly the locked one.
**What it produces.** A stored copy of a recipe whose whole value is that it
follows the Scoring settings in force. It would stop following them: the
2026-08-14 ceiling retune moved every composite score in the project, and this
file would have gone on describing the old ones under the same name and the
same citation.
**Fix.** Refused on the lock alone; `import_recipe` clears `locked`, since a
lock is a claim about this install and an imported recipe must be saveable.
**Avoid.** When a guard's stated rule and its condition are different sentences,
find the case where they disagree — there is usually exactly one, and it is
usually the case the guard was written for. Same shape as
*Attribution read off a rescored copy* above: correct in every state the tests
had, wrong in the only state anyone asks about.
*Test:* `tests/test_shipped_composite.py
::test_the_shipped_composite_cannot_be_written_to_the_library_at_all`, which
now asserts the opposite of what it asserted before.

### A click wrote a layout file into a real research library
**What.** Node positions persist on mouse release. `mouseReleaseEvent` fires on
a plain click as well as on a drag, so merely selecting a box wrote a sidecar —
full of the **automatic** positions, recording no decision anyone had made. One
appeared in the real `Shows/.analysis/recipes/` during the session that built
this and had to be removed by hand.
**Why.** "Persist on drop" and "persist on release" read as the same
instruction. They are not: a release without movement is not a drop.
**Fix.** The press position is recorded and compared on release; no movement,
no write.
**Avoid.** `CLAUDE.md` §6 says never write into the working copy's data from a
test. This was not a test — it was ordinary code with a root pointing at real
research data, which is the more likely way that rule gets broken. Any new
writer of a file under `<root>/.analysis/` deserves the question *what is the
smallest gesture that fires this*, asked before it ships.
*Test:* `tests/test_ui_constructs_tab.py
::test_clicking_a_box_without_moving_it_writes_nothing`.

### `list_recipes` would have adopted the layout sidecars as recipes
**What.** Caught before it shipped, while adding the sidecar. `list_recipes`
globs `*.json` in the recipes folder, and `<recipe id>.view.json` matches.
**Why it would not have raised.** `Recipe.from_dict` is deliberately permissive
— it has to be, so a recipe naming a detector this install lacks stays readable
— so a sidecar would not fail to parse. It would parse into an *Untitled
recipe* over no construct with no bindings, and appear in the Recipes list and
the Constructs chooser as a real one.
**Fix.** Skipped by name, with the reason at the call site.
**Avoid.** When a permissive reader and a glob meet, the glob is doing the
validation. Adding any second file type to a directory something enumerates
means auditing the enumerator — the writer-side of `LEARNINGS.md` shape 6, one
directory over.
*Test:* `tests/test_ui_constructs_tab.py
::test_a_sidecar_is_never_read_back_as_a_recipe`.

### A weighted sum of a fraction and a rate, offered as a default
**What.** Found by looking at the Edit panel in the real application
(2026-08-16). A measure bound from the canvas palette got
`MeasureBinding`'s default transform — `none` — which feeds the **raw** value
into the composite. Cuts per minute runs around 15; colour saturation runs
around 0.46. Two measures added with equal weights therefore produced a score
almost entirely determined by whichever had the larger units, while both
weights on screen read as equal.
**Why it was invisible.** Every measure in the shipped composite is min-max
scaled, so nothing on the existing canvas ever showed an unscaled binding —
and the measure card only prints a "scaled over…" line when a transform IS
set, so an unscaled one showed nothing at all rather than showing a warning.
The panel did not display the transform, because transforms are edited on
File → Recipes…; "edited elsewhere" had quietly become "not shown here".
**Fix.** `recipes.new_binding()` applies the configured reference range where
the configuration has one, and BOTH creation routes go through it so a measure
cannot be scaled or raw depending on which screen bound it. Where no range is
configured — ten of the sixteen measures — the transform stays `none` and the
panel says so in those words, because inventing a ceiling is a scoring
decision made on the researcher's behalf and hidden in a default, which is
what `ARCHITECTURE.md` §8.1a is a record of. `recipes.mixed_scales()` reports
a recipe that weights a raw measure against a scaled one.
**Avoid.** A dataclass default is a decision. `transform = TRANSFORM_NONE` is
the right default for the FIELD and the wrong one for a composite, and the
gap between those two statements is where this lived. When a screen delegates
a parameter to another screen, it still has to display it — otherwise
delegation is indistinguishable from omission.
*Tests:* `tests/test_ui_constructs_tab.py
::test_a_bound_measure_is_scaled_when_a_reference_range_exists`,
`::test_a_measure_with_no_configured_range_says_so_instead_of_inventing_one`,
`::test_summing_a_raw_measure_against_a_scaled_one_is_reported`.

### A panel with a maximum width its own contents could not fit in
**What.** Reported from the real application with a screenshot: the Edit
panel's dropdown arrows, its Add button and its Save button were all drawn off
the right-hand edge of the window. The panel had `setMaximumWidth(340)`; its
`minimumSizeHint` was 372, and the reason field rendered 640 wide. Qt honoured
the maximum and let the children overflow.
**Why.** A `QComboBox` sizes itself to its widest entry. "PySceneDetect —
ContentDetector — validated" and "Pacing — All transitions per minute" are
long enough that two of them alone exceeded the cap.
**Fix.** A `QSplitter` instead of a fixed cap, so the panel takes the width its
controls need and the researcher can give it more; the contents in a
`QScrollArea`; and the combos made shrinkable
(`AdjustToMinimumContentsLengthWithIcon`) so the closed control can be narrow
while the popup still shows every item in full.
**Avoid.** `maximumWidth` does not make contents fit — it makes them
overflow. Compare `minimumSizeHint()` against any maximum you set. And note
what caught this: **no test could**, because every control existed, was
enabled, was correctly wired and had the right value. It was found by looking
at the screen, which is the one check this file cannot replace.
*Test:* `tests/test_ui_constructs_tab.py
::test_no_control_in_the_edit_panel_is_drawn_outside_it`, which asserts on
geometry — every control's right edge inside the viewport, and no horizontal
scrollbar needed.

### One word, two quantities, on two screens open at once
**What.** Reported from the real application within minutes of first use
(2026-08-16). The Constructs picker said Pacing had **"8 measures of its own"**
while the Constructs canvas beside it showed **"1 measure"**. Both numbers were
correct. The picker lists the CATALOGUE — every measure the model defines for
that construct — and the canvas counts BINDINGS in the recipe on screen. Pacing
defines eight measures across three aspects; the shipped composite binds one of
them.
**Why.** Both labels were written from inside their own screen, where the word
was unambiguous. Neither said which quantity it was, because in isolation
neither had to. Put side by side they read as a contradiction, and the first
thing a reader does with a contradiction is doubt the numbers.
**Fix.** The picker says "8 measures **available to bind**", the canvas says
"1 measure **in this recipe**", and the Recipes New menu says "available". The
canvas's caption moved into `ConstructItem.caption()` so a test reads what the
screen draws instead of restating it.
**Avoid.** Two screens can be individually correct and jointly wrong, and no
test of either one catches it. When the same noun counts different things in
different places, put the qualifier in the label rather than in the reader's
head — and note that this was found by LOOKING AT IT, which is the check the
whole of this file otherwise cannot substitute for.
*Test:* `tests/test_ui_construct_editor.py
::test_the_picker_counts_the_catalogue_and_the_canvas_counts_the_bindings`,
which asserts both numbers and both qualifiers at once.

### `new_recipe` accepted a construct key that does not exist either
**What.** The sequel to the entry above about method keys, found the same way —
by a test of mine passing the wrong thing. `new_recipe("...", None, ...)` built
a recipe over the construct `'None'`, and `save_recipe` wrote it: an ordinary
name, version 1, a content hash, a citation, and no definition anywhere behind
it.
**Why.** The method-key fix hardened the bindings and left the construct
argument trusted, because at the time the only callers passed a key they had
just read from the registry. Canvas authoring makes the construct key come from
a researcher's own library, which is precisely where a stale or deleted key
comes from.
**Fix.** `new_recipe` raises on an unknown construct, naming what to do about
it. Deliberately **not** applied to `Recipe.from_dict` — a recipe whose
construct came from another library must stay readable, and
`construct_divergence` reports it as `missing`. Refusing to *author* an
unresolvable reference and refusing to *read* one remain different questions.
**Avoid.** When a defect is fixed in one argument of a constructor, check the
constructor's other arguments for the same trust. This is `LEARNINGS.md` shape
5 — the same one-line mistake, one parameter over — and the first fix is what
made the second one visible.
*Test:* `tests/test_ui_construct_editor.py
::test_a_recipe_cannot_be_authored_over_a_construct_that_does_not_exist`.

### The pipeline panel named a show the pipeline draws nothing from
**What.** Reported from the real application (2026-08-16). The "Arthur
Language" pipeline showed **Arthur** on all four node boxes and, directly
underneath, **"Data source: Peep and the Big Wide World (need to manually trim
out bumpers)/Season 1"** — a completely different show, contributing no
episodes to the pipeline.
**Why.** `MainWindow._refresh_canvas` resolved the document's data source with
`self._derived.get(doc.source_key)`. Since per-node sample binding shipped, a
Sampling node carries its own `sample_key` and the document's key is only a
**fallback** for nodes that have none — which is how every node correctly read
Arthur. The document panel never asked that question. It read the stale
document-level key and presented it as the answer. `LEARNINGS.md` shape 1: the
display and the calculation disagreed.
**The part worth noticing.** The three lines immediately above the defect
already knew per-node bindings exist — `has_any_link` checks
`n.config.get("sample_key")` precisely because "a canvas can have Sampling
nodes linked to a sample without the document itself ever being linked". The
code used that knowledge to decide whether to load derived status, then threw
it away one line later when deciding what to display. Half-applied knowledge
in adjacent lines, not missing knowledge.
**Why it survived.** `_doc_sample_pipelines` — the ONE implementation of "which
samples does this document draw on", deliberately shared by the scope chooser
and pipeline selection so they could not answer differently — already existed
and was correct. The document panel simply never called it, so it was a third
answer to a question that had been consolidated to one. Consolidating readers
does not help a reader nobody noticed.
**Fix.** `_refresh_canvas` resolves through `_doc_sample_pipelines`. The panel
now has **three** states rather than two: a resolved source (named), a key that
is set but matches nothing (named, said to resolve to nothing, with the Link
button offered), and nothing at all. Collapsing the middle state into "not
linked" would have hidden a stale key; presenting it as the data source is the
original defect.
**A second, smaller one fixed alongside.** `Inspector.show_node(None)` — the
deselect path — called `show_doc(self._doc)` with no label, so clicking a node
and clicking away replaced the sample's readable name with its raw folder key.
The panel now remembers what it resolved.
**Avoid.** When a fallback becomes a fallback — when some other binding starts
taking precedence — grep every reader of the field that got demoted.
`doc.source_key` stopped being the answer and became the last resort, and the
readers were not re-audited. This is the reader-side twin of shape 6, which is
about auditing a key's *writers*.
*Tests:* `tests/test_scope.py
::test_the_doc_panel_names_the_nodes_sample_not_a_stale_document_key`
(the reported document reproduced),
`::test_a_document_key_that_resolves_to_nothing_says_so_rather_than_naming_it`,
`::test_the_document_key_is_still_the_fallback_when_no_node_is_bound` (the
behaviour the fix must not break), and
`::test_deselecting_a_node_restores_the_resolved_source_not_the_raw_key`. The
first and last were confirmed by reverting the fix and watching them fail.

### A stored hand-coded figure was two definitions old
**What.** Recomputing Charlie Brown's hand-coded pacing with today's code and
comparing against the values persisted on 2026-08-03 gave `mean_shot_sec`
**8.824** where the file said **7.048**, and `shot_length_cv` **1.27** where
the file said **0.791**. Rates and counts were identical.
**Why.** Not drift, and not an error in either number: the persisted file
predates the comparability fix in `validation/VALIDATION_LOG.md` item 4, which
changed hand-coded shot durations from interior gaps only (32 shots between 33
cuts) to shots bounded by the coded window edges (34 shots across 0–300 s), so
that the figure mirrors `compute_cut_metrics()` and is comparable with the
engine. Interior-only measurement biases the mean downward by dropping the two
window-edge shots.
**What it settles for the model.** `constructs.py` **recomputes** hand-coded
metrics from the sheet and reads the persisted file only for the *window* — an
input, not a derivation. This is the same rule `load_scored()` enforces for the
composite, applied on the hand-coding side: a stored derived value is a cache
of a derivation, and reading it as fact is how four readers gave four answers
for one episode.
**Avoid.** A persisted metrics file is dated evidence of what a definition
*used to be*. When the definition has moved, the file does not say so — it
just keeps returning a plausible older number. Recompute derivations; store
and read only the inputs.

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

### A derived table nobody refreshes is a wrong number with a timestamp on it
**What.** The Index's Shows view read `Spongebob Squarepants Season 1:
2 episodes, mean load 0.3071`. The index held **five** Spongebob episodes,
averaging **0.2557**. Both figures were on screen in the same tab — one on the
Shows view, one derivable from the Episodes view.
**Why.** The `shows` table is written by `upsert_show`, which runs when a
**whole show** is analysed. Analysing episodes individually updates `episodes`
and never touches `shows`. The row keeps its old `updated_at`, so it looks
current. Shape 1 — the display and the calculation disagreed — with the
disagreement stored on disk rather than computed twice.
**Avoid.** A summary of rows the user can see should be **computed from those
rows**, not looked up. `db.summarise_shows()` now does that, so the two views
cannot diverge. Where a derived table must be stored, the refresh has to hang
off the same event as the thing it summarises — and if it cannot, do not read
it. Note what this did **not** fix: `cli.py db --shows` and `gui.py` still read
the stored table.
**Also.** Sorting the derived rows with `(value is None, value)` and
`reverse=True` floats the blank rows to the **top** — `reverse` flips the flag
as well as the value. Partition into have/haven't and sort only the first.

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

### Five readers looked for the same coding sheet; one looked in one place
**What.** `code_events.py`, `analyzer/trials.py`, `gui_handcoding.py` and
`gui_validation.py` all locate an episode's event sheet by searching the
validation folder **recursively**, with a prefix fallback for shortened
filenames. The Qt Code screen built one path — `<validation>/<stem>_events.csv`
— and asked whether it existed. A sheet filed one folder down, or named with a
shortened stem, therefore read as *no sheet* on screen while the command line
scored it, and the screen would have opened a fresh empty sheet over the top of
a real coding pass.
**Why it had not bitten.** This working copy has exactly one event sheet, at
the top level, header-only. The defect needed a second coding session filed
tidily to fire — which is the normal next step, not an exotic case.
**Also found in the same file.** `_open_episode` never cleared `self._events`,
so opening a second, uncoded episode kept the first one's marks in the table
under the second episode's name, and Save Sheet would have written them there.
Hand-placed timestamps are the only measurement in CMAT a person makes
themselves; writing them into the wrong file is the worst available kind of
silent corruption.
**Avoid.** Both were found by needing the answer for something else — a
worklist has to say "is this coded?" per episode, and asking that question
found four implementations of it. `event_coding.find_event_sheet` /
`event_sheet_status` are now the one answer and `trials.py`'s private copy is
deleted. Same shape as `load_scored()`: **when a rule must hold at every call
site, put it IN the call.** And note which half is centralised — *finding* a
sheet is recursive because a person filed it; *writing* a new one stays at the
top of the folder because it needs one predictable home. Asymmetries like that
are exactly what a comment loses and a function keeps.

### A per-row lookup where a one-pass scan already existed
**What.** The hand-coding worklist asked `episode_status` for each episode in
the sample. That function globs the validation folder three times *per
episode*, so a sixteen-row worklist cost **732 ms** — and grows with the
sample.
**Why it is listed here rather than shrugged off.** `validation.py` already
had `coded_episode_map()`, whose docstring says in as many words that it exists
so "provenance markers don't cost a filesystem glob per episode", built for the
Library tree and the Index table. This is shape 4 in miniature: **when one
function in a module already guards against a mistake, that guard is a
specification for its neighbours** — the same reading that caught the blended
F1. The map was one import away and nothing pointed at it from the function
that needed it.
**The fix, and the part worth copying.** `episode_status` and
`event_sheet_status` now take an optional prebuilt map; with one, they read the
paths from it instead of globbing. **The step logic did not move.** Duplicating
the derivation into a new "bulk" function would have been the faster edit and
would have put "what does 'compared' mean" in two places, which is how every
other entry on this page started. 732 ms → 53 ms, and flat in sample size.
**Verified by equality, not by the clock:** every episode in every sample was
run through both paths and the answers compared — 0 mismatches. A faster answer
that is also a different answer is not an optimisation.

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

### `pointSizeF()` is -1 when a stylesheet set the size in px
Deriving a bigger or smaller font by arithmetic on it then silently produces a
tiny one — no error, just unreadable text on a screen a participant is using.
Branch on `pixelSize() > 0` (`study_runner/scale.py`'s `_relative_font`).

### A cancel that derives from `Exception` is not a cancel, it is a bad result
`ARCHITECTURE.md` §7 already recorded this for the analysis worker: the engine
wraps each episode in `except Exception`, so an ordinary exception raised from
a progress callback is caught and recorded as a *failed* episode rather than
stopping the run. The Clip Finder's `PoolWorker` was written with
`class _Cancelled(Exception)` anyway, and `run_candidate_pool` makes it worse
than the original — it caches the failure under the episode's fingerprint, so
every later resumed run reads the cache, believes the episode failed, and never
measures it again. Stopping a measurement would have silently removed episodes
from the pool, permanently, with no error anywhere.

Found while updating §7 to mention the new workers — i.e. by *reading the
document that already said it*, not by a test and not by using the feature.
That is the whole argument for keeping ARCHITECTURE.md current: the rule was
written down, and writing the second worker still reproduced the first worker's
bug because nothing in the new file pointed at it. The docstring on
`_Cancelled` now does, and `tests/test_ui_clip_finder.py` asserts the base
class.

**The general shape:** when a rule exists because of how a *callee* handles
exceptions, every new caller re-learns it. Prefer a named exception the callee
exports over each caller inventing its own.

### A fixture that does not go through the production writer proves nothing
`analyzer/study_clips._write_csv` writes `candidates.csv` as **utf-8-sig**, so
the file begins with a byte-order mark. The new clip-pool reader opened it as
plain `utf-8`, which makes the first header `"﻿clip_id"` — every row loses
its `clip_id`, and the finder's first column renders as an em dash rather than
as anything visibly wrong.

Twenty-five loader tests passed, because the fixture hand-rolled the CSV with
`csv.DictWriter` and plain `utf-8`. The fixture and the loader agreed with each
other and both disagreed with the artefact. It was caught only by running the
real candidate pass over real media and looking at the rendered screen.

Two rules out of it. **Write test fixtures with the production writer**, not
with a parallel one — `_write_run` now calls `_write_csv`. And **the encoding
is part of a file format**: a reader and a writer that disagree about a BOM
fail silently on the first column only, which is exactly the column most likely
to be an identifier nobody reads closely.

### A PyInstaller rebuild deletes the study package it is deployed beside
`COLLECT` clears its output directory before writing. `dist/CMAT Study Runner/`
held the frozen `study/` clips and `participant_data/`, and the documented
build command pointed straight at it — so a *successful* rebuild would have
deleted the participant stimuli and any collected responses, with no error and
no prompt. Found 2026-08-30 only because the running application had a clip
file locked and the build failed. That is luck, not a safeguard.

The shape is general: **build output directories are cleared, so nothing
irreplaceable may live in one.** Staging build + explicit copy of the two build
outputs, in `study_runner/README.md`.

### Closing a window mid-session blocks a test on a modal
`StudyRunnerWindow.closeEvent` asks "end this session?" when the session is
incomplete. In a test that is a modal dialog with nobody to answer it, and the
run hangs with no failure and no output — it looks like a slow test, not a
stuck one. The existing runner tests never hit it because they close from the
finished page. Reach the done page first, or do not close.

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
