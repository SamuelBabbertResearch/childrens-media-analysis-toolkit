# CMAT — Index

Retrieval table of contents. Load what the task needs; do not load everything.

---

## Start every session here

| Read | For |
|---|---|
| [onboarding.md](onboarding.md) | what happened last session, what is next, what a cold start must know |
| [TODO.md](TODO.md) | what is ready to be done now |
| [CLAUDE.md](CLAUDE.md) | the rules — short, strict, non-negotiable |

## Before changing anything

| Read | When |
|---|---|
| [DECISIONS.md](DECISIONS.md) | before revisiting a settled choice — the reason is recorded |
| [LEARNINGS.md](LEARNINGS.md) | before debugging **and before calling work finished** — it opens with the five recurring shapes of defect on this project, and how to test for each |
| [navigation.md](navigation.md) | to find the file that owns a behaviour |

## Reference

| Document | Covers |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | the pipeline model, authoritative vs derived state, data flow, metric definitions, data conventions |
| [CEILINGS.md](CEILINGS.md) | what the normalization ceilings are, how the current values were set, and **when to revisit them** — read before quoting a composite score |
| [STACK.md](STACK.md) | frameworks, libraries, platform constraints, Qt facts that are not guessable |
| [MEASUREMENT_MODEL.md](MEASUREMENT_MODEL.md) | **the current phase** — constructs, measures, methods, recipes, versions, staleness. Partly built: **read the status line on a capability before assuming it is built.** §4.1–§4.3 built (`analyzer/constructs.py`, `analyzer/recipes.py`, the shipped composite); §4.4 and §4.7 partly; §4.5, §4.6 and §4.8–§4.10 not. The screens are `ui/recipes.py`, `ui/construct_editor.py` and the Constructs tab, which draws a recipe **and authors it** |
| [ROADMAP.md](ROADMAP.md) | positioning, priorities, and what is deliberately not being built |
| [README.md](README.md) | public-facing description |
| [design/README.md](design/README.md) | specifications and strategy notes — the pipeline north-star spec, migration strategy, UX audit, positioning. **Inputs, not authority**; never adopt a label, metric or number from them |

## Interface work

| Document | Covers |
|---|---|
| [ui/DESIGN.md](ui/DESIGN.md) | **§0 is the recipe for building a screen.** Read before touching the interface |
| `ui/reference/*.css` | the supplied mockups' stylesheets, verbatim. The source of the design — do not hand-edit |
| `ui/reference/GeminiPipelineSample.qss` | a supplied Qt Style Sheet sample of the target aesthetic. Reference only — nothing loads it, and `reference_css.py` reads `*.css` by name so never sees it |
| `ui/tokens.py` | every colour and metric. Never write a literal colour into a widget |

## Research and domain

| Document | Covers |
|---|---|
| [validation/VALIDATION_LOG.md](validation/VALIDATION_LOG.md) | **the research diary** — dated coding sessions, result corrections, codebook changes |
| [validation/CODEBOOK.md](validation/CODEBOOK.md) | transition hand-coding definitions, including the `other` subtypes |
| [validation/EVENT_CODEBOOK.md](validation/EVENT_CODEBOOK.md) | fantastical-event hand-coding definitions |
| [STUDY_AIMS_AND_STIMULUS_CRITERIA.md](STUDY_AIMS_AND_STIMULUS_CRITERIA.md) | aims, Option 3.5 stimulus structure, feature criteria, and limits on interpretation for the current pacing study |
| [STUDY_HANDOVER.md](STUDY_HANDOVER.md) | current study decisions, latest CMAT run state, commands, unresolved choices, and prioritized next steps for a new chat |
| [STUDY_ADULT_ONLY_REDESIGN_DECISION_2026-08-31.md](STUDY_ADULT_ONLY_REDESIGN_DECISION_2026-08-31.md) | why the study changed to adults only and stopped asking adults to predict children's responses |
| [STUDY_PROCEDURE_ADULT_ONLY.md](STUDY_PROCEDURE_ADULT_ONLY.md) | active adult-only procedure, one perceived-pacing rating per clip, randomized clip order, and minimum response-data structure |
| [STUDY_PROCEDURE_ADULT_AND_CHILD_PHASES.md](STUDY_PROCEDURE_ADULT_AND_CHILD_PHASES.md) | superseded adult-prediction and child-participant procedure, retained as history only |
| [STUDY_RATING_SCALE_DESIGN.md](STUDY_RATING_SCALE_DESIGN.md) | the adult participant 1-5 pace scale: the labelled ramp, design rationale, alternatives rejected, and what still needs piloting |
| [STUDY_CLIP_SELECTION.md](STUDY_CLIP_SELECTION.md) | technical CMAT workflow for measuring, matching, reviewing, exporting, and documenting the study clips — by command or through the Clip Finder, which write the same run folder |
| `validation/*.csv`, `*_manifest_*.json` | hand coding and trial manifests — authoritative data a person typed |
| `docs/wiki` | long-form documentation — **gitignored**, managed separately |

## Not in version control

| File | Why |
|---|---|
| `FOR_PAPER.txt` | paper notes. **Never commit.** Append to it whenever work produces something the paper needs |
| `user_prefs.json` | contains a local absolute path |
| `pipelines/` | personal project data |

## Where a question is answered

| Question | Document |
|---|---|
| What does this metric mean? | `ARCHITECTURE.md` §8 |
| What construct is it a measure of, and by what method? | `analyzer/constructs.py` — seven constructs, sixteen measures, methods generated from the registry. A researcher's own constructs merge into the same lookup; `MEASUREMENT_MODEL.md` §4.1 |
| How do I define a construct of my own, and operationalize it? | **Constructs tab → Constructs…** to define it, then **Edit** on that tab to bind shipped measures to it. Measures are not user-definable, by rule; `ui/construct_editor.py`, `ui/constructs_tab.py` |
| How was this operationalized, and can I cite it? | `analyzer/recipes.py` — a recipe pins its parameters and is cited as version + content hash; `MEASUREMENT_MODEL.md` §4.2 |
| **Can I trust this number?** | `ARCHITECTURE.md` §9 — status per tool, and the F1 qualifiers. **Exactly one tool has been graded against human coding**; the rest are ungraded or have no detection step to grade |
| Which build and which input produced this result? | `analyzer/version.py` — the one place CMAT says so; README — *Reproducibility and provenance* lists what every artefact records |
| Is this sweep's best F1 a performance figure? | **No.** It is a resubstitution estimate, labelled as one in the result, the manifest and the Trials row; `LEARNINGS.md` — *A grid maximum was published as a performance figure* |
| Are the age presets developmental norms? | **No.** They are illustrative configurations with no recorded derivation; `CEILINGS.md`, `DECISIONS.md` — *Age-named presets are presented as illustrative configurations* |
| What is the default for this setting? | `ARCHITECTURE.md` §10 |
| What do the tests protect? | `ARCHITECTURE.md` §11 |
| Why is it built this way? | `DECISIONS.md` |
| Why did this break before? | `LEARNINGS.md` |
| How do I know this actually works? | `LEARNINGS.md` § The shape most of these share; `CLAUDE.md` §6 |
| Which file do I edit? | `navigation.md` |
| What is authoritative vs rebuildable? | `ARCHITECTURE.md` §2 |
| Can I change this dependency? | `STACK.md` — ask first |
| What am I not allowed to do? | `CLAUDE.md` |
