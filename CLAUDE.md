# CMAT — Children's Media Analysis Toolkit

Project reference for anyone (human or model) working in this repository.

**Read first:** §1 Purpose, §2 Rules that must not be broken, §3 Stack.
Everything after §5 is reference material — consult it when you touch that area,
don't read it end to end.

| § | Section | What it is |
|---|---|---|
| 1 | [Purpose](#1-purpose) | What the tool is for, and what it refuses to do |
| 2 | [Rules that must not be broken](#2-rules-that-must-not-be-broken) | Architecture and scientific guardrails |
| 3 | [Stack](#3-stack) | Dependencies; do not substitute without asking |
| 4 | [Current work: Tk → Qt migration](#4-current-work-tkinter--pyside6) | In progress |
| 5 | [Where things are written down](#5-where-things-are-written-down) | Which file gets which kind of note |
| 6 | [Repository map](#6-repository-map) | What exists |
| 7 | [Data conventions](#7-data-conventions) | Folder layout, cache keys, config |
| 8 | [Metric definitions](#8-metric-definitions) | What each number means |
| 9 | [Gotchas](#9-gotchas) | Things that have already bitten |
| 10 | [Research grounding](#10-research-grounding) | Literature, and how to talk about it |

---

## 1. Purpose

A desktop Windows application that analyses MP4 episodes of children's television
and produces a **sensory-load profile** per episode and a cumulative profile per
show. It measures formal/structural features of the video — pacing, colour,
motion, flashing, audio — plus language, and supports structured hand-coding of
things no automated measure can see.

**It does not issue a verdict.** No appropriateness rating, no target age, no
educational value, no recommendation. It presents transparent, labelled metrics
that a person interprets. Every composite score must show its component parts.

---

## 2. Rules that must not be broken

### 2.1 Architecture

1. **`analyzer/` has zero GUI imports.** Each metric is an isolated, testable
   function: input = video path + config, output = numbers. This rule is what
   made the Qt migration a presentation rewrite rather than an application
   rewrite — it is worth real money, so do not spend it.
2. **`cli.py` and the GUI are thin layers over the same engine.** Never
   duplicate analysis logic in a front-end.
3. **Analysis runs on a worker thread** with a progress callback. The UI must
   never freeze.
4. **One palette, one accent, in `ui/tokens.py`** — which imports no framework,
   so both front-ends share it. Two sources of truth is how two different blues
   both came to mean "selected".

### 2.2 The stimulus-only guardrail

No token, badge, column, field, preset, or export may report appropriateness,
target audience age, educational value, or quality. CMAT measures the stimulus,
not the viewer, and issues no verdict.

This has concrete consequences that keep coming up:

- A red cell beside a high flashing rate reads as "bad" whatever the caption
  says. Unusual values are marked with a **glyph plus a legend naming the
  comparison set**, not a colour that implies a verdict.
- Age-named presets (`Toddler (0-2)`) are **reference ranges for studies of
  that group**, not suitability ratings.
- Status badges report the state of the *work* ("Analyzed"), never a property
  of the programme.

### 2.3 Scientific language

**Always correlational. Never causal.** No feature *causes* an outcome. Age,
temperament, sensory-processing profile, and viewing dose are not captured.

Unvalidated components must be visibly flagged wherever their numbers appear —
in the UI, in exports, and in provenance.

---

## 3. Stack

*Do not substitute without asking.*

| Purpose | Choice |
|---|---|
| Language | **Python 3.11+** (tested on 3.13) |
| Cut / scene detection | **PySceneDetect**; optional **TransNetV2** |
| Frame analysis | **OpenCV** + **NumPy** |
| Audio | **FFmpeg** (must be on PATH) |
| Aggregation / export | **pandas** |
| GUI | **PySide6** (Qt 6) — migrating from Tkinter, see §4 |
| Charts | **matplotlib** (Tk backend today; `FigureCanvasQTAgg` after the move) |
| Speech (optional) | **faster-whisper** |
| Language metrics | **spaCy**, **wordfreq** — English only |

No web frameworks.

---

## 4. Current work: Tkinter → PySide6

Tkinter could not render the intended look. Qt has a real stylesheet engine and
renders HTML/CSS, so the design is declarative instead of hand-drawn.

**Presentation rewrite, not an application rewrite.** `analyzer/` imports no GUI
framework — verified, not assumed. The engine, CLI, and site builder (~12,000
lines) do not move. Only the `gui*.py` layer (~13,400 lines) is ported.

**Method: build beside, not on top.** The Qt front-end lives in `ui/`; the Tk
front-end stays in `gui*.py` and keeps working. Both import the same `analyzer/`
and the same tokens. There is never a broken state, the two can be run against
one project and compared directly, and if the migration stalls nothing is lost.
Tk modules are deleted only as each screen reaches parity.

```
python gui.py       Tkinter build — still the complete application
python cmat_qt.py   Qt build      — Library + analysis report ported so far
```

| File | Role |
|---|---|
| **`ui/DESIGN.md`** | **the visual specification — read before building any screen** |
| `ui/tokens.py` | design tokens; **no framework imports** — shared by both builds |
| `ui/theme.py` | fonts, Qt stylesheet |
| `ui/report.py` | analysis results as HTML; no Qt import, so it is testable headless and reusable for PDF export and the static site |
| `ui/main_window.py` | Qt shell: toolbar, tabs, Library grid, report pane |

**Terminology:** call the interface a **Classic Desktop UI**, or a
**Mavericks-inspired layout** when a period reference is needed. Avoid naming
trademarked operating systems or applications in documentation, comments,
commit messages, or UI strings.

**Migration conventions:**

- Type sizes are **points**. Qt scales them for the display. Copying a
  pixel size from a 2010 spec is a units error — that era's "11" was points,
  roughly 15px at today's densities.
- An **unported screen must not look like a broken screen**. Unported tabs say
  so in an ambox and name the Tk build.
- Qt 6 is per-monitor DPI aware by default. Do not add `ctypes` DPI calls.

---

## 5. Where things are written down

| File | Audience | Committed? |
|---|---|---|
| `CLAUDE.md` | this file — rules and orientation | yes |
| `ROADMAP.md` | forward-looking priorities, positioning decisions | yes |
| `validation/VALIDATION_LOG.md` | full lab notebook: every run, decision, result, in order | yes |
| `FOR_PAPER.txt` | distilled paper-relevant subset | **NO — never** |

### `FOR_PAPER.txt` — two standing rules

1. **Keep it updated.** Whenever work produces something the paper will need — a
   validation figure, a corrected number, a methodological decision, a limitation
   discovered, a citation, a piece of draft wording — append it to the relevant
   section without being asked. Date anything numeric. When a figure is revised,
   keep the superseded value and say what changed and why; the record of *why a
   number moved* is itself paper material.
2. **Never commit or push it.** It is in `.gitignore`. Do not `git add -f` it,
   do not include it in a commit, do not paste its contents into a public file,
   a commit message, the README, or the website. If `git add -A` would stage it,
   stop and fix the ignore rule instead.

Also gitignored, for the same reason: `user_prefs.json` (contains a local
absolute path) and `pipelines/` (personal project data).

---

## 6. Repository map

### Analysis engine — `analyzer/` (no GUI imports)

| Module | Role |
|---|---|
| `engine.py` | per-episode analysis; dispatches to the selected tool per measurement |
| `measurements.py` | registry: which tool produces each measurement, with what parameters, and whether it is validated. Fingerprints settings so stale cache is detectable |
| `metrics_cuts.py` | shot boundaries (ContentDetector / AdaptiveDetector / TransNetV2), dissolves, cut classification |
| `metrics_frames.py` | colour, motion, flashing (shared frame pass) |
| `metrics_audio.py` | RMS loudness, dynamic range (via FFmpeg) |
| `speech.py`, `vocab_complexity.py` | WPM and speech density; readability, tiers, AoA, MTLD |
| `metrics_sensory.py` | the weighted composite |
| `batch.py`, `aggregate.py` | batch runs; show-level statistics |
| `cache.py`, `db.py` | disk cache and SQLite index; staleness detection |
| `show_index.py` | folder discovery (one level of category nesting) |
| `schema.py` | `EpisodeResult`, `ShowAggregate` |
| `sampler.py`, `trials.py` | reproducible episode sampling; run registry |
| `validation.py`, `event_coding.py` | tool-vs-human scoring, Cohen's kappa, inter-coder agreement |
| `pipeline.py` | derived workflow status from what is on disk |
| `pipeline_graph.py` | editable pipeline documents, node types, presets |
| `provenance.py` | self-reported accuracy figures |
| `prefs.py` | per-user local state, kept out of the versioned config |
| `config_loader.py` | loads and normalises `config.json` |
| `optional_tools.py`, `detector_transnet.py` | optional dependency registry; TransNetV2 wrapper |
| `report_pdf.py` | PDF export |
| `wiki_importer.py`, `tvmaze_importer.py` | episode metadata import |
| `intro_templates.py` | reusable coding-sheet templates |
| `ffmpeg_path.py` | locates the FFmpeg binary |

### Front-ends

- **Tk** (`gui.py` + 14 `gui_*.py` modules) — complete: Pipeline, Library, Index,
  Automated coding (Analyze / Language / Validation), Human coding (Code /
  Validate tool / Agreement), Trials, Episode Sampler, Measurement Settings,
  coding editor with embedded VLC.
- **Qt** (`ui/`) — Library grid and analysis report.

### Command line

```
python cli.py analyze <file.mp4>       single episode → JSON
python cli.py analyze <show_folder>    batch → per-episode JSON + aggregate
python cli.py db episodes <root>       list indexed episodes
python cli.py db shows <root>          list indexed shows

python validate_cuts.py …              template / export / compare / sweep / summary
python code_events.py …                template / rates / agreement / publish
python build_site.py                   static site
```

---

## 7. Data conventions

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
    pipelines/                 ← pipeline documents (when a root is set)
```

`show_key(root, show_dir)` returns the POSIX relative path (e.g.
`"CategoryName/ShowName"`), used as both the cache subfolder and the DB key.

**`config.json`** — versioned and shared. Seven built-in presets (General /
All Ages, Toddler 0-2, Preschool 2-5, Early Childhood 5-8, Tween 8-12,
Animated / Cartoon, Live-Action / YouTube), each with its own
`sensory_load_weights` and `normalization_reference_ranges`, plus the
`measurements` block. Built-ins cannot be deleted.

**Two axes, deliberately separate:**

- **Scoring** (weights, normalization ceilings) applies to already-computed
  metrics and re-scores from cache instantly.
- **Measurement** (detector, thresholds, sample rates) changes the raw numbers,
  so cached results measured under other settings are stale. Changing these
  marks affected episodes and says how many.

---

## 8. Metric definitions

- **Shot length** — PySceneDetect content detection → cut timestamps → gaps
  between cuts. Mean, median, shots/min, count. Shorter = faster.
- **Scene pacing** — from the same cut series: cut rate, coefficient of
  variation (std/mean), rolling cuts-per-30s timeline. Captures *rhythm*,
  distinct from raw shot length.
  Config-gated extras: dissolve detection (off by default) and cut
  classification (on), labelling each cut within_scene vs scene_change by frame
  similarity ±1s across the cut (Lang: related vs unrelated cuts).
  **The 0.55 similarity threshold is UNVALIDATED** — do not fold
  `scene_changes_per_min` or `within_scene_cut_fraction` into sensory_load until
  tuned against the hand-coded ground truth in `validation/`.
- **Colour saturation** — frames sampled at `sample_fps` (default 2) → HSV →
  mean S per frame. Mean and temporal variance.
- **Colour contrast** — same sample; per-frame standard deviation of the V
  channel. Visual intensity / dramatic lighting.
- **Motion** — normalised mean absolute difference between consecutive *sampled*
  frames, so values depend on the sample rate. Pluggable (Farneback available,
  ungraded). Mean and peak.
- **Flashing** — luminance changes between sampled frames exceeding
  `flashing_luminance_threshold`, per minute. Whole-frame mean, so a flash in
  part of the frame is diluted; it does **not** implement the area and red-flash
  criteria broadcast photosensitivity guidance specifies. A relative indicator,
  not a safety certification.
- **Audio** — FFmpeg RMS loudness (mean, peak) and dynamic range in dB. Linear
  RMS, not LUFS. When absent, its weight is redistributed and the result flagged.
- **Speech / language** — WPM and speech density from captions, or Whisper when
  enabled; vocabulary complexity from caption files. **English only.**
- **Sensory load** — weighted composite of normalised sub-metrics against
  *fixed* reference ranges (not per-corpus), so scores are comparable across
  runs. Always output the composite *and* every component.

---

## 9. Gotchas

### Cache is path-based

`cache_path = root/.analysis/<show_key>/<stem>.json`. Renaming a show folder,
moving it into a category, or renaming episode files orphans the cache and the
analysis appears to vanish. "Remove Stale" finds the reverse (cache with no
video). *Future improvement:* key on a content hash (size + duration) instead.

### Measurement settings versus scoring settings

Changing a weight re-scores instantly. Changing a detector threshold invalidates
every episode measured under the old setting. Results carry a
`measurement_fingerprint`; results predating fingerprinting are grandfathered
rather than invalidating an existing corpus.

### Detectors are not interchangeable within one corpus

TransNetV2 finds ~5–7% more transitions than ContentDetector. A half-migrated
index makes pacing incomparable across shows — migrate all or none.

### Layout bugs that have bitten more than once

Found three times by walking the live widget tree and measuring every mapped
control — invisible to tests and to code review. Worth re-running that sweep
after any layout change to the Tk build.

### Tkinter-only — historical, do not apply to `ui/`

- **Pack order:** `side=BOTTOM`/`side=RIGHT` widgets must be packed *before* any
  `expand=True` sibling, or they get zero width/height. This silently hid the
  Episode Sampler's Browse buttons, three controls in Language → Vocabulary, and
  the Speech status note.
- **Progress bar:** use `after()` polling on a determinate `ttk.Progressbar`;
  indeterminate mode freezes during long Python operations.
- **`ttk.Combobox` tooltips** never fire on Windows — the native Win32 control
  swallows the mouse events. Put the text on an adjacent label.
- **DPI:** the Tk build declares per-monitor awareness via `ctypes` with
  `c_void_p(-4)`; a bare `-4` marshals as a 32-bit int and silently fails on
  64-bit. Qt needs none of this.

---

## 10. Research grounding

The tool measures **formal features** (Huston & Wright) — content-independent
structural attributes that trigger the **orienting response**. Lang's **LC4MP**
supplies the resource account: each cut consumes finite processing capacity.

| Metric | Hook |
|---|---|
| Pacing | Lillard & Peterson (2011, *Pediatrics*): fast-paced cartoon → immediate EF decrements in 4-year-olds. Lillard et al. (2015): fantastical content may matter as much as raw pace. Present pacing as an **associated factor, not a cause**. |
| Motion | Itti & Koch: high motion is a pre-attentive bottom-up attention magnet. |
| Flashing | Photosensitive-epilepsy guidance; the 1997 broadcast incident. The clearest safety rationale of any metric here. |
| Composite | Christakis et al. (2004, *Pediatrics*): correlational association between early heavy TV exposure and later attention problems. Contested; correlational only. |

Full reference scaffold: Huston & Wright; Lang (LC4MP); Lillard & Peterson
(2011); Lillard et al. (2015); Christakis et al. (2004); Itti & Koch; Anderson &
Pempek; Goodrich/Pempek/Calvert. **Verify against primary sources before formal
citation.**

See §2.3 for the language rules this section exists to support.
