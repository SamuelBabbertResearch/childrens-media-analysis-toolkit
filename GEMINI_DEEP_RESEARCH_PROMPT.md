# Gemini Deep Research prompt — methodology comparison

Paste everything below the line into Google Gemini with Deep Research turned on.

---

## Your role and my background

You are a research methods tutor writing for an undergraduate psychology
student. I am not a media-science PhD and I do not know the field's jargon.

**Write the whole report in plain English.** Every time you introduce a
technical term — for example "formal features", "shot length", "LUFS",
"optical flow", "within-subjects design", "counterbalancing", "ecological
validity", "construct validity", "psychophysics", "stimulus sampling" — stop
and explain it in one or two ordinary sentences, with a concrete example,
*before* you use it again. Assume I know basic intro-psych vocabulary (mean,
correlation, sample) and nothing beyond that.

Do not simplify the *content* — I want the real state of the field, including
things that make my study look weak. Simplify only the *language*.

## What I need

I have designed a study and built the software that selects its stimuli. I want
to know how my methodology compares to how this kind of research is actually
done, so I can (a) defend my choices, (b) fix what is fixable before I collect
data, and (c) write an honest limitations section.

---

## MY STUDY — full description

### Topic and question

How adults perceive the *pace* of short clips of children's television, and how
those perceptions relate to three objectively measured properties of the clips:
cut rate, visual motion, and audio intensity.

Primary question: how are measured cut rate, visual motion, and audio intensity
associated with adults' perceived-pacing ratings?

Secondary question: within pairs of clips deliberately chosen to differ mainly
in one of those three features, does the higher-feature clip get a different
pacing rating?

The study explicitly does **not** claim anything about children's perception,
attention, arousal, development, harm, educational value, or appropriateness.
It is correlational and descriptive. Adults rate their own experience only;
they are never asked to predict how a child would respond.

### Participants and task

- 50 adult undergraduate/graduate students at a small US university.
- One session, roughly 8–12 minutes.
- Recruitment by posters and voluntary QR-code sign-up; no course credit or
  other incentive.
- Each participant watches 12 clips, each 30 seconds, once each, no replay
  (replay allowed only after a documented technical failure).
- After each clip, one question: "How fast did this video feel?" on a 5-point
  verbal scale: Very slow / Slow / In between / Fast / Very fast. No default
  option is preselected. Responses can be revised until confirmed, then locked.
- Participants can skip a rating; skips are recorded as missing, never imputed.
- Two fixed presentation orders, Order B being the exact reverse of Order A,
  alternating by enrollment order. Pair members are never presented
  consecutively, and participants are never told the pairs exist.
- An unrecorded practice item plus a direction check ("Which response means
  neither slow nor fast?") before the real trials.
- Participants never see episode titles, timecodes, measurements, or feature
  labels.
- Data collection runs in a purpose-built desktop application that verifies the
  media file hashes before the session starts.

### Stimulus design

All 12 clips come from one series, *Curious George*, Season One only (30 HD
episode files), to hold production style, characters, narrator, and format
roughly constant.

The 12 clips form six "matched pairs":

- 2 pairs contrasting cut rate (motion and audio matched as closely as possible)
- 2 pairs contrasting visual motion (cuts and audio matched)
- 2 pairs contrasting audio intensity (cuts and motion matched)

Two independent pairs per feature, so each feature contrast has a replication.
No clip appears in more than one pair. There is no repeated baseline clip. Pair
members come from different source episodes, and normally no more than two
selected clips come from any one episode.

Crucially: **these are naturally occurring clips selected to differ, not
experimentally manipulated clips.** Nothing was edited, re-cut, or re-mixed.

### The three measures

1. **Cuts per minute** — hard cuts detected automatically by PySceneDetect's
   ContentDetector at threshold 27.0, but the **hand-coded, human-verified**
   hard-cut count is authoritative for final selection and reporting. Automated
   and manual values are stored separately and never overwritten.
2. **Visual motion** — mean frame-to-frame pixel difference, with frames sampled
   uniformly at 2.0 fps.
3. **Audio intensity** — linear RMS amplitude via FFmpeg. Deliberately *not*
   called "loudness" and *not* LUFS, because linear RMS is a signal-amplitude
   measure rather than a perceptual loudness measure.

### THE CLIP FINDER — the software half of the methodology

This is the part I most want compared against existing practice. I built a
research tool (CMAT) whose "Clip Finder" screen does the stimulus selection:

- It cuts every episode into **every contiguous 30-second window**, after
  excluding the first 51 seconds and last 38 seconds of each episode (titles,
  credits, bumpers). Season One produced **1,320 eligible windows from 30
  episodes**, with zero failed files.
- It measures all three features on all 1,320 windows under one pinned
  configuration.
- It labels each window **low / middle / high** as thirds of *this candidate
  pool's own distribution* — explicitly relative to this corpus, not any
  absolute or clinical standard.
- It ranks candidate pairs by **percentile separation** rather than raw units,
  so measures on different scales are not treated as interchangeable.
- Matching priorities, in order: large separation on the target feature; close
  matching on the other two; two independent pairs per feature; 12 unique clips;
  different episodes within a pair; episode diversity; and scenes that survive
  human review.
- Every configuration choice is stored as an inspectable, versioned "recipe"
  with a content hash and a measurement fingerprint. Changing a setting
  invalidates the cached measurements rather than silently reusing them.
- The software **proposes**; two human researchers decide. Every candidate clip
  is watched in full and its cuts hand-coded under frozen rules. Clips are
  rejected for title cards, technical defects, awkward boundaries, dependence on
  outside context, distinctive dialogue/music/comedy that would overwhelm the
  intended contrast, repeated footage, or welfare concerns.
- The exported participant-facing files are **re-measured after export**, and
  their cut counts hand-verified again, so the measured stimulus is literally
  the file participants see.

### The detector-calibration plan (a validation sub-study)

One bounded calibration cycle:

1. **Wave 1:** freeze the 12 Version-1-proposed clips; hand-code true hard-cut
   timestamps and transition types *blind to the software's detections*; compare.
2. **Version 2:** make exactly one pre-documented change to the cut detector's
   settings, saved as a new recipe with a hash and a written reason. Motion and
   audio settings are untouched.
3. **Wave 2:** re-measure all 30 episodes with frozen Version 2, generate a new
   shortlist, hand-code it blind, and score *both* versions against the same new
   manual reference. No further tuning after seeing Wave 2.
4. Report Pearson's r **plus** count error and boundary-detection results,
   because correlation alone hides systematic over- or undercounting.

This is explicitly framed as calibration on a task-selected set, not a
representative validation of the detector across all content.

---

## WHAT I WANT YOU TO RESEARCH AND REPORT

Search the actual published literature — media psychology, communication
science, developmental psychology, film studies / cinemetrics, computational
media analysis, and psychophysics — and compare my methodology to it.

Cover at least these areas. For each, tell me what the field typically does,
name specific studies/authors/years, say where I match convention, where I
deviate, and whether the deviation is a defensible choice or a real weakness.

**1. Measuring "formal features" of television.**
How have researchers historically measured pacing, cuts, motion, and sound in
children's media? Start with the human-coding tradition (Huston & Wright and
colleagues; Lillard & Peterson 2011; Christakis et al. 2004; McCollum &
Bryant's pacing work) and move to computational approaches (cinemetrics, shot
length distributions, Cutting and colleagues' film statistics, modern
computer-vision pipelines). Explain what each tradition counts as "pace" and
why they disagree.

**2. Automated shot/cut detection in research.**
How do researchers actually detect cuts? How common is PySceneDetect
ContentDetector in published work, what thresholds do people use, and what
accuracy is typically achieved and reported? How does the field handle gradual
transitions (fades, dissolves, wipes) versus hard cuts? What are the standard
evaluation metrics (precision, recall, F1, boundary tolerance windows) and what
tolerances are conventional? Is my "hand-code blind, calibrate once, then audit
prospectively" approach normal, unusually rigorous, or unusually weak?

**3. Motion and audio measurement.**
Is mean frame-differencing at 2 fps a defensible motion measure, or does the
field prefer optical flow or something else? What am I likely to be missing
(camera motion vs. object motion, animation-specific issues, sampling rate)?
For audio: how bad is it that I use linear RMS instead of LUFS (ITU-R BS.1770)
or another perceptual loudness measure? Explain what those alternatives are and
what practical difference it makes for 30-second animated clips.

**4. Stimulus selection methodology.**
This is the core comparison. How do researchers usually get stimuli for studies
like mine? Contrast three approaches: (a) editing or manipulating stimuli
experimentally, (b) selecting naturally occurring clips that differ, and (c)
using full episodes or whole programs. What does the stimulus-sampling
literature (Clark's language-as-fixed-effect problem; Wells & Windschitl 1999;
Judd, Westfall & Kenny on treating stimuli as random effects) say about my
design of two clips per feature contrast? Be blunt about how serious this is.
Is there any published precedent for a *corpus-wide automated candidate search*
like my Clip Finder — in media psychology, music/audio research, vision-science
stimulus norming, or anywhere else? If this approach is essentially novel in my
field, say so and say where it has been done elsewhere.

**5. The confounding problem.**
Cuts, motion, and audio intensity are correlated in real television. Explain in
plain English what that means for my "matched pair" logic, what a matched pair
can and cannot buy me, and how other researchers have handled the same problem.
What alternative designs would isolate the features better, and what would each
cost me?

**6. The rating task itself.**
How is perceived pace, tempo, or speed usually measured in participants? Compare
my single 5-point verbal item to alternatives: longer multi-item scales,
continuous sliders, magnitude estimation, paired comparison / forced choice,
continuous-response dials, and physiological or behavioral measures. What is
known about the reliability of single-item perceptual ratings? What does the
psychophysics literature say about how people judge "fast", and how strongly
that scales with objective rates? Does presenting each clip only once, without
replay, help or hurt?

**7. Design and analysis.**
Given 50 participants × 12 clips with each participant seeing everything: what
analysis would the field expect (mixed-effects/multilevel models with crossed
random effects for participant and clip, versus repeated-measures ANOVA on
means)? Explain in plain English what "crossed random effects" means and why it
matters here. What statistical power can I realistically expect for the
within-pair contrasts, and what effect sizes are typical in comparable studies?
Is two fixed reverse orders adequate counterbalancing, or should I have used
randomization or a Latin square — and what does each protect against?

**8. Sampling and generalizability.**
One series, one season, one university's students, no incentive. How does that
compare to the samples in the published literature, and what are the specific
threats to generalizability? Also address whether a self-selected volunteer
sample from posters and QR sign-up introduces a particular bias here.

**9. Open science and reproducibility.**
How does my provenance approach — pinned recipes, content hashes, measurement
fingerprints, frozen manifests, automated and manual values preserved side by
side, re-measurement of the exported files, planned OSF deposit — compare to
normal practice in media research? Is this above, at, or below the field's
standard? Note the copyright constraint: I cannot publicly share the clips
themselves. How do other researchers handle sharing copyrighted stimuli?

**10. Where my study genuinely stands.**
Be honest and specific. Give me:

- the 5 strongest methodological features of my design, and why each is strong;
- the 5 most serious weaknesses, ranked, with how a reviewer would phrase the
  objection;
- for each weakness, whether it is fixable before data collection, fixable in
  the writeup as a limitation, or fatal to a specific claim;
- which of my stated claims are actually supported and which I should drop;
- concrete, specific suggestions — not generic advice like "increase the sample
  size".

**11. Comparable published studies.**
Find 8–15 studies that are the closest matches to what I am doing, and for each
give: full citation, the one-sentence question, how they got their stimuli, how
many stimuli and participants, how they measured the features, how they measured
perception, what they found, and what I should copy or avoid. Prefer studies I
can realistically read and cite. Flag anything paywalled or hard to obtain.

---

## Output format

- A short plain-English executive summary (under 400 words) giving the bottom
  line: is my methodology sound, and what are the two or three things that
  matter most.
- Then the numbered sections above, each with a "**What the field does**", a
  "**How mine compares**", and a "**What I should do**" part.
- A running glossary at the end: every technical term you used, with a
  one-sentence plain-English definition.
- A full reference list with DOIs or links where you can find them.
- Where the literature disagrees or the evidence is thin, say so explicitly
  rather than picking a side. Where you are inferring rather than citing, label
  it clearly as your inference.
