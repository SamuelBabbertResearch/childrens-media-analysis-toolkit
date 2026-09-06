"""Loads and validates config.json. Returns a plain dict — no GUI dependencies."""

from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# What a preset is, said once, for both front-ends
# ---------------------------------------------------------------------------
# Shown above the preset chooser in the Qt Settings dialog and in the classic
# one. ALWAYS, for every preset — a caveat carried only inside each preset's
# own description is a caveat a researcher meets AFTER choosing.
#
# The shipped presets are named for age bands, and an age-named bundle of
# numbers reads as a developmental threshold unless something says otherwise.
# Nothing derives these values: the ceilings were fitted to one 78-episode
# working corpus (`CEILINGS.md`) and the weights have no recorded derivation at
# all (`ARCHITECTURE.md` §8.1a). `DECISIONS.md` records why the age NAMES are
# kept — they say which population a study is about, which is the clearest
# label available — and therefore why the framing has to carry the rest.
#
# IT LIVES HERE, NOT IN `ui/`, because `gui.py` is the Tk front-end and must
# not import a Qt module to read a string. `analyzer/` imports no framework
# (`CLAUDE.md` §2.4, `tests/test_engine_isolation.py`), so it is the one place
# both builds can read from. One wording, two front-ends, no drift.
PRESET_BANNER = (
    "Illustrative presets — not validated developmental norms. An age name "
    "says which population a study using the preset is about. It is not a "
    "recommendation, an appropriateness rating, a safety threshold, or "
    "evidence about that age group. No published source specifies these "
    "weights or ceilings. Where an inferential claim depends on the "
    "composite, define and preregister a study-specific configuration."
)

# What a preset the RESEARCHER saves records about itself. It must not inherit
# the shipped marker, and it must not claim a derivation it does not have.
USER_PRESET_DERIVATION = "user-defined in this install; not recorded here"


def _base_dir() -> Path:
    # When frozen by PyInstaller, _MEIPASS is the unpacked bundle directory.
    # At runtime we prefer a config.json next to the .exe so users can edit weights.
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        if (exe_dir / "config.json").exists():
            return exe_dir
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).parent.parent


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    """Load config from *path*, falling back to the project-root config.json.

    The loaded config is passed through measurements.normalize_config(), which
    builds the `measurements` block from legacy flat keys on first load and
    thereafter keeps the flat keys derived from it. Call sites that read the
    flat keys directly (engine, metrics_frames, speech) are unaffected.
    """
    resolved = Path(path) if path else _base_dir() / "config.json"
    with resolved.open() as fh:
        cfg = json.load(fh)
    from .measurements import normalize_config
    return normalize_config(cfg)
