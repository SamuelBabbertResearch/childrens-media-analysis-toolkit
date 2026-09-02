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


# --- the measurement tabs stage the working set ------------------------------
#
# These assert on the QUEUE — the list `_start` actually hands the worker — not
# on whether a label changed. A staging control that stages nothing is exactly
# `LEARNINGS.md` § *A control that exists is not a feature that works*, and it
# would read as correct on screen: a scope named in the header, a note claiming
# a sample, and an empty run.

def _queued(window) -> list[str]:
    """Queue entries as the interface shows them, one per row."""
    view = window._automated._queue_view
    return [view.item(i).toolTip() for i in range(view.count())]


def _would_analyze(window) -> list[Path]:
    """Exactly what `AutomatedTab._start` would hand the worker."""
    tab = window._automated
    return list(tab._queue) or ([tab._target] if tab._target is not None else [])


def test_a_sample_scope_stages_the_analysis_queue(window, tmp_path):
    """The point of the change: arrive with the working set, not empty-handed."""
    root = _make_library(tmp_path)
    window.set_root(root)
    assert _queued(window) == []

    drawn = [root / "Little Bear" / "S01 E01.mp4",
             root / "Little Bear" / "S01 E03.mp4"]
    folder = _make_draw(tmp_path, drawn)
    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))

    assert sorted(_would_analyze(window)) == sorted(normalize(p) for p in drawn)
    assert len(_queued(window)) == 2


def test_the_whole_library_is_not_staged_as_a_work_list(window, tmp_path):
    """137 episodes queued by opening the application is not a working set."""
    root = _make_library(tmp_path)
    window.set_root(root)
    folder = _make_draw(tmp_path, [root / "Little Bear" / "S01 E01.mp4"])

    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))
    assert len(_queued(window)) == 1

    window.set_scope(library_scope())
    assert _queued(window) == []
    assert not window._automated._btn_queue_scope.isEnabled()


def test_switching_scope_withdraws_only_its_own_staging(window, tmp_path):
    """A hand-queued episode is the user's. Nothing here asked to undo it."""
    root = _make_library(tmp_path)
    window.set_root(root)
    a = _make_draw(tmp_path, [root / "Little Bear" / "S01 E01.mp4"], name="a")
    b = _make_draw(tmp_path, [root / "Little Bear" / "S01 E02.mp4"], name="b")

    window.set_scope(scope_from_draw(f"sample:{a}", "A", a))
    by_hand = root / "Curious George" / "S01 E01.mp4"
    window._automated.enqueue([by_hand])

    window.set_scope(scope_from_draw(f"sample:{b}", "B", b))

    queued = _would_analyze(window)
    assert normalize(by_hand) in [normalize(p) for p in queued], \
        "the hand-queued episode was thrown away by a scope change"
    assert normalize(root / "Little Bear" / "S01 E01.mp4") not in \
        [normalize(p) for p in queued], "sample A stayed queued under scope B"
    assert normalize(root / "Little Bear" / "S01 E02.mp4") in \
        [normalize(p) for p in queued]


def test_one_episode_cannot_be_queued_twice_under_two_spellings(window,
                                                                tmp_path):
    """The Library walks the root; selected.csv stores absolute paths.

    Same defect family as the index's two rows per episode — here it would
    mean measuring one file twice inside a single run.
    """
    root = _make_library(tmp_path)
    window.set_root(root)
    episode = root / "Little Bear" / "S01 E01.mp4"
    awkward = root / "Little Bear" / "." / ".." / "Little Bear" / "S01 E01.mp4"
    window._automated.enqueue([awkward])

    folder = _make_draw(tmp_path, [episode])
    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))

    assert len(_would_analyze(window)) == 1


def test_the_staging_note_reconciles_with_the_rows(window, tmp_path):
    """drawn = staged + gone. A note claiming more than the queue holds is the
    wrong number that displays correctly."""
    root = _make_library(tmp_path)
    present = root / "Little Bear" / "S01 E01.mp4"
    gone = root / "Little Bear" / "S01 E99.mp4"        # never created
    folder = _make_draw(tmp_path, [present, gone])
    window.set_root(root)

    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))

    note = window._automated._scope_note.text()
    assert "1 of its 2 episodes" in note
    assert "1 of the draw is no longer on disk" in note
    assert len(_queued(window)) == 1


def test_clearing_the_queue_leaves_the_note_telling_the_truth(window, tmp_path):
    """It described what set_scope intended, so it survived Clear Queue."""
    root = _make_library(tmp_path)
    window.set_root(root)
    folder = _make_draw(tmp_path, [root / "Little Bear" / "S01 E01.mp4"])
    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))

    window._automated.clear_queue()

    note = window._automated._scope_note.text()
    assert "none queued" in note
    assert "Staged from" not in note
    # And the way back is offered, not left to be guessed at.
    assert window._automated._btn_queue_scope.isEnabled()
    window._automated._enqueue_scope()
    assert len(_queued(window)) == 1


def test_a_pipeline_node_lands_on_the_staged_queue(window, tmp_path):
    """The reported symptom: double-click a node, land on an empty screen.

    Driven through `_open_stage_screen` — the method the canvas connects to —
    rather than by asserting the tab exists.
    """
    from analyzer.pipeline_graph import NODE_TYPES

    root = _make_library(tmp_path)
    window.set_root(root)
    folder = _make_draw(tmp_path, [root / "Little Bear" / "S01 E01.mp4",
                                   root / "Little Bear" / "S01 E03.mp4"])
    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))

    kind = next(k for k in NODE_TYPES.values() if k.stage_key == "automated")
    node = type("Node", (), {"id": "n-fake", "type": kind.key,
                             "title": "Automated coding"})()
    window._open_stage_screen(node)

    assert window._tabs.tabText(window._tabs.currentIndex()) == \
        "Automated coding"
    assert len(_would_analyze(window)) == 2
    assert "No episode or show selected" not in \
        window._automated._target_label.text()


# --- Language: one view narrows, the other stages ----------------------------

def _speech_files(window) -> list[str]:
    table = window._language.speech._table
    return [table.topLevelItem(i).text(1)
            for i in range(table.topLevelItemCount())]


def _vocab_files(window) -> list[str]:
    listing = window._language.vocabulary._files
    return [Path(listing.item(i).text()).name
            for i in range(listing.count())]


def _cache_speech(root: Path, episode: Path, words: int) -> None:
    """A cached result carrying speech figures, written the engine's way."""
    from analyzer.cache import save_cache
    from analyzer.show_index import show_key
    save_cache(root, show_key(root, episode.parent), episode.stem, {
        "file": episode.name,
        "status": "ok",
        "duration_sec": 600.0,
        "metrics": {"speech": {"available": True, "source": "captions",
                               "words_per_minute": 120.0,
                               "speech_density": 0.4,
                               "total_words": words}},
    })


def test_the_speech_table_narrows_to_the_context(window, tmp_path):
    """It reports on episodes already measured, so the scope FILTERS it.

    A whole-corpus table under a header naming one sample is the wrong number
    displayed correctly — the same defect the Index's show means had.
    """
    root = _make_library(tmp_path)
    a = root / "Little Bear" / "S01 E01.mp4"
    b = root / "Curious George" / "S01 E01.mp4"
    window.set_root(root)
    _cache_speech(root, a, 1200)
    _cache_speech(root, b, 900)

    speech = window._language.speech
    speech.refresh()
    assert len(_speech_files(window)) == 2

    folder = _make_draw(tmp_path, [a])
    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))

    assert _speech_files(window) == ["S01 E01.mp4"]
    assert "in Pilot" in speech._count.text()
    # Six episodes exist; one is in scope, so five are not counted here.
    assert "5 episodes elsewhere in the library are not counted" in \
        speech._note.text()

    window.set_scope(library_scope())
    assert len(_speech_files(window)) == 2


def test_the_speech_table_is_not_filled_on_startup(window, tmp_path):
    """It walks every show and opens every cached result.

    Refreshing it from `set_root` would put that walk on the cold path — the
    startup cost this project has already paid once for module-scope imports.
    """
    root = _make_library(tmp_path)
    _cache_speech(root, root / "Little Bear" / "S01 E01.mp4", 1200)

    window.set_root(root)

    assert window._language.speech._loaded is False
    assert _speech_files(window) == []


def test_vocabulary_stages_the_captions_beside_the_sample(window, tmp_path):
    """It is where a run is started, so the scope STAGES rather than filters."""
    root = _make_library(tmp_path)
    a = root / "Little Bear" / "S01 E01.mp4"
    b = root / "Little Bear" / "S01 E02.mp4"
    (root / "Little Bear" / "S01 E01.srt").write_text(
        "1\n00:00:01,000 --> 00:00:02,000\nhello\n", encoding="utf-8")
    window.set_root(root)
    folder = _make_draw(tmp_path, [a, b])

    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))

    assert _vocab_files(window) == ["S01 E01.srt"]
    # The one WITHOUT captions is named, or a short list reads as a small
    # sample rather than as missing captions.
    status = window._language.vocabulary._progress.text()
    assert "1 caption file from Pilot" in status
    assert "1 of its episodes has no .srt or .vtt" in status


def test_a_hand_added_caption_file_survives_a_scope_change(window, tmp_path):
    root = _make_library(tmp_path)
    a = root / "Little Bear" / "S01 E01.mp4"
    b = root / "Curious George" / "S01 E01.mp4"
    for episode in (a, b):
        episode.with_suffix(".srt").write_text("x", encoding="utf-8")
    window.set_root(root)
    mine = tmp_path / "notes_of_my_own.srt"
    mine.write_text("x", encoding="utf-8")

    first = _make_draw(tmp_path, [a], name="first")
    window.set_scope(scope_from_draw(f"sample:{first}", "A", first))
    window._language.vocabulary._add([str(mine)])
    assert sorted(_vocab_files(window)) == ["S01 E01.srt",
                                            "notes_of_my_own.srt"]

    second = _make_draw(tmp_path, [b], name="second")
    window.set_scope(scope_from_draw(f"sample:{second}", "B", second))

    staged = _vocab_files(window)
    assert "notes_of_my_own.srt" in staged, \
        "the hand-added file was thrown away by a scope change"
    assert len(staged) == 2, "the previous sample's caption file stayed staged"

    window.set_scope(library_scope())
    assert _vocab_files(window) == ["notes_of_my_own.srt"]


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


# --- the Index obeys the context, and its Shows view is derived --------------

def test_show_rows_are_derived_from_the_episodes_on_screen():
    """The stored `shows` table goes stale; a summary of the rows cannot.

    Live example on 2026-08-15: the stored Spongebob row read
    episode_count=2, avg_load=0.3071 while the index held five Spongebob
    episodes averaging 0.2557, because `upsert_show` only runs on a
    whole-show analysis.
    """
    from analyzer.db import summarise_shows
    episodes = [
        {"show_key": "S", "show_name": "S", "sensory_load_score": 0.20,
         "cuts_per_min": 10.0, "analyzed_at": "2026-01-01"},
        {"show_key": "S", "show_name": "S", "sensory_load_score": 0.40,
         "cuts_per_min": 20.0, "analyzed_at": "2026-02-02"},
    ]
    rows = summarise_shows(episodes)
    assert len(rows) == 1
    assert rows[0]["episode_count"] == 2
    assert rows[0]["avg_load"] == pytest.approx(0.30)
    assert rows[0]["avg_cuts_per_min"] == pytest.approx(15.0)
    assert rows[0]["updated_at"] == "2026-02-02"


def test_a_column_no_episode_carries_is_none_not_zero():
    """An em dash and a 0.000 are different claims about a measurement."""
    from analyzer.db import summarise_shows
    rows = summarise_shows([{"show_name": "S", "sensory_load_score": None}])
    assert rows[0]["avg_load"] is None
    assert rows[0]["avg_motion"] is None


def test_shows_without_a_value_sort_last_in_both_directions():
    from analyzer.db import summarise_shows
    eps = [{"show_name": "has", "sensory_load_score": 0.3},
           {"show_name": "none", "sensory_load_score": None}]
    for ascending in (True, False):
        rows = summarise_shows(eps, sort_by="avg_load", ascending=ascending)
        assert rows[-1]["show_name"] == "none", ascending


def _seed_index(root: Path, episodes: list[tuple[Path, str, float]]) -> None:
    """Put (path, show_name, load) rows straight into the index."""
    from analyzer.db import get_db
    conn = get_db(root)
    for path, show, load in episodes:
        conn.execute(
            """INSERT OR REPLACE INTO episodes
               (file_path, show_key, show_name, file_name, sensory_load_score,
                cuts_per_min, analyzed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (str(path), show, show, path.name, load, 12.0, "2026-08-15"))
    conn.commit()


def test_the_index_lists_only_the_episodes_in_the_current_context(
        window, tmp_path):
    root = _make_library(tmp_path)
    drawn = root / "Little Bear" / "S01 E01.mp4"
    _seed_index(root, [
        (drawn, "Little Bear", 0.30),
        (root / "Little Bear" / "S01 E02.mp4", "Little Bear", 0.40),
        (root / "Curious George" / "S01 E01.mp4", "Curious George", 0.20),
    ])
    window.set_root(root)
    index = window._index
    index.refresh()
    assert index._table.topLevelItemCount() == 3

    folder = _make_draw(tmp_path, [drawn])
    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))

    assert index._table.topLevelItemCount() == 1
    assert index._table.topLevelItem(0).text(0) == "S01 E01.mp4"
    assert "Pilot" in index._count.text()


def test_the_index_show_means_follow_the_context(window, tmp_path):
    """Otherwise a narrowed index shows whole-corpus means under its own header.

    This is the wrong number that displays correctly: every row plausible,
    every figure describing a set the user is not looking at.
    """
    root = _make_library(tmp_path)
    a = root / "Little Bear" / "S01 E01.mp4"
    b = root / "Little Bear" / "S01 E02.mp4"
    _seed_index(root, [(a, "Little Bear", 0.20), (b, "Little Bear", 0.40)])
    window.set_root(root)
    index = window._index
    index._scope.setCurrentText("Shows")
    index.refresh()
    whole = index._table.topLevelItem(0).text(2)          # Mean load

    folder = _make_draw(tmp_path, [a])
    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))
    index.refresh()
    narrowed = index._table.topLevelItem(0).text(2)

    assert whole == "0.300"          # mean of both
    assert narrowed == "0.200"       # the drawn one only
    assert index._table.topLevelItem(0).text(1) == "1"    # Episodes count


def test_rescore_index_merges_a_show_split_across_seasons(window, tmp_path):
    """cli.py's _db_backfill has an equivalent test for the same bug in the
    CLI path; this is the Qt build's rescore_index(). A show split across
    Season 1/ and Season 2/ subfolders gives list_shows() one entry per
    season, and both seasons' db_show_key collapse to the same parent show —
    upserting the show row once per show_dir let the season walked last
    overwrite every earlier season's aggregate instead of merging with it.
    """
    from analyzer.cache import save_cache
    from analyzer.db import get_db, query_shows
    from analyzer.schema import EpisodeResult
    from analyzer.show_index import show_key

    root = tmp_path / "Library"
    for season, cuts in (("Season 1", 10.0), ("Season 2", 20.0)):
        d = root / "Show" / season
        d.mkdir(parents=True)
        ep = d / "E01.mp4"
        ep.write_bytes(b"")
        r = EpisodeResult(file="E01.mp4", duration_sec=600.0)
        r.metrics.scene_pacing.cuts_per_min = cuts
        save_cache(root, show_key(root, d), "E01", r.to_dict())

    window.set_root(root)
    window.rescore_index()

    rows = query_shows(get_db(root))
    assert len(rows) == 1, "the two seasons must merge into one show row"
    assert rows[0]["episode_count"] == 2
    assert rows[0]["avg_cuts_per_min"] == pytest.approx(15.0)


# --- picking a known scope does not re-run discovery --------------------------

def test_picking_a_known_scope_does_not_rebuild_the_chooser(window, tmp_path, monkeypatch):
    """`_on_scope_picked` must not call `build_pipelines` again.

    The chooser already has every discoverable sample once it is built; picking
    a different one from that list cannot change what is discoverable
    (`TODO.md` — a whole scope change cost ~2.0 s, 1.5 s of it `build_pipelines`
    re-run on every pick). This is the regression test for that split.
    """
    import ui.main_window as mw

    root = _make_library(tmp_path)
    drawn = [root / "Little Bear" / "S01 E01.mp4"]
    folder = _make_draw(tmp_path, drawn)

    window.set_root(root)
    window.set_scope(scope_from_draw(f"sample:{folder}", "Pilot", folder))
    assert len(window._scope_choices) >= 2  # library + the drawn sample

    calls = {"n": 0}
    real_build_pipelines = mw.build_pipelines

    def counting_build_pipelines(root_arg):
        calls["n"] += 1
        return real_build_pipelines(root_arg)

    monkeypatch.setattr(mw, "build_pipelines", counting_build_pipelines)

    # Pick the library from the dropdown — already in _scope_choices at index 0.
    window._on_scope_picked(0)
    assert window._scope.is_library
    assert calls["n"] == 0, "picking an already-known scope re-ran build_pipelines"

    # Picking a scope NOT yet in the list must still fall back to a rebuild —
    # the safety net for a sample drawn moments ago.
    other_folder = _make_draw(tmp_path, drawn, name="draw2")
    unknown = scope_from_draw(f"sample:{other_folder}", "Unknown", other_folder)
    window.set_scope(unknown)
    assert calls["n"] == 1, "a not-yet-discovered scope should still trigger one rebuild"
    assert window._scope.key == unknown.key


# --- a Selection node's Exclude action, end to end -----------------------------

def test_excluding_from_a_selection_node_writes_a_real_narrowed_sample(
        window, tmp_path, monkeypatch):
    """The Inspector's "Exclude Library Selection" button, driven for real.

    Verifies the artefact and its consequences, not just that the call
    returns: a new sample folder on disk, the Library actually narrower, and
    the narrowed sample offered in the Showing: chooser like any other draw.
    """
    import json
    from analyzer.pipeline_graph import default_doc

    root = _make_library(tmp_path)
    drawn = [root / "Little Bear" / "S01 E01.mp4",
             root / "Little Bear" / "S01 E02.mp4",
             root / "Little Bear" / "S01 E03.mp4"]
    # Under root, not merely under tmp_path: build_pipelines(root) discovers
    # samples by walking the root folder, so a draw outside it is invisible
    # to _refresh_canvas the same way it would be to the real application.
    folder = _make_draw(root, drawn)
    (folder / "manifest.json").write_text(json.dumps({
        "method": "systematic", "total_selected": 3, "total_available": 6,
        "entry_id": "Little Bear", "trial_name": "Pilot",
    }), encoding="utf-8")

    window.set_root(root)
    doc = default_doc("Test study")
    doc.source_key = f"sample:{folder}"
    window._docs = [doc]
    window._pipe_pick.blockSignals(True)
    window._pipe_pick.clear()
    window._pipe_pick.addItem(doc.name)
    window._pipe_pick.blockSignals(False)
    window._refresh_canvas()

    sel_node = next(n for n in doc.nodes if n.type == "selection")

    # No node selected on the canvas yet: the action must be a safe no-op.
    window._exclude_from_selection_node()
    assert window._scope.folder != folder or window._scope.is_library

    monkeypatch.setattr(window, "_selected_episode_paths", lambda: [drawn[0]])
    window._canvas._items[sel_node.id].setSelected(True)

    window._exclude_from_selection_node()

    assert not window._scope.is_library
    assert window._scope.folder not in (None, folder), \
        "excluding must land on a NEW sample folder, not mutate the source"
    assert len(window._scope.episodes) == 2
    assert drawn[0] not in window._scope.episodes

    # The new folder really exists and really has only the kept episodes —
    # the artefact, not just the in-memory Scope object.
    with (window._scope.folder / "selected.csv").open(
            newline="", encoding="utf-8") as fh:
        kept = {Path(r["filepath"]) for r in csv.DictReader(fh)}
    assert kept == {drawn[1], drawn[2]}

    # It is now offered in the Showing: chooser, not just the current scope —
    # the whole point of writing it like a sampler draw instead of a
    # canvas-only annotation.
    assert any(s.key == window._scope.key for s in window._scope_choices)

    assert sorted(_library_rows(window)) == ["S01 E02.mp4", "S01 E03.mp4"]


# --- per-node sample binding: two branches, two samples, on one canvas --------

def test_two_sampling_nodes_each_drive_their_own_branchs_status_and_scope(
        window, tmp_path):
    """The large slice of "wires carry the set", driven for real.

    One canvas, two Sampling nodes, each bound to a DIFFERENT sample, each
    feeding its own Automated coding node. Before per-node binding, every
    node on a canvas read the document's one `source_key`, so both branches
    would have shown the same sample's status and staged the same episodes
    regardless of which node's wire actually fed it. This asserts they don't:
    each node's derived status names its OWN sample's episode count, and
    double-clicking a branch's node stages THAT branch's episodes, not the
    other one's.
    """
    import json
    from analyzer.pipeline_graph import blank_doc

    root = _make_library(tmp_path)
    little_bear = [root / "Little Bear" / "S01 E01.mp4",
                   root / "Little Bear" / "S01 E02.mp4"]
    curious_george = [root / "Curious George" / "S01 E03.mp4"]
    folder_a = _make_draw(root, little_bear, name="draw_a")
    folder_b = _make_draw(root, curious_george, name="draw_b")
    for folder, n in ((folder_a, 2), (folder_b, 1)):
        (folder / "manifest.json").write_text(json.dumps({
            "method": "systematic", "total_selected": n,
            "total_available": n + 5, "entry_id": "Show",
            "trial_name": folder.name,
        }), encoding="utf-8")

    window.set_root(root)
    doc = blank_doc("Two branches")
    sampling_a = doc.add_node("sampling", 0, 0)
    sampling_a.config["sample_key"] = f"sample:{folder_a}"
    automated_a = doc.add_node("automated", 250, 0)
    doc.connect(sampling_a.id, automated_a.id)

    sampling_b = doc.add_node("sampling", 0, 200)
    sampling_b.config["sample_key"] = f"sample:{folder_b}"
    automated_b = doc.add_node("automated", 250, 200)
    doc.connect(sampling_b.id, automated_b.id)

    window._docs = [doc]
    window._pipe_pick.blockSignals(True)
    window._pipe_pick.clear()
    window._pipe_pick.addItem(doc.name)
    window._pipe_pick.blockSignals(False)
    window._refresh_canvas()

    stage_a, reason_a = window._stage_for(automated_a)
    stage_b, reason_b = window._stage_for(automated_b)
    assert reason_a == "" and reason_b == "", (reason_a, reason_b)
    assert dict(stage_a.details)["Episodes analyzed"].startswith("0/2")
    assert dict(stage_b.details)["Episodes analyzed"].startswith("0/1")

    window._open_stage_screen(automated_a)
    assert window._scope.folder == folder_a
    assert _would_analyze(window) and len(_would_analyze(window)) == 2

    window._open_stage_screen(automated_b)
    assert window._scope.folder == folder_b
    assert _would_analyze(window) and len(_would_analyze(window)) == 1


def test_validation_fed_by_two_sampling_nodes_merges_instead_of_picking_one(
        window, tmp_path, monkeypatch):
    """A Validation node wired to TWO different Sampling nodes must reflect
    the UNION of both samples' episodes, not silently report only the first
    branch and hide the second.

    `coverage_for_episodes` is monkeypatched at the point `merged_pipeline`
    calls it, to (n_episodes coded == n_episodes given) without needing real
    hand-coding files on disk under this repo's actual validation/ folder --
    the union itself, computed from real selected.csv files, is what this
    test is checking.
    """
    import json
    from analyzer.pipeline_graph import blank_doc

    root = _make_library(tmp_path)
    little_bear = [root / "Little Bear" / "S01 E01.mp4",
                   root / "Little Bear" / "S01 E02.mp4"]
    curious_george = [root / "Curious George" / "S01 E03.mp4"]
    folder_a = _make_draw(root, little_bear, name="draw_a")
    folder_b = _make_draw(root, curious_george, name="draw_b")
    for folder, n in ((folder_a, 2), (folder_b, 1)):
        (folder / "manifest.json").write_text(json.dumps({
            "method": "systematic", "total_selected": n,
            "total_available": n + 5, "entry_id": "Show",
            "trial_name": folder.name,
        }), encoding="utf-8")

    def fake_coverage(episodes, validation_dir=None, root=None):
        return {"n_episodes": len(episodes), "n_transition_coded": len(episodes),
                "n_event_coded": 0}
    monkeypatch.setattr("analyzer.pipeline.coverage_for_episodes", fake_coverage)

    window.set_root(root)
    doc = blank_doc("Compares two samples")
    sampling_a = doc.add_node("sampling", 0, 0)
    sampling_a.config["sample_key"] = f"sample:{folder_a}"
    sampling_b = doc.add_node("sampling", 0, 200)
    sampling_b.config["sample_key"] = f"sample:{folder_b}"
    validation = doc.add_node("validation", 250, 100)
    doc.connect(sampling_a.id, validation.id)
    doc.connect(sampling_b.id, validation.id)

    window._docs = [doc]
    window._pipe_pick.blockSignals(True)
    window._pipe_pick.clear()
    window._pipe_pick.addItem(doc.name)
    window._pipe_pick.blockSignals(False)
    window._refresh_canvas()

    stage, reason = window._stage_for(validation)
    assert reason == ""
    # 2 (Little Bear) + 1 (Curious George) = 3 -- the union, not either alone.
    assert dict(stage.details)["Hand-coded episodes available"] == "3"

    window._canvas._items[validation.id].setSelected(True)
    window._on_node_selected(validation)
    rows = {}
    for r in range(window._inspector._grid.rowCount()):
        k = window._inspector._grid.itemAtPosition(r, 0)
        if k is not None:
            rows[k.widget().text()] = True
    assert "Other branches feeding this node" not in rows, \
        "a real merge happened, so the 'not reflected' caveat must not show"


def test_two_sampling_nodes_wired_into_one_selection_node_show_both_shows(
        window, tmp_path):
    """The reported symptom, reproduced exactly: two Sampling nodes wired
    directly into ONE Selection node -- only one show was coming through.

    Selection is not Validation; it has no special multi-input merge of its
    own (`_stage_for` merges for ANY node type fed by more than one Sampling
    node, not just Validation), so this checks the general case, not the one
    that happened to be built and tested first.
    """
    import json
    from analyzer.pipeline_graph import blank_doc

    root = _make_library(tmp_path)
    little_bear = [root / "Little Bear" / "S01 E01.mp4",
                   root / "Little Bear" / "S01 E02.mp4"]
    curious_george = [root / "Curious George" / "S01 E01.mp4",
                      root / "Curious George" / "S01 E02.mp4"]
    folder_a = _make_draw(root, little_bear, name="draw_a")
    folder_b = _make_draw(root, curious_george, name="draw_b")
    for folder, n in ((folder_a, 2), (folder_b, 2)):
        (folder / "manifest.json").write_text(json.dumps({
            "method": "systematic", "total_selected": n,
            "total_available": n + 5, "entry_id": "Show",
            "trial_name": folder.name,
        }), encoding="utf-8")

    window.set_root(root)
    doc = blank_doc("Two shows, one Selection")
    sampling_a = doc.add_node("sampling", 0, 0)
    sampling_a.config["sample_key"] = f"sample:{folder_a}"
    sampling_b = doc.add_node("sampling", 0, 200)
    sampling_b.config["sample_key"] = f"sample:{folder_b}"
    selection = doc.add_node("selection", 250, 100)
    doc.connect(sampling_a.id, selection.id)
    doc.connect(sampling_b.id, selection.id)

    window._docs = [doc]
    window._pipe_pick.blockSignals(True)
    window._pipe_pick.clear()
    window._pipe_pick.addItem(doc.name)
    window._pipe_pick.blockSignals(False)
    window._refresh_canvas()

    stage, reason = window._stage_for(selection)
    assert reason == ""
    assert stage.headline == "4 episodes", (
        "both shows must be counted -- 2 from Little Bear, 2 from Curious "
        f"George -- not just the first branch's 2 (got {stage.headline!r})")

    assert window._stage_status(selection) == f"— {stage.status_label}"


def test_the_menu_link_never_touches_a_selected_nodes_own_key(
        window, tmp_path, monkeypatch):
    """The actual bug behind the report above: _link_to_sample (the Manage
    menu / no-node Inspector button) and _link_node_to_sample (a selected
    Sampling node's own button) used to be ONE method that inferred which was
    meant from whatever happened to be selected on the canvas. Reproduces the
    exact failure mode: link node A, link node B, then use the MENU item
    while node A is STILL selected (leftover state from clicking around) --
    the menu action must set the document default, never silently overwrite
    node A's own binding.
    """
    import json
    import ui.main_window as mw
    from analyzer.pipeline_graph import blank_doc

    root = _make_library(tmp_path)
    folder_a = _make_draw(root, [root / "Little Bear" / "S01 E01.mp4"], name="draw_a")
    folder_b = _make_draw(root, [root / "Curious George" / "S01 E01.mp4"], name="draw_b")
    folder_c = _make_draw(root, [root / "Little Bear" / "S01 E02.mp4"], name="draw_c")
    for folder in (folder_a, folder_b, folder_c):
        (folder / "manifest.json").write_text(json.dumps({
            "method": "systematic", "total_selected": 1, "total_available": 5,
            "entry_id": "Show", "trial_name": folder.name,
        }), encoding="utf-8")

    window.set_root(root)
    doc = blank_doc("Two nodes")
    sampling_a = doc.add_node("sampling", 0, 0)
    sampling_b = doc.add_node("sampling", 0, 200)
    window._docs = [doc]
    window._pipe_pick.blockSignals(True)
    window._pipe_pick.clear()
    window._pipe_pick.addItem(doc.name)
    window._pipe_pick.blockSignals(False)
    window._refresh_canvas()

    def _pick(name_substr):
        def getItem(parent, title, label, items, current, editable=False):
            return next(i for i in items if name_substr in i), True
        return getItem

    # Link node A to draw_a, via the node-specific path.
    window._canvas._items[sampling_a.id].setSelected(True)
    monkeypatch.setattr(mw.QInputDialog, "getItem", _pick("draw_a"))
    window._link_node_to_sample()
    assert sampling_a.config["sample_key"] == f"sample:{folder_a}"
    assert doc.source_key is None

    # Link node B to draw_b, via the node-specific path.
    window._canvas._items[sampling_a.id].setSelected(False)
    window._canvas._items[sampling_b.id].setSelected(True)
    monkeypatch.setattr(mw.QInputDialog, "getItem", _pick("draw_b"))
    window._link_node_to_sample()
    assert sampling_b.config["sample_key"] == f"sample:{folder_b}"
    assert doc.source_key is None

    # Node A is selected again (the user clicked back on it to look at it),
    # then reaches for Manage -> Link to Episode Sample -- the OLD, familiar
    # menu item -- expecting it to do what it always did: set the document's
    # default. It must NOT silently repoint node A's own binding.
    window._canvas._items[sampling_a.id].setSelected(True)
    monkeypatch.setattr(mw.QInputDialog, "getItem", _pick("draw_c"))
    window._link_to_sample()

    assert doc.source_key == f"sample:{folder_c}"
    assert sampling_a.config["sample_key"] == f"sample:{folder_a}", \
        "the menu action must not have touched node A's own binding"
    assert sampling_b.config["sample_key"] == f"sample:{folder_b}"


# --- drawing a NEW sample from a specific Sampling node -----------------------

def test_drawing_from_a_sampling_node_binds_and_persists_to_that_node(
        window, tmp_path, monkeypatch):
    """The next report: drawing (not just linking to an existing sample) from
    one Sampling node was only ever changing the document's session scope --
    never that node's own binding, and never saved to disk. Reproduces both
    complaints: node isolation, and having to redraw on every reopen.
    """
    from PySide6.QtWidgets import QDialog
    from analyzer.pipeline_graph import blank_doc, list_docs, save_doc

    root = _make_library(tmp_path)
    window.set_root(root)
    doc = blank_doc("Two draws")
    sampling_a = doc.add_node("sampling", 0, 0)
    sampling_b = doc.add_node("sampling", 0, 200)
    save_doc(doc, root)
    window._docs = [doc]
    window._pipe_pick.blockSignals(True)
    window._pipe_pick.clear()
    window._pipe_pick.addItem(doc.name)
    window._pipe_pick.blockSignals(False)
    window._refresh_canvas()

    draw_a = root / "draw_a"
    draw_a.mkdir()
    (draw_a / "selected.csv").write_text(
        "filepath\n" + str(root / "Little Bear" / "S01 E01.mp4"),
        encoding="utf-8")
    draw_b = root / "draw_b"
    draw_b.mkdir()
    (draw_b / "selected.csv").write_text(
        "filepath\n" + str(root / "Curious George" / "S01 E01.mp4"),
        encoding="utf-8")

    import ui.sampler as sampler_module

    def _fake_dialog_for(written):
        class _Fake:
            def __init__(self, *a, **k):
                self.written_dir = written
            def exec(self):
                return QDialog.Accepted
        return _Fake

    # Draw for node A.
    monkeypatch.setattr(sampler_module, "SamplerDialog", _fake_dialog_for(draw_a))
    window.open_sampler(sampling_a)
    assert sampling_a.config["sample_key"] == f"sample:{draw_a}"
    assert sampling_b.config.get("sample_key") is None, \
        "drawing for node A must not silently bind node B too"

    # Draw for node B -- must not clobber node A's own binding.
    monkeypatch.setattr(sampler_module, "SamplerDialog", _fake_dialog_for(draw_b))
    window.open_sampler(sampling_b)
    assert sampling_b.config["sample_key"] == f"sample:{draw_b}"
    assert sampling_a.config["sample_key"] == f"sample:{draw_a}", \
        "drawing for node B must not overwrite node A's own draw"

    # And it must be ON DISK: reload the document the way reopening the
    # pipeline would, not just check the in-memory objects this test built.
    reloaded = next(d for d in list_docs(root) if d.id == doc.id)
    reloaded_a = next(n for n in reloaded.nodes if n.id == sampling_a.id)
    reloaded_b = next(n for n in reloaded.nodes if n.id == sampling_b.id)
    assert reloaded_a.config["sample_key"] == f"sample:{draw_a}"
    assert reloaded_b.config["sample_key"] == f"sample:{draw_b}"


def test_drawing_without_a_node_context_does_not_bind_any_node(
        window, tmp_path, monkeypatch):
    """The File menu / toolbar Episode Sampler button -- not tied to any
    specific pipeline node -- must keep its old behavior: only the session
    scope follows the draw, nothing gets silently bound."""
    from PySide6.QtWidgets import QDialog
    from analyzer.pipeline_graph import blank_doc, save_doc

    root = _make_library(tmp_path)
    window.set_root(root)
    doc = blank_doc("Untouched by a menu draw")
    sampling_a = doc.add_node("sampling", 0, 0)
    save_doc(doc, root)
    window._docs = [doc]
    window._pipe_pick.blockSignals(True)
    window._pipe_pick.clear()
    window._pipe_pick.addItem(doc.name)
    window._pipe_pick.blockSignals(False)
    window._refresh_canvas()

    draw = root / "draw"
    draw.mkdir()
    (draw / "selected.csv").write_text(
        "filepath\n" + str(root / "Little Bear" / "S01 E01.mp4"),
        encoding="utf-8")

    import ui.sampler as sampler_module

    class _Fake:
        def __init__(self, *a, **k):
            self.written_dir = draw
        def exec(self):
            return QDialog.Accepted

    monkeypatch.setattr(sampler_module, "SamplerDialog", _Fake)
    window.open_sampler()          # no node -- the File menu / toolbar path

    assert sampling_a.config.get("sample_key") is None
    assert doc.source_key is None
    assert window._scope.folder == draw, \
        "the session scope should still follow the draw, same as before"


# --- the Library shows BOTH branches' media, not one at a time ---------------

def _two_branch_window(window, tmp_path, node_type="selection"):
    """A canvas with two Sampling nodes, each on its own show, both wired
    into one downstream node. Returns (doc, downstream_node, folder_a,
    folder_b)."""
    import json
    from analyzer.pipeline_graph import blank_doc

    root = _make_library(tmp_path)
    folder_a = _make_draw(root, [root / "Little Bear" / "S01 E01.mp4",
                                 root / "Little Bear" / "S01 E02.mp4"],
                          name="draw_a")
    folder_b = _make_draw(root, [root / "Curious George" / "S01 E01.mp4"],
                          name="draw_b")
    for folder, n in ((folder_a, 2), (folder_b, 1)):
        (folder / "manifest.json").write_text(json.dumps({
            "method": "systematic", "total_selected": n,
            "total_available": n + 5, "entry_id": "Show",
            "trial_name": folder.name,
        }), encoding="utf-8")

    window.set_root(root)
    doc = blank_doc("Two branches")
    a = doc.add_node("sampling", 0, 0)
    a.config["sample_key"] = f"sample:{folder_a}"
    b = doc.add_node("sampling", 0, 200)
    b.config["sample_key"] = f"sample:{folder_b}"
    downstream = doc.add_node(node_type, 250, 100)
    doc.connect(a.id, downstream.id)
    doc.connect(b.id, downstream.id)

    window._docs = [doc]
    window._pipe_pick.blockSignals(True)
    window._pipe_pick.clear()
    window._pipe_pick.addItem(doc.name)
    window._pipe_pick.blockSignals(False)
    window._refresh_canvas()
    return doc, downstream, folder_a, folder_b


def test_opening_a_merged_node_puts_both_shows_in_the_library(
        window, tmp_path):
    """The report: "both of the sampled media doesn't transfer to the Library
    tab, only one of the samples does at a time."

    The Library follows the scope, and the scope was built from the FIRST
    upstream sample only -- so a node the Inspector correctly described as
    merged handed the Library one branch, and the other looked lost.
    """
    doc, selection, folder_a, folder_b = _two_branch_window(window, tmp_path)

    window._open_stage_screen(selection)

    rows = sorted(_library_rows(window))
    assert rows == ["S01 E01.mp4", "S01 E01.mp4", "S01 E02.mp4"], (
        "the Library must list all three episodes -- both Little Bear and "
        f"Curious George -- not one branch's (got {rows})")
    assert len(window._scope.episodes) == 3
    assert window._scope.folder is None, \
        "a union is not any single draw's folder"
    # Both shows are present, not one.
    assert "Little Bear" in _tree_text(window)
    assert "Curious George" in _tree_text(window)


def test_a_single_branch_node_still_scopes_to_its_own_draw(window, tmp_path):
    """The union must not disturb the ordinary one-sample case."""
    import json
    from analyzer.pipeline_graph import blank_doc

    root = _make_library(tmp_path)
    folder = _make_draw(root, [root / "Little Bear" / "S01 E01.mp4"],
                        name="draw_only")
    (folder / "manifest.json").write_text(json.dumps({
        "method": "systematic", "total_selected": 1, "total_available": 6,
        "entry_id": "Show", "trial_name": "draw_only",
    }), encoding="utf-8")

    window.set_root(root)
    doc = blank_doc("One branch")
    a = doc.add_node("sampling", 0, 0)
    a.config["sample_key"] = f"sample:{folder}"
    selection = doc.add_node("selection", 250, 0)
    doc.connect(a.id, selection.id)
    window._docs = [doc]
    window._pipe_pick.blockSignals(True)
    window._pipe_pick.clear()
    window._pipe_pick.addItem(doc.name)
    window._pipe_pick.blockSignals(False)
    window._refresh_canvas()

    window._open_stage_screen(selection)
    assert window._scope.folder == folder, \
        "one upstream sample should still scope to that draw's own folder"
    assert _library_rows(window) == ["S01 E01.mp4"]


# --- the media being sampled is named on the block and in the inspector ------

def test_a_sampling_block_names_the_media_it_drew(window, tmp_path):
    """Two Sampling boxes read "Sampling / How episodes were chosen" and were
    otherwise identical on the canvas; the box must say WHICH media it drew."""
    doc, selection, folder_a, folder_b = _two_branch_window(window, tmp_path)
    sampling_a = next(n for n in doc.nodes
                      if n.config.get("sample_key") == f"sample:{folder_a}")

    assert window._node_media(sampling_a) == "draw_a"
    # ...and it reaches the drawn box, not just the resolver.
    assert window._canvas._items[sampling_a.id].media_line == "draw_a"

    # The Inspector names it too, in a row and in the subtitle.
    window._canvas._items[sampling_a.id].setSelected(True)
    window._on_node_selected(sampling_a)
    rows = {}
    grid = window._inspector._grid
    for r in range(grid.rowCount()):
        k, v = grid.itemAtPosition(r, 0), grid.itemAtPosition(r, 1)
        if k is not None and v is not None:
            rows[k.widget().text()] = v.widget().text()
    assert rows.get("Media") == "draw_a"
    assert "draw_a" in window._inspector._subtitle.text()


def test_a_merged_node_names_every_media_feeding_it(window, tmp_path):
    doc, selection, folder_a, folder_b = _two_branch_window(window, tmp_path)
    media = window._node_media(selection)
    assert "draw_a" in media and "draw_b" in media, (
        "a node fed by two samples should name both, not pick one "
        f"(got {media!r})")


# --- the Showing: chooser offers pipelines, not only single draws ------------

def test_the_chooser_offers_the_whole_pipeline_not_only_its_samples(
        window, tmp_path):
    """The root of the "only one sample at a time" report.

    The chooser listed drawn SAMPLES only, so a pipeline built from two
    Sampling nodes could not be expressed in it at all -- every entry
    narrowed to one branch, and there was no way to ask for the study the
    researcher had actually assembled.
    """
    doc, selection, folder_a, folder_b = _two_branch_window(window, tmp_path)
    window._rebuild_scope_choices()

    pipeline_scopes = [s for s in window._scope_choices
                       if s.key == f"pipeline:{doc.id}"]
    assert len(pipeline_scopes) == 1, (
        "a pipeline drawing on two samples needs its own entry; the chooser "
        f"offered only {[s.label for s in window._scope_choices]}")

    scope = pipeline_scopes[0]
    assert doc.name in scope.label
    assert len(scope.episodes) == 3, "both branches' episodes, not one's"

    # Selecting it from the chooser is what the user actually does.
    index = window._scope_choices.index(scope)
    window._on_scope_picked(index)

    assert sorted(_library_rows(window)) == [
        "S01 E01.mp4", "S01 E01.mp4", "S01 E02.mp4"]
    assert "Little Bear" in _tree_text(window)
    assert "Curious George" in _tree_text(window)


def test_a_one_sample_pipeline_adds_no_duplicate_chooser_entry(
        window, tmp_path):
    """A pipeline on a single sample is already covered by that sample's own
    entry; a second entry under the document's name would be noise in a list
    this library already fills with a dozen draws."""
    import json
    from analyzer.pipeline_graph import blank_doc

    root = _make_library(tmp_path)
    folder = _make_draw(root, [root / "Little Bear" / "S01 E01.mp4"],
                        name="only_draw")
    (folder / "manifest.json").write_text(json.dumps({
        "method": "systematic", "total_selected": 1, "total_available": 6,
        "entry_id": "Show", "trial_name": "only_draw",
    }), encoding="utf-8")

    window.set_root(root)
    doc = blank_doc("Single sample study")
    a = doc.add_node("sampling", 0, 0)
    a.config["sample_key"] = f"sample:{folder}"
    window._docs = [doc]
    window._rebuild_scope_choices()

    assert not [s for s in window._scope_choices
                if s.key == f"pipeline:{doc.id}"]


# --- selecting a pipeline defaults to the combination it was built from ------

def test_selecting_a_two_sample_pipeline_defaults_to_both_together(
        window, tmp_path):
    """Choosing a pipeline with two Sampling blocks should land on both of
    them, not on one arbitrary half of the study the researcher assembled."""
    doc, selection, folder_a, folder_b = _two_branch_window(window, tmp_path)
    window.set_scope(library_scope())
    assert window._scope.is_library

    window._follow_pipeline_scope()

    assert window._scope.key == f"pipeline:{doc.id}"
    assert len(window._scope.episodes) == 3
    assert sorted(_library_rows(window)) == [
        "S01 E01.mp4", "S01 E01.mp4", "S01 E02.mp4"]
    # ...and the chooser shows that, rather than disagreeing with the tree.
    assert window._scope_pick.currentText() == window._scope.describe()


def test_selecting_a_one_sample_pipeline_still_scopes_to_that_sample(
        window, tmp_path):
    """The single-block case keeps its old behaviour."""
    import json
    from analyzer.pipeline_graph import blank_doc

    root = _make_library(tmp_path)
    folder = _make_draw(root, [root / "Little Bear" / "S01 E01.mp4"],
                        name="one_draw")
    (folder / "manifest.json").write_text(json.dumps({
        "method": "systematic", "total_selected": 1, "total_available": 6,
        "entry_id": "Show", "trial_name": "one_draw",
    }), encoding="utf-8")

    window.set_root(root)
    doc = blank_doc("One block")
    a = doc.add_node("sampling", 0, 0)
    a.config["sample_key"] = f"sample:{folder}"
    window._docs = [doc]
    window._pipe_pick.blockSignals(True)
    window._pipe_pick.clear()
    window._pipe_pick.addItem(doc.name)
    window._pipe_pick.blockSignals(False)
    window._refresh_canvas()

    window._follow_pipeline_scope()

    assert window._scope.folder == folder
    assert _library_rows(window) == ["S01 E01.mp4"]


def test_selecting_an_unlinked_pipeline_leaves_the_scope_alone(
        window, tmp_path):
    """An unlinked pipeline has no opinion about which episodes -- it must
    not silently empty the Library."""
    from analyzer.pipeline_graph import blank_doc

    root = _make_library(tmp_path)
    window.set_root(root)
    doc = blank_doc("Nothing linked")
    doc.add_node("sampling", 0, 0)
    window._docs = [doc]
    window._pipe_pick.blockSignals(True)
    window._pipe_pick.clear()
    window._pipe_pick.addItem(doc.name)
    window._pipe_pick.blockSignals(False)
    window._refresh_canvas()

    before = window._scope.key
    window._follow_pipeline_scope()
    assert window._scope.key == before


# --- the document panel names what the pipeline actually draws on -------------

def _inspector_rows(window) -> dict[str, str]:
    """The Inspector's key/value rows as rendered, read off the widgets."""
    grid = window._inspector._grid
    rows: dict[str, str] = {}
    for r in range(grid.rowCount()):
        k = grid.itemAtPosition(r, 0)
        v = grid.itemAtPosition(r, 1)
        if k is not None and v is not None:
            rows[k.widget().text()] = v.widget().text()
    return rows


def _load_one_doc(window, doc):
    window._docs = [doc]
    window._pipe_pick.blockSignals(True)
    window._pipe_pick.clear()
    window._pipe_pick.addItem(doc.name)
    window._pipe_pick.blockSignals(False)
    window._refresh_canvas()


def test_the_doc_panel_names_the_nodes_sample_not_a_stale_document_key(
        window, tmp_path):
    """The reported bug, reproduced from the real document that showed it.

    "Arthur Language" had a Sampling node bound to an Arthur sample and a
    leftover document-level `source_key` naming a different show entirely.
    Every node on the canvas read Arthur; the document panel read the stale
    key and announced "Data source: Peep and the Big Wide World/Season 1" — a
    show contributing no episodes to the pipeline. `LEARNINGS.md` shape 1.
    """
    import json
    from analyzer.pipeline_graph import blank_doc

    root = _make_library(tmp_path)
    drawn = [root / "Little Bear" / "S01 E01.mp4",
             root / "Little Bear" / "S01 E02.mp4"]
    folder = _make_draw(root, drawn, name="arthur_like_draw")
    (folder / "manifest.json").write_text(json.dumps({
        "method": "census", "total_selected": 2, "total_available": 2,
        "entry_id": "Show", "trial_name": "The node's own sample",
    }), encoding="utf-8")
    window.set_root(root)

    doc = blank_doc("Bound node, stale document key")
    # The document points at one show...
    doc.source_key = "Some Other Show/Season 1"
    # ...while its Sampling node is bound to the sample actually being used.
    sampling = doc.add_node("sampling", 0, 0)
    sampling.config["sample_key"] = f"sample:{folder}"
    language = doc.add_node("language", 250, 0)
    doc.connect(sampling.id, language.id)
    _load_one_doc(window, doc)

    rows = _inspector_rows(window)
    assert "Some Other Show" not in rows["Data source"]
    assert rows["Data source"] == "The node's own sample"
    assert "The node's own sample" in window._inspector._subtitle.text()


def test_a_document_key_that_resolves_to_nothing_says_so_rather_than_naming_it(
        window, tmp_path):
    """Three states, not two.

    A stale key is not "not linked" — collapsing them would hide it — and it
    is not a data source either, because it resolves to nothing. It gets said
    out loud, and the Link button is offered as the way out.
    """
    from analyzer.pipeline_graph import blank_doc

    root = _make_library(tmp_path)
    window.set_root(root)
    doc = blank_doc("Stale key, no node binding")
    doc.source_key = "A Show That Went Away/Season 1"
    doc.add_node("sampling", 0, 0)
    _load_one_doc(window, doc)

    rows = _inspector_rows(window)
    assert "A Show That Went Away" in rows["Data source"]
    assert "no drawn sample or show" in rows["Data source"]
    assert "no longer resolves" in window._inspector._subtitle.text()
    assert not window._inspector._action.isHidden()


def test_a_document_with_no_binding_anywhere_still_reads_as_unlinked(
        window, tmp_path):
    from analyzer.pipeline_graph import blank_doc

    root = _make_library(tmp_path)
    window.set_root(root)
    doc = blank_doc("Nothing at all")
    doc.add_node("sampling", 0, 0)
    _load_one_doc(window, doc)

    assert _inspector_rows(window)["Data source"].startswith("none")
    assert "not linked" in window._inspector._subtitle.text()


def test_the_document_key_is_still_the_fallback_when_no_node_is_bound(
        window, tmp_path):
    """The fix must not break the pre-per-node-binding pipelines it exists for.

    `DECISIONS.md`: a Sampling node's own binding FALLS BACK to the document's
    `source_key`, never replaces it.
    """
    import json
    from analyzer.pipeline_graph import blank_doc

    root = _make_library(tmp_path)
    folder = _make_draw(root, [root / "Little Bear" / "S01 E01.mp4"],
                        name="doc_level_draw")
    (folder / "manifest.json").write_text(json.dumps({
        "method": "census", "total_selected": 1, "total_available": 1,
        "entry_id": "Show", "trial_name": "The document's own sample",
    }), encoding="utf-8")
    window.set_root(root)

    doc = blank_doc("Old-style, document-level link")
    doc.source_key = f"sample:{folder}"
    doc.add_node("sampling", 0, 0)          # no binding of its own
    _load_one_doc(window, doc)

    assert _inspector_rows(window)["Data source"] == "The document's own sample"


def test_deselecting_a_node_restores_the_resolved_source_not_the_raw_key(
        window, tmp_path):
    """Clicking a node and clicking away used to replace the sample's name
    with the document's raw folder key, because the deselect path called
    show_doc with no label."""
    import json
    from analyzer.pipeline_graph import blank_doc

    root = _make_library(tmp_path)
    folder = _make_draw(root, [root / "Little Bear" / "S01 E01.mp4"],
                        name="reselect_draw")
    (folder / "manifest.json").write_text(json.dumps({
        "method": "census", "total_selected": 1, "total_available": 1,
        "entry_id": "Show", "trial_name": "Named sample",
    }), encoding="utf-8")
    window.set_root(root)

    doc = blank_doc("Reselect")
    sampling = doc.add_node("sampling", 0, 0)
    sampling.config["sample_key"] = f"sample:{folder}"
    _load_one_doc(window, doc)
    assert _inspector_rows(window)["Data source"] == "Named sample"

    window._inspector.show_node(sampling)
    window._inspector.show_node(None)
    assert _inspector_rows(window)["Data source"] == "Named sample"
