"""
ui/pipeline_view.py — the pipeline workbench: node canvas over an inspector.

Geometry and colour come from ui/reference/pipeline.css; the words and the data
come from analyzer/pipeline_graph.py. Nothing here invents a stage, a status,
or a figure — a node shows what the document and the derived pipeline status
actually say, and says "no data source" when a pipeline is not bound to one,
because that is the true state rather than a placeholder.

Qt Style Sheets cannot describe a node graph, so this is the one screen drawn
rather than styled: QGraphicsView with items that paint themselves. The values
below are still the reference's, read from the extracted CSS where they are
simple enough to be read mechanically and named as constants where they are
not.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush, QColor, QFont, QPainter, QPainterPath, QPen,
)
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect, QGraphicsItem, QGraphicsPathItem,
    QGraphicsScene, QGraphicsView, QLabel, QHBoxLayout, QVBoxLayout, QWidget,
)

from analyzer.pipeline_graph import PipelineDoc, node_type
from ui import theme
from ui.tokens import color

# --- reference geometry (ui/reference/pipeline.css) --------------------------
NODE_W = 210          # .node width
NODE_PAD = 8          # .node padding
NODE_RADIUS = 4       # .node border-radius
PORT_D = 8            # .port width/height
GRID = 16             # .canvas-container background-size
WIRE_W = 1.5          # .connector-svg path stroke-width
HEADER_RULE = 4       # .node-header padding-bottom
PILL_MARGIN_X = 12    # .zoom-toolbar right
PILL_MARGIN_Y = 10    # .zoom-toolbar bottom

# NodeType.icon names a KIND of stage; these are the reference's glyphs for
# each. Unknown kinds fall back to a neutral mark rather than a stray letter.
ICON_GLYPH = {
    "sampling":    "⁙",
    "selection":   "⤡",
    "measurement": "▤",
    "language":    "¶",
    "handcode":    "✎",
    "validation":  "✓",
    "results":     "▦",
    "note":        "•",
}


class NodeItem(QGraphicsItem):
    """One stage, drawn as the reference's node card."""

    def __init__(self, node, status_line: str) -> None:
        super().__init__()
        self.node = node
        self.status_line = status_line
        self._type = node_type(node.type)
        self._hover = False
        self.setFlags(
            QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setPos(node.x, node.y)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 56))   # rgba(0,0,0,.22)
        self.setGraphicsEffect(shadow)

    # -- geometry ---------------------------------------------------------
    def _height(self) -> float:
        fm_desc = theme.font("small")
        lines = self._wrapped(self._type.description, fm_desc)
        return (NODE_PAD * 2 + 16 + HEADER_RULE + 1
                + len(lines) * 14 + 14)

    def _wrapped(self, text: str, font: QFont) -> list[str]:
        from PySide6.QtGui import QFontMetrics
        fm = QFontMetrics(font)
        width = NODE_W - NODE_PAD * 2
        words, lines, cur = text.split(), [], ""
        for word in words:
            trial = f"{cur} {word}".strip()
            if fm.horizontalAdvance(trial) <= width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

    def boundingRect(self) -> QRectF:
        pad = PORT_D
        return QRectF(-pad, -2, NODE_W + pad * 2, self._height() + 4)

    def port_at(self, pos: QPointF) -> str | None:
        """"out", "in", or None for a point in ITEM coordinates."""
        mid = self._height() / 2
        r = PORT_D
        if self._type.outputs and                 (pos - QPointF(NODE_W + r / 2 + 1, mid)).manhattanLength() < r * 1.6:
            return "out"
        if self._type.inputs and                 (pos - QPointF(-r / 2 - 1, mid)).manhattanLength() < r * 1.6:
            return "in"
        return None

    def ports(self) -> tuple[QPointF, QPointF]:
        """Scene positions of the left and right ports."""
        mid = self._height() / 2
        return (self.mapToScene(QPointF(-PORT_D / 2 - 1, mid)),
                self.mapToScene(QPointF(NODE_W + PORT_D / 2 + 1, mid)))

    # -- painting ---------------------------------------------------------
    def paint(self, p: QPainter, option, widget=None) -> None:
        p.setRenderHint(QPainter.Antialiasing)
        h = self._height()
        body = QRectF(0, 0, NODE_W, h)

        selected = self.isSelected()
        edge = color("accent") if (selected or self._hover) \
            else color("control_border")
        p.setBrush(QBrush(QColor(color("node_bg"))))
        p.setPen(QPen(QColor(edge), 2 if selected else 1))
        p.drawRoundedRect(body, NODE_RADIUS, NODE_RADIUS)

        x = NODE_PAD
        y = NODE_PAD

        # Header: icon then bold title, over a hairline.
        p.setFont(theme.font("body", bold=True))
        p.setPen(QColor(color("aqua_bottom")))
        icon = ICON_GLYPH.get(self._type.icon, "•")
        p.drawText(QRectF(x, y, 14, 14), Qt.AlignCenter, icon)
        p.setPen(QColor("#111111"))
        p.drawText(QRectF(x + 18, y, NODE_W - x - 18 - NODE_PAD, 14),
                   Qt.AlignVCenter | Qt.AlignLeft, self.node.title)
        y += 14 + HEADER_RULE
        p.setPen(QPen(QColor(color("node_rule")), 1))
        p.drawLine(QPointF(x, y), QPointF(NODE_W - NODE_PAD, y))
        y += 3

        p.setFont(theme.font("small"))
        p.setPen(QColor(color("text_dim")))
        for line in self._wrapped(self._type.description, theme.font("small")):
            p.drawText(QRectF(x, y, NODE_W - NODE_PAD * 2, 14),
                       Qt.AlignVCenter | Qt.AlignLeft, line)
            y += 14

        status_font = theme.font("tiny")
        status_font.setItalic(True)
        p.setFont(status_font)
        p.setPen(QColor(color("node_status")))
        p.drawText(QRectF(x, y, NODE_W - NODE_PAD * 2, 14),
                   Qt.AlignVCenter | Qt.AlignLeft, self.status_line)

        # Ports, one per side the type actually has.
        p.setBrush(QBrush(QColor(color("port_fill"))))
        p.setPen(QPen(QColor(color("port_border")), 1))
        mid = h / 2
        r = PORT_D / 2
        if self._type.inputs:
            p.drawEllipse(QPointF(-r - 1, mid), r, r)
        if self._type.outputs:
            p.drawEllipse(QPointF(NODE_W + r + 1, mid), r, r)

    # -- interaction ------------------------------------------------------
    def hoverEnterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def hoverLeaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            # Positions live in the document, not the view.
            self.node.x, self.node.y = self.pos().x(), self.pos().y()
            if self.scene():
                self.scene().node_moved.emit()
        return super().itemChange(change, value)


class WireItem(QGraphicsPathItem):
    """A connection, as the reference's bezier."""

    def __init__(self) -> None:
        super().__init__()
        self.setPen(QPen(QColor(color("wire")), WIRE_W))
        self.setZValue(-1)

    def route(self, a: QPointF, b: QPointF) -> None:
        # Horizontal control points, so the curve leaves and enters level —
        # the shape every path in the reference SVG has.
        dx = max(30.0, abs(b.x() - a.x()) * 0.5)
        path = QPainterPath(a)
        path.cubicTo(a.x() + dx, a.y(), b.x() - dx, b.y(), b.x(), b.y())
        self.setPath(path)


class Scene(QGraphicsScene):
    node_moved = Signal()


class Canvas(QGraphicsView):
    """The graph canvas: 16px grid, drag to pan, scroll to zoom."""

    selection_changed = Signal(object)
    connect_requested = Signal(str, str)     # src node id, dst node id
    doc_changed = Signal()

    ZOOM_MIN, ZOOM_MAX = 0.25, 2.5

    def __init__(self) -> None:
        super().__init__()
        self._scene = Scene()
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._doc: PipelineDoc | None = None
        self._items: dict[str, NodeItem] = {}
        self._wires: list[tuple[WireItem, str, str]] = []
        self._scene.selectionChanged.connect(self._emit_selection)
        self._scene.node_moved.connect(self._on_node_moved)
        self._linking: tuple[NodeItem, WireItem] | None = None

    # -- background -------------------------------------------------------
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

    # -- content ----------------------------------------------------------
    def load(self, doc: PipelineDoc, status_for) -> None:
        self._doc = doc
        self._scene.clear()
        self._items.clear()
        self._wires.clear()
        for node in doc.nodes:
            item = NodeItem(node, status_for(node))
            self._scene.addItem(item)
            self._items[node.id] = item
        for conn in doc.connections:
            if conn.src in self._items and conn.dst in self._items:
                wire = WireItem()
                self._scene.addItem(wire)
                self._wires.append((wire, conn.src, conn.dst))
        self._reroute()
        self.fit()

    def _reroute(self) -> None:
        for wire, src, dst in self._wires:
            a = self._items[src].ports()[1]
            b = self._items[dst].ports()[0]
            wire.route(a, b)

    def _on_node_moved(self) -> None:
        self._reroute()
        self.doc_changed.emit()

    def selected_node(self):
        items = [i for i in self._scene.selectedItems()
                 if isinstance(i, NodeItem)]
        return items[0].node if items else None

    def _node_item_at(self, view_pos):
        """The NodeItem under a view point, ignoring wires."""
        for item in self.items(view_pos):
            if isinstance(item, NodeItem):
                return item
        return None

    def _emit_selection(self) -> None:
        items = [i for i in self._scene.selectedItems()
                 if isinstance(i, NodeItem)]
        self.selection_changed.emit(items[0].node if items else None)

    # -- view -------------------------------------------------------------
    def fit(self) -> None:
        rect = self._scene.itemsBoundingRect()
        if rect.isEmpty():
            return
        self.fitInView(rect.adjusted(-24, -24, 24, 24), Qt.KeepAspectRatio)
        self._clamp()

    def zoom_by(self, factor: float) -> None:
        current = self.transform().m11()
        target = max(self.ZOOM_MIN, min(self.ZOOM_MAX, current * factor))
        if target != current:
            self.scale(target / current, target / current)

    def zoom_percent(self) -> int:
        return round(self.transform().m11() * 100)

    def _clamp(self) -> None:
        scale = self.transform().m11()
        if scale < self.ZOOM_MIN:
            self.scale(self.ZOOM_MIN / scale, self.ZOOM_MIN / scale)
        elif scale > self.ZOOM_MAX:
            self.scale(self.ZOOM_MAX / scale, self.ZOOM_MAX / scale)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place_overlays()

    def _place_overlays(self) -> None:
        for child in self.children():
            if isinstance(child, ZoomPill):
                size = child.sizeHint()
                child.resize(size)
                child.move(self.width() - size.width() - PILL_MARGIN_X,
                           self.height() - size.height() - PILL_MARGIN_Y)

    def wheelEvent(self, event) -> None:
        self.zoom_by(1.15 if event.angleDelta().y() > 0 else 1 / 1.15)
        event.accept()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            item = self._node_item_at(event.pos())
            if item is not None:
                local = item.mapFromScene(self.mapToScene(event.pos()))
                if item.port_at(local) == "out":
                    # Starting a wire, not moving the node.
                    ghost = WireItem()
                    ghost.setPen(QPen(QColor(color("accent")), WIRE_W,
                                      Qt.DashLine))
                    self._scene.addItem(ghost)
                    self._linking = (item, ghost)
                    event.accept()
                    return
            elif not self.itemAt(event.pos()):
                # Empty canvas drags the view; a node drags itself.
                self.setDragMode(QGraphicsView.ScrollHandDrag)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._linking is not None:
            src, ghost = self._linking
            ghost.route(src.ports()[1], self.mapToScene(event.pos()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._linking is not None:
            src, ghost = self._linking
            self._linking = None
            self._scene.removeItem(ghost)
            target = self._node_item_at(event.pos())
            if target is not None and target is not src:
                self.connect_requested.emit(src.node.id, target.node.id)
            event.accept()
            return
        super().mouseReleaseEvent(event)
        self.setDragMode(QGraphicsView.RubberBandDrag)


class ZoomPill(QWidget):
    """The reference's floating zoom control, bottom-right of the canvas."""

    def __init__(self, canvas: Canvas) -> None:
        super().__init__(canvas)
        self._canvas = canvas
        self.setObjectName("zoomPill")
        self.setAttribute(Qt.WA_StyledBackground, True)
        row = QHBoxLayout(self)
        row.setContentsMargins(2, 2, 2, 2)
        row.setSpacing(0)

        from PySide6.QtWidgets import QPushButton
        self._out = QPushButton("−")
        self._display = QLabel("100%")
        self._display.setObjectName("zoomDisplay")
        self._display.setAlignment(Qt.AlignCenter)
        self._in = QPushButton("+")
        self._fit = QPushButton("Fit")
        for b in (self._out, self._in, self._fit):
            b.setProperty("zoom", "true")
            b.setFlat(True)
        row.addWidget(self._out)
        row.addWidget(self._display)
        row.addWidget(self._in)
        row.addWidget(self._fit)

        canvas._place_overlays()

        self._out.clicked.connect(lambda: self.step(1 / 1.15))
        self._in.clicked.connect(lambda: self.step(1.15))
        self._fit.clicked.connect(self.fit)

    def step(self, factor: float) -> None:
        """Zoom by *factor* about the view centre, clamped to the range."""
        self._canvas.zoom_by(factor)
        self.refresh()

    def fit(self) -> None:
        self._canvas.fit()
        self.refresh()

    def refresh(self) -> None:
        self._display.setText(f"{self._canvas.zoom_percent()}%")
