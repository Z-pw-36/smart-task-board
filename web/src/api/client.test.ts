import { describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest, authExpiredEvent, session } from "./client";
import { getTaskInputExtraction, retryTaskInputExtraction } from "./endpoints";
import { jsonResponse } from "../test/test-utils";

describe("apiRequest", () => {
  it("attaches the prototype Bearer token without logging it", async () => {
    session.setTokens("secret-prototype-token", "secret-refresh-token");
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await apiRequest("/api/v1/me");

    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer secret-prototype-token");
  });

  it("clears the session and emits auth expiry on 401", async () => {
    session.setTokens("expired-token", "expired-refresh-token");
    const expired = vi.fn();
    window.addEventListener(authExpiredEvent, expired);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ error: { code: "authentication_required", message: "expired", details: {} } }, 401)));

    await expect(apiRequest("/api/v1/me")).rejects.toBeInstanceOf(ApiError);

    expect(session.getToken()).toBeNull();
    expect(session.getRefreshToken()).toBeNull();
    expect(expired).toHaveBeenCalledOnce();
    window.removeEventListener(authExpiredEvent, expired);
  });

  it("uses the safe conflict message and hides non-JSON server output", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("database stack and password", { status: 409 })));

    await expect(apiRequest("/api/v1/tasks/1")).rejects.toMatchObject({
      message: "任务已被其他操作更新，请刷新后重试。",
    });
  });
});

describe("DEV-07 task intake endpoints", () => {
  it("uses extraction retry and polling endpoints", async () => {
    const responseBody = {
      input_id: "11111111-1111-4111-8111-111111111111",
      input_type: "text",
      raw_text: "Task",
      asr_text: null,
      source_channel: "web",
      submitted_by_employee_no: "E-CREATOR",
      submitted_at: "2026-09-02T04:00:00Z",
      extraction_id: "22222222-2222-4222-8222-222222222222",
      extracted_json: { task_name: "Task" },
      missing_fields: [],
      low_confidence_fields: [],
      confirm_questions: [],
      confidence_score: "0.95",
      job_status: "succeeded",
      retry_after_seconds: null,
    };
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse(responseBody)));
    vi.stubGlobal("fetch", fetchMock);

    await retryTaskInputExtraction("11111111-1111-4111-8111-111111111111");
    await getTaskInputExtraction("11111111-1111-4111-8111-111111111111");

    expect(fetchMock.mock.calls[0][0]).toContain("/task-inputs/11111111-1111-4111-8111-111111111111/extract");
    expect(fetchMock.mock.calls[0][1]?.method).toBe("POST");
    expect(fetchMock.mock.calls[1][0]).toContain("/task-inputs/11111111-1111-4111-8111-111111111111/extraction");
    expect(fetchMock.mock.calls[1][1]?.method).toBeUndefined();
  });
});
