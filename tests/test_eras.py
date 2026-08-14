"""
Eras — the date-range grouping that makes a long-running show samplable.

These matter because the feature LOOKED present for weeks and did nothing: the
Tk sampler offered "By era / custom column", but nothing populated
`Episode.extra` and a folder scan leaves `air_date` as None, so every episode
resolved to one stratum. Tests here pin the data path, not just the control.
"""

from __future__ import annotations

from pathlib import Path

from analyzer.eras import (
    ERA_KEY, UNASSIGNED, assign_eras, coverage_note, era_for_date,
    normalise_date,
)
from analyzer.sampler import Episode, sample

ERAS = [
    {"era_name": "1980s", "start_date": "1980-01-01", "end_date": "1989-12-31"},
    {"era_name": "1990s", "start_date": "1990-01-01", "end_date": "1999-12-31"},
    {"era_name": "2000s+", "start_date": "2000-01-01", "end_date": None},
]


def _episode(index: int, air_date: str | None) -> Episode:
    return Episode(entry_id="show", season=1, episode=index,
                   title=f"E{index}", air_date=air_date, runtime=None,
                   filepath=Path(f"e{index}.mp4"))


def test_dates_are_read_in_the_spellings_people_type():
    assert normalise_date("1985") == "1985-01-01"
    assert normalise_date("1985-06-01") == "1985-06-01"
    assert normalise_date("1 June 1985") == "1985-06-01"
    assert normalise_date("June 1, 1985") == "1985-06-01"


def test_an_unreadable_date_returns_empty_rather_than_raising():
    """One bad era row must not stop the other rows working."""
    assert normalise_date("sometime in the eighties") == ""
    assert normalise_date(None) == ""


def test_an_open_ended_era_runs_to_the_present():
    """"2000s+" with no end date is how a current period is expressed."""
    assert era_for_date("2024-01-01", ERAS) == "2000s+"


def test_bounds_are_inclusive():
    assert era_for_date("1980-01-01", ERAS) == "1980s"
    assert era_for_date("1989-12-31", ERAS) == "1980s"
    assert era_for_date("1990-01-01", ERAS) == "1990s"


def test_an_episode_outside_every_era_is_grouped_not_dropped():
    """It is still part of the run, and dropping it would shrink the frame."""
    assert era_for_date("1970-01-01", ERAS) == UNASSIGNED
    assert era_for_date(None, ERAS) == UNASSIGNED


def test_assign_eras_tags_the_column_the_sampler_partitions_on():
    episodes = [_episode(1, "1985-01-01"), _episode(2, "1995-01-01")]
    counts = assign_eras(episodes, ERAS)
    assert [e.extra[ERA_KEY] for e in episodes] == ["1980s", "1990s"]
    assert counts == {"1980s": 1, "1990s": 1}


def test_stratifying_by_era_actually_splits_the_draw():
    """The regression this whole module exists for.

    Without `extra["era"]` populated, `stratify_by="era"` puts everything in
    one `(none)` stratum — which is not stratifying at all, while still
    reporting itself as a stratified design.
    """
    episodes = [_episode(i, d) for i, d in enumerate(
        ["1985-01-01", "1986-01-01", "1987-01-01",
         "1995-01-01", "1996-01-01", "1997-01-01",
         "2005-01-01", "2006-01-01", "2007-01-01"], 1)]
    assign_eras(episodes, ERAS)
    result = sample(episodes, entry_id="show", stratify_by=ERA_KEY,
                    method="spread", per_stratum_n=1, seed=42)
    strata = {s.stratum_key for s in result.manifest.strata}
    assert strata == {"1980s", "1990s", "2000s+"}
    assert result.manifest.total_selected == 3
    assert result.manifest.stratify_by == ERA_KEY


def test_the_draw_is_reproducible_from_the_manifest():
    """A sample is a record: the same seed and design must redraw the same."""
    episodes = [_episode(i, f"198{i}-01-01") for i in range(1, 8)]
    assign_eras(episodes, ERAS)
    first = sample(episodes, entry_id="s", stratify_by=ERA_KEY,
                   method="spread", per_stratum_n=2, seed=7)
    again = sample(episodes, entry_id="s", stratify_by=ERA_KEY,
                   method="spread", per_stratum_n=2, seed=7)
    assert [e.episode for e in first.selected] == \
           [e.episode for e in again.selected]


def test_coverage_note_names_strata_too_thin_to_sample():
    """A one-episode stratum is censused, not sampled — say so before the draw."""
    counts = {"1980s": 5, "1990s": 1, UNASSIGNED: 2}
    note = coverage_note(counts)
    assert "1990s" in note
    assert "censused" in note
    assert "no air date" in note


# ---------------------------------------------------------------------------
# The output audit: things a folder scan cannot fill
# ---------------------------------------------------------------------------

def test_air_date_ordering_survives_a_partial_timeline():
    """The normal case after an import: SOME episodes have a date.

    `sort_key` used to return `(season, air_date)` for dated episodes and
    `(season, episode)` for undated ones, so sorting a mixed list raised
    TypeError comparing str with int. Newly reachable once the sampler began
    filling air dates from the index.
    """
    episodes = [_episode(1, "1985-01-01"), _episode(2, None),
                _episode(3, "1985-03-01"), _episode(4, None)]
    result = sample(episodes, entry_id="s", stratify_by=None, method="spread",
                    per_stratum_n=2, sort_col="air_date", seed=42)
    assert len(result.selected) == 2


def test_dated_episodes_sort_before_undated_ones():
    episodes = [_episode(9, None), _episode(1, "1985-01-01")]
    ordered = sorted(episodes, key=lambda e: e.sort_key("air_date"))
    assert [e.episode for e in ordered] == [1, 9]


def test_a_partial_timeline_is_recorded_in_the_manifest():
    """A spread draw chops the run along this order, so a half-timeline
    changes which episodes are picked. The record has to carry that."""
    episodes = [_episode(1, "1985-01-01"), _episode(2, None)]
    result = sample(episodes, entry_id="s", stratify_by=None, method="spread",
                    per_stratum_n=1, sort_col="air_date", seed=1)
    assert any("have none" in n for n in result.manifest.notes)


def test_ordering_by_a_date_nobody_has_says_so():
    episodes = [_episode(1, None), _episode(2, None)]
    result = sample(episodes, entry_id="s", stratify_by=None, method="spread",
                    per_stratum_n=1, sort_col="air_date", seed=1)
    assert any("NO episode has one" in n for n in result.manifest.notes)


def test_a_registry_csv_carries_its_own_grouping_columns(tmp_path):
    """`stratify_by = any column in Episode.extra` is documented behaviour
    that nothing delivered: `load_registry_csv` dropped unknown columns."""
    import csv as _csv
    from analyzer.sampler import load_registry_csv, stratification_columns
    path = tmp_path / "reg.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = _csv.writer(fh)
        writer.writerow(["season", "episode", "era", "format"])
        writer.writerow([1, 1, "80s", "tv"])
        writer.writerow([1, 2, "90s", "film"])
    episodes = load_registry_csv(path)
    assert episodes[0].extra == {"era": "80s", "format": "tv"}
    assert stratification_columns(episodes) == ["era", "format"]


def test_a_registry_era_is_not_overwritten_by_a_derived_one():
    """An era the researcher typed beats one derived from date ranges.

    Overwriting turned correctly-labelled episodes into one "(no era)"
    stratum, because no date ranges were defined for that source.
    """
    from analyzer.eras import has_declared_eras
    episodes = [_episode(1, "1985-01-01"), _episode(2, "1995-01-01")]
    episodes[0].extra = {ERA_KEY: "80s"}
    episodes[1].extra = {ERA_KEY: "90s"}
    assert has_declared_eras(episodes)
    counts = assign_eras(episodes, [], overwrite=False)
    assert counts == {"80s": 1, "90s": 1}
    # With overwrite (the folder-scan path) the ranges win, as intended.
    assert assign_eras(episodes, ERAS) == {"1980s": 1, "1990s": 1}


def test_manual_selection_warns_about_what_it_could_not_match():
    """A folder scan has no titles, so a title in the manual list matches
    nothing — and that must be reported, not silently dropped."""
    # Shaped like a folder scan: no title, which is what makes S01E02 the
    # label. With a title, label() concatenates to "S01E02E2" — see the
    # label() note in TODO.
    episodes = [Episode(entry_id="show", season=1, episode=i, title=None,
                        air_date=None, runtime=None,
                        filepath=Path(f"e{i}.mp4")) for i in (1, 2, 3)]
    result = sample(episodes, entry_id="s", stratify_by=None, method="manual",
                    manual_list=["S01E02", "3", "A Title"])
    assert [e.episode for e in result.selected] == [2, 3]
    assert any("A Title" in n for n in result.manifest.notes)
    assert result.manifest.probability is False


def test_runtime_is_documented_as_unused():
    """It is set by the registry loader and read by nothing.

    Left in place because it round-trips through a CSV, but the docstring
    must say so — the field otherwise implies duration-weighted sampling
    that does not exist.
    """
    from analyzer.sampler import Episode as _Episode
    assert "read by NOTHING" in (_Episode.__doc__ or "")
