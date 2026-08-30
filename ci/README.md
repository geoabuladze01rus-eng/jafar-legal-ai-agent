# Jafar quality gates

The repository keeps local and GitHub Actions checks on the same executable commands.

## Python gate

```bash
bash ci/run-python-gate.sh
```

This installs the project with development dependencies and runs:

- `ruff check .`
- `python -m compileall -q src`
- `pytest -q`

## Apple gate

Run on a Mac with Xcode and XcodeGen installed:

```bash
brew install xcodegen
bash ci/run-apple-gate.sh
```

The gate regenerates the Xcode project, lists the generated targets, then builds the iOS Simulator and macOS targets with code signing disabled.

## Merge policy

PR #33 remains Draft until the hosted GitHub Actions jobs actually start and both shared gates pass. A `startup_failure` with zero jobs is infrastructure failure, not a successful quality gate.
