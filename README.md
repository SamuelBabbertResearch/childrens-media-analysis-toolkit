# Children's Media Analysis Toolkit (CMAT)

A desktop Windows application that analyzes MP4 episodes of children's TV shows and produces a **sensory-load profile** for each episode and a cumulative profile for a whole show.

The tool measures formal and structural features of the video — pacing, color, motion, flashing, and audio loudness. It does **not** issue a verdict on appropriateness. It presents transparent, labeled metrics that a caregiver, therapist, or researcher interprets.

---

## What it measures

| Metric | What it captures |
|--------|-----------------|
| **Scene pacing** | How fast the camera cuts. Faster cutting triggers more frequent orienting responses and higher cognitive load. |
| **Motion** | Average frame-to-frame movement. High motion is a pre-attentive attention magnet. |
| **Color saturation** | How vivid and pure the colors are. Higher in cartoons; lower in live-action. |
| **Color contrast** | Spatial spread of brightness within a frame. Captures dark/light extremes that make live-action visually intense. |
| **Flashing** | Rapid luminance changes per minute. Relevant to photosensitivity and overstimulation. |
| **Audio loudness** | Average RMS volume level and dynamic range. Loud, consistent audio drives arousal independently of visuals. |
| **Sensory load score** | A transparent weighted composite of all the above. Always shows its component parts. |

Grounded in the Huston & Wright formal features framework, Lang's Limited Capacity Model (LC4MP), and Lillard & Peterson (2011).

> **Honest limitation:** This tool measures the stimulus, not the viewer. It cannot account for the child's age, temperament, or sensory-processing profile. Output is a profile to inform judgment, not a rating or verdict.

---

## Screenshots
<img width="805" height="435" alt="image" src="https://github.com/user-attachments/assets/305685d9-639c-428a-9246-b00e1a5709b6" />
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

1. **Pick a root folder** — File → Open Root Folder. Your folder should look like this:
   ```
   My Videos/
     SpongeBob/
       episode01.mp4
       episode02.mp4
     Little Bear/
       episode01.mp4
   ```
   Each subfolder is a "show." MP4 files inside are episodes.

2. **Analyze an episode** — Select an episode in the tree, click "Analyze Episode." Results appear on the right with a full metric breakdown.

3. **Analyze a whole show** — Select a show folder, click "Analyze Show." Episodes are analyzed in sequence with a live progress bar. Results are cached — re-opening the app never re-analyzes files.

4. **Browse the index** — Click the "Index" tab to see all analyzed episodes and shows across your library, sortable by any metric.

5. **Adjust weights** — Settings → Sensory Load Weights. Change how much each metric contributes to the composite score. Age-range and content-type presets are built in (Toddler, Preschool, Animated, Live-Action, etc.).

6. **Export** — File → Export as CSV or JSON. Or click "Export PDF Report" for a printable one-page summary.

---

## Age-range presets

The Settings dialog includes built-in presets that adjust both weights and normalization ceilings for different audiences:

| Preset | Best for |
|--------|---------|
| General / All Ages | Cross-genre comparison baseline |
| Toddler (0–2) | Tight ceilings; flashing weighted higher for safety |
| Preschool (2–5) | Calibrated to Lillard & Peterson (2011) age range |
| Early Childhood (5–8) | Wider tolerances than preschool |
| Tween (8–12) | Near-adult tolerances |
| Animated / Cartoon | Saturation weighted higher for cartoon-vs-cartoon comparison |
| Live-Action / YouTube | Contrast weighted higher; saturation near-zeroed |

Switching presets re-scores all cached results instantly — no re-analysis needed.

---

## Research grounding

The conceptual framework comes from media research on **formal features** — the perceptually salient, content-independent structural attributes of video (cuts, motion, pace, sound). These features capture attention through the **orienting response**: an automatic, reflexive reallocation of attention toward novel or changing stimuli.

Key references:
- Huston & Wright — formal features framework
- Lang — Limited Capacity Model of Mediated Message Processing (LC4MP)
- Lillard & Peterson (2011), *Pediatrics* — pacing and immediate executive function in 4-year-olds
- Christakis et al. (2004), *Pediatrics* — early TV exposure and attention (correlational)
- Itti & Koch — bottom-up visual saliency and motion

All findings are correlational. The tool describes the stimulus; it does not predict outcomes for any individual child.

---

## Building from source

**Requirements:** Python 3.11+, FFmpeg on PATH

```bash
git clone https://github.com/yourusername/childrens-tv-analyzer.git
cd childrens-tv-analyzer
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
python cli.py analyze "My Videos/SpongeBob/"

# Query the index database
python cli.py db episodes "My Videos/" --sort sensory_load_score --desc
python cli.py db shows "My Videos/" --sort avg_load
```

---

## License

MIT License — see [LICENSE](LICENSE)
