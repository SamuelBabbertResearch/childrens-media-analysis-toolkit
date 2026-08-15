"""
Fantastical-event coding support — pure functions, zero GUI imports.

CMAT's human-coding channel for the content variable the field converged on
(fantastical events; Hinten/Scarf/Imuta 2025 meta-analysis). The tool does NOT
detect fantasy — it is a semantic judgment coded by humans (see
validation/EVENT_CODEBOOK.md). This module makes that coding rigorous and
cheap to analyze:

  write_event_template()   blank coding sheet
  parse_event_csv()        load + normalize a coded sheet
  compute_event_metrics()  events/min (the literature's moderator variable),
                           per-type rates, narrative-relevance and repeat
                           breakdowns, per-30s timeline
  inter_coder_agreement()  two-coder IRR: detection agreement within a time
                           tolerance, type agreement, multi-class Cohen's kappa
  aggregate_rates()        cross-episode norms table
"""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
from typing import Any, Callable

from .validation import (_git_commit, episode_dir, find_latest,
                         get_validation_dir, hms_to_sec, match_transitions,
                         parse_time_arg, sec_to_hms)

EVENT_TYPES = [
    ("physical",        "Violates intuitive physics: gravity, support, solidity (flying, through walls)"),
    ("transformation",  "Impossible change of identity, shape, or size"),
    ("continuity",      "Appearing, vanishing, teleporting, splitting, multiplying"),
    ("body",            "Anatomically impossible body event (eyes pop out, neck stretches)"),
    ("animacy",         "Inanimate object begins acting as an animate agent (onset, not premise)"),
    ("causal",          "Impossible causation: magic, effects without mechanism"),
    ("other_impossible","Clearly impossible, fits nothing above — note required"),
]
_EVENT_TYPE_SET = {t for t, _ in EVENT_TYPES}

_RELEVANCE = {"integral", "incidental"}
_REPEAT    = {"new", "repeat"}

_COLUMNS = ["timestamp_hms", "timestamp_sec", "event_type",
            "narrative_relevance", "repeat", "duration_sec", "notes"]


def write_event_template(video: Path | str,
                         validation_dir: Path | None = None) -> Path:
    """Create a blank event-coding CSV. Raises FileExistsError if present."""
    vdir = validation_dir or get_validation_dir()
    vdir.mkdir(parents=True, exist_ok=True)
    out = vdir / f"{Path(video).stem}_events.csv"
    if out.exists():
        raise FileExistsError(str(out))
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(_COLUMNS)
        w.writerow(["", "", " | ".join(t for t, _ in EVENT_TYPES),
                    "integral | incidental", "new | repeat",
                    "(optional sec)", "premise: <note show premise here>"])
    return out


def find_event_sheet(video: Path | str,
                     validation_dir: Path | None = None) -> Path | None:
    """Locate the event-coding sheet for a video, wherever it was filed.

    Mirrors `validation.find_manual`: exact stem first, then any
    `*_events.csv` whose base name is a prefix of the video stem, minimum
    eight characters. Coders shorten long filenames, and sheets get filed into
    per-episode subfolders, so a top-level exact-name lookup answers "not
    coded" for episodes that are.

    ONE definition, because there were four. `code_events.py`, `trials.py`,
    `gui_handcoding.py` and `gui_validation.py` each searched recursively with
    this fallback while the Qt Code screen looked only at
    `<validation>/<stem>_events.csv` — so the screen would have started a
    fresh empty sheet for an episode the command line scores from an existing
    one, with nothing on either side to reveal it. `LEARNINGS.md` § *The same
    one-line mistake, in four independent places*.

    Finding is recursive; WRITING stays at the top of the validation folder
    (`write_event_template`, and the Code screen's Save). That asymmetry is
    deliberate — a new sheet needs one predictable home, an old one has to be
    found where a person put it.
    """
    vdir = validation_dir or get_validation_dir()
    stem = Path(video).stem
    exact = find_latest(f"{stem}_events.csv", vdir)
    if exact:
        return exact
    if not vdir.exists():
        return None
    suffix = "_events.csv"
    candidates = [
        p for p in vdir.rglob(f"*{suffix}")
        if len(p.name) - len(suffix) >= 8
        and stem.lower().startswith(p.name[:-len(suffix)].lower())
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: p.stat().st_mtime)[-1]


def event_sheet_status(video: Path | str,
                       validation_dir: Path | None = None,
                       cmap: dict[str, dict] | None = None) -> dict:
    """How far event coding has got for one episode.

    `n_events` counts rows `parse_event_csv` accepts, which is what any later
    rate is computed from — not the line count, because a template's guidance
    row carries no timestamp and is not an event. A sheet that exists with
    zero events is a real and different state from no sheet at all: someone
    created it and has not coded yet.

    Pass a `validation.coded_episode_map()` as *cmap* when asking about many
    episodes at once, as the hand-coding worklist does — it answers from one
    scan of the folder instead of one glob per episode.
    """
    if cmap is not None:
        from .validation import coding_for_stem
        sheet = coding_for_stem(Path(video).stem, cmap)["events"]
    else:
        sheet = find_event_sheet(video, validation_dir)
    if sheet is None:
        return {"sheet": None, "exists": False, "n_events": 0,
                "step": "uncoded"}
    try:
        events = parse_event_csv(sheet)
    except Exception:
        return {"sheet": sheet, "exists": True, "n_events": 0,
                "step": "unreadable"}
    return {"sheet": sheet, "exists": True, "n_events": len(events),
            "step": "coded" if events else "started"}


def parse_event_csv(path: Path,
                    warn_cb: Callable[[str], None] | None = None) -> list[dict]:
    """Load a coded event sheet. Rows without a timestamp are skipped."""
    rows: list[dict] = []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader, 2):
            t_hms = (row.get("timestamp_hms") or "").strip()
            t_sec = (row.get("timestamp_sec") or "").strip()
            if not t_hms and not t_sec:
                continue
            try:
                ts = float(t_sec) if t_sec else hms_to_sec(t_hms)
            except ValueError as exc:
                if warn_cb:
                    warn_cb(f"row {i} skipped — {exc}")
                continue
            etype = (row.get("event_type") or "").strip().lower()
            if etype not in _EVENT_TYPE_SET and warn_cb:
                warn_cb(f"row {i} — unknown event_type {etype!r}")
            rel = (row.get("narrative_relevance") or "").strip().lower()
            if rel and rel not in _RELEVANCE and warn_cb:
                warn_cb(f"row {i} — narrative_relevance {rel!r} "
                        f"(use integral/incidental)")
            rep = (row.get("repeat") or "").strip().lower()
            if rep and rep not in _REPEAT and warn_cb:
                warn_cb(f"row {i} — repeat {rep!r} (use new/repeat)")
            dur = (row.get("duration_sec") or "").strip()
            try:
                duration = float(dur) if dur else None
            except ValueError:
                duration = None
                if warn_cb:
                    warn_cb(f"row {i} — bad duration_sec {dur!r}, ignored")
            rows.append({
                "timestamp_sec": round(ts, 3),
                "timestamp_hms": sec_to_hms(ts),
                "event_type": etype or "unknown",
                "narrative_relevance": rel,
                "repeat": rep,
                "duration_sec": duration,
                "notes": (row.get("notes") or "").strip(),
            })
    return sorted(rows, key=lambda r: r["timestamp_sec"])


def compute_event_metrics(
    events: list[dict],
    duration_sec: float,
    start: float | str | None = None,
    end: float | str | None = None,
) -> dict[str, Any]:
    """Event rates in the literature's units (events per minute).

    If start/end are given, rates are computed over that window only
    (window length becomes the denominator).
    """
    lo = parse_time_arg(start)
    hi = parse_time_arg(end)
    window = None
    if lo is not None or hi is not None:
        lo = lo if lo is not None else 0.0
        hi = hi if hi is not None else duration_sec
        window = (lo, hi)
        events = [e for e in events if lo <= e["timestamp_sec"] <= hi]
        span_sec = max(hi - lo, 1e-6)
    else:
        span_sec = max(duration_sec, 1e-6)

    span_min = span_sec / 60.0
    n = len(events)

    by_type = {t: 0 for t, _ in EVENT_TYPES}
    for e in events:
        by_type[e["event_type"]] = by_type.get(e["event_type"], 0) + 1

    n_rel = sum(1 for e in events if e["narrative_relevance"] in _RELEVANCE)
    n_integral = sum(1 for e in events
                     if e["narrative_relevance"] == "integral")
    n_rep_coded = sum(1 for e in events if e["repeat"] in _REPEAT)
    n_repeat = sum(1 for e in events if e["repeat"] == "repeat")

    base = window[0] if window else 0.0
    n_windows = max(1, int(span_sec / 30.0))
    timeline = [
        sum(1 for e in events
            if base + i * 30.0 <= e["timestamp_sec"] < base + (i + 1) * 30.0)
        for i in range(n_windows)
    ]

    return {
        "n_events": n,
        "events_per_min": round(n / span_min, 3),
        "per_type": {t: {"count": c, "per_min": round(c / span_min, 3)}
                     for t, c in by_type.items() if c > 0},
        "pct_integral": round(n_integral / n_rel, 3) if n_rel else None,
        "n_relevance_coded": n_rel,
        "pct_repeat": round(n_repeat / n_rep_coded, 3) if n_rep_coded else None,
        "n_repeat_coded": n_rep_coded,
        "timeline_events_per_30s": timeline,
        "window": window,
        "span_min": round(span_min, 3),
    }


def _kappa_multiclass(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's kappa for (coder_a, coder_b) label pairs, any number of classes.

    Returns None where kappa is UNDEFINED: no pairs, or chance agreement of 1
    (both coders used a single identical category). Returning 0.0 there would
    report perfect unanimity as no agreement beyond chance.
    """
    n = len(pairs)
    if n == 0:
        return None
    p_o = sum(1 for a, b in pairs if a == b) / n
    cats = {a for a, _ in pairs} | {b for _, b in pairs}
    p_e = sum(
        (sum(1 for a, _ in pairs if a == c) / n)
        * (sum(1 for _, b in pairs if b == c) / n)
        for c in cats
    )
    if (1 - p_e) <= 1e-9:
        return None
    return (p_o - p_e) / (1 - p_e)


def inter_coder_agreement(
    coder_a_path: Path,
    coder_b_path: Path,
    tolerance: float = 2.0,
    warn_cb: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Two-coder inter-rater reliability for event coding.

    Detection agreement: events matched between coders within tolerance
    (Dice: 2*matched / (nA + nB)). Type agreement + multi-class Cohen's kappa
    computed over the matched pairs. Symmetric in the two coders except that
    unmatched events are reported per coder.
    """
    a = parse_event_csv(coder_a_path, warn_cb=warn_cb)
    b = parse_event_csv(coder_b_path, warn_cb=warn_cb)

    # Reuse the validation matcher: map events to its expected dict shape.
    a_shaped = [{"timestamp_sec": e["timestamp_sec"],
                 "timestamp_hms": e["timestamp_hms"],
                 "type": e["event_type"]} for e in a]
    b_shaped = [{"timestamp_sec": e["timestamp_sec"],
                 "timestamp_hms": e["timestamp_hms"],
                 "type": e["event_type"]} for e in b]
    results, b_unmatched = match_transitions(b_shaped, a_shaped, tolerance)

    matched = [r for r in results if r["match"] == "TP"]
    a_only  = [r for r in results if r["match"] == "FN"]

    pairs = [(r["manual_type"], r["tool_type"]) for r in matched]
    n_type_agree = sum(1 for x, y in pairs if x == y)

    dice = (2 * len(matched) / (len(a) + len(b))) if (a or b) else 0.0

    return {
        "n_coder_a": len(a), "n_coder_b": len(b),
        "n_matched": len(matched),
        "detection_agreement": round(dice, 3),
        "type_agreement": round(n_type_agree / len(pairs), 3) if pairs else None,
        "type_kappa": (round(_k, 3)
                       if (_k := _kappa_multiclass(pairs)) is not None
                       else None),
        "a_only": [{"timestamp_hms": r["manual_hms"], "type": r["manual_type"]}
                   for r in a_only],
        "b_only": [{"timestamp_hms": d["timestamp_hms"], "type": d["type"]}
                   for d in b_unmatched],
        "matched_pairs": [{"timestamp_hms": r["manual_hms"],
                           "a_type": r["manual_type"],
                           "b_type": r["tool_type"]} for r in matched],
        "tolerance": tolerance,
    }


def write_rates_csv(
    video: Path,
    metrics: dict[str, Any],
    validation_dir: Path | None = None,
) -> Path:
    """Persist a rates summary + manifest for the norms table."""
    vdir = episode_dir(video, validation_dir)
    vdir.mkdir(parents=True, exist_ok=True)
    out = vdir / f"{video.stem}__eventrates_{date.today()}.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["metric", "value"])
        w.writerow(["n_events", metrics["n_events"]])
        w.writerow(["events_per_min", metrics["events_per_min"]])
        w.writerow(["span_min", metrics["span_min"]])
        w.writerow(["pct_integral", metrics["pct_integral"]])
        w.writerow(["pct_repeat", metrics["pct_repeat"]])
        for t, d in metrics["per_type"].items():
            w.writerow([f"per_min[{t}]", d["per_min"]])
    (vdir / f"{video.stem}__eventrates_manifest_{date.today()}.json").write_text(
        json.dumps({
            "date": str(date.today()), "git_commit": _git_commit(),
            "video": str(video),
            "window": list(metrics["window"]) if metrics["window"] else None,
            "n_events": metrics["n_events"],
            "events_per_min": metrics["events_per_min"],
        }, indent=2), encoding="utf-8")
    return out


def publish_manual_metrics(
    video: Path,
    show_key: str,
    sampling_method: str | None = None,
    coder: str = "single coder",
    json_path: Path | None = None,
    validation_dir: Path | None = None,
    trial_manifest: Path | None = None,
    warn_cb: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Publish an episode's coded event metrics into manual_coding.json.

    Reads the most recent __eventrates_ manifest+CSV for the video (produced by
    the `rates` command) so published numbers carry exact provenance. Upserts
    by episode stem under the given show_key. The website build reads this file;
    nothing reaches the site without this explicit publish step (matching the
    site's manual-review policy).
    """
    from .config_loader import _base_dir  # local import to avoid cycles at module load
    vdir = validation_dir or get_validation_dir()
    jpath = json_path or (_base_dir() / "manual_coding.json")

    # Sampling description: derived from a named trial manifest when given
    # (provenance-generated, no transcription errors), else the free text.
    trial_info = None
    if trial_manifest is not None:
        from .trials import sampling_text_from_manifest
        tdata = json.loads(Path(trial_manifest).read_text(encoding="utf-8"))
        sampling_method = sampling_text_from_manifest(tdata)
        trial_info = {"trial_name": tdata.get("trial_name"),
                      "manifest": str(trial_manifest)}
    if not sampling_method:
        raise ValueError("Provide sampling_method text or a trial_manifest.")

    stem = video.stem
    manifests = sorted(vdir.rglob(f"{stem}__eventrates_manifest_*.json"),
                       key=lambda p: p.stat().st_mtime)
    if not manifests:
        raise FileNotFoundError(
            f"No event-rates manifest found for {stem} — run "
            f"`code_events.py rates` first.")
    manifest = json.loads(manifests[-1].read_text(encoding="utf-8"))

    rates_csvs = sorted(vdir.rglob(f"{stem}__eventrates_*.csv"),
                        key=lambda p: p.stat().st_mtime)
    rates_csvs = [p for p in rates_csvs if "_manifest_" not in p.name]
    per_type = {}
    pct_integral = pct_repeat = None
    if rates_csvs:
        with rates_csvs[-1].open(newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                k, v = r["metric"], r["value"]
                if k.startswith("per_min[") and k.endswith("]"):
                    per_type[k[8:-1]] = float(v)
                elif k == "pct_integral" and v not in ("", "None"):
                    pct_integral = float(v)
                elif k == "pct_repeat" and v not in ("", "None"):
                    pct_repeat = float(v)

    # Validate show_key against the site manifest if present.
    site_manifest = _base_dir() / "site_manifest.json"
    if site_manifest.exists() and warn_cb:
        try:
            keys = {s["show_key"] for s in
                    json.loads(site_manifest.read_text(encoding="utf-8"))["shows"]}
            if show_key not in keys:
                warn_cb(f"show_key {show_key!r} not in site_manifest.json — "
                        f"the site build will not display it until it matches. "
                        f"Known keys: {sorted(keys)}")
        except Exception:
            pass

    data: dict[str, Any] = {"fantastical_events": {}}
    if jpath.exists():
        data = json.loads(jpath.read_text(encoding="utf-8"))
        data.setdefault("fantastical_events", {})

    # "Coded and found none" and "never coded" produce identical numbers: an
    # empty template rates out at 0 events/min just as a genuinely
    # event-free episode does. Publishing puts that figure on the public site
    # as a measurement, so say something before it goes — the caller decides,
    # but not unknowingly.
    if warn_cb and not manifest.get("n_events"):
        warn_cb(
            f"{stem} has ZERO coded events. Publishing records 0.0 events/min "
            f"as a finding, which is indistinguishable from an episode nobody "
            f"coded. Publish only if you watched it and found none.")

    window = manifest.get("window")
    episode_entry = {
        "episode": stem,
        "n_events": manifest["n_events"],
        "events_per_min": manifest["events_per_min"],
        "window": ([sec_to_hms(window[0]), sec_to_hms(window[1])]
                   if window else None),
        "per_type_per_min": per_type,
        "pct_integral": pct_integral,
        "pct_repeat": pct_repeat,
        "coded_date": manifest["date"],
        "git_commit": manifest.get("git_commit", "unknown"),
    }

    show = data["fantastical_events"].setdefault(show_key, {"episodes": []})
    show["sampling_method"] = sampling_method
    show["coder"] = coder
    show["codebook"] = "validation/EVENT_CODEBOOK.md"
    if trial_info:
        show["trial"] = trial_info
    show["episodes"] = [e for e in show["episodes"] if e["episode"] != stem]
    show["episodes"].append(episode_entry)
    show["episodes"].sort(key=lambda e: e["episode"])

    jpath.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"json_path": jpath, "show_key": show_key,
            "n_episodes": len(show["episodes"]), "episode": episode_entry}


def latest_rates_for_stem(stem: str,
                          validation_dir: Path | None = None) -> dict | None:
    """Newest published event-rates manifest for an episode stem.

    Exact-stem match first, then prefix fallback (users shorten long
    filenames the same way they do for manual coding sheets).
    """
    vdir = validation_dir or get_validation_dir()
    if not vdir.exists():
        return None
    matches = sorted(vdir.rglob(f"{stem}__eventrates_manifest_*.json"),
                     key=lambda p: p.stat().st_mtime)
    if not matches:
        marker = "__eventrates_manifest_"
        cands = [p for p in vdir.rglob(f"*{marker}*.json")
                 if len(p.name.split(marker)[0]) >= 8
                 and stem.lower().startswith(p.name.split(marker)[0].lower())]
        matches = sorted(cands, key=lambda p: p.stat().st_mtime)
    if not matches:
        return None
    try:
        return json.loads(matches[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def events_stats_for_stems(stems: list[str],
                           validation_dir: Path | None = None) -> dict | None:
    """Join event coding onto a set of episodes (for aggregate displays).

    Returns per-episode rates for coded episodes plus mean/range across them,
    or None when no episode in the set has event coding.
    """
    vdir = validation_dir or get_validation_dir()
    per_episode = []
    for s in stems:
        m = latest_rates_for_stem(s, vdir)
        if m is not None:
            per_episode.append({
                "stem": s,
                "events_per_min": m.get("events_per_min"),
                "n_events": m.get("n_events"),
                "window": m.get("window"),
                "date": m.get("date"),
            })
    if not per_episode:
        return None
    rates = [e["events_per_min"] for e in per_episode
             if e["events_per_min"] is not None]
    return {
        "per_episode": per_episode,
        "n_coded": len(per_episode),
        "n_total": len(stems),
        "mean": round(sum(rates) / len(rates), 2) if rates else None,
        "min": min(rates) if rates else None,
        "max": max(rates) if rates else None,
    }


def aggregate_rates(directory: Path | None = None) -> list[dict]:
    """Collect all __eventrates_ CSVs into one cross-episode table."""
    vdir = directory or get_validation_dir()
    rows = []
    for f in sorted(vdir.rglob("*__eventrates_*.csv")):
        if "_manifest_" in f.name:
            continue
        vals: dict[str, str] = {}
        with f.open(newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                vals[r["metric"]] = r["value"]
        stem = f.stem.split("__eventrates_")[0]
        rows.append({"episode": stem,
                     "n_events": vals.get("n_events", ""),
                     "events_per_min": vals.get("events_per_min", ""),
                     "pct_integral": vals.get("pct_integral", ""),
                     "pct_repeat": vals.get("pct_repeat", "")})
    return rows
