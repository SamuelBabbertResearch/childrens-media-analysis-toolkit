# CMAT — TODO

Only what is ready to be done now, in priority order. Finished items are
removed, not ticked. Longer-term work lives in `ROADMAP.md`.

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

  **Found in passing, not fixed — worth its own item:** `coverage_for_stems`
  (and the `sample_coverage` it replaced) key hand-coding coverage by bare
  episode *stem* ("S01 E01"), not by show + stem. Two different shows whose
  video files happen to share a stem — plausible if a researcher names files
  by season/episode number alone — would silently collapse to one entry in
  any coverage count, single-sample or merged. Not introduced by the
  Validation merge above (the same weakness already existed in
  `sample_coverage`), but the merge's wider episode sets make a collision
  more likely to actually occur. Fix would key coverage lookups by
  `db_show_key` + stem, matching how the cache and index already avoid this
  exact class of bug.

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
