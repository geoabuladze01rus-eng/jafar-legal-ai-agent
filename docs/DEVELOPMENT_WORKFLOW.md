# Development and release workflow

## Branches

- `main` is the stable released line. Do not commit directly to it.
- `feature/*`, `fix/*`, and `chore/*` branches contain active work and merge through pull requests.
- `release/*` branches are temporary integration and release-preparation lines.
- Annotated version tags are immutable release records; never move or force-push a release tag.

Before opening a pull request, run the relevant local gates: Ruff, `compileall`, the full pytest suite, and the affected Apple/Ollama checks. GitHub Actions are an independent verification layer, not a replacement for local validation.

Confidential legal material never belongs in tests, fixtures, logs, cloud smoke tests, or packaging artifacts. External-cloud tests use synthetic data only. Ollama remains the default local-first provider for confidential work; cloud use requires explicit policy opt-in.

## Main protection recommendation

The repository API currently returns a plan/visibility error when branch protection or rulesets are queried, so protection could not be safely automated from this environment. Configure the following in GitHub repository settings when the account plan permits it:

- require pull requests for `main`;
- block force pushes and branch deletion;
- require the exact checks `test` (CI), `build` (Jafar Apple), and `test` (Ollama Integration) in their workflow contexts;
- require branches to be up to date when practical;
- require no reviewers for the solo-maintainer workflow;
- retain administrator emergency recovery access.

Verify the resulting rule through the GitHub UI/API before relying on it.
