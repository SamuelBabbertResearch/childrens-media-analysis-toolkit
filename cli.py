"""
Command-line interface for the Children's Media Analysis Toolkit (CMAT).

Usage:
    python cli.py analyze <file.mp4>            # analyze one episode
    python cli.py analyze <show_folder/>        # batch analyze all episodes + aggregate
    python cli.py shows <root_folder/>          # list all shows under root
    python cli.py db episodes <root_folder/>    # print episode index table
    python cli.py db shows <root_folder/>       # print show index table
    python cli.py sample <entry_root/>          # build reproducible episode sample
    python cli.py study-clips <season_folder/>  # screen contiguous 30-second clips
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

from analyzer import recipes as analysis_recipes
from analyzer.aggregate import compute_show_aggregate, save_show_results
from analyzer.batch import analyze_show_batch
from analyzer.cache import load_cached, load_scored, save_cache
from analyzer.config_loader import load_config
from analyzer.db import get_db, query_episodes, query_shows
from analyzer.engine import analyze_episode
from analyzer.sampler import scan_entry_root, load_registry_csv, sample, write_outputs
from analyzer.show_index import db_show_key, display_show_name, list_episodes, list_shows, show_key
from analyzer.speech import _find_cc_file
from analyzer.study_clips import export_selected_clips, run_candidate_pool
from generate_study_clip_tables import generate_tables as generate_study_tables


def _resolve_analysis_recipe(selector: str, source: Path):
    """Resolve a recipe path, id, exact name, or citation near the library."""
    candidate = Path(selector).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    if candidate.is_file():
        return analysis_recipes.load_recipe(candidate.resolve())

    roots: list[Path] = []
    for root in (Path.cwd().resolve(), *source.resolve().parents):
        if root not in roots:
            roots.append(root)
    recipes = []
    seen = set()
    for root in roots:
        for recipe in analysis_recipes.list_recipes(root):
            if recipe.id not in seen:
                recipes.append(recipe)
                seen.add(recipe.id)
    wanted = selector.casefold()
    matches = [
        recipe for recipe in recipes
        if wanted in {
            recipe.id.casefold(), recipe.name.casefold(),
            recipe.citation().casefold(),
        }
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(
            f"Recipe selector {selector!r} is ambiguous; use a recipe id or path"
        )
    available = ", ".join(recipe.name for recipe in recipes) or "none"
    raise ValueError(
        f"No analysis recipe matches {selector!r}. Available recipes: {available}"
    )


def cmd_analyze(args: argparse.Namespace) -> None:
    target = Path(args.path).resolve()
    cfg = load_config()
    root = Path(args.root).resolve() if getattr(args, "root", "") else None

    if target.is_file() and target.suffix.lower() == ".mp4":
        _analyze_single(target, cfg, force=args.force, root=root)
    elif target.is_dir():
        _analyze_batch(target, cfg, force=args.force, root=root)
    else:
        print(f"Error: {target} is not an MP4 file or a directory.", file=sys.stderr)
        sys.exit(1)


def cmd_study_clips(args: argparse.Namespace) -> None:
    source = Path(args.source).resolve()
    if not source.is_dir():
        print(f"Error: source folder does not exist: {source}", file=sys.stderr)
        sys.exit(1)
    output = (
        Path(args.output).resolve()
        if args.output
        else (Path.cwd() / ".analysis" / "study_clips" / source.name).resolve()
    )
    try:
        recipe = (
            _resolve_analysis_recipe(args.recipe, source)
            if args.recipe else None
        )
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    def _status(message: str) -> None:
        print(f"  {message}", flush=True)

    print(f"Candidate pool: {source}")
    print(f"Output:         {output}")
    print(f"Window:         {args.window_sec:g} seconds\n")
    if recipe is not None:
        print(f"Recipe:         {recipe.citation()}\n")
    if args.exclude_first or args.exclude_last:
        print(
            f"Episode range:  skip first {args.exclude_first:g}s and "
            f"last {args.exclude_last:g}s\n"
        )
    try:
        run = run_candidate_pool(
            source,
            output,
            window_sec=args.window_sec,
            include_partial=args.include_partial,
            exclude_first_sec=args.exclude_first,
            exclude_last_sec=args.exclude_last,
            recursive=not args.flat,
            resume=not args.fresh,
            max_files=args.max_files,
            analysis_recipe=recipe,
            status_cb=_status,
        )
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    manifest = run["manifest"]
    print("\nCandidate measurement complete:")
    print(f"  Source files:     {manifest['source_file_count']}")
    print(f"  30-second clips:  {manifest['candidate_clip_count']}")
    print(f"  Matched pairs:    {manifest['matched_pair_count']} / 6")
    print(f"  Selected clips:   {manifest['selected_clip_count']} / 12")
    print(f"  Failures:         {manifest['failed_source_count']}")
    print(f"\n  Browse: {output / 'candidates.csv'}")
    print(f"  Pairs:  {output / 'matched_pairs.csv'}")
    print(f"  Run:    {output / 'manifest.json'}")

    if manifest["selected_clip_count"] == 12:
        try:
            tables_path = generate_study_tables(output)
            print(f"  Tables: {tables_path}")
        except (OSError, ValueError) as exc:
            print(f"\nCould not generate study tables: {exc}", file=sys.stderr)

    if manifest["matched_pair_count"] < 6:
        print(
            "\nNo complete Option 3.5 set could be formed under the current "
            "high/low and uniqueness constraints. Inspect pair_candidates.csv "
            "and the pool distributions before relaxing the design.",
            file=sys.stderr,
        )

    if args.export_selected:
        if not run["selected_clips"]:
            print("\nNo selected clips to export.", file=sys.stderr)
            return
        print("\nExporting and re-measuring the twelve finalist files...")
        exported = export_selected_clips(
            run["selected_clips"],
            output,
            config=run["config"],
            overwrite=args.overwrite_exports,
            status_cb=_status,
        )
        ok = sum(1 for row in exported if row.get("status") == "ok")
        print(f"\n  Finalists verified: {ok} / {len(exported)}")
        print(f"  Files: {output / 'finalists'}")
        print(f"  Final measurements: {output / 'finalist_measurements.csv'}")


# ---------------------------------------------------------------------------
# Single episode
# ---------------------------------------------------------------------------

def _analyze_single(
    episode: Path,
    cfg: dict,
    force: bool = False,
    root: Path | None = None,
) -> None:
    show_dir = episode.parent
    root = root or show_dir.parent
    try:
        skey = show_key(root, show_dir)
    except ValueError:
        print(f"Error: --root must contain the show folder: {show_dir}", file=sys.stderr)
        sys.exit(1)

    cached = None if force else load_cached(root, skey, episode.stem)
    if cached:
        # Re-scored against the current config, so the CLI and the GUI cannot
        # print different composites for one cached episode.
        print(f"[cache] {episode.name}")
        result = load_scored(root, skey, episode.stem, cfg)
        print(result.to_json() if result is not None
              else json.dumps(cached, indent=2))
        return

    def _progress(frac: float) -> None:
        if frac < 0:
            print("\r  [detecting cuts...]        ", end="", flush=True)
            return
        frac = max(0.0, min(1.0, frac))
        filled = int(frac * 30)
        bar = "#" * filled + "-" * (30 - filled)
        print(f"\r  [{bar}] {int(frac * 100):3d}%", end="", flush=True)

    print(f"Analyzing {episode.name} ...")
    result = analyze_episode(episode, config=cfg, progress_cb=_progress)
    print()

    save_cache(root, skey, episode.stem, result.to_dict())

    if result.status == "failed":
        print(f"Error: {result.error}", file=sys.stderr)
        sys.exit(1)

    print(result.to_json())


# ---------------------------------------------------------------------------
# Batch (show folder)
# ---------------------------------------------------------------------------

def _analyze_batch(
    show_dir: Path,
    cfg: dict,
    force: bool = False,
    root: Path | None = None,
) -> None:
    root = root or show_dir.parent
    try:
        skey = show_key(root, show_dir)
    except ValueError:
        print(f"Error: --root must contain the show folder: {show_dir}", file=sys.stderr)
        sys.exit(1)
    dname, _ = display_show_name(root, show_dir)
    episodes = list_episodes(show_dir)

    if not episodes:
        print(f"No MP4 files found in {show_dir}")
        return

    print(f"Show: {show_dir.name}  ({len(episodes)} episode(s))\n")

    current_ep: list[str] = [""]

    def _progress(ep_name: str, ep_frac: float, overall_frac: float) -> None:
        if ep_name != current_ep[0]:
            if current_ep[0]:
                print()  # newline after previous episode's bar
            current_ep[0] = ep_name
            print(f"  {ep_name}")
        if ep_frac < 0:
            print(f"\r    [detecting cuts...]        (overall {int(max(0.0, overall_frac) * 100):3d}%)",
                  end="", flush=True)
            return
        ep_frac = max(0.0, min(1.0, ep_frac))
        overall_frac = max(0.0, min(1.0, overall_frac))
        filled = int(ep_frac * 30)
        bar = "#" * filled + "-" * (30 - filled)
        print(f"\r    [{bar}] {int(ep_frac * 100):3d}%  (overall {int(overall_frac * 100):3d}%)",
              end="", flush=True)

    results = analyze_show_batch(
        show_dir, root=root, config=cfg, force=force, progress_cb=_progress
    )
    print("\n")

    # Summary table
    ok = [r for r in results if r.status == "ok"]
    failed = [r for r in results if r.status == "failed"]

    print(f"{'Episode':<30} {'Duration':>10} {'Cuts/min':>10} {'Saturation':>12} "
          f"{'Motion':>8} {'Flash/min':>10} {'Load':>6}")
    print("-" * 92)
    for r in results:
        if r.status == "failed":
            print(f"  {r.file:<28} {'FAILED':>10}  {r.error[:40]}")
        else:
            m = r.metrics
            print(
                f"  {r.file:<28} {r.duration_sec:>9.0f}s "
                f"{m.scene_pacing.cuts_per_min:>10.1f} "
                f"{m.color_saturation.mean:>12.3f} "
                f"{m.motion.mean:>8.3f} "
                f"{m.flashing.luminance_delta_events_per_min:>10.1f} "
                f"{m.sensory_load.score:>6.3f}"
            )

    print()

    if not ok:
        print("All episodes failed — no aggregate computed.", file=sys.stderr)
        sys.exit(1)

    if failed:
        print(f"Warning: {len(failed)} episode(s) failed and were excluded from aggregate.\n")

    aggregate = compute_show_aggregate(dname, results)
    json_path, csv_path = save_show_results(root, skey, results, aggregate)

    print("Show aggregate:")
    print(aggregate.to_json())
    print(f"\nSaved: {json_path.relative_to(root)}")
    print(f"       {csv_path.relative_to(root)}")


# ---------------------------------------------------------------------------
# Shows listing
# ---------------------------------------------------------------------------

def cmd_shows(args: argparse.Namespace) -> None:
    root = Path(args.root)
    if not root.is_dir():
        print(f"Error: {root} is not a directory.", file=sys.stderr)
        sys.exit(1)

    shows = list_shows(root)
    if not shows:
        print("No show folders found (folders containing .mp4 files).")
        return

    print(f"Root: {root}")
    for show in shows:
        eps = list_episodes(show)
        print(f"  {show.name}/  — {len(eps)} episode(s)")
        for ep in eps:
            print(f"    {ep.name}")


# ---------------------------------------------------------------------------
# DB index queries
# ---------------------------------------------------------------------------

def _db_backfill(root: Path) -> None:
    """Seed the index DB from all cached episode JSONs — mirrors what the GUI does on folder open."""
    from analyzer.cache import load_scored
    from analyzer.config_loader import load_config
    from analyzer.db import get_db, rebuild_show_aggregates

    cfg = load_config()
    conn = get_db(root)
    # Re-scored: the index stores the composite, so backfilling it from a raw
    # cache read would write scores under whatever weights each episode
    # happened to be analysed with.
    rebuild_show_aggregates(
        conn, root,
        fetch_result=lambda show_dir, skey, ep: load_scored(root, skey, ep.stem, cfg),
    )
    conn.close()


def cmd_db(args: argparse.Namespace) -> None:
    root = Path(args.root)
    if not root.is_dir():
        print(f"Error: {root} is not a directory.", file=sys.stderr)
        sys.exit(1)

    # Reconfigure stdout to UTF-8 so filenames with emoji/non-ASCII print safely
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    _db_backfill(root)   # ensure index is up to date before querying
    conn = get_db(root)
    sort_by = args.sort or ("analyzed_at" if args.table == "episodes" else "avg_load")
    ascending = not args.desc

    if args.table == "episodes":
        rows = query_episodes(conn, sort_by=sort_by, ascending=ascending,
                              filter_show=args.show or "")
        if not rows:
            print("No episodes in index.  Run 'analyze' first, or choose the root folder in the GUI.")
            return
        hdr = f"{'Show':<22} {'File':<28} {'C/min':>6} {'Sat':>5} {'Mot':>5} {'RMS':>7} {'Load':>6}  {'Date'}"
        print(hdr)
        print("-" * len(hdr))
        for r in rows:
            cpm  = f"{r['cuts_per_min']:.1f}"          if r["cuts_per_min"]           is not None else "—"
            sat  = f"{r['color_saturation_mean']:.3f}" if r["color_saturation_mean"]  is not None else "—"
            mot  = f"{r['motion_mean']:.3f}"            if r["motion_mean"]            is not None else "—"
            rms  = f"{r['audio_rms_mean']:.4f}"         if r["audio_rms_mean"]         is not None else "n/a"
            load = f"{r['sensory_load_score']:.3f}"     if r["sensory_load_score"]     is not None else "—"
            date = (r["analyzed_at"] or "")[:16]
            print(f"  {r['show_name']:<20} {r['file_name']:<28} "
                  f"{cpm:>6} {sat:>5} {mot:>5} {rms:>7} {load:>6}  {date}")

    elif args.table == "shows":
        rows = query_shows(conn, sort_by=sort_by, ascending=ascending)
        if not rows:
            print("No shows in index.  Run 'analyze' on a show folder first.")
            return
        hdr = f"{'Show':<30} {'Eps':>4} {'Avg Load':>9} {'Avg C/min':>10} {'Avg Mot':>8} {'Avg Sat':>8}"
        print(hdr)
        print("-" * len(hdr))
        for r in rows:
            load = f"{r['avg_load']:.3f}"         if r["avg_load"]         is not None else "—"
            cpm  = f"{r['avg_cuts_per_min']:.1f}" if r["avg_cuts_per_min"] is not None else "—"
            mot  = f"{r['avg_motion']:.3f}"        if r["avg_motion"]       is not None else "—"
            sat  = f"{r['avg_saturation']:.3f}"    if r["avg_saturation"]   is not None else "—"
            print(f"  {r['show_name']:<28} {r['episode_count']:>4} "
                  f"{load:>9} {cpm:>10} {mot:>8} {sat:>8}")


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Sample command
# ---------------------------------------------------------------------------

def cmd_sample(args: argparse.Namespace) -> None:
    root = Path(args.entry_root)
    if args.registry:
        episodes = load_registry_csv(Path(args.registry), entry_id=args.entry_id)
    else:
        if not root.is_dir():
            print(f"Error: {root} is not a directory.", file=sys.stderr)
            sys.exit(1)
        episodes = scan_entry_root(root, entry_id=args.entry_id or None)

    if not episodes:
        print("No episodes found.", file=sys.stderr)
        sys.exit(1)

    eid = args.entry_id or root.name

    result = sample(
        episodes,
        entry_id=eid,
        stratify_by=None if args.stratify == "none" else args.stratify,
        method=args.method,
        allocation=args.allocation,
        per_stratum_n=args.per_season_n,
        total_n=args.total_n,
        floor=args.floor,
        interval_k=args.interval_k,
        sort_col=args.sort,
        seed=args.seed,
        manual_list=args.manual_list.split(",") if args.manual_list else None,
    )

    # Determine output dir
    if args.output:
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        outdir = Path(args.output) / ts
    else:
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        outdir = root.parent / f"_samples_{ts}"

    paths = write_outputs(result, outdir, gather=args.gather, copy_files=args.copy)

    print(f"Selected {result.manifest.total_selected} / {result.manifest.total_available} episodes")
    print(f"  CSV:       {paths['csv']}")
    print(f"  Manifest:  {paths['manifest']}")
    print(f"  Worklist:  {paths['worklist']}")
    if "files" in paths:
        print(f"  Files:     {paths['files']}")

    if result.manifest.notes:
        print("\nNotes:")
        for n in result.manifest.notes:
            print(f"  * {n}")


# ---------------------------------------------------------------------------
# Vocab complexity command
# ---------------------------------------------------------------------------

def cmd_vocab(args: argparse.Namespace) -> None:
    from analyzer.vocab_complexity import load_norms, analyze_caption_file, batch_analyze

    norm_dir = Path(args.norms) if args.norms else None
    try:
        norms = load_norms(norm_dir) if norm_dir else load_norms()
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    target    = Path(args.target)
    cc_paths: list[Path] = []

    if target.is_file() and target.suffix.lower() in (".srt", ".vtt"):
        # Single caption file — print result inline
        result = analyze_caption_file(target, norms=norms)
        if result.status == "failed":
            print(f"Error: {result.error}", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(result.to_flat_row(), indent=2))
        return

    elif target.is_file() and target.suffix.lower() == ".txt":
        # Worklist file (sampler output: one path per line, # comments ignored)
        for raw in target.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            p = Path(line)
            if p.suffix.lower() in (".srt", ".vtt") and p.exists():
                cc_paths.append(p)
            elif p.exists():
                # Video path — try to find a CC file alongside it
                cc = _find_cc_file(p)
                if cc:
                    cc_paths.append(cc)
                else:
                    print(f"  [skip] no CC file found alongside {p.name}", flush=True)

    elif target.is_dir():
        for ext in ("*.srt", "*.vtt"):
            cc_paths.extend(sorted(target.glob(ext)))

    else:
        print(
            f"Error: '{target}' is not a .srt/.vtt file, a .txt worklist, or a directory.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not cc_paths:
        print("No caption files found.", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.output) if args.output else None
    results, paths = batch_analyze(cc_paths, norms=norms, out_dir=out_dir)

    ok      = sum(1 for r in results if r.status == "ok")
    failed  = sum(1 for r in results if r.status == "failed")
    skipped = sum(1 for r in results if r.status == "skipped")

    print(f"\nDone — {len(cc_paths)} file(s): {ok} ok, {failed} failed, {skipped} skipped")
    print(f"  CSV:      {paths['csv']}")
    print(f"  Manifest: {paths['manifest']}")

    if failed:
        print("\nFailed:")
        for r in results:
            if r.status == "failed":
                first_line = r.error.splitlines()[0] if r.error else "unknown error"
                print(f"  {r.episode_id}: {first_line}")
        sys.exit(1)


# Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Children's Media Analysis Toolkit (CMAT)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_analyze = sub.add_parser(
        "analyze", help="Analyze an episode (MP4) or all episodes in a show folder"
    )
    p_analyze.add_argument("path", help="Path to an MP4 file or a show folder")
    p_analyze.add_argument("--force", action="store_true", help="Re-analyze even if cached")
    p_analyze.add_argument(
        "--root",
        default="",
        help="Library root for cache paths; use this for categorized libraries to match the GUI",
    )
    p_analyze.set_defaults(func=cmd_analyze)

    p_shows = sub.add_parser("shows", help="List all shows under a root folder")
    p_shows.add_argument("root", help="Root folder containing show sub-folders")
    p_shows.set_defaults(func=cmd_shows)

    p_db = sub.add_parser("db", help="Query the persistent index database")
    db_sub = p_db.add_subparsers(dest="table", required=True)

    p_db_ep = db_sub.add_parser("episodes", help="List all indexed episodes")
    p_db_ep.add_argument("root", help="Root folder (where .analysis/index.db lives)")
    p_db_ep.add_argument("--show",  default="", help="Filter by show name substring")
    p_db_ep.add_argument("--sort",  default="", help="Sort column (e.g. sensory_load_score)")
    p_db_ep.add_argument("--desc",  action="store_true", help="Sort descending")
    p_db_ep.set_defaults(func=cmd_db)

    p_db_sh = db_sub.add_parser("shows", help="List all indexed shows")
    p_db_sh.add_argument("root", help="Root folder (where .analysis/index.db lives)")
    p_db_sh.add_argument("--sort",  default="", help="Sort column (e.g. avg_load)")
    p_db_sh.add_argument("--desc",  action="store_true", help="Sort descending")
    p_db_sh.set_defaults(func=cmd_db)

    p_sample = sub.add_parser("sample", help="Build a reproducible episode sample for analysis")
    p_sample.add_argument("entry_root", help="Entry root folder (or pass --registry instead)")
    p_sample.add_argument("--registry",    default="",    help="Path to a registry CSV (bypasses folder scan)")
    p_sample.add_argument("--entry-id",    default="",    dest="entry_id", help="Label for this entry/era")
    p_sample.add_argument("--stratify",    default="season",
                          choices=["none", "season"],
                          help="Stratify by: none | season (default: season)")
    p_sample.add_argument("--method",      default="spread",
                          choices=["census", "srs", "systematic", "spread", "manual"],
                          help="Selection method (default: spread)")
    p_sample.add_argument("--allocation",  default="equal",
                          choices=["equal", "proportional"],
                          help="Allocation for stratified sampling (default: equal)")
    p_sample.add_argument("--per-season-n", dest="per_season_n", type=int, default=2,
                          help="Episodes per stratum for equal allocation (default: 2)")
    p_sample.add_argument("--total-n",     dest="total_n",      type=int, default=None,
                          help="Total episodes for proportional allocation")
    p_sample.add_argument("--floor",       type=int, default=1,
                          help="Minimum per stratum for proportional allocation (default: 1)")
    p_sample.add_argument("--interval-k",  dest="interval_k",   type=int, default=None,
                          help="Explicit interval for systematic sampling")
    p_sample.add_argument("--sort",        default="episode",
                          choices=["episode", "air_date"],
                          help="Sort key within strata (default: episode)")
    p_sample.add_argument("--seed",        type=int, default=42,
                          help="Random seed (default: 42)")
    p_sample.add_argument("--manual-list", dest="manual_list", default="",
                          help="Comma-separated episode identifiers for manual method")
    p_sample.add_argument("--output",      default="",
                          help="Output directory (default: <entry_root_parent>/_samples_<timestamp>)")
    p_sample.add_argument("--gather",      action="store_true",
                          help="Copy/symlink selected files into output folder")
    p_sample.add_argument("--copy",        action="store_true",
                          help="Use full copies instead of symlinks when gathering")
    p_sample.set_defaults(func=cmd_sample)

    p_vocab = sub.add_parser(
        "vocab",
        help="Analyze vocabulary complexity, readability, and lexical diversity from caption files",
    )
    p_vocab.add_argument(
        "target",
        help=".srt/.vtt file | .txt worklist (one path per line) | folder of caption files",
    )
    p_vocab.add_argument(
        "--norms", default="",
        help="Path to norms directory containing kuperman_aoa.csv and brysbaert_concreteness.csv "
             "(default: data/norms/ relative to project root)",
    )
    p_vocab.add_argument(
        "--output", default="",
        help="Output directory for CSV and manifest (default: _vocab_<timestamp>/)",
    )
    p_vocab.set_defaults(func=cmd_vocab)

    p_study = sub.add_parser(
        "study-clips",
        help="Measure a season as contiguous clips and propose Option 3.5 matched pairs",
    )
    p_study.add_argument("source", help="Folder containing the source season videos")
    p_study.add_argument(
        "--output", default="",
        help="Run folder (default: .analysis/study_clips/<source folder name>)",
    )
    p_study.add_argument(
        "--recipe", default="",
        help=("Saved analysis recipe path, id, exact name, or citation. Its "
              "pinned cuts, motion, frame-sampling, and audio settings drive "
              "measurement and are copied into the run manifest."),
    )
    p_study.add_argument(
        "--window-sec", type=float, default=30.0, dest="window_sec",
        help="Contiguous clip duration in seconds (default: 30)",
    )
    p_study.add_argument(
        "--include-partial", action="store_true",
        help="Include each episode's final shorter-than-window remainder",
    )
    p_study.add_argument(
        "--exclude-first", type=float, default=0.0, dest="exclude_first",
        metavar="SECONDS",
        help="Skip this many seconds at the beginning of every episode",
    )
    p_study.add_argument(
        "--exclude-last", type=float, default=0.0, dest="exclude_last",
        metavar="SECONDS",
        help="Skip this many seconds at the end of every episode",
    )
    p_study.add_argument(
        "--flat", action="store_true",
        help="Read only the named folder, not nested folders",
    )
    p_study.add_argument(
        "--fresh", action="store_true",
        help="Ignore resumable per-episode measurements and run every source again",
    )
    p_study.add_argument(
        "--max-files", type=int, default=None, dest="max_files",
        help="Process only the first N source files (for a pilot/smoke test)",
    )
    p_study.add_argument(
        "--export-selected", action="store_true",
        help="Export the twelve proposed clips and re-measure the exact participant files",
    )
    p_study.add_argument(
        "--overwrite-exports", action="store_true",
        help="Replace existing finalist MP4 files when exporting",
    )
    p_study.set_defaults(func=cmd_study_clips)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
