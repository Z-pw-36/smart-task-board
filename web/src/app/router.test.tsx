/**
 * Feature: V1.1 target router tests.
 * Responsibilities: verify route contracts, guard behavior, redirects, role-aware navigation, and return-source state.
 * Does not own: business page rendering, backend auth, or feature workflow APIs.
 * Plan task: DEV-02.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CurrentUser } from "../api/types";
import { AuthContext, type AuthValue } from "../auth/auth-context";
import { jsonResponse, taskSummary } from "../test/test-utils";
import { AppRoutes } from "./router";

const employeePermissions = {
  can_access_executive: false,
  can_manage_permissions: false,
  can_view_all_demo_data: false,
  allowed_routes: ["/workbench", "/tasks", "/create/details", "/create/confirm", "/notifications", "/profile"],
  capabilities: ["task:read:related"],
};

const employeeUser: CurrentUser = {
  employee_no: "DEV02_EMPLOYEE",
  name: "Route Employee",
  department: null,
  role_type: "employee",
  roles: ["employee"],
  permissions: employeePermissions,
  scopes: [],
  auth_mode: "test",
};

const executiveUser: CurrentUser = {
  ...employeeUser,
  employee_no: "DEV02_EXECUTIVE",
  name: "Route Executive",
  role_type: "employee",
  roles: ["employee"],
  permissions: {
    ...employeePermissions,
    can_access_executive: true,
    allowed_routes: [...employeePermissions.allowed_routes, "/executive", "/executive/employee-tasks"],
    capabilities: ["task:read:related", "executive:read"],
  },
};

const roleOnlyExecutiveUser: CurrentUser = {
  ...employeeUser,
  employee_no: "DEV02_ROLE_ONLY",
  name: "Role Only Executive",
  role_type: "executive",
  roles: ["executive"],
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
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const auth: AuthValue = {
    user,
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
  };

  return render(
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={auth}>
        <MemoryRouter initialEntries={[{ pathname: route, state }]}>
          <AppRoutes />
          <LocationProbe />
        </MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

const formalTaskRoutes = [
  ["/task/22222222-2222-4222-8222-222222222222", "task-detail-page"],
  ["/task/22222222-2222-4222-8222-222222222222/report", "task-report-page"],
  ["/task/22222222-2222-4222-8222-222222222222/review", "task-review-page"],
] as const;

const placeholderTargetRoutes = [
  ["/task/DEV02-TASK-001/decomposition", "AI 拆解状态"],
  ["/create/details", "创建任务"],
  ["/create/confirm", "确认发送"],
  ["/notifications", "通知中心"],
  ["/profile", "我的"],
] as const;

function mockWorkbenchFetch() {
  vi.stubGlobal("fetch", vi.fn(async (url: string | URL | Request) => {
    const value = String(url);
    if (value.includes("/dashboard/summary")) {
      return jsonResponse({
        created_task_count: 1,
        assigned_task_count: 1,
        inbox_count: 1,
        in_progress_count: 1,
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
      });
    }
    if (value.includes("/tasks")) return jsonResponse({ items: [taskSummary], limit: 8, offset: 0, total: 1 });
    return jsonResponse({}, 404);
  }));
}

function mockTaskDetailFetch() {
  vi.stubGlobal("fetch", vi.fn(async (url: string | URL | Request) => {
    const value = new URL(String(url)).pathname;
    const taskId = "22222222-2222-4222-8222-222222222222";
    if (value === `/api/v1/tasks/${taskId}`) {
      return jsonResponse({
        task_id: taskId,
        task_no: "DEV05-TASK-ROUTE",
        task_name: "Route detail task",
        task_description: "Route detail",
        task_goal: "Route detail goal",
        task_source: "Route test",
        creator_employee_no: "DEV02_CREATOR",
        main_assignee_employee_no: "DEV02_EMPLOYEE",
        report_to_employee_no: null,
        report_to_level: null,
        reviewer_employee_no: "DEV02_REVIEWER",
        department_id: null,
        status: "in_progress",
        start_time: null,
        deadline: null,
        estimated_hours: null,
        actual_hours: null,
        task_weight: 3,
        deliverable: null,
        acceptance_criteria: null,
        is_urgent: false,
        report_cycle: null,
        cancel_reason: null,
        withdraw_reason: null,
        close_reason: null,
        merged_into_task_id: null,
        task_version: 1,
        created_at: "2026-09-01T08:00:00Z",
        updated_at: "2026-09-01T09:00:00Z",
        participants: [],
        nodes: [],
        dependencies: [],
        node_participants: [],
        ai_extraction_records: [],
        change_requests: [],
      });
    }
    if (value === `/api/v1/tasks/${taskId}/available-actions`) {
      return jsonResponse({ task_id: taskId, task_version: 1, allowed_actions: [], nodes: [] });
    }
    if (value === `/api/v1/tasks/${taskId}/status-logs`) return jsonResponse({ items: [], limit: 100, offset: 0, total: 0 });
    if (value === `/api/v1/tasks/${taskId}/progress-reports`) return jsonResponse({ items: [], limit: 50, offset: 0, total: 0 });
    if (value === `/api/v1/tasks/${taskId}/issues`) return jsonResponse({ items: [], limit: 50, offset: 0, total: 0 });
    if (value === `/api/v1/tasks/${taskId}/completion-reviews`) return jsonResponse({ items: [], limit: 20, offset: 0, total: 0 });
    if (value.includes("/dashboard/summary")) return jsonResponse({ recent_tasks: [], priority_items: [] });
    if (value === "/api/v1/tasks") return jsonResponse({ items: [taskSummary], limit: 8, offset: 0, total: 1 });
    return jsonResponse({}, 404);
  }));
}

describe("DEV-02 target router", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("allows the login route to render for anonymous users", () => {
    renderRoutes({ route: "/login", user: null });

    expect(screen.getByRole("heading", { name: "登录" })).toBeInTheDocument();
    expect(screen.queryByTestId("app-shell")).not.toBeInTheDocument();
  });

  it("recognizes /workbench and renders the Workbench feature inside the protected shell", async () => {
    mockWorkbenchFetch();
    renderRoutes({ route: "/workbench" });

    expect(screen.getByTestId("app-shell")).toBeInTheDocument();
    expect(await screen.findByTestId("workbench-page")).toBeInTheDocument();
    expect(screen.getByText("AI 任务助手")).toBeInTheDocument();
  });

  it("recognizes /tasks and renders the Task Overview feature inside the protected shell", async () => {
    mockWorkbenchFetch();
    renderRoutes({ route: "/tasks" });

    expect(screen.getByTestId("app-shell")).toBeInTheDocument();
    expect(await screen.findByTestId("task-overview-page")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "任务信息管理" })).toBeInTheDocument();
  });

  it.each(formalTaskRoutes)("recognizes %s and renders the DEV-05 page", async (route, testId) => {
    mockTaskDetailFetch();
    renderRoutes({ route });

    expect(screen.getByTestId("app-shell")).toBeInTheDocument();
    expect(await screen.findByTestId(testId)).toBeInTheDocument();
    expect(screen.queryByTestId("route-contract")).not.toBeInTheDocument();
  });

  it.each(placeholderTargetRoutes)("recognizes %s and renders the protected shell placeholder", (route, title) => {
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

  it("does not trust role_type without backend permission projection", () => {
    renderRoutes({ route: "/executive", user: roleOnlyExecutiveUser });

    expect(screen.getByRole("alert")).toHaveTextContent("无权限访问");
  });

  it("redirects legacy root to workbench without a loop", async () => {
    mockWorkbenchFetch();
    renderRoutes({ route: "/" });

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/workbench"));
    expect(screen.getAllByRole("heading", { name: "工作台" }).length).toBeGreaterThan(0);
  });

  it("redirects legacy task detail URLs and preserves taskId", async () => {
    mockTaskDetailFetch();
    renderRoutes({ route: "/tasks/DEV02-TASK-789" });

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/task/DEV02-TASK-789"));
    expect(await screen.findByText("任务不存在")).toBeInTheDocument();
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
    mockTaskDetailFetch();
    renderRoutes({
      route: "/task/22222222-2222-4222-8222-222222222222",
      state: { source: { pathname: "/notifications", search: "?type=task" } },
    });

    await screen.findByTestId("task-detail-page");
    await userEvent.click(screen.getAllByRole("button", { name: "返回" }).at(-1)!);
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/notifications?type=task"));
  });

  it("uses a route-specific safe fallback when no source exists", async () => {
    mockTaskDetailFetch();
    renderRoutes({ route: "/task/22222222-2222-4222-8222-222222222222" });

    await screen.findByTestId("task-detail-page");
    await userEvent.click(screen.getAllByRole("button", { name: "返回" }).at(-1)!);
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
