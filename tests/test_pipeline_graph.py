"""
Pipeline documents — graph editing, persistence, and undo.

These guard the editor's data contract: a saved pipeline must come back
identical, an edit must be undoable, and the graph must refuse structures the
renderer cannot draw (self-links, duplicates, cycles) rather than producing a
file that crashes or loops on load.
"""

from __future__ import annotations
import json

import pytest

from analyzer import pipeline_graph as G


@pytest.fixture
def doc():
    return G.default_doc("Fixture")


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

def test_default_doc_is_a_connected_chain(doc):
    assert [n.type for n in doc.nodes] == G.DEFAULT_CHAIN
    assert len(doc.connections) == len(G.DEFAULT_CHAIN) - 1
    for a, b in zip(doc.nodes, doc.nodes[1:]):
        assert doc.has_connection(a.id, b.id)


def test_blank_doc_is_empty_but_valid():
    d = G.blank_doc("Empty")
    assert d.nodes == [] and d.connections == []
    assert d.bounds() == (0.0, 0.0, 1.0, 1.0), "fit-to-view needs a safe box"


def test_stages_are_ordinary_nodes_not_special_cases(doc):
    """Any stage must be deletable like any other node."""
    first = doc.nodes[0]
    doc.remove_node(first.id)
    assert all(n.id != first.id for n in doc.nodes)
    assert all(first.id not in (c.src, c.dst) for c in doc.connections)


def test_new_node_types_need_no_ui_change():
    """The registry is the extension point — a type is a dict entry."""
    for key, t in G.NODE_TYPES.items():
        assert t.key == key
        assert t.name and t.description and t.icon
    assert G.node_type("does_not_exist").key == "note", "unknown types degrade"


# ---------------------------------------------------------------------------
# Connection rules
# ---------------------------------------------------------------------------

def test_self_connection_refused(doc):
    n = doc.nodes[0]
    assert doc.connect(n.id, n.id) is None


def test_duplicate_connection_refused(doc):
    a, b = doc.nodes[0], doc.nodes[1]
    before = len(doc.connections)
    assert doc.connect(a.id, b.id) is None
    assert len(doc.connections) == before


def test_cycle_refused(doc):
    """A loop would make the renderer and any traversal run forever."""
    assert doc.connect(doc.nodes[-1].id, doc.nodes[0].id) is None


def test_branching_is_allowed(doc):
    """Not every pipeline is linear — one stage may feed several."""
    extra = doc.add_node("export", 900, 400)
    assert doc.connect(doc.nodes[0].id, extra.id) is not None
    outs = [c for c in doc.connections if c.src == doc.nodes[0].id]
    assert len(outs) == 2


def test_connection_to_missing_node_refused(doc):
    assert doc.connect(doc.nodes[0].id, "nope") is None


def test_removing_a_node_removes_its_edges(doc):
    mid = doc.nodes[2]
    doc.remove_node(mid.id)
    assert all(mid.id not in (c.src, c.dst) for c in doc.connections)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_round_trip_preserves_everything(doc, tmp_path):
    doc.zoom, doc.pan_x, doc.pan_y = 1.75, -40.0, 12.5
    path = G.save_doc(doc, tmp_path)
    back = G.PipelineDoc.from_dict(json.loads(path.read_text(encoding="utf-8")))
    assert back.name == doc.name
    assert [n.id for n in back.nodes] == [n.id for n in doc.nodes]
    assert [(n.x, n.y) for n in back.nodes] == [(n.x, n.y) for n in doc.nodes]
    assert [(c.src, c.dst) for c in back.connections] == \
           [(c.src, c.dst) for c in doc.connections]
    assert back.zoom == pytest.approx(1.75)


def test_node_positions_live_in_the_document(doc, tmp_path):
    """Positions must persist — the window is a viewport, not the layout."""
    doc.nodes[0].x, doc.nodes[0].y = 1234.0, -567.0
    G.save_doc(doc, tmp_path)
    back = G.list_docs(tmp_path)[0]
    assert (back.nodes[0].x, back.nodes[0].y) == (1234.0, -567.0)


def test_list_docs_skips_unreadable_files(tmp_path):
    G.save_doc(G.default_doc("Good"), tmp_path)
    (G.pipelines_dir(tmp_path) / "broken.json").write_text("{not json",
                                                           encoding="utf-8")
    names = [d.name for d in G.list_docs(tmp_path)]
    assert names == ["Good"]


def test_dangling_connections_are_dropped_on_load():
    d = G.PipelineDoc.from_dict({
        "name": "X",
        "nodes": [{"id": "n1", "type": "sampling", "x": 0, "y": 0}],
        "connections": [{"id": "c1", "src": "n1", "dst": "ghost"}],
    })
    assert d.connections == [], "an edge to nowhere would draw off into space"


def test_save_is_atomic(doc, tmp_path):
    """A crash mid-write must not leave a half-written pipeline."""
    path = G.save_doc(doc, tmp_path)
    assert path.exists()
    assert not list(G.pipelines_dir(tmp_path).glob("*.tmp"))


def test_delete_removes_the_file(doc, tmp_path):
    path = G.save_doc(doc, tmp_path)
    G.delete_doc(doc)
    assert not path.exists() and doc.path is None


# ---------------------------------------------------------------------------
# Naming and duplication
# ---------------------------------------------------------------------------

def test_duplicate_is_fully_independent(doc):
    copy = G.duplicate_doc(doc, "Copy")
    assert copy.id != doc.id
    ids = {n.id for n in doc.nodes}
    assert not ids & {n.id for n in copy.nodes}, "fresh node ids"
    copy.nodes[0].x = 9999
    assert doc.nodes[0].x != 9999, "editing the copy must not touch the original"
    # ...and the copy's edges must point at the copy's nodes.
    copy_ids = {n.id for n in copy.nodes}
    assert all(c.src in copy_ids and c.dst in copy_ids for c in copy.connections)


def test_unique_name_avoids_collisions():
    assert G.unique_name([], "New Pipeline") == "New Pipeline"
    assert G.unique_name(["New Pipeline"], "New Pipeline") == "New Pipeline 2"
    assert G.unique_name(["New Pipeline", "New Pipeline 2"],
                         "New Pipeline") == "New Pipeline 3"


def test_names_with_path_characters_do_not_escape_the_folder(tmp_path):
    doc = G.default_doc(r"../../evil name: with*chars")
    path = G.save_doc(doc, tmp_path)
    assert path.parent == G.pipelines_dir(tmp_path)


# ---------------------------------------------------------------------------
# Undo
# ---------------------------------------------------------------------------

def test_snapshot_restores_nodes_and_edges(doc):
    snap = doc.snapshot()
    doc.remove_node(doc.nodes[0].id)
    doc.add_node("note", 10, 10)
    doc.restore(snap)
    assert [n.type for n in doc.nodes] == G.DEFAULT_CHAIN
    assert len(doc.connections) == len(G.DEFAULT_CHAIN) - 1


def test_snapshot_ignores_view_state(doc):
    """Panning is not an undoable edit."""
    before = doc.snapshot()
    doc.zoom, doc.pan_x = 2.5, 400.0
    assert doc.snapshot() == before


def test_source_link_persists(doc, tmp_path):
    """Which sample a pipeline reports on is part of the document.

    Without a stored link the view fell back to whichever discovered project
    came first, so a pipeline could display an unrelated study's numbers.
    """
    doc.source_key = "sample:/some/where/draw1"
    G.save_doc(doc, tmp_path)
    assert G.list_docs(tmp_path)[0].source_key == "sample:/some/where/draw1"


def test_unlinked_document_has_no_source(doc):
    assert G.default_doc("X").source_key is None
    assert G.blank_doc("Y").source_key is None


def test_relinking_is_undoable(doc):
    """Linking is an edit — the snapshot must carry it."""
    snap = doc.snapshot()
    doc.source_key = "sample:changed"
    doc.restore(snap)
    assert doc.source_key is None


def test_bounds_covers_all_nodes(doc):
    doc.nodes[0].x, doc.nodes[0].y = -500.0, -300.0
    x0, y0, x1, y1 = doc.bounds()
    assert x0 == -500.0 and y0 == -300.0
    assert x1 >= max(n.x + n.w for n in doc.nodes)
