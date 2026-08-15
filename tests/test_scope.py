"""
The research context: which episodes the application is working on.

These assert on the SET OF EPISODES a scope admits and on the rows the Library
actually builds — not on whether the chooser exists. A scope control that is
present and filters nothing is the shape of defect this project keeps finding
(`LEARNINGS.md` § *A control that exists is not a feature that works*), and it
would look completely correct on screen.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from analyzer.scope import (
    LIBRARY_KEY, library_scope, normalize, read_selected, scope_from_draw,
    scope_from_pipeline,
)


# --- fixtures ----------------------------------------------------------------

def _make_library(tmp_path: Path) -> Path:
    """A root with two shows, three episodes each."""
    root = tmp_path / "Library"
    for show, count in (("Little Bear", 3), ("Curious George", 3)):
        d = root / show
        d.mkdir(parents=True)
        for i in range(1, count + 1):
            (d / f"S01 E{i:02d}.mp4").write_bytes(b"")
    return root


def _make_draw(tmp_path: Path, episodes: list[Path], name: str = "draw") -> Path:
    """A sampler-shaped output folder: selected.csv with a filepath column."""
    folder = tmp_path / name
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "selected.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["entry_id", "season", "episode", "title",
                            "air_date", "filepath"])
        writer.writeheader()
        for i, ep in enumerate(episodes, start=1):
            writer.writerow({"entry_id": "Show", "season": 1, "episode": i,
                             "title": "", "air_date": "",
                             "filepath": str(ep)})
    return folder


# --- the scope itself --------------------------------------------------------

def test_library_scope_admits_everything():
    scope = library_scope()
    assert scope.is_library
    assert scope.key == LIBRARY_KEY
    assert scope.contains(Path("anything/at/all.mp4"))


def test_a_draw_admits_only_its_own_episodes(tmp_path):
    root = _make_library(tmp_path)
    drawn = [root / "Little Bear" / "S01 E01.mp4",
             root / "Little Bear" / "S01 E03.mp4"]
    folder = _make_draw(tmp_path, drawn)

    scope = scope_from_draw("sample:x", "Pilot", folder)

    assert len(scope.episodes) == 2
    assert scope.contains(root / "Little Bear" / "S01 E01.mp4")
    assert scope.contains(root / "Little Bear" / "S01 E03.mp4")
    # The one that was not drawn, and a whole show that was not sampled.
    assert not scope.contains(root / "Little Bear" / "S01 E02.mp4")
    assert not scope.contains(root / "Curious George" / "S01 E01.mp4")


def test_membership_survives_a_different_spelling_of_the_same_path(tmp_path):
    """selected.csv and the library walk produce two spellings of one path.

    This is `LEARNINGS.md` § *The sampler's CSV paths did not match the cache's
    keys* — the same defect, one layer up. Without normalising at the choke
    point the scope silently admits nothing and the Library looks empty.
    """
    root = _make_library(tmp_path)
    episode = root / "Little Bear" / "S01 E01.mp4"
    folder = _make_draw(tmp_path, [episode])

    scope = scope_from_draw("sample:x", "Pilot", folder)

    # Same file, reached through a redundant "." and a parent hop.
    awkward = root / "Little Bear" / "." / ".." / "Little Bear" / "S01 E01.mp4"
    assert scope.contains(awkward)
    assert normalize(awkward) == normalize(episode)


def test_a_missing_file_is_reported_not_dropped(tmp_path):
    """A sample that has lost files is a different study from a smaller one."""
    root = _make_library(tmp_path)
    present = root / "Little Bear" / "S01 E01.mp4"
    gone = root / "Little Bear" / "S01 E99.mp4"        # never created
    folder = _make_draw(tmp_path, [present, gone])

    scope = scope_from_draw("sample:x", "Pilot", folder)

    assert len(scope.episodes) == 1
    assert len(scope.missing) == 1
    assert scope.total_drawn == 2
    assert "1 missing from disk" in scope.describe()


def test_a_draw_with_no_csv_is_empty_rather_than_an_error(tmp_path):
    folder = tmp_path / "empty_draw"
    folder.mkdir()
    scope = scope_from_draw("sample:x", "Pilot", folder)
    assert scope.episodes == ()
    assert read_selected(folder) == []


def test_the_synthetic_pipeline_is_refused_as_a_scope():
    """Its episode paths are `<stem>.mp4` placeholders that resolve to nothing.

    Offering it would give an empty Library indistinguishable from a sample
    whose files had all gone missing.
    """
    class FakePipeline:
        key = "unsampled"
        name = "Unsampled work"
        is_synthetic = True
        folder = None

    assert scope_from_pipeline(FakePipeline()) is None


# --- the Library actually filters --------------------------------------------

def _library_rows(window) -> list[str]:
    """Every episode name currently in the Library tree."""
    names: list[str] = []

    def walk(item):
        for r in range(item.rowCount()):
            child = item.child(r, 0)
            if child is None:
                continue
            if child.data(0x0100):        # Qt.UserRole — an episode payload
                names.append(child.text())
            walk(child)

    model = window._model
    for r in range(model.rowCount()):
        top = model.item(r, 0)
        if top is not None:
            walk(top)
    return names


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    """A MainWindow on a temp library, with no welcome dialog and no prefs."""
    from analyzer import prefs
    monkeypatch.setattr(prefs, "get_pref", lambda k, d=None: None)
    monkeypatch.setattr(prefs, "set_pref", lambda k, v: None)
    import ui.main_window as mw
    monkeypatch.setattr(mw, "get_pref", lambda k, d=None: None)
    monkeypatch.setattr(mw, "set_pref", lambda k, v: None)
    win = mw.MainWindow()
    yield win
    win.close()


def test_the_library_lists_everything_by_default(window, tmp_path):
    """The application opens on the whole library. Non-negotiable per the ask."""
    root = _make_library(tmp_path)
    window.set_root(root)

    assert window._scope.is_library
    assert len(_library_rows(window)) == 6


def test_setting_a_sample_scope_narrows_the_library(window, tmp_path):
    root = _make_library(tmp_path)
    window.set_root(root)
    drawn = [root / "Little Bear" / "S01 E01.mp4",
             root / "Little Bear" / "S01 E03.mp4"]
    folder = _make_draw(tmp_path, drawn)

    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))

    rows = _library_rows(window)
    assert sorted(rows) == ["S01 E01.mp4", "S01 E03.mp4"]
    # The unsampled show is gone entirely, not shown as an empty folder.
    assert "Curious George" not in _tree_text(window)


def test_returning_to_the_whole_library_restores_every_episode(window, tmp_path):
    root = _make_library(tmp_path)
    window.set_root(root)
    folder = _make_draw(tmp_path, [root / "Little Bear" / "S01 E01.mp4"])

    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))
    assert len(_library_rows(window)) == 1

    window.set_scope(library_scope())
    assert len(_library_rows(window)) == 6


def test_the_chooser_offers_the_current_scope_even_before_discovery(
        window, tmp_path):
    """A sample written moments ago is not yet a discovered trial.

    If the chooser dropped it, the control would say "Whole library" while the
    tree showed two episodes — the one failure this control must not have.
    """
    root = _make_library(tmp_path)
    window.set_root(root)
    folder = _make_draw(tmp_path, [root / "Little Bear" / "S01 E01.mp4"],
                        name="fresh_draw")

    window.set_scope(scope_from_draw(f"sample:{folder}", "Fresh", folder))

    labels = [window._scope_pick.itemText(i)
              for i in range(window._scope_pick.count())]
    assert any("Fresh" in label for label in labels)
    assert window._scope_pick.currentIndex() != 0
    assert not window._scope.is_library


def test_the_note_accounts_for_every_drawn_episode(window, tmp_path):
    """The header said "9 episodes" over 8 rows against the real library.

    That particular gap was the `.mkv` one, closed by giving the sampler and
    the library one extension set. The invariant outlives it: a draw can still
    hold an episode the tree cannot show — here one from OUTSIDE the library
    root, which the real index also contains. Whatever the reason,
    drawn = shown + missing + not-listable must reconcile on screen, or the
    count is a wrong number that displays correctly.
    """
    root = _make_library(tmp_path)
    outside = tmp_path / "Elsewhere"
    outside.mkdir()
    stray = outside / "Ocean Waves 1993.mp4"
    stray.write_bytes(b"")                  # exists, but not under the root
    drawn = [root / "Little Bear" / "S01 E01.mp4", stray]
    folder = _make_draw(tmp_path, drawn)

    window.set_root(root)
    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))

    assert len(_library_rows(window)) == 1
    note = window._scope_note.text()
    assert "2 episodes this sample drew" in note
    assert "1 not shown here" in note


def test_a_drawn_mkv_now_appears_in_the_library(window, tmp_path):
    """The original defect, pinned: it was drawn, measured, indexed, invisible."""
    root = _make_library(tmp_path)
    mkv = root / "Little Bear" / "S01 E04.mkv"
    mkv.write_bytes(b"")
    folder = _make_draw(tmp_path, [root / "Little Bear" / "S01 E01.mp4", mkv])

    window.set_root(root)
    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))

    assert sorted(_library_rows(window)) == ["S01 E01.mp4", "S01 E04.mkv"]
    assert "not shown here" not in window._scope_note.text()


def _tree_text(window) -> str:
    model = window._model
    out = []

    def walk(item):
        for r in range(item.rowCount()):
            child = item.child(r, 0)
            if child is not None:
                out.append(child.text())
                walk(child)

    for r in range(model.rowCount()):
        top = model.item(r, 0)
        if top is not None:
            out.append(top.text())
            walk(top)
    return "\n".join(out)


# --- the sampler hands its draw to the scope ---------------------------------

def test_drawing_a_sample_makes_it_the_current_scope(window, tmp_path,
                                                     monkeypatch):
    """The promise of the whole change: draw a sample, the Library follows.

    Driven through the real dialog rather than by asserting on MainWindow's
    source, because the handoff is an attribute the dialog has to actually set
    — `written_dir` — and a source-text check would pass with it unset.
    """
    from PySide6.QtWidgets import QDialog
    import ui.main_window as mw
    from ui.sampler import SamplerDialog

    root = _make_library(tmp_path)
    window.set_root(root)
    assert window._scope.is_library

    show = root / "Little Bear"
    drawn_paths: dict = {}

    def fake_exec(dialog_self):
        """Load the show, draw a census, and write it — no user interaction."""
        from analyzer.sampler import scan_entry_root
        dialog_self._folder = show
        dialog_self._episodes = scan_entry_root(show)
        # The method lives in the item's DATA; its text is a human label, so
        # setCurrentText("census") silently selects nothing and the draw
        # quietly uses the default method instead.
        dialog_self._method.setCurrentIndex(
            dialog_self._method.findData("census"))
        dialog_self._write()
        drawn_paths["dir"] = dialog_self.written_dir
        return QDialog.Accepted

    monkeypatch.setattr(SamplerDialog, "exec", fake_exec)
    window.open_sampler()

    assert drawn_paths["dir"] is not None, "the dialog did not report its draw"
    assert not window._scope.is_library, \
        "the Library stayed on the whole library after a draw"
    assert window._scope.folder == drawn_paths["dir"]
    # A census of a three-episode show, and the tree shows exactly those three
    # — compared against the draw itself rather than a literal, so the test
    # fails on a scope/tree disagreement rather than on the sampler's defaults.
    assert len(window._scope.episodes) == 3
    assert sorted(_library_rows(window)) == \
        sorted(p.name for p in window._scope.episodes)
    # The unsampled show is gone.
    assert "Curious George" not in _tree_text(window)
    # And the chooser agrees with the tree.
    assert window._scope_pick.currentIndex() != 0


# --- one definition of "episode" ---------------------------------------------

def test_the_sampler_and_the_library_agree_on_what_an_episode_is():
    """They did not, and a drawn `.mkv` was invisible in the Library.

    Asserting equality rather than reading either list: the point is that
    there is one definition, so this fails the moment someone adds an
    extension to one side.
    """
    from analyzer.sampler import _DEFAULT_VIDEO_EXTENSIONS
    from analyzer.show_index import VIDEO_EXTENSIONS
    assert set(_DEFAULT_VIDEO_EXTENSIONS) == set(VIDEO_EXTENSIONS)


def test_the_library_lists_every_extension_the_sampler_draws(tmp_path):
    from analyzer.show_index import (
        VIDEO_EXTENSIONS, list_episodes, list_shows, list_top_level,
    )
    root = tmp_path / "Root"
    show = root / "Show"
    show.mkdir(parents=True)
    for i, ext in enumerate(sorted(VIDEO_EXTENSIONS), start=1):
        (show / f"S01 E{i:02d}{ext}").write_bytes(b"")
    (show / "notes.txt").write_bytes(b"")          # not a video

    assert len(list_episodes(show)) == len(VIDEO_EXTENSIONS)
    assert [kind for kind, _p in list_top_level(root)] == ["show"]
    assert list_shows(root) == [show]


def test_a_show_folder_holding_no_mp4_is_still_a_show(tmp_path):
    """It was not: a folder of .mkv files was invisible at every level."""
    from analyzer.show_index import list_episodes, list_shows, list_top_level
    root = tmp_path / "Root"
    show = root / "MKV Only"
    show.mkdir(parents=True)
    (show / "S01 E01.mkv").write_bytes(b"")

    assert list_top_level(root) == [("show", show)]
    assert list_shows(root) == [show]
    assert [p.name for p in list_episodes(show)] == ["S01 E01.mkv"]


def test_extension_matching_ignores_case(tmp_path):
    """`glob("*.mp4")` is case-sensitive on Linux and not on Windows.

    The same library would list differently depending on where it was opened.
    """
    from analyzer.show_index import list_episodes
    show = tmp_path / "Show"
    show.mkdir()
    (show / "LOUD.MP4").write_bytes(b"")
    (show / "quiet.mp4").write_bytes(b"")
    assert len(list_episodes(show)) == 2
