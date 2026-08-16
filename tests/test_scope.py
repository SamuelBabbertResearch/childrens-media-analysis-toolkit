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
    node = type("Node", (), {"type": kind.key, "title": "Automated coding"})()
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
