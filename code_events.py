#!/usr/bin/env python3
"""
code_events.py — CLI for CMAT's fantastical-event coding workflow.

Human coding of fantastical events (the content variable the field converged
on: Hinten/Scarf/Imuta 2025). Logic in analyzer/event_coding.py; coding rules
in validation/EVENT_CODEBOOK.md.

  template  <video>                 Blank event-coding sheet.
  rates     <video> [--start --end] Events/min + per-type + relevance/repeat
                                    breakdown from the coded sheet.
  agreement <coderA.csv> <coderB.csv> [--tolerance]
                                    Two-coder inter-rater reliability.
  summary   [dir]                   Cross-episode norms table.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

from analyzer.event_coding import (aggregate_rates, compute_event_metrics,
                                   inter_coder_agreement, parse_event_csv,
                                   publish_manual_metrics, write_event_template,
                                   write_rates_csv)
from analyzer.validation import find_latest, get_validation_dir, sec_to_hms

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


def _warn(msg: str) -> None:
    print(f"  Warning: {msg}")


def _find_events_csv(video: Path) -> Path | None:
    return find_latest(f"{video.stem}_events.csv", get_validation_dir())


def cmd_template(args: argparse.Namespace) -> None:
    try:
        out = write_event_template(args.video)
    except FileExistsError as exc:
        sys.exit(f"Refusing to overwrite existing event coding: {exc}")
    print(f"Blank event sheet → {out}")
    print("Coding rules: validation/EVENT_CODEBOOK.md (premise vs event, the "
          "7 types, narrative_relevance, repeat).")


def cmd_rates(args: argparse.Namespace) -> None:
    video = Path(args.video)
    events_csv = Path(args.events) if args.events else _find_events_csv(video)
    if events_csv is None or not events_csv.exists():
        sys.exit("No event sheet found — run template and code the episode "
                 "first (or pass --events).")

    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    cap.release()
    duration_sec = frames / fps if fps else 0.0
    if duration_sec <= 0 and not (args.start or args.end):
        sys.exit(f"Could not read duration from {video.name} — pass --start "
                 f"and --end to define the coded window.")

    events = parse_event_csv(events_csv, warn_cb=_warn)
    m = compute_event_metrics(events, duration_sec,
                              start=args.start, end=args.end)

    win = m["window"]
    print(f"\nEpisode : {video.stem}")
    print(f"Sheet   : {events_csv.name}")
    if win:
        print(f"Window  : {sec_to_hms(win[0])}–{sec_to_hms(win[1])} "
              f"({m['span_min']} min)")
    else:
        print(f"Span    : {m['span_min']} min (full episode)")
    print(f"\nFantastical events        : {m['n_events']}")
    print(f"Events per minute         : {m['events_per_min']}"
          f"   (literature moderator variable)")
    if m["per_type"]:
        print("\nBy type (per min):")
        for t, d in sorted(m["per_type"].items(),
                           key=lambda kv: -kv[1]["count"]):
            print(f"  {t:<18} {d['count']:>3}   {d['per_min']}")
    if m["pct_integral"] is not None:
        print(f"\nNarrative relevance coded : {m['n_relevance_coded']}/{m['n_events']}")
        print(f"  integral fraction       : {m['pct_integral']}")
    if m["pct_repeat"] is not None:
        print(f"Repeat coded              : {m['n_repeat_coded']}/{m['n_events']}")
        print(f"  repeat fraction         : {m['pct_repeat']}")

    out = write_rates_csv(video, m)
    print(f"\nRates CSV → {out}")


def cmd_agreement(args: argparse.Namespace) -> None:
    a, b = Path(args.coder_a), Path(args.coder_b)
    for p in (a, b):
        if not p.exists():
            sys.exit(f"Error: {p} not found.")
    res = inter_coder_agreement(a, b, tolerance=args.tolerance, warn_cb=_warn)

    print(f"\nCoder A events : {res['n_coder_a']}   ({a.name})")
    print(f"Coder B events : {res['n_coder_b']}   ({b.name})")
    print(f"Matched (±{res['tolerance']}s) : {res['n_matched']}")
    print(f"\nDetection agreement (Dice) : {res['detection_agreement']}")
    if res["type_agreement"] is not None:
        print(f"Type agreement on matched  : {res['type_agreement']}")
        print(f"Type kappa (multi-class)   : {res['type_kappa']}")
        print("kappa guide: <0.4 poor, 0.4–0.6 moderate, 0.6–0.8 substantial, "
              ">0.8 near-perfect.")
    if res["a_only"]:
        print(f"\nCoder A only ({len(res['a_only'])}):")
        for e in res["a_only"]:
            print(f"  {e['timestamp_hms']:>8}  {e['type']}")
    if res["b_only"]:
        print(f"\nCoder B only ({len(res['b_only'])}):")
        for e in res["b_only"]:
            print(f"  {e['timestamp_hms']:>8}  {e['type']}")
    mism = [p for p in res["matched_pairs"] if p["a_type"] != p["b_type"]]
    if mism:
        print(f"\nType disagreements on matched events ({len(mism)}):")
        for p in mism:
            print(f"  {p['timestamp_hms']:>8}  A={p['a_type']}  B={p['b_type']}")


def cmd_publish(args: argparse.Namespace) -> None:
    video = Path(args.video)
    if not args.sampling and not args.trial:
        sys.exit("Provide --trial <manifest.json> (preferred: sampling text is "
                 "derived from provenance) or --sampling \"<description>\".")
    try:
        res = publish_manual_metrics(
            video, show_key=args.show, sampling_method=args.sampling,
            coder=args.coder,
            trial_manifest=Path(args.trial) if args.trial else None,
            warn_cb=_warn)
    except (FileNotFoundError, ValueError) as exc:
        sys.exit(str(exc))
    ep = res["episode"]
    print(f"\nPublished to {res['json_path'].name}:")
    print(f"  show      : {res['show_key']}  "
          f"({res['n_episodes']} coded episode(s) now published)")
    print(f"  episode   : {ep['episode']}")
    print(f"  events/min: {ep['events_per_min']}  ({ep['n_events']} events"
          + (f", window {ep['window'][0]}–{ep['window'][1]}" if ep["window"] else "")
          + ")")
    print(f"  sampling  : {args.sampling or '(derived from trial manifest)'}")
    print("\nNow rebuild the site (python build_site.py) and push to deploy.")


def cmd_summary(args: argparse.Namespace) -> None:
    rows = aggregate_rates(Path(args.directory) if args.directory else None)
    if not rows:
        sys.exit("No __eventrates_ CSVs found — run rates on at least one "
                 "coded episode first.")
    print(f"\n{'Episode':<50} {'events':>7} {'ev/min':>7} "
          f"{'%integral':>10} {'%repeat':>8}")
    print("-" * 88)
    for r in rows:
        print(f"{r['episode'][:50]:<50} {r['n_events']:>7} "
              f"{r['events_per_min']:>7} {r['pct_integral'] or '—':>10} "
              f"{r['pct_repeat'] or '—':>8}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CMAT fantastical-event coding tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_t = sub.add_parser("template", help="Blank event-coding sheet")
    p_t.add_argument("video")

    p_r = sub.add_parser("rates", help="Event rates from the coded sheet")
    p_r.add_argument("video")
    p_r.add_argument("--events", default=None,
                     help="Path to the coded events CSV (default: found by "
                          "video stem)")
    p_r.add_argument("--start", default=None,
                     help="Coded-window start (sec or MM:SS)")
    p_r.add_argument("--end", default=None,
                     help="Coded-window end (sec or MM:SS)")

    p_a = sub.add_parser("agreement", help="Two-coder inter-rater reliability")
    p_a.add_argument("coder_a")
    p_a.add_argument("coder_b")
    p_a.add_argument("--tolerance", type=float, default=2.0)

    p_p = sub.add_parser("publish",
                         help="Publish coded metrics to manual_coding.json "
                              "for the website build")
    p_p.add_argument("video")
    p_p.add_argument("--show", required=True,
                     help="show_key exactly as in site_manifest.json")
    p_p.add_argument("--trial", default=None,
                     help="Path to a named sampling trial's manifest.json — "
                          "the sampling description is DERIVED from it "
                          "(preferred over --sampling)")
    p_p.add_argument("--sampling", default=None,
                     help="Free-text description of how coded episodes/windows "
                          "were chosen (for hand-picked coding without a "
                          "sampler trial)")
    p_p.add_argument("--coder", default="single coder",
                     help="Coder description shown on the site "
                          "(default: 'single coder')")

    p_s = sub.add_parser("summary", help="Cross-episode event-rate norms table")
    p_s.add_argument("directory", nargs="?", default=None)

    args = parser.parse_args()
    {"template": cmd_template, "rates": cmd_rates,
     "agreement": cmd_agreement, "summary": cmd_summary,
     "publish": cmd_publish}[args.command](args)


if __name__ == "__main__":
    main()
