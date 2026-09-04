"""
Provenance — the accuracy claims that leave the tool.

`analyzer/provenance.py` is read by the PDF export, the CSV provenance
sidecar, the JSON export and the published site. A wrong claim here is not an
internal inconsistency; it is published.

These tests exist because one was. `METRIC_STATUS` described flashing as a
"deterministic signal measurement — no detection step to validate" while
`analyzer/measurements.py` marked it UNVALIDATED and `CLAUDE.md` §2.2 named it
explicitly as unvalidated and not a safety assessment.
"""

from __future__ import annotations

from analyzer.measurements import MEASUREMENTS, UNFLAGGED_STATUSES, VALIDATED
from analyzer.provenance import (
    METRIC_STATUS, validation_dict, validation_short, validation_statement,
)


def test_no_unvalidated_tool_is_described_as_needing_no_validation():
    """The registry is the authority on status; this is the prose for it.

    Anything the registry marks unvalidated or experimental must not appear
    under a "deterministic" heading here, which reads as "nothing to check".
    """
    deterministic = " ".join(
        entry["label"].lower() + " " + entry["note"].lower()
        for entry in METRIC_STATUS.values()
        if entry["status"] == "deterministic")
    for measurement in MEASUREMENTS:
        tool = measurement.default_tool()
        # A tool the registry itself calls DETERMINISTIC is the case this
        # prose is describing correctly, so it is not the case this test is
        # hunting. What must never appear under the deterministic heading is
        # a tool the registry marks unvalidated or experimental - flashing,
        # which is exactly the defect that produced this file.
        if tool.status in UNFLAGGED_STATUSES:
            continue
        # The measurement's own name must not be claimed as deterministic.
        assert measurement.key.split("_")[0] not in deterministic.split(), (
            f"{measurement.name} is {tool.status} in the registry but is "
            f"described as deterministic in METRIC_STATUS")


def test_flashing_is_stated_as_unvalidated_everywhere_it_is_described():
    """CLAUDE.md §2.2 requires the flag wherever the numbers appear."""
    assert METRIC_STATUS["flashing"]["status"] == "unvalidated"
    for text in (validation_short(), validation_statement()):
        low = text.lower()
        assert "flashing" in low
        assert "unvalidated" in low


def test_flashing_is_never_presented_as_a_safety_assessment():
    """It implements neither the area threshold nor the red-flash criterion."""
    note = METRIC_STATUS["flashing"]["note"].lower()
    assert "not a safety assessment" in note
    assert "area threshold" in note and "red-flash" in note
    assert "not a safety assessment" in validation_statement().lower()


def test_every_accuracy_figure_carries_its_qualifiers():
    """An F1 without ±tolerance, coder count and 'preliminary' is the thing
    CLAUDE.md §2.2 forbids."""
    for text in (validation_short(), validation_statement()):
        low = text.lower()
        assert "preliminary" in low
        assert "single coder" in low or "single-coder" in low
        assert "±2s" in text or "content-dependent" in low


def test_the_machine_readable_export_carries_the_same_statuses():
    """JSON exports must not be quietly kinder than the prose."""
    exported = validation_dict()["metric_status"]
    assert exported["flashing"]["status"] == "unvalidated"
    for key, entry in METRIC_STATUS.items():
        assert exported[key]["status"] == entry["status"]


# ---------------------------------------------------------------------------
# "Wherever their numbers appear" — every surface, not just the report
# ---------------------------------------------------------------------------

def test_the_flag_has_one_source_in_the_engine():
    """Each surface used to decide for itself, and most decided 'not at all'."""
    from analyzer.measurements import ungraded_measurements
    names = [name for name, _why in ungraded_measurements()]
    assert "Flashing" in names, names


def test_the_episode_report_flags_a_result_with_no_recorded_tools():
    """11 of 13 cached episodes here carry no `measurement_tools`.

    The provenance section was skipped entirely for those, so the flashing
    and scene-relation warnings vanished while the numbers stayed on screen.
    """
    from analyzer.schema import EpisodeResult
    from ui.report import episode_html
    result = EpisodeResult(file="a.mp4", duration_sec=600.0)
    assert not result.measurement_tools
    html = episode_html(result)
    assert "Not graded against hand coding" in html
    assert "Flashing" in html


def test_the_comparison_flags_ungraded_measures():
    from analyzer.schema import EpisodeResult
    from ui.report import compare_html
    a, b = (EpisodeResult(file="a.mp4"), EpisodeResult(file="b.mp4"))
    assert "Not graded against hand coding" in compare_html(a, b, "A", "B")


def test_the_index_table_marks_ungraded_columns():
    from ui.index_tab import unvalidated_columns
    flagged = unvalidated_columns()
    assert "flashing_events_per_min" in flagged
    # Validated defaults must NOT be flagged, or the mark means nothing.
    assert "cuts_per_min" not in flagged
    assert "audio_rms_mean" not in flagged


def test_the_component_chart_carries_the_note():
    import inspect
    from ui import chart
    src = inspect.getsource(chart._validation_footnote)
    assert "ungraded_measurements" in src
    assert "not a safety assessment" in src
    assert "_validation_footnote(figure)" in inspect.getsource(
        chart.ChartDialog.__init__)


def test_the_published_site_reads_the_statement_rather_than_restating_it():
    """build_site.py hard-coded a THIRD variant of the F1 figure (~0.84–0.96)
    and repeated the wrong flashing claim. Both were published."""
    import pathlib
    src = pathlib.Path("build_site.py").read_text(encoding="utf-8")
    assert "validation_short" in src
    assert "0.84 on dissolve-heavy" not in src
    assert "color, motion, flashing and audio" not in src


def test_no_shipped_preset_presents_flashing_as_a_safety_matter():
    """`config.json` preset descriptions are rendered in the Settings dialog
    (`ui/settings.py`), so they are interface strings. The Toddler preset read
    "Flashing weighted higher (safety)", which is exactly the safety claim
    CLAUDE.md §2.2 forbids — the measure implements neither the area threshold
    nor the red-flash criterion and is unvalidated.
    """
    import json, pathlib
    cfg = json.loads(pathlib.Path("config.json").read_text(encoding="utf-8"))
    for name, preset in cfg.get("presets", {}).items():
        desc = (preset.get("description") or "")
        low = desc.lower()
        if "safety" in low:
            assert "not a safety assessment" in low, (
                f"preset {name!r} mentions safety without disclaiming it: {desc}")


# ---------------------------------------------------------------------------
# The headline figure's NAME must match its basis
# ---------------------------------------------------------------------------

def test_the_exported_f1_is_not_called_hard_cut():
    """It is scored on the ALL row, and hard_cut-only figures for the SAME two
    runs exist and differ (0.841 / 0.964). A key named `hard_cut_f1` therefore
    named a real but different quantity, with nothing in the file to reveal it.
    Schema 1 wrote that key; schema 2 writes `boundary_f1`.
    """
    exported = validation_dict()
    assert "hard_cut_f1" not in exported
    assert "hard_cut_f1_source" not in exported
    assert exported["boundary_f1"]
    assert exported["provenance_schema"] >= 2


def test_the_exported_figure_states_its_own_basis():
    """The file must not require its reader to infer the estimand from a field
    name — that is the failure this rename is fixing."""
    basis = validation_dict()["boundary_f1_basis"].lower()
    assert "all row" in basis
    assert "±2 s" in basis or "+/-2 s" in basis
    assert "single coder" in basis and "preliminary" in basis


def test_the_basis_describes_the_run_that_produced_the_figure():
    """A live figure pools however many comparison runs this install has; the
    reference study's two episodes are a different claim."""
    from analyzer.provenance import local_boundary_f1
    exported = validation_dict()
    live = local_boundary_f1()
    if live:
        assert exported["boundary_f1"] == live[0]
        assert f"{live[1]} comparison run(s)" in exported["boundary_f1_basis"]
        assert exported["boundary_f1_source"] == "local validation runs"


def test_an_aggregate_score_is_for_one_detector_configuration():
    """Summing ContentDetector and TransNetV2 runs over the same episodes
    gave AGGREGATE F1 0.891 — against their real 0.855 and 0.928 — and hid
    that the shipped detector scores 0.133 on dissolves where TransNetV2
    scores 1.000. `local_boundary_f1` has always filtered; this did not.
    """
    import inspect
    from analyzer.validation import aggregate_summary
    src = inspect.getsource(aggregate_summary)
    assert "detector_tag=detector_tag" in src
    assert "detector_tags" in src


def test_the_summary_command_reports_per_detector():
    import inspect
    import validate_cuts
    src = inspect.getsource(validate_cuts.cmd_summary)
    assert "detector_tag=tag" in src
    assert "describes no" in src and "detector you can actually run" in src


def test_no_public_text_claims_the_composite_is_grounded_or_validated():
    """README and the generated site are where overclaims reach an audience.

    The composite's weights and ceilings are AI-generated defaults never traced
    to a source (`ARCHITECTURE.md` §8.1a). Huston & Wright and Lang justify
    WHICH properties are measured and say nothing about how to combine them, so
    a phrase like "empirically grounded database of FFC profiles"
    claims a derivation that does not exist. Four such phrasings were live on
    2026-08-14, including the site's landing page.
    """
    import pathlib
    import re

    banned = re.compile(
        r"empirically[- ]grounded|scientifically[- ]validated|"
        r"literature[- ]grounded|evidence[- ]based (composite|score|index)",
        re.I)
    targets = [pathlib.Path("README.md"), pathlib.Path("build_site.py")]
    for path in targets:
        if not path.exists():
            continue
        hit = banned.search(path.read_text(encoding="utf-8"))
        assert not hit, (
            f"{path} claims the composite is grounded/validated "
            f"({hit.group(0)!r}); the measurement set is grounded, the "
            f"weighting is not. See ARCHITECTURE.md §8.1a and CEILINGS.md")
