# macOS update strategy (design only)

Updates must be signed artifacts with monotonically increasing versions. The updater must reject unsigned content, downgrade attempts, mismatched product identifiers, and feeds served over an untrusted transport.

## Channels

- `beta`: opt-in feed for pre-release builds such as `2.1.0-beta.1`.
- `stable`: signed production feed for released SemVer versions.

The feed URL, key identifier, and channel are configuration, not hardcoded legal-data behavior. GitHub Releases may host the first feed, but the feed contract must allow migration to independent storage without changing the app's update model.

## Rollback and safety

Keep the previous signed app until the new app passes launch validation. If startup fails, retain or restore the previous version and report a recoverable update error. Update signing keys are separate from Apple Developer credentials and must never be committed.

Sparkle is not integrated yet. Select it only after confirming the current XcodeGen target, hardened runtime, nested signing order, and feed-signing key lifecycle. No updater is required for the current unsigned foundation artifact.
