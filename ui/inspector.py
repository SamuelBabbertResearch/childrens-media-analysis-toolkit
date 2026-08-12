"""
ui/inspector.py — the pipeline inspector, below the canvas.

Follows ui/reference/pipeline.css: a header carrying a bold title and a muted
subtitle over a hairline, an info banner, and a key/value grid whose keys are
right-aligned bold on a grey ground in a 140px column.

The rows are whatever the selected object actually has. A pipeline that is not
linked to an episode sample says so; it does not show a plausible figure in
place of one it does not have.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from analyzer.pipeline_graph import node_type
from ui.tokens import color

KEY_W = 140          # .inspector-table td.key width
PANEL_H = 240        # .inspector-panel height


class Inspector(QWidget):
    link_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(PANEL_H)
        self.setObjectName("inspectorPanel")
        # A bare QWidget ignores a stylesheet background without this.
        self.setAttribute(Qt.WA_StyledBackground, True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(8)

        head = QWidget()
        hrow = QHBoxLayout(head)
        hrow.setContentsMargins(0, 0, 0, 4)
        hrow.setSpacing(6)
        self._title = QLabel()
        self._title.setObjectName("inspectorTitle")
        self._subtitle = QLabel()
        self._subtitle.setObjectName("inspectorSubtitle")
        hrow.addWidget(self._title)
        hrow.addWidget(self._subtitle)
        hrow.addStretch(1)
        self._action = QPushButton("Link to Sample…")
        self._action.setProperty("primary", "true")
        self._action.clicked.connect(self.link_requested)
        hrow.addWidget(self._action)
        head.setStyleSheet(
            f"border-bottom:1px solid {color('rule_soft')};")
        outer.addWidget(head)

        self._banner = QLabel()
        self._banner.setObjectName("inspectorBanner")
        self._banner.setWordWrap(True)
        outer.addWidget(self._banner)

        self._grid_host = QFrame()
        self._grid_host.setObjectName("inspectorTable")
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(0)
        outer.addWidget(self._grid_host)
        outer.addStretch(1)

        self._doc = None

    # -- rows -------------------------------------------------------------
    def _clear(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _rows(self, pairs) -> None:
        self._clear()
        for r, (key, val) in enumerate(pairs):
            k = QLabel(key)
            k.setProperty("kvKey", "true")
            k.setFixedWidth(KEY_W)
            k.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            v = QLabel(val)
            v.setProperty("kvVal", "true")
            v.setWordWrap(True)
            self._grid.addWidget(k, r, 0)
            self._grid.addWidget(v, r, 1)
        self._grid.setColumnStretch(1, 1)

    # -- content ----------------------------------------------------------
    def show_doc(self, doc) -> None:
        """The pipeline itself, when no node is selected."""
        self._doc = doc
        self._title.setText(doc.name)
        linked = doc.source_key
        self._subtitle.setText(
            f"(linked to {linked})" if linked
            else "(not linked to an episode sample)")
        self._action.setVisible(not linked)
        self._banner.setText(
            "Select a node to inspect it. Drag the canvas to pan, scroll to "
            "zoom.")
        rows = [
            ("Data source",
             str(linked) if linked
             else "none — nodes show no figures until linked to an "
                  "episode sample"),
            ("Stages", f"{len(doc.nodes)}"),
            ("Connections", f"{len(doc.connections)}"),
        ]
        self._rows(rows)

    def show_node(self, node) -> None:
        if node is None:
            if self._doc is not None:
                self.show_doc(self._doc)
            return
        kind = node_type(node.type)
        self._title.setText(node.title)
        self._subtitle.setText(f"({kind.name})")
        self._action.setVisible(False)
        self._banner.setText(kind.description)
        rows = [
            ("Stage type", kind.name),
            ("Description", kind.description),
            ("Inputs", f"{kind.inputs}"),
            ("Outputs", f"{kind.outputs}"),
        ]
        if kind.stage_key:
            rows.append(("Derived status key", kind.stage_key))
        self._rows(rows)
