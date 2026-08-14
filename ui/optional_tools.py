"""
ui/optional_tools.py — Optional tools: what an extra download buys, and costs.

Some measurement tools need a dependency CMAT does not bundle. TransNetV2, for
example, brings roughly 2 GB of PyTorch with it. That is a real cost, so the
screen states it before offering the button rather than after.

**This screen argues both sides on purpose.** `analyzer.optional_tools` gives
each tool `benefits`, `costs` and `caveats`, and all three are shown with equal
weight. TransNetV2's own caveats include that its published benchmarks are on
live-action video and its accuracy on ANIMATION is unverified — which, for a
children's-television tool, is the single most important thing about it. A
screen that showed only the F1 scores would be selling it.

The exact pip command is shown before it runs. Installing is the one thing
here that changes the machine, so the user sees precisely what will happen.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QGroupBox, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from analyzer.optional_tools import (
    OPTIONAL_TOOLS, OptionalTool, install_command, install_tool,
)
from ui.modal import ModalDialogFrame

DIALOG_W = 720
DIALOG_H = 620


class InstallWorker(QThread):
    """pip, off the interface thread, streaming its output as it goes."""

    line = Signal(str)
    finished_ok = Signal(bool)

    def __init__(self, tool: OptionalTool) -> None:
        super().__init__()
        self._tool = tool

    def run(self) -> None:
        ok = install_tool(self._tool, line_cb=self.line.emit)
        self.finished_ok.emit(ok)


class ToolPanel(QGroupBox):
    """One tool: what it does, what it buys, what it costs, what to watch."""

    def __init__(self, tool: OptionalTool, on_install) -> None:
        super().__init__(tool.name)
        self._tool = tool
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        one_liner = QLabel(tool.one_liner)
        one_liner.setWordWrap(True)
        lay.addWidget(one_liner)

        head = QHBoxLayout()
        head.setSpacing(6)
        self._status = QLabel("")
        self._status.setProperty("role", "dim")
        head.addWidget(self._status, 1)
        self._button = QPushButton("Install")
        self._button.clicked.connect(lambda: on_install(tool))
        head.addWidget(self._button)
        lay.addLayout(head)

        lay.addWidget(self._section("What it does", tool.what_it_does))
        # Benefits, costs and caveats carry the same weight on screen. The
        # caveats are where "unverified on animation" lives, and for this
        # project that outranks the benchmark numbers above it.
        for title, items in (("What it buys you", tool.benefits),
                             ("What it costs", tool.costs),
                             ("What to watch out for", tool.caveats)):
            if items:
                lay.addWidget(self._bullets(title, items))

        footer = QLabel(
            f"Licence: {tool.license}   ·   Disk: "
            f"{tool.disk_estimate or 'unknown'}   ·   {tool.docs_url}")
        footer.setWordWrap(True)
        footer.setProperty("role", "dim")
        footer.setTextInteractionFlags(footer.textInteractionFlags())
        lay.addWidget(footer)

        command = QLabel("Command: " + " ".join(install_command(tool)))
        command.setWordWrap(True)
        command.setProperty("role", "dim")
        lay.addWidget(command)

        self.refresh()

    @staticmethod
    def _section(title: str, body: str) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        head = QLabel(title)
        head.setStyleSheet("font-weight:bold;")
        lay.addWidget(head)
        text = QLabel(body)
        text.setWordWrap(True)
        lay.addWidget(text)
        return page

    @staticmethod
    def _bullets(title: str, items: list[str]) -> QWidget:
        return ToolPanel._section(
            title, "\n".join(f"•  {item}" for item in items))

    def refresh(self) -> None:
        if self._tool.is_available():
            version = self._tool.version()
            self._status.setText(
                f"Installed{f' — version {version}' if version else ''}. It is "
                f"selectable in Measurement settings.")
            self._button.setEnabled(False)
            self._button.setText("Installed")
        else:
            self._status.setText("Not installed.")
            self._button.setEnabled(True)
            self._button.setText("Install")

    def set_busy(self, busy: bool) -> None:
        self._button.setEnabled(not busy and not self._tool.is_available())
        if busy:
            self._button.setText("Installing…")


class OptionalToolsDialog(QDialog):
    """The optional-dependency registry, with an install log."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.resize(DIALOG_W, DIALOG_H)
        self._worker: InstallWorker | None = None

        body = ModalDialogFrame.install(self, "Optional tools",
                                        buttons=("min", "max", "close"))

        intro = QLabel(
            "These are not part of CMAT's validated core. Each one is an "
            "extra download that makes another measurement tool selectable — "
            "and each states what it costs and what has not been checked "
            "about it, because a tool that has not been graded on your "
            "material is not an improvement until you grade it.")
        intro.setWordWrap(True)
        intro.setProperty("role", "dim")
        body.addWidget(intro)

        inner = QWidget()
        column = QVBoxLayout(inner)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)
        self._panels = [ToolPanel(tool, self._install)
                        for tool in OPTIONAL_TOOLS]
        for panel in self._panels:
            column.addWidget(panel)
        if not self._panels:
            column.addWidget(QLabel("No optional tools are registered."))
        column.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        body.addWidget(scroll, 1)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(140)
        self._log.setPlaceholderText(
            "pip output appears here while a tool installs.")
        body.addWidget(self._log)

        row = ModalDialogFrame.add_action_bar(self)
        row.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        row.addWidget(close)

    def _install(self, tool: OptionalTool) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._log.clear()
        for panel in self._panels:
            panel.set_busy(True)
        self._worker = InstallWorker(tool)
        self._worker.line.connect(self._log.appendPlainText)
        self._worker.finished_ok.connect(self._done)
        self._worker.start()

    def _done(self, ok: bool) -> None:
        # NOT `self._worker = None`. This runs in a slot connected to the
        # worker's own signal, so dropping the last reference here frees the
        # QThread while it is still emitting — the process dies with no
        # traceback. Guards use isRunning(); the object is released when the
        # next run replaces it.
        for panel in self._panels:
            panel.set_busy(False)
            panel.refresh()
        self._log.appendPlainText(
            "\nInstalled. It is now selectable in Measurement settings."
            if ok else
            "\nThe install did not complete. The output above says why; "
            "nothing about CMAT has changed.")
