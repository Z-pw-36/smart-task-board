/**
 * Feature: V1.1 task overview UI tests.
 * Responsibilities: verify URL-backed filters, task/node modes, data states, and return source state.
 * Does not own: backend filtering correctness or task detail rendering.
 * Plan task: DEV-04.
 */

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Route, Routes, useLocation } from "react-router-dom";

import { jsonResponse, renderPage, taskSummary } from "../../../test/test-utils";
import { TaskOverviewPage } from "../TaskOverviewPage";

const nodeItem = {
  node_id: "33333333-3333-4333-8333-333333333333",
  task_id: taskSummary.task_id,
  task_no: "TASK-001",
  task_name: "发布原型任务看板",
  node_name: "完成移动端概览",
  status: "in_progress",
  task_status: "in_progress",
  owner: { employee_no: "E-CREATOR", name: "测试创建人" },
  planned_start_time: "2026-08-18T08:00:00Z",
  planned_deadline: "2026-08-20T08:00:00Z",
  progress_percent: 60,
  current_user_relations: ["node_owner"],
  is_overdue: false,
  days_until_deadline: 2,
  created_at: "2026-08-18T08:00:00Z",
  updated_at: "2026-08-18T09:00:00Z",
};

function overviewPage(items: unknown[] = [taskSummary], overrides: Record<string, unknown> = {}) {
  return {
    items,
    limit: 20,
    offset: 0,
    page: 1,
    pageSize: 20,
    total: items.length,
    status_counts: {
      pending_acceptance: 1,
      in_progress: 1,
      blocked: 0,
      pending_report: 0,
      pending_review: 0,
    },
    ...overrides,
  };
}

function mockTasksFetch(payloads: unknown[]) {
  const queue = [...payloads];
  const fetchMock = vi.fn(async (url: string | URL | Request) => {
    void url;
    return jsonResponse(queue.shift() ?? payloads[payloads.length - 1]);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderOverview(route = "/tasks") {
  function LocationProbe() {
    const location = useLocation();
    const state = location.state as { source?: { pathname?: string; search?: string } } | null;
    return (
      <output data-testid="location">
        {`${location.pathname}${location.search}${location.hash}|${state?.source?.pathname ?? ""}${state?.source?.search ?? ""}`}
      </output>
    );
  }

  return renderPage(
    <Routes>
      <Route path="/tasks" element={<TaskOverviewPage />} />
      <Route path="/task/:taskId" element={<LocationProbe />} />
      <Route path="*" element={<LocationProbe />} />
    </Routes>,
    { route },
  );
}

describe("TaskOverviewPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    sessionStorage.clear();
  });

  it("renders server status counts and task cards", async () => {
    mockTasksFetch([overviewPage()]);
    renderOverview();

    expect(screen.getByLabelText("正在加载任务概览")).toBeInTheDocument();
    expect(await screen.findByTestId("task-overview-page")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /待接受任务/ })).toHaveTextContent("1");
    expect(screen.getByRole("link", { name: /发布原型任务看板/ })).toHaveAttribute(
      "href",
      `/task/${taskSummary.task_id}`,
    );
  });

  it("keeps quick status filters in the URL and server request", async () => {
    const fetchMock = mockTasksFetch([overviewPage(), overviewPage()]);
    const user = userEvent.setup();
    renderOverview();

    await screen.findByText("发布原型任务看板");
    await user.click(screen.getByRole("button", { name: /进行中任务/ }));

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]));
      expect(urls.some((url) => url.includes("status=in_progress"))).toBe(true);
    });
  });

  it("applies combined filters through URL-backed server parameters", async () => {
    const fetchMock = mockTasksFetch([overviewPage(), overviewPage([nodeItem])]);
    const user = userEvent.setup();
    renderOverview();

    await screen.findByText("发布原型任务看板");
    await user.click(screen.getByRole("button", { name: "更多筛选" }));
    const sheet = screen.getByRole("dialog", { name: "任务筛选" });
    await user.type(within(sheet).getByLabelText("搜索"), "移动端");
    await user.selectOptions(within(sheet).getByLabelText("任务类型"), "nodes");
    await user.selectOptions(within(sheet).getByLabelText("任务状态"), "in_progress");
    await user.selectOptions(within(sheet).getByLabelText("优先级四象限"), "important_urgent");
    await user.click(within(sheet).getByLabelText("仅看未来3天临期"));
    await user.click(within(sheet).getByLabelText("需要支持"));
    await user.selectOptions(within(sheet).getByLabelText("开始时间"), "custom");
    await user.type(within(sheet).getByLabelText("开始日期"), "2026-08-18");
    await user.type(within(sheet).getByLabelText("结束日期"), "2026-08-20");
    await user.selectOptions(within(sheet).getByLabelText("排序"), "updated_at");
    await user.selectOptions(within(sheet).getByLabelText("顺序"), "desc");
    await user.click(within(sheet).getByRole("button", { name: "应用筛选" }));

    expect(await screen.findByText("完成移动端概览")).toBeInTheDocument();
    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]));
      expect(urls.some((url) =>
        url.includes("mode=nodes")
        && url.includes("status=in_progress")
        && url.includes("quadrant=important_urgent")
        && url.includes("nearDue=true")
        && url.includes("support=open")
        && url.includes("datePreset=custom")
        && url.includes("startDate=2026-08-18")
        && url.includes("endDate=2026-08-20")
        && url.includes("sortBy=updated_at")
        && url.includes("sortOrder=desc"),
      )).toBe(true);
    });
  });

  it("preserves Workbench handoff filters on refresh", async () => {
    const fetchMock = mockTasksFetch([overviewPage()]);
    renderOverview("/tasks?quadrant=important_urgent&support=open");

    expect(await screen.findByText("发布原型任务看板")).toBeInTheDocument();
    expect(screen.getByText("重要且紧急")).toBeInTheDocument();
    expect(screen.getByText("需要支持")).toBeInTheDocument();
    const firstUrl = String(fetchMock.mock.calls[0][0]);
    expect(firstUrl).toContain("quadrant=important_urgent");
    expect(firstUrl).toContain("support=open");
  });

  it("renders node mode and carries node anchor plus source state to detail", async () => {
    mockTasksFetch([overviewPage([nodeItem])]);
    const user = userEvent.setup();
    renderOverview("/tasks?mode=nodes&page=2");

    await user.click(await screen.findByRole("link", { name: /完成移动端概览/ }));

    expect(screen.getByTestId("location")).toHaveTextContent(
      `/task/${taskSummary.task_id}#node-${nodeItem.node_id}|/tasks?mode=nodes&page=2`,
    );
  });

  it("shows empty state and resets filters", async () => {
    const fetchMock = mockTasksFetch([overviewPage([], { total: 0 }), overviewPage()]);
    const user = userEvent.setup();
    renderOverview("/tasks?status=pending_review");

    expect(await screen.findByText("当前筛选条件下暂无任务")).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "重置筛选" }).at(-1)!);

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]));
      expect(urls.some((url) => !url.includes("status=pending_review"))).toBe(true);
    });
  });

  it("shows error state and retries", async () => {
    const fetchMock = vi.fn(async () => {
      if (fetchMock.mock.calls.length === 1) return jsonResponse({ error: { message: "bad filter" } }, 500);
      return jsonResponse(overviewPage());
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderOverview();

    expect(await screen.findByText("任务概览暂时无法加载")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "重试" }));
    expect(await screen.findByText("发布原型任务看板")).toBeInTheDocument();
  });

  it("restores scroll position as session UI state only", async () => {
    mockTasksFetch([overviewPage()]);
    sessionStorage.setItem("smarttaskboard.task-overview.scroll", "120");
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);

    renderOverview("/tasks?status=in_progress");

    await waitFor(() => expect(scrollTo).toHaveBeenCalledWith(0, 120));
  });
});
