"""Build the browser-based matched-pair hard-cut marker.

The page is deliberately self-contained: it reads no network resources, plays
the original episode files at the saved 30-second boundaries, retains work in
browser local storage, and downloads an auditable CSV when the coder finishes.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def _selected_rows(run_dir: Path) -> list[dict[str, Any]]:
    source = Path(run_dir) / "selected_clips.csv"
    if not source.is_file():
        raise FileNotFoundError(f"No matched clip table at {source}")
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("The matched clip table is empty.")
    return rows


def _clip_payload(row: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(row.get("source_path") or ""))
    if not path.is_file():
        raise FileNotFoundError(f"Source episode not found: {path}")
    start = float(row.get("start_sec") or 0)
    end = float(row.get("end_sec") or 0)
    if end <= start:
        raise ValueError(f"Invalid clip boundary for {row.get('clip_id', 'clip')}")
    return {
        "pairId": str(row.get("pair_id") or ""),
        "targetFeature": str(row.get("target_feature") or ""),
        "studyLabel": str(row.get("study_label") or ""),
        "level": str(row.get("target_level") or ""),
        "clipId": str(row.get("clip_id") or ""),
        "episode": str(row.get("source_relpath") or path.name),
        "sourcePath": str(path),
        "sourceUrl": path.resolve().as_uri(),
        "start": start,
        "end": end,
        "duration": end - start,
        "startTimecode": str(row.get("start_timecode") or ""),
        "endTimecode": str(row.get("end_timecode") or ""),
        "automatedCutsPerMin": float(row.get("cuts_per_min") or 0),
    }


def build_pair_cut_marker(run_dir: Path, default_pair: str = "AUDIO_1") -> Path:
    """Write and return a browser cut-marker page for a matched-pair run."""
    run_dir = Path(run_dir)
    clips = [_clip_payload(row) for row in _selected_rows(run_dir)]
    pairs = sorted({clip["pairId"] for clip in clips if clip["pairId"]})
    if not pairs:
        raise ValueError("The selected clips have no pair IDs.")
    initial = default_pair if default_pair in pairs else pairs[0]
    payload = json.dumps(clips, ensure_ascii=True).replace("</", "<\\/")
    storage_key = json.dumps(f"cmat-pair-cut-marker:{run_dir.resolve()}")
    destination = run_dir / "hand_code_matched_pairs.html"
    page = _PAGE.replace("__CLIPS__", payload).replace(
        "__INITIAL_PAIR__", json.dumps(initial)).replace(
        "__STORAGE_KEY__", storage_key)
    destination.write_text(page, encoding="utf-8")
    return destination


_PAGE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CMAT matched-pair cut marker</title>
<style>
  :root { color-scheme: light dark; font-family: system-ui, sans-serif; }
  body { margin: 0; background: Canvas; color: CanvasText; }
  main { max-width: 1100px; margin: auto; padding: 20px; }
  header, .toolbar, .marker-row, .summary { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
  h1 { margin: 0 0 6px; font-size: 1.45rem; font-weight: 600; }
  p { margin: 4px 0 14px; }
  select, button, input, textarea { font: inherit; }
  select, button { min-height: 40px; padding: 7px 12px; }
  button { cursor: pointer; }
  button.primary { background: Highlight; color: HighlightText; border: 1px solid Highlight; border-radius: 5px; }
  button.clip.active { outline: 3px solid Highlight; outline-offset: 2px; }
  .toolbar { margin: 16px 0; }
  .clip-name { margin: 12px 0 4px; font-weight: 600; }
  .meta, .hint, #status { color: GrayText; }
  video { display: block; width: 100%; max-height: 560px; margin: 12px 0; background: #000; }
  .marker-row { margin: 12px 0; }
  #mark { min-width: 190px; min-height: 52px; font-weight: 600; }
  .count { font-size: 1.15rem; font-variant-numeric: tabular-nums; }
  table { width: 100%; border-collapse: collapse; margin-top: 12px; }
  th, td { text-align: left; padding: 8px; border-bottom: 1px solid GrayText; }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  textarea { width: 100%; min-height: 58px; box-sizing: border-box; }
  .content-check { display: grid; grid-template-columns: minmax(180px, 260px) 1fr; gap: 12px; margin: 16px 0; }
  footer { margin-top: 18px; display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
  @media (max-width: 650px) { .content-check { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>Matched-pair hard-cut marker</h1>
      <p>Mark abrupt shot changes only. Do not mark the beginning of the clip, fades, or dissolves.</p>
    </div>
  </header>

  <div class="toolbar">
    <label for="pair">Pair</label>
    <select id="pair"></select>
    <span id="pairFeature" class="meta"></span>
  </div>
  <div id="clipButtons" class="toolbar" aria-label="Clips in selected pair"></div>

  <div id="clipName" class="clip-name"></div>
  <div id="clipMeta" class="meta"></div>
  <video id="video" controls preload="metadata"></video>
  <div id="status" aria-live="polite">Choose a clip above.</div>

  <div class="marker-row">
    <button id="mark" class="primary" type="button">Mark hard cut (M)</button>
    <button id="undo" type="button">Undo last</button>
    <button id="restart" type="button">Restart clip</button>
    <span id="count" class="count"></span>
  </div>

  <div class="content-check">
    <label>Content check
      <select id="contentStatus">
        <option value="unchecked">Not checked yet</option>
        <option value="clean">Looks clean</option>
        <option value="intro">Intro or title content</option>
        <option value="break">Ad or break content</option>
        <option value="other">Other unwanted content</option>
      </select>
    </label>
    <label>Notes<textarea id="notes" placeholder="Optional content or coding notes"></textarea></label>
  </div>

  <table aria-label="Marked hard cuts">
    <thead><tr><th>Cut</th><th class="num">Within clip</th><th class="num">Episode time</th></tr></thead>
    <tbody id="marks"></tbody>
  </table>

  <footer>
    <span class="hint">Progress is retained in this browser on this computer.</span>
    <button id="download" class="primary" type="button">Download coding CSV</button>
  </footer>
</main>
<script>
const clips = __CLIPS__;
const initialPair = __INITIAL_PAIR__;
const storageKey = __STORAGE_KEY__;
const byPair = clips.reduce((groups, clip) => {
  (groups[clip.pairId] ||= []).push(clip); return groups;
}, {});
const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
let current = null;
const $ = id => document.getElementById(id);
const fmt = s => `${Math.floor(s / 60).toString().padStart(2,'0')}:${(s % 60).toFixed(2).padStart(5,'0')}`;
function record(c) {
  return saved[c.clipId] ||= {marks: [], contentStatus: 'unchecked', notes: ''};
}
function persist() { localStorage.setItem(storageKey, JSON.stringify(saved)); }
function loadClip(c) {
  current = c;
  [...document.querySelectorAll('button.clip')].forEach(b => b.classList.toggle('active', b.dataset.id === c.clipId));
  $('clipName').textContent = `${c.studyLabel} · ${c.level[0].toUpperCase()+c.level.slice(1)}`;
  $('clipMeta').textContent = `${c.episode} · ${c.startTimecode}–${c.endTimecode} · automated reference ${c.automatedCutsPerMin.toFixed(1)} cuts/min`;
  const r = record(c);
  $('contentStatus').value = r.contentStatus;
  $('notes').value = r.notes;
  const v = $('video'); v.src = c.sourceUrl; v.load();
  v.onloadedmetadata = () => { v.currentTime = c.start; $('status').textContent = 'Ready at the start of the 30-second window.'; };
  render();
}
function loadPair(id) {
  const pairClips = [...(byPair[id] || [])].sort((a,b) => a.level.localeCompare(b.level));
  $('pairFeature').textContent = pairClips.length ? `Target feature: ${pairClips[0].targetFeature}` : '';
  $('clipButtons').replaceChildren(...pairClips.map(c => {
    const b = document.createElement('button'); b.type='button'; b.className='clip'; b.dataset.id=c.clipId;
    b.textContent = `${c.studyLabel} · ${c.level}`; b.onclick=()=>loadClip(c); return b;
  }));
  if (pairClips.length) loadClip(pairClips[0]);
}
function render() {
  if (!current) return;
  const r = record(current), rate = r.marks.length * 60 / current.duration;
  $('count').textContent = `${r.marks.length} hard cuts · ${rate.toFixed(1)} cuts/min`;
  $('marks').replaceChildren(...r.marks.map((m,i) => {
    const tr=document.createElement('tr');
    [String(i+1), fmt(m.relative), fmt(m.absolute)].forEach((text,j) => {
      const td=document.createElement('td'); td.textContent=text; if(j) td.className='num'; tr.append(td);
    }); return tr;
  }));
  $('undo').disabled = !r.marks.length;
}
function markCut() {
  if (!current) return;
  const v=$('video'); v.pause();
  if (v.currentTime < current.start || v.currentTime > current.end) { $('status').textContent='Move the playhead inside the saved window first.'; return; }
  const r=record(current), absolute=Number(v.currentTime.toFixed(3));
  if (r.marks.some(m => Math.abs(m.absolute-absolute)<0.05)) { $('status').textContent='That cut is already marked.'; return; }
  r.marks.push({absolute, relative:Number((absolute-current.start).toFixed(3))});
  r.marks.sort((a,b)=>a.absolute-b.absolute); persist(); render(); $('status').textContent=`Marked cut at ${fmt(absolute-current.start)}.`;
}
function csvCell(v) { const s=String(v ?? ''); return /[",\n]/.test(s) ? `"${s.replaceAll('"','""')}"` : s; }
function downloadCsv() {
  const header=['record_type','pair_id','target_feature','study_label','target_level','clip_id','source_path','window_start_sec','window_end_sec','hard_cut_count','hand_coded_cuts_per_min','cut_number','cut_timestamp_within_clip_sec','cut_timestamp_episode_sec','content_status','notes'];
  const rows=[header];
  clips.forEach(c => { const r=record(c), rate=r.marks.length*60/c.duration;
    rows.push(['summary',c.pairId,c.targetFeature,c.studyLabel,c.level,c.clipId,c.sourcePath,c.start,c.end,r.marks.length,rate.toFixed(6),'','','',r.contentStatus,r.notes]);
    r.marks.forEach((m,i)=>rows.push(['cut',c.pairId,c.targetFeature,c.studyLabel,c.level,c.clipId,c.sourcePath,c.start,c.end,r.marks.length,rate.toFixed(6),i+1,m.relative,m.absolute,r.contentStatus,r.notes]));
  });
  const blob=new Blob([rows.map(r=>r.map(csvCell).join(',')).join('\r\n')],{type:'text/csv'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='hand_coded_pair_cuts.csv'; a.click(); setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}
Object.keys(byPair).sort().forEach(id => { const o=document.createElement('option'); o.value=id; o.textContent=id; $('pair').append(o); });
$('pair').value=initialPair; $('pair').onchange=e=>loadPair(e.target.value);
$('video').ontimeupdate=()=>{ if(current && $('video').currentTime>=current.end){$('video').pause();$('video').currentTime=current.start;$('status').textContent='End of window. Returned to the start.';} };
$('mark').onclick=markCut;
$('undo').onclick=()=>{if(current){record(current).marks.pop();persist();render();}};
$('restart').onclick=()=>{if(current){$('video').pause();$('video').currentTime=current.start;}};
$('contentStatus').onchange=e=>{if(current){record(current).contentStatus=e.target.value;persist();}};
$('notes').oninput=e=>{if(current){record(current).notes=e.target.value;persist();}};
$('download').onclick=downloadCsv;
document.addEventListener('keydown', e=>{if(e.key.toLowerCase()==='m' && !['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)){e.preventDefault();markCut();}});
loadPair(initialPair);
</script>
</body>
</html>
'''
