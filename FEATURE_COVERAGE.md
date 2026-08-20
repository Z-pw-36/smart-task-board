# SmartTaskBoard Feature Coverage Matrix

This file is a development traceability record. It does not replace the two authoritative
requirements documents under `docs/`.

Status values: `COMPLETE`, `PARTIAL`, `DESIGNED_ONLY`, `NOT_IMPLEMENTED`, `EXTERNAL_CONFIG_REQUIRED`.

| FEATURE | REQUIREMENT_SOURCE | IMPLEMENTED | PARTIALLY_IMPLEMENTED | DESIGNED_ONLY | NOT_IMPLEMENTED | BLOCKED_BY | DEPENDENCIES | BACKEND | DATABASE | API | FRONTEND | TESTS | STATUS |
|---|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|
| Organization / users | Data v4 tables 1-3; flow section 11 | Yes | Yes | Yes | Yes | Formal enterprise identity | departments/users and prototype identity | Prototype identity and user queries | users, departments | auth, me | Login | Unit/API/PostgreSQL | PARTIAL |
| Task raw input | Flow section 2; Data v4 table 4 | Yes | Yes | No | Yes | ASR/WeCom providers | users | ORM only | task_inputs | None | Text task form bypasses raw-input workflow | Model only | PARTIAL |
| AI extraction | Flow sections 2-3; Data v4 table 5 | Yes | Yes | Yes | Yes | LLM provider for production | task_inputs | ORM linkage only | ai_extraction_records | None | None | Model/linkage only | PARTIAL |
| AI clarification | Flow section 2 | No | No | Yes | Yes | None for deterministic demo adapter | AI extraction | None | JSON fields available | None | None | None | DESIGNED_ONLY |
| Task creation | Flow function 1; Data v4 table 6 | Yes | No | No | No | None | users/nodes | Transactional service | tasks and children | POST task | New task page | Unit/API/PostgreSQL/frontend | COMPLETE |
| Task confirmation | Flow section 5 | Yes | No | No | No | None | task creation | State machine and audit log | tasks/status logs | Action APIs | Detail/Inbox | Unit/API/PostgreSQL/frontend | COMPLETE |
| Task acceptance / return | Flow section 5 | Yes | No | No | No | None | task confirmation | State machine, version, lock | tasks/participants/logs | Action APIs | Detail/Inbox | Unit/API/PostgreSQL/frontend | COMPLETE |
| Self-assigned task | Flow section 5 | Yes | No | No | No | None | task confirmation | Dedicated transition | tasks/participants/logs | Action API | Detail | Unit/API/PostgreSQL | COMPLETE |
| Task nodes | Flow section 3 | Yes | No | No | No | None | task creation | Node workflow | task_nodes | Node APIs | Detail | Unit/API/PostgreSQL/frontend | COMPLETE |
| Node dependencies | Flow section 3 | Yes | No | No | No | None | task nodes | Cycle/dependency guards | task_node_dependencies | Embedded create/read | New task/detail | Unit/API/PostgreSQL/frontend | COMPLETE |
| Task participants | Flow sections 3/11; confirmed explicit-ID design | Yes | Yes | Yes | Yes | Fine-grained delegated capabilities | users/tasks | Task and node participants exist | participant tables | Embedded create/read | New task/detail | Model/service/API | PARTIAL |
| Progress reporting | Frozen Batch 2 design; Data v4 table 11 | Yes | No | No | No | None | task lifecycle/permissions | Immutable/versioned service | task_progress_reports | Submit/list/detail/report-due | Detail/Inbox/Dashboard | Unit/API/frontend/PostgreSQL | COMPLETE |
| Progress correction | Frozen Batch 2 design | Yes | No | No | No | None | progress reporting | Direct-root append correction | corrects_report_id | Submit correction | Detail history/correction | Unit/API/frontend/PostgreSQL | COMPLETE |
| Task issues | Frozen Batch 2 design; Data v4 table 12 | Yes | No | No | No | None | task lifecycle/permissions | Five-state workflow and guards | task_issues | Create/list/detail/actions | Detail/Inbox/Dashboard | Unit/API/frontend/PostgreSQL | COMPLETE |
| Resource requests | Flow sections 8-9; task issue type | Yes | No | No | No | None | task issues | Validated issue subtype | task_issues | Issue APIs | Task detail | Unit/API/frontend/PostgreSQL | COMPLETE |
| Task change requests | Flow section 5; Data v4 table 13 | No | No | Yes | Yes | None | task lifecycle/audit | None | None | None | None | None | NOT_IMPLEMENTED |
| Completion review | Flow function 10; Data v4 table 21 | Yes | Yes | Yes | Yes | Rejection/return-work rule not frozen | task lifecycle/issues | Submit and approve only | status logs only | Existing actions | Detail/Inbox | Unit/API/PostgreSQL | PARTIAL |
| Completion rejection | Flow function 10; autonomous hard-stop rule | No | No | Yes | Yes | Business decision: rework/reopen semantics | completion review | None | None | None | None | None | DESIGNED_ONLY |
| Performance metrics | Flow section 4; Data v4 table 14 | No | No | Yes | Yes | None | organization/system parameters | None | None | None | None | None | NOT_IMPLEMENTED |
| Performance matching | Flow section 4; Data v4 table 15 | No | No | Yes | Yes | None | metrics/tasks | None | None | None | None | None | NOT_IMPLEMENTED |
| Workload | Flow section 6; Data v4 table 16 | No | No | Yes | Yes | None | employee profiles/issues/system parameters | None | None | None | None | None | NOT_IMPLEMENTED |
| Priority | Flow section 7; confirmed remaining-work/time split | No | No | Yes | Yes | None | tasks/performance/system parameters | Basic urgent/deadline ordering only | None | None | Basic task ordering | Basic query tests | PARTIAL |
| Conflict detection | Flow section 8; Data v4 table 18 | No | No | Yes | Yes | None | workload/nodes/tasks | None | None | None | None | None | NOT_IMPLEMENTED |
| Reminder rules | Flow section 9; Data v4 table 19 | No | No | Yes | Yes | None | tasks/issues/system parameters | None | None | None | None | None | NOT_IMPLEMENTED |
| Notifications | Flow section 9; confirmed idempotency | No | No | Yes | Yes | WeCom credentials for production connector | reminder rules/users | None | None | None | None | None | NOT_IMPLEMENTED |
| Enterprise WeChat integration | Flow section 9 | No | No | Yes | Yes | Enterprise credentials | notification provider abstraction | None | None | None | None | None | EXTERNAL_CONFIG_REQUIRED |
| Archive | Flow section 10; Data v4 table 22 | No | No | Yes | Yes | None | completed tasks and process data | None | None | None | None | None | NOT_IMPLEMENTED |
| Historical task reuse | Flow sections 3/10 | No | No | Yes | Yes | None | archive/AI abstraction | None | None | None | None | None | NOT_IMPLEMENTED |
| Permissions | Flow section 11; current service guards | Yes | Yes | Yes | Yes | Formal org scopes not implemented | users/participants | Related-task and action guards | Existing relations | Applied to current routes | Server-driven buttons | Unit/API/PostgreSQL | PARTIAL |
| Authorized scopes | Data v4 table 24 | No | No | Yes | Yes | None | organization/audit | None | None | None | None | None | NOT_IMPLEMENTED |
| Dashboard | Flow functions 3/6 | Yes | Yes | Yes | Yes | Future calculations | task queries | Basic personal summary | Derived | Summary API | Responsive summary | Unit/API/frontend/PostgreSQL | PARTIAL |
| Inbox | Flow functions 3-5/10 | Yes | Yes | Yes | Yes | Future actions | state/query services | Basic derived actions | Derived | Inbox API | Responsive inbox | Unit/API/frontend/PostgreSQL | PARTIAL |
| AI task assistant | Flow functions 1-2 | No | No | Yes | Yes | Production LLM selection/credentials | AI extraction/decomposition | None | Existing input/extraction tables | None | None | None | DESIGNED_ONLY |
| Voice task input | Flow section 2 | No | No | Yes | Yes | Production ASR selection/credentials | raw input/provider abstraction | None | task_inputs fields | None | None | None | EXTERNAL_CONFIG_REQUIRED |
| LLM integration | Flow sections 2-4 | No | No | Yes | Yes | Provider selection/credentials | provider abstraction | None | Existing extraction storage | None | None | None | EXTERNAL_CONFIG_REQUIRED |
| Responsive frontend | Flow user functions; Batch 1 | Yes | Yes | Yes | Yes | Future pages | all feature APIs | N/A | N/A | N/A | Current pages responsive | ESLint/Vitest/build | PARTIAL |
| Audit / operation logs | Data v4 table 23; confirmed Phase 1 minimum | Yes | Yes | Yes | Yes | None | request context/permissions | TaskStatusLog only | task_status_logs | Status log API | Timeline | Unit/API/PostgreSQL | PARTIAL |
| System parameters | Data v4 table 25 | No | No | Yes | Yes | None | workload/priority/reminders | None | None | None | None | None | NOT_IMPLEMENTED |
| Attachments / deliverables | Confirmed task_attachments design | No | No | Yes | Yes | Storage provider for real uploads | reports/issues/reviews | Interface not present | None | None | None | None | NOT_IMPLEMENTED |

## Dependency-ordered implementation waves

1. COMPLETE — Batch 2B: progress reports, corrections, issues, report-due, completion guards,
   REST API, Dashboard/Inbox, responsive task-detail integration and real PostgreSQL acceptance.
2. Wave 1-2: completion review/rework records, task change requests and full lifecycle actions.
3. Wave 3-5: organization scopes, system parameters, performance matching, workload, priority
   and conflict detection.
4. Wave 6-7: reminders, notifications/provider abstraction, archives, operation logs and reuse.
5. Wave 8-9: deterministic AI/voice provider abstractions, clarification workflow, complete API
   and responsive UI closure.
6. Wave 10: production hardening, production-equivalent deployment and final full-system gates.
