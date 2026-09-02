"""
The construct editor, and the route it unblocks.

`TODO.md` item G2's first half: until this screen existed, a researcher could
not create or edit a construct from anywhere in the application, so
`MEASUREMENT_MODEL.md` §4.1's "researchers add their own" was a data model with
no door.

Asserted against WRITTEN FILES wherever a file is what the feature produces —
the construct JSON, the recipe JSON, the divergence a redefinition causes —
because the dialog reporting success is compatible with all of them being
wrong, and on this project it has been.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from analyzer import constructs as C
from analyzer import measurements as reg
from analyzer import recipes as R

pytest.importorskip("PySide6")


@pytest.fixture
def config():
    root = Path(__file__).resolve().parent.parent
    return reg.normalize_config(
        json.loads((root / "config.json").read_text(encoding="utf-8")))


@pytest.fixture
def library(tmp_path):
    root = tmp_path / "lib"
    (root / "Test Show").mkdir(parents=True)
    C.set_library(root)
    yield root
    C.set_library(None)


def _fill(editor, name, definition="A definition.", grounding="Ungrounded."):
    editor._name.setText(name)
    editor._definition.setPlainText(definition)
    editor._grounding.setPlainText(grounding)
    editor._sync()
    return editor


# ---------------------------------------------------------------------------
# Creating one
# ---------------------------------------------------------------------------

def test_a_created_construct_is_written_and_comes_back_from_get_construct(
        qapp, library):
    """The merge lives inside `get_construct`, so a construct saved here is
    visible to every call site with none of them edited."""
    from ui.construct_editor import ConstructEditor

    editor = ConstructEditor(library, None)
    _fill(editor, "Narrative complexity",
          "How much simultaneous story information a viewer must hold.",
          "No validated mapping; this study's own construct.")
    editor._save()

    files = list((library / ".analysis" / "constructs").glob("*.json"))
    assert len(files) == 1
    written = json.loads(files[0].read_text(encoding="utf-8"))
    assert written["name"] == "Narrative complexity"
    assert written["definition"].startswith("How much simultaneous")

    back = C.get_construct(editor.saved_key)
    assert back is not None
    assert back.source == C.LIBRARY and back.is_editable
    assert written["content_hash"] == back.content_hash()
    editor.deleteLater()


def test_a_construct_needs_a_name_but_not_a_definition(qapp, library):
    """Refusing a nameless construct is the only hard stop. A missing
    definition is stated as a consequence — the hash is taken over the
    definition, so an empty one is what recipes cite as the meaning."""
    from ui.construct_editor import ConstructEditor

    editor = ConstructEditor(library, None)
    editor._sync()
    assert not editor._btn_save.isEnabled()
    editor._name.setText("Something")
    editor._sync()
    assert editor._btn_save.isEnabled()
    assert "definition is a label" in editor._status.text()
    editor.deleteLater()


def test_aspects_are_written_and_given_distinct_keys(qapp, library):
    """The hash sorts aspects BY KEY, so two sharing one would make the
    definition depend on which sorted first."""
    from ui.construct_editor import ConstructEditor

    editor = ConstructEditor(library, None)
    _fill(editor, "Layered")
    for _ in range(2):
        editor._add_aspect(None)
    editor._aspects[0].name.setText("Threads")
    editor._aspects[1].name.setText("Threads")
    editor._save()

    construct = C.get_construct(editor.saved_key)
    keys = [a.key for a in construct.aspects]
    assert len(keys) == 2 and len(set(keys)) == 2
    editor.deleteLater()


# ---------------------------------------------------------------------------
# The shipped set is shown, not edited
# ---------------------------------------------------------------------------

def test_a_shipped_construct_opens_read_only_and_offers_the_route(qapp,
                                                                  library):
    """An unavailable control must not look like a broken one (`CLAUDE.md`
    §4): the reason is on screen and Duplicate is offered."""
    from ui.construct_editor import ConstructEditor

    editor = ConstructEditor(library, C.get_construct("pacing"))
    assert not editor._name.isEnabled()
    assert not editor._definition.isEnabled()
    assert editor._btn_save.isHidden()
    assert not editor._btn_duplicate.isHidden()
    assert editor._btn_delete.isHidden()
    assert "cannot be edited" in editor._banner.text()
    assert "Duplicat" in editor._banner.text()
    editor.deleteLater()


def test_duplicating_a_shipped_construct_gives_it_its_own_key(qapp, library):
    """`save_construct` refuses a library construct shadowing a shipped key —
    recipes citing `pacing` would otherwise change meaning depending on which
    library was open."""
    from ui.construct_editor import ConstructEditor

    editor = ConstructEditor(library, C.get_construct("pacing"))
    editor._duplicate()
    assert editor.saved_key and editor.saved_key != "pacing"
    copy = C.get_construct(editor.saved_key)
    assert copy.source == C.LIBRARY
    assert C.get_construct("pacing").source == C.SHIPPED
    assert "CMAT has validated it no further" in copy.grounding
    editor.deleteLater()


def test_the_picker_counts_the_catalogue_and_the_canvas_counts_the_bindings(
        qapp, library, config):
    """Two different quantities that were both called "measures".

    Reported from the real application: the Constructs picker said Pacing had
    "8 measures of its own" while the canvas next to it showed one. Both
    numbers were right — the picker lists every measure the model DEFINES for a
    construct, the canvas how many this RECIPE binds — and Pacing does define
    eight while the composite binds one. Saying which is what makes them stop
    looking like a contradiction.
    """
    from analyzer import scope as S
    from ui.construct_editor import ConstructPicker
    from ui.constructs_tab import ConstructItem, ConstructsTab

    assert len(C.measures_for("pacing")) == 8

    picker = ConstructPicker(library)
    row = next(i for i in range(picker._list.count())
               if picker._list.item(i).text().startswith("Pacing"))
    text = picker._list.item(row).text()
    assert "8 measures available to bind" in text
    assert "of its own" not in text
    picker.deleteLater()

    class _Window:
        _root = library
        _cfg = config

        def statusBar(self):
            class _Bar:
                def showMessage(self, *a, **k):
                    pass
            return _Bar()

    tab = ConstructsTab(_Window())
    tab.set_scope(S.library_scope())
    tab.refresh()
    block = next(i for i in tab._view._scene.items()
                 if isinstance(i, ConstructItem) and i.key == "pacing")
    assert block._n == 1, "the composite binds one of pacing's eight"
    assert block.caption() == "construct · 1 measure in this recipe"
    tab.deleteLater()


def test_there_is_no_control_anywhere_for_defining_a_measure():
    """Rule 2, checked at the level a control can be added by accident.

    A user-defined measure with no data path is `LEARNINGS.md` shape 2 — the
    defect this whole phase exists to remove — and offering one here would
    reintroduce it through a nicer interface.
    """
    import inspect

    from ui import construct_editor

    src = inspect.getsource(construct_editor)
    assert "new_measure" not in src
    assert "C.Measure(" not in src
    assert "save_measure" not in src
    # And it says so, rather than leaving the absence to read as unfinished.
    assert "not user-definable" in src


# ---------------------------------------------------------------------------
# Redefining: reported, never folded into a recipe's version
# ---------------------------------------------------------------------------

def test_redefining_moves_the_divergence_and_not_the_recipes_version(
        qapp, library, config):
    """The decision this phase turns on, driven through the screen and read
    back off both files."""
    from ui.construct_editor import ConstructEditor

    editor = ConstructEditor(library, None)
    _fill(editor, "Complexity", "First definition.")
    editor._save()
    key = editor.saved_key
    editor.deleteLater()

    recipe = R.new_recipe(
        "Complexity v1", key, config,
        measures=[("hard_cuts_per_min",
                   "auto:transitions:pyscenedetect_content")],
        reason="fixture")
    R.save_recipe(recipe, library)
    before = R.load_recipe(recipe.path)
    assert R.construct_divergence(before).status == R.CONSTRUCT_CURRENT

    editor = ConstructEditor(library, C.get_construct(key))
    editor._definition.setPlainText("Second definition, meaning something "
                                    "else.")
    editor._sync()
    # It says what will happen, naming the recipes, BEFORE it happens.
    assert "1 recipe" in editor._effect.text()
    assert "Complexity v1" in editor._effect.text()
    assert "not an error" in editor._effect.text()
    editor._save()
    editor.deleteLater()

    after = R.load_recipe(recipe.path)
    assert R.construct_divergence(after).status == R.CONSTRUCT_REDEFINED
    assert after.content_hash() == before.content_hash()
    assert after.version == before.version


def test_renaming_a_construct_changes_nothing_a_recipe_cites(qapp, library,
                                                             config):
    """The hash covers meaning, not the label — the same rule recipes follow."""
    from ui.construct_editor import ConstructEditor

    editor = ConstructEditor(library, None)
    _fill(editor, "Old name", "Unchanged meaning.")
    editor._save()
    key = editor.saved_key
    editor.deleteLater()

    recipe = R.new_recipe("Over it", key, config, measures=[],
                          reason="fixture")
    R.save_recipe(recipe, library)

    editor = ConstructEditor(library, C.get_construct(key))
    editor._name.setText("New name")
    editor._sync()
    assert "Renaming only" in editor._effect.text()
    editor._save()
    editor.deleteLater()

    assert C.get_construct(key).name == "New name"
    assert R.construct_divergence(
        R.load_recipe(recipe.path)).status == R.CONSTRUCT_CURRENT


def test_deleting_a_cited_construct_leaves_the_recipe_reporting_missing(
        qapp, library, config, monkeypatch):
    """Not silently repaired: the key is kept and the gap is named, which is
    the choice `import_recipe` already makes for an unresolvable reference."""
    from PySide6.QtWidgets import QDialog

    from ui import construct_editor as CE

    editor = CE.ConstructEditor(library, None)
    _fill(editor, "Doomed")
    editor._save()
    key = editor.saved_key
    editor.deleteLater()

    recipe = R.new_recipe("Cites it", key, config, measures=[],
                          reason="fixture")
    R.save_recipe(recipe, library)

    editor = CE.ConstructEditor(library, C.get_construct(key))
    monkeypatch.setattr(CE.ConfirmDialog, "exec",
                        lambda self: QDialog.Accepted)
    editor._delete()
    editor.deleteLater()

    assert C.get_construct(key) is None
    reloaded = R.load_recipe(recipe.path)
    assert reloaded.construct_key == key
    assert R.construct_divergence(reloaded).status == R.CONSTRUCT_MISSING


# ---------------------------------------------------------------------------
# The Recipes New menu — the block G2 had to remove
# ---------------------------------------------------------------------------

def test_the_new_menu_offers_every_construct_including_measureless_ones(
        qapp, library, config):
    """This used to DISABLE any construct with no measures of its own, which by
    rule is every construct a researcher defines — so a construct of your own
    could be written and never operationalized."""
    from ui.construct_editor import ConstructEditor
    from ui.recipes import RecipesDialog

    editor = ConstructEditor(library, None)
    _fill(editor, "Mine")
    editor._save()
    editor.deleteLater()

    dialog = RecipesDialog(config, library)
    entries = [(a.text(), a.isEnabled())
               for a in dialog._build_new_menu().actions() if a.text()]
    assert entries, "the menu offers nothing"
    assert all(enabled for _t, enabled in entries), \
        [t for t, e in entries if not e]
    assert any(t.startswith("Mine") for t, _e in entries)
    assert any("Sensory load" in t for t, _e in entries)
    assert any("New construct" in t for t, _e in entries)
    dialog.deleteLater()


def test_a_recipe_over_a_measureless_construct_is_created_empty_and_says_so(
        qapp, library, config):
    """An empty recipe is a step, not a broken state — but it must refuse to
    score rather than report a number for an operationalization with nothing
    in it."""
    from analyzer.constructs import EpisodeRef
    from ui.construct_editor import ConstructEditor
    from ui.recipes import RecipesDialog

    editor = ConstructEditor(library, None)
    _fill(editor, "Mine")
    editor._save()
    key = editor.saved_key
    editor.deleteLater()

    dialog = RecipesDialog(config, library)
    dialog._new_recipe(key)
    assert "no bindings" in dialog._status.text()
    assert "Constructs tab" in dialog._status.text()

    written = next(p for p in (library / ".analysis" / "recipes").glob("*.json")
                   if not p.name.endswith(R.VIEW_SUFFIX))
    recipe = R.load_recipe(written)
    assert recipe.bindings == []
    assert recipe.construct_key == key

    evaluation = R.evaluate(
        recipe, EpisodeRef(root=library, show_name="Test Show",
                           stem="nothing", video=library / "x.mp4"), config)
    assert evaluation.score is None
    assert evaluation.detail
    dialog.deleteLater()


def test_a_recipe_cannot_be_authored_over_a_construct_that_does_not_exist(
        library, config):
    """Found by a test of mine that passed the wrong key: `new_recipe` built a
    recipe over the construct `'None'` and `save_recipe` wrote it, producing a
    file with an ordinary name, version, hash and citation and no definition
    anywhere behind it. The same shape as `LEARNINGS.md` § *`new_recipe`
    accepted a method key that does not exist*, one field over."""
    with pytest.raises(KeyError):
        R.new_recipe("Over nothing", "no_such_construct", config, measures=[])

    # Reading one is still allowed — that is `import_recipe`'s contract.
    orphan = R.Recipe.from_dict({"name": "From elsewhere",
                                 "construct": "their_construct"})
    assert orphan.construct_key == "their_construct"
    assert R.construct_divergence(orphan).status == R.CONSTRUCT_MISSING
