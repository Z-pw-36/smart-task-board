import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { session } from "../api/client";
import { AuthContext, type AuthValue } from "../auth/auth-context";
import { jsonResponse } from "../test/test-utils";
import { LoginPage } from "./LoginPage";

function renderLogin(login: AuthValue["login"]) {
  const auth: AuthValue = { user: null, loading: false, login, logout: vi.fn() };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><AuthContext.Provider value={auth}><MemoryRouter><LoginPage /></MemoryRouter></AuthContext.Provider></QueryClientProvider>);
}

const users = [{ employee_no: "E-CREATOR", name: "测试创建人", department_id: null, department_name: "测试部门", role_type: "employee" }];

describe("LoginPage", () => {
  it("loads prototype users and signs in with the selected identity", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(users)));
    const login = vi.fn().mockResolvedValue(undefined);
    renderLogin(login);
    const user = userEvent.setup();

    await user.selectOptions(await screen.findByLabelText("演示用户"), "E-CREATOR");
    await user.click(screen.getByRole("button", { name: "进入任务看板" }));

    expect(login).toHaveBeenCalledWith("E-CREATOR");
    expect(screen.getByText(/仅用于隔离开发和演示/)).toBeInTheDocument();
  });

  it("normalizes unknown login errors without exposing their contents", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(users)));
    const login = vi.fn().mockRejectedValue({ token: "secret-token", database: "internal" });
    renderLogin(login);
    const user = userEvent.setup();

    await user.selectOptions(await screen.findByLabelText("演示用户"), "E-CREATOR");
    await user.click(screen.getByRole("button", { name: "进入任务看板" }));

    expect(await screen.findByText("登录失败，请稍后重试。")).toBeInTheDocument();
    expect(screen.queryByText(/secret-token|internal/)).not.toBeInTheDocument();
    expect(session.getToken()).toBeNull();
  });
});
