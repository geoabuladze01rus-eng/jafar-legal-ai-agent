# CI validation checkpoint

The feature branch is intentionally validated through a pull request into `main` because the connected GitHub interface does not expose a workflow-dispatch operation.

The CI workflow is configured for pull requests targeting `main` and records installation, compile/import, and pytest diagnostics.

Production Telegram auto-replies remain disabled until CI and inbound dry-run validation pass.
