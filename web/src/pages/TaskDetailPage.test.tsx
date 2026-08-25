import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Route, Routes } from "react-router-dom";

import { jsonResponse, renderPage } from "../test/test-utils";
import { TaskDetailPage } from "./TaskDetailPage";

const taskId = "22222222-2222-4222-8222-222222222222";
const nodeId = "33333333-3333-4333-8333-333333333333";

const emptyPage = { items: [], limit: 50, offset: 0, total: 0 };
const users = [
  {
    employee_no: "E-ASSIGNEE",
    name: "测试承办人",
    department_id: null,
    department_name: null,
    role_type: "employee",
  },
  {
    employee_no: "E-COLLAB",
    name: "协作成员",
    department_id: null,
    department_name: null,
    role_type: "employee",
  },
];

function detail(overrides: Record<string, unknown> = {}) {
  return {
    task_id: taskId,
    task_no: "TASK-001",
    task_name: "只读参与任务",
    task_description: null,
    task_goal: "验证权限",
    task_source: null,
    creator_employee_no: "E-CREATOR",
    main_assignee_employee_no: "E-ASSIGNEE",
    report_to_employee_no: null,
    report_to_level: null,
    reviewer_employee_no: "E-REVIEWER",
    department_id: null,
    status: "in_progress",
    start_time: null,
    deadline: "2026-08-30T18:00:00Z",
    estimated_hours: "4",
    actual_hours: null,
    task_weight: 3,
    deliverable: "报告",
    acceptance_criteria: "完成",
    is_urgent: false,
    report_cycle: null,
    task_version: 4,
    created_at: "2026-08-18T08:00:00Z",
    updated_at: "2026-08-18T09:00:00Z",
    participants: [],
    nodes: [
      {
        node_id: nodeId,
        task_id: taskId,
        node_order: 1,
        sort_weight: 0,
        node_name: "只读节点",
        action_detail: null,
        tools_or_materials: null,
        owner_employee_no: "E-ASSIGNEE",
        planned_start_time: null,
        planned_deadline: null,
        estimated_hours: "2",
        actual_hours: null,
        deliverable: null,
        acceptance_criteria: "节点完成",
        progress_percent: 20,
        status: "in_progress",
        completed_at: null,
      },
    ],
    dependencies: [],
    node_participants: [
      {
        node_participant_id: "44444444-4444-4444-8444-444444444444",
        task_id: taskId,
        node_id: nodeId,
        employee_no: "E-CREATOR",
        participant_role: "collaborator",
      },
    ],
    change_requests: [],
    ai_extraction_records: [],
    ...overrides,
  };
}

function pageResponse(path: string) {
  if (path.includes("progress-reports")) return emptyPage;
  if (path.includes("issues")) return emptyPage;
  if (path.includes("completion-reviews")) return { ...emptyPage, limit: 20 };
  if (path.includes("change-requests")) return { ...emptyPage, limit: 20 };
  if (path.includes("status-logs")) return emptyPage;
  return null;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("TaskDetailPage", () => {
  it("shows details but no node write buttons for a read-only NodeParticipant", async () => {
    const taskDetail = detail();
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      const path = String(url);
      const page = pageResponse(path);
      if (page) return Promise.resolve(jsonResponse(page));
      if (path.includes("available-actions")) {
        return Promise.resolve(
          jsonResponse({
            task_id: taskId,
            task_version: 4,
            allowed_actions: [],
            nodes: [{ node_id: nodeId, allowed_actions: [] }],
          }),
        );
      }
      if (path.includes("prototype-users")) return Promise.resolve(jsonResponse(users));
      return Promise.resolve(jsonResponse(taskDetail));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage(
      <Routes><Route path="/tasks/:taskId" element={<TaskDetailPage />} /></Routes>,
      { route: `/tasks/${taskId}` },
    );

    expect(await screen.findByRole("heading", { name: "只读参与任务" })).toBeInTheDocument();
    expect(screen.getByText(/E-CREATOR \(collaborator\)/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "更新进度" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "完成节点" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "重新生成建议" })).not.toBeInTheDocument();
  });

  it("shows an actionable error when available actions cannot be loaded", async () => {
    const taskDetail = detail({ task_name: "动作加载失败任务", nodes: [], node_participants: [] });
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      const path = String(url);
      const page = pageResponse(path);
      if (page) return Promise.resolve(jsonResponse(page));
      if (path.includes("available-actions")) {
        return Promise.resolve(
          jsonResponse({ error: { code: "temporary", message: "动作列表加载失败", details: {} } }, 503),
        );
      }
      if (path.includes("prototype-users")) return Promise.resolve(jsonResponse(users));
      return Promise.resolve(jsonResponse(taskDetail));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage(
      <Routes><Route path="/tasks/:taskId" element={<TaskDetailPage />} /></Routes>,
      { route: `/tasks/${taskId}` },
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("服务暂时不可用");
    expect(screen.getByRole("button", { name: "重试" })).toBeInTheDocument();
    expect(screen.queryByText("任务不存在")).not.toBeInTheDocument();
  });

  it("collects a required reason before posting a lifecycle cancellation", async () => {
    const taskDetail = detail({ task_name: "可取消任务", nodes: [], node_participants: [] });
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      const path = String(url);
      const page = pageResponse(path);
      if (page) return Promise.resolve(jsonResponse(page));
      if (path.includes("available-actions")) {
        return Promise.resolve(
          jsonResponse({
            task_id: taskId,
            task_version: 4,
            allowed_actions: ["cancel_task"],
            nodes: [],
          }),
        );
      }
      if (path.includes("actions/cancel")) return Promise.resolve(jsonResponse({ status: "cancelled" }));
      if (path.includes("prototype-users")) return Promise.resolve(jsonResponse(users));
      return Promise.resolve(jsonResponse(taskDetail));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage(
      <Routes><Route path="/tasks/:taskId" element={<TaskDetailPage />} /></Routes>,
      { route: `/tasks/${taskId}` },
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "取消任务" }));
    await user.type(screen.getByLabelText("操作原因"), "任务需求已撤销");
    await user.click(screen.getByRole("button", { name: "确认取消任务" }));

    const cancelCall = fetchMock.mock.calls.find(([url]) => String(url).includes("/actions/cancel"));
    expect(cancelCall?.[1]).toEqual(
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ expected_task_version: 4, reason: "任务需求已撤销" }),
      }),
    );
  });

  it("lets the main assignee generate and confirm a manually assigned task plan", async () => {
    const taskDetail = detail({
      task_name: "待规划任务",
      participants: [
        {
          participant_id: "55555555-5555-4555-8555-555555555555",
          employee_no: "E-COLLAB",
          participant_role: "collaborator",
        },
      ],
      nodes: [],
      node_participants: [],
    });
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      const path = String(url);
      const page = pageResponse(path);
      if (page) return Promise.resolve(jsonResponse(page));
      if (path.includes("planning/decompose")) {
        return Promise.resolve(
          jsonResponse({
            task_id: taskId,
            suggested_nodes: [
              {
                client_node_id: "draft-node-1",
                node_order: 1,
                node_name: "确认范围",
                action_detail: "确认任务边界",
                tools_or_materials: null,
                suggested_owner_employee_no: "E-COLLAB",
                planned_start_time: null,
                planned_deadline: "2026-08-25T10:00:00Z",
                estimated_hours: "1",
                deliverable: "范围说明",
                acceptance_criteria: "范围被确认",
                dependencies: [],
                enabled: true,
              },
              {
                client_node_id: "draft-node-2",
                node_order: 2,
                node_name: "交付结果",
                action_detail: "产出最终材料",
                tools_or_materials: null,
                suggested_owner_employee_no: "E-COLLAB",
                planned_start_time: null,
                planned_deadline: "2026-08-28T10:00:00Z",
                estimated_hours: "3",
                deliverable: "交付包",
                acceptance_criteria: "验收通过",
                dependencies: ["draft-node-1"],
                enabled: true,
              },
            ],
            suggested_dependencies: [
              {
                predecessor_client_node_id: "draft-node-1",
                successor_client_node_id: "draft-node-2",
                dependency_type: "finish_to_start",
                reason: null,
              },
            ],
          }),
        );
      }
      if (path.includes("planning/confirm")) {
        return Promise.resolve(
          jsonResponse({
            task_id: taskId,
            status: "in_progress",
            task_version: 5,
            updated_at: "2026-08-18T09:30:00Z",
          }),
        );
      }
      if (path.includes("available-actions")) {
        return Promise.resolve(
          jsonResponse({
            task_id: taskId,
            task_version: 4,
            allowed_actions: ["plan_task"],
            nodes: [],
          }),
        );
      }
      if (path.includes("prototype-users")) return Promise.resolve(jsonResponse(users));
      return Promise.resolve(jsonResponse(taskDetail));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage(
      <Routes><Route path="/tasks/:taskId" element={<TaskDetailPage />} /></Routes>,
      { route: `/tasks/${taskId}` },
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "重新生成建议" }));
    expect(await screen.findByText(/AI 已生成 2 个建议执行节点/)).toBeInTheDocument();
    expect(screen.getAllByText("AI 建议：E-COLLAB")).toHaveLength(2);

    const ownerSelects = screen.getAllByLabelText(/节点负责人/);
    expect(ownerSelects[0]).toHaveValue("");
    await user.selectOptions(ownerSelects[0], "E-ASSIGNEE");
    await user.selectOptions(ownerSelects[1], "E-COLLAB");
    await user.click(screen.getByRole("button", { name: "确认任务规划" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) => String(url).includes("planning/confirm")),
      ).toBe(true),
    );
    const confirmCall = fetchMock.mock.calls.find(([url]) =>
      String(url).includes("planning/confirm"),
    );
    const body = JSON.parse(String((confirmCall?.[1] as RequestInit).body));
    expect(body.nodes).toHaveLength(2);
    expect(body.nodes[0].owner_employee_no).toBe("E-ASSIGNEE");
    expect(body.nodes[1].owner_employee_no).toBe("E-COLLAB");
    expect(body.dependencies).toHaveLength(1);
    expect(body.dependencies[0].predecessor_node_id).toBe(body.nodes[0].node_id);
    expect(body.dependencies[0].successor_node_id).toBe(body.nodes[1].node_id);
  });

  it("blocks plan confirmation when a node deadline exceeds the task deadline", async () => {
    const taskDetail = detail({
      task_name: "截止时间校验任务",
      participants: [
        {
          participant_id: "55555555-5555-4555-8555-555555555555",
          employee_no: "E-COLLAB",
          participant_role: "collaborator",
        },
      ],
      nodes: [],
      node_participants: [],
    });
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      const path = String(url);
      const page = pageResponse(path);
      if (page) return Promise.resolve(jsonResponse(page));
      if (path.includes("planning/decompose")) {
        return Promise.resolve(
          jsonResponse({
            task_id: taskId,
            suggested_nodes: [
              {
                client_node_id: "draft-node-1",
                node_order: 1,
                node_name: "超期节点",
                action_detail: null,
                tools_or_materials: null,
                suggested_owner_employee_no: "E-COLLAB",
                planned_start_time: null,
                planned_deadline: "2026-09-01T10:00:00Z",
                estimated_hours: null,
                deliverable: "结果",
                acceptance_criteria: "通过",
                dependencies: [],
                enabled: true,
              },
            ],
            suggested_dependencies: [],
          }),
        );
      }
      if (path.includes("available-actions")) {
        return Promise.resolve(
          jsonResponse({
            task_id: taskId,
            task_version: 4,
            allowed_actions: ["plan_task"],
            nodes: [],
          }),
        );
      }
      if (path.includes("prototype-users")) return Promise.resolve(jsonResponse(users));
      return Promise.resolve(jsonResponse(taskDetail));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage(
      <Routes><Route path="/tasks/:taskId" element={<TaskDetailPage />} /></Routes>,
      { route: `/tasks/${taskId}` },
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "重新生成建议" }));
    await user.selectOptions(await screen.findByLabelText(/节点负责人/), "E-COLLAB");
    await user.click(screen.getByRole("button", { name: "确认任务规划" }));

    expect(await screen.findByText("节点截止时间不能晚于任务截止时间。")).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).includes("planning/confirm")),
    ).toBe(false);
  });
});
