/**
 * Feature: V1.1 task detail read-only tests.
 * Responsibilities: verify DEV-05 detail, report, review, data states, node anchors, permissions, and route return behavior.
 * Does not own: backend query correctness, workflow mutations, or visual screenshots.
 * Plan task: DEV-05.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import { AuthContext, type AuthValue } from "../../../auth/auth-context";
import { currentUser, jsonResponse, renderPage } from "../../../test/test-utils";
import { TaskDetailPage } from "../TaskDetailPage";
import { TaskReportPage } from "../TaskReportPage";
import { TaskReviewPage } from "../TaskReviewPage";

const taskId = "22222222-2222-4222-8222-222222222222";
const nodeId = "33333333-3333-4333-8333-333333333333";

function detail(overrides: Record<string, unknown> = {}) {
  return {
    task_id: taskId,
    task_no: "DEV05-TASK-001",
    task_name: "落实跨部门移动端看板正式验收",
    task_description: "围绕第二版 HTML 进行只读转换。",
    task_goal: "完成任务详情、汇报、验收页面的数据化展示。",
    task_source: "管理例会",
    creator_employee_no: "E-CREATOR",
    main_assignee_employee_no: "E-ASSIGNEE",
    report_to_employee_no: "E-MANAGER",
    report_to_level: "director",
    reviewer_employee_no: "E-REVIEWER",
    department_id: "11111111-1111-4111-8111-111111111111",
    status: "in_progress",
    start_time: "2026-09-01T01:00:00Z",
    deadline: "2026-09-08T10:30:00Z",
    estimated_hours: "80",
    actual_hours: "6.5",
    task_weight: 4,
    deliverable: "上线清单",
    acceptance_criteria: "移动端和桌面端均无横向溢出。",
    is_urgent: false,
    report_cycle: "weekly:FRI@18:00",
    cancel_reason: null,
    withdraw_reason: null,
    close_reason: null,
    merged_into_task_id: null,
    task_version: 7,
    created_at: "2026-09-01T01:00:00Z",
    updated_at: "2026-09-01T02:00:00Z",
    confirmed_at: "2026-09-01T01:10:00Z",
    sent_at: "2026-09-01T01:12:00Z",
    accepted_at: "2026-09-01T01:30:00Z",
    completed_at: null,
    archived_at: null,
    participants: [
      { participant_id: "44444444-4444-4444-8444-444444444444", employee_no: "E-COLLAB", participant_role: "collaborator" },
    ],
    nodes: [
      {
        node_id: nodeId,
        task_id: taskId,
        node_order: 1,
        sort_weight: 0,
        node_name: "整理只读详情字段",
        action_detail: "核对正式 DTO 后完成页面展示。",
        owner_employee_no: "E-ASSIGNEE",
        planned_start_time: "2026-09-01T01:00:00Z",
        planned_deadline: "2026-09-03T10:30:00Z",
        estimated_hours: "12",
        actual_hours: "3",
        deliverable: "字段矩阵",
        acceptance_criteria: "不得包含写接口调用。",
        tools_or_materials: "OpenAPI",
        progress_percent: 70,
        status: "in_progress",
        completed_at: null,
      },
    ],
    dependencies: [],
    node_participants: [],
    performance_matches: [
      {
        performance_match_id: "99999999-9999-4999-8999-999999999990",
        task_id: taskId,
        metric_id: "99999999-9999-4999-8999-999999999991",
        metric_type: "quality",
        metric_name: "上线质量指标",
        period: "2026-Q3",
        business_unit: "产品事业部",
        definition_formula: "验收缺陷数低于阈值",
        total_score: "88",
        match_level: "strong",
        match_reason: "任务目标直接支撑上线质量。",
        is_confirmed: true,
        confirmed_by_employee_no: "E-CREATOR",
        confirmed_at: "2026-09-01T01:40:00Z",
      },
    ],
    operation_logs: [
      {
        operation_log_id: "99999999-9999-4999-8999-999999999992",
        request_id: "REQ-DEV05",
        operator_employee_no: "E-CREATOR",
        action: "kpi_match_confirmed",
        object_type: "task",
        object_id: taskId,
        before_data: null,
        after_data: { is_confirmed: true },
        result: "success",
        error_message: null,
        created_at: "2026-09-01T01:40:00Z",
      },
    ],
    ai_extraction_records: [],
    change_requests: [],
    ...overrides,
  };
}

function relatedPayloads(overrides: {
  task?: Record<string, unknown>;
  actions?: string[];
  reports?: unknown[];
  issues?: unknown[];
  reviews?: unknown[];
  logs?: unknown[];
} = {}) {
  return {
    task: detail(overrides.task),
    actions: {
      task_id: taskId,
      task_version: 7,
      allowed_actions: overrides.actions ?? ["submit_progress_report", "submit_change_request"],
      nodes: [{ node_id: nodeId, allowed_actions: [] }],
    },
    logs: {
      items: overrides.logs ?? [{
        status_log_id: "55555555-5555-4555-8555-555555555555",
        task_id: taskId,
        from_status: "pending_acceptance",
        to_status: "in_progress",
        action_type: "accept",
        reason: null,
        operator_employee_no: "E-ASSIGNEE",
        task_version: 6,
        created_at: "2026-09-01T01:30:00Z",
      }],
      limit: 100,
      offset: 0,
      total: 1,
    },
    reports: {
      items: overrides.reports ?? [{
        progress_report_id: "66666666-6666-4666-8666-666666666666",
        task_id: taskId,
        node_id: null,
        reporter_employee_no: "E-ASSIGNEE",
        progress_percent: 65,
        report_content: "已完成页面骨架与字段核对。",
        stage_result: "组件结构稳定。",
        difficulty: "无",
        resource_request: null,
        actual_hours: null,
        corrects_report_id: null,
        report_period_start: null,
        report_period_end: null,
        task_version: 7,
        operation_source: "rest_api",
        created_at: "2026-09-01T02:00:00Z",
      }],
      limit: 50,
      offset: 0,
      total: 1,
    },
    issues: {
      items: overrides.issues ?? [{
        issue_id: "77777777-7777-4777-8777-777777777777",
        task_id: taskId,
        node_id: nodeId,
        source_progress_report_id: null,
        reported_by_employee_no: "E-ASSIGNEE",
        issue_type: "blocker",
        title: "数据字段待确认",
        description: "绩效只展示现有投影。",
        requested_resource: null,
        severity: "medium",
        status: "open",
        owner_employee_no: "E-CREATOR",
        resolution_note: null,
        resolved_by_employee_no: null,
        rejected_by_employee_no: null,
        closed_by_employee_no: null,
        created_at: "2026-09-01T02:10:00Z",
        processing_started_at: null,
        resolved_at: null,
        rejected_at: null,
        closed_at: null,
        allowed_actions: [],
      }],
      limit: 50,
      offset: 0,
      total: 1,
    },
    reviews: {
      items: overrides.reviews ?? [{
        completion_review_id: "88888888-8888-4888-8888-888888888888",
        task_id: taskId,
        review_round: 1,
        submitted_by_employee_no: "E-ASSIGNEE",
        completion_note: "所有节点已完成。",
        deliverable_summary: "验收包",
        reviewer_employee_no: "E-REVIEWER",
        review_status: "submitted",
        review_result: null,
        reject_reason: null,
        rework_node_id: null,
        submitted_task_version: 7,
        reviewed_task_version: null,
        submitted_at: "2026-09-01T03:00:00Z",
        reviewed_at: null,
        is_legacy_import: false,
      }],
      limit: 20,
      offset: 0,
      total: 1,
    },
  };
}

function responseForDetailUrl(url: string | URL | Request, payload = relatedPayloads()) {
  const parsed = new URL(String(url));
  if (parsed.pathname === `/api/v1/tasks/${taskId}`) return jsonResponse(payload.task);
  if (parsed.pathname === `/api/v1/tasks/${taskId}/available-actions`) return jsonResponse(payload.actions);
  if (parsed.pathname === `/api/v1/tasks/${taskId}/status-logs`) return jsonResponse(payload.logs);
  if (parsed.pathname === `/api/v1/tasks/${taskId}/progress-reports`) return jsonResponse(payload.reports);
  if (parsed.pathname === `/api/v1/tasks/${taskId}/issues`) return jsonResponse(payload.issues);
  if (parsed.pathname === `/api/v1/tasks/${taskId}/completion-reviews`) return jsonResponse(payload.reviews);
  return jsonResponse({ error: { code: "not_found", message: "not found" } }, 404);
}

function mockDetailFetch(payload = relatedPayloads()) {
  const fetchMock = vi.fn(async (url: string | URL | Request) => responseForDetailUrl(url, payload));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function routeElements() {
  function LocationProbe() {
    const location = useLocation();
    return <output data-testid="location">{`${location.pathname}${location.search}${location.hash}`}</output>;
  }

  return (
    <Routes>
      <Route path="/tasks" element={<LocationProbe />} />
      <Route path="/workbench" element={<LocationProbe />} />
      <Route path="/notifications" element={<LocationProbe />} />
      <Route path="/executive/employee-tasks" element={<LocationProbe />} />
      <Route path="/task/:taskId" element={<TaskDetailPage />} />
      <Route path="/task/:taskId/report" element={<TaskReportPage />} />
      <Route path="/task/:taskId/review" element={<TaskReviewPage />} />
    </Routes>
  );
}

function renderTaskRoutes(route: string) {
  return renderPage(
    routeElements(),
    { route },
  );
}

function renderTaskRoutesWithState(route: string, state: unknown) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const auth: AuthValue = { user: currentUser, loading: false, login: vi.fn(), logout: vi.fn() };
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={auth}>
        <MemoryRouter initialEntries={[{ pathname: route, state }]}>
          {routeElements()}
        </MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

describe("TaskDetail DEV-05 pages", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders the formal five modules and read-only projections without estimated-hour UI", async () => {
    mockDetailFetch();
    renderTaskRoutes(`/task/${taskId}`);

    expect(screen.getByLabelText("正在加载任务详情")).toBeInTheDocument();
    expect(await screen.findByTestId("task-detail-page")).toBeInTheDocument();
    for (const tab of ["概览", "人员", "节点", "进度/汇报", "绩效"]) {
      expect(screen.getByRole("tab", { name: tab })).toBeInTheDocument();
    }
    expect(screen.getByRole("heading", { name: "基本信息" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "人员信息" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "节点执行" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "最新进度汇报" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "绩效关联" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "操作记录" })).toBeInTheDocument();
    expect(screen.getByText("6.5 小时（系统只读）")).toBeInTheDocument();
    expect(screen.getByText("上线质量指标")).toBeInTheDocument();
    expect(screen.getByText("kpi_match_confirmed")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "汇报进度" })).toHaveAttribute("href", `/task/${taskId}/report`);
    expect(screen.queryByText("预计工时")).not.toBeInTheDocument();
    expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument();
  });

  it("focuses the node anchor after async detail data loads", async () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(Element.prototype, "scrollIntoView", { configurable: true, value: scrollIntoView });
    mockDetailFetch();
    renderTaskRoutes(`/task/${taskId}#node-${nodeId}`);

    const node = await waitFor(() => {
      const element = document.getElementById(`node-${nodeId}`);
      expect(element).not.toBeNull();
      return element!;
    });
    await waitFor(() => expect(scrollIntoView).toHaveBeenCalled());
    expect(node).toHaveFocus();
    expect(screen.getByRole("tab", { name: "节点" })).toHaveAttribute("aria-selected", "true");
  });

  it("ignores missing or unauthorized node anchors without treating the task as broken", async () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(Element.prototype, "scrollIntoView", { configurable: true, value: scrollIntoView });
    mockDetailFetch();
    renderTaskRoutes(`/task/${taskId}#node-unauthorized-node`);

    expect(await screen.findByTestId("task-detail-page")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "节点执行" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "概览" })).toHaveAttribute("aria-selected", "true");
    expect(scrollIntoView).not.toHaveBeenCalled();
  });

  it("shows 403, 404, and retryable 500 surfaces", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ error: { code: "SCOPE_DENIED", message: "denied" } }, 403));
    vi.stubGlobal("fetch", fetchMock);
    renderTaskRoutes(`/task/${taskId}`);
    expect(await screen.findByText("无权限查看任务")).toBeInTheDocument();

    cleanup();
    vi.unstubAllGlobals();
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ error: { code: "TASK_NOT_FOUND", message: "missing" } }, 404)));
    renderTaskRoutes(`/task/${taskId}/report`);
    expect(await screen.findByText("任务不存在")).toBeInTheDocument();

    cleanup();
    vi.unstubAllGlobals();
    const payload = relatedPayloads();
    const retryMock = vi.fn(async (url: string | URL | Request) => {
      if (retryMock.mock.calls.length <= 6) return jsonResponse({ error: { code: "INTERNAL_ERROR", message: "boom" } }, 500);
      return responseForDetailUrl(url, payload);
    });
    vi.stubGlobal("fetch", retryMock);
    const user = userEvent.setup();
    renderTaskRoutes(`/task/${taskId}/review`);
    expect(await screen.findByText("验收页面暂时无法加载")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "重试" }));
    expect(await screen.findByTestId("task-review-page")).toBeInTheDocument();
  });

  it("renders empty states for no nodes, no reports, no performance, and missing anchor", async () => {
    mockDetailFetch(relatedPayloads({
      task: { nodes: [], performance_matches: [], operation_logs: [] },
      reports: [],
      issues: [],
      reviews: [],
      logs: [],
    }));
    renderTaskRoutes(`/task/${taskId}#node-missing`);

    expect(await screen.findByText("暂无节点任务")).toBeInTheDocument();
    expect(screen.getByText("暂无进度汇报")).toBeInTheDocument();
    expect(screen.getByText("暂无绩效关联")).toBeInTheDocument();
    expect(screen.getByText("暂无状态轨迹")).toBeInTheDocument();
    expect(screen.getByText("暂无操作记录")).toBeInTheDocument();
  });

  it("treats pending acceptance tasks without nodes as a legal empty state", async () => {
    mockDetailFetch(relatedPayloads({
      task: {
        status: "pending_accept",
        nodes: [],
        performance_matches: [],
        operation_logs: [],
      },
      reports: [],
      issues: [],
    }));
    renderTaskRoutes(`/task/${taskId}`);

    expect((await screen.findAllByText("待接受")).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("待接受或拆解前任务允许没有节点，这不是系统异常。")).toBeInTheDocument();
    expect(screen.queryByText("任务详情暂时无法加载")).not.toBeInTheDocument();
  });

  it("renders report as read-only with no submit mutation or actual-hour input", async () => {
    const fetchMock = mockDetailFetch();
    renderTaskRoutes(`/task/${taskId}/report`);

    expect(await screen.findByTestId("task-report-page")).toBeInTheDocument();
    expect(screen.getByText("当前为 DEV-05 只读汇报页面；提交汇报、卡点和资源诉求写入在 DEV-11 启用。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /提交进度汇报/ })).toBeDisabled();
    expect(screen.queryByLabelText(/实际工时/)).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.map((call) => String(call[0])).some((url) => url.includes("/progress-reports") && url.includes("/api/v1/tasks/"))).toBe(true);
  });

  it.each([
    ["/workbench", ""],
    ["/notifications", "?type=task"],
    ["/executive/employee-tasks", "?employeeNo=E-ASSIGNEE&snapshotId=S1"],
  ])("preserves return source %s%s", async (pathname, search) => {
    mockDetailFetch(relatedPayloads({ actions: ["approve_completion", "reject_completion"], reviews: [] }));
    const user = userEvent.setup();
    renderTaskRoutesWithState(`/task/${taskId}/review`, { source: { pathname, search } });

    expect(await screen.findByTestId("task-review-page")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /验收通过/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /验收退回/ })).toBeDisabled();
    expect(screen.getByText("不会生成模拟验收记录。")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "返回" }));
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent(`${pathname}${search}`));
  });
});
