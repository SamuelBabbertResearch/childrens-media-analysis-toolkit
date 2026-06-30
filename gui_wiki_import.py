"""
Wikipedia episode-metadata import dialog for CMAT.

Lets the user point to a locally-saved Wikipedia "List of X episodes"
HTML page, previews how Wikipedia episodes map to local MP4 files,
and writes air dates (plus season/episode numbers) into the index DB.
"""

from __future__ import annotations
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from analyzer.db import upsert_episode_metadata, auto_set_season
from analyzer.show_index import list_shows, list_episodes
from analyzer.wiki_importer import (
    WikiEpisode, MatchResult,
    parse_wikipedia_episode_list, match_to_files,
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
            "How to use:\n"
            "1. Open the Wikipedia 'List of [Show] episodes' page in your browser.\n"
            "2. Save the full page as HTML (Ctrl+S → 'Webpage, Complete' or 'Web Page, HTML Only').\n"
            "3. Browse to the saved .html file below.\n"
            "4. Review the matched episodes, then click Apply to write air dates to the database."
        )
        tk.Label(self, text=instr, justify=tk.LEFT, anchor="w",
                 bg="#eef4ff", relief=tk.GROOVE, padx=10, pady=6,
                 font=("TkDefaultFont", 9)).pack(fill=tk.X, padx=10, pady=(10, 4))

        # --- File chooser row ---
        file_row = tk.Frame(self)
        file_row.pack(fill=tk.X, **pad)
        tk.Button(file_row, text="Browse for Wikipedia HTML…",
                  command=self._browse_html, padx=6).pack(side=tk.LEFT)
        self._file_var = tk.StringVar(value="No file loaded")
        tk.Label(file_row, textvariable=self._file_var, fg="#444444",
                 anchor="w").pack(side=tk.LEFT, padx=(10, 0))

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

    def _load_html(self, html_path: Path) -> None:
        self._file_var.set(str(html_path))
        self._status_var.set("Parsing…")
        self.update_idletasks()

        try:
            wiki_eps = parse_wikipedia_episode_list(html_path)
        except Exception as exc:
            messagebox.showerror("Parse error",
                                 f"Could not parse the HTML file:\n{exc}", parent=self)
            self._status_var.set("Parse failed — see error dialog.")
            return

        if not wiki_eps:
            messagebox.showwarning(
                "No episodes found",
                "No episode data was found in this HTML file.\n\n"
                "Make sure you saved the full Wikipedia 'List of X episodes' page\n"
                "(not just the article text).",
                parent=self,
            )
            self._status_var.set("No episodes found in file.")
            return

        seasons = len({e.season for e in wiki_eps})
        self._status_var.set(
            f"Found {len(wiki_eps)} episodes across {seasons} season(s). "
            f"Scanning library for local files…"
        )
        self.update_idletasks()

        # Collect all local MP4 files from root folder
        local_files = self._collect_local_files()
        self._results = match_to_files(wiki_eps, local_files)
        self._populate_tree()

    def _collect_local_files(self) -> list[Path]:
        root = getattr(self._app, "_root_folder", None)
        if not root:
            return []
        files: list[Path] = []
        for show_dir in list_shows(root):
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
