#!/usr/bin/env python3
"""
build_site.py — Open Children's Media Index static site generator.

Reads site_manifest.json and .analysis/ cache files, then writes
a complete static HTML site to _site/.

Usage:
    python build_site.py

Output:
    _site/   — push this folder's contents to the GitHub Pages repo
"""

from __future__ import annotations
import html
import json
import os
import re
import shutil
import stat
from collections import Counter
from datetime import date
from pathlib import Path

from analyzer.provenance import validation_short

ROOT     = Path(__file__).parent
SITE     = ROOT / "_site"
MANIFEST = json.loads((ROOT / "site_manifest.json").read_text(encoding="utf-8"))
CONFIG   = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
TODAY    = date.today().strftime("%B %Y")
REPO_URL = "https://github.com/SamuelBabbertResearch/open-childrens-media-index"
TOOL_URL = "https://github.com/SamuelBabbertResearch/childrens-media-analysis-toolkit"
DOMAIN   = "www.OpenChildrensMediaIndex.org"

# Set to "/Open-Childrens-Media-Index" when serving from GitHub Pages subdirectory.
# Set to "" when using a custom domain (OpenChildrensMediaIndex.org).
BASE_PATH = ""

# Shows whose FFC standard deviation exceeds this are flagged with † in the table.
VARIANCE_FLAG_THRESHOLD = 0.08

# Human-coded metrics (fantastical events) published via `code_events.py publish`.
# Nothing appears on the site unless it is in this file — the explicit publish
# step is the manual-review gate.
_MANUAL_CODING_PATH = ROOT / "manual_coding.json"
MANUAL_CODING: dict = {}
if _MANUAL_CODING_PATH.exists():
    MANUAL_CODING = json.loads(_MANUAL_CODING_PATH.read_text(encoding="utf-8"))


def _events_aggregate(show_events: dict) -> dict:
    """Mean/range of events-per-min across a show's published coded episodes."""
    eps = show_events.get("episodes", [])
    rates = [e["events_per_min"] for e in eps]
    if not rates:
        return {}
    return {
        "n": len(eps),
        "mean": round(sum(rates) / len(rates), 2),
        "min": min(rates),
        "max": max(rates),
    }


# ── Manifest auto-sync ───────────────────────────────────────────────────────

def _sync_manifest() -> None:
    """Scan all known .analysis/ locations for analyzed shows and add any
    unknown show_keys to site_manifest.json with a minimal stub entry.
    Rewrites the file only when new entries are found."""
    manifest_path = ROOT / "site_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    known_keys = {e["show_key"] for e in manifest["shows"]}

    # CMAT writes to <root>/.analysis/ when root is the project root,
    # or <root>/Shows/.analysis/ when root is set to the Shows subfolder.
    analysis_roots = [
        ROOT / ".analysis",
        ROOT / "Shows" / ".analysis",
    ]

    # Folder names that are not real shows (containers, test runs, etc.)
    _SKIP = {"Shows", "Lectures", "Overstimulation", "Jordan Peterson",
             "Little Bear", "My Neighbor Totoro", "Ghibili",
             "Season 1", "Season 2", "Season 3", "Season 4", "Season 5"}

    def _has_episode_json(d: Path) -> bool:
        return (d / "aggregate.json").exists() or any(
            f.is_file() and f.suffix == ".json" and f.stem != "aggregate"
            for f in d.iterdir()
        )

    def _candidate_show_dirs(ar: Path) -> list[tuple[str, Path]]:
        """Return (show_key, show_dir) pairs for every analyzed show under ar."""
        if not ar.exists():
            return []
        results = []
        for d in sorted(ar.iterdir()):
            if not d.is_dir() or d.name in _SKIP:
                continue
            if _has_episode_json(d):
                # Only treat as a show if the parent already has an aggregate
                # (avoids picking up season subfolders as top-level shows)
                results.append((d.name, d))
            else:
                # One level of category nesting (e.g. Category/ShowName)
                for sub in sorted(d.iterdir()):
                    if sub.is_dir() and sub.name not in _SKIP and _has_episode_json(sub):
                        results.append((f"{d.name}/{sub.name}", sub))
        return results

    new_entries: list[dict] = []
    seen_keys: set[str] = set()
    for ar in analysis_roots:
        for show_key, _ in _candidate_show_dirs(ar):
            if show_key in known_keys or show_key in seen_keys:
                continue
            seen_keys.add(show_key)
            display_name = show_key.split("/")[-1]
            new_entries.append({
                "show_key":      show_key,
                "display_name":  display_name,
                "category":      "uncategorized",
                "review_needed": True,
            })
            print(f"  [manifest] auto-added: {show_key}  <- fill in metadata and remove review_needed")

    if new_entries:
        manifest["shows"].extend(new_entries)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  [manifest] wrote {manifest_path.name} (+{len(new_entries)} new entries)")

    # Reload the global MANIFEST so build() sees the updated list
    global MANIFEST
    MANIFEST = manifest


# ── Data helpers ─────────────────────────────────────────────────────────────

def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _find_aggregate(show_key: str) -> dict | None:
    """Try several paths where CMAT might have written aggregate.json."""
    candidates = [
        ROOT / ".analysis" / show_key / "aggregate.json",
        ROOT / "Shows" / show_key / ".analysis" / show_key / "aggregate.json",
        ROOT / "Shows" / ".analysis" / show_key / "aggregate.json",
    ]
    for p in candidates:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return None


def _rescored(ep: dict) -> dict:
    """A cached episode dict with its composite re-derived against CONFIG.

    The composite is DERIVED — a weighted sum over raw metrics — but the cache
    stores the value as it stood when the episode was analysed. Publishing the
    stored copy means publishing a score under ceilings and weights that are no
    longer in force, which is exactly what happened when the ceilings were
    retuned on 2026-08-14: the index said 0.2654 for an episode whose cache
    file, and therefore this site, still said 0.2241.

    `analyzer.cache.load_scored()` is the sanctioned reader and the same
    mistake had already been fixed in four other places; this was the fifth,
    and the only one that PUBLISHES. Mirrors load_scored for a dict already in
    hand, so no second implementation of the derivation exists here.
    """
    if ep.get("status") != "ok":
        return ep
    try:
        from analyzer.metrics_sensory import rescore_episode
        from analyzer.schema import EpisodeResult
        return rescore_episode(EpisodeResult.from_dict(ep), CONFIG).to_dict()
    except Exception:
        return ep


def _find_episodes(show_key: str) -> list[dict]:
    d = ROOT / ".analysis" / show_key
    if not d.exists():
        return []
    results = []
    for f in sorted(d.glob("*.json")):
        if f.stem == "aggregate":
            continue
        try:
            ep = json.loads(f.read_text(encoding="utf-8"))
            if ep.get("status") == "ok":
                results.append(_rescored(ep))
        except Exception:
            pass
    return results


def _stat(agg: dict, key: str, sub: str = "mean") -> float | None:
    try:
        val = agg[key][sub]
        return float(val) if val is not None else None
    except (KeyError, TypeError, ValueError):
        return None


def _fmt(val: float | None, decimals: int = 3) -> str:
    if val is None:
        return "—"
    return f"{val:.{decimals}f}"


# ── Language / SRT helpers ────────────────────────────────────────────────────

_STOP_WORDS = {
    "a","an","the","and","or","but","in","on","at","to","for","of","with",
    "is","it","its","was","are","were","be","been","being","have","has","had",
    "do","does","did","will","would","could","should","may","might","shall",
    "i","you","he","she","we","they","me","him","her","us","them","my","your",
    "his","our","their","this","that","these","those","what","which","who",
    "not","no","so","up","out","if","as","just","now","then","there","here",
    "yes","oh","um","uh","like","well","okay","ok",
}

_TS_RE = re.compile(
    r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)"
)


def _srt_to_ms(h, m, s, ms):
    return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms)


def _parse_srt(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    blocks = re.split(r"\n\s*\n", text.strip())
    all_words: list[str] = []
    last_end_ms = 0

    for block in blocks:
        lines = block.strip().splitlines()
        ts_line = next((l for l in lines if "-->" in l), None)
        if not ts_line:
            continue
        m = _TS_RE.search(ts_line)
        if m:
            last_end_ms = max(last_end_ms, _srt_to_ms(*m.groups()[4:]))
        ts_idx = lines.index(ts_line)
        for line in lines[ts_idx + 1:]:
            clean = re.sub(r"<[^>]+>", "", line)
            all_words.extend(re.findall(r"\b[a-zA-Z']+\b", clean.lower()))

    if not all_words or last_end_ms == 0:
        return None

    duration_min = last_end_ms / 60_000
    total        = len(all_words)
    unique       = set(all_words)
    content      = [w for w in all_words if w not in _STOP_WORDS]

    return {
        "wpm":          total / duration_min,
        "ttr":          len(unique) / total,
        "unique_words": len(unique),
        "total_words":  total,
        "lexical_density": len(content) / total if total else 0,
        "duration_min": duration_min,
        "stem":         path.stem,
    }


def _show_language_metrics(show_key: str) -> dict | None:
    """Aggregate language metrics from all SRT files found for a show."""
    show_dir = ROOT / "Shows" / show_key
    if not show_dir.exists():
        return None
    srts = sorted(show_dir.rglob("*.srt"))
    if not srts:
        return None

    episodes = [m for s in srts if (m := _parse_srt(s)) is not None]
    if not episodes:
        return None

    n = len(episodes)

    def _mean(key):
        return sum(e[key] for e in episodes) / n

    return {
        "episode_count": n,
        "wpm_mean":       _mean("wpm"),
        "ttr_mean":       _mean("ttr"),
        "unique_mean":    _mean("unique_words"),
        "lex_den_mean":   _mean("lexical_density"),
        "episodes":       episodes,
    }


def _badge(score: float | None) -> str:
    if score is None:
        return "—"
    cls = "badge-lo" if score < 0.33 else "badge-md" if score < 0.40 else "badge-hi"
    return f'<span class="badge {cls}">{score:.3f}</span>'


# ── HTML shell ───────────────────────────────────────────────────────────────

_NAV = [
    ("Home",          "",             "home"),
    ("Browse shows",  "/shows/",      "shows"),
    ("For Parents",   "/for-parents/","for-parents"),
    ("Methodology",   "/methodology/","methodology"),
    ("The tool",      "/tool/",       "tool"),
    ("Download data", "/download/",   "download"),
]


def _p(path: str) -> str:
    """Prepend BASE_PATH to an internal path."""
    return f"{BASE_PATH}{path}"


def _page(title: str, body: str, active: str = "") -> str:
    nav = " ".join(
        f'<a href="{_p(href)}"{" class=active" if tag == active else ""}>{label}</a>'
        for label, href, tag in _NAV
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Open Children's Media Index</title>
<link rel="stylesheet" href="{_p("/static/style.css")}">
<script src="{_p("/static/sort.js")}" defer></script>
<script src="{_p("/static/preset.js")}" defer></script>
</head>
<body>
<div class="site">
<header>
  <div class="site-name"><a href="{_p("")}/">Open Children's Media Index</a></div>
  <nav>{nav}</nav>
</header>
<main>
{body}
</main>
<footer>
  Open Children's Media Index &nbsp;&middot;&nbsp;
  Data and code on <a href="{REPO_URL}">GitHub</a> &nbsp;&middot;&nbsp;
  Built with <a href="{TOOL_URL}">CMAT</a> &nbsp;&middot;&nbsp;
  Updated {TODAY}
</footer>
</div>
</body>
</html>"""


# ── Homepage ─────────────────────────────────────────────────────────────────

def _show_row(entry: dict, agg: dict | None, is_baseline: bool = False) -> str:
    name  = entry["display_name"]
    slug  = slugify(name)
    score = _stat(agg, "sensory_load_score") if agg else None

    if not is_baseline:
        col2 = entry.get("audience_label", "—")
        col3 = entry.get("network", "—")
    else:
        col2 = entry.get("genre", "—")
        col3 = entry.get("platform") or entry.get("network", "—")

    ep_count  = agg["episode_count"] if agg else "—"
    no_data   = agg is None
    score_std = _stat(agg, "sensory_load_score", "std") if agg else None
    high_var  = score_std is not None and score_std > VARIANCE_FLAG_THRESHOLD
    flag      = ' <span class="var-flag" title="High within-show variability (score std dev {:.3f}). Aggregate reflects sampled episodes; individual episodes may differ meaningfully.">†</span>'.format(score_std) if high_var else ""

    cells = [
        f'<td><a href="{_p(f"/shows/{slug}/")}">{name}</a>{flag}{"<br><span class=tbl-note>no data yet</span>" if no_data else ""}</td>',
        f'<td>{col2}</td>',
        f'<td>{col3}</td>',
        f'<td class="num">{ep_count}</td>',
        f'<td class="num score-cell">{_badge(score)}</td>',
        f'<td class="num">{_fmt(_stat(agg, "cuts_per_min"), 1) if agg else "—"}</td>',
        f'<td class="num">{_fmt(_stat(agg, "color_saturation_mean")) if agg else "—"}</td>',
        f'<td class="num">{_fmt(_stat(agg, "motion_mean"), 4) if agg else "—"}</td>',
        f'<td class="num">{_fmt(_stat(agg, "flashing_events_per_min"), 1) if agg else "—"}</td>',
    ]
    row_class = "baseline-row" if is_baseline else ""
    return f'<tr data-slug="{slug}"{f" class={row_class}" if row_class else ""}>{"".join(cells)}</tr>'


def _build_lang_table(children: list[tuple], lang_data: dict) -> str:
    rows = ""
    for entry, _ in children:
        ld = lang_data.get(entry["show_key"])
        if not ld:
            continue
        slug = slugify(entry["display_name"])
        rows += (
            f'<tr>'
            f'<td><a href="{_p(f"/shows/{slug}/")}">{entry["display_name"]}</a></td>'
            f'<td class=num>{ld["episode_count"]}</td>'
            f'<td class=num>{_fmt(ld["wpm_mean"], 1)}</td>'
            f'<td class=num>{_fmt(ld["ttr_mean"], 3)}</td>'
            f'<td class=num>{_fmt(ld["lex_den_mean"], 3)}</td>'
            f'<td class=num>{int(ld["unique_mean"])}</td>'
            f'</tr>'
        )
    if not rows:
        return "<p class=tbl-note>No transcript data available yet.</p>"
    return (
        "<table>"
        "<thead><tr>"
        "<th>Show</th>"
        "<th class=num>Transcripts</th>"
        "<th class=num>WPM</th>"
        "<th class=num>TTR</th>"
        "<th class=num>Lexical density</th>"
        "<th class=num>Unique words / ep</th>"
        "</tr></thead>"
        f"<tbody>{rows}</tbody>"
        "</table>"
    )


def _build_events_home_table(children: list[tuple]) -> str:
    """Homepage table of human-coded fantastical-event rates (only shows with
    published data; empty string when nothing is published yet)."""
    fe = MANUAL_CODING.get("fantastical_events", {})
    rows = ""
    for entry, _agg in children:
        show_events = fe.get(entry["show_key"])
        if not show_events or not show_events.get("episodes"):
            continue
        ea = _events_aggregate(show_events)
        slug = slugify(entry["display_name"])
        rng = (f"{_fmt(ea['min'],2)}–{_fmt(ea['max'],2)}" if ea["n"] > 1 else "—")
        rows += (
            f'<tr><td><a href="{_p(f"/shows/{slug}/")}">{entry["display_name"]}</a></td>'
            f'<td class=num>{ea["n"]}</td>'
            f'<td class=num>{_fmt(ea["mean"], 2)}</td>'
            f'<td class=num>{rng}</td>'
            f'<td>{show_events.get("sampling_method","")}</td></tr>'
        )
    if not rows:
        return ""
    return f"""<h2>Fantastical events (human-coded)</h2>
<p class="tbl-note">Current research (see <a href="{_p("/methodology/")}#fantastical-events">Methodology</a>) points to <em>fantastical content</em> — impossible events like flying, teleporting, or transforming — as the feature most consistently associated with short-term effects on young children's executive function, more so than editing pace. Fantasy is a human judgment, so these are hand-coded by a trained coder, not computed from pixels. Only shows with published coding appear here.</p>
<table>
<thead><tr><th>Show</th><th class=num>Episodes coded</th><th class=num>Mean events/min</th><th class=num>Range</th><th>How episodes were chosen</th></tr></thead>
<tbody>{rows}</tbody>
</table>"""


def _build_homepage(shows_data: list[tuple], lang_data: dict) -> str:
    children  = [(e, a) for e, a in shows_data if e["category"] == "children"]
    baselines = [(e, a) for e, a in shows_data if e["category"] == "baseline"]

    total_eps   = sum(a["episode_count"] for _, a in children if a)
    total_shows = len(children)

    th = ("<th>Show</th><th>Audience</th><th>Network</th>"
          "<th class=num>Episodes analyzed</th><th class=num>Avg load</th>"
          "<th class=num>Cuts/min</th><th class=num>Saturation</th>"
          "<th class=num>Motion</th><th class=num>Flash/min</th>")

    children_rows = "\n".join(_show_row(e, a) for e, a in children)
    baseline_rows = "\n".join(_show_row(e, a, is_baseline=True) for e, a in baselines)

    # Embed raw show metrics for client-side recompute
    show_js_items = []
    for entry, agg in shows_data:
        if not agg:
            continue
        show_js_items.append({
            "slug":     slugify(entry["display_name"]),
            "pacing":   _stat(agg, "cuts_per_min"),
            "saturation": _stat(agg, "color_saturation_mean"),
            "contrast": _stat(agg, "color_contrast_mean"),
            "motion":   _stat(agg, "motion_mean"),
            "flashing": _stat(agg, "flashing_events_per_min"),
            "audio":    _stat(agg, "audio_rms_mean"),
        })
    show_js = json.dumps(show_js_items)

    # Embed preset configs
    preset_js = json.dumps({
        name: {
            "description": p.get("description", ""),
            "weights": p["sensory_load_weights"],
            "ranges":  p["normalization_reference_ranges"],
        }
        for name, p in CONFIG["presets"].items()
    })

    preset_options = "\n".join(
        f'<option value="{n}">{n}</option>'
        for n in CONFIG["presets"]
    ) + '\n<option value="Custom">Custom weights…</option>'

    metric_sliders = ""
    for key, label in [("pacing","Pacing (cuts/min)"), ("saturation","Color saturation"),
                       ("contrast","Color contrast"), ("motion","Motion"),
                       ("flashing","Flashing"), ("audio","Audio loudness")]:
        metric_sliders += (
            f'<div class="slider-row">'
            f'<label for="w-{key}">{label}</label>'
            f'<input type="range" id="w-{key}" min="0" max="1" step="0.05">'
            f'<span class="weight-val" id="w-{key}-val">—</span>'
            f'</div>'
        )

    return f"""<script>
window.SHOW_DATA = {show_js};
window.PRESET_DATA = {preset_js};
</script>

<h1>Open Children's Media Index</h1>
<p class="lead">A transparent database of formal-feature measurements for children's television — pacing, colour, motion, flashing and audio. Every metric is measurable, and every score shows its component parts. The composite that combines them is a configurable summary, not a validated construct.</p>
<p>This index applies the <a href="{TOOL_URL}">Children's Media Analysis Toolkit (CMAT)</a> to publicly available programming. Analysis is automated and reproducible. This project does not issue verdicts on appropriateness — it presents labeled measurements that researchers and caregivers can interpret in context. All findings are correlational.</p>

<div class="stats-row">
  <div class="stat"><span class="stat-n">{total_shows}</span><span class="stat-l">Shows indexed</span></div>
  <div class="stat"><span class="stat-n">{total_eps}</span><span class="stat-l">Episodes analyzed</span></div>
  <div class="stat"><span class="stat-n">7</span><span class="stat-l">Metrics per episode</span></div>
  <div class="stat"><span class="stat-n">{TODAY}</span><span class="stat-l">Last updated</span></div>
</div>

<h2>Children's programming</h2>
<div class="preset-bar">
  <label for="preset-select">Scoring preset:</label>
  <select id="preset-select">{preset_options}</select>
  <span class="preset-desc" id="preset-desc"></span>
</div>
<div class="custom-weights" id="custom-weights" style="display:none">
  <p class="tbl-note">Adjust weights (0–1). Scores update instantly in your browser. Normalization ranges are locked to the General / All Ages preset when in custom mode.</p>
  {metric_sliders}
</div>
<p class="tbl-note">Average FFC scores are configurable 0–1 composites. The displayed bands are descriptive reference bands, not normative recommendations or viewer-effect thresholds.</p>
<table>
<thead><tr>{th}</tr></thead>
<tbody>{children_rows}</tbody>
</table>
<p class="tbl-note var-note">† High within-show variability (FFC standard deviation &gt; {VARIANCE_FLAG_THRESHOLD}). Aggregate reflects the sampled episodes; individual episodes may differ meaningfully. See the show page for the full distribution.</p>

<h2>Comparison baselines</h2>
<p class="tbl-note">Included for cross-genre reference only. These titles are not children's programming and are not scored against child-audience presets.</p>
<table>
<thead><tr><th>Title</th><th>Genre</th><th>Platform</th><th class=num>Episodes analyzed</th><th class=num>Avg FFC</th><th class=num>Cuts/min</th><th class=num>Saturation</th><th class=num>Motion</th><th class=num>Flash/min</th></tr></thead>
<tbody>{baseline_rows}</tbody>
</table>
<p class="tbl-note var-note">† High within-show variability (FFC standard deviation &gt; {VARIANCE_FLAG_THRESHOLD}).</p>

{_build_events_home_table(children)}

<h2>Language analytics</h2>
<p class="tbl-note">These figures describe how a show <em>uses language</em>, not how well a child will understand it. Comprehension depends on a child's age, vocabulary, and experience. The numbers come from automatic transcripts of each episode's dialogue (generated by OpenAI's Whisper speech-to-text model), so only shows with usable transcripts appear here.</p>
<ul class="metric-defs">
  <li><strong>WPM — words per minute.</strong> How fast the dialogue is spoken. Lower means slower, more deliberate speech. Typical children's shows land around 80–120 WPM; ordinary adult conversation runs 130–160 WPM.</li>
  <li><strong>TTR — type-token ratio (0–1).</strong> A measure of vocabulary variety: how many <em>different</em> words are used compared to the <em>total</em> words spoken. A show that repeats the same handful of words scores low; a show that keeps introducing new words scores higher. Children's shows commonly fall between about 0.20 and 0.45. (Longer episodes tend to score lower simply because common words keep recurring, so compare shows of similar length with care.)</li>
  <li><strong>Lexical density.</strong> The share of words that carry direct meaning — nouns, verbs, adjectives, adverbs — as opposed to connecting words like "the," "is," and "and." Higher means more information packed into each sentence. Casual conversation sits around 0.40–0.50; denser, more instructional speech runs higher.</li>
</ul>
{_build_lang_table(children, lang_data)}"""


# ── Show page ─────────────────────────────────────────────────────────────────

def _build_show_page(entry: dict, agg: dict | None, episodes: list[dict], lang: dict | None = None) -> str:
    name        = entry["display_name"]
    years       = entry.get("years", "")
    network     = entry.get("network") or entry.get("platform", "")
    is_baseline = entry["category"] == "baseline"
    note        = entry.get("note", "")

    # Metadata table
    rows = ""
    if not is_baseline:
        lbl = entry.get("audience_label", "")
        src = entry.get("audience_source", "")
        if lbl:
            rows += f'<tr><td>Target audience</td><td>{lbl}{f" <span class=source>({src})</span>" if src else ""}</td></tr>'
    else:
        genre = entry.get("genre", "")
        if genre:
            rows += f"<tr><td>Genre</td><td>{genre}</td></tr>"
    if network:
        rows += f"<tr><td>Network / platform</td><td>{network}</td></tr>"
    if years:
        rows += f"<tr><td>Production years</td><td>{years}</td></tr>"
    if agg:
        rows += f"<tr><td>Episodes analyzed</td><td>{agg['episode_count']}</td></tr>"
    meta_html = f"<table class=meta><tbody>{rows}</tbody></table>" if rows else ""

    # Era table
    era_html = ""
    if entry.get("sampling") == "era" and entry.get("eras"):
        era_rows = "".join(
            f'<tr><td>{era["name"]}</td><td>{era.get("years","")}</td>'
            f'<td>{era.get("seasons","")}</td>'
            f'<td class=muted>{era.get("status","")}</td></tr>'
            for era in entry["eras"]
        )
        era_html = (
            "<h2>Eras</h2>"
            "<table><thead><tr><th>Era</th><th>Years</th><th>Seasons</th><th>Status</th></tr></thead>"
            f"<tbody>{era_rows}</tbody></table>"
        )

    # Aggregate metrics
    agg_html = ""
    if agg:
        def _row(label: str, key: str, dec: int = 3) -> str:
            return (f"<tr><td>{label}</td>"
                    f'<td class=num>{_fmt(_stat(agg, key), dec)}</td>'
                    f'<td class=num>{_fmt(_stat(agg, key, "median"), dec)}</td>'
                    f'<td class=num>{_fmt(_stat(agg, key, "std"), dec)}</td></tr>')

        score = _stat(agg, "sensory_load_score")
        agg_html = (
            f"<h2>Aggregate metrics</h2>"
            f"<p>Based on {agg['episode_count']} episode(s). "
            f"FFC: {_badge(score)}</p>"
            "<table><thead><tr><th>Metric</th>"
            "<th class=num>Mean</th><th class=num>Median</th><th class=num>Std dev</th>"
            "</tr></thead><tbody>"
            + _row("Formal-Feature Composite (FFC)", "sensory_load_score")
            + _row("Cuts per minute",       "cuts_per_min", 1)
            + _row("Color saturation",      "color_saturation_mean")
            + _row("Color contrast",        "color_contrast_mean")
            + _row("Motion",                "motion_mean", 4)
            + _row("Flashing events / min", "flashing_events_per_min", 1)
            + _row("Audio RMS",             "audio_rms_mean", 4)
            + "</tbody></table>"
            # The accuracy claim comes from analyzer/provenance.py, which its
            # own docstring calls "the single source of truth for CMAT's
            # self-reported accuracy, shown on every results view, export, and
            # the public site". It was not: this paragraph hard-coded a THIRD
            # variant of the F1 figure (~0.84 to ~0.96) that contradicts the
            # constants CLAUDE.md and ARCHITECTURE.md quote, and repeated the
            # claim that flashing is a deterministic measurement needing no
            # validation — which the measurement registry contradicts. Both
            # were being published. Reading the statement means the site
            # follows automatically. Settled 2026-08-14: the hard-coded
            # ~0.84-0.96 was the hard_cut-type-only basis for the same two
            # runs; the published basis is the ALL row, F1 0.85 (0.75-0.91).
            # The site now emits that via validation_short(). Do not
            # reintroduce a literal figure here.
            + '<p class="tbl-note"><strong>Unlike black-box tools, CMAT '
              'measures its own error rate against human coding.</strong> '
              'That validation is currently a small, single-coder pilot, so '
              'treat the figures as indicative, not settled. '
            # validation_short() opens with its own "Detection accuracy
            # (preliminary):" heading, so the lead-in above deliberately does
            # not repeat it.
            + html.escape(validation_short(), quote=False)
            + f' See <a href="{_p("/methodology/")}">Methodology</a>.</p>'
        )

    # Episode table
    ep_html = ""
    if episodes:
        ep_rows = ""
        for ep in episodes:
            m   = ep.get("metrics", {})
            sl  = m.get("sensory_load", {}).get("score")
            cpm = m.get("scene_pacing", {}).get("cuts_per_min")
            sat = m.get("color_saturation", {}).get("mean")
            mot = m.get("motion", {}).get("mean")
            fla = m.get("flashing", {}).get("luminance_delta_events_per_min")
            air = ep.get("air_date") or ""
            fname = Path(ep.get("file", "")).stem
            ep_rows += (
                f"<tr><td>{fname}</td>"
                f'<td class=num>{air}</td>'
                f'<td class=num>{_badge(sl)}</td>'
                f'<td class=num>{_fmt(cpm, 1)}</td>'
                f'<td class=num>{_fmt(sat)}</td>'
                f'<td class=num>{_fmt(mot, 4)}</td>'
                f'<td class=num>{_fmt(fla, 1)}</td>'
                "</tr>"
            )
        ep_html = (
            "<h2>Episodes</h2>"
            "<table><thead><tr>"
            "<th>Episode</th><th class=num>Air date</th><th class=num>Load</th>"
            "<th class=num>Cuts/min</th><th class=num>Saturation</th>"
            "<th class=num>Motion</th><th class=num>Flash/min</th>"
            f"</tr></thead><tbody>{ep_rows}</tbody></table>"
        )

    note_html = f'<p class="show-note">{note}</p>' if note else ""

    # Language analytics section
    lang_html = ""
    if lang:
        ep_lang_rows = ""
        for ep in sorted(lang["episodes"], key=lambda e: e["stem"]):
            ep_lang_rows += (
                f'<tr><td>{ep["stem"]}</td>'
                f'<td class=num>{_fmt(ep["wpm"], 1)}</td>'
                f'<td class=num>{_fmt(ep["ttr"], 3)}</td>'
                f'<td class=num>{_fmt(ep["lexical_density"], 3)}</td>'
                f'<td class=num>{ep["unique_words"]}</td>'
                f'<td class=num>{ep["total_words"]}</td>'
                f'</tr>'
            )
        lang_html = (
            f"<h2>Language analytics</h2>"
            f"<p>Based on {lang['episode_count']} Whisper SRT transcript(s). "
            f"Mean WPM: {_fmt(lang['wpm_mean'], 1)} &nbsp; "
            f"Mean TTR: {_fmt(lang['ttr_mean'], 3)} &nbsp; "
            f"Mean lexical density: {_fmt(lang['lex_den_mean'], 3)}</p>"
            "<table><thead><tr>"
            "<th>Episode</th><th class=num>WPM</th><th class=num>TTR</th>"
            "<th class=num>Lex. density</th><th class=num>Unique words</th><th class=num>Total words</th>"
            f"</tr></thead><tbody>{ep_lang_rows}</tbody></table>"
        )

    # Human-coded fantastical events section (published via code_events.py publish)
    events_html = ""
    show_events = MANUAL_CODING.get("fantastical_events", {}).get(entry["show_key"])
    if show_events and show_events.get("episodes"):
        ea = _events_aggregate(show_events)
        ev_rows = ""
        for ep in show_events["episodes"]:
            win = (f'{ep["window"][0]}–{ep["window"][1]}'
                   if ep.get("window") else "full episode")
            ev_rows += (
                f'<tr><td>{ep["episode"]}</td>'
                f'<td class=num>{win}</td>'
                f'<td class=num>{ep["n_events"]}</td>'
                f'<td class=num>{_fmt(ep["events_per_min"], 2)}</td>'
                f'<td class=num>{_fmt(ep.get("pct_integral"), 2)}</td>'
                f'</tr>'
            )
        rng = (f" (range {_fmt(ea['min'],2)}–{_fmt(ea['max'],2)})"
               if ea["n"] > 1 else "")
        events_html = (
            f"<h2>Fantastical events (human-coded)</h2>"
            f"<p><strong>Mean {_fmt(ea['mean'],2)} fantastical events per minute</strong> "
            f"across {ea['n']} hand-coded episode(s){rng}.</p>"
            f'<p class="tbl-note"><strong>Episode selection:</strong> '
            f'{show_events.get("sampling_method","not documented")}<br>'
            f'<strong>Coding:</strong> {show_events.get("coder","")} using the '
            f'<a href="{TOOL_URL}">CMAT</a> fantastical-event codebook. '
            f'Unlike the automated metrics above, these are human judgments — '
            f'fantasy is a semantic property no pixel measure can detect. '
            f'See <a href="{_p("/methodology/")}#fantastical-events">Methodology</a> '
            f'for the event definition and coding rules.</p>'
            "<table><thead><tr>"
            "<th>Episode</th><th class=num>Coded window</th>"
            "<th class=num>Events</th><th class=num>Events/min</th>"
            "<th class=num>Integral fraction</th>"
            f"</tr></thead><tbody>{ev_rows}</tbody></table>"
        )

    return f"""<h1>{name}</h1>
{note_html}
{meta_html}
{era_html}
{agg_html}
{ep_html}
{lang_html}
{events_html}"""


# ── Static pages ─────────────────────────────────────────────────────────────

_METHODOLOGY = """<h1>Methodology</h1>
<p class="lead">All analysis is performed by the <a href="https://github.com/SamuelBabbertResearch/childrens-media-analysis-toolkit">Children's Media Analysis Toolkit (CMAT)</a>, an open-source Python application. Every result in this index is reproducible from the source video files using the parameters documented here.</p>

<h2>Sampling protocol</h2>
<p>The following parameters are held constant across all shows to ensure cross-show comparability:</p>
<table class=meta><tbody>
<tr><td>Frame sample rate</td><td>2 fps</td></tr>
<tr><td>FFC configuration</td><td>General / All Ages</td></tr>
<tr><td>Flashing threshold</td><td>0.1 (luminance delta, 0–1 scale)</td></tr>
<tr><td>Episode sample seed</td><td>42</td></tr>
</tbody></table>

<h2>Normalization ceilings</h2>
<p>Each component metric is rescaled to 0–1 against a fixed ceiling before it is
weighted, using <code>(value − min) / (max − min)</code>, clamped into [0, 1]. A
ceiling is the <em>denominator</em> that makes six differently-shaped numbers
addable — it is not a threshold, a limit, or a judgement about the content.
Values at or above a ceiling all score 1.0 and are not distinguished from each
other. The composite is not reproducible without these, so they are stated
here:</p>
__CEILINGS_TABLE__
<p>These values are a <strong>scaling convention, not a validated threshold.</strong>
They were set to span the range observed across the analysed corpus rather than
to each metric's theoretical maximum, and were last revised on 2026-08-14.
Because ceilings differ in how much of their range real content occupies, a
metric's nominal weight is not the same as its effective contribution to the
composite — the component figures are published for every episode so that both
can be checked. Composite scores computed before 2026-08-14 are on an earlier
scale and are not comparable with these.</p>
<p>For shows with fewer than 15 episodes, all episodes are analyzed. For shows with 15–60 episodes, a spread sample of 10 is drawn. For shows with more than 60 episodes, a spread sample of 20 is drawn. "Spread" is CMAT's own name for a design, not a standard statistical term: the ordered run is split into <em>n</em> contiguous, near-equal chunks and one episode is drawn uniformly at random from each — <em>stratified random sampling with equal-sized positional strata, one unit per stratum</em>. Inclusion probabilities are 1/chunk-size and are <strong>not equal across the run</strong> when the episode count does not divide evenly, so any estimate assuming equal probabilities will be biased. Each draw records its seed and its full candidate frame.</p>
<p>For long-running shows (20+ years or a significant production format change), the show is divided into named eras and each era is sampled independently.</p>

<h2>Metric definitions</h2>
<table>
<thead><tr><th>Metric</th><th>Method</th><th>Unit</th></tr></thead>
<tbody>
<tr><td>Shot-boundary rate<br><small>(labelled "scene pacing")</small></td><td>PySceneDetect ContentDetector at threshold 27 &rarr; boundaries per minute. <strong>Detected boundaries, not semantic scene changes</strong>: a cut inside one continuous scene counts. Frame-differencing misses gradual transitions by construction.</td><td>boundaries / min</td></tr>
<tr><td>Color saturation</td><td>Mean HSV S-channel per frame, averaged across frames sampled at 2 fps</td><td>0–1</td></tr>
<tr><td>Color contrast</td><td><strong>Spatial</strong> standard deviation of the HSV V-channel within each frame, averaged across sampled frames. Within-frame brightness spread, <strong>not a perceptual contrast metric</strong>.</td><td>0–1</td></tr>
<tr><td>Motion</td><td>Mean absolute grayscale difference between <strong>consecutive sampled</strong> frames, rescaled to 0–1. Measures <strong>image change, not depicted movement</strong> — a cut, a camera pan and a running character all raise it — and depends on the 2 fps sampling rate.</td><td>0–1</td></tr>
<tr><td>Flashing</td><td>Consecutive frames sampled at 10 fps whose <strong>whole-frame mean</strong> luminance differs by more than 0.1. <strong>Not a photosensitivity safety assessment</strong>; see below.</td><td>events / min</td></tr>
<tr><td>Audio intensity</td><td>Mean per-second <strong>RMS amplitude</strong> on the track downmixed to mono and <strong>resampled to 8 kHz</strong>. <strong>Linear amplitude, not perceptual loudness — not LUFS, not EBU R128.</strong> Two files mastered to the same broadcast loudness can differ here.</td><td>linear 0–1</td></tr>
<tr><td>Formal-Feature Composite (FFC)</td><td>Configurable composite of observable audio-visual production and editing features</td><td>0–1</td></tr>
</tbody>
</table>

<h2>Formal-Feature Composite (FFC)</h2>
<p>The FFC is a configurable weighted sum of normalized sub-metrics. Normalization uses fixed reference ranges — not per-corpus normalization — so scores remain comparable across separate analysis runs and future additions to the index. The "General / All Ages" configuration is used for all index entries. The FFC is not a validated measure of viewer sensory load, arousal, or developmental impact. Full weight and normalization configurations are available in the <a href="https://github.com/SamuelBabbertResearch/childrens-media-analysis-toolkit">CMAT repository</a>.</p>

<h2>Language metrics</h2>
<p>When closed-caption or subtitle files are available for an episode, CMAT extracts three language complexity measures from the dialogue text. These numbers describe how the show uses language — not how well children will understand it. Comprehension depends on the individual child's age, vocabulary, and language experience.</p>
<table>
<thead><tr><th>Metric</th><th>What it measures</th><th>How to read it</th></tr></thead>
<tbody>
<tr>
  <td><strong>Mean WPM</strong><br><small>(Words Per Minute)</small></td>
  <td>How quickly dialogue is spoken, averaged across the episode. Calculated from the timing information in the subtitle file.</td>
  <td>Lower numbers mean slower, more deliberate speech. A typical children's show falls in the 80–120&nbsp;WPM range; adult conversation is typically 130–160&nbsp;WPM. <em>Example: 95.7&nbsp;WPM is a relaxed, easy-to-follow pace.</em></td>
</tr>
<tr>
  <td><strong>Mean TTR</strong><br><small>(Type-Token Ratio)</small></td>
  <td>Vocabulary variety — the ratio of unique words (types) to total words spoken (tokens). Computed per episode then averaged.</td>
  <td>A TTR of 1.0 would mean every word is different; a TTR near 0 means the same words repeat constantly. Children's shows typically range from 0.20 to 0.45. <em>Example: a TTR of 0.277 indicates moderate repetition — new words appear regularly alongside familiar core vocabulary.</em></td>
</tr>
<tr>
  <td><strong>Mean Lexical Density</strong></td>
  <td>The share of content words — nouns, verbs, adjectives, adverbs — out of all words spoken. Function words ("the," "is," "and") are not counted.</td>
  <td>Higher density means more information packed into each sentence. Simple conversational speech sits around 0.40–0.50; information-rich narration can reach 0.65+. <em>Example: a lexical density of 0.585 means roughly 3 in every 5 words carry direct meaning — moderately dense for children's content.</em></td>
</tr>
</tbody>
</table>
<p>Language metrics require a subtitle or caption file (.srt or .vtt) for each episode. Episodes without captions show "Not available" for these fields. The metrics are derived from the caption text, which may differ slightly from the audio (simplified captioning, timing gaps, etc.).</p>

<h2 id="fantastical-events">Fantastical events (human-coded)</h2>
<p>Recent research has converged on <em>fantastical content</em> — rather than editing pace alone — as the program feature most consistently associated with short-term reductions in young children's executive function after viewing (Hinten, Scarf &amp; Imuta, 2025, <em>Developmental Science</em> meta-analysis; Lillard et al., 2015). A fantastical event is a discrete impossible occurrence: a character flying unaided, teleporting, transforming, an object coming to life. Following the literature, we report <strong>fantastical events per minute</strong>.</p>
<p>Fantasy is a semantic judgment — whether an event violates how the world works — and cannot be computed from pixels. These metrics are therefore <strong>hand-coded by a human coder</strong> using CMAT's structured event codebook: a seven-category event taxonomy (physical violations, transformations, continuity violations, impossible body events, object animacy, impossible causation, other), an explicit premise-vs-event rule (a standing impossible premise such as talking animals is not counted as events; discrete impossible occurrences are), and per-event properties (narrative relevance; repetition). The full codebook ships with the <a href="https://github.com/SamuelBabbertResearch/childrens-media-analysis-toolkit">open-source toolkit</a>.</p>
<p>Honest limitations: coded samples are small (per-episode windows chosen before viewing and documented alongside each show's numbers); coding is currently by a single coder (the toolkit supports two-coder inter-rater reliability, planned); the codebook is versioned and any rule change is logged. Event rates describe the <em>stimulus</em>, not any child's response, and are associated with — not proof of — effects on viewers.</p>

<h2>Flashing detection note</h2>
<p>The flashing metric measures whole-frame mean luminance change between sampled frames at 2 fps, with a detection ceiling of 1 transition per second. The medically relevant range for photosensitive epilepsy screening is 3–50 Hz. <strong>This metric is not a photosensitive epilepsy screen.</strong> A score of zero does not indicate safety; a non-zero score indicates detectable whole-frame brightness transitions useful for relative comparison across shows.</p>

<h2>Research grounding</h2>
<p>This index measures <em>formal features</em> of video — content-independent structural attributes of the presentation, such as how often the image cuts and how much it changes between frames. Huston &amp; Wright's formal-features framework and Lang's LC4MP motivate <em>measuring</em> these properties; they do not establish what any measured value does to a viewer, and nothing here observes a viewer at all. All associations reported in that literature are correlational.</p>
<ul>
<li>Huston &amp; Wright — formal features framework</li>
<li>Lang — Limited Capacity Model of Mediated Message Processing (LC4MP)</li>
<li>Lillard &amp; Peterson (2011), <em>Pediatrics</em> — pacing and executive function in 4-year-olds</li>
<li>Lillard et al. (2015) — fantastical content as a possible moderator</li>
<li>Christakis et al. (2004), <em>Pediatrics</em> — early TV exposure and attention (correlational)</li>
<li>Itti &amp; Koch — bottom-up visual saliency and motion</li>
</ul>
<p><strong>All findings are correlational.</strong> This tool measures the stimulus, not the viewer. Age, temperament, sensory-processing profile, and viewing dose are not captured.</p>"""


_TOOL = """<h1>The tool</h1>
<p class="lead">The Open Children's Media Index is built with the <strong>Children's Media Analysis Toolkit (CMAT)</strong>, an open-source desktop application for analyzing formal features of video content.</p>
<p>CMAT is a Windows desktop application that analyzes MP4 episodes of television shows and produces a formal-feature profile for each episode and a cumulative profile for an entire show. It measures formal and structural features of video — pacing, color, motion, audio — and does not issue a verdict on appropriateness. Its optional Formal-Feature Composite (FFC) displays its component parts and is not a viewer-effect measure.</p>
<p>Source code, installation instructions, and full documentation:<br>
<a href="https://github.com/SamuelBabbertResearch/childrens-media-analysis-toolkit">github.com/SamuelBabbertResearch/childrens-media-analysis-toolkit</a></p>

<h2>How data enters this index</h2>
<ol>
<li>Video files are analyzed locally using CMAT with the parameters documented in <a href="/methodology/">Methodology</a>.</li>
<li>Results are reviewed manually before publication. No data is published automatically.</li>
<li>The site is regenerated from the reviewed cache and pushed to GitHub Pages.</li>
</ol>
<p>This manual review step is intentional. It catches episodes that failed to decode, were mislabeled, or are not the programme the filename claims, before their numbers reach the public index. It is a data-quality check on the measurement, not a judgement about the programme.</p>

<h2>Reproducing the analysis</h2>
<ol>
<li>Install CMAT from the GitHub repository above.</li>
<li>Obtain the same source video files.</li>
<li>Run analysis with the parameters documented in <a href="/methodology/">Methodology</a>.</li>
</ol>
<p>Per-episode JSON results and show-level aggregate CSVs are available on the <a href="/download/">Download data</a> page.</p>"""


def _build_download(shows_data: list[tuple]) -> str:
    rows = ""
    for entry, agg in shows_data:
        if not agg:
            continue
        slug     = slugify(entry["display_name"])
        ep_count = agg.get("episode_count", "—")
        rows += (
            f'<tr><td>{entry["display_name"]}</td>'
            f'<td class=num>{ep_count}</td>'
            f'<td><a href="{_p(f"/data/{slug}/aggregate.json")}">aggregate.json</a>'
            f' &nbsp; <a href="{_p(f"/data/{slug}/aggregate.csv")}">aggregate.csv</a></td></tr>'
        )

    return f"""<h1>Download data</h1>
<p>Per-episode JSON results and show-level aggregate statistics are freely available for research use. All data is derived from CMAT analysis; see <a href="/methodology/">Methodology</a> for parameters and reproducibility details.</p>
<p>The complete dataset as a single flat file: <a href="{_p("/data/index.json")}">index.json</a> (all shows, aggregate metrics only).</p>

<h2>By show</h2>
<table>
<thead><tr><th>Show</th><th class=num>Episodes</th><th>Files</th></tr></thead>
<tbody>{rows}</tbody>
</table>

<h2>Citation</h2>
<p>Babbert, S. ({date.today().year}). <em>Open Children's Media Index</em>. Retrieved from https://{DOMAIN}</p>

<h2>License</h2>
<p>All metric data is released under <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. Source video files are not distributed by this project.</p>"""


# ── CSS ───────────────────────────────────────────────────────────────────────

CSS = """\
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: Georgia, 'Times New Roman', serif;
  font-size: 15px;
  line-height: 1.65;
  color: #202020;
  background: #faf9f6;
}

.site { max-width: 860px; margin: 0 auto; padding: 0 16px; }

/* ── Header ── */
header {
  border-bottom: 1px solid #c8c8c0;
  padding: 14px 0 0;
  margin-bottom: 24px;
}
.site-name {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 17px;
  font-weight: bold;
  margin-bottom: 8px;
}
.site-name a { color: #202020; text-decoration: none; }
.site-name a:hover { text-decoration: underline; }

nav { font-family: Arial, Helvetica, sans-serif; font-size: 13px; }
nav a {
  display: inline-block;
  color: #0645ad;
  text-decoration: none;
  padding: 4px 10px 7px;
  border-bottom: 3px solid transparent;
  margin-bottom: -1px;
}
nav a:hover { color: #0b0080; text-decoration: underline; }
nav a.active { border-bottom-color: #202020; color: #202020; font-weight: bold; }

/* ── Typography ── */
main { padding-bottom: 40px; }

h1 {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 22px;
  font-weight: bold;
  border-bottom: 1px solid #c8c8c0;
  padding-bottom: 6px;
  margin: 0 0 14px;
}
h2 {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 16px;
  font-weight: bold;
  border-bottom: 1px solid #ddd;
  padding-bottom: 3px;
  margin: 26px 0 10px;
}

p { margin-bottom: 10px; }
.lead { font-style: italic; color: #444; margin-bottom: 12px; }

ul, ol { margin: 0 0 10px 24px; }
li { margin-bottom: 4px; }

a { color: #0645ad; }
a:hover { color: #0b0080; }

/* ── Stats row ── */
.stats-row {
  display: flex;
  border: 1px solid #c8c8c0;
  margin: 16px 0 20px;
  font-family: Arial, Helvetica, sans-serif;
}
.stat {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px 8px;
  border-right: 1px solid #c8c8c0;
}
.stat:last-child { border-right: none; }
.stat-n { font-size: 20px; font-weight: bold; line-height: 1.2; }
.stat-l {
  font-size: 11px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-top: 3px;
}

/* ── Tables ── */
table {
  border-collapse: collapse;
  width: 100%;
  font-family: Arial, Helvetica, sans-serif;
  font-size: 13px;
  margin-bottom: 10px;
}
th {
  background: #f0efe8;
  border: 1px solid #c8c8c0;
  padding: 5px 8px;
  text-align: left;
  font-weight: bold;
  font-size: 12px;
  white-space: nowrap;
}
td {
  border: 1px solid #ddddd5;
  padding: 4px 8px;
  vertical-align: middle;
}
tr:nth-child(even) td { background: #f5f4f0; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }

table.meta { width: auto; margin-bottom: 16px; }
table.meta td:first-child {
  color: #555;
  font-style: italic;
  padding-right: 20px;
  white-space: nowrap;
  border-color: #ddd;
}
table.meta td { border-color: #ddd; }

tr.baseline-row td { color: #555; }

/* ── Badges ── */
.badge {
  display: inline-block;
  font-family: Arial, Helvetica, sans-serif;
  font-size: 12px;
  font-weight: bold;
  padding: 1px 6px;
}
.badge-lo { background: #d4edda; color: #155724; }
.badge-md { background: #fff3cd; color: #856404; }
.badge-hi { background: #f8d7da; color: #721c24; }

/* ── Misc ── */
.tbl-note {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 12px;
  color: #555;
  margin-bottom: 6px;
}
.metric-defs {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 12.5px;
  color: #444;
  line-height: 1.5;
  margin: 0 0 14px 0;
  padding-left: 20px;
}
.metric-defs li { margin-bottom: 6px; }
.metric-defs strong { color: #222; }
.show-note {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 13px;
  color: #666;
  font-style: italic;
  margin-bottom: 14px;
}
.source { color: #888; font-size: 12px; }
.muted  { color: #999; }

.var-flag {
  color: #856404;
  font-size: 11px;
  cursor: help;
  font-family: Arial, Helvetica, sans-serif;
}
.var-note { margin-top: 4px; }

/* ── Preset controls ── */
.preset-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  font-family: Arial, Helvetica, sans-serif;
  font-size: 13px;
}
.preset-bar label { color: #555; white-space: nowrap; }
.preset-bar select { font-size: 13px; padding: 2px 5px; }
.preset-desc { color: #888; font-style: italic; font-size: 12px; }

.custom-weights {
  border: 1px solid #c8c8c0;
  background: #f5f4f0;
  padding: 10px 14px 6px;
  margin-bottom: 10px;
  font-family: Arial, Helvetica, sans-serif;
  font-size: 13px;
}
.slider-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 5px;
}
.slider-row label {
  width: 170px;
  color: #444;
  flex-shrink: 0;
}
.slider-row input[type=range] { flex: 1; max-width: 220px; }
.weight-val {
  font-family: monospace;
  font-weight: bold;
  font-size: 12px;
  min-width: 32px;
  text-align: right;
}

/* ── Footer ── */
footer {
  border-top: 1px solid #c8c8c0;
  padding: 12px 0 28px;
  font-family: Arial, Helvetica, sans-serif;
  font-size: 12px;
  color: #666;
  margin-top: 24px;
}
"""


# ── Sort JS ──────────────────────────────────────────────────────────────────

JS = """\
(function () {
  function cellVal(row, idx) {
    // Use data-val if present (strips badge text), else raw textContent
    var td = row.children[idx];
    return td ? (td.dataset.val !== undefined ? td.dataset.val : td.textContent.trim()) : "";
  }

  function sortTable(th) {
    var table = th.closest("table");
    var tbody = table.querySelector("tbody");
    if (!tbody) return;
    var rows = Array.from(tbody.querySelectorAll("tr"));
    var idx  = Array.from(th.parentNode.children).indexOf(th);
    var isNum = th.classList.contains("num");
    var asc  = th.dataset.sort !== "asc";

    // Reset all headers in this table
    table.querySelectorAll("thead th").forEach(function (h) {
      h.dataset.sort = "";
      h.querySelector(".sort-arrow") && (h.querySelector(".sort-arrow").textContent = "");
    });

    th.dataset.sort = asc ? "asc" : "desc";
    var arrow = th.querySelector(".sort-arrow");
    if (arrow) arrow.textContent = asc ? " \\u25b2" : " \\u25bc";

    rows.sort(function (a, b) {
      var av = cellVal(a, idx);
      var bv = cellVal(b, idx);
      if (isNum) {
        var an = parseFloat(av);
        var bn = parseFloat(bv);
        an = isNaN(an) ? (asc ? Infinity : -Infinity) : an;
        bn = isNaN(bn) ? (asc ? Infinity : -Infinity) : bn;
        return asc ? an - bn : bn - an;
      }
      return asc ? av.localeCompare(bv) : bv.localeCompare(av);
    });

    rows.forEach(function (r) { tbody.appendChild(r); });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("table thead th").forEach(function (th) {
      th.style.cursor = "pointer";
      th.style.userSelect = "none";
      var arrow = document.createElement("span");
      arrow.className = "sort-arrow";
      th.appendChild(arrow);
      th.addEventListener("click", function () { sortTable(th); });
    });

    // Stamp data-val on badge cells so sort uses the numeric value
    document.querySelectorAll("td.num .badge").forEach(function (badge) {
      badge.parentElement.dataset.val = badge.textContent.trim();
    });
  });
})();
"""

# ── Preset JS ────────────────────────────────────────────────────────────────

PRESET_JS = """\
(function () {
  var METRICS = ["pacing","saturation","contrast","motion","flashing","audio"];

  function norm(val, max) {
    if (val === null || val === undefined || max === 0) return 0;
    return Math.min(1, Math.max(0, val / max));
  }

  function badge(score) {
    var cls = score < 0.33 ? "badge-lo" : score < 0.40 ? "badge-md" : "badge-hi";
    return '<span class="badge ' + cls + '">' + score.toFixed(3) + '</span>';
  }

  function recompute() {
    var shows  = window.SHOW_DATA;
    var presets = window.PRESET_DATA;
    if (!shows || !presets) return;

    var name = document.getElementById("preset-select").value;
    var isCustom = (name === "Custom");
    var ranges = isCustom
      ? presets["General / All Ages"].ranges
      : presets[name].ranges;

    var weights = {};
    METRICS.forEach(function (k) {
      var el = document.getElementById("w-" + k);
      weights[k] = el ? parseFloat(el.value) : 0;
    });

    shows.forEach(function (show) {
      var score =
        weights.pacing     * norm(show.pacing,     ranges.cuts_per_min.max) +
        weights.saturation * norm(show.saturation, ranges.color_saturation_mean.max) +
        weights.contrast   * norm(show.contrast,   ranges.color_contrast_mean.max) +
        weights.motion     * norm(show.motion,      ranges.motion_mean.max) +
        weights.flashing   * norm(show.flashing,    ranges.flashing_events_per_min.max) +
        weights.audio      * norm(show.audio,       ranges.audio_rms_mean.max);

      var row = document.querySelector('tr[data-slug="' + show.slug + '"]');
      if (!row) return;
      var cell = row.querySelector(".score-cell");
      if (!cell) return;
      cell.innerHTML = badge(score);
      cell.dataset.val = score.toFixed(3);
    });
  }

  function loadPreset(name) {
    var presets = window.PRESET_DATA;
    if (!presets || !presets[name]) return;
    var p = presets[name];
    METRICS.forEach(function (k) {
      var el  = document.getElementById("w-" + k);
      var val = p.weights[k] !== undefined ? p.weights[k] : 0;
      if (el) el.value = val;
      var lbl = document.getElementById("w-" + k + "-val");
      if (lbl) lbl.textContent = val.toFixed(2);
    });
    var desc = document.getElementById("preset-desc");
    if (desc) desc.textContent = p.description || "";
  }

  function onPresetChange() {
    var name = document.getElementById("preset-select").value;
    var cw = document.getElementById("custom-weights");
    if (name === "Custom") {
      if (cw) cw.style.display = "";
    } else {
      if (cw) cw.style.display = "none";
      loadPreset(name);
    }
    recompute();
  }

  function onWeightChange(key) {
    var el  = document.getElementById("w-" + key);
    var lbl = document.getElementById("w-" + key + "-val");
    if (el && lbl) lbl.textContent = parseFloat(el.value).toFixed(2);
    var sel = document.getElementById("preset-select");
    if (sel) sel.value = "Custom";
    var cw = document.getElementById("custom-weights");
    if (cw) cw.style.display = "";
    recompute();
  }

  document.addEventListener("DOMContentLoaded", function () {
    var sel = document.getElementById("preset-select");
    if (!sel) return; // not on homepage

    sel.addEventListener("change", onPresetChange);

    METRICS.forEach(function (k) {
      var el = document.getElementById("w-" + k);
      if (el) el.addEventListener("input", function () { onWeightChange(k); });
    });

    // Initialize with General / All Ages
    sel.value = "General / All Ages";
    onPresetChange();
  });
})();
"""


# ── Build ─────────────────────────────────────────────────────────────────────

def _clear_site(path: Path) -> None:
    """Delete all non-.git content inside path so the git repo is preserved."""
    def _on_error(func, fpath, _exc):
        os.chmod(fpath, stat.S_IWRITE)
        func(fpath)
    for child in path.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child, onerror=_on_error)
        else:
            child.unlink()


def _build_for_parents(shows_data: list[tuple]) -> str:
    """Build the FFC-ordered episode table for the public site."""

    # Collect every episode from children's shows only
    rows: list[dict] = []
    for entry, agg in shows_data:
        if entry.get("category") != "children":
            continue
        show_key_val = entry["show_key"]
        display      = entry["display_name"]
        slug         = slugify(display)
        for ep in _find_episodes(show_key_val):
            score = ep.get("metrics", {}).get("sensory_load", {}).get("score")
            if score is None:
                continue
            # Derive a clean episode title from the filename
            stem = ep.get("file", "")
            stem = re.sub(r"\.(mp4|mkv|avi|mov)$", "", stem, flags=re.IGNORECASE)
            rows.append({
                "show":    display,
                "show_url": _p(f"/shows/{slug}/"),
                "title":   stem,
                "score":   score,
            })

    rows.sort(key=lambda r: r["score"])
    top = rows[:50]  # show the 50 lowest FFC scores

    if not top:
        table = "<p>No episode data available yet.</p>"
    else:
        def _row(i: int, r: dict) -> str:
            b = _badge(r["score"])
            show_link = f'<a href="{r["show_url"]}">{r["show"]}</a>'
            title = r["title"]
            if len(title) > 70:
                title = title[:69] + "…"
            return (
                f'<tr>'
                f'<td style="text-align:center;color:#888">{i}</td>'
                f'<td>{show_link}</td>'
                f'<td>{title}</td>'
                f'<td class="score-cell" data-val="{r["score"]:.4f}">{b}</td>'
                f'</tr>'
            )

        thead = (
            '<thead><tr>'
            '<th style="width:2.5em">#</th>'
            '<th data-col="show">Show</th>'
            '<th data-col="title">Episode</th>'
            '<th data-col="score">FFC</th>'
            '</tr></thead>'
        )
        tbody = "\n".join(_row(i + 1, r) for i, r in enumerate(top))
        table = f'<table id="calm-table" class="idx-table">{thead}<tbody>{tbody}</tbody></table>'

    return f"""
<h1>For Parents — Episodes by FFC</h1>
<p style="max-width:680px;line-height:1.6">
  The table below lists the <strong>50 episodes with the lowest FFC scores</strong> observed across
  all children's shows in the dataset, scored under the
  <em>General&nbsp;/&nbsp;All&nbsp;Ages</em> preset. Lower scores reflect slower pacing,
  less motion, lower color saturation, fewer flashing events, and quieter audio.
  These are structural features of the video — not a recommendation or safety rating.
  Individual children respond differently based on age, temperament, and viewing history.
</p>
<p style="font-size:0.85em;color:#555;max-width:680px">
  <strong>Score key:</strong>
  <span class="badge badge-lo">0.00–0.32</span> lower FFC &nbsp;
  <span class="badge badge-md">0.33–0.39</span> middle FFC &nbsp;
  <span class="badge badge-hi">0.40+</span> higher FFC
</p>
{table}
<p style="margin-top:2rem;font-size:0.82em;color:#666;max-width:640px">
  Scores are produced by the
  <a href="{TOOL_URL}">Children's Media Analysis Toolkit (CMAT)</a> and reflect a
  spread sample of episodes analyzed under consistent settings (seed&nbsp;42,
  sample_fps&nbsp;=&nbsp;2). Baseline shows (YouTube creators, adult animation) are
  excluded from this view. See <a href="{_p('/methodology/')}">Methodology</a> for
  full metric definitions.
</p>
"""


def build() -> None:
    _sync_manifest()

    if SITE.exists():
        _clear_site(SITE)
    SITE.mkdir(parents=True, exist_ok=True)
    for sub in ("shows", "static", "data", "methodology", "tool", "download", "for-parents"):
        (SITE / sub).mkdir(exist_ok=True)

    (SITE / "static" / "style.css").write_text(CSS, encoding="utf-8")
    (SITE / "static" / "sort.js").write_text(JS, encoding="utf-8")
    (SITE / "static" / "preset.js").write_text(PRESET_JS, encoding="utf-8")
    (SITE / "CNAME").write_text(f"{DOMAIN}\n", encoding="utf-8")

    # Load all show data
    shows_data: list[tuple[dict, dict | None]] = []
    for entry in MANIFEST["shows"]:
        agg = _find_aggregate(entry["show_key"])
        # The stored aggregate carries a composite averaged under whatever
        # ceilings were in force when it was written. Recompute it from the
        # re-scored episodes so the show page and its episode table cannot
        # disagree — the same staleness as the per-episode score, one level up.
        episodes = _find_episodes(entry["show_key"])
        if episodes:
            try:
                from analyzer.aggregate import compute_show_aggregate
                from analyzer.schema import EpisodeResult
                agg = compute_show_aggregate(
                    entry["display_name"],
                    [EpisodeResult.from_dict(e) for e in episodes]).to_dict()
            except Exception as exc:
                print(f"  [warn] could not recompute aggregate for "
                      f"{entry['show_key']}: {exc}")
        shows_data.append((entry, agg))
        if agg is None:
            print(f"  [warn] no aggregate found: {entry['show_key']}")

    # Language data (SRT-based, keyed by show_key)
    lang_data: dict[str, dict] = {}
    for entry in MANIFEST["shows"]:
        ld = _show_language_metrics(entry["show_key"])
        if ld:
            lang_data[entry["show_key"]] = ld
            print(f"  [lang] {entry['show_key']}: {ld['episode_count']} transcripts")

    # Homepage
    (SITE / "index.html").write_text(
        _page("Home", _build_homepage(shows_data, lang_data), active="home"),
        encoding="utf-8",
    )

    # Per-show pages + data exports
    for entry, agg in shows_data:
        slug     = slugify(entry["display_name"])
        episodes = _find_episodes(entry["show_key"])
        lang     = lang_data.get(entry["show_key"])
        show_dir = SITE / "shows" / slug
        show_dir.mkdir(exist_ok=True)
        (show_dir / "index.html").write_text(
            _page(entry["display_name"],
                  _build_show_page(entry, agg, episodes, lang),
                  active="shows"),
            encoding="utf-8",
        )
        if agg:
            data_dir = SITE / "data" / slug
            data_dir.mkdir(exist_ok=True)
            (data_dir / "aggregate.json").write_text(
                json.dumps(agg, indent=2), encoding="utf-8"
            )
            # Copy aggregate CSV if present
            csv_src = ROOT / ".analysis" / entry["show_key"] / "aggregate.csv"
            if csv_src.exists():
                shutil.copy(csv_src, data_dir / "aggregate.csv")

    # For Parents
    (SITE / "for-parents" / "index.html").write_text(
        _page("For Parents", _build_for_parents(shows_data), active="for-parents"),
        encoding="utf-8",
    )

    # Methodology / tool / download
    (SITE / "methodology" / "index.html").write_text(
        _page("Methodology", _methodology_html(), active="methodology"),
        encoding="utf-8",
    )
    (SITE / "tool" / "index.html").write_text(
        _page("The tool", _TOOL, active="tool"),
        encoding="utf-8",
    )
    (SITE / "download" / "index.html").write_text(
        _page("Download data", _build_download(shows_data), active="download"),
        encoding="utf-8",
    )

    # Master index.json
    index_data = [
        {
            "display_name":          e["display_name"],
            "category":              e["category"],
            "network":               e.get("network") or e.get("platform"),
            "years":                 e.get("years"),
            "audience_label":        e.get("audience_label"),
            "episode_count":         a["episode_count"] if a else None,
            "sensory_load_mean":     _stat(a, "sensory_load_score") if a else None,
            "cuts_per_min_mean":     _stat(a, "cuts_per_min") if a else None,
            "saturation_mean":       _stat(a, "color_saturation_mean") if a else None,
            "motion_mean":           _stat(a, "motion_mean") if a else None,
            "flashing_per_min_mean": _stat(a, "flashing_events_per_min") if a else None,
        }
        for e, a in shows_data
    ]
    (SITE / "data" / "index.json").write_text(
        json.dumps(index_data, indent=2), encoding="utf-8"
    )

    total = sum(1 for _ in SITE.rglob("*.html"))
    print(f"Built {total} HTML pages -> {SITE}/")
    print(f"CNAME set to: {DOMAIN}")


# Labels for the published ceilings table. Keys with no entry fall back to the
# raw metric name, so a metric added to the engine appears rather than vanishing.
_CEILING_LABEL = {
    "cuts_per_min": "Cuts per minute",
    "color_saturation_mean": "Colour saturation (mean)",
    "color_contrast_mean": "Colour contrast (mean)",
    "motion_mean": "Motion (mean)",
    "flashing_events_per_min": "Flashing events per minute",
    "audio_rms_mean": "Audio RMS (mean)",
}


def _methodology_html() -> str:
    """Methodology page with the ceilings table generated from config.json.

    Generated rather than written out, because the page claims every result is
    reproducible from the parameters it documents — and a hand-typed copy of a
    number that lives in config.json is how that claim quietly stops being
    true. Retuning the ceilings on 2026-08-14 changed every composite on the
    site; nothing on the page would have said so.
    """
    ranges = CONFIG.get("normalization_reference_ranges", {})
    rows = "".join(
        "<tr><td>{}</td><td>{:g} – {:g}</td></tr>".format(
            _CEILING_LABEL.get(key, key.replace("_", " ")),
            spec.get("min", 0.0), spec.get("max", 0.0))
        for key, spec in ranges.items())
    table = f"<table class=meta><tbody>{rows}</tbody></table>"
    return _METHODOLOGY.replace("__CEILINGS_TABLE__", table)


if __name__ == "__main__":
    build()
