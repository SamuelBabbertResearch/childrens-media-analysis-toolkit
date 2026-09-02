"""
The Constructs tab — a recipe drawn as the graph it already is.

Asserted on the SCENE, not on a screenshot: every claim this canvas makes is
carried by an item's geometry or a pen's width, so those are what get read. In
particular "wire thickness is the contribution share" is a claim about a
`QPen`, and the only honest way to check it is to measure the pen.

Note what these tests deliberately cannot cover: this environment's offscreen
Qt platform has **zero font families**, so nothing renders a glyph and every
drawn screen produces tofu. That is environmental — the existing pipeline
canvas does the same — and it means text POSITIONS are verified here while
text APPEARANCE is not. Nobody has seen this with real fonts yet.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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
    """One analysed episode with values that make the ceilings bite, and one
    that was never analysed."""
    root = tmp_path / "lib"
    show = root / SHOW
    show.mkdir(parents=True)
    (show / f"{STEM}.mp4").touch()
    (show / "S01E02 Unanalysed.mp4").touch()

    result = EpisodeResult(file=f"{STEM}.mp4", duration_sec=600.0,
                           config=json.loads(json.dumps(config)))
    m = result.metrics
    m.scene_pacing.cuts_per_min = 15.0     # 45 ceiling  -> 0.333 normalised
    m.color_saturation.mean = 0.46         # 0.85        -> 0.541
    m.color_saturation.contrast_mean = 0.19  # 0.35      -> 0.543
    m.motion.mean = 0.065                  # 0.35        -> 0.186  (compressed)
    m.flashing.luminance_delta_events_per_min = 2.0   # 40 -> 0.05
    m.audio.available = True
    m.audio.rms_mean = 0.038               # 0.35        -> 0.109
    cache = root / ".analysis" / SHOW / f"{STEM}.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(result.to_dict()), encoding="utf-8")
    return root


class _FakeWindow:
    def __init__(self, root, config):
        self._root = root
        self._cfg = config

    def statusBar(self):
        class _Bar:
            def showMessage(self, *a, **k):
                pass
        return _Bar()


@pytest.fixture
def tab(qapp, library, config):
    from ui.constructs_tab import ConstructsTab
    t = ConstructsTab(_FakeWindow(library, config))
    t.set_scope(S.library_scope())
    t.refresh()
    yield t
    t.deleteLater()


def _items(tab, cls):
    return [i for i in tab._view._scene.items() if isinstance(i, cls)]


def _by_measure(tab):
    from ui.constructs_tab import MeasureItem
    return {i.binding.measure_key: i for i in _items(tab, MeasureItem)}


def _pens(tab, kind="measure"):
    """{key: pen width}, matched by the edge's OWN record of what it ends at.

    Not by geometry: a construct block centred on a one-measure group sits at
    the same y as that measure's card, so position is ambiguous exactly where
    the two edge kinds need telling apart.
    """
    from ui.constructs_tab import EdgeItem
    return {e.dst_key: e.pen().widthF()
            for e in _items(tab, EdgeItem) if e.kind == kind}


def _select(tab, name):
    for i in range(tab._chooser.count()):
        if name in tab._chooser.itemText(i):
            tab._chooser.setCurrentIndex(i)
            return
    raise AssertionError(f"{name} is not in the chooser")


def _evaluate(tab, qapp):
    tab._compute_contributions()
    assert tab._worker is not None
    tab._worker.wait(30000)
    qapp.processEvents()


# ---------------------------------------------------------------------------
# The drawing exists and is the recipe
# ---------------------------------------------------------------------------

def test_the_shipped_composite_draws_three_columns(tab):
    """Target then construct then measure. Colour owns two measures, so there
    are five construct blocks for six bindings."""
    from analyzer import constructs as C
    from ui.constructs_tab import (ConstructItem, EdgeItem, MeasureItem,
                                   TargetItem)

    recipe = tab.current_recipe()
    assert recipe.name == R.SHIPPED_COMPOSITE_NAME
    assert len(_items(tab, TargetItem)) == 1
    assert len(_items(tab, MeasureItem)) == len(recipe.bindings)

    owning = {C.get_measure(b.measure_key).construct_key
              for b in recipe.bindings}
    assert len(_items(tab, ConstructItem)) == len(owning)
    assert {i.key for i in _items(tab, ConstructItem)} == owning
    # One edge per measure, plus one per contributing construct.
    assert len(_items(tab, EdgeItem)) == len(recipe.bindings) + len(owning)


def test_the_columns_are_ordered_left_to_right(tab):
    from ui.constructs_tab import ConstructItem, MeasureItem, TargetItem
    target = _items(tab, TargetItem)[0]
    constructs = _items(tab, ConstructItem)
    measures = _items(tab, MeasureItem)
    assert all(c.pos().x() > target.pos().x() for c in constructs)
    assert all(m.pos().x() > c.pos().x()
               for m in measures for c in constructs)


def test_a_constructs_edge_carries_the_sum_of_its_measures(tab):
    """Colour owns saturation (0.05) and contrast (0.10), so Colour's edge to
    the composite stands for 0.15 — a summary of stored facts, not a stored
    one. Thickness is normalised, so the check is that colour's two measures
    together outweigh either alone."""
    recipe = tab.current_recipe()
    by_construct = _pens(tab, "construct")
    by_measure = _pens(tab, "measure")
    assert set(by_construct) >= {"colour", "pacing"}

    weights = {b.measure_key: b.weight for b in recipe.bindings}
    assert weights["saturation_mean"] + weights["contrast_mean"] == \
        pytest.approx(0.15)
    assert by_construct["colour"] > by_measure["saturation_mean"]
    assert by_construct["colour"] > by_measure["contrast_mean"]


def test_a_single_construct_recipe_grows_no_self_edge(qapp, library, config):
    """A Pacing recipe must not sprout a Pacing block hanging off a Pacing
    target — that is a self-edge dressed up as structure."""
    from ui.constructs_tab import ConstructItem, ConstructsTab, MeasureItem

    recipe = R.new_recipe(
        "Pacing only", "pacing", config,
        measures=[("hard_cuts_per_min",
                   "auto:transitions:pyscenedetect_content")],
        reason="fixture")
    recipe.bindings[0].weight = 1.0
    R.save_recipe(recipe, library)

    t = ConstructsTab(_FakeWindow(library, config))
    t.set_scope(S.library_scope())
    t.refresh()
    for i in range(t._chooser.count()):
        if "Pacing only" in t._chooser.itemText(i):
            t._chooser.setCurrentIndex(i)
            break
    assert t.current_recipe().construct_key == "pacing"
    assert _items(t, ConstructItem) == []
    assert len(_items(t, MeasureItem)) == 1
    t.deleteLater()


def test_no_arrowheads_are_drawn_anywhere(tab):
    """`CLAUDE.md` §2.2 — nothing here is causal, and an arrow between two
    boxes reads as causation to almost every reader. This is the artefact most
    likely to end up in a talk detached from its caption."""
    from PySide6.QtWidgets import QGraphicsPolygonItem
    from ui.constructs_tab import EdgeItem

    assert not _items(tab, QGraphicsPolygonItem)
    for edge in _items(tab, EdgeItem):
        # A plain cubic: one move-to and one curve, nothing appended.
        assert edge.path().elementCount() == 4


def test_every_card_carries_its_pinned_parameters(tab):
    """A recipe is inspectable or it is not a recipe — including when drawn."""
    card = _by_measure(tab)["flashing_events_per_min"]
    text = " ".join(t for _kind, t in card._body)
    assert "threshold = 0.1" in text
    assert "sample_fps = 10.0" in text


def test_an_unvalidated_method_is_flagged_on_its_card(tab):
    card = _by_measure(tab)["flashing_events_per_min"]
    kinds = {kind for kind, _t in card._body}
    assert "flag" in kinds
    assert any("unvalidated" in t for _k, t in card._body)


def test_the_headline_says_the_wires_are_nominal_before_evaluation(tab):
    assert "NOMINAL" in tab._headline.text()


# ---------------------------------------------------------------------------
# The contribution share — the reason this canvas earns its place
# ---------------------------------------------------------------------------

def test_wire_thickness_follows_the_declared_weight_before_evaluation(tab):
    pens = _pens(tab)
    recipe = tab.current_recipe()
    weights = {b.measure_key: b.weight for b in recipe.bindings}
    order_by_pen = sorted(pens, key=lambda k: pens[k])
    order_by_weight = sorted(weights, key=lambda k: weights[k])
    assert [weights[k] for k in order_by_pen] == \
           sorted(weights[k] for k in order_by_weight)


def test_the_shares_account_for_the_whole_score(tab, qapp):
    """If they do not sum to 1, the diagram is attributing more or less of the
    score than the score contains."""
    _evaluate(tab, qapp)
    assert sum(tab._shares.values()) == pytest.approx(1.0, abs=1e-4)


def test_a_compressed_measure_draws_thinner_than_its_weight_claims(tab, qapp):
    """`ARCHITECTURE.md` §8.1a, made visible. Motion is declared 0.25 and
    contrast 0.10, but motion reaches a small fraction of its ceiling while
    contrast reaches most of its — so contrast's wire must end up THICKER
    than motion's despite declaring less than half the weight.

    This is the whole argument for the canvas: the finding was quantified in
    prose in August and could not be seen anywhere.
    """
    recipe = tab.current_recipe()
    declared = {b.measure_key: b.weight for b in recipe.bindings}
    assert declared["motion_mean"] > declared["contrast_mean"]

    before = _pens(tab)
    assert before["motion_mean"] > before["contrast_mean"]

    _evaluate(tab, qapp)

    assert tab._shares["contrast_mean"] > tab._shares["motion_mean"]
    after = _pens(tab)
    assert after["contrast_mean"] > after["motion_mean"], (
        f"contrast contributes {tab._shares['contrast_mean']:.3f} against "
        f"motion's {tab._shares['motion_mean']:.3f}, but its wire is thinner")


def test_each_card_states_declared_against_contributed(tab, qapp):
    _evaluate(tab, qapp)
    card = _by_measure(tab)["motion_mean"]
    share_lines = [t for k, t in card._body if k == "share"]
    assert share_lines, "the card does not say what it actually contributed"
    assert "declared 0.25" in share_lines[0]
    assert "% of the score" in share_lines[0]


def test_the_headline_says_which_quantity_is_on_the_wires(tab, qapp):
    """Showing declared thickness beside an effective score would be
    `LEARNINGS.md` shape 1 in a new place, so the header always says which."""
    _evaluate(tab, qapp)
    assert "CONTRIBUTION SHARE" in tab._headline.text()
    assert "not the declared weight" in tab._headline.text()


# ---------------------------------------------------------------------------
# Computed numbers must not outlive what they were computed for
# ---------------------------------------------------------------------------

def test_switching_recipe_drops_the_computed_contributions(tab, qapp, config,
                                                           library):
    """THE defect found by driving this tab. Contributions are keyed by
    MEASURE, and two recipes routinely share one — so selecting a hand-coding
    pacing recipe showed the composite's ContentDetector mean of 15.38
    cuts/min on a card whose method line read "Hand coding"."""
    _evaluate(tab, qapp)
    assert tab._shares is not None

    hand = R.new_recipe(
        "Pacing by hand", "pacing", config,
        measures=[("hard_cuts_per_min", "hand:transitions")],
        reason="fixture")
    hand.bindings[0].weight = 1.0
    R.save_recipe(hand, library)
    tab.refresh()
    for i in range(tab._chooser.count()):
        if "Pacing by hand" in tab._chooser.itemText(i):
            tab._chooser.setCurrentIndex(i)
            break

    assert tab._shares is None, "one recipe's numbers survived onto another"
    card = _by_measure(tab)["hard_cuts_per_min"]
    assert not any(k in ("value", "share") for k, _t in card._body), (
        "an automated mean is being shown under a hand-coding method")


def test_changing_the_scope_drops_the_computed_contributions(tab, qapp,
                                                             library):
    """They were means over a different set of episodes; leaving them on
    screen under a new scope's name would describe the wrong corpus."""
    _evaluate(tab, qapp)
    assert tab._shares is not None
    tab.set_scope(S.Scope(key="sample:x", label="One episode",
                          episodes=(library / SHOW / f"{STEM}.mp4",)))
    assert tab._shares is None


def test_the_tab_narrows_to_the_scope_it_is_given(tab, library):
    """A view narrows to the scope; a workbench stages from it. This is a
    view."""
    assert len(tab._episode_targets()) == 2
    tab.set_scope(S.Scope(key="sample:x", label="One episode",
                          episodes=(library / SHOW / f"{STEM}.mp4",)))
    assert len(tab._episode_targets()) == 1


# ---------------------------------------------------------------------------
# Refusals are drawn, not hidden
# ---------------------------------------------------------------------------

def test_a_measure_that_did_not_resolve_keeps_its_box_and_says_why(
        qapp, tmp_path, config):
    """A diagram that silently omits what it could not measure is how
    '1 of 6 measured; 5 failed' got reported for a show where nothing failed."""
    from ui.constructs_tab import ConstructsTab

    root = tmp_path / "empty"
    show = root / SHOW
    show.mkdir(parents=True)
    (show / f"{STEM}.mp4").touch()          # present, never analysed

    t = ConstructsTab(_FakeWindow(root, config))
    t.set_scope(S.library_scope())
    t.refresh()
    _evaluate(t, qapp)

    cards = _by_measure(t)
    assert cards, "the diagram dropped its boxes when nothing resolved"
    for card in cards.values():
        assert card.refused()
        assert any(k == "refusal" for k, _t in card._body)
    for width in _pens(t).values():
        assert width > 0
    t.deleteLater()


# ---------------------------------------------------------------------------
# Authoring — `TODO.md` item G2
#
# The tab used to assert it never wrote anything. It writes now, and these
# replace that assertion with the rules that took its place: writes go through
# `save_recipe`, a changed operationalization needs a reason, the shipped
# composite stays locked, measures come from a palette, and a layout is never
# any of those things.
# ---------------------------------------------------------------------------

def test_the_canvas_writes_only_through_save_recipe():
    """Not "it writes nothing" any more — "it writes the sanctioned way".

    A canvas that assembled its own JSON, or wrote a version without
    `bump_version`, would be a second implementation of recipe storage and
    would drift from the first. Resolved rather than grepped, so a name that no
    longer exists cannot pass.
    """
    import inspect

    from analyzer import recipes
    from ui import constructs_tab

    src = inspect.getsource(constructs_tab)
    for sanctioned in ("R.save_recipe", "R.bump_version", "R.save_view"):
        assert sanctioned in src
        assert hasattr(recipes, sanctioned.split(".")[1])
    # No hand-rolled persistence beside the module that owns it.
    assert "json.dump" not in src
    assert "write_text" not in src


def test_edit_mode_is_off_until_asked_for(tab):
    """Without a mode the same drag means pan over the background and move over
    a card — and an accidental drag on the locked composite would read as
    editing something that cannot be saved."""
    assert tab._editing is False
    assert tab._panel.isHidden()
    assert tab._view._editable is False
    for node in tab._view._nodes.values():
        assert not node.flags() & node.GraphicsItemFlag.ItemIsMovable


def test_the_palette_offers_measures_and_only_measures(tab):
    """Rule 2: constructs may be free-form, MEASURES MAY NOT. A user-defined
    measure with no data path is `LEARNINGS.md` shape 2 — the defect this whole
    phase exists to remove — reintroduced through a nicer interface.

    Rule 4 falls out of the same list: the palette holds measures, so a
    composite cannot be offered as an input to a composite and nesting is
    impossible by construction rather than by a check.
    """
    from analyzer import constructs as C

    tab._btn_edit.setChecked(True)
    offered = {tab._palette.itemData(i) for i in range(tab._palette.count())
               if tab._palette.itemData(i)}
    shipped = {m.key for m in C.MEASURES}
    bound = {b.measure_key for b in tab.current_recipe().bindings}
    assert offered == shipped - bound
    assert offered, "nothing to bind"

    # The construct headings carry no measure key and cannot be chosen, so
    # "Add" can never be pressed on one.
    model = tab._palette.model()
    for i in range(tab._palette.count()):
        if tab._palette.itemData(i) is None:
            assert not model.item(i).isEnabled()
    assert tab._palette.itemData(tab._palette.currentIndex()), \
        "the palette opened on a heading rather than a measure"

    # No control anywhere on the tab invents a measure or takes a typed one.
    import inspect

    from ui import constructs_tab
    src = inspect.getsource(constructs_tab)
    assert "new_measure" not in src
    assert "Measure(" not in src


def test_adding_a_measure_writes_a_binding_that_can_actually_resolve(
        qapp, library, config):
    """`LEARNINGS.md` § *`new_recipe` accepted a method key that does not
    exist*: canvas authoring was named there as about to make the permissive
    path the common one. The palette carries the measure key as item DATA and
    the method comes from `methods_for`, so neither is ever a typed string."""
    from analyzer import constructs as C
    from ui.constructs_tab import ConstructsTab

    recipe = R.new_recipe("Empty", "pacing", config, measures=[],
                          reason="fixture")
    R.save_recipe(recipe, library)

    t = ConstructsTab(_FakeWindow(library, config))
    t.set_scope(S.library_scope())
    t.refresh()
    _select(t, "Empty")
    t._btn_edit.setChecked(True)
    for i in range(t._palette.count()):
        if t._palette.itemData(i) == "hard_cuts_per_min":
            t._palette.setCurrentIndex(i)
            break
    t._btn_add.click()

    binding = t.current_recipe().binding("hard_cuts_per_min")
    assert binding is not None
    assert C.get_measure(binding.measure_key) is not None
    assert C.get_method(binding.measure_key, binding.method_key) is not None
    # Pinned from the live config at the moment of binding, as `new_recipe`
    # would have done — not left empty to be filled in later.
    assert binding.parameters == R.pin_parameters(
        "hard_cuts_per_min", binding.method_key, config)
    t.deleteLater()


def test_a_weight_lands_on_the_measure_that_was_selected(qapp, library,
                                                         config):
    """THE defect found by driving G2 and reading the written recipe.

    Every edit refills the bound list, and `QListWidget.clear()` drops the
    current row to -1 — so a row-based restore snapped the selection back to
    the first binding after each edit. Two weights entered for two measures
    were both written onto the first one. The list looked right the whole time;
    only the file said otherwise.
    """
    from ui.constructs_tab import ConstructsTab

    recipe = R.new_recipe("Two measures", "pacing", config, measures=[],
                          reason="fixture")
    R.save_recipe(recipe, library)
    t = ConstructsTab(_FakeWindow(library, config))
    t.set_scope(S.library_scope())
    t.refresh()
    _select(t, "Two measures")
    t._btn_edit.setChecked(True)

    for key, weight in (("hard_cuts_per_min", 0.6), ("mean_shot_length", 0.4)):
        for i in range(t._palette.count()):
            if t._palette.itemData(i) == key:
                t._palette.setCurrentIndex(i)
                break
        t._btn_add.click()
        t._weight.setValue(weight)

    live = t.current_recipe()
    assert live.binding("hard_cuts_per_min").weight == pytest.approx(0.6)
    assert live.binding("mean_shot_length").weight == pytest.approx(0.4)

    t._reason.setText("fixture")
    t._sync_edit_panel()
    t._btn_save.click()

    # The file, not the panel.
    written = R.load_recipe(
        next(p for p in (library / ".analysis" / "recipes").glob("Two*.json")))
    assert {b.measure_key: b.weight for b in written.bindings} == \
        pytest.approx({"hard_cuts_per_min": 0.6, "mean_shot_length": 0.4})
    t.deleteLater()


def test_saving_a_changed_operationalization_demands_a_reason(qapp, library,
                                                              config):
    """Rule 3, and it is `bump_version`'s rule — the screen does not get to
    skip it."""
    from ui.constructs_tab import ConstructsTab

    recipe = R.new_recipe(
        "Reasoned", "pacing", config,
        measures=[("hard_cuts_per_min",
                   "auto:transitions:pyscenedetect_content")],
        reason="fixture")
    R.save_recipe(recipe, library)
    t = ConstructsTab(_FakeWindow(library, config))
    t.set_scope(S.library_scope())
    t.refresh()
    _select(t, "Reasoned")
    t._btn_edit.setChecked(True)
    assert t._btn_save.isEnabled(), "an unchanged recipe should still save"

    t._weight.setValue(0.75)
    assert not t._btn_save.isEnabled()
    assert "reason" in t._edit_status.text().lower()
    t._btn_save.click()                        # a disabled button, pressed
    saved = R.load_recipe(recipe.path)
    assert saved.version == 1, "a version was recorded with no reason"

    t._reason.setText("Weighting the pilot's only measure fully.")
    t._sync_edit_panel()
    assert t._btn_save.isEnabled()
    t._btn_save.click()
    saved = R.load_recipe(recipe.path)
    assert saved.version == 2
    assert saved.history[-1].reason.startswith("Weighting")
    t.deleteLater()


def test_the_locked_composite_cannot_be_rebound_but_can_be_arranged(tab,
                                                                    library):
    """The two halves of decision 3, on one screen. What it binds is fixed —
    the published index is built on it. Where its boxes sit is not part of the
    operationalization, and this is the diagram most likely to become a
    methods figure."""
    recipe = tab.current_recipe()
    assert recipe.locked
    tab._btn_edit.setChecked(True)
    assert not tab._btn_add.isEnabled()
    assert not tab._btn_remove.isEnabled()
    assert not tab._weight.isEnabled()
    assert not tab._btn_save.isEnabled()
    assert "LOCKED" in tab._edit_banner.text()

    node = tab._view._nodes["measure:motion_mean"]
    node.setPos(640.0, 192.0)
    tab._persist_layout()
    assert R.view_path(recipe, library).exists()
    assert R.load_view(recipe, library)["measure:motion_mean"] == (640.0, 192.0)


def test_a_dragged_box_snaps_to_the_pipeline_canvas_grid(tab):
    """Same grid as the Pipeline canvas, so two diagrams out of this
    application do not align differently."""
    from ui.constructs_tab import GRID

    tab._btn_edit.setChecked(True)
    node = tab._view._nodes["target"]
    node.setPos(60.0, 83.0)
    assert node.pos().x() % GRID == 0
    assert node.pos().y() % GRID == 0
    assert (node.pos().x(), node.pos().y()) == (64.0, 80.0)


def test_no_control_in_the_edit_panel_is_drawn_outside_it(qapp, tab):
    """Reported from the real application: the dropdown arrows, the Add button
    and Save were all drawn off the right-hand edge of the window.

    The panel had a maximum width its own contents could not fit in — Qt
    honoured the maximum and the children overflowed. Asserted on GEOMETRY,
    because "the combo is there" was true the whole time it could not be used.
    """
    from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

    host = QWidget()
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(tab)
    host.resize(1280, 800)
    host.show()
    tab._btn_edit.setChecked(True)
    qapp.processEvents()

    scroll = tab._panel.findChild(QScrollArea)
    width = scroll.viewport().width()
    for name in ("_method", "_palette", "_weight", "_btn_add", "_btn_save",
                 "_btn_discard", "_btn_remove", "_reason"):
        widget = getattr(tab, name)
        assert widget.x() >= 0, name
        assert widget.x() + widget.width() <= width, (
            f"{name} is drawn {widget.x() + widget.width() - width}px past "
            f"the panel's edge")
    assert scroll.horizontalScrollBar().maximum() == 0
    host.deleteLater()


def test_a_bound_measure_is_scaled_when_a_reference_range_exists(qapp, library,
                                                                 config):
    """A default transform of "none" feeds the RAW value into a weighted sum.

    Cuts per minute runs around 15 and colour saturation around 0.46, so two
    measures added with equal weights and no transform give a composite
    dominated by whichever has the larger units — with both weights on screen
    reading as equal. Every measure in the shipped composite is scaled for
    exactly this reason.
    """
    from ui.constructs_tab import ConstructsTab

    recipe = R.new_recipe("Scaled", "pacing", config, measures=[],
                          reason="fixture")
    R.save_recipe(recipe, library)
    t = ConstructsTab(_FakeWindow(library, config))
    t.set_scope(S.library_scope())
    t.refresh()
    _select(t, "Scaled")
    t._btn_edit.setChecked(True)
    _add(t, "hard_cuts_per_min")

    binding = t.current_recipe().binding("hard_cuts_per_min")
    assert binding.transform == R.TRANSFORM_MINMAX
    # The ceiling comes from config.json, never restated here.
    assert (binding.range_min, binding.range_max) == \
        R.reference_range_for("hard_cuts_per_min", config)
    assert "scaled over" in t._scale_note.text().lower()
    t.deleteLater()


def test_a_measure_with_no_configured_range_says_so_instead_of_inventing_one(
        qapp, library, config):
    """Ten of the sixteen measures have never had a ceiling chosen for them.

    Inventing one would be a scoring decision made on the researcher's behalf
    and hidden in a default — `ARCHITECTURE.md` §8.1a is a record of that
    having already happened once, not a pattern to extend.
    """
    from ui.constructs_tab import ConstructsTab

    assert R.reference_range_for("mean_shot_length", config) is None

    recipe = R.new_recipe("Unscaled", "pacing", config, measures=[],
                          reason="fixture")
    R.save_recipe(recipe, library)
    t = ConstructsTab(_FakeWindow(library, config))
    t.set_scope(S.library_scope())
    t.refresh()
    _select(t, "Unscaled")
    t._btn_edit.setChecked(True)
    _add(t, "mean_shot_length")

    binding = t.current_recipe().binding("mean_shot_length")
    assert binding.transform == R.TRANSFORM_NONE
    assert "NO transform" in t._scale_note.text()
    assert "has not been invented" in t._scale_note.text()
    t.deleteLater()


def test_summing_a_raw_measure_against_a_scaled_one_is_reported(qapp, library,
                                                                config):
    """Adding a 0–1 fraction to a value in seconds is adding two different
    things, and the weights then describe none of it. Reported, not blocked."""
    from ui.constructs_tab import ConstructsTab

    recipe = R.new_recipe("Mixed", "pacing", config, measures=[],
                          reason="fixture")
    R.save_recipe(recipe, library)
    t = ConstructsTab(_FakeWindow(library, config))
    t.set_scope(S.library_scope())
    t.refresh()
    _select(t, "Mixed")
    t._btn_edit.setChecked(True)

    _add(t, "hard_cuts_per_min")            # scaled, from config
    t._weight.setValue(0.5)
    assert "NOT ON ONE SCALE" not in t._totals.text()

    _add(t, "mean_shot_length")             # raw seconds
    t._weight.setValue(0.5)
    assert "NOT ON ONE SCALE" in t._totals.text()
    assert "Mean shot length" in t._totals.text()
    assert R.mixed_scales(t.current_recipe()) == ["mean_shot_length"]
    t.deleteLater()


def test_an_all_zero_recipe_says_it_will_refuse_before_it_refuses(qapp,
                                                                  library,
                                                                  config):
    """`evaluate` refuses rather than reporting 0.0 — a real number in the
    composite's own range beside genuine ones. The panel says so first."""
    from ui.constructs_tab import ConstructsTab

    recipe = R.new_recipe("Unweighted", "pacing", config, measures=[],
                          reason="fixture")
    R.save_recipe(recipe, library)
    t = ConstructsTab(_FakeWindow(library, config))
    t.set_scope(S.library_scope())
    t.refresh()
    _select(t, "Unweighted")
    t._btn_edit.setChecked(True)
    assert "cannot score" in t._totals.text()
    _add(t, "hard_cuts_per_min")
    assert "REFUSE to score" in t._totals.text()
    t._weight.setValue(1.0)
    assert "REFUSE" not in t._totals.text()
    assert "weights total 1" in t._totals.text()
    t.deleteLater()


def test_a_recipe_can_be_created_and_duplicated_without_leaving_the_tab(
        qapp, library, config):
    """The tab could choose a recipe but not make one, so authoring started
    here and immediately sent you to File → Recipes… — including from the
    locked composite's own banner, which named Duplicate as the route and
    offered no way to take it."""
    from analyzer import constructs as C
    from ui.constructs_tab import ConstructsTab

    t = ConstructsTab(_FakeWindow(library, config))
    t.set_scope(S.library_scope())
    t.refresh()

    t._create_recipe_over("pacing")
    made = t.current_recipe()
    assert made.construct_key == "pacing"
    assert t._editing, "a new recipe should open ready to be built"
    # Pacing's own eight measures, bound at weight zero — the same starting
    # point File → Recipes… produces, so the two routes cannot disagree.
    assert len(made.bindings) == len(C.measures_for("pacing"))
    assert made.total_weight() == 0
    # And the scaling default reaches this route too: cuts per minute has a
    # configured ceiling, mean shot length has never had one chosen.
    assert made.binding("hard_cuts_per_min").transform == R.TRANSFORM_MINMAX
    assert made.binding("mean_shot_length").transform == R.TRANSFORM_NONE

    t._chooser.setCurrentIndex(0)
    assert t.current_recipe().locked
    t._duplicate()
    copy = t.current_recipe()
    assert not copy.locked
    assert copy.name.endswith("copy")
    assert len(copy.bindings) == 6
    assert R.load_recipe(copy.path).locked is False
    t.deleteLater()


def _add(tab, measure_key):
    for i in range(tab._palette.count()):
        if tab._palette.itemData(i) == measure_key:
            tab._palette.setCurrentIndex(i)
            tab._btn_add.click()
            return
    raise AssertionError(f"{measure_key} is not in the palette")


# ---------------------------------------------------------------------------
# The layout sidecar
# ---------------------------------------------------------------------------

def test_a_moved_box_changes_the_layout_and_nothing_else(tab, library):
    """Dragging a box must never create a version or ask for a reason. The
    sidecar gets that by construction rather than by remembering to exclude a
    block from `canonical()`."""
    recipe = tab.current_recipe()
    before_hash, before_version = recipe.content_hash(), recipe.version

    tab._btn_edit.setChecked(True)
    tab._view._nodes["target"].setPos(64.0, 80.0)
    tab._persist_layout()

    assert recipe.content_hash() == before_hash
    assert recipe.version == before_version
    stored = json.loads(
        R.view_path(recipe, library).read_text(encoding="utf-8"))
    assert stored["recipe"] == recipe.id
    assert stored["nodes"]["target"] == [64.0, 80.0]


def test_clicking_a_box_without_moving_it_writes_nothing(tab, library):
    """A click is not a drop.

    Without this, selecting a box wrote a sidecar full of the AUTOMATIC
    positions — a file recording no decision, into a research library, for a
    recipe nobody had arranged. One appeared in the real `Shows` library during
    the session that built this and had to be removed by hand.
    """
    from PySide6.QtCore import QEvent

    recipe = tab.current_recipe()
    tab._btn_edit.setChecked(True)
    node = tab._view._nodes["measure:motion_mean"]

    node.mousePressEvent(_scene_click(QEvent.GraphicsSceneMousePress))
    node.mouseReleaseEvent(_scene_click(QEvent.GraphicsSceneMouseRelease))

    assert not R.view_path(recipe, library).exists()
    assert not (library / ".analysis" / "recipes").exists()

    # And a real move still does write one.
    node.setPos(848.0, 320.0)
    node.mouseReleaseEvent(_scene_click(QEvent.GraphicsSceneMouseRelease))
    assert R.view_path(recipe, library).exists()


def _scene_click(kind):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtWidgets import QGraphicsSceneMouseEvent

    event = QGraphicsSceneMouseEvent(kind)
    event.setButton(Qt.LeftButton)
    event.setPos(QPointF(1.0, 1.0))
    event.setScenePos(QPointF(1.0, 1.0))
    return event


def test_a_stored_layout_is_applied_on_redraw(tab, library):
    recipe = tab.current_recipe()
    R.save_view(recipe, {"measure:motion_mean": (900.0, 400.0)}, library)
    tab.refresh()
    assert tab._view._nodes["measure:motion_mean"].pos().x() == 900.0
    assert tab._view._nodes["measure:motion_mean"].pos().y() == 400.0


def test_a_layout_missing_a_node_keeps_that_node_automatic(tab, library):
    """An out-of-date layout must degrade to a partly-automatic diagram, not to
    a pile of boxes at the origin."""
    recipe = tab.current_recipe()
    auto = {k: (i.pos().x(), i.pos().y())
            for k, i in tab._view._nodes.items()}
    R.save_view(recipe, {"target": (500.0, 500.0)}, library)
    tab.refresh()
    assert (tab._view._nodes["target"].pos().x(),
            tab._view._nodes["target"].pos().y()) == (500.0, 500.0)
    for key, position in auto.items():
        if key == "target":
            continue
        item = tab._view._nodes[key]
        assert (item.pos().x(), item.pos().y()) == position


def test_a_corrupt_layout_falls_back_to_automatic(tab, library):
    recipe = tab.current_recipe()
    path = R.view_path(recipe, library)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json at all", encoding="utf-8")
    assert R.load_view(recipe, library) == {}
    tab.refresh()                              # must not raise
    assert tab._view._nodes


def test_the_wires_follow_a_box_that_moves(tab):
    """A wire is re-routed from where the boxes ARE, not from points captured
    when the diagram was first laid out."""
    tab._btn_edit.setChecked(True)
    edge = next(e for e in tab._view._edges
                if e.dst_view_key == "measure:motion_mean")
    before = edge.path().currentPosition()
    tab._view._nodes["measure:motion_mean"].setPos(880.0, 600.0)
    tab._view._route_all()
    after = edge.path().currentPosition()
    assert after != before
    assert after.x() == 880.0                  # arrives at the box's left edge


def test_a_sidecar_is_never_read_back_as_a_recipe(tab, library):
    """`Recipe.from_dict` is deliberately permissive, so a sidecar would not
    fail to parse — it would parse into a nameless recipe over no construct and
    appear in the list as a real one."""
    R.save_view(tab.current_recipe(), {"target": (1.0, 2.0)}, library)
    names = [r.name for r in R.list_recipes(library)]
    assert "Untitled recipe" not in names
    assert all(r.construct_key for r in R.list_recipes(library))


def test_the_geometry_is_imported_from_the_pipeline_canvas_not_retyped():
    """Both canvases draw the same reference stylesheet's node card. A second
    copy of those numbers would drift the first time the CSS is re-extracted."""
    import inspect

    from ui import constructs_tab, pipeline_view

    src = inspect.getsource(constructs_tab)
    assert "from ui.pipeline_view import" in src
    assert constructs_tab.NODE_RADIUS is pipeline_view.NODE_RADIUS
    assert constructs_tab.GRID is pipeline_view.GRID


def test_the_main_window_builds_the_tab_and_fans_the_scope_to_it():
    """A source-text test cannot tell a name that resolves from one that does
    not, so resolve it."""
    import ast
    import importlib
    import inspect

    from ui.main_window import MainWindow

    src = inspect.getsource(MainWindow._build_tabs)
    tree = ast.parse(src.strip())
    imported = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "ui.constructs_tab":
            module = importlib.import_module(node.module)
            for alias in node.names:
                assert hasattr(module, alias.name)
            imported = True
    assert imported, "the Constructs tab is no longer built"
    assert '"Constructs"' in src

    assert "_constructs.set_scope" in inspect.getsource(MainWindow.set_scope)
    assert "_constructs.refresh" in inspect.getsource(MainWindow.populate)


def test_adding_a_tab_did_not_leave_a_hard_coded_index_behind():
    """Inserting Constructs at position 1 renumbered every tab after it. The
    opening tab is chosen by widget for that reason."""
    import inspect

    from ui.main_window import MainWindow

    src = inspect.getsource(MainWindow._build_tabs)
    assert "setCurrentIndex" not in src
    assert "setCurrentWidget" in src
