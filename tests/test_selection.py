"""
A pipeline Selection node's exclude action: `analyzer.selection`.

The design bet here (see `analyzer/selection.py`'s docstring and `DECISIONS.md`)
is that excluding episodes should write a real sample folder — the same shape
an Episode Sampler draw writes — so it is discovered by the EXISTING sample
machinery with no new discovery code. These tests verify that bet against the
artefact it actually produces, and against the real discovery functions
(`analyzer.trials.discover_trials`, `analyzer.pipeline.build_pipelines`), not
just against `write_narrowed_selection`'s return value.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from analyzer.pipeline import build_pipelines
from analyzer.selection import write_narrowed_selection
from analyzer.trials import discover_trials


def _write_source_sample(tmp_path: Path, episodes: list[Path],
                          name: str = "draw") -> Path:
    """A sampler-shaped folder: selected.csv AND manifest.json, so it is a
    real discoverable sample, not just a CSV `write_narrowed_selection` can
    read."""
    folder = tmp_path / name
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "selected.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["entry_id", "season", "episode", "title",
                            "air_date", "filepath"])
        writer.writeheader()
        for i, ep in enumerate(episodes, start=1):
            writer.writerow({"entry_id": "Show", "season": 1, "episode": i,
                             "title": f"Ep {i}", "air_date": "",
                             "filepath": str(ep)})
    (folder / "manifest.json").write_text(json.dumps({
        "method": "systematic", "total_selected": len(episodes),
        "total_available": len(episodes) + 10, "entry_id": "Show",
        "trial_name": "Pilot", "generated_at_utc": "2026-01-01T00:00:00Z",
    }), encoding="utf-8")
    return folder


def _episodes(tmp_path: Path, n: int) -> list[Path]:
    show = tmp_path / "Show"
    show.mkdir(exist_ok=True)
    paths = []
    for i in range(1, n + 1):
        p = show / f"S01 E{i:02d}.mp4"
        p.write_bytes(b"")
        paths.append(p)
    return paths


# --- the artefact itself ------------------------------------------------------

def test_narrowed_selection_drops_only_the_excluded_rows(tmp_path):
    episodes = _episodes(tmp_path, 3)
    source = _write_source_sample(tmp_path, episodes)

    outdir = write_narrowed_selection(
        source, "Pilot", {episodes[1]}, "node-selection-1")

    assert outdir is not None
    with (outdir / "selected.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    kept_paths = {Path(r["filepath"]) for r in rows}
    assert kept_paths == {episodes[0], episodes[2]}, \
        "exactly the excluded episode must be gone, the other two intact"

    manifest = json.loads((outdir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["total_selected"] == 2
    assert "Selection" in manifest["trial_name"]
    assert "node-selection-1" in manifest["notes"][-1]


def test_narrowing_by_nothing_writes_nothing(tmp_path):
    """Excluding a path not actually in the sample must not fabricate a
    duplicate, identical entry in the chooser."""
    episodes = _episodes(tmp_path, 2)
    source = _write_source_sample(tmp_path, episodes)
    not_in_sample = tmp_path / "Show" / "S01 E99.mp4"

    outdir = write_narrowed_selection(
        source, "Pilot", {not_in_sample}, "node-1")

    assert outdir is None


def test_narrowing_with_no_source_csv_is_refused(tmp_path):
    empty_folder = tmp_path / "empty"
    empty_folder.mkdir()
    outdir = write_narrowed_selection(
        empty_folder, "Pilot", {tmp_path / "x.mp4"}, "node-1")
    assert outdir is None


# --- discovery: the whole point of writing it this way ------------------------

def test_a_narrowed_selection_is_discovered_like_a_sampler_draw(tmp_path):
    """No new discovery code was written for this — `discover_trials` must
    find the narrowed folder exactly as it finds any other sampler draw."""
    episodes = _episodes(tmp_path, 4)
    source = _write_source_sample(tmp_path, episodes)
    outdir = write_narrowed_selection(
        source, "Pilot", {episodes[0], episodes[1]}, "node-1")

    trials = discover_trials(extra_dirs=[tmp_path])
    samples = [t for t in trials if t.get("kind") == "episode_sample"]
    found = {t["folder"] for t in samples}
    assert source in found
    assert outdir in found
    narrowed = next(t for t in samples if t["folder"] == outdir)
    assert narrowed["n_episodes"] == 2
    assert "Selection" in narrowed["name"]


def test_a_narrowed_selection_becomes_its_own_pipeline(tmp_path):
    """The real target: it must appear as a distinct entry `build_pipelines`
    (and therefore the Showing: chooser) can offer, with its own key."""
    episodes = _episodes(tmp_path, 4)
    source = _write_source_sample(tmp_path, episodes)
    outdir = write_narrowed_selection(
        source, "Pilot", {episodes[0]}, "node-1")

    pipelines = build_pipelines(tmp_path, validation_dir=tmp_path)
    keys = {p.key: p for p in pipelines}
    assert f"sample:{source}" in keys
    assert f"sample:{outdir}" in keys
    assert keys[f"sample:{source}"].episode_count == 4
    assert keys[f"sample:{outdir}"].episode_count == 3
    assert keys[f"sample:{source}"].key != keys[f"sample:{outdir}"].key
