# Adult Prediction of Children's Perceived Media Pacing

## Version 1 manual-comparison decision — correction 05

**Document status:** AUTHORITATIVE POST-ANALYSIS INTERPRETATION  
**Decision date:** 2026-08-23  
**Automated method:** Version 1 ContentDetector, threshold 27.0  
**Manual reference:** Single-coder SB01  
**Analysis population:** 11 of 12 originally selected clips  
**Excluded clip:** W1C010; end-credit content outside plot-scene scope  
**Version 2:** Not created

## Decision

Version 1 remains the study's cut-detection method. No Version 2 detector or
recipe will be created because the prespecified seven-threshold comparison
selected Version 1's existing ContentDetector threshold of 27.0. The algorithm
and its parameters therefore remain unchanged.

The threshold exercise is interpreted as an evaluation and confirmation of
Version 1 against hand coding, not as the creation of a newly calibrated model.
Version 1 performed as well as the tested threshold-only alternatives under the
prespecified primary selection rule. This claim is limited to thresholds 18,
21, 24, 27, 30, 33, and 36 on the 11 included Wave 1 clips; it is not a claim
that threshold 27 is globally optimal for every show, corpus, or detector.

This correction supersedes only the requirements to create, cite, hash, or use
a Version 2 artifact in the correction-02 calibration plan, correction-04
single-coder plan, handover, and analysis interpretation. The Version 1 recipe,
configuration, citation, and preserved hash remain authoritative. The full
threshold comparison and raw event-matching outputs remain preserved.

## Version 1 comparison results

The manual reference contained 90 SB01 hard cuts. At the primary ±0.250-second
tolerance, Version 1 detected 97 cuts and produced TP=88, FP=9, FN=2,
precision=0.907216, recall=0.977778, and F1=0.941176. Across the 11 paired clip
counts, Pearson's r was 0.971308, exact-count agreement was 6/11, mean absolute
count error was 0.636364 cuts per 30-second clip, and signed mean error was
+0.636364. At the prespecified ±1.000-second sensitivity tolerance, F1 was
0.962567.

| Setting | Threshold | Automated cuts | r | Exact agreement | MAE | Bias | Precision | Recall | F1 | Rank |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CD_T18 | 18 | 118 | 0.814 | 1/11 | 2.545 | +2.545 | 0.729 | 0.956 | 0.827 | 7 |
| CD_T21 | 21 | 107 | 0.891 | 4/11 | 1.545 | +1.545 | 0.813 | 0.967 | 0.883 | 6 |
| CD_T24 | 24 | 104 | 0.920 | 5/11 | 1.273 | +1.273 | 0.846 | 0.978 | 0.907 | 4 |
| **CD_T27_V1** | **27** | **97** | **0.971** | **6/11** | **0.636** | **+0.636** | **0.907** | **0.978** | **0.941** | **1** |
| CD_T30 | 30 | 94 | 0.940 | 6/11 | 0.727 | +0.364 | 0.915 | 0.956 | 0.935 | 3 |
| CD_T33 | 33 | 89 | 0.941 | 6/11 | 0.636 | -0.091 | 0.944 | 0.933 | 0.939 | 2 |
| CD_T36 | 36 | 80 | 0.857 | 6/11 | 1.091 | -0.909 | 0.963 | 0.856 | 0.906 | 5 |

Threshold 27 ranked first because primary boundary F1 was the prespecified
first selection criterion. Threshold 33 produced slightly less count bias but
missed more genuine manual cuts and had a lower primary F1.

## Required reporting language

Use language substantially equivalent to:

> CMAT Version 1 used PySceneDetect ContentDetector with threshold 27.0. We
> compared automated shot-boundary detections with SB01's hand coding of 11
> plot-scene clips. The original threshold achieved r=.971 across clip counts
> and boundary-level F1=.941 at ±0.250 seconds, and it ranked first among seven
> prespecified thresholds. We therefore retained Version 1 unchanged.

Do not state that a new Version 2 was developed or that calibration improved
the algorithm. It is acceptable to state that Version 1 was checked against
hand coding and that the tested threshold comparison found no better setting.

## Limitations

The manual reference was produced by one coder and has no independent
inter-coder reliability estimate or consensus adjudication. The comparison
estimates agreement with SB01's coded reference, not error-free ground truth.
The 11 clips came from one show and were selected through the study workflow,
so the results do not establish universal performance across children's media.
