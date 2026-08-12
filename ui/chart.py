"""
ui/chart.py — the per-episode chart for a show.

matplotlib on the Qt canvas, as CLAUDE.md's stack table specifies. Kept in its
own module so the import stays lazy: matplotlib costs about a second to load,
and the Library should not pay it to show a table.

WHAT IS PLOTTED, AND WHY IT IS NOT A COMPOSITE

The bars are the six sensory-load COMPONENTS, stacked by their contribution —
normalised value times weight — so the bar's height is the composite and its
segments are what produced it. A bar of the composite alone would show the
number the report already gives in bigger type, and would hide the fact that
two episodes reaching 0.24 can reach it completely differently.

Guardrail: no threshold line, no banding, no colour that means "high". The
scale is 0-1 and the axis says what 0 and 1 mean; a reader compares episodes
with each other, which is the only comparison the data supports.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QVBoxLayout

from ui.modal import ModalDialogFrame
from ui.tokens import COLORS

# The component order the report lists them in, so the two read alike.
COMPONENTS = (
    ("Pacing", "pacing", "pacing"),
    ("Saturation", "saturation", "saturation"),
    ("Contrast", "contrast", "color_contrast"),
    ("Motion", "motion", "motion"),
    ("Flashing", "flashing", "flashing"),
    ("Audio", "audio", "audio"),
)

# One hue per component, distinguishable in greyscale by ordering rather than
# by lightness alone. None of them encodes a judgement; they identify a
# component, which is why the legend is not optional.
BAND_COLORS = ("#4e79a7", "#76b7b2", "#8cd17d", "#f1ce63", "#e15759",
               "#b07aa1")


class ChartDialog(QDialog):
    """Per-episode sensory-load composition for one show."""

    def __init__(self, show_name: str, results, config: dict,
                 parent=None) -> None:
        super().__init__(parent)
        self.setModal(False)
        self.resize(880, 520)

        body = ModalDialogFrame.install(
            self, f"Sensory load by component — {show_name}",
            buttons=("min", "max", "close"))

        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        ok = [r for r in results if r.status == "ok"]
        ok.sort(key=lambda r: r.metrics.sensory_load.score)

        figure = Figure(figsize=(8.6, 4.6), dpi=100,
                        facecolor=COLORS["panel_bg"])
        axes = figure.add_subplot(111)
        axes.set_facecolor(COLORS["panel_bg"])

        weights = config.get("sensory_load_weights", {})
        labels = [_short(r.file) for r in ok]
        bottoms = [0.0] * len(ok)

        for index, (label, attribute, weight_key) in enumerate(COMPONENTS):
            weight = weights.get(weight_key, 0.0)
            values = [getattr(r.metrics.sensory_load.components, attribute)
                      * weight for r in ok]
            axes.bar(labels, values, bottom=bottoms, label=label,
                     color=BAND_COLORS[index], edgecolor="white",
                     linewidth=0.5)
            bottoms = [b + v for b, v in zip(bottoms, values)]

        axes.set_ylabel("Sensory load  (0 = low stimulation, 1 = high)",
                        fontsize=9)
        axes.set_ylim(0, max(1.0, max(bottoms) * 1.15 if bottoms else 1.0))
        axes.tick_params(axis="x", labelrotation=30, labelsize=8)
        axes.tick_params(axis="y", labelsize=8)
        for tick in axes.get_xticklabels():
            tick.set_horizontalalignment("right")
        axes.spines["top"].set_visible(False)
        axes.spines["right"].set_visible(False)
        axes.grid(axis="y", color=COLORS["mw_row_line"], linewidth=0.8)
        axes.set_axisbelow(True)
        axes.legend(fontsize=8, ncol=6, frameon=False,
                    loc="upper center", bbox_to_anchor=(0.5, 1.12))
        # Room for the rotated episode names, which are the long labels here.
        figure.subplots_adjust(bottom=0.34, top=0.86, left=0.09, right=0.98)

        canvas = FigureCanvasQTAgg(figure)
        body.addWidget(canvas, 1)


def _short(file_name: str, limit: int = 28) -> str:
    """Episode names are long; the tail is what distinguishes them."""
    stem = file_name.rsplit(".", 1)[0]
    return stem if len(stem) <= limit else "…" + stem[-(limit - 1):]
