# SmartTaskBoard Backend Feature Coverage

> Historical / Pre-V1.1 evidence: the completion statements below describe the pre-V1.1 backend
> baseline only. They do not mean V1.1 lifecycle, AI decomposition, route, API, or frontend
> requirements are complete. Use `docs/DEV_00_BASELINE_REPORT.md` for the current V1.1 gap map.

Snapshot date: 2026-08-21.

Backend FEATURE_COVERAGE = 10 / 10 COMPLETE

Counts:

- COMPLETE = 10
- PARTIAL = 0
- NOT_IMPLEMENTED = 0

This matrix tracks backend capability completion. External LLM, ASR, and WeCom delivery are
implemented through provider interfaces and deterministic fake providers for local acceptance;
production enablement still requires real credentials and provider configuration.

PostgreSQL note: the real PostgreSQL integration suites are present and were executed against the
approved isolated database `smarttaskboard_core_test` on `127.0.0.1:46479`. Fresh PostgreSQL
`alembic upgrade head`, current-database upgrade validation, migration tests, API integration tests,
frontend API-contract tests, and local startup probes are included in the accepted evidence below.

## Ten-Wave Coverage

| Wave | Scope | Status | Accepted Evidence |
|---:|---|---|---|
| 1 | Completion review, reviewer snapshot, rejection/rework, immutable review history | COMPLETE | `task_completion_reviews`, service/API/UI coverage, existing PostgreSQL-gated tests |
| 2 | Change requests and full task lifecycle | COMPLETE | `task_change_requests`, approve/reject/cancel, structural patch validation, cancel/withdraw/close/archive/restore/merge, API and service tests |
| 3 | Organization profiles, authorization scopes, system parameters, auth hardening | COMPLETE | `employee_profiles`, `user_authorized_scopes`, `system_parameters`, refresh token rotation/revocation/logout, production auth setting guards |
| 4 | Performance metrics and KPI matching | COMPLETE | `performance_metrics`, `task_performance_matches`, deterministic explainable matching, confirmation workflow, API/service tests |
| 5 | Workload, priority, and conflict detection | COMPLETE | `workload_snapshots`, `task_priority_scores`, `task_conflicts`, persisted calculations, conflict dedupe, acknowledge/ignore/resolve/reopen behavior |
| 6 | Reminder rules, notifications, retry, dedupe, WeCom provider boundary | COMPLETE | `reminder_rules`, `notifications`, due scans, idempotent notification creation, finite retry/backoff, fake WeCom provider |
| 7 | Archive, audit, historical search, reuse | COMPLETE | `task_archives`, `operation_logs`, immutable snapshots, searchable archives, reusable task draft creation, audit log query |
| 8 | AI task intake, extraction, clarification, decomposition, voice path | COMPLETE | `task_inputs`, `ai_extraction_records`, fake ASR/extraction/decomposition providers, clarification loop, confirmed draft creation |
| 9 | `/api/v1` contract closure, Tasks/Inbox/Dashboard integration | COMPLETE | 78 `/api/v1` OpenAPI paths, 84 operations, server-derived available actions, Inbox change-review actions, dashboard notification/conflict/workload/priority projections |
| 10 | Production hardening and local deployment readiness | COMPLETE | production auth restrictions, safe error handling, CORS allow-listing, non-secret token storage, configurable DB connect timeout, health/live and health/ready behavior |

## Core Business Table Coverage

| Table | Status | Evidence |
|---|---|---|
| `users` | COMPLETE | identity, role/status guards, refresh-token ownership |
| `departments` | COMPLETE | hierarchy references and department scope matching |
| `employee_profiles` | COMPLETE | skills, capacity, availability, recommendation input |
| `task_inputs` | COMPLETE | text/voice/WeCom-source raw input trace |
| `ai_extraction_records` | COMPLETE | extraction JSON, confidence, missing/low-confidence fields, confirmation link |
| `tasks` | COMPLETE | lifecycle, optimistic versioning, termination/recovery/merge/archive fields |
| `task_participants` | COMPLETE | primary assignee and role projection |
| `task_nodes` | COMPLETE | execution, rework, structural change validation |
| `task_node_dependencies` | COMPLETE | cycle and same-task dependency validation |
| `task_status_logs` | COMPLETE | immutable workflow/status transition audit |
| `task_progress_reports` | COMPLETE | immutable reports and append-only correction chains |
| `task_issues` | COMPLETE | blocker/resource/support/risk lifecycle |
| `task_change_requests` | COMPLETE | immutable request, snapshots, one pending per task, decision/cancel lifecycle |
| `performance_metrics` | COMPLETE | versionable metric catalog fields and indexes |
| `task_performance_matches` | COMPLETE | explainable scored matching and human confirmation |
| `workload_snapshots` | COMPLETE | reproducible capacity and pressure snapshots |
| `task_priority_scores` | COMPLETE | persisted priority score, quadrant, rank and explanation |
| `task_conflicts` | COMPLETE | dedupe key, open/acknowledged/ignored/resolved states and reopen-on-redetect |
| `reminder_rules` | COMPLETE | due/pending/overdue/report/review/issue/conflict schedules |
| `notifications` | COMPLETE | outbox state, retry metadata, read state and dedupe constraint |
| `task_completion_reviews` | COMPLETE | multi-round immutable completion review |
| `task_archives` | COMPLETE | immutable searchable reusable snapshots |
| `operation_logs` | COMPLETE | generic request/object/action/result audit |
| `user_authorized_scopes` | COMPLETE | user, department, role and all-demo-data scopes |
| `system_parameters` | COMPLETE | typed active parameter catalog with defaults |
| `auth_refresh_tokens` | COMPLETE | hashed rotating refresh tokens and revocation |
| `task_node_participants` | COMPLETE | normalized node owner/collaborator authorization support |

## Migration Chain

Current Alembic head: `f7b8c9d0e1f2`.

- `17f69ea12754_initial_schema.py`
- `576787492bd1_add_progress_reports_and_task_issues.py`
- `c31f8e7a4d02_add_task_completion_reviews.py`
- `d4a8e53b7c19_add_task_change_requests.py`
- `e6f1a2b3c4d5_add_remaining_business_tables.py`
- `f7b8c9d0e1f2_add_auth_refresh_tokens.py`

## Verification Snapshot

- `.\.venv\Scripts\python.exe -m ruff check .`: passed.
- `.\.venv\Scripts\python.exe -m pytest`: `334 passed, 21 skipped`; skipped tests are the explicit PostgreSQL gate when the environment variables are not set.
- `RUN_POSTGRESQL_INTEGRATION=1 .\.venv\Scripts\python.exe -m pytest tests\integration -q`: `21 passed`.
- `.\.venv\Scripts\python.exe -m pytest tests\migrations -q`: `31 passed`.
- `.\.venv\Scripts\python.exe -m pip check`: passed.
- `git diff --check`: passed; Git emitted line-ending conversion warnings only.
- `npm.cmd test -- --run`: `11` files / `34` tests passed.
- `npm.cmd run lint`: passed.
- `npm.cmd run build`: passed.
- `.\.venv\Scripts\python.exe -m alembic heads`: `f7b8c9d0e1f2 (head)`.
- Current PostgreSQL `.\.venv\Scripts\python.exe -m alembic upgrade head`: passed at `f7b8c9d0e1f2`.
- Fresh PostgreSQL `.\.venv\Scripts\python.exe -m alembic upgrade head`: passed from empty database to `f7b8c9d0e1f2`.
- Startup probe with PostgreSQL configured: `/health/live=200`, `/health/ready=200`, OpenAPI `78` paths / `84` operations.
- Database probe: `28` public tables including `alembic_version`, `72` foreign keys, `15` unique constraints, notification duplicate keys `0`, archive orphans `0`, timezone `UTC`.
