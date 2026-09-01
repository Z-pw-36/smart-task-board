/**
 * Feature: V1.1 workbench query projection.
 * Responsibilities: load current-user dashboard summary and task list data for the Workbench page.
 * Does not own: task status transitions, priority calculation, or authorization decisions.
 * Plan task: DEV-03.
 */

import { getDashboardSummary, listTasks } from "../../api/endpoints";
import type { DashboardSummary, PaginatedTasks, TaskStatus, TaskSummary } from "../../api/types";

export const workbenchStatusFilters = [
  "pending_acceptance",
  "in_progress",
  "pending_review",
] as const satisfies readonly TaskStatus[];

export type WorkbenchStatusFilter = (typeof workbenchStatusFilters)[number];
export type WorkbenchQuadrant = "important_urgent" | "important_not_urgent" | "urgent_not_important" | "routine";
export type WorkbenchSupportFilter = "open";

export interface WorkbenchFilters {
  status?: WorkbenchStatusFilter;
  quadrant?: WorkbenchQuadrant;
  support?: WorkbenchSupportFilter;
}

export interface WorkbenchQuadrantSummary {
  id: WorkbenchQuadrant;
  label: string;
  count: number;
}

export interface WorkbenchData {
  summary: DashboardSummary;
  tasks: TaskSummary[];
  quadrants: WorkbenchQuadrantSummary[];
}

const statusSet = new Set<string>([
  "draft",
  "pending_confirmation",
  "pending_acceptance",
  "returned",
  "in_progress",
  "pending_review",
  "completed",
  "archived",
  "cancelled",
  "withdrawn",
  "merged",
  "closed",
]);

const quadrantLabels: Record<WorkbenchQuadrant, string> = {
  important_urgent: "重要且紧急",
  important_not_urgent: "重要不紧急",
  urgent_not_important: "紧急不重要",
  routine: "常规任务",
};

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? value as Record<string, unknown> : {};
}

function safeNumber(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : 0;
}

function safeString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function normalizeTaskStatus(value: unknown): TaskStatus {
  return typeof value === "string" && statusSet.has(value) ? value as TaskStatus : "in_progress";
}

function normalizePerson(value: unknown): { employee_no: string; name: string } {
  const record = asRecord(value);
  return {
    employee_no: safeString(record.employee_no) ?? "",
    name: safeString(record.name) ?? "未命名成员",
  };
}

function normalizeTask(value: unknown): TaskSummary | null {
  const record = asRecord(value);
  const taskId = safeString(record.task_id);
  const taskName = safeString(record.task_name);
  if (!taskId || !taskName) return null;

  return {
    task_id: taskId,
    task_no: safeString(record.task_no),
    task_name: taskName,
    status: normalizeTaskStatus(record.status),
    deadline: safeString(record.deadline),
    is_urgent: Boolean(record.is_urgent),
    task_weight: typeof record.task_weight === "number" ? record.task_weight : null,
    task_version: safeNumber(record.task_version),
    creator: normalizePerson(record.creator),
    main_assignee: record.main_assignee ? normalizePerson(record.main_assignee) : null,
    current_user_relations: Array.isArray(record.current_user_relations)
      ? record.current_user_relations.filter((item): item is string => typeof item === "string")
      : [],
    allowed_actions: Array.isArray(record.allowed_actions)
      ? record.allowed_actions.filter((item): item is TaskSummary["allowed_actions"][number] => typeof item === "string")
      : [],
    is_overdue: Boolean(record.is_overdue),
    days_until_deadline: typeof record.days_until_deadline === "number" ? record.days_until_deadline : null,
    created_at: safeString(record.created_at) ?? "",
    updated_at: safeString(record.updated_at) ?? "",
  };
}

function normalizeTasks(payload: PaginatedTasks | unknown): TaskSummary[] {
  const items = asRecord(payload).items;
  if (!Array.isArray(items)) return [];
  return items.map(normalizeTask).filter((task): task is TaskSummary => task !== null);
}

function normalizePriorityQuadrant(value: unknown): WorkbenchQuadrant | null {
  if (value === "important_urgent" || value === "重要且紧急") return "important_urgent";
  if (value === "important_not_urgent" || value === "重要不紧急") return "important_not_urgent";
  if (value === "urgent_not_important" || value === "紧急不重要") return "urgent_not_important";
  if (value === "routine" || value === "常规任务") return "routine";
  return null;
}

function normalizeSummary(payload: DashboardSummary | unknown): DashboardSummary {
  const record = asRecord(payload);
  const recentTasks = Array.isArray(record.recent_tasks)
    ? record.recent_tasks.map(normalizeTask).filter((task): task is TaskSummary => task !== null)
    : [];
  const priorityItems = Array.isArray(record.priority_items)
    ? record.priority_items.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    : [];

  return {
    created_task_count: safeNumber(record.created_task_count),
    assigned_task_count: safeNumber(record.assigned_task_count),
    inbox_count: safeNumber(record.inbox_count),
    in_progress_count: safeNumber(record.in_progress_count),
    pending_acceptance_count: safeNumber(record.pending_acceptance_count),
    today_task_count: safeNumber(record.today_task_count),
    due_within_7_days_count: safeNumber(record.due_within_7_days_count),
    overdue_count: safeNumber(record.overdue_count),
    report_due_count: safeNumber(record.report_due_count),
    open_issue_count: safeNumber(record.open_issue_count),
    blocked_task_count: safeNumber(record.blocked_task_count),
    completion_review_count: safeNumber(record.completion_review_count),
    unread_notification_count: safeNumber(record.unread_notification_count),
    open_conflict_count: safeNumber(record.open_conflict_count),
    due_window_days: safeNumber(record.due_window_days) || 7,
    recent_tasks: recentTasks,
    latest_workload: record.latest_workload && typeof record.latest_workload === "object" ? record.latest_workload as Record<string, unknown> : null,
    priority_items: priorityItems,
  };
}

function quadrantSummaries(summary: DashboardSummary): WorkbenchQuadrantSummary[] {
  const counts: Record<WorkbenchQuadrant, number> = {
    important_urgent: 0,
    important_not_urgent: 0,
    urgent_not_important: 0,
    routine: 0,
  };

  summary.priority_items.forEach((item) => {
    const quadrant = normalizePriorityQuadrant(item.priority_quadrant ?? item.quadrant ?? item.priorityQuadrant);
    if (quadrant) counts[quadrant] += 1;
  });

  return Object.entries(quadrantLabels).map(([id, label]) => ({
    id: id as WorkbenchQuadrant,
    label,
    count: counts[id as WorkbenchQuadrant],
  }));
}

export function isWorkbenchStatusFilter(value: string | null): value is WorkbenchStatusFilter {
  return Boolean(value && workbenchStatusFilters.includes(value as WorkbenchStatusFilter));
}

export function isWorkbenchQuadrant(value: string | null): value is WorkbenchQuadrant {
  return Boolean(value && value in quadrantLabels);
}

export async function loadWorkbenchData(filters: WorkbenchFilters = {}): Promise<WorkbenchData> {
  const taskParams: Record<string, string | number> = { limit: 8, offset: 0 };
  if (filters.status) taskParams.status = filters.status;

  const [summaryPayload, taskPagePayload] = await Promise.all([
    getDashboardSummary(),
    listTasks(taskParams),
  ]);
  const summary = normalizeSummary(summaryPayload);

  return {
    summary,
    tasks: normalizeTasks(taskPagePayload),
    quadrants: quadrantSummaries(summary),
  };
}
