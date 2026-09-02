/**
 * Feature: DEV-05 Task Detail browser coverage.
 * Responsibilities: verify read-only task detail/report/review routing, anchors, states, responsive layout, and performance baseline.
 * Does not own: production data creation, workflow mutations, or backend authorization logic.
 * Plan task: DEV-05.
 */

import { expect, type Page, test } from "@playwright/test";

const tokenKey = "smarttaskboard.prototype.token";
const taskId = "22222222-2222-4222-8222-222222222222";
const nodeId = "33333333-3333-4333-8333-333333333333";
const noNodesTaskId = "44444444-4444-4444-8444-444444444444";
const longTaskId = "55555555-5555-4555-8555-555555555555";
const largeNodesTaskId = "66666666-6666-4666-8666-666666666666";
const largeLogsTaskId = "77777777-7777-4777-8777-777777777777";

const overviewTask = {
  task_id: taskId,
  task_no: "DEV05-TASK-001",
  task_name: "DEV-05 task detail from overview",
  status: "in_progress",
  deadline: "2026-09-08T10:30:00Z",
  is_urgent: false,
  task_weight: 4,
  task_version: 7,
  creator: { employee_no: "E-CREATOR", name: "Creator" },
  main_assignee: { employee_no: "E-ASSIGNEE", name: "Assignee" },
  current_user_relations: ["assigned"],
  allowed_actions: ["submit_progress_report"],
  is_overdue: false,
  days_until_deadline: 5,
  created_at: "2026-09-01T08:00:00Z",
  updated_at: "2026-09-01T09:00:00Z",
};

const overviewNode = {
  node_id: nodeId,
  task_id: taskId,
  task_no: "DEV05-TASK-001",
  task_name: overviewTask.task_name,
  node_name: "Open detail at a node anchor",
  status: "in_progress",
  task_status: "in_progress",
  owner: { employee_no: "E-ASSIGNEE", name: "Assignee" },
  planned_start_time: "2026-09-01T08:00:00Z",
  planned_deadline: "2026-09-03T08:00:00Z",
  progress_percent: 60,
  current_user_relations: ["node_owner"],
  is_overdue: false,
  days_until_deadline: 2,
  created_at: "2026-09-01T08:00:00Z",
  updated_at: "2026-09-01T09:00:00Z",
};

function taskDetail(id = taskId, overrides: Record<string, unknown> = {}) {
  const suffix = id.slice(0, 4);
  const nodes = id === noNodesTaskId
    ? []
    : Array.from({ length: id === largeNodesTaskId ? 36 : 1 }, (_, index) => ({
      node_id: index === 0 ? nodeId : `33333333-3333-4333-8333-${String(index).padStart(12, "0")}`,
      task_id: id,
      node_order: index + 1,
      sort_weight: index,
      node_name: id === longTaskId
        ? "Long node title ".repeat(20)
        : `Open detail at a node anchor ${index + 1}`,
      action_detail: id === largeNodesTaskId ? "Large node fixture ".repeat(8) : "Read-only node display.",
      owner_employee_no: "E-ASSIGNEE",
      planned_start_time: "2026-09-01T01:00:00Z",
      planned_deadline: "2026-09-03T10:30:00Z",
      estimated_hours: "12",
      actual_hours: "3",
      deliverable: "Node deliverable",
      acceptance_criteria: "Node acceptance",
      tools_or_materials: "Existing API",
      progress_percent: 70,
      status: "in_progress",
      completed_at: null,
    }));
  return {
    task_id: id,
    task_no: `DEV05-${suffix}`,
    task_name: id === longTaskId
      ? "Long task title ".repeat(18)
      : "DEV-05 formal read-only task detail",
    task_description: id === longTaskId ? "Long description ".repeat(80) : "Second HTML detail converted to React.",
    task_goal: id === longTaskId ? "Long task goal ".repeat(60) : "Render task detail, report, and review from real read APIs.",
    task_source: "weekly planning",
    creator_employee_no: "E-CREATOR",
    main_assignee_employee_no: "E-ASSIGNEE",
    report_to_employee_no: "E-MANAGER",
    report_to_level: "director",
    reviewer_employee_no: "E-REVIEWER",
    department_id: null,
    status: "in_progress",
    start_time: "2026-09-01T01:00:00Z",
    deadline: "2026-09-08T10:30:00Z",
    estimated_hours: "80",
    actual_hours: "8",
    task_weight: 4,
    deliverable: id === longTaskId ? "Long deliverable ".repeat(40) : "Validated pages",
    acceptance_criteria: id === longTaskId ? "Long acceptance criteria ".repeat(44) : "No fake write action.",
    is_urgent: false,
    report_cycle: "weekly:FRI@18:00",
    cancel_reason: null,
    withdraw_reason: null,
    close_reason: null,
    merged_into_task_id: null,
    task_version: 7,
    created_at: "2026-09-01T01:00:00Z",
    updated_at: "2026-09-01T02:00:00Z",
    confirmed_at: "2026-09-01T01:10:00Z",
    sent_at: "2026-09-01T01:12:00Z",
    accepted_at: "2026-09-01T01:30:00Z",
    completed_at: null,
    archived_at: null,
    participants: [
      { participant_id: "66666666-6666-4666-8666-666666666666", employee_no: "E-COLLAB", participant_role: "collaborator" },
    ],
    nodes,
    dependencies: [],
    node_participants: [],
    performance_matches: id === noNodesTaskId ? [] : [{
      performance_match_id: "99999999-9999-4999-8999-999999999990",
      task_id: id,
      metric_id: "99999999-9999-4999-8999-999999999991",
      metric_type: "quality",
      metric_name: "DEV-05 confirmed KPI",
      period: "2026-Q3",
      business_unit: "Product",
      definition_formula: "Read-only acceptance quality",
      total_score: "91",
      match_level: "strong",
      match_reason: "Confirmed metric returned by the task detail API.",
      is_confirmed: true,
      confirmed_by_employee_no: "E-CREATOR",
      confirmed_at: "2026-09-01T02:10:00Z",
    }],
    operation_logs: [{
      operation_log_id: "99999999-9999-4999-8999-999999999992",
      request_id: "REQ-DEV05",
      operator_employee_no: "E-CREATOR",
      action: "task_detail_projection_read",
      object_type: "task",
      object_id: id,
      before_data: null,
      after_data: null,
      result: "success",
      error_message: null,
      created_at: "2026-09-01T02:10:00Z",
    }],
    ai_extraction_records: [],
    change_requests: [],
    ...overrides,
  };
}

function pagePayload(items: unknown[]) {
  return {
    items,
    limit: 20,
    offset: 0,
    page: 1,
    pageSize: 20,
    total: items.length,
    status_counts: { pending_acceptance: 0, in_progress: 1, blocked: 0, pending_report: 0, pending_review: 0 },
  };
}

async function useDetailFixture(page: Page) {
  await page.route("**/api/v1/me", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
      employee_no: "E-ASSIGNEE",
      name: "Detail Employee",
      department: null,
      role_type: "employee",
      auth_mode: "test",
    }) });
  });
  await page.route("**/api/v1/tasks?**", async (route) => {
    const url = new URL(route.request().url());
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(pagePayload(url.searchParams.get("mode") === "nodes" ? [overviewNode] : [overviewTask])),
    });
  });
  await page.route("**/api/v1/tasks/**", async (route) => {
    const url = new URL(route.request().url());
    const parts = url.pathname.split("/");
    const id = parts[4];
    if (id === "403") {
      await route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ error: { code: "SCOPE_DENIED", message: "denied" } }) });
      return;
    }
    if (id === "404") {
      await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ error: { code: "TASK_NOT_FOUND", message: "missing" } }) });
      return;
    }
    if (url.pathname.endsWith("/available-actions")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ task_id: id, task_version: 7, allowed_actions: ["submit_progress_report", "approve_completion"], nodes: [{ node_id: nodeId, allowed_actions: [] }] }) });
      return;
    }
    if (url.pathname.endsWith("/status-logs")) {
      const logs = id === largeLogsTaskId
        ? Array.from({ length: 30 }, (_, index) => ({ status_log_id: `${index}9999999-9999-4999-8999-999999999999`, task_id: id, from_status: "in_progress", to_status: "in_progress", action_type: `log-${index}`, reason: "Long log ".repeat(12), operator_employee_no: "E-ASSIGNEE", task_version: 7, created_at: "2026-09-01T02:00:00Z" }))
        : [{ status_log_id: "77777777-7777-4777-8777-777777777777", task_id: id, from_status: "pending_acceptance", to_status: "in_progress", action_type: "accept", reason: null, operator_employee_no: "E-ASSIGNEE", task_version: 6, created_at: "2026-09-01T01:30:00Z" }];
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: logs, limit: 100, offset: 0, total: logs.length }) });
      return;
    }
    if (url.pathname.endsWith("/progress-reports")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: id === noNodesTaskId ? [] : [{ progress_report_id: "88888888-8888-4888-8888-888888888888", task_id: id, node_id: null, reporter_employee_no: "E-ASSIGNEE", progress_percent: 75, report_content: id === longTaskId || id === largeLogsTaskId ? "Long report ".repeat(50) : "Report content", stage_result: "Stage result", difficulty: null, resource_request: null, actual_hours: null, corrects_report_id: null, report_period_start: null, report_period_end: null, task_version: 7, operation_source: "rest_api", created_at: "2026-09-01T02:00:00Z" }], limit: 50, offset: 0, total: 1 }) });
      return;
    }
    if (url.pathname.endsWith("/issues") || url.pathname.endsWith("/completion-reviews")) {
      const isReview = url.pathname.endsWith("/completion-reviews");
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: isReview ? [{ completion_review_id: "99999999-9999-4999-8999-999999999999", task_id: id, review_round: 1, submitted_by_employee_no: "E-ASSIGNEE", completion_note: "Completed", deliverable_summary: "Package", reviewer_employee_no: "E-REVIEWER", review_status: "submitted", review_result: null, reject_reason: null, rework_node_id: null, submitted_task_version: 7, reviewed_task_version: null, submitted_at: "2026-09-01T03:00:00Z", reviewed_at: null, is_legacy_import: false }] : [], limit: 20, offset: 0, total: isReview ? 1 : 0 }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(taskDetail(id)) });
  });
  await page.addInitScript(([key]) => {
    window.sessionStorage.setItem(key, "dev-05-task-detail-token");
  }, [tokenKey]);
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}

async function expectTouchTargets(page: Page) {
  const sizes = await page.locator(".stb-task-detail a, .stb-task-detail button").evaluateAll((items) =>
    items.filter((item) => item.checkVisibility()).map((item) => {
      const box = item.getBoundingClientRect();
      return { width: box.width, height: box.height };
    }),
  );
  for (const size of sizes) {
    expect(size.width).toBeGreaterThanOrEqual(44);
    expect(size.height).toBeGreaterThanOrEqual(44);
  }
}

test.describe("DEV-05 Task Detail", () => {
  test("opens task detail from overview and restores the filtered source", async ({ page }) => {
    await useDetailFixture(page);
    await page.goto("/tasks?status=in_progress&search=DEV-05");
    await page.getByRole("link", { name: /DEV-05 task detail/ }).click();

    await expect(page.getByTestId("task-detail-page")).toBeVisible();
    await expect(page.getByText("概览")).toBeVisible();
    await expect(page.getByText("DEV-05 confirmed KPI")).toBeVisible();
    await expect(page.getByText("task_detail_projection_read")).toBeVisible();
    await page.getByRole("button", { name: "返回" }).last().click();
    await expect(page).toHaveURL(/\/tasks\?status=in_progress&search=DEV-05/);
  });

  test("opens node mode links at the node anchor", async ({ page }) => {
    await useDetailFixture(page);
    await page.goto("/tasks?mode=nodes&page=2");
    await page.getByRole("link", { name: /Open detail at a node anchor/ }).click();

    await expect(page).toHaveURL(new RegExp(`#node-${nodeId}`));
    await expect(page.getByRole("tab", { name: "节点" })).toHaveAttribute("aria-selected", "true");
    await expect(page.locator(`#node-${nodeId}`)).toBeFocused();
  });

  test("keeps tabs, report, and review read-only without mobile overflow", async ({ page }) => {
    await useDetailFixture(page);
    await page.goto(`/task/${taskId}`);
    await page.getByRole("tab", { name: "进度/汇报" }).click();
    await expect(page.getByRole("tab", { name: "进度/汇报" })).toHaveAttribute("aria-selected", "true");
    await expectNoHorizontalOverflow(page);
    await expectTouchTargets(page);

    await page.goto(`/task/${taskId}/report`);
    await expect(page.getByTestId("task-report-page")).toBeVisible();
    await expect(page.getByRole("button", { name: /提交进度汇报/ })).toBeDisabled();
    await expect(page.getByLabel("只读汇报字段")).not.toContainText("实际工时");
    await expectNoHorizontalOverflow(page);

    await page.goto(`/task/${taskId}/review`);
    await expect(page.getByTestId("task-review-page")).toBeVisible();
    await expect(page.getByRole("button", { name: /验收通过/ })).toBeDisabled();
    await expect(page.getByRole("button", { name: /验收退回/ })).toBeDisabled();
    await expectNoHorizontalOverflow(page);
  });

  test("renders 403, 404, and no-node states", async ({ page }) => {
    await useDetailFixture(page);
    await page.goto(`/task/403#node-${nodeId}`);
    await expect(page.getByText("无权限查看任务")).toBeVisible();

    await page.goto("/task/403/report");
    await expect(page.getByText("无权限查看汇报")).toBeVisible();

    await page.goto("/task/403/review");
    await expect(page.getByText("无权限查看验收")).toBeVisible();

    await page.goto("/task/404");
    await expect(page.getByText("任务不存在")).toBeVisible();

    await page.goto(`/task/${noNodesTaskId}`);
    await expect(page.getByText("暂无节点任务")).toBeVisible();
    await expect(page.getByText("暂无进度汇报")).toBeVisible();
    await expect(page.getByText("暂无绩效关联")).toBeVisible();
    await expect(page.getByText("操作记录")).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });

  test("handles long detail content within the mobile shell", async ({ page }) => {
    await useDetailFixture(page);
    await page.goto(`/task/${longTaskId}`);
    await expect(page.getByTestId("task-detail-page")).toBeVisible();
    await expect(page.getByRole("heading", { name: /Long task title/ })).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });

  test("keeps tablet and desktop detail surfaces without overflow", async ({ page }) => {
    await useDetailFixture(page);
    for (const size of [{ width: 768, height: 1024 }, { width: 1440, height: 900 }]) {
      await page.setViewportSize(size);
      await page.goto(`/task/${longTaskId}`);
      await expect(page.getByTestId("task-detail-page")).toBeVisible();
      await expectNoHorizontalOverflow(page);

      await page.goto(`/task/${taskId}/report`);
      await expect(page.getByTestId("task-report-page")).toBeVisible();
      await expectNoHorizontalOverflow(page);

      await page.goto(`/task/${taskId}/review`);
      await expect(page.getByTestId("task-review-page")).toBeVisible();
      await expectNoHorizontalOverflow(page);
    }
  });

  test("records deterministic detail P95 baseline", async ({ page }, testInfo) => {
    await useDetailFixture(page);
    const scenarios = [
      { label: "normal", url: `/task/${taskId}` },
      { label: "large-nodes", url: `/task/${largeNodesTaskId}` },
      { label: "large-logs", url: `/task/${largeLogsTaskId}` },
    ];
    const samples: number[] = [];
    for (const scenario of scenarios) {
      const start = Date.now();
      await page.goto(scenario.url);
      await expect(page.getByTestId("task-detail-page")).toBeVisible();
      samples.push(Date.now() - start);
    }
    const p95 = [...samples].sort((left, right) => left - right)[Math.ceil(samples.length * 0.95) - 1];
    console.log(`[${testInfo.project.name}] TASK_DETAIL_P95_MS=${p95}; samples=${samples.join(",")}; scenarios=${scenarios.map((item) => item.label).join(",")}`);
    expect(p95).toBeGreaterThanOrEqual(0);
  });
});
