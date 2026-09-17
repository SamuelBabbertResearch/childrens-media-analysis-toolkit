"""Synthetic Seaborn figure preview for the adult perceived-pace study.

This script creates fake ratings for visual-design review only. It is not an
analysis of participant data and every exported figure is visibly stamped
"SYNTHETIC DEMO DATA".

Usage:
    .\\.venv\\Scripts\\python.exe demo_adult_perception_figures.py
    .\\.venv\\Scripts\\python.exe demo_adult_perception_figures.py --participants 50
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


PROJECT = Path(__file__).resolve().parent
OUTDIR = PROJECT / "output" / "figures" / "synthetic_adult_perception_n50"
ANCHORS = ["1 Very slow", "2 Slow", "3 In between", "4 Fast", "5 Very fast"]
FEATURE_ORDER = ["cuts", "motion", "audio"]
PAIR_ORDER = ["CUTS_1", "CUTS_2", "MOTION_1", "MOTION_2", "AUDIO_1", "AUDIO_2"]
FEATURE_TITLES = {
    "cuts": "Hand-coded cuts per minute",
    "motion": "Visual motion (mean frame difference)",
    "audio": "Audio intensity (mean linear RMS)",
}
FEATURE_MEASURE = {
    "cuts": "cuts_per_min",
    "motion": "motion_mean",
    "audio": "audio_rms_mean",
}


def style() -> None:
    sns.set_theme(style="ticks", context="paper")
    plt.rcParams.update({
        "figure.dpi": 150, "savefig.dpi": 300, "savefig.bbox": "tight",
        "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
        "axes.spines.top": False, "axes.spines.right": False,
        "legend.frameon": False,
    })


def synthetic_ratings(participants: int, seed: int = 7) -> pd.DataFrame:
    """Return a plausible-looking but wholly invented within-subjects dataset."""
    design = pd.DataFrame([
        ("Clip A1", "CUTS_1", "cuts", "low", 4.0, 0.0430, 0.03673),
        ("Clip B1", "CUTS_1", "cuts", "high", 30.0, 0.0437, 0.03719),
        # Exported participant-facing measurements for CUTS_2, not the
        # replacement's source-window values. Motion is closely matched.
        ("Clip A2", "CUTS_2", "cuts", "low", 8.0, 0.0694, 0.03608),
        ("Clip B2", "CUTS_2", "cuts", "high", 24.0, 0.0682, 0.03685),
        ("Clip C1-L", "MOTION_1", "motion", "low", 18.0, 0.0331, 0.04117),
        ("Clip C1-H", "MOTION_1", "motion", "high", 16.0, 0.1082, 0.04109),
        ("Clip C2-L", "MOTION_2", "motion", "low", 14.0, 0.0356, 0.03933),
        ("Clip C2-H", "MOTION_2", "motion", "high", 14.0, 0.1032, 0.03934),
        ("Clip D1-L", "AUDIO_1", "audio", "low", 16.0, 0.0884, 0.03043),
        ("Clip D1-H", "AUDIO_1", "audio", "high", 12.0, 0.0882, 0.04294),
        ("Clip D2-L", "AUDIO_2", "audio", "low", 16.0, 0.0734, 0.02829),
        ("Clip D2-H", "AUDIO_2", "audio", "high", 16.0, 0.0758, 0.04442),
    ], columns=["clip_id", "pair_id", "target_feature", "target_level",
                "cuts_per_min", "motion_mean", "audio_rms_mean"])

    rng = np.random.default_rng(seed)
    lifts = {"cuts": 0.85, "motion": 0.65, "audio": 0.25}
    rows: list[dict[str, object]] = []
    for person in range(1, participants + 1):
        response_style = rng.normal(0, 0.45)
        for _, clip in design.iterrows():
            direction = 1 if clip.target_level == "high" else -1
            latent = 3 + response_style + direction * lifts[clip.target_feature]
            rating = int(np.clip(np.rint(rng.normal(latent, 0.75)), 1, 5))
            rows.append({**clip.to_dict(), "participant_id": f"P{person:03d}",
                         "rating": rating})
    return pd.DataFrame(rows)


def stamp(fig: plt.Figure) -> None:
    fig.text(0.5, 0.5, "SYNTHETIC DEMO DATA", ha="center", va="center",
             fontsize=34, color="0.5", alpha=0.16, rotation=24, zorder=10)


def pair_difference_percent(first: float, second: float) -> float:
    """Return an absolute, symmetric difference relative to the pair average."""
    pair_average = (abs(first) + abs(second)) / 2
    return 0.0 if pair_average == 0 else abs(first - second) / pair_average * 100


def fig0_clip_feature_map(df: pd.DataFrame) -> plt.Figure:
    """Explain the three measured characteristics of every clip at a glance.

    Each column is scaled only within that characteristic, so colour means
    "more of this measurement" rather than better, faster, safer, or a score.
    Raw values remain printed in every cell.  The second panel reports the
    symmetric percentage difference between the two clips in each pair, so
    low values show characteristics that are more closely matched.
    """
    clips = df.drop_duplicates("clip_id").copy()
    clips["pair_id"] = pd.Categorical(clips.pair_id, PAIR_ORDER, ordered=True)
    clips = clips.sort_values(["pair_id", "target_level"])
    columns = ["cuts_per_min", "motion_mean", "audio_rms_mean"]
    labels = ["Hand-coded\ncuts/min", "Visual\nmotion", "Audio intensity\n(linear RMS)"]
    scaled = clips[columns].copy()
    for column in columns:
        lo, hi = scaled[column].min(), scaled[column].max()
        scaled[column] = (scaled[column] - lo) / (hi - lo) if hi > lo else 0.5
    annotations = np.column_stack([
        clips.cuts_per_min.map(lambda value: f"{value:.0f}"),
        clips.motion_mean.map(lambda value: f"{value:.4f}"),
        clips.audio_rms_mean.map(lambda value: f"{value:.5f}"),
    ])
    ylabels = [f"{row.pair_id}  ·  {row.target_level.title()}  ·  {row.clip_id.replace('Clip ', '')}"
               for _, row in clips.iterrows()]
    pair_differences = []
    for pair_id in PAIR_ORDER:
        pair = clips.loc[clips["pair_id"] == pair_id, columns]
        if len(pair) != 2:
            continue
        pair_differences.append({
            "pair_id": pair_id,
            **{column: pair_difference_percent(pair.iloc[0][column], pair.iloc[1][column])
               for column in columns},
        })
    differences = pd.DataFrame(pair_differences).set_index("pair_id")[columns]
    difference_annotations = np.array([
        [f"{value:.1f}%" for value in row] for row in differences.to_numpy()
    ])

    fig, (ax, difference_ax) = plt.subplots(
        1, 2, figsize=(12.2, 6.2), gridspec_kw={"width_ratios": [3.1, 2]}
    )
    sns.heatmap(scaled, cmap="Blues", vmin=0, vmax=1, annot=annotations, fmt="",
                linewidths=1.4, linecolor="white", cbar_kws={"label": "Relative amount within each column"},
                xticklabels=labels, yticklabels=ylabels, ax=ax)
    ax.set(title="What each clip contains",
           xlabel="Darker means more of this characteristic only", ylabel="Matched pair and clip")
    sns.heatmap(differences, cmap="Blues", vmin=0, annot=difference_annotations, fmt="",
                linewidths=1.4, linecolor="white", cbar=False,
                xticklabels=["Hand-coded\ncuts/min", "Visual\nmotion", "Audio\nintensity"],
                yticklabels=differences.index, ax=difference_ax)
    difference_ax.set(
        title="Difference within each pair",
        xlabel="Absolute difference (% of pair average)\nSmaller = more closely matched",
        ylabel="",
    )
    fig.subplots_adjust(wspace=0.48, top=0.9, bottom=0.16)
    return fig


def fig1_distribution(df: pd.DataFrame) -> plt.Figure:
    ordered = df.assign(pair_id=pd.Categorical(df.pair_id, PAIR_ORDER, ordered=True))
    order = ordered.drop_duplicates("clip_id").sort_values(
        ["pair_id", "target_level"])["clip_id"].tolist()
    counts = df.groupby(["clip_id", "rating"]).size().unstack(fill_value=0)
    counts = counts.reindex(index=order, columns=range(1, 6), fill_value=0)
    proportions = counts.div(counts.sum(axis=1), axis=0)
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    bottoms = np.zeros(len(order))
    ramp = sns.color_palette("Blues", 5)
    for rating in range(1, 6):
        values = proportions[rating].to_numpy()
        ax.bar(order, values, bottom=bottoms, color=ramp[rating - 1],
               edgecolor="white", linewidth=0.6, label=ANCHORS[rating - 1])
        bottoms += values
    ax.set(title="Perceived-pace ratings by clip", ylabel="Proportion of ratings",
           xlabel="Clip", ylim=(0, 1))
    ax.tick_params(axis="x", rotation=45)
    ax.legend(title="Response", bbox_to_anchor=(1.02, 1), loc="upper left")
    sns.despine(ax=ax); stamp(fig)
    return fig


def fig2_paired_lines(df: pd.DataFrame) -> plt.Figure:
    pairs = [pair for pair in PAIR_ORDER if pair in set(df.pair_id)]
    colours = dict(zip(FEATURE_ORDER, sns.color_palette("colorblind", 3)))
    fig, axes = plt.subplots(1, 6, figsize=(12, 3.8), sharey=True)
    for ax, pair in zip(axes, pairs):
        sub = df[df.pair_id == pair]
        feature = sub.target_feature.iloc[0]
        wide = sub.pivot(index="participant_id", columns="target_level", values="rating")
        for _, row in wide.iterrows():
            ax.plot([0, 1], [row.low, row.high], color="0.55", alpha=.26, lw=.7)
        ax.plot([0, 1], [wide.low.mean(), wide.high.mean()], marker="o", lw=2.5,
                color=colours[feature])
        ax.set(title=f"{pair}\n{feature.title()}", xlim=(-.3, 1.3), ylim=(.7, 5.3),
               xticks=[0, 1], xticklabels=["Lower", "Higher"], yticks=range(1, 6))
        sns.despine(ax=ax)
    axes[0].set_yticklabels(ANCHORS)
    axes[0].set_ylabel("Perceived pace rating")
    fig.suptitle("Within-participant lower-versus-higher contrasts", y=1.03)
    stamp(fig)
    return fig


def fig3_differences(df: pd.DataFrame) -> plt.Figure:
    wide = df.pivot(index=["participant_id", "pair_id", "target_feature"],
                    columns="target_level", values="rating").reset_index()
    wide["difference"] = wide.high - wide.low
    order = [pair for pair in PAIR_ORDER if pair in set(wide.pair_id)]
    palette = dict(zip(FEATURE_ORDER, sns.color_palette("colorblind", 3)))
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.axvline(0, color="0.35", linestyle="--", lw=1)
    sns.stripplot(data=wide, x="difference", y="pair_id", order=order,
                  hue="target_feature", palette=palette, dodge=False, alpha=.45,
                  size=4, jitter=.2, legend=False, ax=ax)
    sns.pointplot(data=wide, x="difference", y="pair_id", order=order,
                  color="0.12", errorbar=("ci", 95), linestyle="none",
                  marker="D", capsize=.22, ax=ax)
    ax.set(title="Within-participant paired differences", ylabel="Analytical pair",
           xlabel="Rating difference (higher clip − lower clip; scale points)")
    sns.despine(ax=ax); stamp(fig)
    return fig


def fig4_association(df: pd.DataFrame) -> plt.Figure:
    summary = df.groupby(["clip_id", "target_feature", "cuts_per_min",
                          "motion_mean", "audio_rms_mean"], as_index=False).rating.agg(
                              mean="mean", sem="sem")
    colours = dict(zip(FEATURE_ORDER, sns.color_palette("colorblind", 3)))
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.6), sharey=True)
    for ax, feature in zip(axes, FEATURE_ORDER):
        sub = summary[summary.target_feature == feature]
        x = FEATURE_MEASURE[feature]
        ax.errorbar(sub[x], sub["mean"], yerr=sub["sem"], fmt="none", color=".7", zorder=1)
        sns.regplot(data=sub, x=x, y="mean", ci=None, ax=ax,
                    scatter_kws={"s": 52, "color": colours[feature], "edgecolor": "white"},
                    line_kws={"color": colours[feature], "alpha": .45})
        for _, row in sub.iterrows():
            ax.annotate(row.clip_id.replace("Clip ", ""), (row[x], row["mean"]),
                        xytext=(0, 8), textcoords="offset points", ha="center", fontsize=7)
        ax.set(title=FEATURE_TITLES[feature], xlabel=FEATURE_TITLES[feature],
               ylim=(.7, 5.3), yticks=range(1, 6))
        sns.despine(ax=ax)
    axes[0].set_yticklabels(ANCHORS)
    axes[0].set_ylabel("Mean rating (± SE)")
    fig.suptitle("Clip-level descriptive associations (four clips per panel)", y=1.04)
    stamp(fig)
    return fig


def main() -> None:
    parser = argparse.ArgumentParser(description="Create synthetic figure previews")
    parser.add_argument("--participants", type=int, default=50)
    args = parser.parse_args()
    if args.participants < 2:
        raise SystemExit("Use at least two synthetic participants")
    style(); data = synthetic_ratings(args.participants)
    output = PROJECT / "output" / "figures" / f"synthetic_adult_perception_n{args.participants}"
    output.mkdir(parents=True, exist_ok=True)
    for name, fig in {
        "fig0_clip_feature_map": fig0_clip_feature_map(data),
        "fig1_rating_distribution": fig1_distribution(data),
        "fig2_paired_contrasts": fig2_paired_lines(data),
        "fig3_paired_differences": fig3_differences(data),
        "fig4_measure_association": fig4_association(data),
    }.items():
        suffix = "" if name == "fig0_clip_feature_map" else "_SYNTHETIC"
        path = output / f"{name}{suffix}.png"
        fig.savefig(path); plt.close(fig)
        print(path)


if __name__ == "__main__":
    main()
