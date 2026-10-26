# CMAT v1.3.0 Windows package

This release packages the [September integration](INTEGRATION_2026-09-17.md).
It is the research toolkit, not a new Study Runner stimulus package. The
separate public Index website is not republished by this release.

## Build

The build uses `build.spec`, Python 3.12 (64-bit), PyInstaller 6.22.2, and the
qualified PySide6 6.8.3. Build prerequisites are listed in `build.spec`:
local FFmpeg, 64-bit VLC, `en_core_web_sm`, and `.analysis/nltk_data` containing
CMUdict. `textstat` resource files are explicitly collected so its Spache and
Dale-Chall formulas work in the frozen app. The package includes no personal preferences, video library, study
responses, or research caches.

```powershell
.venv/Scripts/python.exe -m PyInstaller build.spec --noconfirm --distpath dist/release_v1.3.0 --workpath build/release_v1.3.0/pyinstaller
Copy-Item config.json dist/release_v1.3.0/CMAT/config.json
```

The ZIP must contain the complete `CMAT/` directory. Its `BUILD_INFO.json`
identifies the source commit and build dependencies. `SHA256SUMS.txt` records
the archive checksum as a separate release asset.

## Qualification

The integrated source suite passed **804 tests**, with **13 media-dependent
skips**. For packaging, run the source and frozen forms of the opt-in check:

```powershell
.venv/Scripts/python.exe cmat_qt.py --check-package build/release_v1.3.0/source-check.json
dist/release_v1.3.0/CMAT/CMAT.exe --check-package build/release_v1.3.0/package-check.json
```

The report must contain `passed: true`; the frozen run must also report
`frozen: true` and version `1.3.0`. The check generates 3.25 seconds of synthetic
video and audio, analyzes it, computes language/readability results, imports
Whisper, renders the main window/charts/Clip Finder, and checks that bundled
VLC decodes the synthetic clip. Images and analysis JSON remain in the scratch
directory identified in the report. No user library is opened.

Verify the ZIP's integrity, extract it into a new location, and repeat the
packaged check there before publication. A successful build alone is not a
release qualification.

## User installation and limits

Download `CMAT-v1.3.0-windows.zip`, extract the whole archive, and open
`CMAT/CMAT.exe`. Keep `_internal` beside the executable. Python, FFmpeg, and VLC
do not need separate installations. Whisper model weights are downloaded on
first use and are not included. Optional lexical norm tables are not bundled.

The package checks are synthetic smoke tests on the build machine, not a
separate clean-Windows-machine validation. The FFC remains unvalidated; all
measurement qualifications in the methodological audit still apply.


## Build-machine results — 2026-09-18

The corrected build passed the frozen package check with external Python,
FFmpeg, VLC, and language-resource environment overrides removed. The bundled
FFmpeg generated a 3.25-second video; the source and frozen runs produced
identical analysis and readability results. Main-window, chart, timed-text,
and Clip Finder rendering succeeded, and VLC advanced through the synthetic
video. The first build's missing word lists were fixed in the spec before the
final build. Archive qualification is repeated immediately before publishing.


## Published release

Published on 2026-09-18 as the latest non-prerelease:
https://github.com/SamuelBabbertResearch/childrens-media-analysis-toolkit/releases/tag/v1.3.0

- Tag/source commit: `v1.3.0` / `7781d60ad6bfe2efee690f53188555d033becf44`.
- Windows archive: `CMAT-v1.3.0-windows.zip`, 352,323,084 bytes.
- SHA-256: `38c66ef90903326164e5cf4033b6cf4ac894c75daee104a7ceafd621f6b24c56`.
- ZIP CRC/integrity check passed. A fresh extraction passed every frozen smoke
  check, with analysis/readability results matching the source run exactly.
- GitHub's uploaded-asset digest matched the local checksum before publication.
- `SHA256SUMS.txt` is attached as a separate asset. `master` was not modified.

This publication record was added after tagging; it does not move the release
tag or change the packaged executable.
