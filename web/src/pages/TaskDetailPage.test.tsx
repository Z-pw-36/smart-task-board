import { Route, Routes } from "react-router-dom";
import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { jsonResponse, renderPage } from "../test/test-utils";
import { TaskDetailPage } from "./TaskDetailPage";

const taskId = "22222222-2222-4222-8222-222222222222";
const nodeId = "33333333-3333-4333-8333-333333333333";

describe("TaskDetailPage", () => {
  it("shows details but no node write buttons for a read-only NodeParticipant", async () => {
    const detail = { task_id: taskId, task_no: "TASK-001", task_name: "只读参与任务", task_description: null, task_goal: "验证权限", task_source: null, creator_employee_no: "E-CREATOR", main_assignee_employee_no: "E-ASSIGNEE", report_to_employee_no: null, report_to_level: null, reviewer_employee_no: "E-REVIEWER", department_id: null, status: "in_progress", start_time: null, deadline: null, estimated_hours: "4", actual_hours: null, task_weight: 3, deliverable: "报告", acceptance_criteria: "完成", is_urgent: false, report_cycle: null, task_version: 4, created_at: "2026-08-18T08:00:00Z", updated_at: "2026-08-18T09:00:00Z", participants: [], nodes: [{ node_id: nodeId, task_id: taskId, node_order: 1, sort_weight: 0, node_name: "只读节点", action_detail: null, tools_or_materials: null, owner_employee_no: "E-ASSIGNEE", planned_start_time: null, planned_deadline: null, estimated_hours: "2", actual_hours: null, deliverable: null, acceptance_criteria: "节点完成", progress_percent: 20, status: "in_progress", completed_at: null }], dependencies: [], node_participants: [{ node_participant_id: "44444444-4444-4444-8444-444444444444", node_id: nodeId, employee_no: "E-CREATOR", participant_role: "collaborator" }] };
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes("available-actions")) return Promise.resolve(jsonResponse({ task_id: taskId, task_version: 4, allowed_actions: [], nodes: [{ node_id: nodeId, allowed_actions: [] }] }));
      if (url.includes("status-logs")) return Promise.resolve(jsonResponse({ items: [], limit: 50, offset: 0, total: 0 }));
      return Promise.resolve(jsonResponse(detail));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage(<Routes><Route path="/tasks/:taskId" element={<TaskDetailPage />} /></Routes>, { route: `/tasks/${taskId}` });

    expect(await screen.findByRole("heading", { name: "只读参与任务" })).toBeInTheDocument();
    expect(screen.getByText(/E-CREATOR \(collaborator\)/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "更新进度" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "完成节点" })).not.toBeInTheDocument();
  });
});
