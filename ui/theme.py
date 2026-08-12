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
    FONT_PX,
    METRICS,
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
    """A QFont sized in device-independent pixels.

    Qt scales these for the display, so 11px here is 11px at 100% and 16.5
    physical pixels at 150% — the reference density, preserved on any monitor.
    """
    f = QFont(mono_family() if mono else ui_family())
    f.setPixelSize(FONT_PX.get(role, FONT_PX["body"]))
    f.setBold(bold)
    return f


def stylesheet() -> str:
    """The application stylesheet, interpolated from the shared tokens."""
    c = COLORS
    pt = FONT_PX
    m = METRICS
    fam = ui_family()
    mono = mono_family()
    return f"""
/* ---------------------------------------------------------------- base -- */
QWidget {{
    background: {c['window_bg']};
    color: {c['text']};
    font-family: "{fam}";
    font-size: {pt['body']}px;
}}
QMainWindow, QDialog {{ background: {c['window_bg']}; }}

QLabel {{ background: transparent; }}
QLabel[role="title"]   {{ font-size: {pt['title']}px; font-weight: bold; }}
QLabel[role="heading"] {{ font-size: {pt['heading']}px; font-weight: bold; }}
QLabel[role="dim"]     {{ color: {c['text_dim']}; font-size: {pt['small']}px; }}
QLabel[role="faint"]   {{ color: {c['text_faint']}; font-size: {pt['small']}px; }}

/* ------------------------------------------------------------ toolbar -- */
QToolBar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {c['toolbar_top']}, stop:1 {c['toolbar_bottom']});
    border: none;
    border-bottom: 1px solid {c['panel_border']};
    spacing: 6px;
    padding: 4px 8px;
}}
/* The title strip paints itself; the toolbar hosting it must add nothing. */
QToolBar#titleBar {{
    background: transparent;
    border: none;
    padding: 0;
    spacing: 0;
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
    border-top: 1px solid {c['statusbar_line']};
    color: {c['statusbar_fg']};
    font-size: {pt['small']}px;
    padding: 3px 8px;
    min-height: {m['header_h']}px;
}}
QStatusBar::item {{ border: none; }}

/* ------------------------------------------------------------ buttons -- */
/* The Aqua-era bevel, declarative: a vertical gradient behind a hairline
   border. In Tk this needed a hand-drawn canvas widget.

   The reference draws the top highlight as an inset white box-shadow, which Qt
   has no equivalent for. It is left off rather than faked with a white
   border-top-color, which lightens the whole edge and reads as a button
   missing its top rather than a lit one. */
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {c['control_top']}, stop:1 {c['control_bottom']});
    border: 1px solid {c['control_border']};
    border-radius: {m['radius']}px;
    color: {c['control_fg']};
    font-weight: 500;
    padding: 0 8px;
    min-height: {m['control_h']}px;
    max-height: {m['control_h']}px;
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
    padding: 2px 8px;
}}
QMenuBar::item {{ padding: 1px 4px; margin: 0 6px 0 0; border-radius: 2px; }}
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
    padding-left: 6px;
    padding-top: 3px;
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
    padding: {m['tab_pad_y']}px {m['tab_pad_x']}px;
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
    padding-bottom: {m['tab_pad_y'] + 1}px;
}}

/* ------------------------------------------------- inputs and combos -- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {{
    background: {c['panel_bg']};
    border: 1px solid {c['control_border']};
    border-top-color: {c['control_border_dark']};
    border-radius: {m['radius_tight']}px;
    padding: 0 4px;
    min-height: {m['control_h']}px;
    max-height: {m['control_h']}px;
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

/* -------------------------------------------------------------- views -- */
/* The selectors are the VIEW classes, not QTreeWidget/QTableWidget. Qt
   stylesheet selectors do not match up an inheritance chain: a rule written
   for QTreeWidget applies to that subclass only and would silently miss the
   QTreeView this application actually uses. QTreeWidget is included so a rule
   holds if one is ever added, but QTreeView is the one doing the work. */
QTreeView, QTableView, QListView, QTreeWidget, QTableWidget {{
    background-color: {c['mw_bg']};
    gridline-color: {c['table_gridline']};
    border: 1px solid {c['mw_border']};
    selection-background-color: {c['accent']};
    selection-color: {c['text_on_accent']};
    outline: none;
    font-size: {pt['grid']}px;
}}
/* One grid line per edge. Bordering the item as well as setting
   gridline-color draws both, which is the doubled rule between cells. */
QTreeView::item, QTableView::item, QListView::item,
QTreeWidget::item, QTableWidget::item {{
    /* .tree-row in the reference: 19px tall, 0 4px. The 6px 8px asked for in
       the polish directive roughly doubled the row and halved how many
       episodes fit on screen, which moved away from the reference rather than
       towards it. `border: none` from that directive is kept — that one was a
       real fix, and is what stops the cell rule doubling. */
    padding: 0 4px;
    min-height: {m['row_h']}px;
    border: none;
    color: {c['text']};
}}
/* A view already inside a Panel must not draw its own frame: the panel's
   border and the view's would sit one pixel apart, which is the doubled
   outline the grid rules above exist to remove. */
QTreeView[inPanel="true"], QTableView[inPanel="true"],
QListView[inPanel="true"] {{ border: none; }}
QTreeView::item:hover, QTableView::item:hover {{
    background: {c['row_hover']};
}}
QTreeView::item:selected, QTableView::item:selected,
QListView::item:selected, QTreeWidget::item:selected,
QTableWidget::item:selected {{
    background-color: {c['accent']};
    color: {c['text_on_accent']};
}}
/* No min/max height: the padding sets the row, and pinning a maximum is what
   clips a descender or a second line once the type grows. */
QHeaderView::section {{
    background-color: {c['mw_header_bg']};
    color: {c['text']};
    font-weight: bold;
    border: 1px solid {c['mw_border']};
    padding: 4px 8px;
}}
QHeaderView::section:hover {{ background-color: {c['panel_header']}; }}

/* ------------------------------------------------------------- panels -- */
QFrame[panel="true"] {{
    background: {c['panel_bg']};
    border: 1px solid {c['panel_border']};
    border-radius: 2px;
}}
QLabel[panelHeader="true"] {{
    background: {c['panel_header']};
    border-bottom: 1px solid {c['panel_border']};
    color: {c['control_fg']};
    padding: 3px 6px;
    font-weight: bold;
}}
/* Monospace, inset, so a long path reads as a value rather than prose. */
QLabel[pathDisplay="true"] {{
    font-family: "{mono}";
    font-size: {pt['small']}px;
    color: {c['path_text']};
    background: {c['panel_bg']};
    border: 1px solid {c['control_border']};
    border-top-color: {c['control_border_dark']};
    border-radius: 2px;
    padding: 1px 6px;
}}

/* --------------------------------------------------------- progress -- */
/* A QProgressBar draws nothing without a ::chunk rule once the application
   carries a stylesheet: the bar renders as an empty trough at any value. */
QProgressBar {{
    background: {c['panel_bg']};
    border: 1px solid {c['control_border']};
    border-top-color: {c['control_border_dark']};
    border-radius: {m['radius_tight']}px;
    min-height: 12px;
    max-height: 12px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {c['aqua_top']}, stop:1 {c['aqua_bottom']});
    border-radius: {m['radius_tight'] - 1}px;
    margin: 1px;
}}

/* ---------------------------------------------------------- scrollbars -- */
/* The period scrollbar was a slim track, not a modern 12-15px gutter. */
QScrollBar:vertical   {{ background: transparent; width: 9px;
                         margin: 0; border: none; }}
QScrollBar:horizontal {{ background: transparent; height: 9px;
                         margin: 0; border: none; }}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: {c['scroll_handle']};
    border: none;
    border-radius: 4px;
    min-height: 28px;
    min-width: 28px;
    margin: 2px;
}}
QScrollBar::handle:hover {{ background: {c['scroll_handle_hover']}; }}
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
QSplitter::handle {{ background: {c['window_bg']}; width: 6px; height: 6px; }}
QSplitter::handle:hover {{ background: {c['accent_glow']}; }}

QTextBrowser {{
    background: {c['panel_bg']};
    border: none;
}}

/* ------------------------------------------------------------ dialogs -- */
/* Values from ui/reference/dialogs.css: .dialog-content, .dialog-action-bar,
   .list-view, .list-item, .wizard-title, fieldset, legend. A dialog adds no
   palette of its own — it is a small window. */
QWidget[dialogContent="true"] {{ background: {c['dialog_content_bg']}; }}
QWidget[actionBar="true"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {c['action_bar_top']}, stop:1 {c['action_bar_bottom']});
    border-top: 1px solid {c['dialog_seam']};
}}
QLabel[confirmQuestion="true"] {{
    font-size: {pt['heading']}px; font-weight: bold; color: #000000;
}}
QLabel[wizardTitle="true"] {{
    font-size: {pt['title']}px; font-weight: bold; color: #000000;
}}
QLabel[wizardSubtitle="true"] {{
    font-size: {pt['small']}px; color: {c['text_dim']};
}}
/* .list-view — an inset box, its top edge darker in place of the shadow. */
QScrollArea[listView="true"] {{
    background: {c['panel_bg']};
    border: 1px solid {c['panel_border']};
    border-top-color: {c['list_sunken_edge']};
    border-radius: {m['radius_tight']}px;
}}
QWidget[listHost="true"] {{ background: {c['panel_bg']}; }}
QWidget[listItem="true"] {{ background: {c['panel_bg']}; }}
QWidget[listItem="true"][selected="true"] {{ background: {c['accent']}; }}
QLabel[listItemTitle="true"] {{
    font-size: {pt['body']}px; font-weight: bold; color: {c['text']};
}}
QLabel[listItemTitle="true"][selected="true"] {{ color: {c['text_on_accent']}; }}
QLabel[listItemDesc="true"] {{
    font-size: {pt['small']}px; color: {c['text_dim']};
}}
QLabel[listItemDesc="true"][selected="true"] {{
    color: {c['text_on_accent_dim']};
}}
/* fieldset / legend, and the callout box. */
QWidget[dialogContent="true"] QGroupBox {{
    border: 1px solid {c['panel_border']};
    border-radius: {m['radius']}px;
    background: {c['fieldset_bg']};
    margin-top: 7px;
    padding-top: 4px;
}}
QWidget[dialogContent="true"] QGroupBox::title {{
    subcontrol-origin: margin;
    left: 7px;
    padding: 0 3px;
    font-size: {pt['small']}px;
    font-weight: bold;
    color: {c['legend_fg']};
}}
QLabel[callout="warn"] {{
    background: {c['warn_bg']};
    border: 1px solid {c['warn_border']};
    border-radius: {m['radius_tight']}px;
    color: {c['warn_text']};
    font-size: {pt['small']}px;
    padding: 6px 8px;
}}

/* Inputs are a pixel shorter inside a dialog than on the toolbar. */
QWidget[dialogContent="true"] QLineEdit {{
    min-height: {m['dialog_input_h']}px;
    max-height: {m['dialog_input_h']}px;
}}

/* ------------------------------------------------- pipeline workbench -- */
/* Values from ui/reference/pipeline.css: .inspector-panel, .inspector-title,
   .inspector-subtitle, .info-banner, .inspector-table, .zoom-toolbar. */
QWidget#inspectorPanel {{
    background: {c['panel_bg']};
    border-top: 1px solid {c['panel_border']};
}}
QLabel#inspectorTitle {{ font-size: {pt['title']}px; font-weight: bold;
                         color: #000000; }}
QLabel#inspectorSubtitle {{ font-size: {pt['small']}px;
                            color: {c['text_dim']}; }}
QLabel#inspectorBanner {{
    background: {c['info_bg']};
    border: 1px solid {c['info_border']};
    border-radius: {m['radius_tight']}px;
    color: {c['info_text']};
    font-size: {pt['small']}px;
    padding: 6px 8px;
}}
QFrame#inspectorTable {{
    background: {c['panel_bg']};
    border: 1px solid {c['panel_border']};
}}
QLabel[kvKey="true"] {{
    background: {c['kv_key_bg']};
    color: {c['kv_key_fg']};
    font-weight: bold;
    border-right: 1px solid {c['kv_key_line']};
    border-bottom: 1px solid {c['kv_row_line']};
    padding: 4px 8px;
}}
QLabel[kvVal="true"] {{
    background: {c['panel_bg']};
    color: {c['kv_val_fg']};
    border-bottom: 1px solid {c['kv_row_line']};
    padding: 4px 8px;
}}
/* The floating zoom pill sits over the canvas. */
QWidget#zoomPill {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #ffffff, stop:1 #e5e5e5);
    border: 1px solid {c['control_border']};
    border-radius: {m['radius']}px;
}}
QPushButton[zoom="true"] {{
    background: transparent;
    border: none;
    border-radius: {m['radius_tight']}px;
    font-weight: bold;
    color: {c['statusbar_fg']};
    padding: 2px 8px;
    min-height: 0;
    max-height: 20px;
}}
QPushButton[zoom="true"]:hover {{ background: rgba(0, 0, 0, 20); }}
QLabel#zoomDisplay {{
    color: {c['text_dim']};
    font-size: {pt['tiny']}px;
    border-left: 1px solid {c['menu_line']};
    border-right: 1px solid {c['menu_line']};
    padding: 0 6px;
}}

/* --------------------------------------------------------- ambox note -- */
QFrame[ambox="info"] {{
    background: {c['info_bg']};
    border: 1px solid {c['info_border']};
    border-radius: {m['radius_tight']}px;
}}
QFrame[ambox="warn"] {{
    background: {c['warn_bg']};
    border: 1px solid {c['warn_border']};
    border-radius: {m['radius_tight']}px;
}}
"""


def apply(app) -> None:
    """Apply fonts and the stylesheet to a QApplication."""
    app.setFont(font("body"))
    app.setStyle("Fusion")          # a predictable base across platforms
    app.setStyleSheet(stylesheet())
