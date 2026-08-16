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
    src_csv = Path(source_folder) / "selected.csv"
    if not src_csv.exists():
        return None
    with src_csv.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))

    excluded_norm = {normalize(p) for p in exclude}
    kept = [r for r in rows
            if (r.get("filepath") or "").strip()
            and normalize(r["filepath"]) not in excluded_norm]
    if len(kept) == len(rows):
        return None

    src_manifest: dict = {}
    src_manifest_path = Path(source_folder) / "manifest.json"
    if src_manifest_path.exists():
        try:
            src_manifest = json.loads(
                src_manifest_path.read_text(encoding="utf-8"))
        except Exception:
            src_manifest = {}

    outdir = _outdir(Path(source_folder))
    outdir.mkdir(parents=True)

    with (outdir / "selected.csv").open(
            "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=list(rows[0].keys()) if rows else FIELDNAMES)
        writer.writeheader()
        writer.writerows(kept)

    removed = len(rows) - len(kept)
    manifest = {
        **src_manifest,
        "trial_name": f"{source_name} — Selection",
        "method": f"{src_manifest.get('method', 'selection')} + selection",
        "total_selected": len(kept),
        "total_available": src_manifest.get("total_available", len(rows)),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "notes": list(src_manifest.get("notes") or []) + [
            f"Derived from {source_folder} by excluding {removed} "
            f"episode{'s' if removed != 1 else ''} at pipeline Selection "
            f"node {node_id}.",
        ],
    }
    (outdir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    return outdir


def _outdir(source_folder: Path) -> Path:
    """A dated, descriptive, never-overwritten folder beside the source draw.

    Same convention as `ui.sampler.SamplerDialog._outdir`, so both kinds of
    draw sit side by side and nothing has to special-case where to look.
    """
    stem = f"{source_folder.name}_selection_{datetime.now(timezone.utc):%Y-%m-%d}"
    outdir = source_folder.parent / stem
    counter = 2
    while outdir.exists():
        outdir = source_folder.parent / f"{stem}_{counter}"
        counter += 1
    return outdir
