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
    link_requested = Signal()          # the DOCUMENT's default sample
    link_node_requested = Signal()     # the SELECTED Sampling node's own sample
    open_requested = Signal()
    exclude_requested = Signal()
    find_clips_requested = Signal()

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
        # WHICH signal this fires is decided when the button is shown
        # (show_doc vs. show_node), not re-derived from canvas selection
        # state at click-time — the two used to share one handler that
        # inferred "document link" vs. "node link" from whatever happened to
        # be selected on the canvas, which was wrong whenever that state was
        # stale (see LEARNINGS.md).
        self._action_targets_node = False
        self._action.clicked.connect(self._emit_link)
        hrow.addWidget(self._action)
        # Only a Selection node on a linked pipeline shows this — see
        # show_node's can_exclude argument.
        self._exclude_action = QPushButton("Exclude Library Selection")
        self._exclude_action.setToolTip(
            "Remove the rows currently selected in the Library from this "
            "node's sample. Writes a new sample folder, the same as an "
            "Episode Sampler draw — it appears in Showing: and the Trials "
            "tab; the original sample is untouched.")
        self._exclude_action.clicked.connect(self.exclude_requested)
        self._exclude_action.setVisible(False)
        hrow.addWidget(self._exclude_action)
        # Selection at window scale. Shown on the same node as the exclude
        # action because they are the same stage asking the same question at
        # two grains: which episodes, and which thirty seconds of them.
        self._find_clips_action = QPushButton("Find Clips…")
        self._find_clips_action.setToolTip(
            "Measure every contiguous window of this node's episodes, then "
            "find the ones with the properties a stimulus needs. Measures "
            "nothing about suitability — only the features the engine "
            "already reports.")
        self._find_clips_action.clicked.connect(self.find_clips_requested)
        self._find_clips_action.setVisible(False)
        hrow.addWidget(self._find_clips_action)
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

    def _emit_link(self) -> None:
        (self.link_node_requested if self._action_targets_node
         else self.link_requested).emit()

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
    def show_doc(self, doc, source_label: str | None = None,
                 unresolved: str = "") -> None:
        """The pipeline itself, when no node is selected.

        *source_label* names what the pipeline ACTUALLY draws on, resolved by
        the caller through every Sampling node's own binding — NOT
        `doc.source_key`, which is only a fallback for nodes that have none.
        Reading the document's key here once reported a show contributing no
        episodes while every node on the canvas named a different one.

        *unresolved* is the document's key when it is set but matches no known
        sample or show. That is a third state and it gets said out loud:
        collapsing it into "not linked" would hide a stale key, and showing it
        as the data source would assert something that resolves to nothing.
        """
        self._doc = doc
        # Remembered so deselecting a node can restore this panel intact. It
        # used to call show_doc(doc) with no label, so clicking a node and
        # clicking away replaced the sample's name with its raw folder key.
        self._doc_source_label = source_label
        self._doc_source_unresolved = unresolved
        self._title.setText(doc.name)
        self._action_targets_node = False
        self._exclude_action.setVisible(False)
        self._find_clips_action.setVisible(False)
        self._set_open_target(None)
        self._banner.setText(
            "Select a node to inspect it; double-click it to open the screen "
            "that does its work. Drag the canvas to pan, scroll to zoom.")

        if source_label:
            self._subtitle.setText(f"(linked to {source_label})")
            self._action.setVisible(False)
            data_source = source_label
        elif unresolved:
            self._subtitle.setText(f"(linked to {unresolved}, which no "
                                   f"longer resolves)")
            self._action.setVisible(True)
            data_source = (
                f"{unresolved} — this key matches no drawn sample or show in "
                f"this library, and no Sampling node on the canvas carries a "
                f"binding of its own. Nothing is being drawn from.")
        else:
            self._subtitle.setText("(not linked to an episode sample)")
            self._action.setVisible(True)
            data_source = ("none — nodes show no figures until linked to an "
                           "episode sample")

        self._rows([
            ("Data source", data_source),
            ("Stages", f"{len(doc.nodes)}"),
            ("Connections", f"{len(doc.connections)}"),
        ])

    def show_node(self, node, stage=None, reason: str = "",
                  target=None, can_exclude: bool = False,
                  extra_rows=None, media: str = "",
                  can_find_clips: bool = False) -> None:
        """A selected node, with its derived stage state when there is one.

        *stage* is an `analyzer.pipeline.Stage`; *reason* says why there is
        none. *target* is the (label, reason) pair for the Open button.
        *can_exclude* is true only for a Selection node on a pipeline linked
        to a sample — the one case there is a sample to narrow.
        *can_find_clips* is true for a Selection node, whose stage covers
        choosing material at window scale as well as at episode scale. *extra_rows*
        is appended after everything else. *media* names the media this node
        works on; it leads the rows and joins the subtitle, because with two
        same-typed nodes on one canvas ("Sampling / Sampling") it is the only
        thing on this panel that says WHICH one is being inspected.
        """
        if node is None:
            if self._doc is not None:
                self.show_doc(self._doc,
                              getattr(self, "_doc_source_label", None),
                              getattr(self, "_doc_source_unresolved", ""))
            return
        kind = node_type(node.type)
        self._title.setText(node.title)
        is_sampling = node.type == "sampling"
        self._action_targets_node = is_sampling
        self._action.setVisible(is_sampling)
        if is_sampling:
            self._action.setText(
                "Change Linked Sample…" if node.config.get("sample_key")
                else "Link to Sample…")
        self._exclude_action.setVisible(can_exclude)
        self._find_clips_action.setVisible(can_find_clips)
        self._set_open_target(target)
        extra_rows = list(extra_rows or [])
        media_rows = [("Media", media)] if media else []

        if stage is None:
            self._subtitle.setText(
                f"({kind.name} — {media})" if media else f"({kind.name})")
            self._banner.setText(kind.description)
            rows = [
                ("Stage type", kind.name),
                ("What it is", kind.description),
                ("Current state",
                 reason or "not a stage with derived status"),
                ("Inputs", f"{kind.inputs}"),
                ("Outputs", f"{kind.outputs}"),
            ]
            self._rows(media_rows + rows + extra_rows)
            return

        self._subtitle.setText(
            f"({kind.name} — {media} — {stage.status_label})" if media
            else f"({kind.name} — {stage.status_label})")
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
        self._rows(media_rows + rows + extra_rows)
