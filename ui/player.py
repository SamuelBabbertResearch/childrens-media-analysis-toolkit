"""
ui/player.py — the video surface, for hand coding.

VLC rather than QMediaPlayer, deliberately. Coding a transition or an event
means naming the moment it happens, and on Windows QMediaPlayer goes through
Media Foundation, where seeking on an arbitrary MP4 lands on the nearest
keyframe rather than the frame asked for. A coder stepping frame by frame
would be recording the wrong timestamp and would have no way to tell. libvlc
seeks accurately: a seek to 30.0s reports 30.000s exactly, and stepping by one
frame duration lands within a millisecond of the frame boundary.

Note that libvlc's own `next_frame()` is NOT used — see `step_frame()`. It
advances the picture without moving the clock, and corrupts the next seek.

The cost is a real dependency: VLC must be installed, 64-bit to match the
interpreter. `available()` reports that rather than letting the screen fail
halfway through opening a video.

Embedding works because VLC draws into a native window handle. Qt hands one
over through `winId()`, and the surface widget must therefore carry
WA_NativeWindow and WA_DontCreateNativeAncestors — without the second, Qt
promotes ancestors to native windows too and the layout can flicker or lose
its clipping.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QEventLoop, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget,
)


# One libvlc instance for the whole application, built once and silenced.
#
# libvlc writes to stderr directly, and on a VLC whose plugin cache is out of
# date that is one "stale plugins cache" line per plugin — hundreds of lines
# before the window appears. The messages are harmless: VLC notices the cache
# is older than the plugins and rescans. They are also not ours to print, so
# the log is routed to a callback that drops them. The reference to that
# callback is kept alive deliberately: libvlc holds a raw pointer to it, and
# letting Python collect it crashes the process on the next log line.
#
# The instance is cached because `available()` and the player each used to
# build their own, which doubled both the startup cost and the noise.
_instance = None
_log_sink = None


def _libvlc():
    """The shared instance, or None if libvlc will not start."""
    global _instance, _log_sink
    if _instance is not None:
        return _instance
    try:
        import vlc
    except ImportError:
        return None
    try:
        inst = vlc.Instance("--no-video-title-show", "--quiet",
                            "--intf", "dummy")
        if inst is None:
            return None
        try:
            _log_sink = vlc.CallbackDecorators.LogCb(
                lambda data, level, ctx, fmt, args: None)
            inst.log_set(_log_sink, None)
        except Exception:       # noqa: BLE001 - silencing is best-effort
            pass
        _instance = inst
        return _instance
    except Exception:           # noqa: BLE001 - reported by available()
        return None


def available() -> tuple[bool, str]:
    """(usable, explanation). Never raises — the caller shows the reason."""
    try:
        import vlc                          # noqa: F401
    except ImportError:
        return False, ("python-vlc is not installed. Install it with "
                       "`pip install python-vlc`.")
    if _libvlc() is None:
        return False, ("VLC is installed but libvlc would not start. A "
                       "64-bit VLC is needed to match this interpreter.")
    return True, ""


def sec_to_hms(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    frac = int(round((seconds - int(seconds)) * 100))
    return f"{h:02d}:{m:02d}:{s:02d}.{frac:02d}"


class VideoSurface(QWidget):
    """The native window libvlc draws into."""

    def __init__(self) -> None:
        super().__init__()
        self.setAttribute(Qt.WA_NativeWindow, True)
        self.setAttribute(Qt.WA_DontCreateNativeAncestors, True)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(True)
        self.setStyleSheet("background:#000000;")
        self.setMinimumSize(320, 180)


class VideoPlayer(QWidget):
    """Transport controls over a VLC surface, reporting the current time."""

    position_changed = Signal(float)        # seconds

    STEP_SMALL = 1.0
    STEP_LARGE = 10.0

    def __init__(self) -> None:
        super().__init__()
        import vlc

        self._vlc = vlc
        self._instance = _libvlc()
        self._player = self._instance.media_player_new()
        self._duration = 0.0
        self._scrubbing = False
        self._fps = 0.0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self.surface = VideoSurface()
        lay.addWidget(self.surface, 1)

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(0, 1000)
        self._slider.sliderPressed.connect(self._begin_scrub)
        self._slider.sliderReleased.connect(self._end_scrub)
        lay.addWidget(self._slider)

        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)
        self._btn_play = QPushButton("Play")
        self._btn_play.clicked.connect(self.toggle)
        rl.addWidget(self._btn_play)
        for text, delta, tip in (
                ("−10s", -self.STEP_LARGE, "Back ten seconds"),
                ("−1s", -self.STEP_SMALL, "Back one second"),
                ("+1s", self.STEP_SMALL, "Forward one second"),
                ("+10s", self.STEP_LARGE, "Forward ten seconds")):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, d=delta: self.nudge(d))
            rl.addWidget(b)
        self._btn_frame_back = QPushButton("◂ Frame")
        self._btn_frame_back.setToolTip("Back one frame.")
        self._btn_frame_back.clicked.connect(lambda: self.step_frame(-1))
        rl.addWidget(self._btn_frame_back)
        self._btn_frame = QPushButton("Frame ▸")
        self._btn_frame.setToolTip("Forward one frame.")
        self._btn_frame.clicked.connect(lambda: self.step_frame(1))
        rl.addWidget(self._btn_frame)
        rl.addStretch(1)
        self._time = QLabel("00:00:00.00 / 00:00:00.00")
        self._time.setProperty("role", "dim")
        rl.addWidget(self._time)
        lay.addWidget(row)

        self._tick = QTimer(self)
        self._tick.setInterval(100)
        self._tick.timeout.connect(self._sync)
        self._tick.start()

    # -- source -----------------------------------------------------------
    def open(self, path: Path) -> None:
        media = self._instance.media_new(str(path))
        self._player.set_media(media)
        handle = int(self.surface.winId())
        if sys.platform == "win32":
            self._player.set_hwnd(handle)
        elif sys.platform == "darwin":
            self._player.set_nsobject(handle)
        else:
            self._player.set_xwindow(handle)
        media.parse_with_options(self._vlc.MediaParseFlag.local, 0)
        self._player.play()
        # Paused on arrival: a coder wants the first frame held, not the
        # episode running. set_pause(1) rather than pause(), which TOGGLES —
        # and a toggle sent before playback has actually begun does nothing,
        # leaving the video running under a button that says "Pause". Retried
        # because how long libvlc takes to start is not knowable up front.
        self._settle = 0
        QTimer.singleShot(150, self._hold_first_frame)

    def _hold_first_frame(self) -> None:
        self._player.set_pause(1)
        self._settle += 1
        if self._player.is_playing() and self._settle < 20:
            QTimer.singleShot(100, self._hold_first_frame)

    def close(self) -> None:
        self._tick.stop()
        self._player.stop()

    # -- transport --------------------------------------------------------
    def toggle(self) -> None:
        self._player.pause()

    def nudge(self, delta: float) -> None:
        self.seek(self.position() + delta)

    def step_frame(self, frames: int = 1) -> None:
        """Move by whole frames, forward or back.

        Implemented as a seek of one frame duration, NOT libvlc's
        `next_frame()`. Measured, `next_frame()` advances the picture but
        leaves `get_time()` and `get_position()` frozen — three steps from
        30.000s all still reported 30000ms — so a coder stepping to the exact
        frame of a cut would record the timestamp of wherever they paused.

        Worse, it leaves the player in a state where the NEXT seek is applied
        wrongly and never corrects: a seek to 45.0s landed at 40.040s and
        stayed there. Re-asserting pause, seeking twice and set_position all
        failed to clear it.

        Seeking by a frame duration has neither problem: the step lands within
        a millisecond of the frame boundary, the clock follows it, later seeks
        stay exact — and stepping backwards becomes possible, which
        `next_frame()` cannot do at all.
        """
        frame = self.frame_duration()
        if frame <= 0:
            return
        self.seek(self.position() + frames * frame)

    def seek(self, seconds: float) -> None:
        seconds = max(0.0, min(seconds, self._duration or seconds))
        self._player.set_time(int(round(seconds * 1000)))
        self.position_changed.emit(seconds)

    def frame_duration(self) -> float:
        """Seconds per frame, from the media's own rate. 0.0 if unknown."""
        if self._fps <= 0:
            try:
                self._fps = float(self._player.get_fps() or 0.0)
            except Exception:       # noqa: BLE001 - unknown rate is not fatal
                self._fps = 0.0
        return 1.0 / self._fps if self._fps > 0 else 0.0

    def position(self) -> float:
        """The position a mark records.

        Exact when paused or after a seek. During PLAYBACK libvlc's clock is
        coarse — measured, it advances in jumps of 0.25–0.5s on 23.976fps
        material — so a mark made while playing can be up to half a second
        stale. Pause before marking; the coding UI enforces that.
        """
        ms = self._player.get_time()
        return max(0.0, ms / 1000.0) if ms and ms > 0 else 0.0

    # -- state ------------------------------------------------------------
    def _begin_scrub(self) -> None:
        self._scrubbing = True

    def _end_scrub(self) -> None:
        self._scrubbing = False
        if self._duration:
            self.seek(self._slider.value() / 1000.0 * self._duration)

    def _sync(self) -> None:
        length = self._player.get_length()
        if length and length > 0:
            self._duration = length / 1000.0
        pos = self.position()
        if not self._scrubbing and self._duration:
            self._slider.setValue(int(pos / self._duration * 1000))
        self._time.setText(
            f"{sec_to_hms(pos)} / {sec_to_hms(self._duration)}")
        self._btn_play.setText(
            "Pause" if self._player.is_playing() else "Play")
        self.position_changed.emit(pos)
