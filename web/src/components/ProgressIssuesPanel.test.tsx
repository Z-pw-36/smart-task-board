import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { AvailableActions, TaskDetail } from "../api/types";
import { jsonResponse, renderPage } from "../test/test-utils";
import { ProgressIssuesPanel } from "./ProgressIssuesPanel";

const taskId = "22222222-2222-4222-8222-222222222222";
const nodeId = "33333333-3333-4333-8333-333333333333";

const task: TaskDetail = {
  task_id: taskId,
  task_no: "TASK-001",
  task_name: "进度任务",
  task_description: null,
  task_goal: null,
  task_source: null,
  creator_employee_no: "E-CREATOR",
  main_assignee_employee_no: "E-CREATOR",
  report_to_employee_no: null,
  report_to_level: null,
  reviewer_employee_no: null,
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
  report_cycle: "weekly:WED@09:00",
  task_version: 5,
  created_at: "2026-08-18T08:00:00Z",
  updated_at: "2026-08-18T08:00:00Z",
  participants: [],
  nodes: [
    {
      node_id: nodeId,
      task_id: taskId,
      node_order: 1,
      sort_weight: 0,
      node_name: "节点一",
      action_detail: null,
      owner_employee_no: "E-CREATOR",
      planned_deadline: null,
      estimated_hours: null,
      actual_hours: null,
      deliverable: null,
      acceptance_criteria: null,
      progress_percent: 20,
      status: "in_progress",
      completed_at: null,
      tools_or_materials: null,
      planned_start_time: null,
    },
  ],
  dependencies: [],
  node_participants: [],
  change_requests: [],
};

const actions: AvailableActions = {
  task_id: taskId,
  task_version: 5,
  allowed_actions: ["submit_progress_report", "report_task_issue"],
  nodes: [
    {
      node_id: nodeId,
      allowed_actions: ["submit_progress_report", "report_task_issue"],
    },
  ],
};

describe("ProgressIssuesPanel", () => {
  it("submits a server-versioned task progress report", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === "POST" && url.includes("progress-reports")) {
        return Promise.resolve(
          jsonResponse({
            progress_report_id: "44444444-4444-4444-8444-444444444444",
            task_id: taskId,
            node_id: null,
            reporter_employee_no: "E-CREATOR",
            progress_percent: 35,
            report_content: "完成接口联调",
            stage_result: null,
            difficulty: null,
            resource_request: null,
            actual_hours: null,
            corrects_report_id: null,
            report_period_start: null,
            report_period_end: null,
            task_version: 6,
            operation_source: "rest_api",
            created_at: "2026-08-19T02:00:00Z",
          }),
        );
      }
      return Promise.resolve(jsonResponse({ items: [], limit: 100, offset: 0, total: 0 }));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage(<ProgressIssuesPanel task={task} actions={actions} />);
    const user = userEvent.setup();

    await user.clear(screen.getByLabelText("进度百分比"));
    await user.type(screen.getByLabelText("进度百分比"), "35");
    await user.type(screen.getByLabelText("汇报内容"), "完成接口联调");
    await user.click(screen.getByRole("button", { name: "提交汇报" }));

    expect(await screen.findByText("进度汇报已提交。")).toBeInTheDocument();
    const post = fetchMock.mock.calls.find(
      ([url, init]) => String(url).includes("progress-reports") && init?.method === "POST",
    );
    expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({
      expected_task_version: 5,
      node_id: null,
      progress_percent: 35,
      report_content: "完成接口联调",
    });
  });

  it("defaults node-only collaborators to their reportable node", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === "POST" && url.includes("progress-reports")) {
        return Promise.resolve(jsonResponse({}));
      }
      return Promise.resolve(jsonResponse({ items: [], limit: 100, offset: 0, total: 0 }));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage(
      <ProgressIssuesPanel
        task={task}
        actions={{ ...actions, allowed_actions: [] }}
      />,
    );
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("汇报内容"), "节点协作进展");
    await user.click(screen.getByRole("button", { name: "提交汇报" }));

    await waitFor(() => {
      const post = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).includes("progress-reports") && init?.method === "POST",
      );
      expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({ node_id: nodeId });
    });
  });

  it("renders and invokes only issue actions authorized by the server", async () => {
    const issue = {
      issue_id: "55555555-5555-4555-8555-555555555555",
      task_id: taskId,
      node_id: null,
      source_progress_report_id: null,
      reported_by_employee_no: "E-CREATOR",
      issue_type: "blocker",
      title: "等待权限",
      description: "需要开通账号",
      requested_resource: null,
      severity: "high",
      status: "open",
      owner_employee_no: "E-CREATOR",
      resolution_note: null,
      created_at: "2026-08-19T02:00:00Z",
      allowed_actions: ["start_processing"],
    };
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === "POST" && url.includes("start-processing")) {
        return Promise.resolve(jsonResponse({ ...issue, status: "processing", allowed_actions: [] }));
      }
      if (url.includes("/issues")) {
        return Promise.resolve(jsonResponse({ items: [issue], limit: 100, offset: 0, total: 1 }));
      }
      return Promise.resolve(jsonResponse({ items: [], limit: 100, offset: 0, total: 0 }));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage(<ProgressIssuesPanel task={task} actions={actions} />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "开始处理" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) => String(url).includes("start-processing") && init?.method === "POST",
        ),
      ).toBe(true);
    });
    expect(screen.queryByRole("button", { name: "标记已解决" })).not.toBeInTheDocument();
  });
});
