/**
 * Feature: DEV-07 task intake browser coverage.
 * Responsibilities: verify deterministic text/voice intake, extraction, clarification, retry, auth, and responsive behavior.
 * Does not own: task creation, task sending, node decomposition, or real AI provider calls.
 * Plan task: DEV-07.
 */

import { expect, type Page, test } from "@playwright/test";

const tokenKey = "smarttaskboard.prototype.token";

const extracted = {
  input_id: "11111111-1111-4111-8111-111111111111",
  input_type: "text",
  raw_text: "请完成门店上线方案",
  asr_text: null,
  source_channel: "web",
  submitted_by_employee_no: "DEV07_CREATOR",
  submitted_at: "2026-09-02T04:00:00Z",
  extraction_id: "22222222-2222-4222-8222-222222222222",
  extracted_json: {
    task_name: "门店上线方案",
    task_description: "完成门店上线方案并提交验收材料",
    task_goal: "门店上线准备完成",
    main_assignee_employee_no: "DEV07_ASSIGNEE",
    report_to_employee_no: "DEV07_CREATOR",
    reviewer_employee_no: "DEV07_CREATOR",
    deadline: "2026-09-08T10:00:00+08:00",
    task_weight: 3,
    acceptance_criteria: "上线材料齐全",
  },
  missing_fields: [],
  low_confidence_fields: [],
  confirm_questions: [],
  confidence_score: "0.95",
  job_status: "succeeded",
  retry_after_seconds: null,
};

const missing = {
  ...extracted,
  extraction_id: "33333333-3333-4333-8333-333333333333",
  extracted_json: {
    task_name: "门店上线方案",
    task_description: "完成门店上线方案",
    task_weight: 3,
  },
  missing_fields: ["main_assignee_employee_no", "deadline"],
  low_confidence_fields: ["deadline"],
  confirm_questions: ["请确认主承办人。", "请确认截止时间。"],
  confidence_score: "0.6",
};

async function useAuth(page: Page) {
  await page.addInitScript(([key]) => {
    window.sessionStorage.setItem(key, "dev-07-token");
    window.sessionStorage.removeItem("smarttaskboard.dev07.intake-draft");
  }, [tokenKey]);
  await page.route("**/api/v1/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        employee_no: "DEV07_CREATOR",
        name: "DEV-07 Creator",
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
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}

async function expectTouchTargets(page: Page) {
  const sizes = await page.locator(".stb-task-intake button").evaluateAll((items) =>
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

test.describe("DEV-07 Task Intake", () => {
  test("redirects anonymous users to login", async ({ page }) => {
    await page.goto("/create/details");

    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole("heading", { name: "登录" })).toBeVisible();
  });

  test("extracts text input without creating or sending a task", async ({ page }) => {
    await useAuth(page);
    const businessWrites: string[] = [];
    await page.route("**/api/v1/task-inputs**", async (route) => {
      const request = route.request();
      if (request.url().includes("/extraction")) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(extracted) });
        return;
      }
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(extracted) });
    });
    await page.route("**/api/v1/tasks**", async (route) => {
      businessWrites.push(route.request().url());
      await route.fulfill({ status: 500, contentType: "application/json", body: "{}" });
    });

    await page.goto("/create/details");
    await page.getByLabel("任务原文").fill("请完成门店上线方案");
    await page.getByRole("button", { name: "识别字段" }).click();

    await expect(page.getByText("字段识别已完成。")).toBeVisible();
    await expect(page.getByText("上线材料齐全")).toBeVisible();
    expect(businessWrites).toEqual([]);
    await expectNoHorizontalOverflow(page);
    await expectTouchTargets(page);
  });

  test("handles clarification and deterministic retry", async ({ page }) => {
    await useAuth(page);
    let current = missing;
    await page.route("**/api/v1/task-inputs**", async (route) => {
      const request = route.request();
      if (request.url().includes("/clarifications")) {
        current = extracted;
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(current) });
        return;
      }
      if (request.url().includes("/extraction")) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(current) });
        return;
      }
      if (request.url().endsWith("/extract")) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(extracted) });
        return;
      }
      await route.fulfill({
        status: request.method() === "POST" ? 201 : 200,
        contentType: "application/json",
        body: JSON.stringify(current),
      });
    });

    await page.goto("/create/details");
    await page.getByLabel("任务原文").fill("门店上线方案缺少人员和日期");
    await page.getByRole("button", { name: "识别字段" }).click();

    await expect(page.getByText("需要补充关键信息。")).toBeVisible();
    await expect(page.locator(".stb-task-intake-review")).toContainText(/主承办人.*截止时间/);
    await page.getByLabel("补充说明").fill("主承办人 DEV07_ASSIGNEE，截止 2026-09-08 10:00");
    await page.getByRole("button", { name: "提交补充" }).click();

    await expect(page.getByText("补充信息已合并。")).toBeVisible();
    await page.getByRole("button", { name: "重试识别" }).click();
    await expect(page.getByText("已重新识别字段。")).toBeVisible();
  });

  test("preserves text after provider failure and retries successfully", async ({ page }) => {
    await useAuth(page);
    let attempts = 0;
    await page.route("**/api/v1/task-inputs**", async (route) => {
      attempts += 1;
      if (attempts === 1) {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ error: { code: "internal_server_error", message: "Internal server error", details: {} } }),
        });
        return;
      }
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(extracted) });
    });

    await page.goto("/create/details");
    await page.getByLabel("任务原文").fill("网络失败后保留的输入");
    await page.getByRole("button", { name: "识别字段" }).click();

    await expect(page.getByRole("alert")).toContainText("服务暂时不可用，请稍后重试。");
    await expect(page.getByLabel("任务原文")).toHaveValue("网络失败后保留的输入");
    await page.getByRole("button", { name: "重试", exact: true }).click();
    await expect(page.getByText("已重新识别字段。")).toBeVisible();
  });

  test("falls back to text when voice input is unsupported", async ({ page }) => {
    await useAuth(page);
    await page.addInitScript(() => {
      delete window.SpeechRecognition;
      delete window.webkitSpeechRecognition;
    });

    await page.goto("/create/details");
    await page.getByRole("button", { name: "语音输入" }).click();

    await expect(page.getByRole("alert")).toContainText("当前浏览器不支持语音输入");
    await expect(page.getByLabel("任务原文")).toBeFocused();
  });

  test("keeps tablet and desktop intake surfaces stable", async ({ page }) => {
    await useAuth(page);
    await page.route("**/api/v1/task-inputs**", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(extracted) });
    });

    for (const viewport of [{ width: 768, height: 1024 }, { width: 1440, height: 900 }]) {
      await page.setViewportSize(viewport);
      await page.goto("/create/details");
      await expect(page.getByTestId("task-intake-page")).toBeVisible();
      await expectNoHorizontalOverflow(page);
      await expectTouchTargets(page);
    }
  });
});
