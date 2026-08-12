# CMAT — Stack

Facts that matter to maintaining the project. **Do not substitute a dependency
without asking** — several were chosen for a reason recorded in
`DECISIONS.md`.

---

## Runtime

| | |
|---|---|
| Language | **Python 3.11+** (developed and tested on 3.13) |
| Platform | **Windows** — this is a Windows desktop application, not cross-platform-first |
| Distribution | PyInstaller (`build/`, `dist/`); FFmpeg shipped separately in the GitHub release |

Windows is a product constraint, not an accident: file dialogs, keyboard
conventions, window management, DPI and accessibility all follow the platform.
Nothing may trade a Windows behaviour for a visual effect.

## Analysis

| Purpose | Choice | Notes |
|---|---|---|
| Cut / scene detection | **PySceneDetect** | `ContentDetector` / `AdaptiveDetector` |
| Cut detection (optional) | **TransNetV2** | finds ~5–7% more transitions — see the corpus warning below |
| Frame analysis | **OpenCV** + **NumPy** | one shared frame pass for colour, motion, flashing |
| Audio | **FFmpeg** | must be on PATH; located by `analyzer/ffmpeg_path.py` |
| Aggregation / export | **pandas** | |
| Speech (optional) | **faster-whisper** | only runs when no caption file is found |
| Language metrics | **spaCy**, **wordfreq** | **English only** |

**Detectors are not interchangeable within one corpus.** A half-migrated index
makes pacing incomparable across shows — migrate all or none.

## Interface

| Purpose | Choice | Notes |
|---|---|---|
| GUI (shipping) | **Tkinter** | `gui*.py` — the front-end users actually run |
| GUI (in progress) | **PySide6** (Qt 6) | `ui/` — the replacement being built |
| Charts | **matplotlib** | `FigureCanvasQTAgg`; imported lazily — it costs ~1s to load |
| Video playback | **python-vlc** + **VLC** | hand coding only; 64-bit VLC required to match the interpreter |

**No web frameworks.**

### Why VLC and not QMediaPlayer

Coding means naming the moment something happens. On Windows `QMediaPlayer`
goes through Media Foundation, where a seek lands on the nearest keyframe
rather than the frame asked for — a coder would record the wrong timestamp
with no way to tell. libvlc decodes and steps frames itself.

VLC is a real external dependency. `ui/player.available()` reports its absence
and the Human coding tab disables itself with the reason, rather than opening
a black rectangle.

## Qt facts that are not guessable

Recorded because each cost real time. Fuller notes in `LEARNINGS.md` and
`ui/DESIGN.md` §0.4.

- **Qt Style Sheets are not CSS.** Different selector language; no flexbox or
  grid, no `box-shadow`, `text-shadow`, `inset`, `line-height`, or structural
  pseudo-classes. Widget chrome must be translated, never pasted.
- **QSS selectors do not match up an inheritance chain.** A rule for
  `QTreeWidget` does not apply to a `QTreeView`.
- **Stylesheet `px` are device-independent** and scale with the display's
  device-pixel ratio. This reverses the Tk rule, where a pixel was physical —
  which is why `FONT_PT` still exists and is marked Tk-only.
- **`QTextDocument` overrides `h1`–`h6` sizes** with its own font-size
  adjustment, which survives the stylesheet. Use classed paragraphs.
- **A bare `QWidget` ignores a stylesheet background** unless
  `WA_StyledBackground` is set. `QFrame` does not need it.
- **`transparent` is not a valid gradient stop** — Qt substitutes white.
- Qt 6 is per-monitor DPI aware by default. **Do not add `ctypes` DPI calls.**

## Layout of dependencies

`requirements.txt` is the source of truth for versions. Optional dependencies
are registered in `analyzer/optional_tools.py` so a missing one degrades to a
clear message rather than a traceback.
