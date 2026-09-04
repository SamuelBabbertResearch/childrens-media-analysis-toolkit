# Adult Prediction of Children's Perceived Media Pacing

## Authoritative study file inventory

**Inventory status:** CORRECTION-07 CODING-COMPLETE RELEASE  
**Inventory date:** 2026-08-22  
**Wave:** Pre-coding preservation / Wave 1 correction-02  
**Method:** SHA-256 provenance inventory  
**Recipe context:** Version 1 sampling context; Version 2 not yet created  

The current exhaustive row-level inventory is
`.analysis/study_workflow/inventory/study_file_inventory_full_method-provenance_recipe-v1_2026-08-18_correction-13.csv`,
which adds the correction-06 stimulus-replacement package, its search tool, the
correction-06 decision document, the completed correction-07 coding package
including its coded events file and viewer, and the 2026-08-23 documentation
written alongside them. Correction-12 and every earlier inventory remain
preserved and were not overwritten.
It records relative path, category, wave, method, recipe context, size,
modification time, SHA-256, read-only state, and preservation notes for original
study files, large source identities, snapshots, and newly generated workflow
artifacts. Its detached checksum file also records the SHA-256 of this Markdown
inventory. The checksum file does not hash itself.

The earlier file without a correction suffix, `_correction-01`, and
`_correction-02` are retained.
The first captured 214 rows before the reporting scaffold and subsequent log
entry; correction 01 captured 217 rows. Correction 02 adds the qualified tools,
regression tests, qualification report, and corrected Wave 1 blind package.
Correction 03 incorporates the final inventory-pointer test and qualification
report revision. Correction 04 adds the qualified blind coding system, its
test suite and release record, the launcher, and all 12 read-only Wave 1 coding
media files plus their frame-map manifest. Correction 05 adds the disposable
active-browser data-entry qualification addendum and the final append-only log
record. Correction 06 adds the preserved launcher attempts, append-only launcher
logs, and Windows startup qualification record. No prior inventory was
overwritten.

### 2026-08-22 correction-02 pre-use release

Correction-10 adds the approved correction-02 codebook, manual-coding plan,
calibration plan, blind worklist and manifest, detached checksums, templates,
12 byte-identical/read-only coding-media hard links and their frame-map
manifest, generator, coding tool, browser interface, launcher/log, regression
suite, ACL correction evidence, active-browser qualification evidence, legacy
server shutdown evidence, and scoped pre-use qualification. The correction-01
package and its empty session remain preserved and are not authorized for use.

The standalone correction-02 Wave 1 blind manual-coding workflow is qualified
for use by
`.analysis/study_workflow/qualification/WAVE1_BLIND_CODING_PREUSE_QUALIFICATION_method-provenance_recipe-v1_2026-08-22_correction-02.json`
(SHA-256
`5eeab0fd8bb28bf1bd71b9f81074e993d85eb877026b11e3340619a35477bee9`).
This scoped GO does not claim that every unrelated CMAT subsystem is defect-free.
At qualification, the study-specific suite passed 111/111; the broader
repository suite passed 631 tests, skipped 14, and retained one unrelated
construct-cache status failure documented in the qualification record.

### 2026-08-22 adjudicated-reference release

Correction-11 adds the qualified Wave 1 adjudicated-reference system, its
implementation contract, 26-test synthetic regression suite, qualification
record, updated handover, append-only analysis-log entries, and correction-11
inventory generator. No real coder events, adjudication decisions, manual
reference events, or manual per-clip counts were created.

The adjudicated-reference qualification record is
`.analysis/study_workflow/qualification/WAVE1_ADJUDICATED_REFERENCE_SYSTEM_QUALIFICATION_method-provenance_recipe-v1_2026-08-22_correction-01.json`
(SHA-256
`10e065b11f96c6e5cb82dce73a389f44a5f2ff3df240133e59193d228699adf8`).
The software is qualified to prepare the manual adjudication worklist after
both coders finalize and to build the final manual reference only after every
case is resolved while blind. It does not authorize detector calibration.

## Authoritative scope

- **Stimulus pool:** 30 MP4 files in
  `Shows/Curious George Full Season One HD`; 1,320 eligible half-open,
  contiguous 30-second windows after excluding the first 51 and last 38 seconds
  per episode.
- **Excluded exploratory feasibility:** 20 MP4 files and all outputs under
  `Curious George Full Season 2 HD`; preserved but never eligible for selection.
- **Version 1 Wave 1 set:** exactly 12 rows in the original
  `selected_clips.csv`; not participant finalists.
- **Finalists at inventory date:** none. No authoritative `finalists/` or
  `finalist_measurements.csv` exists for this study.

The Season One source directory also contains `__ia_thumb.jpg`. It is
inventoried but is not one of the 30 source videos.

## Version 1 recipe identity

| Field | Frozen value |
|---|---|
| Recipe ID | `r_apc_media_pacing` |
| Citation | `Adult Prediction of Children's Perceived Media Pacing - Feature Extraction v1 (0d233950c561)` |
| Recipe content hash | `0d233950c561` |
| Recipe file SHA-256 | `689b8d7bdf6970f862651ca4fd5478aecf6240858632b106e2d53d4b71d60545` |
| Recipe path | `.analysis/recipes/Adult Prediction of Childrens Perceived Media Pacing - Feature Extraction_r_apc_media_pacing.json` |
| Measurement fingerprint | `a5714394da4d` |
| Hard cuts | PySceneDetect ContentDetector, threshold `27.0` |
| Motion | Absolute frame differencing, uniform sampling `2.0 fps` |
| Audio intensity | FFmpeg linear RMS |
| Recipe lock flag at baseline | `false`; preserve unchanged |

## Core Season One Version 1 outputs

All paths below are under
`.analysis/study_clips/Curious George Full Season One HD/` and were generated at
2026-08-17T19:14:54-04:00 unless noted.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `candidates.csv` | 824,715 | `985d04287a5ef6b45908d17e72dc47ff533dc9214054d20321c7f280e8061d64` |
| `failures.csv` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `manifest.json` | 25,998 | `20d9daf313a571257537c99aef9fe62011f564f3ac94e824e3e1554d50782c2a` |
| `matched_pairs.csv` | 5,475 | `81a86c8edd811c2e30dac7ff238011f969c3011773c2ccec4ab1a1cebd0fcf99` |
| `pair_candidates.csv` | 255,207 | `5e3dbebe4f5b90d96b43ee8b48be98c2463b5726f1199afe1ed5e02d3756b1c7` |
| `selected_clips.csv` | 8,339 | `99d6581c25ac34cbfb959d25d817c0dfedfaa1933f00ca64951cf9773434d3a2` |
| `study_clip_tables.md` | 7,187 | `90593cd2655211baa3c6f15f509dfb7f94104f99839f86001ab679dec34a495b` |

The original `episode_measurements/` contains 30 JSON caches. Their individual
sizes, modification times, and SHA-256 values are in the exhaustive CSV.

## Season Two excluded feasibility outputs

All paths below are under
`.analysis/study_clips/Curious George Full Season 2 HD/` and were generated at
2026-08-18T01:06:28-04:00 unless noted.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `candidates.csv` | 522,930 | `186d331f24b94c4530fe63de6d774cf7b5a017dfbc349ff233164cec5fde20fb` |
| `failures.csv` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `manifest.json` | 21,988 | `c460af6013a82a1f624ac181f03f24e60897e9c2772694576c692e7ae84dabda` |
| `matched_pairs.csv` | 5,308 | `9080f46cc46f16f600417c141bf8ac94c25b108af926e981e9c6dd1c7c915f86` |
| `pair_candidates.csv` | 240,764 | `8f9fec5b18e4b12e4fc412353948df558694876d7c0e5c0c2a6f9565b7ddc79c` |
| `selected_clips.csv` | 8,086 | `25601847db9344b62c1497f920d26a9b6d67c685126a683e9162b87ad564327a` |
| `study_clip_tables.md` | 7,087 | `78281e7f6b09a2c62bc51bb667facf7e28bbd47e277fcfa9145674ad10de1914` |

The original `episode_measurements/` contains 20 JSON caches. They and the 20
source MP4 hashes are retained in the exhaustive inventory. They are marked
`excluded_exploratory`, not `authoritative_stimulus_pool`.

## Codebook and authority files

`validation/CODEBOOK.md` has SHA-256
`c15235ebe9b5ba62f0ee5f0217c85ab4339a6ba1c694726d652d89dd110dab53`.
The exhaustive inventory also hashes the handover, procedure, aims/criteria,
clip-selection workflow, generated tables, manifest, and frozen plans.

## Preservation snapshots

The originals remain untouched in their existing paths.

- `snapshot_wave1-method-automated_recipe-v1_2026-08-18/` is an intentionally
  retained **incomplete attempt**. A PowerShell wildcard error copied only the
  recipe. Its failure README explains the error. Do not use it as the snapshot.
- `snapshot_wave1-method-automated_recipe-v1_2026-08-18_correction-01/` is the
  verified snapshot of the Version 1 recipe, all 37 Season One output/cache
  files, and all 27 Season Two output/cache files: **65 files, 4,811,479 bytes,
  zero SHA-256 mismatches**. All 65 copied files were marked read-only.
- Large Season One and Season Two MP4 sources were not duplicated. Their
  identities and SHA-256 values are in the exhaustive inventory.

## Newly established workflow areas

`.analysis/study_workflow/` now contains separately labeled locations for:

- Version 1 baseline and snapshots;
- Wave 1 manual coding;
- calibration results;
- Version 2;
- Wave 2 manual coding;
- Version 1/Version 2 comparisons;
- final selection and rejection records;
- final exported stimuli; and
- paper-reporting tables.

The Wave 1 blind materials are machine-readable and contain no automated result
values, feature labels, pair assignments, or study labels. They have a detached
checksum manifest. Templates are empty and coding has not started.

The qualified local blind coding system is separate from CMAT measurement
software. Its 12 coding-media MP4s total 90,522,328 bytes and are read-only.
Their manifest records every media hash and the one-to-one media-frame to
source-frame timestamp map. Qualification passed 29 coding-system tests and 22
prior workflow tests (51/51 total), plus a read-only browser exercise. Preview
testing created no coder-data directory, manual event, completion record, or
session record. The release record is
`.analysis/study_workflow/qualification/WAVE1_BLIND_CODING_SYSTEM_RELEASE_method-provenance_recipe-v1_2026-08-18_correction-01.json`.
An additional disposable active-browser exercise verified session start, one
frame-mapped event append, clip completion, and the incomplete-finalization
guard without creating authoritative coder data. Its addendum is
`.analysis/study_workflow/qualification/WAVE1_BLIND_CODING_SYSTEM_ACTIVE_UI_QUALIFICATION_method-provenance_recipe-v1_2026-08-18_correction-01.json`.

## Inventory update rule

Never silently replace this baseline or its companion CSV. A later inventory is
a newly dated/versioned CSV plus an append-only log entry. Corrections retain
the original inventory, explain the difference, and receive a new filename.
Every new recipe, run, manual file, comparison, decision log, and export must be
added with wave, method, recipe version, date, size, modification time, and
SHA-256.
