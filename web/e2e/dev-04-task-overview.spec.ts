/**
 * Feature: DEV-04 Task Overview browser coverage.
 * Responsibilities: verify responsive task/node modes, URL filters, navigation, and filter P95 baseline.
 * Does not own: task detail implementation, backend data creation, or workflow mutations.
 * Plan task: DEV-04.
 */

import { expect, type Page, test } from "@playwright/test";

const tokenKey = "smarttaskboard.prototype.token";
const taskId = "22222222-2222-4222-8222-222222222222";
const nodeId = "33333333-3333-4333-8333-333333333333";

const taskItem = {
  task_id: taskId,
  task_no: "DEV04-TASK-001",
  task_name: "Task overview route contract with a deliberately long task title",
  status: "in_progress",
  deadline: "2026-09-08T10:30:00Z",
  is_urgent: false,
  task_weight: 3,
  task_version: 1,
  creator: { employee_no: "DEV04_CREATOR", name: "Route Creator" },
  main_assignee: { employee_no: "DEV04_EMPLOYEE", name: "Route Employee" },
  current_user_relations: ["assigned"],
  allowed_actions: [],
  is_overdue: false,
  days_until_deadline: 5,
  created_at: "2026-09-01T08:00:00Z",
  updated_at: "2026-09-01T09:00:00Z",
};

const nodeItem = {
  node_id: nodeId,
  task_id: taskId,
  task_no: "DEV04-TASK-001",
  task_name: taskItem.task_name,
  node_name: "Review the mobile task overview filters",
  status: "in_progress",
  task_status: "in_progress",
  owner: { employee_no: "DEV04_EMPLOYEE", name: "Route Employee" },
  planned_start_time: "2026-09-01T08:00:00Z",
  planned_deadline: "2026-09-03T08:00:00Z",
  progress_percent: 60,
  current_user_relations: ["node_owner"],
  is_overdue: false,
  days_until_deadline: 2,
  created_at: "2026-09-01T08:00:00Z",
  updated_at: "2026-09-01T09:00:00Z",
};

function pagePayload(items: unknown[], overrides: Record<string, unknown> = {}) {
  return {
    items,
    limit: 20,
    offset: 0,
    page: 1,
    pageSize: 20,
    total: items.length,
    status_counts: {
      pending_acceptance: 1,
      in_progress: 1,
      blocked: 0,
      pending_report: 0,
      pending_review: 0,
    },
    ...overrides,
  };
}

async function useOverviewFixture(page: Page) {
  await page.route("**/api/v1/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        employee_no: "DEV04_EMPLOYEE",
        name: "Task Overview Employee",
        department: null,
        role_type: "employee",
        roles: ["employee"],
        permissions: {
          can_access_executive: false,
          can_manage_permissions: false,
          can_view_all_demo_data: false,
          allowed_routes: ["/workbench", "/tasks", "/create/details", "/create/confirm", "/notifications", "/profile"],
          capabilities: ["task:read:related"],
        },
        scopes: [],
        auth_mode: "test",
      }),
    });
  });
  await page.route("**/api/v1/tasks?**", async (route) => {
    const url = new URL(route.request().url());
    const mode = url.searchParams.get("mode");
    const status = url.searchParams.get("status");
    if (mode === "nodes") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(pagePayload([nodeItem])) });
      return;
    }
    if (status === "pending_review") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(pagePayload([], { total: 0 })) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(pagePayload([taskItem], { total: 42 })) });
  });
  await page.addInitScript(([key]) => {
    window.sessionStorage.setItem(key, "dev-04-task-overview-token");
  }, [tokenKey]);
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}

async function expectTouchTargets(page: Page) {
  const sizes = await page.locator(".stb-task-overview a, .stb-task-overview button").evaluateAll((items) =>
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

test.describe("DEV-04 Task Overview", () => {
  test("renders task mode filters without mobile overflow", async ({ page }) => {
    await useOverviewFixture(page);
    await page.goto("/tasks?status=in_progress");

    await expect(page.getByTestId("task-overview-page")).toBeVisible();
    await expect(page.getByRole("tab", { name: "任务" })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("link", { name: /Task overview route contract/ })).toHaveAttribute("href", `/task/${taskId}`);
    await expectNoHorizontalOverflow(page);
    await expectTouchTargets(page);
  });

  test("applies filter sheet and opens node cards with anchors", async ({ page }) => {
    await useOverviewFixture(page);
    await page.goto("/tasks");

    await page.getByRole("button", { name: "更多筛选" }).click();
    await page.getByLabel("任务类型").selectOption("nodes");
    await page.getByLabel("任务状态").selectOption("in_progress");
    await page.getByLabel("优先级四象限").selectOption("important_urgent");
    await page.getByLabel("仅看未来3天临期").check();
    await page.getByLabel("需要支持").check();
    await page.getByLabel("开始时间").selectOption("custom");
    await page.getByLabel("开始日期").fill("2026-09-01");
    await page.getByLabel("结束日期").fill("2026-09-03");
    await page.getByRole("button", { name: "应用筛选" }).click();

    await expect(page).toHaveURL(/mode=nodes/);
    await expect(page).toHaveURL(/quadrant=important_urgent/);
    await expect(page.getByRole("link", { name: /Review the mobile task overview filters/ })).toHaveAttribute(
      "href",
      `/task/${taskId}#node-${nodeId}`,
    );
    await page.getByRole("link", { name: /Review the mobile task overview filters/ }).click();
    await expect(page).toHaveURL(new RegExp(`/task/${taskId}#node-${nodeId}`));
  });

  test("restores URL filters after refresh and shows empty reset path", async ({ page }) => {
    await useOverviewFixture(page);
    await page.goto("/tasks?status=pending_review&page=2");

    await expect(page.getByText("当前筛选条件下暂无任务")).toBeVisible();
    await page.reload();
    await expect(page).toHaveURL(/status=pending_review/);
    await expect(page.getByLabel("当前筛选").getByText("待验收")).toBeVisible();
    await page.getByRole("button", { name: "重置筛选" }).last().click();
    await expect(page).not.toHaveURL(/status=pending_review/);
  });

  test("keeps tablet and desktop layouts free of horizontal overflow", async ({ page }) => {
    await useOverviewFixture(page);
    for (const size of [{ width: 768, height: 1024 }, { width: 1440, height: 900 }]) {
      await page.setViewportSize(size);
      await page.goto("/tasks?mode=nodes&nearDue=true");
      await expect(page.getByText("Review the mobile task overview filters")).toBeVisible();
      await expectNoHorizontalOverflow(page);
    }
  });

  test("records deterministic filter P95 baseline", async ({ page }, testInfo) => {
    await useOverviewFixture(page);
    const urls = [
      "/tasks?status=in_progress",
      "/tasks?mode=nodes",
      "/tasks?mode=nodes&quadrant=important_urgent&nearDue=true",
      "/tasks?page=2&pageSize=20",
      "/tasks?datePreset=custom&startDate=2026-09-01&endDate=2026-09-03",
    ];
    const samples: number[] = [];

    for (const url of urls) {
      const start = Date.now();
      await page.goto(url);
      await expect(page.getByTestId("task-overview-page")).toBeVisible();
      samples.push(Date.now() - start);
    }

    const sorted = [...samples].sort((left, right) => left - right);
    const p95 = sorted[Math.ceil(sorted.length * 0.95) - 1];
    console.log(`[${testInfo.project.name}] TASK_OVERVIEW_FILTER_P95_MS=${p95}; samples=${samples.join(",")}`);
    expect(p95).toBeLessThan(2_500);
  });
});
