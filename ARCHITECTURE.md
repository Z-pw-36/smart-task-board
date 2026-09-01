# Smart Task Board Architecture

> Version: V1.1 target architecture
> Status: normative for all work listed in `docs/DEVELOPMENT_PLAN_V1.1.md`
> Baseline repository commit: `a4d0b3eb4617e4203c32780a6ad3f63d50a82a49`

## 1. Purpose

This file defines the mandatory architecture, dependency direction, code organization, naming,
commenting, security, and test boundaries for Smart Task Board. Read this file before changing
application code. If an implementation task conflicts with this file, stop and update the approved
plan before coding.

## 2. Authoritative technology stack

| Area | Required choice |
|---|---|
| Frontend | React 19, TypeScript, Vite |
| Routing | React Router |
| Server state | TanStack React Query |
| Frontend tests | Vitest, Testing Library, Playwright for end-to-end coverage |
| Backend | Python 3.12, FastAPI, Pydantic 2 |
| Persistence | PostgreSQL, SQLAlchemy 2, Alembic |
| Backend tests | Pytest, PostgreSQL integration tests |
| Target runtime | Responsive mobile H5 / Enterprise WeChat embedded WebView |

The handoff document's `uni-app` and MySQL references are superseded. Do not introduce a second
frontend or persistence stack. The attached second-version HTML is a visual and interaction
contract, not the production runtime entry point.

## 3. Source-of-truth precedence

When sources disagree, apply this order:

1. The user's latest confirmed decision.
2. PRD V1.1 business rules and acceptance criteria.
3. The second-version HTML for page structure, visual language, components, and interactions.
4. The fourth-version explicit-ID database document for baseline table semantics.
5. The frontend handoff for non-conflicting API, DTO, permission, transaction, and error rules.
6. Existing repository behavior as an implementation baseline only.

Every conflict must be recorded in the development plan. Do not silently choose a rule.

## 4. Dependency direction

### 4.1 Frontend

```text
route/page -> feature component -> feature hook -> shared API client -> FastAPI
```

- Pages compose features and route state; they do not implement business algorithms.
- Feature components own user interaction for one business capability.
- React Query hooks own remote state, invalidation, polling, and mutations.
- The shared API client owns authentication, request IDs, error mapping, idempotency headers,
  and transport conversion.
- Presentational shared components do not import feature modules.
- Client-side visibility is not an authorization boundary.

### 4.2 Backend

```text
FastAPI route -> schema/DTO -> feature service -> repository -> SQLAlchemy model -> PostgreSQL
                                  |
                                  +-> AI provider / shared policy
```

- Routes parse HTTP and obtain dependencies; they contain no workflow decisions.
- Schemas validate transport fields and expose camelCase aliases.
- Feature services own authorization, state transitions, transactions, orchestration, and audit.
- Repositories own queries and persistence, not business state machines.
- ORM models map storage and local invariants; they are never returned directly over HTTP.
- AI providers own external/model integration. Feature services validate AI results before commit.

## 5. Target code organization

### 5.1 Frontend

```text
web/src/
  app/                         # routing, providers, query client, app shell
  features/
    workbench/
    task-overview/
    task-create/
    task-detail/
    task-decomposition/
    task-execution/
    progress-report/
    task-change/
    completion-review/
    notifications/
    executive-dashboard/
    workload-drilldown/
    profile/
  shared/
    api/                       # client, envelope, transport errors
    components/                # reusable visual primitives
    hooks/
    types/
    utils/
  styles/                      # tokens and global styles
  test/                        # shared test setup/helpers
```

A normal feature directory may contain:

```text
feature-name/
  api.ts
  hooks.ts
  types.ts
  FeaturePage.tsx
  components/
  __tests__/
  index.ts
```

### 5.2 Backend

```text
app/
  api/v1/                      # HTTP routers only
  schemas/                     # request/response DTOs
  services/
    features/
      task_creation/
      task_decomposition/
      task_execution/
      progress_reporting/
      task_change/
      completion_review/
      workload/
      executive_dashboard/
      notifications/
    shared/                    # permissions, idempotency, audit, transaction helpers
  repositories/
  models/
  ai/
  core/
```

Existing large services are migrated incrementally. Preserve compatibility through small facades
while callers move; do not duplicate business rules in old and new modules.

## 6. Feature ownership and public APIs

- Each feature has one clear directory and one public entry (`index.ts` or `__init__.py`).
- Cross-feature imports use public entries; internal files are not imported opportunistically.
- Shared code is extracted only after at least two features use the same semantic behavior.
- Avoid generic dumping grounds such as `helpers.py`, `common_utils.ts`, or `misc.ts`.
- Generated OpenAPI types may live under `web/src/shared/api/generated/` and are exempt from
  manual file-header comments.

## 7. Mandatory file comments

Every new hand-written source file starts with a concise feature header.

Python example:

```python
"""
Feature: Assignee acceptance and AI decomposition.

Responsibilities:
- Validate actor, task state, and task version.
- Create one effective decomposition attempt.
- Transition the task to decomposing and emit audit events.

Does not own: HTTP parsing, raw SQL, or provider implementation.
Plan task: DEV-09.
"""
```

TypeScript example:

```ts
/**
 * Feature: AI decomposition status page.
 * Responsibilities: display processing/failure/success and allow an authorized retry.
 * Data: GET decomposition status; POST retry.
 * Plan task: DEV-09.
 */
```

Before a non-obvious core block, add a short comment naming the business function or explaining why
the guard exists. Do not restate syntax, narrate each line, or leave commented-out code.

## 8. Readability and size rules

- One function performs one primary action.
- Prefer early returns and named policies over nested conditionals; avoid nesting beyond three levels.
- A core function should normally stay below 60 lines.
- A hand-written business file should normally stay below 300 lines.
- Exceptions require a comment in the task completion record and a follow-up split task.
- Use domain names such as `invalidate_running_decomposition`, not `process_data`.
- Remove dead imports, obsolete branches, demo-only business mutations, and commented-out code.
- Do not compress logic into dense one-line expressions merely to reduce line count.
- Do not introduce a base class or abstraction without a current, repeated use case.

## 9. Transport and naming

- PostgreSQL and Python internals use `snake_case`.
- JSON transport uses `camelCase`; Pydantic aliases perform explicit conversion.
- During migration, request DTOs may accept current snake_case names, but target responses and new
  frontend code use camelCase. Compatibility is centralized, not repeated per component.
- Times use ISO 8601 with an explicit offset. Business display uses Asia/Shanghai (`+08:00`).
- People are referenced by `employee_no`; business objects use explicit IDs.
- Status labels are derived by the server or a shared mapping; clients never persist Chinese labels.

## 10. State and write rules

- Status changes occur only through action endpoints and feature services.
- Every write validates authorization, current state, and `taskVersion`.
- Publish, accept, decomposition retry, report, change decision, and review support
  `Idempotency-Key`.
- State changes write `task_status_logs`; sensitive/failed/conflicting writes write
  `operation_logs`.
- Client code cannot submit computed fields such as status, progress aggregates, priority quadrant,
  workload score, issue flags, labels, or action availability.
- Multi-table actions use one unit-of-work transaction and roll back completely on failure.

## 11. V1.1 invariants

- Creator flow is exactly: describe task -> confirm information -> confirm sending.
- The creator neither creates nor approves decomposition nodes.
- Sending creates a `pending_accept` task with no nodes.
- Self-assigned tasks still require acceptance.
- Acceptance transitions to `decomposing`, not directly to `in_progress`.
- A task becomes effective only after valid AI nodes/dependencies commit and `effective_at` is set.
- Failed decomposition leaves the task ineffective and can be retried.
- Cancel, withdraw, or reassignment invalidates a running decomposition; late results are ignored.
- New MVP tasks do not write, display, or calculate with estimated hours.
- Actual hours are system-derived from completion time minus start time and are not editable.
- Completion approval automatically archives the task without writing `archive_snapshot`.
- Collaborators can complete authorized nodes but cannot submit task-level reports or resource requests.
- Production contains no manual role switch, reset-demo-data action, fake success, or business write to
  localStorage.

## 12. Test boundaries

- Backend unit tests cover pure rules and service decisions.
- API tests cover transport, authentication, errors, and response aliases.
- PostgreSQL integration tests cover constraints, transactions, locks, idempotency, and rollback.
- Frontend component tests cover visible behavior, forms, loading, empty, error, and permissions.
- Playwright covers approved cross-page user journeys and responsive viewports.
- Tests mirror feature ownership. A feature is incomplete until its task-specific gate passes.

## 13. Architecture change rule

Any new top-level directory, cross-layer dependency, persistence technology, state library, or shared
abstraction requires an approved update to this file in the same change. The development plan must
record why the change is needed and how existing callers migrate.
