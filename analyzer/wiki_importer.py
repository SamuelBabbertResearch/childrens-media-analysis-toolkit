"""
Wikipedia episode-list HTML importer.

Parses a locally-saved "List of X episodes" Wikipedia page and extracts
per-episode metadata (season, episode number, title, air date).

Matches against local MP4 files by season+episode number embedded in the
filename, falling back to fuzzy title matching via difflib.
"""

from __future__ import annotations
import difflib
import re
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------

@dataclass
class WikiEpisode:
    season: int
    episode_num: int        # within season
    episode_overall: int | None
    title: str              # first segment title
    air_date: str | None    # YYYY-MM-DD, or None if not found
    raw_date: str           # verbatim text from page


@dataclass
class MatchResult:
    wiki_ep: WikiEpisode
    local_file: Path | None
    match_type: str         # 'number' | 'title' | 'none'
    score: float            # 0.0–1.0


# ---------------------------------------------------------------------------
# Wikipedia HTML parser
# ---------------------------------------------------------------------------

# ISO date hidden in Wikipedia date templates:
# <span class="bday dtstart published updated itvstart">1995-11-06</span>
_ISO_DATE_RE  = re.compile(r'class="bday[^"]*">\s*(\d{4}-\d{2}-\d{2})\s*<')

# Episode anchor: <th … id="ep3" …>3</th>
_EP_ANCHOR_RE = re.compile(r'id="ep(\d+)"[^>]*>\s*(\d+)\s*</th>', re.IGNORECASE)

# Season episode number: first bare-integer <td rowspan="…">N</td> per block
_SEASON_EP_RE = re.compile(r'<td[^>]*rowspan="\d+"[^>]*>\s*(\d+)\s*</td>')

# First quoted segment title in a block
_TITLE_RE     = re.compile(
    r'class="summary"[^>]*>\s*["“‘]([^"”’<]+)', re.IGNORECASE
)

# Visible date text (before the hidden ISO span) — fallback if no ISO date
_RAW_DATE_RE  = re.compile(r'(?:January|February|March|April|May|June|July|August|'
                            r'September|October|November|December)\s+\d{1,2},\s+\d{4}')

# Season/series heading: <h2>…Season 1…</h2>  or  id="Season_1"
_SEASON_HDG_RE = re.compile(
    r'<h[23][^>]*>.*?(?:[Ss]eason|[Ss]eries)\s+(\d+).*?</h[23]>|'
    r'id="(?:[Ss]eason|[Ss]eries)_(\d+)"',
    re.DOTALL,
)

# Wikitable markers
_TABLE_RE = re.compile(
    r'<table[^>]*class="[^"]*wikitable[^"]*"[^>]*>(.*?)</table>',
    re.DOTALL | re.IGNORECASE,
)


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def parse_wikipedia_episode_list(html_path: Path) -> list[WikiEpisode]:
    """Parse a Wikipedia episode-list HTML file into WikiEpisode records."""
    html = html_path.read_text(encoding="utf-8", errors="replace")

    # Build a list of (char_pos, season_num) from headings
    heading_seasons: list[tuple[int, int]] = []
    for m in _SEASON_HDG_RE.finditer(html):
        s = m.group(1) or m.group(2)
        if s:
            heading_seasons.append((m.start(), int(s)))

    episodes: list[WikiEpisode] = []

    for tbl_m in _TABLE_RE.finditer(html):
        tbl_start = tbl_m.start()
        tbl_html  = tbl_m.group(1)

        # Assign table to the most recent season heading before it
        season = 0
        for pos, s in heading_seasons:
            if pos < tbl_start:
                season = s

        # Split the table into per-episode blocks at each id="epN"
        blocks = re.split(r'(?=<t[dh][^>]*id="ep\d+)', tbl_html)

        for block in blocks:
            # --- overall and in-season episode numbers ---
            ep_m = _EP_ANCHOR_RE.search(block)
            if not ep_m:
                continue
            ep_overall = int(ep_m.group(1))

            # First rowspan <td> after the anchor = episode-in-season number
            ep_in_season = ep_overall  # sensible default
            ses_m = _SEASON_EP_RE.search(block, ep_m.end())
            if ses_m:
                try:
                    ep_in_season = int(ses_m.group(1))
                except ValueError:
                    pass

            # --- air date (prefer hidden ISO span; fall back to visible text) ---
            iso_m = _ISO_DATE_RE.search(block)
            if iso_m:
                air_date = iso_m.group(1)
                raw_date = air_date
            else:
                raw_m = _RAW_DATE_RE.search(_strip_tags(block))
                raw_date = raw_m.group(0) if raw_m else ""
                air_date = None
                if raw_date:
                    from datetime import datetime
                    for fmt in ("%B %d, %Y", "%b %d, %Y"):
                        try:
                            air_date = datetime.strptime(raw_date, fmt).strftime("%Y-%m-%d")
                            break
                        except ValueError:
                            pass

            # --- first segment title ---
            title_m = _TITLE_RE.search(block)
            title = title_m.group(1).strip() if title_m else ""

            episodes.append(WikiEpisode(
                season=season,
                episode_num=ep_in_season,
                episode_overall=ep_overall,
                title=title,
                air_date=air_date,
                raw_date=raw_date,
            ))

    return sorted(episodes, key=lambda e: (e.season, e.episode_num))


# ---------------------------------------------------------------------------
# Filename → (season, episode) extraction
# ---------------------------------------------------------------------------

_NUM_PATTERNS = [
    re.compile(r"(\d+)[xX](\d{2,})"),          # 1x05, 2X03
    re.compile(r"[Ss](\d+)[Ee](\d+)"),          # S01E05
    re.compile(r"[Ss]eason\s*(\d+).*?[Ee]p?\s*(\d+)"),  # Season 1 Ep 5
]


def extract_season_ep(filename: str) -> tuple[int, int] | None:
    stem = Path(filename).stem
    for pat in _NUM_PATTERNS:
        m = pat.search(stem)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _norm(t: str) -> str:
    t = t.lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return " ".join(t.split())


def match_to_files(
    wiki_eps: list[WikiEpisode],
    local_files: list[Path],
) -> list[MatchResult]:
    """Match WikiEpisode list to local MP4 paths.

    Pass 1 — season+episode number in filename (exact, score=1.0).
    Pass 2 — difflib fuzzy title match on remaining files (score=ratio).
    """
    # Build (season, ep) → file index from filenames that carry numbers
    numbered: dict[tuple[int, int], Path] = {}
    for fp in local_files:
        pair = extract_season_ep(fp.name)
        if pair:
            numbered[pair] = fp

    used: set[Path] = set()
    pending: list[WikiEpisode] = []
    results: list[MatchResult] = []

    for wep in wiki_eps:
        fp = numbered.get((wep.season, wep.episode_num))
        if fp and fp not in used:
            used.add(fp)
            results.append(MatchResult(wep, fp, "number", 1.0))
        else:
            pending.append(wep)

    # Fuzzy title pass
    remaining = {fp: _norm(fp.stem) for fp in local_files if fp not in used}
    for wep in pending:
        if not wep.title or not remaining:
            results.append(MatchResult(wep, None, "none", 0.0))
            continue
        wt = _norm(wep.title)
        best_fp, best_score = None, 0.0
        for fp, ft in remaining.items():
            s = difflib.SequenceMatcher(None, wt, ft).ratio()
            if s > best_score:
                best_score, best_fp = s, fp
        if best_score >= 0.45 and best_fp:
            used.add(best_fp)
            del remaining[best_fp]
            results.append(MatchResult(wep, best_fp, "title", round(best_score, 2)))
        else:
            results.append(MatchResult(wep, None, "none", 0.0))

    return sorted(results, key=lambda r: (r.wiki_ep.season, r.wiki_ep.episode_num))
