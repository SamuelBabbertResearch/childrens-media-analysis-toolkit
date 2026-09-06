"""
gui_measurements.py — editor for WHICH tool measures what, and with what settings.

Deliberately separate from SettingsDialog. That dialog edits SCORING (weights,
normalization ceilings), which applies to already-computed metrics and re-scores
the library instantly. This one edits MEASUREMENT, which changes the raw numbers
and therefore invalidates cached analysis. Putting both behind one "Apply"
button would make an expensive change look as cheap as a free one.

Policy: allow-with-warning. A researcher legitimately wants to try a detector on
one episode before committing to re-analyzing a whole library, so a change is
never blocked — but the dialog states exactly how many cached episodes it
invalidates before the change is applied, and the index labels them afterwards.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from analyzer.cache import is_stale, load_cached
from analyzer.config_loader import _base_dir
from analyzer.measurements import (
    EXPERIMENTAL,
    MEASUREMENTS,
    DETERMINISTIC,
    UNVALIDATED,
    VALIDATED,
    diff_fingerprints,
    normalize_config,
    selection,
)
from analyzer.show_index import list_episodes, list_shows, show_key

# Status badge colours. Validated is deliberately not green-on-white "all good";
# it means "we measured its error and published it", not "it is correct".
_STATUS_STYLE = {
    VALIDATED:    ("validated",    "#1a6b2a", "#e8f5ea"),
    DETERMINISTIC: ("deterministic", "#3a4a5a", "#eceff2"),
    EXPERIMENTAL: ("experimental", "#8a4b00", "#fff3e0"),
    UNVALIDATED:  ("unvalidated",  "#8a1a1a", "#fdeaea"),
}


class MeasurementsDialog(tk.Toplevel):
    """Modal editor for the measurements block of the config."""

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self._app = parent
        self.title("Measurement Settings — Tools & Thresholds")
        self.grab_set()
        self.transient(parent)

        self._cfg = normalize_config(copy.deepcopy(parent._cfg))
        self._tool_vars: dict[str, tk.StringVar] = {}
        self._enabled_vars: dict[str, tk.BooleanVar] = {}
        self._param_vars: dict[tuple[str, str], tk.Variable] = {}
        self._param_frames: dict[str, tk.Frame] = {}
        self._note_labels: dict[str, tk.Label] = {}
        self._badge_labels: dict[str, tk.Label] = {}

        self._build()
        self._center_on_parent()

    # ---- layout ----

    def _center_on_parent(self) -> None:
        self.geometry("720x760")
        self.update_idletasks()
        p = self._app
        px, py = p.winfo_rootx(), p.winfo_rooty()
        pw, ph = p.winfo_width(), p.winfo_height()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{max(px + (pw - w) // 2, 0)}+{max(py + (ph - h) // 2, 0)}")

    def _build(self) -> None:
        # Buttons are packed FIRST: a side=BOTTOM widget added after an
        # expand=True widget gets zero height (see CLAUDE.md).
        self._build_buttons()

        tk.Label(
            self,
            text="These settings change the raw measurements, so episodes already "
                 "analyzed under different settings become stale and need "
                 "re-analysis. Weights and ceilings are elsewhere (Settings) and "
                 "re-score instantly without re-analysis.",
            wraplength=680, justify="left", anchor="w",
            fg="#7a5c00", bg="#fffbe6", padx=8, pady=6,
            font=("TkDefaultFont", 8),
        ).pack(fill=tk.X, padx=10, pady=(10, 6))

        # Scrollable body — the measurement list is taller than any sane window.
        outer = tk.Frame(self)
        outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))
        canvas = tk.Canvas(outer, borderwidth=0, highlightthickness=0)
        vbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        body = tk.Frame(canvas)

        body.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        window_id = canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(window_id, width=e.width),
        )
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_wheel(event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_wheel)
        self.bind("<Destroy>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        for spec in MEASUREMENTS:
            self._build_measurement(body, spec)

    def _build_measurement(self, parent: tk.Frame, spec) -> None:
        tool, params, enabled = selection(self._cfg, spec.key)

        box = tk.LabelFrame(parent, text=spec.name, padx=8, pady=6)
        box.pack(fill=tk.X, pady=(0, 8))

        tk.Label(box, text=spec.description, wraplength=630, justify="left",
                 anchor="w", fg="#555555",
                 font=("TkDefaultFont", 8)).pack(fill=tk.X, pady=(0, 4))

        if spec.can_disable:
            var = tk.BooleanVar(value=enabled)
            self._enabled_vars[spec.key] = var
            tk.Checkbutton(
                box, text="Enabled", variable=var,
                command=lambda k=spec.key: self._on_enabled_toggled(k),
            ).pack(anchor="w")

        # Tool row
        row = tk.Frame(box)
        row.pack(fill=tk.X, pady=(2, 0))
        tk.Label(row, text="Tool:", width=6, anchor="w").pack(side=tk.LEFT)

        names = [t.name for t in spec.tools]
        tvar = tk.StringVar(value=tool.name)
        self._tool_vars[spec.key] = tvar
        cb = ttk.Combobox(row, textvariable=tvar, values=names,
                          state="readonly", width=38)
        cb.pack(side=tk.LEFT)
        cb.bind("<<ComboboxSelected>>",
                lambda _e, k=spec.key: self._on_tool_changed(k))

        badge = tk.Label(row, font=("TkDefaultFont", 8), padx=6)
        badge.pack(side=tk.LEFT, padx=(8, 0))
        self._badge_labels[spec.key] = badge

        note = tk.Label(box, wraplength=630, justify="left", anchor="w",
                        fg="#555555", font=("TkDefaultFont", 8))
        note.pack(fill=tk.X, pady=(4, 0))
        self._note_labels[spec.key] = note

        pframe = tk.Frame(box)
        pframe.pack(fill=tk.X, pady=(4, 0))
        self._param_frames[spec.key] = pframe

        self._refresh_tool_ui(spec.key, params)
        if spec.can_disable:
            self._on_enabled_toggled(spec.key)

    def _refresh_tool_ui(self, key: str, params: dict | None = None) -> None:
        """Rebuild badge, notes, and parameter rows for the selected tool."""
        spec = _spec(key)
        tool = self._selected_tool(key)
        frame = self._param_frames[key]

        for child in frame.winfo_children():
            child.destroy()
        for (mkey, _pkey) in list(self._param_vars):
            if mkey == key:
                self._param_vars.pop((mkey, _pkey))

        label, fg, bg = _STATUS_STYLE.get(tool.status, ("", "#555555", "#eeeeee"))
        badge = self._badge_labels[key]
        badge.configure(text=label, fg=fg, bg=bg)

        note_text = tool.summary
        if tool.notes:
            note_text = f"{tool.summary}\n{tool.notes}"
        if not tool.is_available():
            note_text = ("NOT INSTALLED — install it from Tools → Optional tools "
                         "before selecting it.\n" + note_text)
        self._note_labels[key].configure(
            text=note_text,
            fg="#8a1a1a" if not tool.is_available() else "#555555",
        )

        values = dict(tool.defaults())
        if params:
            values.update({k: v for k, v in params.items() if k in values})

        for p in tool.params:
            row = tk.Frame(frame)
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=p.label, width=22, anchor="w",
                     font=("TkDefaultFont", 8)).pack(side=tk.LEFT)

            if p.kind == "bool":
                var: tk.Variable = tk.BooleanVar(value=bool(values.get(p.key)))
                tk.Checkbutton(row, variable=var).pack(side=tk.LEFT)
            elif p.kind == "choice":
                var = tk.StringVar(value=str(values.get(p.key, p.default)))
                ttk.Combobox(row, textvariable=var,
                             values=[v for v, _ in p.choices],
                             state="readonly", width=10).pack(side=tk.LEFT)
            else:
                var = tk.StringVar(value=str(values.get(p.key, p.default)))
                tk.Entry(row, textvariable=var, width=10).pack(side=tk.LEFT)

            self._param_vars[(key, p.key)] = var

            if p.unit:
                tk.Label(row, text=p.unit, font=("TkDefaultFont", 8),
                         fg="#555555").pack(side=tk.LEFT, padx=(3, 0))
            if p.help:
                tk.Label(frame, text=p.help, wraplength=600, justify="left",
                         anchor="w", fg="#777777",
                         font=("TkDefaultFont", 8)).pack(fill=tk.X, padx=(24, 0))

        _ = spec  # spec kept for readability of the lookup above

    # ---- events ----

    def _on_tool_changed(self, key: str) -> None:
        self._refresh_tool_ui(key)

    def _on_enabled_toggled(self, key: str) -> None:
        state = self._enabled_vars[key].get()
        for child in self._param_frames[key].winfo_children():
            _set_state_recursive(child, state)

    def _selected_tool(self, key: str):
        spec = _spec(key)
        name = self._tool_vars[key].get()
        for t in spec.tools:
            if t.name == name:
                return t
        return spec.default_tool()

    # ---- read UI back into a config ----

    def _build_new_cfg(self) -> dict | None:
        new_cfg = copy.deepcopy(self._cfg)
        block = new_cfg.setdefault("measurements", {})

        for spec in MEASUREMENTS:
            tool = self._selected_tool(spec.key)
            entry = block.setdefault(spec.key, {})
            entry["tool"] = tool.key

            params: dict = {}
            for p in tool.params:
                var = self._param_vars.get((spec.key, p.key))
                if var is None:
                    params[p.key] = p.default
                    continue
                try:
                    params[p.key] = p.coerce(var.get())
                except (TypeError, ValueError):
                    messagebox.showerror(
                        "Invalid value",
                        f"{spec.name} — {p.label}: "
                        f"'{var.get()}' is not a valid number.",
                        parent=self,
                    )
                    return None
            entry["params"] = params

            if spec.can_disable:
                entry["enabled"] = bool(self._enabled_vars[spec.key].get())

        return normalize_config(new_cfg)

    # ---- staleness ----

    def _count_stale(self, new_cfg: dict) -> int:
        root = getattr(self._app, "_root_folder", None)
        if not root:
            return 0
        count = 0
        for show_dir in list_shows(root):
            skey = show_key(root, show_dir)
            for ep in list_episodes(show_dir):
                cached = load_cached(root, skey, ep.stem)
                if cached and is_stale(cached, new_cfg):
                    count += 1
        return count

    def _confirm_change(self, new_cfg: dict) -> bool:
        """Show what changes and what it costs. Never blocks — only informs."""
        changes = diff_fingerprints(self._cfg, new_cfg)
        if not changes:
            return True

        unavailable = [
            f"  • {spec.name}: {self._selected_tool(spec.key).name}"
            for spec in MEASUREMENTS
            if not self._selected_tool(spec.key).is_available()
        ]
        if unavailable:
            messagebox.showerror(
                "Tool not installed",
                "These selections require a tool that is not installed:\n\n"
                + "\n".join(unavailable)
                + "\n\nInstall it from Tools → Optional tools, or pick another tool.",
                parent=self,
            )
            return False

        stale = self._count_stale(new_cfg)
        lines = ["Changing:", ""]
        lines += [f"  • {c}" for c in changes]
        lines += [""]
        if stale:
            ep = "episode" if stale == 1 else "episodes"
            lines += [
                f"This makes {stale} already-analyzed {ep} STALE — they were "
                f"measured with different settings, so their numbers are not "
                f"comparable with anything analyzed from now on.",
                "",
                "They are not deleted and will keep displaying. Re-analyze them "
                "to bring the whole library back onto one set of settings.",
                "",
                "Apply anyway?",
            ]
        else:
            lines += ["No analyzed episodes are affected.", "", "Apply?"]

        return messagebox.askyesno(
            "Measurement change", "\n".join(lines), parent=self,
        )

    # ---- actions ----

    def _apply(self) -> None:
        new_cfg = self._build_new_cfg()
        if new_cfg is None or not self._confirm_change(new_cfg):
            return
        stale = self._count_stale(new_cfg)
        self._cfg = new_cfg
        self._app._cfg = copy.deepcopy(new_cfg)
        self._app._refresh_current_view()

        msg = "Measurement settings applied."
        if stale:
            ep = "episode" if stale == 1 else "episodes"
            msg += f" {stale} cached {ep} now stale — re-analyze to compare them."
        self._app._status_var.set(msg)

    def _save_default(self) -> None:
        new_cfg = self._build_new_cfg()
        if new_cfg is None or not self._confirm_change(new_cfg):
            return
        config_path = _base_dir() / "config.json"
        try:
            existing = json.loads(config_path.read_text(encoding="utf-8"))
            existing["measurements"] = new_cfg["measurements"]
            # Keep the flat keys consistent for anything still reading them.
            for key in (
                "cut_detection_threshold", "sample_fps", "flashing_sample_fps",
                "flashing_luminance_threshold", "dissolve_noise_floor",
                "dissolve_min_frames", "dissolve_detection_enabled",
                "cut_classification_enabled", "cut_classification_offset_sec",
                "scene_change_similarity_threshold",
                "speech_transcription_enabled", "speech_whisper_model",
            ):
                if key in new_cfg:
                    existing[key] = new_cfg[key]
            config_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except Exception as exc:                              # noqa: BLE001
            messagebox.showerror("Save failed", str(exc), parent=self)
            return

        self._cfg = new_cfg
        self._app._cfg = copy.deepcopy(new_cfg)
        self._app._refresh_current_view()
        messagebox.showinfo("Saved", f"Measurement settings saved to:\n{config_path}",
                            parent=self)

    def _restore_defaults(self) -> None:
        if not messagebox.askyesno(
            "Restore defaults",
            "Reset every measurement to CMAT's default tool and settings?",
            parent=self,
        ):
            return
        from analyzer.measurements import default_measurements
        self._cfg["measurements"] = default_measurements()
        for spec in MEASUREMENTS:
            tool, params, enabled = selection(self._cfg, spec.key)
            self._tool_vars[spec.key].set(tool.name)
            if spec.can_disable:
                self._enabled_vars[spec.key].set(enabled)
            self._refresh_tool_ui(spec.key, params)
            if spec.can_disable:
                self._on_enabled_toggled(spec.key)

    def _build_buttons(self) -> None:
        bf = tk.Frame(self)
        bf.pack(side=tk.BOTTOM, pady=(4, 10))
        tk.Button(bf, text="Apply", command=self._apply, padx=8).pack(
            side=tk.LEFT, padx=4)
        tk.Button(bf, text="Save as Default", command=self._save_default,
                  padx=8).pack(side=tk.LEFT, padx=4)
        tk.Button(bf, text="Restore Defaults", command=self._restore_defaults,
                  padx=8).pack(side=tk.LEFT, padx=4)
        tk.Button(bf, text="Close", command=self.destroy, padx=8).pack(
            side=tk.LEFT, padx=4)


def _spec(key: str):
    for m in MEASUREMENTS:
        if m.key == key:
            return m
    raise KeyError(key)


def _set_state_recursive(widget: tk.Widget, enabled: bool) -> None:
    try:
        widget.configure(state=(tk.NORMAL if enabled else tk.DISABLED))
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        _set_state_recursive(child, enabled)
