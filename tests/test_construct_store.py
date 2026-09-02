"""
User-defined constructs: the library store, the content hash, and the
divergence a redefinition produces in the recipes that cite it.

`TODO.md` item G's four decisions, answered 2026-08-16 and recorded in
`DECISIONS.md` § *Authoring on the canvas: the four shaping decisions,
answered*. These tests hold the three that this module implements:

  1. user-defined constructs live WITH THE LIBRARY;
  2. a construct is content-hashed over its MEANING, a recipe records the hash
     it was authored against, and a redefinition is REPORTED as a divergence
     rather than folded into the recipe's own hash;
  4. a composite may not contain another composite — held here only as the
     absence of any nesting field.

Every test that claims something was stored **reads the written JSON**, per
`MEASUREMENT_MODEL.md` §4.2's own instruction and item G's ("verify by reading
the written recipe file, not by checking the canvas redrew").
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from analyzer import constructs as C
from analyzer import measurements as reg
from analyzer import recipes as R


@pytest.fixture
def library(tmp_path):
    """A library root with nothing in it, made the active one."""
    C.set_library(tmp_path)
    yield tmp_path
    C.set_library(None)


@pytest.fixture
def config():
    return reg.normalize_config({"cut_detection_threshold": 27.0,
                                 "sample_fps": 2.0})


def _saved(library: Path, name="Narrative complexity", **kw) -> C.Construct:
    construct = C.new_construct(
        name,
        definition=kw.pop("definition", "How much simultaneous story a viewer "
                                        "must hold in mind."),
        grounding=kw.pop("grounding", "My own construct. CMAT has validated "
                                      "nothing about it."),
        aspects=kw.pop("aspects", ()),
        root=library)
    C.save_construct(construct, library)
    return C.get_construct(construct.key)


# ---------------------------------------------------------------------------
# Decision 1 — constructs live with the library
# ---------------------------------------------------------------------------

def test_a_saved_construct_is_a_readable_file_under_the_library(library):
    construct = _saved(library)
    files = list((library / ".analysis" / "constructs").glob("*.json"))
    assert len(files) == 1

    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert data["key"] == construct.key
    assert data["name"] == "Narrative complexity"
    assert data["definition"].startswith("How much simultaneous story")
    assert data["content_hash"] == construct.content_hash()
    assert data["schema"] == C.CONSTRUCT_SCHEMA_VERSION


def test_a_library_construct_is_returned_by_the_ordinary_lookup(library):
    """The whole reason no call site needed editing."""
    construct = _saved(library)
    assert C.get_construct(construct.key) is not None
    assert construct.key in {c.key for c in C.all_constructs()}
    assert len(C.all_constructs()) == len(C.CONSTRUCTS) + 1


def test_saving_makes_a_construct_visible_without_a_manual_reload(library):
    """A screen that writes a construct and then cannot find it is a real gap."""
    before = len(C.all_constructs())
    _saved(library)
    assert len(C.all_constructs()) == before + 1


def test_opening_a_second_library_does_not_leak_the_first_ones_constructs(
        library, tmp_path_factory):
    _saved(library)
    assert len(C.library_constructs()) == 1

    other = tmp_path_factory.mktemp("other_library")
    C.set_library(other)
    assert C.library_constructs() == []
    assert len(C.all_constructs()) == len(C.CONSTRUCTS)


def test_a_construct_file_with_no_key_is_skipped_not_given_one(library):
    """An invented key would make it silently unreferenced by every recipe."""
    d = C.constructs_dir(library)
    d.mkdir(parents=True, exist_ok=True)
    (d / "broken.json").write_text(json.dumps({"name": "No key here"}),
                                   encoding="utf-8")
    C.set_library(library)
    assert C.library_constructs() == []


def test_renaming_re_homes_the_file_and_leaves_no_orphan(library):
    """Two files with one key would be two definitions of one construct."""
    construct = _saved(library)
    renamed = C.Construct(key=construct.key, name="Story complexity",
                          definition=construct.definition,
                          grounding=construct.grounding,
                          aspects=construct.aspects,
                          source=C.LIBRARY, path=construct.path)
    C.save_construct(renamed, library)

    files = list((library / ".analysis" / "constructs").glob("*.json"))
    assert len(files) == 1
    assert [(c.key, c.name) for c in C.library_constructs()] == [
        (construct.key, "Story complexity")]


# ---------------------------------------------------------------------------
# A library construct may not shadow a shipped one
# ---------------------------------------------------------------------------

def test_saving_a_shipped_construct_is_refused(library):
    with pytest.raises(PermissionError):
        C.save_construct(C.get_construct("pacing"), library)


def test_deleting_a_shipped_construct_is_refused(library):
    with pytest.raises(PermissionError):
        C.delete_construct(C.get_construct("pacing"), library)


def test_a_library_construct_may_not_take_a_shipped_key(library):
    with pytest.raises(PermissionError):
        C.save_construct(
            C.Construct(key="pacing", name="My pacing", definition="mine",
                        grounding="mine", source=C.LIBRARY), library)


def test_a_shadowing_file_that_arrives_by_other_routes_still_loses(library):
    """save_construct is not the only way a file reaches that folder.

    A copied library, a hand-edited folder, or an older CMAT with no such rule
    can all put one there. Shadowing `pacing` would silently move what the
    shipped composite claims to measure, so the lookup refuses it too.
    """
    d = C.constructs_dir(library)
    d.mkdir(parents=True, exist_ok=True)
    (d / "sneaky.json").write_text(json.dumps({
        "key": "pacing", "name": "Not the real pacing",
        "definition": "something else entirely", "grounding": ""}),
        encoding="utf-8")
    C.set_library(library)

    assert C.get_construct("pacing").name == "Pacing"
    assert C.get_construct("pacing").source == C.SHIPPED
    assert [c.key for c in C.all_constructs()].count("pacing") == 1


def test_a_generated_key_never_collides_with_a_shipped_one(library):
    assert C.construct_key_for("Pacing") != "pacing"


# ---------------------------------------------------------------------------
# Decision 2 — the hash covers meaning, not labels
# ---------------------------------------------------------------------------

def test_renaming_a_construct_does_not_change_its_hash(library):
    """The same rule `Recipe.canonical()` already applies to a recipe's name."""
    construct = _saved(library)
    renamed = C.Construct(key=construct.key, name="Something else entirely",
                          definition=construct.definition,
                          grounding=construct.grounding,
                          aspects=construct.aspects, source=C.LIBRARY)
    assert renamed.content_hash() == construct.content_hash()


def test_redefining_a_construct_changes_its_hash(library):
    construct = _saved(library)
    for changed in (
        C.Construct(key=construct.key, name=construct.name,
                    definition="A different definition.",
                    grounding=construct.grounding, source=C.LIBRARY),
        C.Construct(key=construct.key, name=construct.name,
                    definition=construct.definition,
                    grounding="A different grounding.", source=C.LIBRARY),
        C.Construct(key=construct.key, name=construct.name,
                    definition=construct.definition,
                    grounding=construct.grounding,
                    aspects=(C.Aspect("new", "New", "An added aspect."),),
                    source=C.LIBRARY),
    ):
        assert changed.content_hash() != construct.content_hash()


def test_reordering_aspects_is_not_a_redefinition(library):
    a = C.Aspect("one", "One", "First.")
    b = C.Aspect("two", "Two", "Second.")
    kw = dict(key="k", name="N", definition="d", grounding="g",
              source=C.LIBRARY)
    assert (C.Construct(aspects=(a, b), **kw).content_hash()
            == C.Construct(aspects=(b, a), **kw).content_hash())


def test_renaming_an_aspect_is_not_a_redefinition(library):
    kw = dict(key="k", name="N", definition="d", grounding="g",
              source=C.LIBRARY)
    assert (C.Construct(aspects=(C.Aspect("one", "One", "First."),), **kw)
            .content_hash()
            == C.Construct(aspects=(C.Aspect("one", "Renamed", "First."),), **kw)
            .content_hash())


# ---------------------------------------------------------------------------
# Decision 2 — a recipe records its baseline, and a redefinition is REPORTED
# ---------------------------------------------------------------------------

def test_a_new_recipe_records_the_constructs_hash_in_the_written_file(
        library, config):
    construct = _saved(library)
    recipe = R.new_recipe("Complexity", construct.key, config,
                          measures=[("hard_cuts_per_min", "auto:transitions:pyscenedetect_content")])
    path = R.save_recipe(recipe, library)

    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["construct_hash"] == construct.content_hash()
    assert R.construct_divergence(R.load_recipe(path)).status == R.CONSTRUCT_CURRENT


def test_redefining_a_construct_reports_a_divergence(library, config):
    construct = _saved(library)
    recipe = R.new_recipe("Complexity", construct.key, config,
                          measures=[("hard_cuts_per_min", "auto:transitions:pyscenedetect_content")])
    path = R.save_recipe(recipe, library)

    C.save_construct(C.Construct(
        key=construct.key, name=construct.name,
        definition="A different definition entirely.",
        grounding=construct.grounding, source=C.LIBRARY,
        path=construct.path), library)

    divergence = R.construct_divergence(R.load_recipe(path))
    assert divergence.status == R.CONSTRUCT_REDEFINED
    assert divergence.is_divergent
    assert divergence.recorded_hash == construct.content_hash()
    assert divergence.current_hash != construct.content_hash()
    assert "REDEFINED" in divergence.describe()


def test_a_redefinition_does_not_bump_the_recipes_version(library, config):
    """The decisive property. If the construct hash were inside canonical(),
    editing a construct would version every citing recipe WITHOUT the reason
    bump_version requires — the one field that cannot be reconstructed later.
    """
    construct = _saved(library)
    recipe = R.new_recipe("Complexity", construct.key, config,
                          measures=[("hard_cuts_per_min", "auto:transitions:pyscenedetect_content")])
    path = R.save_recipe(recipe, library)
    before = json.loads(path.read_text(encoding="utf-8"))["content_hash"]

    C.save_construct(C.Construct(
        key=construct.key, name=construct.name, definition="Different.",
        grounding=construct.grounding, source=C.LIBRARY,
        path=construct.path), library)

    reloaded = R.load_recipe(path)
    assert reloaded.content_hash() == before
    assert R.bump_version(reloaded, "a reason") is None


def test_the_construct_hash_is_not_part_of_the_recipes_canonical_form(
        library, config):
    construct = _saved(library)
    recipe = R.new_recipe("Complexity", construct.key, config,
                          measures=[("hard_cuts_per_min", "auto:transitions:pyscenedetect_content")])
    canonical = recipe.canonical()
    assert "construct_hash" not in canonical

    before = recipe.content_hash()
    recipe.construct_hash = "0000deadbeef"
    assert recipe.content_hash() == before


def test_a_recipe_with_no_recorded_hash_reports_unknown_not_current(
        library, config):
    """Grandfathering, carried over from `cache.is_stale`.

    A recipe written before this mechanism has no baseline. Reporting it as
    current would be a guess presented as a fact — which is exactly what the
    Measurement settings dialog's "3 predate fingerprinting" count exists to
    avoid.
    """
    construct = _saved(library)
    recipe = R.new_recipe("Complexity", construct.key, config,
                          measures=[("hard_cuts_per_min", "auto:transitions:pyscenedetect_content")])
    recipe.construct_hash = ""
    path = R.save_recipe(recipe, library)

    divergence = R.construct_divergence(R.load_recipe(path))
    assert divergence.status == R.CONSTRUCT_UNKNOWN
    assert not divergence.is_divergent
    assert "predates" in divergence.describe()


def test_deleting_a_cited_construct_reports_missing_and_keeps_the_bindings(
        library, config):
    """Nothing is silently repaired — the same choice `import_recipe` makes."""
    construct = _saved(library)
    recipe = R.new_recipe("Complexity", construct.key, config,
                          measures=[("hard_cuts_per_min", "auto:transitions:pyscenedetect_content")])
    path = R.save_recipe(recipe, library)

    C.delete_construct(C.get_construct(construct.key), library)

    reloaded = R.load_recipe(path)
    divergence = R.construct_divergence(reloaded)
    assert divergence.status == R.CONSTRUCT_MISSING
    assert divergence.is_divergent
    assert reloaded.construct_key == construct.key
    assert [b.measure_key for b in reloaded.bindings] == ["hard_cuts_per_min"]


def test_reaffirming_updates_the_baseline_without_versioning(library, config):
    construct = _saved(library)
    recipe = R.new_recipe("Complexity", construct.key, config,
                          measures=[("hard_cuts_per_min", "auto:transitions:pyscenedetect_content")])
    path = R.save_recipe(recipe, library)

    C.save_construct(C.Construct(
        key=construct.key, name=construct.name, definition="Different.",
        grounding=construct.grounding, source=C.LIBRARY,
        path=construct.path), library)

    reloaded = R.load_recipe(path)
    R.reaffirm_construct(reloaded)
    R.save_recipe(reloaded, library)

    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["construct_hash"] == C.get_construct(
        construct.key).content_hash()
    assert written["version"] == 1
    assert R.construct_divergence(R.load_recipe(path)).status == \
        R.CONSTRUCT_CURRENT


def test_reaffirming_a_missing_construct_refuses(library, config):
    construct = _saved(library)
    recipe = R.new_recipe("Complexity", construct.key, config,
                          measures=[("hard_cuts_per_min", "auto:transitions:pyscenedetect_content")])
    C.delete_construct(C.get_construct(construct.key), library)
    with pytest.raises(KeyError):
        R.reaffirm_construct(recipe)


def test_a_shipped_recipe_records_a_shipped_constructs_hash(library, config):
    """The mechanism is not only for user constructs: if a shipped definition
    is ever edited, citing recipes say so too."""
    recipe = R.shipped_composite(config)
    assert recipe.construct_hash == C.get_construct("sensory_load").content_hash()
    assert R.construct_divergence(recipe).status == R.CONSTRUCT_CURRENT


# ---------------------------------------------------------------------------
# Export / import across installs
# ---------------------------------------------------------------------------

def test_an_export_carries_the_constructs_definition_aspects_and_hash(
        library, config):
    """A library construct does NOT follow its recipe to another install, so
    the exported description is the only account that machine ever gets."""
    construct = _saved(library, aspects=(
        C.Aspect("threads", "Concurrent threads", "How many plots run."),))
    recipe = R.new_recipe("Complexity", construct.key, config,
                          measures=[("hard_cuts_per_min", "auto:transitions:pyscenedetect_content")])

    described = R.export_recipe(recipe)["describes"]["construct"]
    assert described["key"] == construct.key
    assert described["definition"] == construct.definition
    assert described["grounding"] == construct.grounding
    assert described["content_hash"] == construct.content_hash()
    assert [a["key"] for a in described["aspects"]] == ["threads"]


def test_importing_where_the_same_key_means_something_else_is_a_named_gap(
        library, config):
    """Worse than a missing construct, because it resolves silently."""
    construct = _saved(library)
    recipe = R.new_recipe("Complexity", construct.key, config,
                          measures=[("hard_cuts_per_min", "auto:transitions:pyscenedetect_content")])
    payload = R.export_recipe(recipe)

    C.save_construct(C.Construct(
        key=construct.key, name=construct.name,
        definition="This library means something quite different by it.",
        grounding=construct.grounding, source=C.LIBRARY,
        path=construct.path), library)

    imported, gaps = R.import_recipe(payload)
    kinds = {g.kind for g in gaps}
    assert "construct_definition" in kinds
    assert imported.construct_key == construct.key
    assert [b.measure_key for b in imported.bindings] == ["hard_cuts_per_min"]


def test_importing_where_the_construct_is_absent_is_still_a_gap(
        library, config):
    construct = _saved(library)
    recipe = R.new_recipe("Complexity", construct.key, config,
                          measures=[("hard_cuts_per_min", "auto:transitions:pyscenedetect_content")])
    payload = R.export_recipe(recipe)
    C.delete_construct(C.get_construct(construct.key), library)

    _imported, gaps = R.import_recipe(payload)
    assert {g.kind for g in gaps} == {"construct"}


def test_an_unchanged_definition_imports_with_no_construct_gap(
        library, config):
    construct = _saved(library)
    recipe = R.new_recipe("Complexity", construct.key, config,
                          measures=[("hard_cuts_per_min", "auto:transitions:pyscenedetect_content")])
    _imported, gaps = R.import_recipe(R.export_recipe(recipe))
    assert not [g for g in gaps if g.kind.startswith("construct")]


# ---------------------------------------------------------------------------
# Rule 2 — constructs may be free-form; MEASURES MAY NOT
# ---------------------------------------------------------------------------

def test_authoring_a_binding_to_an_unknown_measure_is_refused(library, config):
    """The rule that keeps `LEARNINGS.md` shape 2 out through a nicer door.

    Found by driving import against a recipe built here: `new_recipe` used to
    accept any string as a method key, so a typo produced a recipe whose
    binding could never resolve — and nothing said so until an export was
    imported somewhere else.
    """
    construct = _saved(library)
    with pytest.raises(KeyError):
        R.new_recipe("Complexity", construct.key, config,
                     measures=[("a_measure_i_invented", "auto:whatever")])


def test_authoring_a_binding_to_an_unknown_method_is_refused(library, config):
    construct = _saved(library)
    with pytest.raises(KeyError):
        R.new_recipe("Complexity", construct.key, config,
                     measures=[("hard_cuts_per_min", "content")])


def test_a_prebuilt_binding_is_checked_too(library, config):
    construct = _saved(library)
    with pytest.raises(KeyError):
        R.new_recipe("Complexity", construct.key, config,
                     measures=[R.MeasureBinding(
                         measure_key="hard_cuts_per_min",
                         method_key="not_a_real_method", weight=1.0)])


def test_reading_an_unresolvable_recipe_is_still_allowed(library, config):
    """Refusing to AUTHOR one is a different question from refusing to READ
    one — `import_recipe` must keep a foreign detector's binding intact."""
    recipe = R.Recipe.from_dict({
        "id": "r_x", "name": "From elsewhere", "construct": "pacing",
        "bindings": [{"measure": "hard_cuts_per_min",
                      "method": "auto:transitions:something_exotic"}]})
    assert [b.method_key for b in recipe.bindings] == [
        "auto:transitions:something_exotic"]
    _imported, gaps = R.import_recipe(recipe.to_dict())
    assert [g.kind for g in gaps] == ["method"]


# ---------------------------------------------------------------------------
# Decision 4 — no nesting
# ---------------------------------------------------------------------------

def test_a_binding_names_a_measure_and_offers_no_way_to_name_a_recipe(
        library, config):
    """Held as the absence of the field. If a composite ever gains a
    recipe-valued input, contribution share becomes recursive and staleness a
    graph problem — decided against, and reversible only while no saved recipe
    uses it.
    """
    construct = _saved(library)
    recipe = R.new_recipe("Complexity", construct.key, config,
                          measures=[("hard_cuts_per_min", "auto:transitions:pyscenedetect_content")])
    written = json.loads(
        R.save_recipe(recipe, library).read_text(encoding="utf-8"))
    for binding in written["bindings"]:
        assert "recipe" not in binding
        assert C.get_measure(binding["measure"]) is not None
