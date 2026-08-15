"""
ui/inspector.py — the pipeline inspector, below the canvas.

Follows ui/reference/pipeline.css: a header carrying a bold title and a muted
subtitle over a hairline, an info banner, and a key/value grid whose keys are
right-aligned bold on a grey ground in a 140px column. The reference panel is
`overflow-y: auto`, so the grid scrolls — a sampling stage reports seven rows
and the panel is a fixed 240px.

The rows are whatever the selected object actually has. A selected node shows
its DERIVED state — the status, the headline figure, the per-stage details and
the next action `analyzer/pipeline.py` computes from what is on disk — not the
registry text describing what such a stage would be. When there is no derived
state the panel says why, and falls back to the registry description; it does
not show a plausible figure in place of one it does not have.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from analyzer.pipeline_graph import node_type
from ui.tokens import color

KEY_W = 140          # .inspector-table td.key width
PANEL_H = 240        # .inspector-panel height


class Inspector(QWidget):
    link_requested = Signal()
    open_requested = Signal()

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
        self._open = QPushButton()
        self._open.clicked.connect(self.open_requested)
        self._open.setVisible(False)
        hrow.addWidget(self._open)
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

        # The reference panel scrolls; a stage's details routinely exceed 240px.
        self._scroll = QScrollArea()
        self._scroll.setObjectName("inspectorScroll")
        self._scroll.setWidget(self._grid_host)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.viewport().setAutoFillBackground(False)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(self._scroll, 1)

        self._doc = None

    # -- rows -------------------------------------------------------------
    def _clear(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _rows(self, pairs) -> None:
        self._clear()
        pairs = list(pairs)
        for r, (key, val) in enumerate(pairs):
            k = QLabel(key)
            k.setProperty("kvKey", "true")
            k.setFixedWidth(KEY_W)
            # Some derived keys are longer than the reference's 140px column
            # ("Hand-coded episodes available"); wrapping keeps them readable
            # rather than clipped at the column edge.
            k.setWordWrap(True)
            k.setAlignment(Qt.AlignRight | Qt.AlignTop)
            v = QLabel(val)
            v.setProperty("kvVal", "true")
            v.setWordWrap(True)
            self._grid.addWidget(k, r, 0)
            self._grid.addWidget(v, r, 1)
        self._grid.setRowStretch(len(pairs), 1)
        self._grid.setColumnStretch(1, 1)

    def _set_open_target(self, target) -> None:
        """*target* is (label, reason) — one of the two is None.

        A stage whose screen is not in this front-end yet keeps its button,
        disabled and saying why: an unavailable control must not look like a
        broken one.
        """
        if target is None:
            self._open.setVisible(False)
            return
        label, reason = target
        self._open.setVisible(True)
        if label:
            self._open.setText(f"Open {label}")
            self._open.setEnabled(True)
            self._open.setToolTip(
                f"Go to the {label} tab, which does this stage's work. "
                "Double-clicking the node does the same.")
        else:
            self._open.setText("Open Stage")
            self._open.setEnabled(False)
            self._open.setToolTip(reason or "")

    # -- content ----------------------------------------------------------
    def show_doc(self, doc, source_label: str | None = None) -> None:
        """The pipeline itself, when no node is selected.

        *source_label* is the linked sample's readable name; its key is a
        folder path, which is not a thing to put in a subtitle.
        """
        self._doc = doc
        self._title.setText(doc.name)
        linked = doc.source_key
        self._subtitle.setText(
            f"(linked to {source_label or linked})" if linked
            else "(not linked to an episode sample)")
        self._action.setVisible(not linked)
        self._set_open_target(None)
        self._banner.setText(
            "Select a node to inspect it; double-click it to open the screen "
            "that does its work. Drag the canvas to pan, scroll to zoom.")
        rows = [
            ("Data source",
             (source_label or str(linked)) if linked
             else "none — nodes show no figures until linked to an "
                  "episode sample"),
            ("Stages", f"{len(doc.nodes)}"),
            ("Connections", f"{len(doc.connections)}"),
        ]
        self._rows(rows)

    def show_node(self, node, stage=None, reason: str = "",
                  target=None) -> None:
        """A selected node, with its derived stage state when there is one.

        *stage* is an `analyzer.pipeline.Stage`; *reason* says why there is
        none. *target* is the (label, reason) pair for the Open button.
        """
        if node is None:
            if self._doc is not None:
                self.show_doc(self._doc)
            return
        kind = node_type(node.type)
        self._title.setText(node.title)
        self._action.setVisible(False)
        self._set_open_target(target)

        if stage is None:
            self._subtitle.setText(f"({kind.name})")
            self._banner.setText(kind.description)
            rows = [
                ("Stage type", kind.name),
                ("What it is", kind.description),
                ("Current state",
                 reason or "not a stage with derived status"),
                ("Inputs", f"{kind.inputs}"),
                ("Outputs", f"{kind.outputs}"),
            ]
            self._rows(rows)
            return

        self._subtitle.setText(f"({kind.name} — {stage.status_label})")
        # The banner carries the one thing the researcher can act on; the
        # explanation of what the step is falls to a row when it does.
        self._banner.setText(stage.next_action or stage.explanation
                             or kind.description)
        rows = [("Status", stage.status_label)]
        if stage.headline:
            rows.append(("Summary", stage.headline))
        rows += [(k, v) for k, v in stage.details]
        if stage.next_action:
            rows.append(("Next step", stage.next_action))
        if stage.explanation:
            rows.append(("What it is", stage.explanation))
        self._rows(rows)
