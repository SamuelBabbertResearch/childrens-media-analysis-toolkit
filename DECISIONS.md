# CMAT — Decision log

Real decisions and why they were made. Bugs and mistakes belong in
`LEARNINGS.md`, not here.

Format: **decision** · reason · date · what was rejected.

**Companion log.** `validation/VALIDATION_LOG.md` is the *research* diary —
kept contemporaneously since 2026-07-02, with dated coding sessions, result
corrections, and codebook changes. Methodology decisions belong there; product
and architecture decisions belong here. When a change is both, log it in both
and say so.

Sections: [Foundations](#foundations-june--august-2026) (chronological, how the
project got its shape) · [Product identity](#product-identity) ·
[Architecture](#architecture) · [Interface](#interface) ·
[Data and reporting](#data-and-reporting).

---

## Foundations (June – August 2026)

The decisions that gave the project its shape, in the order they were made.
Several were forced by a metric disagreeing with obvious intuition, which is
worth knowing: the composite has been calibrated against judgement more than
once.

### The tool is named CMAT; the public database is the Open Children's Media Index
**Decision.** Two names, deliberately. **CMAT** (Children's Media Analysis
Toolkit) is the software; the **Open Children's Media Index** is the published
dataset at OpenChildrensMediaIndex.org. Repository:
`childrens-media-analysis-toolkit`.
**Reason.** The tool and the corpus it produces are separate contributions, and
conflating them would misdescribe both.
**Date.** 2026-06-30 (naming); the index site followed 2026-07-01.
**Rejected.** "Sensory-Load Analyzer" (the original working name — too narrow
once language and hand coding arrived); one combined name.

### Audio is part of the composite
**Decision.** Add RMS loudness, peak and dynamic range.
**Reason.** A calibration failure: a video of someone dancing energetically to
music scored **0.176** against a quiet episode of *Little Bear* at **0.221**.
The composite was blind to the most obvious difference between them. With
audio, the same video's audio component read 93%.
**Date.** 2026-06-28.
**Rejected.** Vocal event detection and beat/tempo analysis — no dependable
off-the-shelf package, and tempo could not distinguish a show with music from
one without.

### Colour contrast is measured as well as saturation
**Decision.** Per-frame standard deviation of the V channel, alongside mean
saturation.
**Reason.** Saturation alone ranked *Little Bear* (0.33) above a high-energy
YouTube video (0.29). Blown-out, high-value production desaturates colour, so
saturation systematically favours gentle animation — and penalises live action.
**Date.** 2026-06-28.
**Rejected.** Replacing saturation outright; it still carries signal, so both
are reported.

### Presets, and user-editable weights and ceilings
**Decision.** Age-named presets plus full control over weights and
normalization ceilings, including format presets (Animated / Live-Action).
**Reason.** Live action loses on saturation even when more stimulating overall,
so one fixed weighting misrepresents whole categories of content. A researcher
must be able to say what their composite means.
**Date.** 2026-06-28 (deferred as too complex, then built the same day).
**Rejected.** A single fixed composite.

### One level of category nesting
**Decision.** `<root>/Category/Show/*.mp4` is discovered; deeper is not.
**Reason.** Asked for directly — shows could not all sit in one flat folder.
**Date.** 2026-06-29.
**Rejected.** Arbitrary depth — it makes `show_key` ambiguous, and seasons
already sit awkwardly in this scheme (see `LEARNINGS.md`).

### Sampling is a first-class module, and hands off into the tool
**Decision.** Simple random, stratified and spread sampling, with named trials
— and the sample **loads into the analysis queue**, not just an exported list.
**Reason.** "I need it to be able to load those episodes only easily into the
program… as intuitive and accessible as possible." A sampling tool that only
prints a list leaves the researcher to do the bookkeeping by hand.
**Date.** 2026-06-30.
**Rejected.** CSV export alone.

### Speech from captions first, Whisper only as fallback
**Decision.** WPM and speech density from `.srt`/`.vtt` when present;
faster-whisper only when no caption file is found. Vocabulary metrics keep the
source datasets' original column names.
**Reason.** Captions are instant and exact. Whisper costs minutes per episode
and an occasional misheard word barely moves a word count. The dependency had
to be free and open source.
**Date.** 2026-06-30.
**Rejected.** Always transcribing; a paid speech API.

### Episode metadata is imported, not typed
**Decision.** Importers for Wikipedia "List of … episodes" tables and TVMaze,
with flexible air-date formats.
**Reason.** Air dates drive era stratification and timeline charts, and no
researcher should retype a season of them.
**Date.** 2026-06-30 – 2026-07-01.
**Rejected.** Manual entry only.

### Published corpus sampling policy
**Decision.** Under 15 episodes, analyse all; 15–60, a spread sample of 10.
Long-running shows are split into **eras** rather than averaged whole. Baseline
material (non-children's content) is marked as baseline, not ranked as a
children's show.
**Reason.** A single mean across forty years of a show describes nothing that
exists. Baselines anchor the scale but are not the subject.
**Date.** 2026-07-01.
**Rejected.** One sampling rule for every show regardless of run length.

### Fantastical events became a first-class measurement
**Decision.** Hand-coded event coding with its own codebook, rates, and
aggregation.
**Reason.** The literature indicates fantastical content may matter as much as
raw pace — so a tool that measured only pacing would be measuring the less
important half.
**Date.** 2026-07-09.
**Rejected.** Staying formal-features-only.

### Animacy is coded on onset, not premise
**Decision.** An animacy event is an inanimate object *becoming* an agent —
not a show whose premise includes a talking animal.
**Reason.** A talking-dog show that is otherwise entirely realistic is
correctly judged non-fantastical; coding the premise would mark every episode
of it and swamp the measure.
**Date.** 2026-07-09.
**Rejected.** Counting the premise.

### Trials are recorded runs, and have their own tab
**Decision.** A named sampling + coding run is a **trial**, listed and
inspectable.
**Reason.** Reproducibility: the question "what did this number come from?"
must have an answer on screen.
**Date.** 2026-07-09.
**Rejected.** "Experiment" as the name — too strong for what it records.

### CMAT embeds a video player after all
**Decision.** Reversed a standing "no video player in CMAT" rule and built the
coding editor around one.
**Reason.** Hand coding without frame-accurate playback in the same window
means a coder alt-tabbing between a player and a spreadsheet, transcribing
timestamps by hand. The rule was protecting scope at the cost of the workflow.
**Date.** 2026-07-12.
**Rejected.** Keeping coding and playback in separate applications. (This
decision later forced the VLC-vs-QMediaPlayer choice below.)

### Intro coding is templated
**Decision.** Code a title sequence once, label it (`Season 1`, `90s`), reuse
it across every episode that shares it.
**Reason.** Coding the same intro forty times is transcription, not judgement,
and it inflates agreement statistics.
**Date.** 2026-07-13.
**Rejected.** Coding every episode from zero.

### Positioning: an open, customizable pipeline — not a claim of accuracy
**Decision.** CMAT's contribution is being open, accessible and configurable,
with interchangeable measurement tools whose error is *reported*. It is not a
claim to measure cuts better than anyone else.
**Reason.** Reached after directly testing whether the automated analysis could
be made accurate enough to stand alone. It can produce dependable episode-level
counts while still misplacing individual transitions — so the honest product is
one that exposes its tools and its error, not one that hides them behind a
number.
**Date.** 2026-08-04, after a fortnight of doubt about whether the project was
worth continuing.
**Rejected.** Competing on detector accuracy; presenting a single authoritative
composite.

### Automated and hand coding are separate tracks with separate tabs
**Decision.** Library / Index / Automated coding (with Validation inside) /
Hand coding / Trials. Hand coding is reachable without going through
validation.
**Reason.** Hand coding had only been reachable *inside* the validation screen,
which framed it as a step towards checking the automation. For a researcher who
hand-codes and never automates anything, that is the wrong shape entirely.
**Date.** 2026-08-04.
**Rejected.** One combined coding screen; hand coding as a validation
sub-feature.

### Measurement tools are interchangeable and registered
**Decision.** A registry says which tool produces each measurement, with what
parameters and what validation status; settings expose the choice; results
carry a fingerprint of it.
**Reason.** It is what makes "build your own composite" real rather than a
slogan, and it makes stale cache detectable instead of assumed.
**Date.** 2026-08-08.
**Rejected.** Hardcoded detectors.

### TransNetV2 is an optional download, not a bundled dependency
**Decision.** Offered behind a screen explaining what it improves, with the
all-or-none corpus warning.
**Reason.** A neural detector is a large download most users will not need, and
mixing detectors within one corpus makes pacing incomparable across shows.
**Date.** 2026-08-05.
**Rejected.** Bundling it; making it the default.

### The pipeline visualizer is the primary orientation device
**Decision.** A visual, editable pipeline shown prominently, and reachable at
all times.
**Reason.** "It is all so confusing for users, even for me." The workflow was
real but invisible; the software could not explain itself.
**Date.** 2026-08-08.
**Rejected.** A static diagram in the documentation; a linear wizard.

### Move from Tkinter to PySide6
**Decision.** Rebuild the front-end in Qt.
**Reason.** Tkinter could not render the intended interface — it has no real
stylesheet engine, and every gradient and bevel had to be hand-drawn on a
canvas. Qt renders HTML/CSS, so the design becomes declarative.
**Date.** 2026-08-09.
**Rejected.** Continuing to hand-draw controls in Tk.

---

## Product identity

### CMAT issues no verdict
**Decision.** No token, badge, column, field, preset, or export reports
appropriateness, target audience age, educational value, or quality. CMAT
measures the stimulus and presents labelled metrics a person interprets.
**Reason.** The tool measures formal features of a video. Nothing in the data
supports a claim about a viewer, and a rating would be believed anyway.
**Date.** Foundational.
**Rejected.** An overall rating; age-appropriateness badges; traffic-light
colouring of metric cells.

### Age-named presets are reference ranges, not suitability ratings
**Decision.** `Toddler (0-2)` names **the age group a study using that preset is
about**, not an audience the show is suitable for.
**Reason.** Researchers need comparison ranges; presenting them as suitability
would be the verdict the tool refuses to give.
**Date.** Foundational.
**Rejected.** Dropping age names entirely — they are the clearest label for the
range, provided the framing is explicit.
**Corrected 2026-08-14.** This entry previously read "names the literature the
ceilings come from". **No such literature exists.** Checked: no citation appears
in `config.json`, in this file, or anywhere in the repository, and the ceilings
were AI-generated defaults never traced to a source (`ARCHITECTURE.md` §8.1a).
The only literature reference in any preset is `Preschool (2-5)`, which cites
Lillard & Peterson (2011) **for the age band, not for the ceiling values**. The
decision itself — age names denote the study population, not suitability — is
unaffected and still stands; only the false provenance claim is withdrawn.

### Unusual values are marked with a glyph and a named comparison set
**Decision.** ▲/▽ plus a legend naming the set (e.g. "the 24 episodes listed
here"), never colour alone. Tukey fences, and not computed below eight values.
**Reason.** A red cell beside a high flashing rate reads as "bad" whatever the
caption says. Below eight values a quartile cannot call anything unusual.
**Date.** 2026-08-10 (Index tab).
**Rejected.** Heat-map colouring; fixed thresholds.

---

## Architecture

### `analyzer/` imports no GUI framework
**Decision.** The engine is framework-free; front-ends are thin layers.
**Reason.** It made the Tk → Qt move a presentation rewrite rather than an
application rewrite. ~12,000 lines of engine, CLI and site builder did not move.
**Date.** Foundational; proved out 2026-08-09 onwards.
**Rejected.** Convenience imports of Qt into engine modules.

### Scoring settings and measurement settings are separate axes
**Decision.** Weights and ceilings re-score from cache instantly. Detectors,
thresholds and sample rates make cached results stale, and are fingerprinted
into each result.
**Reason.** It is what lets "Apply & Re-score" promise what it says, and what
makes staleness detectable rather than assumed.
**Date.** Foundational.
**Rejected.** One undifferentiated settings screen.

### Migrate Tk → Qt by building beside, not on top
**Decision.** The Qt front-end lives in `ui/`; the Tk build keeps working until
each screen reaches parity.
**Reason.** There is never a broken state, the two can be run against one
project and compared, and if the migration stalls nothing is lost.
**Date.** 2026-08-09.
**Rejected.** In-place rewrite; a big-bang cutover.

### The index stores one canonical absolute path per episode
**Decision.** `upsert_episode` and every function keyed on `file_path` resolve
the path first.
**Reason.** The same episode reached through a relative root and an absolute
one produced two rows, double-counting it in every aggregate — see
`LEARNINGS.md`. Normalising at the choke points means no caller has to
remember.
**Date.** 2026-08-10.
**Rejected.** Fixing the callers; keying on a content hash (a good idea for the
*cache*, still open — see `ROADMAP.md`).

### A pipeline document binds to an episode sample, not to a show
**Decision.** `PipelineDoc.source_key` holds a key `build_pipelines()`
produces — `sample:<folder>`, or `unsampled`. *Link to Episode Sample* offers
those, and only those.
**Reason.** It previously offered **shows**, whose keys (`Show/Season 1`) are a
different namespace, so the look-up never matched and every node of every
linked pipeline reported "no derived status". A stage is derived *for a
sample*: it counts the episodes in one `selected.csv`. A show is not that set.
**Consequence.** The key contains an absolute folder path, so moving the
library breaks the link. The inspector says so and names the fix rather than
falling back to a plausible number.
**Date.** 2026-08-14.
**Rejected.** Matching a show key to a sample by episode overlap — a guess
about which of several samples of one show was meant.

### The Library sends work to other tabs by right-click
**Decision.** Right-clicking a Library selection offers the destinations that
can act on it — analyse, queue, transcribe, hand-code, validate, show in
index, speech, reveal on disk — and every entry routes through
`MainWindow._send_to()`, which sets the target AND switches to the tab. The
tree is multi-select so a batch can be queued in one gesture.
**Reason.** Selecting an episode already pushed it to Automated coding and
Human coding, but nothing said so and nothing took you there: the user had to
know which tab wanted it and go looking. Right-click is the platform's "act on
this item" gesture (`CLAUDE.md` §4 — take Windows' controls and behaviours),
and it is discoverable in a way a fourth toolbar button is not.
**Consequence.** Destinations that need exactly one episode (hand coding,
Show in Index) are DISABLED with a reason for a folder or a multi-selection,
rather than hidden — an unavailable control must not look like a broken one.
**Date.** 2026-08-14.
**Rejected.** A row of "Send to…" buttons above the tree (four more controls
on the densest screen); a drag-and-drop-onto-tab gesture (undiscoverable, and
Qt tab bars are not drop targets without custom event handling).

### A derived value has ONE derivation, called by everyone who shows it
**Decision.** Where a value is computed from other values, the computation
lives in the engine and every display calls it. Three of these now exist and
they are the pattern to copy:

| Helper | Answers |
|---|---|
| `analyzer.cache.load_scored()` | how do I read a cached result |
| `analyzer.metrics_sensory.effective_weights()` | what weights actually produced this score |
| `analyzer.measurements.ungraded_measurements()` | which numbers on this screen need a flag |

**Reason.** The alternative is not "each caller decides" — it is "each caller
decides differently, and nobody notices". Reading the cache without
re-deriving the composite was written independently in four places. The
unvalidated flag was decided independently on five surfaces and most decided
"not at all". The audio weight redistribution was computed in the engine and
re-guessed in two displays. Each site was correct on its own reading; the rule
that made them wrong lived in a comment.
**Date.** 2026-08-14.
**Rejected.** Documenting the rule near the call sites (that is what failed);
storing the derived value everywhere it is shown (a schema change per
display, and old data still lacks it).

### A claim that leaves the tool is read from its source, never restated
**Decision.** `analyzer/provenance.py` is called by the PDF, the CSV sidecar,
the JSON export, the report and `build_site.py`. None of them restates an
accuracy figure or a validation status.
**Reason.** Its docstring already claimed it was "the single source of truth
… shown on every results view, export, and the public site". It was not: the
site hard-coded its own F1 range and its own per-metric statuses, and
published a figure contradicting the constants and a validation status
contradicting the registry. A module is not a source of truth because it says
so; it is one when the consumers call it.
**Consequence.** When `TODO.md` item 1 settles which F1 is authoritative, one
edit updates the interface, the exports and the site together.
**Date.** 2026-08-14.
**Rejected.** Leaving the site's wording independent "because it is
audience-facing" — that is exactly where a wrong claim costs most.

### The unvalidated flag is derived from the registry, in one place
**Decision.** `analyzer.measurements.ungraded_measurements()` is the single
answer to "which numbers on this screen need a flag". The episode report, the
comparison, the Index table, the component chart, the PDF and the published
site all call it.
**Reason.** `CLAUDE.md` §2.2 requires the flag wherever the numbers appear.
Each surface decided for itself and most decided "not at all": the Index, the
chart, the comparison, the PDF and the site all showed flashing figures with
no flag, and the report only flagged results whose cache carried
`measurement_tools` — 2 of 13 here.
**Date.** 2026-08-14.
**Rejected.** A hard-coded list per screen (it is how they diverged);
back-filling `measurement_tools` into old caches (rewrites research data to
fix a display problem).

### Effective weights are part of the result, not a display detail
**Decision.** `metrics_sensory.effective_weights(config, audio_available)` is
called by the engine to compute the composite and by the report and chart to
explain it.
**Reason.** Missing audio redistributes its weight across the visual metrics.
The engine did that in a local variable and returned only the score, so every
display read the nominal weights and produced a breakdown that did not sum to
the score above it. A calculation that adjusts its inputs has to expose the
adjusted ones or its explanation is fiction.
**Date.** 2026-08-14.
**Rejected.** Recomputing the redistribution in `ui/` (duplicating engine
arithmetic in a front-end, which `CLAUDE.md` §2.4 forbids); storing effective
weights in the cache (a schema change to fix a display bug, and old caches
would still lack them).

### Eras are derived from air dates, not typed per episode
**Decision.** `analyzer/eras.py` turns a show's era definitions plus each
episode's air date into `Episode.extra["era"]`, which the sampler stratifies
on like any other column. Air dates come from the index; era ranges come from
`show_eras`.
**Reason.** The pieces already existed and nothing joined them: era ranges had
been in the index since July for chart colouring, and `sample()` has always
accepted `stratify_by="<any column>"` — but `Episode.extra` is populated by
neither `scan_entry_root` nor `load_registry_csv`, and a folder scan leaves
`air_date` as None. Deriving the tag is the smallest join, and it means one
air-date import serves both the sampler and the charts.
**Consequence.** Era stratification is only as good as the imported metadata.
Episodes with no air date group as `(no era)` — a real stratum, so they stay
in the sampling frame and the shortfall is visible rather than silent.
**Date.** 2026-08-14.
**Rejected.** An era field typed per episode (it is a property of the date, so
it would be transcription and would drift); dropping undated episodes from the
frame (it shrinks the sample without saying so).

### One import dialog for Wikipedia and TVMaze
**Decision.** `ui/metadata_import.py` handles both sources; the source is a
combo box, not a separate dialog.
**Reason.** After the fetch they are the same job — both return a
`WikiEpisode` list, both go through `match_to_files`, both end at
`upsert_episode_metadata`. Two dialogs would be two places for the matching
rules to drift apart.
**Date.** 2026-08-14.
**Rejected.** Porting `gui_wiki_import.py` and `gui_tvmaze_import.py`
separately, as the Tk build has them.

### A fuzzy filename match is offered, flagged, and revocable
**Decision.** Rows matched by title similarity show their score, are counted
in a warning above the table, and can be unchecked — individually or all at
once. Nothing unchecked is written.
**Reason.** `match_to_files` falls back to `difflib` similarity down to 0.45.
That is a guess about which file is which episode, and applying a wrong one
writes an air date nothing downstream will ever question — while air dates
drive era stratification in the sampler. Silently applying them would make the
importer a source of quiet data corruption.
**Date.** 2026-08-14.
**Rejected.** Applying every match above the threshold (what the Tk build
does); refusing fuzzy matches outright (they are usually right, and typing a
season of air dates by hand is worse).

### A comparison shows a signed difference and nothing else
**Decision.** `report.compare_html` renders two value columns and B − A in each
metric's own units. No ordering, no colour, no arrow, no "higher/lower" verdict
wording. It refuses to compare an episode with a show aggregate.
**Reason.** A side-by-side is the easiest place in the product to imply a
ranking, and `CLAUDE.md` §2.1 says CMAT issues none. Mixing an episode with an
aggregate would also put one episode's numbers beside a mean of many and call
the gap a difference.
**Date.** 2026-08-14.
**Rejected.** Percentage differences (they imply a baseline that does not
exist); highlighting the larger value.

### Optional-tool availability is a presence check, not an import
**Decision.** `OptionalTool.is_available()` uses `importlib.util.find_spec`;
`version()` reads package metadata. Neither imports the package.
**Reason.** The old `import_module` check was stricter — it proved the package
loads — but for TransNetV2 that means importing PyTorch: 3.6 seconds, and a
deep-learning runtime resident in the process, to decide whether to grey out a
combo-box entry. A package that is installed but broken now reads as
available; the real import error then surfaces when it is actually used, which
is a better place to meet it than a greyed-out menu item.
**Date.** 2026-08-14.
**Rejected.** Memoising the import (still 3.6s once per session, still resident
PyTorch); probing in a background thread (a settings dialog that fills in
after four seconds is worse than one that is simply right).

### The analysis queue holds paths, never results
**Decision.** `AutomatedTab._queue` is a list of episode and show paths. A
target that has disappeared by the time its turn comes is reported as a failed
row; the rest of the run continues.
**Reason.** A queue can sit for an hour while earlier entries run, so anything
derived stored in it would describe the library as it was when queued. And a
twenty-episode run must not be thrown away by one moved file.
**Date.** 2026-08-14.
**Rejected.** Queuing resolved episode lists (a show's contents change);
aborting the run on a missing target.

### Every export carries its provenance, in the shape that fits the format
**Decision.** JSON embeds `validation_provenance`; CSV writes a
`<name>_PROVENANCE.txt` sidecar beside it; PDF renders the statement into the
report.
**Reason.** `CLAUDE.md` §2.2 — an accuracy figure without its qualifiers is
the thing the rule exists to prevent, and an export is exactly where numbers
leave the tool and the qualifiers get left behind. A comment row would have
kept the CSV self-contained but stopped it being machine-readable, so the
sidecar is the compromise, and the status bar names both files.
**Date.** 2026-08-14 (Qt; the Tk build did the same from 2026-07).
**Rejected.** A provenance comment row inside the CSV; provenance only on
request.

### Episode notes and metadata live in the index, not the cache
**Decision.** `air_date`, `season_num`, `episode_num` and notes are written
through `analyzer/db.py` to the SQLite index.
**Reason.** They are things a PERSON recorded. The cache is rewritten by every
re-analysis, so keeping them there would mean re-measuring an episode silently
erased its air date — and air dates drive era stratification in the sampler.
**Date.** 2026-08-14 (Qt; matches the Tk build).
**Rejected.** A sidecar JSON per episode; storing them in the cache file.

### Language is a tab, not a screen inside Automated coding
**Decision.** `ui/language.py` is a seventh top-level tab.
**Reason.** The pipeline already treats language as its own stage with its own
"Language only" template, on the grounds that a language study needs no
sensory pass at all. Burying it inside Automated coding would contradict the
model the pipeline teaches. It also follows the existing decision that
automated and hand coding are separate tracks with separate tabs.
**Date.** 2026-08-14.
**Rejected.** A sub-view of Automated coding, mirroring the Tk layout.

### Screens inside a tab are sub-toolbar buttons, not nested tabs
**Decision.** `SubViews` puts a group of checkable buttons in the reference's
`.sub-toolbar` over a `QStackedWidget`. Used by Language and Human coding.
**Reason.** `ui/reference/*.css` has a tab strip and a sub-bar; it has no
nested tab strip, and a second row of tabs inside the first is not a Windows
convention either. The checked state is the platform's pressed face — no
second accent.
**Date.** 2026-08-14.
**Rejected.** A nested `QTabWidget`; a "View:" combo box.

### Full Series Aggregate does not write to disk
**Decision.** The Qt version renders the aggregate and saves nothing.
**Reason.** The Tk version called `save_show_results` as a side effect of
*viewing* it, which writes a series-level result into the library whenever
someone looks. A view should not change the data it is a view of, and the
aggregate is cheap to recompute.
**Date.** 2026-08-14.
**Rejected.** Keeping the save for parity.

### The composite is re-scored on read, never taken from cache
**Decision.** `MainWindow._cached` runs `rescore_episode` with the settings in
force; every screen goes through it, and a test fails if one calls
`load_cached` directly.
**Reason.** The composite is a weighted sum over numbers already measured, so
the weights in the cache file are whatever happened to be set when it was
written. The Qt build read the score straight out of the cache, which made
Settings' "Apply & Re-score" a no-op — the button promised exactly this call.
**Date.** 2026-08-14.
**Rejected.** Re-writing the cache on a settings change (it would invalidate
nothing but would rewrite every file for a presentation choice).

### A pipeline node opens the screen that does its stage's work
**Decision.** Double-clicking a node, or its inspector button, switches to that
tab. The stage → tab map is `STAGE_TABS` in `ui/main_window.py`; stages whose
screen is still Tk-only are listed in `STAGE_UNPORTED` and keep a **disabled**
button carrying the reason.
**Reason.** `CLAUDE.md` §4 makes the pipeline how a researcher sees what the
software is doing. A node that cannot reach the work is a picture of the
workflow, not the workflow.
**Date.** 2026-08-14.
**Rejected.** Opening the tab on single-click (selection is how you inspect a
node, so it cannot also navigate away); hiding the button when unported.

### The application has one research context, and it is named on screen
**Decision.** `analyzer/scope.py` holds a `Scope` — either the whole library or
exactly the episodes one documented draw selected. `MainWindow._scope` is the
current one; the Library filters to it and a **Showing:** chooser above the
tree always names it. Set by drawing a sample, by choosing a pipeline, or by
the chooser. **Not persisted across launches** — the application always opens
on the whole library.
**Reason.** Every screen answered "which episodes?" for itself, from the
Library tree selection. A sample could be drawn, documented and manifested and
no screen was any the wiser, so the researcher matched `selected.csv` against
the tree by hand. This is `design/CMAT_PIPELINE_INTERACTION_MODEL.md`'s Phase 2
("selection establishes the current research context") at the level the context
actually varies — a pipeline binds to one sample, so every node in it shares a
working set.
**Consequence.** A scope is a **view**, never a filter on the record: nothing
is deleted and no measurement changes. Because it can hide episodes, it is
always visible and always one click from *Whole library* — a filter the user
cannot see is a filter they will forget.
**Date.** 2026-08-15.
**Rejected.** Persisting the scope (opening on a narrowed library with no
memory of having narrowed it is the failure the control exists to avoid);
setting it from pipeline *node* selection (a document binds to one sample, so
nodes do not vary it, and single-click already means "inspect"); scoping the
Index and the measurement tabs in the same change — the Library was the ask,
and the rest is a separate piece of work with its own verification.

### The Index's Shows view is derived from its episode rows, not from `shows`
**Decision.** `db.summarise_shows()` builds show rows from whatever episode
rows are on screen. The Index uses it for both scopes; the stored `shows` table
is no longer read there.
**Reason.** Two reasons that arrived together. The stored table goes stale —
`upsert_show` runs on a whole-show analysis, so analysing episodes one at a
time never refreshes it, and this library's Spongebob row read
`episode_count = 2, avg_load = 0.3071` against five indexed episodes averaging
**0.2557**. And under a sample scope a stored whole-show aggregate answers a
question nobody asked. Deriving fixes both: the Shows view is a summary of the
Episodes view *by construction*, so they cannot disagree.
**Consequence.** `cli.py db --shows` and the Tk build still read the stored
table and can still show stale figures — recorded in `FOR_PAPER.txt` and
`TODO.md`. The derived view groups by the displayed show name and deliberately
does **not** normalise it, so an episode indexed with a raw relative path
(`Show/Season 1`) splinters into its own row and stays visible. Hiding it in a
summary would leave the index defect unfixed and unseen.
**Date.** 2026-08-15.
**Rejected.** Refreshing `shows` on every episode upsert (it makes a derived
table authoritative-by-habit and still leaves scoped views wrong); reading the
stored table under the library scope and deriving only when scoped — switching
scope would then change both the set and the arithmetic, making any difference
unattributable.

### One definition of what counts as an episode
**Decision.** `show_index.VIDEO_EXTENSIONS` — `.mp4 .mkv .avi .mov .wmv .m4v` —
is the single answer, matched on the lowercased suffix rather than by globbing.
`analyzer/sampler.py` imports it instead of keeping its own copy, and a test
asserts the two sets stay equal.
**Reason.** The sampler drew six extensions while `show_index` globbed
`*.mp4` in four separate places, so a documented sample could contain episodes
the Library never listed. Live in this working copy: a drawn `.mkv` that had
been measured **and indexed** — the sampler's path does not go through the
library walk — and was invisible on the screen that lists the corpus.
**Consequence.** More files count as episodes, so "n of m analyzed"
denominators move. Nothing is invalidated: the cache is keyed on show folder
plus filename stem, so existing results keep their keys and no aggregate
changes until a newly-visible file is analysed. Suffix matching also removes a
platform difference — `glob("*.mp4")` is case-sensitive on Linux and not on
Windows, so the same library listed differently depending on where it opened.
**Consequence, less comfortable.** The `.mp4`-only filter had been hiding a
duplicate. Making the corpus honest made the duplicate visible, which is the
right order but means `TODO.md` item 0 must be done before the next draw.
**Date.** 2026-08-15.
**Rejected.** Narrowing the sampler to `.mp4` (it would make existing manifests
undrawable); leaving the two definitions apart and describing the gap in the
interface, which was the interim state and only ever a caption on a defect.

### A validation subset is drawn, not chosen by CMAT
**Decision.** A sample's `selected.csv` is already a valid registry for the
sampler — it carries the `episode` column `load_registry_csv` requires plus
`filepath` — so a hand-coding subset is drawn **from** the sample with the
sampler, seeded and manifested like any other draw. `coding_target` on a
hand-code node stays advisory.
**Reason.** Which episodes get hand-coded is a sampling decision that belongs
in a manifest and a write-up. If CMAT picks them, the study acquires an
undocumented selection step.
**Consequence.** A subsample can only stratify by season/episode, because
`selected.csv` carries no custom columns. Writing the stratification columns
through is the fix when it is needed.
**Date.** 2026-08-15.
**Rejected.** Having CMAT choose N episodes for the subset; treating
`coding_target` as a filter.

---

## Interface

### The supplied design mockups are the source, used directly — not copied from
**Decision.** `ui/reference/*.css` is extracted verbatim and committed.
`ui/reference_css.py` resolves `var()` and returns a component's rules. The
HTML report emits the reference's own class names so its CSS applies unchanged.
**Reason.** Re-deriving the CSS by hand lost or changed something every round,
invisibly, until the two were put side by side.
**Date.** 2026-08-10.
**Rejected.** Transcribing values into the stylesheet (tried repeatedly; failed
repeatedly).

### Take the mockups' surfaces; take Windows' controls and behaviours
**Decision.** Standing rule for the whole port. Gradients, spacing and type
come from the mockups; caption controls, keyboard conventions, file dialogs and
window management come from Windows.
**Reason.** The mockups draw another platform's three round lights in
close-minimise-zoom order — reversed from Windows, meaningless to someone who
has not used that platform, and with no restore affordance.
**Date.** 2026-08-10.
**Rejected.** Cloning the traffic lights (built, then removed).

### The window draws its own title bar without giving up the native window
**Decision.** Keep the real Win32 frame styles and suppress only the frame's
*drawing*, via `WM_NCCALCSIZE`; hand hit-testing back through `WM_NCHITTEST`.
**Reason.** `Qt.FramelessWindowHint` strips `WS_THICKFRAME`/`WS_CAPTION` and
takes Aero Snap, edge resizing, the drop shadow, the maximise animation,
Win+Arrow and the system menu with it. This route costs none of that.
**Date.** 2026-08-10.
**Rejected.** `FramelessWindowHint`; and, earlier, refusing the custom title bar
altogether — that refusal was based on a cost that turned out to be avoidable.

### A dialog is a small window, not a differently-styled object
**Decision.** Dialogs use the same title strip, ground colour and accent as the
main window. One `WindowTitleBar` serves both.
**Reason.** The reference that disagreed introduced its own window colour, 22px
buttons and a second blue, and produced a screen matching nothing else.
**Date.** 2026-08-10.
**Rejected.** A per-dialog palette.

### One accent: `#429CE3 → #1066C7` on `#0F4F96`
**Decision.** Used everywhere including dialogs.
**Reason.** Two of the three reference files specify it. The period gel button
was luminous — a bright top falling to a mid blue over a dark-but-not-black rim
— and the alternative's `#003A70` is nearly navy, making a button read as
stamped out rather than lit.
**Date.** 2026-08-10.
**Rejected.** `#37A2E8 → #0066CC` on `#003A70`, from an extraction of GeminiStartingLayoutAlternative.html — superseded and no longer in `ui/reference/`.

### Report tables follow the mockup, not MediaWiki
**Decision.** `.data-table`: `#EAEAEA` headers, `#B8B8B8`/`#D0D0D0` borders,
`#F9F9F9` striping.
**Reason.** A MediaWiki treatment was built and reverted on sight — flat
`#F8F9FA` ground with centred headers read worse in this chrome.
**Date.** 2026-08-10 (built `0c1a4df`, reverted `aba6885`).
**Rejected.** `.wikitable` styling. The attempt is preserved in history if it is
ever worth revisiting.

### Destructive confirmations are the application's own dialog
**Decision.** `ConfirmDialog` in `ui/modal.py`. Cancel holds focus and is the
default; the confirming button is ordinary, not accented; Enter and Escape both
cancel. The detail line says what will **not** be lost.
**Reason.** `QMessageBox` defaults to the affirmative, so dismissing it with
Enter carries out the destruction.
**Date.** 2026-08-10.
**Rejected.** `QMessageBox.question`.

### Frame-accurate playback via VLC
**Decision.** `python-vlc` embedded in a Qt native window handle.
**Reason.** On Windows `QMediaPlayer` seeks to the nearest keyframe, so a coder
would record the wrong timestamp with no way to tell.
**Date.** 2026-08-10.
**Rejected.** `QMediaPlayer`/`QVideoWidget` — no extra dependency, but not
frame-accurate, and accuracy is the entire point of that screen.

### The starting-layout wizard offers every template, and shows a list
**Decision.** All seven registry templates as rows in one inset list box, with
the chosen row filled solid. Not the mockup's four cards.
**Reason.** Showing four would hide Mixed methods, Validation study and Blank
canvas, making the wizard a worse map of the tool than the tool is. A stack of
separately-bordered cards reads as a web page.
**Date.** 2026-08-10.
**Rejected.** Four option cards; a `QListView` with a delegate (rows carry
wrapped prose of very different heights).

### The wizard's first screen has Skip, not Back
**Decision.** Replace the mockup's Back button.
**Reason.** It is the first screen; there is nothing behind it, and a dead
control is worse than an honest one.
**Date.** 2026-08-10.
**Rejected.** A disabled Back button.

---

## Data and reporting

### The headline accuracy figure is the `ALL`-row boundary F1, not hard-cut only
**Decision.** The published figure is **F1 0.85 aggregate, range 0.75–0.91**,
type-agnostic at ±2 s, on the shipped `content-t27-diss` detector over two
coded episodes (CB 0.753, LB 0.910; pooled 103 TP / 14 FP / 21 FN). The
competing "0.84–0.96, aggregate ~0.91" is **superseded and deleted from the
code comments.** TransNetV2 (0.902 / 0.942, pooled 0.928) is reported
separately and never pooled with it.
**Reason.** The two figures were never rival measurements of one quantity: the
old pair is the **hard_cut-type-only** basis for the *same two runs* (0.841 and
0.964), and its aggregate additionally double-counted reruns across mixed
detector configs. Scoring on `ALL` is the honest basis because the tool is
scored against everything a coder marked, not just the category it handles
best — and it is the *lower* number. Settled by recomputing from the comparison
CSVs on disk rather than by choosing between notes; `local_hard_cut_f1()`
returns `('0.85', 2)`, reproducing the constants exactly.
**Date.** Basis changed 2026-08-08; contradiction traced and closed 2026-08-14.
**Rejected.** Quoting the higher 0.91; averaging the two detectors.
**Both logs.** Methodology in `validation/VALIDATION_LOG.md` (2026-08-08);
`ARCHITECTURE.md` §9 now names which runs the aggregate covers. The constants
were *misnamed* `REFERENCE_HARD_CUT_F1_*` until the rename below.

### The accuracy figure is named `boundary_f1`, and the export schema is versioned
**Decision.** `REFERENCE_HARD_CUT_F1_*` → `REFERENCE_BOUNDARY_F1_*`,
`local_hard_cut_f1()` → `local_boundary_f1()`, and the exported JSON keys
`hard_cut_f1` / `hard_cut_f1_source` → `boundary_f1` / `boundary_f1_source`.
**No deprecated alias is emitted.** Two keys added: `boundary_f1_basis`, which
states the estimand in words, and `provenance_schema`, now **2**. A file with
no `provenance_schema` key is schema 1, and its `hard_cut_f1` field holds this
same ALL-row figure despite the name.
**Reason.** The old name did not merely read vaguely — it named a real,
different quantity. The hard_cut-only F1 for the same two runs is 0.841 / 0.964,
so a reader who trusted the key got the wrong number with nothing in the file to
reveal it. Keeping a deprecated `hard_cut_f1` alongside the new key would have
re-published the misnomer in every new export, which is what the item existed to
stop. `boundary_f1_basis` is the durable half of the fix: a field name is a bad
place to carry an estimand, so the file now says what the figure is instead of
implying it.
**Migration.** Not a data migration. Nothing in CMAT parses the block back — all
four sites are writes (`gui.py`, `ui/main_window.py`) — and no exported JSON
carrying the key exists in this working copy. Exposure is limited to JSON files
already saved outside the repo; those stay readable and are now identifiable as
schema 1.
**Date.** 2026-08-14.
**Rejected.** Emitting both keys for a release (re-publishes the wrong name);
renaming internals only (leaves the lie in the artefact that actually leaves the
tool, which inverts the priority).

### Normalization ceilings are fitted to observed content, and dated
**Decision.** Retuned five of six ceilings on 2026-08-14 from 78 analysed
episodes: `cuts_per_min` 60→45, `color_saturation_mean` 1.0→0.85,
`motion_mean` 1.0→0.35, `flashing_events_per_min` 30→40, `audio_rms_mean`
0.2→0.35. `color_contrast_mean` stays 0.35 — already well matched. Motion was
additionally corrected in **every** preset (0.5/0.7/0.85/1.0 →
0.18/0.25/0.30/0.35). The age presets keep their own ceiling ladder otherwise.
**Reason.** Two opposite defects were live at once. Motion's ceiling was its
*theoretical* maximum of 1.0 while real video produces ~0.09, so a component
weighted 25% contributed ~7% of the composite — the weight said one thing and
the arithmetic did another. Flashing and audio ceilings sat *below* real
content, clamping the most intense episodes to an identical 1.0. Neither is
visible from a score; both are visible from the distribution.
**Migration.** Every composite already computed sits on the old scale. The
index was re-scored (13 of 15 rows; the two that did not are stale rows for
files outside the library root). The public site still publishes old-scale
figures — a separate, deliberate step.
**Provisional on purpose.** n=78, not a random sample, thin on live-action and
fast-cut content. `CEILINGS.md` records the basis, the limitations and the
triggers for revisiting; Settings now shows each metric's observed median and
maximum beside its input so the next revision is made against evidence.
**Date.** 2026-08-14.
**Rejected.** Fitting ceilings tightly to the corpus maximum (scores become
relative to 78 episodes and lose cross-library comparability, and one faster
show forces another migration); leaving motion wrong to preserve comparability
(the composite would keep contradicting its own stated weights).

### A show aggregate weights every episode equally
**Decision.** Every episode counts once regardless of length, **and the choice
is labelled on screen** rather than left to be inferred.
**Reason.** A show's profile is the profile of the episodes a viewer meets;
weighting by duration would let one feature-length episode speak for a season
of eleven-minute ones. Asked directly — "does a 45 minute episode contribute
more to that average than a 30 minute episode?" — and answered "keep it even
weighting, but add a label".
**Date.** 2026-06-28. Carried into the Qt show report 2026-08-10.
**Rejected.** Duration-weighted means.

### "Not analysed" and "failed" are different states
**Decision.** The show report distinguishes measured / failed / not analysed.
**Reason.** Reporting unanalysed episodes as failures describes work that has
not been done as work that went wrong.
**Date.** 2026-08-10.
**Rejected.** A single "excluded" count.

### The chart plots components, not the composite alone
**Decision.** Stacked contribution bars: height is the composite, segments are
what produced it. No threshold line, no banding, no colour meaning "high".
**Reason.** A bar of the composite alone repeats a number the report already
gives in larger type, and hides that two episodes reaching 0.24 can reach it
completely differently.
**Date.** 2026-08-10.
**Rejected.** A single-bar-per-episode composite chart.

### The Index never shows a target age
**Decision.** `target_age_min` / `target_age_max` exist in the shows table from
the metadata importers and are excluded from every column list, with a test.
**Reason.** A target audience age is a claim about the viewer. See the
stimulus-only decision above.
**Date.** 2026-08-10.
**Rejected.** Showing them as imported metadata.
