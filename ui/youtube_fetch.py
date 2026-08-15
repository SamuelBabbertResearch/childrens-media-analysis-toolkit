"""
ui/youtube_fetch.py — fetch a YouTube channel or playlist's video list.

No video is downloaded here — `analyzer.youtube_fetch.fetch_videos()` asks
yt-dlp for metadata only (title, upload date, duration, channel, playlist),
so a sample can be designed before committing to downloading anything. A real
channel can take 30-60s to list (`sample_youtube.py`'s own measured note,
kept, before it was retired into this), so the fetch runs on a worker
thread — the interface must never freeze (`CLAUDE.md` §2.4) — following the
same `QThread` + done/failed signal shape as `ui/metadata_import.py`'s
`FetchWorker`.

On success, the caller (`ui/sampler.py`) reads `self.episodes` and
`self.channel_id` after `exec()` returns `QDialog.Accepted`.
"""

from __future__ import annotations

import hashlib

from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton,
    QSpinBox, QWidget,
)
from PySide6.QtCore import QThread, Signal

from analyzer.youtube_fetch import (
    DEFAULT_MIN_DURATION, available, channel_slug, fetch_videos,
)
from ui.modal import ModalDialogFrame

DIALOG_W = 560
DIALOG_H = 380


class FetchWorker(QThread):
    """Network I/O off the interface thread — same shape as
    ui/metadata_import.py's FetchWorker."""

    done = Signal(object)          # list[Episode]
    failed = Signal(str)

    def __init__(self, urls: list[str], min_duration: int) -> None:
        super().__init__()
        self._urls = urls
        self._min_duration = min_duration

    def run(self) -> None:
        try:
            episodes = fetch_videos(self._urls, self._min_duration)
        except Exception as exc:            # noqa: BLE001 — shown, not hidden
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.done.emit(episodes)


def _channel_id_for(episodes: list) -> str:
    """A stable identifier for this fetch, reused as the era show-key suffix
    and the manifest's entry_id.

    One shared channel across every result -> that channel's slug, so
    re-fetching the same channel later reconnects to the same era
    definitions. Results spanning different channels (a multi-playlist
    fetch that isn't all one channel) -> a short hash of the video ids, so
    the SAME set of URLs still reproduces the SAME identifier next time,
    without pretending there is one channel when there is not.
    """
    channels = {e.extra.get("channel") for e in episodes if e.extra.get("channel")}
    if len(channels) == 1:
        return channel_slug(next(iter(channels)))
    ids = sorted(e.extra.get("video_id", "") for e in episodes)
    digest = hashlib.sha1("|".join(ids).encode("utf-8")).hexdigest()[:8]
    return f"mixed-{digest}"


class YouTubeFetchDialog(QDialog):
    """Fetch a channel or playlist's video list — metadata only."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.resize(DIALOG_W, DIALOG_H)
        self._worker: FetchWorker | None = None
        self.episodes: list | None = None
        self.channel_id: str | None = None

        body = ModalDialogFrame.install(
            self, "Fetch YouTube channel / playlist", buttons=("close",))

        ok, reason = available()
        if not ok:
            warn = QLabel(reason)
            warn.setWordWrap(True)
            body.addWidget(warn)

        body.addWidget(QLabel(
            "Channel or playlist URLs, one per line. Several playlist URLs "
            "together become one sampling frame, each video tagged with "
            "which playlist it came from — usable as a stratification "
            "axis. No video is downloaded; this only lists them."))
        self._urls = QPlainTextEdit()
        self._urls.setPlaceholderText(
            "https://www.youtube.com/@GameTheorists/videos\n"
            "https://www.youtube.com/playlist?list=…")
        body.addWidget(self._urls, 1)

        dur_widget = QWidget()
        dur_row = QHBoxLayout(dur_widget)
        dur_row.setContentsMargins(0, 0, 0, 0)
        dur_row.addWidget(QLabel("Minimum duration (seconds):"))
        self._min_duration = QSpinBox()
        self._min_duration.setRange(0, 24 * 3600)
        self._min_duration.setValue(DEFAULT_MIN_DURATION)
        self._min_duration.setToolTip(
            "Excludes Shorts and clips. 0 disables the filter.")
        dur_row.addWidget(self._min_duration)
        dur_row.addStretch(1)
        body.addWidget(dur_widget)

        self._status = QLabel("Paste one or more URLs, then Fetch.")
        self._status.setProperty("role", "dim")
        self._status.setWordWrap(True)
        body.addWidget(self._status)

        row = ModalDialogFrame.add_action_bar(self)
        row.addStretch(1)
        self._btn_fetch = QPushButton("Fetch")
        self._btn_fetch.setEnabled(ok)
        self._btn_fetch.clicked.connect(self._fetch)
        row.addWidget(self._btn_fetch)
        self._btn_use = QPushButton("Use These Episodes")
        self._btn_use.setProperty("primary", "true")
        self._btn_use.setEnabled(False)
        self._btn_use.clicked.connect(self._use)
        row.addWidget(self._btn_use)
        close = QPushButton("Cancel")
        close.clicked.connect(self.reject)
        row.addWidget(close)

    def _fetch(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        urls = [u for u in self._urls.toPlainText().splitlines() if u.strip()]
        if not urls:
            QMessageBox.information(self, "Fetch",
                                    "Enter at least one URL first.")
            return
        self._btn_fetch.setEnabled(False)
        self._btn_fetch.setText("Fetching…")
        self._btn_use.setEnabled(False)
        self._status.setText(
            "Fetching — a large channel can take 30-60s (metadata only, no "
            "download)…")
        self._worker = FetchWorker(urls, self._min_duration.value())
        self._worker.done.connect(self._fetched)
        self._worker.failed.connect(self._fetch_failed)
        self._worker.start()

    def _reset_fetch_button(self) -> None:
        # NOT `self._worker = None` — see ui/automated.py. Freeing a QThread
        # from a slot connected to it kills the process.
        self._btn_fetch.setEnabled(True)
        self._btn_fetch.setText("Fetch")

    def _fetch_failed(self, message: str) -> None:
        self._reset_fetch_button()
        self._status.setText(f"Fetch failed: {message}")
        QMessageBox.warning(self, "Could not fetch the video list", message)

    def _fetched(self, episodes: list) -> None:
        self._reset_fetch_button()
        self._fetched_episodes = episodes
        if not episodes:
            self._status.setText(
                "No qualifying videos found — try a lower minimum duration, "
                "or check the URL.")
            return
        dates = sorted(e.air_date for e in episodes if e.air_date)
        span = f"{dates[0]} to {dates[-1]}" if dates else "no dates found"
        channels = {e.extra.get("channel") for e in episodes
                   if e.extra.get("channel")}
        self._status.setText(
            f"{len(episodes)} video{'s' if len(episodes) != 1 else ''} "
            f"found ({span})"
            + (f", channel: {next(iter(channels))}" if len(channels) == 1
               else f", {len(channels)} channels" if channels else ""))
        self._btn_use.setEnabled(True)

    def _use(self) -> None:
        episodes = getattr(self, "_fetched_episodes", None)
        if not episodes:
            return
        self.episodes = episodes
        self.channel_id = _channel_id_for(episodes)
        self.accept()
