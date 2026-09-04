# Children's Media Analysis Toolkit (CMAT)

**An open-source research application for quantitative analysis of children's
audiovisual media.** CMAT is a Windows desktop application for researchers who
need to measure formal media features in children's television: pacing and shot
boundaries, shot duration, visual motion, flashing, colour/color and contrast,
audio intensity/loudness, speech rate, speech density, vocabulary, and related
properties.

It brings reproducible episode sampling, clip selection, automated measurement,
human coding, corpus-specific validation, construct operationalization, and
research-data export into one inspectable workflow. The numbers describe the
media stimulus; they do not rate a programme or predict effects for an
individual viewer.

The visual research pipeline keeps the whole study in one understandable flow:

> **Sampling → Selection → Measurement → Validation → Results**

Start with the supplied workflow, click a stage to configure it, and follow the
connections from source videos to exported evidence. Researchers can use the
default pipeline without programming, while advanced users can rearrange or
extend it to match a study design.

## What makes CMAT different

CMAT is designed to keep the decisions linking a research question to a result
visible. Researchers can define a construct in plain language, connect it to
supported measures, choose methods and weights, and save the operationalization
as a versioned recipe that can be inspected, reused, and cited. The same
workflow supports hand coding and comparison of automated results against a
human-coded reference. That reference is a measurement with its own error, not
a ground truth: CMAT's own is quantised to whole seconds and runs about 0.55 s
early, which is why its match tolerance has a floor.

## Validation and scope

CMAT includes a validation workbench for comparing an automated detector with
human coding. It reports precision, recall, F1, Cohen's kappa, and inter-rater
reliability where those statistics fit the question. Validation is
measure-, method-, and corpus-specific: CMAT is not a universally validated
measurement instrument, and a result should be qualified by the coding basis,
sample, settings, and match rule used to produce it.

The formal-feature literature motivates the properties CMAT can measure; it
does not prescribe one universal construct or a single composite score. The
optional **Formal-Feature Composite (FFC)** is a configurable composite of
observable audio-visual production and editing features. Its component measures
remain visible, and its weights and normalization ceilings are configurable
rather than theory-derived or validated. It is not a validated measure of
viewer sensory load, arousal, or developmental impact.

> **Scope:** CMAT measures the stimulus, not the viewer. It cannot account for
> a child's age, temperament, sensory-processing profile, viewing context, or
> exposure history. Its outputs are profiles to inform research judgment—not
> appropriateness ratings, safety assessments, or causal conclusions.

It has two co-equal halves:

**Automated formal-feature measurement.** Measure pacing, motion, colour,
contrast, flashing, and audio, choosing the tools and thresholds behind each
measurement. Researchers may combine selected measures into an optional
composite they configure rather than one the tool imposes. CMAT also measures
the **linguistic complexity** of dialogue through speech rate, readability
formulas, vocabulary frequency tiers, age of acquisition, and lexical diversity.

**Structured hand coding of transitions and fantastical events.** Code
transitions, scene changes, and events against a built-in frame-accurate video
player, using your own category systems, and get metrics computed with the
same definitions as the automated path.

Then compare the two: validate automated detection against hand coding with
precision/recall/F1, Cohen's κ, and inter-rater reliability as appropriate.
See [Automated measurement and human validation](#automated-measurement-and-human-validation).

> **Part of the Open Children's Media Index** — an ongoing effort to build a publicly accessible database of formal-feature measurements for children's television.

---

## A visual pipeline for children's media research

CMAT presents a study as five connected stages instead of a collection of
unrelated analysis tools:

| Stage | What the researcher does | What CMAT preserves |
|---|---|---|
| **Sampling** | Draw a census, simple random sample, systematic sample, positional-chunk ("spread") sample, or hand-picked set, optionally stratified by season or era | The drawn episodes **and the candidate frame they came from**, the seed, method, strata, the regexes and extensions that defined a unit, and a manifest |
| **Selection** | Narrow the episode sample or use Clip Finder to locate candidate scenes | Exclusions, filters, source timecodes, and the selection query |
| **Measurement** | Measure cuts, motion, colour, contrast, flashing, audio, speech, and vocabulary | Methods, parameters, recipe version, and measurement fingerprint |
| **Validation** | Compare automated results with human coding | Precision, recall, F1, Cohen's kappa, and agreement evidence |
| **Results** | Review, compare, chart, and export findings | Component measures, provenance, CSV/JSON output, and reports |

The interface is designed around progressive disclosure: the canvas shows the
study at a glance, selecting a block reveals the controls for that stage, and
double-clicking opens the relevant workspace. A researcher can begin with the
default layout and make ordinary study decisions without constructing a graph
from scratch. Undo/redo, saved pipeline documents, visible stage status, and
direct links from each node to its working screen keep the workflow inspectable.

CMAT also separates the *study workflow* from the *measurement model*. The
Pipeline tab shows where data moves; the Constructs tab shows how a concept is
operationalized as **Construct → Aspect → Measure → Method**. Recipes record
the selected measures, methods, weights, ranges, and parameters so that a
composite is a documented research decision rather than a hidden formula.

## Create and operationalize your own research constructs

CMAT is not limited to a fixed list of researcher concepts. In the
**Constructs** tab, click **Constructs…** to create a construct, give it a name
and definition, and describe the aspects the study intends to represent. Then
use **Edit** to bind supported audiovisual or language measures to those
aspects, select the available measurement methods, and set their contribution
weights. No programming is required.

Save that operationalization as a **recipe**. A recipe preserves the construct,
measure bindings, methods, parameters, ranges, and weights as a versioned,
content-hashed research object. This makes a custom composite transparent:
collaborators and reviewers can see what the construct meant in the study, how
it was measured, and which exact configuration produced the results.

This supports exploratory construct development, preregistered measurement
plans, sensitivity analyses, replication, and comparison between alternative
operationalizations. Researchers may define constructs and combine CMAT's
supported measures; defining entirely new low-level measures still requires
adding a detector to the source code and measurement registry.

### Typical workflow

1. Open a folder containing legally obtained episode files.
2. Use a Sampling node to create or attach a reproducible episode sample.
3. Use Selection to exclude episodes or open **Clip Finder** for scene-level
   stimulus selection.
4. Create or choose a construct and save its operationalization as a recipe.
5. Run Measurement with that documented configuration.
6. Hand-code a validation sample and compare it with automated detection.
7. Inspect the Results stage and export data with its provenance.

---

## Clip Finder: build custom-duration research stimuli

Clip Finder searches contiguous windows inside a folder of episodes using the
**window length the researcher specifies**. A window might be 10 seconds for a
brief orienting-response task, 30 seconds for a pacing-rating study, several
minutes for a comprehension experiment, or another duration required by the
study protocol. CMAT applies that duration consistently across the source
episodes so researchers can build a comparable candidate stimulus pool from
measured properties rather than memory or convenience.

From the **Pipeline** tab, select a **Selection** node and click **Find Clips…**.
Choose the source folder, enter the custom window length in seconds, decide
whether to keep a shorter final window, and set any opening or closing time to
exclude. Then click **Measure Windows**. The work runs in the background,
caches completed episodes, and can resume without starting the entire pool
again.

Once measured, filter candidate clips by:

- cuts per minute;
- mean motion;
- mean audio RMS intensity;
- low, middle, or high relative level for each measured feature;
- episode filename; and
- any combination of minimum and maximum bounds.

The table updates as filters change and states the complete query in plain
language. Selected windows can be exported as standalone MP4 files. CMAT
re-measures the exported files and writes a JSON manifest containing the query,
source episode, absolute timecodes, pool settings, and measurement fingerprint.

### Why custom windows matter for research

Window duration is part of the research method, not merely an export setting.
Short windows can isolate rapid formal features such as cuts, flashes, motion,
or bursts of audio intensity. Longer windows can preserve narrative context,
dialogue, and sustained pacing while reducing the influence of a single edit.
Using one declared duration across a candidate pool makes clips easier to
compare and gives participant tasks consistent exposure times.

CMAT records the chosen duration, excluded opening and closing intervals,
partial-window rule, source episode, and absolute timecodes. This supports
repeatable stimulus selection, preregistration, methods reporting, independent
review, and exact reconstruction of the candidate pool. Researchers should
choose the duration from the construct and task they intend to study—not after
seeing which duration produces the preferred clips.

Clip Finder deliberately does not declare a “best” clip. It filters and sorts
according to criteria the researcher chooses. Its low/middle/high labels are
thirds of the measured candidate pool—not universal properties—so the pool
definition and exclusions remain visible beside the results. This makes the
selection contestable and reproducible without pretending that stimulus choice
is an automated judgment.

---

## What it measures

### Formal media-feature measures

Each row states the quantity that is actually computed, in the units it is
reported in. The name is a label for that quantity and nothing more.

| Metric | What is computed | Units | Notes and limits |
|---|---|---|---|
| **Shot-boundary rate** (`cuts_per_min`) | Boundaries reported by the selected detector, divided by runtime. Shipped detector: PySceneDetect `ContentDetector` at threshold 27. | boundaries/min | **Detected boundaries, not semantic scene changes** — a cut inside one continuous scene counts. Frame-differencing misses gradual transitions (dissolves) by construction: it cannot separate two shots blending from one shot panning. |
| **Shot length** | Mean and median interval between consecutive boundaries; coefficient of variation of those intervals. | seconds; CV unitless | Derived from the same boundaries, so it inherits their errors. |
| **Motion** (`motion_mean`) | Mean absolute difference in grayscale pixel intensity between **consecutive sampled frames**, rescaled 0–255 — 0–1. | 0–1 | Measures **image change, not depicted movement**: a cut, a camera pan and a running character all raise it. **Depends on the sampling rate** (default 2 fps) — values measured at different rates are not comparable. An optional Farneback optical-flow method exists and is on a different, uncalibrated scale. |
| **Color saturation** (`color_saturation_mean`) | Mean of the HSV **S** channel per frame, averaged over sampled frames. | 0–1 | Unstable on blown-out live-action grading. |
| **Color contrast** (`color_contrast_mean`) | **Spatial** standard deviation of the HSV **V** channel within each frame, averaged over sampled frames. | 0–1 | **Within-frame brightness spread, not a perceptual contrast metric.** High for stark dark/light regions — slides, whiteboards — so it can be elevated on footage a viewer would call calm. |
| **Flashing** (`flashing_events_per_min`) | Count of consecutive sampled frames whose **whole-frame mean** luminance differs by more than a threshold (default 0.1), at a dedicated rate (default 10 fps). | events/min | **NOT a photosensitivity safety assessment.** It implements neither the area threshold nor the red-flash criterion broadcast photosensitivity guidance specifies; a flash confined to part of the screen is diluted by the whole-frame mean; and it has never been graded against human coding. **Zero does not indicate safety.** Comparable only across episodes measured at the same rate and threshold. |
| **Audio intensity** (`audio_rms_mean`, `audio_dynamic_range_db`) | Mean and peak of per-second **RMS amplitude**, and 20·log10(peak/mean), on the track downmixed to mono and **resampled to 8 kHz**. | linear 0–1; dB | **Linear amplitude, not perceptual loudness — not LUFS, not EBU R128.** Two files mastered to the same broadcast loudness can differ here. The 8 kHz resample discards high frequencies. |

**Missing is not zero.** An episode with no audio track has `audio_available`
false, empty audio columns, and `audio_unavailable_reason` distinguishing "no
audio track" from "FFmpeg not found" from "extraction failed". A failed
analysis exports empty metrics and an `error`, never a plausible-looking 0.0.
A `0.0` in a CMAT export is a measured zero.

### Optional researcher-defined composite

| Measure | What it captures |
|--------|-----------------|
| **Formal-Feature Composite (FFC)** | A configurable composite of observable audio-visual production and editing features. It always displays its component parts and is not a validated measure of viewer sensory load, arousal, or developmental impact. |

### Language metrics *(optional — requires subtitle files or Whisper AI)*

| Metric | What it captures |
|--------|-----------------|
| **Words per minute** | Words divided by **dialogue time, not runtime** — how fast characters speak when they speak, not how talkative an episode is. Reported with speech density or not at all. Sourced from `.srt`/`.vtt` subtitle files; Whisper transcription used as a fallback when enabled. **A caption-derived count and a Whisper-derived count are different measurements** and the export records which one produced each row (`speech_source`); do not pool them without saying so. Caption files carry the captioner's choices — omitted song lyrics, bracketed sound descriptions — into the count. |
| **Speech density** | Fraction of episode runtime containing dialogue. Separates talk-heavy shows from those with long musical or silent passages. |
| **Readability** | Flesch Reading Ease, Flesch-Kincaid Grade Level, Spache, Dale-Chall, Coleman-Liau, ARI — six formulas applied to the cleaned dialogue transcript. |
| **Vocabulary frequency tiers** | Zipf-scale tier breakdown: Tier 1 (everyday words, ≥ 4.5), Tier 2 (academic/cross-domain, 3.0–4.5), Tier 3 (rare/domain-specific, < 3.0). |
| **Age of Acquisition** | Mean age at which vocabulary words are typically learned, from Kuperman et al. norms. |
| **Lexical diversity (MTLD)** | Measure of Textual Lexical Diversity — how widely the dialogue draws on the available vocabulary, robust to text length. |

The **measurement set** draws on the Huston & Wright formal-features framework
and Lang's Limited Capacity Model (LC4MP). Those frameworks motivate *which*
properties may be useful to measure; they do not establish causal effects or
specify how to combine the properties into one number. The composite's weights
and normalization ceilings are a configurable scaling convention, not derived
from theory and not validated. Component measures are reported separately for
that reason. See [CEILINGS.md](CEILINGS.md).

---

## Screenshots

<img width="805" height="435" alt="CMAT children's television video analysis interface" src="https://github.com/user-attachments/assets/305685d9-639c-428a-9246-b00e1a5709b6" />
<img width="357" height="440" alt="CMAT formal-feature measurement results" src="https://github.com/user-attachments/assets/51a6030d-e4c0-4102-92ea-a81a472b54ba" />
<img width="416" height="313" alt="CMAT episode sampling and media research tools" src="https://github.com/user-attachments/assets/9cc86a50-f268-47dc-89d7-3e8b92d2968f" />
<img width="635" height="401" alt="CMAT audiovisual analysis charts for children's media research" src="https://github.com/user-attachments/assets/9c0f35d7-867e-48de-85ac-079ed28ad2ff" />


---

## Download & Install (Windows)

1. Go to the [Releases page](../../releases/latest)
2. Download the latest `CMAT` Windows `.zip`
3. Unzip anywhere (e.g. `C:\CMAT\`)
4. Double-click `CMAT.exe`

No Python, no FFmpeg, no other installs required. Everything is bundled.

---

## How to use

### 1. Open the research pipeline

Launch CMAT and open the **Pipeline** tab. The default connected workflow gives
you a starting point; click a stage to see what it needs and what it produces.
You can save multiple pipelines for different studies or methods within the
same media library.

### 2. Pick a root folder

File → Open Root Folder. Organize your library like this:

```
My Videos/
  Little Bear/          ← flat show
    ep01.mp4
  Animated/             ← category folder (optional)
    SpongeBob/
      ep01.mp4
  Little Bear (Full Series)/   ← season folders auto-detected
    Season 1/
      ep01.mp4
    Season 2/
      ep01.mp4
```

Each subfolder containing MP4s is a "show." Folders named *Season N*, *Series N*, *S N*, or *Part N* are recognized as season folders and grouped under their parent show name in the index automatically.

### 3. Analyze episodes

- **Single episode** — Select an episode in the Library tree, click **Analyze Episode**. Results appear on the right with a full metric breakdown and a cuts-per-30s timeline chart.
- **Whole show** — Select a show folder, click **Analyze Show (Batch)**. Episodes are analyzed in sequence with a live progress bar. Results are cached — re-opening the app never re-analyzes files.
- **Full series aggregate** — After analyzing all seasons of a show, click **Full Series Aggregate** to see combined statistics across every season folder at once.

### 4. Sample a show for research

For large shows, use **File → Episode Sampler** to build a reproducible, documented sample instead of analyzing every episode.

- Choose a stratification strategy (by season, or unstratified)
- Choose a selection method (below)
- Set your sample size and random seed
- Preview the selected episodes, then **Send to Analysis Queue** to analyze only those episodes
- The sampler saves a `manifest.json` and `selected.csv` alongside your output — a permanent record of exactly how the sample was drawn

**The five methods, and what they actually do.** Ordering is by episode number
by default, or by air date when you ask for it; `spread` and `systematic` cut
the run into chunks along that order, so the order is part of the design and
the manifest records it. If you order by air date and some episodes have none,
the sampler says so in its notes rather than drawing quietly from a different
sequence.

| Method | Implementation | Standard name |
|---|---|---|
| `census` | Every unit in the stratum. | Census. Not a sample. |
| `srs` | `random.sample` over the stratum — equal-probability, without replacement. | Simple random sampling. |
| `systematic` | `k = max(1, N // n)`, a random start in `[0, k-1]`, then every `k`th unit. | Systematic sampling with a random start. **The realised sample size is `N/k` rounded, which is not always the `n` you asked for** — check the manifest's `total_selected`. Warns when `k <= 2`, where a repeating episode pattern can alias. |
| `spread` | Split the ordered stratum into `n` contiguous, near-equal chunks; take one unit uniformly at random from each. | **Not a standard named design.** It is *stratified random sampling with equal-sized positional strata and one unit per stratum*. "Spread" and "chunk" are CMAT's own words for it. Inclusion probabilities are `1/chunk_size` and differ between chunks when `N` is not divisible by `n`; they are not equal across the frame, and any estimate that assumes equal probabilities will be biased. It is CMAT's default because it gives even coverage of a run without the aliasing risk of a fixed interval, not because it is more principled than `srs`. |
| `manual` | Hand-picked identifiers. | **Not a sample.** Flagged `probability: false` in the manifest, and no seed is recorded — a seed beside a hand-picked set would imply it was drawn. |

**Reproducibility of a draw.** Seeds are derived per stratum from
`sha256(seed:entry_id:stratum_key)`, so adding a stratum later does not disturb
the seeds of existing ones. Re-running with the same seed, frame and ordering
reproduces the draw exactly; a test pins this. What the manifest records so a
reader can check the frame was the same — not merely the same size — is
listed under [Reproducibility and provenance](#reproducibility-and-provenance).

Once analyzed, use **View Sample Aggregate** to load a manifest and see aggregate results for only the sampled episodes — useful for comparing different sample sizes against a full-show baseline.

### 5. Add episode metadata

Air dates, season numbers, and episode numbers can be attached to any analyzed episode. This enables chronological charting and longitudinal research.

**Manual entry** — Select any analyzed episode. An **Air Date / Season / Ep #** panel appears below the results. Enter values in any common date format (`11/8/1995`, `8 Nov 1995`, `1995-11-08`, etc.) and click **Save**.

**Import from TVMaze** — `File → Import Episode Metadata from TVMaze…`

Paste any TVMaze show URL (e.g. `https://www.tvmaze.com/shows/17755/franklin/episodes`) and click **Fetch**. CMAT calls the free TVMaze public API — no account or key needed — and previews how each episode matches your local files by season/episode number (green) or fuzzy title match (yellow). Click **Apply to Database** to write the air dates.

**Import from Wikipedia** — `File → Import Episode Metadata from Wikipedia…`

For shows not on TVMaze, save the Wikipedia "List of X episodes" page as HTML (`Ctrl+S` in your browser), then browse to it in this dialog. CMAT parses the episode table and performs the same match preview and apply workflow.

### 6. Visualize series trends

Once episodes are analyzed, click **Show Chart** from any show-level or full-series aggregate view. The chart window has three independent controls:

| Control | Options |
|---------|---------|
| **X-axis** | Air Date (when ≥ 80 % of episodes have dates) · Episode Number |
| **Y-axis** | FFC Score · Cuts per Minute · Color Saturation · Color Contrast · Motion · Flashing / min · Audio RMS |
| **Colour by** | Season · Era |

**Era stratification** — Click **Edit Eras…** to define named date ranges (e.g. *Original Run 1992–1997*, *Revival 2003–2006*). Each era gets its own bar colour; episodes outside all defined ranges appear in gray. Eras are saved per-show to the local database and reload automatically the next time you open the chart.

### 7. Browse and compare

- **Index tab** — Sortable, filterable table of every analyzed episode and show. Columns include Air Date, Season, and Episode Number alongside all analysis metrics. Click any column header to sort; type in the filter bar to search.
- **Compare** — Click **Pin for Compare** on any episode result, then **Compare with Pinned** on another to see a side-by-side metric table.
- **Notes** — Add per-episode notes in the results panel; saved automatically to the local database.

### 8. Adjust weights and presets

**Settings → Formal-Feature Composite Weights** — change how much each metric contributes to the FFC, or adjust normalization ceilings. Age-range and content-type presets are built in. Switching presets re-scores all cached results instantly — no re-analysis needed.

### 9. Analyze speech and vocabulary

The **Language tab** surfaces dialogue-level metrics that are independent of the FFC.

#### Speech sub-tab

After analyzing episodes, click **Refresh** to load WPM and speech density for every episode that has speech data. The table is sortable by any column. Click **Chart WPM…** to open a dual-axis chart for a show: bars show words per minute per episode; an overlaid line shows speech density (% of runtime with dialogue), ordered by air date when available.

**Getting speech data into your episodes:**

- **Subtitle files (recommended)** — Place a `.srt` or `.vtt` file with the same name alongside each `.mp4` (e.g. `ep01.srt` next to `ep01.mp4`). CMAT detects it automatically during analysis. This path is instant and requires no extra software.
- **Whisper AI transcription** — Open **Settings**, enable *Auto-transcription with Whisper AI*, and choose a model size. `small` is recommended: it runs on any CPU in roughly 2–5 minutes per episode and is accurate enough for WPM measurement. When an episode is analyzed, CMAT transcribes it and **saves the result as a `.srt` file alongside the video** — so Whisper only runs once per episode, and the saved `.srt` is available for vocabulary analysis on subsequent runs.

#### Vocabulary sub-tab

Analyzes the linguistic complexity of dialogue from subtitle files.

1. Click **Browse CC Files…** to select `.srt` or `.vtt` files directly, or **Browse Folder…** to add all subtitle files in a folder tree.
2. Click **Analyze** (green button). The pipeline strips stage directions (`[MUSIC]`, `(laughs)`, speaker labels), lemmatizes content words via spaCy, and computes readability and vocabulary metrics.
3. Results appear in the table. Hover any column header for a full explanation of that metric.
4. Use the chart dropdown to visualize results:

| Chart | What it shows |
|-------|--------------|
| **Stacked Tiers** | T1 / T2 / T3 proportion per file — the most useful cross-show comparison |
| **Flesch Reading Ease** | With reference lines at 90 (very easy), 60 (standard), 30 (difficult) |
| **F-K Grade Level** | With reference lines at grades 2, 5, and 8 |
| **Age of Acquisition** | Mean AoA per file with a 6-year early-childhood boundary line |
| **MTLD** | Lexical diversity score per file |

5. Click **Export CSV…** to save a flat-row CSV of all metrics for every successfully analyzed file.

**Optional norm files** — For AoA and concreteness scores, place the following in `data/norms/` relative to the project root:

| File | Source | Key columns |
|------|--------|-------------|
| `kuperman_aoa.csv` | Kuperman et al. (2012) — [OSF](https://osf.io/bhdsm/) | `Word`, `AoA_Rating_Mean` |
| `brysbaert_concreteness.csv` | Brysbaert et al. (2014) — [OSF](https://osf.io/u56th/) | `Word`, `Conc.M` |

The norm files are freely available for research use but are not redistributed here. Without them, Zipf tiers and MTLD still work; AoA and concreteness columns will be blank.

**NLP dependencies** — Vocabulary analysis requires additional packages. Install once:
```bash
pip install spacy wordfreq textstat lexical-diversity
python -m spacy download en_core_web_sm
```

### 10. Export

From the results panel: **Export JSON**, **Export CSV**, or **Export PDF Report** for a printable one-page summary.

### 11. Build a 30-second study-clip candidate pool from the command line

The current participant study is titled **Adult Perceptions of Pacing in
Children’s Television** and uses adults' own pacing ratings only. The recipe
name in the command below retains the former study title because it is a frozen,
hash-bound provenance identifier; it does not describe the active participant
protocol.

The CLI can measure a complete season as contiguous 30-second windows without
first creating hundreds of MP4 files. It writes relative high/middle/low
profiles for cuts, motion, and audio intensity, then proposes the 12 unique
clips / six matched contrasts required by the Option 3.5 replicated-feature
design.

```powershell
python cli.py study-clips "Shows\Curious George Full Season One HD" `
  --recipe "Adult Prediction of Children's Perceived Media Pacing - Feature Extraction" `
  --exclude-first 51 --exclude-last 38
```

Use `--exclude-first SECONDS` and `--exclude-last SECONDS` to skip repeated
openings and closings at decode time while retaining absolute source timecodes.
`--recipe` makes the workflow use the saved recipe's pinned cut detector,
motion method, shared frame-sampling settings, and audio method. The manifest
stores the recipe citation and a complete snapshot for reproducibility.

Runs resume from fingerprinted per-episode measurements. Add
`--export-selected` only after reviewing the proposed scenes; CMAT then exports
the twelve finalist MP4s and re-measures the exact participant files. See
[Selecting 30-second study clips with CMAT](STUDY_CLIP_SELECTION.md) for
outputs, review requirements, HD/SD guidance, and the stimulus-freeze checklist.

Prefer the graphical [Clip Finder](#clip-finder-build-custom-duration-research-stimuli)
for an interactive, no-code workflow. The command-line route uses the same
candidate-pool measurements and is useful for scripting or repeating a frozen
study protocol.

---

## Automated measurement and human validation

Automated measurement should be validated for the measure, method, corpus, and
research use at hand. CMAT includes a **human-coding and validation workbench**
for comparing automated results with a hand-coded reference—and for coding
phenomena a pixel measure cannot represent. Hand coding is also a measurement
method in its own right, not merely a check on automation, and it is a
*reference*, not a ground truth: a human coder has resolution limits and
systematic biases of their own, and calling their labels truth is what hides
them.

### Built-in coding editor with an embedded player

Open a coding sheet from the **Validation** tab and you get a form-style editor with a built-in video player (audio included):

- **Watch and stamp.** Play the episode inside the editor and press **✚ Stamp** (or `S`) to log a row at the *exact current frame* — millisecond-accurate timestamps, no clock-reading, no typing, no transcription errors. A run of identical cuts is just watch → `S` → watch → `S`.
- **Frame-exact refinement.** Frame-step (`E`), nudge, and speed controls; clicking any coded row seeks the player to that moment for pass-2 review.
- **Dropdowns that can't be mistyped** — every category field is a dropdown, and the entry values feed directly into the analysis, so coded vocabulary can't drift.
- **Autosave** after every change — no lost work.

### Code two things

- **Scene cuts / transitions** — `hard_cut`, `dissolve`, `fade_in`, `fade_out`, `other`, plus an optional **within-scene vs scene-change** label (the distinction the literature keeps conflating: a shot-reverse-shot cut is not a scene relocation).
- **Fantastical events** — a structured codebook for the content variable current research points to (impossible physical events, transformations, continuity violations, impossible body events, object animacy, impossible causation), with per-event **narrative relevance** and **repetition** fields for testing the live mechanism accounts.

### Use *your* coding system — fully customizable

**Every dropdown is editable.** Type your lab's own category and it's added to the list for reuse — CMAT ships with a default vocabulary, but you are never locked into it. (The default transition typology is the study's own working scheme and does not yet cite a source; the shot-boundary literature generally uses a coarser CUT/GRADUAL split. Treat it as a starting point, not an authority.) Bring your own transition taxonomy, your own event categories, your own scene-relation scheme; the tool adapts to your system rather than imposing one. The same flexibility runs through the analysis side: **every metric weight, normalization range, and scoring preset is adjustable**, so CMAT can be tuned to whatever constructs and thresholds your study uses.

### Grade the tool against your coding

- **Precision / recall / F1** per transition type, with a match tolerance you set, and a windowed mode for coding only part of an episode.
- An **error-annotation grid** with a controlled failure-reason vocabulary, so "F1 = 0.17" becomes "the detector misses gentle dissolves under snowfall" — a documented error taxonomy.
- A **parameter sweep** to tune detection settings against your reference coding. It reports a **resubstitution estimate**: the configuration is chosen by taking the maximum over a grid on your coded sample, and the score beside it is computed on that same sample, so it is optimistically biased by construction. CMAT labels it as such in the result, the manifest, the Trials registry and every screen that shows it. The tuning/test split is yours to impose — the software does not hold out data for you, and the coded sample is usually too small to split.
- **Cohen's κ** for the within-scene classifier and **two-coder inter-rater reliability** for event coding.
- Every run writes a **provenance manifest** (parameters, date, tool version) and appears in a **Trials registry** — a browsable audit trail of every sampling + coding study.

CMAT is designed to integrate automated formal-feature extraction, structured
human coding, and corpus-specific validation in the same research workflow.
Its validation records make the basis and limits of an automated result
available for inspection rather than treating the output as self-validating.

---

## Illustrative presets — not validated developmental norms

A preset is a bundle of **composite weights and normalization ceilings**. A
ceiling is the **denominator** of a metric's 0–1 scale, not a limit: exceeding
one means "at or above the top of this scale", never "too much". Changing a
preset changes every composite score and no raw measurement.

**None of the shipped values is derived from anything.** The ceilings were
fitted to what one 78-episode working corpus produced
([CEILINGS.md](CEILINGS.md)); the weights have no recorded derivation at all
([ARCHITECTURE.md](ARCHITECTURE.md) §8.1a). Each preset carries
`"illustrative": true` and `"derivation": "none recorded"` in `config.json`, and
the Settings dialog says so above the chooser in both front-ends.

| Preset | What it is |
|--------|---------|
| General / All Ages | Broad ceilings, so a wide range of content lands inside the scale without clamping |
| Toddler (0–2) | Low ceilings, so small differences between quiet programmes stay visible; content above a ceiling clamps rather than being ranked |
| Preschool (2–5) | Mid-range ceilings |
| Early Childhood (5–8) | Wider ceilings than the preschool configuration |
| Tween (8–12) | Ceilings close to General, so fast content is ranked rather than clamped |
| Animated / Cartoon | Saturation weighted higher, on the working assumption that it discriminates between animated titles and not across live action |
| Live-Action / YouTube | Saturation zeroed (blown-out grading makes it unstable); contrast weighted higher instead |

**An age name says which population a study using the preset is about.** It is
not a recommendation, an appropriateness rating, a safety threshold, or
evidence about that age group. In particular:

- The `Preschool (2–5)` band is the one studied by Lillard & Peterson (2011).
  **The ceilings and weights are not from that paper or any other.** That study
  compared two programmes on children's immediate executive function and
  reports no formal-feature thresholds.
- `Toddler (0–2)` weights flashing more heavily, which changes what the
  composite summarises. **This is not a safety weighting**: the flashing measure
  is unvalidated and implements neither the area threshold nor the red-flash
  criterion.
- "Wider tolerances" and "near-adult tolerances" described the ceilings, not
  any measured tolerance. The wording has been removed.

**Where an inferential claim depends on the composite, define and preregister a
configuration for the study**, and report the weights and ceilings you used
alongside the component measures. Custom presets can be created and saved;
built-in presets cannot be deleted.

---

## Research grounding and interpretation

### Four things that are not the same thing

CMAT keeps these apart everywhere — in the interface, the documentation and the
exports — and asks that write-ups do the same. Collapsing any two of them is
the commonest way a formal-feature measurement is over-read.

1. **An observed, computed property of the stimulus.** "This episode has 11.4
   detected shot boundaries per minute." This is what CMAT produces.
2. **A theoretical construct.** "Pacing." Not observable, not in the file. A
   measure is *offered as* an operationalization of a construct; it is never
   identical to one.
3. **An empirical association reported in prior literature.** "Programmes
   differing in pace differed in children's immediate executive-function
   scores in this experiment." A finding about particular stimuli, samples and
   outcome measures.
4. **An outcome in an individual viewer.** CMAT observes no viewer, has no
   information about a viewer, and predicts nothing about one.

**The literature below motivates measuring these properties. None of it
validates CMAT's detectors, thresholds, scaling ranges, weights, or the
composite.** No paper cited here specifies a cuts-per-minute threshold, a
normalization ceiling, or a weighting scheme, and none was used to derive one.
Where the literature reports associations between media features and child
outcomes, those associations are correlational, contested, and about
particular stimuli and samples — not properties of a number CMAT computes.

### What motivates measuring which property

**Formal features as a class of stimulus property.**
Huston, A. C., Wright, J. C., Wartella, E., Rice, M. L., Watkins, B. A.,
Campbell, T., & Potts, R. (1981). Communicating more than content: Formal
features of children's television programs. *Journal of Communication*,
*31*(3), 32–48. <https://doi.org/10.1111/j.1460-2466.1981.tb00426.x>
— *Motivates:* treating pace, visual change, colour and sound as
content-independent structural attributes worth measuring separately from
content. *Does not:* specify any measure, detector or threshold.

**Rate of change as a processing demand.**
Lang, A. (2000). The limited capacity model of mediated message processing.
*Journal of Communication*, *50*(1), 46–70.
<https://doi.org/10.1111/j.1460-2466.2000.tb02833.x>
— *Motivates:* measuring transition rate at all, and CMAT's separation of
*related* from *unrelated* cuts (the within-scene / scene-change classifier).
*Does not:* license reading any CMAT number as a quantity of cognitive load.
CMAT's classifier is unvalidated and is flagged wherever it appears.

**Visual salience and motion.**
Itti, L., Koch, C., & Niebur, E. (1998). A model of saliency-based visual
attention for rapid scene analysis. *IEEE Transactions on Pattern Analysis and
Machine Intelligence*, *20*(11), 1254–1259.
<https://doi.org/10.1109/34.730558>
— *Motivates:* motion as one feature channel worth extracting. *Does not:*
support any statement about children, about television, or about what a
`motion_mean` value does to a viewer. It is a computational model of image
salience, and CMAT's frame-difference measure is not its saliency map.

### Associations reported in the outcome literature

Cited so a reader can see what the field has looked at. **All correlational or
experimental findings about particular stimuli; none is a property of a CMAT
measurement, and none is evidence about a programme CMAT has measured.**

Lillard, A. S., & Peterson, J. (2011). The immediate impact of different types
of television on young children's executive function. *Pediatrics*, *128*(4),
644–649. <https://doi.org/10.1542/peds.2010-1919>
— Compared 4-year-olds' immediate executive-function performance after
watching a fast-paced fantastical cartoon, an educational programme, or
drawing. **Reports no formal-feature thresholds**, and is not the source of any
value in `config.json` — see the note under
[Illustrative presets](#illustrative-presets--not-validated-developmental-norms).

Lillard, A. S., Drell, M. B., Richey, E. M., Boguszewski, K., & Smith, E. D.
(2015). Further examination of the immediate impact of television on children's
executive function. *Developmental Psychology*, *51*(6), 792–805.
<https://doi.org/10.1037/a0039097>
— Separated pacing from fantastical content across several experiments and
found fantastical content the more consistent factor. This is the motivation
for CMAT's **hand-coded** fantastical-event codebook: the variable is coded by
a person because no pixel measure represents it.

Lillard, A. S., Li, H., & Boguszewski, K. (2015). Television and children's
executive function. In J. B. Benson (Ed.), *Advances in Child Development and
Behavior* (Vol. 48, pp. 219–248). Elsevier.
<https://doi.org/10.1016/bs.acdb.2014.11.006>
— Review of the area, including the mixed and contested findings.

Christakis, D. A., Zimmerman, F. J., DiGiuseppe, D. L., & McCarty, C. A.
(2004). Early television exposure and subsequent attentional problems in
children. *Pediatrics*, *113*(4), 708–713.
<https://doi.org/10.1542/peds.113.4.708>
— Observational, from a parent-reported longitudinal survey. **Measures hours
of exposure, not formal features**, so it motivates nothing CMAT computes; it is
listed because it is the study most often invoked in this area, and because
what it does and does not show is routinely overstated.

### Norm files used by the vocabulary analysis

Neither is redistributed here; both are free for research use. CMAT applies
them as published and has not revalidated either.

Kuperman, V., Stadthagen-Gonzalez, H., & Brysbaert, M. (2012).
Age-of-acquisition ratings for 30,000 English words. *Behavior Research
Methods*, *44*(4), 978–990. <https://doi.org/10.3758/s13428-012-0210-4>
— Supplies the `Age of Acquisition` column. Ratings are adult retrospective
estimates for written English words, from a crowdsourced sample; they are not
observations of when children acquired the words, and CMAT applies them to
lemmatized dialogue, which is a use the norms were not built for.

Brysbaert, M., Warriner, A. B., & Kuperman, V. (2014). Concreteness ratings for
40 thousand generally known English word lemmas. *Behavior Research Methods*,
*46*(3), 904–911. <https://doi.org/10.3758/s13428-013-0403-5>
— Supplies the concreteness column, with the same caveat.

### The readability formulas

Flesch Reading Ease, Flesch—Kincaid, Spache, Dale—Chall, Coleman—Liau and ARI
were developed and validated on **written prose for readers**, not on
transcribed speech. Applied to dialogue they are a relative index across
episodes measured the same way, not a grade level a child can read at, and not
a claim about comprehension. CMAT reports all six rather than one because they
disagree, and the disagreement is informative.

### What CMAT does not claim

CMAT describes the stimulus. It does not predict outcomes for an individual
child, measure cognition, rate appropriateness, assess safety, or establish
that any feature causes any effect. Age, temperament, sensory-processing
profile, viewing context and exposure history are not captured and cannot be
inferred from anything it produces.

---

## Reproducibility and provenance

A number is only reproducible if a reader can identify how it was produced.
This is what CMAT records, and where. Everything below is machine-readable.

### Every episode result

Written into the cache and into JSON exports; empty on results cached before
these fields existed, which is why every reader has to treat an empty value as
*not recorded* rather than as a value.

| Field | What it pins |
|---|---|
| `cmat_version`, `git_commit` | The build. The commit carries `-dirty` when the working tree differed from it, and reads `unavailable (not a git checkout)` for a frozen build — never an empty string, which reads as "clean". |
| `analyzed_at_utc` | When the run finished. |
| `source_bytes`, `source_sha256` | **The input file itself.** A filename is not an identity: files get renamed, re-encoded and trimmed, and CMAT's own Clip Finder writes new MP4s from old ones. The hash survives all of it. |
| `measurement_fingerprint` | A hash of the detector, thresholds and sample rates that produced the raw numbers. **Two rows are comparable only if this matches.** It deliberately excludes weights and ceilings, which are re-scorable from cache and therefore not part of measurement identity. |
| `measurement_tools` | Each measurement's tool and its status, e.g. `PySceneDetect — ContentDetector [validated]`, `Frame differencing [deterministic]`. |
| `config` | The full resolved runtime configuration, not the intended one. |

### Every export

JSON exports carry `export_schema`, `exported_at_utc`, a `software` block
(version, commit, and the versions of Python, OpenCV, NumPy and PySceneDetect
— the libraries that can move a number), and the validation-provenance block.
CSV exports carry the same in a `_PROVENANCE.txt` sidecar written beside them,
which also states the empty-cell and comparability rules. Keep the two
together.

### Every sampling draw

`manifest.json` records the method, allocation, seed, per-stratum seeds'
derivation, `probability` flag, strata, **the candidate frame's episode labels
per stratum** (not only its size, so a redraw against a folder that has since
gained files is detectable), the video extensions and season/episode regexes
that defined a unit, `cmat_version` and `cmat_git_commit`, and any notes the
draw generated. `software_version` is the **sampler module's** version string
and is not a commit; it is displayed under its own name.

### Every validation and coding run

A `*_manifest_*.json` beside the outputs, with the date, commit, detector
configuration, match tolerance, coded window, and counts. Runs appear in the
**Trials registry**, which is a browsable index of these manifests.

**Parameter sweeps additionally record `selection_estimate: "resubstitution"`,
`tuned_and_scored_on_same_data: true`, `held_out_data: false` and the warning
text**, because a grid maximum computed on the sample it was fitted to is not
an estimate of performance and must not be reported as one.

### Every clip exported by Clip Finder

A JSON manifest with the plain-language query, the source episode, absolute
source timecodes, the pool settings (window length, excluded opening and
closing intervals, partial-window rule) and the measurement fingerprint. CMAT
re-measures the exported file, so the manifest describes the participant
stimulus and not only the window it was cut from.

### What is deliberately not recorded

OS build, CPU, and the full installed package list. None of them changes a
metric, and a provenance block nobody reads protects nobody.

---

## Building from source

**Requirements:** Python 3.11+, FFmpeg on PATH

```bash
git clone https://github.com/SamuelBabbertResearch/childrens-media-analysis-toolkit.git
cd childrens-media-analysis-toolkit
pip install -r requirements.txt
python cmat_qt.py
```

**Optional — NLP / vocabulary analysis:**
```bash
pip install spacy wordfreq textstat lexical-diversity
python -m spacy download en_core_web_sm
```

**Optional — Whisper AI transcription:**
```bash
pip install faster-whisper
```

**Run tests:**
```bash
pytest tests/
```

**Build the exe:**
```bash
# Place ffmpeg.exe in the project root first, then:
python -m PyInstaller build.spec -y
copy config.json dist\CMAT\config.json
```

---

## CLI usage

```bash
# Analyze a single episode
python cli.py analyze episode.mp4

# Analyze a whole show folder
python cli.py analyze "My Videos/Little Bear/"

# Build a reproducible episode sample
python cli.py sample "My Videos/Little Bear/" --stratify season --method spread --per-season-n 3 --seed 42

# Run vocabulary complexity analysis on subtitle files
python cli.py vocab "My Videos/Little Bear/"          # folder of .srt/.vtt files
python cli.py vocab episode.srt                       # single file
python cli.py vocab files.txt                         # newline-separated list of paths
python cli.py vocab "My Videos/" --norms data/norms/ --output results/

# Query the index database
python cli.py db episodes "My Videos/" --sort ffc_score --desc
python cli.py db shows "My Videos/" --sort avg_ffc
```

---

## License

MIT License — see [LICENSE](LICENSE)
