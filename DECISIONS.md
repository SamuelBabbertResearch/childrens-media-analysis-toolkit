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

### The measurement model's six shaping decisions, answered
**Decision.** `MEASUREMENT_MODEL.md` §7 listed six open decisions that had to
be settled before the data model was written. All six were put to the author
on **2026-08-16** and answered; the section now records the answers rather
than the questions. In brief:

1. **Recipes live with the library**, `<root>/.analysis/recipes/`, travelling
   with the research data as pipelines do and reusing
   `analyzer/pipeline_graph.py`'s conventions — including the re-homing rule
   that file already had to grow. Portability between projects comes from
   export/import (§4.7), not from the storage location.
2. **The existing sensory-load composite becomes a recipe — locked.** It is
   expressed in the model as "Sensory load (as shipped)" and must reproduce
   today's numbers exactly. It is not editable in place. **Expressing it is
   not changing it**, and the distinction is the whole point: the public index
   is built on this composite, so an edit breaks comparability with every
   score already computed and published, while an expression puts its
   underived defaults on the record as an operationalization.
3. **A stale flag attaches to one episode result per recipe version.** The
   finest honest unit, and the one `cache.is_stale()` already works at, so a
   recipe over twenty episodes reports "12 current, 5 stale, 3 predate
   fingerprinting" instead of going red as a whole. The existing
   grandfathering rule carries forward unchanged.
4. **A recipe PINS its parameters.** The single most consequential of the six.
   A recipe stores its own frozen copy of every parameter value, so reopening
   it next year gives the same numbers and an exported recipe carries its
   settings with it.
5. **Presets stay scoring-only; recipes own measurement.** Presets keep doing
   what they already do — weights and normalization ceilings, re-scorable from
   cache. Recipes own the measurement side and the composite definition.
6. **A citable identifier is a friendly sequential version PLUS a content
   hash, both stored.** "Pacing — conservative v3 (a7f3c9d1e204)".

**Reason.** Taken together these keep a saved operationalization *fixed*.
Decisions 4 and 6 are the pair that matter: a version number that can silently
denote different behaviour is not citable, and a hash nobody can pronounce is
not usable in prose.

**Rejected, and why the rejection matters.** *Referencing the live config*
(4) is the tidier engineering answer — one source of truth, no drift between
two places — and was rejected because it makes every saved recipe mutable
behind the researcher's back: a study written up last month would no longer
describe what its recipe now does. The cost accepted in exchange is real and
must be handled rather than forgotten: a threshold can now live in two places,
so **a recipe has to say plainly when its pinned value differs from the live
Measurement settings**. Also rejected: making the composite editable like any
other recipe (2), which trades published comparability for consistency;
folding presets into recipes outright (5), which would migrate every saved
`config.json` and turn the age-named reference ranges into recipes answering a
different question; and a bare content hash (6).
**Date.** 2026-08-16.

### The measurement model reads the registry; it never restates it
**Decision.** `analyzer/constructs.py` holds constructs, aspects, measures and
the resolution of a measure to a number, but holds **no list of detectors**.
Automated methods are *generated* from `analyzer/measurements.py` — one method
per `ToolSpec` — and each carries the status read from its `ToolSpec` at
generation time. A detector added to the registry appears as an available
method with no other edit.
**Reason.** `MEASUREMENT_MODEL.md` names this phase as exactly where a second
list of detectors would get written by accident (`LEARNINGS.md` shape 3 — a
claim restated instead of read), and the project has already published two
contradictions that started that way. Generating rather than declaring makes
the restatement impossible rather than discouraged.
**How it is held.** `tests/test_constructs.py
::test_a_detector_added_to_the_registry_appears_as_a_method` injects an
invented `ToolSpec` into the registry and asserts it shows up here;
`::test_a_methods_status_comes_from_the_registry_not_from_this_module`
downgrades a validated tool and asserts the unvalidated flag follows.
**Rejected.** Declaring each measure's methods explicitly, which reads more
clearly at the definition site and is precisely the drift this project keeps
paying for.
**Date.** 2026-08-16.

### Hand coding is a method with its own status word, not an "unvalidated" one
**Decision.** Hand-coded methods carry `constructs.HUMAN_CODED_STATUS`
("human-coded"), deliberately outside the registry's
validated/experimental/unvalidated vocabulary, and carry no unvalidated flag.
**Reason.** Those three words grade an automated tool *against hand coding*,
which is a meaningless question to ask of hand coding itself. Reusing
"unvalidated" for it would render on screen as "worse than validated" and
contradict `CLAUDE.md` §2.5: automated measurement is not inherently more
valid than human coding. Hand coding's real limitations are different ones and
are carried on the method's notes instead — whole-second quantisation, the
±2 s floor that follows from it, and single-coder status.
**Date.** 2026-08-16.

### A hand-coded value is refused when the coded window is unrecorded
**Decision.** Every span-dependent hand-coded value — every rate, and every
shot-length statistic — resolves only when the coded window is recorded on
disk (persisted hand-coded metrics, or a comparison manifest) or supplied
explicitly by the caller. Otherwise the answer is a refusal naming the reason.
**The episode's duration is not an acceptable substitute.**
**Reason.** Hand coding in this corpus is *segment* coding — the two validated
episodes are the first ~5 minutes of each. Dividing a partially coded sheet by
the full runtime produces a number that looks exactly like a measurement. It
was doing so: see `LEARNINGS.md` § *A coded segment divided by the whole
runtime*.
**Rejected.** Falling back to the runtime with a warning attached. A warning
beside a wrong number is how this project published a flashing claim and an F1
figure it had to correct; the number has to not exist.
**Date.** 2026-08-16.

### A recipe's pin is enforced, not merely stored
**Decision.** `recipes.evaluate()` compares a binding's pinned parameters
against the parameters that actually produced the cached number, and **refuses
that part when they differ** — reporting the real number alongside the refusal
rather than hiding it. `recipes.divergences()` separately reports where a
recipe's pinned values differ from the live Measurement settings.
**Reason.** Decision 4 (a recipe pins) is a claim about what a saved
operationalization *means*. If a recipe pinned to threshold 27 will happily
report a number measured at threshold 30, then it does not describe an
operationalization at all — it is a preset with a version number on it, and
citing it says nothing. The refusal is what gives the pin content. The
divergence report is the other half, and was the condition attached to
accepting pinning: a threshold now lives in two places, so a recipe must say
so out loud.
**A divergence is not an error.** It is the ordinary state of a recipe saved
before a settings change, and it means the recipe still describes what it
always described. Nothing warns, blocks or auto-updates.
**Rejected.** Re-deriving the value under the pinned parameters on the fly —
which would mean re-analysing video inside what should be a read, and would
quietly manufacture numbers that were never measured.
**Date.** 2026-08-16.

### A recipe pins measurement dependencies, not only the named method's fields
**Decision.** A motion binding pins both its motion method and the shared frame-
sampling method/rate. The dependency parameters are stored with namespaced keys
(`sampling.tool`, `sampling.sample_fps`), included in recipe identity, shown in
the recipe screen, compared with live settings, and checked against cached
provenance. The study-clip workflow constructs its measurement configuration
from those pins and embeds the complete recipe snapshot in its manifest.
**Reason.** Frame-difference motion depends on the gap between consecutive
sampled frames. A recipe that pins `absdiff` but silently follows a later change
from 2 fps to 5 fps does not preserve the analysis it cites. The same principle
applies to colour because it uses the shared sampling pass, although the current
study uses motion and not colour.
**Rejected.** Recording only a recipe name beside a run that still follows live
Measurement settings. That is provenance labeling, not reproducibility.
**Date.** 2026-08-17.

### A recipe's missing-data behaviour is a stated policy, per measure
**Decision.** Three policies: `refuse` (the default — the composite produces no
score), `omit` (drop the part, do **not** redistribute, and report the smaller
scale the score now sits on), `redistribute` (spread the weight proportionally
over the parts that resolved). An `Evaluation` always carries the **effective**
weights and every part including the refused ones.
**Reason.** The existing composite already redistributes — audio's weight
across the visual metrics on a silent episode — and reading the nominal weights
while the engine used redistributed ones made a breakdown 0.057 short of the
score printed above it (`LEARNINGS.md`). Making the behaviour a per-measure
choice rather than one hard-coded rule is §2.5's "never hard-code one correct
measurement", and carrying effective weights on the result is what stops the
old defect recurring in a new place. `refuse` is the default because a
composite missing one of its parts is not that composite.
**Date.** 2026-08-16.

### Version 1 is the recipe as first SAVED, and a duplicate starts its own history
**Decision.** `save_recipe` finalises the v1 content hash while a recipe is
still at version 1 with its single creation record. `duplicate_recipe` does not
inherit the original's history; its first record names the source recipe's
citation instead.
**Reason.** A recipe is normally created, then configured, then saved, so a
hash recorded at creation describes a half-built object — and nobody can cite a
version that never left memory. On duplication, carrying the history across
would let a copy claim a provenance it does not have: those versions are
records of a different operationalization's past, and a citation that resolves
to the wrong lineage is worse than no lineage.
**Date.** 2026-08-16.

### A recipe import reports what it cannot resolve and substitutes nothing
**Decision.** `import_recipe` returns `(recipe, gaps)`. An unresolvable
construct, measure or method becomes a named `ImportGap`; the binding is kept
**intact** rather than stripped or repaired.
**Reason.** A recipe referencing a detector the importing install does not have
is a real and expected case (`MEASUREMENT_MODEL.md` §4.7). Substituting a
default would change what the recipe measures while leaving its name, version
and content hash's *appearance* of authority intact — the most damaging thing
this module could do, and a direct descendant of the published-contradiction
defects in `LEARNINGS.md`. Keeping the binding means nothing is lost and a
re-export from a machine that *does* have the detector round-trips.
**Date.** 2026-08-16.

### The shipped composite is expressed as a locked recipe, built from `config.json`
**Decision.** `recipes.shipped_composite(config)` returns "Sensory load (as
shipped)": the six inputs, their reference ranges, their weights, the additive
form, 4-decimal rounding, clamping, and audio redistribution — assembled from
`config.json`'s `sensory_load_weights` and `normalization_reference_ranges`
rather than from constants in the module. It ships `locked=True`.
**Reason.** It is the strongest available test that the model is expressive
enough: holding pacing proves little, holding a composite the project already
publishes proves a lot. And it converts the composite from an algorithm into an
inspectable, content-hashed claim — the 2026-08-14 ceiling retune moved every
score in the project silently, and under a recipe that is a visible version
change instead.
**Built from the config, not restated**, because a second copy of those numbers
would have been wrong within one edit — which is `LEARNINGS.md` shape 3, and
the retune is the proof it happens here. `test_shipped_composite.py` asserts
the recipe's bindings cover exactly the keys `sensory_load_weights` declares,
so adding a seventh component cannot leave the recipe scoring six.
**It changes nothing, and that is verified, not asserted.** The recipe
reproduces `compute_sensory_load` exactly on all 14 cached episodes in the
working copy, and reproduces `effective_weights()` for the silent-episode case
no real episode there exercises.
**It derives nothing, and that has to travel with it.** The weights, ceilings
and additive form remain underived (`ARCHITECTURE.md` §8.1a). The recipe's
`notes` and the `sensory_load` construct's `grounding` both say so in those
words, and a test fails if either stops saying it — because the danger of
naming a construct is precisely that it reads as a justification.
**Locked** because the published index is built on it: `save_recipe` and
`delete_recipe` refuse it, and duplicating is the sanctioned route to
exploring alternatives.
**Rejected.** Hard-coding the composite's numbers in `recipes.py` (a second
source of truth); leaving it editable (breaks comparability with every
published score); and leaving it unexpressed (the model would ship never having
been tested against the one real composite this project has).
**Date.** 2026-08-16.

### A measure can require an availability flag before its value counts
**Decision.** `AutomatedSource.available_path` names a boolean that must be
true for a value to resolve. `audio_rms_mean` gates on `audio.available`; the
three speech measures gate on `speech.available`.
**Reason.** Those blocks carry 0.0 defaults whether or not the pass ever ran.
An episode with no audio track and an episode measured at silence are different
facts, and so are an episode with no captions and one where nobody speaks —
four of the fourteen cached episodes here have no speech block at all. This is
the same distinction `event_coding`'s publish guard already protects on the
hand-coding side, applied to the automated side.
**Consequence that matters for the composite:** it is what lets the recipe
reproduce the engine's audio redistribution. The engine keys redistribution off
`audio.available`; the recipe keys it off the audio part failing to resolve,
which is the same condition expressed in the model's own vocabulary.
**Date.** 2026-08-16.

### The Recipes screen has no summary view, and pinned values are not editable in place
**Decision.** `ui/recipes.py` shows every binding's method, pinned parameter
values, transform, reference range, weight and missing-data policy on the same
screen that names the recipe — there is no collapsed or summary presentation.
Pinned parameters appear as read-only text beside an explicit **Re-pin**
button rather than as editable fields.
**Reason.** "A recipe is inspectable or it is not a recipe" (`CLAUDE.md` §2.5)
is a property of the screen, not only of the file: a name standing in for
settings the researcher cannot read is exactly what this phase exists to
remove, and a summary view is how that creeps back. Pinned values are
read-only because editing one in place would silently make the recipe describe
parameters no cached result was produced under — the recipe would then refuse
its own episodes with no visible cause. Re-pinning is the same operation with
a name on it, and it is the honest response to a divergence.
**Also decided:** Save is disabled until a reason is given whenever the
content hash changed, and the disabled Save states which. The screen does not
get to skip `bump_version`'s rule.
**Rejected.** Editable parameter fields (indistinguishable, to the user, from
changing the measurement settings, which they are not); and a compact list
view with a details pane behind a click.
**Date.** 2026-08-16.

### The construct diagram is a VIEW of a recipe, and it is called Constructs
**Decision.** The visual construct feature is a second view of the recipe that
already exists — not a new object, not a new file format, not a second place
that says how a measurement was made. `ui/constructs_tab.py` reads
`analyzer/recipes.py` and writes nothing. The tab is named **Constructs**.
**Reason for the view.** The shipped composite already binds six measures
across five constructs with a weight each; that IS a construct diagram, stored
as a form. Making it a separate object would give two things that both claim
to describe one operationalization — `LEARNINGS.md` shape 3, and the exact
trap §7.5 flagged for presets versus recipes. As a view it inherits one save
path, one content hash and one version history for free.
**Reason for the name.** It parallels Pipeline: both name the thing being
drawn. **Measurement** was rejected outright — `CLAUDE.md` §3 reserves that
word for the pipeline STAGE, and Automated coding is already that stage's
work, so two tabs would compete for one word. *Recipes* names the storage
object rather than the view and says nothing about measurement to someone
reading the tab strip cold; it remains the name of the object and of the
File menu dialog. *Operationalization* is exact and too heavy for a tab.
**Date.** 2026-08-16.

### The construct canvas is typed, and that is what keeps it inside §6
**Decision.** `MEASUREMENT_MODEL.md` §6 says "do not build a generic node
editor". A construct canvas is permitted under that rule **only while it stays
typed and constrained**: a method attaches to a measure, a measure to a
construct, and only a composite takes weighted inputs. There is no
construct-to-construct edge in the model and none is drawn — the construct
lanes are a grouping, not a chain.
**Reason.** §6 forbids a free-form connect-anything surface, which would stop
this being a measurement system and start it being a diagram tool. The typing
is the whole difference, so it is written down rather than left as an
implementation habit: if this ever becomes "drag any box onto any box", it has
become the thing §6 forbids.
**Consequence for the unbuilt authoring step.** If constructs are ever
authored on this canvas, constructs and aspects may be free-form but
**measures may not** — a measure has to come from a palette of things that
actually resolve to a number. A user-defined measure with no data path is
`LEARNINGS.md` shape 2, which is the defect the whole phase exists to remove,
reintroduced through a nicer interface.
**Date.** 2026-08-16.

**Amended the same day: a contributing construct IS drawn as its own block.**
The first build rendered constructs as lane HEADINGS, on the stated grounds
that "there is no construct-to-construct edge in the model and drawing one
would invent a relationship". That reasoning was too strict, and the author
asked for the blocks. The edge is **derived, not invented**: a recipe binds
measures, each measure belongs to a construct, and a construct block's weight
is the SUM of its own measures' weights. Summing is legitimate here for a
specific reason — contributions to a composite are all fractions of one score,
so colour saturation's and colour contrast's add up to what colour
contributed. It is not averaging across methods, which the model still
refuses: these are different measures, each by its own single pinned method.

Two things keep the amendment honest. The sum is a **summary of stored facts,
not a stored fact** — nothing writes it back to the recipe. And a construct
block appears **only where it differs from the recipe's own construct**, so a
single-construct recipe stays two columns instead of growing a Pacing block
hanging off a Pacing target, which would be a self-edge dressed up as
structure. `tests/test_ui_constructs_tab.py
::test_a_single_construct_recipe_grows_no_self_edge` pins that.

### The diagram draws contribution share, and has no arrowheads
**Decision.** Wire thickness carries the **contribution share** —
`weight × normalised value ÷ score` — once contributions are computed, not the
declared weight and not the redistributed effective weight. Connectors carry
**no arrowheads at all**.
**Reason for the share.** The three quantities are different and only the
share answers a reader's actual question. `ARCHITECTURE.md` §8.1a could only
state in prose that a measure's declared weight is not what it contributed;
drawn, it is the first thing you see. Effective weight was tried first and
rejected on evidence: it is identical to the declared weight whenever nothing
is missing, so the wires did not move at all and the feature delivered nothing.
**Reason for no arrowheads.** An arrow between two boxes reads as causation to
almost every reader, and `CLAUDE.md` §2.2 is absolute. Nothing flows along
these connectors — a measure does not produce a construct, it stands in for
one. This is also the artefact most likely to be shown detached from its
caption, which is exactly when an arrowhead would do its damage.
**Also decided:** the share is a ratio of means rather than a mean of ratios,
because a near-zero-scoring episode makes every per-episode ratio volatile.
**Date.** 2026-08-16.

### Authoring on the canvas: the four shaping decisions, answered
**Decision.** `TODO.md` item G listed four decisions that had to be settled
before authoring was written, each of which changes what gets stored. All four
were put to the author on **2026-08-16** and answered. They are recorded here
in full because the precedent — `MEASUREMENT_MODEL.md` §7's six — is what
stopped the data model being written twice in August.

**1. User-defined constructs live with the library**, in
`<root>/.analysis/constructs/`, beside the recipes that reference them and
following the same conventions `pipeline_graph.py` established, including
re-homing. A construct travels with the research data it describes.

*Reason.* Recipes already live with the library (§7.1), and a construct is
referenced BY recipes — storing the two in different places is how a library
handed to a collaborator arrives with every construct key dangling. The
portability half is already built and does not need the storage location to
solve it: `export_recipe` embeds each construct's name, definition and
grounding **alongside** the key, and `import_recipe` reports an unresolvable
construct as a named `ImportGap` rather than substituting one. So a recipe sent
to another install carries a readable account of what it measures even where
the definition itself cannot follow.

*Accepted cost, stated rather than discovered later.* Two researchers on two
libraries each get their own "Narrative complexity" and nothing reconciles
them. That is the same cost §7.1 already accepted for recipes, and the same
answer applies: reconciliation is export/import's job, not storage's.

*Rejected.* **With the application** — constructs would follow the researcher
across libraries but not travel with the data, which makes §4.7's import gap
the normal case instead of the exception. **Inside the recipe file** — no
dangling reference is possible, but one construct used by three recipes is
stored three times, and a construct could not exist before a recipe used it,
which makes "define the construct, then decide how to measure it" impossible to
do in that order. That order is the entire point of §1.

**2. A construct is content-hashed, and a redefinition is reported as a
divergence — not a new recipe version.** The hash covers definition, grounding
and aspects; **not the name**, so renaming a construct is free, exactly as
renaming a recipe is. A recipe records the construct hash it was authored
against, stored **beside** its own content hash and deliberately **not inside
`Recipe.canonical()`**. Recipes citing a redefined construct report that the
construct has been redefined since they were written. Nothing blocks, warns or
auto-updates.

*Reason.* Redefining what a construct means changes what every citing recipe
claims to measure, and `MEASUREMENT_MODEL.md` §6 forbids letting old results
silently look current. But putting the construct hash inside the recipe's own
hash would mean editing one construct silently bumps every citing recipe's
version — without the reason `bump_version` requires, which is the one field
that cannot be reconstructed afterwards. Recording it beside the hash gets the
detection without corrupting the version rule. The divergence shape is not new:
it is exactly what pinned parameters already do, and `DECISIONS.md` §*A
recipe's pin is enforced* already establishes that **a divergence is not an
error** — it means the recipe still describes what it always described.

*Rejected.* **Full version history on constructs**, mirroring recipes — the
most rigorous answer, and the reason for a redefinition is genuine paper
material, but it is a second versioning system to keep in step with the first
and it puts a required-reason modal in front of fixing a typo in a definition.
**No versioning at all** — cheapest, and precisely the failure §6 names: a
citation resolving to a construct that now means something else, with nothing
anywhere recording that it moved.

**3. Node positions persist in a sidecar**, `<recipe id>.view.json` beside the
recipe, keyed by recipe id and deleted with it. It never enters the recipe file
and never enters `content_hash()`. A missing sidecar means auto-layout, so an
absent one is not a broken state.

*Reason.* Dragging a box must not create a version or demand a written reason,
which item G already stated. The sidecar gets that by construction rather than
by remembering to exclude a block. The decisive argument is the locked recipe:
`save_recipe` refuses the shipped composite, so a layout stored inside the
recipe file could never be saved for the one diagram most likely to become a
methods figure.

*Rejected.* **A `view` block inside the recipe file**, excluded from
`canonical()` — one file instead of two, but it makes moving a box rewrite the
file whose entire value is that it changes only when the operationalization
changes, and it cannot store a layout for the locked composite at all.
**Auto-layout every time** — nothing to store or invalidate, but a researcher
who arranges a diagram for a figure loses it on close.

**4. A composite may NOT contain another composite.** One level: a composite
binds measures. Construct blocks on the canvas stay **derived** from those
measures' constructs, as they are today.

*Reason.* "Combine different constructs" is already satisfied flat, and the
proof is shipped: the sensory-load composite binds six measures across five
constructs, and the canvas derives a block per construct from them. That IS
combining constructs. Nesting would make contribution share a recursive
computation and staleness a graph problem rather than an edge — buying
complexity the stated goal does not need. Saying no now is reversible; saying
yes is not, because saved nested recipes would then exist.

*Rejected.* **One level of nesting** (contribution share becomes two-level and
an inner recipe's change has to propagate staleness outward) and **arbitrary
depth** (cycle detection, recursive share, graph staleness — and a canvas that
has become the generic node editor §6 forbids).

### Where authoring lives, and what shape it takes
**Decision.** Two interface-shape questions, put to the author on
**2026-08-16** when G2 was built and answered then. Neither changes what is
stored, which is why they were asked briefly rather than blocking the way the
four above did.

**1. Construct creation lives in ONE shared editor, reached from two places.**
`ui/construct_editor.py` holds `ConstructEditor` (one construct) and
`ConstructPicker` (the library's constructs, shipped and researcher-defined).
The Constructs tab opens it from a **Constructs…** button; the Recipes
dialog's New menu offers **New construct…** at the foot of its list and, on
accepting, creates a recipe over what was just defined.

*Reason.* The Constructs tab is the screen named for constructs and is where
the rest of authoring happens, so creation belongs there. But the Recipes New
menu is where a researcher actually runs out of constructs — it is the list
they are reading when they discover the one they want is not in it — and a
dead end there would send them somewhere else to look for the door. Two entry
points, one dialog: `CLAUDE.md` §6's rule about a function existing in more
than one build applies just as well to a form existing on two screens.

*Rejected.* **The Constructs tab only** — simplest surface, and it leaves the
Recipes menu a dead end. **The Recipes dialog only** — creation beside the
recipe list is where the route starts, but the screen named for constructs
would then be unable to define one.

**2. The canvas edits the selected recipe IN PLACE, behind an Edit toggle.**
Same canvas, same recipe chooser. Edit swaps panning for box-dragging, reveals
the measure palette and the reason-and-Save bar, and turns off again.

*Reason.* Without a mode the same drag gesture means *pan the canvas* over the
background and *move a box* over a card, which is ambiguous exactly where the
two are adjacent. The mode also stops an accidental drag on the locked
composite reading as editing something that cannot be saved — the boxes there
do move, deliberately, but nothing else does, and the banner says so. In
place rather than in a second screen because two views of one recipe are two
things to keep in step, which is the duplication shape this project keeps
paying for.

*Rejected.* **Always editable** — fewer controls, but the canvas stops being a
quiet reading and figure-export surface and panning needs another gesture.
**A distinct authoring screen** — cleanest separation, most duplication.
**Date.** 2026-08-16.

### A locked recipe cannot be written to the library at all
**Decision.** `save_recipe` refuses on the LOCK alone. It previously also
required the recipe to have an existing file, so the *first* save of a locked
recipe was allowed. An imported recipe now arrives **unlocked** whatever its
file says.
**Reason.** The guard missed the one recipe it exists for. The shipped
composite is generated from the config in force rather than loaded, so its
`path` is None and a save was accepted — writing a stored copy of a recipe
whose entire value is that it follows Scoring settings. That copy would stop
following them: the 2026-08-14 ceiling retune moved every composite score in
the project, and a stored snapshot would have gone on describing the old ones
under the same name. Unlocking on import is the other half: a lock is a claim
about *this* install ("results here already depend on this"), and nothing
published here was produced by a recipe that just arrived from elsewhere —
carrying a foreign lock in would make an imported composite unsaveable, which
is the one thing an import has to be able to do.
**Date.** 2026-08-16. Found by trying it while driving canvas authoring;
`tests/test_shipped_composite.py` now asserts the opposite of what it did.
**Rejected.** Leaving it, on the grounds that no screen does it — the guard's
own docstring claims a protection it did not provide, and the next caller
would have believed it.

### The shipped composite has a stable id
**Decision.** `recipes.SHIPPED_COMPOSITE_ID`, rather than a fresh uuid on each
generation.
**Reason.** The layout sidecar is keyed by recipe id and has to be found again
next session. A generated object still needs a stable identity to hang
anything off, and this is the diagram most likely to become a methods figure —
the case decision 3 above turns on. The id is outside `canonical()`, so no
hash, citation or published number moves.
**Date.** 2026-08-16.

**Three rules carried in from `TODO.md` item G, unchanged and not reopened:**
the canvas stays **typed**; **constructs and aspects may be free-form,
measures may not** — a measure comes from a palette of things that resolve to a
number, because a user-defined measure with no data path is `LEARNINGS.md`
shape 2 reintroduced through a nicer interface; and writes go through
`recipes.save_recipe`, a changed operationalization still needs a reason, and
the shipped composite stays locked.
**Date.** 2026-08-16.

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

### The sampler's content-type selector is presentation only; the engine never changed
**Decision.** `ui/sampler.py` gained a Content type selector — TV show /
Movies / YouTube videos (already downloaded) — that changes the browse
button's text and tooltip, the folder-dialog title, the preview table's
"Season"/"Episode" column headers ("Group"/"#" for non-TV), and the "By
season" stratify label ("By group"). `analyzer/sampler.py` was not touched
beyond two new `TOOLTIPS` entries: `scan_entry_root()`, `load_registry_csv()`,
`sample()` and `write_outputs()` already worked for any flat or grouped
folder, any nullable `season`/`episode`, and even a registry row with no
`filepath` (a fetched-but-undownloaded item) — verified by reading the
engine, not assumed.
**Reason.** The sampler only *read* as TV-only; a folder of movies or
already-downloaded YouTube videos already sampled correctly, just under
"show"/"season"/"episode" framing that doesn't fit. Relabeling the five or six
places that actually mislead (the folder-picker copy, the two fixed preview
columns) closes that gap without touching a working, already-generic engine.
**Date.** 2026-08-17.
**Rejected.** A live YouTube channel/playlist fetch via `yt-dlp` (absorbing
the disconnected `sample_youtube.py` script) — real, separate engineering
(network calls, an undownloaded-episode UX, a download-after-sampling
workflow), deferred to `TODO.md` item 9 rather than folded into a relabeling
pass; renaming the dialog itself ("Episode Sampler"), the toolbar button, or
the Sampling pipeline node — wider blast radius for no functional gain, since
the structural TV-only parts were the folder-picker framing and two columns,
not the dialog's name.

### YouTube gets a real scan function after all: `scan_youtube_folder()`
**Decision.** Corrects the entry above, same day. Pointed out directly: the
YouTube content type called the identical `scan_entry_root()` as Movies, so
it extracted nothing a generic flat-folder scan couldn't — "YouTube" in name
only. `analyzer/sampler.py` gained `scan_youtube_folder()`, which reads a
yt-dlp `<file>.info.json` sidecar beside each video when present (upload
date, title, channel, video id, URL) and is otherwise identical to
`scan_entry_root()`. The preview table's date column is also now
content-type-specific: "Air date" (tv) / "Release date" (movies) / "Upload
date" (youtube) — the direct ask, on the same `Episode.air_date` field.
**Reason.** Checked this project's own real YouTube content
(`Shows/Game Theory/`, `Shows/iShowSpeed/`) before designing anything: plain
filenames, no sidecars. So the honest scan result for the library this
project actually has is unchanged either way — verified,
`scan_youtube_folder()` on `Shows/Game Theory/` produces a result identical
to `scan_entry_root()`'s, field for field. The sidecar path exists for
`--write-info-json` downloads (a standard yt-dlp option) and for `TODO.md`
item 9's eventual fetch-then-download workflow, which would produce exactly
this shape. `extra["channel"]` also falls out of the sidecar for free and
becomes a real stratify option through the mechanism already built for
registry CSVs — no new UI concept.
**Date.** 2026-08-17.
**Rejected.** Inferring an "upload date" from the video file's mtime/ctime —
that is the *download* date, not the upload date, and a wrong-but-plausible
date under a real-sounding label is worse than a blank field admitting it
doesn't know (`CLAUDE.md`'s core anti-pattern: a wrong number that displays
correctly). Also rejected: offering `video_id`/`url` as stratify axes — every
value is unique, so grouping by either is one episode per stratum, not a
real design.

### Live YouTube fetch reuses the eras system unchanged, under a namespaced key
**Decision.** `analyzer/youtube_fetch.py` (new) shells out to `yt-dlp
--flat-playlist` for a channel or playlist's video list — title, upload
date, duration, channel, playlist — with no download, retargeted from the
now-retired `sample_youtube.py` at real `Episode` objects. `ui/youtube_fetch.
py`'s `YouTubeFetchDialog` runs it on a worker thread (a real channel can
take 30-60s; the interface must not freeze) and accepts several playlist
URLs at once, tagging each result `extra["playlist"]` — the fetched episodes
plug into the *already-generic* `stratification_columns()` mechanism with no
new UI concept, the same way `channel` already did for the sidecar reader.
Content type = YouTube now shows three source buttons at once — Fetch,
Choose Downloaded Folder, Load Registry CSV — because a new user shouldn't
need to already know live fetching exists to find it.

For time-era stratification: `SamplerDialog._show_key()` returns
`f"youtube:{fetch_id}"` for a live-fetch source instead of falling back to
`""`. Nothing else about the eras system changes — `analyzer.eras.
assign_eras()` was already a pure function over `Episode.air_date` needing
no database or folder, and `get_show_eras`/`save_show_eras` already treat
`show_key` as an arbitrary string. A researcher who fetches the same channel
again next session gets their era definitions back, the same guarantee a TV
show already has — for free, by reusing the existing `ErasDialog` unchanged.
**Reason.** Thought through end-to-end how a new user would actually sample
a channel like Game Theory: today's folder/registry-only sampler cannot help
someone who hasn't downloaded anything yet — the entire point of sampling
before downloading. "10 years of Game Theory" needs eras for the same reason
"40 years of Sesame Street" already does (2026-07-01) — the folder-less
source was the only real gap in an otherwise-complete existing system.
**Date.** 2026-08-17.
**Rejected**, per discussion: download automation (calling yt-dlp to fetch
the sampled videos from inside CMAT) — the drawn manifest/`selected.csv`
with each row's URL is the complete deliverable this pass; downloading is
left entirely to the researcher. An ad hoc, non-persisted eras path for
fetched channels — unnecessary once a namespaced key lets the real,
persisted system apply unchanged. Keeping `sample_youtube.py` alongside the
new module — two places doing the same fetch is the exact drift `LEARNINGS.
md` warns about; deleted once its logic was absorbed.

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
right order but meant the Spongebob show-level aggregate needed recomputing
before the next draw — done 2026-08-17, see `FOR_PAPER.txt`.
**Date.** 2026-08-15.
**Rejected.** Narrowing the sampler to `.mp4` (it would make existing manifests
undrawable); leaving the two definitions apart and describing the gap in the
interface, which was the interim state and only ever a caption on a defect.

### The scope STAGES a measurement screen; it does not filter one
**Decision.** `AutomatedTab.set_scope()` puts the current sample's episodes into
the analysis queue and names where they came from. It does **not** stop the
screen acting on anything else: the Library can still send it an out-of-scope
episode, and Analyze still runs whatever the queue holds. Changing scope
withdraws only what the *previous* scope staged, so a hand-queued episode
survives. A **Queue Scope (N)** button re-stages after a run or a Clear Queue,
and is disabled — with the reason — under the whole library.
**Reason.** The Library and the Index are views, so a scope narrows them. A
measurement screen is not a view; it is where work is started, and the useful
thing to do with "these twenty episodes" is to have them ready to run. Filtering
here would be the wrong verb twice over: it would forbid work the researcher is
entitled to do, and it would leave the queue — the thing `_start` actually hands
the worker — still empty.
**Consequence.** The whole library is deliberately **not** staged. Queueing 137
episodes because the application opened is not a working set, and it would make
Analyze a much larger action than it looks.
**Consequence, watch this one.** An unlinked pipeline still inherits whatever
scope was current, by the existing rule that it has "no opinion about which
episodes". That was cheap when the scope only hid Library rows; it now
pre-fills a run queue from another study's sample. It stays visible — the
Showing: control and the queue's own note both name the sample — but see
`TODO.md`.
**Date.** 2026-08-16.
**Rejected.** Filtering the queue to the scope (forbids legitimate work and
still leaves nothing staged); staging on tab activation rather than on scope
change (the queue would then depend on which tab you visited, and a run started
from a pipeline node would differ from the same run started from the tab bar);
replacing the whole queue on every scope change (throws away what the user
queued by hand).

### Hand coding gets a worklist, and it is the sample
**Decision.** `Worklist` in `ui/handcoding.py` shows the current sample's
episodes with each one's coding state, on **both** Code and Validate tool.
Double-clicking a row opens that episode. Under the whole-library scope it
shows no rows and says why. Agreement is deliberately left out — it compares
two coders' *sheets*, which are not episodes and are not drawn by a sample.
**Reason.** Hand coding is a pass over a set, and the screen took one file from
the Library tree, so the researcher tracked "what is left?" against
`selected.csv` by hand. `TODO.md` item 6 already named the gap from the other
end: the sampler could send a draw to the analysis queue but not to a
hand-coding worklist, because there was no worklist.
**Consequence.** Each row's state comes from the engine —
`event_coding.event_sheet_status` for event sheets,
`validation.episode_status` for transition sheets — so the worklist and
`code_events.py` cannot disagree about whether an episode is coded. The state
function returns `(text, coded)`; the widget never infers "done" by reading its
own label.
**Consequence.** The whole library gets no worklist. A worklist of 137 episodes
is a library, and what makes a worklist useful is that it ends.
**Date.** 2026-08-16.
**Rejected.** A worklist on Code only (it leaves Validate as the half-done half
of one tab); reusing the Library tree inside the tab (it answers "which
episodes exist", not "which are coded", and it is already one tab away);
advancing automatically to the next uncoded episode on save (coding order is
the coder's, and a screen that moves under you loses work).

### A view narrows to the scope; a workbench stages from it
**Decision.** The rule the three measurement tabs settled into, stated once so
the next screen does not have to re-derive it. A screen that **reports on work
already done** filters to the scope — the Library, the Index, and Language →
Speech. A screen where **work is started** stages the scope's episodes and then
gets out of the way — Automated coding's queue, Human coding's worklist,
Language → Vocabulary's file list. The Language tab is the proof that both are
right: its two views take the same scope in opposite directions.
**Reason.** "Obey the scope" is not one behaviour. Filtering a workbench
forbids work the researcher is entitled to do and still leaves the run empty;
staging a results table would be meaningless. The distinction that decides it
is whether the screen's content is a *report* or a *plan*.
**Consequence.** Every staging screen follows the same three rules: the whole
library stages nothing, a scope change withdraws only its own staging, and the
screen says what it staged **and what it could not** — 8 of 9 drawn, 1 off
disk; 1 caption file, 7 episodes without. A short list with no explanation
reads as a small sample.
**Consequence.** Every filtering screen names the set it is showing in its own
count, rather than printing a bare total under a narrowed table.
**Date.** 2026-08-16.
**Rejected.** One `set_scope` contract for all six screens (it forces the wrong
verb on half of them); filtering the workbenches and adding a separate "load
the sample" button (two controls for one intent, and the empty state is still
the thing the user meets first).

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

### A Selection node's exclusions are written as a sample manifest, not `node.config`
**Decision.** Excluding episodes on a pipeline Selection node
(`ui/inspector.py`'s **Exclude Library Selection**,
`MainWindow._exclude_from_selection_node`) writes a new `selected.csv` +
`manifest.json` pair, sibling to the linked sample's folder
(`analyzer/selection.py`) — the same shape an Episode Sampler draw writes —
rather than storing an exclude list in the pipeline document's
`node.config`.
**Reason.** `CLAUDE.md`'s terminology table already says Selection "is a
property of the study and is recorded in a manifest," and every scope this
app offers — `discover_trials`, `build_pipelines`, the Showing: chooser —
already discovers samples by finding that exact file pair
(`analyzer/trials.py _discover_sample_trials`). Writing it that way meant the
narrowed sample needed **no new discovery code** and became a real, stable
entry in the Showing: chooser automatically. A `node.config`-only exclude list
was rejected specifically because it would have been a second, disconnected
way of saying "these episodes are out" that the dropdown could not see —
picking the same base sample from the chooser later would have silently
forgotten the exclusion, the shape of bug `LEARNINGS.md` already warns about
(numbers that display correctly but are wrong).
**Consequence.** This is the "small slice" of `TODO.md`'s "wires carry the
set": a Selection node narrows the *whole pipeline document's* one linked
sample, not a set derived by tracing which specific nodes are wired to it.
Branch-specific narrowing (an automated-coding branch and a hand-coding
branch on the same canvas getting different working sets) needs per-node
sample binding — moving `source_key` off the document onto individual
Sampling nodes — which is the larger, still-open piece.
**Date.** 2026-08-15.
**Rejected.** Storing exclusions in `node.config`, read only by the pipeline
canvas.

### A Sampling node's own binding falls back to the document's `source_key`, never replaces it
**Decision.** Per-node sample binding
(`PipelineDoc.upstream_sample_keys`, `node.config["sample_key"]`) reads a
Sampling node's own key if it has one, and otherwise falls back to
`doc.source_key` — it does not require every pipeline to be migrated to
per-node keys, and `doc.source_key` is not deprecated or removed.
**Reason.** Every pipeline saved before this existed has one Sampling node
and no `sample_key` on it. Requiring a migration (or worse, silently
treating an unmigrated pipeline as unlinked) would have broken every
existing study's derived status the moment this shipped. The fallback means
a single-sample pipeline — still the common case — needs zero changes and
behaves exactly as before; only a canvas that deliberately adds a second
Sampling node needs to give at least one of them (or both, for clarity) an
explicit key.
**Consequence at the time — since resolved, twice.** A node reached by more
than one Sampling node originally resolved its derived STATUS from only the
first key found, with the others surfaced as an explicit Inspector row
rather than silently dropped. That was replaced first for Validation only
(below), then generalized to every node type the same day after a real user
report: wiring two Sampling nodes directly into one Selection node showed
only one of the two shows. "Only Validation needs this" turned out to be
wrong — any node downstream of more than one Sampling node has the same
problem, Selection included, and Selection is arguably the more common case
of the two.
**Date.** 2026-08-15.
**Rejected.** Requiring per-node keys on every Sampling node (breaks
existing pipelines).

### Merging unions episodes, and never compares across samples
**Decision.** A node fed by more than one Sampling node
(`analyzer.pipeline.merged_pipeline`) reports derived status computed over
the UNION of every resolvable branch's episodes — union the episode lists
(de-duplicated by normalised path, in case two branches happen to draw the
same episode), union the trial records (de-duplicated by manifest file), and
recompute the analyzed count and hand-coding coverage over the union — then
run the ordinary single-sample stage logic (`_all_stages`) over that
synthetic union. This applies uniformly to every stage type — Selection,
Automated coding, Language, Validation, all of it — not a Validation-specific
special case. It does **not**, for any stage type, attempt to compare
sample A's results against sample B's as if they measured the same episodes.

Originally scoped to Validation alone (`merged_validation_view`, since
folded into this) on the reasoning that Validation was the only node type
whose whole purpose was comparing two things. That reasoning held for
*comparison*, but missed that plain *episode-set union* is needed by every
multi-input node, not just Validation — Selection's whole job is reporting
the working set, and a working set fed by two samples is honestly the union
of both, full stop, no comparison semantics involved at all.
**Reason.** A transition-validation comparison record is inherently
per-episode — it compares one episode's automated detection to a human
coding of that SAME episode — and does not care which drawn sample the
episode happened to belong to. So "how much of the combined working set has
been validated," or "how many episodes are in the combined working set," are
real, well-defined questions the union answers correctly for any stage type.
"Does the automated pass on sample A agree with the hand coding on sample B"
is not a real question at all when A and B are different episodes: there is
nothing to compare, and reporting a number for it would be exactly what
`CLAUDE.md` §2.2 forbids — a claim the data cannot support, dressed up as a
validation figure. Union is safe everywhere; cross-sample comparison is not
safe anywhere, and this function never does the second thing regardless of
which stage type is asking.
**Consequence.** If a researcher draws a large automated-only sample and a
separate, smaller hand-coding validation sample, wiring both into one
Validation node correctly reports validation coverage across the combined
set. If they instead draw two shows separately and wire both into one
Selection node, Selection correctly reports both shows' episodes as the
working set — the bug report that prompted generalizing this beyond
Validation.
**Date.** 2026-08-15.
**Rejected.** Comparing sample A's results against sample B's directly for
any stage type; scoping the merge to Validation only (the first version,
replaced the same day); silently reporting only the first branch (the
behavior before either version of this decision); requiring branches to
share every episode before a merged node would report anything.

### Linking a sample to the document vs. to one node are two methods, not one that infers
**Decision.** `MainWindow._link_to_sample` (document default) and
`_link_node_to_sample` (one Sampling node's own key) are separate methods,
fired by separate `Inspector` signals (`link_requested` /
`link_node_requested`). Neither re-derives "did the user mean the document
or a node" from `self._canvas.selected_node()` at click-time.
**Reason.** They used to be one method that inferred which was meant from
whatever happened to be selected on the canvas. `Manage → Link to Episode
Sample…` is reachable regardless of canvas state, so it silently repointed
a still-selected Sampling node's own binding instead of the document's, the
moment a user reached for that familiar menu item with a node selected from
browsing — see `LEARNINGS.md` for the incident this decision fixes.
**Consequence.** `Inspector` now decides which signal its one "Link…"
button fires when it BUILDS the button (`show_doc` vs. `show_node`), not
when the button is clicked — the intent is fixed at the moment the button
became visible for a reason, not re-guessed later from state that can have
moved on.
**Date.** 2026-08-15.
**Rejected.** One method inferring intent from canvas selection at
click-time (the prior, buggy design).

### The Showing: chooser offers pipelines as well as samples
**Decision.** The scope chooser lists the whole library, every drawn sample,
and **every pipeline document that draws on more than one sample** (
`MainWindow._doc_scope`, keyed `pipeline:<doc id>`). A pipeline resolving to
one sample gets no entry — that sample's own entry already covers it.
**Reason.** The chooser was built from `build_pipelines`, which despite its
name returns *derived samples* — one entry per draw. So a study assembled
from two Sampling nodes could not be named in this control at all: every
entry narrowed to one branch, and a researcher who had deliberately built a
two-sample pipeline saw one show at a time with no way to ask for the thing
they had actually built. Per `CLAUDE.md` §3 a **pipeline** is the workflow
the user owns and a sample is one draw inside it; a control whose entire job
is naming the current research context has to be able to name the former.
The user diagnosed this directly: "the library displays sampling rather than
pipelines (which can include two samples together)."
**Consequence.** The chooser is rebuilt at the end of `_discover_pipelines`
rather than early in `set_root`, because pipeline entries cannot be computed
until `self._docs` is loaded — which also keeps a root change to a single
`build_pipelines` pass rather than two. Documents are read from `self._docs`,
not re-listed from disk, so the chooser cannot disagree with the pipeline
picker beside it. Binding a Sampling node rebuilds the chooser, so a study
becomes selectable as soon as it exists rather than after a restart.
**Date.** 2026-08-15.
**Rejected.** Offering an entry for every pipeline including single-sample
ones (duplicates an existing entry under a second name, in a list this
library already fills with a dozen draws); making the pipeline picker and
the scope chooser one control (they answer different questions — which study
am I editing, versus which episodes am I looking at — and `DECISIONS.md`
already separates scope from selection for the same reason).

### Selecting a pipeline defaults to every sample it draws on
**Decision.** `_follow_pipeline_scope` scopes to the union of a document's
Sampling blocks when there is more than one, and to that block's sample when
there is one. Unchanged: a pipeline with nothing resolvable leaves the scope
alone.
**Reason.** The combination of blocks IS the study the researcher assembled,
so selecting it should not land on one arbitrary half. Before this, a
two-block pipeline followed `doc.source_key` — a single sample, and often
not one of the two actually wired up.
**Consequence.** The application still opens on the whole library
(`_discover_pipelines` passes `follow_scope=False`), which is a separate,
earlier decision and its own test; this changes what happens when a pipeline
is *chosen*, not what the app starts on. `_doc_sample_pipelines` is the one
implementation of "which samples does this document draw on", shared with
the chooser so the two cannot answer differently.
**Date.** 2026-08-15.
**Rejected.** Defaulting to the first Sampling block (arbitrary, and the
source of the behaviour this replaces); remembering a per-pipeline last-used
scope in preferences (a scope is a property of the session and is
deliberately never persisted — see the scope/selection split above).

### A pipeline node names the media it works on, on the box and in the inspector
**Decision.** Every node whose upstream samples resolve draws the sample's
name on the canvas box (`NodeItem.media_line`, under the stage description)
and shows it as the leading **Media** row and part of the subtitle in the
Inspector. A node fed by more than one sample names all of them, joined
with " + ".
**Reason.** A node's title and description come from the type registry, so
two Sampling nodes on one canvas were two identical boxes reading "Sampling
/ How episodes were chosen" — with nothing on either to say which show it
drew. Per-node sample binding made that ambiguity a real hazard rather than
a cosmetic one: the whole point is that the two boxes differ, and the
interface did not show how. `CLAUDE.md` §1's clarity principle ("a
researcher must be able to see exactly what the software is doing") and §4's
"the visual pipeline is how a researcher sees what the software is doing"
both point the same way.
**Consequence.** The name shown is the engine's own (`Pipeline.name`, from
the draw's manifest `trial_name`/`entry_id`) — the same string the Trials
tab and the Showing: chooser use, never a label invented in the view, per
`CLAUDE.md` §4. A node with no resolvable sample shows nothing rather than a
placeholder, so an unlinked node still reads as unlinked.
**Date.** 2026-08-15.
**Rejected.** Renaming the node itself on link (the title is the
researcher's to set, and overwriting it would lose their own naming);
showing the sample's folder path (long, and not what the rest of the
interface calls that draw).

### Drawing a new sample from a Sampling node binds it there directly, no separate link step
**Decision.** `MainWindow.open_sampler(self, node=None)` — when opened by
double-clicking a Sampling node, a completed draw writes
`node.config["sample_key"]` and saves the document immediately, rather than
requiring the researcher to draw, then separately open the Inspector and
use Link to Sample to point the node at what was just drawn.
**Reason.** The node the user double-clicked to open the sampler IS the
answer to "which node does this draw belong to" — there is no second
question to ask. Requiring a manual link-after-draw step for something the
UI already knows would be exactly the kind of friction `CLAUDE.md` §5's "no
context drift" and the north-star spec's "researchers interact in the
language of research methodology" argue against, and it is also what let
the bug in `LEARNINGS.md` happen in the first place — an extra manual step
is an extra chance to skip it or do it to the wrong node.
**Consequence.** Opening the sampler WITHOUT a node context (the File menu,
the toolbar button — neither tied to a specific pipeline node) keeps the
old behavior exactly: only the session scope follows the draw, and binding
it to any pipeline stays a deliberate, separate action. The two contexts
are genuinely different questions ("what should this node draw" vs. "draw
something, I'll decide what to do with it after"), so they get different
answers rather than one compromise behavior for both.
**Date.** 2026-08-15.
**Rejected.** Always requiring a manual Link to Sample step after any draw,
node-triggered or not (consistent, but reintroduces the exact friction that
caused the reported bug); auto-binding even the node-less File-menu/toolbar
draw to "whichever pipeline is currently open" (that draw was never asked
to belong to any particular node or document, so guessing one is a worse
default than not guessing).

### The measurement model extends the registry; it does not replace it
**Decision.** CMAT adopts **construct → aspect → measure → method → recipe** as
the vocabulary for how a number was operationalized, and builds it *on top of*
`analyzer/measurements.py` rather than beside it. `ToolSpec` is a method;
`ParamSpec` is its parameters; `measurement_fingerprint()` is the seed of
staleness. Anything enumerating methods reads the registry rather than
restating it, so a detector added there appears as an available method with no
other edit. Hand coding becomes a first-class method alongside the automated
ones. Recorded in full in `MEASUREMENT_MODEL.md`; the rules it must satisfy are
`CLAUDE.md` §2.5.
**Reason.** The gap is real and was identified independently before this phase
was planned (`ARCHITECTURE.md` §8.1a: "nothing maps a specific metric to a
specific construct"). But the registry already solves the two hardest parts —
typed parameters and per-tool validation status — and a second enumeration of
detectors is exactly `LEARNINGS.md` shape 3, the mistake that put a
contradicting accuracy claim on fourteen published pages. The model needed a
layer above the registry, not a rival to it.
**Consequence.** Two vocabularies are now in use and both are correct: the
pipeline **stages** describe the workflow, the **measure/method** words
describe the operationalization. "Measurement" the stage and "a measure" are
not the same thing, and `CLAUDE.md` §3 now says so.
**Date.** 2026-08-16. Documented; **nothing is built**.
**Rejected.** A standalone measurement model with its own tool list (drifts
from the registry within one release); folding constructs into
`MeasurementSpec` as another field (a construct is a research decision the
researcher owns and edits, not a property of a detector); waiting for the
composite's own rationale to be settled first (it cannot be — the defaults are
underived, `ARCHITECTURE.md` §8.1a, and making the operationalization explicit
is what lets a researcher build a *different* one).

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

### Marking auto-pauses the video; the on-screen clock during playback is a cosmetic estimate, never the recorded value
**Decision.** `ui/handcoding.py`'s Mark button now goes through
`VideoPlayer.stamp()`: if the player is paused, the mark records immediately;
if it is playing, `stamp()` pauses it first, waits for libvlc to confirm the
pause, and only then reads the timestamp. Separately, `_sync()`'s on-screen
counter is smoothed during playback by extrapolating from the last real
libvlc tick using wall-clock time — display only, never fed to a mark.
**Reason.** `ui/player.py`'s own docstring had claimed "pause before marking;
the coding UI enforces that" since 2026-08-10, but nothing enforced it —
`_mark()` read `player.position()` directly regardless of play state.
Measured: libvlc's live `get_time()` only refreshes every 0.2–0.5s during
playback, independent of the file's actual frame rate (confirmed 23.976fps
via `ffprobe` on a real episode, not throttled polling on our side) — so a
mark taken while playing could be stamped up to ~0.5s stale relative to what
the coder just saw, on top of the codebook's ±1s target and the
already-documented ~0.55s whole-second-entry bias. Auto-pause was chosen over
blocking the click with a dialog: a coder marking on impulse while watching
should not need Pause-then-Mark as two separate actions to get an accurate
timestamp — the tool should make the accurate path the easy one. The counter
is smoothed separately, purely so a coder gets usable live feedback while
watching for the moment to mark; it snaps back into sync with the real value
on every genuine libvlc tick, so it cannot drift beyond libvlc's own
tick size before self-correcting.
**Date.** 2026-08-17.
**Rejected.** Blocking Mark with a warning until the coder pauses manually
(extra friction for no accuracy gain once auto-pause exists); polling
libvlc's clock faster to smooth playback (measured — does not help, the
number itself only changes every 0.2–0.5s no matter how often it is asked);
switching away from VLC (evaluated and declined — see *Frame-accurate
playback via VLC* above; VLC's *seek* path is exactly as accurate as this
depends on, and any general-purpose player backend throttles its *live*
position reporting the same way for the same reason, so switching would not
remove the problem, only relocate it).

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

### The participant pace scale is a labelled ramp, not a traffic light
**Decision.** The Study Runner's 1-5 pace item is a horizontal labelled ramp:
five equal cells each carrying its number *and* its verbal anchor, coloured by
a single-hue lightness ramp, with a turtle and a rabbit as end anchors beside
the scale rather than on it. Selection is an outline plus a mark, never a
change of fill, and nothing is selected until the participant chooses.
**Reason.** Four findings, each of which changed something on screen: fully
labelled scales beat end-anchored ones for unpractised respondents (Krosnick &
Fabrigar 1997), five points is the ceiling for children (Borgers et al. 2000),
colour on a response scale is read as valence (Tourangeau, Couper & Conrad
2007), and expressive imagery imports affect the study did not ask about
(Chambers & Craig 1998). The colour finding is also the guardrail: a red-to-
green ramp would make "very fast" mean "in the red", which is CMAT issuing a
verdict on a participant screen. Sources and the full reasoning are in
`STUDY_RATING_SCALE_DESIGN.md`; the ramp's monotonic lightness and single hue
are asserted by `tests/test_study_runner_scale.py`, so the rejection below
cannot quietly return.
**Date.** 2026-08-29.
**Rejected.** A red-to-green traffic-light ramp (reads as a verdict, and fails
red-green colour deficiency). Five creatures, one per point, snail to hare
(requires a child to already rank five animals by speed; a different ranking
produces an undetectable error). Creatures instead of words at the five points
(unlabelled interior points). A dot-on-a-rail continuum (asserts equal spacing
the analysis explicitly declines to assume). A pre-selected midpoint.

### The Clip Finder is Selection at window scale, not a new stage
**Decision.** Finding 30-second windows by attribute is reached from a
**Selection** node in the Pipeline, not from a new top-level tab. The node
records the pool it measured and anything it exported in `node.config`, so the
canvas states what that Selection holds.
**Reason.** Selection is the stage that decides which material a study is
about. The Episode Sampler answers it at episode scale and this answers it at
window scale; they are one question at two grains, and a separate tab would
have implied a stage the vocabulary does not have. Asked directly and answered
"inside the Pipeline, as Selection" (2026-08-30).
**Date.** 2026-08-30.
**Rejected.** A top-level "Clip finder" tab; a dialog launched from the Library
against the current scope.

### The Clip Finder measures as well as browses
**Decision.** The screen runs `study_clips.run_candidate_pool` itself, on a
worker thread, as well as reading a pool that already exists.
**Reason.** A browser over a pool the researcher can only produce at a terminal
is a screen that works for people who did not need it. Asked directly and
answered "run the pass, then browse" (2026-08-30). The cost accepted: the run
half duplicates `cli.py study-clips` as a *front end* — it calls the same
function with the same arguments and adds no analysis logic of its own.
**Date.** 2026-08-30.
**Rejected.** Browse-only over an existing run folder.

### A found set never ranks windows by fitness
**Decision.** The finder filters and orders on measured quantities the
researcher names. There is no score, no "best match", no recommended clip, and
no ordering the researcher did not ask for.
**Reason.** The stimulus-only guardrail. A ranked list of clips is a verdict
about which material is *better*, and the moment one exists it will be read as
one — including by the researcher who built it. The query is stated in one line
above the results (`ClipQuery.describe()`) so a found set always carries the
question that produced it.
**Date.** 2026-08-30.
**Rejected.** A relevance or closeness score against target values; sorting by
a composite of the three features.

### The participant study is adult-only and measures adults' own perceived pacing

**Decision.** The study title is **Adult Perceptions of Pacing in Children’s
Television**. Recruit adults age 18 or older only and ask one self-perception
pace question after each of 12 clips. Do not recruit children and do not ask
adults to predict how children would perceive the clips.
**Reason.** Child participation adds parental permission, assent, safeguarding,
scheduling, and recruitment requirements that threaten feasibility within the
project timeline. An adult prediction without child ratings would measure an
adult belief about children, not children's perception, and its accuracy could
not be tested. The narrower adult-only design directly measures the construct
the available participants can report.

**Date.** 2026-08-31.

**Rejected.** Continuing child recruitment despite the feasibility problem;
retaining adult prediction as a proxy outcome after removing children.

**Provenance exception.** Frozen recipe names, file paths, manifests, inventory
rows, and citations keep the former title because changing them would break the
historical hash chain. Active documents label those strings as legacy.
