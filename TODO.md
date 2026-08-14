# CMAT — TODO

Only what is ready to be done now, in priority order. Finished items are
removed, not ticked. Longer-term work lives in `ROADMAP.md`.

---

## Now

1. **Resolve the headline F1 contradiction.** `analyzer/provenance.py` has a
   comment saying per-episode hard-cut F1 spanned **0.84–0.96, aggregate
   ~0.91**, directly above constants saying **0.75–0.91, aggregate 0.85**. The
   validation log shows runs at 0.836 and 0.964. `CLAUDE.md` and
   `ARCHITECTURE.md` both quote the constants. This is the number the product's
   honesty claim rests on — decide which is current, delete the other, and say
   in `ARCHITECTURE.md` §9 which runs the aggregate covers. **Do not guess.**

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
   either.** Then decide whether to fix the Tk editor — it is the shipping
   software. Fixed already in `ui/player.py`; see
   `validation/VALIDATION_LOG.md` 2026-08-11.

4. **Spot-check for whip-pan cuts coded as `hard_cut`.** The codebook now
   defines whip-pan disguised cuts; a coder not looking for them may have coded
   the join as `hard_cut`. The only subtype whose new definition could
   reclassify existing rows. See `validation/VALIDATION_LOG.md` 2026-08-11.

5. **Freeze the codebook.** Still DRAFT after three mid-study additions. The
   2026-07-04 log entry already said to freeze it before the second episode.

6. **Port the Language screen.** Tk's Automated coding has a *Language*
   sub-tab (Speech + Vocabulary, `gui.py` ~line 3521) with **no Qt equivalent**.
   The docs previously implied the port was complete; it is not.

7. **Decide about `master`.** The branch is pushed (done 2026-08-11), so the
   work is backed up. But `feature/language-analysis` is 71 commits ahead of
   `master`, whose last commit is 2026-06-30 — and `master` is what GitHub
   shows visitors. Merging forward is a clean fast-forward.

   `README.md` needs no change on this point — it describes the Tk build
   because the Tk build *is* the software. That was checked, not assumed.

8. **Port Human coding's remaining two screens.**
   *Validate tool* (tool vs. human scoring) and *Agreement* (Cohen's kappa
   between coders) are still Tk-only. Both are table screens over existing
   engine functions — `analyzer/validation.py` and
   `event_coding.inter_coder_agreement` — so no new analysis logic is needed.
   Add them as sub-views of the Human coding tab in `ui/handcoding.py`.

9. **Port the Episode Sampler.**
   The last Tk-only action. Its toolbar button in `ui/main_window.py` is
   disabled with a tooltip pointing at `python gui.py`. Engine side is
   `analyzer/sampler.py`; the Tk screen is `gui_sampler.py`.

10. **Decide the startup wizard's default action.**
   The wizard opens on every launch with *Create Pipeline* as the default
   button, so dismissing it with Enter creates a pipeline — this project
   accumulated several that way. Options: make Skip the default when pipelines
   already exist; only show the wizard when there are none; or leave it.
   Needs a product call before code.

## Ready when the above are done

11. **Retire Tk modules that have reached parity.**
   Fifteen `gui*.py` files are still on disk and both builds read the same
   project, so there is a real risk of editing the wrong one. Delete only
   after items 6, 8 and 9 land — `gui_sampler.py`, `gui_validation.py` and
   `gui_handcoding.py` are still the only home of those screens. Not
   reversible in a hurry; do it deliberately.

12. **Commit or remove the four untracked root files.**
   `CMAT_FIRST_TIME_UX_AUDIT.md`, `cmat_positioning_for_claude.md`,
   `GeminiPipelineSample.qss`, `preview_ui.py`. Each is either a document that
   belongs in `docs/`, a reference that belongs in `ui/reference/`, or scratch
   that should go.
