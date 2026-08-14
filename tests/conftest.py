"""
Shared test fixtures.

The Tk root is session-scoped on purpose. Creating and destroying a root per
test looks tidier but fails intermittently once a run has churned through a
dozen of them — Tk does not fully release interpreter state, and the failure
surfaces as a TclError that a per-test fixture then swallows as "no display".
The symptom is a test that passes alone and silently SKIPS in a full run,
which is worse than a failure because nobody notices.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session")
def tk_root():
    """One hidden Tk root for the whole session, or skip if there is no display."""
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available")
    root.withdraw()
    try:
        root.tk.call("tk", "scaling", root.winfo_fpixels("1i") / 72.0)
    except Exception:
        pass
    yield root
    try:
        root.destroy()
    except Exception:
        pass


@pytest.fixture(scope="session")
def qapp():
    """One offscreen QApplication for the whole session.

    Session-scoped for a harder reason than the Tk root: Qt permits exactly one
    QApplication per process and destroying it leaves widgets pointing at freed
    state, so it cannot be per-test. Offscreen so the suite needs no display.
    """
    widgets = pytest.importorskip("PySide6.QtWidgets")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = widgets.QApplication.instance() or widgets.QApplication([])
    yield app


@pytest.fixture
def root(tk_root):
    """Per-test view of the shared root, cleaned of the previous test's widgets."""
    for child in list(tk_root.winfo_children()):
        try:
            child.destroy()
        except Exception:
            pass
    return tk_root
