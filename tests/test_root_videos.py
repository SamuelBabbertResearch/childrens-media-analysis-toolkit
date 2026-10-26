"""Direct-root stimuli must survive the sampler → cache → Library/Index path."""
import csv

from analyzer.cache import save_cache
from analyzer.schema import EpisodeResult
from analyzer.show_index import (
    db_show_key, display_show_name, list_shows, list_top_level, show_key,
)


def _cache(root, folder, name, cuts):
    path = folder / name
    path.write_bytes(b"")
    result = EpisodeResult(file=name, status="ok", duration_sec=60)
    result.metrics.scene_pacing.cuts_per_min = cuts
    save_cache(root, show_key(root, folder), path.stem, result.to_dict())
    return path


def test_flat_root_and_nested_shows_are_both_discovered(tmp_path):
    root = tmp_path / "Library"
    nested = root / "Show"
    category = root / "Category" / "Other show"
    nested.mkdir(parents=True)
    category.mkdir(parents=True)
    _cache(root, root, "Root.MP4", 3)
    _cache(root, nested, "Nested.mkv", 8)
    _cache(root, category, "Categorized.mov", 12)
    assert list_top_level(root) == [
        ("show", root), ("category", category.parent), ("show", nested)]
    assert list_shows(root) == [root, category, nested]
    assert show_key(root, root) == "."
    assert db_show_key(root, root) == "."


def test_root_named_like_a_season_keeps_its_own_identity(tmp_path):
    root = tmp_path / "Season 1"
    root.mkdir()
    _cache(root, root, "Baby.mp4", 3)
    assert display_show_name(root, root) == ("Season 1", None)
    assert db_show_key(root, root) == "."


def test_qt_reopens_and_indexes_existing_root_results_then_refreshes_new_run(
        qapp, monkeypatch, tmp_path):
    from ui import main_window
    from analyzer.db import get_db, query_episodes
    from analyzer.scope import scope_from_draw

    monkeypatch.setattr(main_window, "get_pref", lambda *a, **k: False)
    root = tmp_path / "Stimuli"
    root.mkdir()
    paths = [_cache(root, root, name, cuts) for name, cuts in
             [("Baby.mp4", 3), ("Cocomelon.mp4", 18.5), ("Kid.mp4", 13.1)]]
    original = {p: p.read_bytes() for p in (root / ".analysis").glob("*.json")}
    win = main_window.MainWindow()
    try:
        win.set_root(root)
        assert win._model.rowCount() == 1
        head = win._model.item(0)
        assert win._show_dir_for(head) == root
        assert head.rowCount() == 3
        assert all(head.child(i, 1).text() == "Analyzed" for i in range(3))
        assert win._index._table.topLevelItemCount() == 3

        paths.append(_cache(root, root, "Inscapes1.mp4", 0))
        win._on_analysis_finished()
        assert win._model.item(0).rowCount() == 4
        assert win._index._table.topLevelItemCount() == 4
        conn = get_db(root)
        try:
            rows = query_episodes(conn)
            assert {r["file_name"]: r["cuts_per_min"] for r in rows} == {
                "Baby.mp4": 3, "Cocomelon.mp4": 18.5,
                "Kid.mp4": 13.1, "Inscapes1.mp4": 0}
            assert {r["show_key"] for r in rows} == {"."}
        finally:
            conn.close()
        # Scope filtering and the root-folder report must use the real path,
        # not root/root.name. Cache bytes and original measurement stay intact.
        win._show_report(root, root.name)
        assert win._export_show[0] == root.name
        draw = tmp_path / "draw"
        draw.mkdir()
        with (draw / "selected.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=["filepath"])
            writer.writeheader()
            writer.writerow({"filepath": str(paths[0])})
        win.set_scope(scope_from_draw("draw", "Selected stimuli", draw))
        assert win._model.item(0).rowCount() == 1
        assert win._index._table.topLevelItemCount() == 1
        assert "not shown" not in win._scope_note.text()
        for path, data in original.items():
            assert path.read_bytes() == data
    finally:
        win.close()
        win.deleteLater()
