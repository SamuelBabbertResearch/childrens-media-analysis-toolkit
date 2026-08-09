"""
ui/theme.py — fonts and the Qt stylesheet, built from ui.tokens.

Why this is shorter than its Tkinter counterpart: Qt has a real stylesheet
engine, so most of what gui_theme.py had to do by hand — gradients, hover and
pressed states, borders on individual edges, header styling — is declarative
here. The tokens are identical; only the rendering differs.

Two things Qt gives that Tk could not:
  * Real gradients and per-state styling on standard widgets, so the Aqua-era
    look does not need a hand-drawn canvas control for every button.
  * Genuine HTML/CSS rendering in QTextBrowser, which is how the analysis
    report gets MediaWiki tables without being redrawn as widgets.

DPI is handled by Qt itself. Nothing here calls SetProcessDpiAwarenessContext;
Qt 6 is per-monitor aware by default and scales device-independent pixels for
us, so sizes below are written once and are correct at 100%, 150% and 200%.
"""

from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from ui.tokens import (
    COLORS,
    FONT_PT,
    MONO_FAMILY_PREFERENCE,
    UI_FAMILY_PREFERENCE,
    color,
)

_ui_family: str | None = None
_mono_family: str | None = None


def _first_available(preference, fallback: str) -> str:
    """First installed family from *preference*.

    QFontDatabase needs a live QApplication; calling it earlier aborts the
    process outright rather than raising, which is a miserable thing to debug.
    Guard it and fall back to naming the first choice — Qt substitutes a
    reasonable face if it is not installed.
    """
    if QApplication.instance() is None:
        return preference[0] if preference else fallback
    try:
        available = set(QFontDatabase.families())
    except Exception:
        return fallback
    for candidate in preference:
        if candidate in available:
            return candidate
    return fallback


def ui_family() -> str:
    global _ui_family
    if _ui_family is None:
        _ui_family = _first_available(UI_FAMILY_PREFERENCE, "Segoe UI")
    return _ui_family


def mono_family() -> str:
    global _mono_family
    if _mono_family is None:
        _mono_family = _first_available(MONO_FAMILY_PREFERENCE, "Courier New")
    return _mono_family


def font(role: str = "body", bold: bool = False, mono: bool = False) -> QFont:
    """A QFont in POINTS. Qt scales points for the display; do not use pixels."""
    f = QFont(mono_family() if mono else ui_family(),
              FONT_PT.get(role, FONT_PT["body"]))
    f.setBold(bold)
    return f


def stylesheet() -> str:
    """The application stylesheet, interpolated from the shared tokens."""
    c = COLORS
    pt = FONT_PT
    fam = ui_family()
    return f"""
/* ---------------------------------------------------------------- base -- */
QWidget {{
    background: {c['window_bg']};
    color: {c['text']};
    font-family: "{fam}";
    font-size: {pt['body']}pt;
}}
QMainWindow, QDialog {{ background: {c['window_bg']}; }}

QLabel {{ background: transparent; }}
QLabel[role="title"]   {{ font-size: {pt['title']}pt; font-weight: bold; }}
QLabel[role="heading"] {{ font-size: {pt['heading']}pt; font-weight: bold; }}
QLabel[role="dim"]     {{ color: {c['text_dim']}; font-size: {pt['small']}pt; }}
QLabel[role="faint"]   {{ color: {c['text_faint']}; font-size: {pt['small']}pt; }}

/* ------------------------------------------------------------ toolbar -- */
QToolBar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {c['chrome_top']}, stop:1 {c['chrome_bottom']});
    border: none;
    border-bottom: 1px solid {c['chrome_line']};
    spacing: 6px;
    padding: 4px 8px;
}}
QStatusBar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {c['chrome_top']}, stop:1 {c['chrome_bottom']});
    border-top: 1px solid {c['chrome_line']};
    color: {c['text_dim']};
}}
QStatusBar::item {{ border: none; }}

/* ------------------------------------------------------------ buttons -- */
/* The Aqua-era bevel, declarative: a vertical gradient, a hairline border,
   and a lighter top edge. In Tk this needed a hand-drawn canvas widget. */
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {c['control_top']}, stop:1 {c['control_bottom']});
    border: 1px solid {c['control_border']};
    border-top-color: {c['control_gloss']};
    border-radius: 3px;
    padding: 3px 12px;
    min-height: 18px;
}}
QPushButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {c['control_hover_top']}, stop:1 {c['control_hover_bottom']});
}}
QPushButton:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {c['control_pressed_top']}, stop:1 {c['control_pressed_bottom']});
}}
QPushButton:disabled {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {c['control_disabled_top']},
                stop:1 {c['control_disabled_bottom']});
    color: {c['text_disabled']};
    border-color: {c['hairline']};
}}
QPushButton:focus {{ border: 1px solid {c['accent']}; }}
/* One default button per dialog, as Aqua had. */
QPushButton[primary="true"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #5b9ae4, stop:1 {c['accent_dark']});
    border: 1px solid {c['accent_dark']};
    color: {c['text_on_accent']};
    font-weight: bold;
}}
QPushButton[primary="true"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #6ba7ea, stop:1 #1a63c8);
}}

/* --------------------------------------------------------------- tabs -- */
QTabWidget::pane {{
    border: 1px solid {c['chrome_line']};
    background: {c['panel_bg']};
    top: -1px;
}}
QTabBar::tab {{
    background: {c['tab_bg']};
    color: {c['tab_fg']};
    border: 1px solid {c['chrome_line']};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 5px 14px;
    margin-right: 2px;
}}
QTabBar::tab:hover     {{ background: {c['tab_active']}; }}
QTabBar::tab:selected  {{
    background: {c['panel_bg']};
    color: {c['text']};
    margin-bottom: -1px;
    padding-bottom: 6px;
}}

/* ------------------------------------------------- inputs and combos -- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {{
    background: {c['panel_bg']};
    border: 1px solid {c['control_border']};
    border-top-color: #7d8086;
    border-radius: 3px;
    padding: 2px 5px;
    min-height: 18px;
    selection-background-color: {c['accent']};
    selection-color: {c['text_on_accent']};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QPlainTextEdit:focus {{ border: 1px solid {c['accent']}; }}
QComboBox::drop-down {{ border: none; width: 16px; }}
QComboBox QAbstractItemView {{
    background: {c['panel_bg']};
    border: 1px solid {c['mw_border']};
    selection-background-color: {c['accent']};
    selection-color: {c['text_on_accent']};
}}

/* ------------------------------------------------- wikitable-style views */
QTreeView, QTableView, QListView {{
    background: {c['mw_bg']};
    alternate-background-color: {c['mw_subtle_bg']};
    border: 1px solid {c['mw_border']};
    gridline-color: {c['mw_row_line']};
    selection-background-color: {c['row_selected_bg']};
    selection-color: {c['text']};
    outline: none;
}}
QTreeView::item, QTableView::item {{ padding: 3px 4px; }}
QTreeView::item:selected, QTableView::item:selected {{
    background: {c['row_selected_bg']};
    color: {c['text']};
}}
QHeaderView::section {{
    background: {c['mw_header_bg']};
    color: {c['text']};
    border: none;
    border-right: 1px solid {c['mw_border']};
    border-bottom: 1px solid {c['mw_border']};
    padding: 4px 6px;
    font-weight: bold;
}}
QHeaderView::section:hover {{ background: {c['panel_header']}; }}

/* ---------------------------------------------------------- scrollbars -- */
QScrollBar:vertical   {{ background: {c['surface_bottom']}; width: 12px;
                         margin: 0; border: none; }}
QScrollBar:horizontal {{ background: {c['surface_bottom']}; height: 12px;
                         margin: 0; border: none; }}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: #c1c4c9;
    border: 1px solid {c['chrome_line']};
    border-radius: 5px;
    min-height: 24px;
    min-width: 24px;
}}
QScrollBar::handle:hover {{ background: #a9adb3; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* --------------------------------------------------------- containers -- */
QGroupBox {{
    border: 1px solid {c['mw_border']};
    border-radius: 3px;
    margin-top: 8px;
    padding-top: 6px;
    background: {c['panel_bg']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    font-weight: bold;
    color: {c['text_dim']};
}}
QSplitter::handle {{ background: {c['chrome_bottom']}; }}
QSplitter::handle:hover {{ background: {c['accent_glow']}; }}

QTextBrowser {{
    background: {c['panel_bg']};
    border: 1px solid {c['mw_border']};
}}

/* --------------------------------------------------------- ambox note -- */
QFrame[ambox="info"] {{
    background: {c['info_bg']};
    border: 1px solid {c['info_border']};
    border-left: 4px solid {c['info_rule']};
    border-radius: 3px;
}}
QFrame[ambox="warn"] {{
    background: {c['warn_bg']};
    border: 1px solid {c['warn_border']};
    border-left: 4px solid {c['warn_rule']};
    border-radius: 3px;
}}
"""


def apply(app) -> None:
    """Apply fonts and the stylesheet to a QApplication."""
    app.setFont(font("body"))
    app.setStyle("Fusion")          # a predictable base across platforms
    app.setStyleSheet(stylesheet())
