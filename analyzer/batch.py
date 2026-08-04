"""
Batch runner: analyze every episode in a show folder.

Already-cached episodes are loaded from disk and skipped.
Failed episodes are logged and skipped — they never crash the batch.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Any, Callable

from .cache import load_cached, save_cache
from .config_loader import load_config
from .engine import analyze_episode
from .schema import EpisodeResult
from .show_index import list_episodes, show_key

logger = logging.getLogger(__name__)


def analyze_show_batch(
    show_dir: Path,
    root: Path | None = None,
    config: dict[str, Any] | None = None,
    force: bool = False,
    progress_cb: Callable[[str, float, float], None] | None = None,
) -> list[EpisodeResult]:
    """
    Analyze all MP4 episodes in *show_dir*.

    Args:
        show_dir: Directory containing MP4 files (one show).
        root: Root directory for cache paths; defaults to show_dir.parent.
        config: Config dict (loaded from config.json if None).
        force: Re-analyze even if a cached result exists.
        progress_cb: Called as (episode_name, episode_fraction, overall_fraction).
                     episode_fraction is progress within the current episode [0,1].
                     overall_fraction is progress across the whole batch [0,1].

    Returns:
        List of EpisodeResult (one per episode, including failed ones).
    """
    root = root or show_dir.parent
    skey = show_key(root, show_dir)
    cfg = config or load_config()
    episodes = list_episodes(show_dir)

    if not episodes:
        logger.warning("No MP4 files found in %s", show_dir)
        return []

    n = len(episodes)
    results: list[EpisodeResult] = []

    for idx, ep in enumerate(episodes):
        base_overall = idx / n
        episode_span = 1.0 / n

        if progress_cb:
            progress_cb(ep.name, 0.0, base_overall)

        cached = None if force else load_cached(root, skey, ep.stem)

        if cached:
            logger.info("[cache] %s", ep.name)
            result = EpisodeResult.from_dict(cached)
            if progress_cb:
                progress_cb(ep.name, 1.0, base_overall + episode_span)
            results.append(result)
            continue

        def _ep_progress(frac: float, _base=base_overall, _span=episode_span) -> None:
            if progress_cb:
                progress_cb(ep.name, frac, _base + frac * _span)

        try:
            result = analyze_episode(ep, config=cfg, progress_cb=_ep_progress)
        except Exception as exc:
            logger.error("Unexpected error analyzing %s: %s", ep.name, exc)
            result = EpisodeResult(file=ep.name, status="failed", error=str(exc))

        if result.status == "failed":
            logger.warning("Skipping failed episode %s: %s", ep.name, result.error)
        else:
            save_cache(root, skey, ep.stem, result.to_dict())

        if progress_cb:
            progress_cb(ep.name, 1.0, base_overall + episode_span)

        results.append(result)

    return results
