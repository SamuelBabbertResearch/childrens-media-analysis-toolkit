"""Audio summary windows must include every decoded sample."""

from types import SimpleNamespace

import numpy as np

from analyzer.metrics_audio import _compute_from_samples, _extract_audio, _SAMPLE_RATE


def test_final_partial_second_is_included():
    one_second_quiet = np.full(_SAMPLE_RATE, 0.1, dtype=np.float32)
    half_second_loud = np.full(_SAMPLE_RATE // 2, 0.5, dtype=np.float32)

    metrics = _compute_from_samples(
        np.concatenate([one_second_quiet, half_second_loud]))

    assert metrics.available
    assert metrics.rms_mean == 0.3
    assert metrics.rms_peak == 0.5


def test_audio_decode_uses_one_ffmpeg_process(monkeypatch, tmp_path):
    """The decoder result is also the stream probe; do not launch twice."""
    import analyzer.metrics_audio as audio
    calls = []
    raw = np.array([0, 16384, -16384], dtype=np.int16).tobytes()

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=raw, stderr=b"")

    monkeypatch.setattr(audio, "ffmpeg_exe", lambda: "ffmpeg")
    monkeypatch.setattr(audio.subprocess, "run", fake_run)
    samples = _extract_audio(tmp_path / "episode.mp4")

    assert len(calls) == 1
    assert samples.tolist() == [0.0, 0.5, -0.5]


def test_audio_decode_recognises_a_missing_stream(monkeypatch, tmp_path):
    import analyzer.metrics_audio as audio

    monkeypatch.setattr(audio, "ffmpeg_exe", lambda: "ffmpeg")
    monkeypatch.setattr(
        audio.subprocess, "run",
        lambda *a, **k: SimpleNamespace(
            returncode=1, stdout=b"",
            stderr=b"Output file #0 does not contain any stream"))

    assert _extract_audio(tmp_path / "silent.mp4") is None
