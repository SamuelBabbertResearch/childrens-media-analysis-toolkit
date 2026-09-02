"""
The Recipes dialog — the measurement model's first appearance in the interface.

Asserted on what the screen PRODUCES, not on which widgets exist. That is the
distinction `LEARNINGS.md` opens with: nineteen defects survived an audit that
compared controls, because a control that is present and a control whose data
path works are different claims. So these read the generated HTML, the
enabled/disabled state, and the text of the status line.

Two defects found by driving this dialog headlessly are pinned here, because
neither was visible from the interface:

  * the dirty check ran one edit behind, so Save became available with no
    reason given — bypassing the version rule the screen exists to enforce;
  * a recipe with every weight still at zero scored 0.0, which reads as a
    measured composite rather than an unset one.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from analyzer import constructs as C
from analyzer import measurements as reg
from analyzer import recipes as R
from analyzer import scope as S
from analyzer.schema import EpisodeResult

pytest.importorskip("PySide6")

SHOW, STEM = "Test Show", "S01E01 Something"


@pytest.fixture
def config():
    root = Path(__file__).resolve().parent.parent
    return reg.normalize_config(
        json.loads((root / "config.json").read_text(encoding="utf-8")))


@pytest.fixture
def library(tmp_path, config):
    """A small library with one analysed episode and one that is not."""
    root = tmp_path / "lib"
    show = root / SHOW
    show.mkdir(parents=True)
    (show / f"{STEM}.mp4").touch()
    (show / "S01E02 Unanalysed.mp4").touch()

    result = EpisodeResult(file=f"{STEM}.mp4", duration_sec=600.0,
                           config=json.loads(json.dumps(config)))
    m = result.metrics
    m.scene_pacing.cuts_per_min = 12.0
    m.color_saturation.mean = 0.4
    m.color_saturation.contrast_mean = 0.2
    m.motion.mean = 0.1
    m.flashing.luminance_delta_events_per_min = 5.0
    m.audio.available = True
    m.audio.rms_mean = 0.15
    cache = root / ".analysis" / SHOW / f"{STEM}.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(result.to_dict()), encoding="utf-8")
    return root


@pytest.fixture
def dialog(qapp, library, config):
    from ui.recipes import RecipesDialog
    d = RecipesDialog(config, library, S.library_scope())
    yield d
    d.deleteLater()


def _text(html: str) -> str:
    import re
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


# ---------------------------------------------------------------------------
# Inspectable by construction
# ---------------------------------------------------------------------------

def test_the_shipped_composite_is_offered_without_being_saved_first(dialog):
    """It is generated from the config, so it is present in a library that has
    never had a recipe written to it."""
    assert dialog._list.count() >= 1
    assert dialog._current.name == R.SHIPPED_COMPOSITE_NAME
    assert dialog._current.locked


def test_every_pinned_parameter_is_on_screen(dialog):
    """`CLAUDE.md` §2.5 — no name standing in for settings that cannot be
    read. The composite's flashing binding has real parameters; they must be
    visible, not merely stored."""
    flashing = next(b for b in dialog._boxes
                    if b.binding.measure_key == "flashing_events_per_min")
    shown = flashing._pinned.text()
    assert "threshold = 0.1" in shown
    assert "sample_fps = 10.0" in shown


def test_every_binding_shows_its_weight_range_transform_and_missing_policy(
        dialog):
    for box in dialog._boxes:
        assert box._transform.currentData() in R.TRANSFORMS
        assert box._missing.currentData() in R.MISSING_POLICIES
        binding = box.binding
        assert box._weight.value() == pytest.approx(binding.weight)
        assert box._max.value() == pytest.approx(binding.range_max)


def test_an_unvalidated_method_is_flagged_in_its_own_box(dialog):
    """`CLAUDE.md` §2.2 — flagged wherever the numbers appear."""
    flashing = next(b for b in dialog._boxes
                    if b.binding.measure_key == "flashing_events_per_min")
    assert "unvalidated" in flashing._flag.text().lower()


def test_the_underived_warning_reaches_the_screen(dialog):
    """The single most important sentence attached to the composite."""
    body = _text(dialog._summary_html(dialog._current))
    assert "no recorded derivation" in body.lower()
    assert "neither says how to combine them" in body.lower()


# ---------------------------------------------------------------------------
# The locked recipe explains itself
# ---------------------------------------------------------------------------

def test_a_locked_recipe_says_why_rather_than_only_greying_out(dialog):
    """`CLAUDE.md` §4: an unavailable control must not look like a broken one."""
    assert dialog._current.locked
    assert dialog._btn_save.isEnabled() is False
    assert dialog._btn_del.isEnabled() is False
    assert dialog._name.isEnabled() is False
    for box in dialog._boxes:
        assert box._weight.isEnabled() is False
        assert box._method.isEnabled() is False

    reason = dialog._banner.text().lower()
    assert "locked" in reason
    assert "published" in reason
    assert "duplicate" in reason
    assert "duplicate" in dialog._status.text().lower()


def test_duplicate_is_offered_and_produces_an_editable_copy(dialog):
    dialog._duplicate()
    assert dialog._current.locked is False
    assert dialog._btn_save.isEnabled() is True
    assert dialog._name.isEnabled() is True
    assert all(b._weight.isEnabled() for b in dialog._boxes)


def test_a_copy_of_a_locked_recipe_does_not_claim_to_be_locked(dialog):
    """Its notes are inherited so the underived caveat survives — but a copy
    that says "locked because the published index is built on it" is stating
    something false about itself."""
    dialog._duplicate()
    notes = dialog._current.notes.lower()
    assert "this copy is not locked" in notes
    assert "no recorded derivation" in notes          # the caveat survived


# ---------------------------------------------------------------------------
# The version rule, which the screen must not be able to skip
# ---------------------------------------------------------------------------

def test_changing_a_weight_demands_a_reason_before_save(dialog, qapp):
    """THE defect found by driving this dialog. `_read_form_into` wrote into
    the live recipe rather than the throwaway copy it was handed, so the dirty
    check compared an unchanged copy against the baseline, reported "nothing
    has changed", and left Save enabled with no reason — one edit behind, and
    invisible from the screen."""
    dialog._duplicate()
    dialog._boxes[0]._weight.setValue(0.40)
    qapp.processEvents()

    assert dialog._reason.isVisibleTo(dialog) is True
    assert dialog._btn_save.isEnabled() is False, (
        "Save was available for a changed operationalization with no reason")
    assert "reason" in dialog._status.text().lower()

    dialog._reason.setText("motion was swamping pacing in the pilot")
    dialog._sync_buttons()
    assert dialog._btn_save.isEnabled() is True


def test_saving_a_changed_recipe_records_the_reason_and_the_diff(dialog):
    dialog._duplicate()
    dialog._boxes[0]._weight.setValue(0.40)
    dialog._reason.setText("pacing was under-weighted for this corpus")
    dialog._sync_buttons()
    dialog._save()

    saved = dialog._current
    assert saved.version == 2
    latest = saved.history[-1]
    assert latest.reason == "pacing was under-weighted for this corpus"
    assert any("weight" in c for c in latest.changes)


def test_renaming_asks_for_no_reason_and_adds_no_version(dialog):
    dialog._duplicate()
    before = dialog._current.version
    dialog._name.setText("A different name entirely")
    dialog._sync_buttons()

    assert dialog._reason.isVisibleTo(dialog) is False
    assert dialog._btn_save.isEnabled() is True
    assert "not a new version" in dialog._status.text().lower()
    dialog._save()
    assert dialog._current.version == before


def test_the_written_file_carries_what_the_screen_showed(dialog, library):
    """Verify against the artefact, not the render."""
    dialog._duplicate()
    dialog._boxes[0]._weight.setValue(0.33)
    dialog._reason.setText("checking the file")
    dialog._sync_buttons()
    dialog._save()

    path = next(p for p in (library / ".analysis" / "recipes").glob("*.json")
                if json.loads(p.read_text(encoding="utf-8"))["id"]
                == dialog._current.id)
    written = json.loads(path.read_text(encoding="utf-8"))
    binding = written["bindings"][0]
    assert binding["weight"] == 0.33
    assert binding["parameters"]                      # pinned, in the file
    assert written["history"][-1]["reason"] == "checking the file"


# ---------------------------------------------------------------------------
# Divergences
# ---------------------------------------------------------------------------

def test_a_pinned_value_that_differs_from_the_live_setting_is_reported(
        qapp, library, config):
    """The accepted cost of pinning, on screen. Note the shipped composite is
    generated FROM the config and so can never diverge from it — this needs a
    saved recipe, which is the real case."""
    from ui.recipes import RecipesDialog

    recipe = R.new_recipe(
        "Pinned pacing", "pacing", config,
        measures=[("hard_cuts_per_min",
                   "auto:transitions:pyscenedetect_content")],
        reason="fixture")
    R.save_recipe(recipe, library)

    moved = json.loads(json.dumps(config))
    moved["measurements"]["transitions"]["params"]["threshold"] = 33.0
    d = RecipesDialog(moved, library, S.library_scope())
    for i in range(d._list.count()):
        if "Pinned pacing" in d._list.item(i).text():
            d._select_row(i)
            break

    body = _text(d._summary_html(d._current))
    assert "27.0" in body and "33.0" in body
    assert "statements, not errors" in body
    d.deleteLater()


# ---------------------------------------------------------------------------
# Applying to a scope
# ---------------------------------------------------------------------------

def test_applying_the_composite_reports_scores_and_refusals_separately(
        dialog, qapp, config):
    """One analysed episode, one not. The unanalysed one must appear as a
    refusal with its reason, not as a missing row and not as a zero."""
    from ui.recipes import EvaluationWorker

    targets = dialog._scope_targets()
    assert len(targets) == 2

    worker = EvaluationWorker(dialog._current, dialog._root, config, targets,
                              None)
    worker.run()                                     # synchronous, in-test
    results = []
    worker.finished_ok.connect(results.append)
    worker.run()
    rows = results[-1]

    scored = [r for _l, r in rows if r.score is not None]
    refused = [r for _l, r in rows if r.score is None]
    assert len(scored) == 1
    assert len(refused) == 1
    assert any("No cached result" in p.detail
               for p in refused[0].parts if not p.ok)

    html = _text(dialog._evaluation_html(rows))
    assert "1 scored, 1 refused" in html
    assert "not a failure to compute" in html


def test_the_refusal_table_groups_instead_of_repeating_itself(dialog):
    """124 unanalysed episodes times six measures is 744 rows all saying the
    same thing, and the one refusal that differs is lost in the middle. The
    count is the fact."""
    from analyzer.recipes import Evaluation

    refused = []
    for i in range(30):
        ev = R.evaluate(dialog._current,
                        C.EpisodeRef(root=dialog._root, show_name=SHOW,
                                     stem=f"absent {i}"),
                        None)
        refused.append((f"absent {i}", ev))

    html = dialog._refusal_table(refused)
    assert html.count("<tr") <= 20, "the table is repeating itself"
    assert ">30<" in html, "the count of affected episodes is the fact"
    assert "and 27 more" in html


def test_a_recipe_with_no_weights_set_refuses_rather_than_scoring_zero(
        dialog, config):
    """A brand-new recipe has every weight at zero. Summing that gives 0.0 —
    a real number in the score's own range, reading as "measured, and very
    low"."""
    fresh = R.new_recipe("Blank", "colour", config)
    assert fresh.total_weight() == 0
    ev = R.evaluate(fresh, C.EpisodeRef(root=dialog._root, show_name=SHOW,
                                        stem=STEM), config)
    assert ev.score is None
    assert ev.status == R.REFUSED
    assert "every weight" in ev.detail.lower()


# ---------------------------------------------------------------------------
# Import reports gaps
# ---------------------------------------------------------------------------

def test_an_imported_binding_this_install_cannot_resolve_says_so_in_its_box(
        qapp, library, config):
    from ui.recipes import RecipesDialog

    recipe = R.new_recipe(
        "Imported", "pacing", config,
        measures=[("hard_cuts_per_min",
                   "auto:transitions:pyscenedetect_content")],
        reason="fixture")
    recipe.bindings[0].method_key = "auto:transitions:acme_shotfinder"
    R.save_recipe(recipe, library)

    d = RecipesDialog(config, library, S.library_scope())
    for i in range(d._list.count()):
        if "Imported" in d._list.item(i).text():
            d._select_row(i)
            break
    box = d._boxes[0]
    assert "no such method" in box._flag.text().lower()
    assert "kept as imported rather than substituted" in box._flag.text()
    d.deleteLater()


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

def test_the_main_window_can_actually_open_this_dialog():
    """A function-local import is invisible to import-time checking, and a
    source-text test cannot tell a name that resolves from one that does not —
    `LEARNINGS.md` § *A source-text test passed while the import it asserted
    on was broken*. So resolve the symbols."""
    import ast
    import importlib
    import inspect

    from ui.main_window import MainWindow

    tree = ast.parse(inspect.getsource(MainWindow.open_recipes).strip())
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = importlib.import_module(node.module)
            for alias in node.names:
                assert hasattr(module, alias.name), (
                    f"{node.module}.{alias.name} does not resolve")
                found = True
    assert found, "open_recipes imports nothing — is it still wired?"


def test_the_dialog_reads_the_scope_it_is_given(qapp, library, config):
    """It applies to the same episodes the rest of the window is showing."""
    from ui.recipes import RecipesDialog

    episode = library / SHOW / f"{STEM}.mp4"
    narrowed = S.Scope(key="sample:x", label="One episode",
                       episodes=(episode,))
    d = RecipesDialog(config, library, narrowed)
    assert len(d._scope_targets()) == 1
    assert "One episode" in d._scope_line()
    d.deleteLater()
