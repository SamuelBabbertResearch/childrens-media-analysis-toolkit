"""Disk cache for per-episode results under <root>/.analysis/<show>/<episode>.json"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any


def cache_path(root: Path, show_name: str, episode_stem: str) -> Path:
    return root / ".analysis" / show_name / f"{episode_stem}.json"


def load_cached(root: Path, show_name: str, episode_stem: str) -> dict[str, Any] | None:
    p = cache_path(root, show_name, episode_stem)
    if p.exists():
        with p.open() as fh:
            return json.load(fh)
    return None


def load_scored(root: Path, show_name: str, episode_stem: str,
                config: dict[str, Any] | None = None):
    """A cached episode, with its composite re-derived against *config*.

    THE ONE WAY TO READ A CACHED RESULT. The cache stores the composite as it
    stood when the episode was analysed, but the composite is DERIVED — a
    weighted sum over raw metrics that are themselves unchanged. Read the file
    without re-deriving and you report a score under weights that are no
    longer in force.

    That mistake was made independently in four places: the Qt Library, the
    CLI's single-episode path, the CLI's index backfill, and the batch runner's
    cached-episode skip. Each looked right on its own; together they gave four
    different answers for one episode after a settings change. Anything that
    needs raw JSON still has `load_cached`.

    Returns None when nothing is cached; returns a failed result unchanged,
    since there is no composite to derive.
    """
    from .metrics_sensory import rescore_episode
    from .schema import EpisodeResult

    cached = load_cached(root, show_name, episode_stem)
    if not cached:
        return None
    result = EpisodeResult.from_dict(cached)
    if result.status != "ok" or config is None:
        return result
    return rescore_episode(result, config)


def save_cache(root: Path, show_name: str, episode_stem: str, data: dict[str, Any]) -> None:
    p = cache_path(root, show_name, episode_stem)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w") as fh:
        json.dump(data, fh, indent=2)


# ---------------------------------------------------------------------------
# Measurement staleness
# ---------------------------------------------------------------------------
# Weights and normalization ceilings are re-scorable from cached raw metrics, so
# changing them must NOT invalidate anything. Measurement settings (detector,
# thresholds, sample rates) change the raw numbers themselves, so a cached
# result measured under different settings is not comparable with a fresh one.
# These helpers make that distinction checkable instead of leaving it to the
# user to remember.

def cached_fingerprint(cached: dict[str, Any] | None) -> str:
    """Measurement fingerprint of a cached result; '' if absent or unreadable."""
    if not isinstance(cached, dict):
        return ""
    value = cached.get("measurement_fingerprint", "")
    return value if isinstance(value, str) else ""


def is_stale(cached: dict[str, Any] | None, config: dict[str, Any]) -> bool:
    """True when *cached* was measured under different measurement settings.

    Results written before fingerprinting existed carry no fingerprint. Those
    are GRANDFATHERED (treated as current) rather than invalidating an entire
    existing corpus on upgrade — staleness detection applies to changes made
    from here forward.
    """
    from .measurements import measurement_fingerprint
    stored = cached_fingerprint(cached)
    if not stored:
        return False
    return stored != measurement_fingerprint(config)


def stale_entries(
    root: Path, config: dict[str, Any], entries: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    """Filter (show_name, episode_stem) pairs down to those needing re-analysis.

    Used to answer 'changing this setting invalidates N episodes' before the
    user commits to the change.
    """
    out: list[tuple[str, str]] = []
    for show_name, stem in entries:
        if is_stale(load_cached(root, show_name, stem), config):
            out.append((show_name, stem))
    return out
