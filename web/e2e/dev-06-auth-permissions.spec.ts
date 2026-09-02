/**
 * Feature: DEV-06 auth and permission projection browser coverage.
 * Responsibilities: verify login redirects, backend current-user projection, executive route gates, and responsive safety.
 * Does not own: executive dashboard implementation, task workflow writes, or production SSO provider integration.
 * Plan task: DEV-06.
 */

import { expect, type Page, test } from "@playwright/test";

const tokenKey = "smarttaskboard.prototype.token";

const baseRoutes = [
  "/workbench",
  "/tasks",
  "/create/details",
  "/create/confirm",
  "/notifications",
  "/profile",
];

function userPayload(canAccessExecutive: boolean) {
  return {
    employee_no: canAccessExecutive ? "DEV06_EXECUTIVE" : "DEV06_EMPLOYEE",
    name: canAccessExecutive ? "Auth Executive" : "Auth Employee",
    department: null,
    role_type: canAccessExecutive ? "executive" : "employee",
    roles: [canAccessExecutive ? "executive" : "employee"],
    permissions: {
      can_access_executive: canAccessExecutive,
      can_manage_permissions: false,
      can_view_all_demo_data: false,
      allowed_routes: canAccessExecutive
        ? [...baseRoutes, "/executive", "/executive/employee-tasks"]
        : baseRoutes,
      capabilities: canAccessExecutive ? ["task:read:related", "executive:read"] : ["task:read:related"],
    },
    scopes: canAccessExecutive
      ? [
          {
            authorized_scope_id: "11111111-1111-4111-8111-111111111111",
            scope_type: "department",
            scope_id: "22222222-2222-4222-8222-222222222222",
            permission_type: "view",
          },
        ]
      : [],
    auth_mode: "test",
  };
}

async function mockSession(page: Page, canAccessExecutive: boolean) {
  await page.route("**/api/v1/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(userPayload(canAccessExecutive)),
    });
  });
  await page.route("**/api/v1/dashboard/summary", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        created_task_count: 1,
        assigned_task_count: 0,
        inbox_count: 0,
        in_progress_count: 0,
        pending_acceptance_count: 0,
        today_task_count: 0,
        due_within_7_days_count: 0,
        overdue_count: 0,
        report_due_count: 0,
        open_issue_count: 0,
        blocked_task_count: 0,
        completion_review_count: 0,
        unread_notification_count: 0,
        open_conflict_count: 0,
        due_window_days: 7,
        recent_tasks: [],
        latest_workload: null,
        priority_items: [],
      }),
    });
  });
  await page.route("**/api/v1/tasks?**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [], limit: 8, offset: 0, total: 0 }),
    });
  });
  await page.addInitScript(([key]) => {
    window.sessionStorage.setItem(key, "dev-06-auth-token");
  }, [tokenKey]);
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}

async function expectVisibleTouchTargets(page: Page) {
  const sizes = await page.locator("a, button").evaluateAll((items) =>
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

test.describe("DEV-06 auth projection", () => {
  test("redirects anonymous protected routes to login without a loop", async ({ page }) => {
    await page.goto("/tasks");

    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByText("登录后返回：/tasks")).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });

  test("keeps ordinary employees out of executive routes", async ({ page }) => {
    await mockSession(page, false);
    await page.goto("/executive");

    await expect(page.getByRole("alert")).toContainText("无权限访问");
    await expect(page.getByRole("button", { name: /安全返回/ })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "底部导航" }).getByRole("button", { name: "团队" })).toHaveCount(0);
    await expectNoHorizontalOverflow(page);
  });

  test("shows executive navigation from backend permission projection", async ({ page }) => {
    await mockSession(page, true);
    await page.goto("/workbench");

    await expect(page.getByTestId("workbench-page")).toBeVisible();
    await expect(page.getByRole("navigation", { name: "底部导航" }).getByRole("button", { name: "团队" })).toBeVisible();
    await expect(page.getByRole("link", { name: "团队态势" })).toHaveAttribute("href", "/executive");
    await expectNoHorizontalOverflow(page);
  });

  test("keeps tablet and desktop auth surfaces stable", async ({ page }) => {
    await mockSession(page, true);
    for (const viewport of [
      { width: 768, height: 1024 },
      { width: 1440, height: 900 },
    ]) {
      await page.setViewportSize(viewport);
      await page.goto("/workbench");

      await expect(page.getByTestId("workbench-page")).toBeVisible();
      await expect(page.getByRole("navigation", { name: "底部导航" }).getByRole("button", { name: "团队" })).toBeVisible();
      await expectNoHorizontalOverflow(page);
      await expectVisibleTouchTargets(page);
    }
  });
});
