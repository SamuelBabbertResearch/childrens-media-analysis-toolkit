"""
The claims CMAT makes about itself, tested.

Everything here protects a statement a researcher could be misled by. Each
test names the specific defect it was written for; none of them tests style.

Grouped by the question a methods reviewer would ask:

  1. Does "validated" mean anything?          — the status taxonomy
  2. Is a tuned parameter's score labelled?   — resubstitution bias
  3. Can this row be traced to a build?       — provenance
  4. Is an empty cell distinguishable from 0? — missing-data semantics
  5. Do the presets claim to be norms?        — the age-band configurations
  6. Does the prose promise what the code does? — documentation vs behaviour
"""

from __future__ import annotations

import inspect
import json
import pathlib
import re

import pytest

from analyzer import measurements as M
from analyzer.aggregate import results_to_dataframe
from analyzer.schema import AudioMetrics, EpisodeMetrics, EpisodeResult, SpeechMetrics

REPO = pathlib.Path(__file__).resolve().parent.parent


# ===========================================================================
# 1. The status taxonomy
# ===========================================================================

def test_validated_means_graded_against_human_coding_and_nothing_else():
    """Until 2026-09-04 five tools were marked VALIDATED because there was no
    word for "deterministic, nothing to grade". `describe_selection()` writes
    that word into `measurement_tools` on every cached result, so every CSV,
    JSON export and PDF report carried "Frame differencing [validated]" for a
    tool never compared against any criterion.

    Only `pyscenedetect_content` has a published grading
    (`validation/VALIDATION_LOG.md`). If a second tool is ever graded, add it
    here — deliberately, with the log entry that justifies it.
    """
    graded = {
        (m.key, t.key)
        for m in M.MEASUREMENTS for t in m.tools if t.status == M.VALIDATED
    }
    assert graded == {("transitions", "pyscenedetect_content")}, (
        f"a tool claims VALIDATED without a published grading: {graded}")


def test_a_deterministic_tool_is_not_advertised_as_validated():
    """The bracket tag is what reaches an export. It must not say `validated`
    for a tool that was never graded."""
    for m in M.MEASUREMENTS:
        for t in m.tools:
            tag = M.STATUS_TAG[t.status]
            if t.status == M.DETERMINISTIC:
                assert tag == "deterministic"
            if t.status != M.VALIDATED:
                assert tag != "validated", (m.key, t.key)


def test_deterministic_carries_no_ungraded_warning_and_no_validity_claim():
    """Two things at once, and they pull in opposite directions.

    A deterministic tool must NOT be flagged "never graded against hand
    coding" — there is no detection step to grade, so the flag would be
    noise and would dilute the flags that matter. It must equally not be
    presented as evidence of anything: whether mean HSV saturation is a good
    stand-in for the construct is untested here.
    """
    flagged = {name for name, _why in M.ungraded_measurements()}
    # Deterministic defaults are not in the flag list...
    assert "Motion" not in flagged
    assert "Audio loudness" not in flagged
    # ...and the genuinely ungraded ones still are.
    assert "Flashing" in flagged
    # ...and the prose label never claims validation.
    label = M.STATUS_LABEL[M.DETERMINISTIC]
    assert "validated" not in label
    assert "no detection step to validate" in label


def test_the_registry_is_the_only_source_of_a_tools_status():
    """`_flag_for` derives from the registry rather than restating it, so a
    regrade in one file changes every screen. `LEARNINGS.md` shape 3."""
    from analyzer import constructs as C
    src = inspect.getsource(C._flag_for)
    assert "reg.UNFLAGGED_STATUSES" in src
    assert "reg.STATUS_LABEL" in src


# ===========================================================================
# 2. Resubstitution bias in the parameter sweeps
# ===========================================================================

def test_both_sweeps_declare_that_they_tune_and_score_on_the_same_data():
    """`run_sweep` and `grade_cut_classifier` each fit a parameter by taking
    the maximum over a grid ON a coded sample, then report the score AT that
    parameter ON that same sample. That is a resubstitution estimate and is
    optimistically biased by construction — taking the maximum over a grid
    takes the maximum of the grid's noise too.

    Neither said so. The Trials registry listed "best diss F1 0.42" and
    "kappa 0.71 @ thr 0.55" beside genuinely held-out figures, in one table,
    with nothing to tell them apart.
    """
    from analyzer import validation as V

    prov = V.selection_provenance()
    assert prov["selection_estimate"] == "resubstitution"
    assert prov["tuned_and_scored_on_same_data"] is True
    assert prov["held_out_data"] is False
    low = prov["warning"].lower()
    assert "optimistically biased" in low
    assert "not the detector's accuracy" in low or "not an estimate" in low

    for fn in (V.run_sweep, V.grade_cut_classifier):
        src = inspect.getsource(fn)
        assert "selection_provenance()" in src, (
            f"{fn.__name__} does not attach the bias disclosure")
        # It must reach the manifest on disk, not only the return value: the
        # manifest is what the Trials registry and a future reader see.
        assert src.count("selection_provenance()") >= 2, (
            f"{fn.__name__} attaches the disclosure to only one of "
            f"(manifest, return value)")


def test_the_trials_registry_labels_a_tuned_figure_as_such():
    """A row in the registry is read as a result. A grid maximum is not one."""
    from analyzer import trials
    src = inspect.getsource(trials.discover_trials)
    assert src.count("resubstitution") >= 2, (
        "sweep and classifier-grading rows must both carry the word")


def test_every_surface_that_prints_a_tuned_figure_prints_the_warning():
    """CLI and Tk both. A caveat on one front-end is a caveat a researcher
    using the other never meets."""
    import validate_cuts
    for fn in (validate_cuts.cmd_sweep, validate_cuts.cmd_grade_cuts):
        src = inspect.getsource(fn)
        assert "RESUBSTITUTION_WARNING" in src, fn.__name__

    tk = (REPO / "gui_validation.py").read_text(encoding="utf-8")
    assert "RESUBSTITUTION" in tk


def test_an_undefined_kappa_never_prints_as_a_number():
    """`_cohen_kappa` returns None where kappa is UNDEFINED — both raters used
    a single identical class, so there is no chance agreement to correct for.
    Printing 0.000 there reads as "no agreement beyond chance", the opposite
    of perfect unanimity. It also used to raise TypeError on the format."""
    import validate_cuts
    assert validate_cuts._k(None) == "n/a"
    assert validate_cuts._k(0.0) == "0.000"


# ===========================================================================
# 3. Provenance
# ===========================================================================

def test_the_software_block_identifies_the_build_not_just_the_version():
    from analyzer.version import software_provenance
    prov = software_provenance()
    assert prov["cmat_version"]
    assert prov["git_commit"]
    # The libraries that can move a number, and only those.
    assert set(prov["libraries"]) == {"python", "opencv", "numpy", "scenedetect"}


def test_a_dirty_working_copy_is_never_reported_as_a_clean_commit():
    """A commit hash beside a result promises that code produced it. With
    uncommitted changes the promise is false and the reader must be told."""
    from analyzer import version
    src = inspect.getsource(version.git_commit)
    assert "-dirty" in src
    assert "status" in src and "porcelain" in src
    # And outside a checkout it must not return "" — an empty string reads as
    # "clean" to anything that tests truthiness.
    assert version._NOT_A_CHECKOUT
    assert "not a git checkout" in version._NOT_A_CHECKOUT


def test_there_is_one_implementation_of_the_commit_lookup():
    """`analyzer/validation.py` had a second copy that returned a bare hash
    and could not express "dirty" or "not a checkout"."""
    from analyzer import validation as V
    assert "version_git_commit()" in inspect.getsource(V._git_commit)


def test_a_sampler_manifests_software_version_is_not_shown_as_a_commit():
    """`software_version` in a sampler manifest is the SAMPLER MODULE's
    version string ("1.0.0"). `trials.py` fed it to a field named
    `git_commit`, so the Trials tab displayed "Code version: 1.0.0" for every
    sample ever drawn — a replication researcher would take that for the
    commit that produced the draw."""
    from analyzer import trials
    src = inspect.getsource(trials._discover_sample_trials)
    assert '"git_commit": data.get("cmat_git_commit"' in src
    assert '"software_version": data.get("software_version"' in src


def test_an_episode_result_records_which_build_and_which_input_made_it():
    r = EpisodeResult(file="a.mp4")
    for field in ("analyzed_at_utc", "cmat_version", "git_commit",
                  "source_bytes", "source_sha256"):
        assert hasattr(r, field), field
    # Empty on results cached before the fields existed, and every reader has
    # to treat "" as "not recorded" rather than as a value.
    assert r.analyzed_at_utc == ""
    # A round trip through the cache must not lose them.
    full = EpisodeResult(file="a.mp4", analyzed_at_utc="2026-09-04T00:00:00+00:00",
                         cmat_version="1.2.0", git_commit="abc1234",
                         source_bytes=17, source_sha256="deadbeef")
    back = EpisodeResult.from_dict(json.loads(full.to_json()))
    assert back.git_commit == "abc1234"
    assert back.source_sha256 == "deadbeef"
    assert back.source_bytes == 17


def test_the_engine_attaches_provenance_to_failures_too():
    """A failed analysis is a result a researcher may have to account for, and
    "which build produced this error" is the first question about it. Three
    separate return paths existed; the block is built once so none can be
    written without it."""
    from analyzer import engine
    src = inspect.getsource(engine.analyze_episode)
    assert src.count("**provenance,") == 3, (
        "a return path in analyze_episode carries no provenance")


def _ep(n: int):
    """One episode in a sampling frame, with every field a scan would leave
    None actually None - the ordinary case for a scanned library."""
    from analyzer.sampler import Episode
    return Episode(entry_id="show", season=1, episode=n, title=None,
                   air_date=None, runtime=None, filepath=None)


def test_the_sampler_manifest_preserves_the_frame_it_drew_from():
    """`total_available` counts the candidate frame; nothing recorded what was
    IN it. A redraw against a folder that has since gained three files is a
    draw from a different population, and the manifest could not show it."""
    from analyzer.sampler import Episode, sample
    episodes = [_ep(n) for n in range(1, 7)]
    result = sample(list(episodes), entry_id="show", stratify_by=None,
                    method="srs", per_stratum_n=2, seed=7)
    d = result.manifest.to_dict()

    frame = d["frame_episodes"]["(all)"]
    assert len(frame) == 6, "the frame must be recorded, not only counted"
    assert set(d["strata"][0]["episodes"]) <= set(frame)

    # And what DEFINED a unit, so a second scan can be checked against it.
    fd = d["frame_definition"]
    assert fd["video_extensions"]
    assert fd["season_regex"] and fd["episode_regex"]

    # The commit, under a name that is not the sampler module's version.
    assert d["cmat_git_commit"]
    assert d["cmat_version"]
    assert d["software_version"] != d["cmat_git_commit"]

    # "no exclusions" and "not recorded" must be distinguishable.
    assert d["exclusions"] == []


def test_a_seeded_draw_is_reproducible_and_the_seed_is_kept():
    from analyzer.sampler import sample
    eps = lambda: [_ep(n) for n in range(1, 21)]
    a = sample(eps(), entry_id="s", stratify_by=None, method="spread",
               per_stratum_n=5, seed=1234)
    b = sample(eps(), entry_id="s", stratify_by=None, method="spread",
               per_stratum_n=5, seed=1234)
    c = sample(eps(), entry_id="s", stratify_by=None, method="spread",
               per_stratum_n=5, seed=4321)
    labels = lambda r: [e.label() for e in r.selected]
    assert labels(a) == labels(b)
    assert labels(a) != labels(c), "different seeds must give different draws"
    assert a.manifest.seed == 1234


def test_a_non_probability_draw_is_flagged_and_records_no_seed():
    """A hand-picked set is not a sample, and a seed beside one would imply
    it was drawn."""
    from analyzer.sampler import sample
    episodes = [_ep(n) for n in range(1, 6)]
    r = sample(episodes, entry_id="s", stratify_by=None, method="manual",
               manual_list=["1", "3"], seed=99)
    assert r.manifest.probability is False
    assert r.manifest.seed is None


# ===========================================================================
# 4. Missing data is not zero
# ===========================================================================

def test_a_failed_episode_exports_empty_metrics_not_zeros():
    """Every metric on a failed result sits at its dataclass default of 0.0.
    The CSV exported `cuts_per_min = 0.0` — a plausible figure for a slow
    programme, indistinguishable from one, and silently poolable into a mean.
    """
    ok = EpisodeResult(file="ok.mp4", duration_sec=600.0)
    bad = EpisodeResult(file="bad.mp4", status="failed", error="decode threw")
    df = results_to_dataframe([ok, bad])

    bad_row = df[df.file == "bad.mp4"].iloc[0]
    for col in ("cuts_per_min", "motion_mean", "color_saturation_mean",
                "flashing_events_per_min", "sensory_load_score", "ffc_score",
                "duration_sec"):
        assert bad_row[col] != bad_row[col], f"{col} is not empty on a failure"
    assert bad_row["error"] == "decode threw"

    # A MEASURED zero survives, or the fix has thrown the data away.
    ok_row = df[df.file == "ok.mp4"].iloc[0]
    assert ok_row["flashing_events_per_min"] == 0.0


def test_an_unavailable_measurement_says_which_failure_it_was():
    """"This programme is silent", "this machine has no FFmpeg" and "the
    decode threw" are three different facts. One boolean collapsed them."""
    for reason in (AudioMetrics.REASON_NO_FFMPEG,
                   AudioMetrics.REASON_NO_AUDIO_TRACK,
                   AudioMetrics.REASON_EXTRACTION_FAILED):
        r = EpisodeResult(
            file="x.mp4",
            metrics=EpisodeMetrics(
                audio=AudioMetrics(available=False, unavailable_reason=reason)))
        row = results_to_dataframe([r]).iloc[0]
        assert row["audio_available"] is False or not row["audio_available"]
        assert row["audio_unavailable_reason"] == reason
        assert row["audio_rms_mean"] is None or row["audio_rms_mean"] != row["audio_rms_mean"]


def test_the_audio_extractor_records_the_reason_at_each_failure_site():
    from analyzer import metrics_audio
    src = inspect.getsource(metrics_audio.compute_audio_metrics)
    for reason in ("REASON_NO_FFMPEG", "REASON_NO_AUDIO_TRACK",
                   "REASON_EXTRACTION_FAILED"):
        assert reason in src, reason


def test_speech_reaches_the_export_at_all():
    """WPM and speech density were measured, stored and charted, and then left
    out of `results_to_dataframe` — so the CSV a researcher analysed had no
    words-per-minute column in it."""
    r = EpisodeResult(
        file="x.mp4",
        metrics=EpisodeMetrics(
            speech=SpeechMetrics(available=True, source="srt",
                                 words_per_minute=112.0,
                                 speech_density=0.41, total_words=2000)))
    row = results_to_dataframe([r]).iloc[0]
    assert row["words_per_minute"] == 112.0
    assert row["speech_source"] == "srt"
    # Paired reporting: WPM divides by DIALOGUE time, not runtime, so alone it
    # invites the reading that density answers (CLAUDE.md §2.2).
    assert row["speech_density"] == 0.41


def test_wpm_and_speech_density_are_never_exported_apart():
    cols = set(results_to_dataframe([EpisodeResult(file="x.mp4")]).columns)
    assert ("words_per_minute" in cols) == ("speech_density" in cols)


def test_the_export_carries_the_fingerprint_that_says_what_is_comparable():
    cols = set(results_to_dataframe([EpisodeResult(file="x.mp4")]).columns)
    for col in ("measurement_fingerprint", "cmat_version", "git_commit",
                "analyzed_at_utc", "source_sha256"):
        assert col in cols, col


# ===========================================================================
# 5. The shipped presets
# ===========================================================================

def _presets() -> dict:
    return json.loads((REPO / "config.json").read_text(encoding="utf-8"))["presets"]


def test_no_shipped_preset_claims_to_be_calibrated_or_normed():
    """`Preschool (2-5)` read "Calibrated for preschoolers — the age range in
    Lillard & Peterson (2011)". That study compared two programmes on
    children's immediate executive function and reports no formal-feature
    thresholds; the ceilings were AI-generated defaults never traced to a
    source (ARCHITECTURE.md §8.1a). A reader would take "calibrated" plus a
    citation for a derivation that does not exist.
    """
    # A CLAIM, not a mention. "Calibrated for preschoolers" is the defect;
    # "nothing here is calibrated to it" is the correction. Forbidding the
    # bare word would forbid the sentence that fixes the problem, so a hit
    # only counts when nothing nearby denies it.
    banned = re.compile(
        r"\bcalibrated (for|to|against)\b"
        r"|\b(developmental |age[- ])?norms?\b"
        r"|\bnormative\b"
        r"|\bsafe(ty)? (threshold|range|limit)\b"
        r"|\btolerances?\b"
        r"|\brecommended for\b", re.I)
    DENIALS = ("not a developmental norm", "not a validated norm",
               "nothing here is calibrated", "not a safety assessment",
               "not developmental norms", "not any measured")
    for name, preset in _presets().items():
        desc = preset.get("description", "")
        for match in banned.finditer(desc):
            window = desc[max(0, match.start() - 80):match.end() + 20].lower()
            assert any(d in window for d in DENIALS), (
                f"preset {name!r} says {match.group(0)!r} without denying it "
                f"nearby: {desc}")


def test_every_shipped_preset_declares_itself_illustrative_in_the_data():
    """A caveat only in prose is a caveat the interface has to parse. The
    marker travels with the preset into any config it is saved to."""
    for name, preset in _presets().items():
        assert preset.get("illustrative") is True, name
        assert preset.get("derivation") == "none recorded", name
        assert "ILLUSTRATIVE CONFIGURATION" in preset["description"], name


def test_an_age_named_preset_says_the_age_is_not_the_claim():
    for name, preset in _presets().items():
        if not re.search(r"\(\d+-\d+\)", name):
            continue
        assert "not a developmental norm" in preset["description"], name


def test_the_preset_caveat_is_on_screen_before_the_list_is_opened():
    """A caveat carried only in each preset's own description is one a
    researcher meets AFTER choosing."""
    from analyzer.config_loader import PRESET_BANNER
    low = PRESET_BANNER.lower()
    assert "not validated developmental norms" in low
    assert "preregister" in low
    src = (REPO / "ui" / "settings.py").read_text(encoding="utf-8")
    assert "body.addWidget(banner)" in src
    # It is defined in the engine, not here — see the front-ends test below.
    assert "PRESET_BANNER = _PRESET_BANNER" in src


def test_both_front_ends_read_the_preset_caveat_from_the_engine():
    """`gui.py` (Tk) and `ui/*.py` (Qt) implement the same job twice by design;
    a string copied between them is one that drifts (CLAUDE.md §6).

    It lives in `analyzer/config_loader.py` rather than in `ui/`, because the
    Tk build must not import a Qt module to read a string — `analyzer/`
    imports no framework (CLAUDE.md §2.4). Having the Tk dialog import
    `ui.settings` was a real regression: opening Settings in the classic build
    would have required PySide6.
    """
    from analyzer.config_loader import PRESET_BANNER
    from ui.settings import PRESET_BANNER as qt_banner
    assert qt_banner == PRESET_BANNER, "the Qt build restates it"

    tk = (REPO / "gui.py").read_text(encoding="utf-8")
    assert "from analyzer.config_loader import PRESET_BANNER" in tk
    assert "text=PRESET_BANNER" in tk
    assert "from ui.settings import" not in tk, (
        "the Tk build imports a Qt module")

    # And the wording itself, wherever it is read from.
    low = PRESET_BANNER.lower()
    assert "not validated developmental norms" in low
    assert "preregister" in low


def test_a_user_saved_preset_does_not_inherit_a_derivation_it_lacks():
    """A preset the researcher saves is theirs. It must be marked illustrative
    like the shipped ones, but must not claim their (absent) derivation as its
    own — and both front-ends must say the same thing."""
    from analyzer.config_loader import USER_PRESET_DERIVATION
    assert "user-defined in this install" in USER_PRESET_DERIVATION
    for path in (REPO / "ui" / "settings.py", REPO / "gui.py"):
        src = path.read_text(encoding="utf-8")
        assert '"illustrative": True,' in src, path.name
        assert '"derivation": USER_PRESET_DERIVATION,' in src, path.name
        assert "user-defined in this install; not recorded here" not in src, (
            f"{path.name} restates the string instead of reading it")


# ===========================================================================
# 6. Documentation against behaviour
# ===========================================================================

README = (REPO / "README.md").read_text(encoding="utf-8")


def test_the_readme_makes_no_priority_claim():
    """"the only open integrated tool that…" needs a documented systematic
    comparison with existing software. There is none in this repository."""
    banned = re.compile(
        r"\b(the only|the first)\b[^.\n]{0,80}\b(tool|software|application|"
        r"package|platform|toolkit)\b"
        r"|\bfirst (open[- ]source |open )?(tool|software|toolkit)\b"
        r"|\bunique(ly)? (in|among)\b", re.I)
    hit = banned.search(README)
    assert not hit, f"README makes a priority claim: {hit.group(0)!r}"


def test_no_public_text_calls_human_coding_ground_truth():
    """Human coding is a reference, not truth. It has its own error — this
    project's own is quantised to whole seconds and runs ~0.55 s early — and
    "ground truth" is the word that hides it. `LEARNINGS.md` and the
    validation logs may keep the historical term where they are recounting
    what was said at the time."""
    for path in (REPO / "README.md", REPO / "build_site.py"):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"ground[- ]truth", text, re.I):
            before = " ".join(
                text[max(0, match.start() - 40):match.start()].lower().split())
            before += " "
            # Saying it is NOT a ground truth is the correction, not the
            # defect. Forbidding the phrase outright would forbid the
            # sentence that fixes the problem.
            assert "not a " in before or "not the " in before, (
                f"{path.name} calls human coding a ground truth: "
                f"...{text[max(0, match.start() - 90):match.end() + 60]}...")


def test_the_readme_does_not_promise_train_test_discipline_in_the_workflow():
    """It said the parameter sweep came "with train/test discipline built into
    the workflow". `analyzer/validation.py` has no holdout, no split and no
    leakage check: `run_sweep` takes the grid maximum on the sample it was
    given and returns it. The discipline is the researcher's to impose, and
    saying otherwise invited exactly the report the sweep cannot support."""
    assert "train/test discipline built into the workflow" not in README
    assert "resubstitution" in README.lower(), (
        "the README must say what the sweep's figure actually is")


def test_the_readme_describes_the_metrics_that_are_implemented():
    """A label has to name the computed quantity. `motion` is a frame
    DIFFERENCE, `audio` is linear RMS and not LUFS, `flashing` is a
    whole-frame luminance mean and not a photosensitivity screen."""
    low = README.lower()
    assert "not lufs" in low or "not a perceptual loudness" in low
    assert "whole-frame" in low
    assert "not a photosensitivity" in low or "not a photosensitive" in low


@pytest.mark.parametrize("phrase", [
    "sensory load score",
    "validated composite",
    "empirically grounded",
    "scientifically validated",
])
def test_the_readme_avoids_the_labels_that_imply_a_psychometric_instrument(phrase):
    """"Sensory Load Score" named a psychological quantity CMAT does not
    measure; the composite is a configurable summary of six stimulus
    features and is now the Formal-Feature Composite."""
    assert phrase not in README.lower(), phrase


def test_developmental_norm_appears_only_as_a_denial():
    """The presets section is headed "not validated developmental norms" —
    the phrase is allowed there and nowhere else."""
    low = README.lower()
    for match in re.finditer(r"developmental norms?", low):
        before = low[max(0, match.start() - 30):match.start()]
        assert "not " in before, low[match.start() - 60:match.end() + 40]


def test_the_composite_always_reports_its_components():
    """"No composite should obscure its components." The engine returns them
    with the score, and the export writes each one."""
    from analyzer.metrics_sensory import compute_sensory_load
    sig = inspect.signature(compute_sensory_load)
    assert "config" in sig.parameters
    cols = set(results_to_dataframe([EpisodeResult(file="x.mp4")]).columns)
    for part in ("pacing", "saturation", "contrast", "motion", "flashing",
                 "audio"):
        assert f"sensory_load_{part}" in cols, part


def test_the_effective_weights_are_the_ones_that_produced_the_score():
    """When an episode has no audio the audio weight is redistributed, so the
    nominal weights in config.json are NOT what made the number. Anything
    displaying a breakdown must use these or it shows a table that does not
    add up to the score above it."""
    from analyzer.metrics_sensory import effective_weights
    cfg = json.loads((REPO / "config.json").read_text(encoding="utf-8"))
    with_audio = effective_weights(cfg, audio_available=True)
    without = effective_weights(cfg, audio_available=False)
    assert without["audio"] == 0.0
    assert without["pacing"] > with_audio["pacing"]
    assert abs(sum(without.values()) - sum(with_audio.values())) < 1e-9


# ===========================================================================
# 7. Provenance must survive the paths a result actually travels
# ===========================================================================

def test_rescoring_a_cached_episode_does_not_erase_its_provenance():
    """`analyzer.cache.load_scored()` is documented as THE ONE WAY to read a
    cached result, and it goes through `rescore_episode`. That function used
    to rebuild the dataclass by naming each field it wanted, so every field
    added afterwards was dropped: by 2026-09-04 that was
    `measurement_fingerprint` (nothing left to say whether two rows were even
    measured the same way) and `measurement_tools` (so the report's "not
    graded against hand coding" warning was skipped while the flashing number
    stayed on screen).

    Rebuilding with `dataclasses.replace` keeps everything by construction.
    This test compares against the dataclass's own field list rather than a
    hand-written one, so a field added tomorrow is covered without an edit
    here — the enumeration is what failed last time.
    """
    import dataclasses
    from analyzer.config_loader import load_config
    from analyzer.metrics_sensory import rescore_episode

    before = EpisodeResult(
        file="a.mp4", duration_sec=600.0,
        measurement_fingerprint="abc123def456",
        measurement_tools={"transitions": "X [validated]"},
        analyzed_at_utc="2026-09-04T00:00:00+00:00",
        cmat_version="1.2.0", git_commit="deadbee-dirty",
        source_bytes=17, source_sha256="cafe")
    after = rescore_episode(before, load_config())

    # Everything except the two things a rescore is allowed to change.
    changeable = {"config", "metrics"}
    for f in dataclasses.fields(EpisodeResult):
        if f.name in changeable:
            continue
        assert getattr(after, f.name) == getattr(before, f.name), (
            f"rescoring dropped {f.name!r}")

    # And the raw metrics really are untouched — only the composite moves.
    assert (after.metrics.scene_pacing.cuts_per_min
            == before.metrics.scene_pacing.cuts_per_min)
    assert after.metrics.audio == before.metrics.audio


def test_a_failed_result_passes_through_rescoring_unchanged():
    """There is no composite to derive, and inventing one would turn a failure
    into a score."""
    from analyzer.config_loader import load_config
    from analyzer.metrics_sensory import rescore_episode
    bad = EpisodeResult(file="b.mp4", status="failed", error="decode threw",
                        git_commit="deadbee")
    assert rescore_episode(bad, load_config()) is bad
