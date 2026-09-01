/**
 * Feature: V1.1 workbench API projection tests.
 * Responsibilities: verify Workbench query normalization over existing dashboard and task APIs.
 * Does not own: backend authorization, task calculations, or network transport internals.
 * Plan task: DEV-03.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { jsonResponse, taskSummary } from "../../../test/test-utils";
import { loadWorkbenchData } from "../api";

function dashboardPayload(overrides: Record<string, unknown> = {}) {
  return {
    created_task_count: 1,
    assigned_task_count: 2,
    inbox_count: 3,
    in_progress_count: 4,
    pending_acceptance_count: 5,
    today_task_count: 6,
    due_within_7_days_count: 7,
    overdue_count: 0,
    report_due_count: 1,
    open_issue_count: 2,
    blocked_task_count: 2,
    completion_review_count: 1,
    unread_notification_count: 1,
    open_conflict_count: 1,
    due_window_days: 7,
    recent_tasks: [],
    latest_workload: null,
    priority_items: [
      { task_id: taskSummary.task_id, priority_quadrant: "important_urgent", sort_rank: 1 },
      { task_id: "33333333-3333-4333-8333-333333333333", priority_quadrant: "routine", sort_rank: 2 },
    ],
    ...overrides,
  };
}

function mockWorkbenchFetch(summary: unknown, tasks: unknown, status = 200) {
  const fetchMock = vi.fn(async (url: string | URL | Request) => {
    const value = String(url);
    if (value.includes("/dashboard/summary")) return jsonResponse(summary, status);
    if (value.includes("/tasks")) return jsonResponse(tasks, status);
    return jsonResponse({}, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("Workbench API projection", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads dashboard summary and server-ordered tasks", async () => {
    const laterTask = { ...taskSummary, task_id: "33333333-3333-4333-8333-333333333333", task_name: "第二项任务" };
    mockWorkbenchFetch(dashboardPayload(), { items: [laterTask, taskSummary], limit: 8, offset: 0, total: 2 });

    const result = await loadWorkbenchData();

    expect(result.summary.inbox_count).toBe(3);
    expect(result.tasks.map((task) => task.task_name)).toEqual(["第二项任务", "发布原型任务看板"]);
    expect(result.quadrants.find((item) => item.id === "important_urgent")?.count).toBe(1);
  });

  it("returns an empty workbench without inventing tasks", async () => {
    mockWorkbenchFetch(dashboardPayload({ created_task_count: 0, assigned_task_count: 0, inbox_count: 0, unread_notification_count: 0, priority_items: [] }), {
      items: [],
      limit: 8,
      offset: 0,
      total: 0,
    });

    const result = await loadWorkbenchData();

    expect(result.tasks).toEqual([]);
    expect(result.quadrants.every((item) => item.count === 0)).toBe(true);
  });

  it("rejects upstream 500 responses for the UI retry state", async () => {
    mockWorkbenchFetch({ error: { message: "internal" } }, { items: [] }, 500);

    await expect(loadWorkbenchData()).rejects.toMatchObject({ status: 500 });
  });

  it("keeps permission-scoped API values without client-side expansion", async () => {
    mockWorkbenchFetch(dashboardPayload({ assigned_task_count: 0, recent_tasks: [] }), {
      items: [{ ...taskSummary, current_user_relations: ["reviewer"], allowed_actions: [] }],
      limit: 8,
      offset: 0,
      total: 1,
    });

    const result = await loadWorkbenchData();

    expect(result.summary.assigned_task_count).toBe(0);
    expect(result.tasks[0].current_user_relations).toEqual(["reviewer"]);
  });

  it("defends against missing and invalid fields", async () => {
    mockWorkbenchFetch({ due_within_7_days_count: "bad", priority_items: [{ priority_quadrant: "unknown" }] }, {
      items: [{ task_id: "", task_name: "" }, { task_id: "44444444-4444-4444-8444-444444444444", task_name: "字段防御任务", status: "unexpected" }],
      limit: 8,
      offset: 0,
      total: 2,
    });

    const result = await loadWorkbenchData();

    expect(result.summary.due_within_7_days_count).toBe(0);
    expect(result.tasks).toHaveLength(1);
    expect(result.tasks[0].status).toBe("in_progress");
  });

  it("passes status filters to the server query", async () => {
    const fetchMock = mockWorkbenchFetch(dashboardPayload(), { items: [taskSummary], limit: 8, offset: 0, total: 1 });

    await loadWorkbenchData({ status: "in_progress" });

    expect(fetchMock.mock.calls.some((call) => String(call[0]).includes("status=in_progress"))).toBe(true);
  });
});
