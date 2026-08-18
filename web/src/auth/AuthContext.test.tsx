import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { session } from "../api/client";
import { currentUser, jsonResponse } from "../test/test-utils";
import { AuthProvider } from "./AuthContext";
import { useAuth } from "./useAuth";

function AuthProbe() {
  const { user, loading } = useAuth();
  return <div>{loading ? "恢复中" : user?.name || "未登录"}</div>;
}

describe("AuthProvider", () => {
  it("restores a session token through /me", async () => {
    session.setToken("restored-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(currentUser)));
    render(<AuthProvider><AuthProbe /></AuthProvider>);

    expect(screen.getByText("恢复中")).toBeInTheDocument();
    expect(await screen.findByText("测试创建人")).toBeInTheDocument();
  });

  it("clears an expired token after a 401", async () => {
    session.setToken("expired-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ error: { code: "authentication_required", message: "expired", details: {} } }, 401)));
    render(<AuthProvider><AuthProbe /></AuthProvider>);

    await waitFor(() => expect(screen.getByText("未登录")).toBeInTheDocument());
    expect(session.getToken()).toBeNull();
  });
});
