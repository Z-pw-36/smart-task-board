/**
 * Feature: V1.1 task detail read model.
 * Responsibilities: compose existing read-only task detail, permissions, report, issue, log, and review APIs for DEV-05 pages.
 * Does not own: task mutations, permission decisions, progress calculation, or KPI matching jobs.
 * Plan task: DEV-05.
 */

import {
  getAvailableActions,
  getTaskDetail,
  getTaskStatusLogs,
  listCompletionReviews,
  listProgressReports,
  listTaskIssues,
} from "../../api/endpoints";
import type {
  AvailableActions,
  ProgressReport,
  StatusLogPage,
  TaskCompletionReview,
  TaskDetail,
  TaskIssue,
} from "../../api/types";

export interface TaskDetailBundle {
  task: TaskDetail;
  actions: AvailableActions;
  logs: StatusLogPage["items"];
  reports: ProgressReport[];
  issues: TaskIssue[];
  reviews: TaskCompletionReview[];
}

export async function loadTaskDetailBundle(taskId: string): Promise<TaskDetailBundle> {
  const [task, actions, logs, reports, issues, reviews] = await Promise.all([
    getTaskDetail(taskId),
    getAvailableActions(taskId),
    getTaskStatusLogs(taskId, { limit: 100, offset: 0 }),
    listProgressReports(taskId, { limit: 50, offset: 0 }),
    listTaskIssues(taskId, { limit: 50, offset: 0 }),
    listCompletionReviews(taskId, { limit: 20, offset: 0 }),
  ]);

  return {
    task,
    actions,
    logs: Array.isArray(logs.items) ? logs.items : [],
    reports: Array.isArray(reports.items) ? reports.items : [],
    issues: Array.isArray(issues.items) ? issues.items : [],
    reviews: Array.isArray(reviews.items) ? reviews.items : [],
  };
}
