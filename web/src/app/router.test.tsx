/**
 * Feature: V1.1 target router tests.
 * Responsibilities: verify route contracts, guard behavior, redirects, role-aware navigation, and return-source state.
 * Does not own: business page rendering, backend auth, or feature workflow APIs.
 * Plan task: DEV-02.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { CurrentUser } from "../api/types";
import { AuthContext, type AuthValue } from "../auth/auth-context";
import { AppRoutes } from "./router";

const employeeUser: CurrentUser = {
  employee_no: "DEV02_EMPLOYEE",
  name: "Route Employee",
  department: null,
  role_type: "employee",
  auth_mode: "test",
};

const executiveUser: CurrentUser = {
  ...employeeUser,
  employee_no: "DEV02_EXECUTIVE",
  name: "Route Executive",
  role_type: "executive",
};

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{`${location.pathname}${location.search}`}</output>;
}

function renderRoutes({
  route,
  user = employeeUser,
  state,
}: {
  route: string;
  user?: CurrentUser | null;
  state?: unknown;
}) {
  const auth: AuthValue = {
    user,
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
  };

  return render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={[{ pathname: route, state }]}>
        <AppRoutes />
        <LocationProbe />
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

const ordinaryTargetRoutes = [
  ["/workbench", "工作台"],
  ["/tasks", "任务概览"],
  ["/task/DEV02-TASK-001", "任务详情"],
  ["/task/DEV02-TASK-001/report", "提交进度汇报"],
  ["/task/DEV02-TASK-001/review", "任务验收"],
  ["/task/DEV02-TASK-001/decomposition", "AI 拆解状态"],
  ["/create/details", "创建任务"],
  ["/create/confirm", "确认发送"],
  ["/notifications", "通知中心"],
  ["/profile", "我的"],
] as const;

describe("DEV-02 target router", () => {
  it("allows the login route to render for anonymous users", () => {
    renderRoutes({ route: "/login", user: null });

    expect(screen.getByRole("heading", { name: "登录" })).toBeInTheDocument();
    expect(screen.queryByTestId("app-shell")).not.toBeInTheDocument();
  });

  it.each(ordinaryTargetRoutes)("recognizes %s and renders the protected shell", (route, title) => {
    renderRoutes({ route });

    expect(screen.getByTestId("app-shell")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: title }).length).toBeGreaterThan(0);
    expect(screen.getByTestId("route-contract")).toHaveTextContent("Business API");
    expect(screen.getByTestId("route-contract")).toHaveTextContent("No");
  });

  it.each([
    ["/executive", "团队任务态势"],
    ["/executive/employee-tasks", "员工负荷任务明细"],
  ] as const)("recognizes executive target route %s for an executive user", (route, title) => {
    renderRoutes({ route, user: executiveUser });

    expect(screen.getByTestId("app-shell")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: title }).length).toBeGreaterThan(0);
    expect(screen.getByTestId("route-contract")).toHaveTextContent("Business API");
    expect(screen.getByTestId("route-contract")).toHaveTextContent("No");
  });

  it("redirects anonymous users from protected routes to login with source state", async () => {
    renderRoutes({ route: "/tasks", user: null });

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/login"));
    expect(screen.getByText("登录后返回：/tasks")).toBeInTheDocument();
  });

  it("hides executive navigation for ordinary employees", () => {
    renderRoutes({ route: "/workbench" });

    const navigation = screen.getByRole("navigation", { name: "底部导航" });
    expect(within(navigation).queryByRole("button", { name: "团队" })).not.toBeInTheDocument();
  });

  it("shows executive navigation for executive users", () => {
    renderRoutes({ route: "/workbench", user: executiveUser });

    const navigation = screen.getByRole("navigation", { name: "底部导航" });
    expect(within(navigation).getByRole("button", { name: "团队" })).toBeInTheDocument();
  });

  it("renders 403 for non-executive access to executive routes", () => {
    renderRoutes({ route: "/executive" });

    expect(screen.getByRole("alert")).toHaveTextContent("无权限访问");
    expect(screen.getByRole("button", { name: /安全返回/ })).toBeInTheDocument();
  });

  it("redirects legacy root to workbench without a loop", async () => {
    renderRoutes({ route: "/" });

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/workbench"));
    expect(screen.getAllByRole("heading", { name: "工作台" }).length).toBeGreaterThan(0);
  });

  it("redirects legacy task detail URLs and preserves taskId", async () => {
    renderRoutes({ route: "/tasks/DEV02-TASK-789" });

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/task/DEV02-TASK-789"));
    expect(screen.getByText("DEV02-TASK-789")).toBeInTheDocument();
  });

  it("does not expose /create/nodes as a production route", () => {
    renderRoutes({ route: "/create/nodes" });

    expect(screen.getAllByText("页面不存在").length).toBeGreaterThan(0);
    expect(screen.queryByText("创建人确认节点")).not.toBeInTheDocument();
  });

  it("renders 404 for unknown authenticated routes", () => {
    renderRoutes({ route: "/unknown-route" });

    expect(screen.getAllByText("页面不存在").length).toBeGreaterThan(0);
  });

  it("uses explicit return source state before route fallback", async () => {
    renderRoutes({
      route: "/task/DEV02-TASK-002",
      state: { source: { pathname: "/notifications", search: "?type=task" } },
    });

    await userEvent.click(screen.getByRole("button", { name: "返回" }));
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/notifications?type=task"));
  });

  it("uses a route-specific safe fallback when no source exists", async () => {
    renderRoutes({ route: "/task/DEV02-TASK-003" });

    await userEvent.click(screen.getByRole("button", { name: "返回" }));
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/tasks"));
  });

  it("keeps the bottom navigation active for task child routes", () => {
    renderRoutes({ route: "/task/DEV02-TASK-004/report" });

    const navigation = screen.getByRole("navigation", { name: "底部导航" });
    expect(within(navigation).getByRole("button", { name: "任务" })).toHaveAttribute("aria-current", "page");
  });

  it("falls back safely for unsafe return source state", async () => {
    renderRoutes({
      route: "/executive",
      state: { source: { pathname: "https://example.invalid/phishing" } },
    });

    await userEvent.click(screen.getByRole("button", { name: /安全返回/ }));
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/workbench"));
  });
});
