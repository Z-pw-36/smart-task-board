/**
 * Feature: V1.1 Workbench UI tests.
 * Responsibilities: verify Workbench sections, route navigation, data states, and role-conditioned entry points.
 * Does not own: backend security decisions, downstream create flow, or task detail implementation.
 * Plan task: DEV-03.
 */

import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Route, Routes, useLocation } from "react-router-dom";

import type { CurrentUser } from "../../../api/types";
import { jsonResponse, renderPage, taskSummary } from "../../../test/test-utils";
import { WorkbenchPage } from "../WorkbenchPage";

const employeePermissions = {
  can_access_executive: false,
  can_manage_permissions: false,
  can_view_all_demo_data: false,
  allowed_routes: ["/workbench", "/tasks", "/create/details", "/create/confirm", "/notifications", "/profile"],
  capabilities: ["task:read:related"],
};

const executiveUser: CurrentUser = {
  employee_no: "DEV03_EXECUTIVE",
  name: "Workbench Executive",
  department: null,
  role_type: "employee",
  roles: ["employee"],
  permissions: {
    ...employeePermissions,
    can_access_executive: true,
    allowed_routes: [...employeePermissions.allowed_routes, "/executive", "/executive/employee-tasks"],
    capabilities: ["task:read:related", "executive:read"],
  },
  scopes: [],
  auth_mode: "test",
};

function dashboardPayload(overrides: Record<string, unknown> = {}) {
  return {
    created_task_count: 1,
    assigned_task_count: 1,
    inbox_count: 2,
    in_progress_count: 1,
    pending_acceptance_count: 1,
    today_task_count: 1,
    due_within_7_days_count: 1,
    overdue_count: 0,
    report_due_count: 0,
    open_issue_count: 1,
    blocked_task_count: 1,
    completion_review_count: 1,
    unread_notification_count: 2,
    open_conflict_count: 0,
    due_window_days: 7,
    recent_tasks: [taskSummary],
    latest_workload: { workload_score: 42, workload_level: "normal" },
    priority_items: [{ task_id: taskSummary.task_id, priority_quadrant: "important_urgent", sort_rank: 1 }],
    ...overrides,
  };
}

function taskPage(items: unknown[] = [taskSummary]) {
  return { items, limit: 8, offset: 0, total: items.length };
}

function mockWorkbenchFetch(summary: unknown, tasks: unknown) {
  const fetchMock = vi.fn(async (url: string | URL | Request) => {
    const value = String(url);
    if (value.includes("/dashboard/summary")) return jsonResponse(summary);
    if (value.includes("/tasks")) return jsonResponse(tasks);
    return jsonResponse({}, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderWorkbench(options: { route?: string; user?: CurrentUser } = {}) {
  function LocationProbe() {
    const location = useLocation();
    return <output data-testid="location">{`${location.pathname}${location.search}`}</output>;
  }

  return renderPage(
    <Routes>
      <Route path="/workbench" element={<WorkbenchPage />} />
      <Route path="*" element={<LocationProbe />} />
    </Routes>,
    { route: options.route ?? "/workbench", auth: options.user ? { user: options.user } : undefined },
  );
}

describe("WorkbenchPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the core Workbench sections from real API payloads", async () => {
    mockWorkbenchFetch(dashboardPayload(), taskPage());
    renderWorkbench();

    expect(screen.getByLabelText("正在加载工作台")).toBeInTheDocument();
    expect(await screen.findByText("任务指标")).toBeInTheDocument();
    expect(screen.getByText("任务风险四象限")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "需要支持" })).toBeInTheDocument();
    expect(screen.getByText("AI 任务助手")).toBeInTheDocument();
    expect(screen.getByText("任务信息管理")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "后端负荷评分" })).toHaveAttribute("aria-valuenow", "42");
    expect(screen.getByText("发布原型任务看板")).toBeInTheDocument();
  });

  it("uses formal DEV-02 route targets and voice fallback navigation", async () => {
    mockWorkbenchFetch(dashboardPayload(), taskPage());
    renderWorkbench();

    expect(await screen.findByRole("link", { name: "描述任务" })).toHaveAttribute("href", "/create/details");
    expect(screen.getByRole("link", { name: "语音描述任务" })).toHaveAttribute("href", "/create/details");
    expect(screen.getByRole("link", { name: "全部任务" })).toHaveAttribute("href", "/tasks");
    expect(screen.getByRole("link", { name: /通知，2 条未读/ })).toHaveAttribute("href", "/notifications");
    expect(screen.getByRole("link", { name: /发布原型任务看板/ })).toHaveAttribute("href", `/task/${taskSummary.task_id}`);
  });

  it("hands status, quadrant, and support filters to task overview URLs", async () => {
    mockWorkbenchFetch(dashboardPayload(), taskPage());
    renderWorkbench();

    expect(await screen.findByRole("link", { name: /进行中 1，按状态查看任务概览/ })).toHaveAttribute("href", "/tasks?status=in_progress");
    expect(screen.getByRole("link", { name: /重要且紧急 1，按象限查看任务概览/ })).toHaveAttribute("href", "/tasks?quadrant=important_urgent");
    expect(screen.getByRole("link", { name: /需要支持 1，查看任务概览/ })).toHaveAttribute("href", "/tasks?support=open");
  });

  it("omits notification red dot when there is no unread notification", async () => {
    mockWorkbenchFetch(dashboardPayload({ unread_notification_count: 0 }), taskPage());
    renderWorkbench();

    expect(await screen.findByRole("link", { name: "通知" })).toHaveAttribute("href", "/notifications");
    expect(screen.queryByRole("link", { name: /条未读/ })).not.toBeInTheDocument();
  });

  it("renders empty state without fake tasks", async () => {
    mockWorkbenchFetch(dashboardPayload({ created_task_count: 0, assigned_task_count: 0, inbox_count: 0, unread_notification_count: 0, priority_items: [] }), taskPage([]));
    renderWorkbench();

    expect(await screen.findByText("暂无工作台数据")).toBeInTheDocument();
    expect(screen.queryByText("发布原型任务看板")).not.toBeInTheDocument();
  });

  it("shows error and retries successfully", async () => {
    const fetchMock = vi.fn(async (url: string | URL | Request) => {
      const value = String(url);
      if (fetchMock.mock.calls.length <= 2) return jsonResponse({ error: { message: "internal" } }, 500);
      if (value.includes("/dashboard/summary")) return jsonResponse(dashboardPayload());
      if (value.includes("/tasks")) return jsonResponse(taskPage());
      return jsonResponse({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderWorkbench();

    expect(await screen.findByText("工作台暂时无法加载")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "重试" }));
    expect(await screen.findByText("发布原型任务看板")).toBeInTheDocument();
  });

  it("keeps executive entry role-conditioned", async () => {
    mockWorkbenchFetch(dashboardPayload(), taskPage());
    renderWorkbench();

    expect(await screen.findByText("任务指标")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "团队态势" })).not.toBeInTheDocument();

    vi.unstubAllGlobals();
    mockWorkbenchFetch(dashboardPayload(), taskPage());
    renderWorkbench({ user: executiveUser });

    expect(await screen.findByRole("link", { name: "团队态势" })).toHaveAttribute("href", "/executive");
  });
});
