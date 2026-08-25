import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { jsonResponse, renderPage } from "../test/test-utils";
import { NewTaskPage } from "./NewTaskPage";

const users = [
  {
    employee_no: "E-ASSIGNEE",
    name: "测试承办人",
    department_id: null,
    department_name: null,
    role_type: "employee",
  },
];

describe("NewTaskPage", () => {
  it("shows a three-step creator flow without node planning", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(users)));
    renderPage(<NewTaskPage />);

    const steps = await screen.findByRole("list", { name: "创建步骤" });
    expect(within(steps).getByText("描述任务")).toBeInTheDocument();
    expect(within(steps).getByText("信息确认")).toBeInTheDocument();
    expect(within(steps).getByText("确认发布")).toBeInTheDocument();
    expect(screen.queryByText("智能拆解")).not.toBeInTheDocument();
    expect(screen.queryByRole("group", { name: /节点/ })).not.toBeInTheDocument();
  });

  it("shows field-level errors for missing confirmed facts", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(users)));
    renderPage(<NewTaskPage />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "手动填写任务信息" }));
    await user.click(screen.getByRole("button", { name: "进入确认发布" }));

    expect(screen.getByText("请输入任务名称。")).toBeInTheDocument();
    expect(screen.getByText("请输入任务描述。")).toBeInTheDocument();
    expect(screen.getByText("请选择主承办人。")).toBeInTheDocument();
    expect(screen.getByText("请选择任务截止时间。")).toBeInTheDocument();
    expect(screen.getByText("任务发布前需要明确验收标准。")).toBeInTheDocument();
  });

  it("publishes a task without sending nodes or dependencies", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(users))
      .mockResolvedValueOnce(jsonResponse({
        task_id: "22222222-2222-4222-8222-222222222222",
        status: "draft",
        task_version: 1,
        updated_at: "2026-08-25T08:00:00Z",
      }, 201))
      .mockResolvedValueOnce(jsonResponse({
        task_id: "22222222-2222-4222-8222-222222222222",
        status: "pending_confirmation",
        task_version: 2,
        updated_at: "2026-08-25T08:00:00Z",
      }))
      .mockResolvedValueOnce(jsonResponse({
        task_id: "22222222-2222-4222-8222-222222222222",
        status: "pending_acceptance",
        task_version: 3,
        updated_at: "2026-08-25T08:00:00Z",
      }));
    vi.stubGlobal("fetch", fetchMock);
    renderPage(<NewTaskPage />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "手动填写任务信息" }));
    await user.type(screen.getByLabelText("任务名称 *"), "新任务");
    await user.type(screen.getByLabelText("任务描述 *"), "创建者只描述和确认任务。");
    await user.selectOptions(
      screen.getByLabelText("主承办人 *"),
      within(screen.getByLabelText("主承办人 *")).getByRole("option", {
        name: "测试承办人 · E-ASSIGNEE",
      }),
    );
    await user.type(screen.getByLabelText("截止时间 *"), "2026-08-30T18:00");
    await user.type(screen.getByLabelText("任务验收标准 *"), "任务整体验收通过");
    await user.click(screen.getByRole("button", { name: "进入确认发布" }));
    await user.click(screen.getByRole("button", { name: "确认发布" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
    const createRequest = fetchMock.mock.calls[1][1] as RequestInit;
    const createBody = JSON.parse(String(createRequest.body)) as Record<string, unknown>;
    expect(createBody.nodes).toBeUndefined();
    expect(createBody.dependencies).toBeUndefined();
    expect(createBody.task_name).toBe("新任务");
    expect(fetchMock.mock.calls[2][0]).toContain("/actions/submit-for-confirmation");
    expect(fetchMock.mock.calls[3][0]).toContain("/actions/confirm-and-send");
  });
});
