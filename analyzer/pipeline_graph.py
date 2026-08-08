"""
Pipeline documents — editable graphs, persisted as JSON.

analyzer/pipeline.py DERIVES a read-only view of what is on disk. This module
is the other half: a pipeline the user OWNS and edits — nodes they place,
connections they draw, names they choose. The two meet at NodeType.stage_key,
which lets a node bind to live derived status without hardcoding either side.

Design rules that matter downstream:

  * Node positions live in the document, not the view. Resizing the window
    moves the viewport, never the diagram.
  * Node types are a registry, so a new stage is a dict entry rather than a UI
    rewrite. The five original stages are ordinary nodes of registered types
    with no special casing anywhere.
  * Connections are their own objects with explicit endpoints, so the graph can
    branch and merge instead of assuming one linear chain.
  * Everything round-trips through plain dicts, so undo/redo is a snapshot of
    to_dict() and persistence is json.dump of the same thing.

Pure data; zero GUI imports.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config_loader import _base_dir

SCHEMA_VERSION = 1

# --- node type registry ------------------------------------------------------


@dataclass(frozen=True)
class NodeType:
    key: str
    name: str
    description: str
    icon: str
    stage_key: str | None = None     # binds to analyzer.pipeline.Stage
    inputs: int = 1
    outputs: int = 1
    accent: str = "neutral"


NODE_TYPES: dict[str, NodeType] = {
    "sampling": NodeType(
        "sampling", "Sampling", "How episodes were chosen", "sampling",
        stage_key="sampling", inputs=0),
    "selection": NodeType(
        "selection", "Selection", "Working set and tracks", "selection",
        stage_key="selection"),
    "measurement": NodeType(
        "measurement", "Measurement", "Metrics and hand coding", "measurement",
        stage_key="measurement"),
    "validation": NodeType(
        "validation", "Validation", "Graded against humans", "validation",
        stage_key="validation"),
    "results": NodeType(
        "results", "Results", "Outputs and locations", "results",
        stage_key="results", outputs=1),
    "export": NodeType(
        "export", "Export", "Write a report or dataset", "export"),
    "note": NodeType(
        "note", "Note", "Free-text annotation", "note", inputs=0, outputs=0),
}

DEFAULT_CHAIN = ["sampling", "selection", "measurement", "validation", "results"]


def node_type(key: str) -> NodeType:
    return NODE_TYPES.get(key) or NODE_TYPES["note"]


# --- documents ---------------------------------------------------------------


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@dataclass
class GraphNode:
    id: str
    type: str
    title: str
    x: float
    y: float
    w: float = 196.0
    h: float = 96.0
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "type": self.type, "title": self.title,
                "x": self.x, "y": self.y, "w": self.w, "h": self.h,
                "config": dict(self.config)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "GraphNode":
        return cls(
            id=str(d.get("id") or _new_id("n")),
            type=str(d.get("type") or "note"),
            title=str(d.get("title") or node_type(d.get("type", "")).name),
            x=float(d.get("x", 0.0)), y=float(d.get("y", 0.0)),
            w=float(d.get("w", 196.0)), h=float(d.get("h", 96.0)),
            config=dict(d.get("config") or {}),
        )


@dataclass
class Connection:
    id: str
    src: str
    dst: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "src": self.src, "dst": self.dst}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Connection":
        return cls(id=str(d.get("id") or _new_id("c")),
                   src=str(d.get("src", "")), dst=str(d.get("dst", "")))


@dataclass
class PipelineDoc:
    id: str
    name: str
    nodes: list[GraphNode] = field(default_factory=list)
    connections: list[Connection] = field(default_factory=list)
    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    source_key: str | None = None     # links to a discovered episode sample
    path: Path | None = None

    # -- lookups --

    def node(self, node_id: str) -> GraphNode | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    def connections_of(self, node_id: str) -> list[Connection]:
        return [c for c in self.connections
                if c.src == node_id or c.dst == node_id]

    def has_connection(self, src: str, dst: str) -> bool:
        return any(c.src == src and c.dst == dst for c in self.connections)

    # -- mutation --

    def add_node(self, type_key: str, x: float, y: float,
                 title: str | None = None) -> GraphNode:
        t = node_type(type_key)
        n = GraphNode(id=_new_id("n"), type=t.key, title=title or t.name,
                      x=x, y=y)
        self.nodes.append(n)
        return n

    def remove_node(self, node_id: str) -> None:
        self.nodes = [n for n in self.nodes if n.id != node_id]
        self.connections = [c for c in self.connections
                            if c.src != node_id and c.dst != node_id]

    def connect(self, src: str, dst: str) -> Connection | None:
        """Add an edge, refusing self-links, duplicates, and simple cycles."""
        if src == dst or self.has_connection(src, dst):
            return None
        if not self.node(src) or not self.node(dst):
            return None
        if self._reaches(dst, src):
            return None                      # would close a loop
        c = Connection(id=_new_id("c"), src=src, dst=dst)
        self.connections.append(c)
        return c

    def _reaches(self, start: str, target: str) -> bool:
        seen: set[str] = set()
        stack = [start]
        while stack:
            cur = stack.pop()
            if cur == target:
                return True
            if cur in seen:
                continue
            seen.add(cur)
            stack += [c.dst for c in self.connections if c.src == cur]
        return False

    def disconnect(self, connection_id: str) -> None:
        self.connections = [c for c in self.connections
                            if c.id != connection_id]

    def bounds(self) -> tuple[float, float, float, float]:
        """(x0, y0, x1, y1) of all nodes; a unit box when empty."""
        if not self.nodes:
            return (0.0, 0.0, 1.0, 1.0)
        x0 = min(n.x for n in self.nodes)
        y0 = min(n.y for n in self.nodes)
        x1 = max(n.x + n.w for n in self.nodes)
        y1 = max(n.y + n.h for n in self.nodes)
        return (x0, y0, x1, y1)

    # -- serialisation --

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_VERSION,
            "id": self.id,
            "name": self.name,
            "source_key": self.source_key,
            "view": {"zoom": self.zoom, "pan_x": self.pan_x,
                     "pan_y": self.pan_y},
            "nodes": [n.to_dict() for n in self.nodes],
            "connections": [c.to_dict() for c in self.connections],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any], path: Path | None = None) -> "PipelineDoc":
        view = d.get("view") or {}
        doc = cls(
            id=str(d.get("id") or _new_id("p")),
            name=str(d.get("name") or "Untitled Pipeline"),
            nodes=[GraphNode.from_dict(n) for n in (d.get("nodes") or [])],
            connections=[Connection.from_dict(c)
                         for c in (d.get("connections") or [])],
            zoom=float(view.get("zoom", 1.0) or 1.0),
            pan_x=float(view.get("pan_x", 0.0) or 0.0),
            pan_y=float(view.get("pan_y", 0.0) or 0.0),
            source_key=d.get("source_key"),
            path=path,
        )
        # Drop edges whose endpoints vanished, so a hand-edited file cannot
        # produce connections that draw to nowhere.
        ids = {n.id for n in doc.nodes}
        doc.connections = [c for c in doc.connections
                           if c.src in ids and c.dst in ids]
        return doc

    def snapshot(self) -> dict[str, Any]:
        """State for the undo stack — view position deliberately excluded."""
        d = self.to_dict()
        d.pop("view", None)
        return d

    def restore(self, snap: dict[str, Any]) -> None:
        self.name = str(snap.get("name") or self.name)
        self.source_key = snap.get("source_key")
        self.nodes = [GraphNode.from_dict(n) for n in (snap.get("nodes") or [])]
        self.connections = [Connection.from_dict(c)
                            for c in (snap.get("connections") or [])]


# --- default layout ----------------------------------------------------------

def default_doc(name: str = "New Pipeline",
                source_key: str | None = None) -> PipelineDoc:
    """A blank pipeline seeded with the standard chain as ordinary nodes."""
    doc = PipelineDoc(id=_new_id("p"), name=name, source_key=source_key)
    x, y, step = 60.0, 120.0, 250.0
    prev: GraphNode | None = None
    for key in DEFAULT_CHAIN:
        n = doc.add_node(key, x, y)
        if prev:
            doc.connect(prev.id, n.id)
        prev = n
        x += step
    return doc


def blank_doc(name: str = "Untitled Pipeline") -> PipelineDoc:
    return PipelineDoc(id=_new_id("p"), name=name)


# --- storage -----------------------------------------------------------------

def pipelines_dir(root: Path | None = None) -> Path:
    """Where pipeline documents live.

    Prefers the analysis folder of the current library so pipelines travel with
    the data they describe; falls back to the application folder when no
    library root has been chosen yet.
    """
    if root:
        return Path(root) / ".analysis" / "pipelines"
    return _base_dir() / "pipelines"


def _safe_stem(name: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip() or "pipeline"
    return stem[:60]


def list_docs(root: Path | None = None) -> list[PipelineDoc]:
    """Every saved pipeline, newest first. Unreadable files are skipped."""
    d = pipelines_dir(root)
    if not d.is_dir():
        return []
    out: list[PipelineDoc] = []
    for p in sorted(d.glob("*.json"), key=lambda q: q.stat().st_mtime,
                    reverse=True):
        try:
            out.append(PipelineDoc.from_dict(
                json.loads(p.read_text(encoding="utf-8")), path=p))
        except Exception:
            continue
    return out


def save_doc(doc: PipelineDoc, root: Path | None = None) -> Path:
    d = pipelines_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    if doc.path is None:
        doc.path = d / f"{_safe_stem(doc.name)}_{doc.id}.json"
    tmp = doc.path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc.to_dict(), indent=2), encoding="utf-8")
    tmp.replace(doc.path)                    # atomic; never a half-written file
    return doc.path


def delete_doc(doc: PipelineDoc) -> None:
    if doc.path and doc.path.exists():
        doc.path.unlink()
    doc.path = None


def duplicate_doc(doc: PipelineDoc, new_name: str | None = None) -> PipelineDoc:
    """Copy with fresh ids throughout, so the original is untouched."""
    copy = PipelineDoc.from_dict(doc.to_dict())
    copy.id = _new_id("p")
    copy.name = new_name or f"{doc.name} copy"
    copy.path = None
    remap = {n.id: _new_id("n") for n in copy.nodes}
    for n in copy.nodes:
        n.id = remap[n.id]
    for c in copy.connections:
        c.id = _new_id("c")
        c.src = remap.get(c.src, c.src)
        c.dst = remap.get(c.dst, c.dst)
    return copy


def unique_name(existing: list[str], base: str = "New Pipeline") -> str:
    if base not in existing:
        return base
    i = 2
    while f"{base} {i}" in existing:
        i += 1
    return f"{base} {i}"
