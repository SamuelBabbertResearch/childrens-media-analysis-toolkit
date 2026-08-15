# design/ — specifications and strategy notes

Durable design and positioning documents. Versioned deliberately: `docs/` is
the separately-managed wiki and is **gitignored**, so anything moved there
leaves version control. These needed to stay tracked.

**These are inputs, not authority.** The rulebook is `CLAUDE.md`; settled
choices are in `DECISIONS.md`. Where a document here disagrees with either, the
rulebook wins. In particular, `CLAUDE.md` §4 applies to everything in this
folder as it does to the mockups: **never adopt an invented label, metric, or
number from one of these documents.** Words, columns, figures and states come
from the engine.

| Document | What it is | Status |
|---|---|---|
| `CMAT_PIPELINE_INTERACTION_MODEL.md` | North-star specification for the pipeline system. Its own header says **do not implement the advanced features yet** — finish and stabilise the basic Qt pipeline first. | **Live.** The spec current pipeline work is measured against. |
| `CMAT_PYSIDE6_MIGRATION_STRATEGY.md` | The minimum-work strategy for getting off Tk. | **Largely discharged.** Every screen exists in Qt as of 2026-08-14. Kept as the record of why the migration was scoped as it was. |
| `CMAT_FIRST_TIME_UX_AUDIT.md` | First-time-researcher UX audit of the Windows build. | **Partly stale.** Traced against the Tk build (`gui.py`, `gui_sampler.py`, `gui_pipeline.py`), which is being retired. Its findings need re-checking against Qt before being acted on. |
| `CMAT_GITHUB_PIPELINE_POSITIONING.md` | Argues the pipeline should be the organising metaphor for how CMAT presents itself publicly. | **Advisory.** Bears directly on `TODO.md` item 9 (what `README.md` should say). |
| `POSITIONING_BRIEF.md` | Positioning and specialisation notes. Was `cmat_positioning_for_claude.md` at the repo root. | **Advisory, and overlaps the row above.** Both should be folded into `ROADMAP.md` and deleted — see `TODO.md`. |

The Qt stylesheet sample that used to sit beside these is now
`ui/reference/GeminiPipelineSample.qss`. It is a design reference only: nothing
loads it, `ui/reference_css.py` reads `*.css` by explicit name and never sees
it, and per `CLAUDE.md` §4 reference files are consumed, never hand-edited.
