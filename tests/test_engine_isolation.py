"""
The engine must import no GUI framework.

This is the architectural property the whole project rests on: it is what made
the Tkinter → PySide6 move a presentation rewrite rather than an application
rewrite, and it is what lets `cli.py`, the Qt build, the PDF export and the
static site all be thin layers over one engine.

It held for months by discipline alone. A convenience import of Qt into an
engine module would break it silently — nothing would fail, the coupling would
simply exist — so it is checked here rather than trusted.
"""

from __future__ import annotations

import ast
import pathlib

FORBIDDEN = {"tkinter", "PySide6", "PyQt5", "PyQt6", "PySide2", "wx", "kivy"}

ENGINE = pathlib.Path(__file__).resolve().parent.parent / "analyzer"


def _imports(path: pathlib.Path) -> set[str]:
    """Every top-level module name imported by *path*, including inside
    functions — a deferred import is still a dependency."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return found


def test_engine_imports_no_gui_framework():
    offenders = {}
    for module in sorted(ENGINE.rglob("*.py")):
        bad = _imports(module) & FORBIDDEN
        if bad:
            offenders[module.name] = sorted(bad)
    assert offenders == {}, (
        f"analyzer/ must import no GUI framework, but {offenders} do. "
        f"Move the code needing it into a front-end; see ARCHITECTURE.md §5."
    )


def test_report_renders_without_qt():
    """ui/report.py is the one UI module the engine's outputs flow through.

    It has no Qt import on purpose, so it stays testable headless and can back
    the PDF export and the static site as well as the Qt view.
    """
    report = ENGINE.parent / "ui" / "report.py"
    assert not (_imports(report) & FORBIDDEN)


def test_tokens_import_no_framework():
    """One palette, shared by both front-ends — so it may import neither."""
    tokens = ENGINE.parent / "ui" / "tokens.py"
    assert not (_imports(tokens) & FORBIDDEN)
