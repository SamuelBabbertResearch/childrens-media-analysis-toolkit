# CMAT — TODO

Only what is ready to be done now, in priority order. Finished items are
removed, not ticked. Longer-term work lives in `ROADMAP.md`.

---

## Current phase — the measurement model

**Agreed 2026-08-16.** The pipeline is built and intuitive enough; the work now
is to make the measurement system scientifically serious, flexible and
traceable. The plan of record is [`MEASUREMENT_MODEL.md`](MEASUREMENT_MODEL.md)
— read it, and `CLAUDE.md` §2.5, before writing any of this. Everything under
*Now* below is still real and still true; none of it is a prerequisite for
this, and this does not licence expanding into it.

**Terminology settled 2026-09-04.** The shipped configurable aggregate is the
**Formal-Feature Composite (FFC)**, not a measure of viewer sensory load. Its
legacy `sensory_load` storage keys remain compatibility identifiers only; see
`DECISIONS.md` and `onboarding.md`. The CLI accepts `ffc_score` and `avg_ffc`
as user-facing sort aliases.

**Research-credibility audit completed 2026-09-04.** Statuses, sweep-bias
labelling, preset framing, provenance, missing-data semantics and citations
were corrected; `tests/test_research_claims.py` pins them. No measurement
changed, so nothing is stale. See `onboarding.md` and `DECISIONS.md`. Three
things it surfaced and deliberately did **not** attempt, because each is a
session of its own:

- **The composite's weights still have no derivation.** They cannot be
  validated by coding — that needs a criterion outside the tool
  (`ROADMAP.md`). The audit made the absence explicit everywhere; it did not
  close it, and no amount of documentation can.
- **`ungraded_measurements()` covers the six shipped composite inputs only.**
  The language measures (readability formulas, Zipf tiers, AoA, MTLD) are not
  in the measurement registry, so they get no status and no flag — they are
  applied as published and have not been revalidated on transcribed dialogue,
  which the README now says and the interface does not.
- **`grade_cut_classifier` has no interface at all** — it is reachable only
  through `validate_cuts.py gradecuts`, so the within-scene classifier can be
  graded from a terminal and nowhere else. (Its undefined-kappa crash on the
  CLI print path was fixed; `ui/handcoding.py` already handled `None`
  correctly for the two-coder kappa, which is a different statistic.)

**Ready now, and in this order.** Each is its own session with its own
verification against real output — do not do two at once.

- ~~**A. Answer the six open decisions.**~~ **Done 2026-08-16.** All six
  answered by the author; `MEASUREMENT_MODEL.md` §7 now states the answers and
  `DECISIONS.md` carries the reasoning and the rejections. The consequential
  one: **a recipe pins its parameters**.
- ~~**B. The data model**~~ — **Done 2026-08-16** for constructs, measures and
  methods, in `analyzer/constructs.py` with `tests/test_constructs.py` (29
  tests). **Recipes and versions are NOT part of what shipped** — they are C
  and the version-tracking item below. Verified as the item asked: every
  shipped measure resolved against a real cached episode and a real coding
  sheet in this working copy, printed beside the existing engine and
  `manual_pacing_metrics()` numbers, all matching. Two things came out of it
  that are now on record rather than in anyone's head:
  - **A real data defect** — three of five transition-coding sheets have no
    recorded coded window, and dividing one by the full runtime gave 0.084
    cuts/min against a detected 17.785. The model now refuses. `LEARNINGS.md`
    § *A coded segment divided by the whole runtime*, and `FOR_PAPER.txt`.
  - **Only two constructs ship** (pacing, speech), per `MEASUREMENT_MODEL.md`
    §4.3's instruction not to generalize past two. Saturation, contrast,
    motion, flashing and audio are measured by the engine and **not yet
    expressed in the model**; they arrive with the shipped composite recipe.
    **Superseded by item D**, which brought all five in — seven constructs and
    sixteen measures now.
- ~~**C. Recipe save / load**~~ — **Done 2026-08-16**, in
  `analyzer/recipes.py` with `tests/test_recipes.py` (34 tests). Create, save,
  load, list, duplicate, delete, export, import, **evaluate**, and version.
  Verified as §4.2 asks — by reading the written JSON, and by saving a recipe
  in one library, moving it, and reopening it in another, where it produced
  identical scores for three real episodes. Decision 4's accepted cost is
  discharged: `divergences()` reports where a recipe's pins differ from the
  live Measurement settings, and `evaluate()` **refuses** a part whose pinned
  parameters do not match the parameters that produced the cached number.
  It also closed **§4.4 in part** (recipe versioning: content-addressed, a
  reason is required, renaming is not a new version) and **§4.7 in part**
  (recipes export/import; an unresolvable method becomes a named gap, never a
  substitution). One real defect was found by the verification —
  `LEARNINGS.md` § *Attribution read off a rescored copy*.
- ~~**D. The shipped composite as a locked recipe**~~ — **Done 2026-08-16**,
  `recipes.shipped_composite(config)` with `tests/test_shipped_composite.py`
  (28 tests). Built from `config.json`'s weights and ranges, never restated.
  **Verified as this item asked**: it reproduces
  `metrics_sensory.compute_sensory_load` exactly on all 14 cached episodes in
  this working copy, and reproduces `effective_weights()` on the silent-episode
  path none of them exercises. Locked; duplicating is the route to
  alternatives. It derives nothing, and its notes and its construct's grounding
  both say so.

  It brought the other five inputs in, so the model now holds seven constructs
  and sixteen measures. It also needed one new capability worth knowing about:
  **a measure can gate on an availability flag** (`available_path`), so
  `audio.rms_mean` counts only when `audio.available` is true and the speech
  measures only when `speech.available` is. That fixed a live wrong answer —
  `words_per_minute` had been resolving 0.0 for episodes with no speech block
  at all, of which there are four here.
- ~~**E. The recipe editor**~~ — **Done 2026-08-16**, `ui/recipes.py` with
  `tests/test_ui_recipes.py` (19 tests), reached from **File → Recipes…**.
  Lists recipes (the shipped composite first, generated rather than stored),
  shows each down to the pinned parameter, reports divergences, edits
  method / transform / range / weight / missing-data policy / notes, records a
  version with its reason, applies a recipe to the current scope on a worker
  thread, and duplicates / deletes / exports / imports.

  **Audited by output, as this item asked** — driven headlessly against a
  mirror of the real 137-episode library, reading the generated HTML and every
  control's enabled state. That found three defects, all invisible from the
  interface:
  - **The dirty check ran one edit behind**, so Save was available for a
    changed recipe with no reason given — the version rule the screen exists
    to enforce could be walked straight past. `LEARNINGS.md`.
  - **A recipe with every weight still at zero scored 0.0**, which reads as a
    measured composite rather than an unset one. `evaluate` now refuses.
  - **124 unanalysed episodes produced 744 identical refusal rows**, burying
    the one refusal that differed. The table groups by measure and reason now.

  Left deliberately: the **Tk build has no equivalent** and is not getting one
  (`gui.py` is being retired, item 9 below). Note that when it is audited.
- ~~**F. The construct diagram**~~ — **Done 2026-08-16**, the **Constructs
  tab** (`ui/constructs_tab.py`) beside Pipeline, with
  `tests/test_ui_constructs_tab.py` (21 tests). Three columns: target
  construct, contributing constructs as their own blocks, measures. Read-only: it draws a recipe as
  a graph and writes nothing. Wire thickness is the **contribution share**, so
  `ARCHITECTURE.md` §8.1a is finally visible — on this library colour contrast
  declares 0.10 and contributes 21% while motion declares 0.25 and contributes
  18%. No arrowheads, refusals keep their boxes, and the diagram exports as a
  PNG for a methods figure. Two defects found by driving it, both in
  `LEARNINGS.md`: one recipe's computed numbers drawn under another recipe's
  name, and a long-standing worker-reference guard that turned out to be wrong
  in both directions.

  **Verified with real fonts by nobody.** This environment's offscreen Qt
  platform has zero font families, so every drawn screen renders tofu. Layout
  and content are checked by reading the scene; appearance is not. Look at it
  in the real application before trusting the visual density.

- ~~**G. Authoring on the construct canvas**~~ — **Done 2026-08-16**, both
  halves. The canvas drew; it builds now. The thing originally asked for —
  **assemble a custom composite by combining constructs** — works end to end: a
  construct of your own, a recipe over it, shipped measures bound to it from a
  palette, versioned with a reason, and drawn where you put it.

  **G1 — the data model. DONE 2026-08-16**, in `analyzer/constructs.py` and
  `analyzer/recipes.py`, with `tests/test_construct_store.py` (33 tests).
  `MEASUREMENT_MODEL.md` §4.1's "researchers add their own" now exists: a
  construct is created, saved to `<root>/.analysis/constructs/`, renamed,
  redefined and deleted, and comes back from the **ordinary `get_construct`
  lookup** — the merge is inside that one call, so no call site needed editing
  (`CLAUDE.md` §6). A recipe records the construct hash it was authored
  against and `construct_divergence()` reports current / redefined / missing /
  unknown.

  **Verified by reading the written files**, as this item asked: the construct
  JSON, and the recipe JSON's `construct_hash` matching it. Redefining moves
  the divergence to `redefined` while the recipe's own `content_hash` does not
  move and `bump_version` still refuses — confirmed by **reintroducing the
  defect** (folding the construct hash into `canonical()`) and watching
  `::test_the_construct_hash_is_not_part_of_the_recipes_canonical_form` fail.
  Driven through a real `MainWindow.set_root` against the real `Shows` library,
  which has **no saved recipes and no constructs folder**, so nothing existing
  is disturbed — and equally, the "old recipes report unknown" grandfathering
  path has **no real instance here** and has only been exercised synthetically.
  One real defect found on the way: `new_recipe` accepted a method key that
  does not exist (`LEARNINGS.md`).

  **G2 — canvas authoring. DONE 2026-08-16.** `ui/construct_editor.py` (new,
  with `tests/test_ui_construct_editor.py`, 12 tests) and an **Edit** mode on
  the Constructs tab (`tests/test_ui_constructs_tab.py`, now 35). A researcher
  can define a construct, create a recipe over it, bind shipped measures to it
  from a palette, set each one's method and weight, save with a reason, and
  arrange the diagram — the arrangement persisting in the sidecar decision 3
  called for. The Recipes New menu no longer disables a measureless construct;
  it creates the recipe empty and says where the bindings come from, which is
  the route this item always described.

  **Verified by reading the written files**, as this item asked: the construct
  JSON, the recipe JSON after a canvas save (v2, both weights on the right
  measures, the reason in the history), and the `<recipe id>.view.json`
  sidecar — checking the recipe's own `content_hash` and version did *not*
  move when a box did. Driven against the real `Shows` library too, which
  still has no recipes and no constructs folder and gained neither by being
  opened.

  **Five defects found on the way, all in `LEARNINGS.md`.** The one worth
  naming here: **every edit refilled the bound-measures list, and
  `QListWidget.clear()` drops the current row to −1**, so the selection snapped
  back to the first binding and two weights entered for two measures were both
  written onto the first. The panel looked right throughout; only the recipe
  file said otherwise.

  **What G2 does NOT give you.** Transforms, reference ranges, pinned
  parameters, missing-data policy and notes are still edited only on
  **File → Recipes…** — the canvas edits what is bound and how much it counts,
  and points at that screen for the rest. Deliberate: `ui/recipes.py` shows a
  recipe down to the parameter and duplicating that here would be two editors
  of one object. Aspects can be written but nothing yet binds a measure to a
  specific aspect from this screen.

  **THREE RULES WERE ALREADY SETTLED** and survived into what was built
  (`DECISIONS.md`):
  1. The canvas stays **typed** — a method attaches to a measure, a measure to
     a construct, only a composite takes weighted inputs. Free-form
     box-to-box wiring is the generic node editor `MEASUREMENT_MODEL.md` §6
     forbids, and typing is the whole difference.
  2. **Constructs and aspects may be free-form; measures may not.** A measure
     must be chosen from a palette of things that actually resolve to a number.
     A user-defined measure with no data path is `LEARNINGS.md` shape 2 — the
     defect this entire phase exists to remove — reintroduced through a nicer
     interface.
  3. Writes go through `recipes.save_recipe`, and a changed operationalization
     still needs a **reason** before it can be saved. The shipped composite
     stays locked.

  **THE FOUR OPEN DECISIONS ARE ANSWERED** — 2026-08-16, by the author, before
  any code, as `MEASUREMENT_MODEL.md` §7's precedent demanded. Reasoning and
  what was rejected are in `DECISIONS.md` § *Authoring on the canvas: the four
  shaping decisions, answered*. In brief:
  1. **User-defined constructs live with the library**, in
     `<root>/.analysis/constructs/`, beside the recipes that cite them,
     following `pipeline_graph.py`'s conventions including re-homing.
     Portability stays §4.7's job: the export already embeds each construct's
     definition alongside its key, and an unresolvable one is a named
     `ImportGap`, never a substitution.
  2. **A construct is content-hashed** over its definition, grounding and
     aspects — not its name, so renaming is free. A recipe records the
     construct hash it was authored against, **beside** its own content hash
     and **not inside `Recipe.canonical()`**: editing a construct must not
     silently bump a citing recipe's version without the reason `bump_version`
     requires. A redefinition is reported as a **divergence**, the same shape
     pinned parameters already use — and a divergence is not an error.
  3. **Node positions persist in a sidecar**, `<recipe id>.view.json` beside
     the recipe, deleted with it, never in `content_hash()`. A missing sidecar
     means auto-layout. Decisive argument: `save_recipe` refuses the locked
     composite, so a layout stored inside the recipe file could never be saved
     for the one diagram most likely to become a methods figure.
  4. **A composite may NOT contain another composite.** One level; construct
     blocks stay derived. Combining constructs already works flat — the shipped
     composite binds six measures across five constructs — so nesting would buy
     recursive contribution share and graph staleness for no gain. Reversible
     later; shipping saved nested recipes would not be.

  All four held. Two further interface-shape questions were put to the author
  and answered on 2026-08-16 — construct creation lives in **one shared editor
  reached from both the Constructs tab and the Recipes New menu**, and the
  canvas **edits in place behind an Edit toggle** rather than in a separate
  authoring screen. Neither changes what is stored. `DECISIONS.md`.

  **SEEN WITH FONTS, and it paid immediately — four findings in the first
  hour, none of which a test could have produced.** A label reading as a
  contradiction against the canvas behind it ("8 measures of its own" beside
  "1 measure"); the Edit panel drawn off the right-hand edge of the window,
  because it had a maximum width its own contents could not fit in; a default
  transform that would have summed a rate against a fraction and called it a
  composite; and no way to create a construct or a recipe from the screen for
  authoring them. All four fixed — `LEARNINGS.md` has the first three.

  **Keep looking at it.** What is still unjudged: the density of the canvas
  itself, whether the splitter's default division is right on a smaller
  monitor, and how any of it prints. The question "do the palette and the
  canvas fit side by side" is now answered — they did not, and the fix was a
  splitter — but only at one window size on one screen.

- **H. Stale detection (§4.5)** — next after those. The decision is settled (a flag per
  episode result per recipe version) and `cache.is_stale` is the one edge that
  already works, including its grandfathering rule. The recipe half is now
  possible because a recipe has a content hash to depend on.
- Then method comparison (§4.6), reproducibility reports, methods text,
  citation. `MEASUREMENT_MODEL.md` §4 has what each one
  means here and how each is verified.

**Found while building B, not fixed, and not a blocker.** The SpongeBob
transitions sheet is filed as `SpongeBob S01E01A Help Wanted_manual.csv` while
the video stem is `SpongeBob SquarePants S01E01A Help Wanted`, so
`coding_for_stem`'s prefix match (which requires the stem to *start with* the
sheet's base name) does not find it and the episode reads as uncoded. That
lookup is shared by five readers and is deliberate as written; renaming the
sheet is the cheap fix, changing the matcher is not. Decide which.

**Two traps this phase walks straight into**, both already on this project's
record: a second list of detectors written beside the registry
(`LEARNINGS.md` shape 3), and a control whose data path is empty — a construct
that names a measure that resolves to nothing (shape 2).

---

## Now

**Delete `_duplicates_quarantined_2026-08-15/` when you are satisfied.** The
66 duplicate files moved there on 2026-08-15 (a whole-series `Little Bear`
copy and a misfiled `SpongeBob` episode) are reversible by moving them back;
nothing in the tool reads the folder. That part is yours.

2. **Freeze the codebook.** Still DRAFT after three mid-study additions. The
   2026-07-04 log entry already said to freeze it before the second episode.

3. **Two data decisions the audit surfaced.** The output-audit passes on
   2026-08-14 found nineteen defects across four rounds, all fixed; see
   `LEARNINGS.md` and `FOR_PAPER.txt`. Every path listed for auditing has now
   been run and its artefact inspected. What is left is not defects but
   choices:

   - **There are TWO caches in this working copy.** `<project>/.analysis` has
     82 cached episodes (from when the root was the project folder);
     `<project>/Shows/.analysis` has 28 (the live library).
     `patch_speech_cache.py` was reading the first one.

     **DO NOT DELETE `<project>/.analysis` — corrected 2026-08-14.** Earlier
     wording here said to archive or delete it as "stale". It is not stale to
     everything: **`build_site.py` reads it as its data source**, and **7 of
     the 15 published shows exist ONLY there** — Peep and the Big Wide World,
     The Berenstain Bears, Mr Beast, iShowSpeed, Bob Ross, Game Theory and
     Evangelion, which include every baseline comparison on the public site.
     Deleting it would silently empty those pages.

     The real task is therefore not "delete the stale copy" but **decide which
     cache is the site's corpus**, and make `build_site.py` say so explicitly
     rather than defaulting to the project root. Until then, leave both.
   - **`Episode.label()` concatenates without a separator** —
     `S01E02Birthday Soup`. It is the manual-selection lookup key *and* the
     episode list recorded in every written manifest, so changing it needs a
     migration decision, not just an edit.
   - `Episode.runtime` is read by nothing. Remove it if duration-weighted
     sampling is never planned.

   The audit method itself is worth keeping: **run the thing and read what it
   produced.** Every one of the nineteen was invisible from the interface —
   the control was present, the button worked, and the record described the
   design that was asked for rather than the one that ran.

4. **One Qt decision, not a port.** **Watch Analysis (Live)** (`gui_live.py`).
   The Qt Automated coding tab already shows a progress bar, the current
   episode, and a per-episode results table as the run proceeds. Decide
   whether a separate live window still earns its place before porting it.

   Smaller and also a decision: Settings has **Save as Preset** but not *Save
   as Default*. (The hand-coding worklist that used to be listed here is
   **done** — 2026-08-16, see *The research context, continued*.)

5. **Decide about `master`.** The branch is pushed (done 2026-08-11), so the
   work is backed up. But `feature/language-analysis` is far ahead of
   `master`, whose last commit is 2026-06-30 — and `master` is what GitHub
   shows visitors. Merging forward is a clean fast-forward.

   `README.md` **now needs a change on this point.** It describes the Tk build
   because the Tk build *was* the software; as of 2026-08-14 every screen
   exists in Qt, so the sentence naming `gui.py` as the product is no longer
   true. Decide which build the README describes before merging.

6. **Try the Qt build as the daily driver, then retire `gui.py`.**
   Every Tk screen now has a Qt equivalent, but "exists" is not "proven": the
   Qt Language, Validate tool, Agreement and Sampler screens have each been
   driven once, headless. Use them for real work before deleting anything —
   see item 10.

7. **Decide the startup wizard's default action.**
   The wizard opens on every launch with *Create Pipeline* as the default
   button, so dismissing it with Enter creates a pipeline — this project
   accumulated several that way. Options: make Skip the default when pipelines
   already exist; only show the wizard when there are none; or leave it.
   Needs a product call before code.

## The research context, continued

The scope exists and the Library obeys it (2026-08-15, `DECISIONS.md`). These
are the rest of it, in the order they pay off. **Do not do them all in one
session** — each needs its own verification against real output.

- ~~Scope the Index tab.~~ **Done 2026-08-15.** It filters to the context and
  its Shows view is now derived from the episode rows on screen. Doing it
  surfaced two things that are NOT done:
  - **`cli.py db --shows` and `gui.py` still read the stored `shows` table**,
    which goes stale (see `LEARNINGS.md`). Either make them derive too, or
    make `upsert_show` refresh on every episode upsert. Until then those two
    surfaces can print show means that describe an older, smaller set.
  - **One index row has a raw relative path as its show name** —
    `Spongebob Squarepants Season 1/Season 1`, from the `.mkv` indexed through
    the sampler's path, which does not apply `show_index`'s naming. It shows
    as its own show in any grouping. Re-index it, and check whether the
    sampler's analysis path should be routed through `db_show_key` /
    `display_show_name` so it cannot recur.
- ~~Scope Automated coding.~~ **Done 2026-08-16.** A sample scope stages its
  episodes into the analysis queue and the queue says where they came from and
  how many already have a cached result. Verified against the real library:
  a pipeline node now lands on a filled queue instead of "No episode or show
  selected". `DECISIONS.md` has why it stages rather than filters. It surfaced
  one thing that is **not** done:
  - **An unlinked pipeline inherits the previous pipeline's scope.**
    `_follow_pipeline_scope` deliberately leaves the scope alone when
    `source_key` is empty — "no opinion about which episodes", not "no
    episodes". Six of the eleven pipeline documents here are unlinked, so
    selecting one leaves another study's sample current, and that sample now
    arrives pre-staged in the run queue. It is visible (the Showing: control
    and the queue note both name it) and nothing is mis-attributed, but decide
    whether an unlinked pipeline should reset to the whole library instead.
- ~~Scope Human coding.~~ **Done 2026-08-16.** Code and Validate tool both show
  the sample as a worklist with each episode's coding state, read from the
  engine. This also closes item 5's "the Qt Human coding tab has no worklist".
  Two real defects were found on the way and fixed — one sheet lookup instead
  of two, and opening a second episode no longer carries the first one's marks
  (`LEARNINGS.md`).
- ~~Scope Language.~~ **Done 2026-08-16.** Both, as suspected — and the tab is
  now the worked example of the rule in `DECISIONS.md` § *A view narrows to the
  scope; a workbench stages from it*. **Speech** filters, and its count names
  the set. **Vocabulary** stages the caption files beside the sample's
  episodes and says how many of them have none. Speech stays lazy: it is
  filled by Refresh, never from `set_root`, because it opens every cached
  result under the root.

  Worth correcting for the record: Language never took `set_target(path)` at
  all. It read the whole library and nothing narrowed it, which is why the
  wrong number here was a table of the corpus rather than an empty screen.
- ~~Show the scope outside the Library.~~ **Done 2026-08-15** — the chooser is
  on the main toolbar beside Root folder and Preset, so it is visible from
  every tab. The Library keeps the sentence explaining the current context.
- ~~A scope change costs ~2.0 s, and 1.5 s of it is `build_pipelines()`.~~
  **Done 2026-08-15.** `_sync_scope_choices` split into `_rebuild_scope_choices`
  (calls `build_pipelines`; only from `set_root` and as a fallback) and
  `_select_scope_in_chooser` (moves the combo box using the already-built list,
  no disk I/O). `set_scope` now calls the cheap one. The scope-set-before-its
  -draw-is-discoverable case still works: when the requested scope isn't in
  `_scope_choices` yet, `_select_scope_in_chooser` falls back to one full
  rebuild, so the chooser still cannot disagree with the tree. See
  `onboarding.md` and the regression test
  `tests/test_scope.py::test_picking_a_known_scope_does_not_rebuild_the_chooser`.

- ~~Wires carry the set.~~ **Done (2026-08-15) — small slice, large slice, and
  the Validation merge.** Sampling emits N, selection narrows it, a hand-code
  branch takes its subset — the north-star spec's "output produced here
  becomes input there."

  **Small slice (done):** a Selection node can now genuinely narrow a sample.
  Selecting one and pressing **Exclude Library Selection** in the Inspector
  (`ui/inspector.py`, `MainWindow._exclude_from_selection_node`) writes the
  linked sample's episodes minus the Library's current row selection as a
  brand-new `selected.csv` + `manifest.json` pair — the same shape an Episode
  Sampler draw writes (`analyzer/selection.py`). Deliberate choice over a
  canvas-only exclude list in `node.config`: `CLAUDE.md` already says
  Selection belongs in a manifest, and every scope in this app
  (`discover_trials`, `build_pipelines`, the Showing: chooser) discovers
  samples by finding exactly that pair — so the narrowed sample needed **no
  new discovery code**. See `DECISIONS.md`.

  **Large slice (done for plumbing):** sample binding moved off the whole
  document and onto individual Sampling nodes
  (`node.config["sample_key"]`, `PipelineDoc.upstream_sample_keys`). A canvas
  can now hold two Sampling nodes, each linked to a different sample, each
  feeding its own branch — every node's derived status (Inspector rows,
  canvas subtitle, `_exclude_from_selection_node`) and the scope a
  double-click stages (`_follow_node_scope`) resolve by walking that node's
  wires backward to the nearest bound Sampling node, not by reading the
  whole document's one `source_key`. A Sampling node with no binding of its
  own still falls back to `doc.source_key`, so every pipeline saved before
  this existed keeps resolving exactly as it always did — see `DECISIONS.md`
  for why the fallback was kept rather than requiring migration.

  Verified against the artefact and end to end, not just unit-tested:
  `tests/test_pipeline_graph.py` covers the traversal itself (fallback,
  override, converging paths collapsing to one key, two Sampling nodes
  reporting both); `tests/test_scope.py
  ::test_two_sampling_nodes_each_drive_their_own_branchs_status_and_scope`
  builds a real two-branch canvas through `MainWindow` and asserts each
  branch's Inspector status names its own episode count and double-clicking
  each branch stages that branch's own episodes, not the other one's.

  **The merge (done, generalized beyond Validation the same day):** a node
  fed by more than one Sampling node no longer silently reports only the
  first branch — for ANY node type, not just Validation.
  `analyzer.pipeline.merged_pipeline` unions every resolvable branch's
  episodes (de-duplicated by path), unions their trial records
  (de-duplicated by manifest file), and recomputes analysis/hand-coding
  coverage over the union, then runs the ordinary single-sample stage logic
  over that — so Selection, Automated coding, Language and Validation all
  get a correct union, not five special cases.

  Started scoped to Validation only, on the theory that Validation was the
  one node type actually built to compare two things. Widened to every
  stage type the same session after a real report: wiring two Sampling
  nodes into one *Selection* node showed only one of the two shows —
  Selection has no "compare" semantics at all, it just needed the union,
  and so does every other stage type. What still stays refused for every
  stage type — comparing sample A's automated results against sample B's
  hand coding as if they measured the same episodes — is explained in
  `DECISIONS.md`.

  The exclude action on a Selection node fed by more than one branch has the
  matching fix: `analyzer.selection.write_narrowed_selection_from_sources`
  narrows the union of all branches' episodes (de-duplicating a shared
  episode first), not just the first branch's sample.

  Verified with real coverage/episode-count math (the union has more than
  either branch alone) and end to end through `MainWindow`, in
  `tests/test_pipeline.py`, `tests/test_selection.py`, and
  `tests/test_scope.py
  ::test_two_sampling_nodes_wired_into_one_selection_node_show_both_shows`
  (the reported bug, reproduced directly) and
  `::test_validation_fed_by_two_sampling_nodes_merges_instead_of_picking_one`.

  **A second, real bug turned up when the merge still failed after the
  above shipped:** the merge logic was correct, but `_link_to_sample` — one
  method reachable from both `Manage → Link to Episode Sample…` and the
  Inspector's per-node button — inferred which one it was doing from
  whatever happened to be selected on the canvas at click-time, instead of
  from which control was actually pressed. Linking two Sampling nodes and
  then reaching for the familiar menu item while a node was still selected
  from browsing silently overwrote the document's default instead of doing
  nothing, and left both nodes falling back to the same single key — one
  show, not two, exactly the report. Split into
  `_link_to_sample`/`_link_node_to_sample`, two methods and two `Inspector`
  signals, so which one runs is decided by construction, not inference.
  Regression test drives the exact click sequence:
  `tests/test_scope.py
  ::test_the_menu_link_never_touches_a_selected_nodes_own_key`. See
  `LEARNINGS.md` for why this shape of bug — inferring intent from
  incidental state — cannot be caught by a test that sets state directly.

  **A third bug, a different action entirely:** *linking* to an existing
  sample worked once fixed above, but *drawing a brand-new one* from a
  Sampling node never told that node about it at all. Double-clicking a
  Sampling node opened the Episode Sampler through a dispatch table that
  called `open_sampler()` with no arguments, so the method had no way to
  know which node (if any) it was opened from — a successful draw only ever
  updated the session's ephemeral scope, never `node.config["sample_key"]`,
  and never called `save_doc`. Both reported symptoms were this one cause:
  drawing from either node looked like it changed "the overall list" because
  neither node's own binding ever moved, and nothing persisted because
  nothing was ever written to persist. Fixed: `open_sampler(self,
  node=None)` now writes and saves the node's own binding when opened from a
  specific Sampling node, and keeps the old scope-only behavior for the File
  menu / toolbar button (no node context). Verified with two tests —
  `tests/test_scope.py
  ::test_drawing_from_a_sampling_node_binds_and_persists_to_that_node`
  (draws for two different nodes, checks neither clobbers the other, then
  reloads the document from disk the way reopening the pipeline would) and
  `::test_drawing_without_a_node_context_does_not_bind_any_node` (the old
  path is unchanged). See `LEARNINGS.md`.

  **A fourth and fifth, from testing the real build:** (a) *the Library
  showed one branch at a time* — `_stage_for` merged across branches but
  `_follow_node_scope`, which decides what the Library displays, still built
  its scope from `keys[0]` alone, so the panel said two samples and the tree
  showed one. Fixed with `analyzer.scope.scope_from_draws` (union across
  draw folders, `folder=None` since a union is no single draw's folder).
  (b) *nothing persisted across reopen* — `save_doc` pinned `doc.path` on
  first write, so a document first saved before a library root was known
  (the wizard on a first run) kept writing to the app-folder fallback while
  `list_docs(root)` only ever reads the library's own folder: saved fine,
  reloaded as nothing. `save_doc` now re-homes into the target folder and
  moves the old file. Both in `LEARNINGS.md`; tests in `tests/test_scope.py`
  (`::test_opening_a_merged_node_puts_both_shows_in_the_library`) and
  `tests/test_pipeline_graph.py`
  (`::test_a_doc_saved_before_a_root_is_known_rehomes_into_the_library`).

  **The actual root cause of the "one sample at a time" report, found by the
  user:** the Showing: chooser was built from `build_pipelines`, which
  returns one entry per *drawn sample* — so a pipeline combining two samples
  had no entry in it at all, and the ordinary control for changing the
  Library's working set could not express the study that had been built.
  Every earlier fix was real and none could reach the symptom. The chooser
  now offers pipelines as well as samples (`MainWindow._doc_scope`); see
  `DECISIONS.md`, and `LEARNINGS.md` on why three green fixes in a row left
  the report standing. Test:
  `tests/test_scope.py
  ::test_the_chooser_offers_the_whole_pipeline_not_only_its_samples`.

  **Selecting a pipeline defaults to the combination it was built from** —
  a document with two Sampling blocks scopes to both together rather than to
  one arbitrary half (`_follow_pipeline_scope`, sharing
  `_doc_sample_pipelines` with the chooser so both answer "which samples
  does this draw on" identically). Startup still opens on the whole library,
  which is a separate settled decision. See `DECISIONS.md`; tests in
  `tests/test_scope.py::test_selecting_a_two_sample_pipeline_defaults_to_both_together`
  and the one- and zero-sample cases beside it.

  **Each node now names its media** on the canvas box and in the Inspector
  (`MainWindow._node_media`, `NodeItem.media_line`) — two Sampling boxes
  were otherwise identical, which per-node binding made a real hazard. See
  `DECISIONS.md`.

  **Fixed:** hand-coding coverage now keys episode identity by `db_show_key`
  plus stem. If two shows both contain "S01 E01", each sheet must live below
  that show's validation subfolder; one ambiguous legacy top-level sheet is
  not silently credited to both. Unique stems retain the legacy recursive and
  shortened-filename lookup. Regression tests cover both the ambiguous
  one-sheet case and two correctly namespaced sheets.

## Clip Finder — what the first slice does not do

Built 2026-08-30. A Selection node now opens a Clip Finder
(`ui/clip_finder.py`, `analyzer/clip_query.py`): measure every contiguous
window of a folder of episodes on a worker thread, then filter the pool by
cuts per minute, motion, audio, relative level and episode, and export the
chosen windows as standalone files. Verified end to end against the twelve
real study clips — 43 windows measured, filtered to 5, read back off disk.
`DECISIONS.md` carries the three decisions; do not add a ranking.

Not done, roughly in order of how much each is missed:

- **No preview.** A researcher cannot watch a window before choosing it, which
  is the single most obvious omission — `ui/player.py` already plays a range.
- **No recipe pin.** `run_candidate_pool` accepts an `analysis_recipe` that
  pins the measurement parameters, and the screen does not offer one, so every
  pool is measured with the live Measurement settings. The manifest records the
  fingerprint either way, but a recipe is the inspectable form (`CLAUDE.md`
  §2.5) and the screen should offer it.
- **The matched-pair half is untouched.** `study_clips` proposes Option 3.5
  contrasts and the finder ignores them entirely; pairing is still CLI-only.
- **No marked set across filters.** Selection is the table's own, so changing
  a filter loses what was chosen. Collecting windows across several different
  queries is the obvious next want.
- **Progress is indeterminate.** The pass reports the episode it is on but the
  bar cannot show how far through it is.
- **The source folder is guessed from the node's sample.** If a sample spans
  several folders the finder offers their common ancestor, which may be far too
  wide. It is visible and editable, but it is a guess.

## Study Runner — the participant rating scale

Built 2026-08-29: the vertical radio column is gone and the rating screen is a
horizontal labelled 1-5 ramp with turtle and rabbit end anchors
(`study_runner/scale.py`, 15 tests). The design, the evidence and what was
rejected are in `STUDY_RATING_SCALE_DESIGN.md`; the decision is in
`DECISIONS.md`. **Read that document before changing the scale** — its
properties are findings, not styling, and the tests assert them.

**Protocol changed 2026-08-31.** The active study is adult-only and collects
one adult self-perception rating per clip. The current runner and pilot package
still implement adult prediction and a child flow, so they must not be used for
piloting or collection. Follow `STUDY_PROCEDURE_ADULT_ONLY.md`.

What the scale still needs, in order:

- **Replace the participant flow.** Remove the prediction question, target-age
  wording, child blocks, and assent screens. Collect exactly one `adult_self`
  response after each of 12 clips and update the schema and tests.
- **The adult practice item and comprehension check.** Use the same widget as
  the study trials and freeze approved wording before the adult pilot.
- **Decide whether turtle/rabbit imagery remains for adults.** Preserve the
  five verbal anchors either way and record the pilot/faculty decision.
- **Response latency.** Nothing records it yet. Worth logging, but only if
  the screen stays unpressured — no countdown, no auto-advance.
- **Move the deployment out of `dist/`.** Found 2026-08-30: the deployed
  runner lives in `dist/CMAT Study Runner/` with the frozen `study/` clips and
  `participant_data/` inside it, and PyInstaller clears that directory on every
  build — a successful rebuild would delete the stimuli and any collected
  responses. Documented and worked around today (staging build plus an explicit
  copy, `study_runner/README.md`), but the real fix is that a deployment must
  not sit in a build output directory at all. Do this before piloting.
- **Check it on the study computer.** The steps are painted rather than
  styled specifically so a high-contrast Windows theme cannot change them;
  that reasoning has not been exercised on the real machine at its real DPI.

## Ready when the above are done

9. **Retire Tk modules that have reached parity.**
   Fifteen `gui*.py` files are still on disk and both builds read the same
   project, so there is a real risk of editing the wrong one. Delete only
   after item 7 — the Qt equivalents of `gui_sampler.py`, `gui_validation.py`
   and `gui_handcoding.py` exist as of 2026-08-14 but have not yet been used
   for real work. Not reversible in a hurry; do it deliberately.

10. **Fold the positioning documents into `ROADMAP.md`, then delete them.**
   **Done (2026-08-15).** `design/CMAT_GITHUB_PIPELINE_POSITIONING.md` and
   `design/POSITIONING_BRIEF.md` overlapped each other and `ROADMAP.md`;
   both are now the *Public positioning* section of `ROADMAP.md` and are
   deleted. Bears on item 6 — what `README.md` should say when it's next
   revised.

   The rest of item 10 was already done (2026-08-14): the seven root files
   were sorted into `design/` and `ui/reference/`, and `preview_ui.py` was
   deleted as dead scratch. `docs/` was deliberately **not** used — it is
   gitignored, so moving anything there silently untracks it. See
   `design/README.md`.

11. **Re-check the UX audit against the Qt build.**
   `design/CMAT_FIRST_TIME_UX_AUDIT.md` traced the *Tk* build (`gui.py`,
   `gui_sampler.py`, `gui_pipeline.py`), which item 9 retires. Its findings
   may be fixed, may have moved, or may never have applied to Qt. Do this
   alongside item 7 rather than acting on the audit as written.
