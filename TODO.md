# CMAT — TODO

Only what is ready to be done now, in priority order. Finished items are
removed, not ticked. Longer-term work lives in `ROADMAP.md`.

---

## Now

1. **Port Human coding's remaining two screens.**
   *Validate tool* (tool vs. human scoring) and *Agreement* (Cohen's kappa
   between coders) are still Tk-only. Both are table screens over existing
   engine functions — `analyzer/validation.py` and
   `event_coding.inter_coder_agreement` — so no new analysis logic is needed.
   Add them as sub-views of the Human coding tab in `ui/handcoding.py`.

2. **Port the Episode Sampler.**
   The last Tk-only action. Its toolbar button in `ui/main_window.py` is
   disabled with a tooltip pointing at `python gui.py`. Engine side is
   `analyzer/sampler.py`; the Tk screen is `gui_sampler.py`.

3. **Decide the startup wizard's default action.**
   The wizard opens on every launch with *Create Pipeline* as the default
   button, so dismissing it with Enter creates a pipeline — this project
   accumulated several that way. Options: make Skip the default when pipelines
   already exist; only show the wizard when there are none; or leave it.
   Needs a product call before code.

## Ready when the above are done

4. **Retire Tk modules that have reached parity.**
   Fifteen `gui*.py` files are still on disk and both builds read the same
   project, so there is a real risk of editing the wrong one. Delete only
   after 1 and 2 land — `gui_sampler.py`, `gui_validation.py` and
   `gui_handcoding.py` are still the only home of those screens. Not
   reversible in a hurry; do it deliberately.

5. **Commit or remove the four untracked root files.**
   `CMAT_FIRST_TIME_UX_AUDIT.md`, `cmat_positioning_for_claude.md`,
   `GeminiPipelineSample.qss`, `preview_ui.py`. Each is either a document that
   belongs in `docs/`, a reference that belongs in `ui/reference/`, or scratch
   that should go.
