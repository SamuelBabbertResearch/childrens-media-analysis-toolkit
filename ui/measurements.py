"""
ui/measurements.py — Measurement settings: which tool measures what.

**The other settings axis.** `ui/settings.py` edits SCORING — weights and
normalization ceilings applied to numbers already computed, so changing them
re-scores from cache instantly and invalidates nothing. This dialog edits
MEASUREMENT — which detector, what threshold, what sample rate — which changes
the raw numbers themselves and makes every episode measured under the old
settings **stale**.

Conflating the two would let someone change a detector threshold and see
scores that mix old detections with a new configuration label. Keeping them
apart is why Settings' "Apply & Re-score" can promise what it says. See
`ARCHITECTURE.md` §3.

Everything on screen is built from `analyzer.measurements.MEASUREMENTS` — the
registry is the source, so a measurement or a tool added to the engine appears
here without this file changing. Two things the registry carries that the
screen must not drop:

* **Validation status.** A tool that has never been graded against hand coding
  says so, next to its name, wherever it is chosen. That is `CLAUDE.md` §2.2,
  and it is the whole reason the status field exists.
* **Availability.** A tool needing an optional dependency that is not
  installed is offered but cannot be applied; the dialog says which one and
  where to get it, rather than failing at analysis time.

Applying tells the user exactly how many cached episodes it invalidates,
before the change happens. Nothing is deleted — stale results keep displaying,
because a number that was measured is still a number that was measured.
"""

from __future__ import annotations

import copy
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from analyzer.cache import cached_fingerprint, is_stale, load_cached
from analyzer.measurements import (
    DETERMINISTIC, MEASUREMENTS, STATUS_LABEL, VALIDATED, diff_fingerprints,
    normalize_config, selection,
)
from analyzer.show_index import list_episodes, list_shows, show_key
from ui.modal import ModalDialogFrame

DIALOG_W = 720
DIALOG_H = 620


def _status_text(tool) -> str:
    """A tool's name always travels with its validation status."""
    return f"{tool.name}  —  {STATUS_LABEL.get(tool.status, tool.status)}"


class MeasurementsDialog(QDialog):
    """Pick the tool and parameters for each measurement."""

    def __init__(self, config: dict, root: Path | None, parent=None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.resize(DIALOG_W, DIALOG_H)
        self.config = copy.deepcopy(config)
        self.stale_count = 0
        self.unknown_count = 0
        self._root = root
        self._tools: dict[str, QComboBox] = {}
        self._enabled: dict[str, QCheckBox] = {}
        self._params: dict[tuple[str, str], QWidget] = {}
        self._status: dict[str, QLabel] = {}
        self._holders: dict[str, QWidget] = {}
        # The boxes are built one measurement at a time, and each one wires up
        # signals that ask for a summary of ALL of them. Suppressed until the
        # form exists, or the first box summarises a half-built dialog.
        self._building = True

        body = ModalDialogFrame.install(self, "Measurement settings",
                                        buttons=("min", "max", "close"))

        warning = QLabel(
            "These change the RAW NUMBERS, not the score. Every episode "
            "already analysed under different settings becomes stale — its "
            "figures are not comparable with anything measured from now on. "
            "Weights and ceilings live in Scoring settings instead; those "
            "re-score from cache and invalidate nothing.")
        warning.setWordWrap(True)
        warning.setProperty("role", "dim")
        body.addWidget(warning)

        inner = QWidget()
        self._form = QVBoxLayout(inner)
        self._form.setContentsMargins(0, 0, 0, 0)
        self._form.setSpacing(8)
        for spec in MEASUREMENTS:
            self._form.addWidget(self._measurement_box(spec))
        self._form.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        body.addWidget(scroll, 1)

        row = ModalDialogFrame.add_action_bar(self)
        self._summary = QLabel("")
        self._summary.setProperty("role", "dim")
        self._summary.setWordWrap(True)
        row.addWidget(self._summary, 1)
        restore = QPushButton("Restore Defaults")
        restore.clicked.connect(self._restore_defaults)
        row.addWidget(restore)
        apply_button = QPushButton("Apply")
        apply_button.setProperty("primary", "true")
        apply_button.clicked.connect(self._apply)
        row.addWidget(apply_button)
        close = QPushButton("Cancel")
        close.clicked.connect(self.reject)
        row.addWidget(close)

        self._building = False
        self._refresh_summary()

    # -- building ---------------------------------------------------------
    def _measurement_box(self, spec) -> QWidget:
        box = QGroupBox(spec.name)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        description = QLabel(spec.description)
        description.setWordWrap(True)
        description.setProperty("role", "dim")
        lay.addWidget(description)

        current_tool, current_params, enabled = selection(self.config,
                                                          spec.key)
        head = QHBoxLayout()
        head.setSpacing(6)
        if spec.can_disable:
            check = QCheckBox("Measure this")
            check.setChecked(enabled)
            check.toggled.connect(
                lambda on, k=spec.key: self._set_enabled(k, on))
            self._enabled[spec.key] = check
            head.addWidget(check)
        head.addWidget(QLabel("Tool:"))
        combo = QComboBox()
        for tool in spec.tools:
            combo.addItem(_status_text(tool), tool.key)
            index = combo.count() - 1
            combo.setItemData(index, tool.summary, Qt.ToolTipRole)
            if not tool.is_available():
                combo.setItemData(
                    index,
                    f"{tool.summary}\n\nNeeds an optional download that is "
                    f"not installed — see File → Optional tools.",
                    Qt.ToolTipRole)
        keys = [t.key for t in spec.tools]
        if current_tool.key in keys:
            combo.setCurrentIndex(keys.index(current_tool.key))
        combo.currentIndexChanged.connect(
            lambda _i, k=spec.key: self._tool_changed(k))
        self._tools[spec.key] = combo
        head.addWidget(combo, 1)
        lay.addLayout(head)

        note = QLabel("")
        note.setWordWrap(True)
        note.setProperty("role", "dim")
        self._status[spec.key] = note
        lay.addWidget(note)

        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(3)
        holder.setLayout(grid)
        lay.addWidget(holder)
        # Held by key rather than found by walking up from the combo box:
        # a parent chain is a layout detail and changes when the layout does.
        self._holders[spec.key] = holder
        self._fill_params(spec, holder, current_params)
        self._refresh_note(spec)
        if spec.can_disable:
            self._set_enabled(spec.key, enabled)
        return box

    def _fill_params(self, spec, holder: QWidget, values: dict) -> None:
        grid = holder.layout()
        while grid.count():
            item = grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for key in [k for k in self._params if k[0] == spec.key]:
            self._params.pop(key, None)

        tool = spec.tool(self._tools[spec.key].currentData()) \
            or spec.default_tool()
        row = 0
        for param in tool.params:
            value = values.get(param.key, param.default)
            label = QLabel(param.label + (f" ({param.unit})"
                                          if param.unit else "") + ":")
            label.setToolTip(param.help)
            if param.kind == "bool":
                editor = QCheckBox()
                editor.setChecked(bool(value))
            elif param.kind == "choice":
                editor = QComboBox()
                for choice_value, choice_label in param.choices:
                    editor.addItem(choice_label, choice_value)
                choices = [c for c, _l in param.choices]
                if value in choices:
                    editor.setCurrentIndex(choices.index(value))
            else:
                editor = QLineEdit(str(value))
                editor.setMaximumWidth(80)
            editor.setToolTip(param.help)
            grid.addWidget(label, row, 0)
            grid.addWidget(editor, row, 1)
            hint = QLabel(param.help)
            hint.setWordWrap(True)
            hint.setProperty("role", "dim")
            grid.addWidget(hint, row, 2)
            grid.setColumnStretch(2, 1)
            self._params[(spec.key, param.key)] = editor
            row += 1
        holder.setVisible(row > 0)

    # -- reactions --------------------------------------------------------
    def _tool_changed(self, key: str) -> None:
        spec = next(m for m in MEASUREMENTS if m.key == key)
        holder = self._holders[key]
        tool = spec.tool(self._tools[key].currentData()) or spec.default_tool()
        self._fill_params(spec, holder, tool.defaults())
        self._refresh_note(spec)
        self._refresh_summary()

    def _refresh_note(self, spec) -> None:
        tool = spec.tool(self._tools[spec.key].currentData()) \
            or spec.default_tool()
        parts = [tool.summary]
        if tool.status == DETERMINISTIC:
            parts.append(
                "This tool is deterministic: it computes a signal directly and "
                "has no detection or classification step that could be graded "
                "against human coding. That is not a claim that the quantity "
                "is a valid stand-in for the construct — it is the researcher "
                "who has to argue that.")
        elif tool.status != VALIDATED:
            parts.append(
                f"This tool is {STATUS_LABEL.get(tool.status, tool.status)} — "
                f"its numbers are flagged wherever they appear, in the "
                f"interface and in exports.")
        if tool.notes:
            parts.append(tool.notes)
        if not tool.is_available():
            parts.append(
                "NOT INSTALLED. It needs an optional download — File → "
                "Optional tools. Applying with this selected is refused, "
                "rather than failing when you next press Analyze.")
        self._status[spec.key].setText("  ".join(parts))

    def _set_enabled(self, key: str, on: bool) -> None:
        self._tools[key].setEnabled(on)
        for (spec_key, _p), editor in self._params.items():
            if spec_key == key:
                editor.setEnabled(on)
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        if self._building:
            return
        candidate = self._collect(warn=False)
        if candidate is None:
            self._summary.setText("")
            return
        changes = diff_fingerprints(self.config, candidate)
        if not changes:
            self._summary.setText("No measurement change.")
            return
        stale, unknown = self._count_stale(candidate)
        parts = [f"{len(changes)} change{'s' if len(changes) != 1 else ''}"]
        parts.append(f"{stale} cached episode{'s' if stale != 1 else ''} would "
                     f"become stale" if stale else
                     "no fingerprinted episode is affected")
        if unknown:
            parts.append(f"{unknown} predate{'' if unknown != 1 else 's'} "
                         f"fingerprinting and cannot be checked")
        self._summary.setText("; ".join(parts) + ".")

    # -- collecting -------------------------------------------------------
    def _collect(self, warn: bool = True) -> dict | None:
        new_config = copy.deepcopy(self.config)
        block = new_config.setdefault("measurements", {})
        for spec in MEASUREMENTS:
            tool = spec.tool(self._tools[spec.key].currentData()) \
                or spec.default_tool()
            entry = block.setdefault(spec.key, {})
            entry["tool"] = tool.key
            params: dict = {}
            for param in tool.params:
                editor = self._params.get((spec.key, param.key))
                if editor is None:
                    params[param.key] = param.default
                    continue
                if isinstance(editor, QCheckBox):
                    raw = editor.isChecked()
                elif isinstance(editor, QComboBox):
                    raw = editor.currentData()
                else:
                    raw = editor.text()
                try:
                    params[param.key] = param.coerce(raw)
                except (TypeError, ValueError):
                    if warn:
                        QMessageBox.warning(
                            self, "Not a number",
                            f"{spec.name} — {param.label}: “{raw}” is not a "
                            f"valid value.")
                    return None
            entry["params"] = params
            if spec.can_disable:
                entry["enabled"] = self._enabled[spec.key].isChecked()
        return normalize_config(new_config)

    def _count_stale(self, new_config: dict) -> tuple[int, int]:
        """(newly stale, cannot be checked) across the cached library.

        Walks the library, so the first number is the true count rather than
        an estimate — the user is being asked to accept a cost and deserves
        the real figure.

        The second number matters as much. `analyzer.cache.is_stale`
        GRANDFATHERS results written before measurement fingerprinting
        existed: with no fingerprint to compare, it reports False. That is the
        right default — one upgrade should not invalidate a whole corpus — but
        it means "1 episode goes stale" can sit on top of eleven whose
        settings are simply unknown. Reporting the first without the second
        would understate the cost in exactly the direction that flatters the
        change.
        """
        if not self._root:
            return 0, 0
        stale = unknown = 0
        try:
            for show_dir in list_shows(self._root):
                key = show_key(self._root, show_dir)
                for episode in list_episodes(show_dir):
                    cached = load_cached(self._root, key, episode.stem)
                    if not cached:
                        continue
                    if not cached_fingerprint(cached):
                        unknown += 1
                    elif is_stale(cached, new_config):
                        stale += 1
        except Exception:
            return stale, unknown
        return stale, unknown

    # -- actions ----------------------------------------------------------
    def _restore_defaults(self) -> None:
        for spec in MEASUREMENTS:
            combo = self._tools[spec.key]
            keys = [t.key for t in spec.tools]
            combo.setCurrentIndex(keys.index(spec.default_tool().key))
            if spec.can_disable:
                self._enabled[spec.key].setChecked(spec.default_enabled)
        self._refresh_summary()

    def _apply(self) -> None:
        new_config = self._collect()
        if new_config is None:
            return

        missing = [
            f"{spec.name}: "
            f"{(spec.tool(self._tools[spec.key].currentData()) or spec.default_tool()).name}"
            for spec in MEASUREMENTS
            if not (spec.tool(self._tools[spec.key].currentData())
                    or spec.default_tool()).is_available()
        ]
        if missing:
            QMessageBox.warning(
                self, "That tool is not installed",
                "These selections need an optional download that is not "
                "installed:\n\n  • " + "\n  • ".join(missing)
                + "\n\nInstall it from File → Optional tools, or choose "
                  "another tool.")
            return

        changes = diff_fingerprints(self.config, new_config)
        if changes:
            stale = self._count_stale(new_config)
            lines = ["Changing:", ""] + [f"  • {c}" for c in changes] + [""]
            if stale:
                lines += [
                    f"This makes {stale} already-analysed episode"
                    f"{'s' if stale != 1 else ''} STALE. They were measured "
                    f"with different settings, so their numbers are not "
                    f"comparable with anything analysed from now on.",
                    "",
                    "Nothing is deleted and they keep displaying. Re-analyse "
                    "them to bring the library back onto one set of settings.",
                    "", "Apply anyway?"]
            else:
                lines += ["No analysed episode is affected.", "", "Apply?"]
            answer = QMessageBox.question(self, "Measurement change",
                                          "\n".join(lines))
            if answer != QMessageBox.Yes:
                return
            self.stale_count = stale
        self.config = new_config
        self.accept()
