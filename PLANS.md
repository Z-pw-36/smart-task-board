# SmartTaskBoard Delivery Plan

This plan tracks execution of `提示词文件.md`. The master specification and verified repository
state take precedence if this summary becomes stale.

## Completed foundation

- [x] Protect and audit the inherited worktree, migration history and baseline tags.
- [x] Restore the project-local Python 3.12 environment and install development dependencies.
- [x] Validate Batch 2B against an isolated PostgreSQL 16 database.
- [x] Close Batch 2B authorization regressions and stale response assertions.
- [x] Pass backend, frontend, migration, OpenAPI, dependency, secret and residual-data gates.

## Remaining delivery waves

- [ ] Wave 1 — immutable completion-review rounds, rejection, explicit rework and resubmission.
- [ ] Wave 2 — immutable task-change requests and complete cancel/withdraw/merge/close lifecycle.
- [ ] Wave 3 — employee profiles, authorized scopes, system parameters and production auth/RBAC.
- [ ] Wave 4 — performance metrics, matching snapshots and explainable recommendations.
- [ ] Wave 5 — workload snapshots, priority scoring and conflict detection.
- [ ] Wave 6 — reminder rules, idempotent notification outbox and provider adapters.
- [ ] Wave 7 — archives, operation logs, structured search and safe task reuse.
- [ ] Wave 8 — AI/voice input workflow with deterministic fake providers and human confirmation.
- [ ] Wave 9 — complete `/api/v1` and responsive frontend closure for all implemented capabilities.
- [ ] Wave 10 — production hardening, production-equivalent deployment, backup/restore and CI.
- [ ] Final acceptance — 25 logical tables or verified equivalents, clean worktree and release tag.

Every wave includes design review, additive migration, model, service, API, necessary UI, tests,
documentation, real PostgreSQL acceptance and the complete quality gate before checkpointing.
