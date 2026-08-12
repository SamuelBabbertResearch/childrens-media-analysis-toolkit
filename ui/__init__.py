"""
ui — the PySide6 front-end.

Built alongside the existing Tkinter front-end (gui*.py) rather than replacing
it in place, so the application keeps running throughout the migration and the
two can be compared directly. Both import the same framework-free `analyzer`
package and the same `ui.tokens` palette.

Layers:
    ui.tokens   design tokens; no framework imports at all
    ui.theme    fonts, DPI, and the Qt stylesheet built from those tokens
    ui.report   HTML rendering of analysis results
"""
