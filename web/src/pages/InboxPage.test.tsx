import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { jsonResponse, renderPage, taskSummary } from "../test/test-utils";
import { InboxPage } from "./InboxPage";

describe("InboxPage", () => {
  it("renders only server-authorized actions and does not invent participant writes", async () => {
    const participantOnly = { inbox_item_type: "observer", action_code: "update_node", task: taskSummary, node: { node_id: "33333333-3333-4333-8333-333333333333", node_name: "只读节点", status: "in_progress", progress_percent: 20, owner_employee_no: "E-ASSIGNEE" }, reason: "只读参与", expected_task_version: 4, endpoint: "/api/v1/tasks/x/nodes/y/progress", allowed_actions: [], is_overdue: false, relevant_at: "2026-08-18T09:00:00Z" };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ items: [participantOnly], limit: 20, offset: 0, total: 1 })));
    renderPage(<InboxPage />);

    const inboxCard = await screen.findByRole("article");
    expect(within(inboxCard).getByText(/只读节点/)).toHaveTextContent("只读节点");
    expect(within(inboxCard).getByText(/20%/)).toHaveTextContent("20%");
    expect(within(inboxCard).queryByRole("button", { name: "更新进度" })).not.toBeInTheDocument();
    expect(within(inboxCard).queryByRole("button", { name: "完成节点" })).not.toBeInTheDocument();
  });

  it("shows the required refresh message after a 409", async () => {
    const item = { inbox_item_type: "accept_task", action_code: "accept_task", task: taskSummary, node: null, reason: "等待接受", expected_task_version: 4, endpoint: "/api/v1/tasks/x/actions/accept", allowed_actions: ["accept"], is_overdue: false, relevant_at: "2026-08-18T09:00:00Z" };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ items: [item], limit: 20, offset: 0, total: 1 }))
      .mockResolvedValueOnce(jsonResponse({ error: { code: "task_version_conflict", message: "conflict", details: {} } }, 409));
    vi.stubGlobal("fetch", fetchMock);
    renderPage(<InboxPage />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "接受任务" }));

    expect(await screen.findByText("任务已被其他操作更新，请刷新后重试。")).toBeInTheDocument();
  });

  it("posts issue inbox actions to the issue action endpoint", async () => {
    const issueItem = {
      inbox_item_type: "task_issue",
      action_code: "handle_issue",
      task: taskSummary,
      node: null,
      reason: "Issue needs attention",
      expected_task_version: 4,
      endpoint: "/api/v1/tasks/22222222-2222-4222-8222-222222222222/issues/44444444-4444-4444-8444-444444444444/actions",
      allowed_actions: ["start_processing_issue"],
      is_overdue: false,
      relevant_at: "2026-08-18T09:00:00Z",
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ items: [issueItem], limit: 20, offset: 0, total: 1 }))
      .mockResolvedValueOnce(jsonResponse({ status: "processing" }))
      .mockResolvedValue(jsonResponse({ items: [], limit: 20, offset: 0, total: 0 }));
    vi.stubGlobal("fetch", fetchMock);
    renderPage(<InboxPage />);
    const user = userEvent.setup();

    const inboxCard = await screen.findByRole("article");
    await user.click(within(inboxCard).getByRole("button"));

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/v1/tasks/22222222-2222-4222-8222-222222222222/issues/44444444-4444-4444-8444-444444444444/actions/start-processing",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ expected_task_version: 4 }),
      }),
    );
  });

  it("routes change request approval through the explicit approval endpoint", async () => {
    const changeRequestItem = {
      inbox_item_type: "approve_change_request",
      action_code: "approve_change_request",
      task: taskSummary,
      node: null,
      reason: "A pending change request needs a decision",
      expected_task_version: 4,
      endpoint: "/api/v1/tasks/22222222-2222-4222-8222-222222222222/change-requests/55555555-5555-4555-8555-555555555555/actions",
      allowed_actions: ["approve_change_request"],
      is_overdue: false,
      relevant_at: "2026-08-18T09:00:00Z",
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ items: [changeRequestItem], limit: 20, offset: 0, total: 1 }))
      .mockResolvedValue(jsonResponse({ status: "in_progress" }));
    vi.stubGlobal("fetch", fetchMock);
    renderPage(<InboxPage />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "批准变更" }));

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/v1/tasks/22222222-2222-4222-8222-222222222222/change-requests/55555555-5555-4555-8555-555555555555/actions/approve",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ expected_task_version: 4, approval_comment: null }),
      }),
    );
  });

  it("prompts for a cancellation reason before posting a change request cancellation", async () => {
    const changeRequestItem = {
      inbox_item_type: "cancel_change_request",
      action_code: "cancel_change_request",
      task: taskSummary,
      node: null,
      reason: "Cancel the pending request",
      expected_task_version: 4,
      endpoint: "/api/v1/tasks/22222222-2222-4222-8222-222222222222/change-requests/55555555-5555-4555-8555-555555555555/actions",
      allowed_actions: ["cancel_change_request"],
      is_overdue: false,
      relevant_at: "2026-08-18T09:00:00Z",
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ items: [changeRequestItem], limit: 20, offset: 0, total: 1 }))
      .mockResolvedValue(jsonResponse({ status: "in_progress" }));
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(window, "prompt").mockReturnValue("需求已调整");
    renderPage(<InboxPage />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "取消变更申请" }));

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/v1/tasks/22222222-2222-4222-8222-222222222222/change-requests/55555555-5555-4555-8555-555555555555/actions/cancel",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ expected_task_version: 4, reason: "需求已调整" }),
      }),
    );
  });

  it("navigates completion submit, review, and reopen work to the rich detail flow", async () => {
    const taskId = taskSummary.task_id;
    const base = {
      task: taskSummary,
      node: null,
      reason: "Completion work requires detail context",
      expected_task_version: 4,
      is_overdue: false,
      relevant_at: "2026-08-18T09:00:00Z",
    };
    const items = [
      {
        ...base,
        inbox_item_type: "submit_completion",
        action_code: "submit_completion",
        endpoint: `/api/v1/tasks/${taskId}/actions/submit-completion`,
        allowed_actions: ["submit_completion"],
      },
      {
        ...base,
        inbox_item_type: "approve_completion",
        action_code: "approve_completion",
        endpoint: `/api/v1/tasks/${taskId}/actions/approve-completion`,
        allowed_actions: ["approve_completion", "reject_completion"],
      },
      {
        ...base,
        inbox_item_type: "reopen_node",
        action_code: "reopen_node",
        endpoint: `/api/v1/tasks/${taskId}/nodes/node/actions/reopen`,
        allowed_actions: ["reopen_node"],
      },
    ];
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ items, limit: 20, offset: 0, total: items.length }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPage(<InboxPage />);

    expect(await screen.findByRole("link", { name: "填写完成说明并提交" })).toHaveAttribute(
      "href",
      `/tasks/${taskId}`,
    );
    expect(screen.getByRole("link", { name: "查看并验收" })).toHaveAttribute(
      "href",
      `/tasks/${taskId}`,
    );
    expect(screen.getByRole("link", { name: "查看返工要求" })).toHaveAttribute(
      "href",
      `/tasks/${taskId}`,
    );
    expect(screen.queryByRole("button", { name: "提交验收" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "通过验收" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "重开节点" })).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
