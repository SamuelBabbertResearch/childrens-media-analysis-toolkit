"""PDF report generator — no GUI imports."""
from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage, HRFlowable,
)

if TYPE_CHECKING:
    from analyzer.schema import EpisodeResult, ShowAggregate


_GREY  = colors.HexColor("#555555")
_BLUE  = colors.HexColor("#1f497d")
_LIGHT = colors.HexColor("#dce6f1")
_RED   = colors.HexColor("#c00000")
_DIM   = colors.HexColor("#888888")

LIMITATIONS = (
    "This report describes the video stimulus, not the viewer. It cannot account for the "
    "child's age, temperament, sensory-processing profile, or cumulative screen time. "
    "The evidence base linking formal features (pacing, motion, color) to developmental "
    "outcomes is largely correlational and in places actively debated. Scores are a "
    "transparent profile to inform caregiver judgment — not a rating, verdict, or "
    "recommendation."
)


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title":  ParagraphStyle("rpt_title",  parent=base["Title"],
                                 fontSize=18, spaceAfter=4, textColor=_BLUE),
        "h2":     ParagraphStyle("rpt_h2",     parent=base["Heading2"],
                                 fontSize=11, spaceBefore=10, spaceAfter=2,
                                 textColor=_BLUE),
        "body":   ParagraphStyle("rpt_body",   parent=base["Normal"],
                                 fontSize=8.5, leading=12),
        "dim":    ParagraphStyle("rpt_dim",    parent=base["Normal"],
                                 fontSize=7.5, leading=11, textColor=_GREY),
        "score":  ParagraphStyle("rpt_score",  parent=base["Normal"],
                                 fontSize=26, textColor=_RED, spaceAfter=2),
        "limits": ParagraphStyle("rpt_limits", parent=base["Normal"],
                                 fontSize=7, leading=10, textColor=_GREY,
                                 spaceBefore=6),
    }


def _bar_png(value: float, width_px: int = 200, height_px: int = 14) -> bytes:
    """Render a single horizontal bar as a tiny PNG via matplotlib."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(width_px / 96, height_px / 96), dpi=96)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.barh(0.5, min(1.0, max(0.0, value)), height=0.8,
            color="#1f497d", left=0)
    ax.barh(0.5, 1.0, height=0.8, color="#dce6f1", left=0)
    ax.barh(0.5, min(1.0, max(0.0, value)), height=0.8,
            color="#1f497d", left=0)
    ax.axis("off")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _component_chart_png(result: "EpisodeResult", cfg: dict) -> bytes:
    """Reproduce the GUI Formal-Feature Composite bar chart as PNG."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    c = result.metrics.sensory_load.components
    w = cfg.get("sensory_load_weights", {})
    labels       = ["Pacing", "Saturation", "Contrast", "Motion", "Flashing", "Audio"]
    keys         = ["pacing", "saturation", "contrast", "motion", "flashing", "audio"]
    weight_keys  = ["pacing", "saturation", "color_contrast", "motion", "flashing", "audio"]
    norm_vals    = [getattr(c, k) for k in keys]
    weighted_vals= [getattr(c, k) * w.get(wk, 0) for k, wk in zip(keys, weight_keys)]

    fig, ax = plt.subplots(figsize=(5.2, 2.6), dpi=130)
    x = list(range(len(labels)))
    ax.bar(x, norm_vals, color="#5b9bd5", alpha=0.55, label="Normalized component")
    ax.bar(x, weighted_vals, color="#1f497d", alpha=0.90, label="Weighted contribution")
    ax.axhline(result.metrics.sensory_load.score, color="#c00000",
               linestyle="--", linewidth=1.2,
               label=f"Composite: {result.metrics.sensory_load.score:.3f}")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Value (0-1)", fontsize=8)
    ax.legend(fontsize=7)
    ax.set_title("Formal-Feature Composite Components", fontsize=9)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _timeline_chart_png(result: "EpisodeResult") -> bytes | None:
    """Cuts-per-30s timeline chart, or None if no data."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tl = result.metrics.scene_pacing.timeline_cuts_per_30s
    if not tl:
        return None

    fig, ax = plt.subplots(figsize=(5.2, 1.8), dpi=130)
    ax.plot(tl, color="#1f497d", linewidth=1.0)
    ax.fill_between(range(len(tl)), tl, alpha=0.20, color="#1f497d")
    ax.set_xlabel("30-second window", fontsize=7)
    ax.set_ylabel("Cuts", fontsize=7)
    ax.set_title("Cuts per 30-second window", fontsize=9)
    ax.tick_params(labelsize=7)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _tbl(data: list[list], col_widths: list[float], header: bool = True) -> Table:
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING",  (0, 0), (-1, -1), 11),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), ["#ffffff", "#f2f7fc"]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        style += [
            ("BACKGROUND",  (0, 0), (-1, 0), _BLUE),
            ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
            ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ]
    return Table(data, colWidths=col_widths, style=TableStyle(style))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_episode_pdf(result: "EpisodeResult", cfg: dict, dest: Path) -> None:
    """Write a one-page episode report PDF to *dest*."""
    S = _styles()
    doc = SimpleDocTemplate(
        str(dest), pagesize=letter,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        topMargin=0.75*inch, bottomMargin=0.75*inch,
    )
    story = []
    m = result.metrics
    c = m.sensory_load.components
    cfg_w = cfg.get("sensory_load_weights", {})

    # Header
    story.append(Paragraph("Formal-Feature Composite Report", S["title"]))
    story.append(Paragraph(f"<b>Episode:</b> {result.file}", S["body"]))
    if result.duration_sec:
        story.append(Paragraph(
            f"<b>Duration:</b> {result.duration_sec / 60:.1f} min  ({result.duration_sec:.0f} s)",
            S["body"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_BLUE, spaceAfter=6))

    # Score
    story.append(Paragraph("Formal-Feature Composite (FFC)", S["h2"]))
    story.append(Paragraph(f"{m.sensory_load.score:.3f}", S["score"]))
    story.append(Paragraph(
        "Configurable 0–1 composite; not a viewer-effect measure.", S["dim"]))
    if not m.sensory_load.audio_available:
        story.append(Paragraph("[Visual only — no audio track]", S["dim"]))
    story.append(Spacer(1, 6))

    # Component table
    story.append(Paragraph("Score Components", S["h2"]))
    comp_rows = [["Component", "Normalized Value", "Weight", "Contribution"]]
    component_data = [
        ("Pacing",     c.pacing,     cfg_w.get("pacing",         0.25), "pacing"),
        ("Saturation", c.saturation, cfg_w.get("saturation",     0.05), "saturation"),
        ("Contrast",   c.contrast,   cfg_w.get("color_contrast", 0.10), "color_contrast"),
        ("Motion",     c.motion,     cfg_w.get("motion",         0.25), "motion"),
        ("Flashing",   c.flashing,   cfg_w.get("flashing",       0.15), "flashing"),
        ("Audio",      c.audio,      cfg_w.get("audio",          0.20), "audio"),
    ]
    for label, val, wt, _ in component_data:
        if label == "Audio" and not m.sensory_load.audio_available:
            comp_rows.append([label, "n/a", f"{wt:.0%}", "n/a"])
        else:
            comp_rows.append([label, f"{val:.3f}", f"{wt:.0%}", f"{val * wt:.3f}"])
    cw = [1.8*inch, 1.5*inch, 1.0*inch, 1.3*inch]
    story.append(_tbl(comp_rows, cw))
    story.append(Spacer(1, 8))

    # Chart — component bars
    chart_png = _component_chart_png(result, cfg)
    story.append(RLImage(io.BytesIO(chart_png), width=5.2*inch, height=2.6*inch))
    story.append(Spacer(1, 4))

    # Timeline chart
    tl_png = _timeline_chart_png(result)
    if tl_png:
        story.append(RLImage(io.BytesIO(tl_png), width=5.2*inch, height=1.8*inch))
        story.append(Spacer(1, 4))

    # Metric detail table
    story.append(Paragraph("Metric Detail", S["h2"]))
    sl = m.shot_length
    sp = m.scene_pacing
    cs = m.color_saturation
    mo = m.motion
    fl = m.flashing
    au = m.audio
    detail_rows = [
        ["Metric", "Value"],
        ["Mean shot length",          f"{sl.mean_sec:.2f} s"],
        ["Median shot length",        f"{sl.median_sec:.2f} s"],
        ["Shots per minute",          f"{sl.shots_per_min:.1f}"],
        ["Total shots",               str(sl.count)],
        ["Cuts per minute",           f"{sp.cuts_per_min:.1f}"],
        ["Shot-length CV (rhythm)",   f"{sp.shot_length_cv:.3f}"],
        ["Color saturation mean",     f"{cs.mean:.3f}"],
        ["Color saturation variance", f"{cs.temporal_var:.4f}"],
        ["Color contrast mean",       f"{cs.contrast_mean:.3f}"],
        ["Motion mean",               f"{mo.mean:.4f}"],
        ["Motion peak",               f"{mo.peak:.4f}"],
        ["Flashing events / min",     f"{fl.luminance_delta_events_per_min:.2f}"],
    ]
    if au.available:
        detail_rows += [
            ["Audio RMS mean",        f"{au.rms_mean:.4f}"],
            ["Audio RMS peak",        f"{au.rms_peak:.4f}"],
            ["Dynamic range",         f"{au.dynamic_range_db:.1f} dB"],
        ]
    else:
        detail_rows.append(["Audio loudness", "n/a"])
    story.append(_tbl(detail_rows, [3.2*inch, 2.4*inch]))
    story.append(Spacer(1, 10))

    # Limitations
    story.append(HRFlowable(width="100%", thickness=0.5, color=_GREY, spaceAfter=4))
    story.append(Paragraph("<b>Honest Limitations</b>", S["dim"]))
    from analyzer.provenance import validation_short
    story.append(Paragraph(validation_short(),
                           S["limits"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(LIMITATIONS, S["limits"]))

    doc.build(story)


def export_show_pdf(
    agg: "ShowAggregate",
    results: "list[EpisodeResult]",
    cfg: dict,
    dest: Path,
) -> None:
    """Write a show-level aggregate report PDF to *dest*."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    S = _styles()
    doc = SimpleDocTemplate(
        str(dest), pagesize=letter,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        topMargin=0.75*inch, bottomMargin=0.75*inch,
    )
    story = []

    # Header
    story.append(Paragraph("Formal-Feature Composite Report", S["title"]))
    story.append(Paragraph(f"<b>Show:</b> {agg.show_name}", S["body"]))
    analyzed = agg.episode_count - agg.failed_count
    story.append(Paragraph(
        f"<b>Episodes analyzed:</b> {analyzed} of {agg.episode_count}"
        + (f"  ({agg.failed_count} failed)" if agg.failed_count else ""),
        S["body"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_BLUE, spaceAfter=6))

    # Aggregate table
    story.append(Paragraph("Aggregate Metrics (across all episodes)", S["h2"]))
    agg_rows = [["Metric", "Mean", "Median", "Std Dev", "Min", "Max"]]
    def _s(stat): return [f"{stat.mean:.3f}", f"{stat.median:.3f}",
                           f"{stat.std:.3f}",  f"{stat.min:.3f}", f"{stat.max:.3f}"]
    agg_rows.append(["Formal-Feature Composite (FFC)"] + _s(agg.sensory_load_score))
    agg_rows.append(["Cuts / min"]         + _s(agg.cuts_per_min))
    agg_rows.append(["Shot length mean (s)"]+ _s(agg.shot_length_mean_sec))
    agg_rows.append(["Color saturation"]   + _s(agg.color_saturation_mean))
    agg_rows.append(["Motion mean"]        + _s(agg.motion_mean))
    agg_rows.append(["Flashing events/min"]+ _s(agg.flashing_events_per_min))
    if agg.audio_rms_mean.mean > 0:
        agg_rows.append(["Audio RMS mean"]  + _s(agg.audio_rms_mean))
    else:
        agg_rows.append(["Audio RMS mean", "n/a", "n/a", "n/a", "n/a", "n/a"])
    cw2 = [2.4*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch]
    story.append(_tbl(agg_rows, cw2))
    story.append(Spacer(1, 10))

    # Formal-Feature Composite distribution chart
    ok_results = [r for r in results if r.status == "ok"]
    if ok_results:
        loads = [r.metrics.sensory_load.score for r in ok_results]
        names = [Path(r.file).stem[:18] for r in ok_results]
        fig, ax = plt.subplots(figsize=(5.4, max(1.4, 0.28 * len(loads))), dpi=130)
        y = list(range(len(loads)))
        ax.barh(y, loads, color="#1f497d", alpha=0.85)
        ax.set_yticks(y)
        ax.set_yticklabels(names, fontsize=7)
        ax.set_xlim(0, 1)
        ax.set_xlabel("FFC score", fontsize=8)
        ax.set_title("Formal-Feature Composite by Episode", fontsize=9)
        ax.axvline(agg.sensory_load_score.mean, color="#c00000", linestyle="--",
                   linewidth=1.0, label=f"Mean: {agg.sensory_load_score.mean:.3f}")
        ax.legend(fontsize=7)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        chart_h = max(1.4, 0.28 * len(loads))
        story.append(RLImage(io.BytesIO(buf.read()), width=5.4*inch, height=chart_h*inch))
        story.append(Spacer(1, 8))

    # Per-episode table
    if ok_results:
        story.append(Paragraph("Per-Episode Breakdown", S["h2"]))
        ep_rows = [["Episode", "Cut/m", "Sat", "Motion", "Flash", "Audio", "Load"]]
        for r in ok_results:
            m = r.metrics
            ep_rows.append([
                Path(r.file).name[:28],
                f"{m.scene_pacing.cuts_per_min:.1f}",
                f"{m.color_saturation.mean:.3f}",
                f"{m.motion.mean:.3f}",
                f"{m.flashing.luminance_delta_events_per_min:.1f}",
                f"{m.audio.rms_mean:.4f}" if m.audio.available else "n/a",
                f"{m.sensory_load.score:.3f}",
            ])
        for r in results:
            if r.status == "failed":
                ep_rows.append([Path(r.file).name[:28], "FAILED", "", "", "", "", ""])
        cw3 = [2.5*inch, 0.6*inch, 0.55*inch, 0.65*inch, 0.6*inch, 0.65*inch, 0.55*inch]
        story.append(_tbl(ep_rows, cw3))
        story.append(Spacer(1, 10))

    # Limitations
    story.append(HRFlowable(width="100%", thickness=0.5, color=_GREY, spaceAfter=4))
    story.append(Paragraph("<b>Honest Limitations</b>", S["dim"]))
    from analyzer.provenance import validation_short
    story.append(Paragraph(validation_short(),
                           S["limits"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(LIMITATIONS, S["limits"]))

    doc.build(story)
