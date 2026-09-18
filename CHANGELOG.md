# Update history

## 2026-09-17 — integrated source update

This update combines Dr. Liu's September 16–17 changes with the local chart,
clip-tool, documentation, and public Index improvements. The application
source reports version **1.3.0** and export schema **3**. This is a source
update on `codex/integrate-liu-september-updates`, not a new Windows release.

### Measurements and reproducibility

- Separate hard-cut measures from broader transition measures when choosing
  detector methods.
- Tie validation claims to the exact detector configuration graded.
- Clean non-speech caption cues and merge overlapping timed-text intervals;
  report words per timed-text minute alongside timed-text density.
- Export source, requested, and effective frame-sampling rates and intervals.
- Retain the final partial audio window and identify audiovisual versus
  visual-only Formal-Feature Composite inputs.
- Use more precise measurement labels and exploratory language-output status;
  allow lexical norm tables to be independently optional.

### Performance and charts

- Defer heavy analysis imports, reuse result-cache reads and folder scans,
  combine frame-analysis passes, and remove redundant audio probing.
- Render chart bars in collections while keeping distinct numeric positions
  and unique episode labels, including duplicate titles.
- Keep horizontal FFC charts for sets above ten episodes and improve spacing
  for episode labels and validation notes.

### Clip tools, documentation, and public Index code

- Add a candidate feature map and a browser-based matched-pair hard-cut marker
  with timestamp coding and CSV export.
- Preserve adult-perception study documentation updates, research prompts,
  and the demonstration-figure script.
- Move ten project documents into `docs/project/`, retain both development
  histories, and align the agent rulebooks with the updated methods and paths.
- Preserve the September 7 public Index terminology, show-key consistency,
  build fixes, and withholding of composites that cannot be re-derived. This
  source push does not republish the separate Index website.

### Verification and limits

The integrated source passed **804 tests**, with **13 skipped** because the
isolated test copy lacked the required Little Bear media. Rendered Qt charts
and Clip Finder were visually checked with synthetic data. No packaged-release
or real-media playback qualification was performed for this integration.
The FFC remains an unvalidated researcher-configured index.

### Downloads

- [Download this integration branch as source ZIP](https://github.com/SamuelBabbertResearch/childrens-media-analysis-toolkit/archive/refs/heads/codex/integrate-liu-september-updates.zip).
  This follows the branch as it changes and requires the source installation
  described in the README.
- [Download the tested merge as a fixed source snapshot](https://github.com/SamuelBabbertResearch/childrens-media-analysis-toolkit/archive/fe041e3234b6dfb6726818260d7d95cf8f396dd0.zip).
  This identifies the tested code exactly; subsequent download documentation
  is not part of that snapshot.
- [Existing Windows package: v1.2.1](https://github.com/SamuelBabbertResearch/childrens-media-analysis-toolkit/releases/tag/v1.2.1).
  It does **not** contain these September 16–17 changes. The newer `v1.2.2`
  DOI-linkage release has no attached Windows package as of this update.

See the [integration record](docs/project/INTEGRATION_2026-09-17.md) for the
checkpoint, merge decisions, and detailed verification.
