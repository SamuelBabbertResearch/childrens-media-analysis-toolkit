# Children's Media Analysis Toolkit (CMAT) — Project Reference

All phases (0–5) are complete. This file documents what's built, the architecture rules,
and gotchas to be aware of when adding new features.

---

## Goal

A desktop Windows application that analyzes MP4 episodes of children's TV shows and produces a
**sensory-load profile** for each episode and a **cumulative profile** for a whole show. The tool
measures formal/structural features of the video (pacing, color, motion). It does **not** issue a
verdict on "appropriateness" — it presents transparent, labeled metrics that a person interprets.
Every composite score must show its component parts.

---

## Stack (do not substitute without asking)

- Language: **Python 3.11+** (tested on 3.13)
- Cut / scene detection: **PySceneDetect**
- Frame analysis: **OpenCV** (`opencv-python`) + **NumPy**
- Audio metrics: **FFmpeg** (must be on PATH)
- Aggregation / export: **pandas**
- GUI: **Tkinter** (standard library) — plain and classic; no Qt, no web frameworks
- Charts: **matplotlib** embedded in Tk

---

## Architecture (non-negotiable)

1. **`analyzer/` package** — pure analysis engine, zero GUI imports. Each metric is an isolated,
   independently testable function: input = video path + config, output = numbers.
2. **`cli.py`** — runs the engine on one file or a folder, writes JSON/CSV. The GUI is a thin
   layer over this same engine — never duplicate analysis logic in the UI.
3. **GUI worker thread** — all analysis runs on a background thread with a progress callback.
   The UI must never freeze.

---

## What's built (feature inventory)

### Analysis engine (`analyzer/`)
- `engine.py` — per-episode analysis: shot_length, scene_pacing, color_saturation,
  color_contrast, motion, flashing, audio (FFmpeg RMS + dynamic range), sensory_load composite
- `batch.py` — batch runner with per-episode progress callback; skips/logs failures
- `aggregate.py` — show-level aggregate (mean/median/stddev per metric); writes JSON + CSV
- `cache.py` — disk cache at `<root>/.analysis/<show_key>/<episode_stem>.json`
- `db.py` — SQLite index at `<root>/.analysis/index.db`; upsert on every analysis
- `show_index.py` — folder discovery supporting one level of category nesting
- `schema.py` — `EpisodeResult` and `ShowAggregate` dataclasses

### GUI (`gui.py`)
- **Library tab**: tree of categories → shows → episodes; `[analyzed]` label on cached episodes
- **Index tab**: two sub-tabs (All Episodes / All Shows), sortable `ttk.Treeview` columns,
  live filter bar, double-click to view details, Refresh Index button
- **Results panel**: metric table with sensory-load score + all components; percentile rank
  against indexed episodes; cuts-per-30s timeline chart (matplotlib); Export JSON/CSV/PDF buttons
- **Toolbar**: Root folder chooser; preset combobox (re-scores instantly from cache); Settings button
- **Settings dialog**: edit sensory-load weights and normalization ceilings per preset;
  Apply & Re-score (instant, no re-analysis); Save as Preset / Save as Default
- **Analysis queue**: enqueue multiple episodes; progress bar with live cut-detection pulse
- **Episode notes**: text field per episode, saved to SQLite
- **Compare**: Pin for Compare → Compare with Pinned (side-by-side metric table)
- **Remove Stale**: scans index for entries whose video file no longer exists
- **Help → About metrics**: scrollable reference with research grounding and preset guidance

### Config (`config.json`)
Seven built-in presets: General / All Ages, Toddler (0-2), Preschool (2-5), Early Childhood (5-8),
Tween (8-12), Animated / Cartoon, Live-Action / YouTube. Each has its own `sensory_load_weights`
and `normalization_reference_ranges`. User can save custom presets; built-ins cannot be deleted.

### CLI (`cli.py`)
```
python cli.py analyze <file.mp4>          # single episode → JSON
python cli.py analyze <show_folder>       # batch → per-episode JSON + aggregate
python cli.py db episodes <root>          # list indexed episodes (sortable)
python cli.py db shows <root>             # list indexed shows
```

---

## Folder / data convention

```
<root>/
  ShowName/                  ← flat show (MP4s directly inside)
    ep01.mp4
  CategoryName/              ← category (no direct MP4s)
    ShowName/                ← show inside category
      ep01.mp4
  .analysis/
    ShowName/
      ep01.json              ← cached episode result
      aggregate.json / .csv
    CategoryName/
      ShowName/
        ep01.json
    index.db                 ← SQLite index (all analyzed episodes/shows)
```

`show_key(root, show_dir)` returns the POSIX relative path (e.g. `"CategoryName/ShowName"`),
used as both the cache subfolder and the DB primary key.

---

## Metric definitions

- **Shot length** — PySceneDetect content detection → cut timestamps → gaps between cuts.
  Report mean, median, shots-per-minute, count. Shorter = faster.
- **Scene pacing** — Derived from the same cut series: cut rate (cuts/min), variability
  (coefficient of variation = std/mean), rolling "cuts per 30s" timeline array.
  Captures *rhythm* distinct from raw shot length.
- **Color saturation** — Sample frames at `sample_fps` (default 2), convert to HSV, mean of
  S channel per frame. Report mean and temporal variance.
- **Color contrast** — Same frame sample; per-frame standard deviation of V (luminance) channel.
  Captures visual intensity / dramatic lighting.
- **Motion** — Normalized mean absolute frame difference between consecutive sampled frames.
  Method is pluggable (Farneback optical flow can be swapped in). Report mean and peak.
- **Flashing** — Count luminance-change events exceeding `flashing_luminance_threshold` between
  sampled frames; report events per minute. Photosensitivity / overstimulation concern.
- **Audio** — FFmpeg: RMS loudness (mean and peak) and dynamic range (dB). Folded into
  sensory_load as a weighted component.
- **Sensory load** — Weighted composite of normalized sub-metrics. Uses fixed reference ranges
  (NOT per-corpus normalization) so scores are comparable across separate runs. Always output
  both the composite score and all normalized components.

---

## Known design decisions and gotchas

### Cache is path-based
`cache_path = root / ".analysis" / show_key / f"{episode_stem}.json"`. If the user renames a
show folder, moves it into a category, or renames episode files, the cache entry is orphaned and
analysis appears to "disappear." The Remove Stale button finds the reverse (cache with no video).
**Future improvement**: use a content hash (file size + duration) as the key instead of filename.

### Tkinter pack order in toolbar
`side=tk.BOTTOM` widgets (and `side=tk.RIGHT`) must be packed **before** any `expand=True`
widget, otherwise Tkinter allocates all space to the expandable widget first and the later
widget gets zero height/width. The root-folder label uses `expand=True`, so all right-side
toolbar widgets are packed before it.

### Progress bar animation
Use `after()` timer-based polling on a `ttk.Progressbar` in determinate mode, not
`progressbar.start()` in indeterminate mode. The indeterminate animation freezes during
long Python operations because it needs the event loop.

### ttk.Combobox tooltip on Windows
`ttk.Combobox` on Windows uses the native Win32 COMBOBOX control. Mouse events (`<Enter>`,
`<Motion>`) route to the internal native subwindow and do NOT fire at the Tkinter widget level.
`_WidgetTooltip` will not show on a combobox regardless of binding strategy. The preset
tooltip text is available via Help → About metrics instead.

### DPI scaling
Tkinter reports `winfo_screenwidth()` in logical pixels. The physical display resolution may
differ. The `SettingsDialog` centers itself using `winfo_rootx()` / `winfo_width()`, which
works correctly at runtime; be cautious with any hardcoded pixel sizes.

---

## Research grounding (condensed)

The tool measures **formal features** of video (Huston & Wright framework) — content-independent
structural attributes that trigger the **orienting response** (automatic attention reallocation
toward novel stimuli). Lang's **LC4MP** provides the resource account: each cut/edit consumes
finite processing capacity.

Per-metric literature hooks:
- **Pacing** — Lillard & Peterson (2011, *Pediatrics*): fast-paced cartoon → immediate EF
  decrements in 4-year-olds. Lillard et al. (2015): fantastical content may matter as much as
  raw pace. Present pacing as an associated factor, not a cause.
- **Motion** — Itti & Koch: high motion is a pre-attentive bottom-up attention magnet.
- **Flashing** — Photosensitive-epilepsy guidance; 1997 broadcast incident. Clearest safety rationale.
- **Sensory load composite** — Christakis et al. (2004, *Pediatrics*): correlational association
  between early heavy TV exposure and later attention problems (contested; correlational only).

**Always use correlational language. Never state a feature *causes* an outcome.**
The tool measures the stimulus, not the viewer. Age, temperament, sensory-processing profile,
and viewing dose are not captured.

Full reference scaffold: Huston & Wright, Lang (LC4MP), Lillard & Peterson (2011),
Lillard et al. (2015), Christakis et al. (2004), Itti & Koch, Anderson & Pempek,
Goodrich/Pempek/Calvert. Verify before formal citation.
