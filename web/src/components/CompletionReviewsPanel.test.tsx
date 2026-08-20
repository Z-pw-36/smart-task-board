import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type {
  AvailableActions,
  TaskCompletionReview,
  TaskDetail,
} from "../api/types";
import { jsonResponse, renderPage } from "../test/test-utils";
import { CompletionReviewsPanel } from "./CompletionReviewsPanel";

const taskId = "22222222-2222-4222-8222-222222222222";
const nodeId = "33333333-3333-4333-8333-333333333333";
const reviewId = "44444444-4444-4444-8444-444444444444";

const task: TaskDetail = {
  task_id: taskId,
  task_no: "TASK-001",
  task_name: "完成验收任务",
  task_description: null,
  task_goal: "交付并验收",
  task_source: null,
  creator_employee_no: "E-CREATOR",
  main_assignee_employee_no: "E-ASSIGNEE",
  report_to_employee_no: null,
  report_to_level: null,
  reviewer_employee_no: "E-REVIEWER",
  department_id: null,
  status: "in_progress",
  start_time: null,
  deadline: null,
  estimated_hours: null,
  actual_hours: null,
  task_weight: null,
  deliverable: "验收报告",
  acceptance_criteria: "报告完整",
  is_urgent: false,
  report_cycle: null,
  task_version: 8,
  created_at: "2026-08-18T08:00:00Z",
  updated_at: "2026-08-20T08:00:00Z",
  participants: [],
  nodes: [
    {
      node_id: nodeId,
      task_id: taskId,
      node_order: 1,
      sort_weight: 0,
      node_name: "完成报告",
      action_detail: null,
      owner_employee_no: "E-ASSIGNEE",
      planned_deadline: null,
      estimated_hours: null,
      actual_hours: null,
      deliverable: "报告",
      acceptance_criteria: "内容齐全",
      progress_percent: 100,
      status: "completed",
      completed_at: "2026-08-20T07:00:00Z",
      tools_or_materials: null,
      planned_start_time: null,
    },
  ],
  dependencies: [],
  node_participants: [],
};

const submittedReview: TaskCompletionReview = {
  completion_review_id: reviewId,
  task_id: taskId,
  review_round: 2,
  submitted_by_employee_no: "E-ASSIGNEE",
  completion_note: "第二轮修订已完成",
  deliverable_summary: "报告与附件",
  reviewer_employee_no: "E-REVIEWER",
  review_status: "submitted",
  review_result: null,
  reject_reason: null,
  rework_node_id: null,
  submitted_task_version: 8,
  reviewed_task_version: null,
  submitted_at: "2026-08-20T08:00:00Z",
  reviewed_at: null,
  is_legacy_import: false,
};

function availableActions(
  taskActions: AvailableActions["allowed_actions"],
  nodeActions: AvailableActions["nodes"][number]["allowed_actions"] = [],
): AvailableActions {
  return {
    task_id: taskId,
    task_version: 8,
    allowed_actions: taskActions,
    nodes: [{ node_id: nodeId, allowed_actions: nodeActions }],
  };
}

function reviewPage(items: TaskCompletionReview[]) {
  return { items, limit: 20, offset: 0, total: items.length };
}

describe("CompletionReviewsPanel", () => {
  it("submits required completion content with the server task version", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === "POST") return Promise.resolve(jsonResponse({}));
      if (url.includes("completion-reviews")) return Promise.resolve(jsonResponse(reviewPage([])));
      return Promise.resolve(jsonResponse({}));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage(
      <CompletionReviewsPanel task={task} actions={availableActions(["submit_completion"])} />,
    );
    const user = userEvent.setup();

    expect(await screen.findByText("暂无验收记录")).toBeInTheDocument();
    await user.type(screen.getByLabelText("完成说明"), "功能与测试已经完成");
    await user.type(screen.getByLabelText("交付物摘要"), "报告、源码与验收结果");
    await user.click(screen.getByRole("button", { name: "提交完成申请" }));

    expect(await screen.findByText("完成申请已提交，新的验收轮次已创建。")).toBeInTheDocument();
    const post = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/actions/submit-completion") && init?.method === "POST",
    );
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({
      expected_task_version: 8,
      completion_note: "功能与测试已经完成",
      deliverable_summary: "报告、源码与验收结果",
    });
  });

  it("approves the current immutable review round", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === "POST") return Promise.resolve(jsonResponse({}));
      return Promise.resolve(jsonResponse(reviewPage([submittedReview])));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage(
      <CompletionReviewsPanel task={{ ...task, status: "pending_review" }} actions={availableActions(["approve_completion"])} />,
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "通过本轮验收" }));

    const post = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/actions/approve-completion") && init?.method === "POST",
    );
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({
      expected_task_version: 8,
      completion_review_id: reviewId,
    });
  });

  it("rejects for whole-deliverable rework without reopening a node", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === "POST") return Promise.resolve(jsonResponse({}));
      return Promise.resolve(jsonResponse(reviewPage([submittedReview])));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage(
      <CompletionReviewsPanel task={{ ...task, status: "pending_review" }} actions={availableActions(["reject_completion"])} />,
    );
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("驳回原因"), "交付物摘要需要补充附件说明");
    await user.click(screen.getByRole("button", { name: "驳回本轮验收" }));

    const post = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/actions/reject-completion") && init?.method === "POST",
    );
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({
      expected_task_version: 8,
      completion_review_id: reviewId,
      reject_reason: "交付物摘要需要补充附件说明",
      rework_node_id: null,
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/actions/reopen"))).toBe(false);
  });

  it("records one selected completed node without automatically reopening it", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === "POST") return Promise.resolve(jsonResponse({}));
      return Promise.resolve(jsonResponse(reviewPage([submittedReview])));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage(
      <CompletionReviewsPanel task={{ ...task, status: "pending_review" }} actions={availableActions(["reject_completion"])} />,
    );
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("驳回原因"), "报告节点需要重新核对");
    await user.click(screen.getByLabelText("指定一个已完成节点返工"));
    await user.selectOptions(screen.getByLabelText("返工节点"), nodeId);
    await user.click(screen.getByRole("button", { name: "驳回本轮验收" }));

    const post = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/actions/reject-completion") && init?.method === "POST",
    );
    expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({ rework_node_id: nodeId });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/actions/reopen"))).toBe(false);
  });

  it("renders immutable legacy history and explicitly reopens only a server-authorized node", async () => {
    const rejectedReview: TaskCompletionReview = {
      ...submittedReview,
      review_status: "rejected",
      review_result: "rejected",
      reject_reason: "重新核对数据",
      rework_node_id: nodeId,
      reviewed_task_version: 9,
      reviewed_at: "2026-08-20T09:00:00Z",
    };
    const legacyReview: TaskCompletionReview = {
      ...submittedReview,
      completion_review_id: "55555555-5555-4555-8555-555555555555",
      review_round: 1,
      completion_note: null,
      deliverable_summary: null,
      review_status: "approved",
      review_result: "approved",
      reviewed_task_version: 4,
      reviewed_at: "2026-08-19T09:00:00Z",
      is_legacy_import: true,
    };
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === "POST") return Promise.resolve(jsonResponse({}));
      return Promise.resolve(jsonResponse(reviewPage([legacyReview, rejectedReview])));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage(
      <CompletionReviewsPanel task={task} actions={availableActions([], ["reopen_node"])} />,
    );
    const user = userEvent.setup();

    expect((await screen.findAllByText("历史迁移记录未包含此项")).length).toBe(2);
    expect(
      screen.getByText((_content, element) => element?.textContent === "指定返工节点：完成报告"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /删除|编辑/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "重开节点：完成报告" }));

    const post = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith(`/nodes/${nodeId}/actions/reopen`) && init?.method === "POST",
    );
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({
      expected_task_version: 8,
      completion_review_id: reviewId,
    });
  });

  it("shows loading, query failure retry, and then the empty state", async () => {
    let resolveFirst!: (response: Response) => void;
    const firstResponse = new Promise<Response>((resolve) => { resolveFirst = resolve; });
    const fetchMock = vi.fn()
      .mockReturnValueOnce(firstResponse)
      .mockResolvedValue(jsonResponse(reviewPage([])));
    vi.stubGlobal("fetch", fetchMock);
    renderPage(<CompletionReviewsPanel task={task} actions={availableActions([])} />);

    expect(screen.getByRole("status")).toHaveTextContent("正在加载验收记录");
    resolveFirst(jsonResponse({ error: { code: "temporary", message: "失败", details: {} } }, 503));
    expect(await screen.findByRole("alert")).toHaveTextContent("服务暂时不可用");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "重试" }));
    expect(await screen.findByText("暂无验收记录")).toBeInTheDocument();
  });

  it("keeps completion input after a 409 and offers an explicit data refresh", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        return Promise.resolve(jsonResponse({ error: { code: "task_version_conflict", message: "conflict", details: {} } }, 409));
      }
      return Promise.resolve(jsonResponse(reviewPage([])));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage(
      <CompletionReviewsPanel task={task} actions={availableActions(["submit_completion"])} />,
    );
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("完成说明"), "不要清空这段说明");
    await user.type(screen.getByLabelText("交付物摘要"), "不要清空这段摘要");
    await user.click(screen.getByRole("button", { name: "提交完成申请" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("你的输入已保留");
    expect(screen.getByLabelText("完成说明")).toHaveValue("不要清空这段说明");
    expect(screen.getByLabelText("交付物摘要")).toHaveValue("不要清空这段摘要");
    await user.click(screen.getByRole("button", { name: "刷新当前数据" }));
    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(2));
  });
});
