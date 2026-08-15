"""
ui/settings.py — Presets & Weights, the reference's modal 2.

Follows ui/reference/dialogs.css: a 450px dialog in the ordinary window chrome,
a preset bar over two side-by-side fieldsets, a callout, the speech fieldset,
and an action bar.

Everything here is a SCORING setting: it applies to metrics that have already
been computed, so changing it re-scores from cache instantly and invalidates
nothing. Measurement settings — detectors, thresholds, sample rates — change
the raw numbers and belong elsewhere, because they make cached results stale.
Keeping the two apart is why "Apply & Re-score" can promise what it says.

The rows are read from config.json, not from the reference: the weights are
whatever `sensory_load_weights` holds, and the ceilings are whatever
`normalization_reference_ranges` holds, in that order. A metric added to the
engine appears here without this file changing.
"""

from __future__ import annotations

import copy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from ui.modal import ConfirmDialog, ModalDialogFrame
from ui.tokens import color

DIALOG_W = 450        # .settings-dialog width
FIELD_W = 44          # .form-row-dense input width

# The label each weight and ceiling is shown under. A key with no entry falls
# back to its own name, so a new metric appears rather than vanishing.
WEIGHT_LABEL = {
    "pacing": "Pacing", "saturation": "Saturation",
    "color_contrast": "Contrast", "motion": "Motion",
    "flashing": "Flashing", "audio": "Audio",
}
CEILING_LABEL = {
    "cuts_per_min": "Cuts/min max",
    "color_saturation_mean": "Saturation max",
    "color_contrast_mean": "Contrast max",
    "motion_mean": "Motion max",
    "flashing_events_per_min": "Flashing max",
    "audio_rms_mean": "Audio RMS max",
}

WHISPER_MODELS = ("tiny", "base", "small", "medium", "large")

CEILING_NOTE = (
    "A ceiling sets the top of a metric's 0–1 scale — it is a denominator, "
    "not a threshold or a limit. Set it against the figures on the right, "
    "which are what this library actually produces.\n"
    "• Too LOW and episodes above it all score exactly 1.0, so the most "
    "intense ones become indistinguishable. That is intentional in the tight "
    "age presets, which flag rather than rank; use a broader preset for "
    "fine-grained comparison.\n"
    "• Too HIGH and the metric barely moves, so it contributes far less than "
    "its weight suggests. Motion's ceiling was 1.0 against a real range of "
    "~0.09, so a 25% weight delivered ~7% of the score.\n"
    "Changing a ceiling changes every score already computed. See CEILINGS.md."
)


def _pretty(key: str) -> str:
    return key.replace("_", " ").capitalize()


def _observed_hint(entry: dict | None) -> str:
    """One-line 'what this library produces' note for a ceiling field."""
    if not entry:
        return "library: not analysed yet"
    text = f"library: median {entry['median']:.3g} · max {entry['max']:.3g}"
    clamped = entry.get("n_clamped") or 0
    if clamped:
        text += f"  ⚠ {clamped} at ceiling"
    elif entry.get("pct_of_ceiling") is not None:
        text += f"  ({entry['pct_of_ceiling']:.0f}% of scale)"
    return text


class SettingsDialog(QDialog):
    """Scoring settings. `config` holds the edited copy once accepted."""

    def _observed_distributions(self) -> dict:
        """What the indexed library produces per scaled metric, or {}.

        Best-effort and never fatal: the dialog must open with no index, no
        library root, or no analysed episodes — it just shows no figures then.
        """
        try:
            from analyzer.db import ceiling_distributions
            conn = self.parent()._db()          # MainWindow owns the handle
            if conn is None:
                return {}
            return ceiling_distributions(
                conn, self.config.get("normalization_reference_ranges", {}))
        except Exception:
            return {}

    def __init__(self, config: dict, parent=None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setFixedWidth(DIALOG_W)
        self.config = copy.deepcopy(config)
        self.rescore = False

        body = ModalDialogFrame.install(self, "Settings — Presets & Weights")

        # -- preset bar ---------------------------------------------------
        bar = QWidget()
        br = QHBoxLayout(bar)
        br.setContentsMargins(0, 0, 0, 0)
        br.setSpacing(6)
        label = QLabel("Preset:")
        label.setStyleSheet("font-weight:bold;")
        br.addWidget(label)
        self._preset = QComboBox()
        self._preset.addItems(sorted(self.config.get("presets", {})))
        br.addWidget(self._preset, 1)
        self._delete = QPushButton("Delete")
        self._delete.clicked.connect(self._delete_preset)
        br.addWidget(self._delete)
        body.addWidget(bar)

        self._preset_note = QLabel("")
        self._preset_note.setProperty("role", "dim")
        self._preset_note.setWordWrap(True)
        body.addWidget(self._preset_note)

        # -- the two fieldsets, side by side -------------------------------
        pair = QWidget()
        pr = QHBoxLayout(pair)
        pr.setContentsMargins(0, 0, 0, 0)
        pr.setSpacing(6)

        weights_box = QGroupBox("Sensory Load Weights")
        wgrid = QGridLayout(weights_box)
        wgrid.setContentsMargins(8, 6, 8, 6)
        wgrid.setVerticalSpacing(3)
        self._weights: dict[str, QLineEdit] = {}
        for r, key in enumerate(self.config.get("sensory_load_weights", {})):
            wgrid.addWidget(QLabel(WEIGHT_LABEL.get(key, _pretty(key))), r, 0)
            edit = QLineEdit()
            edit.setFixedWidth(FIELD_W)
            edit.setAlignment(Qt.AlignRight)
            edit.textChanged.connect(self._sync_total)
            self._weights[key] = edit
            wgrid.addWidget(edit, r, 1)
            wgrid.addWidget(QLabel("%"), r, 2)
        self._total = QLabel("")
        self._total.setAlignment(Qt.AlignRight)
        wgrid.addWidget(self._total, len(self._weights), 0, 1, 3)
        wgrid.setColumnStretch(0, 1)
        pr.addWidget(weights_box, 1)

        ceilings_box = QGroupBox("Normalization Ceilings (max)")
        cgrid = QGridLayout(ceilings_box)
        cgrid.setContentsMargins(8, 6, 8, 6)
        cgrid.setVerticalSpacing(3)
        self._ceilings: dict[str, QLineEdit] = {}
        ranges = self.config.get("normalization_reference_ranges", {})
        observed = self._observed_distributions()
        for r, key in enumerate(ranges):
            cgrid.addWidget(QLabel(CEILING_LABEL.get(key, _pretty(key))), r, 0)
            edit = QLineEdit()
            edit.setFixedWidth(FIELD_W)
            edit.setAlignment(Qt.AlignRight)
            self._ceilings[key] = edit
            cgrid.addWidget(edit, r, 1)
            # A ceiling is only choosable against evidence. Show what this
            # library actually produces, right beside the box that sets the
            # top of the scale — see CEILINGS.md.
            hint = QLabel(_observed_hint(observed.get(key)))
            hint.setProperty("role", "dim")
            cgrid.addWidget(hint, r, 2)
        cgrid.setColumnStretch(0, 1)
        pr.addWidget(ceilings_box, 1)
        body.addWidget(pair)

        callout = QLabel(CEILING_NOTE)
        callout.setProperty("callout", "warn")
        callout.setWordWrap(True)
        body.addWidget(callout)

        # -- speech --------------------------------------------------------
        speech_box = QGroupBox("Speech Analysis")
        sv = QVBoxLayout(speech_box)
        sv.setContentsMargins(8, 6, 8, 6)
        sv.setSpacing(4)
        self._whisper = QCheckBox("Auto-transcribe with Whisper when no "
                                  "caption file is found")
        sv.addWidget(self._whisper)
        model_row = QWidget()
        mr = QHBoxLayout(model_row)
        mr.setContentsMargins(0, 0, 0, 0)
        mr.setSpacing(6)
        mr.addWidget(QLabel("Model size:"))
        self._model = QComboBox()
        self._model.addItems(WHISPER_MODELS)
        mr.addWidget(self._model)
        hint = QLabel("slow — roughly 2–5 min per episode")
        hint.setProperty("role", "dim")
        mr.addWidget(hint)
        mr.addStretch(1)
        sv.addWidget(model_row)
        note = QLabel(
            "Caption files are instant; Whisper only runs when none is found. "
            "For words per minute and speech density, tiny or base is usually "
            "enough — an occasional misheard word barely moves a word count. "
            "Larger models matter only if the transcript itself must be "
            "readable. Episodes already in the cache must be re-analysed after "
            "turning this on: this is a measurement setting, not a scoring one.")
        note.setProperty("role", "dim")
        note.setWordWrap(True)
        sv.addWidget(note)
        self._whisper.toggled.connect(self._model.setEnabled)
        body.addWidget(speech_box)
        body.addStretch(1)

        # -- action bar -----------------------------------------------------
        action = ModalDialogFrame.add_action_bar(self)
        action.addStretch(1)
        save_preset = QPushButton("Save as Preset…")
        save_preset.clicked.connect(self._save_preset)
        action.addWidget(save_preset)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        action.addWidget(cancel)
        apply_btn = QPushButton("Apply && Re-score")
        apply_btn.setProperty("primary", "true")
        apply_btn.setDefault(True)
        apply_btn.clicked.connect(self._apply)
        action.addWidget(apply_btn)

        self._preset.currentTextChanged.connect(self._load_preset)
        self._select_matching_preset()

    # -- presets ----------------------------------------------------------
    def _select_matching_preset(self) -> None:
        """Show the preset whose values the config currently holds."""
        current = self.config.get("sensory_load_weights", {})
        for name, preset in self.config.get("presets", {}).items():
            if preset.get("sensory_load_weights") == current:
                self._preset.setCurrentText(name)
                self._load_preset(name)
                return
        self._fill_from(self.config)
        self._preset_note.setText("Custom — not one of the saved presets.")

    def _load_preset(self, name: str) -> None:
        preset = self.config.get("presets", {}).get(name)
        if not preset:
            return
        self._fill_from(preset)
        self._preset_note.setText(preset.get("description", ""))
        # A built-in preset is part of the shared config and cannot be removed.
        self._delete.setEnabled(not preset.get("builtin", False))

    def _fill_from(self, source: dict) -> None:
        for key, edit in self._weights.items():
            value = source.get("sensory_load_weights", {}).get(key, 0.0)
            edit.setText(f"{value * 100:.1f}")
        ranges = source.get("normalization_reference_ranges", {})
        for key, edit in self._ceilings.items():
            edit.setText(f"{ranges.get(key, {}).get('max', 0.0):g}")
        self._whisper.setChecked(
            bool(self.config.get("speech_transcription_enabled", False)))
        self._model.setCurrentText(
            str(self.config.get("speech_whisper_model", "base")))
        self._model.setEnabled(self._whisper.isChecked())
        self._sync_total()

    def _delete_preset(self) -> None:
        name = self._preset.currentText()
        if not ConfirmDialog.ask(
                self, "Delete Preset",
                f"Delete the preset “{name}”?",
                "The weights and ceilings saved under this name are removed. "
                "Nothing is re-scored until you apply a different preset, and "
                "no measurement is affected.",
                confirm_text="Delete Preset"):
            return
        self.config.get("presets", {}).pop(name, None)
        self._preset.removeItem(self._preset.currentIndex())

    def _save_preset(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Save as Preset", "Name:")
        if not ok or not name.strip():
            return
        values = self._collect()
        if values is None:
            return
        self.config.setdefault("presets", {})[name.strip()] = {
            "builtin": False,
            "description": "Saved from the current values.",
            "sensory_load_weights": values["sensory_load_weights"],
            "normalization_reference_ranges":
                values["normalization_reference_ranges"],
        }
        if self._preset.findText(name.strip()) < 0:
            self._preset.addItem(name.strip())
        self._preset.setCurrentText(name.strip())

    # -- values -----------------------------------------------------------
    def _sync_total(self) -> None:
        total = 0.0
        for edit in self._weights.values():
            try:
                total += float(edit.text() or 0)
            except ValueError:
                self._total.setText("Total: —")
                self._total.setStyleSheet(f"color:{color('warn_text')};")
                return
        ok = abs(total - 100.0) < 0.05
        self._total.setText(f"Total: {total:.1f}%" + (" ✓" if ok else ""))
        self._total.setStyleSheet(
            f"color:{color('valid_ok') if ok else color('warn_text')};"
            "font-weight:bold;")

    def _collect(self) -> dict | None:
        """Read the fields back, or explain what is wrong and return None."""
        weights, total = {}, 0.0
        for key, edit in self._weights.items():
            try:
                pct = float(edit.text())
            except ValueError:
                QMessageBox.warning(
                    self, "Settings",
                    f"{WEIGHT_LABEL.get(key, key)} is not a number.")
                return None
            weights[key] = pct / 100.0
            total += pct
        if abs(total - 100.0) >= 0.05:
            QMessageBox.warning(
                self, "Settings",
                f"The weights total {total:.1f}%, not 100%.\n\n"
                f"A composite of weights that do not sum to 1 is not on the "
                f"0–1 scale the score claims to be on.")
            return None

        ranges = copy.deepcopy(
            self.config.get("normalization_reference_ranges", {}))
        for key, edit in self._ceilings.items():
            try:
                ceiling = float(edit.text())
            except ValueError:
                QMessageBox.warning(
                    self, "Settings",
                    f"{CEILING_LABEL.get(key, key)} is not a number.")
                return None
            if ceiling <= ranges.get(key, {}).get("min", 0.0):
                QMessageBox.warning(
                    self, "Settings",
                    f"{CEILING_LABEL.get(key, key)} must be above its "
                    f"minimum, or every episode normalises to the same value.")
                return None
            ranges.setdefault(key, {"min": 0.0})["max"] = ceiling
        return {"sensory_load_weights": weights,
                "normalization_reference_ranges": ranges}

    def _apply(self) -> None:
        values = self._collect()
        if values is None:
            return
        self.config.update(values)
        self.config["speech_transcription_enabled"] = self._whisper.isChecked()
        self.config["speech_whisper_model"] = self._model.currentText()
        self.rescore = True
        self.accept()
