# CMAT — Learnings

Things that went wrong, why, and how to avoid them. Architecture choices belong
in `DECISIONS.md`, not here.

Format: **what went wrong** · why · how to avoid it.

---

## Measurement and calibration

These are the recurring ways the numbers have been wrong. Every one was caught
by a result disagreeing with obvious judgement — which is the main quality
control this project has, and worth using deliberately.

### Metric names that mislead
**What.** Four numbers read as something other than what they measure.
**Why.** Each is a reasonable name for a slightly different quantity:

| Reads as | Actually is |
|---|---|
| `words_per_minute` — talkativeness | speech rate **while speaking** (divides by dialogue time, not runtime) |
| `contrast_mean` — change between frames | **spatial** brightness spread *within* a frame, averaged |
| `dynamic_range_db` — peak to noise floor | **peak-to-mean** ratio |
| `temporal_var` — a standard deviation | a **variance** |

**Avoid.** Check `ARCHITECTURE.md` §8 before interpreting any of them, and pair
WPM with `speech_density` whenever it is shown.

### The composite silently ignores most of what is measured
**What.** Assuming "sensory load" summarises everything CMAT measures.
**Why.** Only six inputs are scored. Shot length, `shot_length_cv`, motion
peak, audio peak and variance, dynamic range, all speech and vocabulary
metrics, dissolves, scene relation and hand-coded events are **reported and not
scored**.
**Avoid.** Two episodes with identical composites can differ enormously on
things the composite never looked at. Name the metric rather than the composite
when the metric is what matters.

### Values above the ceiling are indistinguishable
**What.** Under a tight preset, very different shows post identical component
scores.
**Why.** Normalization is min-max against a fixed range and **clamped to
[0,1]** — everything above the ceiling is 1.0.
**Avoid.** Expected behaviour of a fixed range, not a bug. When a comparison
looks flat, re-read it under a broader preset before concluding the shows are
alike. See also the ceiling entry below.

### A no-audio episode is scored differently, not just differently sourced
**What.** Comparing a 0.30 with audio against a 0.30 without.
**Why.** Missing audio redistributes its weight proportionally across the five
visual metrics. The score stays on 0–1 but is not composed the same way.
**Avoid.** Check `sensory_load.audio_available` before any comparison.

### Zero cuts can mean a slow episode or a failed detection
**What.** `cuts_per_min` 0.0 with `shot_length_cv` 0.0 looks like a valid
measurement of very slow content.
**Why.** No detected cuts yields one shot spanning the whole file.
**Avoid.** Treat an exact zero as suspect and check the video before believing
it.

### Rankings invert when a show has too few episodes
**What.** *Little Bear* ranked above *SpongeBob*; lectures ranked above
*Bluey*; *Franklin* looked wrong.
**Why.** Small-N artifacts. A handful of episodes from one show against a full
season of another is not a comparison. Adding more *Franklin* episodes made the
ordering resolve itself with no code change.
**Avoid.** Before believing a cross-show ranking, check the episode counts on
both sides. Treat a corpus-wide index as provisional until the shows in it are
sampled comparably.

### A ceiling can compress the difference it exists to show
**What.** Under the General preset, *Bluey* at 11.1 cuts/min read as only 18.5%
of the pacing scale, so its pacing advantage over a lecture almost vanished.
**Why.** The 60 cuts/min ceiling is set for the fastest content that exists, so
ordinary children's television sits in the bottom fifth of it.
**Avoid.** This is a real property of fixed reference ranges, not a bug — it is
why presets exist and why tight presets carry an explicit note. When a
comparison looks flat, check which ceiling is in force before changing weights.

### Feature-length films do not belong in an episode ranking untagged
**What.** *Ocean Waves* (72 minutes) ranked implausibly high.
**Why.** Format confound: a film is not an episode, and per-minute rates plus
equal weighting do not make it one.
**Avoid.** Keep films and episodes distinguishable in the corpus, and be
suspicious of any ranking where a feature sits among half-hour episodes.

### Renaming a show folder silently invalidated its data
**What.** A folder renamed from the show's title to a studio name kept showing
the old title in the index, with figures "way off".
**Why.** The cache is keyed on the path (`.analysis/<show_key>/<stem>.json`) and
the index row is keyed on the file path. Renaming orphans the cache and leaves
the old index rows behind — first hit **2026-06-28**, and the same root cause
as the duplicate-rows bug below.
**Avoid.** Re-analyse after moving or renaming anything. The durable fix is to
key the cache on a content hash (size + duration) — still open, see
`ROADMAP.md`.

### Seasons in subfolders get treated as separate shows
**What.** Season folders inside a show folder were repeatedly conflated with
shows — "it is still conflating season files within a show file as different
shows", and full-series aggregates would not produce.
**Why.** The convention discovers exactly one level of nesting, so
`Show/Season 1/*.mp4` reads as category `Show` containing show `Season 1`.
**Avoid.** Know that this is the convention behaving as designed, not a bug —
selecting `Arthur` correctly reports that it groups shows. If a true
show-across-seasons aggregate is needed, that is a feature, not a fix.

### The sampler's CSV paths did not match the cache's keys
**What.** Loading a sampling template failed to find already-analysed episodes;
it recurred after a restart.
**Why.** The sampler wrote paths in one form and `show_key()` derived another.
**Avoid.** The same class of defect as the duplicate index rows: **one spelling
of a path, normalised at the choke point.** Any new component that writes a
path into a file is a candidate for this bug.

## Reporting and correctness

### Unanalysed episodes were reported as failures
**What.** The first show-aggregate report read "1 of 6 measured; 5 failed" for a
show where nothing had failed — the five had simply never been analysed.
**Why.** `failed_count` was computed as `episode_count - len(ok)`. The cache
holds only what has been run, so everything absent from it looked like a
failure. A comment in the same function warned against exactly this.
**Avoid.** Three states, not two: measured, failed, not analysed. Anything
missing from `results` has not been run. A comment warning about a trap is not
the same as handling it — check the code does what the comment says.

### The index held two rows per episode
**What.** 24 rows for 13 episodes. Every show aggregate read from the index
double-counted them, and "Remove Stale" could not clear it.
**Why.** `file_path` is the primary key, and the same episode reached through a
relative root and an absolute one produced two rows. Both spellings still
resolved to a file that exists, so nothing looked wrong from inside the app.
**Avoid.** Normalise at the choke point, not in the callers. It also closes the
subtler half: a note saved under one spelling was invisible under the other.

### A cancel would have been recorded as a failed episode
**What.** Cancelling a batch run raised an exception from the progress callback.
**Why.** `analyze_show_batch` wraps each episode in `except Exception`, so the
cancel would have been swallowed and the episode marked *failed* — a cancel that
silently corrupts the record.
**Avoid.** The cancel signal derives from `BaseException`. A test pins the base
class, because making it an ordinary `Exception` later would reintroduce the
bug quietly.

### The video kept playing under a button reading "Pause"
**What.** After opening an episode, a seek to 30s recorded 31.02s.
**Why.** The arrival pause used `pause()`, which **toggles** — and a toggle sent
before playback has actually begun does nothing. Every mark would have been late
by however long the coder took to notice.
**Avoid.** `set_pause(1)`, retried until the player reports stopped. Measure the
timestamp rather than watching the window: the defect was invisible on screen.

---

## Working from design mockups

### Re-deriving the CSS by hand lost something every round
**What.** Several rounds of "it still doesn't match", each fixing some values
and missing others.
**Why.** The mockup CSS was being read and re-typed into the stylesheet each
time. The losses were invisible until the two were put side by side.
**Avoid.** Extract the stylesheets verbatim into `ui/reference/` and consume
them. Where Qt cannot use them directly, translate from a committed file that
can be diffed — never from a screenshot or from memory.

### Built the wrong mockup for a whole screen
**What.** The starting-layout wizard was built from `GeminiStartingLayoutAlternative.html`
when the intended file was `GeminiStartingLayoutAndSettings.html` — two
different designs of the same dialog.
**Why.** Both had been supplied at different times and were not compared.
**Avoid.** The supplied references agree on every value they share
(`#ECECEC`, `#7A7A7A`, `#B8B8B8`, `#2B73DE`, 20px buttons, 11px text). **That
agreement is the design.** A mockup departing from it is the thing to question,
not the thing to build.

### Chrome was right, density was wrong
**What.** "Looks nothing like the files I've sent", with the colours and layout
apparently correct.
**Why.** Every control was 20–50% taller than specified. Qt's defaults are
considerably airier than a dense desktop utility.
**Avoid.** Measure before theorising: row 23→19, header 30→20, button 27→20,
font 12→11. Every box metric must be stated or the interface drifts.

### Named a font for the wrong reason
**What.** Every string in the application had the wrong texture.
**Why.** A Lucida was named first because it was the closer period reference.
The mockup's stack resolves to **Segoe UI** on Windows, and Lucida Sans Unicode
is wide and softly hinted at 11px.
**Avoid.** Resolve a font stack for the actual platform rather than picking the
most authentic-sounding name in it.

---

## Qt behaviours that look like styling failures

Each of these cost real time and none is guessable. Also in `ui/DESIGN.md` §0.4.

### `QTextDocument` overrides heading sizes
A 13px rule on an `h1` still rendered near 24px: Qt's HTML importer applies its
own font-size *adjustment* that survives the stylesheet. **Use classed
paragraphs.** A test enforces it.

### QSS selectors do not match up an inheritance chain
A rule written for `QTreeWidget` does **not** apply to a `QTreeView`. Style the
class actually instantiated.

### `transparent` is not a valid gradient stop
Qt substitutes **white**, so a fade-to-nothing becomes a fade-to-white disc.
Use `rgba(255,255,255,0)`. This survived two attempts to remove a white ring
inside a selected radio button.

### A bare `QWidget` ignores a stylesheet background
Needs `setAttribute(Qt.WA_StyledBackground, True)`. `QFrame` does not. This is
why the inspector and the zoom pill first rendered untinted.

### Do not style a `QRadioButton` indicator into a circle
It is drawn as a small bevelled box that takes the widget background — stamping
a pale slab over a filled row — and reshaping it needs a radial gradient for the
dot, which runs into the `transparent` trap above. **Paint the mark instead**;
`Dot` in `ui/welcome.py` is twenty lines and exact.

### Qt focuses the first widget in the tab order
If that is a text field, any key the field consumes looks dead on a freshly
opened dialog — which is why the wizard's arrow keys only worked after closing
and reopening it. Set the intended focus in `showEvent`, **not** `__init__`:
focus set before a widget is shown does not stick.

### Bordering an item *and* setting `gridline-color` draws both
That is the doubled rule between cells. Items take `border: none`.

### `max-height` on a header section clips it
It cannot then grow to fit its text.

### `ResizeToContents` pins a column after sizing it
Good initial widths, but the user cannot widen it and long names stay elided.
Hand columns back as `Interactive` once sized.

### A `QProgressBar` draws nothing without a `::chunk` rule
Once the application carries a stylesheet, the bar renders as an empty trough
at any value — which reads as a hung run.

### `setStretchLastSection` is on by default
It parks a trailing column's figures an inch from their heading.

---

## Validation and external review

### The published hard-cut F1 was not type-correct
**What.** An external code review (Codex, 2026-08-05) found `score_by_type()`
credited a true positive by the *manual* type whenever any tool transition
matched, regardless of the tool's own type. Follow-up review found a further
matcher issue: correct cardinality, incorrect offset claim.
**Why.** The scorer conflated "a transition was detected here" with "the right
*kind* of transition was detected here".
**Avoid.** Validation code is the code most worth having someone else read: it
is the part that decides whether every other number can be believed, and it
fails silently by reporting a number that is merely too kind. Any published
accuracy figure should be re-derived after a scorer change, and the superseded
value kept in `FOR_PAPER.txt` with what changed.

### Event-level accuracy and count accuracy are different claims
**What.** A tool can produce a dependable episode-level cut *count* while
misplacing individual transitions, because false positives and false negatives
cancel.
**Why.** They are different estimands.
**Avoid.** Report both, and frame the count result as an estimand-specific
accuracy check — never as a substitute for event-level validation.

### Speech metrics reported "not available" while the analysis had the words
**What.** The console reported 1,297 words; the interface said speech was
unavailable. Separately, episodes with `.srt` files present were counted as
lacking them.
**Why.** The speech result was not reaching the same place the interface read
from, and caption discovery disagreed with what was on disk.
**Avoid.** When a metric is "missing", check whether it was *computed* before
assuming it was not — the gap between the engine and the display is a real
failure mode, and it looks identical to a measurement failure.

## Tooling and process

### A patch script failed silently and the work looked done
**What.** `ConfirmDialog` was imported but never called; the old message box
was still live. Caught only because a test hung on the real modal dialog.
**Why.** A string-replacement patch script whose anchor did not match the source
escaping — twice, both times with `\n` inside an f-string.
**Avoid.** Use the editing tools for anything containing escapes. After any
scripted edit, **grep for the new symbol actually being called**, not just
imported. Verifying a button exists is not verifying it does anything.

### Documentation described a build several commits out of date
**What.** `cmat_qt.py` announced "Screens ported so far: Library" long after
every tab was ported.
**Why.** Docstrings and `CLAUDE.md` were not part of the change that made them
false.
**Avoid.** A file that overstates progress is worse than one that says nothing.
When a screen lands, the sentence describing what is ported changes with it.

### Tkinter pack order (historical — does not apply to `ui/`)
`side=BOTTOM`/`side=RIGHT` widgets must be packed **before** any `expand=True`
sibling or they get zero size. This silently hid the Episode Sampler's Browse
buttons, three controls in Language → Vocabulary, and the Speech status note.
Found by walking the live widget tree and measuring every mapped control —
invisible to tests and to code review.

### Cache is path-based
`cache_path = root/.analysis/<show_key>/<stem>.json`. Renaming a show folder,
moving it into a category, or renaming episode files orphans the cache and the
analysis appears to vanish. "Remove Stale" finds the reverse. *Future
improvement:* key on a content hash (size + duration).
