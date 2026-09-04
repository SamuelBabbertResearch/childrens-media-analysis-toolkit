# CMAT Study Runner

> **Adult-only software pilot build.** The 2026-09-01 staged build implements
> one adult self-perception pacing rating per clip and refuses the superseded
> prediction/child package schema. It is `status=pilot`, not an IRB-approved
> collection release. Change it to `approved` only after the final consent,
> participant wording, and operating procedure have IRB/faculty approval and
> the manual pre-use check below has passed on the collection computer.

The Study Runner is a separate participant-facing application. It deliberately
does not import CMAT's analyzer, coding interfaces, OpenCV, scene detection,
speech models, or data-management UI. It shares exactly one module with CMAT
proper — `ui.tokens`, which imports no framework and holds the pace scale's
colours, so the participant palette has one definition rather than two.

## The rating screen

Responses are given on a horizontal labelled ramp, 1 to 5, with a turtle and a
rabbit as end anchors: `study_runner/scale.py`. It is not a styling choice.
Every point is worded, the ramp is a single hue varying only in lightness, the
selected answer is an outline rather than a colour, and nothing is selected
until the participant chooses. Read
[STUDY_RATING_SCALE_DESIGN.md](../STUDY_RATING_SCALE_DESIGN.md) before altering
any of that — the current properties have documented measurement and
accessibility rationales, and `tests/test_study_runner_scale.py` asserts them.
The turtle/rabbit imagery is now an open adult-pilot decision.

## Package layout

```text
study/
  study_config.json
  clips/
    C01.mp4
    ...
participant_data/
```

Schema version 2 freezes the study ID and title, release status, adult question,
instructions, unrecorded practice check, debrief, five scale anchors, twelve
stimulus identities and SHA-256 checksums, and both permitted clip orders. It
refuses schema version 1 and any package containing `target_age_wording`. The
runner verifies every media hash before opening a session.

Order assignment is not chosen on screen. The first anonymous participant code
receives the first configured order, the second receives the second, and the
sequence alternates. Reusing a participant code is refused. The two active
orders must contain all 12 clips, and the second must be the reverse of the
first.

Release statuses are:

- `draft`: development only; refused unless launched with `--allow-draft`.
- `pilot`: pilot sessions, not approved participant data collection.
- `approved`: the IRB/faculty-approved collection package.

The runner records one `adult_self` row per trial in
`participant_data/responses.csv`, including an explicit `skipped` row with an
empty rating when a participant skips. `assignments.csv` preserves alternating
assignment and duplicate-code detection. An atomically replaced progress file
records session completion or technical termination. If a participant stops
while the session is still identifiable, that session's response rows are
removed; its rating-free assignment remains to prevent duplicate enrollment.

## Run from source

```powershell
python study_runner_qt.py --package study --data-dir participant_data
```

## Build the separate executable

**Never build straight into a folder that holds a study package or collected
responses.** PyInstaller's COLLECT step *clears its output directory first*, so
building into a deployed folder deletes the `study/` clips and everything in
`participant_data/` — silently, as a normal part of a successful build. Build
to a staging folder and copy the two build outputs across:

```powershell
python -m pip install -r study_runner-requirements.txt
python -m PyInstaller study_runner.spec -y --distpath dist\_staging
```

Then update a deployment by replacing only the executable and `_internal`,
leaving `study/` and `participant_data/` alone. Close the running Study Runner
first — Windows locks the executable while it runs, and a copy that fails
half-way leaves a stale executable beside a new `_internal`:

```powershell
Copy-Item "dist\_staging\CMAT Study Runner\CMAT Study Runner.exe" "dist\CMAT Study Runner\" -Force
Remove-Item "dist\CMAT Study Runner\_internal" -Recurse -Force
Copy-Item "dist\_staging\CMAT Study Runner\_internal" "dist\CMAT Study Runner\_internal" -Recurse
```

The deployed executable is `dist/CMAT Study Runner/CMAT Study Runner.exe`. Put
the frozen `study` folder beside it. The runner resolves it relative to the
executable itself, regardless of the current working directory. If it is
missing or invalid, the runner stays visible, explains the problem, and offers
to browse to another package folder.

**A running executable is a stale executable.** Source changes do not reach a
frozen build until it is rebuilt; if a change is not visible in the `.exe`,
check its build time before looking for a bug.

## Qualification and remaining pre-use check

The adult-only rewrite has automated coverage for package refusal, alternating
assignment, exact one-row-per-clip collection, skip, withdrawal, technical
restart, scale behavior, and the absence of group/order selectors. Run:

```powershell
python -m pytest tests/test_study_runner.py tests/test_study_runner_scale.py tests/test_study_runner_ui.py -q
python qualify_study_runner.py --package "dist\_adult_only_staging\CMAT Study Runner\study"
```

On 2026-09-01, 30 focused tests passed; the staged executable launched without
early exit; and Qt Multimedia loaded and advanced playback for all 12 checksum-
verified clips (30.00–30.03 seconds each). This is technical qualification.
Before a pilot or collection session, a researcher must still run one complete
manual session on the actual collection computer, visibly inspect every clip,
hear its audio at the approved calibrated setting, confirm the response export,
and verify that the package text exactly matches the approved IRB materials.
