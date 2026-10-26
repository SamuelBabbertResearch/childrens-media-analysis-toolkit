# Stanford STORM prompts — background research for the pacing study

## First, what STORM is and is not

STORM is not the same kind of tool as Gemini Deep Research, and giving it the
same prompt would waste it.

**What it does:** you give it a *topic*. It researches that topic from the open
web, asks itself questions from several different perspectives, builds an
outline, and writes a long, Wikipedia-style referenced article about it.

**What it will not do:** critique your study. It cannot take a long private
description of your methodology and tell you where you deviate from the field.
It has no interest in your Clip Finder specifically, and if you paste your study
description in as the "topic", it will produce a vague, badly grounded article,
because there is nothing on the web about your study to retrieve.

**So use it for the opposite half of the job.** Gemini Deep Research is your
*evaluator* — it holds your design and compares it to the field. STORM is your
*background reading generator* — it gives you a referenced survey of each area
your study touches, which is exactly what you need for a literature review and
an introduction section, and exactly what you cannot write yet because you do
not know the field's landmarks.

**Practical notes:**

- One topic per run. Do not combine them. STORM writes better on a tight topic
  than a broad one, and you want seven separate reference lists, not one.
- The hosted version at `storm.genie.stanford.edu` asks for the topic and,
  optionally, the purpose of your writing. Use both fields — the purpose field
  is what steers the level and the emphasis. If your version only takes a topic,
  paste the topic line alone.
- Treat every citation as unverified until you open it. STORM retrieves from the
  open web, so it will mix peer-reviewed papers with blog posts, course notes,
  and tool documentation. Check every reference before it goes near your paper.
- If you have access to **Co-STORM** (the conversational mode), run the flagship
  topic there instead and use the follow-up questions at the end of this file to
  steer it.

---

## RUN 1 — Flagship. Do this one first.

### Topic

```text
Automated measurement of pacing and formal features in children's television research
```

### Purpose

```text
I am an undergraduate psychology student writing the literature review for a
study on how adults perceive the pace of short clips of children's television.
I need to understand how researchers have measured the pace of television
programmes, from the early hand-coding tradition in developmental psychology
through to modern automated computer-vision methods. Please cover what
"formal features" means in this literature and where the term comes from; how
pacing has been operationally defined and why different researchers define it
differently; the shift from human coders to automated shot-boundary detection;
and the disagreements about whether these measures capture the same underlying
construct. Please explain technical terms in plain English as you introduce
them, because I am not a media scientist. Include specific studies, authors and
dates so I can follow up on the primary sources.
```

---

## RUN 2 — The cut-detection method itself

### Topic

```text
Shot boundary detection methods and their accuracy evaluation
```

### Purpose

```text
I use PySceneDetect's ContentDetector to find hard cuts in animated television
episodes, and I hand-code a sample of clips to check its accuracy. I need to
understand the field I have wandered into: how shot boundary detection
algorithms work, the difference between detecting hard cuts and detecting
gradual transitions such as fades and dissolves, how detection accuracy is
conventionally evaluated (precision, recall, F1, and the tolerance window used
when matching a detected boundary to a hand-coded one), what accuracy levels are
considered good, and what the standard benchmark datasets are. I also want to
know the known failure cases, especially for animation rather than live action.
Please explain the technical terms in plain English. I am a psychology student,
not a computer scientist.
```

---

## RUN 3 — The part of your design a reviewer will attack

### Topic

```text
Stimulus sampling and the fixed-effects fallacy in psychology experiments
```

### Purpose

```text
My experiment uses twelve video clips as stimuli, arranged into six pairs, with
two pairs contrasting each of three properties. Fifty participants rate every
clip. I have been warned that treating a small number of stimuli as if they were
fixed rather than sampled is a known statistical problem. I need to understand
this properly: what the language-as-fixed-effect problem is and where it came
from, why generalising from a handful of stimuli to a whole category is risky,
what "treating stimuli as random effects" means and how it is done in practice,
and what the recommended designs and analyses are. Please explain this in plain
English with concrete examples rather than equations where possible, and name
the key papers so I can cite them.
```

---

## RUN 4 — How people judge speed

### Topic

```text
Perception of tempo and speed in audiovisual media
```

### Purpose

```text
I am asking adults to watch thirty-second video clips and rate how fast each one
felt, on a five-point scale from "very slow" to "very fast". I need background on
how the perception of speed, tempo and pace has been studied: what is known
about how people judge the speed of things they watch and hear, how editing rate,
visual motion and sound intensity each contribute to a felt sense of pace,
whether these judgements track objective rates closely or compress at the
extremes, and how researchers have measured subjective tempo — rating scales,
sliders, magnitude estimation, forced-choice comparison, and continuous response
methods. Please cover both the psychophysics and the media-research traditions,
explain the terms in plain English, and note where the two literatures disagree.
```

---

## RUN 5 — The audio measure you are exposed on

### Topic

```text
Loudness measurement standards in audio: RMS, LUFS and perceptual loudness
```

### Purpose

```text
My study measures the audio of video clips using linear RMS amplitude, and I
deliberately call this "audio intensity" rather than "loudness" because I
understand RMS is a measure of signal amplitude and not of how loud something
sounds to a person. I need to understand exactly how defensible that position is:
what RMS actually measures, what the LUFS standard (ITU-R BS.1770) does
differently and why it was created, what loudness normalisation in broadcasting
involves, and in what situations RMS and a perceptual loudness measure would rank
two pieces of audio differently. I am comparing thirty-second clips of the same
animated series to each other, not measuring absolute loudness, so I especially
want to know whether that use case makes the difference matter more or less.
Please explain in plain English for someone with no audio engineering training.
```

---

## RUN 6 — Computational film analysis, for precedent

### Topic

```text
Cinemetrics and the statistical analysis of film style
```

### Purpose

```text
I am building a corpus of measurements across an entire season of a children's
television series — every shot boundary, motion level and audio level across
thirty episodes — and using it to find clips with particular properties. I want
to know whether there is an established tradition of doing this, what it is
called, and what it has found. Please cover the history of measuring average
shot length and shot length distributions, the cinemetrics movement, statistical
work on how editing patterns in film have changed over time, and modern
computational approaches to analysing film style at scale. I want to know what
kinds of claims this tradition makes, what its methods are, and what its critics
say. Explain the terms in plain English and name specific researchers and
datasets.
```

---

## RUN 7 — Reproducibility and the copyright problem

### Topic

```text
Reproducibility and data sharing for copyrighted stimuli in media research
```

### Purpose

```text
My study uses clips from a commercial children's television series, so I cannot
publicly share the stimuli themselves, but I want the work to be reproducible. I
record the exact software settings, content hashes of the media files, and a
frozen manifest of which clips were used and where they came from, and I plan to
deposit materials on the Open Science Framework. I want to know what normal
practice is in media and communication research: how researchers share stimulus
sets they do not own, what a materials deposit usually contains, whether
timecode-and-checksum references are an accepted substitute for the media, how
preregistration works for this kind of study, and what the reproducibility
situation in media research currently looks like. Please explain the open-science
terminology in plain English.
```

---

## If you are using Co-STORM

Run the flagship topic, then steer with these. They are the questions your study
actually turns on, and they are worth asking directly rather than hoping the
outline covers them.

1. When researchers select naturally occurring clips that already differ on a
   feature, rather than editing clips to create the difference, what can they
   claim and what can they not claim?
2. Are cut rate, visual motion and audio intensity correlated with each other in
   real television? By how much, and has anyone measured it?
3. Has anyone built an automated search across a whole corpus to find candidate
   stimuli matched on some features and separated on another? What is that
   approach called, and in which fields is it used?
4. What is the smallest number of stimuli per condition that reviewers in media
   psychology will accept, and what do they require in exchange?
5. How do researchers decide how long a video clip should be, and what is known
   about whether thirty seconds is enough for a stable impression to form?
6. What effect sizes are typical when comparing perceived-pace ratings between
   two clips that differ in editing rate?
7. Where hand coding and automated coding of the same footage disagree, which is
   treated as the reference, and how is the disagreement usually reported?

---

## What to do with the output

Do not cite STORM. Do not cite an article it wrote. The article is a map, not a
source — its value is that it tells you which papers exist and roughly what they
say, so you know what to go and read. Every claim that reaches your paper should
come from a primary source you have opened yourself.

The most useful thing to extract from each run is the reference list. Pull the
citations that look genuinely relevant, find the real papers through the
university library, and read those.
