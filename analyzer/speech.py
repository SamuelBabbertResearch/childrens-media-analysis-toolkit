"""
Speech metrics: words per minute and speech density.

Source priority:
  1. SRT file alongside the video   (exact timestamps, zero compute)
  2. VTT file alongside the video   (same)
  3. faster-whisper auto-transcription (offline, ~2-5 min/episode on CPU)
  4. unavailable                    (no CC + transcription disabled or not installed)

Speech metrics are NOT included in the sensory-load composite because they are
absent for many episodes. Including them would make scores incomparable across
episodes with and without CC files.
"""

from __future__ import annotations
import os as _os
import re
import warnings as _warnings
from pathlib import Path
from typing import Any

# Set before faster-whisper is imported so the HuggingFace Hub warnings
# never appear. Done at module load time (main thread) rather than inside
# the worker so global state is not mutated from a background thread.
_os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
_os.environ.setdefault("HF_HUB_VERBOSITY", "error")
_warnings.filterwarnings("ignore", message=".*symlinks.*", category=UserWarning)

from .schema import SpeechMetrics

_TAG_RE   = re.compile(r'<[^>]+>')
_WORD_RE  = re.compile(r'\b\w+\b')
_SEQ_RE   = re.compile(r'^\d+\s*$')   # SRT sequence number lines

# Matches both SRT (comma) and VTT (period) timestamp separators
_STAMP_RE = re.compile(
    r'(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*'
    r'(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})'
)


def _ts_to_sec(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def _count_words(text: str) -> int:
    text = _TAG_RE.sub(' ', text)
    return len(_WORD_RE.findall(text))


# ---------------------------------------------------------------------------
# CC file discovery
# ---------------------------------------------------------------------------

def _find_cc_file(video_path: Path) -> Path | None:
    """Return path to .srt or .vtt with the same stem as the video, or None."""
    for ext in (".srt", ".vtt"):
        candidate = video_path.with_suffix(ext)
        if candidate.exists():
            return candidate
    return None


# ---------------------------------------------------------------------------
# SRT / VTT parser
# ---------------------------------------------------------------------------

def extract_cc_text(cc_path: Path) -> str:
    """Return cue dialogue lines joined as a single string.

    Strips timestamps and SRT sequence numbers only. Non-speech cues
    (e.g. [MUSIC], speaker labels) are left intact for the caller to
    handle according to its own analysis needs.
    """
    try:
        text = cc_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""

    lines: list[str] = []
    for cue in re.split(r'\n\s*\n', text):
        if not _STAMP_RE.search(cue):
            continue
        body = _STAMP_RE.sub('', cue, count=1).strip()
        for ln in body.splitlines():
            ln = ln.strip()
            if ln and not _SEQ_RE.match(ln):
                lines.append(ln)
    return ' '.join(lines)


def _parse_cc(cc_path: Path, duration_sec: float) -> SpeechMetrics:
    try:
        text = cc_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return SpeechMetrics(available=False, source="none")

    total_words        = 0
    total_dialogue_sec = 0.0

    for cue in re.split(r'\n\s*\n', text):
        m = _STAMP_RE.search(cue)
        if not m:
            continue
        start = _ts_to_sec(m.group(1), m.group(2), m.group(3), m.group(4))
        end   = _ts_to_sec(m.group(5), m.group(6), m.group(7), m.group(8))
        if end <= start or start >= duration_sec:
            continue
        end = min(end, duration_sec)

        cue_body = _STAMP_RE.sub('', cue, count=1).strip()
        lines    = [ln for ln in cue_body.splitlines() if not _SEQ_RE.match(ln.strip())]
        total_words        += _count_words(' '.join(lines))
        total_dialogue_sec += end - start

    if total_dialogue_sec < 0.5:
        return SpeechMetrics(available=False, source="none")

    wpm     = total_words / (total_dialogue_sec / 60.0)
    density = min(1.0, total_dialogue_sec / duration_sec) if duration_sec > 0 else 0.0

    return SpeechMetrics(
        available=True,
        source=cc_path.suffix.lower().lstrip("."),
        words_per_minute=round(wpm, 1),
        speech_density=round(density, 4),
        total_words=total_words,
    )


# ---------------------------------------------------------------------------
# faster-whisper transcription
# ---------------------------------------------------------------------------

_whisper_cache: dict[str, Any] = {}


def _get_whisper_model(model_size: str) -> Any:
    if model_size not in _whisper_cache:
        from faster_whisper import WhisperModel
        _whisper_cache[model_size] = WhisperModel(
            model_size, device="cpu", compute_type="int8"
        )
    return _whisper_cache[model_size]


def _fmt_srt_ts(sec: float) -> str:
    """Convert seconds to SRT timestamp format HH:MM:SS,mmm."""
    ms = round(sec * 1000)
    h, ms  = divmod(ms, 3_600_000)
    m, ms  = divmod(ms, 60_000)
    s, ms  = divmod(ms, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _save_srt(video_path: Path, segments: list) -> None:
    """Write Whisper segments to an SRT file alongside the video."""
    srt_path = video_path.with_suffix(".srt")
    lines: list[str] = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{_fmt_srt_ts(seg.start)} --> {_fmt_srt_ts(seg.end)}")
        lines.append(seg.text.strip())
        lines.append("")
    srt_path.write_text("\n".join(lines), encoding="utf-8")


def _transcribe(video_path: Path, duration_sec: float, model_size: str) -> SpeechMetrics:
    try:
        print(f"[speech] loading {model_size} model…", flush=True)
        model = _get_whisper_model(model_size)
        print(f"[speech] transcribing {video_path.name}…", flush=True)
        segments_gen, _ = model.transcribe(str(video_path), beam_size=5)
        segments = list(segments_gen)   # consume generator so we can iterate twice
    except Exception as exc:
        import traceback; traceback.print_exc()
        return SpeechMetrics(available=False, source=f"error:{exc}")

    # Persist transcript as SRT alongside the video so vocab analysis can use it
    # and so re-analysis skips Whisper entirely on subsequent runs.
    try:
        _save_srt(video_path, segments)
        print(f"[speech] saved SRT → {video_path.with_suffix('.srt').name}", flush=True)
    except Exception as exc:
        print(f"[speech] warning — could not save SRT: {exc}", flush=True)

    total_words        = 0
    total_dialogue_sec = 0.0
    for seg in segments:
        start, end = seg.start, seg.end
        if end <= start or start >= duration_sec:
            continue
        end = min(end, duration_sec)
        total_words        += _count_words(seg.text)
        total_dialogue_sec += end - start
    print(f"[speech] done — {total_words} words, {total_dialogue_sec:.1f}s dialogue", flush=True)

    if total_dialogue_sec < 0.5:
        return SpeechMetrics(available=False, source="none")

    wpm     = total_words / (total_dialogue_sec / 60.0)
    density = min(1.0, total_dialogue_sec / duration_sec) if duration_sec > 0 else 0.0

    return SpeechMetrics(
        available=True,
        source="whisper",
        words_per_minute=round(wpm, 1),
        speech_density=round(density, 4),
        total_words=total_words,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transcribe_only(
    video_path: Path,
    duration_sec: float,
    cfg: dict[str, Any],
) -> SpeechMetrics:
    """Run Whisper transcription and save an SRT alongside the video.

    Unlike compute_speech_metrics, this always runs Whisper even when
    transcription_enabled is False — the caller is explicitly requesting it.
    Returns SpeechMetrics(available=False) if faster-whisper is not installed.
    """
    try:
        import faster_whisper  # noqa: F401
    except ImportError as exc:
        return SpeechMetrics(available=False, source=f"not_installed:{exc}")
    return _transcribe(video_path, duration_sec, cfg.get("speech_whisper_model", "small"))


def compute_speech_metrics(
    video_path: Path,
    duration_sec: float,
    cfg: dict[str, Any],
) -> SpeechMetrics:
    """Return WPM and speech density from a CC file, Whisper, or unavailable."""
    print(f"[speech] speech_transcription_enabled={cfg.get('speech_transcription_enabled', False)}", flush=True)

    cc = _find_cc_file(video_path)
    if cc is not None:
        print(f"[speech] found CC file: {cc.name}", flush=True)
        result = _parse_cc(cc, duration_sec)
        if result.available:
            return result

    if not cfg.get("speech_transcription_enabled", False):
        print("[speech] transcription disabled — returning unavailable", flush=True)
        return SpeechMetrics(available=False, source="disabled")

    try:
        import faster_whisper
        print(f"[speech] faster_whisper version: {faster_whisper.__version__}", flush=True)
    except ImportError as exc:
        print(f"[speech] faster_whisper import failed: {exc}", flush=True)
        return SpeechMetrics(available=False, source="not_installed")

    return _transcribe(video_path, duration_sec, cfg.get("speech_whisper_model", "small"))
