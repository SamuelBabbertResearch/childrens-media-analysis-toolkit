# CMAT — TODO

Only what is ready to be done now, in priority order. Finished items are
removed, not ticked. Longer-term work lives in `ROADMAP.md`.

---

## Now

1. **Rename the headline F1 constants — they are not hard-cut figures.**
   The 2026-08-14 recomputation settled which number is current (see
   `DECISIONS.md`): **0.75–0.91, aggregate 0.85**, two episodes on the shipped
   `content-t27-diss` detector, scored on the `ALL` row. What is left is the
   misnomer that caused the contradiction in the first place —
   `REFERENCE_HARD_CUT_F1_RANGE` / `_AGG` in `analyzer/provenance.py`,
   `local_hard_cut_f1()`, the `"hard_cut_f1"` key in the provenance dict, and
   the prose in `ARCHITECTURE.md` §9 and `CLAUDE.md` §2.2 all say *hard-cut*
   for a figure scored type-agnostically across every coded transition type.
   The genuine hard_cut-only figures are 0.841 / 0.964, so the name currently
   points at real but *different* numbers — the worst kind of wrong name.
   Rename to `REFERENCE_BOUNDARY_F1_*`, and grep for the shape: the
   `"hard_cut_f1"` / `"hard_cut_f1_source"` keys go into `validation_dict()`,
   which both front-ends write into **JSON exports** (`gui.py:2373`,
   `ui/main_window.py:463`). Renaming them changes the export schema for files
   already written, so it needs a migration decision, not a find-and-replace.

2. **Write down why the composite is shaped as it is.** Three choices have no
   recorded rationale: why a weighted linear sum rather than z-scores or a
   component score; why the default weights are 25/5/10/25/15/20; and where the
   normalization ceilings came from. The grounding theories are named but no
   metric is mapped to a construct. This is the first thing a reviewer will ask
   and the composite cannot be described as an operational measure until it
   exists. See `ARCHITECTURE.md` §8.1a. **Do not invent a justification** — if
   the defaults were judgement, say so.

3. **Assess the frame-step timestamp defect against the coded data.** The Tk
   coding editor (`gui_coding_editor.py`, the one the validation study was
   coded in) uses `next_frame()`, which does not move the clock — so any mark
   placed after frame-stepping is early by one frame per step. Marks placed by
   seeking or nudging are unaffected. Estimate how much stepping the coded
   episodes involved: if routine, the timestamps are biased early and the F1
   figures need recomputing; if rare, note it as a limitation. **Do not assume
   either.** The defect itself is **fixed** in both editors as of 2026-08-11,
   so no new coding is affected; this item is only about the timestamps already
   collected. See `validation/VALIDATION_LOG.md` 2026-08-11.

4. **Spot-check for whip-pan cuts coded as `hard_cut`.** The codebook now
   defines whip-pan disguised cuts; a coder not looking for them may have coded
   the join as `hard_cut`. The only subtype whose new definition could
   reclassify existing rows. See `validation/VALIDATION_LOG.md` 2026-08-11.

5. **Cite the transition typology, or say it is ours.** `CODEBOOK.md` defines
   five transition types and four `other` subtypes and cites **no source for
   any of them** — including `hard_cut` and `dissolve`. The `other` subtype
   definitions added 2026-08-11 were written from general editing vocabulary,
   unverified. There is also a live tension: the shot-boundary-detection
   literature generally bins transitions as CUT vs GRADUAL, so this scheme is
   finer-grained than the field it will be compared against, which needs
   justifying rather than assuming. Per `CLAUDE.md` §2.2, verify against
   primary sources before formal citation — or state plainly that the typology
   is the study's own and give the reasoning.

6. **Freeze the codebook.** Still DRAFT after three mid-study additions. The
   2026-07-04 log entry already said to freeze it before the second episode.

7. **Two data decisions the audit surfaced.** The output-audit passes on
   2026-08-14 found nineteen defects across four rounds, all fixed; see
   `LEARNINGS.md` and `FOR_PAPER.txt`. Every path listed for auditing has now
   been run and its artefact inspected. What is left is not defects but
   choices:

   - **There are TWO caches in this working copy.** `<project>/.analysis` has
     82 cached episodes (stale — from when the root was the project folder);
     `<project>/Shows/.analysis` has 28 (live). `patch_speech_cache.py` was
     reading the stale one. Archive or delete the stale copy before the
     paper's numbers are finalised, so nothing can read it by mistake.
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

8. **One Qt decision, not a port.** **Watch Analysis (Live)** (`gui_live.py`).
   The Qt Automated coding tab already shows a progress bar, the current
   episode, and a per-episode results table as the run proceeds. Decide
   whether a separate live window still earns its place before porting it.

   Smaller and also decisions: Settings has **Save as Preset** but not *Save
   as Default*; and the Episode Sampler can send a draw to the analysis queue
   but not to a hand-coding worklist, because the Qt Human coding tab has no
   worklist — it takes one episode at a time.

9. **Decide about `master`.** The branch is pushed (done 2026-08-11), so the
   work is backed up. But `feature/language-analysis` is far ahead of
   `master`, whose last commit is 2026-06-30 — and `master` is what GitHub
   shows visitors. Merging forward is a clean fast-forward.

   `README.md` **now needs a change on this point.** It describes the Tk build
   because the Tk build *was* the software; as of 2026-08-14 every screen
   exists in Qt, so the sentence naming `gui.py` as the product is no longer
   true. Decide which build the README describes before merging.

10. **Try the Qt build as the daily driver, then retire `gui.py`.**
   Every Tk screen now has a Qt equivalent, but "exists" is not "proven": the
   Qt Language, Validate tool, Agreement and Sampler screens have each been
   driven once, headless. Use them for real work before deleting anything —
   see item 12.

11. **Decide the startup wizard's default action.**
   The wizard opens on every launch with *Create Pipeline* as the default
   button, so dismissing it with Enter creates a pipeline — this project
   accumulated several that way. Options: make Skip the default when pipelines
   already exist; only show the wizard when there are none; or leave it.
   Needs a product call before code.

## Ready when the above are done

12. **Retire Tk modules that have reached parity.**
   Fifteen `gui*.py` files are still on disk and both builds read the same
   project, so there is a real risk of editing the wrong one. Delete only
   after item 10 — the Qt equivalents of `gui_sampler.py`, `gui_validation.py`
   and `gui_handcoding.py` exist as of 2026-08-14 but have not yet been used
   for real work. Not reversible in a hurry; do it deliberately.

13. **Commit or remove the seven untracked root files.**
   `CMAT_FIRST_TIME_UX_AUDIT.md`, `CMAT_GITHUB_PIPELINE_POSITIONING.md`,
   `CMAT_PIPELINE_INTERACTION_MODEL.md`, `CMAT_PYSIDE6_MIGRATION_STRATEGY.md`,
   `cmat_positioning_for_claude.md`, `GeminiPipelineSample.qss`,
   `preview_ui.py`. Each is either a document that belongs in `docs/`, a
   reference that belongs in `ui/reference/`, or scratch that should go.
   `CMAT_PIPELINE_INTERACTION_MODEL.md` is the north-star specification the
   pipeline work is being measured against and should not stay untracked.
