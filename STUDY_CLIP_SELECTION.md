# Selecting 30-second study clips with CMAT

For the research purpose and the substantive criteria used to accept or reject
stimuli, see [STUDY_AIMS_AND_STIMULUS_CRITERIA.md](STUDY_AIMS_AND_STIMULUS_CRITERIA.md).

**Participant-design update (2026-08-31):** the study now recruits adults only
and measures their own perceived pacing. This does not change the frozen
stimulus extraction, measurement, or matching workflow below. Any former-title
recipe name is retained as a legacy provenance identifier and must not be
renamed in place.

This workflow screens a season for the Option 3.5 replicated-feature design.
It measures contiguous 30-second windows, labels each window relative to the
measured candidate pool, and proposes two independent matched contrasts for
each primary measure:

- cuts per minute, with motion and audio intensity matched as closely as possible;
- visual motion, with cuts and audio intensity matched as closely as possible;
- audio intensity, with cuts and motion matched as closely as possible.

The output is a stimulus-selection aid, not an automatic final decision.
Researchers must review the proposed scenes for credits, title sequences,
dialogue/content differences, repeated scenes, narrative context, and anything
else CMAT does not measure.

The settled role of automation and human coding is:

> CMAT reproducibly screened a large video corpus and identified promising
> stimulus candidates. Automated cut detection was calibrated using hand-coded
> candidate clips, then audited on newly selected clips. Final stimulus
> selection used manually verified cut counts alongside automated motion and
> audio-intensity measurements.

Season One HD is the only authoritative stimulus pool. Season Two was measured
as an exploratory feasibility check but is excluded because it provided
negligible matching improvement once cross-season pairs were prohibited, while
adding narrator and season-level context. Do not merge the two candidate tables.

## Two-wave cut-calibration workflow

The workflow permits exactly one show- and task-specific cut calibration:

1. Preserve the existing Version 1 manifest, recipe, candidate table, proposed
   pairs, and 12 proposed clips as the **Wave 1 calibration set**.
2. Hand-code true hard-cut timestamps and transition types in those exact
   30-second windows without viewing CMAT's detections or values. Preserve coder
   identity, coding rules, clip boundaries, notes, and any adjudication.
3. Compare Version 1 automated cuts with the Wave 1 manual reference. Pearson's
   `r` may be included, but also retain count error and boundary-detection
   results so systematic overcounting or undercounting remains visible.
4. Apply one pre-documented cut-detector calibration. Preserve Version 1 and
   save a new Version 2 recipe with a reason, citation, and content hash. Do not
   change motion, its shared sampling method/rate, or audio intensity.
5. Freeze Version 2, remeasure the full Season One HD pool, and generate a new
   **Wave 2 prospective audit set**. Wave 1 clips may not be used to calculate
   Wave 2 audit performance.
6. Manually code the new Wave 2 shortlist while blind to both versions. Compare
   both Version 1 and Version 2 against the same Wave 2 manual reference. Do not
   tune again after viewing Wave 2 manual coding.
7. Select the final pairs from defensible hand-coded Wave 1 and Wave 2
   candidates. Manual cuts are authoritative wherever cuts are a target or
   control; the frozen automated motion and linear RMS measurements remain
   authoritative for those dimensions.

This is a stimulus-search calibration and prospective workflow audit, not a
representative validation of every Season One scene or a validation of CMAT as
a whole.

## Full-season command

This first version is a source-tree CLI workflow rather than a button in the
desktop interface. From a CMAT development environment with the project
requirements installed, run:

```powershell
python cli.py study-clips "Shows\Curious George Full Season One HD" `
  --recipe "Adult Prediction of Children's Perceived Media Pacing - Feature Extraction" `
  --exclude-first 51 --exclude-last 38
```

This is the study's finalized episode-range rule: omit the first 51 seconds and
the last 38 seconds of every episode before constructing 30-second candidate
windows.

The named Version 1 recipe is stored with this project under
`.analysis/recipes/`. It pins the raw-analysis choices that create the three
study dimensions:

- hard cuts: PySceneDetect ContentDetector, threshold `27.0`;
- motion: frame differencing with uniform sampling at `2.0 fps`; and
- audio intensity: FFmpeg linear RMS.

CMAT copies the recipe citation and a complete snapshot into `manifest.json`.
It also derives the measurement cache fingerprint from the recipe's pinned
settings. A recipe change therefore cannot silently reuse measurements made
under incompatible detector or sampling parameters.

Preserve Version 1 unchanged. After Wave 1 manual coding and after freezing the
tuning grid and selection rule, open CMAT's **Recipes** screen, duplicate the
Version 1 recipe, change only the intended cut-detector settings in
**Measurement settings**, use **Re-pin** on the cut binding, and save Version 2
with a written reason. Motion's pinned parameters include the shared frame-
sampling method and rate and must remain unchanged; audio must also remain
unchanged. Version 2 must be frozen before Wave 2 and may not be revised from
Wave 2 results.

The clip-selection workflow uses the three bound raw measures separately. It
does not use the recipe's transforms, weights, or composite score.

The excluded ranges are not decoded by cut detection, motion sampling, or
audio extraction. Candidate timecodes remain absolute episode timecodes, so a
row beginning at `00:01:00.000` still points directly to the source episode.
The exclusion settings are part of the cache fingerprint and run manifest;
changing either value automatically invalidates incompatible episode results.

The default output folder is:

```text
.analysis/study_clips/Curious George Full Season One HD/
```

The run is resumable. Each completed source episode has a fingerprinted file in
`episode_measurements/`. Re-running the command retains valid episode results
and measures only missing, changed, or stale sources. Use `--fresh` only when a
deliberate complete rerun is required.

For a one-episode pilot:

```powershell
python cli.py study-clips "Shows\Curious George Full Season One HD" `
  --recipe "Adult Prediction of Children's Perceived Media Pacing - Feature Extraction" `
  --exclude-first 51 --exclude-last 38 --max-files 1
```

## Two ways in

The command below is one route; the **Clip Finder** in the Qt build is the
other, and both call the same `run_candidate_pool` with the same arguments and
write the same run folder. Use whichever suits the moment — the finder can open
a run the command produced, and the command can extend a run the finder
started, because both resume from the same fingerprinted per-episode cache.

The finder is reached from the **Pipeline** tab: single-click a Selection node,
then **Find Clips…** at the top-right of the inspector. It adds searching that
the command has no equivalent for — filter the measured pool by cuts per
minute, motion, audio, relative level and episode name, then export the chosen
windows with a JSON record of the query beside them. It does **not** cover the
Option 3.5 matched-pair proposal; that remains command-only, and
`matched_pairs.csv` is still produced by the pass itself.

Nothing in this document's review, freeze or provenance requirements changes
according to which route measured the pool.

## Outputs

- `candidates.csv` - every full 30-second window, source timecodes, three raw
  measures, percentiles, and relative feature profile.
- `pair_candidates.csv` - the top alternative low/high matches for each target
  measure, retained so the researcher can reject a scene and choose the next
  defensible candidate.
- `matched_pairs.csv` - the proposed six analytical pairs.
- `selected_clips.csv` - the twelve unique proposed clips, labeled with the
  Option 3.5 names (`Clip A1`, `Clip B1`, `Clip C1-L`, and so on).
- `study_clip_tables.md` - automatically generated clip inventory and matched-
  pair tables containing source filenames, absolute episode time spans, roles,
  what each rating contrast helps test, and full-pool versus selected-clip
  highest/lowest values for cuts, motion, and audio intensity. This is written
  whenever a complete 12-clip set is available.
- `manifest.json` - source inventory, exact measurement configuration and
  fingerprint, pool thresholds, scoring rule, timestamps, and limitations.
- `failures.csv` - unreadable or failed source files, if any.

The current files contain automated measurements only. Manual cut results must
be stored in a separate provenance-bearing overlay keyed by `clip_id`, with at
least the manual count, event-level coding source, coder, codebook version,
adjudication state, and notes. Do not edit `candidates.csv` to replace automated
values. The current `study-clips` implementation does not yet ingest this
overlay or rerank candidates using manual cuts; that support must be added
before final constrained selection.

To regenerate the tables later without reanalyzing video, run:

```powershell
python generate_study_clip_tables.py
```

`High` and `low` are relative to this candidate pool. CMAT uses the top and
bottom thirds of the measured distributions, preserving ties at the thresholds.
The matching score rewards separation on the target measure and penalizes
percentile differences on the other two measures. It does not prove that the
target measure is the only meaningful difference between two natural scenes.

## Review, final selection, export, and freeze

For both waves, review `matched_pairs.csv`, the source timecodes, and a frozen
set of plausible alternatives from `pair_candidates.csv`. Human cut coding is
required for every clip considered for the final set, not only the clips that
eventually win. Record every rejection or replacement reason.

After Wave 2, final selection uses this measurement hierarchy:

- **Cut pair:** manual cuts determine the target contrast; automated motion and
  linear RMS determine control matching.
- **Motion pair:** automated motion determines the target contrast; manual cuts
  and automated linear RMS determine control matching.
- **Audio pair:** automated linear RMS determines the target contrast; manual
  cuts and automated motion determine control matching.

The final selection must still contain two independent pairs per feature, 12
unique clips, different source episodes within each pair, and normally no more
than two clips from one episode. Numerical fit never overrides the human content
criteria in `STUDY_AIMS_AND_STIMULUS_CRITERIA.md`.

Once the twelve scenes are defensible, export standalone participant files with
the exact saved Version 2 recipe name:

```powershell
$finalRecipe = "<exact saved Version 2 recipe name>"

python cli.py study-clips "Shows\Curious George Full Season One HD" `
  --recipe $finalRecipe `
  --exclude-first 51 --exclude-last 38 --export-selected
```

CMAT re-encodes only the selected twelve windows, then re-measures those exact
participant-facing MP4 files. The final automated values are written to
`finalist_measurements.csv`; per-file provenance is written under
`finalist_measurements/`. Use these post-export values in the study manifest
because transcoding can change a measurement slightly. Manually verify hard
cuts in the exact exported files as well, applying the frozen rule that a cut at
the first frame is not experienced as a transition within the standalone clip.

Before collecting participant data, freeze and retain:

1. the twelve exported MP4 files;
2. Version 1 and Version 2 recipes, citations, hashes, manifests, candidate
   tables, and comparison outputs;
3. the Wave 1 and Wave 2 manual coding, coder provenance, adjudication records,
   and automated-versus-manual comparison results;
4. the tuning grid, frozen selection rule, chosen parameter, and written reason;
5. the manual-cut overlay and complete finalist acceptance/rejection log;
6. `finalist_measurements.csv`, its per-file JSON records, and final manual cut
   verification; and
7. the CMAT version/configuration and final participant clip-order manifest.

## HD versus SD

Use the HD files for the final run when participants will see HD files. This
keeps stimulus selection and final measurement tied to the same masters. An SD
copy can be useful for an early speed test only if it contains the same edits
and audio mix. Rankings from SD are provisional: resolution and transcoding can
change cut detection, sampled motion, and linear RMS. Any scenes screened in SD
must be exported from the HD source and re-measured before they become study
stimuli.

For the local Season One folders, the complete SD set is 320x240 at 29.97 fps
and the HD set is 1280x720 at 23.976 fps. The SD source therefore presents
roughly one-tenth as many pixels per second to the video decoders. Actual speed
depends on codec and hardware, but cut detection and motion measurement should
be substantially faster; audio extraction changes little because both sources
are reduced to the same 8 kHz mono signal.

In a local 120-second benchmark of the first episode, the complete trimmed
candidate pass took 34.2 seconds from HD and 15.6 seconds from SD (about 2.2x
faster for SD). This is one machine/scene, not a guaranteed season-wide ratio.
The SD copy also has a substantially different audio gain from the HD copy, so
never combine SD and HD rows into one candidate distribution. If participants
will see HD, rerun the final selection and all reported measurements on HD.

## Measurement language

The audio measure is linear RMS and must be called **audio intensity**, not
perceptual loudness or LUFS. The clips are naturally occurring scenes, so the
matched contrasts support associational and exploratory interpretation. They do
not establish independent causal effects of cuts, motion, or sound. Final cut
values are manually verified hard-cut counts; automated Version 1 and Version 2
cut values describe the screening and calibration workflow and must be labeled
by method and recipe version.
