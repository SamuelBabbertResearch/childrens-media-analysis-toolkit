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
    mono = mono_family()
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
                stop:0 {c['toolbar_top']}, stop:1 {c['toolbar_bottom']});
    border: none;
    border-bottom: 1px solid {c['panel_border']};
    spacing: 6px;
    padding: 4px 8px;
}}
/* Per-tab controls, one step lighter than the main toolbar so the hierarchy
   reads: window chrome, then tab strip, then this. */
QFrame[subbar="true"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {c['subbar_top']}, stop:1 {c['subbar_bottom']});
    border: none;
    border-bottom: 1px solid {c['panel_border']};
}}
QStatusBar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {c['statusbar_top']}, stop:1 {c['statusbar_bottom']});
    border-top: 1px solid {c['chrome_line']};
    color: {c['text']};
    font-size: {pt['small']}pt;
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
/* One default button per window, as the period convention had it. More than
   one and it stops meaning "this is the action you probably want". */
QPushButton[primary="true"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {c['aqua_top']}, stop:1 {c['aqua_bottom']});
    border: 1px solid {c['aqua_border']};
    color: {c['text_on_accent']};
    font-weight: bold;
}}
QPushButton[primary="true"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #55a8e8, stop:1 #1470d4);
}}
QPushButton[primary="true"]:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {c['aqua_pressed_top']},
                stop:1 {c['aqua_pressed_bottom']});
}}
QPushButton[primary="true"]:disabled {{
    background: {c['control_disabled_bottom']};
    border-color: {c['hairline']};
    color: {c['text_disabled']};
}}

/* ------------------------------------------------------------ menu bar -- */
QMenuBar {{
    background: {c['menu_bg']};
    border-bottom: 1px solid {c['menu_line']};
    padding: 1px 4px;
}}
QMenuBar::item {{ padding: 2px 8px; border-radius: 2px; }}
QMenuBar::item:selected {{
    background: {c['accent']};
    color: {c['text_on_accent']};
}}
QMenu {{
    background: {c['panel_bg']};
    border: 1px solid {c['mw_border']};
    padding: 2px;
}}
QMenu::item {{ padding: 4px 22px 4px 18px; }}
QMenu::item:selected {{
    background: {c['accent']};
    color: {c['text_on_accent']};
}}
QMenu::separator {{
    height: 1px;
    background: {c['hairline']};
    margin: 3px 6px;
}}

/* --------------------------------------------------------------- tabs -- */
QTabWidget::pane {{
    border: 1px solid {c['panel_border']};
    background: {c['panel_bg']};
    top: -1px;
}}
QTabBar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {c['tabstrip_top']}, stop:1 {c['tabstrip_bottom']});
}}
QTabBar::tab {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {c['tab_inactive_top']},
                stop:1 {c['tab_inactive_bottom']});
    color: {c['tab_fg']};
    border: 1px solid {c['panel_border']};
    border-bottom: none;
    border-top-left-radius: 3px;
    border-top-right-radius: 3px;
    padding: 4px 12px;
    margin-right: 1px;
}}
QTabBar::tab:hover {{ background: {c['tab_active']}; }}
/* The accent rule along the top edge is what marks the active tab; the
   fill alone is too quiet once several tabs are open. */
QTabBar::tab:selected {{
    background: {c['panel_bg']};
    color: {c['text']};
    font-weight: bold;
    border-top: 2px solid {c['accent']};
    margin-bottom: -1px;
    padding-bottom: 5px;
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
    alternate-background-color: {c['table_alt_row']};
    /* Sunken frame: Qt ignores inset box-shadow, but a darker top edge
       against three lighter ones reads the same way. */
    border: 1px solid {c['panel_border']};
    border-top-color: {c['list_sunken_edge']};
    gridline-color: {c['table_cell_line']};
    outline: none;
}}
QTreeView::item, QTableView::item, QListView::item {{ padding: 2px 4px; }}
QTreeView::item:hover, QTableView::item:hover {{
    background: {c['row_hover']};
}}
/* Choosing an item uses the solid accent; a table of FIGURES uses the light
   wash instead, so the numbers keep their contrast. See ui/DESIGN.md §3. */
QListView::item:selected {{
    background: {c['accent']};
    color: {c['text_on_accent']};
}}
QTreeView::item:selected, QTableView::item:selected {{
    background: {c['row_selected_bg']};
    color: {c['text']};
}}
QHeaderView::section {{
    background: {c['table_header']};
    color: {c['text']};
    border: none;
    border-right: 1px solid {c['panel_border']};
    border-bottom: 1px solid {c['panel_border']};
    padding: 3px 6px;
    font-weight: bold;
}}
QHeaderView::section:hover {{ background: {c['panel_header']}; }}

/* ------------------------------------------------------------- panels -- */
QFrame[panel="true"] {{
    background: {c['panel_bg']};
    border: 1px solid {c['panel_border']};
    border-radius: 2px;
}}
QLabel[panelHeader="true"] {{
    background: {c['panel_header']};
    border-bottom: 1px solid {c['panel_border']};
    padding: 3px 6px;
    font-weight: bold;
}}
/* Monospace, inset, so a long path reads as a value rather than prose. */
QLabel[pathDisplay="true"] {{
    font-family: "{mono}";
    font-size: {pt['small']}pt;
    color: {c['path_text']};
    background: {c['panel_bg']};
    border: 1px solid {c['control_border']};
    border-top-color: {c['control_border_dark']};
    border-radius: 2px;
    padding: 1px 6px;
}}

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
