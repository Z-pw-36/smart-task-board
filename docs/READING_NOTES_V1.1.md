# SmartTaskBoard V1.1 Reading Notes

## 1. Source Materials

| Material | Source Read | Completeness | Notes |
|---|---|---|---|
| 材料介绍及使用方法.docx | `/Users/panwenzhou/Desktop/旺序-开发文档 2/材料介绍及使用方法.docx` | Full text via `textutil`; 72 lines | Defines DEV-by-DEV execution, DEV-00 deliverables, and no business-code boundary. |
| ARCHITECTURE.md | `ARCHITECTURE.md` | Full file | Normative target architecture; copied into the required repo root location during DEV-00 closeout. |
| DEVELOPMENT_PLAN_V1.1.md | `docs/DEVELOPMENT_PLAN_V1.1.md` | Full file | Defines DEV-00 through DEV-18, target routes, APIs, state machine, database plan; copied into required repo location. |
| CODEX_EXECUTION_PROMPT.md | `CODEX_EXECUTION_PROMPT.md` | Full file | Execution prompt; contains known stale references and DEV-00 checklist; copied into required repo root location. |
| 01-第二版-智能任务看板PRD-V1.1.docx | `docs/reference/01-第二版-智能任务看板PRD-V1.1.docx` | Full text via `textutil`; 3927 lines | Primary business source; copied into required `docs/reference/` location. |
| 02-第二版-智能任务看板前端.html | `docs/reference/02-第二版-智能任务看板前端.html` | Full 216-line HTML plus extracted routes/actions/forms | Visual, component, interaction and navigation contract, not production entry; copied into required `docs/reference/` location. |
| 03-第四版-智能任务看板数据表结构-显式ID版.docx | `docs/reference/03-第四版-智能任务看板数据表结构-显式ID版.docx` | Full text via `textutil`; 1901 lines | Baseline 25-table explicit ID structure; copied into required `docs/reference/` location. |
| 04-第一版-前端交接文档.docx | `docs/reference/04-第一版-前端交接文档.docx` | Full text via `textutil`; 1189 lines | Useful for API/DTO/permission/transaction rules where not superseded; copied into required `docs/reference/` location. |
| Existing repo docs | `README.md`, `PLANS.md`, `FEATURE_COVERAGE.md`, `AUTONOMOUS_RUN.md`, `docs/*.docx` | Read relevant status and source list | Historical baseline; current repo docs are not V1.1 authoritative when conflicting. |

Formal V1.1 material source directory before import:

- `/Users/panwenzhou/Desktop/旺序-开发文档 2`

The material guide and Codex prompt explicitly require the V1.1 files to exist in the repository as `ARCHITECTURE.md`, `docs/DEVELOPMENT_PLAN_V1.1.md`, `CODEX_EXECUTION_PROMPT.md`, and `docs/reference/*`. DEV-00 closeout copied only these development materials into those required locations; no `.env`, secret, token, database data, virtual environment, or local runtime artifact was copied.

SHA-256 for the formal DEV-01 through DEV-18 source set:

| File | SHA-256 |
|---|---|
| `ARCHITECTURE.md` | `e71eea3ae71f0da852595db62d06abda618445c26475eaddcc4a61dfe724207e` |
| `docs/DEVELOPMENT_PLAN_V1.1.md` | `e7369f44ace13685238a7352feeda57dbe3151a20ae0574755d2456e658f5df3` |
| `CODEX_EXECUTION_PROMPT.md` | `dfb9ca7812a3508e2963c220f1e17e34b71e6db443aab456094d6c531ad1ced5` |
| `docs/reference/01-第二版-智能任务看板PRD-V1.1.docx` | `a983b3cbddf2ed4de7940bd7d2ef38083b213bd2ac65d16a71d0cc0ee81c0aa7` |
| `docs/reference/02-第二版-智能任务看板前端.html` | `5af94728d882bc4287f4e76aebab6f685d276cfc5432b161ad198c9a84344586` |
| `docs/reference/03-第四版-智能任务看板数据表结构-显式ID版.docx` | `912c23e9be14021a8d14e71c3ea80308cb9f0667b2ecae63eafffcda168185b8` |
| `docs/reference/04-第一版-前端交接文档.docx` | `a892390919079ee17ad8a85efce402090b3f2f3afe9cf5c6b1c08b88c82fd10e` |
| External `材料介绍及使用方法.docx` | `810c89547b4b3c8eb13a0011a5bf26d4b018d09606f46f12b3ecc5a4b124bc47` |

## 2. Requirement Priority

Priority order for all future work:

1. User latest confirmed instructions.
2. PRD V1.1.
3. Second-version frontend HTML for page structure, visual language, components, interactions and navigation.
4. Fourth-version explicit-ID database structure.
5. First-version frontend handoff for non-conflicting API/DTO/permission/transaction/error rules.
6. Current repository behavior as implementation baseline only.

## 3. Product Requirements

- Product goal: turn fragmented instructions into structured task facts, executable nodes, trackable progress, workload and priority signals, performance linkage, review and archive.
- MVP includes login/current user, workbench, task overview/detail, notifications, profile, executive dashboard, AI input/extraction, creator three-step creation, acceptance-triggered AI decomposition, node execution, progress reports, issues/resources, changes, completion review, automatic archive, priority/workload/conflict/reminder alignment.
- MVP excludes uni-app migration, attachment repository, estimated/planned hours input/display/calculation, user-entered actual hours, creator node approval, manual archive snapshots, production role switch/reset-demo-data, and fake localStorage business writes.
- Creator flow is exactly `describe task -> information confirmation -> confirm sending`.
- Confirm sending creates `pending_accept`, writes task-level data/participants/performance/logs/notifications, and must not create `task_nodes`, dependencies, or node reminders.
- Self-assigned tasks still require the assignee acceptance action.
- Acceptance transitions `pending_accept -> decomposing`; the task becomes effective only after AI result validation and atomic commit.
- AI decomposition creates 5-10 medium-granularity nodes, owner candidates limited to confirmed participants, and succeeds only with at least one valid node, required action detail, legal time windows, and acyclic dependencies.
- Successful decomposition atomically writes nodes, dependencies, reminders, `tasks.effective_at`, `tasks.decomposition_status=succeeded`, and `tasks.status=in_progress`.
- Failed decomposition leaves task ineffective as `decomposition_failed` and supports authorized retry.
- Withdraw, cancel, or main-assignee change during decomposition invalidates the running decomposition; late AI responses must not write nodes, dependencies, reminders, `effective_at`, or task status.

## 4. Task State Machine

Target task statuses:

`draft`, `pending_confirm`, `pending_accept`, `returned`, `decomposing`, `decomposition_failed`, `in_progress`, `blocked`, `pending_report`, `pending_review`, `completed`, `archived`, `cancelled`, `withdrawn`, `merged`, `closed`.

Key target transitions:

| Transition | Rule |
|---|---|
| `draft -> pending_confirm -> pending_accept` | Creator validates task-level information only; no nodes/dependencies. |
| `pending_accept --accept--> decomposing` | Main assignee only; idempotent; creates exactly one active decomposition record. |
| `decomposing --valid AI result--> in_progress` | Nodes, dependencies, reminders and `effective_at` commit atomically. |
| `decomposing --invalid/error--> decomposition_failed` | No effective nodes or task activation. |
| `decomposition_failed --retry--> decomposing` | Main assignee only; idempotent; preserves failed records. |
| `pending_accept --reject--> returned` | Reason required. |
| `in_progress/blocked/pending_report --submit completion--> pending_review` | Requires all effective nodes completed. |
| `pending_review --approve--> completed -> archived` | One transaction; no new `archive_snapshot`. |
| `pending_review --reject--> in_progress` | Reason required; new review round later. |

Current old implementation still contains `accept -> in_progress -> manual planning -> confirm nodes`, including `confirm_self_assigned -> in_progress`. This conflicts with V1.1 and is recorded as a DEV-09/DEV-08 gap only.

## 5. HTML Page / Route / Component Inventory

Routes found in HTML:

- `/workbench`
- `/executive`
- `/tasks`
- `/task/:id`
- `/task/:id/report`
- `/task/:id/review`
- `/create/details`
- `/create/nodes`
- `/create/confirm`
- `/notifications`
- `/profile`

Target V1.1 routes from PRD/development plan add or rename:

- `/task/:taskId/decomposition`
- `/executive/employee-tasks` for employee workload task drilldown. PRD V1.1 section 5.11 and UI scene 41 define this route; the development plan's `/executive/workload-tasks` is superseded by PRD priority.
- old `/create/nodes` is removed from production creator flow

HTML functions and major responsibilities:

- `seed`: mock users, tasks, nodes, participants, progress reports, issues, logs, notifications, workload snapshots, reviews, performance matches and draft data.
- `normalizeState`, `load`, `save`: localStorage-backed demo state.
- `navigate`, `route`, `render`: hash routing and page rendering.
- `nav`, `page`, `header`, `badge`, `taskCard`: shared shell primitives.
- `workbench`, `executive`, `taskOverview`, `taskDetail`, `reportPage`, `reviewPage`, `createDetails`, `createNodes`, `createConfirm`, `notificationsPage`, `profilePage`: page renderers.
- `showSheet`, `showDialog`, `showReasonDialog`, `closeOverlay`: modal/sheet primitives.
- `showOverviewFilters`, `taskMoreSheet`, `showTaskLog`, `workloadSheet`, `peoplePicker`, `metricPicker`: business sheets.
- `startVoice`, `publish`, `copyTaskNo`, `addNotification`, `logStatus`: local mock business actions.

HTML data/action inventory:

- Navigation: `data-route`, `data-task`, `data-nav`, `data-notice`, `data-detail-anchor`, `data-target`, `data-overview-count`, `data-overview-status`, `data-workload`, `data-node`.
- Form/search binding: `data-draft`, `data-node-index`, `data-node-field`, `data-people-search`, `data-picker`, `data-select-person`, `data-select-metric`.
- Actions: `voice`, `ai-submit`, `clear-quadrant`, `all-tasks`, `generic`, `toggle-issue`, `save-draft`, `accordion`, `publish-task`, `mark-read`, `accept-task`, `reject-task`, `confirm-reject`, `review-approve`, `confirm-approve`, `review-reject`, `confirm-review-reject`, `creator-withdraw`, `confirm-withdraw`, `cancel-task`, `confirm-cancel`, `reassign`, `reset-data`, `confirm-reset`, `close-overlay`, `overlay-close`, `task-more`, `show-task-log`, `copy-task-no`, `open-change-request`, `overview-filters`, `overview-reset`, `overview-filter-reset`, `open-overview-node`.

HTML forms:

- `overview-filter-form`: mode/status/quadrant/nearDue/datePreset/startDate/endDate, with custom-date validation.
- `report-form`: progress range, `stageResult` required in prototype, issue switch/note, remark; prototype writes progress/status/actualHours locally.
- Create details fields: task name, metric picker, assignee/reportTo/collaborator/reviewer pickers, deadline, weight, draft text.
- Create nodes: node selected/name/owner/deadline editing; V1.1 removes this from creator production flow.
- Reason dialogs: shared textarea `action-reason`, max length 200.

DEV-00 HTML interaction matrix audit:

- Scan scope: `data-action`, `data-route`, `form`, `button`, `input`, `select`, `textarea`, modal/sheet/dialog references, inline `onclick`, and dynamic JavaScript page/action functions.
- Result: TOTAL HTML INTERACTIONS = 165, MAPPED = 165, UNMAPPED = 0.
- Mapping location: `docs/DEVELOPMENT_PLAN_V1.1.md` section 6.6.
- Important decision: `/create/nodes` is mapped only as removed prototype evidence; it is not a V1.1 production route.

Visual/component inventory:

- App shell capped at 500px, bottom nav, topbar, icon buttons, cards, metrics, status badges, quadrant cards, support card, task cards, progress bars, executive head/filters/metrics/donut/heatmap, detail hero/tabs/timeline/sections/node cards/report/performance, action bar, fields, switch, stepper, node editor, accordion, notifications, profile card, segmented control, menu rows, overlay, sheet, dialog, toast, empty state.

## 6. Database Inventory

Database source defines 25 baseline tables:

`users`, `departments`, `employee_profiles`, `task_inputs`, `ai_extraction_records`, `tasks`, `task_participants`, `task_nodes`, `task_node_dependencies`, `task_status_logs`, `task_progress_reports`, `task_issues`, `task_change_requests`, `performance_metrics`, `task_performance_matches`, `workload_snapshots`, `task_priority_scores`, `task_conflicts`, `reminder_rules`, `notifications`, `task_completion_reviews`, `task_archives`, `operation_logs`, `user_authorized_scopes`, `system_parameters`.

PRD V1.1 requires 27 tables by adding:

- `task_decomposition_records`
- `workload_snapshot_task_details`

V1.1 required field additions:

- `tasks`: `effective_at`, `decomposition_status`, `latest_decomposition_id`.
- `task_nodes`: `decomposition_id`, `source_type`, confirm or add `blocked_reason`.

AI decomposition record required fields:

- `decomposition_id`
- `task_id`
- `triggered_by_employee_no`
- `trigger_type`
- `task_version`
- `idempotency_key`
- `input_snapshot`
- `model_name`
- `model_version`
- `prompt_version`
- `result_json`
- `node_count`
- `error_code`
- `error_message`
- `retry_count`
- `started_at`
- `completed_at`
- `created_at`
- `status`

Status decision: `task_decomposition_records.status` must use PRD V1.1's business-table enum `pending/processing/succeeded/failed/invalidated`. The handoff and PRD async-job protocol use `pending/running/succeeded/failed` for generic `/jobs/{jobId}` style jobs. These are separate status spaces and must not be mixed. The development plan line using `pending/running/succeeded/failed/invalidated` for the decomposition table is superseded by PRD priority.

## 7. API Inventory

Target groups:

- Auth/user: `POST /auth/login`, `GET /me`, `GET /users`, `GET /departments`.
- Input/extraction: `POST /task-inputs`, `POST /task-inputs/{inputId}/extract`, `GET /task-inputs/{inputId}/extraction`.
- Creation/lifecycle: `POST /tasks`, `PATCH /tasks/{taskId}`, `POST /tasks/{taskId}/send`, `POST /tasks/{taskId}/accept`, `POST /tasks/{taskId}/reject`, withdraw/cancel/assignee/merge/close.
- Decomposition: `GET /tasks/{taskId}/decomposition`, `POST /tasks/{taskId}/decomposition/retry`, `GET /jobs/{jobId}`.
- Query/logs: `GET /tasks`, `GET /tasks/{taskId}`, `GET /tasks/{taskId}/status-logs`.
- Execution: node start/update/complete/reopen.
- Progress/issues/change/review/archive: progress report APIs, issue APIs, change-request APIs, completion-review APIs, automatic archive internals and archive query.
- Notifications: `GET /notifications` and real read action only if read storage exists.
- Executive/workload: `GET /executive/overview`, `GET /executive/workload-snapshots/{snapshotId}`, `GET /executive/workload-snapshots/{snapshotId}/tasks`.

Current repo exposes many V1.0/transition APIs, including `/api/v1/tasks/{taskId}/planning/decompose` and `/planning/confirm`, `/api/v1/dashboard/summary`, `/api/v1/tasks/inbox`, node actions, progress/issues/change/review/archive-related routes. OpenAPI baseline: 80 paths, 86 operations, 0 duplicate operation IDs.

## 8. Frontend Gap

- Current routing is `/`, `/tasks`, `/tasks/new`, `/tasks/:taskId`, `/inbox`, `/notifications`, `/archives`; target is `/workbench`, `/task/:taskId`, `/create/details`, `/create/confirm`, `/profile`, `/executive`, `/task/:taskId/decomposition`, `/executive/employee-tasks`.
- Current code has no `web/src/features/*` target organization; pages and shared components remain under `pages/`, `components/`, `api/`, `auth/`.
- Visual system is not the second-version mobile H5 contract; current app is a more generic responsive web UI.
- New task page is three visible steps in React, but API action names and status labels still use old `pending_confirmation/pending_acceptance`; it still includes estimated hours.
- Task detail page still exposes manual AI planning/decompose and manual node confirmation after accept.
- Detail page displays estimated hours and allows estimated hours in planning nodes.
- There are no React pages for AI decomposition status, executive dashboard, workload task drilldown, or profile target route.
- Notifications and current user exist but do not fully match V1.1 pending-action red dot/read rules.

## 9. Backend Gap

- Current state constants use `pending_confirmation` and `pending_acceptance`, not `pending_confirm` and `pending_accept`.
- `TaskWorkflowService.accept_task` transitions directly to `in_progress`; V1.1 requires `decomposing`.
- `confirm_self_assigned` bypasses acceptance and decomposition; V1.1 forbids this.
- `create_task_draft` currently accepts and persists nodes/dependencies and estimated/actual hours; V1.1 send path must be task-level only and no estimated/actual user input.
- Manual planning APIs `/planning/decompose` and `/planning/confirm` exist; V1.1 requires acceptance-triggered decomposition records and automatic commit.
- `task_decomposition_records` model/repository/service/API are absent.
- `tasks.effective_at`, `tasks.decomposition_status`, and `tasks.latest_decomposition_id` are absent.
- `task_nodes.decomposition_id`, `task_nodes.source_type`, and `task_nodes.blocked_reason` are absent or incomplete in current ORM.
- Archive service writes `archive_snapshot`; V1.1 approval must not write new snapshots.
- Several analytics/workload calculations still depend on `estimated_hours`.
- Current services are large (`task_workflow.py`, `business_capabilities.py`) and not yet migrated to `app/services/features/*`.

## 10. AI Gap

- Current AI provider supports extraction and planning suggestions, but not a persisted decomposition attempt lifecycle.
- No idempotency-keyed `task_decomposition_records`.
- No persisted `input_snapshot` for decomposition with task version, participant pool, time window, performance context and prompt version.
- No validated atomic AI success transaction that writes nodes, dependencies, reminders, `effective_at`, and task status together.
- No invalidation policy for withdraw/cancel/main-assignee change during decomposition.
- No late-response guard against stale task version, stale `latest_decomposition_id`, invalidated record, or changed task status.

## 11. Architecture Gap

- Frontend target directories `web/src/app`, `web/src/features`, `web/src/shared`, `web/src/styles` are not yet in place except a small `web/src/app/query-client.ts`.
- Backend target directories `app/services/features/*` and `app/services/shared/*` are not present; feature services are still broad modules.
- Existing APIs and DTOs mostly expose snake_case; target JSON is camelCase with centralized compatibility.
- Current implementation has production-visible prototype/demo concepts in naming and UI.
- Tests are broad, but no Playwright configuration or target viewport matrix exists in the repo.

DEV-00 compliance update:

- Playwright baseline files now exist at `web/playwright.config.ts` and `web/e2e/dev-00-smoke.spec.ts`.
- Required mobile viewport matrix is fixed in config: 375, 390, and 430 px widths.
- Test data isolation convention: all E2E data must use deterministic `DEV00_E2E_` prefixes or backend test fixtures and must not rely on production/demo localStorage writes.
- Dependency declaration exists in `web/package.json` / `web/package-lock.json`; package installation succeeded after retry. DEV-00 verified configuration/test discovery with 3 tests across the required viewport matrix, without running browser binaries.

## 11.1 State / Error / API Compatibility Strategy

State migration:

- Legacy backend/frontend names `pending_confirmation` and `pending_acceptance` are compatibility-only aliases during migration.
- Formal V1.1 names are `pending_confirm` and `pending_accept`.
- DEV-08/DEV-09 must perform the business transition work; DEV-00 only records the contract and must not change the state machine.

Error strategy:

- Frontend pages must consume a single normalized backend error envelope through shared API client/error helpers.
- Pages may render contextual copy, but must not independently parse status codes, raw exception text, or backend validation shapes.
- Target coverage must include 401/403/404/409/422 plus requestId propagation.

API compatibility:

- Python models, database columns, and internal service code remain `snake_case`.
- Target JSON contracts are `camelCase`.
- Compatibility must be centralized in schema/DTO aliasing and shared API client mapping; endpoint-by-endpoint ad hoc conversion is not acceptable.

## 12. Document Conflicts

| Source A | Source B | Conflict | Priority | Decision | Reason |
|---|---|---|---|---|---|
| CODEX_EXECUTION_PROMPT.md | DEVELOPMENT_PLAN_V1.1.md | Prompt asks to read development plan section 1.3/1.4 for DOCX and SHA checks; plan has 1.1/1.2 then product section, no 1.3/1.4 under section 1 and no hash table. | User latest + observed files | Record available SHA-256 values; no hash comparison possible. | Requested known conflict verified. |
| PRD 5.11 and UI scene 41 | DEVELOPMENT_PLAN 5 and 9.2 | PRD route for workload task drilldown is `/executive/employee-tasks`; development plan route is `/executive/workload-tasks`. | PRD V1.1 | Use `/executive/employee-tasks` as the formal V1.1 route. | PRD is higher priority than the development plan for business/page requirements, and it explicitly defines the route in the component matrix and UI coverage table. |
| PRD 8.27 / 6.4 | DEVELOPMENT_PLAN 8.2 and handoff async-job protocol | PRD defines `task_decomposition_records.status` as `pending/processing/succeeded/failed/invalidated`; development plan uses `pending/running/succeeded/failed/invalidated`; generic async job status uses `pending/running/succeeded/failed`. | PRD V1.1 for business table; handoff/PRD async protocol only for generic jobs | Use `pending/processing/succeeded/failed/invalidated` for `task_decomposition_records.status`; keep generic async job status separate as `pending/running/succeeded/failed`. | The PRD explicitly defines the database field in the V1.1 table dictionary. `running` belongs to the generic async job protocol and must not be reused as the decomposition table enum. |
| PRD V1.1 / ARCHITECTURE | Frontend handoff | Handoff keeps old `/create/nodes`, `POST /tasks/decompose`, and accept -> `in_progress`. | PRD V1.1 | Use V1.1: no creator node page; accept -> decomposing. | Handoff is lower priority and older. |
| PRD V1.1 / ARCHITECTURE | HTML prototype | HTML `publish()` creates nodes and estimated hours; `accept-task` sets status to `进行中`; `report-form` requires stage result and increments actual hours. | PRD V1.1 | Treat these as prototype-only gaps. | PRD explicitly corrects old prototype behavior. |
| PRD V1.1 | Fourth-version DB doc | DB doc lists 25 tables and makes `archive_snapshot` required; PRD requires 27 tables and no new snapshot writes. | PRD V1.1 | Add V1.1 extensions in later DEV; migrate archive snapshot nullable later if needed. | PRD defines V1.1 deltas. |

## 13. Open Questions

- Confirm whether a later approved documentation task should update `docs/DEVELOPMENT_PLAN_V1.1.md` section 19 from `TODO` to a completed DEV-00 evidence row; this closeout only imported the formal source file and updated DEV-00 reports.
- Confirm whether notification read storage is deferred entirely or implemented by adding `read_at`/`notification_reads` in a later task.
