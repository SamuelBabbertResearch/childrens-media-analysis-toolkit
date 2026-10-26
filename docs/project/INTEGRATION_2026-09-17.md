# Local work and Dr. Liu's September updates

## Preserved history

- Original branch: `feature/language-analysis`, at `2399ec6`.
- Local checkpoint: `723c8a5`, on `codex/checkpoint-before-liu-integration`.
  Includes the previously uncommitted chart, clip-tool, study-documentation,
  research-prompt, and project-documentation edits. Private ignored files were
  not staged.
- Integration branch: `codex/integrate-liu-september-updates`.
- Incoming commits: `0f0a6a7` (methodological corrections) and `5d187a1`
  (performance improvements), merged from `origin/master`.

The four September 7 commits on the original branch remain in the history.
`build_site.py` and `site_manifest.json` retain their checkpoint contents.
The integrated `analyzer/` files match Dr. Liu's incoming version exactly.

## Resolutions

Git recognized all ten document moves to `docs/project/`. The three text
conflicts were `INDEX.md`, `docs/project/onboarding.md`, and `ui/chart.py`.
The index retains the relocated links and adds the methodological audit;
onboarding retains both the September 7 and September 16 records.

Charts retain unique episode labels and the horizontal layout above ten
episodes. Dr. Liu's collection-based rendering now supports both orientations,
with numeric positions independent of labels. Timed-text labels follow the
audit. Regression checks cover 3, 12, and 200 episodes, component totals with
and without audio, and alignment of timed-text rates and density.

The Clip Finder feature map and browser cut marker are preserved. Feature-map
headings use the audited motion and audio definitions. `AGENTS.md` and
`CLAUDE.md` agree on document paths, the default detector's validation basis,
and the timed-text denominator. Chart margins were adjusted after rendering
revealed overlapping footnote text and clipped episode labels.

## Verification

The final full suite ran in a disposable source copy, with the existing local
CMU pronunciation dictionary copied into it and the native Tcl/Tk runtime
available: **804 passed, 13 skipped, 1 dependency deprecation warning**.
All 13 skips require absent Little Bear media. Neither the episode library nor
the working copy's analysis/hand-coding data was used as writable test data.

An earlier sandbox run could not initialize Tcl/Tk and the first disposable
copy omitted the pronunciation dictionary. Those environment issues were
corrected before the successful full run. A targeted recheck also passed
all 138 chart, Clip Finder, cut-marker, Qt, and vocabulary tests.

Visual inspection used rendered Qt dialogs with synthetic data and registered
Windows fonts: vertical and horizontal FFC, timed-text rate/density, vocabulary
tiers, readability including a negative value, the feature map, and Clip
Finder. This was not a real-media playback trial or a packaged-release check.

At verification time the merge was local. The subsequent source-publication
step targets `origin/codex/integrate-liu-september-updates`, preserving `master`.
[Update notes](../../CHANGELOG.md) describe the combined changes and distinguish
the source archive from the older Windows package. No new packaged release or
Index website publication is included.
