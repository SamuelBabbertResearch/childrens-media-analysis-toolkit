# Children's Media Analysis Toolkit (CMAT)

A desktop Windows application that analyzes MP4 episodes of children's TV shows and produces a **sensory-load profile** — a transparent, labeled breakdown of how visually and aurally stimulating a show is, based on measurable structural features of the video.

CMAT measures pacing, motion, color, flashing, and audio loudness. It does **not** issue a verdict on appropriateness. Every composite score shows its component parts, and every design decision in the scoring model is adjustable.

> **Part of the Open Children's Media Index** — an ongoing effort to build a publicly accessible, empirically grounded database of sensory-load profiles for children's television.

---

## What it measures

| Metric | What it captures |
|--------|-----------------|
| **Scene pacing** | How fast the camera cuts. Faster cutting triggers more frequent orienting responses and higher cognitive load. |
| **Motion** | Average frame-to-frame movement. High motion is a pre-attentive attention magnet. |
| **Color saturation** | How vivid and pure the colors are. Higher in animation; lower in live-action. |
| **Color contrast** | Spatial spread of brightness within a frame. Captures dark/light extremes that drive visual intensity. |
| **Flashing** | Rapid luminance changes per minute. Relevant to photosensitivity and overstimulation. |
| **Audio loudness** | Average RMS volume and dynamic range. Loud, consistent audio drives arousal independently of visuals. |
| **Sensory load score** | A transparent weighted composite of all the above. Always shows its component parts. |

Grounded in the Huston & Wright formal features framework, Lang's Limited Capacity Model (LC4MP), and Lillard & Peterson (2011).

> **Honest limitation:** This tool measures the stimulus, not the viewer. It cannot account for a child's age, temperament, or sensory-processing profile. Output is a profile to inform judgment, not a rating or verdict. All findings are correlational.

---

## Screenshots

<img width="740" height="502" alt="image" src="https://github.com/user-attachments/assets/29a4dc19-16bf-4a44-95df-fa976fb51ecb" />
<img width="357" height="440" alt="image" src="https://github.com/user-attachments/assets/51a6030d-e4c0-4102-92ea-a81a472b54ba" />
<img width="416" height="313" alt="image" src="https://github.com/user-attachments/assets/9cc86a50-f268-47dc-89d7-3e8b92d2968f" />

---

## Download & Install (Windows)

1. Go to the [Releases page](../../releases/latest)
2. Download `CMAT-v1.0.zip`
3. Unzip anywhere (e.g. `C:\CMAT\`)
4. Double-click `CMAT.exe`

No Python, no FFmpeg, no other installs required. Everything is bundled.

---

## How to use

### 1. Pick a root folder

File → Open Root Folder. Organize your library like this:

```
My Videos/
  Little Bear/          ← flat show
    ep01.mp4
  Animated/             ← category folder (optional)
    SpongeBob/
      ep01.mp4
  Little Bear (Full Series)/   ← season folders auto-detected
    Season 1/
      ep01.mp4
    Season 2/
      ep01.mp4
```

Each subfolder containing MP4s is a "show." Folders named *Season N*, *Series N*, *S N*, or *Part N* are recognized as season folders and grouped under their parent show name in the index automatically.

### 2. Analyze episodes

- **Single episode** — Select an episode in the Library tree, click **Analyze Episode**. Results appear on the right with a full metric breakdown and a cuts-per-30s timeline chart.
- **Whole show** — Select a show folder, click **Analyze Show (Batch)**. Episodes are analyzed in sequence with a live progress bar. Results are cached — re-opening the app never re-analyzes files.
- **Full series aggregate** — After analyzing all seasons of a show, click **Full Series Aggregate** to see combined statistics across every season folder at once.

### 3. Sample a show for research

For large shows, use **File → Episode Sampler** to build a reproducible, documented sample instead of analyzing every episode.

- Choose a stratification strategy (by season, or unstratified)
- Choose a selection method: census, simple random, systematic, or spread (chunk) sampling
- Set your sample size and random seed
- Preview the selected episodes, then **Send to Analysis Queue** to analyze only those episodes
- The sampler saves a `manifest.json` and `selected.csv` alongside your output — a permanent record of exactly how the sample was drawn

Once analyzed, use **View Sample Aggregate** to load a manifest and see aggregate results for only the sampled episodes — useful for comparing different sample sizes against a full-show baseline.

### 4. Add episode metadata

Air dates, season numbers, and episode numbers can be attached to any analyzed episode. This enables chronological charting and longitudinal research.

**Manual entry** — Select any analyzed episode. An **Air Date / Season / Ep #** panel appears below the results. Enter values in any common date format (`11/8/1995`, `8 Nov 1995`, `1995-11-08`, etc.) and click **Save**.

**Import from TVMaze** — `File → Import Episode Metadata from TVMaze…`

Paste any TVMaze show URL (e.g. `https://www.tvmaze.com/shows/17755/franklin/episodes`) and click **Fetch**. CMAT calls the free TVMaze public API — no account or key needed — and previews how each episode matches your local files by season/episode number (green) or fuzzy title match (yellow). Click **Apply to Database** to write the air dates.

**Import from Wikipedia** — `File → Import Episode Metadata from Wikipedia…`

For shows not on TVMaze, save the Wikipedia "List of X episodes" page as HTML (`Ctrl+S` in your browser), then browse to it in this dialog. CMAT parses the episode table and performs the same match preview and apply workflow.

### 5. Visualize series trends

Once episodes are analyzed, click **Show Chart** from any show-level or full-series aggregate view. The chart window has three independent controls:

| Control | Options |
|---------|---------|
| **X-axis** | Air Date (when ≥ 80 % of episodes have dates) · Episode Number |
| **Y-axis** | Sensory Load Score · Cuts per Minute · Color Saturation · Color Contrast · Motion · Flashing / min · Audio RMS |
| **Colour by** | Season · Era |

**Era stratification** — Click **Edit Eras…** to define named date ranges (e.g. *Original Run 1992–1997*, *Revival 2003–2006*). Each era gets its own bar colour; episodes outside all defined ranges appear in gray. Eras are saved per-show to the local database and reload automatically the next time you open the chart.

### 6. Browse and compare

- **Index tab** — Sortable, filterable table of every analyzed episode and show. Columns include Air Date, Season, and Episode Number alongside all analysis metrics. Click any column header to sort; type in the filter bar to search.
- **Compare** — Click **Pin for Compare** on any episode result, then **Compare with Pinned** on another to see a side-by-side metric table.
- **Notes** — Add per-episode notes in the results panel; saved automatically to the local database.

### 7. Adjust weights and presets

**Settings → Sensory Load Weights** — change how much each metric contributes to the composite score, or adjust normalization ceilings. Age-range and content-type presets are built in. Switching presets re-scores all cached results instantly — no re-analysis needed.

### 8. Export

From the results panel: **Export JSON**, **Export CSV**, or **Export PDF Report** for a printable one-page summary.

---

## Age-range presets

| Preset | Best for |
|--------|---------|
| General / All Ages | Cross-genre comparison baseline |
| Toddler (0–2) | Tight ceilings; flashing weighted higher for safety |
| Preschool (2–5) | Calibrated to Lillard & Peterson (2011) age range |
| Early Childhood (5–8) | Wider tolerances than preschool |
| Tween (8–12) | Near-adult tolerances |
| Animated / Cartoon | Saturation weighted higher for cartoon-vs-cartoon comparison |
| Live-Action / YouTube | Contrast weighted higher; saturation near-zeroed |

Custom presets can be created and saved. Built-in presets cannot be deleted.

---

## Research grounding

The conceptual framework comes from media research on **formal features** — the perceptually salient, content-independent structural attributes of video (cuts, motion, pace, sound). These features capture attention through the **orienting response**: an automatic, reflexive reallocation of attention toward novel or changing stimuli.

Key references:
- Huston & Wright — formal features framework
- Lang — Limited Capacity Model of Mediated Message Processing (LC4MP)
- Lillard & Peterson (2011), *Pediatrics* — pacing and immediate executive function in 4-year-olds
- Lillard et al. (2015) — fantastical content as a possible moderator
- Christakis et al. (2004), *Pediatrics* — early TV exposure and attention (correlational)
- Itti & Koch — bottom-up visual saliency and motion

All findings are correlational. CMAT describes the stimulus; it does not predict outcomes for any individual child.

---

## Building from source

**Requirements:** Python 3.11+, FFmpeg on PATH

```bash
git clone https://github.com/SamuelBabbertResearch/childrens-media-analysis-toolkit.git
cd childrens-media-analysis-toolkit
pip install -r requirements.txt
python gui.py
```

**Run tests:**
```bash
pytest tests/
```

**Build the exe:**
```bash
# Place ffmpeg.exe in the project root first, then:
python -m PyInstaller build.spec -y
copy config.json dist\CMAT\config.json
```

---

## CLI usage

```bash
# Analyze a single episode
python cli.py analyze episode.mp4

# Analyze a whole show folder
python cli.py analyze "My Videos/Little Bear/"

# Build a reproducible episode sample
python cli.py sample "My Videos/Little Bear/" --stratify season --method spread --per-season-n 3 --seed 42

# Query the index database
python cli.py db episodes "My Videos/" --sort sensory_load_score --desc
python cli.py db shows "My Videos/" --sort avg_load
```

---

## License

MIT License — see [LICENSE](LICENSE)
