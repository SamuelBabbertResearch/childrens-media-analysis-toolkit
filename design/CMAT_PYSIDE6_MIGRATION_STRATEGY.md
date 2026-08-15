# CMAT Tkinter → PySide6 Migration Strategy

## Purpose

The Tkinter-to-PySide6 migration is consuming too much development time, context, and Claude Code usage.

**Do not continue treating “convert all Tkinter code to PySide6” as the objective.**

The new objective is:

> **Get CMAT to a stable PySide6 foundation with the minimum migration work necessary, then return to building the actual research product.**

PySide6 remains the intended UI framework. This document changes the **migration strategy**, not the decision to use PySide6.

---

# 1. Stop Blind Migration

Before doing more migration work, perform a **read-only migration audit**.

**Do not modify code during the audit.**

Determine:

- What Tkinter code remains?
- What PySide6 code is complete?
- Which migrated screens actually work?
- Which screens are partially migrated?
- Which business/research logic is still coupled to Tkinter?
- Which old UI features are genuinely necessary for the current CMAT MVP?
- Which old features no longer fit the current product direction?
- Which features can be deferred instead of migrated?
- Are there duplicate Tkinter and PySide6 implementations?
- What prevents us from declaring the migration “good enough” today?
- Which remaining tasks are blockers versus polish?

At the end of the audit, produce a **finite migration checklist**.

Do not respond with an open-ended recommendation to “continue migrating.” Quantify the remaining work and classify it.

Use categories:

- **BLOCKER — must migrate**
- **REBUILD — functionality matters, but old UI should not be ported literally**
- **DEFER — useful but unnecessary for migration completion**
- **DELETE — obsolete or superseded**
- **DONE — migrated and verified**

---

# 2. Treat Tkinter as a Prototype and Specification

The Tkinter application is **not sacred legacy UI** that must be reproduced screen-for-screen.

Treat it primarily as:

- evidence of existing functionality;
- a behavioral reference;
- a source of research/business logic that may need preservation;
- a prototype showing what worked and what did not.

For every remaining Tkinter component, ask:

> **If CMAT were being designed today, would we build this feature?**

If **yes**, migrate or rebuild it.

If **no**, delete/deprecate it.

If **maybe**, defer it.

Do not spend substantial effort recreating UI that the new pipeline-centered architecture will replace.

---

# 3. Prefer Rebuilding Over Literal Porting When Appropriate

A Tkinter screen does not automatically deserve a PySide6 clone.

If the functionality remains important but the interaction model is obsolete:

> **Preserve the capability, not necessarily the old interface.**

A simple temporary PySide6 interface is acceptable if it exposes the necessary functionality safely.

Do not spend tokens achieving pixel-level parity with obsolete Tkinter screens.

Do not polish temporary migration UI unless it is becoming part of the final product.

---

# 4. Protect Research Logic From the UI Layer

Identify research/business logic that is currently coupled to Tkinter.

Where necessary, separate it so that:

```text
Research / Domain Logic
          ↓
Application Services
          ↓
PySide6 UI
```

rather than:

```text
Tkinter callback
      ↓
Research logic
      ↓
UI state
```

Do this deliberately and only where needed.

Do **not** use the migration as an excuse for an unlimited architecture rewrite.

Scientific functionality should ultimately be callable independently of a particular widget.

---

# 5. Migration Definition of Done

The PySide6 migration should have a concrete stopping point.

The migration is **good enough to end** when:

- [ ] CMAT launches reliably using PySide6.
- [ ] Projects can be created, opened, and saved.
- [ ] Media can be imported/accessed through the new application.
- [ ] Essential existing research and analysis functions remain reachable.
- [ ] The basic PySide6 pipeline is functional.
- [ ] No critical research functionality requires launching a Tkinter window.
- [ ] Core domain/research logic required by the product is not dependent on Tkinter UI state.
- [ ] Remaining Tkinter code is explicitly classified as deprecated, deferred, or safe to delete.
- [ ] Major duplicate implementations have been identified.
- [ ] Critical workflows have been smoke-tested.
- [ ] The repository clearly identifies PySide6 as the active UI architecture.

**UI polish is NOT a requirement for migration completion.**

Advanced pipeline functionality is NOT a requirement for migration completion.

Perfect feature parity is NOT a requirement for migration completion.

---

# 6. Finish the Basic Pipeline, Not the Entire Pipeline Vision

The current PySide6 pipeline:

**Sampling → Selection → Measurement → Validation → Results**

is important and should be completed as part of the PySide6 foundation.

However, do **not** implement the advanced measurement/provenance pipeline vision merely to finish the migration.

Advanced concepts such as:

- nested measurement pipelines;
- construct → measure → method graphs;
- full provenance visualization;
- measurement recipes;
- dependency invalidation;
- stale-result propagation;
- advanced composite construction;

belong to later product-development phases.

First establish a reliable basic PySide6 application and pipeline.

---

# 7. Use Small, Disposable Migration Sessions

Do not use one enormous Claude Code conversation for the entire migration.

Each migration session should have a **single bounded objective**.

Examples:

> **Task: Migrate Project Configuration. Do not work elsewhere.**

> **Task: Remove the Tkinter dependency from sampling logic. Do not redesign Sampling.**

> **Task: Verify feature parity for X, then identify whether the old Tkinter implementation can be deleted.**

> **Task: Audit the remaining Tkinter dependencies. Make no code changes.**

At the end of each successful bounded task:

1. test the affected functionality;
2. review the diff;
3. update the migration checklist;
4. update the project handoff/onboarding documentation;
5. commit the coherent change to Git;
6. start a fresh Claude session for the next substantial task.

Do not carry a huge migration conversation indefinitely.

---

# 8. Minimize Context and Token Waste

Claude should retrieve only the files relevant to the current migration task.

Do not repeatedly load the entire project history.

Use the project's documentation/index/navigation files to locate relevant code.

Before modifying code:

1. identify the smallest relevant subsystem;
2. inspect its dependencies;
3. state the intended change;
4. modify only what is required;
5. test;
6. stop when the bounded objective is complete.

Avoid opportunistic cleanup unrelated to the task.

Avoid redesigning neighboring systems “while we are here.”

Avoid generating large explanations unless they are needed for a decision or documentation.

---

# 9. Do Not Repeatedly Fix the Same Migration Problem in a Degraded Session

If a Claude session begins:

- repeating mistakes;
- forgetting decisions made earlier in the same session;
- undoing working changes;
- producing increasingly broad fixes;
- misunderstanding the architecture after repeated correction;

stop the session.

Write/update the handoff documentation, preserve working changes in Git, and start a fresh session.

Do not keep spending tokens attempting to rescue a degraded context.

---

# 10. Git Is the Migration Safety Net

Before a substantial migration or refactor:

- ensure the current working state is understood;
- commit known-good work;
- use an appropriate branch/worktree when useful.

After a bounded migration succeeds:

- test it;
- inspect the diff;
- make a coherent commit.

Do not allow Claude to make dozens of unrelated migration changes before establishing a recovery point.

---

# 11. Avoid the Sunk-Cost Trap

The fact that substantial effort has already been spent on migration does **not** mean every remaining Tkinter feature must be ported.

Evaluate remaining components based on the current CMAT vision.

For each component:

### KEEP / MIGRATE
The capability remains necessary and the existing behavior is appropriate.

### REBUILD
The capability remains necessary, but the old Tkinter interaction should be replaced with a better PySide6/pipeline-centered design.

### DEFER
The capability may be useful later but is not needed to complete the migration.

### DELETE
The capability is obsolete, duplicated, superseded, or inconsistent with current CMAT direction.

The goal is not to preserve sunk cost.

The goal is to reach the best maintainable version of CMAT with the least unnecessary work.

---

# 12. Preserve the New CMAT Direction

CMAT has evolved beyond the original Tkinter application.

The new application is becoming a pipeline-centered scientific workbench for children's media research.

Do not let migration requirements dictate the future product architecture.

In particular, do not painstakingly recreate an old workflow if it will soon be superseded by:

**Sampling → Selection → Measurement → Validation → Results**

Use the old implementation to understand what capability needs to survive, then decide how that capability belongs in the current CMAT design.

---

# 13. Migration Audit Deliverable

Before substantial additional migration work, create/update a migration tracker containing a table like:

| Component | Tkinter State | PySide6 State | Classification | Blocker? | Next Action |
|---|---|---|---|---|---|
| Example | Existing | Partial | REBUILD | Yes | Complete minimal PySide6 implementation |

Then provide:

### Migration blockers
Only tasks required to meet the Definition of Done.

### Deferred work
Features that can wait until after migration.

### Delete candidates
Tkinter code that no longer needs to survive.

### Estimated finish line
A concrete list of remaining bounded tasks required to declare the migration complete.

The purpose is to turn:

> “Keep converting CMAT.”

into:

> **“There are N remaining migration blockers. Complete those, verify the application, and end the migration phase.”**

---

# Final Directive to Claude Code

**Do not optimize for preserving the Tkinter application. Optimize for reaching a stable, maintainable PySide6 CMAT as efficiently as possible.**

The Tkinter version is a **reference implementation and prototype**, not a specification requiring perfect parity.

The migration is infrastructure work. It must not consume the project indefinitely.

The desired progression is:

```text
Audit remaining migration
        ↓
Identify true blockers
        ↓
Migrate / rebuild only what matters
        ↓
Finish basic PySide6 pipeline
        ↓
Verify critical workflows
        ↓
Declare migration complete
        ↓
Return to building CMAT
```

The key question for every remaining migration task is:

> **Does this work need to be completed before we can safely stop thinking about Tkinter and continue building the actual research product?**

If the answer is no, strongly consider **deferring or deleting it**.
