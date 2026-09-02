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

The cost is a native dependency: source runs need 64-bit VLC to match the
interpreter. Frozen Windows releases carry a private VLC runtime and plugins;
`available()` reports a loading problem rather than letting the screen fail
halfway through opening a video.

Embedding works because VLC draws into a native window handle. Qt hands one
over through `winId()`, and the surface widget must therefore carry
WA_NativeWindow and WA_DontCreateNativeAncestors — without the second, Qt
promotes ancestors to native windows too and the layout can flicker or lose
its clipping.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QEventLoop, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from ui import theme
from ui.tokens import color


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
_dll_directory = None


def _prepare_bundled_vlc() -> None:
    """Point python-vlc at the private runtime shipped by PyInstaller."""
    global _dll_directory
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    vlc_dir = bundle_root / "vlc"
    library = vlc_dir / "libvlc.dll"
    plugins = vlc_dir / "plugins"
    if not library.is_file() or not plugins.is_dir():
        return
    os.environ.setdefault("PYTHON_VLC_LIB_PATH", str(library))
    os.environ.setdefault("PYTHON_VLC_MODULE_PATH", str(vlc_dir))
    os.environ.setdefault("VLC_PLUGIN_PATH", str(plugins))
    if sys.platform.startswith("win") and hasattr(os, "add_dll_directory"):
        # The handle must stay alive while libvlc loads libvlccore and plugins.
        _dll_directory = os.add_dll_directory(str(vlc_dir))


def _libvlc():
    """The shared instance, or None if libvlc will not start."""
    global _instance, _log_sink
    if _instance is not None:
        return _instance
    _prepare_bundled_vlc()
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
        return False, ("libVLC would not start. Source runs need a 64-bit VLC "
                       "installation; packaged releases include one.")
    return True, ""


def sec_to_hms(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    frac = int(round((seconds - int(seconds)) * 100))
    return f"{h:02d}:{m:02d}:{s:02d}.{frac:02d}"


class VideoSurface(QWidget):
    """The native window libvlc draws into.

    `WA_OpaquePaintEvent` promises Qt that this widget paints every one of its
    pixels, so Qt skips erasing the background. libvlc keeps that promise while
    a video is loaded. **Before one is**, nothing painted here at all, and the
    pixels of whatever was previously on screen survived underneath — the
    Trials tab's list showed through the coding screen, which read as the
    coding screen being broken. So the promise is kept here too: paintEvent
    fills the surface, and says what it is waiting for.

    `setStyleSheet("background: ...")` does not do this. A plain QWidget does
    not draw its own stylesheet background without `WA_StyledBackground` and a
    paintEvent, and `WA_OpaquePaintEvent` suppresses the autofill that would
    otherwise cover it. Three settings that each looked like they painted the
    widget black, and none of them did.
    """

    IDLE_TEXT = "No episode open — use Open Episode."

    def __init__(self) -> None:
        super().__init__()
        self.setAttribute(Qt.WA_NativeWindow, True)
        self.setAttribute(Qt.WA_DontCreateNativeAncestors, True)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setMinimumSize(320, 180)
        self._idle = True

    def set_idle(self, idle: bool) -> None:
        """Whether libvlc has a media loaded and is painting this surface."""
        if idle != self._idle:
            self._idle = idle
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(color("video_surface")))
        if not self._idle:
            return
        painter.setPen(QColor(color("video_surface_text")))
        painter.setFont(theme.font("small"))
        painter.drawText(self.rect(), Qt.AlignCenter, self.IDLE_TEXT)


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
        self._anchor_pos = 0.0
        self._anchor_time = time.monotonic()

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
        # libvlc owns the pixels from here, so Qt stops drawing the placeholder
        # over them. Set before play() rather than after: the first frame can
        # arrive inside this call.
        self.surface.set_idle(False)
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
        self._anchor_pos = seconds
        self._anchor_time = time.monotonic()
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
        """The ground truth a mark is built from — never read this directly
        to record one; call `stamp()` instead.

        Exact when paused or after a seek. During PLAYBACK libvlc's own
        clock is coarse — measured, it only refreshes every 0.2–0.5s on
        23.976fps material (a ~0.042s frame), independent of how often this
        is polled — so a value read here while playing can be up to half a
        second stale relative to what is on screen at that instant.
        """
        ms = self._player.get_time()
        return max(0.0, ms / 1000.0) if ms and ms > 0 else 0.0

    def is_playing(self) -> bool:
        return bool(self._player.is_playing())

    def stamp(self, callback: Callable[[float], None]) -> None:
        """Call `callback(seconds)` with an exact position for a mark.

        `position()` is only exact once paused. Marking must never record
        the coarse, up-to-0.5s-stale value playback can return, so: already
        paused -> call back immediately with today's `position()`. Playing
        -> pause first, wait for libvlc to actually confirm it, THEN call
        back — closing the gap between "the coder saw the cut" and "the
        clock we read really stopped there".

        The settle loop mirrors `_hold_first_frame`'s bounded-retry idiom.
        Measured in steady-state playback (not cold-open): `set_pause(1)`
        flips `is_playing()` False and freezes `get_time()` within ~20ms, so
        the 15x20ms=300ms cap here is a safety margin, not the normal path.
        `set_pause(1)` is used rather than `toggle()` for the same reason
        `_hold_first_frame` avoids it — toggling assumes you already know
        the state you are toggling away from.
        """
        if not self.is_playing():
            callback(self.position())
            return
        self._player.set_pause(1)
        self._settle_stamp(callback, 0)

    def _settle_stamp(self, callback: Callable[[float], None],
                       tries: int) -> None:
        if not self.is_playing() or tries >= 15:
            callback(self.position())
            return
        QTimer.singleShot(20, lambda: self._settle_stamp(callback, tries + 1))

    # -- state ------------------------------------------------------------
    def _begin_scrub(self) -> None:
        self._scrubbing = True

    def _end_scrub(self) -> None:
        self._scrubbing = False
        if self._duration:
            self.seek(self._slider.value() / 1000.0 * self._duration)

    def _display_position(self) -> float:
        """What the on-screen counter shows — a smoothed ESTIMATE while
        playing, never the value a mark is stamped with (see `stamp()`).

        libvlc's real position only refreshes every 0.2-0.5s during
        playback (see `position()`), which reads as visibly frozen against
        a 0.042s frame. Between real ticks, this extrapolates forward from
        the last real tick using wall-clock time, and snaps back in sync
        the instant a new real tick arrives — so the display cannot drift
        further than the size of libvlc's own tick before self-correcting.
        """
        raw = self.position()
        now = time.monotonic()
        if raw != self._anchor_pos:
            self._anchor_pos = raw
            self._anchor_time = now
        if self.is_playing():
            return self._anchor_pos + (now - self._anchor_time)
        return raw

    def _sync(self) -> None:
        length = self._player.get_length()
        if length and length > 0:
            self._duration = length / 1000.0
        if self._scrubbing:
            # The player hasn't moved yet — show where the dragged thumb
            # points, not the stale pre-drag position, or the counter
            # visibly disagrees with the seek bar until release.
            pos = self._slider.value() / 1000.0 * self._duration \
                if self._duration else 0.0
        else:
            pos = self._display_position()
            if self._duration:
                self._slider.setValue(int(pos / self._duration * 1000))
        self._time.setText(
            f"{sec_to_hms(pos)} / {sec_to_hms(self._duration)}")
        self._btn_play.setText(
            "Pause" if self._player.is_playing() else "Play")
        self.position_changed.emit(pos)
