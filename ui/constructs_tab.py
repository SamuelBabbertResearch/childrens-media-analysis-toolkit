"""
ui/constructs_tab.py — the Constructs tab: a construct, drawn.

The Pipeline canvas answers *"what are the stages of my study?"*. This one
answers the question beside it in `MEASUREMENT_MODEL.md` §2: **"how did I
operationalize what I wanted to study?"** Same research process, different
view — which is why it is a tab next to Pipeline rather than a screen inside
one.

WHAT IT DRAWS

A recipe, as the graph it already is. The shipped composite binds six measures
belonging to five different constructs, each with a weight; that is a diagram
stored as a form. Nothing here is a new data model — `analyzer/recipes.py` and
`analyzer/constructs.py` own everything this screen reads and writes.

    FFC ──────────── Pacing ─────── Hard cuts / min   ContentDetector @27
     (construct)  ─── Colour ─────── Saturation       HSV mean
                                 └── Contrast         HSV mean
                  ─── Motion ─────── Motion           Frame differencing
                  ─── Luminance ──── Flashing         Luminance delta  ⚠
                  ─── Loudness ───── Audio loudness   FFmpeg RMS

Three columns: the construct the recipe operationalizes, the constructs that
contribute to it, and the measures that stand in for those. The middle column
is DERIVED — a recipe stores bindings to measures and has no
construct-to-construct edge — so a construct block's weight is the sum of its
own measures' weights. That is a summary of stored facts, not a stored fact,
and nothing writes it back. A construct block appears only where it differs
from the recipe's own construct, so a single-construct recipe stays two
columns rather than growing a self-edge.

THREE RULES THE DRAWING FOLLOWS, each of which is a decision rather than a
style choice:

1. **No arrowheads.** An arrow between two boxes reads as causation to almost
   every reader, and `CLAUDE.md` §2.2 is absolute that nothing here is causal.
   Nothing flows along these connectors — a measure does not *produce* a
   construct, it stands in for one. So they are plain lines, and the legend
   says how to read them. This is also the artefact most likely to end up in a
   talk detached from its caption, which is exactly when an arrowhead would do
   its damage.

2. **Wire thickness is the CONTRIBUTION SHARE**, once contributions have been
   computed — not the declared weight, and not the redistributed weight
   either. Those three are different quantities and only the third answers the
   question a reader actually has:

   * *declared weight* — what the recipe says, e.g. motion 0.25;
   * *effective weight* — the declared weight after a missing measure's share
     is redistributed. Identical to the declared weight whenever nothing is
     missing, which is most of the time;
   * *contribution share* — how much of the finished score this measure
     actually accounts for, `weight × normalised value ÷ score`.

   `ARCHITECTURE.md` §8.1a can only state in prose that motion is nominally
   25% and contributes 7% while contrast is nominally 10% and contributes 24%,
   because motion reaches 8.6% of its ceiling and contrast 62%. That is the
   contribution share, and drawing it is the reason this canvas earns its
   place: a thin wire labelled 0.25 is the ceiling-compression problem, seen.

   Drawn from the DECLARED weight until contributions are computed, and the
   header always says which is on screen — a canvas showing declared thickness
   beside an effective score would be `LEARNINGS.md` shape 1, the display and
   the calculation disagreeing, in a new place.

3. **Refusals are drawn, not hidden.** A measure that did not resolve keeps its
   box and its wire goes dashed and grey with the reason beside it. A diagram
   that silently omits what it could not measure is how "1 of 6 measured; 5
   failed" got reported for a show where nothing had failed.

WHAT IT AUTHORS (added 2026-08-16, `TODO.md` item G2)

It drew and wrote nothing until this. **Edit** turns panning into box-dragging
and reveals a palette; four rules shape what that palette can do, and each is a
settled decision rather than a limit of the implementation (`DECISIONS.md`
§ *Authoring on the canvas*):

1. **The canvas stays TYPED.** A method attaches to a measure and a measure to
   a construct. There is no box-to-box wiring, which is the generic node editor
   `MEASUREMENT_MODEL.md` §6 forbids.
2. **Constructs may be free-form; MEASURES MAY NOT.** The palette offers
   shipped measures only. A user-defined measure with no data path is
   `LEARNINGS.md` shape 2 — the defect this whole phase exists to remove —
   arriving through a nicer interface. Writing a construct is
   `ui/construct_editor.py`, reached from the Constructs… button.
3. **Writes go through `recipes.save_recipe`,** and a changed operationalization
   goes through `bump_version` first, which requires a reason — so Save stays
   disabled until one is given, and says so. The shipped composite's bindings
   cannot be changed here at all, and the banner explains why and where to go.
4. **A composite may not contain another composite.** Nothing enforces this
   because nothing nestable is offered: the palette lists measures.

**A layout is not part of the operationalization**, and that is why dragging a
box never asks for a reason. Positions go to `<recipe id>.view.json` beside the
recipe (`recipes.save_view`), never into `content_hash()`, written on a drop —
not on a click — and deleted with the recipe. The locked composite can be
arranged and keep its arrangement, which is the case that decided the sidecar:
`save_recipe` refuses that recipe, so a layout stored inside the recipe file
could never be saved for the diagram most likely to become a methods figure.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetrics, QImage, QPainter, QPainterPath, QPen,
)
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QGraphicsItem,
    QGraphicsPathItem, QGraphicsScene, QGraphicsView, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QPushButton,
    QScrollArea, QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

from analyzer import constructs as C
from analyzer import recipes as R
from analyzer.show_index import list_episodes, list_shows, show_key
from ui.modal import ConfirmDialog
from ui.recipes import EvaluationWorker
from ui import theme
# Geometry is IMPORTED from the pipeline canvas rather than re-typed. Both
# canvases are the same reference stylesheet's node card, and a second copy of
# these numbers would drift the first time `ui/reference/pipeline.css` is
# re-extracted — `LEARNINGS.md` shape 3 applies to values as much as to claims.
from ui.pipeline_view import GRID, NODE_PAD, NODE_RADIUS, WIRE_W
from ui.tokens import color

TARGET_W = 200
CONSTRUCT_W = 170
MEASURE_W = 250
CARD_GAP = 10
LANE_GAP = 18
COL_GAP = 150

PANEL_W = 320

WIRE_MIN, WIRE_MAX = 1.0, 7.0


def _shrinkable(combo: QComboBox) -> None:
    """Let a combo be narrower than its longest item.

    A QComboBox sizes itself to its widest entry by default. "PySceneDetect —
    ContentDetector — validated" and "Pacing — All transitions per minute" are
    long enough that two of them forced the whole panel wider than the window,
    which is how the dropdown arrows, the Add button and Save came to be drawn
    off the right-hand edge. The popup still shows every item in full — the
    list is what has to be readable, not the closed control.
    """
    combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(10)
    combo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)


class CanvasNode(QGraphicsItem):
    """A box on the canvas that knows its own name in the layout sidecar.

    `view_key` is what a stored position is filed under — `"target"`,
    `"construct:<key>"`, `"measure:<key>"` — and it is recorded rather than
    derived from position or draw order, for the same reason `EdgeItem` records
    what it ends at: two boxes routinely share a y coordinate, and a layout
    matched by geometry would swap them the first time one was moved.

    Dragging is off unless the tab is in Edit. That is not decoration: with
    dragging always on, the same gesture would mean *pan the canvas* over the
    background and *move a box* over a card, and an accidental drag on the
    locked composite would read as editing something that cannot be saved.
    Moving a box is nonetheless allowed on the locked composite, because a
    layout is not part of the operationalization — see `recipes.save_view`.
    """

    def __init__(self, view_key: str) -> None:
        super().__init__()
        self.view_key = view_key
        self.moved_cb = None                  # reroute the wires, live
        self.dropped_cb = None                # persist the layout, once
        self._press_pos = None                # where a drag started, if one did

    def set_movable(self, on: bool) -> None:
        self.setFlag(QGraphicsItem.ItemIsMovable, on)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, on)
        self.setCursor(Qt.SizeAllCursor if on else Qt.ArrowCursor)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            # Snapped to the same grid the pipeline canvas uses, so two
            # diagrams from this application do not align differently.
            return QPointF(round(value.x() / GRID) * GRID,
                           round(value.y() / GRID) * GRID)
        if change == QGraphicsItem.ItemPositionHasChanged and self.moved_cb:
            self.moved_cb()
        return super().itemChange(change, value)

    def mousePressEvent(self, event) -> None:
        self._press_pos = self.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        # Written on the drop rather than on leaving Edit: a layout a
        # researcher arranged for a figure should not depend on remembering to
        # leave a mode before closing the window. One write per drag.
        #
        # A CLICK IS NOT A DROP. Without the comparison, merely selecting a box
        # wrote a sidecar full of the automatic positions — a file that records
        # no decision, into a research library, for a recipe nobody had
        # arranged. One appeared in the real `Shows` library during this
        # session and had to be removed by hand.
        if self.dropped_cb and self.pos() != getattr(self, "_press_pos",
                                                     self.pos()):
            self.dropped_cb()


class TargetItem(CanvasNode):
    """The construct the recipe operationalizes."""

    def __init__(self, construct, recipe: R.Recipe) -> None:
        super().__init__("target")
        self._construct = construct
        self._recipe = recipe
        self._lines = _wrap(
            construct.definition if construct else "",
            theme.font("small"), TARGET_W - NODE_PAD * 2)

    def _height(self) -> float:
        return NODE_PAD * 2 + 16 + 6 + len(self._lines) * 13 + 16

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, TARGET_W, self._height())

    def paint(self, p: QPainter, option, widget=None) -> None:
        p.setRenderHint(QPainter.Antialiasing)
        body = QRectF(0, 0, TARGET_W, self._height())
        p.setBrush(QBrush(QColor(color("node_bg"))))
        p.setPen(QPen(QColor(color("accent")), 2))
        p.drawRoundedRect(body, NODE_RADIUS, NODE_RADIUS)

        x, y = NODE_PAD, NODE_PAD
        p.setFont(theme.font("body", bold=True))
        p.setPen(QColor("#111111"))
        name = self._construct.name if self._construct else self._recipe.construct_key
        p.drawText(QRectF(x, y, TARGET_W - NODE_PAD * 2, 16),
                   Qt.AlignVCenter | Qt.AlignLeft, name)
        y += 16 + 4
        p.setPen(QPen(QColor(color("node_rule")), 1))
        p.drawLine(QPointF(x, y), QPointF(TARGET_W - NODE_PAD, y))
        y += 2

        p.setFont(theme.font("small"))
        p.setPen(QColor(color("text_dim")))
        for line in self._lines:
            p.drawText(QRectF(x, y, TARGET_W - NODE_PAD * 2, 13),
                       Qt.AlignVCenter | Qt.AlignLeft, line)
            y += 13

        # The word "construct" on the box itself: this is the one node on the
        # canvas that is NOT observable, and that is the whole point of it.
        f = theme.font("tiny")
        f.setItalic(True)
        p.setFont(f)
        p.setPen(QColor(color("node_status")))
        p.drawText(QRectF(x, y, TARGET_W - NODE_PAD * 2, 14),
                   Qt.AlignVCenter | Qt.AlignLeft,
                   "construct — not observable, not in the file")


class MeasureItem(CanvasNode):
    """One binding: a measure, the method producing it, and its settings."""

    def __init__(self, binding: R.MeasureBinding, part=None) -> None:
        super().__init__(f"measure:{binding.measure_key}")
        self.binding = binding
        self.part = part                      # recipes.EvaluatedPart | None
        self._measure = C.get_measure(binding.measure_key)
        self._method = C.get_method(binding.measure_key, binding.method_key)
        self._body = self._compose()

    # -- content ----------------------------------------------------------
    def _compose(self) -> list[tuple[str, str]]:
        """[(kind, text)] — kind drives the colour, so nothing is styled by
        position and a missing line cannot shift another line's meaning."""
        out: list[tuple[str, str]] = []
        method_label = self._method.label if self._method else \
            f"{self.binding.method_key} — not available here"
        out.append(("method", method_label))

        if self._method is not None and self._method.kind == C.HAND_CODED:
            out.append(("status", "human-coded"))
        elif self._method is not None and self._method.status == "deterministic":
            out.append(("status", "deterministic — no detection step to grade"))
        elif self._method is not None and self._method.status != "validated":
            out.append(("flag", f"{self._method.status} — not graded"))

        if self.binding.parameters:
            out.append(("param", ", ".join(
                f"{k} = {v}" for k, v in sorted(self.binding.parameters.items()))))
        else:
            out.append(("param", "no tunable parameters"))

        if self.binding.transform == R.TRANSFORM_MINMAX:
            out.append(("param", f"scaled over "
                                 f"{self.binding.range_min:g}–{self.binding.range_max:g}"))

        if self.part is not None:
            if self.part.ok:
                out.append(("value", f"{self.part.raw:g} {self._unit()}"))
                share = getattr(self.part, "share", None)
                if share is not None:
                    # The line the whole canvas exists for. Declared and
                    # contributed side by side, because either alone misleads:
                    # the weight overstates a compressed measure and the share
                    # says nothing about what was intended.
                    out.append(("share",
                                f"declared {self.binding.weight:g}  →  "
                                f"{share * 100:.1f}% of the score"))
                effective = getattr(self.part, "effective_weight", None)
                if effective and abs(effective - self.binding.weight) > 1e-9:
                    out.append(("flag",
                                f"weight redistributed to {effective:.4g} — "
                                f"another measure was missing"))
            else:
                out.append(("refusal", _refusal_line(self.part)))
        return out

    def _unit(self) -> str:
        return self._measure.unit if self._measure else ""

    def _height(self) -> float:
        return NODE_PAD * 2 + 16 + 4 + len(self._body) * 13

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, MEASURE_W, self._height())

    def refused(self) -> bool:
        return self.part is not None and not self.part.ok

    def paint(self, p: QPainter, option, widget=None) -> None:
        p.setRenderHint(QPainter.Antialiasing)
        body = QRectF(0, 0, MEASURE_W, self._height())
        refused = self.refused()
        p.setBrush(QBrush(QColor(color("node_bg"))))
        pen = QPen(QColor(color("node_status") if refused
                          else color("control_border")), 1)
        if refused:
            pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.drawRoundedRect(body, NODE_RADIUS, NODE_RADIUS)

        x, y = NODE_PAD, NODE_PAD
        p.setFont(theme.font("body", bold=True))
        p.setPen(QColor(color("node_status") if refused else "#111111"))
        title = self._measure.name if self._measure else self.binding.measure_key
        unit = f"  ({self._unit()})" if self._unit() else ""
        p.drawText(QRectF(x, y, MEASURE_W - NODE_PAD * 2, 16),
                   Qt.AlignVCenter | Qt.AlignLeft, title + unit)
        y += 16 + 4

        for kind, text in self._body:
            if kind == "method":
                p.setFont(theme.font("small"))
                p.setPen(QColor("#111111" if not refused
                                else color("node_status")))
            elif kind == "flag":
                f = theme.font("tiny")
                f.setItalic(True)
                p.setFont(f)
                p.setPen(QColor(color("warn_rule")))
            elif kind == "value":
                p.setFont(theme.font("small", bold=True))
                p.setPen(QColor(color("accent_dark")))
            elif kind == "share":
                p.setFont(theme.font("small", bold=True))
                p.setPen(QColor(color("aqua_bottom")))
            elif kind == "refusal":
                f = theme.font("tiny")
                f.setItalic(True)
                p.setFont(f)
                p.setPen(QColor(color("node_status")))
            else:
                p.setFont(theme.font("tiny"))
                p.setPen(QColor(color("text_dim")))
            p.drawText(QRectF(x, y, MEASURE_W - NODE_PAD * 2, 13),
                       Qt.AlignVCenter | Qt.AlignLeft, text)
            y += 13


class ConstructItem(CanvasNode):
    """A construct that CONTRIBUTES to the recipe's target, as its own block.

    Its weight is the SUM of its measures' weights, and that sum is a real
    quantity rather than an invented one: contributions to a composite are all
    fractions of the same score, so adding colour saturation's to colour
    contrast's says exactly what colour contributed. It is not averaging
    across methods, which the model refuses — these are different measures,
    each by its own single method, summed the way the composite itself sums
    them.
    """

    def __init__(self, construct, key: str, n_measures: int) -> None:
        super().__init__(f"construct:{key}")
        self.construct = construct
        self.key = key
        self._n = n_measures

    def caption(self) -> str:
        """"IN THIS RECIPE" is load-bearing, and it is one expression.

        This counts how many of the construct's measures THIS RECIPE binds,
        which is usually fewer than the construct has: pacing defines eight
        measures and the shipped composite binds one of them. The Constructs
        picker counts the other quantity — the catalogue — and until each said
        which it was, the two screens read as a contradiction and were reported
        as one from the real application.

        A method rather than an expression inside `paint` so that a test can
        read the caption the screen actually draws instead of restating it,
        which is `LEARNINGS.md` shape 3 in miniature.
        """
        return (f"construct · {self._n} measure"
                f"{'' if self._n == 1 else 's'} in this recipe")

    def _height(self) -> float:
        return NODE_PAD * 2 + 16 + 14

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, CONSTRUCT_W, self._height())

    def paint(self, p: QPainter, option, widget=None) -> None:
        p.setRenderHint(QPainter.Antialiasing)
        body = QRectF(0, 0, CONSTRUCT_W, self._height())
        p.setBrush(QBrush(QColor(color("node_bg"))))
        p.setPen(QPen(QColor(color("aqua_bottom")), 1))
        p.drawRoundedRect(body, NODE_RADIUS, NODE_RADIUS)

        x, y = NODE_PAD, NODE_PAD
        p.setFont(theme.font("body", bold=True))
        p.setPen(QColor("#111111"))
        p.drawText(QRectF(x, y, CONSTRUCT_W - NODE_PAD * 2, 16),
                   Qt.AlignVCenter | Qt.AlignLeft,
                   self.construct.name if self.construct else self.key)
        y += 16
        f = theme.font("tiny")
        f.setItalic(True)
        p.setFont(f)
        p.setPen(QColor(color("node_status")))
        p.drawText(QRectF(x, y, CONSTRUCT_W - NODE_PAD * 2, 14),
                   Qt.AlignVCenter | Qt.AlignLeft,
                   self.caption())


class EdgeItem(QGraphicsPathItem):
    """A connector, thickness carrying the weight. No arrowhead, ever."""

    def __init__(self, weight_frac: float, refused: bool,
                 dst_key: str = "", kind: str = "",
                 src_view_key: str = "", dst_view_key: str = "") -> None:
        super().__init__()
        # What this edge ends at, recorded rather than inferred from geometry:
        # a construct block centred on a one-measure group sits at the same y
        # as that measure's card, so matching by position is ambiguous exactly
        # where it matters. The view keys are the same fact for the two nodes
        # this edge joins, and they are what lets a moved box be re-wired
        # without re-deriving the whole diagram.
        self.dst_key = dst_key
        self.kind = kind                      # "construct" | "measure"
        self.src_view_key = src_view_key
        self.dst_view_key = dst_view_key
        self.label = None                     # the QGraphicsTextItem beside it
        width = WIRE_MIN + (WIRE_MAX - WIRE_MIN) * max(0.0, min(1.0, weight_frac))
        pen = QPen(QColor(color("node_status") if refused else color("wire")),
                   width if not refused else WIRE_W)
        if refused:
            pen.setStyle(Qt.DashLine)
        pen.setCapStyle(Qt.RoundCap)
        self.setPen(pen)
        self.setZValue(-1)

    def route(self, a: QPointF, b: QPointF) -> None:
        dx = max(40.0, abs(b.x() - a.x()) * 0.5)
        path = QPainterPath(a)
        path.cubicTo(a.x() + dx, a.y(), b.x() - dx, b.y(), b.x(), b.y())
        self.setPath(path)


class DiagramView(QGraphicsView):
    """The canvas. Pan by dragging, zoom by scrolling; nothing is editable."""

    ZOOM_MIN, ZOOM_MAX = 0.3, 2.5

    layout_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._scene = QGraphicsScene()
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setFrameShape(QGraphicsView.NoFrame)
        self._zoom = 1.0
        self._editable = False
        self._nodes: dict[str, CanvasNode] = {}
        self._edges: list[EdgeItem] = []

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        painter.fillRect(rect, QColor(color("canvas_bg")))
        painter.setPen(QPen(QColor(color("canvas_grid")), 1))
        left = int(rect.left()) - (int(rect.left()) % GRID)
        top = int(rect.top()) - (int(rect.top()) % GRID)
        x = left
        while x < rect.right():
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            x += GRID
        y = top
        while y < rect.bottom():
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            y += GRID

    def wheelEvent(self, event) -> None:
        step = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        target = max(self.ZOOM_MIN, min(self.ZOOM_MAX, self._zoom * step))
        if target != self._zoom:
            self.scale(target / self._zoom, target / self._zoom)
            self._zoom = target

    # -- building ---------------------------------------------------------
    def build(self, recipe: R.Recipe, parts: dict | None,
              shares: dict | None, layout: dict | None = None) -> None:
        """Lay the recipe out in three columns: target ← construct ← measure.

        *layout* is the stored sidecar, `{view_key: (x, y)}`, applied OVER the
        automatic arrangement rather than instead of it: a key the sidecar does
        not carry — a measure added since the layout was saved — keeps its
        computed slot, so an out-of-date layout degrades to a partly-automatic
        diagram rather than to a pile of boxes at the origin.

        *parts* and *shares* are keyed by measure key and are None until
        contributions have been computed. *shares* is the fraction of the
        finished score each measure accounted for — NOT its declared weight,
        which is what the boxes carry.

        THE CONSTRUCT COLUMN IS DERIVED, and it is worth being explicit about
        what that does and does not claim. A recipe stores bindings to
        MEASURES; it has no construct-to-construct edge. The `FFC ←
        Colour` edge here is assembled from the fact that colour saturation and
        colour contrast both belong to Colour, and its weight is their sum.
        That sum is a real quantity — contributions to a composite are all
        fractions of one score — but it is a summary of stored facts rather
        than a stored fact, and nothing writes it back.

        A construct block is inserted only where it DIFFERS from the recipe's
        own construct. A single-construct recipe (`Pacing — conservative`)
        would otherwise get a Pacing block hanging off a Pacing target, which
        is a self-edge dressed up as structure.
        """
        self._scene.clear()
        self._nodes = {}
        self._edges = []
        if recipe is None:
            return

        construct = C.get_construct(recipe.construct_key)
        target = TargetItem(construct, recipe)

        groups: dict[str, list[R.MeasureBinding]] = {}
        for binding in recipe.bindings:
            measure = C.get_measure(binding.measure_key)
            key = measure.construct_key if measure else "?"
            groups.setdefault(key, []).append(binding)

        weights = shares or {b.measure_key: b.weight for b in recipe.bindings}
        top_weight = max([abs(w) for w in weights.values()] or [0.0]) or 1.0

        measure_x = TARGET_W + COL_GAP + CONSTRUCT_W + COL_GAP
        y = 0.0
        placed: list[tuple[str, ConstructItem | None,
                          list[tuple[MeasureItem, float]]]] = []

        for construct_key, bindings in groups.items():
            group_top = y
            in_group: list[tuple[MeasureItem, float]] = []
            for binding in bindings:
                item = MeasureItem(binding, (parts or {}).get(binding.measure_key))
                self._add_node(item, measure_x, y)
                in_group.append((item, weights.get(binding.measure_key,
                                                   binding.weight)))
                y += item.boundingRect().height() + CARD_GAP

            node = None
            if construct_key != recipe.construct_key:
                node = ConstructItem(C.get_construct(construct_key),
                                     construct_key, len(bindings))
                span = (y - CARD_GAP) - group_top
                self._add_node(
                    node, TARGET_W + COL_GAP,
                    group_top + (span - node.boundingRect().height()) / 2)

            placed.append((construct_key, node, in_group))
            y += LANE_GAP

        total_h = max(y - LANE_GAP - CARD_GAP, target.boundingRect().height())
        self._add_node(target, 0,
                       max(0.0, (total_h - target.boundingRect().height()) / 2))

        def _label(value: float) -> str:
            return (f"{value * 100:.0f}% of score" if shares
                    else f"{value:.4g}".rstrip("0").rstrip("."))

        for construct_key, node, in_group in placed:
            if node is None:
                # No construct block: the measures ARE this recipe's construct,
                # so they wire straight to it.
                for item, weight in in_group:
                    self._edge("target", item, weight / top_weight,
                               _label(weight), item.binding.measure_key,
                               "measure", item.refused())
                continue

            summed = sum(w for _i, w in in_group)
            all_refused = all(i.refused() for i, _w in in_group)
            self._edge("target", node, abs(summed) / top_weight,
                       _label(summed), construct_key, "construct", all_refused)

            for item, weight in in_group:
                self._edge(node.view_key, item, abs(weight) / top_weight,
                           _label(weight), item.binding.measure_key,
                           "measure", item.refused())

        # The stored arrangement goes on LAST, over the computed one, and the
        # wires are routed afterwards from wherever the boxes actually ended up
        # — which is also what makes a drag re-wire correctly, since it runs
        # exactly the same pass.
        for key, (x, y_pos) in (layout or {}).items():
            item = self._nodes.get(key)
            if item is not None:
                item.setPos(float(x), float(y_pos))

        self._route_all()
        self.set_editable(self._editable)
        self._reset_scene_rect()

    def _add_node(self, item: CanvasNode, x: float, y: float) -> CanvasNode:
        item.setPos(x, y)
        item.moved_cb = self._route_all
        item.dropped_cb = self._on_dropped
        self._nodes[item.view_key] = item
        self._scene.addItem(item)
        return item

    def _edge(self, src_view_key: str, item, frac: float, label: str,
              dst_key: str, kind: str, refused: bool) -> None:
        """Record an edge between two NODES. Geometry comes later.

        Endpoints are named rather than passed as points, because the same
        edge has to be re-routed every time a box moves and a point captured at
        build time would freeze the wire where the box used to be.
        """
        edge = EdgeItem(frac, refused, dst_key=dst_key, kind=kind,
                        src_view_key=src_view_key, dst_view_key=item.view_key)
        self._scene.addItem(edge)
        if label:
            edge.label = self._scene.addText(label, theme.font("tiny"))
            edge.label.setDefaultTextColor(QColor(color("text_dim")))
        self._edges.append(edge)

    def _route_all(self) -> None:
        """Re-draw every wire from where its two boxes currently are.

        One rule for every edge: leave the source's right edge, arrive at the
        target's left edge, both at mid-height. Uniform, so a box dragged
        anywhere stays wired the same way rather than by a rule that depends on
        which column it started in.
        """
        for edge in self._edges:
            src = self._nodes.get(edge.src_view_key)
            dst = self._nodes.get(edge.dst_view_key)
            if src is None or dst is None:                     # pragma: no cover
                continue
            a = QPointF(src.pos().x() + src.boundingRect().width(),
                        src.pos().y() + src.boundingRect().height() / 2)
            b = QPointF(dst.pos().x(),
                        dst.pos().y() + dst.boundingRect().height() / 2)
            edge.route(a, b)
            if edge.label is not None:
                edge.label.setPos((a.x() + b.x()) / 2 - 10,
                                  (a.y() + b.y()) / 2 - 16)

    def _reset_scene_rect(self) -> None:
        self._scene.setSceneRect(self._scene.itemsBoundingRect().adjusted(
            -40, -40, 40, 40))

    def _on_dropped(self) -> None:
        self._reset_scene_rect()
        self.layout_changed.emit()

    # -- editing ----------------------------------------------------------
    def set_editable(self, on: bool) -> None:
        """Boxes move, and the background stops panning under the same drag."""
        self._editable = bool(on)
        for item in self._nodes.values():
            item.set_movable(self._editable)
        self.setDragMode(QGraphicsView.NoDrag if self._editable
                         else QGraphicsView.ScrollHandDrag)

    def node_positions(self) -> dict[str, tuple[float, float]]:
        return {key: (item.pos().x(), item.pos().y())
                for key, item in self._nodes.items()}

    def fit(self) -> None:
        rect = self._scene.itemsBoundingRect()
        if rect.isEmpty():
            return
        self.fitInView(rect.adjusted(-20, -20, 20, 20), Qt.KeepAspectRatio)
        self._zoom = self.transform().m11()

    def to_image(self) -> QImage:
        """The diagram as a picture, for a methods-section figure.

        Rendered from the SCENE rather than grabbed from the widget, so the
        image is the whole diagram at full resolution rather than whatever
        happened to be scrolled into view.
        """
        rect = self._scene.itemsBoundingRect().adjusted(-20, -20, 20, 20)
        scale = 2.0
        image = QImage(int(rect.width() * scale), int(rect.height() * scale),
                       QImage.Format_ARGB32)
        image.fill(QColor(color("canvas_bg")))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        self._scene.render(painter, target=QRectF(image.rect()), source=rect)
        painter.end()
        return image


class ConstructsTab(QWidget):
    """A construct and how it was operationalized, drawn."""

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self._recipes: list[R.Recipe] = []
        self._parts: dict | None = None
        self._shares: dict | None = None
        self._worker: EvaluationWorker | None = None
        self._scope = None
        self._contrib_note = ""
        self._editing = False
        self._pristine: R.Recipe | None = None
        self._baseline_hash = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        from ui.main_window import SubToolBar
        bar = SubToolBar()
        bar.row.addWidget(QLabel("Showing:"))
        self._chooser = QComboBox()
        self._chooser.setMinimumWidth(240)
        self._chooser.currentIndexChanged.connect(self._recipe_changed)
        bar.row.addWidget(self._chooser)

        self._btn_contrib = QPushButton("Show contributions for the scope")
        self._btn_contrib.setToolTip(
            "Apply this recipe across the episodes currently in scope and "
            "redraw the wires from the EFFECTIVE weights — the ones that "
            "actually produced the scores — rather than the nominal ones.")
        self._btn_contrib.clicked.connect(self._compute_contributions)
        bar.row.addWidget(self._btn_contrib)

        self._btn_nominal = QPushButton("Back to nominal")
        self._btn_nominal.clicked.connect(self._clear_contributions)
        bar.row.addWidget(self._btn_nominal)

        self._btn_image = QPushButton("Save image…")
        self._btn_image.setToolTip("Write the diagram as a PNG figure.")
        self._btn_image.clicked.connect(self._save_image)
        bar.row.addWidget(self._btn_image)

        self._btn_edit = QPushButton("Edit")
        self._btn_edit.setCheckable(True)
        self._btn_edit.setToolTip(
            "Arrange the boxes, and add or remove the measures this recipe "
            "binds. Moving a box only stores a layout — it is never a new "
            "version and never asks for a reason. Changing what is bound is a "
            "change to the operationalization and does ask for one.")
        self._btn_edit.toggled.connect(self._toggle_edit)
        bar.row.addWidget(self._btn_edit)

        # Creating is a separate button from browsing, because "define a
        # construct" is the act this screen exists to make possible and burying
        # it one dialog deep made it look absent.
        self._btn_new_construct = QPushButton("New construct…")
        self._btn_new_construct.setToolTip(
            "Define a construct of your own — the theoretical thing you are "
            "studying. Measures stay shipped: a construct of yours is "
            "operationalized by binding them to it, here, in Edit.")
        self._btn_new_construct.clicked.connect(self._new_construct)
        bar.row.addWidget(self._btn_new_construct)

        self._btn_constructs = QPushButton("Constructs…")
        self._btn_constructs.setToolTip(
            "Every construct this library can operationalize, shipped and your "
            "own. Read a shipped one, edit or delete yours.")
        self._btn_constructs.clicked.connect(self._open_constructs)
        bar.row.addWidget(self._btn_constructs)

        # A recipe could be chosen here but not created, so authoring started
        # on this tab and immediately sent you to File → Recipes… — including
        # from the locked composite's own banner, which named Duplicate as the
        # route and offered no way to take it.
        self._btn_new_recipe = QPushButton("New recipe…")
        self._btn_new_recipe.setToolTip(
            "Start a recipe over a construct. It opens in Edit with that "
            "construct's own measures bound at weight zero — remove what you "
            "do not want, weight what you do, and the palette adds measures "
            "from any other construct. A construct with no measures of its "
            "own starts empty.")
        self._btn_new_recipe.clicked.connect(self._new_recipe)
        bar.row.addWidget(self._btn_new_recipe)

        self._btn_duplicate = QPushButton("Duplicate")
        self._btn_duplicate.setToolTip(
            "Copy this recipe into one you can change. This is the route out "
            "of the locked composite: the copy is unlocked and keeps its "
            "caveats.")
        self._btn_duplicate.clicked.connect(self._duplicate)
        bar.row.addWidget(self._btn_duplicate)

        bar.row.addStretch(1)
        lay.addWidget(bar)

        self._headline = QLabel("")
        self._headline.setWordWrap(True)
        self._headline.setContentsMargins(8, 4, 8, 4)
        lay.addWidget(self._headline)

        # A SPLITTER, not a fixed side panel. The panel was first given a
        # maximum width, which Qt honoured while its contents needed more than
        # that — so the combo boxes, the Add button and Save all rendered past
        # the panel's edge and off the window. A splitter lets the panel take
        # the width its controls actually need and lets the researcher give it
        # more, which is also the shape `ui/recipes.py` already uses.
        self._split = QSplitter(Qt.Horizontal)
        self._view = DiagramView()
        self._view.layout_changed.connect(self._persist_layout)
        self._split.addWidget(self._view)
        self._panel = self._build_edit_panel()
        self._panel.setVisible(False)
        self._split.addWidget(self._panel)
        self._split.setStretchFactor(0, 1)
        self._split.setStretchFactor(1, 0)
        self._split.setCollapsible(0, False)
        lay.addWidget(self._split, 1)

        self._legend = QLabel(
            "Lines mean “is operationalized by”, not “causes” — nothing flows "
            "along them, and they carry no arrowheads for that reason. Line "
            "thickness is the weight. A dashed grey box is a measure that did "
            "not resolve, with the reason on it.")
        self._legend.setWordWrap(True)
        self._legend.setProperty("role", "dim")
        self._legend.setContentsMargins(8, 4, 8, 6)
        lay.addWidget(self._legend)

    # -- the editing panel ------------------------------------------------
    def _build_edit_panel(self) -> QWidget:
        """The palette. It offers MEASURES, and nothing else.

        Three rules are visible in what this panel does and does not contain,
        and each is a settled decision rather than an omission:

        * **There is no "new measure" control.** Measures are not
          user-definable. One that does not resolve to a real number from real
          data is `LEARNINGS.md` shape 2 — the defect this whole phase exists
          to remove — and adding it through a nicer interface is still adding
          it. Constructs ARE free-form, and the Constructs… button is where
          they are written.
        * **There is no way to add a recipe as an input.** A composite may not
          contain another composite (`DECISIONS.md`, decision 4); the palette
          lists measures, so nesting is impossible by construction rather than
          by a check somebody has to remember.
        * **The canvas stays typed.** A measure attaches to its own construct
          and thereby to the composite; there is no box-to-box wiring, which is
          the generic node editor `MEASUREMENT_MODEL.md` §6 forbids.
        """
        from ui.main_window import Panel
        panel = Panel("Edit this recipe")
        panel.setMinimumWidth(PANEL_W)
        # Its contents live in a scroll area, so the panel's minimum height is
        # its title strip rather than the sum of everything in it — a recipe
        # with a dozen bindings must not force the window taller than the
        # screen.
        inner = QWidget()
        box = QVBoxLayout(inner)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(4)
        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        panel.body_layout.addWidget(scroll, 1)

        self._edit_banner = QLabel("")
        self._edit_banner.setWordWrap(True)
        self._edit_banner.setProperty("role", "dim")
        self._edit_banner.setContentsMargins(6, 4, 6, 4)
        box.addWidget(self._edit_banner)

        box.addWidget(self._dim_label("Measures bound to this recipe:"))
        self._bound = QListWidget()
        self._bound.setProperty("inPanel", "true")
        self._bound.currentRowChanged.connect(self._binding_selected)
        box.addWidget(self._bound, 1)

        form = QWidget()
        grid = QGridLayout(form)
        grid.setContentsMargins(6, 2, 6, 2)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(3)
        grid.addWidget(QLabel("Method:"), 0, 0)
        self._method = QComboBox()
        _shrinkable(self._method)
        self._method.currentIndexChanged.connect(self._method_changed)
        grid.addWidget(self._method, 0, 1)
        grid.addWidget(QLabel("Weight:"), 1, 0)
        self._weight = QDoubleSpinBox()
        self._weight.setDecimals(4)
        self._weight.setRange(0.0, 1e6)
        self._weight.setSingleStep(0.05)
        self._weight.setMinimumWidth(80)
        self._weight.valueChanged.connect(self._weight_changed)
        grid.addWidget(self._weight, 1, 1)
        grid.setColumnStretch(1, 1)
        box.addWidget(form)

        # The transform, stated rather than left off the panel. It decides
        # whether this measure enters the sum as a 0–1 fraction or as its raw
        # value in its own units, which changes the composite more than the
        # weight beside it does — and it is edited on File → Recipes…, so
        # showing it here is what stops it being a hidden parameter.
        self._scale_note = QLabel("")
        self._scale_note.setWordWrap(True)
        self._scale_note.setProperty("role", "dim")
        self._scale_note.setContentsMargins(6, 0, 6, 2)
        box.addWidget(self._scale_note)

        self._btn_remove = QPushButton("Remove this measure")
        self._btn_remove.clicked.connect(self._remove_binding)
        box.addWidget(self._btn_remove)

        self._detail_note = QLabel("")
        self._detail_note.setWordWrap(True)
        self._detail_note.setProperty("role", "dim")
        self._detail_note.setContentsMargins(6, 2, 6, 2)
        box.addWidget(self._detail_note)

        box.addWidget(self._dim_label("Add a measure:"))
        add_row = QHBoxLayout()
        add_row.setContentsMargins(6, 0, 6, 0)
        add_row.setSpacing(4)
        self._palette = QComboBox()
        _shrinkable(self._palette)
        add_row.addWidget(self._palette, 1)
        self._btn_add = QPushButton("Add")
        self._btn_add.clicked.connect(self._add_binding)
        add_row.addWidget(self._btn_add)
        box.addLayout(add_row)

        # Weights total and, more importantly, whether the parts being added
        # are on the same scale at all.
        self._totals = QLabel("")
        self._totals.setWordWrap(True)
        self._totals.setProperty("role", "dim")
        self._totals.setContentsMargins(6, 4, 6, 2)
        box.addWidget(self._totals)

        rule = QLabel(
            "Measures are shipped and cannot be defined here — one that does "
            "not resolve to a real number from a cached result or a coding "
            "sheet would be a label. Constructs are yours to write: New "
            "construct…. Transforms, reference ranges, pinned parameters and "
            "missing-data policy are on File → Recipes…, which shows every "
            "recipe down to the parameter.")
        rule.setWordWrap(True)
        rule.setProperty("role", "dim")
        rule.setContentsMargins(6, 4, 6, 4)
        box.addWidget(rule)

        self._reason_label = self._dim_label("Reason for this change:")
        box.addWidget(self._reason_label)
        self._reason = QLineEdit()
        self._reason.setPlaceholderText(
            "Why the operationalization changed — what changed is derived, "
            "why cannot be recovered later")
        self._reason.textEdited.connect(self._sync_edit_panel)
        box.addWidget(self._reason)

        self._edit_status = QLabel("")
        self._edit_status.setWordWrap(True)
        self._edit_status.setProperty("role", "dim")
        self._edit_status.setContentsMargins(6, 2, 6, 2)
        box.addWidget(self._edit_status)

        save_row = QHBoxLayout()
        save_row.setContentsMargins(6, 0, 6, 6)
        save_row.setSpacing(4)
        self._btn_discard = QPushButton("Discard")
        self._btn_discard.clicked.connect(self._discard)
        save_row.addWidget(self._btn_discard)
        self._btn_save = QPushButton("Save")
        self._btn_save.setProperty("primary", "true")
        self._btn_save.clicked.connect(self._save_recipe)
        save_row.addWidget(self._btn_save)
        box.addLayout(save_row)
        return panel

    @staticmethod
    def _dim_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "dim")
        label.setContentsMargins(6, 2, 6, 0)
        return label

    # -- entering and leaving Edit ----------------------------------------
    def _toggle_edit(self, on: bool) -> None:
        recipe = self.current_recipe()
        if on and recipe is None:
            self._btn_edit.setChecked(False)
            return
        if not on and self._is_dirty():
            confirm = ConfirmDialog(
                self, "Discard changes",
                "Leave Edit and discard the unsaved changes?",
                detail=("The recipe file on disk is untouched, and so is the "
                        "layout — box positions are saved as you move them "
                        "and are not part of what would be discarded."),
                confirm_text="Discard")
            if confirm.exec() != QDialog.Accepted:
                self._btn_edit.setChecked(True)      # stay where we were
                return
            self._restore_pristine()

        self._editing = on
        self._panel.setVisible(on)
        self._view.set_editable(on)
        if on:
            self._begin_edit()
        else:
            self._pristine = None
        self._redraw()

    def _begin_edit(self) -> None:
        recipe = self.current_recipe()
        if recipe is None:
            return
        # The baseline is the recipe AS IT WAS WHEN EDITING STARTED, kept as a
        # whole object rather than only as a hash: `bump_version` needs the
        # previous recipe to derive what changed, and a hash cannot say what.
        self._pristine = R.Recipe.from_dict(recipe.to_dict(),
                                            path=recipe.path)
        self._baseline_hash = recipe.content_hash()
        self._reason.setText("")
        self._refill_panel()

    def _restore_pristine(self) -> None:
        """Put the recipe back the way it was, in place in the list.

        Located BY ID rather than by the chooser's current index: this also
        runs when the chooser has already moved to another recipe, and an index
        would then restore the pristine copy of one recipe over the top of a
        different one.
        """
        if self._pristine is None:
            return
        for i, recipe in enumerate(self._recipes):
            if recipe.id == self._pristine.id:
                self._recipes[i] = R.Recipe.from_dict(
                    self._pristine.to_dict(), path=self._pristine.path)
                break
        self._pristine = None

    def _discard(self) -> None:
        self._restore_pristine()
        self._btn_edit.setChecked(False)

    def _is_dirty(self) -> bool:
        """Unsaved changes to the recipe the baseline was taken from.

        The identity check is not belt-and-braces: the chooser restores the
        pristine copy and then leaves Edit, by which time the current recipe is
        a DIFFERENT one — and comparing its hash against the previous recipe's
        baseline would report a change nobody made, and ask to discard it.
        """
        recipe = self.current_recipe()
        return (self._editing and recipe is not None
                and self._pristine is not None
                and recipe.id == self._pristine.id
                and recipe.content_hash() != self._baseline_hash)

    # -- the panel's contents ---------------------------------------------
    def _refill_panel(self, select_measure: str | None = None) -> None:
        """Rebuild the panel, KEEPING the selection on the same measure.

        The selection is carried by measure key rather than by row, and that is
        not tidiness. Every edit refills this list, and `QListWidget.clear()`
        drops the current row to -1 — so a row-based restore silently snapped
        back to the first binding after each edit. The list looked correct
        throughout, and the next weight typed went onto the wrong measure: two
        weights entered for two measures were both written onto the first one,
        which is what the recipe file said when it was read back. A wrong number
        that displays correctly is this project's own failure mode.
        """
        recipe = self.current_recipe()
        if recipe is None:
            return
        current = self._current_binding()
        keep = select_measure or (current.measure_key if current else None)

        self._bound.blockSignals(True)
        self._bound.clear()
        for binding in recipe.bindings:
            measure = C.get_measure(binding.measure_key)
            construct = C.get_construct(measure.construct_key) if measure else None
            self._bound.addItem(QListWidgetItem(
                f"{measure.name if measure else binding.measure_key}\n"
                f"   {construct.name if construct else '?'} · "
                f"weight {binding.weight:g}"))
        self._bound.blockSignals(False)
        keys = [b.measure_key for b in recipe.bindings]
        if keys:
            self._bound.setCurrentRow(keys.index(keep) if keep in keys else 0)

        # Grouped under a heading per construct, and the headings are not
        # selectable. Sixteen measures in one flat list is a list you read
        # rather than a list you choose from, and the construct a measure
        # belongs to is the thing that tells you whether you want it.
        bound = {b.measure_key for b in recipe.bindings}
        self._palette.blockSignals(True)
        self._palette.clear()
        model = self._palette.model()
        for construct in C.all_constructs():
            available = [m for m in C.measures_for(construct.key)
                         if m.key not in bound]
            if not available:
                continue
            self._palette.addItem(f"— {construct.name} —", None)
            item = model.item(self._palette.count() - 1)
            item.setEnabled(False)
            for measure in available:
                self._palette.addItem(f"    {measure.name}  ({measure.unit})",
                                      measure.key)
                self._palette.setItemData(
                    self._palette.count() - 1,
                    f"{measure.definition}\n\n{construct.name}",
                    Qt.ToolTipRole)
        first = next((i for i in range(self._palette.count())
                      if self._palette.itemData(i)), -1)
        if first >= 0:
            self._palette.setCurrentIndex(first)
        self._palette.blockSignals(False)
        self._binding_selected()
        self._sync_edit_panel()

    def _current_binding(self) -> R.MeasureBinding | None:
        recipe = self.current_recipe()
        row = self._bound.currentRow()
        if recipe is None or not (0 <= row < len(recipe.bindings)):
            return None
        return recipe.bindings[row]

    def _binding_selected(self, *_a) -> None:
        binding = self._current_binding()
        self._method.blockSignals(True)
        self._weight.blockSignals(True)
        self._method.clear()
        if binding is None:
            self._weight.setValue(0.0)
            self._detail_note.setText("")
        else:
            methods = C.methods_for(binding.measure_key)
            for method in methods:
                label = (f"{method.label}  —  human-coded"
                         if method.kind == C.HAND_CODED
                         else f"{method.label}  —  {method.status}")
                self._method.addItem(label, method.key)
            keys = [m.key for m in methods]
            if binding.method_key in keys:
                self._method.setCurrentIndex(keys.index(binding.method_key))
            self._weight.setValue(binding.weight)
            measure = C.get_measure(binding.measure_key)
            self._detail_note.setText(
                f"{measure.definition} ({measure.unit})" if measure else "")
            self._method.setToolTip(self._method.currentText())
        self._sync_scale_note()
        self._method.blockSignals(False)
        self._weight.blockSignals(False)
        self._sync_edit_panel()

    def _sync_scale_note(self) -> None:
        """Say how this measure's value enters the sum, in its own words."""
        binding = self._current_binding()
        if binding is None:
            self._scale_note.setText("")
            return
        measure = C.get_measure(binding.measure_key)
        unit = measure.unit if measure else ""
        if binding.transform == R.TRANSFORM_MINMAX:
            self._scale_note.setText(
                f"Enters the composite scaled over "
                f"{binding.range_min:g}–{binding.range_max:g} {unit}, "
                f"clamped to 0–1. Change the range on File → Recipes….")
        else:
            self._scale_note.setText(
                f"NO transform: the raw value in {unit} enters the composite "
                f"as it is. No reference range is configured for this measure, "
                f"and one has not been invented. Set a range on File → "
                f"Recipes… before weighting it against a measure in different "
                f"units.")

    def _method_changed(self) -> None:
        """Changing the method re-pins the parameters for the NEW method.

        The same rule `ui/recipes.py`'s BindingBox follows, and for the same
        reason: keeping the previous method's frozen values would pin numbers
        that never applied to this one — a threshold of 27 means something
        different to ContentDetector than to TransNetV2.
        """
        binding = self._current_binding()
        key = self._method.currentData()
        if binding is None or not key:
            return
        binding.method_key = key
        binding.parameters = R.pin_parameters(binding.measure_key, key,
                                              self._window._cfg)
        self._after_edit()

    def _weight_changed(self, value: float) -> None:
        binding = self._current_binding()
        if binding is None:
            return
        binding.weight = float(value)
        self._after_edit()

    def _add_binding(self) -> None:
        """Bind one shipped measure to this recipe.

        Built through `MeasureBinding` with parameters pinned from the live
        config, so a binding added here is the same object `new_recipe` would
        have produced — and the measure key comes from the palette's item data
        rather than from a typed string, which is what makes
        `LEARNINGS.md` § *`new_recipe` accepted a method key that does not
        exist* unreachable from this screen rather than merely unlikely.
        """
        recipe = self.current_recipe()
        measure_key = self._palette.currentData()
        if recipe is None or not measure_key:
            return
        methods = C.methods_for(measure_key)
        if not methods:
            # Nothing is invented: a measure with no method available here is
            # left unbound rather than bound to a placeholder.
            self._edit_status.setText(
                f"{measure_key} has no method available in this install, so "
                f"binding it would produce a measure that can never resolve.")
            return
        # `new_binding`, not a bare MeasureBinding: it applies the configured
        # reference range where one exists, because a default transform of
        # "none" feeds the raw value into a weighted sum and two measures in
        # different units then produce a composite dominated by whichever has
        # the larger numbers — with both weights on screen reading as equal.
        recipe.bindings.append(
            R.new_binding(measure_key, methods[0].key, self._window._cfg))
        self._after_edit(select_measure=measure_key)

    def _remove_binding(self) -> None:
        recipe = self.current_recipe()
        binding = self._current_binding()
        if recipe is None or binding is None:
            return
        recipe.bindings.remove(binding)
        self._refill_panel()
        self._after_edit()

    def _after_edit(self, select_measure: str | None = None) -> None:
        # Computed contributions describe the operationalization that produced
        # them. Changing a weight or a method makes them a different recipe's
        # numbers, and leaving them on the wires would be the exact defect
        # switching recipes already guards against.
        self._parts = None
        self._shares = None
        self._contrib_note = ""
        self._refill_panel(select_measure)
        self._redraw()

    def _sync_edit_panel(self, *_a) -> None:
        recipe = self.current_recipe()
        if recipe is None:
            return
        locked = recipe.locked
        has_binding = self._current_binding() is not None
        for widget in (self._method, self._weight, self._btn_add,
                       self._palette, self._btn_remove):
            widget.setEnabled(not locked)
        if not locked:
            self._method.setEnabled(has_binding)
            self._weight.setEnabled(has_binding)
            self._btn_remove.setEnabled(has_binding)
            self._btn_add.setEnabled(self._palette.count() > 0)

        self._sync_totals()
        if locked:
            self._edit_banner.setText(
                "LOCKED. This is the composite CMAT has always computed and "
                "the published index is built on it, so what it binds cannot "
                "be changed here — a different weighting is a different "
                "operationalization and should not be citable under this "
                "name. The boxes still move and the arrangement is still "
                "saved: a layout is not part of the operationalization. Use "
                "File → Recipes… to duplicate it and edit the copy.")
            self._btn_save.setEnabled(False)
            self._btn_discard.setEnabled(False)
            self._reason.setVisible(False)
            self._reason_label.setVisible(False)
            self._edit_status.setText("")
            return

        self._edit_banner.setText("")
        self._btn_discard.setEnabled(True)
        self._sync_totals()
        changed = recipe.content_hash() != self._baseline_hash
        self._reason.setVisible(changed)
        self._reason_label.setVisible(changed)
        if not changed:
            self._btn_save.setEnabled(True)
            self._edit_status.setText(
                "Nothing about the operationalization has changed. Box "
                "positions are saved as you move them and never need a "
                "reason.")
            return
        has_reason = bool(self._reason.text().strip())
        self._btn_save.setEnabled(has_reason)
        self._edit_status.setText(
            "The operationalization has changed, so saving records a new "
            "version. " + ("" if has_reason else
                           "Give a reason first: what changed is derived "
                           "automatically, why it changed cannot be "
                           "recovered later."))

    def _sync_totals(self) -> None:
        """The weights total, and whether the parts are on the same scale.

        Two things a researcher cannot see from the wires. `evaluate` refuses a
        recipe whose weights are all zero — it would otherwise report 0.0, a
        real number in the composite's own range, sitting beside genuine scores
        — so an unweighted recipe says so here rather than at the moment it
        refuses.
        """
        recipe = self.current_recipe()
        if recipe is None:
            self._totals.setText("")
            return
        total = recipe.total_weight()
        lines = [f"{len(recipe.bindings)} measure"
                 f"{'' if len(recipe.bindings) == 1 else 's'} bound; "
                 f"weights total {total:g}."]
        if not recipe.bindings:
            lines.append("Nothing is bound yet, so this recipe cannot score. "
                         "Add a measure below.")
        elif not total:
            lines.append("Every weight is zero, so this recipe will REFUSE to "
                         "score rather than report 0.0 — a real number in the "
                         "composite's range beside genuine ones.")
        mixed = R.mixed_scales(recipe)
        if mixed:
            names = ", ".join(
                (C.get_measure(k).name if C.get_measure(k) else k)
                for k in mixed)
            lines.append(
                f"NOT ON ONE SCALE: {names} enter{'s' if len(mixed) == 1 else ''} "
                f"the sum as raw values while others are scaled to 0–1. Adding "
                f"them is adding different quantities, and the weights then "
                f"describe none of it. Set reference ranges on File → "
                f"Recipes….")
        self._totals.setText("  ".join(lines))

    # -- writing ----------------------------------------------------------
    def _save_recipe(self) -> None:
        """The only write of a recipe on this screen, and it obeys the rule.

        A changed operationalization goes through `bump_version`, which
        requires a reason, before `save_recipe`. The screen does not get to
        skip that, which is why Save is disabled until the reason exists rather
        than the reason being asked for afterwards.
        """
        recipe = self.current_recipe()
        root = self._window._root
        if recipe is None or recipe.locked or root is None:
            return
        reason = self._reason.text().strip()
        if recipe.content_hash() != self._baseline_hash:
            if not reason:
                return
            R.bump_version(recipe, reason, previous=self._pristine)
        try:
            R.save_recipe(recipe, root)
        except PermissionError as exc:                        # pragma: no cover
            self._edit_status.setText(str(exc))
            return
        saved_id = recipe.id
        self._pristine = None
        self.refresh()
        for i, other in enumerate(self._recipes):
            if other.id == saved_id:
                self._chooser.setCurrentIndex(i)
                break
        if self._editing:
            self._begin_edit()
        self._window.statusBar().showMessage(
            f"Saved {recipe.citation()}", 8000)

    def _persist_layout(self) -> None:
        """Write the sidecar. Never a version, never a reason, never a hash.

        Reached only from a box being dropped. Allowed for the locked
        composite, which is the case `DECISIONS.md` decision 3 turned on: a
        layout stored inside the recipe file could not be saved at all for the
        one diagram most likely to become a methods figure.
        """
        recipe = self.current_recipe()
        root = self._window._root
        if recipe is None or root is None:
            return
        R.save_view(recipe, self._view.node_positions(), root)

    # -- constructs and recipes -------------------------------------------
    def _new_construct(self) -> None:
        """Define a construct, and offer the recipe over it in the same breath.

        Defining one and then having to find the recipe route separately is
        the gap that made this whole item necessary; the two acts belong
        together, and the second is offered rather than assumed.
        """
        from ui.construct_editor import ConstructEditor
        root = self._window._root
        if root is None:
            self._window.statusBar().showMessage(
                "Choose a root folder first — a construct is stored with the "
                "library it describes.", 8000)
            return
        editor = ConstructEditor(root, None, self)
        if editor.exec() != QDialog.Accepted or not editor.saved_key:
            return
        construct = C.get_construct(editor.saved_key)
        self.refresh()
        confirm = ConfirmDialog(
            self, "Operationalize it",
            f"Start a recipe over “{construct.name if construct else ''}”?",
            detail=("A construct on its own measures nothing. A recipe is "
                    "where measures are bound to it. Yours has no measures of "
                    "its own — measures are shipped — so it opens here in "
                    "Edit with nothing bound, and the palette is where they "
                    "come from. You can do this later instead."),
            confirm_text="Start a recipe")
        if confirm.exec() == QDialog.Accepted:
            self._create_recipe_over(editor.saved_key)

    def _new_recipe(self) -> None:
        """Pick a construct, then create an empty recipe over it."""
        root = self._window._root
        if root is None:
            self._window.statusBar().showMessage(
                "Choose a root folder first — recipes are stored with the "
                "library they describe.", 8000)
            return
        menu = QMenu(self)
        for construct in C.all_constructs():
            n = len(C.measures_for(construct.key))
            action = menu.addAction(
                f"{construct.name}  ({n} measure{'' if n == 1 else 's'} "
                f"available)")
            action.setToolTip(construct.definition)
            action.triggered.connect(
                lambda _c=False, k=construct.key: self._create_recipe_over(k))
        menu.exec(self._btn_new_recipe.mapToGlobal(
            self._btn_new_recipe.rect().bottomLeft()))

    def _create_recipe_over(self, construct_key: str) -> None:
        construct = C.get_construct(construct_key)
        recipe = R.new_recipe(
            R.unique_name([r.name for r in self._recipes],
                          construct.name if construct else construct_key),
            construct_key, self._window._cfg,
            reason="Created on the Constructs canvas")
        R.save_recipe(recipe, self._window._root)
        self._select_after_refresh(recipe.id)
        self._btn_edit.setChecked(True)

    def _duplicate(self) -> None:
        recipe = self.current_recipe()
        root = self._window._root
        if recipe is None or root is None:
            return
        copy = R.duplicate_recipe(
            recipe, R.unique_name([r.name for r in self._recipes],
                                  f"{recipe.name} copy"))
        R.save_recipe(copy, root)
        self._select_after_refresh(copy.id)
        self._window.statusBar().showMessage(
            f"“{copy.name}” is unlocked and can be edited.", 8000)

    def _select_after_refresh(self, recipe_id: str) -> None:
        self.refresh()
        for i, other in enumerate(self._recipes):
            if other.id == recipe_id:
                self._chooser.setCurrentIndex(i)
                return

    def _open_constructs(self) -> None:
        from ui.construct_editor import ConstructPicker
        picker = ConstructPicker(self._window._root, self)
        picker.exec()
        if picker.changed:
            # A construct's definition feeds the target box and every construct
            # block, and `save_construct` has already reloaded the active set —
            # so redrawing is what makes an edit visible rather than requiring
            # the library to be reopened.
            self.refresh()

    # -- plumbing ---------------------------------------------------------
    def set_scope(self, scope) -> None:
        self._scope = scope
        # A scope change invalidates computed contributions: they were means
        # over a different set of episodes, and leaving them on screen under a
        # new scope's name would describe the wrong corpus.
        self._clear_contributions()

    def refresh(self) -> None:
        root = self._window._root
        shipped = R.shipped_composite(self._window._cfg)
        saved = R.list_recipes(root) if root else []
        self._recipes = [shipped] + [r for r in saved if r.name != shipped.name]

        current = self._chooser.currentText()
        self._chooser.blockSignals(True)
        self._chooser.clear()
        for recipe in self._recipes:
            construct = C.get_construct(recipe.construct_key)
            self._chooser.addItem(
                f"{recipe.name}  ·  {construct.name if construct else recipe.construct_key}")
        index = self._chooser.findText(current)
        self._chooser.setCurrentIndex(max(0, index))
        self._chooser.blockSignals(False)
        self._redraw()

    def current_recipe(self) -> R.Recipe | None:
        i = self._chooser.currentIndex()
        return self._recipes[i] if 0 <= i < len(self._recipes) else None

    # -- drawing ----------------------------------------------------------
    def _recipe_changed(self) -> None:
        """Switching recipe drops any computed contributions.

        They are keyed by MEASURE, and two recipes routinely share a measure —
        so without this, selecting a hand-coding recipe for pacing showed the
        composite's ContentDetector mean of 15.3763 cuts/min on a card whose
        method line read "Hand coding". A number computed under one
        operationalization, displayed under another's name, is the defect this
        entire phase exists to make impossible.

        Switching also leaves Edit, discarding any unsaved change to the recipe
        being left behind. That is the same mistake in the editing direction:
        the panel would be describing one recipe while its baseline hash
        described another, so a later Save would compare against the wrong
        thing.
        """
        if self._editing:
            self._restore_pristine()
            self._btn_edit.setChecked(False)     # runs _toggle_edit(False)
        self._clear_contributions()

    def _redraw(self) -> None:
        recipe = self.current_recipe()
        layout = (R.load_view(recipe, self._window._root)
                  if recipe is not None else {})
        self._view.build(recipe, self._parts, self._shares, layout)
        # Fitting an arranged diagram would override the arrangement's scale on
        # every redraw; a stored layout is a decision about the picture, so it
        # is left where it was put.
        if not layout:
            self._view.fit()
        self._sync_headline()
        if self._editing:
            self._sync_edit_panel()
        self._btn_nominal.setEnabled(self._shares is not None)
        has_root = self._window._root is not None
        self._btn_contrib.setEnabled(
            recipe is not None and has_root
            and not (self._worker is not None and self._worker.isRunning()))

        # An unavailable control must not look like a broken one, so each one
        # that needs a library says which thing it is missing.
        for button in (self._btn_new_construct, self._btn_new_recipe,
                       self._btn_constructs):
            button.setEnabled(has_root)
        self._btn_duplicate.setEnabled(has_root and recipe is not None)
        if not has_root:
            no_root = ("Choose a root folder first — constructs and recipes "
                       "are stored with the library they describe.")
            for button in (self._btn_new_construct, self._btn_new_recipe,
                           self._btn_constructs, self._btn_duplicate):
                button.setToolTip(no_root)
        self._btn_edit.setEnabled(recipe is not None and has_root)

    def _sync_headline(self) -> None:
        recipe = self.current_recipe()
        if recipe is None:
            self._headline.setText("No recipe to draw.")
            return
        parts = [recipe.citation()]
        if self._shares is None:
            parts.append(
                "Wire thickness is the NOMINAL weight — what the recipe "
                "declares, not what the components contributed.")
        else:
            parts.append(self._contrib_note)
        divergences = R.divergences(recipe, self._window._cfg)
        if divergences:
            parts.append(
                f"{len(divergences)} pinned parameter"
                f"{'' if len(divergences) == 1 else 's'} differ from the "
                f"current Measurement settings — this recipe still describes "
                f"what it always described. File → Recipes… lists them.")
        self._headline.setText("   ".join(parts))

    # -- contributions ----------------------------------------------------
    def _episode_targets(self) -> list[tuple[str, Path]]:
        root = self._window._root
        if not root:
            return []
        out: list[tuple[str, Path]] = []
        for show_dir in list_shows(root):
            skey = show_key(root, show_dir)
            for episode in list_episodes(show_dir):
                if self._scope is None or self._scope.contains(episode):
                    out.append((skey, episode))
        return out

    def _compute_contributions(self) -> None:
        recipe = self.current_recipe()
        if recipe is None or self._window._root is None:
            return
        if self._worker is not None and self._worker.isRunning():
            return
        targets = self._episode_targets()
        if not targets:
            self._headline.setText("Nothing in the current scope to apply "
                                   "this recipe to.")
            return

        # The worker is IMPORTED from the Recipes dialog, not reimplemented.
        # Two copies of "apply a recipe across episodes" would drift, and this
        # project has already paid for that shape more than once.
        from ui.recipes import EvaluationWorker
        from analyzer.validation import get_validation_dir

        self._btn_contrib.setEnabled(False)
        self._headline.setText(f"Applying to {len(targets)} episodes…")
        self._worker = EvaluationWorker(recipe, self._window._root,
                                        self._window._cfg, targets,
                                        get_validation_dir())
        self._worker.finished_ok.connect(self._on_evaluated)
        self._worker.failed.connect(self._on_failed)
        # Never rebind or clear the worker inside a slot connected to its own
        # finished signal — that frees a live QThread from under itself and the
        # process dies with no traceback (`LEARNINGS.md`).
        self._worker.finished.connect(self._redraw)
        self._worker.start()

    def _on_failed(self, message: str) -> None:              # pragma: no cover
        self._headline.setText(f"Could not apply the recipe: {message}")

    def _on_evaluated(self, results: list) -> None:
        """Mean value, mean effective weight and CONTRIBUTION SHARE per
        measure, over the episodes that actually scored.

        The share is `mean contribution ÷ mean score` — a ratio of means, not
        a mean of ratios. Said out loud because the two differ and the choice
        matters: a mean of per-episode ratios lets a near-zero-scoring episode
        dominate, since every measure's share of a tiny score is volatile.
        The ratio of means answers "across this corpus, how much of the
        composite did this measure account for", which is the question
        `ARCHITECTURE.md` §8.1a asks.

        Averaging one measure's values across EPISODES is an ordinary
        aggregate. It is not averaging across methods — which the model
        refuses, and which once produced a published figure describing no
        detector that existed — because every episode here was measured by
        this recipe's single pinned method for that measure.
        """
        scored = [ev for _label, ev in results if ev.score is not None]
        counts: dict[str, int] = {}
        weight_sum: dict[str, float] = {}
        value_sum: dict[str, float] = {}
        contrib_sum: dict[str, float] = {}
        refusals: dict[str, tuple[str, int]] = {}

        for ev in scored:
            for part in ev.parts:
                if not part.ok:
                    continue
                key = part.binding.measure_key
                counts[key] = counts.get(key, 0) + 1
                weight_sum[key] = weight_sum.get(key, 0.0) + part.effective_weight
                value_sum[key] = value_sum.get(key, 0.0) + float(part.raw or 0.0)
                contrib_sum[key] = contrib_sum.get(key, 0.0) + part.contribution

        for _label, ev in results:
            for part in ev.parts:
                if part.ok:
                    continue
                key = part.binding.measure_key
                reason, n = refusals.get(key, (part.status, 0))
                refusals[key] = (reason, n + 1)

        n_scored = len(scored)
        mean_score = (sum(ev.score for ev in scored) / n_scored) if n_scored else 0.0

        recipe = self.current_recipe()
        self._shares = {}
        self._parts = {}
        for binding in (recipe.bindings if recipe else []):
            key = binding.measure_key
            n = counts.get(key, 0)
            mean_contrib = (contrib_sum[key] / n) if n else 0.0
            share = (mean_contrib / mean_score) if mean_score else 0.0
            self._shares[key] = share
            self._parts[key] = _MeanPart(
                binding=binding,
                ok=n > 0,
                raw=(value_sum[key] / n) if n else None,
                n=n,
                refusal=refusals.get(key),
                effective_weight=(weight_sum[key] / n) if n else 0.0,
                share=share if n else None,
            )

        total = len(results)
        self._contrib_note = (
            f"Wire thickness is the CONTRIBUTION SHARE — how much of the "
            f"finished score each measure actually accounted for, averaged "
            f"over the {n_scored} of {total} episode"
            f"{'' if total == 1 else 's'} in scope that scored. It is not the "
            f"declared weight, which each box also shows.")
        self._redraw()

    def _clear_contributions(self) -> None:
        self._parts = None
        self._shares = None
        self._contrib_note = ""
        self._redraw()

    # -- export -----------------------------------------------------------
    def _save_image(self) -> None:
        recipe = self.current_recipe()
        if recipe is None:
            return
        suggested = f"{recipe.name.replace(' ', '_')}_v{recipe.version}.png"
        path, _f = QFileDialog.getSaveFileName(
            self, "Save diagram", suggested, "PNG image (*.png)")
        if not path:
            return
        self._view.to_image().save(path)
        self._window.statusBar().showMessage(f"Diagram written to {path}", 8000)


class _MeanPart:
    """An EvaluatedPart-shaped summary over several episodes.

    Deliberately its own small type rather than a real `EvaluatedPart`: this
    holds MEANS over a set of episodes, and letting a mean masquerade as one
    episode's measurement is how two different quantities end up sharing a
    field name.
    """

    def __init__(self, binding, ok, raw, n, refusal,
                 effective_weight=0.0, share=None) -> None:
        self.binding = binding
        self.ok = ok
        self.raw = raw
        self.n = n
        self.refusal = refusal
        self.effective_weight = effective_weight
        self.share = share
        self.status = "measured" if ok else (refusal[0] if refusal else "not_run")
        self.detail = ""


def _refusal_line(part) -> str:
    n = getattr(part, "n", None)
    refusal = getattr(part, "refusal", None)
    if refusal is not None:
        reason, count = refusal
        return f"did not resolve for {count} episode" \
               f"{'' if count == 1 else 's'} — {reason.replace('_', ' ')}"
    return (part.status.replace("_", " ") if getattr(part, "status", "")
            else "did not resolve")


def _wrap(text: str, font: QFont, width: float) -> list[str]:
    if not text:
        return []
    fm = QFontMetrics(font)
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if fm.horizontalAdvance(trial) <= width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:4]
