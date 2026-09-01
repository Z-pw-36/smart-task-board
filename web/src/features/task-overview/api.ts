/**
 * Feature: V1.1 task overview query projection.
 * Responsibilities: normalize URL query state and load server-filtered task or node overview pages.
 * Does not own: backend filtering authority, task detail data, or business calculations.
 * Plan task: DEV-04.
 */

import { listTasks } from "../../api/endpoints";
import type { PaginatedTaskOverview, TaskOverviewNode, TaskStatus, TaskSummary } from "../../api/types";

export type OverviewMode = "tasks" | "nodes";
export type OverviewQuadrant = "important_urgent" | "important_not_urgent" | "urgent_not_important" | "routine";
export type OverviewDatePreset = "all" | "week" | "month" | "custom";
export type OverviewSort = "deadline" | "created_at" | "updated_at" | "status" | "task_weight";
export type OverviewSortOrder = "asc" | "desc";
export type OverviewSupport = "open";

export interface TaskOverviewFilters {
  mode: OverviewMode;
  status: TaskStatus | "";
  quadrant: OverviewQuadrant | "";
  support: OverviewSupport | "";
  nearDue: boolean;
  datePreset: OverviewDatePreset;
  startDate: string;
  endDate: string;
  search: string;
  page: number;
  pageSize: number;
  sortBy: OverviewSort;
  sortOrder: OverviewSortOrder;
}

export interface TaskOverviewData extends Omit<PaginatedTaskOverview, "items"> {
  items: Array<TaskSummary | TaskOverviewNode>;
  status_counts: Record<string, number>;
}

export const overviewStatuses: Array<{ value: TaskStatus; label: string }> = [
  { value: "pending_acceptance", label: "待接受" },
  { value: "decomposing", label: "AI拆解中" },
  { value: "decomposition_failed", label: "拆解失败" },
  { value: "in_progress", label: "进行中" },
  { value: "blocked", label: "受阻" },
  { value: "pending_report", label: "待汇报" },
  { value: "pending_review", label: "待验收" },
  { value: "completed", label: "已完成" },
  { value: "archived", label: "已归档" },
  { value: "cancelled", label: "已取消" },
  { value: "withdrawn", label: "已撤回" },
  { value: "merged", label: "已合并" },
  { value: "closed", label: "已关闭" },
];

export const overviewStatusCounts = [
  "pending_acceptance",
  "in_progress",
  "blocked",
  "pending_report",
  "pending_review",
] as const satisfies readonly TaskStatus[];

export const quadrantOptions: Array<{ value: OverviewQuadrant; label: string }> = [
  { value: "important_urgent", label: "重要且紧急" },
  { value: "important_not_urgent", label: "重要不紧急" },
  { value: "urgent_not_important", label: "紧急不重要" },
  { value: "routine", label: "常规任务" },
];

export const modeOptions: Array<{ value: OverviewMode; label: string }> = [
  { value: "tasks", label: "任务" },
  { value: "nodes", label: "我的节点" },
];

export const datePresetOptions: Array<{ value: OverviewDatePreset; label: string }> = [
  { value: "all", label: "全部" },
  { value: "week", label: "本周" },
  { value: "month", label: "本月" },
  { value: "custom", label: "自定义" },
];

const statusSet = new Set(overviewStatuses.map((item) => item.value));
const quadrantSet = new Set(quadrantOptions.map((item) => item.value));
const datePresetSet = new Set(datePresetOptions.map((item) => item.value));
const sortSet = new Set<OverviewSort>(["deadline", "created_at", "updated_at", "status", "task_weight"]);

function oneOf<T extends string>(value: string | null, values: Set<T>, fallback: T): T {
  return value && values.has(value as T) ? value as T : fallback;
}

function optionalOneOf<T extends string>(value: string | null, values: Set<T>): T | "" {
  return value && values.has(value as T) ? value as T : "";
}

function positiveInt(value: string | null, fallback: number): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

export function parseTaskOverviewFilters(params: URLSearchParams): TaskOverviewFilters {
  return {
    mode: oneOf(params.get("mode"), new Set<OverviewMode>(["tasks", "nodes"]), "tasks"),
    status: optionalOneOf(params.get("status"), statusSet),
    quadrant: optionalOneOf(params.get("quadrant"), quadrantSet),
    support: params.get("support") === "open" ? "open" : "",
    nearDue: params.get("nearDue") === "true",
    datePreset: oneOf(params.get("datePreset"), datePresetSet, "all"),
    startDate: params.get("startDate") ?? "",
    endDate: params.get("endDate") ?? "",
    search: params.get("search") ?? "",
    page: positiveInt(params.get("page"), 1),
    pageSize: Math.min(100, positiveInt(params.get("pageSize"), 20)),
    sortBy: oneOf(params.get("sortBy"), sortSet, "deadline"),
    sortOrder: oneOf(params.get("sortOrder"), new Set<OverviewSortOrder>(["asc", "desc"]), "asc"),
  };
}

export function taskOverviewSearchParams(filters: TaskOverviewFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.mode !== "tasks") params.set("mode", filters.mode);
  if (filters.status) params.set("status", filters.status);
  if (filters.quadrant) params.set("quadrant", filters.quadrant);
  if (filters.support) params.set("support", filters.support);
  if (filters.nearDue) params.set("nearDue", "true");
  if (filters.datePreset !== "all") params.set("datePreset", filters.datePreset);
  if (filters.datePreset === "custom") {
    if (filters.startDate) params.set("startDate", filters.startDate);
    if (filters.endDate) params.set("endDate", filters.endDate);
  }
  if (filters.search.trim()) params.set("search", filters.search.trim());
  if (filters.page > 1) params.set("page", String(filters.page));
  if (filters.pageSize !== 20) params.set("pageSize", String(filters.pageSize));
  if (filters.sortBy !== "deadline") params.set("sortBy", filters.sortBy);
  if (filters.sortOrder !== "asc") params.set("sortOrder", filters.sortOrder);
  return params;
}

export function isNodeOverviewItem(item: TaskSummary | TaskOverviewNode): item is TaskOverviewNode {
  return "node_id" in item;
}

export async function loadTaskOverview(filters: TaskOverviewFilters): Promise<TaskOverviewData> {
  const payload = await listTasks({
    mode: filters.mode,
    status: filters.status,
    quadrant: filters.quadrant,
    support: filters.support,
    nearDue: filters.nearDue,
    datePreset: filters.datePreset,
    startDate: filters.datePreset === "custom" ? filters.startDate : "",
    endDate: filters.datePreset === "custom" ? filters.endDate : "",
    search: filters.search.trim(),
    page: filters.page,
    pageSize: filters.pageSize,
    sortBy: filters.sortBy,
    sortOrder: filters.sortOrder,
  }) as PaginatedTaskOverview;
  return {
    ...payload,
    status_counts: payload.status_counts ?? {},
  };
}
