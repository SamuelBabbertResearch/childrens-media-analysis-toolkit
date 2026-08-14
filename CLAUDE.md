# CLAUDE.md — CMAT rulebook

Rules only. Everything else has a home: `INDEX.md` points at it.

---

## 1. What CMAT is

**Scientific workflow software for children's media research.** It measures
formal features of children's television — pacing, colour, motion, flashing,
audio, language — and supports structured hand coding of what no automated
measure can see.

It is not a media player, a recommendation engine, or a content rater.

### Product principles

- **Clarity.** A researcher must be able to see exactly what the software is
  doing. Every composite shows its component parts.
- **Reproducibility.** A run is a record: settings fingerprinted, provenance
  kept, results comparable across runs.
- **Transparency.** Unvalidated measures are flagged wherever their numbers
  appear — in the interface, in exports, and in provenance.
- **Windows-native behaviour.** Platform conventions outrank visual ambition.
- **Professional scientific interface.** Dense, legible, information-first.

## 2. Non-negotiable rules

### 2.1 The stimulus-only guardrail

**CMAT issues no verdict.** No token, badge, column, field, preset, or export
may report appropriateness, target audience age, educational value, or quality.
It measures the stimulus, not the viewer.

Consequences that keep coming up:

- Unusual values get a **glyph plus a legend naming the comparison set**, never
  a colour that implies a verdict.
- Age-named presets (`Toddler (0-2)`) are **reference ranges for studies of
  that group**, not suitability ratings.
- Status badges report the state of the *work* ("Analyzed"), never a property
  of the programme.
- `target_age_min`/`target_age_max` exist in the database from metadata
  imports. They are never a column.

### 2.2 Scientific language

**Always correlational. Never causal.** No feature *causes* an outcome. Age,
temperament, sensory-processing profile and viewing dose are not captured.

**Never quote an accuracy figure without its qualifiers.** The headline is
hard-cut F1 **0.85** (range 0.75–0.91), matched **type-agnostically within
±2 s**, from a **PRELIMINARY single-coder pilot**. Type classification scores
lower and is reported separately. Event-level accuracy and count accuracy are
different claims and both must be labelled as such.

**Flashing is never presented as a safety assessment.** It is a whole-frame
luminance mean that implements neither the area threshold nor the red-flash
criterion broadcast photosensitivity guidance specifies, and the tool is
unvalidated. It compares episodes measured the same way. Nothing more.

**Words per minute is reported with speech density, or not at all.** WPM
divides by *dialogue time, not runtime* — it is how fast characters speak when
they speak, not how talkative an episode is. Alone it invites the wrong
reading.

**Say "sensory load" only for the composite.** Six numbers feed it —
`cuts_per_min`, saturation mean, contrast mean, motion mean, flashing rate,
audio RMS mean. Shot length, rhythm variability, motion peak, dynamic range,
speech and hand-coded events are measured and reported but **not scored**.
Name the metric when you mean the metric.

**Unvalidated measures are flagged wherever their numbers appear.**
`analyzer.measurements.ungraded_measurements()` computes the current list from
the registry — call it, never hard-code one, or the copy goes stale silently.
`ARCHITECTURE.md` §9 explains what each status means.

The grounding is Huston & Wright's formal features and Lang's LC4MP; Lillard &
Peterson (2011) and Christakis et al. (2004) are the associations usually
cited, both correlational and both contested. Verify against primary sources
before formal citation.

### 2.3 Files that must never be committed

- **`FOR_PAPER.txt`** — paper notes. Gitignored. Do not `git add -f` it, do not
  include it in a commit, do not paste its contents into a public file, a
  commit message, the README, or the website. If `git add -A` would stage it,
  stop and fix the ignore rule instead.
  **Keep it updated**: whenever work produces something the paper will need — a
  figure, a corrected number, a methodological decision, a limitation, a
  citation — append it without being asked. Date anything numeric, and when a
  figure is revised keep the superseded value and say what changed; the record
  of *why a number moved* is itself paper material.
- **`user_prefs.json`** — contains a local absolute path.
- **`pipelines/`** — personal project data.

### 2.4 Architecture

1. **`analyzer/` has zero GUI imports.** Each metric is an isolated, testable
   function: input = video path + config, output = numbers. Enforced by
   `tests/test_engine_isolation.py`. This is what made the Qt migration a
   presentation rewrite; do not spend it.
2. **`cli.py` and the GUI are thin layers over the same engine.** Never
   duplicate analysis logic in a front-end.
3. **Analysis runs on a worker thread** with a progress callback. The
   interface must never freeze.
4. **One palette, one accent, in `ui/tokens.py`** — which imports no framework,
   so both front-ends share it. Never write a literal colour into a widget.
   Two sources of truth is how two different blues both came to mean
   "selected".

## 3. Terminology

The pipeline stages are the vocabulary of the whole product. Use these words in
code, interface strings, and documents; do not invent synonyms.

| Term | Means |
|---|---|
| **Sampling** | how episodes were chosen |
| **Selection** | the working set drawn from them |
| **Measurement** | producing numbers — automated coding *or* hand coding |
| **Validation** | comparing the tool against a human coder |
| **Results** | aggregates and exports |

Two names, and they are not interchangeable:

- **CMAT** (Children's Media Analysis Toolkit) — the software.
- **Open Children's Media Index** — the published dataset at
  OpenChildrensMediaIndex.org, built by `build_site.py`.

Other terms:

- **Pipeline**, not "trial", for a workflow the user owns. A *trial* is a
  recorded run — a named sampling plus coding pass, listed in the Trials tab.
- **Automated coding** and **hand coding** are both measurement. Hand coding is
  a measurement in its own right, not merely a step towards validating
  automation.
- Call the interface a **Classic Desktop UI**, or a **Mavericks-inspired
  layout** when a period reference is needed. Avoid naming trademarked
  operating systems or applications in documentation, comments, commit
  messages, or interface strings.

## 4. Design constraints

- **The visual pipeline is a central product feature**, not decoration. It is
  how a researcher sees what the software is doing.
- **Not a generic AI dashboard.** No card grids, no giant headings, no modern
  SaaS styling, no dashboard tiles.
- **Take the mockups' surfaces; take Windows' controls and behaviours.**
  Gradients, spacing and type from the design references; caption controls,
  keyboard conventions, file dialogs and window management from the platform.
- **The mockups specify styling only.** Words, columns, figures and states come
  from the engine. Never adopt a mockup's invented label, metric, or number. If
  a mockup shows a field the software has no data for, the field is not built.
- **`ui/reference/*.css` is the source of the design.** Extracted verbatim from
  the supplied mockups; consume it, never hand-edit it, never re-type values
  out of it.
- **Read `ui/DESIGN.md` §0 before building any screen.**
- **An unavailable control must not look like a broken one.** Disable it and
  say why.

## 5. Session rules

- **Short sessions.** When a task broadens, stop and split it — hand off
  through the repo files, not the chat.
- **Start by reading** `onboarding.md`, `TODO.md`, `DECISIONS.md`,
  `LEARNINGS.md`. Do not assume context from previous chats unless it is
  recorded in the repo.
- **End by updating** `TODO.md` and `onboarding.md`; log any real decision in
  `DECISIONS.md` and any failure in `LEARNINGS.md`; update `navigation.md` if
  the structure changed.
- **No unrequested redesigns.** A settled choice is recorded in `DECISIONS.md`
  with its reason — read it before revisiting.
- **No context drift.** If a change does not serve the research pipeline, it
  does not belong.

## 6. Coding constraints

The five recurring failure shapes on this project, each with a test for it,
are in `LEARNINGS.md` § *The shape most of these share*. Read it before
believing a piece of work is finished.

- **Verify against the artefact, not the render.** Run it, then read *what it
  produced* — draw the sample and read the strata, export the CSV and read the
  columns, extract the PDF's text and check it against the screen. "It
  rendered", "the tests pass" and "the button works" are all compatible with a
  wrong number, and on this project a wrong number that displays correctly is
  the failure mode. A scripted edit is not done until the new symbol is
  grepped and found *called*, not merely imported.
- **A control that exists is not a feature that works.** Check the data path
  reaches it.
- **Audit a port by ENTRY POINTS, not by screens** — every menu item, every
  button, every dialog opened from another dialog. A tab-by-tab comparison
  reveals nothing.
- **When a rule must hold at every call site, put it IN the call.**
  `analyzer.cache.load_scored()` is the shape of the fix.
- **Read the neighbouring implementation before writing a parallel one.**
- **A module that calls itself the source of truth must be READ, not
  restated** — by every consumer, or it is not one.
- **Fixing one instance of a repeated mistake is the least useful response to
  finding it.** Grep for the shape.
- **State what is not done, and do not declare completion from the builder's
  side.** "I built what I set out to build" is not "it works". A file that
  overstates progress is worse than one that says nothing.
- **Never write into the working copy's data from a test.** `Shows/`,
  `validation/` and the pipeline documents are real research data.
- **Do not substitute a dependency** without asking — see `STACK.md`.
- Type sizes in the Qt front-end are **device-independent pixels**; the Tk
  tokens are points and are marked Tk-only.
- Qt 6 is per-monitor DPI aware by default. **Do not add `ctypes` DPI calls.**
