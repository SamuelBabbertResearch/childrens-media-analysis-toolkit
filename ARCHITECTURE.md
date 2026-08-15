# CMAT — Architecture

How the system is put together, for a developer or a Claude session reading it
cold. Rules live in `CLAUDE.md`; this file explains the shape.

---

## 1. The pipeline model

Everything in CMAT maps onto one research workflow. If a feature does not
belong to a stage, it does not belong.

```
Sampling ─→ Selection ─→ Measurement ─→ Validation ─→ Results
                            │  ▲
                            │  └── hand coding feeds validation
                            └───── automated coding
```

| Stage | Question it answers | Where it lives |
|---|---|---|
| **Sampling** | Which episodes were chosen, and how? | `analyzer/sampler.py`, `analyzer/trials.py` |
| **Selection** | Which of them is the working set? | `analyzer/show_index.py`, `analyzer/pipeline.py` |
| **Measurement** | What are the numbers? | `analyzer/engine.py` and the `metrics_*` modules |
| **Validation** | How wrong is the tool, against a human? | `analyzer/validation.py`, `analyzer/event_coding.py` |
| **Results** | What does the corpus look like? | `analyzer/aggregate.py`, `analyzer/db.py`, `ui/report.py` |

Two things follow from the diagram that are easy to get wrong:

- **Measurement has two tracks, and either can be used alone.** Automated
  coding and hand coding are both measurement. Hand coding is not merely a
  step towards validating automation — a study may hand-code and never
  automate anything. This was not always true of the interface: hand coding
  used to be reachable only *inside* the validation screen, which framed it as
  a step towards checking the automation. Separating them (2026-08-04) is why
  the tabs are shaped as they are.
- **Validation compares the two tracks.** It needs both, which is why a
  hand-coding-only study has no validation stage and that is correct rather
  than incomplete.
- **Validation is on a subset, not the whole sample.** The automated pass runs
  on every sampled episode; a small subset is also hand-coded and the two are
  compared to estimate the tool's error, which is then reported alongside the
  automated numbers. Hand-coding the whole sample would make the automated
  measure redundant for those episodes.

### What a stage produces

| Stage | Artefact | Where it lands |
|---|---|---|
| Sampling | a named **trial** manifest + episode list | `validation/*_manifest_*.json` |
| Selection | the working set | in-memory, from the manifest or the library |
| Measurement (auto) | `EpisodeResult` | `.analysis/<show>/<stem>.json` |
| Measurement (hand) | a coding sheet | `validation/<stem>_events.csv`, `_cuts_*.json` |
| Validation | precision / recall / F1, Cohen's κ | `validation/` + the Trials tab |
| Results | aggregates, exports, the published index | `.analysis/`, `_site/` |

**Intro templates** (`analyzer/intro_templates.py`) exist because coding the
same title sequence for every episode of a season is transcription rather than
judgement, and it inflates agreement statistics. Code it once, label it, reuse.

### The research context: which episodes the application is working on

The stages above describe a *study*. The **research context** is the smaller,
live question the interface has to answer every moment it draws a list: which
episodes am I showing right now?

`analyzer/scope.py` owns it. A `Scope` is either the whole library or exactly
the episodes one documented draw selected, and `MainWindow._scope` is the
current one. It is set by drawing a sample, by choosing a pipeline, or from the
**Showing:** chooser on the toolbar.

Three properties that are load-bearing:

- **It is a view, never a filter on the record.** Narrowing it hides rows. It
  deletes nothing, re-measures nothing, and changes no cached result.
- **It is never persisted.** The application always opens on the whole library.
  Restoring a narrowed library with no memory of having narrowed it is the
  failure the visible chooser exists to prevent.
- **Paths are normalised on entry.** A draw's `selected.csv` and the library
  walk produce two spellings of one path, so `Scope.contains()` is the only
  sanctioned membership test — see `LEARNINGS.md` on the sampler's CSV paths.

Not every screen obeys it yet. The Library and the Index do; the measurement
tabs still take one episode from the Library selection. `TODO.md` § *The
research context, continued* has the rest, and
`design/CMAT_PIPELINE_INTERACTION_MODEL.md` Phase 2 is where the idea comes
from.

**Scope is not Selection.** Selection is the pipeline stage — which episodes
belong to a study. Scope is what the interface is currently showing. They
usually coincide, and they are still different questions; see `CLAUDE.md` §3.

## 2. Authoritative state versus derived state

This distinction decides where a change belongs.

| Kind | What it is | Lives in | Rebuildable? |
|---|---|---|---|
| **Authoritative** | The video files | `<root>/ShowName/*.mp4` | no — the source |
| **Authoritative** | Hand coding | `validation/*.csv` | no — a person typed it |
| **Authoritative** | Pipeline documents | `<root>/.analysis/pipelines/*.json` | no — the user drew them |
| **Authoritative** | Scoring config | `config.json` | no — versioned and shared |
| **Derived** | Episode results | `<root>/.analysis/<show>/<stem>.json` | yes — re-analyse |
| **Derived** | Show aggregates | computed on demand from cached results | yes |
| **Derived** | The SQLite index | `<root>/.analysis/index.db` | yes — re-analyse |
| **Derived** | Pipeline *status* | computed by `analyzer/pipeline.py` from disk | yes |
| **Derived** | The research context | `analyzer/scope.py`, from a draw's `selected.csv` | yes — and deliberately **not** persisted between launches |
| **Derived** | Show-level rows in the Index | `db.summarise_shows()`, from the episode rows on screen | yes |

Derived state is never the record. If a derived file disagrees with the
authoritative source, the source wins and the derived file is stale.

## 3. Scoring settings versus measurement settings

The single most consequential distinction in the codebase.

- **Scoring** — weights, normalization ceilings. Applied to metrics that have
  already been computed. Changing them re-scores from cache instantly and
  invalidates nothing. This is what the Settings dialog edits.
- **Measurement** — detector choice, thresholds, sample rates. Changes the raw
  numbers, so every cached result measured under the old settings is stale.

`analyzer/measurements.py` fingerprints the measurement settings (SHA256[:12],
weights excluded) into each result, so staleness is detectable rather than
assumed. Results predating fingerprinting are grandfathered rather than
invalidating an existing corpus.

## 4. Data flow

```
MP4 ─→ analyzer/engine.py ─→ EpisodeResult ─→ cache (.analysis/<show>/*.json)
                                    │                    │
                                    │                    ├─→ db.upsert_episode ─→ index.db
                                    │                    └─→ aggregate.py ─→ ShowAggregate
                                    └─→ ui/report.py ─→ HTML ─→ QTextBrowser
```

- `EpisodeResult` (`analyzer/schema.py`) is the unit of measurement. Everything
  downstream reads it; nothing recomputes from video.
- The cache is keyed `<root>/.analysis/<show_key>/<stem>.json`, where
  `show_key` is the POSIX relative path from the root. **Renaming a show
  folder orphans its cache** — see `LEARNINGS.md`.
- The index is keyed on the **resolved absolute** `file_path`. It is derived,
  so rebuilding it is always safe.
- **The Index tab does not read the `shows` table.** It queries episode rows,
  narrows them to the research context, and summarises them with
  `db.summarise_shows()`, so its Shows view is its Episodes view by
  construction. The stored table is written by `upsert_show` on a whole-show
  analysis only, and goes stale when episodes are analysed one at a time —
  measured at 2 episodes / 0.3071 against a true 5 / 0.2557. `cli.py db
  --shows` and `gui.py` still read it. See `LEARNINGS.md`.

## 5. Front-end structure

`analyzer/` imports no GUI framework. That is what made the Tk → Qt move a
presentation rewrite rather than an application rewrite, and it is worth
protecting.

```
analyzer/   engine + data model      (no GUI imports — enforced by test)
  scope.py    the research context — which episodes are current, and the only
              reader of a draw's selected.csv
cli.py      thin layer over analyzer
gui*.py     Tk front-end             (THE CURRENT SOFTWARE)
ui/         Qt front-end             (in progress — not yet the product)
```

Both front-ends read the same project folder, cache, config and preferences,
so they can be run against one project and compared directly.

## 6. The visual pipeline UI

A central product feature, not decoration. It is how a researcher sees what
the software is actually doing.

- A **pipeline document** (`analyzer/pipeline_graph.py`) is a graph the user
  owns: nodes they placed, connections they drew, a name they chose. It
  round-trips through plain dicts, so undo is a snapshot of `to_dict()` and
  persistence is `json.dump` of the same thing.
- **Node positions live in the document, not the view.** Resizing the window
  moves the viewport, never the diagram.
- **Node types are a registry.** A new stage is a dict entry in `NODE_TYPES`,
  not a UI rewrite. The original stages are ordinary nodes with no special
  casing anywhere.
- **Connections are objects with explicit endpoints**, so the graph can branch
  and merge rather than assuming one linear chain. `connect()` refuses
  self-links, duplicates, and anything that would close a cycle.
- A node binds to live status through `NodeType.stage_key`, which
  `analyzer/pipeline.py` derives from what is on disk. A pipeline not linked
  to an episode sample reports **"no data source"** — that is its true state,
  not a placeholder.

`analyzer/pipeline.py` (derived, read-only status) and
`analyzer/pipeline_graph.py` (the editable document) are two halves that meet
at `stage_key`. Neither hardcodes the other.

## 7. Threading

Analysis runs on a worker thread with a progress callback; the interface never
freezes. `ui/automated.py` holds the only worker.

Cancellation is not a flag on the engine: `analyze_show_batch` wraps each
episode in `except Exception`, so an ordinary exception raised from the
progress callback would be swallowed and recorded as a *failed* episode. The
cancel signal therefore derives from `BaseException`.

## 8. The metrics, exactly

Every formula, its units, and what it does **not** capture. Source of truth is
`analyzer/metrics_*.py` and `analyzer/schema.py`.

### 8.1 What actually feeds the composite

Only **six** numbers enter `sensory_load`. Everything else is measured,
reported, and **not scored**:

| In the composite | Reported but NOT scored |
|---|---|
| `scene_pacing.cuts_per_min` | `shot_length.mean_sec`, `median_sec`, `shots_per_min`, `count` |
| `color_saturation.mean` | `scene_pacing.shot_length_cv` |
| `color_saturation.contrast_mean` | `color_saturation.temporal_var` |
| `motion.mean` | `motion.peak` |
| `flashing.luminance_delta_events_per_min` | `audio.rms_peak`, `rms_temporal_var`, `dynamic_range_db` |
| `audio.rms_mean` | all speech and vocabulary metrics; fantastical events; dissolves; scene relation |

This surprises people. A show with violent volume swings and a show with
constant loudness score identically on audio, because only `rms_mean` counts.
Say "sensory load" when you mean the composite and name the metric otherwise.

### 8.1a What the composite's shape is NOT justified by — an open gap

Three choices are load-bearing and **have no recorded rationale anywhere**.
They are listed here so nobody mistakes silence for justification, and because
a Methods section or a reviewer will ask about each one first.

1. **Why a weighted linear sum at all.** The composite is
   `Σ(weight × normalised value)`. Nothing records why an additive model was
   chosen over standardised z-scores, a principal component, or a factor
   score. A linear sum assumes the components are commensurable and
   independently additive; neither has been tested.
2. **Why these default weights** — pacing 25%, saturation 5%, contrast 10%,
   motion 25%, flashing 15%, audio 20%. Pacing and motion carry five times the
   weight of saturation. That is a substantive theoretical claim about what
   drives sensory load, and it is written down nowhere. The per-preset
   `description` fields in `config.json` explain each preset's *emphasis*, not
   the base weighting.
3. **Where the ceilings came from.** `cuts_per_min` max 60, contrast max 0.35,
   flashing max 30/min, audio RMS max 0.2. No source, derivation, or corpus is
   recorded for any of them, and they set the scale every score sits on.

The theoretical grounding is named — Huston & Wright's formal features, Lang's
LC4MP (`CLAUDE.md` §2.2) — but **nothing maps a specific metric to a specific
construct**, which is the step that would justify 1 and 2.

Until this is written down, the composite is best described as *a configurable
weighted index whose defaults are a working judgement*, not as an operational
measure of a construct. That framing is honest and defensible; claiming more
would not be. See `TODO.md`.

#### What IS recorded, and what the corpus shows (2026-08-14)

An evidence pass, to separate "undocumented" from "undocumentable". Nothing
below is a reconstructed rationale — it is what the repository and the measured
data actually contain.

**Recoverable.** The per-preset `description` fields do give reasons for each
preset's *departure* from the base weighting, and they are substantive:
Animated raises saturation because "vivid cartoon palettes are a meaningful
stimulation dimension in animation"; Live-Action zeroes saturation because
"blown-out production style makes it unreliable" and moves that weight to
contrast. Preschool cites Lillard & Peterson (2011) — but **for the age band,
not for the ceilings**. `DECISIONS.md` states that "`Toddler (0-2)` names the
literature the ceilings come from"; no citation appears in `config.json` or
anywhere else, so that claim is currently unsupported by the artefact.

**Not recoverable from the repository.** The base weights and every ceiling
arrive in the initial commit (`62d402f`) with no derivation in the history.
`git log -S` on `config.json` returns that commit alone.

**The finding that changes how gaps 2 and 3 must be written up: the weights and
the ceilings are not separable, and the nominal weights are not what the
components actually contribute.** Over the 15 episodes in the live index:

| Component | Nominal weight | Mean normalised value | Share of the mean composite |
|---|---|---|---|
| Pacing | 25% | 0.253 | 28.0% |
| Saturation | 5% | 0.451 | 10.0% |
| Colour contrast | 10% | 0.549 | **24.3%** |
| Motion | 25% | 0.064 | **7.0%** |
| Flashing | 15% | 0.210 | 13.9% |
| Audio | 20% | 0.191 | 16.9% |

Motion is nominally joint-heaviest at 25% and contributes **7%** — less than
saturation, which is nominally weighted five times lower. Colour contrast is
nominally 10% and contributes **24%**. The cause is the ceilings: observed
`motion_mean` reaches 0.086 against a ceiling of 1.0 (8.6% of range), while
`color_contrast_mean` reaches 0.216 against 0.35 (62%). A weight only means
what its ceiling lets it mean.

Consequently the composite occupies a narrow band — scores here run **0.132 to
0.295** on a 0–1 scale. This is not an argument that the defaults are wrong; a
ceiling chosen as a fixed absolute reference rather than a corpus maximum is a
legitimate choice, and §8.2 already explains why fixed ranges make runs
comparable. It is an argument that **"the weights are 25/5/10/25/15/20" is not
a description a reader can act on**, and that any write-up must give the
effective contributions beside the nominal weights.

**Therefore, three things must be recorded together or none of them mean
anything:** the model form, the weights, *and* the ceilings the weights operate
against.

#### The actual provenance of the defaults (established 2026-08-14)

The question "why these numbers" was put to the project's author, who is the
researcher rather than the implementer. **The answer is that no one derived
them.** The weights, the ceilings and the additive form were produced by an AI
coding assistant during implementation as plausible-looking starting values, and
were never traced back to a source. They are not the researcher's expert
judgement, and they are not from the literature.

This is recorded here deliberately, because the alternative failure is worse:
a gap in the record invites a later reader — including a future session — to
assume a rationale existed and reconstruct one. There is none to reconstruct.

**What the theory citations do and do not cover.** Huston & Wright's formal
features and Lang's LC4MP legitimately motivate **which properties are
measured** — cuts, motion, saturation, contrast, luminance change and audio
intensity are formal features, and that framing is sound. Neither framework
specifies **how to combine them into one number**, and neither supplies a
weight or a ceiling. The citations support the measurement set; they do not
support the composite.

**What the repository does record** is two occasions where the researcher's
judgement corrected the measure — audio was added after a dance video scored
below an episode of *Little Bear*, and colour contrast after saturation alone
favoured gentle animation (`DECISIONS.md` § Foundations). Note what those are:
decisions about **which metrics exist**, driven by outputs contradicting an
expert's expectation. There is no recorded instance of the **weights or
ceilings** being tuned that way.

**Consequences that are now settled rather than open:**

1. The composite must be described as *a configurable weighted index with
   unvalidated default parameters*, never as an operational measure of a
   construct — which is what this section already said, now for a definite
   reason rather than a missing one.
2. `DECISIONS.md`'s statement that "`Toddler (0-2)` names the literature the
   ceilings come from" is **not supported** and should not be repeated.
3. Any public wording implying the *composite* is empirically or theoretically
   grounded overstates it. The measurement set is grounded; the weighting is
   not. See `TODO.md`.
4. The defaults being arbitrary is **not** a reason to change them. Changing
   them now would break comparability with every score already computed, for no
   gain in justification. The fix is disclosure, plus the effective-contribution
   table above.

### 8.2 Normalization, and the ceiling that discards information

```python
normalized = clamp01((value - ref.min) / (ref.max - ref.min))
```

Min-max against **fixed** reference ranges from the active preset — not
per-corpus — so scores are comparable across runs. The clamp is the part worth
knowing:

- **Everything above the ceiling becomes 1.0 and is indistinguishable.** Under
  the Toddler preset (8 cuts/min ceiling), a show at 12 and a show at 40 both
  read 1.0 on pacing.
- Under a broad ceiling the opposite happens: with `cuts_per_min` max 60,
  ordinary children's television sits in the bottom fifth of the scale and real
  differences look small.

That is the intended behaviour of a fixed range, not a bug — it is why presets
exist, and why a comparison that looks flat should be re-read under a different
preset before anyone concludes the shows are alike.

### 8.3 Missing audio redistributes its weight

When there is no audio track or no FFmpeg, the audio weight is spread
**proportionally** across the five visual metrics so the score stays on 0–1,
and `sensory_load.audio_available` records that it happened.

The score remains on the same scale but is **not composed the same way**. Two
episodes at 0.30, one with audio and one without, are not the same claim.
Always check `audio_available` before comparing.

### 8.4 Frame metrics — one pass, `sample_fps` = 2

`grab()` skips frames without decoding; `read()` runs only on sampled frames.

| Metric | Formula | Units |
|---|---|---|
| `color_saturation.mean` | mean of HSV **S** channel ÷ 255 | 0–1 |
| `color_saturation.temporal_var` | **variance** (not SD) of the sampled saturation series | — |
| `color_saturation.contrast_mean` | mean over frames of the **spatial** SD of the HSV **V** channel ÷ 255 | 0–1 |
| `motion.mean` (`absdiff`) | mean of \|gray − prev_gray\| ÷ 255 | 0–1 |
| `motion.mean` (`farneback`) | mean optical-flow magnitude ÷ **20**, capped at 1.0 | 0–1 |
| `motion.peak` | max of the sampled motion series | 0–1 |

Three traps:

- **`contrast_mean` is spatial, not temporal.** It is how much brightness
  varies *within* a frame, averaged over frames — dramatic lighting — not how
  much brightness changes between frames.
- **Motion depends on the sample rate.** It compares *consecutive sampled*
  frames, so at 2 fps it measures change across 500 ms. Change `sample_fps` and
  every motion value changes. They are not comparable across sample rates.
- **The Farneback ÷ 20 is an arbitrary scale factor**, and that tool is
  unvalidated. Do not mix `absdiff` and `farneback` values in one corpus.

### 8.5 Flashing — the weakest metric in the set

```python
is_flash = abs(luminance - prev_luminance) > flashing_luminance_threshold
luminance = mean(grayscale) / 255
```

Counted per sampled frame pair at `flashing_sample_fps` (**10**, higher than
the 2 fps used for everything else, because flashes are short), then divided by
duration.

What it cannot do, and must never be claimed to do:

- It is a **whole-frame mean**, so a bright flash in one corner is diluted to
  nothing.
- It implements **neither the area threshold nor the red-flash criterion** that
  broadcast photosensitivity guidance specifies.
- The tool is **unvalidated**.

It is a relative indicator for comparing episodes measured the same way. It is
**not a safety assessment**, and CMAT must never present it as one.

### 8.6 Cuts, shots, and pacing

| Metric | Formula |
|---|---|
| `shots_per_min` | number of shot durations ÷ duration in minutes |
| `cuts_per_min` | number of cut timestamps ÷ duration in minutes |
| `shot_length_cv` | SD(durations) ÷ mean(duration) — coefficient of variation |

`shots ≈ cuts + 1`, so the two rates differ slightly; they are not synonyms and
the difference grows as episodes get shorter. `shot_length_cv` is the rhythm
measure: high means bursty, low means metronomic. It is **not** in the
composite.

Edge case: a video with no detected cuts yields one shot spanning the whole
file, `cuts_per_min` 0.0 and `cv` 0.0 — which looks like a valid measurement of
an extremely slow episode and may instead mean detection failed.

### 8.7 Audio — linear RMS, not loudness

| Metric | Formula |
|---|---|
| `rms_mean` | mean of per-window RMS |
| `rms_peak` | loudest window |
| `rms_temporal_var` | variance of the per-window RMS series |
| `dynamic_range_db` | `20 · log10(peak ÷ mean)` |

- **Linear RMS, not LUFS.** No perceptual weighting, so it is not a loudness
  measurement in the broadcast sense and cannot be compared to LUFS figures.
- **`dynamic_range_db` is peak-to-mean**, not the peak-to-noise-floor that
  "dynamic range" usually means. It is 0.0 when the mean is ~0.

### 8.8 Speech — WPM is a rate *while speaking*

```python
wpm     = total_words / (total_dialogue_sec / 60)
density = total_dialogue_sec / duration_sec
```

**This is the single most misread metric in CMAT.** `words_per_minute` divides
by **dialogue time, not runtime**. It measures how fast characters talk when
they talk — not how talkative the episode is. A near-silent episode with one
rapid line can post a high WPM.

Talkativeness is `speech_density` (0–1). Report the two together or neither.

Also: captions are parsed for cue timings, so density inherits the caption
file's timing quality. Under 0.5 s of total dialogue the result is reported as
unavailable rather than as zero. **English only.**

### 8.9 Naming mismatch to watch

The config weight key is `color_contrast`; the component attribute is
`contrast`. Same quantity, two spellings — check which one a given piece of
code expects.

## 9. What is validated, and what is not

**Read this before quoting any number from CMAT.** The registry
(`analyzer/measurements.py`) carries a status per tool, and
`analyzer/provenance.py` carries the self-reported accuracy. Both are in the
code so the interface, the exports and the paper cannot drift apart.

| Measurement | Tools (status) |
|---|---|
| `transitions` | `pyscenedetect_content` **validated** · `pyscenedetect_adaptive` *unvalidated* · `transnetv2` *experimental* |
| `motion` | `absdiff` **validated** · `farneback` *unvalidated* |
| `color` | `hsv_mean` **validated** |
| `audio` | `ffmpeg_rms` **validated** |
| `speech` | `captions_only` **validated** · `captions_then_whisper` *unvalidated* |
| `sampling` | `uniform` **validated** |
| `flashing` | `luminance_delta` — ***unvalidated*** |
| `dissolves` | `cmat_plateau` — *experimental* |
| `scene_relation` | `frame_similarity` — ***unvalidated*** |

Five statuses, and they mean different things. The table above shows only the first three; the last two apply to whole metric families (see `METRIC_STATUS` in `analyzer/provenance.py`):

- **validated** — graded against human coding.
- **unvalidated** — works, ungraded. Flag it wherever its numbers appear.
- **experimental** — ungraded *and* known to be rough.
- **deterministic** — colour, motion and audio are direct signal measurements
  with no detection or classification step to validate.
  **Flashing is NOT in this group**, though `analyzer/provenance.py` described
  it as such until 2026-08-14 — and that description was published on the
  site and in every PDF. The *signal* is deterministic; whether the whole-frame
  luminance mean counts the right events is a separate question and is
  unvalidated, which is why the registry marks it so and why it is flagged
  wherever its numbers appear.
- **human** — fantastical events. The tool structures the coding; it does not
  detect fantasy.

### The headline accuracy figure

```
transition-boundary F1 = 0.85 aggregate, range 0.75–0.91 across production styles
matched type-agnostically within ±2 s
```

Everything in that sentence is load-bearing:

- **Type-agnostic.** It scores whether a transition was detected *there*, not
  whether the right *kind* was detected. Type classification scores lower and
  is reported separately.
- **±2 s** is the default match tolerance (`compare_detections`).
- **PRELIMINARY.** A small single-coder pilot. Inter-rater reliability and a
  larger sample are outstanding.
- Weakest on dissolve-heavy, low-contrast and visually noisy footage.

**Which runs the aggregate covers** (confirmed 2026-08-14 by recomputing from
the comparison CSVs; `local_hard_cut_f1` reproduces it):

| Episode | Detector | TP | FP | FN | F1 |
|---|---|---|---|---|---|
| A Charlie Brown Christmas 1965 | `content-t27-diss` | 32 | 10 | 11 | 0.753 |
| Little Bear 1x01 | `content-t27-diss` | 71 | 4 | 10 | 0.910 |
| **pooled** | `content-t27-diss` | **103** | **14** | **21** | **0.855** |

Two episodes, one detector — the shipped ContentDetector configuration. The
range endpoints are those two episodes, not a distribution. TransNetV2
(`transnet-t0.5-solo`) scores 0.902 / 0.942, pooled **0.928**, and is reported
separately; the two detectors are never pooled.

**Coverage is the first ~5 minutes of each, not whole episodes.** Every
comparison manifest records a scoring window: Charlie Brown 0–300 s (43 of 45
marks), Little Bear 0–320 s (81 of 86). The figure therefore rests on **~10
minutes 20 seconds of video in total**. Stated here because "two episodes"
overstates it, and `CLAUDE.md` §2.2 forbids the figure without its qualifiers.

**The human reference is quantised to whole seconds** and biased ~0.55 s early
(mean human − tool: −0.523 s CB, −0.610 s LB), because the marks were hand-typed
in `mm:ss` while watching rather than stamped from the player clock. Correcting
the full bias moves pooled F1 by +0.008 — the ±2 s tolerance absorbs it. The
consequence that matters: **the tolerance cannot be tightened below ~1 s without
recoding at frame resolution**, because below that it measures the coding
resolution rather than the detector. Assessed 2026-08-14; see
`validation/VALIDATION_LOG.md`.

**It is scored on the `ALL` row** — every transition type a human coded — not
on `hard_cut` alone. The hard_cut-only figures for the same two runs are 0.841
and 0.964, and that pair is the superseded "0.84–0.96" reference range. Both
numbers are correct; they answer different questions. The 2026-08-08 log entry
moved the published basis to `ALL` because the tool is scored against
everything a coder marked.

**The name was fixed 2026-08-14.** Until then the constants, the function and
the exported JSON key all said *hard-cut* for this type-agnostic figure — a
name pointing at a real but different pair of numbers, which is the worst kind
of wrong name. They are now `REFERENCE_BOUNDARY_F1_RANGE` / `_AGG`,
`local_boundary_f1()`, and `boundary_f1` / `boundary_f1_source` in
`validation_dict()`. The exported block also gained `boundary_f1_basis`, which
states the estimand in words, and `provenance_schema` (now **2**) so a file
written before the rename is identifiable: **schema 1 is any file with no
`provenance_schema` key, and its `hard_cut_f1` field holds this same ALL-row
figure despite the name.** Nothing in CMAT reads the block back, so no
in-repo artefact needed converting.

### Two different accuracy claims

Event-level accuracy and **count** accuracy are different estimands. A detector
can produce a dependable episode-level cut count while misplacing individual
transitions, because false positives and false negatives cancel. Report both,
and frame the count result as an estimand-specific check — never as a
substitute for event-level validation.

Matching uses **maximum-cardinality** matching (`_max_cardinality_match`), not
greedy: greedy under-counts true positives when detections cluster, and an
external review found the earlier implementation wrong in exactly that way.

### Do not fold these into the composite yet

`scene_changes_per_min` and `within_scene_cut_fraction` rest on the
`scene_change_similarity_threshold` of **0.55**, which is unvalidated. Tune it
against the hand-coded ground truth in `validation/` first.

## 10. Configuration defaults

Real values from `config.json`. Changing anything in the left column is a
**measurement** change and makes cached results stale.

| Key | Default | What it does |
|---|---|---|
| `sample_fps` | `2.0` | frame sampling rate for colour and motion |
| `flashing_sample_fps` | `10.0` | higher rate for the flashing pass — flashes are short |
| `cut_detection_threshold` | `27.0` | PySceneDetect content threshold |
| `flashing_luminance_threshold` | `0.1` | frame-to-frame luminance change counting as a flash |
| `dissolve_detection_enabled` | `False` | off by default — experimental |
| `dissolve_noise_floor` | `3.0` | |
| `dissolve_min_frames` | `15` | |
| `cut_classification_enabled` | `True` | within-scene vs scene-change labelling |
| `cut_classification_offset_sec` | `1.0` | how far either side of a cut is compared |
| `scene_change_similarity_threshold` | `0.55` | **unvalidated** — see above |
| `speech_transcription_enabled` | `False` | Whisper fallback; off by default |
| `speech_whisper_model` | `base` | |

Seven built-in presets, each with its own weights **and** ceilings: General /
All Ages, Toddler (0-2), Preschool (2-5), Early Childhood (5-8), Tween (8-12),
Animated / Cartoon, Live-Action / YouTube. Built-ins cannot be deleted. The two
format presets exist because saturation systematically favours animation — see
`DECISIONS.md`.

## 11. Test suite

234 collected: 221 passed, 13 skipped. What each file protects:

| File | Guards |
|---|---|
| `test_engine_isolation.py` | **the engine imports no GUI framework** — the invariant everything rests on |
| `test_measurements.py` | the registry, fingerprinting, staleness detection |
| `test_metrics.py` | the metric functions |
| `test_pipeline.py`, `test_pipeline_graph.py` | derived status; the editable document, undo, cycle refusal |
| `test_batch.py` | whole-show runs |
| `test_schema.py`, `test_db_paths.py` | the data model; **one spelling of a path** |
| `test_tables.py`, `test_theme.py` | Tk-era table and theme behaviour |
| `test_ui_qt.py` | tokens, stylesheet, the HTML report, the guardrails |
| `test_vocab_complexity.py` | language metrics |

The Tk tests `importorskip("tkinter")`, which is where most of the 13 skips
come from.

## 12. Data conventions

**What counts as an episode.** `show_index.VIDEO_EXTENSIONS` —
`.mp4 .mkv .avi .mov .wmv .m4v` — is the single definition, matched on the
lowercased suffix (not by globbing, which is case-sensitive on Linux and not on
Windows). `analyzer/sampler.py` imports it rather than keeping its own; a test
asserts the two sets stay equal. They were separate until 2026-08-15, and a
sample could contain episodes the Library never listed.

```
<root>/
  ShowName/                    ← flat show (videos directly inside)
    ep01.mp4
  CategoryName/                ← category (no direct videos)
    ShowName/
      ep01.mp4
  .analysis/
    ShowName/
      ep01.json                ← cached episode result
      aggregate.json / .csv
    index.db                   ← SQLite index
    pipelines/                 ← pipeline documents
```

Only **one** level of category nesting is discovered — but season folders are
handled at a second layer, and the two disagree in a way worth knowing.

`analyzer/show_index.py` recognises `Season N`, `Series N`, `S N` and `Part N`
(`parse_season_folder`), and `show_name_for_db()` returns the **parent** folder
as the show name, so all seasons appear under one show **in the index**.

So for `Little Bear/Season 1/ep.mp4`:

| Layer | Sees |
|---|---|
| Library tree / `show_key` / cache path | a category `Little Bear` containing a show `Season 1` |
| Index and database `show_name` | one show, `Little Bear`, with `season_num` 1 |

Both are working as written. The consequence is that selecting `Little Bear` in
the Library reports that it groups shows rather than episodes, while the Index
correctly shows it as a single show — and a cross-season aggregate exists in
the Tk build's **Full Series Aggregate**, not in the Qt Library.
