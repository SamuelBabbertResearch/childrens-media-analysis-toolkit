"""Regression for long paths and inactive tabs forcing controls off-screen."""
from pathlib import Path

from PySide6.QtCore import QPoint
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QPushButton
import pytest


def test_long_library_path_and_constructs_controls_fit_window(qapp, monkeypatch):
    from ui import main_window, theme

    for name in ("segoeui.ttf", "segoeuib.ttf", "consola.ttf"):
        font = Path("C:/Windows/Fonts") / name
        if font.is_file():
            QFontDatabase.addApplicationFont(str(font))
    if not QFontDatabase.families():
        pytest.skip("Window bounds require real fonts")
    monkeypatch.setattr(main_window, "get_pref", lambda *args, **kwargs: False)
    theme.apply(qapp)
    win = main_window.MainWindow()
    path = "C:/Research/" + "Long institutional folder/" * 15 + "Stimuli"
    try:
        win._root_label.setText(path)
        win._scope_pick.addItem("Whole library")
        win.resize(1280, 820)
        win.show()
        qapp.processEvents()
        assert win.width() == 1280
        assert win.minimumSizeHint().width() <= 1280
        assert win._root_label.toolTip() == path
        assert win._root_label.accessibleName() == path
        assert "\u2026" in win._root_label.text()
        for button in win.findChildren(QPushButton):
            if button.text() in {"Settings...", "Episode Sampler..."}:
                assert button.isVisible()
                origin = button.mapTo(win, QPoint(0, 0))
                assert 0 <= origin.x() < origin.x() + button.width() <= win.width()
        win._tabs.setCurrentWidget(win._constructs)
        qapp.processEvents()
        assert win.width() == 1280
        for button in (win._constructs._btn_zoom_in, win._constructs._btn_zoom_reset):
            assert button.isVisible()
            origin = button.mapTo(win, QPoint(0, 0))
            assert 0 <= origin.x() < origin.x() + button.width() <= win.width()
    finally:
        win.close()
        win.deleteLater()
