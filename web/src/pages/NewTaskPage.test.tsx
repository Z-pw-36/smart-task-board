import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { jsonResponse, renderPage } from "../test/test-utils";
import { NewTaskPage } from "./NewTaskPage";

const users = [{ employee_no: "E-ASSIGNEE", name: "测试承办人", department_id: null, department_name: null, role_type: "employee" }];

describe("NewTaskPage", () => {
  it("shows field-level errors for missing confirmed facts", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(users)));
    renderPage(<NewTaskPage />);
    await userEvent.setup().click(screen.getByRole("button", { name: "创建草稿" }));

    expect(screen.getByText("请输入任务名称。")).toBeInTheDocument();
    expect(screen.getByText("请选择主承办人。")).toBeInTheDocument();
    expect(screen.getByText("任务发送前需要明确验收标准。")).toBeInTheDocument();
  });

  it("generates node UUIDs and a dependency request", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(users))
      .mockResolvedValueOnce(jsonResponse({ task_id: "22222222-2222-4222-8222-222222222222" }, 201));
    vi.stubGlobal("fetch", fetchMock);
    renderPage(<NewTaskPage />);
    const user = userEvent.setup();

    const assigneeSelect = screen.getByLabelText("主承办人 *");
    const reviewerSelect = screen.getByLabelText("验收人");
    const firstNode = screen.getByRole("group", { name: "节点 1" });
    const firstOwnerSelect = within(firstNode).getByLabelText("负责人");
    const assigneeOption = await within(assigneeSelect).findByRole("option", {
      name: "测试承办人 · E-ASSIGNEE",
    });
    const reviewerOption = await within(reviewerSelect).findByRole("option", {
      name: "测试承办人",
    });
    const firstOwnerOption = await within(firstOwnerSelect).findByRole("option", {
      name: "测试承办人",
    });

    expect(assigneeOption).toBeInTheDocument();
    expect(reviewerOption).toBeInTheDocument();
    expect(firstOwnerOption).toBeInTheDocument();
    await user.type(screen.getByLabelText("任务名称 *"), "新任务");
    await user.selectOptions(assigneeSelect, assigneeOption);
    await user.type(screen.getByLabelText("任务验收标准 *"), "任务验收通过");
    await user.type(within(firstNode).getByLabelText("节点名称 *"), "节点一");
    await user.type(within(firstNode).getByLabelText("验收标准 *"), "节点一验收");
    await user.click(screen.getByRole("button", { name: "添加节点" }));
    const secondNode = screen.getByRole("group", { name: "节点 2" });
    await user.type(within(secondNode).getByLabelText("节点名称 *"), "节点二");
    await user.type(within(secondNode).getByLabelText("验收标准 *"), "节点二验收");
    const dependencySelect = within(secondNode).getByLabelText("依赖前置节点");
    const predecessorOption = within(dependencySelect).getByRole("option", {
      name: "节点一",
    });
    await user.selectOptions(dependencySelect, predecessorOption);
    await user.click(screen.getByRole("button", { name: "创建草稿" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const request = fetchMock.mock.calls[1][1] as RequestInit;
    const body = JSON.parse(String(request.body)) as { nodes: Array<{ node_id: string }>; dependencies: Array<{ predecessor_node_id: string; successor_node_id: string }> };
    expect(body.nodes).toHaveLength(2);
    expect(body.nodes.every((node) => /^[0-9a-f-]{36}$/.test(node.node_id))).toBe(true);
    expect(body.dependencies[0]).toMatchObject({ predecessor_node_id: body.nodes[0].node_id, successor_node_id: body.nodes[1].node_id });
  });
});
