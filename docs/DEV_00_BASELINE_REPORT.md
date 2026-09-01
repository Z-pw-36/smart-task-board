# DEV-00 Baseline Report

## Environment

- Date/time context: 2026-09-01, Asia/Shanghai.
- Working directory: `/Users/panwenzhou/Projects/SmartTaskBoard`.
- System `python3 --version`: Python 3.14.7.
- Project `.venv/bin/python --version`: Python 3.12.14.
- Required backend Python per `pyproject.toml`: `>=3.12,<3.13`.
- `DATABASE_URL`: SET.
- `POSTGRES_DB`: SET.
- `POSTGRES_USER`: SET.
- `POSTGRES_PASSWORD`: SET.
- `JWT_SECRET_KEY`: SET.
- `PROTOTYPE_AUTH_ENABLED`: SET.
- `ALLOW_TEST_EMPLOYEE_HEADER`: SET.

## Git

- Branch: `main`.
- HEAD: `20a3e33164edd22ddffa05b457fccf5390288cf0`.
- origin/main: `20a3e33164edd22ddffa05b457fccf5390288cf0`.
- Initial status: `## main...origin/main`.

## Source Material Read Status

- `材料介绍及使用方法.docx`: read fully from local package.
- `ARCHITECTURE.md`: read fully and copied into repo root as required by the material guide.
- `docs/DEVELOPMENT_PLAN_V1.1.md`: read fully and copied into required repo location.
- `CODEX_EXECUTION_PROMPT.md`: read fully and copied into repo root as required by the material guide.
- `docs/reference/01-第二版-智能任务看板PRD-V1.1.docx`: read fully and copied into required reference location.
- `docs/reference/02-第二版-智能任务看板前端.html`: read fully; routes, functions, actions, forms, localStorage and mock data inventoried; copied into required reference location.
- `docs/reference/03-第四版-智能任务看板数据表结构-显式ID版.docx`: read fully and copied into required reference location.
- `docs/reference/04-第一版-前端交接文档.docx`: read fully and copied into required reference location.
- Formal notes: `docs/READING_NOTES_V1.1.md`.

Material placement decision:

- `材料介绍及使用方法.docx` says the whole repo must contain `ARCHITECTURE.md`, `docs/DEVELOPMENT_PLAN_V1.1.md`, `docs/reference/01-第二版-智能任务看板PRD-V1.1.docx`, `docs/reference/02-第二版-智能任务看板前端.html`, `docs/reference/03-第四版-智能任务看板数据表结构-显式ID版.docx`, `docs/reference/04-第一版-前端交接文档.docx`, and `CODEX_EXECUTION_PROMPT.md`.
- `CODEX_EXECUTION_PROMPT.md` also requires those same repo paths in its mandatory read order.
- Decision: copy exactly those V1.1 development files into the specified repository locations during DEV-00 closeout; do not copy `.env`, secrets, virtualenvs, database data, or local runtime files.

Source conflict decisions now closed:

| Source A | Source B | Decision | Reason |
|---|---|---|---|
| PRD 5.11 and UI scene 41 define `/executive/employee-tasks` | Development plan route table defines `/executive/workload-tasks` | Formal V1.1 route is `/executive/employee-tasks`. | PRD V1.1 has higher priority for page/business requirements and explicitly defines the route twice. |
| PRD 8.27 defines `task_decomposition_records.status` as `pending/processing/succeeded/failed/invalidated` | Development plan 8.2 uses `pending/running/succeeded/failed/invalidated`; generic async job protocol uses `pending/running/succeeded/failed` | `task_decomposition_records.status` uses `processing`; generic async jobs may use `running` in their separate status space. | PRD explicitly defines the business table field; async job status is not the same database enum and must not be mixed. |

## Backend Baseline

Commands run:

```bash
python3 --version
.venv/bin/python --version
python3 -m ruff check app tests
.venv/bin/python -m ruff check app tests
python3 -m pip check
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
ALLOW_TEST_EMPLOYEE_HEADER=true AUTH_MODE=test_header .venv/bin/python -m pytest -q
```

Results:

- System Python: `Python 3.14.7`; not suitable for project backend.
- Project Python: `Python 3.12.14`.
- `python3 -m ruff check app tests`: failed because system Python has no `ruff`.
- `.venv/bin/python -m ruff check app tests`: passed.
- `python3 -m pip check`: failed; system environment reports `wheel 0.47.0 requires packaging`.
- `.venv/bin/python -m pip check`: passed; no broken requirements.
- `.venv/bin/python -m pytest -q`: failed with 29 API tests returning 401 because the current local default environment uses prototype auth with `ALLOW_TEST_EMPLOYEE_HEADER=false`, while many API route tests intentionally send `X-Employee-No`.
- Canonical test invocation: `ALLOW_TEST_EMPLOYEE_HEADER=true AUTH_MODE=test_header .venv/bin/python -m pytest -q`.
- Canonical result: 345 passed, 21 skipped.
- The ordinary-environment 29 authentication failures are an environment configuration result caused by not enabling the test authentication mode, not a business regression. This conclusion is supported by `app/core/config.py` requiring `ALLOW_TEST_EMPLOYEE_HEADER=true` when `AUTH_MODE=test_header`, `app/api/dependencies.py` reading `X-Employee-No` only in that mode, and the route tests using `X-Employee-No` headers.
- Skips are PostgreSQL integration tests requiring `RUN_POSTGRESQL_INTEGRATION=1`.

## Frontend Baseline

Scripts in `web/package.json`:

- `dev`: `vite`
- `build`: `tsc --noEmit && vite build`
- `lint`: `eslint .`
- `test`: `vitest`

Commands run:

```bash
npm --prefix web install --save-dev @playwright/test --package-lock-only --strict-ssl=false
npm --prefix web install --strict-ssl=false
npm --prefix web run lint
npm --prefix web run test -- --run
npm --prefix web run build
npm exec -- playwright test --list
```

Results:

- Playwright dependency is declared in `web/package.json` / `web/package-lock.json` as `@playwright/test`.
- Runtime npm package installation succeeded after retry with `--strict-ssl=false`; no browser binary download was performed.
- Playwright config: `web/playwright.config.ts`.
- E2E directory: `web/e2e/`.
- Test data isolation convention: E2E-created data must use deterministic `DEV00_E2E_` prefixes or backend test fixtures and must not depend on production/demo localStorage writes.
- Viewport matrix: 375, 390, 430 px.
- Playwright discovery: passed; 3 tests discovered in 1 file across `mobile-375`, `mobile-390`, and `mobile-430`.
- Frontend lint: passed.
- Frontend test: passed; 11 test files, 37 tests.
- Frontend build: passed; TypeScript no emit and Vite build completed.

## Legacy Documentation Alignment

- `PLANS.md`: marked as Historical / Pre-V1.1 evidence; its old wave plan is not V1.1 completion evidence.
- `FEATURE_COVERAGE.md`: marked as Historical / Pre-V1.1 evidence; old backend 10/10 complete does not mean V1.1 is complete.
- `AUTONOMOUS_RUN.md`: marked as Historical / Pre-V1.1 evidence; old next action is superseded by `docs/DEVELOPMENT_PLAN_V1.1.md`.

## HTML Interaction Matrix

- Source: `docs/reference/02-第二版-智能任务看板前端.html`.
- Scan scope: `data-action`, `data-route`, `form`, `button`, `input`, `select`, `textarea`, modal/sheet/dialog references, inline `onclick`, dynamic JavaScript page/action functions.
- TOTAL HTML INTERACTIONS: 165.
- MAPPED: 165.
- UNMAPPED: 0.
- Mapping location: `docs/DEVELOPMENT_PLAN_V1.1.md` section 6.6.
- `/create/nodes` is recorded as prototype-only evidence and is not a formal V1.1 production route.

## State / Error / API Compatibility Strategy

- State migration: legacy `pending_confirmation` and `pending_acceptance` are transitional compatibility names only; formal V1.1 uses `pending_confirm` and `pending_accept`. Business transition changes are deferred to DEV-08/DEV-09.
- Error strategy: frontend must consume unified backend error envelopes through shared API client/error helpers; pages must not parse raw exceptions or invent page-local error formats. Target coverage includes 401/403/404/409/422 and requestId.
- API compatibility: Python/database internals remain `snake_case`; target JSON is `camelCase`; compatibility must be centralized in DTO/schema aliases and shared API client mapping.

## OpenAPI Baseline

- Operations: 86.
- Duplicate operationIds: 0.

## Database Baseline

Commands run:

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
.venv/bin/python -m alembic heads
.venv/bin/python -m alembic current
.venv/bin/python -m alembic check
```

Results:

- Docker access inside sandbox initially failed; with approved local Docker access, `smart-task-board-postgres` is `healthy` and mapped to local 5432.
- Alembic heads: `f7b8c9d0e1f2 (head)`.
- Alembic current: `f7b8c9d0e1f2 (head)`.
- Alembic check: passed; no new upgrade operations detected.
- PostgreSQL integration tests were not enabled during full pytest; they skipped as designed because `RUN_POSTGRESQL_INTEGRATION=1` was not set.

## Current Implementation

Frontend:

- `web/src/App.tsx` uses React Router routes `/`, `/tasks`, `/tasks/new`, `/tasks/:taskId`, `/inbox`, `/notifications`, `/archives`.
- Code is organized under `pages`, `components`, `api`, `auth`, `app`; target `features/shared/styles` structure is not yet adopted.
- `NewTaskPage.tsx` has three visible steps but still sends through old actions and includes `estimated_hours`.
- `TaskDetailPage.tsx` still supports manual planning through `/planning/decompose` and `/planning/confirm`.

Backend:

- FastAPI routers and SQLAlchemy models are present under existing layered directories.
- `TaskWorkflowService` owns large lifecycle logic and still uses `pending_confirmation` / `pending_acceptance`.
- Accept currently transitions directly to `in_progress`.
- Self-assigned confirmation currently transitions directly to `in_progress`.
- Manual plan confirmation is modeled as a post-accept workflow.

Database:

- Current migrations include baseline plus extension migrations through `f7b8c9d0e1f2`.
- Current ORM has no `task_decomposition_records`, no `workload_snapshot_task_details`, and no task decomposition fields on `tasks`.
- `task_archives.archive_snapshot` is currently non-null.

AI:

- Existing AI provider supports extraction and planning suggestions.
- There is no persisted AI decomposition attempt lifecycle, invalidation, or late-response guard.

Auth:

- Prototype Bearer JWT flow exists.
- `X-Employee-No` test header is disabled by default in current env and must be enabled via `AUTH_MODE=test_header` plus `ALLOW_TEST_EMPLOYEE_HEADER=true` for legacy API route tests.

## V1.1 Gap Map

| DEV | Current State | Missing | Dependency | Future Work |
|---|---|---|---|---|
| DEV-00 | Source materials read; required V1.1 files copied into prescribed repo locations; Playwright baseline files added; HTML interaction matrix audited; old docs marked historical; canonical test mode recorded. | Playwright package/browser execution requires network-capable dependency installation in this environment. | None. | DEV-18 will expand E2E and release gates from the DEV-00 baseline. |
| DEV-01 | Generic styles/components. | HTML design tokens and shared mobile primitives. | DEV-00. | Build reusable visual primitives and component mapping. |
| DEV-02 | Old routes and app shell. | `/workbench`, `/task/:taskId`, `/create/*`, `/profile`, `/executive`, decomposition route, redirects. | DEV-01. | Implement target shell/routing/navigation. |
| DEV-03 | Dashboard page exists but not second-version workbench. | Workbench visual contract, AI entry, status/quadrant/support cards. | DEV-02. | Rebuild workbench on real APIs. |
| DEV-04 | Task list exists. | Target overview modes, filters, node mode, URL/session restoration. | DEV-03. | Add server-backed overview behavior. |
| DEV-05 | Detail/report/review exist in older layout. | Target detail modules, no estimated hours, V1.1 read-only action projection. | DEV-04. | Rebuild visual/detail aggregation surface. |
| DEV-06 | Prototype auth exists. | Production-aligned current user, role/scope projection, no role spoofing. | DEV-02. | Align auth/me/allowedActions. |
| DEV-07 | AI intake/extraction and fake provider exist. | Target task input/extract job flow, ASR fallback, clarification UX. | DEV-03, DEV-06. | Implement V1.1 input slice. |
| DEV-08 | Creation can create task and may include estimated hours; API actions use old status names. | Strict task-level send, `pending_accept`, no nodes/dependencies/estimatedHours, self-assigned still waits. | DEV-07. | Implement creator three-step send transaction. |
| DEV-09 | Accept -> `in_progress`; manual planning exists. | `decomposing`, decomposition table/fields, retry, invalidation, late callback protection. | DEV-08. | Implement acceptance-triggered AI decomposition. |
| DEV-10 | Node execution exists for current model. | Enforce only effective V1.1 tasks and participant-limited AI nodes. | DEV-09. | Align node workflow and collaborator permissions. |
| DEV-11 | Progress reports/issues exist. | No actual-hours input, stage result optional, collaborator restrictions, V1.1 transaction rules. | DEV-10. | Align reports and issue closure. |
| DEV-12 | Change/lifecycle actions exist. | V1.1 decomposition invalidation during withdraw/cancel/reassign and target status names. | DEV-09. | Align change, reassign, withdraw, cancel, merge, close. |
| DEV-13 | Completion reviews and archives exist. | Automatic archive without new snapshot; archive snapshot nullable if required. | DEV-10, DEV-11. | Align review/archive transaction and actual-hours calculation. |
| DEV-14 | Priority/workload/conflict basics exist. | Remove estimated-hours dependency; use remaining work window and V1.1 formulas. | DEV-13. | Rework calculations and guards. |
| DEV-15 | Notifications page/API exist; demo behavior remains. | Real notification read/pending semantics, profile, remove production demo role/reset/localStorage writes. | DEV-12, DEV-13. | Align support features and clean prototype affordances. |
| DEV-16 | No target executive page in React. | Authorized team metrics, quadrants, heatmap, workload breakdown. | DEV-14, DEV-15. | Implement executive dashboard. |
| DEV-17 | No workload task details table/page. | `workload_snapshot_task_details`, `/executive/employee-tasks`, historical consistency. | DEV-16. | Implement second-stage workload drilldown using PRD route decision. |
| DEV-18 | No V1.1 E2E/CI gate. | Full E2E, performance/security/OpenAPI release gates. | DEV-17. | Final regression and release acceptance. |

## V1.1 Gap By Capability

- Creation: must remove old node creation/confirmation from creator flow and ensure send leaves zero nodes/dependencies.
- Acceptance: must replace direct `in_progress` acceptance and self-assigned bypass with required accept action to `decomposing`.
- Decomposition: must add persisted attempts, validation, transaction, status page, retry, invalidation and late-result protection.
- Execution: must gate node work to effective tasks only.
- Progress: must remove actual/estimated hours inputs and enforce main-assignee-only task reports.
- Change: must invalidate running decomposition on assignee change/withdraw/cancel.
- Completion: must calculate actual hours and archive automatically without new snapshot writes.
- Notifications: must replace local/demo unread with real notification/pending semantics or hide read actions.
- Executive: must implement target executive dashboard and authorized scopes.
- Workload: must add snapshot task details in second stage and resolve route naming conflict.

## Boundary Check

- Business code modified during DEV-00: no.
- Business migrations added: no.
- DEV-01+ implemented: no.
