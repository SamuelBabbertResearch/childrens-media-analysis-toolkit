"""
Audio loudness metrics via FFmpeg.

Extracts mono PCM audio through FFmpeg (assumed on PATH), then computes
windowed RMS loudness to capture both overall intensity and temporal variation.

WHAT IS COMPUTED. The track is downmixed to mono and RESAMPLED TO 8 kHz before
any measurement, so everything below is amplitude on a band-limited signal, not
perceptual loudness. It is not LUFS and not EBU R128; two files mastered to the
same broadcast loudness can differ here, and a file's values are comparable only
with files measured by this same path.

  - rms_mean: mean of the per-window (1 s) RMS amplitude, linear, 0-1.
  - rms_peak: the loudest single 1-second window.
  - rms_temporal_var: variance of the per-window RMS — how much the level moves
    about, as distinct from how high it sits.
  - dynamic_range_db: 20*log10(peak / mean) over those windows.

Why these are measured at all: audio intensity is one of the formal features
Huston & Wright's framework identifies, and Lang's LC4MP treats structural
change as a processing demand. That literature motivates measuring the
stimulus; it does not make any of these four numbers a measure of arousal,
startle, or anything else occurring in a listener, and none of them has been
graded against a perceptual criterion.
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
        return AudioMetrics(
            available=False,
            unavailable_reason=AudioMetrics.REASON_NO_FFMPEG)
    except RuntimeError as exc:
        logger.warning("Audio extraction failed for %s: %s", video_path.name, exc)
        return AudioMetrics(
            available=False,
            unavailable_reason=AudioMetrics.REASON_EXTRACTION_FAILED)

    if audio is None or len(audio) == 0:
        # No samples came back. Either the container has no audio stream, or
        # it has one and it is empty; both are "there is nothing to measure",
        # which is NOT the same as "the audio measured zero".
        return AudioMetrics(
            available=False,
            unavailable_reason=AudioMetrics.REASON_NO_AUDIO_TRACK)

    return _compute_from_samples(audio)


def compute_windowed_audio_metrics(
    video_path: Path,
    window_sec: float,
    window_count: int,
    start_sec: float = 0.0,
    end_sec: float | None = None,
) -> list[AudioMetrics]:
    """Compute audio metrics for contiguous clips after one FFmpeg decode."""
    if window_sec <= 0:
        raise ValueError("window_sec must be greater than zero")
    if window_count <= 0:
        return []

    try:
        duration_sec = (
            max(0.0, end_sec - start_sec) if end_sec is not None else None
        )
        audio = _extract_audio(
            video_path, start_sec=start_sec, duration_sec=duration_sec
        )
    except (FileNotFoundError, RuntimeError) as exc:
        logger.warning("Audio extraction failed for %s: %s", video_path.name, exc)
        return [AudioMetrics(available=False) for _ in range(window_count)]
    if audio is None or len(audio) == 0:
        return [AudioMetrics(available=False) for _ in range(window_count)]

    samples_per_window = max(1, int(round(window_sec * _SAMPLE_RATE)))
    out: list[AudioMetrics] = []
    for idx in range(window_count):
        start = idx * samples_per_window
        end = min(len(audio), start + samples_per_window)
        samples = audio[start:end]
        out.append(
            _compute_from_samples(samples)
            if len(samples) else AudioMetrics(available=False)
        )
    return out


def _extract_audio(
    video_path: Path,
    start_sec: float = 0.0,
    duration_sec: float | None = None,
) -> np.ndarray | None:
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

    command = [ffmpeg_exe()]
    if start_sec > 0:
        command.extend(["-ss", f"{start_sec:.6f}"])
    command.extend(["-i", str(video_path)])
    if duration_sec is not None:
        command.extend(["-t", f"{duration_sec:.6f}"])
    command.extend([
            "-vn",                        # drop video
            "-acodec", "pcm_s16le",       # 16-bit signed PCM
            "-ar", str(_SAMPLE_RATE),     # resample to 8 kHz
            "-ac", "1",                   # mono
            "-f", "s16le",                # raw PCM output
            "-",                          # pipe to stdout
    ])
    result = subprocess.run(
        command,
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
