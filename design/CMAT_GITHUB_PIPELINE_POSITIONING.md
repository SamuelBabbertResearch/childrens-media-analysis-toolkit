# CMAT GitHub Pipeline-Centered Positioning

## Core change

The new pipeline concept should substantially change how CMAT is presented on GitHub. The pipeline is not merely another feature to list in the README. It should become the **organizing metaphor for how CMAT explains itself**.

Old framing:

> CMAT helps researchers sample, code, validate, and analyze children's media.

Stronger framing:

> **CMAT helps researchers design, execute, inspect, and reproduce computational analyses of children's media through a visual research pipeline.**

The GitHub page should communicate a coherent scientific workflow rather than a pile of analysis utilities.

## Hero

Recommended opening:

# Children's Media Analysis Toolkit

**From sampling frame to results.**

*A visual research workbench for transparent, reproducible analysis of children's television and video.*

**Sampling → Selection → Measurement → Validation → Results**

CMAT helps researchers turn collections of children's media into transparent, reproducible research pipelines—combining systematic sampling, automated and human measurement, validation, provenance, and research-ready outputs.

Place the strongest pipeline screenshot immediately below this introduction. The screenshot should explain the product, not merely showcase the UI.

## Your Research Method, Made Visible

CMAT organizes analysis around:

**Sampling → Selection → Measurement → Validation → Results**

Each stage represents methodological decisions contributing to what happens next. Rather than hiding analysis behind a single **Analyze** button, CMAT is designed to let researchers inspect how media were sampled, which media entered an analysis, how constructs were operationalized, which measurements were performed, whether methods were automated or human-coded, how automated methods were validated, how variables were transformed, how composites were constructed, and how results were produced.

> **Do not make automation a black box.**

The research method itself should be inspectable.

## Where Did This Number Come From?

Use this as a core public-facing idea.

Computational analysis can produce thousands of measurements, but a number is only scientifically useful if researchers can understand how it was produced.

CMAT is being designed around **measurement provenance**:

```text
Source Media
     ↓
Raw Observation
     ↓
Measurement
     ↓
Transformation
     ↓
Composite
     ↓
Result
```

Long-term example:

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

Core message:

> **CMAT should not merely produce numbers. It should help researchers understand where those numbers came from.**

## Measure Constructs, Not Just Files

Children's-media characteristics such as **pacing** are theoretical constructs—not values embedded in an MP4 file.

CMAT is being designed to help researchers explicitly operationalize constructs using observable measures.

```text
                         Transitions/min
                       ↗
Visual Pacing ────────→ Motion Intensity
                       ↘
                         Average Shot Duration
```

Where multiple scientifically defensible approaches exist, CMAT should give researchers methodological choice rather than silently defining a construct using one algorithm.

Publicly distinguish:

**Construct → Operationalization → Measure → Method → Observation → Transformation → Result**

## Multiple Measurement Methods

Explain why automated and human coding coexist:

```text
                    Transitions
                   /           \
          Automated             Human
          Detection             Coding
                   \           /
                    Validation
```

Automated measurements should be testable against human judgment or other reference methods rather than treated as inherently valid. CMAT is being designed to connect automated and human-coded measurements directly to validation workflows.

## How CMAT Thinks About Research

### Study

**Sampling → Selection → Measurement → Validation → Results**

What did the study do?

### Operationalization

**Construct → Aspect → Measure → Method**

How was the theoretical idea turned into something observable?

### Provenance

**Source → Observation → Transformation → Result**

Where did the resulting number come from?

Summary:

> **CMAT connects all three: what you studied, how you measured it, and where the resulting numbers came from.**

## Organize Features by the Pipeline

Avoid a long unordered feature checklist.

### Sampling

Build systematic samples from children's-media collections while preserving the decisions that produced them.

### Selection

Review and refine the media entering an analysis.

### Measurement

Operationalize media characteristics using automated, human-coded, or hybrid measures.

### Validation

Compare measurement approaches and evaluate automated methods against reference coding where appropriate.

### Results

Inspect and export research-ready measurements while preserving their methodological context.

The README and application should share the same information architecture.

## Intended Audience

### Built for Children's-Media Researchers

CMAT is intended for researchers in developmental psychology, communication, education, media studies, and related fields who need to systematically sample and quantify children's television and video.

Potential use cases:

- **Developmental psychology:** characterize media stimuli or children's media environments.
- **Media research:** compare characteristics across programs, platforms, seasons, genres, or other groups.
- **Educational media:** systematically examine educational and developmental characteristics.
- **Computational content analysis:** develop scalable measurements and validate automated approaches against human coding or other reference methods.

## Screenshot Strategy

Do not fill the README with screenshots of every dialog. Screenshots should tell a methodological story.

1. **Pipeline Overview** — hero image showing Sampling → Selection → Measurement → Validation → Results.
2. **Measurement** — eventually show something such as Pacing → Visual Pacing → Transitions → Automated / Human.
3. **Provenance** — eventually show a selected result being traced backward.
4. **Validation** — eventually show automated-versus-human comparison.
5. **Results** — eventually show research-ready data, figures, or exports.

Together they should tell:

**Design → Measure → Verify → Understand → Export**

rather than “here are all the screens in the application.”

## Be Precise About Development Status

**Do not advertise planned functionality as completed functionality.**

Clearly distinguish:

### Available Now
Implemented and reasonably usable features.

### In Development
Features actively being built.

### Long-Term Vision
Product and architectural goals not yet implemented.

For example, if full provenance tracing does not exist, do not say:

> CMAT provides complete measurement provenance.

Say:

> CMAT is being designed around measurement provenance, with the long-term goal of making results traceable to their source media and measurement configuration.

Candor makes the project more credible.

## Avoid Generic AI Positioning

Do not position CMAT as:

- an “AI-powered media analyzer”;
- a magical one-click analysis platform;
- a generic video-analysis application;
- a collection of unrelated AI tools.

Avoid language such as:

> Supercharge your research with AI.

Stronger identity:

> **Scientific workflow software for transparent, reproducible analysis of children's media.**

Automation and AI may implement particular measurement methods. They are not the product's identity.

## Tagline

Recommended:

# Children's Media Analysis Toolkit

## **From sampling frame to results.**

**A visual research workbench for transparent, reproducible analysis of children's television and video.**

Other useful phrases:

> **Build transparent, reproducible analyses of children's media.**

> **Reproducible content analysis for researchers studying what children watch.**

The messaging should communicate domain + workflow + philosophy.

## Suggested README Narrative

1. What is CMAT?
2. Hero pipeline screenshot
3. Why CMAT exists
4. Your research method, made visible
5. Sampling → Selection → Measurement → Validation → Results
6. Where did this number come from?
7. Constructs, measures, and methods
8. Automated + human measurement and validation
9. Research use cases
10. Current capabilities
11. In development
12. Long-term vision
13. Installation / getting started
14. Documentation
15. Contributing
16. Citation
17. License

The README should tell a coherent story before becoming technical documentation.

## GitHub and CMAT Should Teach the Same Mental Model

The application teaches:

**Sampling → Selection → Measurement → Validation → Results**

The README should teach the same structure.

The measurement system teaches:

**Construct → Measure → Method**

The documentation should teach the same distinction.

The provenance system asks:

> **Where did this number come from?**

The GitHub page should explain why that question matters.

Maintain consistency across scientific philosophy, product architecture, interaction design, terminology, documentation, GitHub presentation, and eventual papers/publications.

## The Pipeline Is Not Just a Feature

**Do not describe the pipeline as merely one feature among many.**

CMAT is not:

> Sampling tool + video analyzer + hand coding + validation + exports.

CMAT is:

> **A visual scientific workflow that connects sampling, selection, measurement, validation, and results while preserving the methodological decisions between them.**

## Final Positioning Principle

CMAT's purpose is not simply to automate children's-media analysis.

Its purpose is to help researchers make that analysis:

- systematic;
- transparent;
- inspectable;
- reproducible;
- flexible;
- scientifically defensible.

The pipeline is the visual expression of that philosophy.

> **The methodology itself becomes part of the interface.**

And therefore:

> **The pipeline should not merely be a feature advertised on the GitHub page. It should become the organizing metaphor of the GitHub page itself.**
