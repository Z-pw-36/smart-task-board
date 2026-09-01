/**
 * Feature: DEV-02 route shell responsive checks.
 * Responsibilities: verify target app shell, role navigation, error surfaces, and mobile overflow across approved widths.
 * Does not own: business page data, backend auth, or workflow API behavior.
 * Plan task: DEV-02.
 */

import { expect, type Page, test } from "@playwright/test";

const tokenKey = "smarttaskboard.prototype.token";

async function useAuthenticatedRouteFixture(page: Page, roleType: "employee" | "executive" = "employee") {
  await page.route("**/api/v1/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        employee_no: roleType === "executive" ? "DEV02_EXECUTIVE" : "DEV02_EMPLOYEE",
        name: roleType === "executive" ? "Route Executive" : "Route Employee",
        department: null,
        role_type: roleType,
        auth_mode: "test",
      }),
    });
  });
  await page.addInitScript(([key]) => {
    window.sessionStorage.setItem(key, "dev-02-route-token");
  }, [tokenKey]);
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}

test.describe("DEV-02 target route shell", () => {
  test("renders app shell without horizontal overflow and keeps touch targets", async ({ page }) => {
    await useAuthenticatedRouteFixture(page);
    await page.goto("/workbench");

    await expect(page.getByTestId("app-shell")).toBeVisible();
    await expect(page.locator("h1", { hasText: "工作台" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "底部导航" })).toBeVisible();
    await expectNoHorizontalOverflow(page);

    const navButtonSizes = await page.getByRole("navigation", { name: "底部导航" }).getByRole("button").evaluateAll((buttons) =>
      buttons.map((button) => {
        const box = button.getBoundingClientRect();
        return { width: box.width, height: box.height };
      }),
    );
    for (const size of navButtonSizes) {
      expect(size.width).toBeGreaterThanOrEqual(44);
      expect(size.height).toBeGreaterThanOrEqual(44);
    }
  });

  test("renders 403 and 404 surfaces without overflow", async ({ page }) => {
    await useAuthenticatedRouteFixture(page);

    await page.goto("/executive");
    await expect(page.getByRole("alert")).toContainText("无权限访问");
    await expect(page.getByRole("button", { name: /安全返回/ })).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await page.goto("/create/nodes");
    await expect(page.getByRole("heading", { name: "页面不存在" })).toBeVisible();
    await expect(page.getByText("创建人确认节点")).toHaveCount(0);
    await expectNoHorizontalOverflow(page);
  });

  test("shows executive navigation only for executive fixture", async ({ page }) => {
    await useAuthenticatedRouteFixture(page, "executive");
    await page.goto("/workbench");

    await expect(page.getByRole("navigation", { name: "底部导航" }).getByRole("button", { name: "团队" })).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });
});
