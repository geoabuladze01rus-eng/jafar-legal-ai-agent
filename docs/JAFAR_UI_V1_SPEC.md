# JAFAR UI v1 implementation specification

## Product boundary

JAFAR AI is a legal assistant for a lawyer, not an autonomous lawyer. The UI
may analyze, classify, extract and draft. Sending mail, filing documents,
publishing Telegram replies or any consequential external action always requires
an explicit human confirmation flow.

## Screen and navigation map

The macOS-first shell uses a persistent sidebar: Главная, Дела, Календарь,
Документы, Почта, Правовой радар, Практика, Черновики, Голосовые материалы,
Аналитика, Библиотека норм, Проверка контрагентов, Настройки. iPad/iPhone will
later use a compact tab/sidebar adaptation rather than a desktop clone.

Home contains a top bar, Justice hero/command area, Focus of Day, My Matters,
Tasks and Deadlines, Upcoming Hearings, Jafar Activity, Legal Radar, AI Analytics,
Voice Materials and a truthful system-status footer.

## Visual system

Use semantic SwiftUI tokens (no scattered literals): `backgroundPrimary`,
`backgroundSecondary`, `panel`, `panelElevated`, `goldPrimary`, `goldMuted`,
`textPrimary`, `textSecondary`, `border`, `critical`, `warning`, `success`,
`info`. Graphite/near-black surfaces, restrained warm gold, thin borders,
low-glare contrast, 8-point spacing grid, 12/16-point card radii and adaptive
grids are required. Typography uses the system San Francisco family with Dynamic
Type; headings are restrained and readable rather than decorative.

## Component hierarchy

`JafarApp` → `NavigationSplitView` → `JafarSidebar` + `HomeDashboardView`.
Home composes `JafarTopBar`, `JusticeHeroView`, `JafarCommandBar`,
`JafarQuickCommand`, `JafarCard`, `JafarSectionHeader`, `JafarStatusBadge`,
`JafarMatterCard`, `JafarDeadlineRow`, `JafarHearingRow`, `JafarActivityRow`,
`JafarRiskIndicator`, `JafarEmptyState`, `JafarLoadingState` and
`JafarErrorState`. Justice is an abstract/local asset slot until approved artwork
is supplied; no third-party copyrighted image is embedded.

## Data contract and truthfulness

| Component | Backend source/API | Status |
|---|---|---|
| Health/status footer | `GET /health`, `GET /readiness` | LIVE |
| Quick command: последнее письмо | `/v1/command`, Gmail readonly gateway | LIVE |
| Quick command: внимание | `/v1/command` attention summary | LIVE |
| Quick command: дела Павлика | matter update command when query exists | PARTIAL |
| Matter cards | `/v1/matters` and local MatterStore | PARTIAL |
| Deadlines/hearings | MatterStore deadlines; hearing API not present | PARTIAL |
| Activity feed | audit/backend events; no unified dashboard API | PLANNED |
| Legal radar | no verified source contract | PLANNED |
| AI analytics | analysis response fields only | PARTIAL |
| Voice materials | existing voice gateway state | PARTIAL |

Preview/demo models are allowed only in SwiftUI Preview/development fixtures.
Production empty, loading and error states must be explicit and must not invent
client or case data.

## Approval and status language

Every draft displays one of: AI АНАЛИЗ, ЧЕРНОВИК, ТРЕБУЕТ ПРОВЕРКИ,
ОДОБРЕНО АДВОКАТОМ, ГОТОВО К ОТПРАВКЕ, ОТПРАВЛЕНО. The last state is shown only
when a real backend confirms an external action; no UI button may imply sending
or filing without confirmation.

## States and accessibility

All cards define loading, empty, error and human-review states. Use VoiceOver
labels, keyboard focus rings, Dynamic Type, semantic colors plus text/icon
labels, and contrast suitable for gold-on-black. Test widths 1440×900,
1728×1117 and a narrower desktop layout with adaptive priorities.

## Implementation plan

Foundation slice: tokens, navigation shell, sidebar, top bar, hero asset slot,
command bar, quick commands and typed Home dashboard shells. Wire only existing
commands and readiness APIs. Follow-up slices add real calendar/radar/activity
contracts, then dedicated mobile layouts. Database and backend migrations are
out of scope for UI v1.
