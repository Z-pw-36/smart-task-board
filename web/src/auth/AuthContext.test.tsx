import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { session } from "../api/client";
import { currentUser, jsonResponse } from "../test/test-utils";
import { AuthProvider } from "./AuthContext";
import { useAuth } from "./useAuth";

function AuthProbe() {
  const { user, loading } = useAuth();
  return <div>{loading ? "恢复中" : user?.name || "未登录"}</div>;
}

function LoginProbe() {
  const { user, login } = useAuth();
  return (
    <button type="button" onClick={() => void login("E-CREATOR")}>
      {user?.name || "登录"}
    </button>
  );
}

describe("AuthProvider", () => {
  it("restores a session token through /me", async () => {
    session.setToken("restored-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(currentUser)));
    render(<AuthProvider><AuthProbe /></AuthProvider>);

    expect(screen.getByText("恢复中")).toBeInTheDocument();
    expect(await screen.findByText("测试创建人")).toBeInTheDocument();
  });

  it("rotates a stored refresh token before restoring /me", async () => {
    session.setTokens("", "refresh-token");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({
        access_token: "a2",
        token_type: "bearer",
        expires_in: 1800,
        refresh_token: "r2",
      }))
      .mockResolvedValueOnce(jsonResponse(currentUser));
    vi.stubGlobal("fetch", fetchMock);
    render(<AuthProvider><AuthProbe /></AuthProvider>);

    expect(await screen.findByText("测试创建人")).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][0]).toContain("/api/v1/auth/refresh");
    expect(session.getToken()).toBe("a2");
    expect(session.getRefreshToken()).toBe("r2");
  });

  it("signs in through the backend login endpoint and stores refresh token", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({
        access_token: "a1",
        token_type: "bearer",
        expires_in: 1800,
        refresh_token: "r1",
      }))
      .mockResolvedValueOnce(jsonResponse(currentUser));
    vi.stubGlobal("fetch", fetchMock);
    render(<AuthProvider><LoginProbe /></AuthProvider>);

    await userEvent.click(screen.getByRole("button", { name: "登录" }));

    expect(await screen.findByRole("button", { name: "测试创建人" })).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][0]).toContain("/api/v1/auth/login");
    expect(session.getToken()).toBe("a1");
    expect(session.getRefreshToken()).toBe("r1");
  });

  it("clears an expired token after a 401", async () => {
    session.setToken("expired-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ error: { code: "authentication_required", message: "expired", details: {} } }, 401)));
    render(<AuthProvider><AuthProbe /></AuthProvider>);

    await waitFor(() => expect(screen.getByText("未登录")).toBeInTheDocument());
    expect(session.getToken()).toBeNull();
    expect(session.getRefreshToken()).toBeNull();
  });
});
