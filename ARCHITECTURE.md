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

## 5. Front-end structure

`analyzer/` imports no GUI framework. That is what made the Tk → Qt move a
presentation rewrite rather than an application rewrite, and it is worth
protecting.

```
analyzer/   engine + data model      (no GUI imports — enforced by test)
cli.py      thin layer over analyzer
ui/         Qt front-end             (thin layer over analyzer)
gui*.py     Tk front-end             (legacy; being retired)
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

Four statuses, and they mean different things:

- **validated** — graded against human coding.
- **unvalidated** — works, ungraded. Flag it wherever its numbers appear.
- **experimental** — ungraded *and* known to be rough.
- **deterministic** — colour, motion, flashing and audio are direct signal
  measurements with no detection or classification step to validate. The
  *signal* is deterministic; whether `flashing` counts the right events is a
  separate question, and it is unvalidated.
- **human** — fantastical events. The tool structures the coding; it does not
  detect fantasy.

### The headline accuracy figure

```
hard-cut F1 = 0.85 aggregate, range 0.75–0.91 across production styles
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

```
<root>/
  ShowName/                    ← flat show (MP4s directly inside)
    ep01.mp4
  CategoryName/                ← category (no direct MP4s)
    ShowName/
      ep01.mp4
  .analysis/
    ShowName/
      ep01.json                ← cached episode result
      aggregate.json / .csv
    index.db                   ← SQLite index
    pipelines/                 ← pipeline documents
```

Only **one** level of category nesting is discovered. A show whose episodes sit
in a `Season 1` subfolder is treated as a category containing a show called
`Season 1` — correct behaviour given the convention, and worth knowing when a
show row reports that it groups shows rather than episodes.
