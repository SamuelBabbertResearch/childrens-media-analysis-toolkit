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
- **A scope change costs ~2.0 s, and 1.5 s of it is `build_pipelines()`.**
  Measured 2026-08-16 on this working copy. `_sync_scope_choices` rebuilds the
  chooser from `build_pipelines(root)` on **every** `set_scope`, and that call
  alone is 1524 ms — up from the 420 ms in `onboarding.md`'s table. The rest is
  small and flat in sample size (Library + Index + Trials 353 ms, the queue
  92 ms, both worklists 293 ms, both Language views 261 ms), so this is one
  pre-existing hotspot on a control that now matters more, not a cost the
  measurement tabs added.

  The list of discovered samples **cannot change as a result of choosing one**,
  so the fix is to split discovery from selection: rebuild the chooser when the
  root changes or a sample is drawn, and otherwise only move the current index.
  Do it deliberately — `_sync_scope_choices` also handles the case of a scope
  set before its draw is discoverable, and getting that wrong makes the chooser
  disagree with the tree, which its own comments call the one thing this
  control must never do. Worth a test that drives a fresh draw.

- **Then, and only then, consider making the wires carry the set.** Sampling
  emits N, selection narrows it, a hand-code branch takes its subset. This is
  the north-star spec's "output produced here becomes input there", and it is
  the point at which drawing the graph starts to matter. Currently
  `doc.connections` is only ever counted, and `node.config` is written by the
  templates and read by nothing.

## Ready when the above are done

9. **Retire Tk modules that have reached parity.**
   Fifteen `gui*.py` files are still on disk and both builds read the same
   project, so there is a real risk of editing the wrong one. Delete only
   after item 7 — the Qt equivalents of `gui_sampler.py`, `gui_validation.py`
   and `gui_handcoding.py` exist as of 2026-08-14 but have not yet been used
   for real work. Not reversible in a hurry; do it deliberately.

10. **Fold the two positioning documents into `ROADMAP.md`, then delete them.**
   `design/CMAT_GITHUB_PIPELINE_POSITIONING.md` and
   `design/POSITIONING_BRIEF.md` overlap each other and overlap `ROADMAP.md`,
   which `INDEX.md` already names as the home for "positioning, priorities, and
   what is deliberately not being built". Three files answering one question is
   how they drift apart. Bears on item 6 — what `README.md` should say.

   The rest of item 10 is **done** (2026-08-14): the seven root files were
   sorted into `design/` and `ui/reference/`, and `preview_ui.py` was deleted
   as dead scratch. `docs/` was deliberately **not** used — it is gitignored,
   so moving anything there silently untracks it. See `design/README.md`.

11. **Re-check the UX audit against the Qt build.**
   `design/CMAT_FIRST_TIME_UX_AUDIT.md` traced the *Tk* build (`gui.py`,
   `gui_sampler.py`, `gui_pipeline.py`), which item 9 retires. Its findings
   may be fixed, may have moved, or may never have applied to Qt. Do this
   alongside item 7 rather than acting on the audit as written.
