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
| **Can I trust this number?** | `ARCHITECTURE.md` §9 — status per tool, and the F1 qualifiers |
| What is the default for this setting? | `ARCHITECTURE.md` §10 |
| What do the tests protect? | `ARCHITECTURE.md` §11 |
| Why is it built this way? | `DECISIONS.md` |
| Why did this break before? | `LEARNINGS.md` |
| How do I know this actually works? | `LEARNINGS.md` § The shape most of these share; `CLAUDE.md` §6 |
| Which file do I edit? | `navigation.md` |
| What is authoritative vs rebuildable? | `ARCHITECTURE.md` §2 |
| Can I change this dependency? | `STACK.md` — ask first |
| What am I not allowed to do? | `CLAUDE.md` |
