# CMAT v1.3.2 Windows release

This release makes the two hand-coding tasks directly accessible and repairs
result discovery and Windows window management. Automated measurement formulas
and export schema 3 are unchanged from v1.3.1.

- Human coding begins with **Hand Code Cuts** and **Hand Code Fantastical Events**.
  Task choices sit above the active task's controls. Detector comparison and
  coder agreement remain separate views. Cut marks save the established manual
  transition CSV; fantastical events save their separate event CSV.
- Pipeline entry points open the matching coding task. Both tasks use the same
  frame-accurate player and timestamp path. Switching a Library target no longer
  changes the identity of an already-loaded coding sheet before opening it.
- Library discovery includes supported videos directly inside the chosen root,
  alongside show/category subfolders. Existing direct-root caches retain their
  identifiers. Opening a root or completing measurement imports cached results
  into Index without reanalyzing the videos.
- Real native Windows frames provide dragging, resizing and maximize/restore
  after startup-dialog dismissal, for the main window and shared dialogs.
- Compact styling is restored. Long root paths elide with full-path tooltips;
  selected workflow names reserve bold-text width. Diagram title wrapping and
  functional zoom remain. Bundled VLC discovery remains fixed.

## Installation

Download `CMAT-v1.3.2-windows.zip`, extract the complete archive, and open
`CMAT/CMAT.exe`. Keep `_internal` beside the executable. No separate Python,
FFmpeg or VLC installation is needed. Optional transcription model weights
download on first use. Do not copy personal settings or research data into the
public archive.

## Qualification

Build from the tagged source with `build.spec`. Run the full source suite in
an isolated checkout, then `CMAT.exe --check-package report.json` from a fresh
extraction. The diagnostic checks cold bundled VLC loading, FFmpeg analysis,
language resources, startup-dialog dismissal and native window controls,
direct-root Library/Index persistence, both coding choices and their actual
CSV readback, diagram zoom, rendering, and VLC decoding. Compare synthetic
measurement and language artifacts against the prior qualified build.

Use a waiting Windows launcher with redirected output for frozen diagnostics;
an exiting launcher can close inherited handles and invalidate the check.
Desktop interaction checks must separately confirm the task selectors are
visible. Checks on the build computer do not establish separate clean-PC or
on-device audible-playback qualification.

Source is published on `codex/integrate-liu-september-updates`; the release tag
does not merge the branch into master. The public Index website and Study
Runner remain separate products. Researcher reports and stimulus files are
not release assets.


## Published qualification record — 2026-10-26

[v1.3.2](https://github.com/SamuelBabbertResearch/childrens-media-analysis-toolkit/releases/tag/v1.3.2) is published as the latest stable Windows release. Source/tag commit: `f30148fd74ec0efcba6fa6a05d265c086973aa04`. The full isolated suite passed **819 tests**, with **13 absent-media skips**. The fresh ZIP extraction passed all packaged checks described above; synthetic metrics and language values matched the previous qualified dev3 build exactly. Both direct hand-coding choices were also verified on the real release desktop after startup dismissal.

Archive: `CMAT-v1.3.2-windows.zip`, **355447329 bytes**. SHA256: `addfceba85d1e3cc5a3c89fa5994f93a5c8b6e76bf62b83e6b28e0d1dca7f564`. GitHub's uploaded-asset digest matches. ZIP integrity and exclusion of personal preferences and research data were checked. Testing was on the build machine; separate clean-PC and audible-device checks remain unverified.

[Integration PR #16](https://github.com/SamuelBabbertResearch/childrens-media-analysis-toolkit/pull/16) awaits the project's review before merging to master. The release tag remains pinned to its exact tested source; this subsequent documentation record does not change that artifact.
