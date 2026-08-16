# Validation Log — CMAT Transition Detection Study

Chronological lab notebook. Every session, parameter change, and decision gets an
entry. Never edit old entries; append corrections as new entries.

Entry format:

```
## YYYY-MM-DD — short title
- What was done (commands run, episodes coded, params tried)
- Why
- Outcome / numbers
- Open questions
```

---

## 2026-08-15 — CORPUS CORRECTION: 66 duplicate episodes removed; one show-level figure was double-counted

**What was done.** While building the research-context feature, the library was
scanned for duplicate episodes for the first time. It held **203 video files
with 66 duplicated filename stems**. Two groups:

1. `Shows/Little Bear (Full Series) - Copy/` — a whole-series duplicate, 65
   episodes, byte-identical file sizes, same five season folders as
   `Little Bear (Full Series)/`. Not a fuller backup: the four Season 4
   episodes that the *PilotTrial2* draw is missing are absent from both.
   Little Bear was not analysed, so nothing was double-counted from it.
2. `SpongeBob SquarePants S01E08B Squeaky Boots` — present as `.mkv` under
   `Season 1/` and `.mp4` under `Season 2/`. Confirmed the **same episode** by
   ffprobe: duration 00:11:02.60 both (identical to the centisecond), 512x384,
   23.98 fps, start offset 0.021000, h264 Main; differing only in container and
   bitrate (979 vs 952 kb/s). It was **filed under two different seasons**, so
   its season attribution was wrong in one of them.

Both were **moved out of the library**, not deleted, to
`_duplicates_quarantined_2026-08-15/` (gitignored, reversible). The `.mkv` under
`Season 1/` was kept: `S01E08B` is a season-one episode, so it is the correctly
filed copy, and it is the one the sample manifests reference.

**Why it went unnoticed.** `analyzer/show_index.py` listed `*.mp4` only while
`analyzer/sampler.py` drew six extensions, so the `.mkv` was invisible in the
Library — while having been measured and written to the index through the
sampler's own path, which does not go through the library walk. The `.mp4`-only
filter was hiding one half of the pair.

**Outcome / numbers.**

| | Before | After |
|---|---|---|
| Video files in `Shows/` | 203 | **137** |
| Duplicated filename stems | 66 | **0** |
| Index rows | 15 | **14** |

**RESULT CORRECTION.** The SQLite index held rows for *both* copies of Squeaky
Boots, so **any Spongebob show-level aggregate computed before 2026-08-15
counted that episode twice**. Episode-level figures are unaffected — each file
measured itself correctly. Recompute before quoting any Spongebob show-level
mean. The affected draw (`Shows/_samples_20260630T012204`) has a manifest N of
9 whose true N is **8 distinct episodes**; the manifest is deliberately not
rewritten, because a manifest records what was drawn.

**A second, separate stale figure found the same day.** The `shows` table is
written by `db.upsert_show`, which runs only when a *whole show* is analysed;
analysing episodes individually never refreshes it. Measured here: the stored
Spongebob row read `episode_count = 2, avg_load = 0.3071` against five indexed
episodes averaging **0.2557** — a ~20% error in the headline show-level figure,
with a current-looking timestamp on the row. The Qt Index now derives its
show rows from the episode rows on screen. **`cli.py db --shows` and `gui.py`
still read the stored table.**

**Open questions.**
- Re-analyse Spongebob? No — re-analysis is not needed, only re-aggregation:
  the per-episode results are correct and cached. Confirm the show-level
  figures after the index rebuild before using any of them.
- One index row carries a raw relative path as its show name
  (`Spongebob Squarepants Season 1/Season 1`), from the `.mkv` indexed through
  the sampler's path. It appears as its own show in any grouping and should be
  re-indexed.
- Should the sampler's analysis path be routed through `show_index`'s naming
  (`db_show_key` / `display_show_name`) so this class of defect cannot recur?
  It has now produced two separate defects.

## 2026-08-14 — Frame-step defect assessed against the coded data: NOT affected

Closing the question the 2026-08-11 timestamp entry left open — whether the
frozen-clock frame-stepping defect biased the timestamps already collected.
**It did not, and the reason is decisive rather than probabilistic.**

**Method.** The defect can only reach a timestamp through the Stamp button,
which records the player clock (`current_sec()`). So the question is whether
the coded marks were stamped at all. `_fmt_hms()` in `gui_coding_editor.py`
writes tenths unless the time is within 0.05 s of a whole second — a stamped
mark is therefore fractional roughly 90% of the time.

| Episode | Marks | Fractional | Whole seconds |
|---|---|---|---|
| A Charlie Brown Christmas 1965 | 45 | 1 (`05:13.6`) | 44 |
| Little Bear 1x01 | 86 | 0 | 86 |

If these had been stamped, P(44 consecutive whole seconds) ≈ 10⁻⁴⁴, and for
Little Bear ≈ 10⁻⁸⁶. The marks were **hand-typed at whole-second resolution
while watching**, not stamped. Frame-stepping never touched them. No
recomputation is required on this account.

**But a larger bias is present, from a different cause.** Signed offsets on the
matched pairs (human − tool), `content-t27-diss`, 2026-08-08 runs:

| Episode | Matched pairs | Mean | Median | Human earlier |
|---|---|---|---|---|
| A Charlie Brown Christmas 1965 | 32 | −0.523 s | −0.485 s | 29/32 |
| Little Bear 1x01 | 71 | −0.610 s | −0.608 s | 64/71 |

That is **second-truncation**, not frame-stepping: a coder writing `00:29` for
an event at 29.6 s is early by 0.6 s, and the mean error of flooring a
uniformly-distributed time is −0.5 s, which is what both episodes show. It is
~12× a single frame (41.7 ms at 23.976 fps), so the defect that prompted this
check was never the dominant error term.

**Sensitivity — does it move the headline?** Re-scored with the project's own
`compare_detections`, in a scratch directory, with a correction added to every
human mark. The +0.00 row reproduces the published figures exactly, which is
what makes the rest of the column trustworthy:

| Correction | CB | LB | Pooled TP/FP/FN | Pooled F1 |
|---|---|---|---|---|
| +0.00 (as coded) | 0.753 | 0.910 | 103/14/21 | **0.855** |
| +0.25 | 0.753 | 0.923 | 104/13/20 | 0.863 |
| +0.50 | 0.753 | 0.923 | 104/13/20 | 0.863 |
| +0.61 | 0.753 | 0.923 | 104/13/20 | 0.863 |
| +1.00 | 0.729 | 0.923 | 103/14/21 | 0.855 |

**Outcome.** Correcting the full observed bias moves pooled boundary F1 by
**+0.008** (0.855 → 0.863) — one true positive. The ±2 s matching tolerance
absorbs a ±0.5 s quantisation comfortably. **The published figures stand
unchanged.**

**Record it as a limitation, not a defect.** The human reference is quantised
to whole seconds and biased ~0.55 s early. Two consequences: the ±2 s tolerance
is doing real work and cannot be tightened without recoding at frame
resolution, and any future tolerance sweep below ~1 s measures the coding
resolution rather than the detector.

**Open questions.**
- Frame-resolution recoding is required before any sub-second tolerance claim.
- The one fractional CB mark (`05:13.6`) is outside the scored window; nothing
  turns on it.

## 2026-08-14 — The published F1 covers the first ~5 minutes, not whole episodes

Found while reproducing the above. Every comparison manifest records a window:

| Episode | Window | Marks scored |
|---|---|---|
| A Charlie Brown Christmas 1965 | 0–300 s | 43 of 45 |
| Little Bear 1x01 | 0–320 s | 81 of 86 |

So "two episodes" means **~10 minutes 20 seconds of video in total**, not two
whole episodes. This was recorded at the time (2026-07-04, "Charlie Brown,
first 5 min") but never propagated into the places the figure is *published* —
`ARCHITECTURE.md` §9, `CLAUDE.md` §2.2 and `analyzer/provenance.py` all said
"two episodes" with no window.

Per `CLAUDE.md` §2.2 — never quote an accuracy figure without its qualifiers —
the window is now stated everywhere the figure appears, including the exported
`boundary_f1_basis`. **No number changes;** the coverage claim does.

## 2026-08-11 — CODEBOOK: `other` subtypes given operational definitions

The `other` row listed "wipes, iris transitions, whip-pan disguised cuts, page
turns" with **no definitions**. Four named categories a coder was expected to
recognise but that the codebook never described.

Added a **Subtypes of `other`** table defining each: what it is, how to tell it
from the thing it is most often confused with, and where to place the
timestamp. The confusions each definition targets:

- **wipe vs dissolve** — a wipe has a hard travelling edge and the shots are
  never superimposed; a dissolve superimposes them.
- **iris vs fade** — a fade changes the whole frame's brightness uniformly; an
  iris has a travelling aperture edge.
- **whip-pan cut vs camera movement** — frame-step it. A real join shows a
  single-frame discontinuity; continuous motion is not a transition (Rule 3).
- **page turn vs wipe** — a wipe moves an *edge* across a static image; a page
  turn moves the *image itself*.

**Why now.** These matter for this corpus specifically: irises are common in the
1965 *A Charlie Brown Christmas* material, shaped wipes in the SpongeBob
episodes, and page turns in storybook-framed shows. A second coder — which
inter-rater reliability requires — had no shared definition to work from, so
disagreement on these would have measured the codebook's vagueness rather than
coder judgement.

**Effect on already-coded episodes.** The category boundary has **not** moved:
anything that was `other` is still `other`, and no coded row changes type by
this edit alone. But the definitions make one prior risk visible — a
**whip-pan disguised cut may previously have been coded `hard_cut`**, since the
join is real and a coder not looking for the disguise would call it what it
looks like.

- [ ] **Spot-check outstanding.** Re-check the coded episodes for whip-pan
      joins coded as `hard_cut`. Not yet done; this is the only subtype whose
      definition could reclassify existing rows.

**Codebook status.** Still DRAFT, still not frozen. This is the third mid-study
addition (Rules 6 and 7 preceded it). Freezing before the next coding session is
overdue — see the 2026-07-04 entry, which said the same thing.

## 2026-08-11 — Timestamp accuracy defect in the coding player (affects collected data)

Investigating a stuttering timer in the Qt coding screen found three defects in
how the video clock is read. Measured on *A Charlie Brown Christmas* (23.976fps):

1. **During playback the clock is coarse** — it advances in 0.25–0.5s jumps, not
   per frame. A mark made while playing can be up to ~0.5s stale.
2. **Frame stepping did not move the clock at all.** `libvlc next_frame()`
   advances the picture but leaves `get_time()` and `get_position()` frozen:
   three steps from 30.000s all still reported 30000ms. A coder stepping to the
   exact frame of a transition recorded the timestamp of wherever they paused.
3. **A seek issued after frame-stepping is wrong and stays wrong** — a seek to
   45.0s landed at 40.040s and did not correct over 1.4s of polling.

**Fixed in the Qt player** (`ui/player.py`): stepping is now a seek of one frame
duration rather than `next_frame()`. Verified — steps land within a millisecond
of the frame boundary, later seeks are exact in both directions, and backward
stepping now works.

**Also fixed, same day, in the Tk editor** (`gui_coding_editor.py`) — the one
the validation study was actually coded in. Same approach: stepping is a seek
of one frame duration, and a back-step (W) is now possible alongside forward
(E). Verified end to end on the workflow the button's own tooltip describes —
nudge back 0.5s, frame-step forward four times, Stamp:

    before the fix   stamped 29.490s  (the nudge position; the four steps were
                     invisible to the clock)
    after the fix    stamped 29.658s  vs 29.657s expected — within 1.2ms

So the defect is closed going forward. **It does not undo timestamps already
collected.**

**What this does and does not imply.**

- Marks placed by seeking or by the ±1s nudge buttons are **unaffected** — those
  use `set_time`, which is exact.
- Marks placed *after frame-stepping* are early by one frame per step
  (0.042s each at 23.976fps). Ten steps is 0.42s — under the ±1s target, but
  systematic and in one direction.
- The size of the effect depends entirely on how often frame-stepping was used
  before marking, which only the coder knows.

- [ ] **Assess and decide.** Estimate how much frame-stepping the coded episodes
      involved. If it was routine, the affected timestamps are biased early and
      the hard-cut F1 figures should be recomputed after correction. If it was
      rare, note it as a limitation. **Do not assume either.**
- [ ] **Decide whether to fix the Tk editor.** It is the shipping software and
      the only one used for real coding. Not changed here without a decision.

## 2026-07-02 — Study infrastructure created

- Built `validate_cuts.py` (template / export / compare / sweep / summary) and this
  log + CODEBOOK.md. Dissolve detection added to `analyzer/metrics_cuts.py`
  (`_compute_frame_scores` + `_find_dissolves`); the validation script imports the
  same functions the engine uses, so validation always measures the shipping detector.
- Trigger: a dissolve at ~0:37 in *A Charlie Brown Christmas* (1965) was missed by
  ContentDetector at threshold 27.0 — gradual transitions spread the frame delta
  across many frames, so no single frame crosses the spike threshold.
- Default detector params at study start: ContentDetector threshold=27.0 (unchanged
  from all prior index analyses); dissolve pass noise_floor=3.0, min_frames=15,
  exclusion radius 1.5s around hard cuts. These dissolve defaults are UNVALIDATED
  guesses — tuning them is the point of the study.
- Study design decisions (pre-registered here):
  - Ground truth: single-coder blind manual coding per CODEBOOK.md.
  - Validation episodes will be split into a TUNING set and a HELD-OUT TEST set
    before any comparison is run. Parameters are tuned only on the tuning set,
    then frozen; test-set numbers are reported in the paper and never used to tune.
  - Match tolerance: ±2.0s default, ±1.0s for fast-cut content; a tolerance
    sensitivity check (±1 / ±2 / ±3) will be reported for at least one episode.
- PENDING (fill in before first coding session):
  - [ ] Finalize CODEBOOK.md and mark it frozen
  - [ ] Choose validation episodes, stratified by era/style/pacing; list them here
  - [ ] Assign each episode to tuning or test set (before looking at any results)
  - [ ] Intra-rater plan: pick 1 episode to re-code >= 3 days after first coding

## 2026-07-04 — First coding session: A Charlie Brown Christmas (1965)

- Began blind manual coding of the first validation episode in Google Sheets
  (exported to `A Charlie Brown Christmas 1965_manual.csv`). Coding the opening
  minutes; dissolve-heavy as expected for 1960s cel animation.
- Timestamps entered in `timestamp_hms` as plain text (Sheets left-aligns them,
  so they export cleanly). Dissolves logged at the blend midpoint per convention.
- Edge case found → **new CODEBOOK Rule 6 (graphic / text overlays).** The
  "A Charlie Brown Christmas" title card at ~02:11 fades in as a graphic over a
  held background shot rather than a shot-to-shot dissolve. By the codebook's own
  definition (`dissolve` = two shots superimposed), this is not a dissolve. Decided
  to code overlay-only transitions as `other` with a note, and added Rule 6 to the
  codebook. Rationale: the pacing metric targets shot boundaries, and a graphic
  animating over a held shot is not a shot boundary. Watch at compare time whether
  the pixel-based detector fires a dissolve here anyway — if so, that is a real
  finding ("detector cannot distinguish graphic-overlay fades from shot dissolves")
  and belongs in the error taxonomy.
- Reminder for this episode before running `compare`: resolve every timestamped row
  that still has a blank/invalid `type` (e.g., the 01:38 "hard zoom, not a cut"
  reminder row — per Rule 3 a zoom is not a transition, so delete it unless a real
  cut is hiding in it). Rows with a timestamp but no valid type parse as phantom
  "unknown" transitions and distort scoring.
- Note: CODEBOOK is still DRAFT and not yet frozen, so adding Rule 6 mid-session is
  allowed. It must be applied retroactively to any overlay already coded in this
  episode. Freeze the codebook before starting the second episode.

## 2026-07-04 — First compare results (Charlie Brown, first 5 min)

Detections regenerated with current shipping detector (git commit at time of run):
ContentDetector t=27 + dissolve pass (noise_floor=3.0, min_frames=15). Full episode:
163 hard cuts, 20 dissolves. Compared against manual coding restricted to the coded
window 00:00–05:08 (`compare --end 308`).

Window composition: manual 43 (34 hard_cut, 6 dissolve, 1 fade_out, 1 fade_in, 1 other);
tool 44 (35 hard_cut, 9 dissolve).

Results (±2.0s tolerance):

| Type | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| hard_cut | 29 | 7 | 5 | 0.806 | 0.853 | 0.829 |
| dissolve | 1 | 5 | 5 | 0.167 | 0.167 | 0.167 |
| fade_out | 1 | 0 | 0 | (matched by time; tool labeled hard_cut) |
| fade_in | 1 | 0 | 0 | (matched by time; tool labeled hard_cut) |
| other | 0 | 0 | 1 | title card missed entirely |
| ALL | 32 | 12 | 11 | 0.727 | 0.744 | 0.736 |

Note on scoring: TP = temporal match (a transition detected there), independent of
type label. The tool's detector only emits hard_cut / dissolve, so fades are always a
type mismatch by construction (no fade class). Read the type-mismatch list, not the
per-type F1 alone, for classification accuracy.

Findings:
- **Hard-cut detection is solid** (F1 0.83). The tool does well at its core job.
- **Dissolve detection is failing** (F1 0.17): missed all four opening artistic
  dissolves (0:27, 0:36, 0:41, 0:48) and 1:33; fired 5 phantom dissolves elsewhere.
  Both low recall and low precision.
- **Snowfall hypothesis supported.** Exploratory sweep (window-restricted, cached):
  best dissolve F1 = 0.471 at noise_floor=2.0 / min_frames=6 (P=0.36, R=0.67). At
  noise_floor >= 4.0 the tool finds ZERO dissolves — i.e., dissolve content-scores on
  this episode sit mostly in the 2–4 band, barely above the snowfall baseline. The
  gentle dissolves do not form a clean plateau above the noise floor.
- **Post-cut confusion:** 3 hard cuts (2:00, 2:06, 3:33) relabeled dissolve with
  ~1.5s offset — dissolve pass catching residual motion just after a hard cut. The
  1.5s exclusion radius around cuts looks too narrow for this footage.
- **Title-card prediction resolved (Rule 6 case):** the 02:12 graphic-overlay fade-in
  was NOT detected at all. Too gradual to cross threshold. → error-taxonomy line
  "graphic-overlay fades under threshold."

Decisions / next steps:
- Do NOT freeze any dissolve params from this single episode. Sweep numbers are
  exploratory only. Code 2–3 more stylistically different episodes before tuning.
- Added coding-window support (`--start/--end`) to the `sweep` command so partial
  codings score fairly.
- TODO next: annotate failure_reason column in the match-detail CSV; run an
  AdaptiveDetector comparison (`export --detector adaptive --threshold 3` then
  `compare`) to test whether it recovers the missed gradual dissolves.
- Files: `..._content-t27-diss_comparison_2026-07-04.csv`,
  `..._content-t27-diss_match_detail_2026-07-04.csv`,
  `A Charlie Brown Christmas 1965__sweep_2026-07-04.csv`.

## 2026-07-04 — Ground-truth correction + re-run (supersedes the numbers above)

Correction to ground truth: while reviewing tool detections, noticed an opening
`fade_in` from black at ~00:02 that had been omitted from the manual coding.
Re-watched and confirmed it against the video, then added it to `_manual.csv`.
Transparency note: this omission was caught during unblinded review of tool output;
the event itself is objective (screen rises from black), verified independently of
the tool's label. Logged here rather than editing the original entry.

Also cleaned the validation folder: canonical manual coding file is now
`A Charlie Brown Christmas 1965_manual.csv` (removed the Google-Sheets `.csv.csv`
duplicate and two blank templates; removed the superseded Jul-2 detections file).

Re-run results (`compare --end 308`, same detections):

| Type | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| hard_cut | 29 | 6 | 5 | 0.829 | 0.853 | 0.841 |
| dissolve | 1 | 5 | 5 | 0.167 | 0.167 | 0.167 |
| fade_in | 2 | 0 | 0 | matched by time; both labeled hard_cut |
| fade_out | 1 | 0 | 0 | matched by time; labeled hard_cut |
| other | 0 | 0 | 1 | title card missed |
| ALL | 33 | 11 | 11 | 0.750 | 0.750 | 0.750 |

Deltas vs pre-correction run: overall F1 0.736 → 0.750; hard_cut F1 0.829 → 0.841
(the 00:02 detection moved from a false positive to a true-positive fade with a
type mismatch). Dissolve results unchanged — the core finding stands.

Type mismatches split cleanly into two mechanisms (6 total):
- `no_fade_class` (3): 00:02, 02:13, 02:15 — fades labeled hard_cut (detector has
  no fade category).
- `post_cut_motion` (3): 02:00, 02:06, 03:33 — hard cuts labeled dissolve from
  residual motion ~1.3s after the cut.

Error-taxonomy controlled vocabulary (use these exact tags in the failure_reason
column so they aggregate across episodes). Grouped by mechanism:

- Classification limits:
  - `no_fade_class` — fade detected but labeled hard_cut (detector has no fade class)
- Missed real transitions (false negatives):
  - `missed_dissolve` (+ context suffix `_snow` or `_gradual`)
  - `missed_cut` — a real hard cut the detector failed to find
    - `missed_cut_lowcontrast` — similar adjacent shots, sub-threshold frame delta
    - `missed_cut_highcontrast` — missed despite a clear shot change (anomaly)
- Phantom dissolves (false positives):
  - `false_dissolve_pan` — camera pan / foreground parallax
  - `false_dissolve_zoom` — a zoom read as a cross-fade
  - `false_dissolve_snow` — snowfall plateau (snow as sole trigger; rare)
- Phantom hard cuts (false positives):
  - `false_cut_zoom` — a smooth zoom read as a cut
  - `false_cut_motion` — general on-screen motion (use `false_cut_pan` for camera-pan parallax)
  - `false_cut_snow` — snowfall between real cuts
- Over-detection near a real cut:
  - `post_cut_motion` — residual motion just after a cut, mislabeled dissolve
  - `double_fire` — the detector fired twice for one real transition
- Overlays:
  - `overlay_under_threshold` — graphic/title fade too gradual to detect (Rule 6 case)

Context suffixes (append to any dissolve/cut tag): `_snow`, `_gradual`.

Added 2026-07-04 from Charlie Brown FP review: `false_cut_zoom`, `false_cut_motion`
/`false_cut_pan`, `false_cut_snow`, `false_dissolve_zoom`, `double_fire`, `missed_cut`.

Finding (Charlie Brown, all 11 FPs now reviewed): the tool's false positives are not
random. Every phantom dissolve was triggered by CAMERA MOVEMENT — 4 camera pans
(00:11, 01:47, 02:03, 02:52) and 1 zoom (05:02). Snow co-occurred in most but was
never the sole trigger, so `false_dissolve_snow` did not actually apply on this
episode. Phantom hard cuts came from zooms (01:07, 01:09), motion (01:41), and
double-fires just after a real cut (03:34, 04:00). So the dissolve detector's core
weakness is that sustained frame-change from camera movement mimics a cross-fade
plateau. This is a mechanism, not noise — a much sharper story than a raw FP count.

Note this refines (does not contradict) the earlier snow hypothesis: snow drives the
FALSE NEGATIVES (raises the baseline so gentle real dissolves never clear the noise
floor), while camera movement drives the FALSE POSITIVES. Two distinct snow/motion
effects pulling in opposite directions.

Missed hard cuts (5), diagnosed by re-watching each (2026-07-04): four are
`missed_cut_lowcontrast` — real cuts between visually near-identical snowy shots
(02:59, 03:22, 04:09, 04:11: same background, same snow pattern, similar palette of
kids' skin/clothing), so the frame delta stayed under the cut threshold. Expected
failure mode. ONE outlier: 01:52 is `missed_cut_highcontrast` — a clear cut from a
wide group-skating shot to a Snoopy close-up, high contrast, yet still missed. Sits
2s before the 01:54 cut that WAS detected. Hypothesis to check later: adjacency /
rapid-cut suppression or a threshold quirk, NOT low contrast. This single anomaly
means "missed cuts = low contrast" is a strong tendency but not a complete rule —
worth flagging in the writeup rather than smoothing over.

## 2026-07-05 — Validation tooling moved into CMAT (no methodology change)

- Validation logic refactored into `analyzer/validation.py`; `validate_cuts.py`
  is now a thin CLI over it, and a new **Validation tab** in the CMAT GUI wraps
  the same functions (guide, tooltips, status tracking, annotation grid with the
  controlled-vocabulary dropdown, sweep window). Detection code itself unchanged —
  scores are identical (verified against the Charlie Brown comparison: same
  0.750 / 33-11-11 numbers).
- New behaviors worth knowing:
  - Re-running compare now PRESERVES failure_reason annotations (carried forward
    from prior match-detail files; verified 28/28 survive).
  - Manual CSV lookup accepts shortened names ("Little Bear 1x01_manual.csv"
    matches the full-length video stem by prefix).
  - `validate_cuts.py status <video>` shows an episode's workflow step.
- Any comparison run after this date carries a new git_commit in its manifest.

## 2026-07-05 — Coding-session observation: cut rate ≠ processing demand (Little Bear)

While hand-coding Little Bear 1x01: the dialogue stretches (e.g. ~1:44–2:23) run a
cut every 2–3 seconds — locally 20+ cuts/min, comparable on raw numbers to fast
YouTube content — yet the material is maximally calm. Nearly every cut is
shot-reverse-shot within one scene ("back to mama bear / back to little bear"):
same room, same characters, same audio bed, zero novelty per cut.

Literature hooks: Lang's LC4MP work distinguishes RELATED cuts (new angle, same
scene — small orienting response, low processing cost) from UNRELATED cuts (new
scene/location — mental model must be rebuilt, high cost). Lillard et al. (2015)
found fantastical CONTENT impaired young children's EF somewhat independently of
pace. Together: cuts/min is a proxy for processing demand, not the demand itself.

Implications recorded:
1. LIMITATION (for the paper): fantasticality is semantically invisible to a
   formal-features tool by design — part of the EF-relevant stimulus is outside
   CMAT's field of view. State plainly in Limitations, citing Lillard et al. (2015).
2. NEW METRIC IDEA (feature backlog): classify each detected cut as within-scene
   vs scene-change by comparing frame similarity ~1s before vs ~1s after the cut
   (color histogram / composition). Yields "scene-changes per minute" and
   "proportion of cuts within-scene" — operationalizes the related/unrelated
   distinction. The manual coding notes already collected ("back to mama bear"
   vs "new scene…") are ready-made ground truth for validating the classifier.

## 2026-07-05 — Cut classifier implemented (within_scene vs scene_change) — UNVALIDATED

Implemented the metric proposed in the same-day observation entry:
- `analyzer/metrics_cuts.py::classify_cut_transitions()` — for each hard cut,
  compares a frame ~1s before vs ~1s after (window clamped to half the distance
  to neighboring cuts, 0.15s min standoff). Similarity = 0.5 × HSV hue/sat
  histogram correlation + 0.5 × 32×32 grayscale structural agreement.
  similarity ≥ threshold → within_scene, else scene_change.
- Engine integration: new ScenePacingMetrics fields `scene_changes_per_min`,
  `within_scene_cut_fraction`, `cut_classifications` (per-cut list). Config keys:
  `cut_classification_enabled` (true), `cut_classification_offset_sec` (1.0),
  `scene_change_similarity_threshold` (0.55 — UNVALIDATED default).
- CLI: `python validate_cuts.py classify <video>` writes
  `<stem>__cutclass_<detector>_<date>.csv` + manifest, using the cached cut list.

First run (Charlie Brown, 163 cuts, threshold 0.55): 80 within_scene /
83 scene_change (3.26 scene changes/min; within fraction 0.49).

Spot-check against the manual coding notes (10 known cases in the coded window):
7/10 correct. All 3 errors were WITHIN-scene cuts mislabeled scene_change, with
similarities 0.457–0.467 — clustered just under the 0.55 threshold. Pattern: all
three are close-up reverse shots where a character fills the frame, leaving little
background visible to establish scene identity. Threshold looks too high for this
content, and/or character-dominant close-ups need handling. No scene-change cut
was mislabeled within_scene in the spot-check.

Next step for this metric: hand-label each detected cut in the coded windows as
within/change (the manual notes nearly do this already), then tune
`scene_change_similarity_threshold` on tuning episodes exactly like the dissolve
params — same train/test discipline. Do NOT feed these numbers into the
sensory-load composite until validated.

## 2026-07-05 — Little Bear 1x01 results (window 0:00–5:20)

Detections: content t=27 + dissolve pass (defaults). Full episode: 316 hard cuts,
6 dissolve candidates. Manual: 81 transitions in window (the 05:27 row is outside
the declared 5:20 window and was excluded from scoring).

Tolerance sensitivity (pre-registered check, run on this episode):

| Tolerance | ALL F1 | hard_cut F1 |
|---|---|---|
| ±3.0s | 0.923 | 0.978 |
| ±2.0s | 0.910 (canonical) | 0.964 |
| ±1.0s | 0.654 | 0.691 |

Reading: stable from ±2 to ±3; the ±1s collapse produces PAIRED FP+FN (20/23 new
ones at once) — the same events failing to pair — which indicates 1–2s offsets
between the rough manual timestamps and the frame-accurate detections, not
detector failure. Manual coding for this episode is pass-1 precision (whole
seconds). ±2s is the canonical tolerance; a pass-2 timestamp refinement would be
needed before ±1s scoring is meaningful.

Canonical results (±2.0s): ALL P 0.947 / R 0.877 / F1 0.910.
hard_cut: 67 TP, 1 FP, 4 FN → F1 0.964 (vs 0.841 on Charlie Brown).

Findings:
- **Mechanism story supported.** On snow-free, clean-cut content the hard-cut
  detector is near-perfect (0.964). Charlie Brown's weaker 0.841 is consistent
  with snow/low-contrast interference, not a general detector weakness.
- **Dissolves still broken, and snow is now excluded as the FP cause:** 0 TP,
  3 FP (00:25, 02:05, 02:58) with NO snow in frame — supports camera-movement
  (pan/zoom/motion) as the phantom-dissolve driver. Both real dissolves
  (00:55, 01:17) missed.
- **Wipes/irises (type `other`):** 5 coded; tool temporally caught 2 — both
  labeled dissolve (00:39 wipe, 00:59 iris) — and missed 3 (00:08, 00:33, 01:07).
  Gradual geometric transitions partially register as dissolves. Proposed new
  vocabulary: `missed_wipe_iris`, `wipe_iris_as_dissolve`.
- **Missed hard cuts (01:45, 03:46, 03:59, 04:03):** all inside rapid
  shot-reverse-shot dialogue runs with cuts 1–2s apart — could be low-contrast
  misses or matching ambiguity in dense regions; needs VLC review before tagging.
- Fades behaved as expected (`no_fade_class`); the 01:01 fade_out/fade_in pair at
  the same second matched as one event (the fade_in FN is partly a matching
  artifact of two manual rows sharing a timestamp).

Cut classification (UNVALIDATED threshold 0.55), full episode:
- Little Bear 1x01: 316 cuts, 13.2 cuts/min — but 67.7% within-scene;
  scene changes/min = 4.2.
- Charlie Brown: 6.4 cuts/min, 49% within-scene; scene changes/min = 3.3.
- **The Lillard/Lang insight quantified:** Little Bear runs DOUBLE Charlie
  Brown's raw cut rate (13.2 vs 6.4/min) yet its scene-relocation rate is nearly
  the same (4.2 vs 3.3/min) — the extra cuts are almost all low-cost
  shot-reverse-shot. Caveats: threshold unvalidated, and Charlie Brown's
  within-scene share is likely underestimated (close-up cuts cluster just below
  threshold), so the true contrast may be larger.

## 2026-07-06 — SpongeBob "Help Wanted" preliminary + three-way classifier comparison

SpongeBob S01E01A detection: 150 hard cuts, 4 dissolve candidates. NOT yet hand-coded
(hard-cut detector trusted from CB/LB validation; classifier run is exploratory).

Cut classification, all at UNVALIDATED threshold 0.55 (exploratory only):

| Show | cuts/min | within-scene | scene changes/min |
|---|---|---|---|
| Charlie Brown | 6.4  | 49% | 3.3 |
| Little Bear   | 13.2 | 68% | 4.2 |
| SpongeBob     | ~16.6| 54% | 7.6 |

Directional finding (the cuts/min ≠ stimulation thesis): Little Bear and SpongeBob
have similar RAW cut rates, but SpongeBob's SCENE-CHANGE rate is ~2× Little Bear's.
Little Bear's fast cutting is mostly within-scene shot-reverse-shot dialogue;
SpongeBob's cuts relocate the viewer. Scene changes/min separates the two where
cuts/min conflates them.

CAVEATS (do not report until the classifier is validated):
1. Threshold 0.55 is unvalidated — all fractions can move with calibration.
2. Close-up bias deflates within-scene counts, and MORE so for dialogue-heavy
   Little Bear (many close-up reverse shots) than for SpongeBob — so the true
   LB/SB gap is likely LARGER than shown. The bias is conservative w.r.t. the thesis.
3. Single episode each; SpongeBob not hand-coded at all yet.

Next: build classifier grading harness (labeled cuts -> agreement + threshold
sweep) and add a scene_relation label column to the coding format, so hand-coding
SpongeBob also produces classifier ground truth.

## 2026-07-06 — Cut-classifier grading harness built

- CODEBOOK: added "Scene-relation labeling" section (within vs change operational
  rules — judged from CONTENT: place/characters/time, not visual difference).
- New optional `scene_relation` column in the manual coding format (within/change,
  hard_cut rows only). `write_template` now emits it; `parse_manual_csv` reads and
  normalizes it (backward compatible — existing CB/LB coding without the column
  still parses; verified LB compare unchanged at 0.910).
- `analyzer/validation.py::grade_cut_classifier()` — matches each hand-labeled cut
  to its detected similarity score, sweeps the similarity threshold, reports
  accuracy + Cohen's kappa per threshold and the confusion matrix at best kappa.
  CLI: `validate_cuts.py grade-cuts <video> <manual.csv>`.
- Machinery check (8 hand-picked clear CB cuts): best threshold 0.475 → perfect
  separation. NOT a validation result (cherry-picked), but confirms 0.475 ≈ where
  the close-up misses (0.457–0.467) sit, so the shipped 0.55 default is likely too
  high. Real calibration needs ALL cuts in a coded window labeled, not just clear ones.
- SpongeBob template regenerated with the scene_relation column for coding from scratch.
- TODO: label scene_relation on the coded CB + LB cuts (retro from notes), code
  SpongeBob with labels, then tune threshold on tuning episodes / test on held-out.
  GUI wrapping of grade-cuts is a later step.

## 2026-07-09 — Fantastical-event coding instrument built (EVENT_CODEBOOK + code_events.py)

Rationale: the field converged on fantastical content as the EF driver (Hinten,
Scarf & Imuta 2025 meta-analysis). Literature review findings that shaped the design
(sources fetched and verified today):
- Studies operationalize fantasy as **fantastical events per minute** (the
  meta-analysis's continuous moderator; extreme variance across studies, one ~30/min,
  most <10).
- **No published taxonomy or coding scheme exists.** Essex et al. (2025) define
  fantastical content ("impossible physical or identity transformations or...
  violations of continuity") but published no systematic coding procedure and no IRR.
  Hinten & Imuta (2026) name exactly one property future work should measure —
  narrative relevance — and provide no measurement framework.
- **Direct validation of the cut classifier's purpose:** the meta-analysis manually
  recoded pace for 11 studies and explicitly notes the literature confuses camera
  cuts with scene changes, "which are not synonymous." Four studies' fast/slow labels
  contradicted their measured cut rates. CMAT's cuts-vs-scene-changes separation
  answers a complaint the field published this year. Cite this in the norms paper.

What was built:
- `validation/EVENT_CODEBOOK.md` — 7-type event taxonomy grounded in the sources
  (physical, transformation, continuity, body, animacy, causal, other_impossible),
  premise-vs-event rule (talking sponge = premise, not event), exaggeration-vs-
  impossibility rule, plus two per-event properties motivated by the live mechanism
  debate: `narrative_relevance` (integral/incidental — SPECT account) and `repeat`
  (new/repeat — schema-habituation). DRAFT until first coding session.
- `analyzer/event_coding.py` + `code_events.py` CLI: template / rates (events per
  minute, per-type, %integral, %repeat, per-30s timeline, window support) /
  agreement (two-coder IRR: detection Dice + type agreement + multi-class Cohen's
  kappa — no study in the meta-analysis published event-coding IRR; the instrument
  supporting it is itself a contribution) / summary (cross-episode norms table).
- Fantasy remains HUMAN-coded by design; the tool structures the coding.
  Synthetic tests pass (agreement math verified: planted disagreement detected,
  kappa 0.737 on 5 matched pairs; rates verified with window denominator).

Status: taxonomy is a DRAFT instrument — needs a pilot coding session (suggest the
already-familiar SpongeBob Help Wanted window) and ideally a second coder for IRR
before any norms are reported.

Amendment (same day, pre-freeze): coder proposed not counting consistent
impossibilities (habituation intuition, using Martha Speaks as a "correctly
classified realistic" example). Fact-check reversed the premise: Lillard et al.
(2015, Study 2) used Martha Speaks as the FANTASTICAL educational condition and it
depleted EF as much as fantastical entertainment. Resolution: the habituation idea
stays a testable hypothesis (the `repeat` column), NOT a counting rule. Added
Rules 7–9: consistent capabilities are premise (unit-of-counting rule, explicitly
decoupled from any cost assumption); never skip "expected" events — tag them
`repeat`; impossibility judged from adult/actual-world standpoint (child-relative
fantasy noted as limitation). Clarified `animacy` = inanimate objects only.

## 2026-07-09 — Site publication pipeline for human-coded event metrics

- New `code_events.py publish <video> --show "<show_key>" --sampling "<description>"`
  → writes/updates `manual_coding.json` (project root) from the latest eventrates
  manifest+CSV (exact provenance: numbers, window, date, git commit). The explicit
  publish step is the manual-review gate — nothing reaches the site otherwise.
  Validates show_key against site_manifest.json and warns on mismatch.
- `build_site.py` reads manual_coding.json and renders (only when data exists):
  - Homepage: "Fantastical events (human-coded)" table — mean events/min per show,
    range, episodes coded, and the REQUIRED sampling-method description column.
  - Show page: per-episode table (window, events, events/min, integral fraction),
    aggregate mean + range, the sampling-method description, and an honest
    human-coded/limitations note linking to methodology.
  - Methodology: new anchored section (#fantastical-events) — literature grounding,
    events-per-min unit, 7-type taxonomy summary, premise-vs-event rule, single-coder
    and small-sample limitations, correlational language.
- End-to-end tested with a synthetic publication (rendered on all three pages),
  then removed; site rebuilt clean. Sections stay hidden until real coding is
  published.

## 2026-07-09 — Trials tab added to CMAT

New "Trials" tab (gui_trials.py + analyzer/trials.py): a registry of every
sampling + manual-coding study, AUTO-DISCOVERED from the provenance manifests
each run already writes (no hand-maintained list). One row per run with date,
episode, trial type, sampling description, episode count, coded window, key
result (F1 / events-per-min / kappa / within-scene fraction), and a published-
to-site flag (green; joined from manual_coding.json). Sortable columns;
double-click opens a detail window with the full manifest and open-folder/
open-file buttons. Machine-only runs (detection, cut classification) shown
grey to distinguish them from manual-coding trials. Discovery verified on real
data: 12 trials found across Charlie Brown / Little Bear / SpongeBob.

## 2026-07-09 — Named sampling trials + Results-panel integration

- Episode Sampler now has a "Trial name" field; the name is stored in the
  sample's manifest.json (`trial_name`, new optional SampleManifest field —
  backward compatible with existing manifests).
- Trials tab discovers Episode Sampler manifests (searched under the root
  folder + validation dir) as "Episode sample" trials: the user's trial name in
  the Trial column, auto-described sampling ("spread, stratified by season,
  seed 42"), episode counts (selected of available).
- Selecting any trial row now renders a summary in the main Results panel
  (right side): key result, sampling, window, publication status, tool version,
  and for episode samples the selected episode list + sampler notes.
  Double-click still opens the full-manifest detail window.
- Verified: named manifest discovered, sampling description built, selection
  callback renders; existing 12 trials unaffected.

## 2026-07-09 — Trial-aware aggregation + provenance-derived publishing

Built the two highest-priority fixes from the PBS-researcher what-if review:

1. **Trial-aware aggregation.** Sample-trial detail window now has "Compute
   trial aggregate" — computes the show aggregate over EXACTLY that sample's
   episodes (reuses the Sample Aggregate path; renders in the Results panel
   with the sample design shown). The corpus-wide show aggregate now carries an
   explicit caution that it covers ALL analyzed episodes (the union of multiple
   samples is not a designed sample). Sample trials also display CODING
   COVERAGE ("1 of 2 sampled episodes transition-coded; 0 event-coded") in both
   the Results panel and the detail window.
2. **`code_events.py publish --trial <manifest.json>`** — the website's
   sampling description is now DERIVED from the named trial's manifest
   ("LB pilot spread: spread, stratified by season, seed 42 — 2 of 65
   episodes") instead of free-typed, and the published show entry records the
   trial link. --sampling free text remains for hand-picked coding; one of the
   two is required.

Remaining from the review (deferred): overlap disclosure between sample trials,
duplicate-trial-name warning in the sampler, _archive/ skip convention,
root-unset hint, filter bar at scale.

## 2026-07-09 — Fantastical events surfaced in the Results panel

Event coding was previously invisible in the app's results views (only in its
own CSVs, the Trials tab, and the site). Added a display-time join from the
validation folder (deliberately NOT merged into the .analysis cache — the
cache is machine-generated and re-analysis would overwrite human coding):
- Episode results: "Fantastical Events (human-coded)" block — events/min,
  count, coded window/date; or an honest "Not coded" note explaining fantasy
  is hand-coded.
- Show + trial aggregates: mean events/min with range across the coded subset,
  explicit coverage line ("1 of 2 episodes in this set are event-coded"),
  per-episode rates, and a PARTIAL-COVERAGE warning so a mean over a subset is
  never mistaken for a mean over the sample.
- Lookup uses newest eventrates manifest per episode, with the same shortened-
  filename prefix fallback as manual coding sheets (verified).

## 2026-07-10 — In-app coding editor (gui_coding_editor.py)

Form-style coding editor (deliberately not a spreadsheet), opened from the
Validation tab for both sheet types (transition `_manual.csv` and event
`_events.csv`). Design driven by the coder's loop (VLC left, editor right):
- Entry bar for pass-1 logging: type a time (validated mm:ss, normalized),
  pick type from dropdown, Enter → row inserted in sorted order, focus returns
  to the time field, dropdown values persist for shot-reverse-shot runs.
- Dropdowns populated from the SAME constants the parsers accept
  (TRANSITION_TYPES, EVENT_TYPES, scene_relation, narrative_relevance, repeat)
  — coded vocabulary cannot drift from the codebook. Guarded by an assert.
- Autosave (default on) after every add/edit/delete — removes the
  buffer-vs-disk loss class entirely. Ctrl+S manual save; unsaved-close guard.
- Pass-2: double-click any cell to edit (choice cells stay dropdowns);
  Delete key removes rows (confirmed). Rows missing a type highlighted red +
  counted in the stats line (the phantom-row trap).
- Sheet-note field persists timestamp-less notes (event sheets: the show
  PREMISE line, per codebook rule that premises are not events).
- Opening an older sheet upgrades its schema on first save (verified: LB sheet
  copy gained scene_relation column; 86 real rows round-tripped through
  parse_manual_csv).
- New Validation-tab button: "Open event coding sheet (fantasy)" — creates the
  template if missing and opens it in the editor.

## 2026-07-10 — Full dogfood QA pass + output-location fix

Operated the whole researcher workflow on Charlie Brown (first 5 min already
coded), driving the real code paths the GUI buttons call:
detection → compare → classify → grade-cuts → event coding → publish → site
rebuild → Trials discovery → headless GUI render. All steps worked; F1 0.753 /
hard-cut 0.836 reproduced exactly; the 27 annotations survived a live
re-compare; event pipeline handled the 0-event realistic baseline; Trials
auto-discovered all five run types with the published one flagged; GUI tabs
built headlessly. Pretend event data removed afterward; real files intact.

Rough edges found:
1. FIXED — outputs (detections, classify, grade, sweep, rates, caches) wrote to
   the validation ROOT, scattering an episode's files away from its manual sheet
   (which the researcher keeps in a per-episode subfolder). Added
   `validation.episode_dir(video)` — outputs now follow the manual sheet into
   its folder. Cache READ fallback widened to search the whole validation tree,
   so relocating output dirs never triggers an expensive re-decode (verified:
   re-run detection landed in Charlie Brown/ with no frame re-decode).
2. NOT YET — `grade-cuts` is CLI-only; no button in the Validation tab.
3. NOT YET (cosmetic) — a `κ` in a classifier-grading result string crashes a
   raw cp1252 console print; the GUI (Tkinter) renders it fine. Any future
   `trials` CLI listing should reconfigure stdout to utf-8.

## 2026-07-10 — Built-in video transport + frame-exact stamping in the coding editor

Coder proposal: click a "+" on an embedded player to log a row at the exact
current frame. Implemented via libVLC (python-vlc 3.0.21203 against installed
VLC 3.0.21) — chosen over silent OpenCV rendering because coders use AUDIO
cues (music changes at scene boundaries, act-break fades). This reverses the
earlier "no player in CMAT" rule deliberately: the ask is a transport with a
stamp, not an editor, and stamping addresses a documented methodological
problem — hand-typed whole-second timestamps caused the ±1s tolerance collapse
in the Little Bear comparison. Stamped times are millisecond-accurate.

- VideoPane in gui_coding_editor.py: play/pause (Space), ±3s (arrows), −0.5s
  nudge, frame-step (E), speed 0.5–1.5×, seek slider, clock, and "✚ Stamp row"
  (S): new row at the current frame using the entry bar's current dropdown
  values (sticky for runs). Key bindings guarded — typing in fields is never
  hijacked.
- Selecting a grid row seeks the player there, paused (pass-2 refinement:
  click row → look → frame-step).
- Sub-second timestamps: new _fmt_hms keeps tenths ("02:13.4");
  parse/compare already handle fractional times. Whole-second entries
  unchanged.
- Degrades gracefully: no VLC/python-vlc or no video path → sheet-only editor
  with a notice. Player shutdown on window close.
- Backward frame-step remains approximate (libVLC keyframe seeking) — the
  documented workflow is nudge −0.5s then frame-step forward.
- Live-tested against the real Charlie Brown MP4 headlessly: playback
  advanced, stamp at 1.16s wrote "00:01.2" with sticky type/relation,
  autosave persisted it, seek-to-60s landed at 60.00s.

Dependency note: python-vlc added (pip). For the distributed .exe, VLC being
installed becomes an optional runtime requirement for this feature only —
add python-vlc to build.spec hiddenimports at next release build.

## 2026-07-10 — Custom dropdown options + README rewrite

- Coding-editor dropdowns are now EDITABLE, not readonly: researchers can type
  their own category (transition type, scene_relation, event_type, relevance,
  repeat) and it's registered + reusable for the session. Custom values already
  present in an opened sheet are absorbed into the dropdown. Default codebook
  vocabulary still ships and still matches the parsers exactly; the parser keeps
  unknown values (warns only). This makes CMAT adaptable to any lab's own coding
  system — a stated goal of the "open instrument other labs use" identity.
  Verified: file-custom value absorbed, typed value registered + persisted +
  round-trips through parse_manual_csv.
- README: new "Manual coding & validation" section (embedded player + stamping,
  coding scene cuts + fantastical events, editable/custom dropdowns, grade the
  tool F1/κ/IRR, trials registry) + top-of-page mention. Emphasizes
  customizability of both coding vocabulary and scoring metrics.

## 2026-07-10 — Self-reported accuracy on every artifact (the NVivo differentiator)

New `analyzer/provenance.py` — single source of truth for CMAT's honest,
per-metric validation statement (validated / experimental / deterministic /
human-coded). Computes the LIVE hard-cut aggregate F1 from this install's
comparison CSVs (currently 0.91 across 5 runs, 219 TP / 20 FP / 23 FN),
falling back to the reference range 0.84–0.96 when no local runs exist.
Wired into: GUI episode + show results panels, JSON export (validation_provenance
block), CSV export (sidecar _PROVENANCE.txt to keep data clean), PDF report
(accuracy line above limitations), and every show page on the website.
Strategic point: "the tool reports its own error rate" is the claim no coding
tool (NVivo etc.) can make — now it's literally on every output CMAT produces.

## 2026-07-11 — Intro templates: code a title sequence once, reuse everywhere

- New `analyzer/intro_templates.py` + Intro ▾ menu in the coding editor:
  save the coded rows of a title sequence as a named template (labeled by
  season/era — "Little Bear S1", "SpongeBob 90s intro"), then insert it into
  any other episode's sheet at that episode's intro start time (cold opens
  shift intros, so the start is per-episode). Works for both transition and
  event sheets; templates store OFFSETS from intro start; registry at
  validation/intro_templates.json.
- Provenance: every inserted row is tagged "[intro: name]" in notes; tags are
  stripped if inserted rows are re-saved into a new template (no nesting).
  Overlap warning when the target range already has coded rows.
- CODEBOOK Rule 7 added: spot-check after inserting (syndication cuts shift
  intros); new label per season/era change; never stretch one template across
  visibly different intros.
- Verified end-to-end: 3-row intro (incl. a fractional 00:08.4 stamp and a
  custom type) saved from episode A, inserted into episode B at 0:45 →
  00:47 / 00:53.4 / 00:56, fractional offset preserved, custom type absorbed
  into dropdowns, tags on disk, re-save strips tags.
- Methodological upside: full-episode coding windows can now INCLUDE intros
  cheaply, so detector cuts during intros no longer have to be windowed out
  or counted as false positives against partial coding.

## 2026-07-27 — Hand-coding as a first-class path + tab restructure

Problem identified by user: hand-coding lived only under the Validation tab,
whose entire framing is "grade the automated tool" — wrong home for researchers
who want human coding as their PRIMARY measurement (e.g. characterizing
stimuli for a study with children). Worse, an analysis path was missing
entirely: `compute_event_metrics()` turned coded EVENTS into rates, but
nothing turned coded TRANSITIONS into pacing metrics. A hand-coder got no
numbers back at all.

- NEW `validation.manual_pacing_metrics()` — descriptive pacing metrics computed
  FROM hand coding, mirroring the automated ScenePacingMetrics definitions so
  hand-coded and automated rates are directly comparable: hard cuts/min, all
  transitions/min, counts by type, mean/median shot length, shot-length CV,
  per-30s timeline, and scene-changes/min + within-scene fraction when
  scene_relation is labeled. Window-aware (segment coding is the norm here).
  Shot lengths use gaps BETWEEN coded transitions — window-edge shots are
  truncated and excluded to avoid biasing the mean downward.
- NEW `gui_handcoding.py` (Hand-coding tab): pick episode → code transitions
  and/or events (opens the coding editor with the embedded player) → compute
  metrics into the Results panel → export CSV. No detection, no compare, and
  the blind-coding rule explicitly does NOT apply (nothing to be biased by).
- Tab restructure (user-directed):
    Library | Index | Automated coding | Hand-coding | Trials
  Library is now a pure browser; the analyze controls + queue moved into
  Automated coding > Analyze, with Language and Validation as its other
  sub-tabs. Selection still happens in Library, so the Analyze sub-tab shows
  a live "Selected in Library:" line so the user can see what the buttons act
  on. Trials stays top-level — it's the audit trail across BOTH paths.

FIRST RESULT (the count-bias table the paper needs, now computable in-tool):

| Episode | Manual cuts/min | Auto cuts/min | Rate error | Mean shot |
|---|---|---|---|---|
| Charlie Brown (0–5:00) | 6.60 | 6.80 | +3.0% | 7.0s |
| Little Bear (0–5:20) | 13.31 | 13.13 | −1.4% | 3.9s |

i.e. the automated CUT RATE — the metric actually published — is within ~3% of
human coding on both episodes, despite per-event F1 of 0.84 on Charlie Brown.
Per-event F1 and rate accuracy are different claims; report both.

## 2026-07-27 — Sampler feeds both measurement paths

Gap found once hand-coding became a first-class path: the Episode Sampler could
only "Send to Analysis Queue" (automated), so a researcher who drew a sample
intending to HAND-CODE it had no route from sampler to coding. Neither coding
tab could ingest a sample draw either.

- `trials.read_sample_episodes(manifest)` — shared helper reading episode paths
  from a draw (manifest.json + sibling selected.csv). One source of truth for
  every destination a sample can flow to.
- Sampler: "Send to:" destination selector — Automated analysis queue /
  Hand-coding worklist / Both. Button relabeled "Send Sample to CMAT"; status
  line reports per-destination counts. `App.send_to_handcoding()` bridges to the
  tab and switches to it so the result is visible.
- Hand-coding tab: NEW coding worklist — "Load sample…" (or pushed from the
  sampler), listbox of episodes with per-episode coding-progress flags
  (· none / T transitions / E events / TE both), click to make one current,
  "n of N have coding" summary that refreshes as you code. Missing files are
  reported but still listed.
- Validation tab: "Choose from a sample draw…" — pick an episode out of a
  manifest instead of browsing the filesystem, so you validate exactly the
  sampled episodes.

Verified end-to-end on a fixture draw: 2 episodes read → routed to hand-coding
→ worklist populated with correct progress flags (both already showed T) →
first episode auto-selected.

## 2026-07-27 — Provenance separation in Library and Index

Integrity problem spotted by user: neither the Library nor the Index
distinguished automated from hand-coded data. Two halves — automated numbers
weren't LABELED as automated, and hand-coded numbers didn't appear at all
(they existed only transiently in the Results panel). With both measurement
paths now first-class, that ambiguity is a real risk: nothing stopped a
machine-measured cuts/min being read as human-coded or vice versa.

- `validation.coded_episode_map()` / `coding_for_stem()` — one filesystem pass
  builds a {sheet_base: transitions/events/metrics} map reused across many
  rows, so provenance markers cost no per-episode glob. Handles the shortened-
  filename convention via longest-prefix match.
- `validation.write_manual_metrics()` — hand-coded metrics now PERSIST
  (`<stem>__handcoded_<date>.json`, in the coding folder, never in .analysis:
  the cache is machine-generated and re-analysis would overwrite human work).
- Library tree: `[auto]` / `[hand-coded]` / `[auto + hand-coded]` per episode
  (was an undifferentiated `[analyzed]`).
- Index > Episodes: new **Source** column (always "automated" — that table
  holds machine measurements only) and **Hand** column (T / E / TE / —)
  showing which episodes additionally have coding. Both are derived columns,
  excluded from DB sorting.
- Index > NEW **Hand-coded** sub-tab: human-coded metrics (cuts/min,
  transitions/min, mean shot, CV, scene-changes/min, within-scene %,
  events/min, coded window and date) in a SEPARATE table. Deliberately never
  merged into the automated table or into automated aggregates.

Verified: 4 coded episodes discovered; prefix lookup matched the shortened
"Little Bear 1x01" sheet to the full 90-char episode stem; Charlie Brown shows
[auto + hand-coded] in the tree and TE in the index; computing metrics
persisted them and they appeared in the Hand-coded sub-tab (6.60 cuts/min,
window 00:00–05:00).

## 2026-07-27 — Wikipedia import by URL (metadata importers verified intact)

Checked after the tab restructure: both metadata importers are launched from
the File menu, so they were unaffected — verified both dialogs still build and
the underlying matching path is unchanged.

Added URL input to the Wikipedia importer (parity with TVMaze, which already
fetched over the network):
- `wiki_importer.fetch_wikipedia_html(url)` — urllib with a descriptive
  User-Agent, restricted to wikipedia.org hosts so a pasted URL can't be used
  to fetch arbitrary sites. Returns rendered HTML (what the table parser
  expects; `action=raw` wikitext will not parse).
- `parse_wikipedia_episode_list(path)` split into a thin file wrapper over new
  `parse_wikipedia_html(html)`, so both input paths share one parser.
- Dialog: URL entry + Fetch button (Enter also fires), fetching on a worker
  thread with the result marshalled back via `after()` — the UI never blocks
  on the network. Saved-HTML browsing still works and is offered as the
  fallback in the error message.

Verified live: rejected non-wikipedia hosts (including
`evil-wikipedia.org.attacker.com`) and non-http schemes; fetched the real
"List of Little Bear episodes" page (314 KB) and parsed 65 episodes across 5
seasons with correct titles and air dates.

## 2026-07-27 — BUG: metadata importers matched across the whole library

User reported Wikipedia import matching Little Bear episodes to SpongeBob,
Martha Speaks, etc. Root cause was NOT the new URL fetch (that worked — 63/65
found); it was a PRE-EXISTING bug in both importers: `_collect_local_files()`
gathered episodes from EVERY show in the library, and `match_to_files` matches
on season/episode number, so Little Bear S1E1 grabbed whichever S01E01 it hit
first. Affected the saved-HTML path identically, and TVMaze had the same bug.

Fix — a "Match against show:" selector in both dialogs, scoping matching to one
show. Two subtleties:
- Lists TOP-LEVEL shows, not `list_shows()` leaves. A show stored as
  `Little Bear (Full Series)/Season 1..5` must be selectable as ONE unit, since
  a "List of X episodes" page covers the whole run. Collection walks all leaf
  dirs at or beneath the chosen top-level folder.
- Defaults to the Library tab's current selection (walking up to its top level),
  so the common case needs no interaction. "(all shows — not recommended)" is
  offered but never the default: the dangerous behavior now requires a
  deliberate choice.
- Changing the selector re-matches already-loaded data without re-fetching
  (parsed episodes cached on the dialog).

Verified against the live Little Bear page:
  scope = Little Bear (Full Series)  ->  65 files, 62 matched, 0 wrong-show
  scope = (all shows)                -> 202 files, 63 matched, 14 wrong-show
S1E1 now maps to "Little Bear 1x01 What Will Little Bear Wear", not SpongeBob.

## 2026-08-03 — Optional tools framework + TransNetV2 detector (opt-in)

Rationale: CMAT's dissolve detection fails (F1 0.17) because frame-differencing
structurally cannot separate a dissolve (two shots blending) from a camera pan
(one shot translating) — confirmed by the frame-score analysis below. That
needs a different FEATURE, not recalibration, so the fix is an optional
learned detector rather than more tuning.

Frame-score separability check (Charlie Brown, cached scores vs hand coding):
  background (no transition within 3s): median 0.61, p90 4.00, p99 8.75
  hand-coded dissolves: peaks 3.80–9.35 (median 4.6) → sit at p89–p99
  hand-coded hard cuts: median peak 15.1
So the dissolve signal EXISTS but overlaps the band where camera motion lives.
Note the dissolve upper bound (`hard_threshold`, 27) was never binding —
dissolves peak far below it — so the earlier ContentDetector-scale error, while
real, is not what caused the poor performance.

Built:
- `analyzer/optional_tools.py` — registry for opt-in components: description,
  benefits, costs, caveats, availability probe (by import), and a pip installer
  that streams output. Extensible; TransNetV2 is the first entry.
- `analyzer/detector_transnet.py` — wraps `transnetv2-pytorch` and returns cut
  times in CMAT's existing convention (scene starts after the first), so it
  drops into the detection + validation flow unchanged. Fails with an
  actionable message when absent; nothing in the validated core depends on it.
- `gui_optional_tools.py` — explanation screen shown BEFORE install: what it
  does, why you might want it, what it costs (~2 GB PyTorch), and the caveats
  (community port of the official MIT model; benchmarks are live-action, so
  ANIMATION accuracy is unverified).
- Selectable as `--detector transnet` in the CLI and wherever a detector is
  chosen, so it can be graded against existing hand coding immediately.

Authors' reported F1: BBC Planet Earth 96.2, RAI 93.9, ClipShots 77.9 (vs
TransNet v1: 92.9 / 94.3 / 73.5). Trained ~35% hard cuts, ~50% dissolves.

NEXT: this is a hypothesis to TEST, not an assumed upgrade. Run it on Charlie
Brown and Little Bear and compare against the same hand coding — head-to-head
against ContentDetector's 0.836 / 0.964 hard-cut F1 and the 6 missed dissolves.

## 2026-08-03 — RESULT: TransNetV2 vs ContentDetector on animation

First head-to-head on identical hand coding, same window (0:00–5:00), same
tolerance (±2s). This is the "does the learned detector actually help on
animation" test — animation is OUTSIDE TransNetV2's training distribution, so
the outcome was genuinely uncertain.

Charlie Brown (the hard case: 1960s cel, dissolve-heavy, constant snowfall):

| Metric | ContentDetector | TransNetV2 |
|---|---|---|
| ALL F1 | 0.753 | **0.902** |
| ALL precision / recall | 0.762 / 0.744 | 0.949 / 0.860 |
| hard_cut F1 | 0.836 | **0.906** |
| dissolves found (of 6) | 1 | **6** |
| false positives | 10 | **2** |

The dissolve result is the headline: CMAT's experimental pass found 1 of 6;
TransNetV2 located all 6 within tolerance. False positives dropped 10 → 2,
i.e. the pan/zoom confusions that dominated the error taxonomy largely
disappeared — consistent with the diagnosis that the failure was a FEATURE
limitation (frame-differencing cannot separate blending from translation),
not a calibration problem.

IMPORTANT INTERPRETATION CAVEAT: TransNetV2 emits shot boundaries WITHOUT type
labels, so every detection enters the comparison as `hard_cut`. Because the
matcher scores a TP by the HUMAN label on temporal match alone (see the
type-correctness issue in the code-review entry), "dissolve F1 = 1.000" means
"all six hand-coded dissolves had a detection within 2s" — it does NOT mean
TransNetV2 classified them as dissolves. For cuts/min and transition-rate
purposes that is exactly what matters; for type-conditional claims it is not.
The ALL row is the trustworthy figure.

Prior expectation was "modest gains, possibly worse on animation given domain
shift." That was too pessimistic — it substantially outperformed on the
hardest content in the corpus. Worth reporting honestly as a corrected
prediction.

Little Bear 1x01 (the clean case, 0:00–5:20):

| Metric | ContentDetector | TransNetV2 |
|---|---|---|
| ALL F1 | 0.910 | **0.942** |
| hard_cut F1 | 0.964 | **0.979** |
| dissolves found (of 2) | 0 | **2** |
| false positives | 4 | **1** |

As predicted, the hard-cut gain on clean animation is small (0.964 → 0.979,
little headroom). The ALL gain comes from the dissolves. So the pattern holds
across both episodes: large win on gradual transitions, marginal on hard cuts,
fewer false positives everywhere.

NEW LIMITATION FOUND: TransNetV2 misses `other` transitions — wipes, iris
transitions, and graphic overlays (5 FN on Little Bear, 1 on Charlie Brown, 0
detected of 6 total). Little Bear's intro uses wipes and irises heavily, and
none were found. So geometric/decorative transitions remain a gap for BOTH
detectors, and hand-coding is currently the only reliable way to capture them.
Worth stating in the paper: automated detection covers hard cuts well and
(with TransNetV2) dissolves well, but not stylised transitions.

INTEGRITY CHECK: Little Bear was scored twice — once from detections computed
on a 0:00–5:20 CLIP, once from detections computed on the FULL episode and
filtered to the same window. Both gave 74 detections and identical scores
(ALL F1 0.942, hard_cut 0.979). Clipping to the coded window is therefore a
valid shortcut; it just isn't a fast one (see timings below).

⚠ FULL-EPISODE COUNT SHIFT — comparability warning. Across whole episodes:
  Charlie Brown : ContentDetector 163 cuts → TransNetV2 172 (+5.5%)
  Little Bear   : ContentDetector 316 cuts → TransNetV2 337 (+6.6%)
Adopting TransNetV2 would move published cuts/min by roughly 5–7%. As with
`flashing_sample_fps`, this must be an all-or-nothing corpus re-analysis —
mixing detectors across shows would make pacing incomparable, which is exactly
the failure mode the meta-analysis criticises in the existing literature.

Practical notes: full-episode CPU inference ran several minutes (25-min
episode); clipping to the coded window took ~330–400s per 5-minute clip, so
clipping is not obviously faster — model load and per-frame cost dominate.
The model loads once and is cached. `--threshold` means a PROBABILITY
(0–1, default 0.5) for transnet but a frame-difference magnitude (27) for
content — passing 27 to transnet silently detects nothing. Use
`--no-dissolves` with transnet: it detects gradual transitions natively, so
CMAT's dissolve pass would double-count.

## 2026-08-08 — Code-review fixes applied (all six Part A findings)

1. TYPE-CORRECTNESS. `score_by_type()` now scores two ways and both are
   written to the comparison CSV under a `scoring` column:
     boundary — a TP means the tool flagged a transition there, whatever it
                called it. Stratified by the HUMAN label. This is the correct
                measure for transition RATES and the only fair one for
                detectors that emit untyped boundaries (TransNetV2).
     typed    — a TP additionally requires the label to match; temporal
                matches with the wrong label become FN for the human type and
                FP for the tool's type. This is classification performance.
   Added `type_confusion()` (human type → tool type over matched events).
   `aggregate_summary()` reads only the boundary rows, so the two scorings are
   never summed together; files without the column are treated as boundary.
2. MATCHING. Greedy nearest-unclaimed replaced with maximum-cardinality
   matching (Kuhn's augmenting path, no new dependency — scipy is not a CMAT
   requirement). Candidate edges are visited nearest-first so offsets stay
   small among maximum matchings. Codex's counterexample now scores F1 1.0
   where greedy gave 0.5.
3. KAPPA. `_cohen_kappa()` and `_kappa_multiclass()` return None where kappa is
   UNDEFINED (no pairs, or chance agreement = 1) instead of 0.0, which read as
   "no agreement beyond chance" for what is actually perfect unanimity. Sweep
   selection sorts None below any real value so it cannot win.
4. COMPARABILITY. `manual_pacing_metrics()` no longer claims parity it did not
   have. Engine-comparable fields (hard_cuts_per_min, mean/median_shot_sec,
   shot_length_cv, timeline_per_30s) are now computed from HARD CUTS ONLY with
   ceil binning, matching compute_cut_metrics(). All-transition figures are
   renamed to inter_transition_* / timeline_all_types_per_30s and documented as
   having no automated counterpart. The remaining edge difference (manual
   excludes window-edge shots, the engine includes its first/last scene) is
   now stated in the docstring rather than glossed.
5. STANDOFF BUG. The 0.15s minimum in `classify_cut_transitions()` could exceed
   half the distance to a neighbouring cut on shots under ~0.3s, sampling
   ACROSS that cut. Clamp reordered so staying inside the shot always wins.
6. DISSOLVE SCALE. Verified against PySceneDetect 0.7 source: its
   ContentDetector uses EQUAL component weights (1.0/1.0/1.0), raw 0–255 mean
   absolute channel differences, averaged. CMAT's dissolve score uses
   0.28/0.45/0.27 with per-channel normalisation and a ×100 rescale — the
   scales are NOT comparable and the shared `threshold=27` ceiling was
   meaningless. Documented; moot in practice since the dissolve pass is now
   superseded by TransNetV2 and the ceiling was never binding (dissolve peaks
   sit at 4–9, far below 27).

REGENERATED NUMBERS (tolerance ±2s, same windows):

| run | boundary F1 | previously | typed F1 |
|---|---|---|---|
| CB ContentDetector | 0.753 | 0.753 | 0.612 |
| CB TransNetV2 | 0.902 | 0.902 | 0.707 |
| LB ContentDetector | 0.910 | 0.910 | 0.846 |
| LB TransNetV2 | 0.942 | 0.942 | 0.890 |

Boundary F1 is UNCHANGED on all four: greedy happened to find the optimal
matching on this data, so no previously reported figure was wrong — it was
correct by luck rather than by guarantee. It is now guaranteed.

The typed column is the newly visible truth. TransNetV2's large gap
(0.902 → 0.707) is expected and not a defect: it emits untyped boundaries, so
every dissolve it correctly LOCATED is counted as mislabelled. That is exactly
why both numbers must be reported, and why "hard-cut F1" was the wrong name
for the boundary figure.

Tests: 39 passed, 13 skipped.

## 2026-08-08 — Second review round: three material issues fixed

Codex confirmed the first-round fixes to matching, typed scoring, kappa
handling and short-gap crossing, and found three that still blocked reliance
on the revised claims. All confirmed by reproducing the counterexamples.

1. OFFSET CLAIM WAS FALSE (and now fixed, not just retracted). Nearest-first
   edge traversal does NOT minimise total offset — an augmenting path can
   displace an earlier good pairing. Verified: manual (0,1) vs detections
   (0,2) at tolerance 2 produced total offset 3 where 1 is achievable.
   Cardinality (and therefore TP/FP/FN) was never affected, but the
   `offset_sec` values shown in the match-detail CSV — which the coder reads
   while annotating — were wrong. Added a swap-refinement pass after matching:
   exchanges partners between matched pairs where that lowers total offset and
   both stay in tolerance. Counterexample now yields offset 1.0 at full
   cardinality.

2. MANUAL SHOT LENGTHS STILL DID NOT MATCH THE ENGINE. The previous fix
   aligned rates and timelines but left interval statistics measuring only the
   C−1 interior gaps between C hard cuts, while compute_cut_metrics() measures
   the C+1 PySceneDetect scenes INCLUDING both edges. This was not "slight" as
   the docstring claimed: one cut at 10s in a 100s episode gave manual
   mean/median/CV of 0.0 against an engine mean of 50.0. Manual shot stats are
   now bounded by the window (or 0..duration), giving C+1 intervals; verified
   50.0 and 33.3 against Codex's two examples. A `shot_edges_included` flag
   reports when the span end is unknown and the figure falls back to interior
   gaps.

3. AGGREGATION AND PROVENANCE WERE UNRELIABLE.
   - aggregate_summary() summed EVERY dated rerun, double-counting episodes and
     over-weighting whichever was re-run most. Now keeps only the newest
     comparison per (episode, detector-config) via new _latest_comparisons().
   - A present-but-blank `scoring` cell was treated as boundary; now only an
     ABSENT column means legacy-boundary, malformed values are skipped.
   - provenance selected files by `detector_tag in filename`, which would match
     an episode titled "Contentment" and merged different thresholds and
     dissolve settings into one supposedly-single configuration. Replaced with
     structural parsing (parse_comparison_name) plus per-episode dedupe.
   - provenance published the per-type `hard_cut` boundary row, which is a
     HYBRID: TPs stratified by the human label, FPs by the tool's label, so its
     precision mixes denominators. Only the ALL row is a clean detector-level
     figure; provenance now uses it.

Also: type_confusion() gained a `<missed>` column and `<spurious>` row so the
matrix is self-contained (a detector could otherwise look perfect while missing
most of the episode). classify_cut_transitions() no longer samples past the
final frame (the old `max(duration, last_cut+1)` bound let a cut at 99.8s in a
100s video sample ~100.3s) and returns `unknown` where no strictly-interior
standoff exists rather than sampling at the cut itself.

PUBLISHED FIGURE CHANGED as a result — this supersedes earlier entries:
  self-reported accuracy was F1 0.91 over "9 comparison runs"
  it is now  F1 0.85 over 2 episodes  (ContentDetector; TransNetV2 is 0.93)
The drop is not a regression. It comes from removing double-counted reruns and
from quoting the clean ALL row instead of the hybrid hard_cut row. The
reference range moved from 0.84–0.96 (hard-cut basis) to 0.75–0.91 (all coded
transition types), which is the honest basis given the tool is scored against
everything a human coded, not just hard cuts.

Per-episode boundary/typed F1 are unchanged: CB 0.753/0.612, CB-transnet
0.902/0.707, LB 0.910/0.846, LB-transnet 0.942/0.890.

Tests: 39 passed, 13 skipped.

## 2026-08-08 — Count/rate reasoning reviewed; terminology corrected

Independent review of the claim that per-event F1 and cut-RATE accuracy are
distinct estimands. Verdict: legitimate, but only framed as an estimand-specific
calibration check, never as a substitute for event-level validation.

KEY IDENTITY (verified exactly on all 9 comparison runs on disk):

    predicted_count / actual_count  ==  recall / precision

so recall > precision predicts an OVERCOUNT and precision > recall an
UNDERCOUNT. This is the exact form of the pattern noted informally earlier.
Charlie Brown: P .762, R .744 → ratio .976 (measured .977). Little Bear:
P .947, R .877 → .926 (measured .926).

WHEN CANCELLATION FAILS (both plausible in real video):
  - Poor F1, perfect count: 50 TP / 50 FN / 50 FP → count exact, F1 = .50.
    In the limit FP = FN = all, F1 = 0 with an exactly correct count.
  - Good F1, large rate error: 100 TP / 0 FN / 11 FP → F1 ≈ .948 but +11%.
    Especially likely AFTER threshold tuning, which trades precision against
    recall and therefore moves the count in a predictable direction.

TERMINOLOGY CORRECTION (supersedes earlier entries): a single episode's +3.0%
is a signed relative count error, NOT a "bias". Bias is a property of an
estimator across a representative held-out sample. Earlier log entries used "count
bias" for single episodes; read those as "count error". Across episodes the
correct terms are mean percentage error / relative bias (signed) and MAPE
(absolute). Computer vision calls the raw difference DiC (difference in count).

NOT METRIC-SHOPPING IF: pre-specified as co-primary outcomes, computed on
held-out episodes, and reported as per-episode distributions rather than a
single pooled figure that hides cancellation. It becomes metric-shopping if the
favourable rate result is foregrounded while event-level failures are buried,
or if episodes/thresholds are chosen after seeing results.

IMPLEMENTED: compare_detections() now returns and records count_ratio and
signed_relative_count_error in the comparison manifest, and the CLI prints them
under a "Rate calibration" heading that states explicitly that it is a
different property from the F1 above, shows the recall-vs-precision direction,
and labels the single-episode figure an error rather than a bias.

STILL TO DO for the paper: report per-episode rate errors (table or plot, not
just pooled), stratify by production style and cut density, and give
uncertainty intervals clustered by episode. For zero-count windows report an
absolute count difference, since percentage error is undefined.

Suggested wording: "On held-out coded windows, CMAT's boundary-detection F1 was
X; its cut-rate ratio was Y (signed relative rate error Z%). These assess
distinct properties: boundary localisation and aggregate rate calibration."

## 2026-08-15 — Whip-pan spot-check: no `hard_cut` rows reclassified

**What was done.** `CODEBOOK.md`'s `whip-pan disguised cut` subtype was added
2026-08-11, after all three currently-coded episodes were coded, so any
`hard_cut` row in them was a candidate for having hidden a whip-pan join. All
113 `hard_cut` rows across the three real `_manual.csv` files were
spot-checked — Curious George S01E01 (2), A Charlie Brown Christmas 1965 (35),
Little Bear 1x01 (76). SpongeBob Help Wanted and Little Bear 1x02 have no
coded rows yet, so nothing there needed checking.

**Method.** Built a local review tool (not published — copyrighted footage):
a 5-second clip per `hard_cut` timestamp (2.5s before/after the coded frame),
playable at 1x/0.5x/0.25x, with a jump-to-coded-frame control. 8 of the 113
were pre-flagged because the coder's own original note already used a word
like "motion," "pan," "blur," or "instant" (e.g. Little Bear `00:11`, `00:20`,
`4:50`, `4:52`). Coder (Samuel Babbert) reviewed all 113 clips against the
codebook's test — a single-frame discontinuity in subject/background/blur
direction inside apparently-continuous motion.

**Outcome.** **Zero reclassifications.** None of the 113 `hard_cut` rows,
including the 8 flagged by their own notes, were whip-pan disguised cuts on
review. No `_manual.csv` edits were made. This closes `TODO.md` item 1.

**Why the null result is still worth recording.** It rules out the specific
concern raised in the 2026-08-11 codebook entry — that a coder without the
subtype definition might have miscoded a whip-pan join as `hard_cut` — for
this corpus. The "high motion" notes on some Little Bear cuts describe fast
in-shot action (a bird flying at camera, a jump) rather than a whipped camera
move with a hidden join; motion in the frame is not the same thing as a
disguised cut, and this pass distinguishes them for the record.

## 2026-08-15 — Codebook provenance note added; typology is not separately cited

**What was done.** `TODO.md` had flagged that `CODEBOOK.md`'s five transition
types and four `other` subtypes cite no source. Checked git history:
`hard_cut`/`dissolve`/`fade_in`/`fade_out`/`other` were introduced in the
codebook's first commit (2026-07-12); the four `other` subtypes were added
2026-08-11. Neither addition cited a source at the time, and none exists in
`DECISIONS.md` or `FOR_PAPER.txt` either.

**Decision.** Rather than search for a citation to retrofit onto this exact
taxonomy, added a provenance note to `CODEBOOK.md`: the terms themselves
(`hard_cut`, `dissolve`, `fade_in`/`fade_out`, `wipe`, `iris`) are standard
editing / shot-boundary-detection vocabulary, not something this study
invented — so "cite it" and "say we invented it" were both the wrong framing.
What *is* study-specific, and was never checked against a published
instrument, is this codebook's exact operational definitions, timestamp
conventions, decision rules, and — notably — the choice to bucket wipe, iris,
whip-pan-disguised-cut, and page-turn together under `other` because the tool
cannot yet tell them apart. That grouping is an engineering decision, not a
term from the literature.

**Rejected.** Searching for a paper to cite for this specific five-type +
subtype scheme — the shot-boundary-detection literature bins transitions
CUT/GRADUAL, coarser than this codebook, so citing a specific source would
overstate how directly this scheme was adapted from one. Closes `TODO.md`
item 1.

## Planned validation sample (fill in)

| Episode | Show | Era/style | Pacing regime | Set (tuning/test) | Coded | Re-coded |
|---|---|---|---|---|---|---|
| A Charlie Brown Christmas (1965) | Peanuts special | 1960s cel, dissolve-heavy | slow | | | |
| | | | | | | |
