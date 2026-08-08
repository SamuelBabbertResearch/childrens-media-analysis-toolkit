"""
Wikipedia episode-metadata import dialog for CMAT.

Lets the user point to a locally-saved Wikipedia "List of X episodes"
HTML page, previews how Wikipedia episodes map to local MP4 files,
and writes air dates (plus season/episode numbers) into the index DB.
"""

from __future__ import annotations
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from analyzer.db import upsert_episode_metadata, auto_set_season
from analyzer.show_index import (list_shows, list_episodes, list_top_level,
                                  show_key)
from analyzer.wiki_importer import (
    WikiEpisode, MatchResult,
    parse_wikipedia_episode_list, parse_wikipedia_html,
    fetch_wikipedia_html, match_to_files,
)


class WikiImportDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, app_ref):
        super().__init__(parent)
        self.title("Import Episode Metadata from Wikipedia")
        self.resizable(True, True)
        self.minsize(860, 520)
        self._app = app_ref
        self._results: list[MatchResult] = []

        self._build_ui()
        self.transient(parent)
        self.grab_set()

        # Centre on parent
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2 - self.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2 - self.winfo_height() // 2
        self.geometry(f"+{max(0, px)}+{max(0, py)}")

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self) -> None:
        pad = dict(padx=10, pady=6)

        # --- Instructions ---
        instr = (
            "How to use — either way works:\n"
            "  • Paste the Wikipedia 'List of [Show] episodes' page URL below and click Fetch, or\n"
            "  • Save the page as HTML in your browser (Ctrl+S) and browse to the file.\n"
            "Then review the matched episodes and click Apply to write air dates to the database."
        )
        tk.Label(self, text=instr, justify=tk.LEFT, anchor="w",
                 bg="#eef4ff", relief=tk.GROOVE, padx=10, pady=6,
                 font=("TkDefaultFont", 9)).pack(fill=tk.X, padx=10, pady=(10, 4))

        # --- URL row ---
        url_row = tk.Frame(self)
        url_row.pack(fill=tk.X, padx=10, pady=(4, 0))
        tk.Label(url_row, text="Wikipedia URL:").pack(side=tk.LEFT)
        self._url_var = tk.StringVar(value="")
        url_entry = tk.Entry(url_row, textvariable=self._url_var)
        url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 6))
        url_entry.bind("<Return>", lambda e: self._fetch_url())
        self._btn_fetch = tk.Button(url_row, text="Fetch",
                                    command=self._fetch_url, padx=10)
        self._btn_fetch.pack(side=tk.LEFT)
        tk.Label(self,
                 text="e.g. https://en.wikipedia.org/wiki/List_of_Little_Bear_episodes"
                      "   —   only wikipedia.org links are accepted.",
                 fg="#666666", font=("TkDefaultFont", 8),
                 anchor="w").pack(fill=tk.X, padx=10)

        # --- File chooser row ---
        file_row = tk.Frame(self)
        file_row.pack(fill=tk.X, **pad)
        tk.Button(file_row, text="…or browse for saved HTML",
                  command=self._browse_html, padx=6).pack(side=tk.LEFT)
        self._file_var = tk.StringVar(value="No file loaded")
        tk.Label(file_row, textvariable=self._file_var, fg="#444444",
                 anchor="w").pack(side=tk.LEFT, padx=(10, 0))

        # --- Show scope ---
        # Without this the matcher sees EVERY episode in the library and
        # matches by season/episode number, so e.g. Little Bear S1E1 grabs
        # SpongeBob's S01E01. Matching must be scoped to one show.
        show_row = tk.Frame(self)
        show_row.pack(fill=tk.X, padx=10, pady=(0, 2))
        tk.Label(show_row, text="Match against show:").pack(side=tk.LEFT)
        self._show_var = tk.StringVar(value="")
        self._show_cb = ttk.Combobox(show_row, textvariable=self._show_var,
                                     state="readonly", width=42)
        self._show_cb.pack(side=tk.LEFT, padx=(6, 6))
        self._show_cb.bind("<<ComboboxSelected>>",
                           lambda e: self._on_show_changed())
        tk.Label(show_row,
                 text="episodes are matched only within this show",
                 fg="#666666", font=("TkDefaultFont", 8)).pack(side=tk.LEFT)
        self._populate_show_list()

        # --- Status ---
        self._status_var = tk.StringVar(value="Load a Wikipedia HTML file to begin.")
        tk.Label(self, textvariable=self._status_var, anchor="w",
                 fg="#225522", font=("TkDefaultFont", 9, "italic")).pack(
            fill=tk.X, padx=10, pady=(0, 4))

        # --- Preview treeview ---
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 4))

        cols = ("s", "ep", "wiki_title", "air_date", "matched_file", "match")
        hdrs = ("S", "Ep", "Wikipedia Title", "Air Date", "Matched File", "Match")
        widths = (28, 32, 230, 82, 230, 70)

        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                   selectmode="browse")
        for col, hdr, w in zip(cols, hdrs, widths):
            self._tree.heading(col, text=hdr)
            self._tree.column(col, width=w, minwidth=20, stretch=(col == "wiki_title"))

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._tree.tag_configure("num",      background="#d4edda")  # green
        self._tree.tag_configure("title",    background="#fff3cd")  # yellow
        self._tree.tag_configure("none",     background="#f8d7da")  # red
        self._tree.tag_configure("no_date",  foreground="#888888")

        # --- Bottom bar ---
        bottom = tk.Frame(self, relief=tk.GROOVE, bd=1)
        bottom.pack(fill=tk.X, padx=10, pady=(0, 10))

        self._summary_var = tk.StringVar()
        tk.Label(bottom, textvariable=self._summary_var, anchor="w",
                 fg="#333333", font=("TkDefaultFont", 9)).pack(side=tk.LEFT, padx=8, pady=6)

        self._btn_apply = tk.Button(
            bottom, text="Apply to Database",
            command=self._apply, padx=10, pady=4,
            fg="white", bg="#225522", activebackground="#336633",
            state=tk.DISABLED,
        )
        self._btn_apply.pack(side=tk.RIGHT, padx=8, pady=6)

    # -----------------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------------

    def _browse_html(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Select saved Wikipedia HTML file",
            filetypes=[("HTML files", "*.html *.htm"), ("All files", "*.*")],
        )
        if not path:
            return
        self._load_html(Path(path))

    def _fetch_url(self) -> None:
        """Fetch a pasted Wikipedia URL on a worker thread (never block the UI)."""
        url = self._url_var.get().strip()
        if not url:
            messagebox.showinfo("No URL",
                                "Paste a Wikipedia episode-list URL first.",
                                parent=self)
            return
        self._btn_fetch.config(state=tk.DISABLED)
        self._status_var.set("Fetching from Wikipedia…")
        self.update_idletasks()

        def worker() -> None:
            try:
                html = fetch_wikipedia_html(url)
                self.after(0, lambda: self._on_fetched(url, html))
            except Exception as exc:            # noqa: BLE001
                self.after(0, lambda e=exc: self._on_fetch_error(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_fetch_error(self, exc: Exception) -> None:
        self._btn_fetch.config(state=tk.NORMAL)
        self._status_var.set("Fetch failed — see error dialog.")
        messagebox.showerror(
            "Fetch failed",
            f"Could not fetch that page:\n{exc}\n\n"
            "Check the URL and your connection. You can also save the page as "
            "HTML in your browser and use the browse button instead.",
            parent=self)

    def _on_fetched(self, url: str, html: str) -> None:
        self._btn_fetch.config(state=tk.NORMAL)
        self._file_var.set(f"(fetched) {url}")
        self._parse_and_match(html, source_desc="page")

    def _load_html(self, html_path: Path) -> None:
        self._file_var.set(str(html_path))
        try:
            html = html_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            messagebox.showerror("Read error",
                                 f"Could not read the file:\n{exc}",
                                 parent=self)
            return
        self._url_var.set("")
        self._parse_and_match(html, source_desc="HTML file")

    def _parse_and_match(self, html: str, source_desc: str = "page") -> None:
        """Shared path for both input methods: parse HTML, match to local files."""
        self._status_var.set("Parsing…")
        self.update_idletasks()

        try:
            wiki_eps = parse_wikipedia_html(html)
        except Exception as exc:
            messagebox.showerror("Parse error",
                                 f"Could not parse the {source_desc}:\n{exc}",
                                 parent=self)
            self._status_var.set("Parse failed — see error dialog.")
            return

        if not wiki_eps:
            messagebox.showwarning(
                "No episodes found",
                f"No episode data was found in this {source_desc}.\n\n"
                "Make sure it is a Wikipedia 'List of X episodes' page with\n"
                "episode tables (not just an article about the show).",
                parent=self,
            )
            self._status_var.set(f"No episodes found in {source_desc}.")
            return

        # Kept so changing the show selector re-matches without re-fetching.
        self._wiki_eps = wiki_eps
        self._match_and_show(wiki_eps)

    def _match_and_show(self, wiki_eps: list) -> None:
        seasons = len({e.season for e in wiki_eps})
        scope = self._show_var.get() or "the library"
        self._status_var.set(
            f"Found {len(wiki_eps)} episodes across {seasons} season(s). "
            f"Matching against {scope}…"
        )
        self.update_idletasks()

        local_files = self._collect_local_files()
        self._results = match_to_files(wiki_eps, local_files)
        self._populate_tree()

    _ALL_SHOWS = "(all shows — not recommended)"

    def _populate_show_list(self) -> None:
        """Fill the show selector, defaulting to the Library tab's selection.

        Lists TOP-LEVEL shows, not leaf directories: a show whose episodes live
        in Season 1..N subfolders must be selectable as one unit, since a
        Wikipedia 'List of X episodes' page covers the whole run.
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

        # Default to the Library tree's selection (walk up to its top level).
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
        """Re-match already-loaded Wikipedia data against the new show."""
        if getattr(self, "_wiki_eps", None):
            self._match_and_show(self._wiki_eps)

    def _collect_local_files(self) -> list[Path]:
        root = getattr(self._app, "_root_folder", None)
        if not root:
            return []
        chosen = self._show_var.get()
        target = getattr(self, "_show_dirs", {}).get(chosen)
        files: list[Path] = []
        for show_dir in list_shows(root):
            # Include leaf dirs at or beneath the chosen top-level show, so a
            # show split into Season 1..N folders is gathered as one unit.
            if target is not None and chosen != self._ALL_SHOWS:
                if not (show_dir == target or target in show_dir.parents):
                    continue
            files.extend(list_episodes(show_dir))
        return files

    def _populate_tree(self) -> None:
        self._tree.delete(*self._tree.get_children())
        n_num = n_title = n_none = n_no_date = 0

        for r in self._results:
            wep = r.wiki_ep
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
                wep.season,
                wep.episode_num,
                wep.title,
                air_disp,
                file_name,
                match_label,
            ))

        total = len(self._results)
        self._summary_var.set(
            f"● {n_num} by episode number   ◐ {n_title} by title   "
            f"✗ {n_none} unmatched   (no date: {n_no_date})"
        )
        can_apply = (n_num + n_title) > 0
        self._btn_apply.config(state=tk.NORMAL if can_apply else tk.DISABLED)

        seasons = len({r.wiki_ep.season for r in self._results})
        self._status_var.set(
            f"Matched {n_num + n_title} of {total} episodes across {seasons} season(s). "
            f"Review above, then click Apply."
        )

    def _apply(self) -> None:
        if not self._results:
            return
        db = getattr(self._app, "_db_conn", None)
        if not db:
            messagebox.showwarning("No database",
                                   "No root folder is loaded — open a root folder first.",
                                   parent=self)
            return

        applied = skipped = 0
        for r in self._results:
            if r.local_file is None or r.match_type == "none":
                skipped += 1
                continue
            if not r.wiki_ep.air_date:
                skipped += 1
                continue
            upsert_episode_metadata(
                db,
                str(r.local_file),
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
            f"{skipped} episode(s) were skipped (no match or no air date).",
            parent=self,
        )
        self._status_var.set(f"Applied to {applied} episodes. {skipped} skipped.")
        self._btn_apply.config(state=tk.DISABLED)
