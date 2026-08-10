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

from ui import reference_css
from ui.tokens import COLORS as C

# Qt's rich text engine supports a practical subset of CSS 2.1: it honours
# borders, background-color, padding, font properties and table attributes,
# but not flexbox, custom properties, border-collapse, box-shadow, or the
# structural pseudo-classes. So: cellspacing=0 instead of border-collapse, and
# the label column is marked with a class rather than reached by :first-child.
#
# Headings are classed paragraphs rather than h1/h2. Qt's HTML importer gives
# h1-h6 a font-size ADJUSTMENT of its own, which survives the stylesheet: a
# rule of 13px on an h1 was still rendering near 24px. That is not a size the
# CSS can win, so the elements are avoided entirely.
#
# One table idiom throughout. The report used to switch to a key/value grid
# between sections; that switch made neighbouring tables read as unrelated
# things.
#
# The reference's OWN rules for these components, lifted from ui/reference/,
# not transcribed, so the markup uses the reference's class names and its CSS
# applies unchanged.
#
# The TABLE is the exception, and deliberately. The mockup's .data-table is a
# native grid — white ground, two border weights, zebra striping. The tables
# here are the academic-presentation surface of the tool, so they follow
# MediaWiki's .wikitable instead, which differs in four specific ways:
#
#   * one border weight throughout, #A2A9B1, outer and inner alike;
#   * a #F8F9FA ground rather than white, so the table reads as a block set
#     into the page rather than as part of it;
#   * a #EAECF0 header, bluish rather than neutral grey, with CENTRED headings;
#   * no zebra striping — the tinted ground already separates the table from
#     the page, and banding on top of it is one device too many.
_REFERENCE = reference_css.rules((
    "section-title", "sub-text", "info-banner", "info-title",
    "results-container", "fieldset", "legend",
))

STYLE = _REFERENCE + f"""
body {{ color: {C['text']}; font-size: 11px; }}
p {{ margin: 3px 0; }}

table.wikitable {{ background-color: {C['mw_subtle_bg']};
                   color: {C['text']};
                   border: 1px solid {C['mw_border']};
                   margin: 6px 0 8px 0; }}
table.wikitable th {{ background-color: {C['mw_header_bg']};
                      border: 1px solid {C['mw_border']};
                      padding: 3px 6px; font-weight: bold;
                      text-align: center; }}
table.wikitable td {{ border: 1px solid {C['mw_border']};
                      padding: 3px 6px; text-align: right; }}
/* Qt's rich text engine has no :first-child, so the label column is marked. */
table.wikitable th.l, table.wikitable td.l {{ text-align: left; }}
/* A prose cell in an otherwise numeric table. */
table.wikitable td.n {{ color: {C['text_dim']}; font-size: 10px;
                        text-align: left; font-style: italic; }}
/* The MediaWiki caption: above the table, naming what it holds. */
table.wikitable caption {{ font-weight: bold; text-align: left;
                           padding: 0 0 2px 0; }}

.title {{ font-size: 12px; font-weight: bold; margin: 0; }}
.score {{ font-size: 20px; font-weight: bold; color: {C['status_complete']}; }}
.scorenote {{ color: {C['text_dim']}; }}
.pct {{ color: {C['accent_dark']}; margin: 2px 0 6px 0; }}
.dim {{ color: {C['text_dim']}; }}
.note {{ color: {C['text_dim']}; font-style: italic; font-size: 10px; }}
.warn {{ background: {C['warn_bg']}; border: 1px solid {C['warn_border']};
         color: {C['warn_text']}; font-size: 10px; padding: 6px 8px; }}
"""

# The reference gives the key column a fixed 140px. Qt's rich text layout wants
# it as a column width on the cell, not a stylesheet rule.
_KEY_W = 140

# Marks a column of prose rather than figures: left aligned, muted, and
# with a blank header, since "Note" as a heading is pure noise.
NOTE = object()


def _e(v) -> str:
    return escape(str(v), quote=False)


def _table(headers, rows, first_col_width: int | None = None) -> str:
    """A MediaWiki-style table: centred headers over right-aligned figures.

    Every table in the report takes this one form. The first column is the
    label and stays left-aligned; the rest are figures. A column headed NOTE
    holds prose rather than a figure, so it keeps the left alignment and takes
    the muted note styling.
    """
    note_cols = {i for i, h in enumerate(headers) if h == NOTE}
    w = f' width="{first_col_width}"' if first_col_width else ""

    def cell(tag: str, j: int, text) -> str:
        cls = "l" if j == 0 else ("n" if j in note_cols else "")
        attrs = f' class="{cls}"' if cls else ""
        if j == 0 and w:
            attrs += w
        return f"<{tag}{attrs}>{_e(text)}</{tag}>"

    out = ['<table class="wikitable" cellspacing="0" cellpadding="0" width="100%">',
           "<tr>"]
    out += [cell("th", j, "" if h == NOTE else h)
            for j, h in enumerate(headers)]
    out.append("</tr>")
    for row in rows:
        out.append("<tr>")
        out += [cell("td", j, v) for j, v in enumerate(row)]
        out.append("</tr>")
    out.append("</table>")
    return "".join(out)


def _props(label: str, rows) -> str:
    """A measurement table: label, value, and a note explaining the value."""
    return _table((label, "Value", NOTE), rows,
                  first_col_width=_KEY_W)


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
    parts: list[str] = [f'<p class="title">{_e(result.file)}</p>']

    if result.duration_sec:
        parts.append(
            f'<p class="sub-text">Duration {result.duration_sec / 60:.1f} min '
            f'({result.duration_sec:.0f} s)</p>')

    if result.status == "failed":
        parts.append(f'<p class="warn">Analysis failed: {_e(result.error)}</p>')
        return _document("".join(parts))

    # --- sensory load -------------------------------------------------------
    sl = m.sensory_load
    parts.append('<p class="section-title">Sensory load</p>')
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
    body = []
    for label, val, wt in comps:
        if label == "Audio" and not sl.audio_available:
            body.append(("Audio", "n/a", f"{wt:.0%}", "—"))
        else:
            body.append((label, f"{val:.3f}", f"{wt:.0%}", f"{val * wt:.3f}"))
    parts.append(_table(
        ("Component", "Normalised", "Weight", "Contribution"), body))

    # --- measured features --------------------------------------------------
    shot, pace = m.shot_length, m.scene_pacing
    col, mot, fla = m.color_saturation, m.motion, m.flashing
    parts.append('<p class="section-title">Measured features</p>')
    parts.append(_props("Feature", [
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
    parts.append('<p class="section-title">Audio</p>')
    if au.available:
        parts.append(_props("Audio", [
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
    parts.append('<p class="section-title">Speech</p>')
    if sp.available:
        src = {"srt": "SRT subtitle file", "vtt": "VTT subtitle file",
               "whisper": "Whisper transcription"}.get(sp.source, sp.source)
        parts.append(_props("Speech", [
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
    parts.append('<p class="section-title">Fantastical events (hand-coded)</p>')
    if events:
        win = events.get("window")
        win_txt = (f"{win[0]:.0f}–{win[1]:.0f}s"
                   if isinstance(win, (list, tuple)) and len(win) == 2
                   else "full episode")
        parts.append(_props("Hand coding", [
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
        parts.append('<p class="section-title">Measured with</p>')
        rows = []
        ungraded = []
        for key, desc in tools.items():
            if desc == "disabled":
                continue
            label = key.replace("_", " ").capitalize()
            rows.append((label, desc, ""))
            if "[unvalidated]" in desc or "[experimental]" in desc:
                ungraded.append(label)
        parts.append(_props("Measurement", rows))
        if ungraded:
            parts.append(
                f'<p class="warn">Not graded against hand coding: '
                f'{_e(", ".join(ungraded))}. Treat these as exploratory; do '
                f'not report them as validated measures.</p>')

    return _document("".join(parts))


def _document(body: str) -> str:
    return f"<html><head><style>{STYLE}</style></head><body>{body}</body></html>"
