"""
ui/recipes.py — the Recipes dialog: how a construct was operationalized.

**The third settings axis.** `ui/settings.py` edits SCORING (weights and
ceilings, re-scorable from cache). `ui/measurements.py` edits MEASUREMENT
(which detector, what parameters, invalidates the cache). This edits neither:
a recipe is a saved, versioned, citable claim about how a construct was
measured, and it **pins** its parameters rather than following either dialog.
See `ARCHITECTURE.md` §3b.

Three rules this screen exists to honour, each of which shapes the layout:

* **A recipe is inspectable or it is not a recipe** (`CLAUDE.md` §2.5). There
  is no summary view. Every binding shows its method, its **pinned parameter
  values**, its transform, its reference range, its weight and its
  missing-data policy, always, on the same screen that names the recipe. A
  name standing in for settings the researcher cannot read is the thing this
  whole phase exists to remove.

* **Pinning has a visible cost, and the screen pays it.** Because a recipe
  holds its own copy of a threshold, that threshold can differ from the live
  Measurement settings. `recipes.divergences()` is surfaced in the header,
  worded as a statement rather than a warning — a divergence is the ordinary
  state of a recipe saved before a settings change, and it means the recipe
  still describes what it always described.

* **An unavailable control must not look like a broken one** (`CLAUDE.md` §4).
  The shipped composite is locked because the published index is built on it.
  Its editors are disabled and the reason is on screen, with Duplicate offered
  as the route — not a greyed-out Save with no explanation.

A version needs a reason, so Save is disabled until one is given whenever the
operationalization actually changed — and the disabled Save says which. That
is the same rule `recipes.bump_version` enforces in the engine; the screen
does not get to skip it.

Evaluation runs on a worker thread. It is cache reading rather than analysis,
but it is 358 ms over this library's 137 episodes and grows with the corpus,
and `CLAUDE.md` §2.4 does not carve out an exception for "only a bit slow".
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
    QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QMessageBox, QPushButton,
    QScrollArea, QSpinBox, QSplitter, QTextBrowser, QVBoxLayout, QWidget,
)

from analyzer import constructs as C
from analyzer import recipes as R
from analyzer.show_index import list_episodes, list_shows, show_key
from ui import reference_css
from ui.modal import ConfirmDialog, ModalDialogFrame
from ui.tokens import COLORS as _C

DIALOG_W = 980
DIALOG_H = 700

# The reference's own rules, loaded rather than transcribed — `ui/DESIGN.md`
# §0.1. The detail pane is document-shaped, so it is real HTML in a
# QTextBrowser using the reference class names (§0.2, route 1).
_REFERENCE = reference_css.rules((
    "data-table", "section-title", "sub-text", "info-banner", "info-title",
))

_STYLE = _REFERENCE + f"""
body {{ color: {_C['text']}; font-size: 11px; }}
p {{ margin: 3px 0; }}
tr.alt td {{ background-color: {_C['table_alt_row']}; }}
.data-table th.l, .data-table td.l {{ text-align: left; }}
.dim {{ color: {_C['text_dim']}; }}
.note {{ color: {_C['text_dim']}; font-style: italic; font-size: 10px; }}
.warn {{ background: {_C['warn_bg']}; border: 1px solid {_C['warn_border']};
         color: {_C['warn_text']}; font-size: 10px; padding: 6px 8px; }}
.cite {{ font-family: Consolas, monospace; font-size: 10px;
         color: {_C['accent_dark']}; }}
"""


def _document(body: str) -> str:
    return f"<html><head><style>{_STYLE}</style></head><body>{body}</body></html>"


def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


# ---------------------------------------------------------------------------
# Evaluation, off the interface thread
# ---------------------------------------------------------------------------

class EvaluationWorker(QThread):
    """Applies a recipe across a set of episodes without freezing the window.

    Note what is NOT done here: the results are not combined into an average.
    `resolve_measure` offers no aggregate across methods and neither does this
    — the table lists one row per episode and the summary counts outcomes.
    """

    progress = Signal(int, int)                  # done, total
    finished_ok = Signal(list)                   # [(label, Evaluation)]
    failed = Signal(str)

    def __init__(self, recipe: R.Recipe, root: Path, config: dict,
                 targets: list[tuple[str, Path]], validation_dir: Path | None):
        super().__init__()
        self._recipe = recipe
        self._root = root
        self._config = config
        self._targets = list(targets)
        self._vdir = validation_dir
        self._stop = False

    def cancel(self) -> None:
        self._stop = True

    def run(self) -> None:                                    # pragma: no cover
        try:
            out = []
            total = len(self._targets)
            for i, (skey, path) in enumerate(self._targets):
                if self._stop:
                    return
                ref = C.EpisodeRef(root=self._root, show_name=skey,
                                   stem=path.stem, video=path,
                                   validation_dir=self._vdir)
                out.append((path.stem,
                            R.evaluate(self._recipe, ref, self._config)))
                self.progress.emit(i + 1, total)
            self.finished_ok.emit(out)
        except Exception as exc:                              # pragma: no cover
            self.failed.emit(str(exc))


# ---------------------------------------------------------------------------
# One binding's editor
# ---------------------------------------------------------------------------

class BindingBox(QGroupBox):
    """One measure, one method, and every setting that acts on it.

    Deliberately shows the pinned parameters as read-only text with an explicit
    **Re-pin** button rather than as editable fields. Editing a pinned value
    in place would quietly make the recipe describe something no cached result
    was produced under; re-pinning is an act with a visible name, and it is the
    honest answer to a divergence.
    """

    changed = Signal()

    def __init__(self, binding: R.MeasureBinding, config: dict,
                 editable: bool) -> None:
        measure = C.get_measure(binding.measure_key)
        super().__init__(measure.name if measure else binding.measure_key)
        self.binding = binding
        self._config = config
        self._editable = editable

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        construct = C.get_construct(measure.construct_key) if measure else None
        head = QLabel(
            f"{construct.name if construct else '?'} · {measure.unit if measure else ''}"
            f" — {measure.definition if measure else ''}")
        head.setWordWrap(True)
        head.setProperty("role", "dim")
        lay.addWidget(head)

        # -- method ---------------------------------------------------------
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(QLabel("Method:"))
        self._method = QComboBox()
        for method in C.methods_for(binding.measure_key):
            label = method.label
            if method.kind == C.HAND_CODED:
                label += "  —  human-coded"
            else:
                label += f"  —  {method.status}"
            self._method.addItem(label, method.key)
            index = self._method.count() - 1
            tip = method.summary
            if method.notes:
                tip += "\n\n" + method.notes
            if not method.available:
                tip += ("\n\nNot installed — needs an optional download "
                        "(File → Optional tools).")
            self._method.setItemData(index, tip, Qt.ToolTipRole)
        keys = [m.key for m in C.methods_for(binding.measure_key)]
        if binding.method_key in keys:
            self._method.setCurrentIndex(keys.index(binding.method_key))
        self._method.currentIndexChanged.connect(self._method_changed)
        row.addWidget(self._method, 1)
        lay.addLayout(row)

        self._flag = QLabel("")
        self._flag.setWordWrap(True)
        self._flag.setProperty("role", "dim")
        lay.addWidget(self._flag)

        # -- pinned parameters ----------------------------------------------
        pin_row = QHBoxLayout()
        pin_row.setSpacing(6)
        self._pinned = QLabel("")
        self._pinned.setWordWrap(True)
        self._pinned.setTextInteractionFlags(Qt.TextSelectableByMouse)
        pin_row.addWidget(self._pinned, 1)
        self._repin = QPushButton("Re-pin")
        self._repin.setToolTip(
            "Replace this binding's frozen parameter values with the ones in "
            "the current Measurement settings. This CHANGES what the recipe "
            "operationalizes, so it needs a new version and a reason.")
        self._repin.clicked.connect(self._repin_clicked)
        pin_row.addWidget(self._repin)
        lay.addLayout(pin_row)

        # -- transform, range, weight, missing -------------------------------
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(3)

        grid.addWidget(QLabel("Transform:"), 0, 0)
        self._transform = QComboBox()
        self._transform.addItem("None — use the raw value", R.TRANSFORM_NONE)
        self._transform.addItem("Min–max against a fixed range, clamped",
                                R.TRANSFORM_MINMAX)
        self._transform.setCurrentIndex(
            1 if binding.transform == R.TRANSFORM_MINMAX else 0)
        self._transform.currentIndexChanged.connect(self._emit_changed)
        grid.addWidget(self._transform, 0, 1, 1, 3)

        grid.addWidget(QLabel("Reference range:"), 1, 0)
        self._min = QDoubleSpinBox()
        self._max = QDoubleSpinBox()
        for spin, value in ((self._min, binding.range_min),
                            (self._max, binding.range_max)):
            spin.setDecimals(4)
            spin.setRange(-1e6, 1e6)
            spin.setValue(value)
            spin.setMaximumWidth(90)
            spin.valueChanged.connect(self._emit_changed)
        grid.addWidget(self._min, 1, 1)
        grid.addWidget(QLabel("to"), 1, 2)
        grid.addWidget(self._max, 1, 3)

        grid.addWidget(QLabel("Weight:"), 2, 0)
        self._weight = QDoubleSpinBox()
        self._weight.setDecimals(4)
        self._weight.setRange(0.0, 1e6)
        self._weight.setSingleStep(0.05)
        self._weight.setValue(binding.weight)
        self._weight.setMaximumWidth(90)
        self._weight.valueChanged.connect(self._emit_changed)
        grid.addWidget(self._weight, 2, 1)

        grid.addWidget(QLabel("If missing:"), 3, 0)
        self._missing = QComboBox()
        self._missing.addItem("Refuse — produce no score at all",
                              R.MISSING_REFUSE)
        self._missing.addItem("Omit — drop it, report the smaller scale",
                              R.MISSING_OMIT)
        self._missing.addItem("Redistribute — spread its weight over the rest",
                              R.MISSING_REDISTRIBUTE)
        policies = [R.MISSING_REFUSE, R.MISSING_OMIT, R.MISSING_REDISTRIBUTE]
        self._missing.setCurrentIndex(policies.index(binding.missing)
                                      if binding.missing in policies else 0)
        self._missing.currentIndexChanged.connect(self._emit_changed)
        grid.addWidget(self._missing, 3, 1, 1, 3)
        grid.setColumnStretch(3, 1)
        lay.addLayout(grid)

        if measure and measure.notes:
            note = QLabel(measure.notes)
            note.setWordWrap(True)
            note.setProperty("role", "dim")
            lay.addWidget(note)

        for widget in (self._method, self._transform, self._min, self._max,
                       self._weight, self._missing, self._repin):
            widget.setEnabled(editable)

        self._refresh_pinned()
        self._refresh_flag()

    # -- reactions ----------------------------------------------------------
    def _emit_changed(self, *_a) -> None:
        self.changed.emit()

    def _method_changed(self) -> None:
        """Changing the method re-pins from the config for the NEW method.

        Keeping the old method's parameters would pin values that never
        applied to it — a threshold of 27 means something different to
        ContentDetector than to TransNetV2.
        """
        self.binding.method_key = self._method.currentData()
        self.binding.parameters = R.pin_parameters(
            self.binding.measure_key, self.binding.method_key, self._config)
        self._refresh_pinned()
        self._refresh_flag()
        self.changed.emit()

    def _repin_clicked(self) -> None:
        self.binding.parameters = R.pin_parameters(
            self.binding.measure_key, self.binding.method_key, self._config)
        self._refresh_pinned()
        self.changed.emit()

    def _refresh_pinned(self) -> None:
        method = C.get_method(self.binding.measure_key,
                              self.binding.method_key)
        if method is not None and method.kind == C.HAND_CODED:
            self._pinned.setText(
                "Pinned parameters: none. Hand coding has no tunables — its "
                "equivalents are the codebook and the coded window, which "
                "live with the sheet.")
            self._repin.setEnabled(False)
            self._repin.setToolTip("Hand coding has no parameters to re-pin.")
            return
        if not self.binding.parameters:
            self._pinned.setText("Pinned parameters: none for this method.")
            return
        shown = ", ".join(f"{k} = {v}"
                          for k, v in sorted(self.binding.parameters.items()))
        self._pinned.setText(f"Pinned parameters: {shown}")

    def _refresh_flag(self) -> None:
        method = C.get_method(self.binding.measure_key,
                              self.binding.method_key)
        if method is None:
            self._flag.setText(
                "This install has no such method. The binding is kept as "
                "imported rather than substituted, and cannot produce a "
                "number here.")
            return
        parts = [method.summary]
        flag = C._flag_for(method)
        if flag:
            parts.append(
                f"{flag}. Its numbers are flagged wherever they appear.")
        if not method.available:
            parts.append("NOT INSTALLED — File → Optional tools.")
        self._flag.setText("  ".join(p for p in parts if p))

    # -- reading back -------------------------------------------------------
    def values(self) -> dict:
        """What this box currently says, WITHOUT writing it anywhere.

        Deliberately not an `apply_to_binding()` that mutates
        `self.binding`. That is what this box was written as first, and it is
        wrong in a way that is invisible from the screen: the dialog's
        dirty-check builds a throwaway copy of the recipe and fills it from the
        form, but a mutating apply writes into the LIVE recipe's binding
        instead — the copy stays as it was, its hash matches the baseline, and
        the screen reports "nothing has changed" for a change the user just
        made. The check ran one edit behind, and Save became available with no
        reason given, which is exactly the rule this screen exists to enforce.
        A reader hands values back; only the dialog decides where they land.
        """
        return {
            "method_key": self._method.currentData(),
            "transform": self._transform.currentData(),
            "range_min": self._min.value(),
            "range_max": self._max.value(),
            "weight": self._weight.value(),
            "missing": self._missing.currentData(),
            "parameters": dict(self.binding.parameters),
        }


# ---------------------------------------------------------------------------
# The dialog
# ---------------------------------------------------------------------------

class RecipesDialog(QDialog):
    """Browse, inspect, edit, evaluate, export and import recipes."""

    def __init__(self, config: dict, root: Path | None, scope=None,
                 parent=None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.resize(DIALOG_W, DIALOG_H)
        self._config = config
        self._root = root
        self._scope = scope
        self._recipes: list[R.Recipe] = []
        self._current: R.Recipe | None = None
        self._baseline_hash = ""
        self._boxes: list[BindingBox] = []
        self._worker: EvaluationWorker | None = None
        self._building = False

        body = ModalDialogFrame.install(self, "Recipes",
                                        buttons=("min", "max", "close"))

        intro = QLabel(
            "A recipe records how a construct was operationalized: which "
            "measures stand in for it, by which methods, with which "
            "parameters. It PINS those parameters, so it keeps describing "
            "what it always described even after Measurement settings change. "
            "Every recipe is shown down to the parameter — there is no summary "
            "view.")
        intro.setWordWrap(True)
        intro.setProperty("role", "dim")
        body.addWidget(intro)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(self._build_list())
        split.addWidget(self._build_detail())
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([260, DIALOG_W - 260])
        body.addWidget(split, 1)

        row = ModalDialogFrame.add_action_bar(self)
        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setProperty("role", "dim")
        row.addWidget(self._status, 1)
        self._btn_save = QPushButton("Save")
        self._btn_save.setProperty("primary", "true")
        self._btn_save.clicked.connect(self._save)
        row.addWidget(self._btn_save)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        row.addWidget(close)

        self._reload()

    # -- construction -------------------------------------------------------
    def _build_list(self) -> QWidget:
        from ui.main_window import Panel
        panel = Panel("Recipes")
        self._list = QListWidget()
        self._list.setProperty("inPanel", "true")
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.currentRowChanged.connect(self._select_row)
        panel.body_layout.addWidget(self._list, 1)

        buttons = QWidget()
        brow = QHBoxLayout(buttons)
        brow.setContentsMargins(6, 6, 6, 6)
        brow.setSpacing(4)
        self._btn_new = QPushButton("New…")
        self._btn_new.clicked.connect(self._new_menu)
        self._btn_dup = QPushButton("Duplicate")
        self._btn_dup.clicked.connect(self._duplicate)
        self._btn_del = QPushButton("Delete…")
        self._btn_del.clicked.connect(self._delete)
        for b in (self._btn_new, self._btn_dup, self._btn_del):
            brow.addWidget(b)
        panel.body_layout.addWidget(buttons)

        buttons2 = QWidget()
        brow2 = QHBoxLayout(buttons2)
        brow2.setContentsMargins(6, 0, 6, 6)
        brow2.setSpacing(4)
        self._btn_export = QPushButton("Export…")
        self._btn_export.clicked.connect(self._export)
        self._btn_import = QPushButton("Import…")
        self._btn_import.clicked.connect(self._import)
        brow2.addWidget(self._btn_export)
        brow2.addWidget(self._btn_import)
        brow2.addStretch(1)
        panel.body_layout.addWidget(buttons2)
        return panel

    def _build_detail(self) -> QWidget:
        holder = QWidget()
        lay = QVBoxLayout(holder)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self._banner = QLabel("")
        self._banner.setWordWrap(True)
        self._banner.setProperty("role", "dim")
        lay.addWidget(self._banner)

        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        name_row.addWidget(QLabel("Name:"))
        self._name = QLineEdit()
        self._name.textEdited.connect(self._dirty)
        name_row.addWidget(self._name, 1)
        name_row.addWidget(QLabel("Report to"))
        self._decimals = QSpinBox()
        self._decimals.setRange(0, 10)
        self._decimals.setMaximumWidth(50)
        self._decimals.valueChanged.connect(self._dirty)
        name_row.addWidget(self._decimals)
        name_row.addWidget(QLabel("dp"))
        self._clamp = QCheckBox("Clamp to 0–1")
        self._clamp.toggled.connect(self._dirty)
        name_row.addWidget(self._clamp)
        lay.addLayout(name_row)

        notes_row = QHBoxLayout()
        notes_row.setSpacing(6)
        notes_row.addWidget(QLabel("Notes:"))
        self._notes = QLineEdit()
        self._notes.setPlaceholderText(
            "What this operationalization does — and what it does not justify")
        self._notes.setToolTip(
            "Carried into exports and into any copy of this recipe. This is "
            "where a caveat belongs: the shipped composite's notes are what "
            "keep 'these defaults are underived' attached to the number.")
        self._notes.textEdited.connect(self._dirty)
        notes_row.addWidget(self._notes, 1)
        lay.addLayout(notes_row)

        inner = QWidget()
        self._form = QVBoxLayout(inner)
        self._form.setContentsMargins(0, 0, 0, 0)
        self._form.setSpacing(6)
        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        lay.addWidget(scroll, 3)

        reason_row = QHBoxLayout()
        reason_row.setSpacing(6)
        self._reason_label = QLabel("Reason for this change:")
        reason_row.addWidget(self._reason_label)
        self._reason = QLineEdit()
        self._reason.setPlaceholderText(
            "Why the operationalization changed — what changed is derived; "
            "why cannot be recovered later")
        self._reason.textEdited.connect(self._sync_buttons)
        reason_row.addWidget(self._reason, 1)
        lay.addLayout(reason_row)

        eval_row = QHBoxLayout()
        eval_row.setSpacing(6)
        self._btn_eval = QPushButton("Apply to the current scope")
        self._btn_eval.clicked.connect(self._evaluate)
        eval_row.addWidget(self._btn_eval)
        self._eval_note = QLabel("")
        self._eval_note.setProperty("role", "dim")
        self._eval_note.setWordWrap(True)
        eval_row.addWidget(self._eval_note, 1)
        lay.addLayout(eval_row)

        self._detail = QTextBrowser()
        self._detail.setOpenExternalLinks(False)
        lay.addWidget(self._detail, 2)
        return holder

    # -- data ---------------------------------------------------------------
    def _reload(self, select_id: str | None = None) -> None:
        """Rebuild the list: the shipped composite first, then saved recipes.

        The shipped composite is GENERATED from the config each time rather
        than read from disk, so it always reflects the weights and ceilings in
        force — which is what makes it the composite CMAT actually computes
        rather than a snapshot of one.
        """
        saved = R.list_recipes(self._root) if self._root else []
        shipped = R.shipped_composite(self._config)
        self._recipes = [shipped] + [r for r in saved
                                     if r.name != shipped.name]

        self._list.blockSignals(True)
        self._list.clear()
        for recipe in self._recipes:
            construct = C.get_construct(recipe.construct_key)
            item = QListWidgetItem(
                f"{recipe.name}\n   v{recipe.version} · "
                f"{construct.name if construct else recipe.construct_key}"
                f"{'  · locked' if recipe.locked else ''}")
            item.setToolTip(recipe.citation())
            self._list.addItem(item)
        self._list.blockSignals(False)

        target = 0
        if select_id:
            for i, recipe in enumerate(self._recipes):
                if recipe.id == select_id:
                    target = i
                    break
        self._list.setCurrentRow(target)
        self._select_row(target)

    def _select_row(self, row: int) -> None:
        if not (0 <= row < len(self._recipes)):
            self._current = None
            return
        self._current = self._recipes[row]
        self._baseline_hash = self._current.content_hash()
        self._populate()

    def _populate(self) -> None:
        recipe = self._current
        if recipe is None:
            return
        self._building = True

        editable = not recipe.locked
        self._name.setText(recipe.name)
        self._notes.setText(recipe.notes)
        self._notes.setCursorPosition(0)
        self._decimals.setValue(recipe.score_decimals)
        self._clamp.setChecked(recipe.clamp_score)
        for widget in (self._name, self._notes, self._decimals, self._clamp):
            widget.setEnabled(editable)

        if recipe.locked:
            self._banner.setText(
                "LOCKED. This is the composite CMAT has always computed, and "
                "the published index is built on it — editing it would break "
                "comparability with every score already published. It is "
                "shown in full so it can be read; press Duplicate to explore "
                "a different weighting on a copy. Its weights and ceilings "
                "follow Scoring settings, so it always reflects the preset in "
                "force.")
        else:
            self._banner.setText("")

        while self._form.count():
            item = self._form.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._boxes = []
        for binding in recipe.bindings:
            box = BindingBox(binding, self._config, editable)
            box.changed.connect(self._dirty)
            self._form.addWidget(box)
            self._boxes.append(box)
        self._form.addStretch(1)

        self._reason.setText("")
        self._detail.setHtml(_document(self._summary_html(recipe)))
        self._eval_note.setText(self._scope_line())
        self._building = False
        self._sync_buttons()

    # -- the read-only summary ---------------------------------------------
    def _summary_html(self, recipe: R.Recipe) -> str:
        construct = C.get_construct(recipe.construct_key)
        parts: list[str] = []

        parts.append('<p class="section-title">This version</p>')
        parts.append(f'<p class="cite">{_esc(recipe.citation())}</p>')
        if construct is not None:
            parts.append(f'<p><b>{_esc(construct.name)}</b> — '
                         f'{_esc(construct.definition)}</p>')
            parts.append(f'<p class="note">{_esc(construct.grounding)}</p>')
        else:
            parts.append(
                f'<p class="warn">This install has no construct '
                f'<b>{_esc(recipe.construct_key)}</b>, so nothing here '
                f'defines what the recipe measures.</p>')
        if recipe.notes:
            parts.append(f'<p class="note">{_esc(recipe.notes)}</p>')
        parts.append(
            f'<p class="dim">Weights total {recipe.total_weight():g}; '
            f'score reported to {recipe.score_decimals} decimal places'
            f'{", clamped to 0–1" if recipe.clamp_score else ""}.</p>')

        # -- divergences ----------------------------------------------------
        found = R.divergences(recipe, self._config)
        parts.append('<p class="section-title">Pinned versus the current '
                     'Measurement settings</p>')
        if not found:
            parts.append('<p class="dim">Every pinned parameter matches the '
                         'settings currently in force.</p>')
        else:
            parts.append(
                '<p class="note">These are statements, not errors. A recipe '
                'pins its parameters so that it keeps describing what it '
                'always described; a difference here means the settings moved '
                'after this recipe was written, and the recipe did not. '
                'Re-pin a binding only if you intend to change what it '
                'operationalizes.</p>')
            rows = ['<table class="data-table" cellspacing="0" width="100%">'
                    '<tr><th class="l">Measure</th><th class="l">Parameter</th>'
                    '<th class="l">Pinned</th><th class="l">In force</th></tr>']
            for i, d in enumerate(found):
                cls = ' class="alt"' if i % 2 else ''
                rows.append(
                    f'<tr{cls}><td class="l">{_esc(d.measure_name)}</td>'
                    f'<td class="l">{_esc(d.parameter)}</td>'
                    f'<td class="l">{_esc(d.pinned)}</td>'
                    f'<td class="l">{_esc(d.live)}</td></tr>')
            rows.append('</table>')
            parts.append("".join(rows))

        # -- version history ------------------------------------------------
        parts.append('<p class="section-title">Version history</p>')
        if not recipe.history:
            parts.append('<p class="dim">No versions recorded.</p>')
        else:
            rows = ['<table class="data-table" cellspacing="0" width="100%">'
                    '<tr><th class="l">Version</th><th class="l">Date</th>'
                    '<th class="l">Reason</th><th class="l">Changed</th></tr>']
            for i, record in enumerate(reversed(recipe.history)):
                cls = ' class="alt"' if i % 2 else ''
                changes = "<br>".join(_esc(c) for c in record.changes) or "—"
                rows.append(
                    f'<tr{cls}><td class="l">v{record.version}<br>'
                    f'<span class="cite">{_esc(record.content_hash)}</span></td>'
                    f'<td class="l">{_esc(record.created)}</td>'
                    f'<td class="l">{_esc(record.reason) or "—"}</td>'
                    f'<td class="l">{changes}</td></tr>')
            rows.append('</table>')
            parts.append("".join(rows))
        return "".join(parts)

    # -- evaluation ---------------------------------------------------------
    def _scope_targets(self) -> list[tuple[str, Path]]:
        """(cache show key, episode path) for everything in the current scope."""
        if not self._root:
            return []
        out: list[tuple[str, Path]] = []
        for show_dir in list_shows(self._root):
            skey = show_key(self._root, show_dir)
            for episode in list_episodes(show_dir):
                if self._scope is None or self._scope.contains(episode):
                    out.append((skey, episode))
        return out

    def _scope_line(self) -> str:
        if not self._root:
            return "No library root chosen, so there is nothing to apply to."
        n = len(self._scope_targets())
        where = (self._scope.describe() if self._scope is not None
                 else "the whole library")
        return f"{where} — {n} episode{'' if n == 1 else 's'}."

    def _evaluate(self) -> None:
        if self._current is None or not self._root:
            return
        if self._worker is not None and self._worker.isRunning():
            return
        targets = self._scope_targets()
        if not targets:
            self._detail.setHtml(_document(
                '<p class="warn">Nothing in the current scope to apply this '
                'recipe to.</p>'))
            return

        self._read_form_into(self._current)
        self._btn_eval.setEnabled(False)
        self._eval_note.setText(f"Applying to {len(targets)} episodes…")
        # The worker reference is deliberately kept, not cleared in the slot
        # connected to its own finished signal — doing that frees a live
        # QThread from under itself and the process dies with no traceback.
        # `LEARNINGS.md` § *Dropping a QThread reference inside its own signal
        # handler crashes Qt*.
        self._worker = EvaluationWorker(
            self._current, self._root, self._config, targets,
            self._validation_dir())
        self._worker.progress.connect(self._on_eval_progress)
        self._worker.finished_ok.connect(self._on_evaluated)
        self._worker.failed.connect(self._on_eval_failed)
        self._worker.finished.connect(self._sync_buttons)
        self._worker.start()

    def _validation_dir(self) -> Path | None:
        from analyzer.validation import get_validation_dir
        try:
            return get_validation_dir()
        except Exception:                                     # pragma: no cover
            return None

    def _on_eval_progress(self, done: int, total: int) -> None:
        self._eval_note.setText(f"Applying… {done} of {total}")

    def _on_eval_failed(self, message: str) -> None:           # pragma: no cover
        self._eval_note.setText("")
        self._detail.setHtml(_document(
            f'<p class="warn">{_esc(message)}</p>'))

    def _on_evaluated(self, results: list) -> None:
        self._eval_note.setText(self._scope_line())
        self._detail.setHtml(_document(self._evaluation_html(results)))

    def _evaluation_html(self, results: list) -> str:
        recipe = self._current
        parts = ['<p class="section-title">Applied to the current scope</p>']
        parts.append(f'<p class="cite">{_esc(recipe.citation())}</p>')

        scored = [(label, ev) for label, ev in results if ev.score is not None]
        refused = [(label, ev) for label, ev in results if ev.score is None]

        parts.append(
            f'<p class="dim">{len(scored)} scored, {len(refused)} refused, '
            f'out of {len(results)}.</p>')

        flags: list[str] = []
        for _label, ev in results:
            for flag in ev.flags:
                if flag not in flags:
                    flags.append(flag)
        if flags:
            parts.append('<p class="warn">' + "<br>".join(
                _esc(f) for f in flags) + '</p>')

        if scored:
            rows = ['<table class="data-table" cellspacing="0" width="100%">'
                    '<tr><th class="l">Episode</th><th>Score</th>'
                    '<th>Scale</th><th class="l">Note</th></tr>']
            for i, (label, ev) in enumerate(scored):
                cls = ' class="alt"' if i % 2 else ''
                rows.append(
                    f'<tr{cls}><td class="l">{_esc(label)}</td>'
                    f'<td>{ev.score}</td><td>{ev.scale:g}</td>'
                    f'<td class="n">{_esc(ev.detail)}</td></tr>')
            rows.append('</table>')
            parts.append("".join(rows))

        if refused:
            parts.append('<p class="section-title">Refused, and why</p>')
            parts.append(
                '<p class="note">A refusal is not a failure to compute. It '
                'means the numbers this recipe describes were not produced '
                'for that episode, and reporting one anyway would be a '
                'measurement that never happened.</p>')
            parts.append(self._refusal_table(refused))
        return "".join(parts)

    @staticmethod
    def _refusal_table(refused: list) -> str:
        """Refusals GROUPED by measure and reason, with example episodes.

        Listed one row per refused part, an unanalysed library produces the
        same sentence hundreds of times — 124 episodes times six measures is
        744 rows saying "no cached result", and the one refusal that differs is
        buried in the middle of them. Grouping is what makes the table
        readable: the count is the fact, and a few named episodes are enough to
        act on.
        """
        groups: dict[tuple[str, str], list[str]] = {}
        for label, ev in refused:
            for part in ev.parts:
                if part.ok:
                    continue
                # Key on the STATUS, not the detail: details carry per-episode
                # paths, which would defeat the grouping entirely.
                groups.setdefault((part.measure_name, part.status),
                                  []).append((label, part.detail))

        rows = ['<table class="data-table" cellspacing="0" width="100%">'
                '<tr><th class="l">Measure</th><th class="l">Reason</th>'
                '<th>Episodes</th><th class="l">For example</th></tr>']
        for i, ((measure, status), entries) in enumerate(
                sorted(groups.items(), key=lambda kv: -len(kv[1]))):
            cls = ' class="alt"' if i % 2 else ''
            examples = ", ".join(label for label, _d in entries[:3])
            if len(entries) > 3:
                examples += f", and {len(entries) - 3} more"
            explanation = entries[0][1] if entries else ""
            rows.append(
                f'<tr{cls}><td class="l">{_esc(measure)}</td>'
                f'<td class="l">{_esc(status)}</td>'
                f'<td>{len(entries)}</td>'
                f'<td class="l">{_esc(examples)}</td></tr>')
            rows.append(
                f'<tr{cls}><td class="l"></td>'
                f'<td class="n" colspan="3">{_esc(explanation)}</td></tr>')
        rows.append('</table>')
        return "".join(rows)

    # -- editing ------------------------------------------------------------
    def _dirty(self, *_a) -> None:
        if self._building:
            return
        self._sync_buttons()

    def _read_form_into(self, recipe: R.Recipe) -> None:
        """Fill *recipe* from the form. Writes only into the recipe given.

        Matched by measure key rather than by position, so this is correct for
        the live recipe and for a throwaway copy alike — see `BindingBox
        .values`, which exists because an earlier version wrote into the live
        binding regardless of the argument and made the dirty check run one
        edit behind.
        """
        recipe.name = self._name.text().strip() or recipe.name
        recipe.notes = self._notes.text()
        recipe.score_decimals = self._decimals.value()
        recipe.clamp_score = self._clamp.isChecked()
        by_key = {b.measure_key: b for b in recipe.bindings}
        for box in self._boxes:
            target = by_key.get(box.binding.measure_key)
            if target is None:
                continue
            for field, value in box.values().items():
                setattr(target, field, value)

    def _sync_buttons(self, *_a) -> None:
        recipe = self._current
        running = self._worker is not None and self._worker.isRunning()
        self._btn_eval.setEnabled(recipe is not None and bool(self._root)
                                  and not running)
        if recipe is None:
            self._btn_save.setEnabled(False)
            self._btn_dup.setEnabled(False)
            self._btn_del.setEnabled(False)
            return

        self._btn_dup.setEnabled(True)
        self._btn_del.setEnabled(not recipe.locked and recipe.path is not None)

        if recipe.locked:
            self._btn_save.setEnabled(False)
            self._btn_del.setToolTip(
                "The shipped composite cannot be deleted: the published index "
                "is built on it.")
            self._status.setText(
                "This recipe is locked and cannot be saved over. Duplicate it "
                "to make a version you can change.")
            self._show_reason(False)
            return

        probe = R.Recipe.from_dict(recipe.to_dict())
        self._read_form_into(probe)
        changed = probe.content_hash() != self._baseline_hash
        self._show_reason(changed)

        if not changed:
            self._btn_save.setEnabled(True)
            self._status.setText(
                "Nothing about the operationalization has changed. Saving "
                "records the name and notes without adding a version — "
                "renaming a recipe is not a new version.")
            return

        has_reason = bool(self._reason.text().strip())
        self._btn_save.setEnabled(has_reason)
        self._status.setText(
            "The operationalization has changed, so saving records a new "
            "version. " + ("" if has_reason else
                           "Give a reason first: what changed is derived "
                           "automatically, why it changed cannot be "
                           "recovered later."))

    def _show_reason(self, visible: bool) -> None:
        self._reason_label.setVisible(visible)
        self._reason.setVisible(visible)

    def _save(self) -> None:
        recipe = self._current
        if recipe is None or recipe.locked or not self._root:
            return
        previous = R.Recipe.from_dict(recipe.to_dict())
        self._read_form_into(recipe)
        reason = self._reason.text().strip()
        if recipe.content_hash() != self._baseline_hash and reason:
            R.bump_version(recipe, reason, previous=previous)
        try:
            R.save_recipe(recipe, self._root)
        except PermissionError as exc:
            QMessageBox.information(self, "Locked", str(exc))
            return
        self._reload(select_id=recipe.id)

    # -- lifecycle ----------------------------------------------------------
    def _new_menu(self) -> None:
        menu = self._build_new_menu()
        if menu.actions():
            menu.exec(self._btn_new.mapToGlobal(
                self._btn_new.rect().bottomLeft()))

    def _build_new_menu(self) -> QMenu:
        """Every construct is offered, including the ones with no measures.

        This used to DISABLE a construct owning no measures of its own — which,
        by rule, is every construct a researcher defines, since measures are
        not user-definable. The block was total: a construct of your own could
        be written and then never operationalized, which is the thing the whole
        authoring phase is for.

        The route is now the one `TODO.md` item G describes: create the recipe
        over the construct, empty, then bind measures to it from the palette on
        the Constructs tab. An empty recipe is not a broken one — it refuses to
        score, and `evaluate` says why — so creating it is a step rather than a
        half-finished state.

        Built here and executed by its caller, so a test can read what the menu
        OFFERS and which entries are enabled. `menu.exec` blocks, which is
        precisely why the disabled entry above sat unexamined: nothing could
        look at it without stopping.
        """
        menu = QMenu(self)
        # `all_constructs()`, not `CONSTRUCTS`: the latter is only the shipped
        # starting set, and a researcher's own constructs live with the library.
        for construct in C.all_constructs():
            measures = C.measures_for(construct.key)
            # "available", for the same reason the Constructs picker says it:
            # this is the catalogue, not what any recipe binds.
            action = menu.addAction(
                f"{construct.name}  ({len(measures)} measure"
                f"{'' if len(measures) == 1 else 's'} available)")
            if measures:
                action.setToolTip(construct.definition)
            else:
                # Two different constructs land here and they need different
                # guidance. `sensory_load` is shipped and has a shipped recipe
                # worth copying; a researcher's own has nothing to copy, and
                # telling them to duplicate one would send them nowhere.
                action.setToolTip(
                    f"{construct.name} has no measures of its own — it is "
                    f"operationalized by a recipe drawing on other "
                    f"constructs. This creates that recipe empty; bind "
                    f"measures to it on the Constructs tab, or duplicate the "
                    f"shipped composite to start from its six."
                    if construct.source == C.SHIPPED else
                    f"{construct.name} is your own construct, so it has no "
                    f"measures of its own — measures are shipped, and a "
                    f"construct of yours is operationalized by binding them "
                    f"to it. This creates the recipe; bind the measures on "
                    f"the Constructs tab.")
            action.triggered.connect(
                lambda _c=False, k=construct.key: self._new_recipe(k))

        menu.addSeparator()
        # Creation lives on the Constructs tab and is REACHED from here too,
        # through the one shared editor — this is where a researcher runs out
        # of constructs, so a dead end here would be the wrong place to send
        # them somewhere else to look for the door.
        define = menu.addAction("New construct…")
        define.setToolTip(
            "Define a construct of your own. Measures stay shipped: a "
            "construct of yours is operationalized by binding them to it.")
        define.triggered.connect(self._new_construct)
        return menu

    def _new_construct(self) -> None:
        from ui.construct_editor import ConstructEditor
        if not self._root:
            QMessageBox.information(
                self, "No library",
                "Choose a root folder first — a construct is stored with the "
                "library it describes, beside the recipes that cite it.")
            return
        editor = ConstructEditor(self._root, None, self)
        if editor.exec() == QDialog.Accepted and editor.saved_key:
            self._new_recipe(editor.saved_key)

    def _new_recipe(self, construct_key: str) -> None:
        if not self._root:
            QMessageBox.information(
                self, "No library",
                "Choose a root folder first — recipes are stored with the "
                "library they describe.")
            return
        construct = C.get_construct(construct_key)
        name = R.unique_name([r.name for r in self._recipes],
                             f"{construct.name if construct else construct_key}")
        empty = not C.measures_for(construct_key)
        recipe = R.new_recipe(
            name, construct_key, self._config,
            reason=("Created over a construct with no measures of its own; "
                    "measures are bound to it on the Constructs tab"
                    if empty else "Created from the shipped measures"))
        R.save_recipe(recipe, self._root)
        self._reload(select_id=recipe.id)
        if empty:
            self._status.setText(
                f"“{name}” was created with no bindings — {construct.name if construct else construct_key} "
                f"has no measures of its own. Bind measures to it on the "
                f"Constructs tab, in Edit. It will refuse to score until it "
                f"has at least one with a weight.")

    def _duplicate(self) -> None:
        if self._current is None or not self._root:
            return
        name = R.unique_name([r.name for r in self._recipes],
                             f"{self._current.name} copy")
        copy = R.duplicate_recipe(self._current, name)
        R.save_recipe(copy, self._root)
        self._reload(select_id=copy.id)

    def _delete(self) -> None:
        recipe = self._current
        if recipe is None or recipe.locked or recipe.path is None:
            return
        confirm = ConfirmDialog(
            self, "Delete recipe",
            f"Delete “{recipe.name}”?",
            detail=("The recipe file is removed. No measurement, cached "
                    "result or coding sheet is touched — a recipe records "
                    "how numbers were operationalized, it does not hold "
                    "any."),
            confirm_text="Delete")
        if confirm.exec() != QDialog.Accepted:
            return
        R.delete_recipe(recipe)
        self._reload()

    # -- export / import ----------------------------------------------------
    def _export(self) -> None:
        if self._current is None:
            return
        suggested = f"{self._current.name.replace(' ', '_')}.recipe.json"
        path, _f = QFileDialog.getSaveFileName(
            self, "Export recipe", suggested, "Recipe JSON (*.json)")
        if not path:
            return
        Path(path).write_text(
            json.dumps(R.export_recipe(self._current), indent=2),
            encoding="utf-8")
        self._status.setText(f"Exported to {path}")

    def _import(self) -> None:
        if not self._root:
            QMessageBox.information(
                self, "No library",
                "Choose a root folder first — an imported recipe is stored "
                "with the library.")
            return
        path, _f = QFileDialog.getOpenFileName(
            self, "Import recipe", "", "Recipe JSON (*.json)")
        if not path:
            return
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not read", str(exc))
            return

        recipe, gaps = R.import_recipe(payload)
        recipe.name = R.unique_name([r.name for r in self._recipes],
                                    recipe.name)
        R.save_recipe(recipe, self._root)
        self._reload(select_id=recipe.id)

        if gaps:
            # Reported, never substituted. A default swapped in silently would
            # change what the recipe measures while keeping its name and
            # version intact.
            lines = "\n\n".join(
                f"{g.kind}: {g.described_as}\n{g.detail}" for g in gaps)
            QMessageBox.warning(
                self, "Imported with gaps",
                f"The recipe was imported and nothing was substituted for "
                f"what this install does not have. These references cannot "
                f"resolve here:\n\n{lines}")
