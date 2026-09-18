# Methodological audit of CMAT measures

**Audit date:** 2026-09-16
**Scope:** automated and hand-coded measures exposed by the Children's Media
Analysis Toolkit (CMAT), their implementations, validation artefacts, and the
empirical literature that can support the claims made for them.
**Review type:** code-and-artefact audit with a focused primary-source check;
not a systematic review and not an independent replication.

## Executive conclusion

CMAT has an unusually strong *measurement architecture*: it records methods and
parameters, fingerprints measurement settings, separates raw measures from
recipes, distinguishes missing values from zero, and now labels most tools
honestly as deterministic, experimental, or unvalidated. Those are important
conditions for sound research.

The measures themselves are not equally mature:

- **Suitable now for carefully labelled descriptive use:** hand-coded events;
  ContentDetector-derived abrupt boundary counts and shot-duration summaries,
  with the pilot-validation qualifications below; mean HSV saturation; mean
  absolute sampled-frame difference; and linear windowed audio RMS. These are
  reproducible operational quantities, not validated measures of children's
  attention, arousal, learning, suitability, or safety.
- **Exploratory only:** TransNetV2 on this animation corpus, AdaptiveDetector,
  Farneback optical flow, the frame-similarity scene classifier, caption/Whisper
  speech measures, vocabulary and readability measures, and the whole-frame
  luminance-change event rate currently labelled “flashing.” Each is either
  unvalidated in the target domain or is currently labelled more broadly than
  its implementation warrants.
- **Not methodologically supportable as a validated construct score:** the
  shipped Formal-Feature Composite (FFC). Its six inputs are real observations,
  but the weights, reference ceilings, additive form, clamping, and missing-audio
  redistribution have no empirical derivation or external criterion validation.
  It can be used only as an explicitly researcher-authored index or sensitivity
  analysis, never as a measure of sensory load, developmental effect, quality,
  appropriateness, or safety.

The principal risk is therefore not fabricated computation. It is **construct
overreach**: names such as “motion,” “contrast,” “loudness,” “flashing,” and
“words per minute” can invite interpretations that the underlying signals do
not support. The application already contains many of the right caveats, but
several estimand and implementation mismatches still need correction.

## How the audit judged a measure

Four questions were kept separate:

1. **Computational definition:** Is the formula clear and correctly implemented?
2. **Reliability/reproducibility:** Would the same file and pinned environment
   produce the same result, and are parameters recorded?
3. **Criterion validity:** Has the output been compared with an appropriate
   independent reference, with uncertainty and a defensible sample?
4. **Construct validity:** Does evidence justify interpreting the output as the
   theoretical construct named in the interface?

“Deterministic” answers only part of question 2. It is not evidence for questions
3 or 4. A published algorithm likewise does not validate CMAT's particular
sampling rate, normalization, corpus, or interpretation.

## Measure-by-measure assessment

| Measure / method | What CMAT actually computes | Assessment | Defensible use now |
|---|---|---|---|
| Shot boundaries — PySceneDetect ContentDetector | HSV content-change boundaries at threshold 27; `cuts_per_min` and shot durations follow from those boundaries | **Provisionally sound for abrupt-boundary description; narrowly validated.** Internal pilot boundary F1 is promising but extremely small and the published run includes the optional dissolve pass. | Report as detector-specific boundaries or abrupt cuts per minute, with threshold, software version, coded windows, and pilot qualifiers. |
| Shot boundaries — AdaptiveDetector | Local-average-normalized content-change boundaries | **Exploratory.** Plausible algorithm, no CMAT criterion validation. | Method-comparison or sensitivity analysis only. |
| Shot boundaries — TransNetV2 | Neural shot boundaries including gradual transitions | **Promising but target-domain evidence is preliminary.** The external model paper supports the algorithm, not performance on children's animation. CMAT's two-window pilot is encouraging. | Report separately as TransNetV2 boundaries per minute; never mix with ContentDetector results. |
| Dissolve plateau pass | Sustained moderate ContentDetector scores | **Not fit for substantive dissolve rates.** CMAT records F1 about 0.17. | Failure analysis and method development only. |
| Mean/median shot length; shot-length CV | Summaries of detector-defined intervals | **Mathematically sound derived descriptors.** Validity is inherited entirely from the chosen boundary method. CV uses population SD (`ddof=0`), which should be stated. | Descriptive pacing/rhythm, with method and boundary conventions pinned. |
| Detected scene changes | Pre/post-boundary grayscale similarity thresholded at 0.55 | **Unvalidated and construct-poor.** Visual similarity is not scene understanding; known reverse-shot bias is acknowledged. | Exploratory diagnostic only; do not pool with hand-coded scene changes. |
| Hand-coded transitions/events | Human labels under repository codebooks | **Potentially strong measurement, currently reliability-limited.** One coder, evolving/draft codebook, whole-second quantisation, and no inter-rater reliability for the main pilot. | Report as single-coder hand coding with window and codebook version; obtain double coding before using as a reference standard. |
| Mean HSV saturation | Pixel mean of OpenCV HSV S, averaged over sampled frames | **Sound as that exact image statistic, not as perceptual salience.** Sensitive to grading, black bars, overlays, sampling, and encoding. | “Mean sampled-frame HSV saturation,” compared only under the same pipeline. |
| “Colour contrast” | Within-frame standard deviation of HSV V, averaged over frames | **Formula is reproducible; label is too broad.** HSV V is `max(R,G,B)`, not luminance, and its SD is not a perceptual contrast measure. | Rename/report as “spatial HSV-value dispersion.” |
| “Motion” — absolute difference | Mean absolute grayscale difference between consecutive sampled frames | **Sound as sampled-frame image change, not motion.** It includes cuts, camera motion, object motion, lighting change, compression noise, and sampling-gap effects. | Rename/report as “sampled-frame grayscale change.” Do not interpret as depicted movement. |
| “Motion” — Farneback | Mean optical-flow magnitude divided by an assumed 20 px and clamped to 1 | **Algorithm established; CMAT scale unsupported.** Pixel displacement is resolution- and interval-dependent; 20 px has no calibration. | Raw or physically normalized flow in a validation study; not comparable with absolute difference. |
| “Flashing” | Count of adjacent sampled frames whose whole-frame mean grayscale differs by more than 0.1 | **Not a flash detector in the broadcast/clinical sense.** It omits affected area, red-flash criteria, flash frequency/duration rules, and local flashes. Cuts can trigger it. | “Whole-frame luminance-change events per minute,” only for within-method comparison. Never safety assessment. |
| Audio RMS mean | Mean of 1-second RMS windows after mono downmix and 8 kHz resampling | **Sound as band-limited digital amplitude; not perceptual loudness.** It depends on mastering and gain and discards the final partial window for files longer than one second. | “Mean 1-s linear RMS amplitude at 8 kHz mono.” For loudness, implement LUFS/EBU R128. |
| Audio “dynamic range” | `20 log10(max one-second RMS / mean one-second RMS)` | **Reproducible but nonstandard label.** It is a peak-to-mean windowed-RMS ratio, not EBU loudness range or programme dynamic range. | Rename to the exact ratio; do not compare with LRA/DR values. |
| Caption-based WPM and speech density | Regex word count divided by summed cue display durations; summed cue duration divided by runtime | **Requires correction before inferential use.** Cue display time is not verified articulation time; overlapping cues are double-counted; bracketed cues and speaker labels count as words; repeated two-line captions may duplicate words. | Total caption tokens as a source-dependent descriptor. WPM/density only after interval-union, cleaning, and validation against timed human transcripts. |
| Whisper-based speech measures | Same formulas applied to Whisper segment text/timing | **Unvalidated in this corpus.** ASR errors, segmentation and model choice affect both numerator and denominator. | Exploratory, with model/version and a held-out word/timing error study. |
| Readability formulas | Six `textstat` formulas on cleaned caption text | **Published formulas, out-of-domain application.** They were designed for written prose/readers; grade-level interpretations are not valid for spoken dialogue. | Relative, source-matched textual descriptors only, preferably pre-specified rather than six opportunistic tests. |
| Zipf tiers / mean Zipf | `wordfreq` estimates over lemmatized NOUN/VERB/ADJ/ADV tokens; custom 4.5/3.0 tier thresholds | **Frequency estimates have an empirical basis; tiers and preprocessing are CMAT choices.** Proper-noun exclusion and lemmatization alter the estimand. | Mean frequency and tier proportions with thresholds, token policy and language stated; validate robustness to token choices. |
| AoA and concreteness | Token-weighted means for norm-covered lemmas, with coverage | **Norms are empirically grounded, target interpretation is limited.** AoA values are adult retrospective ratings for written words, not observed child acquisition. OOV exclusion can bias means. | Descriptive lexical norm summaries with coverage; no claim about the age of a viewer or what a child understands. |
| MTLD | MTLD applied to lemmatized content-word-only tokens, excluding function/proper words | **The published MTLD validation does not directly cover this modified token stream.** This is a custom lexical-diversity statistic. | Label the preprocessing in the metric name or calculate standard MTLD alongside the custom version. |
| Formal-Feature Composite (FFC) | Clamped min-max normalization of six measures followed by a weighted sum; audio weight redistributed when missing | **Not validated and not empirically derived.** Correlated inputs can double-count change; ceilings induce saturation; missing audio changes the estimand. | Researcher-authored index with full recipe and sensitivity analysis. Do not use as a primary outcome until externally validated. |

## Major methodological findings

### 1. The automated pacing methods do not all estimate the same quantity

`analyzer/constructs.py` defines `hard_cuts_per_min` as instantaneous boundaries
and says the engine's detectors “produce boundaries of this kind only.” That is
not true for TransNetV2: its purpose and CMAT's own registry both say it detects
gradual transitions, and the pilot credits it with all 8 coded dissolves. The
same stored `cuts_per_min` field therefore means approximately abrupt cuts under
ContentDetector but all predicted shot transitions under TransNetV2.

This violates the repository's own rule not to compare different quantities as
alternative methods. The defensible repair is one of:

- rename the automated measure to **detector-defined shot boundaries per minute**
  and stop pairing it with hand-coded `hard_cuts_per_min`; or
- expose distinct automated measures for abrupt cuts and all transitions, using
  only methods that actually emit the required type information.

Until repaired, a recipe must not present ContentDetector and TransNetV2 as
interchangeable methods for “hard cuts per minute.”

### 2. The validation figure is attached to a different configuration than the registry says

The repository's headline is transition-boundary F1 **0.85** (episode range
0.75–0.91), type-agnostic within ±2 s, from a preliminary single-coder pilot.
The underlying comparison artefacts are explicitly named `content-t27-diss`:
ContentDetector at 27 **plus the experimental plateau dissolve pass**. The
shipped default has dissolve detection disabled, while the registry marks
`pyscenedetect_content` itself as validated and attaches the combined figure to
it.

The number is correctly recomputed from the two stored comparison CSVs
(TP=103, FP=14, FN=21; pooled F1=0.855), but the attribution is not exact. A
fresh, versioned comparison must grade each selectable configuration exactly as
it runs:

- ContentDetector alone at 27;
- ContentDetector plus plateau pass, explicitly a two-part method;
- AdaptiveDetector;
- TransNetV2.

No status should travel from one configuration to another. The current figure
also covers only 0–300 s and 0–320 s (~10 min 20 s total), two programmes, one
coder, and whole-second marks biased about 0.55 s early. It supports a
**preliminary engineering-performance claim**, not general validity across
children's media or production styles.

### 3. Caption timing is not dialogue time as currently calculated

`speech._parse_cc()` sums every cue's `(end - start)`. It does not merge
overlapping intervals. A diagnostic SRT with cues at 0–10 s and 5–15 s in a
20-second episode produced density 1.0; the union of displayed intervals is
15 seconds, so even *caption-display density* is 0.75. The same fixture counted
`HELLO: [MUSIC]` as two spoken words because the speech path does not use the
cleaning applied by `vocab_complexity.py`.

Even after merging overlaps and removing non-speech cues, caption display time
is not automatically speaking time: captions can lead/lag speech, remain on
screen during pauses, paraphrase, omit songs, or identify sounds. The interface
should call the denominator **caption-cue time** unless validated alignment or
human timestamps justify “dialogue time.” WPM should continue to be paired with
density, but that pairing does not cure a biased denominator.

### 4. Several labels overstate their operational definitions

The following exact labels would materially reduce construct slippage:

| Current | Methodologically safer |
|---|---|
| Motion | Sampled-frame grayscale change |
| Colour contrast | Spatial HSV-value dispersion |
| Flashing | Whole-frame luminance-change events |
| Audio loudness | Linear RMS amplitude (8 kHz mono) |
| Dynamic range | Peak-to-mean 1-s RMS ratio |
| Speech time | Caption-cue time (until validated) |

Researchers can still place these measures under broader constructs in a
recipe, but the raw measure name should describe the observable quantity rather
than the hoped-for construct.

### 5. Sampling rates are requested rates, not necessarily effective rates

Frame passes use `frame_interval = round(video_fps / sample_fps)`. The effective
rate is therefore `video_fps / frame_interval`: for 24 fps material, a requested
10 fps flashing pass actually samples at 12 fps; for 25 fps it is 12.5 fps
because Python rounds 2.5 to 2. Results remain reproducible from the source and
settings, but the stored description “10 fps” is not always the executed rate.

Record the source frame rate, integer interval, and effective sampling rate in
each result. Better still, select frames by timestamps when a specified temporal
rate is itself part of the method.

### 6. The FFC changes meaning when audio is missing

Redistributing a missing audio weight maintains a numerical 0–1 range but does
not maintain the same composite. An audio-present score summarizes six inputs;
an audio-missing score summarizes five with different effective weights. They
are not measurement-invariant merely because both totals have the same bounds.

The default FFC also gives pacing and sampled-frame change 0.25 each even though
sampled-frame change includes cut boundaries. Abrupt visual change can therefore
enter twice, while the arbitrary ceilings determine when each path saturates.
Use `refuse` as the scientifically conservative default for a fixed composite,
or treat the five-input and six-input recipes as different named versions.

### 7. Language measures sit outside the status/recipe system

The six readability formulas, word-frequency tiers, AoA, concreteness, and MTLD
are visible outputs but are not first-class `Measure` entries in the registry.
Consequently their numbers do not receive the same validation-status flags or
method pinning as audiovisual measures. This is a governance gap: published
formula provenance does not remove the need to identify CMAT's tokenizer,
lemmatizer, POS filter, model version, norm coverage, and target-domain status.

The norm files are documented as optional, but `load_norms()` requires both
files before *any* vocabulary analysis runs. In this checkout `data/norms/` is
absent. That is primarily an availability/documentation defect, but it also
means the full language pipeline could not be independently executed in this
audit.

## Appraisal of the existing validation study

### What is strong

- Validation calls the shipping comparison logic rather than a parallel scorer.
- Artefacts preserve detections, manual coding, match detail, manifests, coded
  windows, parameters, and version information.
- Matching is maximum-cardinality and type-agnostic boundary scoring is kept
  separate from type classification.
- The repository preserves corrected/superseded claims and reports the
  whole-second timing limitation.
- Results reveal real method heterogeneity: the dissolve-heavy programme is
  much harder for the plateau approach than the other programme.

### What prevents a general validation claim

- Two opening windows from two programmes are a convenience/purposive sample,
  not a representative sample of eras, genres, animation techniques, frame
  rates, or production styles.
- One coder means no inter-rater reliability and no independent adjudicated
  reference standard.
- The codebook changed during coding and remained draft; no frozen version is
  attached to every row.
- Whole-second coding and the ±2 s tolerance cannot establish frame-accurate
  boundary performance.
- Range 0.75–0.91 contains only two episode estimates; it is not a confidence
  interval or population range.
- Parameter sweeps are correctly labelled resubstitution estimates, but no
  held-out corpus exists.
- No uncertainty intervals are reported. With only 124 manual events, bootstrap
  or episode-level intervals would still be wide and would not solve the
  sampling problem.

### Minimum credible next validation

1. Freeze the codebook and operational definitions before coding.
2. Draw a stratified corpus by era, production technique, genre, pacing, and
   source/frame-rate characteristics; pre-specify inclusion and windows.
3. Double-code at least a substantial random subset, report boundary agreement
   and type-specific agreement, and adjudicate a reference set.
4. Record frame-level timestamps or use a tolerance sensitivity analysis whose
   lower bound exceeds coding resolution.
5. Separate tuning and evaluation by programme, not by event, to avoid leakage.
6. Grade exact selectable configurations and report precision, recall, F1,
   count error, and error taxonomy with bootstrap confidence intervals.
7. Test measurement invariance across animation/live action, resolution,
   frame rate, caption source, and audio mastering conditions.

## Priority recommendations

### Block claims before collecting new substantive data

1. **Split or rename the pacing estimands.** Do not let TransNetV2 populate a
   field defined as hard cuts per minute.
2. **Correct validation attribution.** Grade the exact default ContentDetector
   configuration independently of the plateau pass and attach statuses at the
   configuration level.
3. **Fix caption interval arithmetic and labels.** Merge overlaps, remove
   non-speech cues consistently, and call the denominator caption-cue time until
   human-timed validation supports speech time.
4. **Keep the FFC out of confirmatory analyses.** If retained, make every paper
   report component results and a sensitivity analysis over defensible recipes.

### Improve measures before broader use

5. Rename raw measures to match their formulas; preserve the broader construct
   only in the explicit construct/recipe layer.
6. Record effective frame-sampling rates and source media characteristics.
7. Replace or supplement RMS with integrated loudness and loudness range under
   EBU R128/ITU-R BS.1770 when the construct is perceived programme loudness.
8. Treat photosensitive-flash analysis as a separate future method implementing
   the relevant area, luminance/red-flash, and temporal criteria; do not evolve
   the current event count into a safety claim by relabelling it.
9. Add language measures to the registry/recipe/status system, and provide a
   standard-token MTLD alongside any content-lemma variant.
10. Add synthetic invariance tests: identical content at different frame rates,
    resolutions, gain levels, letterboxing, subtitle overlap patterns, and
    encodes should reveal exactly which measures are expected to change.

## Empirical and technical evidence

The literature supports studying formal features and supplies several algorithms
or lexical norms. It does **not** supply CMAT's thresholds, weights, ceilings, or
causal interpretation.

- Huston, Wright, Wartella, Rice, Watkins, Campbell, and Potts (1981),
  “Communicating More than Content: Formal Features of Children's Television
  Programs,” *Journal of Communication*.
  [doi:10.1111/j.1460-2466.1981.tb00426.x](https://doi.org/10.1111/j.1460-2466.1981.tb00426.x).
  Supports formal features as objects of content analysis, not CMAT's formulas.
- Rice, Huston, and Wright (1983), “The forms of television: Effects on
  children's attention, comprehension, and social behavior.”
  [doi:10.1515/9783111641089.21](https://doi.org/10.1515/9783111641089.21).
- Lang (2000), “The Limited Capacity Model of Mediated Message Processing,”
  *Journal of Communication*.
  [doi:10.1111/j.1460-2466.2000.tb02833.x](https://doi.org/10.1111/j.1460-2466.2000.tb02833.x).
  Motivates hypotheses about processing demands; it does not validate an FFC.
- Lang, Geiger, Strickwerda, and Sumner (1993), “The Effects of Related and
  Unrelated Cuts on Television Viewers' Attention, Processing Capacity, and
  Memory,” *Communication Research*.
  [doi:10.1177/009365093020001001](https://doi.org/10.1177/009365093020001001).
  Supports distinguishing cut relationships rather than treating all cuts as
  cognitively equivalent; it does not validate grayscale scene classification.
- Soucek and Lokoc (2024), “TransNet V2: An Effective Deep Network Architecture
  for Fast Shot Transition Detection,” ACM Multimedia.
  [doi:10.1145/3664647.3685517](https://doi.org/10.1145/3664647.3685517).
  Supports the model architecture, not out-of-domain animation performance.
- Farnebäck (2003), “Two-Frame Motion Estimation Based on Polynomial Expansion.”
  [doi:10.1007/3-540-45103-x_50](https://doi.org/10.1007/3-540-45103-x_50).
  Supports optical-flow estimation, not division by 20 px or construct validity.
- ITU-R BT.1702, *Guidance for the reduction of photosensitive epileptic
  seizures caused by television*.
  [ITU publication](https://www.itu.int/rec/R-REC-BT.1702/).
  Demonstrates why whole-frame mean change is insufficient for safety analysis.
- EBU R 128, *Loudness normalisation and permitted maximum level of audio
  signals*.
  [EBU recommendation](https://tech.ebu.ch/publications/r128).
  Provides an appropriate operational standard when programme loudness is the
  construct.
- McCarthy and Jarvis (2010), “MTLD, vocd-D, and HD-D: A validation study of
  sophisticated approaches to lexical diversity assessment,” *Behavior
  Research Methods*.
  [doi:10.3758/BRM.42.2.381](https://doi.org/10.3758/BRM.42.2.381).
- Kuperman, Stadthagen-Gonzalez, and Brysbaert (2012), “Age-of-acquisition
  ratings for 30,000 English words.”
  [doi:10.3758/s13428-012-0210-4](https://doi.org/10.3758/s13428-012-0210-4).
- Brysbaert, Warriner, and Kuperman (2014), “Concreteness ratings for 40 thousand
  generally known English word lemmas.”
  [doi:10.3758/s13428-013-0403-5](https://doi.org/10.3758/s13428-013-0403-5).
- Spache (1953), “A New Readability Formula for Primary-Grade Reading
  Materials,” *The Elementary School Journal*.
  [doi:10.1086/458513](https://doi.org/10.1086/458513).
  Its population and task are reading written material, not listening to
  audiovisual dialogue.
- Lillard and Peterson (2011), “The Immediate Impact of Different Types of
  Television on Young Children's Executive Function,” *Pediatrics*.
  [doi:10.1542/peds.2010-1919](https://doi.org/10.1542/peds.2010-1919).
  This programme comparison supplies no formal-feature thresholds or FFC weights.
- Christakis, Zimmerman, DiGiuseppe, and McCarty (2004), “Early Television
  Exposure and Subsequent Attentional Problems in Children,” *Pediatrics*.
  [doi:10.1542/peds.113.4.708](https://doi.org/10.1542/peds.113.4.708).
  It measures exposure duration, not CMAT formal features, and is observational.

## Audit limitations and verification record

- Primary-source metadata and DOI identity were checked on 2026-09-16 through
  Crossref and publisher/standards records. Full-text claim extraction was not
  possible for every paywalled source; formal citation wording should be checked
  against the primary text before publication.
- The stored 2026-08-08 comparison CSVs and manifests were read directly. Their
  reported pooled ContentDetector-plus-dissolve figure recomputes to F1 0.855.
- A synthetic caption artefact demonstrated the overlap/non-speech counting
  problem in the shipping parser.
- The complete test suite could not be executed in this environment. PySide6's
  QtCore DLL failed to load under the installed Python 3.12 environment, and the
  alternate test run lacked OpenCV. This audit therefore does not certify build
  integrity. The findings above rest on code, stored artefacts, and focused
  diagnostics, not on a green suite.
- No metric implementation or cached result was changed by this audit.
