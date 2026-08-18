import { apiRequest } from "./client";
import type { AllowedAction } from "./types";

const actionPaths: Record<Exclude<AllowedAction, "start_node" | "update_node_progress" | "complete_node">, string> = {
  submit_for_confirmation: "submit-for-confirmation",
  confirm_and_send: "confirm-and-send",
  confirm_self_assigned: "confirm-self-assigned",
  accept: "accept",
  return: "return",
  resend: "resend",
  submit_completion: "submit-completion",
  approve_completion: "approve-completion",
};

export const actionLabels: Record<AllowedAction, string> = {
  submit_for_confirmation: "提交确认",
  confirm_and_send: "确认并发送",
  confirm_self_assigned: "确认并开始",
  accept: "接受任务",
  return: "退回任务",
  resend: "重新发送",
  start_node: "开始节点",
  update_node_progress: "更新进度",
  complete_node: "完成节点",
  submit_completion: "提交验收",
  approve_completion: "通过验收",
};

export async function runTaskAction(
  taskId: string,
  action: Exclude<AllowedAction, "start_node" | "update_node_progress" | "complete_node">,
  version: number,
  reason?: string,
): Promise<void> {
  await apiRequest(`/api/v1/tasks/${taskId}/actions/${actionPaths[action]}`, {
    method: "POST",
    body: JSON.stringify({
      expected_task_version: version,
      ...(action === "return" ? { reason } : {}),
    }),
  });
}

export async function runNodeAction(
  taskId: string,
  nodeId: string,
  action: "start_node" | "update_node_progress" | "complete_node",
  version: number,
  progressPercent?: number,
): Promise<void> {
  const suffix = action === "start_node" ? "actions/start" : action === "complete_node" ? "actions/complete" : "progress";
  await apiRequest(`/api/v1/tasks/${taskId}/nodes/${nodeId}/${suffix}`, {
    method: action === "update_node_progress" ? "PATCH" : "POST",
    body: JSON.stringify({
      expected_task_version: version,
      ...(action === "update_node_progress" ? { progress_percent: progressPercent } : {}),
    }),
  });
}

export async function runInboxAction(
  endpoint: string,
  action: AllowedAction,
  version: number,
  reason?: string,
  progressPercent?: number,
): Promise<void> {
  await apiRequest(endpoint, {
    method: action === "update_node_progress" ? "PATCH" : "POST",
    body: JSON.stringify({
      expected_task_version: version,
      ...(action === "return" ? { reason } : {}),
      ...(action === "update_node_progress" ? { progress_percent: progressPercent } : {}),
    }),
  });
}
