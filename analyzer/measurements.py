"""
Measurement registry — which tool produces each measurement, and with what
parameters.

CMAT's composite is a lens the researcher configures, not a claim CMAT makes.
That means two axes have to be editable, not one:

  * SCORING parameters (weights, normalization ceilings) — cheap. They are
    applied to already-computed raw metrics, so changing them re-scores the
    whole library instantly from cache.
  * MEASUREMENT parameters (which detector, what threshold, what sample rate)
    — expensive. They change the raw numbers themselves, so every cached
    episode measured under the old settings is STALE and must be re-analyzed.

Conflating the two would let a user change a detector threshold and see scores
that mix old detections with a new config label. This module keeps them
separate and gives the measurement side a fingerprint so staleness is
detectable rather than silent.

Structure:  MeasurementSpec (what is measured)
              -> ToolSpec    (which implementation produces it)
                   -> ParamSpec (that tool's tunable parameters)

Config shape produced/consumed (config.json):

    "measurements": {
      "transitions": {"tool": "pyscenedetect_content",
                      "params": {"threshold": 27.0}},
      "dissolves":   {"enabled": false, "tool": "cmat_plateau",
                      "params": {...}},
      ...
    }

Legacy flat keys (cut_detection_threshold, sample_fps, ...) remain in the
config and are kept in sync by normalize_config(), so older call sites and
saved configs keep working. The measurements block is authoritative.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


# --- status flags -----------------------------------------------------------
# Surfaced in the editor and in result provenance. The roadmap guardrail is
# that unvalidated components must be visibly flagged wherever they are used.
VALIDATED = "validated"        # measured against hand coding, error published
EXPERIMENTAL = "experimental"  # implemented, measured, known to perform poorly
UNVALIDATED = "unvalidated"    # implemented, never graded against ground truth

STATUS_LABEL = {
    VALIDATED: "validated",
    EXPERIMENTAL: "experimental",
    UNVALIDATED: "unvalidated",
}


@dataclass(frozen=True)
class ParamSpec:
    key: str
    label: str
    kind: str                     # "float" | "int" | "bool" | "choice"
    default: Any
    help: str = ""
    minimum: float | None = None
    maximum: float | None = None
    unit: str = ""
    advanced: bool = True         # advanced params live behind a disclosure
    choices: list[tuple[str, str]] = field(default_factory=list)  # (value, label)

    def coerce(self, raw: Any) -> Any:
        """Parse a UI string into the declared type, clamped to any bounds."""
        if self.kind == "bool":
            if isinstance(raw, str):
                return raw.strip().lower() in ("1", "true", "yes", "on")
            return bool(raw)
        if self.kind == "choice":
            valid = [v for v, _ in self.choices]
            return raw if raw in valid else self.default
        value = int(float(raw)) if self.kind == "int" else float(raw)
        if self.minimum is not None:
            value = max(value, self.minimum)
        if self.maximum is not None:
            value = min(value, self.maximum)
        return int(value) if self.kind == "int" else float(value)


@dataclass(frozen=True)
class ToolSpec:
    key: str
    name: str
    summary: str
    status: str = UNVALIDATED
    params: list[ParamSpec] = field(default_factory=list)
    optional_tool_key: str | None = None   # -> analyzer.optional_tools registry
    notes: str = ""

    def is_available(self) -> bool:
        """False only when the tool needs an optional dependency that is absent."""
        if not self.optional_tool_key:
            return True
        from .optional_tools import get_tool
        tool = get_tool(self.optional_tool_key)
        return bool(tool and tool.is_available())

    def defaults(self) -> dict[str, Any]:
        return {p.key: p.default for p in self.params}


@dataclass(frozen=True)
class MeasurementSpec:
    key: str
    name: str
    description: str
    tools: list[ToolSpec]
    feeds: str = ""              # composite component this contributes to
    can_disable: bool = False
    default_enabled: bool = True

    def tool(self, key: str) -> ToolSpec | None:
        for t in self.tools:
            if t.key == key:
                return t
        return None

    def default_tool(self) -> ToolSpec:
        return self.tools[0]


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

TRANSITIONS = MeasurementSpec(
    key="transitions",
    name="Shot transitions",
    description=(
        "Where one shot ends and the next begins. Drives cuts/min, shot length, "
        "and the pacing timeline — the most consequential measurement in CMAT, "
        "and the one the literature argues about most."
    ),
    feeds="pacing",
    tools=[
        ToolSpec(
            key="pyscenedetect_content",
            name="PySceneDetect — ContentDetector",
            summary=(
                "Frame-differencing on HSV. Fast, no extra dependencies, and the "
                "detector CMAT's published accuracy figures were measured with."
            ),
            status=VALIDATED,
            notes=(
                "Boundary-detection F1 0.75–0.91 against hand coding, depending on "
                "production style. Misses gradual transitions (dissolves) by "
                "construction: it cannot separate two shots blending from one shot "
                "panning."
            ),
            params=[
                ParamSpec(
                    key="threshold", label="Detection threshold", kind="float",
                    default=27.0, minimum=1.0, maximum=100.0, advanced=False,
                    help=(
                        "Content-change score a frame must exceed to count as a cut. "
                        "LOWER finds more cuts (more false alarms on pans and zooms); "
                        "HIGHER finds fewer (more misses on low-contrast cuts). "
                        "27.0 is the PySceneDetect default and CMAT's validated value."
                    ),
                ),
            ],
        ),
        ToolSpec(
            key="pyscenedetect_adaptive",
            name="PySceneDetect — AdaptiveDetector",
            summary=(
                "Frame-differencing scored against a rolling local average rather "
                "than a fixed threshold. Intended to be steadier under sustained "
                "camera motion."
            ),
            status=UNVALIDATED,
            notes=(
                "Not yet graded against CMAT's hand-coded episodes. Plausibly better "
                "on content with constant motion (the snowfall failure mode), but "
                "that is a hypothesis, not a result — grade it in the Validation tab "
                "before using it for anything you intend to report."
            ),
            params=[
                ParamSpec(
                    key="adaptive_threshold", label="Adaptive threshold", kind="float",
                    default=3.0, minimum=0.5, maximum=20.0, advanced=False,
                    help=(
                        "How far above the rolling local average a frame must score "
                        "to count as a cut. Lower = more sensitive."
                    ),
                ),
                ParamSpec(
                    key="min_scene_len", label="Minimum shot length", kind="int",
                    default=15, minimum=1, maximum=300, unit="frames",
                    help=(
                        "Shortest allowed gap between two cuts, in frames. Suppresses "
                        "double-firing on a single transition."
                    ),
                ),
                ParamSpec(
                    key="window_width", label="Rolling window", kind="int",
                    default=2, minimum=1, maximum=10, unit="frames",
                    help="Frames on each side used to compute the local average.",
                ),
            ],
        ),
        ToolSpec(
            key="transnetv2",
            name="TransNetV2 (neural)",
            summary=(
                "Neural shot-boundary detector trained with dissolves as roughly "
                "half its examples. Catches gradual transitions that "
                "frame-differencing structurally cannot."
            ),
            status=EXPERIMENTAL,
            optional_tool_key="transnetv2",
            notes=(
                "On CMAT's coded episodes it found 8/8 dissolves (built-in pass: "
                "1/8) and raised boundary F1 to 0.90–0.94. It also finds ~5–7% more "
                "transitions overall, so mixing it with ContentDetector results in "
                "one corpus makes pacing incomparable across shows — migrate all or "
                "none. Published benchmarks are live-action; animation is outside "
                "its training distribution."
            ),
            params=[
                ParamSpec(
                    key="threshold", label="Transition probability", kind="float",
                    default=0.5, minimum=0.05, maximum=0.95, advanced=False,
                    help=(
                        "Per-frame probability above which a transition is declared. "
                        "0.5 is the model default. Lower catches more gradual "
                        "transitions at the cost of precision."
                    ),
                ),
            ],
        ),
    ],
)

DISSOLVES = MeasurementSpec(
    key="dissolves",
    name="Dissolves / gradual transitions",
    description=(
        "Transitions where two shots blend over many frames rather than switching "
        "in one frame. Reported as a separate rate; not folded into the composite."
    ),
    feeds="",
    can_disable=True,
    default_enabled=False,
    tools=[
        ToolSpec(
            key="cmat_plateau",
            name="CMAT plateau pass",
            summary=(
                "Second pass over frame scores looking for sustained moderate-change "
                "runs that sit below the hard-cut threshold."
            ),
            status=EXPERIMENTAL,
            notes=(
                "Measured F1 ≈ 0.17 against hand coding — it finds roughly one "
                "dissolve in eight. The signal exists but is not separable from "
                "camera motion by frame-differencing alone. Do not report these "
                "numbers as a dissolve rate. If you need dissolves, use TransNetV2 "
                "for transitions instead."
            ),
            params=[
                ParamSpec(
                    key="noise_floor", label="Noise floor", kind="float",
                    default=3.0, minimum=0.5, maximum=27.0, advanced=False,
                    help=(
                        "Minimum content score for a frame to be considered part of a "
                        "dissolve. Below this is treated as a static shot."
                    ),
                ),
                ParamSpec(
                    key="min_frames", label="Minimum duration", kind="int",
                    default=15, minimum=2, maximum=200, unit="frames",
                    help=(
                        "Consecutive qualifying frames required before a run is called "
                        "a dissolve. At 25fps, 15 frames ≈ 0.6s."
                    ),
                ),
            ],
        ),
    ],
)

SCENE_RELATION = MeasurementSpec(
    key="scene_relation",
    name="Cut classification (within-scene vs scene change)",
    description=(
        "Labels each cut as staying inside one scene (shot-reverse-shot) or "
        "relocating to a new one. Motivated by Lang's related vs unrelated cuts: "
        "raw cuts/min conflates a cheap cut with an expensive one."
    ),
    feeds="",
    can_disable=True,
    default_enabled=True,
    tools=[
        ToolSpec(
            key="frame_similarity",
            name="Frame-similarity comparison",
            summary=(
                "Compares a frame shortly before the cut with one shortly after; "
                "high similarity means the viewer is still in the same place."
            ),
            status=UNVALIDATED,
            notes=(
                "The similarity threshold has never been calibrated against "
                "hand-coded scene relations. Known bias: close-up reverse shots "
                "score low and get mislabeled as scene changes, deflating "
                "within-scene counts. Exploratory only — do not fold into the "
                "composite until tuned."
            ),
            params=[
                ParamSpec(
                    key="similarity_threshold", label="Similarity threshold",
                    kind="float", default=0.55, minimum=0.05, maximum=0.95,
                    advanced=False,
                    help=(
                        "Similarity at or above this = within_scene; below = "
                        "scene_change. Raising it labels more cuts as scene changes."
                    ),
                ),
                ParamSpec(
                    key="offset_sec", label="Comparison offset", kind="float",
                    default=1.0, minimum=0.15, maximum=5.0, unit="sec",
                    help=(
                        "How far either side of the cut to sample the comparison "
                        "frames. Automatically clamped to stay inside the adjacent "
                        "shots on short cuts."
                    ),
                ),
            ],
        ),
    ],
)

SAMPLING = MeasurementSpec(
    key="sampling",
    name="Frame sampling",
    description=(
        "How often frames are decoded for the color and motion pass. One shared "
        "pass feeds both, so this rate applies to saturation, contrast, and motion "
        "together — they cannot be sampled independently."
    ),
    feeds="saturation, contrast, motion",
    tools=[
        ToolSpec(
            key="uniform",
            name="Uniform sampling",
            summary="Decode every Nth frame at a fixed rate across the episode.",
            status=VALIDATED,
            params=[
                ParamSpec(
                    key="sample_fps", label="Sample rate", kind="float",
                    default=2.0, minimum=0.25, maximum=30.0, unit="fps",
                    advanced=False,
                    help=(
                        "Frames decoded per second of video. Higher is more faithful "
                        "and proportionally slower. 2 fps is CMAT's default and the "
                        "rate its published color/motion figures use — changing it "
                        "shifts motion values, since motion is the difference between "
                        "CONSECUTIVE SAMPLED frames and therefore depends on the gap "
                        "between them."
                    ),
                ),
            ],
        ),
    ],
)

MOTION = MeasurementSpec(
    key="motion",
    name="Motion",
    description=(
        "How much the image changes between sampled frames. A pre-attentive "
        "bottom-up attention magnet (Itti & Koch)."
    ),
    feeds="motion",
    tools=[
        ToolSpec(
            key="absdiff",
            name="Frame differencing",
            summary=(
                "Mean absolute grayscale difference between consecutive sampled "
                "frames. Fast; the default."
            ),
            status=VALIDATED,
            notes=(
                "Cannot distinguish object motion from camera motion from a cut. "
                "Values depend on the sampling rate set under Frame sampling."
            ),
        ),
        ToolSpec(
            key="farneback",
            name="Farneback optical flow",
            summary=(
                "Dense optical flow — estimates actual pixel displacement rather "
                "than raw difference, so it separates movement from brightness change."
            ),
            status=UNVALIDATED,
            notes=(
                "Substantially slower than frame differencing and never graded "
                "against hand coding. Its output is normalized against an assumed "
                "~20px maximum displacement, which is a guess, not a calibration — "
                "values are NOT comparable with frame-differencing values."
            ),
        ),
    ],
)

FLASHING = MeasurementSpec(
    key="flashing",
    name="Flashing",
    description=(
        "Abrupt luminance changes between frames. The metric with the clearest "
        "safety rationale (photosensitive-epilepsy guidance)."
    ),
    feeds="flashing",
    tools=[
        ToolSpec(
            key="luminance_delta",
            name="Luminance delta",
            summary=(
                "Counts frame-to-frame jumps in mean brightness that exceed a "
                "threshold, reported per minute."
            ),
            status=UNVALIDATED,
            notes=(
                "Whole-frame mean luminance, so a flash confined to part of the "
                "screen is diluted. Broadcast photosensitivity guidance is specified "
                "on area and red-flash criteria this measure does not implement — "
                "treat it as a relative indicator, not a safety certification."
            ),
            params=[
                ParamSpec(
                    key="threshold", label="Luminance jump threshold", kind="float",
                    default=0.1, minimum=0.01, maximum=0.9, advanced=False,
                    help=(
                        "Change in mean brightness (0–1 scale) between sampled frames "
                        "that counts as a flash event. Lower = more sensitive. "
                        "Researchers studying photosensitivity typically want this "
                        "lower than the default."
                    ),
                ),
                ParamSpec(
                    key="sample_fps", label="Flashing sample rate", kind="float",
                    default=10.0, minimum=1.0, maximum=60.0, unit="fps",
                    advanced=False,
                    help=(
                        "Dedicated higher-rate pass for flashing only. Flashes are "
                        "brief, so the 2fps color/motion rate misses most of them. "
                        "Must exceed the frame sampling rate to take effect. Note "
                        "that a rate change makes flashing values incomparable with "
                        "episodes measured at another rate."
                    ),
                ),
            ],
        ),
    ],
)

COLOR = MeasurementSpec(
    key="color",
    name="Color saturation & contrast",
    description=(
        "Mean HSV saturation and the spatial spread of luminance per frame, "
        "averaged over the episode."
    ),
    feeds="saturation, contrast",
    tools=[
        ToolSpec(
            key="hsv_mean",
            name="HSV mean",
            summary="Mean S channel and standard deviation of the V channel.",
            status=VALIDATED,
            notes=(
                "Uses the frame sampling rate set under Frame sampling. Saturation "
                "is unreliable on blown-out live-action production styles — the "
                "Live-Action preset near-zeroes its weight for that reason."
            ),
        ),
    ],
)

AUDIO = MeasurementSpec(
    key="audio",
    name="Audio loudness",
    description="RMS loudness and dynamic range, extracted with FFmpeg.",
    feeds="audio",
    tools=[
        ToolSpec(
            key="ffmpeg_rms",
            name="FFmpeg RMS",
            summary="Windowed RMS loudness, peak, and peak-to-mean dynamic range.",
            status=VALIDATED,
            notes=(
                "Linear RMS, not a perceptual loudness standard (not LUFS/EBU R128). "
                "When no audio track or no FFmpeg is present, the audio weight is "
                "redistributed across the visual metrics and the result is flagged."
            ),
        ),
    ],
)

SPEECH = MeasurementSpec(
    key="speech",
    name="Speech",
    description=(
        "Words per minute and speech density. Caption files are used when present; "
        "Whisper transcribes only when they are absent."
    ),
    feeds="",
    can_disable=True,
    # Captions are parsed whenever a .srt/.vtt is present, so the measurement is
    # on by default; the legacy speech_transcription_enabled flag chose the TOOL
    # (whether to fall back to Whisper), not whether speech ran at all.
    default_enabled=True,
    tools=[
        ToolSpec(
            key="captions_only",
            name="Caption files only",
            summary=(
                "Parse .srt/.vtt sitting next to the video. Instant, exact, and "
                "skips the episode entirely when no caption file exists."
            ),
            status=VALIDATED,
        ),
        ToolSpec(
            key="captions_then_whisper",
            name="Captions, else Whisper",
            summary=(
                "Use a caption file when present; otherwise transcribe with Whisper "
                "(~2–5 min per episode on CPU)."
            ),
            status=UNVALIDATED,
            notes=(
                "Whisper word counts have not been graded against captions on this "
                "corpus. For words-per-minute, occasional word errors matter little, "
                "so tiny/base is usually sufficient. English-only downstream "
                "language metrics."
            ),
            params=[
                ParamSpec(
                    key="model", label="Whisper model", kind="choice",
                    default="base", advanced=False,
                    choices=[
                        ("tiny", "tiny — fastest"),
                        ("base", "base — balanced"),
                        ("small", "small"),
                        ("medium", "medium"),
                        ("large", "large — most accurate, slowest"),
                    ],
                    help=(
                        "Larger models mainly improve transcript readability, not "
                        "word-count accuracy."
                    ),
                ),
            ],
        ),
    ],
)


MEASUREMENTS: list[MeasurementSpec] = [
    TRANSITIONS, SAMPLING, MOTION, COLOR, FLASHING, AUDIO,
    DISSOLVES, SCENE_RELATION, SPEECH,
]

# Measurements whose settings change RAW metric values. Editing any of these
# invalidates cached analysis. Everything outside this set (weights,
# normalization ceilings) is re-scorable from cache instantly.
FINGERPRINTED = [m.key for m in MEASUREMENTS]


def ungraded_measurements(cfg: dict[str, Any] | None = None
                          ) -> list[tuple[str, str]]:
    """[(measurement name, why it is flagged)] for anything not validated.

    The single answer to "which numbers on this screen need a flag".
    `CLAUDE.md` §2.2 requires unvalidated measures to be flagged WHEREVER
    their numbers appear — the report, the index table, the comparison, the
    chart, the exports and the published site. Each of those used to decide
    for itself, and most of them decided "not at all".

    With *cfg* the answer reflects the tools actually selected; without it,
    the shipped defaults.
    """
    out: list[tuple[str, str]] = []
    for measurement in MEASUREMENTS:
        if cfg is not None:
            tool, _params, enabled = selection(cfg, measurement.key)
            if measurement.can_disable and not enabled:
                continue
        else:
            tool = measurement.default_tool()
        if tool.status == VALIDATED:
            continue
        out.append((
            measurement.name,
            f"{tool.name} is {STATUS_LABEL.get(tool.status, tool.status)} — "
            f"never graded against hand coding",
        ))
    return out


def get_measurement(key: str) -> MeasurementSpec | None:
    for m in MEASUREMENTS:
        if m.key == key:
            return m
    return None


# ---------------------------------------------------------------------------
# Config normalization / migration
# ---------------------------------------------------------------------------

def default_measurements() -> dict[str, Any]:
    """The measurements block as it would be with every default selected."""
    out: dict[str, Any] = {}
    for m in MEASUREMENTS:
        tool = m.default_tool()
        entry: dict[str, Any] = {"tool": tool.key, "params": tool.defaults()}
        if m.can_disable:
            entry["enabled"] = m.default_enabled
        out[m.key] = entry
    return out


# Legacy flat config keys -> (measurement key, param key). Kept so old
# config.json files migrate cleanly and older call sites keep reading the
# values they expect.
_LEGACY_MAP: list[tuple[str, str, str]] = [
    ("cut_detection_threshold",           "transitions",    "threshold"),
    ("sample_fps",                        "sampling",       "sample_fps"),
    ("flashing_luminance_threshold",      "flashing",       "threshold"),
    ("flashing_sample_fps",               "flashing",       "sample_fps"),
    ("dissolve_noise_floor",              "dissolves",      "noise_floor"),
    ("dissolve_min_frames",               "dissolves",      "min_frames"),
    ("cut_classification_offset_sec",     "scene_relation", "offset_sec"),
    ("scene_change_similarity_threshold", "scene_relation", "similarity_threshold"),
    ("speech_whisper_model",              "speech",         "model"),
]

# speech_transcription_enabled is deliberately absent: it selects the speech
# TOOL (captions-only vs captions-then-Whisper), not whether speech runs.
_LEGACY_ENABLED: list[tuple[str, str]] = [
    ("dissolve_detection_enabled",   "dissolves"),
    ("cut_classification_enabled",   "scene_relation"),
]


def normalize_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Ensure cfg has a complete, valid measurements block; keep legacy keys in sync.

    Migration rules:
      * No measurements block  -> build one from the legacy flat keys.
      * Measurements present   -> it wins; legacy flat keys are re-derived from it.
      * Unknown tools or params are dropped; missing ones get defaults.

    Mutates and returns cfg (callers pass a config they already own).
    """
    incoming = cfg.get("measurements")
    had_block = isinstance(incoming, dict)
    block = default_measurements()

    if not had_block:
        # Migrate: legacy flat keys seed the new block.
        for flat_key, m_key, p_key in _LEGACY_MAP:
            if flat_key in cfg and p_key in block[m_key]["params"]:
                spec = get_measurement(m_key)
                tool = spec.tool(block[m_key]["tool"]) if spec else None
                pspec = next((p for p in tool.params if p.key == p_key), None) if tool else None
                if pspec is not None:
                    try:
                        block[m_key]["params"][p_key] = pspec.coerce(cfg[flat_key])
                    except (TypeError, ValueError):
                        pass
        for flat_key, m_key in _LEGACY_ENABLED:
            if flat_key in cfg and "enabled" in block[m_key]:
                block[m_key]["enabled"] = bool(cfg[flat_key])
        # Legacy speech: the enabled flag chose between captions-only and Whisper.
        if cfg.get("speech_transcription_enabled"):
            block["speech"]["tool"] = "captions_then_whisper"
            model = cfg.get("speech_whisper_model")
            if model:
                block["speech"]["params"]["model"] = model
    else:
        for m in MEASUREMENTS:
            given = incoming.get(m.key)
            if not isinstance(given, dict):
                continue
            tool = m.tool(given.get("tool", "")) or m.default_tool()
            block[m.key]["tool"] = tool.key
            params = tool.defaults()
            given_params = given.get("params")
            if isinstance(given_params, dict):
                for p in tool.params:
                    if p.key in given_params:
                        try:
                            params[p.key] = p.coerce(given_params[p.key])
                        except (TypeError, ValueError):
                            pass
            block[m.key]["params"] = params
            if m.can_disable and "enabled" in given:
                block[m.key]["enabled"] = bool(given["enabled"])

    cfg["measurements"] = block

    # Re-derive legacy flat keys so anything still reading them stays correct.
    for flat_key, m_key, p_key in _LEGACY_MAP:
        params = block[m_key]["params"]
        if p_key in params:
            cfg[flat_key] = params[p_key]
    for flat_key, m_key in _LEGACY_ENABLED:
        if "enabled" in block[m_key]:
            cfg[flat_key] = block[m_key]["enabled"]
    # Speech is a tool choice in the new model; the legacy flag is derived.
    cfg["speech_transcription_enabled"] = (
        block["speech"].get("enabled", False)
        and block["speech"]["tool"] == "captions_then_whisper"
    )
    if "model" in block["speech"]["params"]:
        cfg["speech_whisper_model"] = block["speech"]["params"]["model"]

    return cfg


def selection(cfg: dict[str, Any], measurement_key: str) -> tuple[ToolSpec, dict[str, Any], bool]:
    """Return (tool, params, enabled) for a measurement, normalizing if needed."""
    spec = get_measurement(measurement_key)
    if spec is None:
        raise KeyError(f"Unknown measurement: {measurement_key}")
    block = cfg.get("measurements")
    if not isinstance(block, dict) or measurement_key not in block:
        cfg = normalize_config(dict(cfg))
        block = cfg["measurements"]
    entry = block[measurement_key]
    tool = spec.tool(entry.get("tool", "")) or spec.default_tool()
    params = dict(tool.defaults())
    params.update({k: v for k, v in entry.get("params", {}).items() if k in params})
    enabled = bool(entry.get("enabled", True)) if spec.can_disable else True
    return tool, params, enabled


# ---------------------------------------------------------------------------
# Fingerprint — cache identity for measurement settings
# ---------------------------------------------------------------------------

def fingerprint_payload(cfg: dict[str, Any]) -> dict[str, Any]:
    """The canonical subset of config that determines RAW metric values.

    Weights and normalization ranges are deliberately excluded: they are
    re-scorable from cached metrics, so changing them must not mark anything
    stale. Disabled measurements contribute only their disabled state, so
    fiddling with a switched-off measurement's parameters is not a change.
    """
    payload: dict[str, Any] = {}
    for m in MEASUREMENTS:
        tool, params, enabled = selection(cfg, m.key)
        if m.can_disable and not enabled:
            payload[m.key] = {"enabled": False}
            continue
        payload[m.key] = {"tool": tool.key, "params": params}
    return payload


def measurement_fingerprint(cfg: dict[str, Any]) -> str:
    """Short stable hash of the measurement settings that produced a result."""
    canonical = json.dumps(fingerprint_payload(cfg), sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def describe_selection(cfg: dict[str, Any]) -> dict[str, str]:
    """Human-readable 'measurement -> tool (status)' map for provenance output."""
    out: dict[str, str] = {}
    for m in MEASUREMENTS:
        tool, _params, enabled = selection(cfg, m.key)
        if m.can_disable and not enabled:
            out[m.key] = "disabled"
        else:
            out[m.key] = f"{tool.name} [{STATUS_LABEL.get(tool.status, tool.status)}]"
    return out


def diff_fingerprints(old_cfg: dict[str, Any], new_cfg: dict[str, Any]) -> list[str]:
    """Human-readable list of measurement changes between two configs.

    Used to tell the user exactly what makes their cache stale, rather than
    just asserting that it is.
    """
    changes: list[str] = []
    old = fingerprint_payload(old_cfg)
    new = fingerprint_payload(new_cfg)
    for m in MEASUREMENTS:
        o, n = old.get(m.key, {}), new.get(m.key, {})
        if o == n:
            continue
        if o.get("enabled") is False and n.get("enabled") is not False:
            changes.append(f"{m.name}: enabled")
            continue
        if n.get("enabled") is False and o.get("enabled") is not False:
            changes.append(f"{m.name}: disabled")
            continue
        if o.get("tool") != n.get("tool"):
            spec = get_measurement(m.key)
            o_tool = spec.tool(o.get("tool", "")) if spec else None
            n_tool = spec.tool(n.get("tool", "")) if spec else None
            changes.append(
                f"{m.name}: {o_tool.name if o_tool else o.get('tool')} → "
                f"{n_tool.name if n_tool else n.get('tool')}"
            )
            continue
        for p_key, n_val in (n.get("params") or {}).items():
            o_val = (o.get("params") or {}).get(p_key)
            if o_val != n_val:
                spec = get_measurement(m.key)
                tool = spec.tool(n.get("tool", "")) if spec else None
                pspec = next((p for p in tool.params if p.key == p_key), None) if tool else None
                label = pspec.label if pspec else p_key
                changes.append(f"{m.name} — {label}: {o_val} → {n_val}")
    return changes
