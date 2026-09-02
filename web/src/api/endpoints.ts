import { apiRequest } from "./client";
import type {
  ArchivePayload,
  ArchiveSearchResponse,
  AuthTokenPayload,
  AuthTokenResponse,
  AuthorizedScope,
  AuthorizedScopePayload,
  AvailableActions,
  ConfirmTaskInputPayload,
  ConfirmTaskPlanningPayload,
  Conflict,
  CreateTaskPayload,
  CurrentUser,
  DashboardSummary,
  DepartmentOption,
  EmployeeProfile,
  EmployeeProfilePayload,
  LoginResponse,
  NotificationItem,
  PaginatedInbox,
  PaginatedTasks,
  PerformanceMatch,
  PerformanceMetric,
  PerformanceMetricPayload,
  ProgressReport,
  ProgressReportPage,
  PrototypeUser,
  Recommendation,
  RecommendationPayload,
  RefreshTokenPayload,
  ReportDueResponse,
  StatusLogPage,
  SystemParameter,
  SystemParameterPayload,
  TaskActionResult,
  TaskArchive,
  TaskClarificationPayload,
  TaskChangeRequest,
  TaskChangeRequestPage,
  TaskCompletionReview,
  TaskCompletionReviewPage,
  TaskDetail,
  TaskInputPayload,
  TaskIntakeResponse,
  TaskIssue,
  TaskIssuePage,
  TaskNode,
  TaskPlanningSuggestionPayload,
  TaskPlanningSuggestionResponse,
  WorkloadCalculationPayload,
  WorkloadSnapshot,
  PriorityScore,
} from "./types";

type QueryPrimitive = string | number | boolean | null | undefined;
type QueryParams = Record<string, QueryPrimitive>;

function withQuery(path: string, params?: QueryParams): string {
  if (!params) return path;
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    search.set(key, String(value));
  });
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

export function listPrototypeUsers(): Promise<PrototypeUser[]> {
  return apiRequest<PrototypeUser[]>("/api/v1/auth/prototype-users", {}, { anonymous: true });
}

export const listUsers = listPrototypeUsers;

export async function listDepartments(): Promise<DepartmentOption[]> {
  const users = await listPrototypeUsers();
  const byId = new Map<string, DepartmentOption>();
  users.forEach((user) => {
    if (!user.department_id || !user.department_name) return;
    byId.set(user.department_id, {
      department_id: user.department_id,
      department_name: user.department_name,
    });
  });
  return [...byId.values()].sort((left, right) =>
    left.department_name.localeCompare(right.department_name),
  );
}

export function prototypeLogin(employeeNo: string): Promise<LoginResponse> {
  return apiRequest<LoginResponse>(
    "/api/v1/auth/prototype-login",
    { method: "POST", body: JSON.stringify({ employee_no: employeeNo }) },
    { anonymous: true },
  );
}

export function issueAuthTokens(payload: AuthTokenPayload): Promise<AuthTokenResponse> {
  return apiRequest<AuthTokenResponse>(
    "/api/v1/auth/login",
    { method: "POST", body: JSON.stringify(payload) },
    { anonymous: true },
  );
}

export function refreshAuthTokens(payload: RefreshTokenPayload): Promise<AuthTokenResponse> {
  return apiRequest<AuthTokenResponse>(
    "/api/v1/auth/refresh",
    { method: "POST", body: JSON.stringify(payload) },
    { anonymous: true },
  );
}

export function revokeRefreshToken(payload: RefreshTokenPayload): Promise<void> {
  return apiRequest<void>(
    "/api/v1/auth/revoke",
    { method: "POST", body: JSON.stringify(payload) },
    { anonymous: true },
  );
}

export function getCurrentUser(): Promise<CurrentUser> {
  return apiRequest<CurrentUser>("/api/v1/me");
}

export function logoutSession(): Promise<void> {
  return apiRequest<void>("/api/v1/auth/logout", { method: "POST" });
}

export function listTasks(params: QueryParams): Promise<PaginatedTasks> {
  return apiRequest<PaginatedTasks>(withQuery("/api/v1/tasks", params));
}

export function createTask(payload: CreateTaskPayload): Promise<TaskActionResult> {
  return apiRequest<TaskActionResult>("/api/v1/tasks", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getTaskDetail(taskId: string): Promise<TaskDetail> {
  return apiRequest<TaskDetail>(`/api/v1/tasks/${taskId}`);
}

export function listTaskNodes(taskId: string): Promise<TaskNode[]> {
  return apiRequest<TaskNode[]>(`/api/v1/tasks/${taskId}/nodes`);
}

export function getTaskNode(taskId: string, nodeId: string): Promise<TaskNode> {
  return apiRequest<TaskNode>(`/api/v1/tasks/${taskId}/nodes/${nodeId}`);
}

export function decomposeTaskPlan(
  taskId: string,
  payload: TaskPlanningSuggestionPayload = {},
): Promise<TaskPlanningSuggestionResponse> {
  return apiRequest<TaskPlanningSuggestionResponse>(`/api/v1/tasks/${taskId}/planning/decompose`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function confirmTaskPlan(
  taskId: string,
  payload: ConfirmTaskPlanningPayload,
): Promise<TaskActionResult> {
  return apiRequest<TaskActionResult>(`/api/v1/tasks/${taskId}/planning/confirm`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getAvailableActions(taskId: string): Promise<AvailableActions> {
  return apiRequest<AvailableActions>(`/api/v1/tasks/${taskId}/available-actions`);
}

export function getTaskStatusLogs(
  taskId: string,
  params: QueryParams = { limit: 50, offset: 0 },
): Promise<StatusLogPage> {
  return apiRequest<StatusLogPage>(withQuery(`/api/v1/tasks/${taskId}/status-logs`, params));
}

export function getInbox(params?: QueryParams): Promise<PaginatedInbox> {
  return apiRequest<PaginatedInbox>(withQuery("/api/v1/tasks/inbox", params));
}

export function getDashboardSummary(): Promise<DashboardSummary> {
  return apiRequest<DashboardSummary>("/api/v1/dashboard/summary");
}

export function submitTaskInput(payload: TaskInputPayload): Promise<TaskIntakeResponse> {
  return apiRequest<TaskIntakeResponse>("/api/v1/task-inputs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function clarifyTaskInput(
  inputId: string,
  payload: TaskClarificationPayload,
): Promise<TaskIntakeResponse> {
  return apiRequest<TaskIntakeResponse>(`/api/v1/task-inputs/${inputId}/clarifications`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function confirmTaskInput(
  inputId: string,
  payload: ConfirmTaskInputPayload,
): Promise<TaskActionResult> {
  return apiRequest<TaskActionResult>(`/api/v1/task-inputs/${inputId}/confirm-task`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listProgressReports(taskId: string, params?: QueryParams): Promise<ProgressReportPage> {
  return apiRequest<ProgressReportPage>(withQuery(`/api/v1/tasks/${taskId}/progress-reports`, params));
}

export function getProgressReport(
  taskId: string,
  progressReportId: string,
): Promise<ProgressReport> {
  return apiRequest<ProgressReport>(
    `/api/v1/tasks/${taskId}/progress-reports/${progressReportId}`,
  );
}

export function submitProgressReport(
  taskId: string,
  payload: Record<string, unknown>,
): Promise<ProgressReport> {
  return apiRequest<ProgressReport>(`/api/v1/tasks/${taskId}/progress-reports`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listTaskIssues(taskId: string, params?: QueryParams): Promise<TaskIssuePage> {
  return apiRequest<TaskIssuePage>(withQuery(`/api/v1/tasks/${taskId}/issues`, params));
}

export function getTaskIssue(taskId: string, issueId: string): Promise<TaskIssue> {
  return apiRequest<TaskIssue>(`/api/v1/tasks/${taskId}/issues/${issueId}`);
}

export function createTaskIssue(taskId: string, payload: Record<string, unknown>): Promise<TaskIssue> {
  return apiRequest<TaskIssue>(`/api/v1/tasks/${taskId}/issues`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function runIssueAction(
  taskId: string,
  issueId: string,
  action: "start_processing" | "resolve" | "reject" | "close",
  payload: Record<string, unknown>,
): Promise<TaskIssue> {
  return apiRequest<TaskIssue>(
    `/api/v1/tasks/${taskId}/issues/${issueId}/actions/${action.replace("_", "-")}`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function listCompletionReviews(
  taskId: string,
  params?: QueryParams,
): Promise<TaskCompletionReviewPage> {
  return apiRequest<TaskCompletionReviewPage>(
    withQuery(`/api/v1/tasks/${taskId}/completion-reviews`, params),
  );
}

export function getCompletionReview(
  taskId: string,
  completionReviewId: string,
): Promise<TaskCompletionReview> {
  return apiRequest<TaskCompletionReview>(
    `/api/v1/tasks/${taskId}/completion-reviews/${completionReviewId}`,
  );
}

export function listChangeRequests(
  taskId: string,
  params?: QueryParams,
): Promise<TaskChangeRequestPage> {
  return apiRequest<TaskChangeRequestPage>(
    withQuery(`/api/v1/tasks/${taskId}/change-requests`, params),
  );
}

export function getChangeRequest(
  taskId: string,
  changeRequestId: string,
): Promise<TaskChangeRequest> {
  return apiRequest<TaskChangeRequest>(
    `/api/v1/tasks/${taskId}/change-requests/${changeRequestId}`,
  );
}

export function listReportDue(): Promise<ReportDueResponse> {
  return apiRequest<ReportDueResponse>("/api/v1/tasks/report-due");
}

export function listPerformanceMetrics(): Promise<PerformanceMetric[]> {
  return apiRequest<PerformanceMetric[]>("/api/v1/performance-metrics");
}

export function createPerformanceMetric(payload: PerformanceMetricPayload): Promise<PerformanceMetric> {
  return apiRequest<PerformanceMetric>("/api/v1/performance-metrics", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function suggestPerformanceMatches(taskId: string, limit = 10): Promise<PerformanceMatch[]> {
  return apiRequest<PerformanceMatch[]>(
    withQuery(`/api/v1/tasks/${taskId}/performance-matches/suggest`, { limit }),
    { method: "POST" },
  );
}

export function confirmPerformanceMatch(
  taskId: string,
  performanceMatchId: string,
): Promise<PerformanceMatch> {
  return apiRequest<PerformanceMatch>(
    `/api/v1/tasks/${taskId}/performance-matches/${performanceMatchId}/confirm`,
    { method: "POST" },
  );
}

export function recommendAssignees(payload: RecommendationPayload): Promise<Recommendation[]> {
  return apiRequest<Recommendation[]>("/api/v1/organization/recommendations/assignees", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function upsertEmployeeProfile(
  employeeNo: string,
  payload: EmployeeProfilePayload,
): Promise<EmployeeProfile> {
  return apiRequest<EmployeeProfile>(`/api/v1/organization/employee-profiles/${employeeNo}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function grantAuthorizedScope(payload: AuthorizedScopePayload): Promise<AuthorizedScope> {
  return apiRequest<AuthorizedScope>("/api/v1/permissions/scopes", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listAuthorizedScopes(employeeNo?: string): Promise<AuthorizedScope[]> {
  return apiRequest<AuthorizedScope[]>(
    withQuery("/api/v1/permissions/scopes", { employee_no: employeeNo }),
  );
}

export function calculateWorkload(
  employeeNo: string,
  payload: WorkloadCalculationPayload,
): Promise<WorkloadSnapshot> {
  return apiRequest<WorkloadSnapshot>(`/api/v1/analytics/workload/${employeeNo}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function calculatePriorities(): Promise<PriorityScore[]> {
  return apiRequest<PriorityScore[]>("/api/v1/analytics/priorities", { method: "POST" });
}

export function detectConflicts(employeeNo?: string): Promise<Conflict[]> {
  return apiRequest<Conflict[]>(
    withQuery("/api/v1/analytics/conflicts/detect", { employee_no: employeeNo }),
    { method: "POST" },
  );
}

export function runConflictAction(
  conflictId: string,
  action: "acknowledge" | "resolve" | "ignore",
  resolutionNote: string,
): Promise<Conflict> {
  return apiRequest<Conflict>(`/api/v1/conflicts/${conflictId}/actions/${action}`, {
    method: "POST",
    body: JSON.stringify({ resolution_note: resolutionNote }),
  });
}

export function scanReminders() {
  return apiRequest("/api/v1/reminders/scan", { method: "POST" });
}

export function sendPendingNotifications(): Promise<NotificationItem[]> {
  return apiRequest<NotificationItem[]>("/api/v1/notifications/send-pending", { method: "POST" });
}

export function listNotifications(unreadOnly = false): Promise<NotificationItem[]> {
  return apiRequest<NotificationItem[]>(
    withQuery("/api/v1/notifications", { unread_only: unreadOnly }),
  );
}

export function markNotificationRead(notificationId: string): Promise<NotificationItem> {
  return apiRequest<NotificationItem>(`/api/v1/notifications/${notificationId}/read`, {
    method: "POST",
  });
}

export function archiveTaskSnapshot(
  taskId: string,
  payload: ArchivePayload,
): Promise<TaskArchive> {
  return apiRequest<TaskArchive>(`/api/v1/tasks/${taskId}/archive-snapshot`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function searchArchives(params?: QueryParams): Promise<ArchiveSearchResponse> {
  return apiRequest<ArchiveSearchResponse>(withQuery("/api/v1/archives/search", params));
}

export function similarArchives(taskId: string, limit = 5): Promise<TaskArchive[]> {
  return apiRequest<TaskArchive[]>(withQuery(`/api/v1/tasks/${taskId}/similar-archives`, { limit }));
}

export function reuseArchive(
  archiveId: string,
  payload: Record<string, unknown>,
): Promise<TaskActionResult> {
  return apiRequest<TaskActionResult>(`/api/v1/archives/${archiveId}/reuse`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listOperationLogs(params?: QueryParams) {
  return apiRequest(withQuery("/api/v1/operation-logs", params));
}

export function listSystemParameters(): Promise<SystemParameter[]> {
  return apiRequest<SystemParameter[]>("/api/v1/system-parameters");
}

export function upsertSystemParameter(
  paramKey: string,
  payload: SystemParameterPayload,
): Promise<SystemParameter> {
  return apiRequest<SystemParameter>(`/api/v1/system-parameters/${paramKey}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}
