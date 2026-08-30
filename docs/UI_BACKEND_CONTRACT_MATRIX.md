# Justice AI UI → backend contract matrix

| Screen | Current contract | Evidence |
|---|---|---|
| Dashboard | PARTIAL/LIVE | `/v1/dashboard` returns matters, signals, deadlines and approvals |
| Matters | LIVE | `/v1/matters` and owner-scoped matter lookup |
| Matter Overview | LIVE/PARTIAL | `/v1/matters/{id}` plus existing detail client |
| Documents | LIVE metadata | `/v1/matters/{id}/intelligence/documents` maps persisted source-linked events; no file download |
| Evidence | LIVE empty-capable | endpoint exists; evidence layer is not persisted/queryable by matter yet |
| Timeline | LIVE | endpoint maps deterministic matter events with source/provenance |
| Contradictions | LIVE empty-capable | endpoint exists; contradiction engines currently require in-memory graph input |
| Case Law | LIVE empty-capable | endpoint exists; authority pipeline has no matter repository |
| AI Council | LIVE empty-capable | endpoint returns `not_generated`; GET never invokes models |
| Legal Position | LIVE empty-capable | endpoint returns explicit `not_generated` state |
| Hearing Preparation | LIVE empty-capable | endpoint returns explicit unavailable state |
| Court Mode | PARTIAL | projection UI exists; no persisted hearing/court outline query yet |
| Approval Center | LIVE | existing approvals API and local authentication flow |
| AI Cost Dashboard | PARTIAL | privacy-safe cost service exists; matter cost route is empty until ledger query is exposed |
| Search | PARTIAL | local UI search only; no global backend search contract |
| Notifications | PARTIAL | dashboard signal/alerts store; no dedicated notification query |
| Settings | LIVE/local | connection, keychain and device security settings |

All intelligence routes are authenticated by the existing `/v1` middleware in production,
owner-scoped through the server repository, bounded to `limit <= 100`, and read-only. Unknown
or malformed matter IDs return sanitized `404`/`422`. Empty intelligence is represented as an
empty result or `not_generated`; it is never filled with synthetic production data. Synthetic
data remains available only when the explicit Demo Mode toggle is enabled.

## Capability inventory

The evidence graph, contradiction analyzers, authority applicability pipeline, AI Council,
case theory, defense planner and hearing outline are deterministic/domain services, not
matter-keyed repositories. Connecting them as live query endpoints requires persistence and
new contracts; this release deliberately exposes honest empty states rather than inventing
storage or triggering expensive analysis from GET requests.
