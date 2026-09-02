"""
ui/construct_editor.py — defining a construct, which is the one thing in the
measurement model a researcher writes rather than chooses.

`MEASUREMENT_MODEL.md` §4.1 says CMAT "ships a small starting set; researchers
add their own". `analyzer/constructs.py` made that true of the data model on
2026-08-16; until this file there was no screen for it, so the sentence was
still half a sentence.

WHAT IS EDITABLE HERE, AND WHAT DELIBERATELY IS NOT

A **construct** is a theoretical claim — a name, a definition, an honest
grounding note, and any aspects needed to keep its measures apart. All of it is
free text, because a theoretical claim is exactly the thing CMAT must not
pretend to adjudicate.

A **measure** is not editable here and there is no button for one. A measure has
to resolve to a real number from a real cached result or a real coding sheet;
one that does not is `LEARNINGS.md` shape 2 — a control whose data path is
empty — which is the defect this entire phase exists to remove. Offering "New
measure…" would reintroduce it through a nicer interface. The screen says so in
those words rather than leaving the absence to be read as an oversight, and the
route it points at is the real one: a construct of your own is operationalized
by binding shipped measures to it on the Constructs canvas.

SHIPPED CONSTRUCTS ARE SHOWN, NOT EDITABLE

Editing `pacing` in place would move what the shipped composite — and every
published score — claims to measure, while leaving every name, version and hash
intact. So a shipped construct opens read-only with the reason on screen and
**Duplicate into a construct of my own** offered as the route, matching both
`Construct.is_editable` in the engine and the locked-recipe rule on the Recipes
screen. An unavailable control must not look like a broken one (`CLAUDE.md` §4).

REDEFINING IS ALLOWED, AND IS REPORTED RATHER THAN BLOCKED

Saving a changed definition moves the construct's content hash, and every recipe
citing it then reports `redefined` through `recipes.construct_divergence()`.
Nothing here blocks that, warns modally, or quietly updates the recipes: a
divergence is not an error, and it is the same shape a diverging pinned
parameter already has. The dialog states what will happen, naming the recipes
concerned, because the researcher deciding whether to redefine is the person who
should know how many claims it touches.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from analyzer import constructs as C
from analyzer import recipes as R
from ui.modal import ConfirmDialog, ModalDialogFrame

DIALOG_W = 620


class AspectRow(QWidget):
    """One aspect: a name and a definition, removable."""

    def __init__(self, aspect: C.Aspect | None, on_remove) -> None:
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        # The key is generated once from the first name and then held, exactly
        # as a construct's is: aspects are cited by key inside measures, so
        # re-deriving one from a later name would silently orphan them.
        self.key = aspect.key if aspect else ""
        self.name = QLineEdit(aspect.name if aspect else "")
        self.name.setPlaceholderText("Aspect name, e.g. Visual pacing")
        self.definition = QLineEdit(aspect.definition if aspect else "")
        self.definition.setPlaceholderText("What this facet covers")
        row.addWidget(self.name, 1)
        row.addWidget(self.definition, 2)
        remove = QPushButton("Remove")
        remove.clicked.connect(lambda: on_remove(self))
        row.addWidget(remove)

    def value(self) -> C.Aspect | None:
        name = self.name.text().strip()
        if not name:
            return None
        key = self.key or C.construct_key_for(name)
        return C.Aspect(key=key, name=name,
                        definition=self.definition.text().strip())

    def set_enabled(self, on: bool) -> None:
        self.name.setEnabled(on)
        self.definition.setEnabled(on)


class ConstructEditor(QDialog):
    """Create or edit one construct. `saved_key` is what the caller reads back."""

    def __init__(self, root: Path | None, construct: C.Construct | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setMinimumWidth(DIALOG_W)
        self._root = root
        self._construct = construct
        self._aspects: list[AspectRow] = []
        self.saved_key: str | None = None

        creating = construct is None
        editable = creating or construct.is_editable
        title = "New construct" if creating else construct.name
        body = ModalDialogFrame.install(self, title)

        intro = QLabel(
            "A construct is the theoretical thing being studied — not "
            "observable, and not a value in a video file. CMAT ships a "
            "starting set; this is where you add your own. A construct of "
            "yours is operationalized by binding shipped measures to it in a "
            "recipe, on the Constructs tab.")
        intro.setWordWrap(True)
        intro.setProperty("role", "dim")
        body.addWidget(intro)

        self._banner = QLabel("")
        self._banner.setWordWrap(True)
        self._banner.setProperty("role", "dim")
        self._banner.setVisible(False)
        body.addWidget(self._banner)

        body.addWidget(QLabel("Name:"))
        self._name = QLineEdit(construct.name if construct else "")
        self._name.setPlaceholderText("e.g. Narrative complexity")
        self._name.textEdited.connect(self._sync)
        body.addWidget(self._name)

        body.addWidget(QLabel("Definition:"))
        self._definition = QTextEdit(construct.definition if construct else "")
        self._definition.setPlaceholderText(
            "What this construct is, in the terms your study uses.")
        self._definition.setMaximumHeight(70)
        self._definition.textChanged.connect(self._sync)
        body.addWidget(self._definition)

        body.addWidget(QLabel("Grounding — where this comes from, honestly:"))
        self._grounding = QTextEdit(construct.grounding if construct else "")
        self._grounding.setPlaceholderText(
            "The literature this rests on, and what it does NOT establish. A "
            "construct CMAT ships is a starting point, never a validated "
            "mapping; one of your own has been validated by nobody yet, and "
            "saying so here is what keeps that attached to the number.")
        self._grounding.setMaximumHeight(70)
        self._grounding.textChanged.connect(self._sync)
        body.addWidget(self._grounding)

        aspect_head = QHBoxLayout()
        aspect_head.addWidget(QLabel("Aspects (optional):"))
        aspect_head.addStretch(1)
        self._btn_aspect = QPushButton("Add aspect")
        self._btn_aspect.setToolTip(
            "A facet of the construct, where one is needed to keep measures "
            "honest — pacing has visual-transitions, rhythm and "
            "scene-structure aspects so that measures of different facets are "
            "not read as measures of one thing.")
        self._btn_aspect.clicked.connect(lambda: self._add_aspect(None))
        aspect_head.addWidget(self._btn_aspect)
        body.addLayout(aspect_head)

        holder = QWidget()
        self._aspect_box = QVBoxLayout(holder)
        self._aspect_box.setContentsMargins(0, 0, 0, 0)
        self._aspect_box.setSpacing(3)
        body.addWidget(holder)
        for aspect in (construct.aspects if construct else ()):
            self._add_aspect(aspect)

        # The rule that is a rule, said on the screen rather than only in the
        # documents — the absence of a "New measure…" button is otherwise
        # indistinguishable from an unfinished screen.
        rule = QLabel(
            "Measures are not user-definable, and that is deliberate rather "
            "than unfinished. A measure has to resolve to a real number from a "
            "cached result or a coding sheet; one that cannot is a label. Bind "
            "the shipped measures to this construct on the Constructs tab.")
        rule.setWordWrap(True)
        rule.setProperty("role", "dim")
        body.addWidget(rule)

        self._effect = QLabel("")
        self._effect.setWordWrap(True)
        self._effect.setProperty("role", "dim")
        body.addWidget(self._effect)
        body.addStretch(1)

        row = ModalDialogFrame.add_action_bar(self)
        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setProperty("role", "dim")
        row.addWidget(self._status, 1)

        self._btn_duplicate = QPushButton("Duplicate into a construct of my own")
        self._btn_duplicate.clicked.connect(self._duplicate)
        self._btn_duplicate.setVisible(not editable)
        row.addWidget(self._btn_duplicate)

        self._btn_delete = QPushButton("Delete…")
        self._btn_delete.clicked.connect(self._delete)
        self._btn_delete.setVisible(
            not creating and construct is not None and construct.is_editable)
        row.addWidget(self._btn_delete)

        self._btn_save = QPushButton("Save")
        self._btn_save.setProperty("primary", "true")
        self._btn_save.clicked.connect(self._save)
        self._btn_save.setVisible(editable)
        row.addWidget(self._btn_save)

        cancel = QPushButton("Close")
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)

        if not editable:
            self._banner.setVisible(True)
            self._banner.setText(
                "This is a construct CMAT ships. It is shown in full so it can "
                "be read, and cannot be edited: the shipped composite and every "
                "published score are computed under this definition, so "
                "changing it here would move what they claim to measure while "
                "leaving their names and hashes intact. Duplicating it into a "
                "construct of your own is the route.")
            for widget in (self._name, self._definition, self._grounding,
                           self._btn_aspect):
                widget.setEnabled(False)
            for aspect_row in self._aspects:
                aspect_row.set_enabled(False)
        self._sync()

    # -- aspects ------------------------------------------------------------
    def _add_aspect(self, aspect: C.Aspect | None) -> None:
        row = AspectRow(aspect, self._remove_aspect)
        self._aspects.append(row)
        self._aspect_box.addWidget(row)
        if self._construct is not None and not self._construct.is_editable:
            row.set_enabled(False)

    def _remove_aspect(self, row: AspectRow) -> None:
        if row in self._aspects:
            self._aspects.remove(row)
        row.setParent(None)
        row.deleteLater()
        self._sync()

    # -- state --------------------------------------------------------------
    def _values(self) -> tuple[str, str, str, tuple[C.Aspect, ...]]:
        # Aspect keys are made distinct here rather than left to chance: the
        # content hash sorts aspects BY KEY, so two aspects sharing one would
        # make the hash depend on which of them sorted first — a definition
        # that changes meaning without changing text.
        aspects: list[C.Aspect] = []
        seen: set[str] = set()
        for row in self._aspects:
            aspect = row.value()
            if aspect is None:
                continue
            key, i = aspect.key, 2
            while key in seen:
                key, i = f"{aspect.key}_{i}", i + 1
            seen.add(key)
            aspects.append(C.Aspect(key=key, name=aspect.name,
                                    definition=aspect.definition))
        aspects = tuple(aspects)
        return (self._name.text().strip(),
                self._definition.toPlainText().strip(),
                self._grounding.toPlainText().strip(),
                aspects)

    def _citing_recipes(self) -> list[R.Recipe]:
        if self._construct is None or not self._root:
            return []
        return [r for r in R.list_recipes(self._root)
                if r.construct_key == self._construct.key]

    def _sync(self, *_a) -> None:
        name, definition, grounding, aspects = self._values()
        editable = self._construct is None or self._construct.is_editable
        self._btn_save.setEnabled(editable and bool(name))
        if not editable:
            self._status.setText("Read-only.")
            return
        if not name:
            self._status.setText("A construct needs a name before it can be "
                                 "saved.")
            return
        if not definition:
            self._status.setText(
                "Saving with no definition is allowed, but a construct with no "
                "definition is a label — and its content hash is taken over "
                "the definition, so it is what recipes cite as its meaning.")
        else:
            self._status.setText("")

        # What saving will actually do downstream, before it is done.
        if self._construct is None:
            self._effect.setText("")
            return
        moved = C.Construct(
            key=self._construct.key, name=name, definition=definition,
            grounding=grounding, aspects=aspects, source=C.LIBRARY,
        ).content_hash() != self._construct.content_hash()
        citing = self._citing_recipes()
        if moved and citing:
            names = ", ".join(f"“{r.name}”" for r in citing[:4])
            if len(citing) > 4:
                names += f", and {len(citing) - 4} more"
            self._effect.setText(
                f"This changes what the construct MEANS, so {len(citing)} "
                f"recipe{'' if len(citing) == 1 else 's'} citing it will "
                f"report it as redefined: {names}. That is a statement, not an "
                f"error — those recipes still describe what they always "
                f"described, and nothing about them is rewritten. Their own "
                f"versions do not move, because a construct's meaning is "
                f"recorded beside a recipe's hash rather than inside it.")
        elif moved:
            self._effect.setText(
                "This changes what the construct means. No saved recipe cites "
                "it, so nothing reports a divergence.")
        else:
            self._effect.setText(
                "Renaming only — the meaning is unchanged, so no recipe "
                "reports a divergence. The content hash covers the definition, "
                "grounding and aspects, never the name.")

    # -- actions ------------------------------------------------------------
    def _save(self) -> None:
        name, definition, grounding, aspects = self._values()
        if not name:
            return
        if self._construct is None:
            construct = C.new_construct(name, definition, grounding, aspects,
                                        root=self._root)
        else:
            construct = C.Construct(
                key=self._construct.key, name=name, definition=definition,
                grounding=grounding, aspects=aspects, source=C.LIBRARY,
                path=self._construct.path)
        try:
            C.save_construct(construct, self._root)
        except PermissionError as exc:
            QMessageBox.information(self, "Cannot save", str(exc))
            return
        self.saved_key = construct.key
        self.accept()

    def _duplicate(self) -> None:
        """A shipped construct, copied into one of the researcher's own.

        The copy gets its OWN key — `save_construct` refuses a library
        construct whose key shadows a shipped one, because recipes citing
        `pacing` would then change meaning depending on which library was open.
        """
        if self._construct is None:
            return
        name, definition, grounding, aspects = self._values()
        copy = C.new_construct(
            f"{name} (my definition)", definition,
            (f"{grounding}\n\nCopied from the construct CMAT ships. This copy "
             f"is the researcher's own and CMAT has validated it no further "
             f"than it validated the original — which is to say, not at all.")
            .strip(),
            aspects, root=self._root)
        try:
            C.save_construct(copy, self._root)
        except PermissionError as exc:                        # pragma: no cover
            QMessageBox.information(self, "Cannot save", str(exc))
            return
        self.saved_key = copy.key
        self.accept()

    def _delete(self) -> None:
        construct = self._construct
        if construct is None or not construct.is_editable:
            return
        citing = self._citing_recipes()
        detail = ("The construct file is removed. No recipe, measurement, "
                  "cached result or coding sheet is touched.")
        if citing:
            detail += (
                f" {len(citing)} recipe{'' if len(citing) == 1 else 's'} cite "
                f"it and will keep their construct key, reporting it as "
                f"missing — the key is kept rather than repaired, for the same "
                f"reason an unresolvable import is reported rather than "
                f"substituted.")
        confirm = ConfirmDialog(self, "Delete construct",
                                f"Delete “{construct.name}”?", detail=detail,
                                confirm_text="Delete")
        if confirm.exec() != QDialog.Accepted:
            return
        C.delete_construct(construct, self._root)
        self.saved_key = None
        self.accept()


class ConstructPicker(QDialog):
    """The library's constructs, shipped and researcher-defined, in one list.

    A picker rather than a manager: it exists so the Constructs tab has a place
    to put New and Edit without either screen growing its own copy of the
    editor.
    """

    def __init__(self, root: Path | None, parent=None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setMinimumWidth(DIALOG_W)
        self._root = root
        self.changed = False
        body = ModalDialogFrame.install(self, "Constructs")

        intro = QLabel(
            "Every construct this library can operationalize. The shipped set "
            "is read-only; your own can be edited and deleted. Measures are "
            "shipped and are not definable here — a construct of yours is "
            "operationalized by binding them to it in a recipe.")
        intro.setWordWrap(True)
        intro.setProperty("role", "dim")
        body.addWidget(intro)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.itemDoubleClicked.connect(lambda _i: self._open())
        self._list.currentRowChanged.connect(self._sync)
        body.addWidget(self._list, 1)

        row = ModalDialogFrame.add_action_bar(self)
        self._status = QLabel("")
        self._status.setProperty("role", "dim")
        self._status.setWordWrap(True)
        row.addWidget(self._status, 1)
        self._btn_new = QPushButton("New construct…")
        self._btn_new.clicked.connect(self._new)
        row.addWidget(self._btn_new)
        self._btn_open = QPushButton("Open…")
        self._btn_open.clicked.connect(self._open)
        row.addWidget(self._btn_open)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row.addWidget(close)

        self._reload()

    def _reload(self, select_key: str | None = None) -> None:
        self._constructs = C.all_constructs()
        self._list.blockSignals(True)
        self._list.clear()
        for construct in self._constructs:
            n = len(C.measures_for(construct.key))
            origin = ("shipped" if construct.source == C.SHIPPED
                      else "yours — editable")
            # "AVAILABLE TO BIND", not "of its own". This is the catalogue —
            # every measure the model defines for this construct — and the
            # Constructs canvas beside it says "1 measure in this recipe"
            # meaning something else entirely: how many are bound. Pacing
            # defines eight and a pacing recipe may bind one of them. The two
            # screens used the same word for the two quantities, which read as
            # a contradiction and was reported as one.
            count = (f"{n} measure{'' if n == 1 else 's'} available to bind"
                     if n else "no measures of its own — operationalized by "
                               "binding other constructs' measures")
            item = QListWidgetItem(f"{construct.name}\n   {origin} · {count}")
            item.setToolTip(construct.definition)
            self._list.addItem(item)
        self._list.blockSignals(False)
        target = 0
        if select_key:
            for i, construct in enumerate(self._constructs):
                if construct.key == select_key:
                    target = i
                    break
        self._list.setCurrentRow(target)
        self._sync()

    def current(self) -> C.Construct | None:
        i = self._list.currentRow()
        return self._constructs[i] if 0 <= i < len(self._constructs) else None

    def _sync(self, *_a) -> None:
        construct = self.current()
        self._btn_open.setEnabled(construct is not None)
        if construct is None:
            self._status.setText("")
            return
        self._status.setText(
            "Shipped — opens read-only, with Duplicate offered."
            if construct.source == C.SHIPPED else "Yours — editable.")

    def _new(self) -> None:
        if not self._root:
            QMessageBox.information(
                self, "No library",
                "Choose a root folder first — a construct is stored with the "
                "library it describes, beside the recipes that cite it.")
            return
        editor = ConstructEditor(self._root, None, self)
        if editor.exec() == QDialog.Accepted:
            self.changed = True
            self._reload(select_key=editor.saved_key)

    def _open(self) -> None:
        construct = self.current()
        if construct is None:
            return
        editor = ConstructEditor(self._root, construct, self)
        if editor.exec() == QDialog.Accepted:
            self.changed = True
            self._reload(select_key=editor.saved_key)
