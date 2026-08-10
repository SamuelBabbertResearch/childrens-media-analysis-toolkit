"""
ui/player.py — the video surface, for hand coding.

VLC rather than QMediaPlayer, deliberately. Coding a transition or an event
means naming the moment it happens, and on Windows QMediaPlayer goes through
Media Foundation, where seeking on an arbitrary MP4 lands on the nearest
keyframe rather than the frame asked for. A coder stepping frame by frame
would be recording the wrong timestamp and would have no way to tell. libvlc
decodes and steps frames itself, so `next_frame` really is the next frame.

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

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget,
)


def available() -> tuple[bool, str]:
    """(usable, explanation). Never raises — the caller shows the reason."""
    try:
        import vlc
    except ImportError:
        return False, ("python-vlc is not installed. Install it with "
                       "`pip install python-vlc`.")
    try:
        vlc.Instance("--no-video-title-show")
    except Exception as exc:                # noqa: BLE001 - reported verbatim
        return False, (f"VLC is installed but libvlc would not start: {exc}. "
                       f"A 64-bit VLC is needed to match this interpreter.")
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
        self._instance = vlc.Instance("--no-video-title-show", "--quiet")
        self._player = self._instance.media_player_new()
        self._duration = 0.0
        self._scrubbing = False

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
        self._btn_frame = QPushButton("Frame ▸")
        self._btn_frame.setToolTip(
            "Advance one frame. VLC decodes it, so this is the next frame "
            "rather than the next keyframe.")
        self._btn_frame.clicked.connect(self.step_frame)
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

    def step_frame(self) -> None:
        self._player.next_frame()

    def seek(self, seconds: float) -> None:
        seconds = max(0.0, min(seconds, self._duration or seconds))
        self._player.set_time(int(seconds * 1000))
        self.position_changed.emit(seconds)

    def position(self) -> float:
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
