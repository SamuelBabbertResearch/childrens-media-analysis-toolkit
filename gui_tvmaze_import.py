"""
TVMaze episode-metadata import dialog for CMAT.

Lets the user paste a TVMaze show URL, fetches episode data from the
public TVMaze API (no key required), previews how episodes match local
MP4 files, and writes air dates + season/episode numbers to the index DB.
"""

from __future__ import annotations
import threading
import urllib.error
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path

from analyzer.db import upsert_episode_metadata
from analyzer.show_index import list_shows, list_episodes, list_top_level
from analyzer.tvmaze_importer import (
    extract_show_id, fetch_show_info, fetch_episodes,
)
from analyzer.wiki_importer import match_to_files, MatchResult


class TVMazeImportDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, app_ref) -> None:
        super().__init__(parent)
        self.title("Import Episode Metadata from TVMaze")
        self.resizable(True, True)
        self.minsize(880, 540)
        self._app     = app_ref
        self._results: list[MatchResult] = []

        self._build_ui()
        self.transient(parent)
        self.grab_set()
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width()  // 2 - self.winfo_width()  // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2 - self.winfo_height() // 2
        self.geometry(f"+{max(0, px)}+{max(0, py)}")

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self) -> None:
        pad = dict(padx=10, pady=6)

        # instructions
        tk.Label(
            self,
            text=(
                "How to use:\n"
                "1. Find your show on TVMaze (tvmaze.com) and copy the URL from your browser.\n"
                "2. Paste it below and click Fetch — no account or API key needed.\n"
                "3. Review the matched episodes, then click Apply to write air dates to the database.\n"
                "\n"
                "Example URL:  https://www.tvmaze.com/shows/17755/franklin/episodes"
            ),
            justify=tk.LEFT, anchor="w", bg="#eef4ff", relief=tk.GROOVE,
            padx=10, pady=6, font=("TkDefaultFont", 9),
        ).pack(fill=tk.X, padx=10, pady=(10, 4))

        # URL row
        url_row = tk.Frame(self)
        url_row.pack(fill=tk.X, **pad)
        tk.Label(url_row, text="TVMaze URL:").pack(side=tk.LEFT, padx=(0, 6))
        self._url_var = tk.StringVar()
        url_entry = tk.Entry(url_row, textvariable=self._url_var, width=62)
        url_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 8))
        url_entry.bind("<Return>", lambda _: self._fetch())
        self._btn_fetch = tk.Button(url_row, text="Fetch", command=self._fetch, padx=10)
        self._btn_fetch.pack(side=tk.LEFT)

        # show info / status
        self._show_info_var = tk.StringVar()
        tk.Label(self, textvariable=self._show_info_var, anchor="w",
                 fg="#225522", font=("TkDefaultFont", 9, "bold"),
                 ).pack(fill=tk.X, padx=10, pady=(0, 1))

        # --- Show scope ---
        # Without this the matcher sees EVERY episode in the library and
        # matches by season/episode number, so one show's S1E1 can grab
        # another show's S01E01. Matching must be scoped to one show.
        show_row = tk.Frame(self)
        show_row.pack(fill=tk.X, padx=10, pady=(0, 2))
        tk.Label(show_row, text="Match against show:").pack(side=tk.LEFT)
        self._show_var = tk.StringVar(value="")
        self._show_cb = ttk.Combobox(show_row, textvariable=self._show_var,
                                     state="readonly", width=42)
        self._show_cb.pack(side=tk.LEFT, padx=(6, 6))
        self._show_cb.bind("<<ComboboxSelected>>",
                           lambda e: self._on_show_changed())
        tk.Label(show_row, text="episodes are matched only within this show",
                 fg="#666666", font=("TkDefaultFont", 8)).pack(side=tk.LEFT)
        self._populate_show_list()

        self._status_var = tk.StringVar(value="Paste a TVMaze show URL above and click Fetch.")
        tk.Label(self, textvariable=self._status_var, anchor="w",
                 fg="#444444", font=("TkDefaultFont", 9, "italic"),
                 ).pack(fill=tk.X, padx=10, pady=(0, 4))

        # treeview
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 4))

        cols   = ("s", "ep", "title", "air_date", "matched_file", "match")
        hdrs   = ("S", "Ep", "TVMaze Title", "Air Date", "Matched File", "Match")
        widths = (28, 32, 230, 82, 230, 70)

        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                   selectmode="browse")
        for col, hdr, w in zip(cols, hdrs, widths):
            self._tree.heading(col, text=hdr)
            self._tree.column(col, width=w, minwidth=20, stretch=(col == "title"))

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,   command=self._tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._tree.tag_configure("num",     background="#d4edda")
        self._tree.tag_configure("title",   background="#fff3cd")
        self._tree.tag_configure("none",    background="#f8d7da")
        self._tree.tag_configure("no_date", foreground="#888888")

        # bottom bar
        bottom = tk.Frame(self, relief=tk.GROOVE, bd=1)
        bottom.pack(fill=tk.X, padx=10, pady=(0, 10))

        self._summary_var = tk.StringVar()
        tk.Label(bottom, textvariable=self._summary_var, anchor="w",
                 fg="#333333", font=("TkDefaultFont", 9),
                 ).pack(side=tk.LEFT, padx=8, pady=6)

        self._btn_apply = tk.Button(
            bottom, text="Apply to Database", command=self._apply,
            padx=10, pady=4, fg="white", bg="#225522",
            activebackground="#336633", state=tk.DISABLED,
        )
        self._btn_apply.pack(side=tk.RIGHT, padx=8, pady=6)

    # -----------------------------------------------------------------------
    # Fetch
    # -----------------------------------------------------------------------

    def _fetch(self) -> None:
        url = self._url_var.get().strip()
        if not url:
            messagebox.showwarning("No URL", "Please paste a TVMaze show URL.", parent=self)
            return

        show_id = extract_show_id(url)
        if show_id is None:
            messagebox.showerror(
                "Invalid URL",
                "Could not find a TVMaze show ID in that URL.\n\n"
                "Expected format:\n"
                "https://www.tvmaze.com/shows/12345/show-name/episodes",
                parent=self,
            )
            return

        self._btn_fetch.config(state=tk.DISABLED)
        self._show_info_var.set("")
        self._status_var.set(f"Fetching show {show_id} from TVMaze API…")
        self._tree.delete(*self._tree.get_children())
        self._summary_var.set("")
        self._btn_apply.config(state=tk.DISABLED)
        self.update_idletasks()

        def _worker() -> None:
            try:
                info     = fetch_show_info(show_id)
                episodes = fetch_episodes(show_id)
                self.after(0, lambda: self._on_fetch_done(info, episodes))
            except urllib.error.HTTPError as exc:
                msg = (
                    f"Show ID {show_id} was not found on TVMaze."
                    if exc.code == 404
                    else f"TVMaze API returned HTTP {exc.code}: {exc.reason}"
                )
                self.after(0, lambda: self._on_fetch_error(msg))
            except Exception as exc:
                self.after(0, lambda: self._on_fetch_error(str(exc)))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_fetch_done(self, info: dict, episodes) -> None:
        self._btn_fetch.config(state=tk.NORMAL)

        show_name = info.get("name", "Unknown")
        network   = (
            (info.get("network")    or {}).get("name") or
            (info.get("webChannel") or {}).get("name") or ""
        )
        premiered = info.get("premiered") or ""
        parts = [show_name]
        if network:
            parts.append(network)
        if premiered:
            parts.append(f"premiered {premiered}")
        self._show_info_var.set("  ·  ".join(parts))

        # Kept so changing the show selector re-matches without re-fetching.
        self._tvm_eps = episodes
        self._match_and_show(episodes)

    def _match_and_show(self, episodes) -> None:
        seasons = len({e.season for e in episodes})
        scope = self._show_var.get() or "local files"
        self._status_var.set(
            f"Found {len(episodes)} episodes across {seasons} season(s). "
            f"Matching against {scope}…"
        )
        self.update_idletasks()

        local_files   = self._collect_local_files()
        self._results = match_to_files(episodes, local_files)
        self._populate_tree()

    def _on_fetch_error(self, msg: str) -> None:
        self._btn_fetch.config(state=tk.NORMAL)
        self._status_var.set("Fetch failed — see error dialog.")
        messagebox.showerror(
            "Fetch Error",
            f"Could not retrieve data from TVMaze:\n\n{msg}\n\n"
            "Check your internet connection and that the URL points to a valid show.",
            parent=self,
        )

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    _ALL_SHOWS = "(all shows — not recommended)"

    def _populate_show_list(self) -> None:
        """Fill the show selector, defaulting to the Library tab's selection.

        Lists TOP-LEVEL shows so a show split into Season 1..N subfolders is
        selectable as one unit (a TVMaze listing covers the whole run).
        """
        root = getattr(self._app, "_root_folder", None)
        self._show_dirs: dict[str, Path] = {}
        if root:
            try:
                for _kind, d in list_top_level(root):
                    self._show_dirs[d.name] = d
            except Exception:
                for d in list_shows(root):
                    self._show_dirs[d.name] = d
        names = sorted(self._show_dirs) + [self._ALL_SHOWS]
        self._show_cb.config(values=names)

        default = ""
        try:
            kind, path = self._app._selected_item()
            if kind in ("show", "episode", "category") and path and root:
                p = Path(path).resolve()
                for k, d in self._show_dirs.items():
                    dr = d.resolve()
                    if p == dr or dr in p.parents:
                        default = k
                        break
        except Exception:
            pass
        self._show_var.set(default or (names[0] if len(names) > 1
                                       else self._ALL_SHOWS))

    def _on_show_changed(self) -> None:
        """Re-match already-fetched TVMaze data against the new show."""
        if getattr(self, "_tvm_eps", None):
            self._match_and_show(self._tvm_eps)

    def _collect_local_files(self) -> list[Path]:
        root = getattr(self._app, "_root_folder", None)
        if not root:
            return []
        chosen = self._show_var.get()
        target = getattr(self, "_show_dirs", {}).get(chosen)
        files: list[Path] = []
        for show_dir in list_shows(root):
            if target is not None and chosen != self._ALL_SHOWS:
                if not (show_dir == target or target in show_dir.parents):
                    continue
            files.extend(list_episodes(show_dir))
        return files

    def _populate_tree(self) -> None:
        self._tree.delete(*self._tree.get_children())
        n_num = n_title = n_none = n_no_date = 0

        for r in self._results:
            wep       = r.wiki_ep
            file_name = r.local_file.name if r.local_file else "—"
            match_label = {
                "number": "● number",
                "title":  "◐ title",
                "none":   "✗ none",
            }.get(r.match_type, r.match_type)
            if r.match_type == "title":
                match_label += f" ({int(r.score * 100)}%)"

            air_disp = wep.air_date or "(no date)"
            tag = r.match_type
            if not wep.air_date:
                tag = "no_date"
                n_no_date += 1
            elif r.match_type == "number":
                n_num += 1
            elif r.match_type == "title":
                n_title += 1
            else:
                n_none += 1

            self._tree.insert("", tk.END, tags=(tag,), values=(
                wep.season, wep.episode_num, wep.title,
                air_disp, file_name, match_label,
            ))

        total   = len(self._results)
        seasons = len({r.wiki_ep.season for r in self._results})
        self._summary_var.set(
            f"● {n_num} by episode number   ◐ {n_title} by title   "
            f"✗ {n_none} unmatched   (no date: {n_no_date})"
        )
        self._btn_apply.config(
            state=tk.NORMAL if (n_num + n_title) > 0 else tk.DISABLED
        )
        self._status_var.set(
            f"Matched {n_num + n_title} of {total} episodes across {seasons} season(s). "
            "Review above, then click Apply."
        )

    # -----------------------------------------------------------------------
    # Apply
    # -----------------------------------------------------------------------

    def _apply(self) -> None:
        if not self._results:
            return
        db = getattr(self._app, "_db_conn", None)
        if not db:
            messagebox.showwarning(
                "No database",
                "No root folder is loaded — open a root folder first.",
                parent=self,
            )
            return

        applied = skipped = 0
        for r in self._results:
            if r.local_file is None or r.match_type == "none" or not r.wiki_ep.air_date:
                skipped += 1
                continue
            upsert_episode_metadata(
                db, str(r.local_file),
                r.wiki_ep.air_date,
                r.wiki_ep.season,
                r.wiki_ep.episode_num,
            )
            applied += 1

        if hasattr(self._app, "_refresh_index"):
            self._app._refresh_index()

        messagebox.showinfo(
            "Done",
            f"Applied metadata to {applied} episode(s).\n"
            f"{skipped} skipped (no match or no air date).",
            parent=self,
        )
        self._status_var.set(f"Applied to {applied} episodes.  {skipped} skipped.")
        self._btn_apply.config(state=tk.DISABLED)
