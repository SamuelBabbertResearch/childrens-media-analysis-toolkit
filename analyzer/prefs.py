"""
Per-user preferences — local machine state, kept out of the shared config.

config.json is versioned: it holds the presets, weights, and measurement
settings that define how CMAT measures, and those are meant to be shared and
reviewed. Which folder *this* person last opened, and whether *they* want the
welcome screen, are neither. Mixing them meant a local absolute path landed in
a tracked file and would be pushed to a public repository.

Written to user_prefs.json beside config.json and gitignored. Missing or
unreadable files fall back to defaults rather than failing — a preference is
never important enough to block the application.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config_loader import _base_dir

FILENAME = "user_prefs.json"

DEFAULTS: dict[str, Any] = {
    "last_root_folder": None,
    "show_welcome_on_start": True,
    "show_pipeline_on_start": True,
}


def prefs_path() -> Path:
    return _base_dir() / FILENAME


def load_prefs() -> dict[str, Any]:
    out = dict(DEFAULTS)
    path = prefs_path()
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                out.update({k: v for k, v in data.items() if k in DEFAULTS})
    except Exception:
        pass
    return out


def get_pref(key: str, default: Any = None) -> Any:
    return load_prefs().get(key, DEFAULTS.get(key, default))


def set_pref(key: str, value: Any) -> None:
    """Write one preference, preserving the others. Never raises."""
    data = load_prefs()
    data[key] = value
    try:
        prefs_path().write_text(json.dumps(data, indent=2) + "\n",
                                encoding="utf-8")
    except Exception:
        pass


def migrate_from_config(cfg: dict[str, Any]) -> None:
    """Move any preference keys that were previously written to config.json.

    Older builds stored these in the shared config. Copy them across once so
    the setting survives the upgrade; the caller strips them from config.json.
    """
    found = {k: cfg[k] for k in DEFAULTS if k in cfg}
    if not found:
        return
    data = load_prefs()
    for k, v in found.items():
        data.setdefault(k, v)
        if data.get(k) is None:
            data[k] = v
    try:
        prefs_path().write_text(json.dumps(data, indent=2) + "\n",
                                encoding="utf-8")
    except Exception:
        pass
