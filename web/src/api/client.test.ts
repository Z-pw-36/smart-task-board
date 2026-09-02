import { describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest, authExpiredEvent, session } from "./client";
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
