import { expect, test } from "@playwright/test";

test.describe("DEV-00 baseline", () => {
  test("loads the current application shell", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("body")).toBeVisible();
  });
});
