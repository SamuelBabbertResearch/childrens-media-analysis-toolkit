# Feature extraction and clip selection — flowchart

**Study:** Adult Perceptions of Pacing in Children’s Television  
**Legacy frozen recipe identifier:** `Adult Prediction of Children's Perceived Media Pacing - Feature
Extraction` v1 (`0d233950c561`), measurement fingerprint `a5714394da4d`
**Corpus:** Curious George Full Season One HD, 30 episodes → 1,320 candidate
windows → 6 matched pairs → 12 Wave 1 clips
**Written:** 2026-08-23

This diagram is descriptive: it records how the three matching features were
actually produced for Version 1. Authority for the procedure itself stays with
`STUDY_CLIP_SELECTION.md`, `STUDY_CALIBRATION_PLAN.md` and
`STUDY_WAVE1_SINGLE_CODER_ANALYSIS_PLAN_method-manual-vs-automated_recipe-v1_2026-08-23_correction-04.md`.

Nothing here is a composite. All three recipe weights are zero by design, so
cuts, motion and audio intensity stay separate matching dimensions and no
sensory-load score is calculated or interpreted.

```mermaid
flowchart TD
    SRC["Episode MP4<br/>30 files, Season One HD"]
    EXC["Trim recurring structure<br/>drop first 51 s and last 38 s"]
    WIN["Cut into contiguous 30 s windows<br/>partial final window discarded<br/>1,320 candidate clips"]

    SRC --> EXC --> WIN

    subgraph CUTS["CUTS — hard cuts per minute"]
        C0["PySceneDetect ContentDetector<br/>threshold 27.0"]
        C1["Cut timestamps for the whole<br/>measured range"]
        C2["Count cuts falling inside the window<br/>a cut on the first frame is excluded,<br/>one before the exclusive end counts"]
        C3["cut_count<br/>cuts_per_min = count / 0.5 min"]
        C0 --> C1 --> C2 --> C3
    end

    subgraph MOTION["MOTION — mean frame difference"]
        M0["Decode 2 frames per second<br/>OpenCV VideoCapture, uniform sampling"]
        M1["Convert each sampled frame to greyscale"]
        M2["Absolute difference vs previous sampled frame<br/>baseline resets at every window edge"]
        M3["Mean over all pixels, divided by 255<br/>one value per frame pair, 59 per window"]
        M4["motion_mean = average<br/>motion_peak = maximum"]
        M0 --> M1 --> M2 --> M3 --> M4
    end

    subgraph AUDIO["AUDIO INTENSITY — linear RMS"]
        A0["FFmpeg decode to 8 kHz mono PCM"]
        A1["Slice the stream into the same 30 s windows"]
        A2["RMS per short sub-window inside the clip"]
        A3["audio_rms_mean, audio_rms_peak,<br/>dynamic range in dB<br/>null when no audio track"]
        A0 --> A1 --> A2 --> A3
    end

    WIN --> C0
    WIN --> M0
    WIN --> A0

    C3 --> POOL
    M4 --> POOL
    A3 --> POOL

    POOL["candidates.csv<br/>one row per window, three raw features"]
    RANK["Rank within this pool, per feature<br/>average-rank percentile, ties kept tied"]
    LVL["Bottom / top third split<br/>cuts 14.0 and 18.0 per min<br/>motion 0.0584 and 0.0730<br/>audio 0.03775 and 0.03963"]
    PAIR["Score every low/high pairing<br/>score = target percentile gap<br/>minus 0.75 x sum of the two control gaps<br/>pair must cross episodes"]
    SEL["6 matched pairs, 2 per feature<br/>selected_clips.csv, 12 Wave 1 clips"]

    POOL --> RANK --> LVL --> PAIR --> SEL

    SEL --> REV["Human scene review<br/>pairs are screening aids, not decisions"]
    REV --> FREEZE["Version 1 frozen<br/>recipe, config and clip identities locked"]

    FREEZE --> MAN
    subgraph VAL["VALIDATION — cuts only"]
        MAN["Blind hand coding of the 11 eligible clips<br/>SB01, single coder; W1C010 excluded"]
        CMP["Compare against CD_T27_V1 output<br/>matched within +/- 0.250 s"]
        RES["TP 88, FP 9, FN 2<br/>precision 0.907, recall 0.978, F1 0.941<br/>against 90 SB01 hard cuts"]
        DEC["Threshold unchanged, so no Version 2<br/>Version 1 stays authoritative"]
        MAN --> CMP --> RES --> DEC
    end

    MOTION -.->|"no hand-coded criterion exists"| NOVAL["Motion and audio intensity<br/>are frozen, not validated"]
    AUDIO -.-> NOVAL
```

## What the diagram is claiming, and what it is not

**Cuts** is the only feature with a human comparison behind it. The F1 of 0.941
shown above is this study's own single-coder calibration at ±0.250 s on 11
clips — it is not CMAT's headline figure, which is a transition-**boundary**
F1 of 0.85 (range 0.75–0.91), matched type-agnostically within ±2 s, from a
preliminary single-coder pilot on the first ~5 minutes of two episodes. The two
numbers answer different questions on different material and must not be merged
or quoted interchangeably.

**Motion** is a deterministic signal measurement with no detection step: mean
absolute greyscale frame difference at 2 fps. It cannot separate object motion
from camera motion from a cut, and its value depends on the sampling rate,
which is why the rate is frozen. No hand-coded motion criterion exists in this
project, so it has been graded against nothing.

**Audio intensity** is linear RMS, not perceptual loudness — not LUFS, not
EBU R128. Ungraded in the same sense as motion.

**The selection is relative.** "Low" and "high" mean bottom and top third *of
these 1,320 windows*, not of children's television. The thresholds are printed
in the diagram so the comparison set is always visible.

**The CUTS_2 low member changed on 2026-08-23.** This diagram describes how the
Version 1 pool and pairs were produced, which is unchanged. But the clip filling
the CUTS_2 low slot was replaced under correction-06 because the original
contained the inter-story title card; the pair is now 8 vs 26 cuts/min rather
than 4 vs 26. The selection rule shown here is the rule that chose the
replacement too.

**The exported files were re-measured on 2026-08-23.** Motion and audio are
essentially unchanged by the transcode. Four clips lose one near-start cut each
— a boundary effect, since a standalone clip has no frame before its own first
frame — which means MOTION_1 and AUDIO_2 no longer have exactly equal cut rates
between their members on the files participants would watch.

**These are naturally occurring clips.** Nothing was manipulated, so the design
supports associational claims only. Final exported stimuli must be re-measured,
because transcoding can move the values.
