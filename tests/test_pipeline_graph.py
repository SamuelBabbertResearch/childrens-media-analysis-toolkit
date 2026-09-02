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

def test_default_doc_branches_into_both_measurement_tracks(doc):
    """The default is a full study: machine and human tracks run in parallel.

    It is deliberately NOT a straight line — collapsing both tracks into one
    box is what made every other study design awkward to express.
    """
    types = [n.type for n in doc.nodes]
    assert "automated" in types
    assert "handcode_transitions" in types
    assert "validation" in types
    selection = next(n for n in doc.nodes if n.type == "selection")
    downstream = [c.dst for c in doc.connections if c.src == selection.id]
    assert len(downstream) == 2, "selection feeds both tracks"
    validation = next(n for n in doc.nodes if n.type == "validation")
    into_validation = [c.src for c in doc.connections if c.dst == validation.id]
    assert len(into_validation) == 2, "validation compares the two tracks"


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


# ---------------------------------------------------------------------------
# Workflow presets
# ---------------------------------------------------------------------------

def test_every_template_builds_a_valid_graph():
    for t in G.TEMPLATES:
        doc = t.build()
        ids = {n.id for n in doc.nodes}
        assert len(ids) == len(doc.nodes), "node ids are unique"
        for c in doc.connections:
            assert c.src in ids and c.dst in ids
        assert t.name and t.summary and t.detail


def test_full_study_validates_on_a_subset_not_the_whole_sample():
    """Hand coding in a full study estimates error; it does not measure the corpus.

    If every sampled episode were hand-coded, the automated pass would be
    redundant for those episodes — so the node carries a subset target.
    """
    doc = G.template("full").build()
    hand = next(n for n in doc.nodes if n.type == "handcode_transitions")
    assert hand.config.get("coding_target"), "subset target must be set"
    assert "subset" in hand.title.lower()


def test_full_study_reports_automated_numbers_directly():
    """Results come from the automated pass; validation attaches the error rate."""
    doc = G.template("full").build()
    auto = next(n for n in doc.nodes if n.type == "automated")
    res = next(n for n in doc.nodes if n.type == "results")
    val = next(n for n in doc.nodes if n.type == "validation")
    assert doc.has_connection(auto.id, res.id), "automated feeds results"
    assert doc.has_connection(val.id, res.id), "validation also feeds results"
    hand = next(n for n in doc.nodes if n.type == "handcode_transitions")
    assert not doc.has_connection(hand.id, res.id), \
        "hand coding reaches results through validation, not around it"


def test_validation_study_codes_everything():
    """Where the coded set IS the study, there is no subset target."""
    doc = G.template("validation").build()
    hand = next(n for n in doc.nodes if n.type == "handcode_transitions")
    assert not hand.config.get("coding_target")


def test_hand_coding_preset_has_no_validation():
    """Hand coding is a measurement, not a step towards validating the tool.

    A study that only codes by hand has nothing to validate against, so the
    preset must not imply otherwise.
    """
    doc = G.template("handcoding").build()
    types = [n.type for n in doc.nodes]
    assert "validation" not in types
    assert "automated" not in types
    assert "handcode_transitions" in types and "handcode_events" in types


def test_language_preset_skips_the_sensory_pass():
    doc = G.template("language").build()
    types = [n.type for n in doc.nodes]
    assert types.count("language") == 1
    assert "automated" not in types and "validation" not in types


def test_mixed_preset_combines_tracks():
    """The point of splitting the tracks: hand-code one thing, automate another."""
    doc = G.template("mixed").build()
    types = [n.type for n in doc.nodes]
    assert "handcode_transitions" in types
    assert "language" in types


def test_blank_preset_is_empty():
    doc = G.template("blank").build()
    assert doc.nodes == [] and doc.connections == []


def test_unknown_template_falls_back_to_blank():
    assert G.template("nope").key == "blank"


def test_templates_are_editable_after_creation():
    """Presets are starting points, not modes."""
    doc = G.template("automated").build()
    before = len(doc.nodes)
    added = doc.add_node("handcode_events", 500, 500)
    assert doc.connect(doc.nodes[1].id, added.id) is not None
    first = doc.nodes[0].id
    doc.remove_node(first)
    assert len(doc.nodes) == before          # one added, one removed
    assert all(n.id != first for n in doc.nodes)


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


def test_note_text_persists_in_config(tmp_path):
    doc = G.blank_doc("Notes")
    n = doc.add_node("note", 40, 40, title="Reminder")
    n.config["text"] = "Code only the first four episodes."
    path = G.save_doc(doc, tmp_path)
    back = G.list_docs(tmp_path)[0]
    note = next(x for x in back.nodes if x.type == "note")
    assert note.title == "Reminder"
    assert note.config["text"] == "Code only the first four episodes."


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
    before_types = [n.type for n in doc.nodes]
    before_edges = len(doc.connections)
    snap = doc.snapshot()
    doc.remove_node(doc.nodes[0].id)
    doc.add_node("note", 10, 10)
    doc.restore(snap)
    assert [n.type for n in doc.nodes] == before_types
    assert len(doc.connections) == before_edges


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


# ---------------------------------------------------------------------------
# Which sample feeds a node - the large slice of "wires carry the set"
# ---------------------------------------------------------------------------

def test_an_unlinked_document_resolves_to_no_sample(doc):
    automated = next(n for n in doc.nodes if n.type == "automated")
    assert doc.upstream_sample_keys(automated.id) == []


def test_the_document_default_reaches_every_downstream_node(doc):
    """A pipeline saved before per-node binding existed -- one Sampling node,
    never given its own key -- must keep resolving exactly as it always did."""
    doc.source_key = "sample:pilot"
    for n in doc.nodes:
        kind = G.node_type(n.type)
        if kind.inputs == 0 and n.type != "sampling":
            continue                       # a note: nothing upstream to reach
        assert doc.upstream_sample_keys(n.id) == ["sample:pilot"], n.type


def test_a_nodes_own_binding_overrides_the_document_default(doc):
    doc.source_key = "sample:pilot"
    sampling = next(n for n in doc.nodes if n.type == "sampling")
    sampling.config["sample_key"] = "sample:override"
    automated = next(n for n in doc.nodes if n.type == "automated")
    assert doc.upstream_sample_keys(automated.id) == ["sample:override"]


def test_converging_paths_to_one_sampling_node_do_not_duplicate_it(doc):
    """default_doc's Validation node has two upstream paths (automated,
    handcode_transitions) that both trace back to the SAME single Sampling
    node -- one sample feeding it, not two."""
    doc.source_key = "sample:pilot"
    validation = next(n for n in doc.nodes if n.type == "validation")
    assert doc.upstream_sample_keys(validation.id) == ["sample:pilot"]


def test_two_sampling_nodes_feeding_one_node_report_both():
    """The actual point: a node fed by two DIFFERENT Sampling nodes reports
    both keys, nearest first -- not one, collapsed."""
    doc = G.blank_doc("Branches")
    a = doc.add_node("sampling", 0, 0)
    a.config["sample_key"] = "sample:a"
    b = doc.add_node("sampling", 0, 200)
    b.config["sample_key"] = "sample:b"
    val = doc.add_node("validation", 300, 100)
    doc.connect(a.id, val.id)
    doc.connect(b.id, val.id)

    keys = doc.upstream_sample_keys(val.id)
    assert keys == ["sample:a", "sample:b"]


def test_a_node_with_no_path_to_any_sampling_node_resolves_to_nothing():
    doc = G.blank_doc("Orphan")
    note = doc.add_node("note", 0, 0)
    results = doc.add_node("results", 200, 0)
    doc.connect(note.id, results.id)
    assert doc.upstream_sample_keys(results.id) == []


# ---------------------------------------------------------------------------
# Where a document is saved
# ---------------------------------------------------------------------------

def test_a_doc_saved_before_a_root_is_known_rehomes_into_the_library(tmp_path):
    """The "I have to do the sampling again every time I open the pipeline"
    report.

    A document first saved with no library root lands in the application
    folder fallback. Saving it again WITH a root must move it into that
    library, because `list_docs(root)` only ever reads the library's own
    pipelines folder -- a doc pinned to the fallback saves fine, reloads as
    nothing, and looks like it never saved at all.
    """
    root = tmp_path / "Library"
    root.mkdir()

    doc = G.blank_doc("Made before a root was chosen")
    fallback = G.save_doc(doc, None)
    assert fallback.parent == G.pipelines_dir(None)

    node = doc.add_node("sampling", 0, 0)
    node.config["sample_key"] = "sample:drawn-later"
    saved = G.save_doc(doc, root)

    assert saved.parent == G.pipelines_dir(root)
    assert not fallback.exists(), "moved, not copied -- one doc id, one file"

    reloaded = [d for d in G.list_docs(root) if d.id == doc.id]
    assert len(reloaded) == 1, "reopening the library must find it"
    assert reloaded[0].nodes[0].config["sample_key"] == "sample:drawn-later"


def test_resaving_an_already_homed_doc_keeps_its_path(tmp_path):
    """Re-homing must not churn the filename on every ordinary save."""
    root = tmp_path / "Library"
    root.mkdir()
    doc = G.blank_doc("Normal")
    first = G.save_doc(doc, root)
    doc.add_node("sampling", 0, 0)
    second = G.save_doc(doc, root)
    assert first == second
    assert len(G.list_docs(root)) == 1
