# CMAT v1.3.1 Windows package

This release fixes a Windows VLC startup discovery error reported for v1.3.0.
The bundled DLL belongs in `_internal/vlc`; the availability probe and player
constructor now prepare that path before importing python-vlc. Users do not
need to install VLC separately or move DLLs.

This release also combines the v1.3.0 integration with Dr. Liu's interface commits
`3f7903a` and `6221971`. Their Git timestamps correspond to September 18 UTC.
The refreshed theme, larger text, Constructs cards, and explicit zoom controls
are included. Long card titles wrap so full measurement names and units remain
visible. Analysis calculations and export schema 3 are unchanged.

Chart reconciliation retains horizontal layouts and unique episode labels,
with the upstream palette and wrapped validation notes. Project documentation
keeps both histories under `docs/project/`. No research data are packaged.

## Build and qualification

Use the prerequisites and procedure in [v1.3.0 build notes](RELEASE_1.3.0.md),
substituting `1.3.1` in output paths. The diagnostic now exercises Constructs
zoom-in and reset buttons. Run the full source suite in an isolated copy,
inspect a populated diagram with real fonts, and check both source and frozen
forms. Validate ZIP integrity and repeat the frozen check from a fresh extraction.
The expected package version is `1.3.1`, with export schema `3`.

## Installation and scope

Download `CMAT-v1.3.1-windows.zip`, extract the complete archive, then open
`CMAT/CMAT.exe`. Keep `_internal` beside the executable. Python, FFmpeg, VLC,
the English model, pronunciation dictionary, and readability word lists are
bundled. Whisper weights download on first use; optional lexical norm tables
are not bundled. Testing is on the build machine, not a separate clean PC.

The source is published on `codex/integrate-liu-september-updates`; a release
tag does not merge that branch into `master`. The public Index site and Study
Runner stimulus package are separate deliverables.

## Cold-start qualification — 2026-10-23

The diagnostic now calls the normal availability entry point before any other
VLC import or window initialization and verifies the native DLL actually loaded
from the extracted package. Clear external VLC environment overrides and repeat
the full check from a new extraction before publication. Record the exact source
commit, archive checksum, and observed results here after qualification.

## Published Windows release — 2026-10-23

[v1.3.1](https://github.com/SamuelBabbertResearch/childrens-media-analysis-toolkit/releases/tag/v1.3.1) fixes bundled VLC discovery before cold imports and completes the existing interface integration. Source/tag: `v1.3.1` / `d85f8bd63e6e8da9898b09b9d7a84e9e48c4038d` on `codex/integrate-liu-september-updates`; master is unchanged. The isolated source suite passed **812 tests**, with **13 absent-media skips**. Source and fresh-extraction frozen diagnostics passed: bundled VLC DLL path, bundled FFmpeg, synthetic analysis, all readability formulas, interface/chart/Clip Finder rendering, Constructs zoom, and synthetic VLC playback. Source and frozen metrics/readability matched exactly; ordinary offscreen startup remained running for 15 seconds. The archive passed CRC/integrity checks and contains no personal preferences, research library, pipelines, or private paper notes.

Archive: `CMAT-v1.3.1-windows.zip`, 355,445,077 bytes. SHA-256: `b61fc8729fc88f8c56ec36bbdc8531bde29b24460a290810362f9b46b3797d4b`. GitHub's uploaded-asset digest matches. Checks are on the Windows build machine; separate clean-PC testing and on-device audible playback remain unverified. This publication supersedes the earlier pending-build notes. Unrelated local Study Runner changes remain outside this release.
