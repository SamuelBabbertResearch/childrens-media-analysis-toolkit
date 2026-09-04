"""
ui/chart.py — the per-episode chart for a show.

matplotlib on the Qt canvas, as CLAUDE.md's stack table specifies. Kept in its
own module so the import stays lazy: matplotlib costs about a second to load,
and the Library should not pay it to show a table.

WHAT IS PLOTTED, AND WHY THE FFC IS NOT A VIEWER-EFFECT MEASURE

The bars are the six FFC COMPONENTS, stacked by their contribution —
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
    """Per-episode Formal-Feature Composite composition for one show."""

    def __init__(self, show_name: str, results, config: dict,
                 parent=None) -> None:
        super().__init__(parent)
        self.setModal(False)
        self.resize(880, 520)

        body = ModalDialogFrame.install(
            self, f"Formal-Feature Composite (FFC) — {show_name}",
            buttons=("min", "max", "close"))

        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        ok = [r for r in results if r.status == "ok"]
        ok.sort(key=lambda r: r.metrics.sensory_load.score)

        figure = Figure(figsize=(8.6, 4.6), dpi=100,
                        facecolor=COLORS["panel_bg"])
        axes = figure.add_subplot(111)
        axes.set_facecolor(COLORS["panel_bg"])

        # Per EPISODE, because the effective weights differ for a silent one:
        # audio's share is redistributed across the visual metrics. Using the
        # nominal weights made the bar height stop equalling the composite —
        # which is the one thing this chart's docstring promises.
        from analyzer.metrics_sensory import effective_weights
        per_episode = [effective_weights(r.config,
                                         r.metrics.sensory_load.audio_available)
                       for r in ok]
        labels = [_short(r.file) for r in ok]
        bottoms = [0.0] * len(ok)

        for index, (label, attribute, weight_key) in enumerate(COMPONENTS):
            values = [getattr(r.metrics.sensory_load.components, attribute)
                      * w.get(weight_key, 0.0)
                      for r, w in zip(ok, per_episode)]
            axes.bar(labels, values, bottom=bottoms, label=label,
                     color=BAND_COLORS[index], edgecolor="white",
                     linewidth=0.5)
            bottoms = [b + v for b, v in zip(bottoms, values)]

        axes.set_ylabel("FFC score (configurable 0–1 composite)",
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
        # Room for the rotated episode names, which are the long labels here,
        # plus the validation note beneath them.
        figure.subplots_adjust(bottom=0.40, top=0.86, left=0.09, right=0.98)
        _validation_footnote(figure)

        canvas = FigureCanvasQTAgg(figure)
        body.addWidget(canvas, 1)


def _short(file_name: str, limit: int = 28) -> str:
    """Episode names are long; the tail is what distinguishes them."""
    stem = file_name.rsplit(".", 1)[0]
    return stem if len(stem) <= limit else "…" + stem[-(limit - 1):]


def _validation_footnote(figure) -> None:
    """Name the ungraded components under the chart.

    CLAUDE.md §2.2 requires the flag wherever the numbers appear, and a
    stacked bar is a number: the flashing band is a segment of every bar here,
    with nothing on the figure saying it has never been graded.
    """
    from analyzer.measurements import ungraded_measurements
    names = [name for name, _why in ungraded_measurements()]
    if not names:
        return
    figure.text(
        0.09, 0.015,
        "Not graded against hand coding: " + ", ".join(names)
        + ".  These compare episodes measured the same way; they are not "
          "validated figures, and flashing is not a safety assessment.",
        fontsize=7, color=COLORS["text_dim"], ha="left", va="bottom",
        wrap=True)


def _axes(figure):
    """The shared chart furniture: no top/right spine, horizontal grid only."""
    axes = figure.add_subplot(111)
    axes.set_facecolor(COLORS["panel_bg"])
    axes.tick_params(axis="x", labelrotation=30, labelsize=8)
    axes.tick_params(axis="y", labelsize=8)
    for tick in axes.get_xticklabels():
        tick.set_horizontalalignment("right")
    axes.spines["top"].set_visible(False)
    axes.spines["right"].set_visible(False)
    axes.grid(axis="y", color=COLORS["mw_row_line"], linewidth=0.8)
    axes.set_axisbelow(True)
    return axes


class SpeechChartDialog(QDialog):
    """Words per minute per episode, with speech density beside it.

    The two are plotted together on purpose. WPM divides by dialogue time, so
    a fast-talking episode with very little dialogue and a chatty one can sit
    at the same height; the density series is what tells them apart. A WPM
    chart on its own is the misreading `CLAUDE.md` §2.2 names.
    """

    def __init__(self, rows, parent=None) -> None:
        super().__init__(parent)
        self.setModal(False)
        self.resize(900, 520)
        body = ModalDialogFrame.install(
            self, "Speech rate and density by episode",
            buttons=("min", "max", "close"))

        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        ordered = sorted(rows, key=lambda r: r["wpm"])
        labels = [_short(r["file"]) for r in ordered]

        figure = Figure(figsize=(8.8, 4.6), dpi=100,
                        facecolor=COLORS["panel_bg"])
        axes = _axes(figure)
        axes.bar(labels, [r["wpm"] for r in ordered],
                 color=BAND_COLORS[0], edgecolor="white", linewidth=0.5,
                 label="Words per minute (of dialogue time)")
        axes.set_ylabel("Words per minute", fontsize=9)

        density = axes.twinx()
        density.plot(labels, [r["density"] for r in ordered], marker="o",
                     markersize=3.5, linewidth=1.2, color=BAND_COLORS[4],
                     label="Speech density (fraction of runtime)")
        density.set_ylabel("Speech density", fontsize=9)
        density.set_ylim(0, 1)
        density.spines["top"].set_visible(False)
        density.tick_params(axis="y", labelsize=8)

        handles = axes.get_legend_handles_labels()[0] + \
            density.get_legend_handles_labels()[0]
        labels_ = axes.get_legend_handles_labels()[1] + \
            density.get_legend_handles_labels()[1]
        axes.legend(handles, labels_, fontsize=8, ncol=2, frameon=False,
                    loc="upper center", bbox_to_anchor=(0.5, 1.12))
        figure.subplots_adjust(bottom=0.34, top=0.86, left=0.08, right=0.92)
        body.addWidget(FigureCanvasQTAgg(figure), 1)


# What each vocabulary chart plots: (flat-row key, axis label). The stacked
# tier chart is handled separately because it is three series, not one.
VOCAB_SERIES = {
    "Flesch Reading Ease": ("read_flesch_reading_ease",
                            "Flesch Reading Ease (higher = simpler)"),
    "Flesch-Kincaid grade": ("read_flesch_kincaid_grade",
                             "Flesch-Kincaid grade (a relative index)"),
    "Mean age of acquisition": ("vocab_aoa_mean",
                                "Mean age of acquisition (years)"),
    "MTLD (lexical diversity)": ("div_mtld",
                                 "MTLD (higher = more varied vocabulary)"),
}

TIER_SERIES = (("vocab_tier1_proportion", "Tier 1 — everyday"),
               ("vocab_tier2_proportion", "Tier 2 — cross-domain"),
               ("vocab_tier3_proportion", "Tier 3 — rare"))


class VocabChartDialog(QDialog):
    """One vocabulary measure across the analysed caption files.

    Guardrail: the axis label says what the number is a relative index OF.
    None of these is a reading level, a grade, or a claim about a viewer, and
    the label is the only place a reader learns that from the chart alone.
    """

    def __init__(self, kind: str, results, parent=None) -> None:
        super().__init__(parent)
        self.setModal(False)
        self.resize(900, 520)
        body = ModalDialogFrame.install(self, kind,
                                        buttons=("min", "max", "close"))

        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        rows = [r.to_flat_row() for r in results]
        figure = Figure(figsize=(8.8, 4.6), dpi=100,
                        facecolor=COLORS["panel_bg"])
        axes = _axes(figure)

        if kind not in VOCAB_SERIES:            # the stacked tier chart
            rows.sort(key=lambda r: r.get("vocab_tier1_proportion") or 0.0)
            labels = [_short(str(r["episode_id"])) for r in rows]
            bottoms = [0.0] * len(rows)
            for index, (key, label) in enumerate(TIER_SERIES):
                values = [(r.get(key) or 0.0) for r in rows]
                axes.bar(labels, values, bottom=bottoms, label=label,
                         color=BAND_COLORS[index], edgecolor="white",
                         linewidth=0.5)
                bottoms = [b + v for b, v in zip(bottoms, values)]
            axes.set_ylabel("Share of content words", fontsize=9)
            axes.set_ylim(0, 1)
            axes.legend(fontsize=8, ncol=3, frameon=False, loc="upper center",
                        bbox_to_anchor=(0.5, 1.12))
        else:
            key, ylabel = VOCAB_SERIES[kind]
            present = [r for r in rows if r.get(key) is not None]
            present.sort(key=lambda r: r[key])
            axes.bar([_short(str(r["episode_id"])) for r in present],
                     [r[key] for r in present], color=BAND_COLORS[0],
                     edgecolor="white", linewidth=0.5)
            axes.set_ylabel(ylabel, fontsize=9)
            if not present:
                axes.text(0.5, 0.5, "No episode has this measure.",
                          transform=axes.transAxes, ha="center", fontsize=9,
                          color=COLORS["text_dim"])

        figure.subplots_adjust(bottom=0.34, top=0.86, left=0.09, right=0.98)
        body.addWidget(FigureCanvasQTAgg(figure), 1)
