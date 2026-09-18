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

from collections import defaultdict
import re

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


# Display text is never used as a matplotlib categorical coordinate. Long
# filenames regularly share a title fragment, and matplotlib draws matching
# categorical strings at one position. Keep identity and geometry separate.
_EPISODE_ID = re.compile(
    r"(?i)(?:s(?P<season>\d{1,2})e(?P<first>\d{1,3})(?:[-–]e?(?P<last>\d{1,3}))?"
    r"|(?P<season_x>\d{1,2})x(?P<first_x>\d{1,3})(?:[-–]?(?P<last_x>\d{1,3}))?)"
)


def _bar_series(axes, labels, values, *, bottoms=None, label="", color="",
                horizontal=False):
    """Add many bars as one collection instead of one Artist per bar.

    ``Axes.bar`` creates a Python Rectangle for every episode and component.
    The FFC chart therefore built 1,200 artists for 200 episodes.  A
    PolyCollection keeps the same rectangular geometry, colours and legend
    semantics with one artist per series.
    """
    import numpy as np
    from matplotlib.collections import PolyCollection

    count = len(values)
    if not count:
        (axes.set_yticks if horizontal else axes.set_xticks)([])
        return []
    x = np.arange(count, dtype=float)
    low = np.asarray(bottoms if bottoms is not None else [0.0] * count,
                     dtype=float)
    high = low + np.asarray(values, dtype=float)
    left, right = x - 0.4, x + 0.4
    vertices = np.stack((
        np.column_stack((left, low)),
        np.column_stack((left, high)),
        np.column_stack((right, high)),
        np.column_stack((right, low)),
    ), axis=1)
    if horizontal:
        vertices = vertices[:, :, ::-1]
    collection = PolyCollection(
        vertices, facecolors=color, edgecolors="white", linewidths=0.5,
        label=label)
    axes.add_collection(collection)
    if horizontal:
        axes.set_ylim(-0.5, count - 0.5)
        axes.set_yticks(x, labels)
    else:
        axes.set_xlim(-0.5, count - 0.5)
        axes.set_xticks(x, labels)
    axes.autoscale_view(scalex=horizontal, scaley=not horizontal)
    return high.tolist()


class ChartDialog(QDialog):
    """Per-episode Formal-Feature Composite composition for one show."""

    def __init__(self, show_name: str, results, config: dict,
                 parent=None) -> None:
        super().__init__(parent)
        self.setModal(False)

        body = ModalDialogFrame.install(
            self, f"Formal-Feature Composite (FFC) — {show_name}",
            buttons=("min", "max", "close"))

        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        ok = [r for r in results if r.status == "ok"]
        ok.sort(key=lambda r: r.metrics.sensory_load.score)
        horizontal = len(ok) > 10
        figure_height = (max(5.6, min(8.6, 1.7 + len(ok) * 0.30))
                         if horizontal else 4.6)
        self.resize(920 if horizontal else 880,
                    max(520, int(figure_height * 100) + 60))

        figure = Figure(figsize=(8.9 if horizontal else 8.6, figure_height),
                        dpi=100,
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
        positions = list(range(len(ok)))
        labels = _episode_labels(
            [r.file for r in ok], title_limit=30 if horizontal else 24)
        bottoms = [0.0] * len(ok)

        for index, (label, attribute, weight_key) in enumerate(COMPONENTS):
            values = [getattr(r.metrics.sensory_load.components, attribute)
                      * w.get(weight_key, 0.0)
                      for r, w in zip(ok, per_episode)]
            bottoms = _bar_series(
                axes, labels, values, bottoms=bottoms, label=label,
                color=BAND_COLORS[index], horizontal=horizontal)

        score_limit = max(1.0, max(bottoms) * 1.15 if bottoms else 1.0)
        if horizontal:
            axes.set_yticks(positions, labels=labels, fontsize=8)
            axes.set_xlabel("FFC score (configurable 0–1 composite)",
                            fontsize=9)
            axes.set_ylabel("Episode — ordered by FFC", fontsize=9)
            axes.set_xlim(0, score_limit)
            axes.invert_yaxis()
            axes.grid(axis="x", color=COLORS["mw_row_line"], linewidth=0.8)
        else:
            _set_x_labels(axes, positions, labels)
            axes.set_ylabel("FFC score (configurable 0–1 composite)",
                            fontsize=9)
            axes.set_ylim(0, score_limit)
            axes.grid(axis="y", color=COLORS["mw_row_line"], linewidth=0.8)
        axes.tick_params(axis="y", labelsize=8)
        axes.set_axisbelow(True)
        axes.legend(fontsize=8, ncol=6, frameon=False,
                    loc="upper center", bbox_to_anchor=(0.5, 1.12))
        if horizontal:
            figure.subplots_adjust(bottom=0.19, top=0.87, left=0.36,
                                   right=0.98)
            _validation_footnote(figure, x=0.36)
        else:
            # Room for the rotated episode names, which are the long labels
            # here, plus the validation note beneath them.
            figure.subplots_adjust(bottom=0.40, top=0.86, left=0.09,
                                   right=0.98)
            _validation_footnote(figure)

        canvas = FigureCanvasQTAgg(figure)
        body.addWidget(canvas, 1)


def _short(file_name: str, limit: int = 28) -> str:
    """Compact a title without discarding the episode identifier before it."""
    stem = file_name.rsplit(".", 1)[0]
    return stem if len(stem) <= limit else stem[:limit - 1].rstrip() + "…"


def _episode_labels(file_names, title_limit: int = 28) -> list[str]:
    """Return readable, unique labels for a list of episode identifiers.

    A label is presentation, not an x-coordinate. The numbered suffix is
    deliberately retained even for duplicate source filenames: an analyst
    must be able to see that the chart holds separate results rather than one
    silently overwritten category.
    """
    bases = [_episode_label(name, title_limit) for name in file_names]
    seen: defaultdict[str, int] = defaultdict(int)
    labels = []
    for base in bases:
        seen[base] += 1
        labels.append(base if seen[base] == 1 else f"{base} [{seen[base]}]")
    return labels


def _episode_label(file_name: str, title_limit: int) -> str:
    stem = file_name.rsplit(".", 1)[0]
    match = _EPISODE_ID.search(stem)
    if not match:
        return _short(stem, title_limit)

    season = match.group("season") or match.group("season_x")
    first = match.group("first") or match.group("first_x")
    last = match.group("last") or match.group("last_x")
    episode_id = f"S{int(season):02}E{int(first):02}"
    if last:
        episode_id += f"–E{int(last):02}"
    title = stem[match.end():].strip(" ._-–")
    return (f"{episode_id} — {_short(title, title_limit)}"
            if title else episode_id)


def _set_x_labels(axes, positions, labels) -> None:
    """Attach labels to numeric positions; never invoke categorical plotting."""
    axes.set_xticks(positions, labels=labels, rotation=30, ha="right",
                    fontsize=8)


def _validation_footnote(figure, x: float = 0.09) -> None:
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
        x, 0.015,
        "Not graded against hand coding: " + ", ".join(names)
        + ".  These compare episodes measured the same way; they are not "
          "validated figures, and flashing is not a safety assessment.",
        fontsize=7, color=COLORS["text_dim"], ha="left", va="bottom",
        wrap=True)


def _axes(figure):
    """The shared chart furniture: no top/right spine, horizontal grid only."""
    axes = figure.add_subplot(111)
    axes.set_facecolor(COLORS["panel_bg"])
    axes.tick_params(axis="y", labelsize=8)
    axes.spines["top"].set_visible(False)
    axes.spines["right"].set_visible(False)
    axes.grid(axis="y", color=COLORS["mw_row_line"], linewidth=0.8)
    axes.set_axisbelow(True)
    return axes


class SpeechChartDialog(QDialog):
    """Words per timed-text minute per episode, with timed-text density.

    The two are plotted together on purpose. WPM divides by the union of
    word-bearing timed-text intervals, so
    a fast-talking episode with very little dialogue and a chatty one can sit
    at the same height; the density series is what tells them apart. A WPM
    chart on its own is the misreading `CLAUDE.md` §2.2 names.
    """

    def __init__(self, rows, parent=None) -> None:
        super().__init__(parent)
        self.setModal(False)
        self.resize(900, 520)
        body = ModalDialogFrame.install(
            self, "Timed-text rate and density by episode",
            buttons=("min", "max", "close"))

        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        ordered = sorted(rows, key=lambda r: r["wpm"])
        positions = list(range(len(ordered)))
        labels = _episode_labels([r["file"] for r in ordered])

        figure = Figure(figsize=(8.8, 4.6), dpi=100,
                        facecolor=COLORS["panel_bg"])
        axes = _axes(figure)
        _bar_series(
            axes, labels, [r["wpm"] for r in ordered],
            color=BAND_COLORS[0], label="Words per timed-text minute")
        _set_x_labels(axes, positions, labels)
        axes.set_ylabel("Words per timed-text minute", fontsize=9)

        density = axes.twinx()
        density.plot(positions, [r["density"] for r in ordered], marker="o",
                     markersize=3.5, linewidth=1.2, color=BAND_COLORS[4],
                     label="Timed-text density (fraction of runtime)")
        density.set_ylabel("Timed-text density", fontsize=9)
        density.set_ylim(0, 1)
        density.spines["top"].set_visible(False)
        density.tick_params(axis="y", labelsize=8)

        handles = axes.get_legend_handles_labels()[0] + \
            density.get_legend_handles_labels()[0]
        labels_ = axes.get_legend_handles_labels()[1] + \
            density.get_legend_handles_labels()[1]
        axes.legend(handles, labels_, fontsize=8, ncol=2, frameon=False,
                    loc="upper center", bbox_to_anchor=(0.5, 1.12))
        figure.subplots_adjust(bottom=0.34, top=0.86, left=0.22, right=0.92)
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
            positions = list(range(len(rows)))
            labels = _episode_labels(
                [str(r["episode_id"]) for r in rows])
            bottoms = [0.0] * len(rows)
            for index, (key, label) in enumerate(TIER_SERIES):
                values = [(r.get(key) or 0.0) for r in rows]
                bottoms = _bar_series(
                    axes, labels, values, bottoms=bottoms, label=label,
                    color=BAND_COLORS[index])
            _set_x_labels(axes, positions, labels)
            axes.set_ylabel("Share of content words", fontsize=9)
            axes.set_ylim(0, 1)
            axes.legend(fontsize=8, ncol=3, frameon=False, loc="upper center",
                        bbox_to_anchor=(0.5, 1.12))
        else:
            key, ylabel = VOCAB_SERIES[kind]
            present = [r for r in rows if r.get(key) is not None]
            present.sort(key=lambda r: r[key])
            positions = list(range(len(present)))
            labels = _episode_labels(
                [str(r["episode_id"]) for r in present])
            _bar_series(
                axes, labels, [r[key] for r in present], color=BAND_COLORS[0])
            _set_x_labels(axes, positions, labels)
            axes.set_ylabel(ylabel, fontsize=9)
            if not present:
                axes.text(0.5, 0.5, "No episode has this measure.",
                          transform=axes.transAxes, ha="center", fontsize=9,
                          color=COLORS["text_dim"])

        figure.subplots_adjust(bottom=0.34, top=0.86, left=0.22, right=0.98)
        body.addWidget(FigureCanvasQTAgg(figure), 1)
