"""
Turning a pipeline's Selection node into a real, discoverable narrowed sample.

Excluding episodes on a Selection node writes selected.csv + manifest.json in
a new sibling folder — exactly what `analyzer.sampler.write_outputs` writes
for an Episode Sampler draw. That is deliberate, not incidental:
`CLAUDE.md`'s terminology table says Selection is "a property of the study...
recorded in a manifest," and every scope in this app — the Showing: chooser,
the Trials tab, `analyzer.pipeline.build_pipelines` — already discovers
samples by finding a manifest.json + selected.csv pair
(`analyzer.trials._discover_sample_trials`). Reusing that machinery means a
narrowed selection needs no new discovery code and cannot silently disagree
with the chooser the way a pipeline-canvas-only exclude list would have (see
`DECISIONS.md` for the alternative that was rejected and why).

Pure data; zero GUI imports.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from .scope import normalize

FIELDNAMES = ["entry_id", "season", "episode", "title", "air_date", "filepath"]


# --- shared plumbing ---------------------------------------------------------

def _read_rows(folder: Path) -> list[dict] | None:
    """Rows from *folder*'s selected.csv, or None if there isn't one."""
    csv_path = Path(folder) / "selected.csv"
    if not csv_path.exists():
        return None
    with csv_path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _read_manifest(folder: Path) -> dict:
    p = Path(folder) / "manifest.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_rows(outdir: Path, rows: list[dict], manifest: dict) -> None:
    outdir.mkdir(parents=True)
    with (outdir / "selected.csv").open(
            "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=list(rows[0].keys()) if rows else FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    (outdir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")


def _narrowed_manifest(source_manifest: dict, source_name: str, kept: int,
                       total_before: int, note: str) -> dict:
    return {
        **source_manifest,
        "trial_name": f"{source_name} — Selection",
        "method": f"{source_manifest.get('method', 'selection')} + selection",
        "total_selected": kept,
        "total_available": source_manifest.get("total_available", total_before),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "notes": list(source_manifest.get("notes") or []) + [note],
    }


def _outdir(anchor_folder: Path) -> Path:
    """A dated, descriptive, never-overwritten folder beside *anchor_folder*.

    Same convention as `ui.sampler.SamplerDialog._outdir`, so every kind of
    draw sits side by side and nothing has to special-case where to look.
    """
    stem = f"{anchor_folder.name}_selection_{datetime.now(timezone.utc):%Y-%m-%d}"
    outdir = anchor_folder.parent / stem
    counter = 2
    while outdir.exists():
        outdir = anchor_folder.parent / f"{stem}_{counter}"
        counter += 1
    return outdir


# --- one Sampling node feeding the Selection node ----------------------------

def write_narrowed_selection(
    source_folder: Path,
    source_name: str,
    exclude: set[Path],
    node_id: str,
) -> Path | None:
    """Write *source_folder*'s sample minus *exclude* as a new, discoverable
    sample folder sibling to it.

    Returns the new folder, or None if the source has no `selected.csv` to
    narrow, or nothing in *exclude* was actually in the sample (writing an
    identical copy would just be a confusing duplicate in the chooser).
    """
    rows = _read_rows(source_folder)
    if rows is None:
        return None
    excluded_norm = {normalize(p) for p in exclude}
    kept = [r for r in rows
            if (r.get("filepath") or "").strip()
            and normalize(r["filepath"]) not in excluded_norm]
    if len(kept) == len(rows):
        return None

    outdir = _outdir(Path(source_folder))
    removed = len(rows) - len(kept)
    note = (f"Derived from {source_folder} by excluding {removed} "
           f"episode{'s' if removed != 1 else ''} at pipeline Selection "
           f"node {node_id}.")
    manifest = _narrowed_manifest(_read_manifest(source_folder), source_name,
                                  len(kept), len(rows), note)
    _write_rows(outdir, kept, manifest)
    return outdir


# --- more than one Sampling node feeding the Selection node ------------------

def write_narrowed_selection_from_sources(
    source_folders: list[Path],
    source_name: str,
    exclude: set[Path],
    node_id: str,
) -> Path | None:
    """Same idea as `write_narrowed_selection`, but *source_folders* is more
    than one sample — a Selection node fed by more than one Sampling node.

    Rows are de-duplicated by filepath first (two branches can legitimately
    draw the same episode; it should appear once, not twice, in the narrowed
    sample), then filtered by *exclude* exactly as the single-source case.
    Without this, a Selection node wired to two Sampling nodes would only
    ever narrow the first branch and silently drop the second one's episodes
    entirely — the bug this function exists to not have.

    Returns None if none of *source_folders* has a `selected.csv`, or if
    nothing in *exclude* was actually in the union.
    """
    rows_by_path: dict[Path, dict] = {}
    manifests: list[dict] = []
    for folder in source_folders:
        rows = _read_rows(folder)
        if rows is None:
            continue
        for r in rows:
            fp = (r.get("filepath") or "").strip()
            if fp:
                rows_by_path.setdefault(normalize(fp), r)
        manifests.append(_read_manifest(folder))
    if not rows_by_path:
        return None

    excluded_norm = {normalize(p) for p in exclude}
    kept = [r for path, r in rows_by_path.items() if path not in excluded_norm]
    if len(kept) == len(rows_by_path):
        return None

    outdir = _outdir(Path(source_folders[0]))
    removed = len(rows_by_path) - len(kept)
    note = (f"Derived from the union of {len(source_folders)} samples by "
           f"excluding {removed} episode{'s' if removed != 1 else ''} at "
           f"pipeline Selection node {node_id}.")
    base_manifest = manifests[0] if manifests else {}
    manifest = _narrowed_manifest(base_manifest, source_name, len(kept),
                                  len(rows_by_path), note)
    _write_rows(outdir, kept, manifest)
    return outdir
