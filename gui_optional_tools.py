"""
gui_optional_tools.py — "Optional tools" screen.

Explains each opt-in component BEFORE installing it: what it does, what it
buys you, what it costs, and what is still unverified. Installing is a
deliberate, informed choice — nothing large is pulled in behind the user's back,
and nothing here is required for CMAT's validated measurements.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

from analyzer.optional_tools import (OPTIONAL_TOOLS, OptionalTool,
                                     install_command, install_tool)
from gui_validation import _Tip


class OptionalToolsWindow(tk.Toplevel):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.title("Optional tools")
        self.geometry("780x660")
        self._q: queue.Queue = queue.Queue()
        self._installing = False
        self._build_ui()
        self.after(100, self._poll)

    def _build_ui(self) -> None:
        tk.Label(
            self,
            text="Optional tools extend CMAT with components too large to bundle. "
                 "Each is opt-in, and CMAT works fully without them — nothing here "
                 "is part of the validated core.",
            font=("TkDefaultFont", 9), fg="#333333", wraplength=740,
            justify="left", padx=12, pady=8,
        ).pack(fill=tk.X)

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))
        self._panels: list[_ToolPanel] = []
        for tool in OPTIONAL_TOOLS:
            panel = _ToolPanel(nb, tool, on_install=self._start_install)
            nb.add(panel, text=tool.name.split("—")[0].strip()[:28])
            self._panels.append(panel)

        log_fr = tk.LabelFrame(self, text=" Install output ", padx=6, pady=4)
        log_fr.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0, 8))
        self._log = tk.Text(log_fr, height=8, font=("Consolas", 8),
                            wrap=tk.NONE, state=tk.DISABLED)
        lsb = ttk.Scrollbar(log_fr, orient=tk.VERTICAL, command=self._log.yview)
        self._log.configure(yscrollcommand=lsb.set)
        lsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Button(self, text="Close", command=self.destroy,
                  width=12).pack(pady=(0, 10))

    # -- install ---------------------------------------------------------

    def _start_install(self, tool: OptionalTool) -> None:
        if self._installing:
            messagebox.showinfo("Install running",
                                "An install is already in progress.",
                                parent=self)
            return
        cmd = " ".join(install_command(tool))
        if not messagebox.askyesno(
                f"Install {tool.name}?",
                f"CMAT will run:\n\n    {cmd}\n\n"
                f"Downloads roughly {tool.disk_estimate}. This can take several "
                f"minutes.\n\nProceed?",
                parent=self):
            return
        self._installing = True
        self._append(f"Installing {tool.name}…")
        for p in self._panels:
            p.set_busy(True)

        def worker() -> None:
            ok = install_tool(tool, line_cb=lambda ln: self._q.put(("log", ln)))
            self._q.put(("done", (tool, ok)))

        threading.Thread(target=worker, daemon=True).start()

    def _append(self, line: str) -> None:
        self._log.config(state=tk.NORMAL)
        self._log.insert(tk.END, line + "\n")
        self._log.see(tk.END)
        self._log.config(state=tk.DISABLED)

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "log":
                    self._append(payload)
                elif kind == "done":
                    tool, ok = payload
                    self._installing = False
                    for p in self._panels:
                        p.set_busy(False)
                        p.refresh_status()
                    if ok and tool.is_available():
                        self._append(f"{tool.name} installed successfully.")
                        messagebox.showinfo(
                            "Installed",
                            f"{tool.name} is ready.\n\nIt now appears as a "
                            f"detector option in the Validation tab, so you can "
                            f"grade it against your own hand coding.",
                            parent=self)
                    elif ok:
                        self._append("pip succeeded but the module still does "
                                     "not import — a restart may be required.")
                        messagebox.showwarning(
                            "Restart needed",
                            "Install finished, but the module isn't importable "
                            "in this session. Restart CMAT and check again.",
                            parent=self)
                    else:
                        messagebox.showerror(
                            "Install failed",
                            "Installation did not complete. See the output log "
                            "for details — you can also run the command "
                            "yourself in a terminal.", parent=self)
        except queue.Empty:
            pass
        self.after(100, self._poll)


class _ToolPanel(tk.Frame):
    def __init__(self, parent: tk.Misc, tool: OptionalTool, on_install) -> None:
        super().__init__(parent)
        self._tool = tool
        self._on_install = on_install

        canvas = tk.Canvas(self, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        body = tk.Frame(canvas)
        wid = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfigure(wid, width=e.width))

        def _wheel(e):
            canvas.yview_scroll(int(-e.delta / 120), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        pad = dict(padx=12, anchor="w")
        tk.Label(body, text=tool.name, font=("TkDefaultFont", 11, "bold"),
                 anchor="w").pack(fill=tk.X, pady=(10, 0), **pad)
        tk.Label(body, text=tool.one_liner, font=("TkDefaultFont", 9),
                 fg="#444444", wraplength=680, justify="left",
                 anchor="w").pack(fill=tk.X, pady=(2, 6), **pad)

        status_row = tk.Frame(body)
        status_row.pack(fill=tk.X, pady=(0, 8), **pad)
        self._status_var = tk.StringVar()
        self._status_lbl = tk.Label(status_row, textvariable=self._status_var,
                                    font=("TkDefaultFont", 9, "bold"))
        self._status_lbl.pack(side=tk.LEFT)
        self._btn = tk.Button(status_row, text="Install",
                              command=lambda: self._on_install(self._tool),
                              padx=14, bg="#c8e6c9",
                              font=("TkDefaultFont", 9, "bold"))
        self._btn.pack(side=tk.LEFT, padx=12)
        _Tip(self._btn, "Runs pip in this Python environment. CMAT shows you "
                        "the exact command and asks before doing anything.")
        tk.Button(status_row, text="Project page",
                  command=lambda: webbrowser.open(tool.docs_url)).pack(side=tk.LEFT)

        _section(body, "What it does", tool.what_it_does, pad)
        _bullets(body, "Why you might want it", tool.benefits, pad, "#005500")
        _bullets(body, "What it costs", tool.costs, pad, "#884400")
        _bullets(body, "Important caveats", tool.caveats, pad, "#aa0000")

        tk.Label(body,
                 text=f"License: {tool.license}   ·   pip package: "
                      f"{tool.pip_package}   ·   disk: {tool.disk_estimate}",
                 font=("TkDefaultFont", 8), fg="#666666",
                 anchor="w").pack(fill=tk.X, pady=(8, 14), **pad)

        self.refresh_status()

    def refresh_status(self) -> None:
        if self._tool.is_available():
            self._status_var.set(f"✓ Installed  ({self._tool.version()})")
            self._status_lbl.config(fg="#007700")
            self._btn.config(text="Reinstall", bg="#e0e0e0")
        else:
            self._status_var.set("Not installed")
            self._status_lbl.config(fg="#884400")
            self._btn.config(text="Install", bg="#c8e6c9")

    def set_busy(self, busy: bool) -> None:
        self._btn.config(state=tk.DISABLED if busy else tk.NORMAL)


def _section(parent: tk.Misc, title: str, text: str, pad: dict) -> None:
    tk.Label(parent, text=title, font=("TkDefaultFont", 9, "bold"),
             anchor="w").pack(fill=tk.X, pady=(6, 2), **pad)
    tk.Label(parent, text=text, font=("TkDefaultFont", 9), fg="#333333",
             wraplength=680, justify="left",
             anchor="w").pack(fill=tk.X, **pad)


def _bullets(parent: tk.Misc, title: str, items: list[str], pad: dict,
             color: str) -> None:
    if not items:
        return
    tk.Label(parent, text=title, font=("TkDefaultFont", 9, "bold"),
             anchor="w").pack(fill=tk.X, pady=(8, 2), **pad)
    for it in items:
        row = tk.Frame(parent)
        row.pack(fill=tk.X, **pad)
        tk.Label(row, text="•", fg=color,
                 font=("TkDefaultFont", 9)).pack(side=tk.LEFT, anchor="n")
        tk.Label(row, text=it, font=("TkDefaultFont", 9), fg="#333333",
                 wraplength=650, justify="left",
                 anchor="w").pack(side=tk.LEFT, fill=tk.X, padx=(4, 0))
