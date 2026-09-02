/**
 * Feature: DEV-03 Workbench browser coverage.
 * Responsibilities: verify Workbench responsive rendering, navigation targets, and a deterministic P95 baseline.
 * Does not own: backend data creation, downstream route business pages, or AI provider behavior.
 * Plan task: DEV-03.
 */

import { expect, type Page, test } from "@playwright/test";

const tokenKey = "smarttaskboard.prototype.token";

const task = {
  task_id: "33333333-3333-4333-8333-333333333333",
  task_no: "DEV03-TASK-001",
  task_name: "Workbench responsive route contract with a deliberately long task title",
  status: "in_progress",
  deadline: "2026-09-08T10:30:00Z",
  is_urgent: true,
  task_weight: 4,
  task_version: 2,
  creator: { employee_no: "DEV03_CREATOR", name: "Workbench Creator" },
  main_assignee: { employee_no: "DEV03_ASSIGNEE", name: "Workbench Assignee" },
  current_user_relations: ["assigned"],
  allowed_actions: [],
  is_overdue: false,
  days_until_deadline: 5,
  created_at: "2026-09-01T08:00:00Z",
  updated_at: "2026-09-01T09:00:00Z",
};

async function useWorkbenchFixture(page: Page, roleType: "employee" | "executive" = "employee") {
  const canAccessExecutive = roleType === "executive";
  await page.route("**/api/v1/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        employee_no: roleType === "executive" ? "DEV03_EXECUTIVE" : "DEV03_EMPLOYEE",
        name: roleType === "executive" ? "Workbench Executive" : "Workbench Employee",
        department: null,
        role_type: roleType,
        roles: [roleType],
        permissions: {
          can_access_executive: canAccessExecutive,
          can_manage_permissions: false,
          can_view_all_demo_data: false,
          allowed_routes: canAccessExecutive
            ? ["/workbench", "/tasks", "/create/details", "/create/confirm", "/notifications", "/profile", "/executive", "/executive/employee-tasks"]
            : ["/workbench", "/tasks", "/create/details", "/create/confirm", "/notifications", "/profile"],
          capabilities: canAccessExecutive ? ["task:read:related", "executive:read"] : ["task:read:related"],
        },
        scopes: [],
        auth_mode: "test",
      }),
    });
  });
  await page.route("**/api/v1/dashboard/summary", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        created_task_count: 1,
        assigned_task_count: 1,
        inbox_count: 2,
        in_progress_count: 1,
        pending_acceptance_count: 1,
        today_task_count: 0,
        due_within_7_days_count: 1,
        overdue_count: 0,
        report_due_count: 0,
        open_issue_count: 1,
        blocked_task_count: 1,
        completion_review_count: 1,
        unread_notification_count: 2,
        open_conflict_count: 0,
        due_window_days: 7,
        recent_tasks: [task],
        latest_workload: { workload_score: 42, workload_level: "normal" },
        priority_items: [{ task_id: task.task_id, priority_quadrant: "important_urgent", sort_rank: 1 }],
      }),
    });
  });
  await page.route("**/api/v1/tasks?**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [task], limit: 8, offset: 0, total: 1 }),
    });
  });
  await page.addInitScript(([key]) => {
    window.sessionStorage.setItem(key, "dev-03-workbench-token");
  }, [tokenKey]);
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}

async function expectTouchTargets(page: Page) {
  const sizes = await page.locator(".stb-workbench a, .stb-workbench button").evaluateAll((items) =>
    items
      .filter((item) => item.checkVisibility())
      .map((item) => {
        const box = item.getBoundingClientRect();
        return { width: box.width, height: box.height };
      }),
  );
  for (const size of sizes) {
    expect(size.width).toBeGreaterThanOrEqual(44);
    expect(size.height).toBeGreaterThanOrEqual(44);
  }
}

test.describe("DEV-03 Workbench", () => {
  test("renders the Workbench without overflow and uses formal route targets", async ({ page }) => {
    await useWorkbenchFixture(page);
    await page.goto("/workbench");

    await expect(page.getByTestId("workbench-page")).toBeVisible();
    await expect(page.getByText("任务指标")).toBeVisible();
    await expect(page.getByText("任务风险四象限")).toBeVisible();
    await expect(page.getByRole("heading", { name: "需要支持" })).toBeVisible();
    await expect(page.getByText("AI 任务助手")).toBeVisible();
    await expect(page.getByRole("link", { name: "描述任务", exact: true })).toHaveAttribute(
      "href",
      "/create/details",
    );
    await expect(page.getByRole("link", { name: "语音暂不可用，改用文字描述任务" })).toHaveAttribute("href", "/create/details");
    await expect(page.getByRole("link", { name: "全部任务" })).toHaveAttribute("href", "/tasks");
    await expect(page.getByRole("link", { name: /通知，2 条未读/ })).toHaveAttribute("href", "/notifications");
    await expect(page.getByRole("link", { name: /Workbench responsive route contract/ })).toHaveAttribute("href", `/task/${task.task_id}`);
    await expect(page.getByRole("link", { name: /进行中 1，按状态查看任务概览/ })).toHaveAttribute("href", "/tasks?status=in_progress");
    await expect(page.getByRole("link", { name: /重要且紧急 1，按象限查看任务概览/ })).toHaveAttribute("href", "/tasks?quadrant=important_urgent");
    await expect(page.getByRole("link", { name: /需要支持 1，查看任务概览/ })).toHaveAttribute("href", "/tasks?support=open");
    await expect(page.getByRole("link", { name: "团队态势" })).toHaveCount(0);
    await expectNoHorizontalOverflow(page);
    await expectTouchTargets(page);
  });

  test("records a deterministic Workbench P95 baseline", async ({ page }, testInfo) => {
    await useWorkbenchFixture(page, "executive");
    const samples: number[] = [];

    for (let index = 0; index < 5; index += 1) {
      const start = Date.now();
      await page.goto(`/workbench?sample=${index}`);
      await expect(page.getByTestId("workbench-page")).toBeVisible();
      samples.push(Date.now() - start);
    }

    const sorted = [...samples].sort((left, right) => left - right);
    const p95 = sorted[Math.ceil(sorted.length * 0.95) - 1];
    console.log(`[${testInfo.project.name}] WORKBENCH_P95_MS=${p95}; samples=${samples.join(",")}`);
    await expect(page.getByRole("link", { name: "团队态势" })).toHaveAttribute("href", "/executive");
    expect(p95).toBeLessThan(2_000);
  });
});
