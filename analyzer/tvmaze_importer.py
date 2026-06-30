"""
TVMaze episode-metadata fetcher.

Uses the free TVMaze public API — no authentication required.
API reference: https://www.tvmaze.com/api

Returns WikiEpisode objects so the same match_to_files() logic used by
the Wikipedia importer works without modification.
"""

from __future__ import annotations
import json
import re
import urllib.error
import urllib.request

from .wiki_importer import WikiEpisode, match_to_files  # noqa: F401 (re-exported)

_API_BASE   = "https://api.tvmaze.com"
_SHOW_ID_RE = re.compile(r"tvmaze\.com/shows/(\d+)")
_HEADERS    = {"User-Agent": "CMAT/1.0 (children's media analysis research tool)"}


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def extract_show_id(url: str) -> int | None:
    """Return the integer show ID embedded in a TVMaze URL, or None."""
    m = _SHOW_ID_RE.search(url)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------

def _get(path: str, timeout: int = 12) -> object:
    req = urllib.request.Request(f"{_API_BASE}{path}", headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_show_info(show_id: int) -> dict:
    """Return the TVMaze show-level metadata dict (name, network, premiered, …)."""
    return _get(f"/shows/{show_id}")  # type: ignore[return-value]


def fetch_episodes(show_id: int) -> list[WikiEpisode]:
    """Fetch all *regular* episodes for a show; return as WikiEpisode list.

    Specials (type != 'regular') are excluded because they usually lack
    season/episode numbers that match filenames.
    """
    data: list[dict] = _get(f"/shows/{show_id}/episodes")  # type: ignore[assignment]

    episodes: list[WikiEpisode] = []
    for ep in data:
        if ep.get("type", "regular") != "regular":
            continue
        air_date = ep.get("airdate") or None
        if air_date in ("0000-00-00", ""):
            air_date = None
        episodes.append(WikiEpisode(
            season        = ep["season"],
            episode_num   = ep["number"],
            episode_overall = None,
            title         = ep.get("name") or "",
            air_date      = air_date,
            raw_date      = air_date or "",
        ))

    return sorted(episodes, key=lambda e: (e.season, e.episode_num))
