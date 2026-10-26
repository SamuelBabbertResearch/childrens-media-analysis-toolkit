# Working together on CMAT

GitHub's `master` branch is the shared baseline. Each laptop has its own copy;
GitHub only receives edits after they are committed and pushed. Pulling only
updates the current branch, not every branch on the laptop.

## Start a piece of work

1. Commit any existing work to its own branch first. Do not discard local edits
   to make a pull succeed.
2. Fetch GitHub updates, switch to `master`, and pull using fast-forward only.
3. Create a short-lived branch for the change, such as `samuel/chart-labels` or
   `liu/audio-metrics`. Avoid doing unrelated work on the same branch.
4. Note which parts you plan to edit so the other researcher can avoid
   overlapping work, especially shared charts, measurement definitions, and
   the project handover.

Equivalent commands, once the working tree is clean:

```text
git fetch origin
git switch master
git pull --ff-only origin master
git switch -c your-name/short-description
```

If fast-forward fails, stop and reconcile the divergent commits; do not force
push or reset away work. Existing local branches may contain unique history.

## Share and integrate

Commit small, meaningful changes and push the working branch regularly. Open a
pull request into `master`, summarize the behavior changed and the verification,
and have the other researcher review it. Integrate new `origin/master` changes
into the working branch when needed, resolve conflicts, and rerun the relevant
checks. Prefer a merge when the working branch is already shared; do not
rewrite the other researcher's published history.

After the pull request is merged, both researchers update their local `master`
before starting the next branch. A pushed working branch or release tag does
not, by itself, update `master`. Branch protection and required checks would
help enforce this workflow, but this guide does not configure those settings.

## Keep the environment and data straight

Use the same supported Python and dependency versions when comparing results.
The v1.3.0 Windows build uses Python 3.12 and PySide6 6.8.3; install source
dependencies from `requirements.txt` and follow the README for language data.
Check `BUILD_INFO.json` when comparing packaged builds.

Keep videos, analysis caches, personal preferences, private paper notes,
pipeline documents, and participant responses out of Git. Share research data
through the project's agreed data workflow and record its provenance separately.
The existing tracked validation artifacts and study records should retain their
intentional history; never regenerate them as a side effect of running tests.

Before pausing work, update `docs/project/onboarding.md` and
`docs/project/TODO.md` with the current branch, completed work, checks, and next
step. Record methodological changes where the project rules require them.

## Release from an exact tested commit

Prefer releases from merged, tested `master`. If a release deliberately targets
an integration branch, record that explicitly and bring the integration back
through review before either person treats `master` as containing it. Tag the
exact source used for the package; do not reuse a published version tag for
different code. A Windows build and a source ZIP are separate deliverables.

This follows [GitHub flow](https://docs.github.com/en/get-started/using-github/github-flow).
