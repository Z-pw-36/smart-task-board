/**
 * Feature: V1.1 task detail display mapping.
 * Responsibilities: convert read-only task DTO values into labels, dates, tones, and section summaries.
 * Does not own: business status transitions, authorization, or persistence.
 * Plan task: DEV-05.
 */

import type { AllowedAction, TaskStatus } from "../../api/types";

export const detailModules = [
  { id: "overview", label: "概览", targetId: "detail-overview" },
  { id: "people", label: "人员", targetId: "detail-people" },
  { id: "nodes", label: "节点", targetId: "detail-nodes" },
  { id: "progress", label: "进度/汇报", targetId: "detail-progress" },
  { id: "performance", label: "绩效", targetId: "detail-performance" },
] as const;

export type DetailModuleId = typeof detailModules[number]["id"];

export const statusLabels: Record<string, string> = {
  draft: "草稿",
  pending_confirmation: "待确认",
  pending_acceptance: "待接受",
  pending_confirm: "待确认",
  pending_accept: "待接受",
  returned: "已退回",
  decomposing: "AI拆解中",
  decomposition_failed: "拆解失败",
  in_progress: "进行中",
  blocked: "受阻",
  pending_report: "待汇报",
  pending_review: "待验收",
  completed: "已完成",
  archived: "已归档",
  cancelled: "已取消",
  withdrawn: "已撤回",
  merged: "已合并",
  closed: "已关闭",
};

export const nodeStatusLabels: Record<string, string> = {
  pending: "未开始",
  in_progress: "进行中",
  blocked: "受阻",
  completed: "已完成",
  cancelled: "已取消",
};

export const actionLabels: Record<AllowedAction, string> = {
  submit_for_confirmation: "提交确认",
  confirm_and_send: "确认发送",
  confirm_self_assigned: "确认发送",
  accept: "接受任务",
  return: "退回任务",
  resend: "重新发送",
  plan_task: "任务规划",
  start_node: "开始节点",
  update_node_progress: "更新节点",
  complete_node: "完成节点",
  submit_completion: "提交完成",
  approve_completion: "验收通过",
  reject_completion: "验收退回",
  reopen_node: "重开节点",
  submit_change_request: "申请变更",
  approve_change_request: "同意变更",
  reject_change_request: "拒绝变更",
  cancel_change_request: "取消变更",
  cancel_task: "取消任务",
  withdraw_task: "撤回任务",
  merge_task: "合并任务",
  close_task: "关闭任务",
  archive_task: "归档任务",
  restore_task: "恢复任务",
  submit_progress_report: "汇报进度",
  report_task_issue: "上报卡点",
  start_processing_issue: "开始处理",
  resolve_issue: "解决问题",
  reject_issue: "驳回问题",
  close_issue: "关闭问题",
};

export function statusLabel(status: string): string {
  return statusLabels[status] ?? status;
}

export function statusTone(status: TaskStatus | string): "info" | "success" | "warning" | "danger" | "neutral" {
  if (["completed", "archived"].includes(status)) return "success";
  if (["blocked", "decomposition_failed", "cancelled", "withdrawn", "closed"].includes(status)) return "danger";
  if (["pending_acceptance", "pending_accept", "pending_report", "pending_review", "decomposing"].includes(status)) return "warning";
  if (status === "in_progress") return "info";
  return "neutral";
}

export function formatDateTime(value?: string | null): string {
  if (!value) return "未设置";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "未设置";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function displayValue(value?: string | number | null): string {
  if (value === null || value === undefined || value === "") return "未设置";
  return String(value);
}
