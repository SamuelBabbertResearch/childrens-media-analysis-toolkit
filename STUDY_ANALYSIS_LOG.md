# Adult Prediction of Children's Perceived Media Pacing

## Append-only study analysis log

**Log created:** 2026-08-18  
**Scope:** Wave 1 preservation, manual coding, one cut-detector calibration,
Version 2 freeze, Wave 2 prospective audit, final selection, and export  
**Rule:** Never revise or delete an earlier entry. Corrections are new dated
entries that quote the superseded statement and explain the change.

## 2026-08-18 — Initial read-only state audit and authority review

### Authorization and guardrails

The user directed that the 30 Season One HD files and 1,320 windows remain the
only authoritative stimulus pool; Season Two remain excluded exploratory
feasibility; Version 1 remain unchanged; Wave 1 be the current 12-clip proposal;
only one documented cut calibration occur; Version 2 freeze before Wave 2; and
manual hard-cut counts, frozen automated motion, and frozen automated audio
intensity be retained separately. No tuning, Season One rerun, finalist export,
or exposure of automated results in coding materials was authorized at this
stage.

Preserved methodological summary:

> CMAT reproducibly screened a large video corpus and identified promising
> stimulus candidates. Automated cut detection was calibrated using hand-coded
> candidate clips, then audited on newly selected clips. Final stimulus
> selection used manually verified cut counts alongside automated motion and
> audio-intensity measurements.

### Commands executed before documentation creation

All commands used PowerShell from
`C:\Users\Samuel\Child Development Television Index Project`. They were
read-only. Exact commands and outcomes:

1. `git status --short` plus top-level and study-like directory enumeration.
   Outcome: dirty tree with pre-existing modified and untracked work. The
   study-like recursive formatting portion exited 1 and printed unusable blank
   path rows; `git status` and the top-level listing succeeded. No file changed.
2. Enumerated `output/` and `validation/`, then read `STUDY_HANDOVER.md` in
   full. Outcome: handover authority order and settled two-wave design verified.
3. Read the procedure, aims/criteria, and clip-selection Markdown files in the
   stated order. Combined tool output was truncated, so each affected file was
   reread individually; this was a display recovery, not an analysis rerun.
4. Read `.analysis/study_clips/Curious George Full Season One HD/study_clip_tables.md`
   and `manifest.json` in full. Outcome: 30 sources, 1,320 windows, 12 Wave 1
   clips, six pairs, zero failures, fingerprint `a5714394da4d`.
5. Searched for `AGENTS.md` (none found), read `validation/CODEBOOK.md`, and
   computed its SHA-256. An overly broad `.analysis` directory enumeration
   included the local virtual environment and was truncated; relevant study
   directories were later queried directly.
6. Enumerated Version 1 and Season Two top-level outputs; read the Version 1
   recipe, selected clips, matched pairs, and CSV headers. Outcome: the manual
   overlay/reselection ingestion identified in the handover remains absent.
7. Computed SHA-256, size, and modification time for the Version 1 recipe, all
   Season One and Season Two study outputs and episode caches, and all files in
   both HD source directories. Outcome: 116 files hashed successfully in one
   read-only pass. The Season One directory also contained `__ia_thumb.jpg`,
   which is inventoried but is not one of the 30 stimulus masters.
8. Inspected `analyzer/metrics_cuts.py`, `analyzer/study_clips.py`,
   `analyzer/measurements.py`, `analyzer/recipes.py`, `cli.py`, and relevant
   tests with `rg`/`Get-Content`. Outcome: Version 1 uses ContentDetector
   threshold 27.0; window counts exclude a cut exactly at the first frame and
   the exclusive end; ContentDetector threshold is the only exposed parameter
   for that method; motion/audio need not be touched for cut calibration.

### Authority review findings and decisions

- All six authoritative handover documents were read in the stated order.
- `validation/CODEBOOK.md` hash is
  `c15235ebe9b5ba62f0ee5f0217c85ab4339a6ba1c694726d652d89dd110dab53`.
- The codebook is labeled draft and has inconsistent graphics-overlay wording.
  It remains untouched. The frozen study-specific coding plan resolves only
  whether an event contributes to the manual hard-cut outcome.
- A ±1.000-second one-to-one boundary tolerance is frozen before coding,
  consistent with the codebook's timestamp-accuracy target and more suitable
  than its general 2-second default for short animated shots.
- Both Samuel (`SB01`) and Mia (`MIA01`) independently code all clips in both
  waves; raw first-pass records, corrections, and adjudication remain separate.
- The single frozen grid is ContentDetector thresholds 18, 21, 24, 27, 30, 33,
  and 36. No other detector or non-cut measurement is eligible.
- No study-software implementation was changed. The known implementation gap
  is that `study-clips` cannot yet ingest a manual cut overlay or rerank with
  manual cuts. That change is deferred until after this preservation/planning
  stage and requires provenance-preserving implementation and tests.

### Files created in this documentation action

- `STUDY_ANALYSIS_LOG.md` (this append-only log).
- `STUDY_MANUAL_CODING_PLAN.md` (frozen before coding).
- `STUDY_CALIBRATION_PLAN.md` (frozen before coding/tuning).

No detector was run, no source or existing analysis output was modified, no
manual coding began, and no finalist was exported.

## 2026-08-18 — Preservation snapshot, blind materials, and inventory

### Documentation-only creation

Created the frozen manual-coding plan and calibration plan using `apply_patch`.
No CMAT source file was changed. Frozen hashes at the completion of this action:

- `STUDY_MANUAL_CODING_PLAN.md` SHA-256
  `e0e86d1a4ce2df8294944a6023ae6b79105cd38e22cf4f6319135d85c39dbe28`.
- `STUDY_CALIBRATION_PLAN.md` SHA-256
  `8228088550ab66c08309f230be611f00f9a1b313bbf5c9c62a77ebe4f6933dcb`.

Established separately labeled directories for Version 1, Wave 1 manual
coding, calibration results, Version 2, Wave 2 manual coding, comparisons,
final selection, final exported stimuli, reporting, inventory, and generation
tools.

### Snapshot attempt and correction

Executed a PowerShell snapshot command intended to copy the Season One and
Season Two study-output trees plus the Version 1 recipe. `Copy-Item
-LiteralPath` was incorrectly given paths ending in `*`; the wildcard was not
expanded. The command produced two nonterminating errors, returned exit code 0,
and copied only the recipe. It changed no original. The partial directory was
retained and labeled incomplete with a failure README.

Executed a second, separately named correction command using
`Get-ChildItem -LiteralPath <source> | Copy-Item -Destination <destination>
-Recurse -ErrorAction Stop`. It copied:

- the Version 1 recipe;
- all 37 original Season One top-level/cache files; and
- all 27 excluded Season Two top-level/cache files.

Outcome: 65 files, 4,811,479 bytes, every copy marked read-only, and zero
SHA-256 mismatches against originals. The correction snapshot path is
`.analysis/study_workflow/version_1_baseline/snapshot_wave1-method-automated_recipe-v1_2026-08-18_correction-01/`.

### Blind Wave 1 materials

Created the reproducible documentation utility
`.analysis/study_workflow/tools/generate_wave1_blind_materials_method-manual_recipe-v1_2026-08-18.py`
with `apply_patch`, then executed:

```powershell
python .\.analysis\study_workflow\tools\generate_wave1_blind_materials_method-manual_recipe-v1_2026-08-18.py
```

Inputs: untouched Version 1 `selected_clips.csv`, 12 referenced HD masters,
the frozen coding plan, and `validation/CODEBOOK.md`. Output: nine generated
machine-readable artifacts (blind worklist, JSON manifest, two coder-specific
first-pass templates, correction/session/adjudication/overlay templates, and
detached checksums), plus the manually written README.

Validation results:

- 12 worklist rows and 12 unique stable `clip_id` values;
- exact set equality with the original Version 1 selected clip IDs;
- 12 JSON manifest clips;
- zero forbidden automated/result columns in the worklist or manifest clip
  records;
- no detections or automated values generated or copied;
- automated result categories named only in a manifest exclusion list so the
  omission itself is auditable.

The source intervals were ordered deterministically by SHA-256 of the frozen
seed plus `clip_id`. The source filenames/timecodes and source hashes remain
available for coding; feature labels, pair assignments, study labels, scores,
and automated values are absent.

### Exhaustive inventory

Created and executed:

```powershell
python .\.analysis\study_workflow\tools\generate_study_file_inventory_method-provenance_recipe-v1_2026-08-18.py
```

The command rehashed all relevant files and produced a 214-row inventory and
detached checksums. Counts: 30 authoritative Season One MP4 masters, 20 excluded
Season Two MP4 masters, one auxiliary thumbnail, 37 original Season One output/
cache files, 27 excluded Season Two output/cache files, 65 verified snapshot
files, two retained failed-snapshot files, 10 Wave 1 manual materials, eight
authoritative/new study documents, one codebook, one recipe, and 12 other
workflow artifacts. Inventory CSV SHA-256:
`3f8ccb8ed49fc77badf51866ee14780252dc2a25f1529f0a0b73e5f4d9f9c4a4`.

No original recipe, manifest, candidate table, generated table, cache, source
video, or Season Two feasibility output was modified. No tuning, corpus rerun,
manual coding, comparison, final selection, or export occurred.

## 2026-08-18 — Inventory correction and reporting scaffold

After the initial 214-row inventory was created, the methods-reporting scaffold
and the preceding append-only log entry were added. Because replacing the
inventory would violate provenance rules, the 214-row CSV and its checksum were
retained. `STUDY_FILE_INVENTORY.md` was updated to identify a correction file,
and the inventory generator gained a validated `--suffix` option that refuses
existing targets.

Executed:

```powershell
python .\.analysis\study_workflow\tools\generate_study_file_inventory_method-provenance_recipe-v1_2026-08-18.py --suffix correction-01
```

Outcome: 217 inventory rows. Current correction inventory SHA-256:
`0176ef0c1b2cde7c81d1cdb24672fba572b90b5ffda0f2651e18cf72791219e7`.
Its detached checksum-file SHA-256 is
`fd93dbf3696738c0e96743f5553e5c77fcab9966ea294cb3af758a57cc11322e`.
The inventoried `STUDY_FILE_INVENTORY.md` hash is
`9aea5e4e8370e9dffe6a3686a502696224a73075e4b9992fc36159709a6c0247`.
This log is append-only and therefore is expected to differ from the point-in-
time log hash inside a prior inventory after this entry is appended.

Created a methods-ready reporting scaffold labeled **MATERIAL FOR RESEARCHER TO
REWRITE IN THEIR OWN WORDS**. It separates current facts, prespecified methods,
pending calibration results, prospective Wave 2 results, final measurements,
participant outcomes, limitations, and permitted claims.

## 2026-08-18 — Final integrity verification for the preservation stage

Executed one read-only PowerShell verification command that:

- compared the Version 1 recipe, core Season One outputs, and codebook against
  the hashes captured before any writes;
- compared every original Season One/Season Two output and cache with the
  correction snapshot;
- checked the snapshot read-only flags;
- parsed the blind CSV/JSON materials and compared their clip set to the
  original selected clips;
- recomputed all 12 referenced source hashes;
- checked plan/codebook hashes embedded in the blind manifest;
- looked for unexpected finalist MP4s and calibration-result files;
- counted the correction inventory rows; and
- captured final `git status --short`.

Outcome: zero verification errors; all original core hashes matched; 65/65
snapshot files matched and were read-only; 12 worklist rows and 12 manifest
clips matched the frozen selection; no forbidden automated/result columns were
present in the worklist; zero finalist MP4s and zero calibration result files
existed; correction inventory contained 217 rows. The final dirty-tree listing
still contained the pre-existing unrelated modified/untracked work plus the new
root study documentation. No unrelated file was reverted or cleaned.

## 2026-08-18 — Research workflow release qualification

### Scope and pre-test state

The user requested that every workflow function/tool created in the preservation
stage be exercised for bugs before actual research data are recorded. Captured
`git status --short` and recomputed the Version 1 recipe, core Season One output,
and codebook hashes before testing. All matched the preservation baseline. No
detector, source-video analysis, manual coding, or export was run.

Function inventory:

- blind-material generator: `sha256`, `write_csv`, `main` plus subsequently
  factored validation/naming helpers;
- study-file inventory generator: `sha256`, `files_under`, `category`, `main`
  plus subsequently added required-input validation;
- all generated Wave 1 worklist, manifest, checksum, event, correction, session,
  adjudication, and manual-overlay templates;
- preservation snapshot and current inventory/checksum relationships.

### Test infrastructure attempts

1. `python -m pytest ...` failed before collection because the default
   `C:\Python313\python.exe` does not have pytest.
2. Retried with `.analysis\cmat-test-venv\Scripts\python.exe`. Pytest was
   available, but its default user temp directory and `.pytest_cache` were not
   writable in the managed sandbox. Fifteen tests errored during fixture setup;
   one real audit failed on the manifest Boolean type and one test passed.
3. Retried with cache disabled and a unique workspace-local `--basetemp` under
   `tmp/`. This isolated environment produced the meaningful pre-fix result:
   **13 failed, 4 passed**.

The environment failures and meaningful test failures are both retained here;
neither was treated as evidence about research measurements.

### Defects demonstrated before data collection

- A failed `write_csv` could leave a partial header-only file.
- Both generators could leave partial artifact sets if a later operation failed.
- The blind generator did not reject duplicate clip IDs, non-30-second or
  invalid intervals, a wrong measurement fingerprint, or a source outside the
  authoritative Season One directory.
- Frozen selected-file, codebook, coding-plan, and source-master hashes were not
  enforced by the generator.
- The original blind JSON encoded `automated_detections_provided` as string
  `"false"`, not Boolean `false`.
- The inventory generator silently tolerated a missing required tree or wrong
  Season One file count, and could leave a partial CSV after a hash failure.
- A non-MP4 auxiliary file under Season Two would have been mislabeled as a
  source master.
- The blind generator lacked provenance suffix support, preventing a clean
  corrected package without changing code.

No research data had been entered, so no coding records required repair or
recoding.

### Provenance-preserving fixes

Hardened only the documentation/provenance generators; CMAT measurement and
selection software was not changed.

- Added atomic per-file CSV writes with temporary cleanup.
- Added full target-set preflight and staged publishing.
- Added correction suffix validation/support.
- Added exact frozen hashes for the selected-clips CSV, codebook, coding plan,
  and the nine referenced Season One source masters.
- Added selection schema, clip uniqueness, interval, duration, fingerprint,
  path, source-set, and source-hash validation.
- Changed the new JSON field to a true Boolean.
- Added required inventory tree/file, 30/20 corpus, 37/27 output/cache, protected
  hash, and exact top-level output-set validation.
- Made missing inventory paths errors, fixed Season Two auxiliary classification,
  built inventory rows before publishing, and staged both inventory outputs.
- Added a persistent regression suite in the study workflow.

The original blind package was not edited. Generated a separately named
`correction-01` package from the unchanged frozen selection and inputs. The
Wave 1 README now states that only `_correction-01` files may receive research
data and that unsuffixed files are superseded preservation records.

### Qualification runs

- After generator fixes but before corrected artifacts: **16 passed, 1 failed**;
  the sole failure was the intentionally preserved original string-valued JSON.
- After generating `correction-01`: **17 passed**.
- After expanding tamper, missing-source, protected-hash, schema, completeness,
  and checksum coverage: **22 passed in 19.53 seconds**.

The 22-test suite covers successful deterministic generation, SHA-256 helpers,
atomic CSV failure, overwrite refusal, target preflight, suffix validation,
duplicate/interval/fingerprint/path rejection, frozen-input tampering, source
tampering and absence, required inventory trees/counts/output sets, protected
hash drift, injected hash failure, category behavior, every corrected template
schema, exact selected/worklist/manifest correspondence, deterministic blind
order, both original and corrected checksum sets, 65-file snapshot equality and
read-only state, original protected hashes, and absence of calibration/finalist
outputs.

Direct CLI overwrite tests then attempted both corrected blind generation and
the existing correction-01 inventory names. Both commands exited 1 with
`FileExistsError`; all nine corrected blind-file hashes and the inventory hash
remained unchanged.

Four explicitly verified workspace-local test temporary directories were then
removed; all resolved inside the intended project `tmp` directory before the
recursive removal. Zero matching test-temp directories remained.

### Qualified hashes

- hardened blind generator:
  `9dddd8afc2a17741a99e60ea92f6545e96460043784bb4d446408479ed55ceb9`;
- hardened inventory generator:
  `87d3830250e984f80aa8f1d4d20c570d8c89eac336284463312143d5ad26454c`;
- 22-test qualification suite:
  `c5a494454b6f3ff15107a3996801df52343d6e2a7dc389fefcc0263622c72679`;
- corrected blind worklist:
  `140c7fb1ee2fa48472f16567438675e8abda45ea589f2613edaab9d461c22146`;
- corrected blind manifest:
  `74d8c39750672914ef62231af8d26b80b3349cd4232aca2a044cc1d1a7c81216`;
- corrected blind checksum file:
  `e21250d8651f7c8a957fc3d53ed36a5f061d0a1e109782198551f979d185d153`.

The frozen manual plan hash remains
`e0e86d1a4ce2df8294944a6023ae6b79105cd38e22cf4f6319135d85c39dbe28`;
the frozen calibration plan hash remains
`8228088550ab66c08309f230be611f00f9a1b313bbf5c9c62a77ebe4f6933dcb`.

### Qualification inventory corrections

Generated `study_file_inventory..._correction-02.csv` after the initial
qualification documentation. It contained 233 rows. SHA-256 was
`3a551779338dd70f830f51e420570daa07334f7d3994e607a6ed11bd0f29e571`;
its checksum file SHA-256 was
`36265f640f792b910fae42206b70e82985f3bda36eacc970e3f04258a2955d5c`.

The regression test initially named correction 01 directly, so changing the
inventory document to point to correction 02 made that historical checksum
comparison inappropriate. The test was corrected to discover the latest
provenance-suffixed inventory, require the inventory document to name it, and
verify its matching detached checksum. This was a test-maintenance issue, not a
research-data error. The revised full suite again passed **22/22 in 13.97
seconds**. Current regression-suite SHA-256 is
`956b4b9371c14ac6f1aa3ed08205f009650c482f382943738d071e345fe875db`.

The inventory document now points to a final correction 03, generated after
this test/report update. Correction 02 remains preserved.

## 2026-08-18 — Final workflow release qualification and handoff

Generated the final point-in-time provenance inventory
`study_file_inventory_full_method-provenance_recipe-v1_2026-08-18_correction-03.csv`.
It contains 235 rows and has SHA-256
`289ad376753d58c85401f7e97f6f501ee09f2e6325c28a8ec275fd7d734fe767`.
Earlier inventories remain preserved and were not overwritten.

Ran the complete persistent workflow qualification suite after correction 03:
**22/22 tests passed in 13.95 seconds**. The suite and direct CLI checks verified
deterministic generation, blind-material schemas and content, frozen-input and
source-integrity enforcement, atomic failure behavior, overwrite refusal,
inventory completeness, snapshot equality, and the absence of calibration or
final-stimulus outputs.

The first final read-only verification command contained an incorrect relative
path when resolving the root-level `STUDY_FILE_INVENTORY.md`; it stopped with a
path-resolution error and changed no files. The corrected read-only verifier
reported **0 errors**. It confirmed all protected Version 1 hashes, corrected
blind-package checksums, correction-03 inventory checksums, 235 inventory rows,
zero staging directories, zero qualification temporary directories, zero final
participant MP4s, and zero calibration-result files. No detector tuning, corpus
rerun, manual coding, or finalist export occurred during qualification.

Release decision: the Wave 1 documentation/provenance workflow is qualified
for research-data entry. Only the files whose names contain `_correction-01`
in the Wave 1 manual-coding directory are authorized for coding; the original
unsuffixed blind package is a preserved, superseded record and must not receive
research data.

## 2026-08-18 — Qualified Wave 1 blind coding-media and data-entry system

### Scope and implementation decision

The requested next step was an easy, automatic system that isolates each
selected 30-second Wave 1 interval and supports blind hand coding. The active
PySide6 application source was inspected, including `ui/handcoding.py`,
`ui/player.py`, and `analyzer/study_clips.py`. The available command-line Python
environment did not contain PySide6, so changing and rebuilding CMAT would have
introduced an unnecessary implementation and packaging dependency. No CMAT
measurement software was changed. A separate, localhost-only study tool was
created under `.analysis/study_workflow/` so manual coding remains isolated
from automated results.

The tool reads only the qualified Wave 1 `_correction-01` blind worklist and
manifest, the frozen codebook/coding plan, the 30 authoritative Season One HD
sources, its own interface, and the rendered blind coding media. It does not
read or serve `candidates.csv`, `selected_clips.csv`, automated detections,
cut counts, motion/audio measurements, feature labels, study labels, or pair
assignments.

### Boundary investigation and correction

A disposable FFmpeg probe showed that naïve `-ss` plus `-t 30` output included
720 frames for W1C001, while source-frame inspection found the last decoded
frame had a nominal relative incoming timestamp of `30.046578`. This violated
the frozen exclusive-end rule. The extractor was changed to filter video with
`trim=end=30,setpts=PTS-STARTPTS` and audio with
`atrim=end=30,asetpts=PTS-STARTPTS`. W1C001 then contained 719 frames, with the
last media timestamp `29.946583`; its source-frame map contains no incoming
frame at or after `30.000`.

At 23.976 fps, six correct outputs report a container duration of `30.03`
seconds because the final eligible frame has a full sample duration crossing
the nominal boundary. A second disposable test showed that adding output
`-t 30` did not change this without dropping the eligible final frame. The
settled implementation retains every frame whose nominal source-relative
incoming timestamp is `<30.000`, records events by verified source-frame index,
forbids the first displayed frame as an event, and cannot produce a timestamp
at or after `30.000`. No extra source frame is present. This preserves the
frozen boundary rule more faithfully than deleting an eligible frame merely to
make the MP4 container display `30.00`.

### System behavior and provenance safeguards

Created:

- `wave1_blind_coding_system_method-manual_recipe-v1_2026-08-18.py`;
- `wave1_blind_coding_interface_method-manual_recipe-v1_2026-08-18.html`;
- `START_WAVE1_BLIND_CODING_method-manual_recipe-v1_2026-08-18.cmd`;
- a persistent 29-test study-system suite; and
- a separate machine-readable release-qualification record.

The system verifies frozen hashes, exact 12-row correspondence, 30-second
intervals, source identity, forbidden-field absence, source hashes, media
hashes, strict frame maps, and output collisions before use. Media publication
is staged and all-or-nothing. JSON publication uses exclusive atomic hard-link
creation and cannot replace an existing name. Staging cleanup validates the
resolved target is a specifically named child of the Wave 1 directory before
recursive removal.

First-pass session start requires coder/date/session identity, codebook and
plan acknowledgment, and four separate unexposed-to-automation confirmations.
Each event is derived server-side from the selected frame index and appends the
complete qualified template row. There is no edit or delete endpoint. Event
saves use append-only intent/commit journal records; interrupted writes are
recovered idempotently before accepting a new event. Clip completion and
session finalization are also retry-safe. Finalization is possible only after
all 12 clips are confirmed complete, records SHA-256 values in the session
ledger, and marks raw event, progress, audit, start, and final files read-only.

### Test progression and bugs found

- Initial new-system suite: **25 passed, 1 failed**. The sole failure showed
  that `prepare` hashed source masters before reporting an existing-output
  collision. Collision preflight was moved ahead of expensive validation.
- After that fix: **26/26 passed**.
- Added a real FFmpeg synthetic boundary test: **27/27 passed**.
- Added exclusive JSON publication, event transaction recovery, idempotent
  completion/finalization, and interruption injection: **29/29 passed**.
- Combined with the previously qualified 22 workflow tests: **51/51 passed in
  58.46 seconds**, then **51/51 passed in 49.29 seconds** after correction-04
  inventory publication.

Read-only browser qualification loaded W1C001 at source-relative `0.017`, moved
one displayed frame to `0.058`, played to frame 38 at `1.560`, navigated to
W1C002 at source-relative `0.009`, and confirmed that event, completion, and
finalization controls were disabled in preview mode. Normal browser-cancelled
byte-range requests initially printed connection-reset tracebacks during seeks
and source changes. Those expected non-data disconnects are now handled without
an alarming traceback. No session-start dialog was opened and no research data
was written.

A PowerShell hash-report one-liner also stopped with a parser error caused by an
empty pipe element; it was corrected and rerun read-only. It changed no file.

### Published Wave 1 coding media

One documented preparation run verified source hashes, rendered all 12 clips,
decoded source and output frame maps, required equal source/output frame counts,
hashed each output, marked every media artifact read-only, and published the
complete set only after all clips passed.

- directory:
  `.analysis/study_workflow/wave_1_manual/coding_media_wave1_method-manual_recipe-v1_2026-08-18_correction-01/`;
- 12 MP4 files, 90,522,328 bytes total;
- 719 or 720 eligible frames per file;
- coding-media manifest SHA-256:
  `7668440e0c39ca14fb989fd3c55ec22fbd5865d5f60896a630d20331069fb377`;
- deep published-media verification: passed.

These files are manual-coding media, not participant finalists. They are not a
Season One rerun and contain no automated measurements.

### Qualified release hashes

- coding-system tool:
  `670d402688bca58b1ff10755e0cd92a92f4aac3aaf654144383ab370a31b8436`;
- browser interface:
  `a4e37814184a10dca9f88211d17dd57226697faac620059738da027e88c07792`;
- 29-test suite:
  `142462b6e3f6728cb97e1cbb042ee659a22277dcb8baab4c319b85f32e425c3f`;
- launcher:
  `e962f4d071d5fd5a17140d96264e75504c7dde6d6a2112a6f5db678de621048c`;
- release record:
  `2aaec7597b0fc2985ac355565d7c8f4858fa232a643dcb768519f012eeb005ab`.

Correction-04 inventory contains 257 rows. Its CSV SHA-256 is
`db9d3db92892d8727ca18679f35e9550f12f4d5e33d075bfeae5cc2226377535`;
its detached checksum-file SHA-256 is
`5746d647c4440bd6f726ed39aef1681c13694eccb65a3b1154bb33aab8db7d9d`.
It is the point-in-time inventory immediately before this required append-only
log entry. Prior inventories remain unchanged.

### Final state before first coding

Protected Version 1 recipe, candidates, manifest, and selected-clip hashes
still match their preserved values. Codebook hash remains
`c15235ebe9b5ba62f0ee5f0217c85ab4339a6ba1c694726d652d89dd110dab53`;
manual-plan hash remains
`e0e86d1a4ce2df8294944a6023ae6b79105cd38e22cf4f6319135d85c39dbe28`;
calibration-plan hash remains
`8228088550ab66c08309f230be611f00f9a1b313bbf5c9c62a77ebe4f6933dcb`.

Zero coding-system staging directories, matching qualification temporary
directories, calibration-result files, and participant-facing MP4s remain.
The coder-data directory does not exist: **manual coding has not started**.

### Disposable active-browser data-entry qualification addendum

After the read-only preview, the complete browser-to-server write path was
tested in a disposable workspace at
`tmp/wave1_active_ui_qualification_20260818`. This was explicitly not research
data. The fixture copied the frozen small inputs and used the qualified coding
media without altering them.

Two PowerShell attempts to create 12 individual hard links failed because
Windows did not accept the long fixture destination paths. Both attempts
reported errors and created zero media links. The authoritative media were
unchanged. After verifying the empty fixture media directory resolved inside
the disposable workspace and contained only its copied manifest, it was
removed and replaced by a temporary directory junction to the authoritative
read-only coding-media directory.

The active browser test then:

1. completed all six start confirmations and created disposable session
   `W1-SB01-20260818-999`;
2. confirmed event recording was disabled on frame 1/719;
3. stepped to frame 2/719 and appended `W1-SB01-001-E0001` with
   clip-relative `0.058289`, absolute `1101.058289`,
   `transition_type=hard_cut`, and `counts_as_manual_hard_cut=true`;
4. verified the CSV contained exactly one row and the audit actions were
   `session_started,event_intent,event_committed,clip_completed`;
5. required the normal-speed-pass confirmation, completed W1C001, displayed
   `1/12 complete`, and disabled further event recording for that clip; and
6. blocked finalization with `Complete all 12 clips first (1/12 complete).`

The browser tab and local server were closed. The junction target was checked
against the authoritative media path and removed without recursion before the
fixture was recursively removed. After cleanup, the authoritative directory
still contained 12 MP4 files and its manifest still hashed to
`7668440e0c39ca14fb989fd3c55ec22fbd5865d5f60896a630d20331069fb377`.

## 2026-08-18 15:41 EDT — Wave 1 Windows launcher failure investigation and correction

The user reported that double-clicking the original Wave 1 `.cmd` launcher led
to a keypress prompt and then the window closed without presenting the coding
interface. The original launcher was preserved unchanged. Running that exact
launcher under a persistent development terminal succeeded, showing that the
coding application and frozen inputs were intact, but the launcher depended on
the ambient Windows `python` command and did not retain enough diagnostic output
to resolve a double-click environment failure.

Four new, separately named corrections were created and tested in sequence;
none replaced an earlier launcher:

1. `_correction-01` attempted verified-runtime selection and append-only output
   capture. CMD caret escapes reached PowerShell literally, causing a parser
   failure during preflight. No server or coding session started.
2. `_correction-02` corrected quoting. Deep preflight passed and the localhost
   server listened, but the PowerShell pipeline buffered the long-running
   process and the terminal harness could not reliably deliver `Ctrl+C`.
3. `_correction-03` removed the pipeline and invoked the project virtual
   environment directly. Deep preflight passed and the URL printed immediately,
   but the virtual-environment shim spawned a base-Python child across which the
   terminal harness could not deliver `Ctrl+C`.
4. `_correction-04` invokes the verified base interpreter
   `C:\Python313\python.exe` directly. It passed deep verification of all 12
   frozen coding-media files, reproduced the authoritative media-manifest hash,
   printed the tokenized localhost URL immediately, issued the browser-open
   request, and listened only on `127.0.0.1`. No session form was submitted.

For attempts 2–4, any qualification process that could not be stopped through
the terminal harness was identified using its exact executable path, command
line/path context, process ID, and qualification start time before it was
stopped. Final inspection found zero remaining qualification listeners. The
authoritative coder-data directory does not exist, so this investigation
created no research coding data. Existing frozen media and study inputs were
not modified.

The qualified startup launcher is
`START_WAVE1_BLIND_CODING_method-manual_recipe-v1_2026-08-18_correction-04.cmd`
(SHA-256
`e6ea593b4fb063da23d4a3816303b60ca5892c12a6d33ab9d13c0f1660e3f2e1`).
Its append-only lifecycle log is
`wave1_blind_coding_launcher_log_method-manual_recipe-v1_2026-08-18_correction-04.log`.
The immutable launcher qualification record is
`WAVE1_BLIND_CODING_LAUNCHER_QUALIFICATION_method-provenance_recipe-v1_2026-08-18_correction-01.json`
(SHA-256
`ed8e3b29831d27e069eade007429790a1858b6ffcd58dc9c68e98cf69b1377a1`).
This qualifies double-click startup, deep preflight, URL presentation, browser
launch request, and localhost listening. It does not claim that the terminal
harness qualified nested Windows-console shutdown signaling. The user should
keep the command window open throughout coding and close it only after the
coding session is finished.
The authoritative coder-data directory remained absent.

The immutable active-interface qualification addendum is
`WAVE1_BLIND_CODING_SYSTEM_ACTIVE_UI_QUALIFICATION_method-provenance_recipe-v1_2026-08-18_correction-01.json`.

Correction-05 inventory was then generated with 260 rows after the active
qualification record and this log section existed. Its CSV SHA-256 is
`6c42c94ae895e26a52287adf7c75b1f01390f8486af6eb36ca83cf811a5ed2bc`;
its checksum-file SHA-256 is
`e42dd652bf8bbb509e1c3547546fd59f8682648a29a09a8eff31b5f5906b6827`.
The active-interface addendum SHA-256 is
`acf58809b475e9a175306af89503339c6fa35b3e9d8b9302da802b83c17a4c43`.
This final paragraph is necessarily the append-only entry immediately after
that point-in-time inventory.

The complete 51-test gate passed again in **45.63 seconds** against the
correction-05 inventory pointer, and deep verification again passed all 12
published media files. Final cleanup reported zero matching qualification
temporary directories, zero staging directories, and no authoritative
coder-data directory. The authoritative media count remained 12 and the media
manifest hash remained
`7668440e0c39ca14fb989fd3c55ec22fbd5865d5f60896a630d20331069fb377`.

### Append-only placement correction

The launcher investigation entry timestamped 2026-08-18 15:41 EDT was
accidentally inserted immediately before the last two sentences of the prior
active-interface qualification entry instead of at the physical end of this
file. In accordance with the append-only rule, the misplaced text has not been
deleted, moved, or rewritten. Those two following sentences—beginning “The
authoritative coder-data directory remained absent” and continuing through the
correction-05 qualification results—belong to the earlier active-interface
entry. This correction is appended to preserve both the original bytes and the
intended chronology transparently.

### Final launcher requalification and correction-06 inventory

After the launcher records and placement correction existed, the correction-06
point-in-time inventory was generated with 271 rows. The inventory CSV SHA-256
is `970360d2d19c69ea508c3dab52b43df92e03f3ff0e77d7f4c11fa064f45c96f4`;
the detached checksum-file SHA-256 is
`3be359557798fea4b5ef5b55076dd97e169b62fb6c7f171a1c2eb079ac3dacfc`.
This paragraph necessarily follows that point-in-time inventory and is not a
row within it.

The complete research-workflow and blind-coding-system gate passed **51/51
tests in 53.48 seconds** against the correction-06 inventory pointer. A separate
deep verification passed all 12 frozen blind coding clips and reproduced media
manifest SHA-256
`7668440e0c39ca14fb989fd3c55ec22fbd5865d5f60896a630d20331069fb377`.
The exact test temporary directory was confirmed to resolve as a direct child
of the project `tmp` directory and was then removed. Final inspection found no
authoritative coder-data directory and zero localhost qualification listeners.
No research coding data were created during launcher qualification.

## 2026-08-18 15:52 EDT — Researcher-account access failure and ACL correction

The user's screenshot showed a `PermissionError: [Errno 13]` while reading
`wave1_blind_worklist_method-manual_recipe-v1_2026-08-18_correction-01.csv`.
The error footer exactly matched the preserved unsuffixed launcher, confirming
that it—not `_correction-04`—had been opened. Inspection also found a substantive
cross-account qualification gap: nine corrected blind-package files had
protected Windows ACLs containing only OWNER RIGHTS, SYSTEM, and Administrators.
Their owner was the Codex sandbox identity, so the enabled
`DESKTOP-OL7MNUO\Samuel` account had no read access. Tests run as the sandbox
owner could not expose this defect.

Before any ACL change, the exact owner, protected SDDL, size, modification time,
and SHA-256 of all nine files were frozen in
`WAVE1_BLIND_MATERIALS_ACL_PRECHANGE_method-provenance_recipe-v1_2026-08-18_correction-01.json`.
The initial `icacls /grant:r` correction granted the intended read entry but
unexpectedly re-enabled inherited parent permissions, transiently giving the
Samuel account FullControl. Immediate ACL verification detected this. No file
content, size, modification time, or hash changed. A complete protected SDDL was
then applied to each exact file, retaining the original owner and original
OWNER RIGHTS/SYSTEM/Administrators full-control entries while adding only
`Read, Synchronize; Allow` for Samuel's SID. Final verification found nine
protected ACLs, nine explicit Samuel read-only entries, no Samuel write entries,
and zero ACL verification errors. All nine content hashes, sizes, and
modification times still match the pre-change record.

Deep package verification then passed all 12 clips and reproduced coding-media
manifest SHA-256
`7668440e0c39ca14fb989fd3c55ec22fbd5865d5f60896a630d20331069fb377`.
The complete outcome, including the detected transient overgrant, is preserved
in
`WAVE1_BLIND_MATERIALS_ACL_CORRECTION_method-provenance_recipe-v1_2026-08-18_correction-01.json`
(SHA-256
`f594c720f3bbad2d70fd9d7c1464d3b17237fd090198902e1448d1bf73f91234`).

Created the separately named `_correction-05` launcher (SHA-256
`1dba12bf0b82f38a31323ed440b321c8b0d937f4c04599acb3e4b659b1151769`).
It visibly labels its revision, records the executing Windows identity, and
verifies readable frozen inputs before starting the localhost server. Its
verification-only qualification passed all 12 clips without starting a server
or coding session. The authoritative coder-data directory remained absent;
this investigation created no research coding data.

### ACL-correction release gate and correction-07 inventory

After the ACL records, `_correction-05` launcher, README update, and preceding
log entry existed, the correction-07 point-in-time inventory was generated with
277 rows. Its CSV SHA-256 is
`8e496d4ddebb2a040a4902cc7c432999bde53de0b6477c905a625a41101dbd32`;
its detached checksum-file SHA-256 is
`e6dcd71d27ae539826f81ee3e6b688ab1e5b8a7a88d1bd767dfcaea42427e9a7`.
This paragraph necessarily follows that inventory and is not a row within it.

The complete research-workflow and blind-coding-system gate passed **51/51
tests in 51.00 seconds** against the correction-07 inventory pointer. Separate
deep verification again passed all 12 frozen clips and reproduced media
manifest SHA-256
`7668440e0c39ca14fb989fd3c55ec22fbd5865d5f60896a630d20331069fb377`.
Final ACL inspection again found nine protected package files with one explicit
Samuel `Read, Synchronize; Allow` entry apiece and no verification errors. The
exact test temporary directory was verified as a direct child of project
`tmp` and removed. No coder-data directory and no localhost qualification
listener remained. Actual startup under the Samuel account remains a required
user confirmation because the automated qualification process runs under the
separate Codex sandbox identity.

## 2026-08-19 — Pre-use technical qualification and methodological hold

This entry records the requested last pre-use check. It does not authorize
manual event coding. The frozen Wave 1 browser system was exercised only with
disposable qualification data, and the real session files were read but not
modified.

### State and provenance audit

`git status --short`, the study-output trees, the frozen hashes, the Windows
ACLs, active listeners, launcher logs, and coder-data paths were inspected
before testing. The initial combined read-only PowerShell audit command failed
with an `empty pipe element` parser error; it changed nothing and was corrected
and rerun. A later `Get-CimInstance Win32_Process` query returned Access Denied;
it also changed nothing, and `Get-NetTCPConnection` established that no study
listener remained. The Version 1 recipe, Season One manifest, candidates,
selected-clips table, codebook, coding plan, and calibration plan retained their
previously frozen SHA-256 values.

The earlier statement that no coder-data directory remained was no longer
current after the user successfully started the correction-05 launcher on
2026-08-18 at 16:03:12 EDT. The authoritative directory contains a real
session-start JSON, a header-only first-pass event CSV, and a one-record audit
journal for `W1-SB01-20260818-001`. It contains **zero manual event rows and zero
clip-completion rows**. Their SHA-256 values are, respectively,
`38359a8136715f7da05517f5adf4b56db2b2f38159d31d9dce80cd29b825f511`,
`654e6b865481535bf297f132462d7bf61807bfe32cf24d814ba082e6165faeed`,
and `8f1c707f5a671df161b870458216523d1433bdb8feffa84e34fe0345b60af4b9`.
They were preserved unchanged throughout this qualification.

### Automated tests and media verification

The initial study-specific command used the existing analysis virtual
environment, disabled the pytest cache, selected a dated disposable base
directory, and ran both study-workflow test files. It passed 51/51 tests in
45.81 seconds. Deep verification with
`wave1_blind_coding_system_method-manual_recipe-v1_2026-08-18.py --root . verify`
passed all 12 media clips and reproduced manifest SHA-256
`7668440e0c39ca14fb989fd3c55ec22fbd5865d5f60896a630d20331069fb377`.

The first repository-wide `tests` run produced 68 failures, 427 passes, and 81
skips because the existing analysis test virtual environment lacked the
declared PySide6 dependency. `PySide6>=6.6,<7` was installed into that test-only
virtual environment; version 6.11.2 was obtained. The rerun then produced 620
passes, 15 skips, and 11 failures. Ten failures concern the separate unfinished
desktop `ui/handcoding.py` worklist/editor (`CodeView.worklist` and
`CodeView._table` are absent). One concerns the separate construct resolver:
an unavailable TransNetV2 method reports `unavailable` before it can report
`method_not_used`. Two shutdown-time Qt callbacks also attempted to read an
already-deleted `Scene`. These failures do not execute the frozen Wave 1
localhost coding system. They were diagnosed and left unchanged as unrelated
work.

The study-specific suite previously covered all major persistence and failure
paths but explicitly round-tripped only one of the six `Other` subtypes. A
test-only parameterized case was appended to cover every visible option:
`hard_cut`, `dissolve`, `fade_out`, `fade_in`, `wipe`, `iris`,
`whip_pan_disguised_cut`, `page_turn`, `non_boundary_graphic_overlay`, and
`other_described`. It also verifies the frozen derived-count rule: only
`hard_cut` and `whip_pan_disguised_cut` produce
`counts_as_manual_hard_cut=true`. No frozen material or runtime behavior was
changed. The expanded study-specific gate passed **61/61 tests**.

### Visible browser qualification

A disposable root named
`tmp/wave1_browser_qualification_method-manual_recipe-v1_2026-08-19_correction-01`
was created. It held exact copies of the small frozen contract files and links
to the real FFmpeg executable, Season One sources, and 12 coding-media files.
Its coder-data directory was independent of the authoritative directory. The
first fixture command used an incorrect event-template name and omitted the
media correction suffix, FFmpeg, and source paths; startup failed closed before
serving. The partial fixture was verified as a direct child of `tmp`, removed,
and recreated correctly.

The corrected disposable server bound only to `127.0.0.1:8765`. Through the
visible in-app browser, the following user path was confirmed: real W1C001 MP4
playback advanced with media `readyState=4`; the first displayed frame could
not be recorded; all six start attestations were required; `Other` enabled the
subtype control; `other_described` without notes was rejected; a valid uncertain
event was appended with the expected clip-relative and absolute timestamps;
reopening the page resumed that exact event; clip completion required the
full-normal-speed-pass checkbox and an irreversible-action confirmation; the
completion API returned 200; premature finalization was blocked at 1/12; and
W1C002 loaded with an independent empty event list. Browser console inspection
returned no warnings or errors. Two early automated completion attempts timed
out while waiting at the JavaScript confirmation dialog; accepting that dialog
concurrently in a fresh disposable tab completed the same action successfully.
This was a browser-automation control issue, not a coding-application failure.

The resulting disposable files contained one deliberately labeled
qualification-only event and one clip completion, matching the UI. Inspection
again found zero manual event rows in the authoritative session. The localhost
server was stopped before cleanup.

### Qualification outcome

The machine-readable record is
`.analysis/study_workflow/qualification/WAVE1_BLIND_CODING_PREUSE_QUALIFICATION_method-provenance_recipe-v1_2026-08-19_correction-01.json`.
The technical verdict is **pass**, but authorization for real manual event
coding is **on hold**. The current `validation/CODEBOOK.md` identifies itself as
a draft, and the literature review identified unresolved operational choices:
the whip-pan-as-Other representation, the non-boundary-overlay event category,
the one-blend-frame rule, interval versus midpoint coding for gradual
transitions, and the two-event fade rule. These must be resolved or explicitly
accepted and then frozen before the first real event is coded. This is a
methodological hold, not a software failure.

### Pre-use qualification inventory and cleanup

After the qualification record and preceding log entry existed, correction-08
of the exhaustive point-in-time inventory was generated with 283 artifact rows
(284 CSV lines including the header). The inventory CSV SHA-256 is
`0082b1224f024d6298c636c4416f8dc8f02fff1071800cc8eb8b17cbf2d00ade`;
its detached checksum-file SHA-256 is
`02b71d87092ff819a61eda0676729ba2156bf577338f785c18da28adcd5b8205`.
The qualification-record SHA-256 captured by that inventory is
`bcd79965145cb130f7dada9e635c37405cbd308e27f01344f3b8f55dbe18f08c`.
The exhaustive-transition test file SHA-256 is
`122ec3fddc2238b130c234895702aa76472f451442b37d50b27f37dd991546c8`.
The inventory pointer was advanced from correction-07 to correction-08 without
altering or deleting any earlier inventory.

All seven exact qualification/test directories were verified to resolve as
direct children of the project `tmp` directory before removal. The two
disposable junctions were verified as junctions and removed without traversing
their targets. Final cleanup found zero remaining target directories, zero
listeners on port 8765, and zero authoritative manual event rows. No source
video, coding-media file, frozen plan, frozen contract, prior inventory, cache,
or feasibility output was modified or deleted.

### Append-only correction — correction-08 pointer ordering

The first final gate against correction-08 produced 60 passes and one failure.
The failure was confined to provenance ordering: correction-08's detached
checksum recorded `STUDY_FILE_INVENTORY.md` before that document was changed to
point to correction-08. The inventory CSV and checksum were not overwritten or
deleted. To correct the sequence, the pointer was advanced to the new
correction-09 filename **before** generating correction-09. Correction-09
therefore hashes the already-final pointer document. This preserves the failed
correction-08 evidence and makes the ordering error reproducible.

Correction-09 was generated after the pointer was already final. It contains
285 artifact rows. Its inventory CSV SHA-256 is
`2224df10e69aaf29da0e7f04bf0f887e20ef45145dbb8418e4867f1db7d23e5f`;
its detached checksum-file SHA-256 is
`ac5901fe96dc7eaf597b7d7f6f476ad6a9c7739eb28ef00b7578a39e094360de`;
and the pointer document hash recorded inside that checksum file is
`2019b151cbf0b348160aaf119ef43cc5d0a0a8edf4e5f9da2c982654b27df1d5`.
The complete study-specific gate then passed **61/61 tests in 46.26 seconds**
against correction-09. Deep verification again passed all 12 clips and
reproduced media-manifest SHA-256
`7668440e0c39ca14fb989fd3c55ec22fbd5865d5f60896a630d20331069fb377`.
Both exact final-gate temporary directories were verified as direct children
of `tmp` and removed. Final inspection found zero matching temporary
directories, zero listeners on port 8765, and zero authoritative manual event
rows.

## 2026-08-22 — Correction-02 methodological decisions and Markdown authorities

This is an append-only documentation entry. It records Samuel's explicit
approval in the study chat of the five methodological resolutions and the
primary plus-or-minus-0.250-second automated/manual matching tolerance. No
manual coding, detector calibration, Season One rerun, finalist selection,
media export, manifest generation, coding-package generation, tool-code edit,
or coder-data edit occurred in this documentation step.

### Approved methodological decisions

1. A genuine hard cut masked by a whip pan remains `hard_cut`; a separate
   `whip_pan_masking` flag records the masking mechanism.
2. A graphic/text overlay over a continuing shot is not a transition event. It
   belongs in a separate non-boundary-observation overlay.
3. Exactly one confirmed blended frame is not automatically a clean hard cut.
   It is coded `single_frame_blend`, uncertain, and pending adjudication. The
   immutable raw row does not count as a manual hard cut; only a separate
   adjudication establishing a decoding/transcoding artifact around an
   adjacent-frame editorial cut can resolve the derived reference to
   `hard_cut`.
4. Gradual transitions retain observed start and end frames/timestamps; their
   midpoint is derived rather than hand-entered.
5. A fade-out/fade-in through a solid color remains two raw optical-event rows
   linked by `fade_pair_id`, with `black_gap_frames` preserved. A complete pair
   produces one derived fade-through-color shot-structure transition.
6. Primary automated/manual boundary correspondence uses a frozen one-to-one
   plus-or-minus-0.250-second tolerance. Plus or minus 1.000 second is retained
   only as a prespecified sensitivity analysis and cannot select Version 2.

The same correction also makes the formal clip-boundary rule explicitly
conjunctive: displayed frame index greater than zero, clip-relative timestamp
greater than 0.000 seconds, and clip-relative timestamp less than 30.000
seconds. The short interval before the first displayed decoded frame is
documented as unobservable.

### New correction-02 Markdown authorities

- `validation/CODEBOOK_wave1-2_method-manual_recipe-v1_2026-08-22_correction-02.md`  
  SHA-256:
  `b46bdaab419d1e33138d2bf3a6e98a5b6bf80f7fa97fcf311c2c18b905906f90`
- `STUDY_MANUAL_CODING_PLAN_wave1-2_method-manual_recipe-v1_2026-08-22_correction-02.md`  
  SHA-256:
  `2050c040227e0e1c00f3d420547381b5f7c76ad5d6cba78fedc477af6ddf477a`
- `STUDY_CALIBRATION_PLAN_wave1_method-manual-vs-automated_recipe-v1-v2_2026-08-22_correction-02.md`  
  SHA-256:
  `bc323b4176f2018aba9ff685f123f49781c45e8bc791e7da174ef38c8293b39d`

The earlier files remain unchanged:

- `validation/CODEBOOK.md`, SHA-256
  `c15235ebe9b5ba62f0ee5f0217c85ab4339a6ba1c694726d652d89dd110dab53`;
- `STUDY_MANUAL_CODING_PLAN.md`, SHA-256
  `e0e86d1a4ce2df8294944a6023ae6b79105cd38e22cf4f6319135d85c39dbe28`;
  and
- `STUDY_CALIBRATION_PLAN.md`, SHA-256
  `8228088550ab66c08309f230be611f00f9a1b313bbf5c9c62a77ebe4f6933dcb`.

### Inspection and documentation commands

From the project root, the documentation step used read-only `git status
--short`, `Get-Content`, `rg`, and `Get-FileHash -Algorithm SHA256` commands to
inspect the dirty tree, read the authoritative study files in the handover's
stated order, inspect the independent pre-use audit, and calculate document
hashes. New Markdown files and this append-only entry were written with
provenance-preserving patch operations. No command wrote to source videos,
recipes, manifests, candidate tables, generated tables, caches, inventories,
qualification records, Season Two outputs, coding media, or coder files.

### Invalidation and release status

These methodological authorities invalidate the correction-01 codebook/plan
hash references in the existing worklist, blind manifest, detached checksums,
media manifest, tool `FROZEN_HASHES`, launcher qualification, and empty session
start record. They do not alter the frozen 12 Wave 1 clip identities or source
timecodes, the Version 1 automated results, motion measurements, audio-intensity
measurements, or media bytes.

The empty correction-01 session remains preserved with zero manual event rows
and must not be resumed. A new correction-02 tool, worklist, manifest,
checksums, media-manifest provenance, templates/overlays, launcher, tests, and
pre-use qualification record are required before coding. The current status
therefore remains **NO-GO for authoritative manual coding**.

### Handover correction

`STUDY_HANDOVER.md` received a clearly labeled 2026-08-22 correction section
directing future chats to the three correction-02 methodological authorities
and retaining its earlier content. Its pre-correction SHA-256
`f8a2f229ecf0b92df7d61480b3eb5e7719504354a3927b98e6b9edc6c5b9f802`
is preserved in that section. Its post-correction SHA-256 is
`dd7029edeb649c9f782b6bd9b4f838fa307639f87e28940fd307dec09f7c53a8`.

### Documentation artifact inventory at creation

| Artifact | Bytes | Modification time UTC | SHA-256 |
|---|---:|---|---|
| `validation/CODEBOOK_wave1-2_method-manual_recipe-v1_2026-08-22_correction-02.md` | 10,816 | `2026-08-22T14:54:10.0850033Z` | `b46bdaab419d1e33138d2bf3a6e98a5b6bf80f7fa97fcf311c2c18b905906f90` |
| `STUDY_MANUAL_CODING_PLAN_wave1-2_method-manual_recipe-v1_2026-08-22_correction-02.md` | 12,417 | `2026-08-22T14:55:32.5170206Z` | `2050c040227e0e1c00f3d420547381b5f7c76ad5d6cba78fedc477af6ddf477a` |
| `STUDY_CALIBRATION_PLAN_wave1_method-manual-vs-automated_recipe-v1-v2_2026-08-22_correction-02.md` | 11,035 | `2026-08-22T14:56:41.4358541Z` | `bc323b4176f2018aba9ff685f123f49781c45e8bc791e7da174ef38c8293b39d` |
| `STUDY_HANDOVER.md` after the dated correction | 22,134 | `2026-08-22T14:58:52.7933325Z` | `dd7029edeb649c9f782b6bd9b4f838fa307639f87e28940fd307dec09f7c53a8` |

The exhaustive inventory pointer remains correction-09 during this
documentation-only step. A new exhaustive inventory revision must be generated
after the correction-02 software and package artifacts exist so it captures the
complete release atomically rather than presenting this partial documentation
set as a qualified package.

## 2026-08-22 — Verified shutdown of obsolete Wave 1 coding servers

After Samuel authorized correction-02 remediation, process metadata was
captured as `desktop-ol7mnuo\samuel` before termination. PIDs 2416, 3840, 6748,
13320, and 10040 were present and each command line contained the exact obsolete
`wave1_blind_coding_system_method-manual_recipe-v1_2026-08-18.py` filename. PIDs
2416, 3840, 6748, and 13320 were listening on ports 58461, 52059, 65255, and
8765 respectively; PID 10040 was the non-listening Python shim/parent for
13320.

The termination command re-read and rejected any PID whose command line did
not match that exact study tool. It produced:

```text
verified_ids=2416,3840,6748,13320,10040
remaining_processes:
remaining_study_listeners:
```

The five verified processes were stopped. Follow-up inspection found no Python
process running the obsolete tool and no listener on the four captured ports.

The correction-01 authoritative session remained unchanged with zero event
rows. Its audit, event, and session-start SHA-256 values remained
`8f1c707f5a671df161b870458216523d1433bdb8feffa84e34fe0345b60af4b9`,
`654e6b865481535bf297f132462d7bf61807bfe32cf24d814ba082e6165faeed`,
and `38359a8136715f7da05517f5adf4b56db2b2f38159d31d9dce80cd29b825f511`.

Detailed evidence was written to the new file
`.analysis/study_workflow/qualification/WAVE1_LEGACY_SERVER_SHUTDOWN_method-provenance_recipe-v1_2026-08-22_correction-01.md`.
This shutdown does not authorize coding; correction-02 remains NO-GO.

### Append-only correction — browser disclosure and document hashes

During correction-02 implementation, before generating any dependent package,
the browser-disclosure wording was checked against the actual stable
`clip_id`. That identifier embeds the source episode and therefore cannot be
shown while claiming episode blinding. The manual plan was corrected to expose
only neutral `blind_id` and blind order in the browser while retaining
`clip_id`, source filename, and absolute timecodes privately in saved records.

The original correction-02 document hashes recorded above remain as historical
pre-correction values. The corrected manual-plan SHA-256 is
`c4e8f709c474703a377b6abce4333c2741d016201104d369566dac3ed6486f7c`.
Because the calibration plan pins that hash, it received a corresponding
pre-package correction; its new SHA-256 is
`ca0008cf7346787ca9c186c3465633fde79a8a73d0da9f3575c2c860d4464bd7`.
No coding had begun, so no recoding is required. These corrected hashes are the
ones eligible for the correction-02 package.

## 2026-08-22 — Correction-02 blind-coding release, qualification, and scoped GO

Samuel authorized implementation after approving all five taxonomy decisions.
No detector tuning, Season One rerun, Version 2 run, finalist selection, or
stimulus export was performed. The correction-01 release, its qualification
records, and its empty coder session were retained.

### Correction-02 package generation

The new package was generated from the unchanged 12-row correction-01 Wave 1
selection with
`.analysis/study_workflow/tools/generate_wave1_blind_materials_method-manual_recipe-v1_2026-08-22_correction-02.py`.
The generator verified the correction-01 worklist/manifest/media-manifest
hashes and the three correction-02 authority hashes before writing new,
non-overwriting correction-02 paths. It created a worklist, blind manifest,
detached checksums, event/non-boundary/correction/adjudication/session/manual-
overlay/fade-pair templates, and a new media manifest. The 12 correction-02
MP4 names are hard links to the preserved correction-01 bytes; `fsutil hardlink
list` reported exactly the old and new paths for every clip, and all 12 old/new
and manifest hashes matched. No media was rerendered and the 12 files remain
read-only (90,522,328 bytes total).

Frozen package identities:

| Artifact | SHA-256 |
|---|---|
| correction-02 codebook | `b46bdaab419d1e33138d2bf3a6e98a5b6bf80f7fa97fcf311c2c18b905906f90` |
| correction-02 manual plan | `c4e8f709c474703a377b6abce4333c2741d016201104d369566dac3ed6486f7c` |
| correction-02 calibration plan | `ca0008cf7346787ca9c186c3465633fde79a8a73d0da9f3575c2c860d4464bd7` |
| worklist | `cf9c1d36a7854da0e390a742b7baefbe73ec050ddc3006c05823889edd8b0727` |
| blind manifest | `45ee34fb0d39752b51e21b60ab6a6e18542cd7164d6305c5949b77b1f148a6b7` |
| detached checksums | `a2dc0bf8ee6a67535438822afde93b9f26cce11fe2da26cebda392fdad2d28b3` |
| media manifest | `519b288b0a1a204fcd83c04c79ca4d99259b6e5b2735f8c0547ee0c921e67e22` |
| final coding interface | `e310453afc6fa9be07a5912322369473f907a999e05d0fc5863d406f5c2a921a` |
| final coding tool | `52f6b3afdd79649aebecc4b29384c801215293961761a59f3f898a5474d5ee24` |
| launcher | `1ce768bafba7bba9b9a2aae5a3ae7de20a4087102131fddee076a727b85b7514` |
| final correction-02 regression test | `1a40c5d1dabe9d80746ce2ae2b430450b5c4b8aa5516d656521f536f7a22278f` |

Rerunning the generator after release returned `RuntimeError: Refusing to
replace correction-02 artifacts` with exit code 1. Before/after hashes of the
worklist, blind manifest, detached checksums, and media manifest were equal.
This was the expected non-overwrite result.

### F4 inventory ACL correction

Three pre-change attempts stopped without modifying ACLs: one PowerShell
parser error, one wrong `version_1` directory assumption, and one exact-name
check that found only the eight CSVs because the checksum companions use
`study_file_inventory_checksums_...` names. After resolving the exact paths,
`icacls` granted `DESKTOP-OL7MNUO\Samuel` read-only access on exactly the eight
correction-02 through correction-09 full inventories and eight checksum
companions. All 16 content hashes were unchanged. A command running as Samuel
read and hashed all 16 successfully. Evidence is
`.analysis/study_workflow/qualification/WAVE1_INVENTORY_ACL_CORRECTION_method-provenance_recipe-v1_2026-08-22_correction-02.json`
(SHA-256
`98fe28f74593b36d36e3b35fe9787e1d9c45c939cd08d2d2db8d8951c208bdd0`).

### Automated tests and researcher-account gates

The correction-02-only suite first passed 46 tests. Review then added explicit
duplicate/recovery tests for non-boundary observations and a same-workspace
server-lock test; 49 passed. Active-browser inspection found an initial-state
UI gap: if the session dialog were dismissed, Complete and Finalize were not
initially disabled. The server would reject the request, but the coder would
see a confusing failure. Both buttons were made disabled by default, the HTML
was added to the tool's frozen runtime hash set, and an interface-drift test was
added. The final correction-02-only run passed 50/50.

The complete study-specific suite was run as
`DESKTOP-OL7MNUO\Samuel` using the project test virtual environment and a
dedicated `--basetemp`. The final result was **111 passed in 89.02 seconds**.
The correction-02 `verify` command then deep-hashed all 12 clips and returned
manifest SHA-256
`519b288b0a1a204fcd83c04c79ca4d99259b6e5b2735f8c0547ee0c921e67e22`.
The correction-02 `.cmd --verify-only` launcher passed as Samuel and explicitly
reported that no server or coding session started.

### Active browser qualification

Browser testing used the in-app browser workflow and a verified direct child
of `tmp`. The first attempted disposable path was too long for PowerShell to
create nested hard links; it created no media links or coder data. A shorter
disposable root used a junction to the already verified read-only media only;
all coder files remained inside the disposable root. Both disposable roots
were removed after testing, and the exact server processes/listeners were
stopped and verified absent.

The final live exercise verified safe initial controls, all seven start
attestations, 12 neutral blind IDs without source/episode or automated-result
disclosure, real playback, frame stepping, first-frame point-event exclusion,
a whip-pan-masked hard cut, a separate graphic-overlay observation, a forced-
uncertain/pending single-frame blend, a start-censored gradual event, paired
fade-out/fade-in rows, resume after reload, same-workspace second-server
rejection, one confirmed append-only clip completion, and finalization still
blocked at 1/12 clips. Browser warning/error logs were empty.

One browser-control call timed out during the fade pair, and a later call
waited on the completion confirmation. Before reconnecting, the disposable
CSV and server log were read so no write was repeated. The fade-out was already
present and the prepared fade-in was recorded once; Samuel clicked OK on the
visible disposable completion prompt. Final disposable outputs were 5 event
rows, 1 non-boundary row, and 1 completion row. They were hashed for evidence
then deleted. No authoritative correction-02 coder-data directory was created.
Evidence is
`.analysis/study_workflow/qualification/WAVE1_BLIND_CODING_ACTIVE_UI_QUALIFICATION_method-provenance_recipe-v1_2026-08-22_correction-02.json`
(SHA-256
`0e2609e3e6dfee383171e05d177b2c31010adb87fe42da19a7058f7fd92d654b`).

### Broader repository check and scope boundary

The first repository-wide command was interrupted during collection because
pytest traversed four disposable `tmp` trees owned by the sandbox account and
Samuel could not read them. Those exact direct children were removed, and the
rerun used `--ignore=tmp`.

Before dependency correction, the broader result was 620 passed, 15 skipped,
and 11 failed. Ten `tests/test_handcoding_worklist.py` failures were reproduced
as the audit described: native 64-bit VLC existed at
`C:\Program Files\VideoLAN\VLC\vlc.exe`, but the project test virtual
environment lacked `python-vlc`, so `ui/player.py:85-95` returned unavailable
and `CodeView.__init__` intentionally returned at `ui/handcoding.py:262-275`
before creating `worklist` or `_table`. With Samuel's approval,
`python-vlc==3.0.21203` was installed only into the existing test virtual
environment. The hand-coding UI file then passed 16/16 tests.

The final broader result was **631 passed, 14 skipped, 1 failed**. The remaining
failure is
`tests/test_constructs.py::test_a_method_that_did_not_produce_the_cached_number_refuses`:
`analyzer/constructs.py:1026-1029` returns `unavailable` before the cache
attribution check at lines 1051-1088 can return `method_not_used`. This module
is not imported by the standalone correction-02 blind-coding tool. It was not
silently edited because it is a separate CMAT subsystem outside this release's
frozen scope. Therefore the qualification makes no whole-repository all-green
claim.

### Preservation and release decision

The correction-01 event file remained at zero data rows with SHA-256
`654e6b865481535bf297f132462d7bf61807bfe32cf24d814ba082e6165faeed`;
its start and audit hashes remained
`38359a8136715f7da05517f5adf4b56db2b2f38159d31d9dce80cd29b825f511`
and `8f1c707f5a671df161b870458216523d1433bdb8feffa84e34fe0345b60af4b9`.
No authoritative correction-02 coder-data directory exists.

The scoped pre-use qualification is
`.analysis/study_workflow/qualification/WAVE1_BLIND_CODING_PREUSE_QUALIFICATION_method-provenance_recipe-v1_2026-08-22_correction-02.json`
(SHA-256
`5eeab0fd8bb28bf1bd71b9f81074e993d85eb877026b11e3340619a35477bee9`).
Its decision is **GO only for the correction-02 standalone Wave 1 blind manual-
coding workflow**. Correction-01 remains DO NOT USE. This is not approval to
tune the detector, rerun Season One, inspect automated values before first-pass
lock, or use the unrelated CMAT construct resolver as though its full suite
were green.

### Exhaustive inventory correction-10

The preserved 2026-08-18 inventory generator did not include the new versioned
root authority files. It was left unchanged. A new dated generator,
`.analysis/study_workflow/tools/generate_study_file_inventory_method-provenance_recipe-v1_2026-08-22_correction-02.py`,
extended the validated scope to the correction-02 codebook and plans and wrote
only new correction-10 targets. Syntax compilation passed. Running it as
`DESKTOP-OL7MNUO\Samuel` produced 330 rows:

- inventory SHA-256:
  `c6b74fc4f87d0b98a0db951f18bf954d4f6f6afb7302d70a8a465aa23eb84b1e`;
- checksum-file SHA-256:
  `bfdfd9e5088e21c6f8e059ebe633c8a07cacc56e1d24170195ec05b81e639c54`.

Samuel-account verification found all five specifically queried correction-02
authority/tool/qualification rows, no missing required path, and matching CSV
and `STUDY_FILE_INVENTORY.md` detached hashes. A second generator invocation
returned `FileExistsError: Refusing to replace correction-10 inventory
artifacts` with exit code 1, as required. This append-only log paragraph was
written after the inventory snapshot and therefore is intentionally later than
the log-file hash recorded in correction-10; it does not alter the frozen
inventory CSV or its detached checksum.

### Final post-inventory study-specific gate

After `STUDY_FILE_INVENTORY.md` was updated to identify correction-10, the
complete study-workflow test directory was rerun as
`DESKTOP-OL7MNUO\Samuel` with the project test virtual environment, pytest
cache disabled, and the dedicated disposable base directory
`tmp/pytest_wave1_final_post_inventory_20260822`. The exact command was:

`\.analysis\cmat-test-venv\Scripts\python.exe -m pytest
\.analysis\study_workflow\tests --basetemp
\.tmp\pytest_wave1_final_post_inventory_20260822 -p no:cacheprovider -q`

Result: **111 passed in 67.65 seconds**, exit code 0. This includes the test
that resolves the newest correction inventory and verifies its detached
checksums and the pointer in `STUDY_FILE_INVENTORY.md`. The disposable pytest
directory was resolved as a direct child of the project `tmp` directory and
then removed; the post-removal existence check returned `removed=True`.

Correction to the command transcription immediately above: the three relative
paths were displayed without their leading dots. No command was rerun and no
result changed. The exact executed command used
`.\.analysis\cmat-test-venv\Scripts\python.exe`,
`.\.analysis\study_workflow\tests`, and
`.\tmp\pytest_wave1_final_post_inventory_20260822`, respectively. The original
transcription is retained above as required by the append-only correction
policy.

## 2026-08-22 — Researcher ratification of correction-02 methodological decisions

Samuel provided the following explicit ratification in the study task after
reviewing the independent auditor's concern about the one-blend-frame rule:

> I ratify the five methodological decisions recorded in the correction-02
> qualification, including treating exactly one blended frame as
> single_frame_blend, uncertain and pending adjudication, rather than
> automatically counting it as a hard cut.

This statement explicitly ratifies the five entries in
`approved_method_decisions` in
`.analysis/study_workflow/qualification/WAVE1_BLIND_CODING_PREUSE_QUALIFICATION_method-provenance_recipe-v1_2026-08-22_correction-02.json`.
It confirms, rather than changes, the correction-02 codebook, manual-coding
plan, calibration plan, software behavior, or qualification decision. No
coding session was started, no manual event or completion row was written, and
no automated result was exposed. The authoritative correction-02 coder-data
directory remained absent immediately before this append-only entry.

## 2026-08-22 — Wave 1 adjudicated-reference system implementation and qualification

Samuel authorized construction of the derived adjudicated-reference system
after explicitly ratifying the correction-02 methodological decisions. Before
editing, `git status --short` and the Wave 1 manual, comparison, calibration,
qualification, tool, and test directories were inspected. The unrelated dirty
working tree was preserved. The authoritative correction-02 coder-data
directory did not exist.

### Frozen inputs and implementation gap

The correction-02 codebook, manual-coding plan, calibration plan, event
template, correction template, adjudication template, fade-pair template,
non-boundary template, session template, coding-media manifest, and finalized-
session implementation were read before the new system was written. The
confirmed gap was that the frozen plan described derived refined views and an
adjudicated hard-cut reference but no program could construct or validate
them. The change did not alter the frozen authorities or transition taxonomy.

The new files are:

- `.analysis/study_workflow/tools/wave1_adjudicated_reference_system_method-manual_recipe-v1_2026-08-22_correction-01.py`;
- `.analysis/study_workflow/tests/test_wave1_adjudicated_reference_system_method-manual_recipe-v1_2026-08-22_correction-01.py`;
- `.analysis/study_workflow/wave_1_manual/WAVE1_ADJUDICATED_REFERENCE_SYSTEM_method-manual_recipe-v1_2026-08-22_correction-01.md`; and
- `.analysis/study_workflow/qualification/WAVE1_ADJUDICATED_REFERENCE_SYSTEM_QUALIFICATION_method-provenance_recipe-v1_2026-08-22_correction-01.json`.

Their release hashes before this log and the later inventory step were:

| Artifact | SHA-256 |
|---|---|
| Tool | `3e921233dd13597f3a7703cb52770ea5f74d80bddc1fc3855b039388833c609c` |
| Test suite | `f06ff98f2ac59480137f4bb5633d35f282b6711239d0cd2d487fab75c597d74f` |
| System contract document | `7528a690fea301fe8284310c952a22c7f66a4a02939df74415d3b6a4ad7d0ead` |
| Qualification record | `10e065b11f96c6e5cb82dce73a389f44a5f2ff3df240133e59193d228699adf8` |

### Implemented workflow

`prepare-adjudication` verifies the four frozen authorities, both finalized
coder streams, first-pass hashes, complete 12-clip progress, correction
schemas, frame maps, source provenance, blinding fields, and authority hashes.
It applies append-only corrections in memory, writes deterministic refined
views, uses maximum-cardinality/minimum-total-distance one-to-one matching at
the frozen plus-or-minus-0.250-second tolerance, and emits a prefilled
adjudication worklist whose rows remain pending human review. It never fills a
resolved value or human attestation.

`create-contract` exclusively creates a read-only JSON contract containing
every manual input and authority SHA-256. `build` refuses an existing output,
uses a verified direct-child staging directory, rejects path escape, and
requires every refined event to appear in exactly one final adjudication. It
rejects pending/unresolved states, stale snapshots, malformed corrections,
false agreement labels, duplicate resolved hard-cut boundaries, invalid frame
times, automation exposure, authority or input drift, and inconsistent fade
pairs. A successful atomic build writes two refined views, all adjudicated
dispositions, only resolved manual hard cuts, one count row for each of the 12
clips including zeros, fade-pair output, and a hash manifest. All outputs are
made read-only before the staging directory receives its final name.

The refined view preserves each raw event's transition type and adjudication
status even after a correction. Consequently, a raw `single_frame_blend`
cannot bypass joint adjudication by being corrected to `hard_cut` during the
per-coder pass. Any adjudication involving that raw history must be resolved
and use one of the exact substantive prefixes
`artifact_adjacent_frame_cut:`,
`genuine_one_frame_optical_transition:`, or
`reclassified_after_joint_review:`. Only the first permits a final hard cut.
The raw row is never edited.

### Development findings and reruns

The first 19-test development run produced 17 passes and two failures. One
test supplied an ordinary reason where the intentionally strict single-frame-
blend rule required an artifact prefix. The fixture was corrected. The other
revealed that a resolved gradual midpoint is derived and need not equal a
decoded-frame timestamp. The system now requires point and one-blend events to
map to one eligible decoded frame, while a gradual midpoint must remain in the
half-open interval and within the frozen tolerance of a coder-observed
midpoint. The rerun passed 19/19.

Preparation, matcher, correction addition/deletion, and read-only tests raised
the suite to 24/24. Raw blend-history retention, duplicate-final-boundary
rejection, and false-agreement rejection raised it to 26/26. The final
dedicated result was **26 passed in 2.91 seconds**. Python compilation passed.

A complete study-workflow run under the sandbox account produced 134 passes
and one permission failure when the sandbox account attempted to read the
Samuel-protected correction-10 inventory. This was the previously documented
account boundary, not a code failure. The authoritative gate was therefore
run as `DESKTOP-OL7MNUO\Samuel` with:

`.\.analysis\cmat-test-venv\Scripts\python.exe -m pytest
.\.analysis\study_workflow\tests --basetemp
.\tmp\pytest_study_workflow_adjudicated_final_20260822 -p no:cacheprovider -q`

The result was **137 passed in 49.78 seconds**, exit code 0. The exact final
pytest directory was resolved as a direct child of project `tmp`, removed as
Samuel, and verified absent.

An earlier cleanup command attempted to set an `IsReadOnly` property on both
files and directories; PowerShell reported that the property was unavailable
for directory objects. `Remove-Item` nevertheless removed every exact listed
disposable development directory, and a separate enumeration returned no
matching directory. No study input or output was targeted by that command.

### Qualification and scope

The qualification record is
`.analysis/study_workflow/qualification/WAVE1_ADJUDICATED_REFERENCE_SYSTEM_QUALIFICATION_method-provenance_recipe-v1_2026-08-22_correction-01.json`
(SHA-256
`10e065b11f96c6e5cb82dce73a389f44a5f2ff3df240133e59193d228699adf8`).
Its scoped decisions are GO for adjudication preparation after both coders
finalize and GO for a real reference build only after complete blind
adjudication. A build before complete adjudication is NO-GO. This record does
not authorize detector calibration.

All test events, corrections, adjudications, contracts, and reference outputs
were synthetic and disposable. No authoritative coding session started; no
real manual event, completion, adjudication, reference event, or per-clip count
was created. Automated results were not exposed. The detector was not tuned,
Season One was not rerun, Season Two outputs were unchanged, and finalists
were not exported.

### Correction-11 inventory and post-inventory gate

`STUDY_FILE_INVENTORY.md` was advanced to the new correction-11 filename
before generation. The new dated generator,
`.analysis/study_workflow/tools/generate_study_file_inventory_method-provenance_recipe-v1_2026-08-22_correction-03.py`,
compiled and created only new correction-11 targets. Running it as
`DESKTOP-OL7MNUO\Samuel` produced 341 rows. Researcher-account verification
confirmed the tool, test, system contract, and qualification rows and their
exact release hashes. The inventory SHA-256 is
`a146cb33fdf3358062637f518fe8ca403bad3855d442a7eb8b75fa6425a8954f`;
the detached-checksum-file SHA-256 is
`1649dc9c2f4052fd391b00810eca15a2b54ec117b6c9638c3dda8584e9684b6d`.
The checksum file records the inventory hash and the already-final
`STUDY_FILE_INVENTORY.md` hash
`d2efcc79775f9f45fe219b7ad230666cde29023efb3a539ed130d5e017c6c0e8`.

A second generator invocation returned
`FileExistsError: Refusing to replace correction-11 inventory artifacts` with
exit code 1. A sandbox-account attempt to compute before/after hashes around
that refusal could not read the Samuel-protected inventory files; its displayed
`unchanged=True` comparisons were comparisons of null values and are not used
as evidence. A subsequent researcher-account hash check reproduced both exact
hashes above, establishing that the refusal left the files unchanged.

The complete study-workflow suite was then rerun as
`DESKTOP-OL7MNUO\Samuel` against the correction-11 pointer and detached
checksums. The post-inventory result was **137 passed in 48.78 seconds**, exit
code 0. Its dedicated pytest directory was resolved as a direct child of
project `tmp`, removed, and verified absent.

This final log section necessarily follows the point-in-time correction-11
inventory and therefore is not represented by the log-file hash inside that
CSV. It changes no frozen release artifact or study result.

## 2026-08-23 — W1C010 excluded from initial plot-scene analysis

W1C010 was identified during blind manual review as including end credits.
The initial tool fine-tuning analysis is restricted to plot scenes, so W1C010
is excluded from that analysis. It will not contribute manual event counts,
calibration targets, detector-accuracy estimates, threshold selection, or
aggregate summaries. No replacement clip will be selected at this stage.

Accordingly, the initial analysis denominator is **11 of the 12 originally
selected Wave 1 clips**. This is a deliberate content-scope exclusion, not
missing data, coder attrition, or a change to the frozen source worklist. The
original 12-clip worklist and any raw audit/progress records remain unchanged
for provenance. The machine-readable decision record is
`.analysis/study_workflow/wave_1_manual/wave1_initial_analysis_exclusions_method-provenance_recipe-v1_2026-08-23.json`.

## 2026-08-23 — SB01 eligible-clip first pass complete; pre-analysis gate

SB01 completed all 11 clips eligible for the initial plot-scene analysis:
W1C001–W1C009 and W1C011–W1C012. The raw stream contains 94 events. After the
documented W1C010 exclusion, 93 events are in scope: 90 hard cuts, two wipes,
and one dissolve. The included stream has no duplicate event IDs, uncommitted
transactions, out-of-range times, uncertainty flags, or failed blinding
attestations. The provisional single-coder hard-cut summary is 90 total, mean
8.182 per 30-second clip, median 8, sample SD 3.281, and range 2–15.

These numbers are manual-only readiness descriptors, not an adjudicated
reference or detector-performance analysis. Calibration remains gated because
the qualified finalizer still expects all 12 frozen worklist rows, SB01 is not
immutably finalized, MIA01's independent stream is absent, and reliability
comparison plus joint adjudication have not occurred. Automated output remains
sealed. The detailed readiness record is
`.analysis/study_workflow/wave_1_manual/WAVE1_PREANALYSIS_READINESS_method-manual_recipe-v1_2026-08-23.md`.

## 2026-08-23 — Correction-03 Wave 1 analysis-scope authority

`STUDY_WAVE1_ANALYSIS_SCOPE_method-manual-vs-automated_recipe-v1_2026-08-23_correction-03.md`
was created as the authoritative post-coding scope correction. The frozen
correction-02 manual and calibration plans and correction-01 adjudicated-
reference system were not edited, preserving their hashes and existing coding
provenance.

Correction-03 defines the exact 11 eligible blind IDs, applies the same mask to
manual and automated data before event matching or metric calculation,
requires an 11-row adjudicated per-clip reference, excludes every W1C010 event
and count from reliability/calibration quantities, prohibits representing the
excluded clip as a zero-count observation, and requires reports to state
`n=11 of 12 originally selected clips`, end-credit contamination, plot-scene
scope, and no replacement. The two-coder, blinding, reliability, adjudication,
and single permitted calibration requirements remain unchanged.

This Markdown authority documents the methodological change; real comparison
output remains blocked until the finalization, adjudicated-reference, and
calibration software enforce the exact exclusion and pass qualification.

## 2026-08-23 — Researcher revision to single-coder Wave 1 analysis

The researcher explicitly determined that MIA01 does not need to code the Wave
1 clips and directed revision of the plan. The new governing authority is
`STUDY_WAVE1_SINGLE_CODER_ANALYSIS_PLAN_method-manual-vs-automated_recipe-v1_2026-08-23_correction-04.md`.

Correction-04 designates SB01 as the sole manual coder, removes MIA01 coding,
inter-coder reliability, and joint adjudication as Wave 1 prerequisites, and
defines the append-only-corrected and finalized SB01 stream as a single-coder
manual reference. It retains the exact 11-clip scope and W1C010 exclusion,
requires identical manual and automated masks, preserves the frozen matching
tolerances and one-calibration restriction, and mandates explicit disclosure
that the reference has no independent reliability estimate or consensus
adjudication.

Earlier correction-02 and correction-03 authorities remain unchanged as
superseded provenance. Automated results remain sealed until exclusion-aware
single-coder finalization/reference/calibration software is implemented and
tested and SB01 review/corrections are complete.

## 2026-08-23 — Wave 1 correction-04 single-coder calibration completed

The correction-04 runner finalized an 11-row SB01 reference containing 90
manual hard cuts. It verified the exact eligible ID set, W1C010 exclusion,
normal-speed completion attestations, source/worklist identity, unique event
IDs, matching audit intents and commits, automation blinding, and absence of
included uncertainty or single-frame-blend cases. The finalized reference is
`.analysis/study_workflow/wave_1_manual/finalized_reference_wave1_method-single-coder-SB01_recipe-v1_2026-08-23_correction-04/`.

The one permitted calibration then ran all seven frozen ContentDetector
thresholds against the exact 11 source-master intervals. W1C010 appeared in no
manual or automated metric table. Threshold 27 reproduced every frozen
Version 1 per-clip count after the detector was given post-roll for a real cut
0.054 seconds before W1C007's interval end; results remained filtered to the
unchanged half-open intervals. Two failed technical attempts and their reasons
are retained in the adjacent attempts log; neither produced metric output.

The frozen lexicographic rule selected **`CD_T27_V1` (threshold 27.0)** for
Version 2. Against 90 SB01 cuts, it detected 97 cuts. At the primary ±0.250-
second tolerance: TP=88, FP=9, FN=2, precision=0.907216, recall=0.977778, and
F1=0.941176. Pearson's r across 11 paired clip counts was 0.971308; exact-count
agreement was 6/11; mean absolute count error was 0.636364 cuts per clip; and
signed mean error was +0.636364. At the prespecified ±1.000-second sensitivity
tolerance: TP=90, FP=7, FN=0, precision=0.927835, recall=1.000000, and
F1=0.962567.

Threshold 33 ranked second (primary F1=0.938547) and threshold 30 ranked third
(F1=0.934783); therefore no tie-break altered the primary F1 decision. The
full immutable-input/provenance manifest, seven-setting summary, 77 per-clip
rows, 689 automated events, and all primary/sensitivity matched and unmatched
events are in
`.analysis/study_workflow/wave_1_analysis/calibration_wave1_method-single-coder-vs-automated_recipe-v1_2026-08-23_correction-04/`.

Interpretation is limited to agreement with the single SB01-coded reference;
there is no independent inter-coder reliability estimate or consensus
adjudication. Version 2 still requires a distinct citation and content hash
even though calibration retained the Version 1 threshold.

Final verification passed the correction-04 runner's five dedicated tests,
confirmed all five manifest-listed result hashes, found zero W1C010 rows across
the result CSVs, confirmed seven setting summaries and 77 setting-by-clip rows,
and found exactly one selected setting (`CD_T27_V1`). The final result-manifest
SHA-256 is
`8a757646244b94fc3593bb665bd80b06d814746492264d1d7b109815fc164c4e`.

## 2026-08-23 — Version 1 retained; no Version 2

The researcher determined that no Version 2 is needed because the comparison
selected the unchanged Version 1 threshold. The governing interpretation is
`STUDY_VERSION1_MANUAL_COMPARISON_DECISION_method-manual-vs-automated_recipe-v1_2026-08-23_correction-05.md`.

The seven-threshold exercise is now described as an evaluation and confirmation
of Version 1 against SB01 hand coding, not as creation of a newly calibrated
model. Version 1 remains unchanged and authoritative. The complete threshold
table, count metrics, and boundary metrics remain preserved, with a concise
reader-facing summary at
`.analysis/study_workflow/wave_1_analysis/calibration_wave1_method-single-coder-vs-automated_recipe-v1_2026-08-23_correction-04/VERSION1_EVALUATION_RESULTS_correction-05.md`.

The defensible claim is limited: threshold 27 performed best among the seven
prespecified thresholds on the 11 included Wave 1 clips, with r=0.971 and
primary boundary F1=0.941, so the study retained Version 1 unchanged. This is
not a claim of universal optimality, error-free ground truth, or independent
inter-coder reliability.

## 2026-08-23 — CUTS_2 low-member stimulus replaced (correction-06)

The researcher directed that the participant stimulus set be corrected. Clip A2
(W1C010, S01 E04 at 00:11:51) contains the inter-story title card — roughly six
seconds of story, a black gap, about five seconds of static credit text, then
the opening of the second story. Correction-03 had excluded it from the
calibration analysis while explicitly preserving the 12-row selection, so it
remained slated for participant viewing. It is the low-cut member of the pair
that isolates cut rate, so its low count of 4 cuts per minute is produced partly
by a motionless card rather than by slow plot pacing.

The governing document is
`STUDY_CUTS2_STIMULUS_REPLACEMENT_DECISION_method-automated-with-visual-review_recipe-v1_2026-08-23_correction-06.md`.

Nothing was tuned. The detector, threshold 27.0, the selection rule, its control
penalty and all constraints are unchanged, and Version 1 remains authoritative
under correction-05. The closed correction-04 single-coder calibration is
untouched and stays on its frozen 11-clip mask. The other eleven stimuli, their
media files and their measurements are unchanged. The frozen `selected_clips.csv`
was not edited; a new twelve-row selection record was written instead.

The frozen selection rule was applied unchanged and returned 492 eligible
candidates; the replaced pair scored 0.9492. Ranked candidates 1 (0.9189) and 2
(0.8898) both sat at 00:11:51 — the same structural position as the clip being
replaced — and the researcher confirmed both as non-plot content on visual
review. Candidate 3, S01 E28 "The Elephant Upstairs; Being Hundley" at
00:04:21–00:04:51, score 0.8497, was confirmed as continuous plot content and
adopted. It is the highest-scoring candidate passing content review.

A structural limitation was identified and is now recorded: the windowing rule
trims the first 51 s and last 38 s of each episode but nothing mid-episode, so
in these two-story episodes the mid-episode title card enters the candidate
pool — roughly 2–5% of the 1,320 windows. Because a static card suppresses the
cut count, such windows are systematically over-represented among low-cut
candidates. Low-cut selections from this pool must be screened visually; score
alone is insufficient.

The replacement was exported with the same encoder settings as the existing
eleven files and re-measured under the frozen configuration: source window 8.0
cuts/min, motion 0.0718, audio 0.03612; exported file 8.0 cuts/min, motion
0.0694, audio 0.03608. Cut count is identical between source and export. The
resulting CUTS_2 pair is 8.0 vs 26.0 cuts/min with motion differing by 0.0012
and audio by 0.00069 — control matching as tight as the pair replaced. The
target contrast narrows from 4 vs 26 to 8 vs 26; the surviving contrast compares
two plot scenes rather than a plot scene against a title card.

No manual data was lost, because W1C010 was already outside the coded set. The
replacement clip has no manual cut count. Any count later produced for it is a
descriptive stimulus property only, is necessarily post-hoc and non-blind
because the automated result is already known, and must not enter the closed
correction-04 comparison.

Artifacts are under
`.analysis/study_workflow/stimulus_replacement/cuts2_low_replacement_method-automated-with-visual-review_recipe-v1_2026-08-23_correction-06/`
with detached checksums. The exported stimulus SHA-256 is
`500972cfa38384b4a833338780140aa4295490b23fb58b58fc3afaa30c386b60`. The search
tool is
`.analysis/study_workflow/tools/find_cuts2_replacement_method-automated_recipe-v1_2026-08-23_correction-06.py`
and was verified to reproduce its ranked output byte-identically on re-run.

Outstanding: the participant-facing set is now defined by the correction-06
selection record rather than by the frozen snapshot; any downstream tool that
reads `selected_clips.csv` directly must be pointed at the new record before use.

## 2026-08-23 — Correction-12 inventory for the stimulus replacement

The file inventory was regenerated to cover the correction-06 artifacts. The
generator is
`.analysis/study_workflow/tools/generate_study_file_inventory_method-provenance_recipe-v1_2026-08-23_correction-04.py`,
which chains from the preserved correction-03 generator and refuses to run if
its own targets already exist. Correction-11 and every earlier inventory were
not overwritten.

379 rows. Inventory SHA-256
`1f2f21229e9d4184a7072065be92003f8db1257b9686b9f20e613e87160b5567`; detached
checksums SHA-256
`7dd3686732b688ca8a35ce3a323c90195530acc264049536e65158e91c9ee840`. Ten rows
carry `correction_06_stimulus_replacement`: the five-file replacement package,
the search tool, this generator, the correction-06 decision document, and the
two study documents written alongside it. The package's own detached checksums
were verified file by file after generation.

`STUDY_FILE_INVENTORY.md` now points at correction-12 and its status line reads
CORRECTION-06 STIMULUS-REPLACEMENT RELEASE. It was updated before generation so
that the hash recorded for it in the detached checksum file is the current one.

## 2026-08-23 — Correction-07 coding package prepared (not yet coded)

A hand-coding package was prepared for the correction-06 replacement stimulus so
that the CUTS_2 pair carries a manual hard-cut count on both members. Its high
member already has one from Wave 1; the low member does not, and CUTS_2 is the
pair whose manipulation is cut count itself.

The package is at
`.analysis/study_workflow/stimulus_replacement/cuts2_low_replacement_method-automated-with-visual-review_recipe-v1_2026-08-23_correction-06/coding_package_method-manual-nonblind_recipe-v1_2026-08-23_correction-07/`
and contains the coding contract, a one-row worklist, an empty events CSV using
the correction-02 54-field schema, a 720-entry frame map, the constant row
prefill values, and detached checksums. Definitions come from the unchanged
correction-02 codebook, SHA-256
`b46bdaab419d1e33138d2bf3a6e98a5b6bf80f7fa97fcf311c2c18b905906f90`, and the
boundary rule is unchanged.

The coding is explicitly NOT BLIND — the automated result for this clip is
already known — and is EXCLUDED from the closed correction-04 calibration. Every
event row carries `automation_blind_confirmed = FALSE` and
`automated_values_viewed_before_lock = TRUE`. It is single-coder, with no
reliability estimate and no adjudication, and is a descriptive stimulus property
only.

BLOCKER RECORDED. The qualified correction-02 blind coding system cannot serve
this clip. It verifies frozen hashes for the Wave 1 worklist, blind manifest,
checksums, codebook, coding plan, calibration plan and HTML interface, and
requires exactly twelve blind rows ordered 1 through 12; a single non-blind clip
fails that contract by construction. The tool was NOT modified, because
loosening it would break the qualification that makes the existing Wave 1
records trustworthy. Two routes are documented in the coding contract: commission
a separate correction-07 tool with its own tests and qualification, or code
directly into the events CSV against the written contract. The choice is the
researcher's and must be logged.

No coding has been performed. The events CSV contains only its header row.

## 2026-08-23 — Correction-07 route 2 chosen; coding viewer built

The researcher chose route 2: code directly into the events CSV against the
written contract, rather than commissioning a qualified single-clip coding tool.
The choice is recorded here as the contract requires.

A disposable viewer was built to support it:
`.analysis/study_workflow/tools/single_clip_coding_viewer_method-manual-nonblind_recipe-v1_2026-08-23_correction-07.html`,
SHA-256 `dd19eb900b6ca575740569e1effc75fcf0c606c070581489972539039287d169`.

It embeds the 720-entry frame map, offers exactly the eight frozen
`transition_type` values from the correction-02 codebook and no others, refuses
frame 0 and any event outside 0.000–30.000 s per the boundary rule, requires
both endpoints for gradual transitions and derives the midpoint rather than
accepting a hand-entered one, and treats only `hard_cut` as counting toward the
manual hard-cut total. It reads the media locally in the browser, uploads
nothing, and neither computes nor displays any automated detection.

It is UNQUALIFIED — no regression suite and no qualification record — which is
what route 2 accepts and why the count it supports is descriptive only. Its
logic was exercised before use: frame 0 refused under the boundary rule, hard
cut counted, dissolve excluded from the hard-cut total, derived midpoint exact
to 1e-6, and the per-minute rate correct for a thirty-second clip.

The coding contract was updated to record the route and the viewer hash, and the
package checksums were refreshed. NO CODING HAS BEEN PERFORMED: the events CSV
still contains only its header row. The count does not exist until SB01 produces
it.

Outstanding, in order: SB01 codes the clip; the events CSV is written from those
observations and hashed; a completion entry is appended here; and the file
inventory is regenerated once at the end to cover the correction-06 package, the
correction-07 package, the viewer and the completed coding.

## 2026-08-23 — Correction-07 coding complete

SB01 coded the correction-06 replacement stimulus on 2026-08-23, session
`C7-SB01-20260823-001`, via route 2 using the disposable single-clip viewer.

**Result: 5 events — 4 hard cuts and 1 dissolve. Manual hard-cut count 4, or
8.0 per minute over the thirty-second clip.**

Hard cuts at clip-relative 21.438, 24.650, 26.985 and 28.987 s; a dissolve
spanning frames 365–389 (15.224–16.225 s) with a derived midpoint of 15.724 s.
The dissolve is not a hard cut under the codebook and is not counted as one.

The events file is
`.../coding_package_method-manual-nonblind_recipe-v1_2026-08-23_correction-07/coding_events_method-manual-nonblind_recipe-v1_2026-08-23_correction-07.csv`,
5 rows across the 54-field correction-02 schema, SHA-256
`e3110e5c9276ba5cd93d9c818283a671e39d2b4b6827d68990b04a57c158e62b`. Package
checksums were refreshed and the contract status set to CODED AND COMPLETE.

VALIDATION BEFORE WRITING. Every event was checked against the frame map and the
codebook: all frame indices greater than zero and inside the 720-frame map; all
event times strictly inside 0.000–30.000 s; every clip-relative time equal to
its frame-map entry; the dissolve endpoints ordered and its midpoint derived,
not hand-entered; the hard-cut flag consistent with the transition type in every
row; events in time order. All checks passed.

MANUAL VERSUS AUTOMATED ON THIS CLIP. The automated detector at threshold 27.0
returns 4 detections on the same exported file, at 21.438, 24.650, 26.985 and
28.987 s. Matched at the primary ±0.250 s tolerance this is 4 true positives,
0 false positives and 0 false negatives, with every delta 0.000 s — agreement to
the frame. The hand-coded dissolve at 15.724 s produced no automated detection,
which is correct behaviour: dissolve detection is disabled in the frozen
configuration and the codebook does not count a dissolve as a hard cut. Both
methods therefore report 4 hard cuts, and the agreement is positional, not a
coincidence of counts.

THIS RESULT DOES NOT ENTER THE CALIBRATION. It is a descriptive stimulus
property. The correction-04 comparison remains closed on its frozen 11-clip mask
at TP=88 / FP=9 / FN=2, F1 0.9412, and is unchanged. This coding was non-blind —
the automated result was known beforehand, recorded in every row as
`automation_blind_confirmed=FALSE` and `automated_values_viewed_before_lock=TRUE`
— and single-coder, with no reliability estimate and no adjudication. It must be
reported with those qualifiers and must never be pooled with the Wave 1 figures.

The CUTS_2 pair now carries a manual hard-cut count on both members: the high
member from the Wave 1 blind coding, the low member from this descriptive pass.
The two counts were produced under different conditions and are not
interchangeable as evidence.

## 2026-08-23 — Correction-13 inventory; session close

The file inventory was regenerated once more, after the coding, so that a single
inventory covers the whole 2026-08-23 sequence. The generator is
`.analysis/study_workflow/tools/generate_study_file_inventory_method-provenance_recipe-v1_2026-08-23_correction-05.py`,
chaining from correction-04 and refusing to run if its own targets exist.
Correction-12 and every earlier inventory were preserved.

391 rows. Inventory SHA-256
`270727944bb2f4252020c303c7932de4d75d2fc0e10aa9dd39bbf855241e4d41`; detached
checksums SHA-256
`da6045acde072870d3eba3531bf03032649db983975852117efc3d50d27af4c6`. Eight rows
carry `correction_07_coding_complete`: the six-file coding package including the
coded events file, the unqualified viewer, and this generator. Every recorded
hash was verified against the file on disk after generation, with zero
mismatches.

`STUDY_FILE_INVENTORY.md` now points at correction-13 and its status line reads
CORRECTION-07 CODING-COMPLETE RELEASE. It was updated before generation so its
recorded hash is current.

KNOWN AND ACCEPTED: this log entry postdates the inventory that hashes
`STUDY_ANALYSIS_LOG.md`, so that one row is stale by construction. An entry
describing an inventory cannot be inside it. Regenerating again would only move
the same problem forward one step.

## 2026-08-29 — Study Runner correction-06 pilot package

The researcher specified that the recruited child age range will be 8–12.
For the software pilot package, the adult prompt therefore uses: **“How fast
do you think this video would feel to a child between 8 and 12 years old?”**

`build_study_runner_package.py` assembled a `status=pilot` package beside the
standalone Study Runner executable. It consumes the correction-06 twelve-row
selection authority, uses the correction-06 replacement media for Clip A2,
and resolves the other eleven clip IDs through the frozen correction-02 coding
media manifest rather than assuming that blind IDs follow selection-row order.
Every copied MP4 is verified against its source and recorded by SHA-256.

Two software-pilot orders (`PILOT-A`, `PILOT-B`) are explicit permutations of
all twelve clips and place no analytical pair members consecutively. They are
pilot orders only, not the final approved counterbalancing plan. The package
is not an IRB-approved data-collection release. Its purpose is interface,
playback, comprehension, timing, and logging evaluation before the remaining
methodological decisions and approvals are frozen.

## 2026-08-31 — Participant design changed to adult-only perceived pacing

Samuel and Mia changed the current study title to **Adult Perceptions of Pacing
in Children’s Television** and replaced the adult-prediction-plus-child design
with one adult participant group. Adults age 18 or older will watch the 12
selected clips and provide one rating after each clip in response to “How fast
did this video feel?” The current design contains no child recruitment,
parent/guardian permission, child assent, target-child-age prompt, adult
prediction of children's responses, or adult-child agreement analysis.

REASON. The additional review, safeguarding, permission/assent, scheduling, and
recruitment requirements for children threatened the study's feasibility and
timeline. Retaining only an adult prediction question was rejected because it
would measure an adult's belief about children, not children's actual
perception, and there would be no child ratings against which to evaluate its
accuracy. The adult-only study therefore asks the narrower and directly
answerable question of how measured media characteristics relate to adults' own
perceived pacing.

UNCHANGED. The 12 clips, six matched contrasts, one-program scope, cut/motion/
audio measurements, manual-coding record, calibration result, correction-06
replacement, and stimulus provenance remain unchanged. The redesign changes
participants, outcome framing, procedure, IRB materials, software flow, and
analysis—not the stimulus-selection evidence.

SOFTWARE STATUS. The Study Runner and the pilot package logged on 2026-08-29
implement the superseded adult-prediction and child flow. They are development
artifacts and must not be used for participant piloting or collection. An
adult-only package must be implemented, tested, and requalified before use.

PROVENANCE. Existing recipe identifiers, recipe filenames, manifests,
inventory rows, and frozen correction records containing the former title are
not renamed. They are hash-bound historical identifiers. The governing change
record is `STUDY_ADULT_ONLY_REDESIGN_DECISION_2026-08-31.md`; the active
participant procedure is `STUDY_PROCEDURE_ADULT_ONLY.md`.

## 2026-09-01 — Adult-only Study Runner rewrite and technical qualification

The participant runner was rebuilt around schema version 2 for **Adult
Perceptions of Pacing in Children’s Television**. The active interface has no
participant-group selector, child flow, prediction-of-children question, or
target-age wording. It confirms adult eligibility and completed consent,
alternates automatically between two fixed reverse orders, presents an
unrecorded direction-check practice item, and provides one adult
self-perception response opportunity after each of 12 clips. Normal replay is
unavailable; restart is enabled only after a playback error. Participants can
skip a rating or stop. A skip is an explicit row with no rating, and stopping
before de-identification removes that session's rating rows while retaining the
rating-free assignment needed to prevent duplicate enrollment.

The response schema now records `block_type=adult_self`,
`question_id=adult_pacing_self_v1`, clip and source identifiers, trial order,
counterbalance condition, integer rating 1–5 or an empty skipped rating,
`response_sequence=adult_self`, and completion status. Schema version 1 and a
configuration containing `target_age_wording` fail closed.

QUALIFICATION. Thirty focused tests passed across package validation, storage,
scale, and the complete participant flow. The rebuilt pilot package contains
12 checksum-verified clips under study ID
`adult-perceptions-pacing-childrens-tv-pilot-correction-06`; Order B is the
reverse of Order A. Qt Multimedia loaded and advanced playback for every clip,
reporting durations from 30.00 to 30.03 seconds. The separately staged
executable launched without early exit. Package hash:
`4d5e5d41e441de99cc236e7dc23e20ee07b4d68ef88e3bcbe75db6a8dda27def`.

LIMIT. This is a `status=pilot` technical build, not an IRB-approved collection
release. Before participant use, a researcher must complete one visible and
audible end-to-end session on the actual collection computer, verify calibrated
volume and every clip, confirm the exported data, and compare all configured
instructions, practice, and debrief wording with the final IRB-approved
materials.

## 2026-09-01 — IRB proposal/appendix submission-consistency pass

The live Google Docs proposal and appendix were synchronized with the adult-only
runner and agreed data-sharing plan. The OSF language now freezes release after
linkage deletion, completion of primary analyses, and a residual-disclosure
check; specifies an anonymized dataset, data dictionary, and analysis materials;
uses new publication IDs; and excludes original participant codes, session IDs,
timestamps, free text, assignment/operational logs, consent/scheduling records,
and copyrighted clips. Restricted OneDrive records remain subject to three-year
destruction while public anonymized OSF materials remain available indefinitely.
No compensation, gift, reimbursement, course credit, or extra credit is offered.

The exact unrecorded practice direction check is now “Which response means
neither slow nor fast?” with `3. In between` required to continue. Response time
was removed from the planned record. Per-rating completion status is now limited
to `completed` or `skipped`; complete, withdrawn, and technical-termination
states belong to the separate restricted session record. The unresolved scale
screenshot placeholder and yellow-decision notices were removed. Samuel's four
completed technical/content certifications were dated 2026-09-01. Faculty
advisor approval remains explicitly pending Dr. Chao Liu's actual review and
was not represented as granted.
