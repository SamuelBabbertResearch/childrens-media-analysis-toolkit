# CMAT Pipeline Interaction Model

## Status and Implementation Priority

**IMPORTANT: This is a north-star specification for the future CMAT pipeline system. Do not implement the advanced features in this document yet.**

The immediate priority is to **finish and stabilize the basic PySide6 pipeline first**:

**Sampling → Selection → Measurement → Validation → Results**

The advanced interaction and measurement concepts below should inform architectural decisions, but they must not cause premature abstraction, scope creep, or a rewrite of the current pipeline.

---

## Core Principle

The pipeline should become one of the conceptual centers of CMAT.

> **The pipeline should represent the research method itself.**

It should not merely be a visualization of tools or a decorative flowchart.

The pipeline should eventually make the path from:

**Children's Media → Measurement → Scientific Evidence**

visible, inspectable, reproducible, and understandable.

---

# The Pipeline Is the Researcher's Map

The pipeline should become CMAT's primary navigation and workflow interface, but it must **not** become a rigid wizard.

The core interaction model is:

> **The pipeline is the researcher's map.**

> **Selecting a node establishes the current research context.**

> **The workspace provides the tools needed for that context.**

> **The inspector explains and configures the selected methodological object.**

> **The pipeline changes as the researcher makes methodological decisions.**

> **The pipeline displays the current state and dependencies of the study.**

> **Researchers can move backward and forward freely rather than following a rigid wizard.**

Most importantly:

> **Researchers interact in the language of research methodology; CMAT translates those decisions into the technical pipeline underneath.**

The goal is **not visual programming**.

The goal is to make **the structure of the research visually understandable and manipulable**.

---

# Pipeline = Context, Workspace = Work, Inspector = Details

Selecting a pipeline node should tell CMAT:

> "This is the part of my research workflow I want to work on."

The rest of the application should adapt to that selection.

For example, selecting **Sampling** could focus the application on the corpus, sampling frame, sampling methods, sampled versus unsampled episodes, parameters, exclusions, and provenance.

Selecting **Measurement** could focus the application on constructs, available measures, automated and human-coded methods, configurations, progress, and outputs.

Selecting **Validation** could focus on reference coding, automated-versus-human comparisons, disagreements, reliability/agreement, and validation results.

Selecting **Results** could focus on final datasets, figures, summaries, exports, and the provenance of reported results.

The user should gradually learn:

**Pipeline = what I am working on**

**Workspace = where I work on it**

**Inspector = details and configuration for it**

---

# Do Not Make It a Wizard

CMAT should not force researchers through:

**Sampling → Next → Selection → Next → Measurement → Next → Validation → Next**

Research is iterative.

Users must be able to move freely among stages. A researcher in Results may need to inspect Measurement. A validation problem may require changing a measurement method. An unexpected episode may require returning to Sampling.

Incomplete prerequisites can produce warnings and guidance without unnecessarily preventing navigation.

CMAT should distinguish:

> "You cannot compute this yet."

from:

> "You cannot look at this yet."

The interaction should feel more like a scientific workbench or IDE than an installation wizard.

---

# The Pipeline Should Grow Through Research Decisions

Researchers should not normally construct the measurement graph by dragging low-level implementation nodes onto a blank canvas.

Instead, CMAT should ask methodological questions.

Example:

1. The researcher selects **Measurement**.
2. CMAT asks: **What do you want to measure?**
3. The researcher chooses **Pacing**.
4. The pipeline represents **Measurement → Pacing**.
5. CMAT offers possible aspects such as Visual Pacing, Auditory Pacing, Linguistic Pacing, or Custom.
6. The researcher chooses **Visual Pacing**.
7. CMAT offers measures such as Transitions, Motion Intensity, Average Shot Duration, Human-Rated Pacing, or Custom.
8. The researcher chooses **Transitions**.
9. CMAT asks how transitions should be measured: Automated Shot Detection, Human Coding, Both, or another available method.

Choosing both might create:

```text
Measurement
     ↓
   Pacing
     ↓
Visual Pacing
     ↓
Transitions
   ↙     ↘
Automated  Human
Detection  Coding
```

The researcher has not "programmed a graph."

The researcher has answered research-method questions, and CMAT has constructed a visual representation of those decisions.

---

# Context-Sensitive Workspace

Selecting a deeper measurement node should determine which tools and data CMAT emphasizes.

For example, selecting **Transitions** could make the application show:

- **Media viewer:** detected transition markers and navigation between events.
- **Data table:** transition timestamps, counts, episode-level rates, missing or failed analyses.
- **Inspector:** method, parameters, algorithm/version, units, inputs, outputs.
- **Tools:** run detector, review detections, compare methods, send cases to human coding, inspect provenance.

Selecting **Validation** could instead show:

- **Media viewer:** cases where automated and human coding disagree.
- **Data table:** validation cases and corresponding measurements.
- **Inspector:** validation configuration and reference method.
- **Tools:** reliability/agreement analysis, error inspection, and method comparison.

---

# Three Levels of Pipeline

Long term, CMAT should support three conceptual levels.

## 1. Study Pipeline

**Sampling → Selection → Measurement → Validation → Results**

Answers:

> "What are the major stages of my study?"

## 2. Measurement Pipeline

**Construct → Aspect → Measure → Method → Raw Measurement → Transformation → Composite**

Answers:

> "How did I operationalize what I wanted to study?"

## 3. Provenance / Data Lineage

**Source Media → Raw Observations → Derived Measurements → Transformations → Composite → Result**

Answers:

> **"Where did this number come from?"**

These should feel like different zoom levels of the same research process.

---

# Constructs, Measures, and Methods Must Be Distinct

CMAT should distinguish a theoretical **construct** from its **measures**, and measures from their **methods**.

For example:

**Pacing** is a construct.

Possible aspects include visual pacing, auditory pacing, and linguistic pacing.

Visual pacing might be represented by measures such as:

- transitions per minute;
- average shot duration;
- motion intensity;
- human-rated editing pace.

A measure such as transitions per minute might be obtained using:

- automated shot-boundary method A;
- automated method B;
- human coding.

CMAT should never silently imply:

> "Transitions = Algorithm X."

Instead:

> **"Transitions have been operationalized using Method X with Parameters Y."**

Researchers—not CMAT—ultimately determine which operationalization is scientifically appropriate.

CMAT should make those choices explicit, understandable, configurable, comparable, reproducible, and inspectable.

---

# Measurement Toolbox

CMAT should eventually provide at least one useful measurement tool for the major measurable aspects it claims to support, while allowing multiple implementations where scientifically defensible alternatives exist.

Possible categories include:

### Visual
Shot transitions, scene transitions, average shot duration, motion, visual change, luminance, color characteristics, faces, on-screen text, camera movement.

### Auditory
Loudness, dynamic range, speech/non-speech, music, silence, audio-event density.

### Language
Speech rate, word count, vocabulary measures, turn-taking, transcript-derived measures.

### Content
Potential future measures include prosocial behavior, aggression/violence, educational content, emotional content, character interaction, and representation.

### Temporal
Event rates, transition frequency, duration measures, temporal variability.

Measures should clearly identify whether they are **Automated**, **Human-coded**, or **Hybrid**.

---

# Preserve Raw Observations and Transformations

CMAT should preserve useful intermediate observations rather than only final values.

Example:

```text
Episode
    ↓
83 detected shot boundaries
    ↓
422 seconds analyzed
    ↓
11.8 transitions/minute
    ↓
standardization
    ↓
z = 0.63
```

Do not unnecessarily discard raw counts, timestamps, intermediate measurements, relevant confidence values, audit-worthy algorithm outputs, or transformation metadata.

Transformations such as normalization, standardization, aggregation, weighting, filtering, exclusions, direction reversal, missing-data handling, and unit conversion are part of the research method and should not be invisible.

---

# Composites

CMAT should eventually allow researchers to combine multiple measurements into theoretically meaningful composites.

```text
Transitions/min ───────┐
Motion intensity ──────┤
Audio-event density ───┼──→ Pacing Composite
Speech rate ───────────┘
```

CMAT must not silently determine how variables are combined.

Preserve included components, exclusions, weighting, normalization, directionality, aggregation method, missing-data policy, and configuration/version.

---

# Provenance: "Where Did This Number Come From?"

This should become a core CMAT principle.

A researcher should eventually be able to select a result and trace it backward:

```text
Pacing Composite = 0.73
        ↑
4 standardized measures
        ↑
Transitions = 11.8/min
        ↑
83 detected boundaries / 422 seconds
        ↑
Shot Boundary Method X
Threshold = Y
Version = Z
        ↑
Source Episode
```

Potential provenance includes source media, source identifiers, sampling method, random seed, exclusions, measurement implementation, algorithm/model/dependency version, parameters, raw observations, transformations, composite configuration, validation decisions, CMAT version, and scientifically useful timestamps.

---

# Validation Should Connect to Measurement

Validation should not merely be a final checkbox.

Example:

```text
                   TRANSITIONS
                        │
             ┌──────────┴──────────┐
             ↓                     ↓
      Automated Detection      Human Coding
             │                     │
      11.8 cuts/min            12.1 cuts/min
             │                     │
             └──────────┬──────────┘
                        ↓
                    VALIDATION
                        ↓
               Agreement / Error
```

This lets CMAT support questions such as:

> "Does this automated transition detector adequately reproduce human coding?"

---

# Pipeline Status and Dependency Awareness

The pipeline should eventually communicate project state at a glance:

```text
✓ Sampling
120 / 120 episodes
        ↓
✓ Selection
116 retained
        ↓
● Measurement
83 / 116 processed
        ↓
○ Validation
Not started
        ↓
○ Results
Waiting on measurement
```

Possible states include not configured, ready, running, partially complete, complete, warning, failed, stale, and blocked by dependency.

If an upstream methodological decision changes, CMAT should eventually explain the consequences:

```text
Transition Detector
Threshold 30 → 20
        ↓
Transition measurements are stale
        ↓
Pacing composite is stale
        ↓
Dependent results are stale
```

Do not implement full dependency invalidation prematurely, but preserve the possibility architecturally.

---

# "Why?" Should Be a First-Class Interaction

A selected node should eventually make it easy to access:

- About this step
- Why is this used?
- View method
- View inputs
- View outputs
- View provenance
- View dependencies

This should combine educational explanation with the researcher's actual project configuration.

CMAT should educate without becoming a rigid tutorial.

---

# Every Node Should Answer Five Questions

1. **What is this?** What does this measure or operation represent?
2. **Why is it here?** What construct, analysis, or research purpose does it serve?
3. **How is it measured?** What implementation, human-coding procedure, parameters, or transformation is being used?
4. **What happened?** What data were produced? Did processing succeed? Were there missing values or exclusions?
5. **Where does the output go?** Which downstream measure, transformation, composite, validation procedure, or result depends on it?

Pipeline arrows should also be meaningful: **output produced here becomes input there.**

---

# Pipeline Nodes Are Not UI Cards

Architectural non-negotiable:

> **A pipeline node must not merely be a rectangle displayed by PySide6.**

A meaningful node should eventually represent a methodological operation with defined inputs, outputs, configuration, dependencies, execution state, provenance, and relevant version information.

Desired architecture:

```text
Research / Domain Model
        ↓
Pipeline Model / Execution System
        ↓
PySide6 Visualization
```

Avoid:

```text
PySide6 Boxes
      ↓
Miscellaneous callbacks
      ↓
Research logic
```

The visual graph must not become the authoritative source of scientific state.

---

# Scientific Philosophy

CMAT should distinguish:

**Construct → Operationalization → Measure → Implementation → Observation → Transformation → Composite → Result**

A construct may have multiple operationalizations. An operationalization may use multiple measures. A measure may have multiple implementations. Automated and human implementations may coexist.

Researchers decide which operationalization is scientifically appropriate. CMAT makes that decision explicit and preserves it.

---

# Implementation Order

## Phase 1 — CURRENT PRIORITY
Finish and stabilize the **basic PySide6 study pipeline**:

**Sampling → Selection → Measurement → Validation → Results**

## Phase 2 — Interaction Foundation
Make top-level pipeline selection establish the current research context and connect cleanly to the workspace and inspector.

## Phase 3 — Domain Modeling
Carefully design constructs, aspects, measures, measurement methods, observations, transformations, and composites before building elaborate nested UI.

## Phase 4 — Measurement Pipeline
Allow Measurement to expand into a structured representation of operationalization.

## Phase 5 — Provenance
Build inspectable data lineage:

**Source → Observation → Measurement → Transformation → Result**

## Phase 6 — Validation Integration
Connect alternative measurement methods and human coding to validation.

## Phase 7 — Advanced Research Features
Only after the foundations are stable, consider measurement recipes, method comparison, pipeline versioning, dependency invalidation, stale-result detection, import/export of measurement specifications, reproducibility reports, methods-section generation, and citation support.

---

# Final Directive to Claude Code

**Finish the existing basic PySide6 pipeline before implementing the advanced features in this document.**

Treat this document as a **north-star specification**, not an instruction to immediately increase scope.

While finishing the basic pipeline:

1. Keep the implementation simple.
2. Do not prematurely generalize everything.
3. Do not build speculative abstractions without a present need.
4. Do not turn the pipeline into a generic node editor.
5. Do not turn the pipeline into a rigid wizard.
6. Do not let PySide6 visual components become the source of truth for research state.
7. Keep research/domain logic separable from presentation logic.
8. Preserve enough architectural flexibility that the future measurement system can be added cleanly.
9. Document consequential architectural decisions affecting this direction.
10. Design toward: **Pipeline = context, Workspace = work, Inspector = details.**

The long-term goal is not merely to make CMAT capable of analyzing children's media.

The goal is to make **how the media was analyzed** visible, inspectable, reproducible, scientifically defensible, and intuitive to navigate.

> **Researchers should interact in the language of research methodology; CMAT should translate those decisions into the technical pipeline underneath.**
