"""
TransNetV2 shot-boundary detector — optional backend for CMAT.

Wraps the `transnetv2-pytorch` package (a community PyTorch port of the original
TransNetV2, both MIT) and returns cut timestamps in the SAME shape as CMAT's
PySceneDetect path, so it can be dropped into the existing detection and
validation flow and graded against hand coding.

Availability is optional by design: every entry point fails with a clear,
actionable message rather than an ImportError traceback when the package is
absent. Nothing in CMAT's validated core depends on this module.

Cite: Souček & Lokoč, "TransNet V2: An effective deep network architecture for
fast shot transition detection." https://github.com/soCzech/TransNetV2
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

# Default probability threshold for calling a frame a transition. 0.5 is the
# package default; lower catches more (including more gradual transitions) at
# the cost of precision. Tunable against hand coding like any other threshold.
DEFAULT_THRESHOLD = 0.5


class TransNetUnavailable(RuntimeError):
    """Raised when the optional dependency is not installed."""


def is_available() -> bool:
    try:
        import transnetv2_pytorch  # noqa: F401
        return True
    except Exception:
        return False


def _require() -> Any:
    try:
        from transnetv2_pytorch import TransNetV2
        return TransNetV2
    except Exception as exc:                        # noqa: BLE001
        raise TransNetUnavailable(
            "TransNetV2 is not installed. Install it from "
            "Tools → Optional tools, or run:\n"
            "    pip install transnetv2-pytorch\n"
            f"(import failed: {exc})"
        ) from exc


_model_cache: dict[str, Any] = {}


def _get_model() -> Any:
    """Load once and reuse — model construction is the expensive part."""
    if "m" not in _model_cache:
        TransNetV2 = _require()
        _model_cache["m"] = TransNetV2()
    return _model_cache["m"]


def detect_cuts(
    video_path: Path,
    threshold: float = DEFAULT_THRESHOLD,
    status_cb: Callable[[str], None] | None = None,
) -> list[float]:
    """Cut timestamps in seconds, matching CMAT's PySceneDetect convention.

    A "cut" is the START of each scene after the first, so a video with N
    scenes yields N-1 cuts — identical to how compute_cut_metrics() derives
    cut_times from PySceneDetect's scene list.
    """
    model = _get_model()
    if status_cb:
        status_cb("Running TransNetV2 (neural shot detection — a few minutes "
                  "on CPU)…")

    scenes = model.detect_scenes(str(video_path), threshold=threshold)

    cut_times: list[float] = []
    for scene in scenes[1:]:                        # scene 0 starts at t=0
        start = _scene_start(scene)
        if start is not None:
            cut_times.append(round(float(start), 3))
    cut_times.sort()
    if status_cb:
        status_cb(f"TransNetV2 found {len(cut_times)} cuts "
                  f"({len(scenes)} scenes).")
    return cut_times


def _scene_start(scene: Any) -> float | None:
    """Pull the start time out of a scene record.

    The package documents dicts with 'start_time', but tolerate tuples/objects
    so a minor upstream change doesn't break detection outright.
    """
    if isinstance(scene, dict):
        for k in ("start_time", "start", "start_sec"):
            if k in scene:
                return scene[k]
        return None
    if isinstance(scene, (tuple, list)) and scene:
        return scene[0]
    for k in ("start_time", "start"):
        if hasattr(scene, k):
            return getattr(scene, k)
    return None


def describe() -> str:
    """Short provenance string for manifests and reports."""
    if not is_available():
        return "TransNetV2 (not installed)"
    try:
        import transnetv2_pytorch as m
        return f"TransNetV2 via transnetv2-pytorch {getattr(m, '__version__', '?')}"
    except Exception:
        return "TransNetV2"
