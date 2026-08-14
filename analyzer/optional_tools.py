"""
Optional tools registry — heavyweight or third-party components researchers can
add to CMAT if their work needs them, without bloating the base install.

The pattern: CMAT ships a small, self-contained core; anything large (deep
learning runtimes, model weights) is opt-in, clearly explained before install,
and degrades gracefully when absent. Nothing here is required for CMAT's
validated measurements.

Add a tool by appending an OptionalTool to OPTIONAL_TOOLS. Availability is
probed by INSTALLATION, not by import, so a tool the user installed by hand is
picked up too — and probing costs nothing.

WHY PRESENCE RATHER THAN IMPORT
-------------------------------
`is_available()` used to call `import_module()`. That is the strictest check —
it proves the package actually loads — but for TransNetV2 it imports PyTorch,
which takes **3.6 seconds** and pulls a deep-learning runtime into the process.
The interface asks this question to decide whether to grey out a combo-box
entry, and it asked it once per tool while building a settings dialog, so
opening Measurement settings froze for four seconds.

`find_spec` answers "is this installed" without executing anything. The cost is
that a package present but broken now reads as available; when it is actually
used the engine raises the real import error, which is a better place to
discover a broken install than a greyed-out menu item anyway.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class OptionalTool:
    key: str
    name: str
    one_liner: str
    pip_package: str          # what `pip install` receives
    import_name: str          # module probed to detect availability
    docs_url: str
    license: str
    what_it_does: str
    benefits: list[str] = field(default_factory=list)
    costs: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    disk_estimate: str = ""

    def is_available(self) -> bool:
        """True when the package is installed. Does not import it."""
        try:
            return importlib.util.find_spec(self.import_name) is not None
        except (ImportError, ValueError):
            # A missing parent package raises rather than returning None.
            return False

    def version(self) -> str:
        """The installed version, read from package metadata, not by import."""
        try:
            return importlib.metadata.version(self.pip_package)
        except Exception:
            return "installed" if self.is_available() else ""


TRANSNETV2 = OptionalTool(
    key="transnetv2",
    name="TransNetV2 shot-boundary detector",
    one_liner="Neural shot-transition detector — built to catch dissolves and "
              "other gradual transitions that frame-differencing misses.",
    pip_package="transnetv2-pytorch",
    import_name="transnetv2_pytorch",
    docs_url="https://github.com/soCzech/TransNetV2",
    license="MIT",
    what_it_does=(
        "CMAT's built-in detector (PySceneDetect ContentDetector) finds a cut by "
        "measuring how much consecutive frames differ. That works well for hard "
        "cuts but structurally cannot separate a DISSOLVE (two shots blending) "
        "from a CAMERA PAN (one shot translating) — both produce sustained, "
        "moderate frame change.\n\n"
        "TransNetV2 is a small neural network trained specifically on shot "
        "transitions, with roughly half its training examples being dissolves of "
        "varying length. It reads a window of frames and predicts, per frame, "
        "whether a transition is underway — so it can use cues frame-differencing "
        "throws away."
    ),
    benefits=[
        "Detects gradual transitions (dissolves, fades) that CMAT's built-in "
        "detector largely misses — CMAT's dissolve pass is experimental and "
        "measured F1 ≈ 0.17 in validation.",
        "Should reduce false positives from camera pans and zooms, which are the "
        "dominant error in CMAT's own error taxonomy.",
        "Authors report F1 96.2 (BBC Planet Earth), 93.9 (RAI), 77.9 (ClipShots).",
        "Becomes selectable anywhere CMAT lets you choose a detector, so you can "
        "grade it against your own hand coding and see if it actually helps.",
    ],
    costs=[
        "Installs PyTorch, a large dependency (roughly 2 GB on disk).",
        "Slower than the built-in detector: expect a few minutes per episode on "
        "CPU rather than under a minute.",
        "Not bundled in the packaged CMAT release — this is an opt-in download.",
    ],
    caveats=[
        "`transnetv2-pytorch` is a community PyTorch port of the original "
        "TensorFlow model (both MIT licensed); its author states it reproduces "
        "the original's results. Cite the original TransNetV2 paper, not the port.",
        "Published benchmarks are on live-action video. ANIMATION is outside its "
        "training distribution, so its accuracy on cartoons is unverified — "
        "measure it on your own coded episodes before trusting it.",
        "It replaces the transition DETECTOR only. It does not change any other "
        "CMAT metric, and it is not part of CMAT's validated core.",
    ],
    disk_estimate="~2 GB (mostly PyTorch)",
)


OPTIONAL_TOOLS: list[OptionalTool] = [TRANSNETV2]


def get_tool(key: str) -> OptionalTool | None:
    for t in OPTIONAL_TOOLS:
        if t.key == key:
            return t
    return None


def install_command(tool: OptionalTool) -> list[str]:
    """The exact command CMAT would run — shown to the user before running."""
    return [sys.executable, "-m", "pip", "install", tool.pip_package]


def install_tool(
    tool: OptionalTool,
    line_cb: Callable[[str], None] | None = None,
) -> bool:
    """Run the pip install, streaming output. Blocking — call on a worker thread."""
    cmd = install_command(tool)
    if line_cb:
        line_cb("$ " + " ".join(cmd))
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
    except Exception as exc:                       # noqa: BLE001
        if line_cb:
            line_cb(f"Failed to start pip: {exc}")
        return False
    assert proc.stdout is not None
    for line in proc.stdout:
        if line_cb:
            line_cb(line.rstrip())
    proc.wait()
    ok = proc.returncode == 0
    if line_cb:
        line_cb("" if ok else f"pip exited with code {proc.returncode}")
    return ok
