import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { AvailableActions, TaskDetail } from "../api/types";
import { jsonResponse, renderPage } from "../test/test-utils";
import { ChangeRequestsPanel } from "./ChangeRequestsPanel";

const taskId = "22222222-2222-4222-8222-222222222222";
const requestId = "55555555-5555-4555-8555-555555555555";

const task = {
  task_id: taskId,
  task_no: "TASK-001",
  task_name: "变更申请测试任务",
  task_description: null,
  task_goal: null,
  task_source: null,
  creator_employee_no: "E-CREATOR",
  main_assignee_employee_no: "E-ASSIGNEE",
  report_to_employee_no: null,
  report_to_level: null,
  reviewer_employee_no: "E-CREATOR",
  department_id: null,
  status: "in_progress",
  start_time: null,
  deadline: null,
  estimated_hours: null,
  actual_hours: null,
  task_weight: null,
  deliverable: null,
  acceptance_criteria: null,
  is_urgent: false,
  report_cycle: null,
  task_version: 4,
  created_at: "2026-08-18T08:00:00Z",
  updated_at: "2026-08-18T09:00:00Z",
  participants: [],
  nodes: [],
  dependencies: [],
  node_participants: [],
  change_requests: [],
} as TaskDetail;

function actions(...allowedActions: AvailableActions["allowed_actions"]): AvailableActions {
  return { task_id: taskId, task_version: 4, allowed_actions: allowedActions, nodes: [] };
}

function request(status: "pending" | "approved" | "rejected" | "cancelled" = "pending") {
  return {
    change_request_id: requestId,
    task_id: taskId,
    requester_employee_no: "E-ASSIGNEE",
    patch_json: { deadline: "2026-08-30T09:00:00Z" },
    reason: "客户确认时间变化",
    before_snapshot: { deadline: "2026-08-25T08:00:00Z" },
    after_snapshot: { deadline: "2026-08-30T09:00:00Z" },
    status,
    decision_by_employee_no: null,
    decision_at: null,
    decision_comment: null,
    cancelled_by_employee_no: null,
    cancelled_at: null,
    cancellation_reason: null,
    requester_task_version: 4,
    base_task_version: 4,
    created_at: "2026-08-18T09:00:00Z",
  };
}

describe("ChangeRequestsPanel", () => {
  it("submits a non-empty JSON patch with the current task version", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ status: "pending" }, 201));
    vi.stubGlobal("fetch", fetchMock);
    renderPage(<ChangeRequestsPanel task={task} actions={actions("submit_change_request")} />);
    const user = userEvent.setup();

    fireEvent.change(screen.getByLabelText("变更内容（JSON）"), {
      target: { value: '{"deadline":"2026-08-30T09:00:00Z"}' },
    });
    await user.type(screen.getByLabelText("申请理由"), "客户确认时间变化");
    await user.click(screen.getByRole("button", { name: "提交变更申请" }));

    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/api/v1/tasks/${taskId}/change-requests`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          expected_task_version: 4,
          patch_json: { deadline: "2026-08-30T09:00:00Z" },
          reason: "客户确认时间变化",
        }),
      }),
    );
  });

  it("uses reason for rejection and requires a reason for cancellation", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ status: "rejected" }));
    vi.stubGlobal("fetch", fetchMock);
    const pendingTask = { ...task, change_requests: [request()] } as TaskDetail;
    renderPage(
      <ChangeRequestsPanel
        task={pendingTask}
        actions={actions("reject_change_request", "cancel_change_request")}
      />,
    );
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "驳回变更" }));
    await user.type(screen.getByLabelText("驳回原因"), "依赖尚未确认");
    await user.click(screen.getByRole("button", { name: "确认驳回" }));

    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/api/v1/tasks/${taskId}/change-requests/${requestId}/actions/reject`,
      expect.objectContaining({
        body: JSON.stringify({ expected_task_version: 4, reason: "依赖尚未确认" }),
      }),
    );
  });

  it("sends reason, rather than approval_comment, when cancelling a request", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ status: "cancelled" }));
    vi.stubGlobal("fetch", fetchMock);
    const pendingTask = { ...task, change_requests: [request()] } as TaskDetail;
    renderPage(<ChangeRequestsPanel task={pendingTask} actions={actions("cancel_change_request")} />);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "取消变更申请" }));
    await user.type(screen.getByLabelText("取消原因"), "不再需要调整");
    await user.click(screen.getByRole("button", { name: "确认取消" }));

    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/api/v1/tasks/${taskId}/change-requests/${requestId}/actions/cancel`,
      expect.objectContaining({
        body: JSON.stringify({ expected_task_version: 4, reason: "不再需要调整" }),
      }),
    );
  });
});
