"""Live analysis viewer for CMAT.

The main GUI imports this module lazily at startup. Analysis still runs through
the shared analyzer engine; this window only streams sampled frames and progress
messages back to Tk on the main thread.
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from analyzer.cache import save_cache
from analyzer.engine import analyze_episode
from analyzer.show_index import show_key

try:
    from PIL import Image, ImageTk
except ImportError:  # pragma: no cover - exercised only in minimal installs
    Image = None
    ImageTk = None


class LiveAnalysisWindow(tk.Toplevel):
    """Analyze one episode while displaying sampled frames."""

    def __init__(
        self,
        parent: tk.Misc,
        ep_path: Path,
        root_folder: Path,
        cfg: dict,
        on_complete=None,
    ) -> None:
        super().__init__(parent)
        self.title(f"Live Analysis - {ep_path.name}")
        self.geometry("760x560")
        self.minsize(560, 420)
        self._ep_path = ep_path
        self._root_folder = root_folder
        self._cfg = cfg
        self._on_complete = on_complete
        self._queue: queue.Queue[dict] = queue.Queue()
        self._closed = False
        self._completion_notified = False
        self._photo = None

        self.protocol("WM_DELETE_WINDOW", self._close)
        self._build_ui()
        self._poll_queue()
        threading.Thread(target=self._worker, daemon=True).start()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top = tk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        top.columnconfigure(0, weight=1)
        self._status = tk.StringVar(value="Starting analysis...")
        tk.Label(top, textvariable=self._status, anchor="w").grid(row=0, column=0, sticky="ew")
        self._progress = ttk.Progressbar(top, mode="determinate", maximum=100)
        self._progress.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        self._image_label = tk.Label(self, bg="black")
        self._image_label.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        bottom = tk.Frame(self)
        bottom.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        bottom.columnconfigure(0, weight=1)
        self._metrics = tk.StringVar(value="")
        tk.Label(bottom, textvariable=self._metrics, anchor="w", justify=tk.LEFT).grid(
            row=0, column=0, sticky="ew"
        )

    def _worker(self) -> None:
        def progress(frac: float) -> None:
            if frac < 0:
                self._put({"type": "progress", "value": 5, "status": "Detecting cuts..."})
            else:
                self._put({
                    "type": "progress",
                    "value": max(0.0, min(100.0, frac * 100.0)),
                    "status": f"Analyzing {self._ep_path.name} ({int(frac * 100)}%)",
                })

        def frame(frame_bgr, saturation: float, motion: float, luminance: float, is_flash: bool) -> None:
            if Image is None or self._queue.qsize() > 3:
                return
            rgb = frame_bgr[:, :, ::-1]
            image = Image.fromarray(rgb)
            image.thumbnail((720, 420))
            self._put({
                "type": "frame",
                "image": image.copy(),
                "metrics": (
                    f"Saturation {saturation:.3f}   Motion {motion:.4f}   "
                    f"Luminance {luminance:.3f}" + ("   FLASH" if is_flash else "")
                ),
            })

        result = analyze_episode(
            self._ep_path,
            config=self._cfg,
            progress_cb=progress,
            frame_cb=frame,
        )
        if result.status == "ok":
            skey = show_key(self._root_folder, self._ep_path.parent)
            save_cache(self._root_folder, skey, self._ep_path.stem, result.to_dict())
        self._put({"type": "done", "result": result})

    def _put(self, msg: dict) -> None:
        if not self._closed:
            self._queue.put(msg)

    def _poll_queue(self) -> None:
        if self._closed:
            return
        try:
            while True:
                self._handle(self._queue.get_nowait())
        except queue.Empty:
            pass
        self.after(50, self._poll_queue)

    def _handle(self, msg: dict) -> None:
        kind = msg["type"]
        if kind == "progress":
            self._progress["value"] = msg["value"]
            self._status.set(msg["status"])
        elif kind == "frame" and ImageTk is not None:
            self._photo = ImageTk.PhotoImage(msg["image"])
            self._image_label.config(image=self._photo)
            self._metrics.set(msg["metrics"])
        elif kind == "done":
            result = msg["result"]
            self._progress["value"] = 100
            if result.status == "ok":
                self._status.set(f"Complete: {self._ep_path.name}")
            else:
                self._status.set(f"Failed: {result.error}")
            self._notify_complete()

    def _notify_complete(self) -> None:
        if self._completion_notified:
            return
        self._completion_notified = True
        if self._on_complete:
            self._on_complete()

    def _close(self) -> None:
        self._closed = True
        self._notify_complete()
        self.destroy()
