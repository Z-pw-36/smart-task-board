import { apiRequest } from "./client";
import type { AllowedAction, TaskActionResult } from "./types";

export type TaskLifecycleAction = Exclude<
  AllowedAction,
  | "start_node"
  | "update_node_progress"
  | "complete_node"
  | "plan_task"
  | "submit_completion"
  | "approve_completion"
  | "reject_completion"
  | "reopen_node"
  | "submit_progress_report"
  | "report_task_issue"
  | "start_processing_issue"
  | "resolve_issue"
  | "reject_issue"
  | "close_issue"
  | "submit_change_request"
  | "approve_change_request"
  | "reject_change_request"
  | "cancel_change_request"
>;

const actionPaths: Record<TaskLifecycleAction, string> = {
  submit_for_confirmation: "submit-for-confirmation",
  confirm_and_send: "confirm-and-send",
  confirm_self_assigned: "confirm-self-assigned",
  accept: "accept",
  return: "return",
  resend: "resend",
  cancel_task: "cancel",
  withdraw_task: "withdraw",
  close_task: "close",
  archive_task: "archive",
  restore_task: "restore",
  merge_task: "merge",
};

export const actionLabels: Record<AllowedAction, string> = {
  submit_change_request: "提交变更申请",
  approve_change_request: "批准变更",
  reject_change_request: "驳回变更",
  cancel_change_request: "取消变更申请",
  cancel_task: "取消任务",
  withdraw_task: "撤回任务",
  merge_task: "合并任务",
  close_task: "关闭任务",
  archive_task: "归档任务",
  restore_task: "恢复任务",
  submit_for_confirmation: "提交确认",
  confirm_and_send: "确认并发送",
  confirm_self_assigned: "确认并开始",
  accept: "接受任务",
  return: "退回任务",
  resend: "重新发送",
  plan_task: "任务规划",
  start_node: "开始节点",
  update_node_progress: "更新进度",
  complete_node: "完成节点",
  submit_completion: "提交验收",
  approve_completion: "通过验收",
  reject_completion: "驳回验收",
  reopen_node: "重开节点",
  submit_progress_report: "提交进度汇报",
  report_task_issue: "上报卡点",
  start_processing_issue: "开始处理",
  resolve_issue: "标记已解决",
  reject_issue: "驳回问题",
  close_issue: "确认关闭",
};

const issueActionPaths: Partial<Record<AllowedAction, string>> = {
  start_processing_issue: "start-processing",
  resolve_issue: "resolve",
  reject_issue: "reject",
  close_issue: "close",
};

const changeRequestActionPaths: Partial<Record<AllowedAction, string>> = {
  approve_change_request: "approve",
  reject_change_request: "reject",
  cancel_change_request: "cancel",
};

export async function runTaskAction(
  taskId: string,
  action: TaskLifecycleAction,
  version: number,
  reason?: string,
): Promise<TaskActionResult> {
  return apiRequest<TaskActionResult>(`/api/v1/tasks/${taskId}/actions/${actionPaths[action]}`, {
    method: "POST",
    body: JSON.stringify({
      expected_task_version: version,
      ...(["return", "cancel_task", "withdraw_task", "close_task", "restore_task"].includes(action)
        ? { reason }
        : {}),
    }),
  });
}

export async function submitChangeRequest(
  taskId: string,
  version: number,
  patch: Record<string, unknown>,
  reason: string,
): Promise<void> {
  await apiRequest(`/api/v1/tasks/${taskId}/change-requests`, {
    method: "POST",
    body: JSON.stringify({ expected_task_version: version, patch_json: patch, reason }),
  });
}

export async function decideChangeRequest(
  taskId: string,
  requestId: string,
  version: number,
  action: "approve" | "reject" | "cancel",
  comment = "",
): Promise<void> {
  const body =
    action === "cancel"
      ? { expected_task_version: version, reason: comment }
      : action === "reject"
        ? { expected_task_version: version, reason: comment }
        : { expected_task_version: version, approval_comment: comment || null };
  await apiRequest(`/api/v1/tasks/${taskId}/change-requests/${requestId}/actions/${action}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function mergeTask(
  taskId: string,
  targetTaskId: string,
  version: number,
  reason: string,
): Promise<void> {
  await apiRequest(`/api/v1/tasks/${taskId}/actions/merge`, {
    method: "POST",
    body: JSON.stringify({
      expected_task_version: version,
      target_task_id: targetTaskId,
      reason,
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

export async function submitCompletion(
  taskId: string,
  version: number,
  completionNote: string,
  deliverableSummary: string,
): Promise<void> {
  await apiRequest(`/api/v1/tasks/${taskId}/actions/submit-completion`, {
    method: "POST",
    body: JSON.stringify({
      expected_task_version: version,
      completion_note: completionNote,
      deliverable_summary: deliverableSummary,
    }),
  });
}

export async function approveCompletion(
  taskId: string,
  version: number,
  completionReviewId: string,
): Promise<void> {
  await apiRequest(`/api/v1/tasks/${taskId}/actions/approve-completion`, {
    method: "POST",
    body: JSON.stringify({
      expected_task_version: version,
      completion_review_id: completionReviewId,
    }),
  });
}

export async function rejectCompletion(
  taskId: string,
  version: number,
  completionReviewId: string,
  rejectReason: string,
  reworkNodeId: string | null,
): Promise<void> {
  await apiRequest(`/api/v1/tasks/${taskId}/actions/reject-completion`, {
    method: "POST",
    body: JSON.stringify({
      expected_task_version: version,
      completion_review_id: completionReviewId,
      reject_reason: rejectReason,
      rework_node_id: reworkNodeId,
    }),
  });
}

export async function reopenNode(
  taskId: string,
  nodeId: string,
  version: number,
  completionReviewId: string,
): Promise<void> {
  await apiRequest(`/api/v1/tasks/${taskId}/nodes/${nodeId}/actions/reopen`, {
    method: "POST",
    body: JSON.stringify({
      expected_task_version: version,
      completion_review_id: completionReviewId,
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
  const actionPath = issueActionPaths[action] || changeRequestActionPaths[action];
  const target = actionPath && !endpoint.endsWith(`/${actionPath}`) ? `${endpoint}/${actionPath}` : endpoint;
  const body =
    action === "cancel_change_request"
      ? { expected_task_version: version, reason }
      : action === "reject_change_request"
        ? { expected_task_version: version, reason }
        : action === "approve_change_request"
        ? { expected_task_version: version, approval_comment: reason || null }
        : ["return", "cancel_task", "withdraw_task", "close_task", "restore_task"].includes(action)
          ? { expected_task_version: version, reason }
        : {
            expected_task_version: version,
            ...(issueActionPaths[action] && action !== "start_processing_issue" ? { reason } : {}),
            ...(action === "update_node_progress" ? { progress_percent: progressPercent } : {}),
          };
  await apiRequest(target, {
    method: action === "update_node_progress" ? "PATCH" : "POST",
    body: JSON.stringify(body),
  });
}
