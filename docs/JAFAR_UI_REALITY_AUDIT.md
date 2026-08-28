# JAFAR UI reality audit

Status: factual audit, no fabricated data.

| Module | Reality | Evidence |
|---|---|---|
| Главная | LIVE_BACKEND_PARTIAL | Dashboard now loads `/v1/matters`; other cards are safe placeholders. |
| Дела | LIVE_REAL_DATA | `JafarMattersViewModel` and matter APIs. |
| Календарь | LIVE_BACKEND_BUT_PARTIAL | Deadline/event views exist; no aggregate calendar feed. |
| Документы | LIVE_BACKEND_BUT_PARTIAL | Read-only repository/API path. |
| Правовой позиция | LIVE_REAL_DATA | LegalPosition service/API and Swift view. |
| Почта | LIVE_BACKEND_BUT_PARTIAL | Gmail read-only metadata gateway. |
| Правовой радар | COMING_SOON | No backend source wired. |
| Практика | COMING_SOON | No implementation found. |
| Черновики | SAFE_EMPTY | No persisted draft feed. |
| Голосовые материалы | SAFE_EMPTY | No persisted recording feed. |
| Аналитика | COMING_SOON | No metrics endpoint. |
| Библиотека норм | COMING_SOON | No source wired. |
| Проверка контрагентов | COMING_SOON | No source wired. |
| Настройки | LIVE_BACKEND_PARTIAL | Local connection settings only. |

JusticeHeroView is an SF Symbols composition (`scalemass.fill` + `crown.fill`),
not approved artwork; replacement is a later design task.

UI-P0: matters, documents, deadlines, legal position, read-only mail, truthful
loading/empty/error states. UI-P1: dashboard deadlines, persisted findings and
voice materials. UI-P2: radar, analytics, norms and counterparty checks.
