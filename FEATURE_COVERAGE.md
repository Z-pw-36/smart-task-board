# SmartTaskBoard Feature Coverage Matrix

This file is the auditable development traceability record for SmartTaskBoard. It does not
replace the two authoritative requirements documents under `docs/` or the higher-priority
master specification in `提示词文件.md`.

Snapshot date: 2026-08-20. A code draft, ORM class, migration file, or table by itself is not
evidence that a business capability is complete.

## Status and evidence rules

Status values:

- `COMPLETE`: the requested business path is implemented and its applicable unit, API,
  frontend, migration, and real PostgreSQL evidence has passed.
- `IN_PROGRESS`: implementation is actively under way, but the complete acceptance evidence
  has not passed.
- `PARTIAL`: useful behavior exists, but a named part of the requirement is still absent.
- `DESIGNED_ONLY`: a design exists without an accepted implementation.
- `NOT_IMPLEMENTED`: no accepted implementation exists.
- `EXTERNAL_CONFIG_REQUIRED`: only the real external integration is blocked by credentials or
  provider configuration; deterministic local behavior must still be implemented and tested.

Cross-cutting invariants:

- `blocked` and `pending_report` are derived flags, never task lifecycle states. The lifecycle
  uses `draft`, `pending_confirm`, `pending_accept`, `returned`, `in_progress`,
  `pending_review`, `completed`, `archived`, `cancelled`, `withdrawn`, `merged`, and `closed`.
- Every mutation must enforce role, current state, and `expected_task_version` (or a proven
  equivalent lock), return a stable conflict for stale requests, and write immutable audit
  evidence in the same transaction.
- Existing `task_status_logs` do not count as the future generic `operation_logs` table.
- An original logical table is not covered by an unrelated auxiliary table. Equivalence must be
  explicit and verified.

Wave 1 authorization decision, resolving the source-document ambiguity:

- Only the main assignee submits a task for completion review.
- Each review round snapshots the task's explicitly designated `reviewer_employee_no`; when the
  task has no designated reviewer, that round snapshots `creator_employee_no` as the reviewer.
- Creator, executive, administrator, or other identity roles do not automatically grant review
  authority. The actor must equal the reviewer snapshot for that round.

## Detailed business requirement coverage

| ID | FEATURE / REQUIREMENT | REQUIREMENT SOURCE | CURRENT ACCEPTED EVIDENCE | MISSING OR DEFERRED EVIDENCE | TARGET | STATUS |
|---|---|---|---|---|---|---|
| BASE-01 | Organization and prototype users | Data v4 tables 1-3; flow section 11 | `users` and `departments`; prototype identity and related-task guards | Employee profiles, formal identity, organization scopes, token hardening | Waves 3, 9, 10 | PARTIAL |
| BASE-02 | Task raw input persistence | Flow section 2; Data v4 table 4 | `task_inputs` ORM/schema linkage | End-to-end text/voice ingestion, provider metadata, corrections and confirmation | Wave 8 | PARTIAL |
| BASE-03 | AI extraction persistence | Flow sections 2-3; Data v4 table 5 | `ai_extraction_records` ORM/schema linkage | Provider, confidence validation, clarification, repair and final confirmation loop | Wave 8 | PARTIAL |
| BASE-04 | Task creation | Flow function 1; Data v4 table 6 | Transactional task/participant/node/dependency creation; API, UI and PostgreSQL tests | Later lifecycle extensions are tracked separately | Baseline | COMPLETE |
| BASE-05 | Task confirmation | Flow section 5 | Service-controlled transition, version guard and status log; API/UI tests | None for the baseline transition | Baseline | COMPLETE |
| BASE-06 | Task acceptance, return and self-assignment | Flow section 5 | Service-controlled transitions, reasons, locking and status logs; API/UI/PostgreSQL tests | Later change/termination lifecycle is separate | Baseline | COMPLETE |
| BASE-07 | Task nodes and dependencies | Flow section 3 | Node workflow, cycle/dependency guards, plus Wave 1 explicit rework reopen with retained completion history; API/UI/PostgreSQL tests | Wave 2 change-request mutation validation is tracked separately | Baseline / Waves 1-2 | COMPLETE |
| BASE-08 | Task and node participants | Flow sections 3/11; explicit-ID design | `task_participants` and auxiliary `task_node_participants` exist | Formal delegated capabilities and organization-scope interaction | Waves 3 and 9 | PARTIAL |
| B2B-01 | Immutable progress reports | Batch 2 design; Data v4 table 11 | Submit/list/detail/report-due; service/API/UI/real PostgreSQL evidence | None for Batch 2B scope | Batch 2B | COMPLETE |
| B2B-02 | Append-only progress correction | Batch 2 design | Direct-root correction chain and history UI; service/API/PostgreSQL tests | None for Batch 2B scope | Batch 2B | COMPLETE |
| B2B-03 | Issue and resource-request lifecycle | Batch 2 design; Data v4 table 12 | Five-state issue flow, relation/role guards, Inbox/detail/dashboard and PostgreSQL tests | Notification escalation is Wave 6 | Batch 2B / Wave 6 | COMPLETE |
| B2B-04 | Dashboard and Inbox baseline | Flow functions 3-6/10 | Server-derived baseline summaries/actions plus Wave 1 completion-review Inbox actions; responsive pages and tests | Future change, priority, conflict, notification and archive projections | Waves 2-9 | PARTIAL |
| B2B-05 | Current permission guards | Flow section 11 | Related-task visibility and server-derived action guards | Formal employee profiles, authorized scopes and full RBAC/data-scope closure | Waves 3 and 9 | PARTIAL |
| W1-01 | Completion submission preconditions | Flow functions 8/10; master Wave 1 | Main-assignee-only submission validates all nodes and no unclosed issue, creates the next immutable review round with content/version snapshots, and enters `pending_review` atomically | None for Wave 1 scope | Wave 1 | COMPLETE |
| W1-02 | Reviewer snapshot and authorization | Data v4 tasks/review tables; decision above | Each round snapshots the designated task reviewer or, only when absent, the creator; decision authorization uses the snapshot and identity roles grant no implicit authority | None for Wave 1 scope | Wave 1 | COMPLETE |
| W1-03 | Completion approval | Flow function 10; master Wave 1 | Reviewer decides exactly one submitted round, persists approved result/time/version and transitions `pending_review -> completed` without overwriting history | Downstream performance/statistics/archive effects are separate rows | Wave 1 | COMPLETE |
| W1-04 | Completion rejection with mandatory reason | Flow function 10; Data v4 table 21; master Wave 1 | API/service/UI require a nonblank reason, persist the rejected decision and transition `pending_review -> in_progress`; conflict and PostgreSQL tests passed | Notifications are COMP-DOWN-01 | Wave 1 | COMPLETE |
| W1-05 | Whole-deliverable rework | Master Wave 1 | Rejection can require only overall-deliverable rework while all completed nodes and their history remain intact; later resubmission creates a new round | None for Wave 1 scope | Wave 1 | COMPLETE |
| W1-06 | Targeted node rework and explicit reopen | Master Wave 1 | Same-task node validation, explicit reviewer-authorized reopen, retained prior completion history, task/log/version behavior and API/UI/PostgreSQL tests passed | None for Wave 1 scope | Wave 1 | COMPLETE |
| W1-07 | Immutable multi-round review history | Master Wave 1; Data v4 table 21 | Accepted `task_completion_reviews` migration, per-task rounds, one submitted round, preserved decided rounds, safe legacy backfill, history API/UI and migration round-trip | None for Wave 1 scope | Wave 1 | COMPLETE |
| W1-08 | Review details and “待我验收” Inbox | Master Wave 1 | Submit/approve/reject/reopen actions, round detail/history, Inbox projection, task-detail panel and loading/empty/error/conflict/retry frontend coverage passed | Later notification center is Wave 6 | Wave 1 | COMPLETE |
| W1-09 | Review transaction, logs and conflict behavior | Master Wave 1 | Review row, task/node state and immutable status logs share transaction boundaries; stale/duplicate/illegal/cross-task requests and rollback/concurrency behavior are tested | Generic `operation_logs` remains Wave 7 | Wave 1 | COMPLETE |
| W1-10 | Wave 1 migration and full acceptance | Master per-Wave gate | Head `c31f8e7a4d02`; 13 tables; backend 306 passed including 20 real-PG integration tests; frontend 10 files/28 tests; all named quality gates and zero-residual check passed | Checkpoint commit hash has not yet been created | Wave 1 | COMPLETE |
| COMP-DOWN-01 | Completion reminder and notification | Flow sections 5/9 and function 10; Data v4 tables 19-20 | Inbox is a derived work queue, not a persisted notification implementation | Reminder rule, idempotent notification/outbox, retry/channel evidence and WeCom adapter | Wave 6 | NOT_IMPLEMENTED |
| COMP-DOWN-02 | Completion effect on performance linkage | Flow function 10; Data v4 tables 14-15 | No accepted performance tables or matching workflow | Versioned metrics/matches and defined completion-result update semantics | Wave 4 | NOT_IMPLEMENTED |
| COMP-DOWN-03 | Completion effect on workload, dashboard and statistics | Flow section 5 and function 10; Data v4 table 16 | Basic task summary updates from current task state | Persisted/reproducible workload snapshots, completion recalculation and executive statistics evidence | Wave 5 | NOT_IMPLEMENTED |
| COMP-DOWN-04 | Completion-triggered archive and reusable snapshot | Flow functions 8/10; Data v4 table 22 | Completed task remains queryable; no archive table/workflow | Archive trigger, immutable snapshot, review result/history inclusion, search and reuse | Wave 7 | NOT_IMPLEMENTED |
| W2-01 | Immutable task change requests and approval | Flow section 5; Data v4 table 13 | Design only | Table, structural patch/snapshots, atomic approval, rejection reason, dependency validation, API/UI/tests | Wave 2 | NOT_IMPLEMENTED |
| W2-02 | Cancel, withdraw, merge, close, archive-eligible recovery | Master Wave 2 | Baseline state machine only | Complete authorized lifecycle, reasons, non-destructive merge history, recovery and tests | Wave 2 | NOT_IMPLEMENTED |
| W3-01 | Employee profiles and organization scope | Data v4 tables 3 and 24 | Users/departments baseline | Profiles, skills/capacity/status, self/department/subdepartment/person/admin scopes and server filtering | Wave 3 | NOT_IMPLEMENTED |
| W3-02 | System parameters | Data v4 table 25 | Constants exist in application behavior | Typed/versioned parameters, validation, activation and audit | Wave 3 | NOT_IMPLEMENTED |
| W3-03 | Production authentication lifecycle | Master Wave 3 | Prototype login/access token | Refresh rotation/revocation, logout, production prototype-login prohibition and WeCom identity adapter | Waves 3 and 10 | PARTIAL |
| W4-01 | Performance metrics | Flow section 4; Data v4 table 14 | Design only | Version/effective dates/source/import/scope/conditions and API/UI/tests | Wave 4 | NOT_IMPLEMENTED |
| W4-02 | Explainable performance matching | Flow section 4; Data v4 table 15 | Design only | Suggestions, Decimal score/thresholds, algorithm version, reasons, human decisions, override/recompute and immutable history | Wave 4 | NOT_IMPLEMENTED |
| W5-01 | Workload snapshots | Flow section 6; Data v4 table 16 | No persisted calculation | Capacity window, remaining effort, task/urgent/overdue/blocker inputs, versioned snapshot, risk levels and tests | Wave 5 | NOT_IMPLEMENTED |
| W5-02 | Priority scores and explanation | Flow section 7; Data v4 table 17 | Basic urgent/deadline query ordering only | Persisted parameterized score, manual adjustment, explanation and boundary tests | Wave 5 | PARTIAL |
| W5-03 | Conflict detection lifecycle | Flow section 8; Data v4 table 18 | Design only | Capacity/deadline/node/dependency/resource/change conflicts; deduplication; acknowledge/ignore/resolve/reopen | Wave 5 | NOT_IMPLEMENTED |
| W6-01 | Reminder scheduling | Flow section 9; Data v4 table 19 | Design only | Timezone-aware rule parsing/occurrences for reports, deadlines, issues, reviews, changes, conflicts and no-response | Wave 6 | NOT_IMPLEMENTED |
| W6-02 | Idempotent notifications and escalation | Flow section 9; Data v4 table 20 | Design only | Durable notification/outbox, finite retry/backoff, templates/channels/attempts, read state and partial-failure isolation | Wave 6 | NOT_IMPLEMENTED |
| W6-03 | Enterprise WeChat delivery | Flow section 9 | Provider boundary is planned | Fake adapter and tests are required locally; real delivery needs credentials and feature flag | Wave 6 | EXTERNAL_CONFIG_REQUIRED |
| W7-01 | Archive, search and reuse | Flow section 10; Data v4 table 22 | Design only | Immutable archive snapshot, structured search and safe template/task copy | Wave 7 | NOT_IMPLEMENTED |
| W7-02 | Generic operation logs | Data v4 table 23 | `task_status_logs` provide task-state audit only | Generic request/object/action/result log without sensitive content; search/tests | Wave 7 | PARTIAL |
| W8-01 | AI clarification and confirmed extraction | Flow sections 2-4; Data v4 tables 4-5 | Storage baseline only | Deterministic fake provider, confidence/errors, multi-turn repair, human revisions, idempotent confirmed creation | Wave 8 | PARTIAL |
| W8-02 | Voice input | Flow section 2 | `task_inputs` can describe an input source | ASR provider boundary, deterministic fake, transcription metadata/correction and tests; real provider needs credentials | Wave 8 | EXTERNAL_CONFIG_REQUIRED |
| W9-01 | Consistent `/api/v1` closure | Master Wave 9 | Existing baseline APIs use stable errors/auth/actions | All Wave capabilities need pagination/filtering/version/idempotency/request IDs/unique operation IDs and N+1/index evidence | Wave 9 | PARTIAL |
| W9-02 | Necessary responsive frontend closure | Master Wave 9 | Baseline task/board/progress/issue UI | Change, scope, performance, workload, priority, conflict, notification, archive and AI flows with all UI states | Wave 9 | PARTIAL |
| W10-01 | Production hardening and deployment | Master Wave 10 | Development build and current quality gates | Production configuration/secrets/CORS/proxy/health/observability/backups/runbook/deployment and final audit | Wave 10 | NOT_IMPLEMENTED |
| AUX-01 | Attachments and deliverables | Confirmed auxiliary design | Task/report text fields only | Storage/provider-neutral metadata, authorization, API/UI and tests; real storage provider separately configured | Later justified auxiliary work | DESIGNED_ONLY |

## Original 25 logical tables plus the accepted auxiliary table

`MIGRATED + ORM` means only that the accepted Batch baseline has the physical table and model;
the separate feature status still controls whether its business behavior is complete.

| # | TABLE | ORIGINAL BUSINESS RESPONSIBILITY | CURRENT TABLE / MODEL EVIDENCE | FEATURE STATUS | TARGET |
|---:|---|---|---|---|---|
| 1 | `users` | Identity and all employee references | MIGRATED + ORM | PARTIAL | Wave 3/9/10 hardening |
| 2 | `departments` | Organization hierarchy and view scope | MIGRATED + ORM | PARTIAL | Wave 3 |
| 3 | `employee_profiles` | Skills, capability, availability and recommendation | Not present | NOT_IMPLEMENTED | Wave 3 |
| 4 | `task_inputs` | Raw text/voice/WeCom input trace | MIGRATED + ORM | PARTIAL | Wave 8 |
| 5 | `ai_extraction_records` | Structured extraction, confidence and clarification trace | MIGRATED + ORM | PARTIAL | Wave 8 |
| 6 | `tasks` | Task master lifecycle and board data | MIGRATED + ORM | PARTIAL (baseline lifecycle complete; later lifecycle/calculation effects remain) | Waves 1-9 |
| 7 | `task_participants` | Assignee, collaborator, report, reviewer and mentioned roles | MIGRATED + ORM | PARTIAL | Waves 1/3/9 |
| 8 | `task_nodes` | Decomposition, node execution and deliverables | MIGRATED + ORM; explicit Wave 1 reopen retains completion history | COMPLETE for baseline and Wave 1; Wave 2 change mutation pending | Wave 2 extension |
| 9 | `task_node_dependencies` | Dependency ordering and cycle protection | MIGRATED + ORM | COMPLETE for baseline; Wave 2 change validation pending | Wave 2 extension |
| 10 | `task_status_logs` | Immutable task transition/action trace | MIGRATED + ORM; Wave 1 review/rework actions covered | PARTIAL (current task workflows covered; future waves pending) | Waves 2-9 |
| 11 | `task_progress_reports` | Immutable progress and corrections | MIGRATED + ORM | COMPLETE | Batch 2B |
| 12 | `task_issues` | Blocker/resource/support/risk lifecycle | MIGRATED + ORM | COMPLETE | Batch 2B |
| 13 | `task_change_requests` | Immutable requested changes and decisions | Not present | NOT_IMPLEMENTED | Wave 2 |
| 14 | `performance_metrics` | Versioned performance metric catalog | Not present | NOT_IMPLEMENTED | Wave 4 |
| 15 | `task_performance_matches` | Suggested and human-confirmed task/metric matches | Not present | NOT_IMPLEMENTED | Wave 4 |
| 16 | `workload_snapshots` | Versioned capacity and workload calculations | Not present | NOT_IMPLEMENTED | Wave 5 |
| 17 | `task_priority_scores` | Explainable priority calculation snapshots | Not present; basic query ordering is not equivalent | NOT_IMPLEMENTED | Wave 5 |
| 18 | `task_conflicts` | Conflict detection and resolution lifecycle | Not present | NOT_IMPLEMENTED | Wave 5 |
| 19 | `reminder_rules` | Timezone-aware reminder schedules | Not present | NOT_IMPLEMENTED | Wave 6 |
| 20 | `notifications` | Idempotent channel delivery, attempts and read state | Not present | NOT_IMPLEMENTED | Wave 6 |
| 21 | `task_completion_reviews` | Multi-round completion submission and decisions | MIGRATED + ORM at head `c31f8e7a4d02`; service/API/Inbox/detail/UI, safe legacy backfill, migration and real-PG evidence passed | COMPLETE | Wave 1 |
| 22 | `task_archives` | Immutable archive snapshot, search and reuse | Not present | NOT_IMPLEMENTED | Wave 7 |
| 23 | `operation_logs` | Generic request/object/action/result audit | Not present; `task_status_logs` are not an equivalent replacement | NOT_IMPLEMENTED | Wave 7 |
| 24 | `user_authorized_scopes` | Self/org/person/admin data scopes | Not present | NOT_IMPLEMENTED | Wave 3 |
| 25 | `system_parameters` | Typed business parameters and thresholds | Not present | NOT_IMPLEMENTED | Wave 3 |
| AUX-1 | `task_node_participants` | Normalized node-level owners/collaborators | MIGRATED + ORM; justified auxiliary table outside the original 25 | PARTIAL | Waves 3/9 capability extension |

The original 25 names remain individually required unless a future checkpoint documents and
verifies an explicit equivalent design. `task_node_participants` is an additive normalization
and does not replace any original table.

## Wave 1-10 auditable roadmap

Every wave follows: requirements reconciliation -> migration -> ORM -> service -> API -> needed
UI -> unit/API/frontend/real PostgreSQL tests -> documentation -> complete quality gates ->
checkpoint. A wave stays below `COMPLETE` until that entire chain has evidence.

| WAVE | OBJECTIVE | PRIMARY TABLES / SURFACES | COMPLETION-RELATED BOUNDARY | CURRENT STATUS |
|---:|---|---|---|---|
| 1 | Completion review and rework | `task_completion_reviews`, tasks/nodes/status logs, Inbox/detail/history UI | Core submit/approve/reject/rework rounds complete; reminders/performance/statistics/archive remain in their owning waves | **COMPLETE — implementation and total quality gates passed; checkpoint commit candidate not yet created** |
| 2 | Change requests and complete lifecycle | `task_change_requests`, task/node/participant/dependency mutations | Must preserve review/history invariants when approved changes affect a task | NOT_IMPLEMENTED |
| 3 | Organization profiles, authorization and parameters | `employee_profiles`, `user_authorized_scopes`, `system_parameters`, auth | Reviewer relation remains task/round based; identity role alone never authorizes review | NOT_IMPLEMENTED |
| 4 | Performance metrics and matching | `performance_metrics`, `task_performance_matches` | Owns the completion-to-performance-link effect | NOT_IMPLEMENTED |
| 5 | Workload, priority and conflicts | `workload_snapshots`, `task_priority_scores`, `task_conflicts` | Owns completion recalculation and executive statistics | NOT_IMPLEMENTED |
| 6 | Reminders, notifications and escalation | `reminder_rules`, `notifications`, optional occurrence/outbox | Owns completion/rejection/rework reminders and external delivery | NOT_IMPLEMENTED |
| 7 | Archive, audit, search and reuse | `task_archives`, `operation_logs` | Owns completion-triggered archive snapshots and generic audit | NOT_IMPLEMENTED |
| 8 | AI and voice input closure | Extended `task_inputs`/`ai_extraction_records`, provider adapters | Must not bypass review, permission or lifecycle rules | NOT_IMPLEMENTED |
| 9 | Complete API and necessary frontend | All feature APIs, schemas, query indexes and responsive workflows | Final cross-feature completion UI/API consistency and server actions | PARTIAL baseline only |
| 10 | Production hardening and deployment | Runtime configuration, observability, security, backup and runbooks | Final production-equivalent evidence for the complete system | NOT_IMPLEMENTED |

Batch 2B remains checkpoint `7a0cf4e3c6b920d5fea10c351d4d7789f39baf90`: progress
reporting, corrections, issue/resource-request lifecycle, report-due, completion guards,
related REST APIs, Dashboard/Inbox/task-detail integration, and real PostgreSQL acceptance.

Wave 1 is a completed checkpoint candidate. Current evidence is Alembic head `c31f8e7a4d02`,
13 business tables, backend `306 passed` including `20` real PostgreSQL integration tests,
frontend `10 test files / 28 tests passed`, `35` OpenAPI paths and `38` operations. Ruff,
`pip check`, `pip-audit`, SQLAlchemy mapper configuration, Alembic check and downgrade/upgrade,
zero PostgreSQL business residuals, ESLint, TypeScript and Vite build all passed. This file is
part of the Wave 1 checkpoint candidate; no checkpoint commit hash exists yet.
