# Children's Media Analysis Toolkit (CMAT)

**Open-source video analysis software for children's media research.** CMAT is
a Windows desktop application for reproducible episode sampling, audiovisual
formal-feature analysis, language and subtitle analysis, human coding,
validation, and research-data export.

The visual research pipeline keeps the whole study in one understandable flow:

> **Sampling → Selection → Measurement → Validation → Results**

Start with the supplied workflow, click a stage to configure it, and follow the
connections from source videos to exported evidence. Researchers can use the
default pipeline without programming, while advanced users can rearrange or
extend it to match a study design.

Researchers can also **create their own research constructs without writing
code**. Define the concept in plain language, connect it to CMAT's supported
measures, choose methods and weights, and save the operationalization as a
versioned recipe that can be inspected, reused, and cited.

It has two co-equal halves:

**Custom automated audio-visual sensory composites.** Measure pacing, motion, colour, contrast, flashing, and audio — then choose the tools and thresholds behind each measurement and combine them into a composite *you* configure, rather than one the tool imposes. CMAT also measures the **linguistic complexity** of dialogue through speech rate, readability formulas, vocabulary frequency tiers, age of acquisition, and lexical diversity.

**Structured hand-coding of pacing and fantastical events** — the two features current research focuses on. Code transitions, scene changes, and impossible events against a built-in frame-accurate video player, using your own category systems, and get metrics computed with the same definitions as the automated path.

Then **validate one against the other**: grade the automated detection against your own coding (precision/recall/F1, Cohen's κ, inter-rater reliability) so you know how far to trust it. See [Manual coding & validation](#manual-coding--validation).

CMAT does **not** issue a verdict on appropriateness. Every composite score shows its component parts, and every design decision in the scoring model is adjustable.

> **Part of the Open Children's Media Index** — an ongoing effort to build a publicly accessible database of formal-feature measurements for children's television.

---

## A visual pipeline for children's media research

CMAT presents a study as five connected stages instead of a collection of
unrelated analysis tools:

| Stage | What the researcher does | What CMAT preserves |
|---|---|---|
| **Sampling** | Draw a census, random sample, systematic sample, or sample stratified by season or era | Selected episodes, random seed, method, strata, and manifest |
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

### Sensory load metrics

| Metric | What it captures |
|--------|-----------------|
| **Scene pacing** | How fast the camera cuts. Faster cutting triggers more frequent orienting responses and higher cognitive load. |
| **Motion** | Average frame-to-frame movement. High motion is a pre-attentive attention magnet. |
| **Color saturation** | How vivid and pure the colors are. Higher in animation; lower in live-action. |
| **Color contrast** | Spatial spread of brightness within a frame. Captures dark/light extremes that drive visual intensity. |
| **Flashing** | Rapid luminance changes per minute. Relevant to photosensitivity and overstimulation. |
| **Audio loudness** | Average RMS volume and dynamic range. Loud, consistent audio drives arousal independently of visuals. |
| **Sensory load score** | A transparent weighted composite of all the above. Always shows its component parts. |

### Language metrics *(optional — requires subtitle files or Whisper AI)*

| Metric | What it captures |
|--------|-----------------|
| **Words per minute** | Average spoken word rate during dialogue segments. Sourced from `.srt`/`.vtt` subtitle files; Whisper AI transcription used as fallback when enabled. |
| **Speech density** | Fraction of episode runtime containing dialogue. Separates talk-heavy shows from those with long musical or silent passages. |
| **Readability** | Flesch Reading Ease, Flesch-Kincaid Grade Level, Spache, Dale-Chall, Coleman-Liau, ARI — six formulas applied to the cleaned dialogue transcript. |
| **Vocabulary frequency tiers** | Zipf-scale tier breakdown: Tier 1 (everyday words, ≥ 4.5), Tier 2 (academic/cross-domain, 3.0–4.5), Tier 3 (rare/domain-specific, < 3.0). |
| **Age of Acquisition** | Mean age at which vocabulary words are typically learned, from Kuperman et al. norms. |
| **Lexical diversity (MTLD)** | Measure of Textual Lexical Diversity — how widely the dialogue draws on the available vocabulary, robust to text length. |

The **measurement set** is grounded in the Huston & Wright formal features framework and Lang's Limited Capacity Model (LC4MP); Lillard & Peterson (2011) is among the correlational findings usually cited.

Those frameworks motivate *which* properties are worth measuring. They do not specify how to combine them into one number, and nothing else does either: the composite's weights and normalization ceilings are a configurable scaling convention, not derived from theory and not validated. Component measures are reported separately everywhere for that reason. See [CEILINGS.md](CEILINGS.md).

> **Honest limitation:** This tool measures the stimulus, not the viewer. It cannot account for a child's age, temperament, or sensory-processing profile. Output is a profile to inform judgment, not a rating or verdict. All findings are correlational.

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
- Choose a selection method: census, simple random, systematic, or spread (chunk) sampling
- Set your sample size and random seed
- Preview the selected episodes, then **Send to Analysis Queue** to analyze only those episodes
- The sampler saves a `manifest.json` and `selected.csv` alongside your output — a permanent record of exactly how the sample was drawn

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
| **Y-axis** | Sensory Load Score · Cuts per Minute · Color Saturation · Color Contrast · Motion · Flashing / min · Audio RMS |
| **Colour by** | Season · Era |

**Era stratification** — Click **Edit Eras…** to define named date ranges (e.g. *Original Run 1992–1997*, *Revival 2003–2006*). Each era gets its own bar colour; episodes outside all defined ranges appear in gray. Eras are saved per-show to the local database and reload automatically the next time you open the chart.

### 7. Browse and compare

- **Index tab** — Sortable, filterable table of every analyzed episode and show. Columns include Air Date, Season, and Episode Number alongside all analysis metrics. Click any column header to sort; type in the filter bar to search.
- **Compare** — Click **Pin for Compare** on any episode result, then **Compare with Pinned** on another to see a side-by-side metric table.
- **Notes** — Add per-episode notes in the results panel; saved automatically to the local database.

### 8. Adjust weights and presets

**Settings → Sensory Load Weights** — change how much each metric contributes to the composite score, or adjust normalization ceilings. Age-range and content-type presets are built in. Switching presets re-scores all cached results instantly — no re-analysis needed.

### 9. Analyze speech and vocabulary

The **Language tab** surfaces dialogue-level metrics that are independent of the sensory-load composite.

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

## Manual coding & validation

Automated detection is only trustworthy if you know how accurate it is. CMAT includes a full **human-coding and validation workbench** so researchers can measure the tool against their own hand-coded ground truth — and code the things a pixel measure cannot see.

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
- A **parameter sweep** to tune detection settings against your ground truth (with train/test discipline built into the workflow).
- **Cohen's κ** for the within-scene classifier and **two-coder inter-rater reliability** for event coding.
- Every run writes a **provenance manifest** (parameters, date, tool version) and appears in a **Trials registry** — a browsable audit trail of every sampling + coding study.

> This makes CMAT, to our knowledge, the only open, integrated tool that both extracts formal media features automatically *and* validates that extraction against human coding — reporting its own accuracy rather than asking you to trust it.

---

## Age-range presets

| Preset | Best for |
|--------|---------|
| General / All Ages | Cross-genre comparison baseline |
| Toddler (0–2) | Tight ceilings; flashing weighted higher for safety |
| Preschool (2–5) | Calibrated to Lillard & Peterson (2011) age range |
| Early Childhood (5–8) | Wider tolerances than preschool |
| Tween (8–12) | Near-adult tolerances |
| Animated / Cartoon | Saturation weighted higher for cartoon-vs-cartoon comparison |
| Live-Action / YouTube | Contrast weighted higher; saturation near-zeroed |

Custom presets can be created and saved. Built-in presets cannot be deleted.

---

## Research grounding

The conceptual framework comes from media research on **formal features** — the perceptually salient, content-independent structural attributes of video (cuts, motion, pace, sound). These features capture attention through the **orienting response**: an automatic, reflexive reallocation of attention toward novel or changing stimuli.

Key references:
- Huston & Wright — formal features framework
- Lang — Limited Capacity Model of Mediated Message Processing (LC4MP)
- Lillard & Peterson (2011), *Pediatrics* — pacing and immediate executive function in 4-year-olds
- Lillard et al. (2015) — fantastical content as a possible moderator
- Christakis et al. (2004), *Pediatrics* — early TV exposure and attention (correlational)
- Itti & Koch — bottom-up visual saliency and motion
- Kuperman et al. (2012) — Age of Acquisition norms
- Brysbaert et al. (2014) — Concreteness norms

All findings are correlational. CMAT describes the stimulus; it does not predict outcomes for any individual child.

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
python cli.py db episodes "My Videos/" --sort sensory_load_score --desc
python cli.py db shows "My Videos/" --sort avg_load
```

---

## License

MIT License — see [LICENSE](LICENSE)
