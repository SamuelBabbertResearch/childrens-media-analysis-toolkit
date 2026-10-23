"""Startup-dialog dismissal must leave usable native window controls."""
import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog


@pytest.mark.parametrize("buttons", [("close",), ("min", "max", "close")])
def test_dialog_native_controls_preserve_modality(qapp, buttons):
    from ui.modal import ModalDialogFrame

    dialog = QDialog()
    dialog.setModal(True)
    try:
        ModalDialogFrame.install(dialog, "Native dialog", buttons)
        flags = dialog.windowFlags()
        assert dialog.isModal()
        assert flags & Qt.WindowType_Mask == Qt.Dialog
        assert flags & Qt.WindowTitleHint
        assert not flags & Qt.FramelessWindowHint
        assert bool(flags & Qt.WindowMaximizeButtonHint) == ("max" in buttons)
        assert bool(flags & Qt.WindowMinimizeButtonHint) == ("min" in buttons)
    finally:
        dialog.deleteLater()


def test_closing_welcome_leaves_main_window_movable_and_maximizable(qapp, monkeypatch):
    from ui import main_window, welcome

    monkeypatch.setattr(main_window, "get_pref", lambda *args, **kwargs: False)
    monkeypatch.setattr(welcome, "set_pref", lambda *args, **kwargs: None)
    win = main_window.MainWindow()
    observed = []

    def close_popup():
        dialog = qapp.activeModalWidget()
        observed.append(isinstance(dialog, welcome.WelcomeDialog))
        if dialog is not None:
            dialog.close()

    try:
        win.show()
        QTimer.singleShot(0, close_popup)
        win.show_welcome()
        assert observed == [True]
        assert qapp.activeModalWidget() is None
        assert win.isEnabled()
        assert win.windowFlags() & Qt.WindowTitleHint
        assert win.windowFlags() & Qt.WindowMaximizeButtonHint
        assert not win.windowFlags() & Qt.FramelessWindowHint
        win.showMaximized()
        qapp.processEvents()
        assert win.isMaximized()
        win.showNormal()
        qapp.processEvents()
        assert not win.isMaximized()
        assert win.isEnabled()
    finally:
        win.close()
        win.deleteLater()
