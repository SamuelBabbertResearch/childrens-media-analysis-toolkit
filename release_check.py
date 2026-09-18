"""Opt-in checks inside the shipped executable; uses only synthetic scratch data.

Run ``CMAT.exe --check-package report.json`` to qualify a Windows package.
Normal startup never imports or runs this module.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback


def run(report_path: str) -> int:
    report_file = Path(report_path).resolve()
    report_file.parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="cmat-package-check-"))
    report = {"passed": False, "frozen": bool(getattr(sys, "frozen", False)),
              "scratch": str(scratch), "checks": {}}
    checks = report["checks"]
    try:
        from analyzer.version import CMAT_VERSION, EXPORT_SCHEMA
        report.update(version=CMAT_VERSION, export_schema=EXPORT_SCHEMA)
        from analyzer.ffmpeg_path import ffmpeg_exe
        ffmpeg = ffmpeg_exe()
        checks["ffmpeg"] = str(ffmpeg)
        video = scratch / "synthetic.mp4"
        subprocess.run([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=160x120:rate=24",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=8000",
            "-t", "3.25", "-c:v", "mpeg4", "-c:a", "aac", str(video),
        ], check=True, capture_output=True, timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        from analyzer.engine import analyze_episode
        result = analyze_episode(video)
        if result.status != "ok" or not result.metrics.audio.available:
            raise RuntimeError(f"Synthetic analysis failed: {result.error}")
        if result.duration_sec < 3 or result.metrics.audio.rms_mean <= 0:
            raise RuntimeError("Synthetic duration/audio measurements are invalid")
        (scratch / "analysis.json").write_text(
            json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        checks["analysis"] = {"duration_sec": result.duration_sec,
                              "audio_rms_mean": result.metrics.audio.rms_mean}

        from analyzer.vocab_complexity import _process, compute_readability
        text = ("The little bear walked through the forest with a friend. "
                "They found a small tree and watched the birds sing. ") * 3
        cleaned, tokens = _process(text)
        readability = compute_readability(cleaned)
        if not tokens or readability["flesch_reading_ease"] is None:
            raise RuntimeError("Bundled language resources did not produce results")
        checks["language"] = {"content_tokens": len(tokens), **readability}
        import faster_whisper
        checks["whisper_import"] = faster_whisper.__version__

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QFontDatabase
        from ui import theme
        app = QApplication.instance() or QApplication(["CMAT package check"])
        fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for name in ("segoeui.ttf", "segoeuib.ttf", "consola.ttf"):
            QFontDatabase.addApplicationFont(str(fonts / name))
        theme.apply(app)
        from ui import main_window
        old_pref = main_window.get_pref
        main_window.get_pref = lambda *args, **kwargs: False
        try:
            window = main_window.MainWindow()
        finally:
            main_window.get_pref = old_pref
        window.show()
        app.processEvents()
        window.grab().save(str(scratch / "main-window.png"))
        window.hide()
        checks["main_window"] = True
        from ui.chart import ChartDialog, SpeechChartDialog
        from ui.clip_finder import ClipFinderDialog
        for name, dialog in [
            ("chart", ChartDialog("Synthetic package check", [result], result.config)),
            ("timed-text", SpeechChartDialog([
                {"file": "synthetic", "wpm": 90, "density": 0.5}])),
            ("clip-finder", ClipFinderDialog(source_dir=scratch)),
        ]:
            dialog.show()
            app.processEvents()
            dialog.grab().save(str(scratch / f"{name}.png"))
            dialog.close()
            checks[name] = True

        from ui.player import _libvlc, available
        ok, detail = available()
        if not ok:
            raise RuntimeError(f"Bundled VLC unavailable: {detail}")
        instance = _libvlc()
        media = instance.media_new(str(video))
        media.add_option(":vout=dummy")
        media.add_option(":aout=dummy")
        player = instance.media_player_new()
        player.set_media(media)
        try:
            player.play()
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline and player.get_time() <= 0:
                app.processEvents()
                time.sleep(0.05)
            if player.get_time() <= 0 or player.get_length() < 3000:
                raise RuntimeError("VLC did not decode the synthetic video")
            checks["vlc_playback"] = {"length_ms": player.get_length(),
                                       "position_ms": player.get_time()}
        finally:
            player.stop()
            player.release()
            media.release()
        report["passed"] = True
    except Exception:
        report["error"] = traceback.format_exc()
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["passed"] else 1
