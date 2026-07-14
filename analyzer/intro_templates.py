"""
Intro templates — code a show's title sequence once, reuse it everywhere.

A show's intro is (near-)identical across episodes within a season/era, so the
coder saves its coded rows once as a named template ("Little Bear S1",
"SpongeBob 90s intro") and inserts them into other episodes' sheets instead of
re-coding the same 40 seconds every time.

Storage: validation/intro_templates.json — rows hold OFFSETS from the intro's
start, so a template can be inserted at any absolute time (cold opens shift
intros). Inserted rows are provenance-tagged "[intro: <name>]" in notes.

Methodological note (see CODEBOOK): inserting a template asserts the intro is
identical in this episode — spot-check one or two transitions after inserting,
since syndication/DVD cuts can differ by a second or drop the sequence.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from .validation import get_validation_dir

_REGISTRY_NAME = "intro_templates.json"

# Columns never stored in a template (recomputed on insert)
_TIME_KEYS = {"timestamp_hms", "timestamp_sec"}


def _registry_path(validation_dir: Path | None = None) -> Path:
    return (validation_dir or get_validation_dir()) / _REGISTRY_NAME


def load_templates(validation_dir: Path | None = None) -> dict[str, dict]:
    p = _registry_path(validation_dir)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_template(
    name: str,
    schema: str,
    rows: list[dict],
    start_sec: float,
    end_sec: float,
    source_sheet: str,
    validation_dir: Path | None = None,
) -> dict[str, Any]:
    """Capture rows in [start_sec, end_sec] as offsets and store under *name*.

    `rows` are editor rows with a parsed absolute time under `_abs_sec`.
    Existing "[intro: …]" tags are stripped from notes so re-saving inserted
    rows never nests provenance tags. Overwrites an existing template of the
    same name (that's how you update one).
    """
    name = name.strip()
    if not name:
        raise ValueError("Template needs a name (e.g. 'Little Bear S1 intro').")
    captured = []
    for r in rows:
        t = r.get("_abs_sec")
        if t is None or not (start_sec <= t <= end_sec):
            continue
        row = {k: v for k, v in r.items()
               if k not in _TIME_KEYS and not k.startswith("_")}
        note = (row.get("notes") or "")
        if "[intro:" in note:
            note = note.split("[intro:")[0].rstrip()
            row["notes"] = note
        row["offset_sec"] = round(t - start_sec, 3)
        captured.append(row)
    if not captured:
        raise ValueError(
            f"No coded rows between {start_sec:.0f}s and {end_sec:.0f}s — "
            f"code the intro first, then save it as a template.")
    captured.sort(key=lambda r: r["offset_sec"])

    templates = load_templates(validation_dir)
    templates[name] = {
        "schema": schema,
        "span_sec": round(end_sec - start_sec, 3),
        "n_rows": len(captured),
        "rows": captured,
        "source_sheet": source_sheet,
        "created": str(date.today()),
    }
    p = _registry_path(validation_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(templates, indent=2), encoding="utf-8")
    return templates[name]


def apply_template(
    template: dict,
    at_sec: float,
) -> list[dict]:
    """Instantiate a template at an absolute start time.

    Returns editor-style rows with `_abs_sec` set (caller formats the
    timestamp) and notes provenance-tagged. Never mutates the template.
    """
    out = []
    for r in template.get("rows", []):
        row = {k: v for k, v in r.items() if k != "offset_sec"}
        row["_abs_sec"] = round(at_sec + float(r["offset_sec"]), 3)
        note = (row.get("notes") or "").strip()
        tag = f"[intro: {template.get('_name', 'template')}]"
        row["notes"] = f"{note} {tag}".strip() if note else tag
        out.append(row)
    return out


def delete_template(name: str, validation_dir: Path | None = None) -> bool:
    templates = load_templates(validation_dir)
    if name not in templates:
        return False
    del templates[name]
    _registry_path(validation_dir).write_text(
        json.dumps(templates, indent=2), encoding="utf-8")
    return True
