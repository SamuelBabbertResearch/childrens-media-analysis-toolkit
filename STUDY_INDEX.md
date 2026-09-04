# Adult Perceptions of Pacing in Children’s Television

## Study index — where everything lives

**Written:** 2026-08-23. **Updated:** 2026-08-31. This is a map, not an
authority. Where this file and a study document disagree, the study document
wins.

Nothing has been moved to create this index. The study's provenance chain
records files by their relative path and binds them with SHA-256, so the
documents stay where the frozen inventory says they are. See *Why the files are
not in one folder* at the bottom.

### Start here

| File | What it is |
|---|---|
| [STUDY_HANDOVER.md](STUDY_HANDOVER.md) | Current state, and which document is presently authoritative. **Read this first.** |
| [STUDY_ADULT_ONLY_REDESIGN_DECISION_2026-08-31.md](STUDY_ADULT_ONLY_REDESIGN_DECISION_2026-08-31.md) | Governing participant-design change: adults only, one self-perception rating, no child recruitment or adult proxy question, with rationale. |
| [STUDY_AIMS_AND_STIMULUS_CRITERIA.md](STUDY_AIMS_AND_STIMULUS_CRITERIA.md) | Current adult-only research purpose, Option 3.5 replicated-feature design, and what makes a stimulus acceptable. Any older PDF export must be regenerated before use. |
| [STUDY_ANALYSIS_LOG.md](STUDY_ANALYSIS_LOG.md) | Append-only record of every decision and run. Never revised — corrections are new dated entries. |

### Design and procedure

| File | What it is |
|---|---|
| [STUDY_PROCEDURE_ADULT_ONLY.md](STUDY_PROCEDURE_ADULT_ONLY.md) | Active participant procedure: adult consent, practice, 12 clips, and one own-perception rating per clip. |
| [STUDY_RATING_SCALE_DESIGN.md](STUDY_RATING_SCALE_DESIGN.md) | The adult participant response format: the labelled 1-5 pace ramp, design rationale, and remaining pilot decisions. Working spec. |
| [STUDY_CLIP_SELECTION.md](STUDY_CLIP_SELECTION.md) | How a season is screened into 30-second candidate windows and matched pairs. |
| [STUDY_MEASUREMENT_FLOWCHART.md](STUDY_MEASUREMENT_FLOWCHART.md) | Diagram of how cuts, motion and audio intensity were each measured, and what each number does not claim. |

### Frozen method — currently authoritative

| File | What it is |
|---|---|
| `STUDY_WAVE1_SINGLE_CODER_ANALYSIS_PLAN_..._correction-04.md` | **The governing Wave 1 analysis design.** SB01 sole coder; supersedes the earlier two-coder, inter-rater and joint-adjudication requirements. |
| `STUDY_WAVE1_ANALYSIS_SCOPE_..._correction-03.md` | Plot-scene scope correction. W1C010 excluded without replacement (end credits), leaving 11 eligible clips. |
| `STUDY_CUTS2_STIMULUS_REPLACEMENT_DECISION_..._correction-06.md` | Replaces the CUTS_2 low-member stimulus (W1C010 contained the inter-story title card). **The participant set is now defined by the correction-06 selection record.** |
| `STUDY_VERSION1_MANUAL_COMPARISON_DECISION_..._correction-05.md` | The post-analysis decision: detector and parameters unchanged, so no Version 2. Version 1 stays authoritative. |
| `STUDY_MANUAL_CODING_PLAN_wave1-2_..._correction-02.md` | Frozen hand-coding method. |
| `STUDY_CALIBRATION_PLAN_wave1_..._correction-02.md` | Frozen calibration method. One calibration permitted; motion, sampling and audio ineligible for change. |
| [validation/CODEBOOK_wave1-2_method-manual_recipe-v1_2026-08-22_correction-02.md](validation/CODEBOOK_wave1-2_method-manual_recipe-v1_2026-08-22_correction-02.md) | The coding definitions the hand coder worked to. |

### Superseded, retained as history

Kept deliberately — the record of *why* a decision moved is itself material for
the paper. Do not code or analyse from these.

- `STUDY_MANUAL_CODING_PLAN.md` (2026-08-18) → replaced by correction-02
- `STUDY_CALIBRATION_PLAN.md` (2026-08-18) → replaced by correction-02
- The two-coder / MIA01 sections inside `STUDY_HANDOVER.md` → replaced by correction-04
- [STUDY_PROCEDURE_ADULT_AND_CHILD_PHASES.md](STUDY_PROCEDURE_ADULT_AND_CHILD_PHASES.md) → participant design replaced by the adult-only procedure on 2026-08-31

Some frozen method files, inventory rows, paths, and recipe citations retain the
former study title. Those strings are hash-bound historical identifiers, not a
description of the current participant design; do not rename them in place.

### Provenance

| File | What it is |
|---|---|
| [STUDY_FILE_INVENTORY.md](STUDY_FILE_INVENTORY.md) | Authoritative SHA-256 inventory of every study file. Points at the current row-level CSV. |
| `.analysis/study_workflow/inventory/` | The inventory CSVs themselves, one per correction. |
| `.analysis/study_workflow/qualification/` | Records qualifying each tool before use. |

### Data and results (not in git — `.analysis/` is local)

| Path | What it holds |
|---|---|
| `.analysis/study_workflow/version_1_baseline/snapshot_wave1-...correction-01/` | The frozen Version 1 baseline: recipe, `candidates.csv` (1,320 windows), `matched_pairs.csv`, `selected_clips.csv` (12 clips), per-episode measurements, `manifest.json`. |
| `.analysis/study_workflow/wave_1_manual/` | Blind coding package, media hard links, coder sessions. |
| `.analysis/study_workflow/wave_1_analysis/calibration_wave1_..._correction-04/` | The single-coder comparison results. |
| `.analysis/study_workflow/tools/`, `tests/` | The study-specific tools and their regression suites. |
| `.analysis/study_clips/` | Earlier per-season candidate runs. |

### The software behind it

The study uses CMAT but is not part of it. Relevant engine pieces:

- [analyzer/study_clips.py](analyzer/study_clips.py) — the windowing, measurement and pair-matching workflow
- [analyzer/metrics_frames.py](analyzer/metrics_frames.py) — motion and colour
- [analyzer/metrics_cuts.py](analyzer/metrics_cuts.py) — transition detection
- [analyzer/metrics_audio.py](analyzer/metrics_audio.py) — RMS audio intensity
- [analyzer/recipes.py](analyzer/recipes.py) — the frozen recipe binding
- [MEASUREMENT_MODEL.md](MEASUREMENT_MODEL.md) — construct / measure / method / recipe vocabulary

### Why the files are not in one folder

Moving them was considered on 2026-08-23 and rejected. The study documents are
referenced by relative path in three places that would all break:

1. the frozen SHA-256 inventory CSVs, which record each file's relative path;
2. `generate_study_file_inventory_...py`, which names eight root documents
   explicitly and would need requalifying;
3. 44 files under `.analysis/study_workflow/` and 61 cross-references among the
   study documents themselves.

A physical reorganisation is still possible, but it is a provenance change and
needs its own log entry, a re-run inventory, and requalification of the tools —
not a quiet `git mv`. This index gives the organisation without the risk.
