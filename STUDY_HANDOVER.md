# Adult Perceptions of Pacing in Children’s Television

## Handover for the Next Chat

### 2026-08-31 authoritative adult-only participant-design update

The study now recruits **adults age 18 or older only**. Each adult watches the
12 selected *Curious George* clips and answers one question after each clip:
“How fast did this video feel?” Adults are not asked to predict how children
would respond. There is no child recruitment, parental permission, or child
assent in the active design.

Samuel and Mia made this change because the review, safeguarding, scheduling,
and recruitment requirements for child participants threatened the study's
feasibility. Keeping only an adult proxy question would not measure children's
perceptions and could not be validated without child ratings. The adult-only
design therefore asks the narrower, directly answerable question of how media
characteristics relate to adults' own pacing perceptions.

This update supersedes every later passage in this handover that describes
child participants, adult predictions of children, a target child age,
permission/assent, 24 adult responses, adult-child agreement, or a child phase.
Those passages remain as dated history only. The active authorities are:

1. [STUDY_ADULT_ONLY_REDESIGN_DECISION_2026-08-31.md](STUDY_ADULT_ONLY_REDESIGN_DECISION_2026-08-31.md)
2. [STUDY_PROCEDURE_ADULT_ONLY.md](STUDY_PROCEDURE_ADULT_ONLY.md)
3. [STUDY_AIMS_AND_STIMULUS_CRITERIA.md](STUDY_AIMS_AND_STIMULUS_CRITERIA.md)

The 2026-09-01 Study Runner rewrite and schema-version-2 package implement the
adult-only flow and refuse the superseded prediction/child schema. Thirty
focused tests passed; the staged executable launched; and Qt Multimedia loaded
and advanced all 12 checksum-verified clips. The package remains
`status=pilot`, not IRB-approved. Before participant use, complete a visible and
audible manual session on the collection computer and verify all configured
wording against the final approval. Frozen recipe names, paths, inventory rows,
and citations containing the former title remain unchanged as provenance
identifiers.

### 2026-08-23 stimulus-set correction (correction-06)

The CUTS_2 low-member stimulus was replaced. Clip A2 (W1C010, S01 E04 at
00:11:51) contains the inter-story title card and was the low-cut member of the
pair that isolates cut rate, so its low count was produced partly by a static
card. The governing document is
`STUDY_CUTS2_STIMULUS_REPLACEMENT_DECISION_method-automated-with-visual-review_recipe-v1_2026-08-23_correction-06.md`.

The replacement is S01 E28 "The Elephant Upstairs; Being Hundley" at
00:04:21-00:04:51, chosen by the unchanged frozen selection rule and confirmed
as plot content on visual review. The resulting pair is 8.0 vs 26.0 cuts/min
with control matching as tight as the pair replaced.

**The participant-facing set is now defined by the correction-06 selection
record**, not by the frozen snapshot's `selected_clips.csv`. Any tool reading
the frozen file directly must be repointed before use.

Nothing was tuned. Version 1, threshold 27.0 and the correction-04 calibration
on its 11-clip mask are all unchanged and remain authoritative.

A standing limitation was recorded: the windowing rule trims each episode's
first 51 s and last 38 s but nothing mid-episode, so mid-episode title cards
enter the candidate pool and are over-represented among low-cut candidates.
Low-cut selections must be screened visually.

Related: the twelve exported clip files were re-measured under the frozen
configuration on 2026-08-23. Motion and audio are essentially unchanged by the
transcode; four clips lose one near-start cut each, which is a boundary effect
and not transcode degradation. Two control matches that were exactly equal in
the source measurement are no longer equal on the exported files (MOTION_1 cuts
16 vs 18; AUDIO_2 cuts 14 vs 16), so the earlier claim that both motion pairs
have identical cut rates now holds for MOTION_2 only.

### 2026-08-23 governing single-coder revision

The current Wave 1 authority is
`STUDY_WAVE1_SINGLE_CODER_ANALYSIS_PLAN_method-manual-vs-automated_recipe-v1_2026-08-23_correction-04.md`.
It supersedes the earlier Wave 1 requirements for MIA01 coding, inter-coder
reliability, and joint adjudication. SB01 is the sole manual coder. All 11
eligible clips are first-pass complete; W1C010 is excluded without replacement
because it contains end credits outside the plot-scene scope.

The earlier two-coder and adjudicated-reference sections below are preserved
as dated methodological and software-qualification history, not as the current
Wave 1 analysis design. Do not wait for MIA01 and do not describe the SB01
reference as adjudicated. Before analysis, update and test the finalization and
comparison software for the exact 11-ID mask, complete SB01 self-review and
append-only corrections, and finalize the SB01 reference. Then compare that
single-coder reference with automated output and report the required
single-coder limitation.

The correction-04 single-coder comparison has now been completed. The frozen
selection rule retained `CD_T27_V1` (ContentDetector threshold 27.0). Primary
±0.250-second results were TP=88, FP=9, FN=2, precision=0.9072,
recall=0.9778, and F1=0.9412 against 90 SB01 hard cuts. Correction-05
subsequently determined that no Version 2 will be created because the detector
and parameters did not change. Version 1 remains authoritative, now supported
by the documented manual comparison. Full results are in
`.analysis/study_workflow/wave_1_analysis/calibration_wave1_method-single-coder-vs-automated_recipe-v1_2026-08-23_correction-04/`.

### 2026-08-22 adjudicated-reference system qualification update

Samuel explicitly ratified all five correction-02 methodological decisions,
including the rule that a raw `single_frame_blend` remains uncertain and
pending rather than automatically counting as a hard cut. The exact statement
is preserved in `STUDY_ANALYSIS_LOG.md`.

The downstream Wave 1 adjudicated-reference system is now implemented and
qualified on synthetic data. Its qualification record is
`.analysis/study_workflow/qualification/WAVE1_ADJUDICATED_REFERENCE_SYSTEM_QUALIFICATION_method-provenance_recipe-v1_2026-08-22_correction-01.json`
(SHA-256
`10e065b11f96c6e5cb82dce73a389f44a5f2ff3df240133e59193d228699adf8`).
The dedicated suite passed 26/26 tests, and the complete study-workflow suite
passed 137/137 as `DESKTOP-OL7MNUO\Samuel`.

The system validates both finalized coder streams, applies append-only
corrections without modifying raw rows, prepares a still-pending human
adjudication worklist, freezes a hash-bound input contract, and fails closed
unless every event is finally adjudicated exactly once. It creates deterministic
refined views, event dispositions, final manual hard-cut boundaries, 12 per-
clip counts, fade-pair results, and a provenance manifest. A raw one-frame blend
cannot enter the hard-cut reference unless joint adjudication explicitly records
`artifact_adjacent_frame_cut:` with a substantive reason. The system never reads
automated results.

No real adjudicated reference exists yet because neither coder has begun the
authoritative correction-02 session. The immediate research action remains
blind first-pass coding with the correction-02 launcher. Use the adjudicated-
reference system only after both coders finish and lock their Wave 1 records.
This qualification does not authorize detector calibration before the manual
reference is complete, verified, hashed, and frozen.

### 2026-08-22 correction-02 operational qualification update

This later update supersedes only the operational NO-GO paragraph in the
methodological update below; it does not replace or revise any settled method.
The standalone correction-02 Wave 1 blind manual-coding workflow is now
**GO for Wave 1 coding**. The signed scope and evidence are in
`.analysis/study_workflow/qualification/WAVE1_BLIND_CODING_PREUSE_QUALIFICATION_method-provenance_recipe-v1_2026-08-22_correction-02.json`
(SHA-256
`5eeab0fd8bb28bf1bd71b9f81074e993d85eb877026b11e3340619a35477bee9`).

Use only
`.analysis/study_workflow/wave_1_manual/START_WAVE1_BLIND_CODING_method-manual_recipe-v1_2026-08-22_correction-02.cmd`.
Do not use any correction-01 launcher or resume its preserved empty session.
No authoritative correction-02 coder-data directory existed at qualification,
so actual Wave 1 coding has not begun. The next research action is to read the
frozen correction-02 codebook and manual-coding plan and then start a real
first-pass session with the correction-02 launcher. Do not tune the detector,
rerun Season One, or view automated detections before first-pass coding locks.

Qualification passed 111/111 study-specific tests as
`DESKTOP-OL7MNUO\Samuel`, deep-verified all 12 clips, passed the launcher
preflight, and passed an active browser exercise in a deleted disposable
workspace. The broader repository is not claimed to be defect-free: after the
test-only VLC dependency was supplied, 631 tests passed, 14 skipped, and one
unrelated construct-cache status test remained failing. That defect does not
import into or change the standalone correction-02 Wave 1 coding workflow.

### 2026-08-22 correction-02 methodological authority update

This dated correction retains the original 2026-08-18 handover below. The
pre-correction handover SHA-256 was
`f8a2f229ecf0b92df7d61480b3eb5e7719504354a3927b98e6b9edc6c5b9f802`.

An independent adversarial pre-use audit issued **NO-GO** for the correction-01
Wave 1 blind-coding release. Samuel subsequently approved the five unresolved
methodological decisions and a primary plus-or-minus-0.250-second boundary
matching tolerance. The new frozen Markdown authorities are:

1. `validation/CODEBOOK_wave1-2_method-manual_recipe-v1_2026-08-22_correction-02.md`;
2. `STUDY_MANUAL_CODING_PLAN_wave1-2_method-manual_recipe-v1_2026-08-22_correction-02.md`;
3. `STUDY_CALIBRATION_PLAN_wave1_method-manual-vs-automated_recipe-v1-v2_2026-08-22_correction-02.md`.

For correction-02 and later work, read those three documents after the six
authoritative files in the existing reading order. The original
`validation/CODEBOOK.md`, `STUDY_MANUAL_CODING_PLAN.md`, and
`STUDY_CALIBRATION_PLAN.md` remain preserved historical evidence and are not
the authority for new coding.

The decisions now frozen are: whip-pan-masked joins remain hard cuts with a
separate flag; non-boundary graphic overlays move outside the transition table;
one confirmed blend frame receives a `single_frame_blend` uncertain category
and adjudication rather than automatic hard-cut status; gradual transitions
retain start and end frames; and fade-out/fade-in rows are paired while one
derived shot-structure transition is reported. The primary automated/manual
matcher uses plus or minus 0.250 seconds, with plus or minus 1.000 second only
as a sensitivity analysis.

**Current operational status remains NO-GO.** The correction-02 software,
worklist, blind manifest, checksums, media-manifest provenance, templates,
launcher, tests, and independent pre-use qualification do not yet exist. Do
not use the old `.cmd` launcher or resume the empty correction-01 session.

**Prepared:** August 18, 2026  
**Researchers:** Samuel and Mia, Cedarville University undergraduate psychology  
**Current design:** Adult-only perceived-pacing study using the Option 3.5
Replicated Feature stimulus design; see the 2026-08-31 update above  
**Status:** CMAT Version 1 has produced a complete 12-clip Wave 1 calibration
proposal from 30 HD Season One files. Manual cut coding, one documented
show-specific calibration, a frozen Wave 2 run, final human selection, finalist
export, piloting, faculty/methods review, and IRB approval remain.

Start the next chat with:

> Read `STUDY_HANDOVER.md` and the authoritative files it links. Continue the
> Adult Perceptions of Pacing in Children’s Television project without
> reverting the settled decisions in this handover.

## Read these files in this order

1. [This handover](STUDY_HANDOVER.md) — current decisions, state, and next steps.
2. [Adult-only study procedure](STUDY_PROCEDURE_ADULT_ONLY.md) — current adult
   participant sequence, question, scale, and response data.
3. [Study aims and stimulus criteria](STUDY_AIMS_AND_STIMULUS_CRITERIA.md) —
   research questions, stimulus rationale, interpretation limits, and success
   criteria.
4. [CMAT clip-selection workflow](STUDY_CLIP_SELECTION.md) — commands, recipe,
   output meanings, review, export, and stimulus-freeze requirements.
5. [Generated clip tables](.analysis/study_clips/Curious%20George%20Full%20Season%20One%20HD/study_clip_tables.md)
   — the current filenames, time spans, six proposed pairs, and pool extremes.
6. [Latest run manifest](.analysis/study_clips/Curious%20George%20Full%20Season%20One%20HD/manifest.json)
   — exact source inventory, recipe snapshot, parameters, thresholds, and
   measurement fingerprint.

The original Word document in Downloads is historical design input, not the
current authority. Some older variants used forced choice or two adult viewing
blocks. The Markdown files above contain the decisions made after reviewing
those variants.

## Settled study design

### Central question

Can adults accurately predict children's reported perceptions of the pace of
short *Curious George* clips?

CMAT is used to locate, characterize, and reproducibly freeze the stimuli. This
study does not claim to validate every CMAT feature or show that cuts, motion,
or sound cause perceived pacing.

### Settled role of CMAT and human coding

The study uses a bounded human-in-the-loop workflow rather than treating
automated output as final ground truth:

> CMAT reproducibly screened a large video corpus and identified promising
> stimulus candidates. Automated cut detection was calibrated using hand-coded
> candidate clips, then audited on newly selected clips. Final stimulus
> selection used manually verified cut counts alongside automated motion and
> audio-intensity measurements.

The current 12-clip Version 1 proposal is the **Wave 1 calibration set**, not a
frozen finalist set. Researchers will hand-code its true hard cuts without
consulting CMAT's detections, compare the original automated values with the
manual reference, perform one documented cut-detector calibration, and freeze a
new Version 2 recipe. Version 2 will then remeasure the complete Season One pool
and propose a new Wave 2 set. Both Version 1 and Version 2 will be compared with
the same independently hand-coded Wave 2 clips. No further tuning occurs after
Wave 2 coding is examined.

Final stimuli may be selected from any defensible hand-coded Wave 1 or Wave 2
candidate. Manual hard-cut counts are authoritative for final cut contrasts and
cut matching. The frozen automated measurements remain authoritative for motion
and audio intensity. Automated and manual cut values must both be retained; one
must never silently overwrite the other.

### Stimulus set

- 12 unique clips, each 30 seconds long.
- The clips form six hidden analytical pairs:
  - two pairs contrast cut rate while matching motion and audio intensity;
  - two pairs contrast visual motion while matching cuts and audio intensity;
  - two pairs contrast audio intensity while matching cuts and motion.
- Adults see the same 12 clips once each.
- Everyone sees both members of every pair, but pair membership and CMAT high/
  low labels are never shown to participants.
- Pair members are presented as individual clips in a randomized or
  counterbalanced order. Do not deliberately group them back-to-back; decide
  before data collection whether the ordering algorithm will prohibit adjacent
  pair members.
- Participants are **not** asked which member of a pair seemed faster. Their
  individual 1–5 ratings are compared by pair during analysis.

### Five-point pace rating

Use the same ordered response options for everyone:

1. Very slow
2. Slow
3. In between
4. Fast
5. Very fast

“Five-point Likert-type item” is acceptable shorthand, but “five-point ordered
pace-rating scale” is more precise because this is one repeated item rather
than a multi-item Likert scale.

### Phase 1: Adults

Each adult watches the 12 clips once. Immediately after each clip:

1. Display only the primary prediction question: **How fast do you think this
   video would feel to a [target-age] child?**
2. Record and lock the 1–5 prediction so it cannot be revised.
3. Replace that screen with: **How fast did this video feel to you?**
4. Record the 1–5 adult self-perception rating without displaying the prior
   answer.

Each adult produces 12 responses from 12 clip viewings: one self-perception
rating after each clip. The working session estimate is 8–12 minutes and must
be checked in piloting. No adult prediction question is included.

### Phase 2: Children — superseded history

After parent/guardian permission and age-appropriate child assent, each child
watches the same 12 clips once. After each clip ask:

> **How fast did this video feel to you?**

Each child produces 12 responses from 12 viewings. The working estimate is
8–12 minutes and must be checked in piloting.

### Analysis structure

For the initial tool fine-tuning analysis, use **11 of the 12** Wave 1 clips.
Exclude W1C010 because it includes end credits and the fine-tuning scope is
strictly plot scenes. Do not replace it at this stage. Treat this as a
documented content-scope exclusion—not missing data—and do not include W1C010
in event counts, calibration targets, accuracy estimates, threshold selection,
or aggregate summaries. Preserve the original 12-clip worklist for
provenance. The machine-readable exclusion record is
`.analysis/study_workflow/wave_1_manual/wave1_initial_analysis_exclusions_method-provenance_recipe-v1_2026-08-23.json`.
The governing revised plan is
`STUDY_WAVE1_SINGLE_CODER_ANALYSIS_PLAN_method-manual-vs-automated_recipe-v1_2026-08-23_correction-04.md`.
SB01 is the sole Wave 1 manual coder. MIA01 coding, inter-coder reliability,
and joint adjudication are no longer required. The finalized, append-only-
corrected SB01 stream is the single-coder manual reference, and every report
must disclose that it has no independent reliability estimate or consensus
adjudication. Correction-03 remains preserved as superseded history.

- **Primary:** estimate associations between measured cut rate, visual motion,
  audio intensity, and adults' own perceived-pacing ratings.
- **Secondary:** examine adult rating differences within the six matched
  feature contrasts and whether both pairs for a feature show similar patterns.
- **Exploratory:** compare adult self-ratings with their child predictions;
  examine replication across the two pairs per feature; relate ratings to
  continuous manually verified cut counts and frozen automated motion and
  audio-intensity measurements.
- Treat the 1–5 responses as ordered categories when choosing the statistical
  model; do not automatically assume equal distance between scale points.
- Naturally occurring scenes support associational and exploratory conclusions,
  not isolated causal effects of a feature.

## Current CMAT implementation

The source-tree CLI command `study-clips`:

- measures contiguous 30-second windows without first exporting hundreds of
  video clips;
- excludes the first 51 seconds and last 38 seconds of every episode at decode
  time while retaining absolute episode timecodes;
- supports `--max-files N` for a limited episode run;
- resumes from fingerprinted per-episode measurements;
- uses a saved recipe to pin the cut, motion, sampling, and audio methods;
- proposes the six matched pairs and 12 unique clips;
- generates human-readable clip tables automatically when a complete set exists;
  and
- can export and remeasure the 12 exact participant-facing MP4 files after human
  review.

### Version 1 study recipe (legacy name retained for provenance)

- ID: `r_apc_media_pacing`
- Name: `Adult Prediction of Children's Perceived Media Pacing - Feature Extraction`
- Version: `1`
- Content hash: `0d233950c561`
- Current recipe file:
  `.analysis/recipes/Adult Prediction of Childrens Perceived Media Pacing - Feature Extraction_r_apc_media_pacing.json`
- Hard cuts: PySceneDetect ContentDetector, threshold `27.0`.
- Motion: absolute frame differencing, uniformly sampled at `2.0 fps`.
- Audio intensity: FFmpeg linear RMS.
- All recipe weights are intentionally zero. The workflow uses the three raw
  measures separately and does not calculate or interpret a composite score.
- The recipe is currently marked `locked: false`. Preserve it unchanged as the
  Version 1 baseline. Do not silently edit it.
- After Wave 1 manual coding, tune only the cut-detection operationalization
  under a documented rule, duplicate/re-pin it, and save the result as a new
  Version 2 recipe with a reason and new content hash. Motion, motion sampling,
  and audio intensity remain unchanged.
- Version 2 must be frozen before the full-season Wave 2 run. Do not tune again
  after Wave 2 manual coding is viewed.

### How matching works

- “Low” and “high” are the bottom and top thirds of the measured candidate-pool
  distribution, with ties preserved at the thresholds.
- Candidate low/high clips for a pair must come from different source episodes.
- Pair score = target-feature percentile separation minus `0.75` times the sum
  of the two control-feature percentile separations.
- The selector chooses two independent pairs per feature, does not reuse a clip,
  and normally allows at most two selected clips from one source episode.
- The score is a ranking aid, not a cluster classifier, causal test, or substitute
  for human content review.

## Latest output on disk

Folder:

```text
C:\Users\Samuel\Child Development Television Index Project\.analysis\study_clips\Curious George Full Season One HD
```

The latest manifest reports:

- 30 HD Season One source files;
- 1,320 eligible 30-second candidate windows;
- six matched pairs;
- 12 selected clips;
- zero failed source files;
- the two-clips-per-source diversity guard was not relaxed;
- exclusions of 51 seconds at the start and 38 seconds at the end; and
- measurement fingerprint `a5714394da4d`.

Current high/low thresholds for the full HD candidate pool:

| Feature | Bottom-third maximum | Top-third minimum |
|---|---:|---:|
| Cuts | 14 cuts/min | 18 cuts/min |
| Motion | 0.05837 mean frame difference | 0.07300 |
| Audio intensity | 0.03775 RMS | 0.03963 RMS |

`study_clip_tables.md` contains the proposed filenames and absolute time spans.
It also includes the highest and lowest values among all 1,320 candidates and
among the 12 Wave 1 clips, plus “what the rating contrast helps test.”

The 12 Wave 1 clips have **not** been accepted or exported as finalists: no
`finalists/` folder or `finalist_measurements.csv` currently exists. Do not run
`--export-selected` until calibration, Wave 2, manual verification, and final
selection are complete.

### Season Two feasibility run and exclusion decision

Season Two was successfully measured in HD on August 18, 2026: 20 files, 880
candidate windows, no failed files, and the same Version 1 measurement
fingerprint. Its candidate distributions were similar to Season One. However,
the numerical benefit disappeared when cross-season pair members were
prohibited: the mean six-pair match score increased only from approximately
`.958` for Season One alone to `.960` for a two-season pool constrained to
same-season pairs. Equal representation of both seasons scored approximately
`.955`.

Unrestricted pooling scored better primarily by proposing cross-season pairs,
which would confound feature contrasts with narrator and other season-level
production differences. Alternating narrator voices could also introduce
sequential rating context. Season Two is therefore excluded from stimulus
selection. Retain its outputs as an exploratory feasibility record; do not mix
its candidates into the authoritative Season One pool.

## PowerShell commands

Commands must be run from the project directory, not from `C:\Users\Samuel`:

```powershell
Set-Location "C:\Users\Samuel\Child Development Television Index Project"
```

Analyze five episodes:

```powershell
python .\cli.py study-clips "Shows\Curious George Full Season One HD" `
  --recipe "Adult Prediction of Children's Perceived Media Pacing - Feature Extraction" `
  --exclude-first 51 `
  --exclude-last 38 `
  --max-files 5
```

Analyze or resume the full HD season:

```powershell
python .\cli.py study-clips "Shows\Curious George Full Season One HD" `
  --recipe "Adult Prediction of Children's Perceived Media Pacing - Feature Extraction" `
  --exclude-first 51 `
  --exclude-last 38
```

Regenerate the Markdown tables without reanalyzing video:

```powershell
python .\generate_study_clip_tables.py
```

Only after Version 2 is frozen, Wave 2 is hand-coded, and the final 12 clips are
chosen, export and remeasure the exact finalists using the exact saved Version 2
recipe name. The command below must not be run with the Version 1 recipe shown
earlier:

```powershell
$finalRecipe = "<exact saved Version 2 recipe name>"

python .\cli.py study-clips "Shows\Curious George Full Season One HD" `
  --recipe $finalRecipe `
  --exclude-first 51 `
  --exclude-last 38 `
  --export-selected
```

Do not add `--fresh` unless a deliberate complete remeasurement is required.

## HD versus SD decision

SD requires less processing. A local 120-second benchmark took 15.6 seconds for
SD and 34.2 seconds for HD, about 2.2 times faster for SD on that test. However,
the local SD copy has a substantially different audio gain, and resolution or
transcoding can change cut and motion measurements. Never mix SD and HD rows in
one candidate distribution. The current complete proposal was made from HD,
which should remain the source if participants will watch HD.

## Next actions, in order

1. **Run the retained Version 1 over all 30 Season One HD files for Wave 2.**
   Exclude the Wave 1 clips from
   the prospective Wave 2 audit set, generate new proposed pairs and reserves,
   and do not change Version 1 after viewing their manual coding.
2. **Hand-code the Wave 2 shortlist.** Compare the retained Version 1 against
   the same new manually coded clips. Report the result as a prospective
   audit of new clips selected through this workflow, not as validation of all
   Season One scenes or all CMAT uses.
3. **Make the final constrained selection.** Choose from defensible hand-coded
   Wave 1 and Wave 2 candidates. Use manual cuts with automated motion and RMS,
   preserve the same feature-separation, control-matching, episode-diversity,
   clip-uniqueness, and content-review requirements, and log every rejection or
   replacement reason.
4. **Finalize the target child wording.** `[target-age]` must become one fixed
   age that matches recruitment. The working child range is 8–12, but the exact
   adult prompt remains unresolved.
5. **Finalize presentation rules.** Freeze clip-order randomization, decide
   whether paired clips can ever be adjacent, choose the adult practice clip,
   and decide whether the turtle/rabbit imagery remains for adults.
6. **Export and verify the approved 12 clips.** Use the retained frozen Version 1 recipe,
   retain post-export motion and RMS measurements, and manually verify cuts in
   the exact exported participant-facing files because clip boundaries and
   transcoding can affect the final count.
7. **Freeze study provenance.** Retain Version 1, Wave 1 and Wave 2
   automated manifests, all manual coding and comparison outputs, tuning
   decisions, finalist MP4s and measurements, rejection log, and participant
   presentation-order manifest.
8. **Pilot both participant flows.** Verify instructions, prediction-first
   locking, scale comprehension, playback volume, randomization, breaks, timing,
   and response logging.
9. **Complete faculty, statistical, and IRB review** before recruitment or data
   collection.

## Open methodological and operational decisions

- Sample size, power justification, and final statistical model.
- Confirmatory versus exploratory analysis labels beyond those stated here.
- Exact Wave 1 tuning grid, frozen threshold-selection criterion, Wave 2
  shortlist size, manual-coding reliability plan, and comparison statistics.
- A provenance-preserving way for `study-clips` to ingest manual cut counts and
  rerank candidates without editing or overwriting `candidates.csv`.
- Visual scale presentation and whether turtle/rabbit imagery survives piloting.
- Practice item and scale-comprehension rule.
- Demographic/background questions.
- Rules for replay, missing answers, pauses, withdrawal, technical failures,
  and participant exclusion.
- Adult recruitment, compensation, privacy, retention, consent, and debriefing
  language.
- Participant-facing application implementation; the procedure document lists
  the minimum one-row-per-rating data fields.

## Important cautions for the next chat

- Do not reintroduce child recruitment or an adult prediction-of-children item.
  The current decision is 12 adult viewings with one self-perception rating
  after each clip.
- Do not introduce direct “which paired clip was faster?” trials unless Samuel
  deliberately changes the design.
- Do not show pair identities or CMAT feature labels to participants.
- Call the sound measure **audio intensity** or linear RMS, not loudness or LUFS.
- Do not call the high/low profiles clusters unless a true clustering algorithm
  is later added; they are relative feature levels and matched contrasts.
- Do not treat a high match score as evidence that natural scenes differ only
  on the target feature.
- Do not combine SD and HD measurements.
- Do not use Season Two candidates in this study. Its completed run is an
  exploratory feasibility record only.
- Do not tune the cut detector more than once. Version 1 is the preserved
  baseline; Version 2 is frozen before Wave 2; Wave 2 does not feed Version 3.
- Do not edit automated candidate CSVs to substitute manual values. Preserve
  automated and human measurements side by side with explicit provenance.
- Preserve unrelated changes in the dirty working tree. Several current study
  and measurement-model files are untracked or modified; inspect `git status`
  before editing or committing.

## Relevant implementation files

- `cli.py` — `study-clips` command and arguments.
- `analyzer/study_clips.py` — window measurement, relative profiles, matching,
  selection, cache, export, and remeasurement.
- `analyzer/recipes.py` — customizable recipe model and resolution.
- `generate_study_clip_tables.py` — generated inventory, pair, rationale, and
  pool-extremes tables.
- `tests/test_study_clips.py` — candidate workflow and CLI argument tests.
- `tests/test_study_clip_tables.py` — generated table tests.
- `tests/test_recipes.py` — recipe behavior tests.
- `validation/CODEBOOK.md` — transition definitions and blind-coding rules to
  apply to the 30-second Wave 1 and Wave 2 clips.
- A manual-cut overlay/reselection implementation is still required; the
  current `study-clips` command does not yet ingest corrected human counts.
