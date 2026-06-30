"""Output data contract for per-episode and per-show analysis results."""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any
import json


@dataclass
class ShotLengthMetrics:
    mean_sec: float = 0.0
    median_sec: float = 0.0
    shots_per_min: float = 0.0
    count: int = 0


@dataclass
class ScenePacingMetrics:
    cuts_per_min: float = 0.0
    # Coefficient of variation (std/mean) of shot lengths — captures rhythm/burstiness
    shot_length_cv: float = 0.0
    # Rolling cut count sampled every 30 seconds across the episode
    timeline_cuts_per_30s: list[float] = field(default_factory=list)


@dataclass
class ColorSaturationMetrics:
    mean: float = 0.0
    temporal_var: float = 0.0
    contrast_mean: float = 0.0   # spatial std-dev of V channel, averaged across sampled frames


@dataclass
class MotionMetrics:
    mean: float = 0.0
    peak: float = 0.0


@dataclass
class FlashingMetrics:
    luminance_delta_events_per_min: float = 0.0


@dataclass
class AudioMetrics:
    rms_mean: float = 0.0          # mean per-window RMS loudness (linear 0–1)
    rms_peak: float = 0.0          # loudest 1-second window
    rms_temporal_var: float = 0.0  # variance of per-window RMS — captures sudden peaks
    dynamic_range_db: float = 0.0  # peak-to-mean ratio in dB
    available: bool = False        # False when FFmpeg is absent or no audio track


@dataclass
class SpeechMetrics:
    available: bool = False
    source: str = "none"           # "srt" | "vtt" | "whisper" | "none"
    words_per_minute: float = 0.0
    speech_density: float = 0.0    # fraction of episode duration with speech (0.0–1.0)
    total_words: int = 0


@dataclass
class SensoryLoadComponents:
    pacing: float = 0.0
    saturation: float = 0.0
    contrast: float = 0.0
    motion: float = 0.0
    flashing: float = 0.0
    audio: float = 0.0


@dataclass
class SensoryLoadMetrics:
    score: float = 0.0
    audio_available: bool = False
    components: SensoryLoadComponents = field(default_factory=SensoryLoadComponents)


@dataclass
class EpisodeMetrics:
    shot_length: ShotLengthMetrics = field(default_factory=ShotLengthMetrics)
    scene_pacing: ScenePacingMetrics = field(default_factory=ScenePacingMetrics)
    color_saturation: ColorSaturationMetrics = field(default_factory=ColorSaturationMetrics)
    motion: MotionMetrics = field(default_factory=MotionMetrics)
    flashing: FlashingMetrics = field(default_factory=FlashingMetrics)
    audio: AudioMetrics = field(default_factory=AudioMetrics)
    speech: SpeechMetrics = field(default_factory=SpeechMetrics)
    sensory_load: SensoryLoadMetrics = field(default_factory=SensoryLoadMetrics)


@dataclass
class EpisodeResult:
    file: str = ""
    duration_sec: float = 0.0
    status: str = "ok"          # "ok" | "failed"
    error: str = ""             # populated if status == "failed"
    metrics: EpisodeMetrics = field(default_factory=EpisodeMetrics)
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EpisodeResult":
        """Reconstruct an EpisodeResult from a cached JSON dict."""
        m = d.get("metrics", {})
        sl = m.get("shot_length", {})
        sp = m.get("scene_pacing", {})
        cs = m.get("color_saturation", {})
        mo = m.get("motion", {})
        fl = m.get("flashing", {})
        au = m.get("audio", {})
        spe = m.get("speech", {})
        sn = m.get("sensory_load", {})
        sc = sn.get("components", {})
        return cls(
            file=d.get("file", ""),
            duration_sec=d.get("duration_sec", 0.0),
            status=d.get("status", "ok"),
            error=d.get("error", ""),
            config=d.get("config", {}),
            metrics=EpisodeMetrics(
                shot_length=ShotLengthMetrics(**sl) if sl else ShotLengthMetrics(),
                scene_pacing=ScenePacingMetrics(**sp) if sp else ScenePacingMetrics(),
                color_saturation=ColorSaturationMetrics(
                    mean=cs.get("mean", 0.0),
                    temporal_var=cs.get("temporal_var", 0.0),
                    contrast_mean=cs.get("contrast_mean", 0.0),
                ) if cs else ColorSaturationMetrics(),
                motion=MotionMetrics(**mo) if mo else MotionMetrics(),
                flashing=FlashingMetrics(**fl) if fl else FlashingMetrics(),
                audio=AudioMetrics(**au) if au else AudioMetrics(),
                speech=SpeechMetrics(
                    available=spe.get("available", False),
                    source=spe.get("source", "none"),
                    words_per_minute=spe.get("words_per_minute", 0.0),
                    speech_density=spe.get("speech_density", 0.0),
                    total_words=spe.get("total_words", 0),
                ) if spe else SpeechMetrics(),
                sensory_load=SensoryLoadMetrics(
                    score=sn.get("score", 0.0),
                    audio_available=sn.get("audio_available", False),
                    components=SensoryLoadComponents(
                        pacing=sc.get("pacing", 0.0),
                        saturation=sc.get("saturation", 0.0),
                        contrast=sc.get("contrast", 0.0),
                        motion=sc.get("motion", 0.0),
                        flashing=sc.get("flashing", 0.0),
                        audio=sc.get("audio", 0.0),
                    ) if sc else SensoryLoadComponents(),
                ),
            ),
        )


# ---------------------------------------------------------------------------
# Show-level aggregate schema
# ---------------------------------------------------------------------------

@dataclass
class MetricStats:
    """Summary statistics for one metric across all episodes in a show."""
    mean: float = 0.0
    median: float = 0.0
    std: float = 0.0
    min: float = 0.0
    max: float = 0.0


@dataclass
class ShowAggregate:
    show_name: str = ""
    episode_count: int = 0
    failed_count: int = 0
    shot_length_mean_sec: MetricStats = field(default_factory=MetricStats)
    cuts_per_min: MetricStats = field(default_factory=MetricStats)
    color_saturation_mean: MetricStats = field(default_factory=MetricStats)
    color_contrast_mean: MetricStats = field(default_factory=MetricStats)
    motion_mean: MetricStats = field(default_factory=MetricStats)
    flashing_events_per_min: MetricStats = field(default_factory=MetricStats)
    audio_rms_mean: MetricStats = field(default_factory=MetricStats)
    sensory_load_score: MetricStats = field(default_factory=MetricStats)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
