import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { jsonResponse, renderPage, taskSummary } from "../test/test-utils";
import { DashboardPage } from "./DashboardPage";
import { TasksPage } from "./TasksPage";

describe("dashboard and task list", () => {
  it("shows current-user metrics and recent tasks", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ created_task_count: 2, assigned_task_count: 1, inbox_count: 3, in_progress_count: 1, due_within_7_days_count: 1, overdue_count: 0, due_window_days: 7, recent_tasks: [taskSummary] })));
    renderPage(<DashboardPage />);

    expect(await screen.findByText("发布原型任务看板")).toBeInTheDocument();
    expect(screen.getByText("未来 7 天截止")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "创建任务" })).toHaveAttribute("href", "/tasks/new");
  });

  it("applies relation and search filters to the task query", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ items: [], limit: 20, offset: 0, total: 0 }));
    vi.stubGlobal("fetch", fetchMock);
    renderPage(<TasksPage />);
    const user = userEvent.setup();

    await screen.findByText("没有符合条件的任务");
    await user.selectOptions(screen.getByLabelText("关系"), "assigned");
    await user.type(screen.getByLabelText("搜索"), "发布");

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]));
      expect(urls.some((url) => url.includes("relation=assigned") && url.includes("search=%E5%8F%91%E5%B8%83"))).toBe(true);
    });
  });
});
