"""
Audio loudness metrics via FFmpeg.

Extracts mono PCM audio through FFmpeg (assumed on PATH), then computes
windowed RMS loudness to capture both overall intensity and temporal variation.

Why these metrics:
  - mean_rms: overall loudness level — loud music/screaming drives arousal directly.
  - rms_temporal_var: how much volume jumps around — sudden peaks are more startling
    than steady noise of the same average level.
  - dynamic_range_db: peak-to-mean ratio; high values indicate surprising loud events.
"""

from __future__ import annotations
import logging
import subprocess
import sys
from pathlib import Path

# Suppress the console window that Windows pops up for subprocess calls
_NO_WINDOW = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}

import numpy as np

from .ffmpeg_path import ffmpeg_exe
from .schema import AudioMetrics

logger = logging.getLogger(__name__)

_SAMPLE_RATE = 8000   # Hz — sufficient for loudness; keeps memory low
_WINDOW_SEC  = 1.0    # seconds per RMS window


def compute_audio_metrics(video_path: Path) -> AudioMetrics:
    """
    Extract audio via FFmpeg and compute loudness metrics.

    Returns AudioMetrics with available=False if FFmpeg is not found,
    the file has no audio track, or any other extraction error occurs.
    """
    try:
        audio = _extract_audio(video_path)
    except FileNotFoundError:
        logger.warning("FFmpeg not found on PATH — skipping audio metrics.")
        return AudioMetrics(available=False)
    except RuntimeError as exc:
        logger.warning("Audio extraction failed for %s: %s", video_path.name, exc)
        return AudioMetrics(available=False)

    if audio is None or len(audio) == 0:
        return AudioMetrics(available=False)

    return _compute_from_samples(audio)


def _extract_audio(video_path: Path) -> np.ndarray | None:
    """
    Run FFmpeg to decode audio as 8 kHz mono float32 PCM piped to stdout.
    Returns None if the file has no audio stream.
    """
    # Fast probe: ffmpeg -i reads only container headers and exits immediately.
    # (No output file specified → exits with error, but stderr has stream info.)
    probe = subprocess.run(
        [ffmpeg_exe(), "-i", str(video_path)],
        capture_output=True, text=True, timeout=15, **_NO_WINDOW,
    )
    if "Audio:" not in probe.stderr:
        logger.info("No audio stream in %s", video_path.name)
        return None

    result = subprocess.run(
        [
            ffmpeg_exe(), "-i", str(video_path),
            "-vn",                        # drop video
            "-acodec", "pcm_s16le",       # 16-bit signed PCM
            "-ar", str(_SAMPLE_RATE),     # resample to 8 kHz
            "-ac", "1",                   # mono
            "-f", "s16le",                # raw PCM output
            "-",                          # pipe to stdout
        ],
        capture_output=True,
        timeout=300, **_NO_WINDOW,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode(errors="replace")[-300:])

    raw = np.frombuffer(result.stdout, dtype=np.int16)
    return raw.astype(np.float32) / 32768.0


def _compute_from_samples(audio: np.ndarray) -> AudioMetrics:
    window_samples = max(1, int(_WINDOW_SEC * _SAMPLE_RATE))
    n_windows = max(1, len(audio) // window_samples)

    rms_values = np.array([
        float(np.sqrt(np.mean(audio[i * window_samples:(i + 1) * window_samples] ** 2)))
        for i in range(n_windows)
    ])

    mean_rms = float(np.mean(rms_values))
    peak_rms = float(np.max(rms_values))

    # Dynamic range: ratio of peak to mean in dB (0 if silent)
    if mean_rms > 1e-9:
        dynamic_range_db = float(20 * np.log10(peak_rms / mean_rms))
    else:
        dynamic_range_db = 0.0

    return AudioMetrics(
        rms_mean=round(mean_rms, 5),
        rms_peak=round(peak_rms, 5),
        rms_temporal_var=round(float(np.var(rms_values)), 6),
        dynamic_range_db=round(dynamic_range_db, 2),
        available=True,
    )
