# CMAT — Decision log

Real decisions and why they were made. Bugs and mistakes belong in
`LEARNINGS.md`, not here.

Format: **decision** · reason · date · what was rejected.

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
**Decision.** `Toddler (0-2)` names the literature the ceilings come from, not
an audience the show is suitable for.
**Reason.** Researchers need comparison ranges; presenting them as suitability
would be the verdict the tool refuses to give.
**Date.** Foundational.
**Rejected.** Dropping age names entirely — they are the clearest label for the
range, provided the framing is explicit.

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
**Rejected.** `#37A2E8 → #0066CC` on `#003A70` from `welcome.css`.

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
