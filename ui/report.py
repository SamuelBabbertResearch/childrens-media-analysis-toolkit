"""
ui/report.py — the analysis report, as HTML.

This is the clearest single argument for the move. Under Tkinter the report was
a Text widget with monospace padding, and making it look like a research write-up
meant embedding widget-based tables one at a time and tying 1px frames to the
widget width to fake a section rule. Here it is a document: MediaWiki table
markup and a stylesheet, rendered by QTextBrowser.

Pure presentation — takes an EpisodeResult or ShowAggregate and returns a
string. No Qt imports, so it is testable without a display and could be reused
for the PDF export and the static site.

Guardrail: nothing here reports appropriateness, target age, or educational
value. Unusual values are marked with a glyph and an explicit legend naming the
comparison set, never with a colour that reads as a verdict.
"""

from __future__ import annotations

from html import escape

from ui.tokens import COLORS as C

# Qt's rich text engine supports a practical subset of CSS 2.1: it honours
# borders, background-color, padding, font properties and table attributes,
# but not flexbox, custom properties, or border-collapse. The markup below
# stays inside that subset — hence cellspacing=0 rather than border-collapse.
STYLE = f"""
body {{ color: {C['text']}; }}
h1 {{ font-size: 15pt; font-weight: bold; margin: 0 0 2px 0; }}
h2 {{ font-size: 11pt; font-weight: bold; color: {C['text']};
      margin: 16px 0 4px 0; border-bottom: 1px solid {C['mw_border']};
      padding-bottom: 2px; }}
p  {{ margin: 3px 0; }}
.lead   {{ color: {C['text_dim']}; margin: 0 0 10px 0; }}
.score  {{ font-size: 20pt; font-weight: bold; color: {C['status_complete']}; }}
.scorenote {{ color: {C['text_dim']}; }}
.pct    {{ color: {C['accent_dark']}; margin: 2px 0 8px 0; }}
.dim    {{ color: {C['text_dim']}; }}
.note   {{ color: {C['text_faint']}; font-size: 8pt; }}
.warn   {{ color: {C['warn_text']}; background: {C['warn_bg']};
           padding: 6px 8px; }}
table.wikitable {{ background: {C['mw_bg']}; margin: 6px 0 4px 0; }}
table.wikitable th {{ background: {C['mw_header_bg']}; color: {C['text']};
                      border: 1px solid {C['mw_border']}; padding: 4px 7px;
                      font-weight: bold; text-align: right; }}
table.wikitable th.l {{ text-align: left; }}
table.wikitable td {{ border: 1px solid {C['mw_border']}; padding: 3px 7px;
                      text-align: right; }}
table.wikitable td.l {{ text-align: left; }}
table.wikitable td.k {{ background: {C['mw_label_bg']}; font-weight: bold;
                        text-align: left; }}
table.wikitable td.n {{ color: {C['text_dim']}; font-size: 8pt;
                        text-align: left; }}
"""


def _e(v) -> str:
    return escape(str(v), quote=False)


def _props(rows) -> str:
    """A label/value(/note) table — the MediaWiki definition-list idiom."""
    out = ['<table class="wikitable" cellspacing="0" cellpadding="0">']
    for row in rows:
        label, value = row[0], row[1]
        note = row[2] if len(row) > 2 else ""
        out.append(
            f'<tr><td class="k">{_e(label)}</td>'
            f'<td>{_e(value)}</td>'
            f'<td class="n">{_e(note)}</td></tr>')
    out.append("</table>")
    return "".join(out)


def _ordinal(n: int) -> str:
    if n <= 0:
        return "lowest"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(
        n % 10 if n % 100 not in (11, 12, 13) else 0, "th")
    return f"{n}{suffix}"


def episode_html(result, percentile: dict | None = None,
                 events: dict | None = None) -> str:
    """Render one episode's analysis as a document."""
    m = result.metrics
    parts: list[str] = [f"<h1>{_e(result.file)}</h1>"]

    if result.duration_sec:
        parts.append(
            f'<p class="lead">Duration {result.duration_sec / 60:.1f} min '
            f'({result.duration_sec:.0f} s)</p>')

    if result.status == "failed":
        parts.append(f'<p class="warn">Analysis failed: {_e(result.error)}</p>')
        return _document("".join(parts))

    # --- sensory load -------------------------------------------------------
    sl = m.sensory_load
    parts.append("<h2>Sensory load</h2>")
    parts.append(f'<p><span class="score">{sl.score:.3f}</span>'
                 f'<span class="scorenote">&nbsp;&nbsp;0 = low stimulation, '
                 f'1 = high</span></p>')
    if not sl.audio_available:
        parts.append('<p class="dim">Visual only — no audio track.</p>')

    if percentile:
        line = (f"{_ordinal(percentile['percentile'])} of "
                f"{percentile['global_total']} indexed episodes")
        if percentile.get("show_total", 0) >= 3:
            line += (f"; {_ordinal(percentile['show_rank'])} of "
                     f"{percentile['show_total']} in "
                     f"{percentile['show_name']}")
        parts.append(f'<p class="pct">{_e(line)}.</p>')

    # Contribution = normalised value x weight. A bar chart showed the
    # normalised value alone, which cannot explain the composite sitting
    # above it: saturation at 0.372 contributes less than contrast at 0.560.
    cfg = result.config.get("sensory_load_weights", {})
    c = sl.components
    comps = [
        ("Pacing",     c.pacing,     cfg.get("pacing", 0.25)),
        ("Saturation", c.saturation, cfg.get("saturation", 0.05)),
        ("Contrast",   c.contrast,   cfg.get("color_contrast", 0.10)),
        ("Motion",     c.motion,     cfg.get("motion", 0.25)),
        ("Flashing",   c.flashing,   cfg.get("flashing", 0.15)),
        ("Audio",      c.audio,      cfg.get("audio", 0.20)),
    ]
    rows = ['<table class="wikitable" cellspacing="0" cellpadding="0">'
            '<tr><th class="l">Component</th><th>Normalised</th>'
            '<th>Weight</th><th>Contribution</th></tr>']
    for label, val, wt in comps:
        if label == "Audio" and not sl.audio_available:
            rows.append(f'<tr><td class="l">Audio</td><td class="dim">n/a</td>'
                        f'<td>{wt:.0%}</td><td class="dim">—</td></tr>')
            continue
        rows.append(f'<tr><td class="l">{label}</td><td>{val:.3f}</td>'
                    f'<td>{wt:.0%}</td><td>{val * wt:.3f}</td></tr>')
    rows.append("</table>")
    parts.append("".join(rows))

    # --- measured features --------------------------------------------------
    shot, pace = m.shot_length, m.scene_pacing
    col, mot, fla = m.color_saturation, m.motion, m.flashing
    parts.append("<h2>Measured features</h2>")
    parts.append(_props([
        ("Cuts per minute", f"{pace.cuts_per_min:.1f}", ""),
        ("Mean shot length", f"{shot.mean_sec:.2f} s", ""),
        ("Median shot length", f"{shot.median_sec:.2f} s", ""),
        ("Shots per minute", f"{shot.shots_per_min:.1f}", ""),
        ("Total shots", f"{shot.count:,}", ""),
        ("Shot-length CV", f"{pace.shot_length_cv:.3f}",
         "rhythm variability; higher is burstier"),
        ("Colour saturation", f"{col.mean:.3f}",
         f"temporal variance {col.temporal_var:.4f}"),
        ("Colour contrast", f"{col.contrast_mean:.3f}",
         "spatial spread of brightness"),
        ("Motion (mean)", f"{mot.mean:.4f}", f"peak {mot.peak:.4f}"),
        ("Flashing events/min",
         f"{fla.luminance_delta_events_per_min:.2f}",
         "whole-frame luminance change"),
    ]))

    # --- audio --------------------------------------------------------------
    au = m.audio
    parts.append("<h2>Audio</h2>")
    if au.available:
        parts.append(_props([
            ("RMS mean", f"{au.rms_mean:.4f}", ""),
            ("RMS peak", f"{au.rms_peak:.4f}", ""),
            ("Temporal variance", f"{au.rms_temporal_var:.6f}",
             "volume variation over time"),
            ("Dynamic range", f"{au.dynamic_range_db:.1f} dB",
             "peak-to-mean ratio"),
        ]))
    else:
        parts.append('<p class="dim">Not available — FFmpeg not found, or the '
                     'file has no audio track.</p>')

    # --- speech -------------------------------------------------------------
    sp = m.speech
    parts.append("<h2>Speech</h2>")
    if sp.available:
        src = {"srt": "SRT subtitle file", "vtt": "VTT subtitle file",
               "whisper": "Whisper transcription"}.get(sp.source, sp.source)
        parts.append(_props([
            ("Words per minute", f"{sp.words_per_minute:.1f}", ""),
            ("Speech density", f"{sp.speech_density:.1%}",
             "share of runtime containing dialogue"),
            ("Total words", f"{sp.total_words:,}", ""),
            ("Source", src, "English-only metrics"),
        ]))
    else:
        parts.append('<p class="dim">Not available — no caption file found. '
                     'Add an .srt/.vtt beside the video, or enable Whisper in '
                     'Settings.</p>')

    # --- hand coding --------------------------------------------------------
    parts.append("<h2>Fantastical events (hand-coded)</h2>")
    if events:
        win = events.get("window")
        win_txt = (f"{win[0]:.0f}–{win[1]:.0f}s"
                   if isinstance(win, (list, tuple)) and len(win) == 2
                   else "full episode")
        parts.append(_props([
            ("Events per minute", events.get("events_per_min", "—"), ""),
            ("Events coded", events.get("n_events", "—"), f"window {win_txt}"),
            ("Coded", events.get("date", "—"), "per EVENT_CODEBOOK.md"),
        ]))
        parts.append('<p class="note">A human judgement, not a pixel '
                     'measurement.</p>')
    else:
        parts.append('<p class="dim">Not coded. Fantasy is a semantic '
                     'judgement no formal-features measure can make; code it '
                     'under Human coding → Code.</p>')

    # --- provenance ---------------------------------------------------------
    tools = getattr(result, "measurement_tools", None) or {}
    if tools:
        parts.append("<h2>Measured with</h2>")
        rows = []
        ungraded = []
        for key, desc in tools.items():
            if desc == "disabled":
                continue
            label = key.replace("_", " ").capitalize()
            rows.append((label, desc, ""))
            if "[unvalidated]" in desc or "[experimental]" in desc:
                ungraded.append(label)
        parts.append(_props(rows))
        if ungraded:
            parts.append(
                f'<p class="warn">Not graded against hand coding: '
                f'{_e(", ".join(ungraded))}. Treat these as exploratory; do '
                f'not report them as validated measures.</p>')

    return _document("".join(parts))


def _document(body: str) -> str:
    return f"<html><head><style>{STYLE}</style></head><body>{body}</body></html>"
