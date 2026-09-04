"""Pre-use package and playback qualification for CMAT Study Runner.

This is a technical check, not a substitute for a researcher watching every
clip on the collection computer at the approved display and volume settings.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoSink

from study_runner.core import PackageError, load_package


def qualify_media(path: Path, *, timeout_ms: int = 10_000) -> tuple[bool, str]:
    player = QMediaPlayer()
    audio = QAudioOutput()
    audio.setMuted(True)
    video = QVideoSink()
    player.setAudioOutput(audio)
    player.setVideoOutput(video)
    loop = QEventLoop()
    result = {"ok": False, "detail": "timed out before playback advanced"}

    def on_status(status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.LoadedMedia:
            player.play()
        elif status == QMediaPlayer.InvalidMedia:
            result["detail"] = player.errorString() or "invalid media"
            loop.quit()

    def on_position(position: int) -> None:
        if position >= 250:
            result["ok"] = True
            result["detail"] = f"duration={player.duration()}ms"
            loop.quit()

    def on_error(_error: QMediaPlayer.Error, message: str) -> None:
        result["detail"] = message or player.errorString() or "playback error"
        loop.quit()

    player.mediaStatusChanged.connect(on_status)
    player.positionChanged.connect(on_position)
    player.errorOccurred.connect(on_error)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(timeout_ms)
    player.setSource(QUrl.fromLocalFile(str(path)))
    loop.exec()
    player.stop()
    return bool(result["ok"]), str(result["detail"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        package = load_package(args.package)
    except PackageError as exc:
        print(f"PACKAGE FAIL: {exc}", file=sys.stderr)
        return 2

    app = QGuiApplication(sys.argv[:1])
    failures = []
    for number, stimulus in enumerate(package.order(next(iter(package.order_conditions))), 1):
        ok, detail = qualify_media(stimulus.path)
        print(f"{number:02d} {stimulus.label}: {'PASS' if ok else 'FAIL'} ({detail})")
        if not ok:
            failures.append(stimulus.label)
    if failures:
        print(f"PLAYBACK FAIL: {', '.join(failures)}", file=sys.stderr)
        return 3
    print(
        f"PACKAGE PASS: {package.study_id}; {len(package.stimuli)} clips; "
        f"hash={package.package_hash}")
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
