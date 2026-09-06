"""
Software identity — the one place CMAT says which build produced a result.

A number in a paper is only reproducible if a reader can get back to the code
that made it. Before this module the answer was scattered and partly wrong:

  * `analyzer/validation.py` had a private `_git_commit()`, used by validation
    manifests only.
  * `analyzer/sampler.py` wrote `software_version = "1.0.0"` — the SAMPLER
    MODULE's version, not CMAT's — and `analyzer/trials.py` copied that string
    into a field named `git_commit`, so the Trials tab displayed
    "Code version: 1.0.0" for every sample ever drawn.
  * Episode results, CSV exports and JSON exports recorded neither.

Everything that leaves CMAT now reads `software_provenance()`. Adding a field
here adds it to every output at once, which is the point: `CLAUDE.md` §6 —
when a rule must hold at every call site, put it in the call.

WHAT IS AND IS NOT RECORDED. Enough to identify the build and the libraries
whose version can change a number, and nothing else. A full environment dump
is not provenance, it is noise that hides the three lines that matter:

  * `cmat_version` — this repository's release string.
  * `git_commit` — the working-copy commit, when running from a git checkout,
    with `-dirty` appended when tracked files differ from it. A frozen build
    has no checkout, so this reads "unavailable (not a git checkout)" rather
    than an empty string that could be mistaken for "clean".
  * `python`, `opencv`, `numpy`, `scenedetect` — the libraries that decode
    frames, compute the metrics and detect the boundaries. A different
    OpenCV can decode a frame differently; a different PySceneDetect can
    place a cut differently. These four can move a published figure.

Deliberately absent: OS build, CPU, every installed package, environment
variables. None of them change a metric, and a provenance block nobody reads
protects nobody.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

# Release string for the toolkit as a whole. Bump on a release; the commit
# below is what pins an individual run.
__version__ = "1.2.0"

CMAT_VERSION = __version__

# Bumped when the SHAPE of an export changes — a key added, removed, or given
# a new meaning — so a file written by an older build is identifiable by
# inspection rather than by guessing which era it came from.
#   1  (unversioned) — no software block at all.
#   2  2026-09-04 — `software`, `exported_at_utc` and `export_schema` added to
#      JSON exports; `results_to_dataframe` gained speech, error, fingerprint
#      and per-metric availability columns, and returns empty rather than zero
#      for a failed episode.
EXPORT_SCHEMA = 2

_NOT_A_CHECKOUT = "unavailable (not a git checkout)"


def _repo_root() -> Path:
    """The directory this package lives under."""
    return Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def git_commit() -> str:
    """The working-copy commit, with `-dirty` when tracked files differ.

    `-dirty` is not decoration. A commit hash beside a result is a promise
    that the code at that commit produced it; if the working tree had
    uncommitted changes, the promise is false and the reader has to be told.

    Returns `_NOT_A_CHECKOUT` outside a git checkout — a frozen PyInstaller
    build, or a source zip. Never an empty string, which reads as "clean".
    """
    kwargs: dict[str, Any] = dict(
        capture_output=True, text=True, cwd=_repo_root(), timeout=5)
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], **kwargs)
        commit = head.stdout.strip()
        if head.returncode != 0 or not commit:
            return _NOT_A_CHECKOUT
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"], **kwargs)
        if status.returncode == 0 and status.stdout.strip():
            return f"{commit}-dirty"
        return commit
    except Exception:
        return _NOT_A_CHECKOUT


def _lib(module_name: str, attr: str = "__version__") -> str:
    """A library's version, or 'not installed'. Never raises, never guesses."""
    try:
        import importlib
        return str(getattr(importlib.import_module(module_name), attr))
    except Exception:
        return "not installed"


def library_versions() -> dict[str, str]:
    """Only the libraries whose version can change a measured number."""
    return {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}"
                  f".{sys.version_info.micro}",
        "opencv": _lib("cv2"),
        "numpy": _lib("numpy"),
        "scenedetect": _lib("scenedetect"),
    }


def software_provenance() -> dict[str, Any]:
    """The block every export embeds. Machine-readable, stable keys."""
    return {
        "cmat_version": CMAT_VERSION,
        "git_commit": git_commit(),
        "libraries": library_versions(),
    }


def utc_now() -> str:
    """An ISO-8601 UTC timestamp. One spelling, so exports sort together."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
