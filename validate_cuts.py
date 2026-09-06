#!/usr/bin/env python3
"""
validate_cuts.py — CLI for CMAT's transition-detection validation workflow.

All logic lives in analyzer/validation.py (also used by the GUI Validation tab);
this file only parses arguments and prints results.

Research workflow (in this order — coding must happen BLIND, before export):

  1. template <video>          Write a blank manual-coding CSV. Code the episode
                               in VLC *before* ever looking at tool detections.
  2. export   <video>          Run hard-cut + dissolve detection, write a
                               detections CSV + a JSON manifest.
  3. compare  <detections.csv> <manual.csv>
                               Precision / recall / F1 per transition type.
  4. sweep    <video> <manual.csv>
                               Grid-search noise_floor x min_frames (TUNING
                               episodes only, never the held-out set).
  5. summary  [dir]            Aggregate all comparison CSVs across episodes.

Manual coding CSV format (fill timestamp_hms OR timestamp_sec, one per row):
  timestamp_hms, timestamp_sec, type, notes
  00:37,        , dissolve,
  01:04,        , hard_cut,

Accepted types: hard_cut, dissolve, fade_in, fade_out, other
See validation/CODEBOOK.md for operational definitions.
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

from analyzer.validation import (
    aggregate_summary, classify_cuts_for_video, compare_detections,
    episode_status, export_detections, get_validation_dir,
    RESUBSTITUTION_WARNING,
    grade_cut_classifier, run_sweep, sec_to_hms, write_template,
)

# Windows consoles often default to cp1252, which can't print arrows/± symbols.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


def _warn(msg: str) -> None:
    print(f"  Warning: {msg}")


def _print_score_table(rows: list[dict]) -> None:
    print()
    print(f"{'Transition type':<16}  {'TP':>4}  {'FP':>4}  {'FN':>4}  "
          f"{'Prec':>6}  {'Rec':>6}  {'F1':>6}")
    print("-" * 58)
    for row in rows:
        if row["type"] in ("ALL", "AGGREGATE"):
            print("-" * 58)
        print(f"  {row['type']:<14}  {row['TP']:>4}  {row['FP']:>4}  {row['FN']:>4}"
              f"  {row['precision']:>6.3f}  {row['recall']:>6.3f}  {row['F1']:>6.3f}")


def cmd_template(args: argparse.Namespace) -> None:
    try:
        out = write_template(args.video)
    except FileExistsError as exc:
        sys.exit(f"Refusing to overwrite existing manual coding: {exc}\n"
                 f"Delete it yourself if you truly want to start over.")
    print(f"Blank coding sheet → {out}")
    print("Code the episode in VLC now, BEFORE running export.")
    print("Conventions are in validation/CODEBOOK.md — finalize it before your first session.")


def cmd_export(args: argparse.Namespace) -> None:
    video_path = Path(args.video)
    if not video_path.exists():
        sys.exit(f"Error: {video_path} not found.")
    dissolves_on = not args.no_dissolves
    print(f"\nExporting detections for: {video_path.name}")
    res = export_detections(
        video_path,
        detector=args.detector, threshold=args.threshold,
        noise_floor=args.noise_floor, min_frames=args.min_frames,
        dissolves_on=dissolves_on, use_cache=not args.no_cache,
        status_cb=lambda m: print(f"  {m}"),
    )
    print(f"  {res['n_hard_cuts']} hard cuts.")
    if dissolves_on:
        print(f"  {res['n_dissolves']} dissolve candidates "
              f"(noise_floor={args.noise_floor}, min_frames={args.min_frames}).")
    print(f"\n  Detections → {res['detections_path']}")
    print(f"  Manifest   → {res['manifest_path']}")
    manual_guess = get_validation_dir() / f"{video_path.stem}_manual.csv"
    print(f"\nNext:  python validate_cuts.py compare \"{res['detections_path']}\" "
          f"\"{manual_guess}\"")


def cmd_compare(args: argparse.Namespace) -> None:
    det_path, manual_path = Path(args.detections), Path(args.manual)
    if not det_path.exists():
        sys.exit(f"Error: {det_path} not found.")
    if not manual_path.exists():
        sys.exit(f"Error: {manual_path} not found.")

    res = compare_detections(det_path, manual_path, tolerance=args.tolerance,
                             start=args.start, end=args.end, warn_cb=_warn)

    window = res["window"]
    print(f"\n{'='*60}")
    print(f"Detections file : {det_path.name}")
    print(f"Manual codes    : {manual_path.name}")
    print(f"Match tolerance : ±{args.tolerance}s"
          + (f"   window: {sec_to_hms(window[0])}–{sec_to_hms(window[1])}"
             if window else ""))
    print(f"{'='*60}")
    print(f"Tool detected   : {res['n_detections']} transitions")
    print(f"Manual coded    : {res['n_manual']} transitions")
    _print_score_table(res["summary_rows"])

    # Rate calibration — the estimand CMAT publishes (cuts/min). Reported
    # alongside F1, never instead of it: they assess different properties.
    if res.get("count_ratio") is not None:
        all_row = next((r for r in res["summary_rows"] if r["type"] == "ALL"), None)
        print(f"\nRate calibration (a DIFFERENT property from the F1 above):")
        print(f"  count ratio (tool/human)     : {res['count_ratio']:.3f}")
        print(f"  signed relative count error  : {res['rel_count_error']*100:+.1f}%")
        if all_row and all_row["precision"] and all_row["recall"]:
            direction = ("over" if all_row["recall"] > all_row["precision"]
                         else "under" if all_row["recall"] < all_row["precision"]
                         else "un")
            print(f"  recall {all_row['recall']:.3f} vs precision "
                  f"{all_row['precision']:.3f} → {direction}counts "
                  f"(ratio == recall/precision, exactly)")
        print("  Single episode: this is an ERROR, not a bias. Bias requires a "
              "held-out sample.")

    fn_list = [r for r in res["results"] if r["match"] == "FN"]
    if fn_list:
        print(f"\nMissed by tool (false negatives — {len(fn_list)}):")
        for r in fn_list:
            print(f"  {r['manual_hms']:>8}  {r['manual_type']}")
    if res["false_positives"]:
        print(f"\nFalse positives — tool detected, not in manual "
              f"({len(res['false_positives'])}):")
        for d in res["false_positives"]:
            print(f"  {d['timestamp_hms']:>8}  {d['type']}")
    if res["mismatches"]:
        print(f"\nType mismatches — matched by time, different label "
              f"({len(res['mismatches'])}):")
        for r in res["mismatches"]:
            print(f"  {r['manual_hms']:>8}  manual={r['manual_type']}  "
                  f"tool={r['tool_type']}  (offset {r['offset_sec']:+.1f}s)")

    print(f"\nSummary → {res['comparison_path']}")
    print(f"Detail  → {res['detail_path']}")
    print("Annotate the failure_reason column in the detail CSV while reviewing "
          "each miss in VLC — that becomes your error taxonomy.")


def _k(value) -> str:
    """Cohen's kappa for printing. None means UNDEFINED, and must not print
    as a number - 0.000 there reads as "no agreement beyond chance" for what
    is actually perfect unanimity."""
    return "n/a" if value is None else f"{value:.3f}"


def _wrap(text: str, width: int = 78) -> str:
    return "\n".join(textwrap.wrap(text, width))


def cmd_sweep(args: argparse.Namespace) -> None:
    video_path, manual_path = Path(args.video), Path(args.manual)
    if not manual_path.exists():
        sys.exit(f"Error: {manual_path} not found.")
    if not video_path.exists():
        print(f"Note: {video_path.name} not found on disk — relying on caches.")

    floors = [float(x) for x in args.floors.split(",")]
    frames = [int(x) for x in args.frames.split(",")]
    res = run_sweep(video_path, manual_path,
                    detector=args.detector, threshold=args.threshold,
                    tolerance=args.tolerance, floors=floors, frames=frames,
                    start=args.start, end=args.end,
                    status_cb=lambda m: print(f"  {m}"))

    window = res["window"]
    print(f"\nSweep: {len(floors)} noise_floor x {len(frames)} min_frames = "
          f"{len(floors)*len(frames)} configurations   (tolerance ±{args.tolerance}s)"
          + (f"   window: {sec_to_hms(window[0])}–{sec_to_hms(window[1])}"
             if window else ""))
    print(f"Hard cuts fixed: {args.detector} t={args.threshold:g}\n")

    by_floor: dict[float, dict[int, float]] = {}
    for row in res["grid_rows"]:
        by_floor.setdefault(row["noise_floor"], {})[row["min_frames"]] = row["diss_F1"]
    print(f"{'floor':>6} | " + " | ".join(f"mf={mf:<3}" for mf in frames)
          + "   (dissolve F1)")
    print("-" * (9 + 9 * len(frames)))
    for floor in floors:
        cells = [f"{by_floor[floor][mf]:.3f}" for mf in frames]
        print(f"{floor:>6.1f} | " + " | ".join(f"{c:<6}" for c in cells))

    best = res["best"]
    print(f"\nBest-FITTING configuration on THIS sample: noise_floor="
          f"{best['noise_floor']}, min_frames={best['min_frames']}")
    print(f"  dissolve F1 there = {best['diss_F1']:.3f} "
          f"(P={best['diss_precision']:.3f}, R={best['diss_recall']:.3f}) "
          f"— RESUBSTITUTION, over {len(res['grid_rows'])} grid points")
    print(f"Grid CSV → {res['csv_path']}")
    print()
    print(_wrap(RESUBSTITUTION_WARNING))


def cmd_summary(args: argparse.Namespace) -> None:
    """One table PER DETECTOR, not one table across all of them.

    Summing ContentDetector and TransNetV2 runs over the same episodes gave a
    single figure describing neither — 0.891, against 0.855 and 0.928 for the
    two detectors that actually exist.
    """
    directory = Path(args.directory) if args.directory else None
    wanted = getattr(args, "detector", None)
    probe = aggregate_summary(directory, detector_tag=wanted)
    if not probe["n_files"] and not probe["detector_tags"]:
        sys.exit("No *_comparison_*.csv files found.")

    tags = [wanted] if wanted else probe["detector_tags"]
    if wanted and wanted not in probe["detector_tags"]:
        sys.exit(f"No comparisons for detector {wanted!r}. "
                 f"On disk: {', '.join(probe['detector_tags'])}")

    for tag in tags:
        res = aggregate_summary(directory, detector_tag=tag)
        if not res["n_files"]:
            continue
        print(f"\nDetector: {tag}   "
              f"({res['n_files']} comparison file(s), latest per episode)\n")
        for cf in res["files"]:
            print(f"  {cf.name}")
        _print_score_table(res["rows"])
    if len(tags) > 1:
        print("\nThese are separate detectors and their scores are NOT "
              "combined: a figure averaged across configurations describes no "
              "detector you can actually run.")


def cmd_classify(args: argparse.Namespace) -> None:
    video_path = Path(args.video)
    if not video_path.exists():
        sys.exit(f"Error: {video_path} not found.")
    res = classify_cuts_for_video(
        video_path,
        detector=args.detector, threshold=args.threshold,
        offset_sec=args.offset,
        similarity_threshold=args.sim_threshold,
        status_cb=lambda m: print(f"  {m}"))
    print(f"\nCuts classified : {res['n_cuts']}")
    print(f"  within_scene  : {res['n_within_scene']}")
    print(f"  scene_change  : {res['n_scene_change']}")
    if res["n_unknown"]:
        print(f"  unknown       : {res['n_unknown']}")
    print(f"Scene changes/min       : {res['scene_changes_per_min']}")
    print(f"Within-scene fraction   : {res['within_scene_fraction']}")
    print(f"\nCSV → {res['csv_path']}")
    print("Similarity threshold is UNVALIDATED — compare the labels against "
          "your manual coding notes before trusting them.")


def cmd_grade_cuts(args: argparse.Namespace) -> None:
    video_path, manual_path = Path(args.video), Path(args.manual)
    if not video_path.exists():
        sys.exit(f"Error: {video_path} not found.")
    if not manual_path.exists():
        sys.exit(f"Error: {manual_path} not found.")
    res = grade_cut_classifier(
        video_path, manual_path,
        detector=args.detector, threshold=args.threshold,
        tolerance=args.tolerance, offset_sec=args.offset,
        start=args.start, end=args.end,
        warn_cb=_warn, status_cb=lambda m: print(f"  {m}"))

    print(f"\nHuman-labeled cuts (within/change) : {res['n_human_labeled']}")
    print(f"Matched to a detected cut          : {res['n_matched']}")
    if res["n_unmatched"]:
        print(f"Labeled but unmatched (tool missed): {res['n_unmatched']}")
    if res["n_matched"] == 0:
        print("\nNo labeled cuts matched — add a scene_relation column "
              "(within/change) to your hard_cut rows first.")
        return

    print(f"\n{'threshold':>9}  {'accuracy':>8}  {'kappa':>6}")
    print("-" * 28)
    for r in res["sweep_rows"]:
        star = "  <- best fit" if r["threshold"] == res["best"]["threshold"] else ""
        print(f"{r['threshold']:>9.3f}  {r['accuracy']:>8.3f}  "
              f"{_k(r['kappa']):>6}{star}")

    b = res["best"]
    c = res["confusion"]
    print(f"\nBest-FITTING threshold on THIS sample: {b['threshold']:.3f}  "
          f"accuracy {b['accuracy']:.3f}  kappa {_k(b['kappa'])}  "
          f"— RESUBSTITUTION, over {res['n_thresholds_searched']} thresholds")
    print("Confusion at best threshold (human → predicted):")
    print(f"  within → within : {c['within_within']:>3}   "
          f"within → change : {c['within_change']:>3}  (missed within-scene)")
    print(f"  change → within : {c['change_within']:>3}   "
          f"change → change : {c['change_change']:>3}")
    print(f"\nDetail → {res['csv_path']}")
    print("kappa guide: <0.4 poor, 0.4–0.6 moderate, 0.6–0.8 substantial, "
          ">0.8 near-human. 'n/a' means kappa is UNDEFINED here, not zero: "
          "both raters used a single identical class, so there is no chance "
          "agreement to correct for.")
    print()
    print(_wrap(RESUBSTITUTION_WARNING))


def cmd_status(args: argparse.Namespace) -> None:
    st = episode_status(Path(args.video))
    print(f"\nEpisode : {st['stem']}")
    print(f"Step    : {st['step']}")
    print(f"Manual  : {st['manual_path'] or '(no template yet)'}  "
          f"({st['coded_rows']} transitions coded)")
    print(f"Detections files: {len(st['detections'])}")
    if st["latest_detail"]:
        print(f"Latest match detail: {st['latest_detail'].name}")
        print(f"Error annotation: {st['errors_annotated']}/{st['errors_total']} done")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CMAT transition-detection validation tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_tmpl = sub.add_parser("template", help="Write a blank manual-coding CSV (do this FIRST)")
    p_tmpl.add_argument("video", help="Video path (used only for the filename stem)")

    p_exp = sub.add_parser("export", help="Detect transitions and write CSVs + manifest")
    p_exp.add_argument("video", help="Path to video file")
    p_exp.add_argument("--detector", choices=["content", "adaptive", "transnet"], default="content",
                       help="Hard-cut detector (default: content)")
    p_exp.add_argument("--threshold", type=float, default=27.0,
                       help="Detector threshold (ContentDetector default 27.0; "
                            "AdaptiveDetector default is ~3.0 — pass it explicitly)")
    p_exp.add_argument("--noise-floor", type=float, default=3.0,
                       help="Minimum score for a dissolve frame (default: 3.0)")
    p_exp.add_argument("--min-frames", type=int, default=15,
                       help="Minimum consecutive dissolve frames (default: 15)")
    p_exp.add_argument("--no-dissolves", action="store_true",
                       help="Skip the dissolve pass (hard-cut-only ablation)")
    p_exp.add_argument("--no-cache", action="store_true",
                       help="Force recompute of frame scores and cut lists")

    p_cmp = sub.add_parser("compare", help="Score detections against manual coding")
    p_cmp.add_argument("detections", help="Path to *_detections.csv")
    p_cmp.add_argument("manual", help="Path to manually coded CSV")
    p_cmp.add_argument("--tolerance", type=float, default=2.0,
                       help="Match window in seconds (default: 2.0; use ~1.0 for fast shows)")
    p_cmp.add_argument("--start", default=None,
                       help="Coding-window start (sec or MM:SS) for segment-based coding")
    p_cmp.add_argument("--end", default=None,
                       help="Coding-window end (sec or MM:SS)")

    p_swp = sub.add_parser("sweep", help="Grid-search dissolve params against manual coding")
    p_swp.add_argument("video", help="Video path (caches used if present)")
    p_swp.add_argument("manual", help="Path to manually coded CSV")
    p_swp.add_argument("--detector", choices=["content", "adaptive", "transnet"], default="content")
    p_swp.add_argument("--threshold", type=float, default=27.0)
    p_swp.add_argument("--tolerance", type=float, default=2.0)
    p_swp.add_argument("--floors", default="2,3,4,5",
                       help="Comma-separated noise_floor values (default: 2,3,4,5)")
    p_swp.add_argument("--frames", default="8,12,15,20",
                       help="Comma-separated min_frames values (default: 8,12,15,20)")
    p_swp.add_argument("--start", default=None,
                       help="Coding-window start (sec or MM:SS) — match compare's window")
    p_swp.add_argument("--end", default=None,
                       help="Coding-window end (sec or MM:SS)")

    p_sum = sub.add_parser("summary", help="Aggregate comparison CSVs across episodes")
    p_sum.add_argument("directory", nargs="?", default=None)
    p_sum.add_argument("--detector", default=None,
                       help="Only this detector config, e.g. content-t27-diss. "
                            "Default: one table per detector found.")

    p_cls = sub.add_parser("classify",
                           help="Label each hard cut within_scene vs "
                                "scene_change (experimental)")
    p_cls.add_argument("video", help="Path to video file")
    p_cls.add_argument("--detector", choices=["content", "adaptive", "transnet"],
                       default="content")
    p_cls.add_argument("--threshold", type=float, default=27.0)
    p_cls.add_argument("--offset", type=float, default=1.0,
                       help="Seconds from the cut to sample comparison frames "
                            "(default: 1.0, clamped near adjacent cuts)")
    p_cls.add_argument("--sim-threshold", type=float, default=0.55,
                       help="Similarity below this = scene_change "
                            "(default: 0.55, UNVALIDATED)")

    p_gc = sub.add_parser("grade-cuts",
                          help="Grade within/scene-change classifier against "
                               "hand-labeled scene_relation column")
    p_gc.add_argument("video", help="Path to video file")
    p_gc.add_argument("manual", help="Manual CSV with a scene_relation column")
    p_gc.add_argument("--detector", choices=["content", "adaptive", "transnet"],
                      default="content")
    p_gc.add_argument("--threshold", type=float, default=27.0)
    p_gc.add_argument("--tolerance", type=float, default=2.0)
    p_gc.add_argument("--offset", type=float, default=1.0,
                      help="Seconds from cut to sample comparison frames")
    p_gc.add_argument("--start", default=None, help="Window start (sec or MM:SS)")
    p_gc.add_argument("--end", default=None, help="Window end (sec or MM:SS)")

    p_st = sub.add_parser("status", help="Show where an episode is in the workflow")
    p_st.add_argument("video", help="Video path (stem used for lookup)")

    args = parser.parse_args()
    {"template": cmd_template, "export": cmd_export, "compare": cmd_compare,
     "sweep": cmd_sweep, "summary": cmd_summary, "status": cmd_status,
     "classify": cmd_classify, "grade-cuts": cmd_grade_cuts}[args.command](args)


if __name__ == "__main__":
    main()
