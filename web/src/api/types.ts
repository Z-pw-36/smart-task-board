export type TaskStatus =
  | "draft"
  | "pending_confirmation"
  | "pending_acceptance"
  | "pending_confirm"
  | "pending_accept"
  | "returned"
  | "decomposing"
  | "decomposition_failed"
  | "in_progress"
  | "blocked"
  | "pending_report"
  | "pending_review"
  | "completed"
  | "archived"
  | "cancelled"
  | "withdrawn"
  | "merged"
  | "closed";

export type AllowedAction =
  | "submit_for_confirmation"
  | "confirm_and_send"
  | "confirm_self_assigned"
  | "accept"
  | "return"
  | "resend"
  | "plan_task"
  | "start_node"
  | "update_node_progress"
  | "complete_node"
  | "submit_completion"
  | "approve_completion"
  | "reject_completion"
  | "reopen_node"
  | "submit_change_request"
  | "approve_change_request"
  | "reject_change_request"
  | "cancel_change_request"
  | "cancel_task"
  | "withdraw_task"
  | "merge_task"
  | "close_task"
  | "archive_task"
  | "restore_task"
  | "submit_progress_report"
  | "report_task_issue"
  | "start_processing_issue"
  | "resolve_issue"
  | "reject_issue"
  | "close_issue";

export interface PrototypeUser {
  employee_no: string;
  name: string;
  department_id: string | null;
  department_name: string | null;
  role_type: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: { employee_no: string; name: string };
}

export interface AuthTokenPayload {
  employee_no: string;
}

export interface RefreshTokenPayload {
  refresh_token: string;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  refresh_token: string;
}

export interface CurrentUser {
  employee_no: string;
  name: string;
  department: { department_id: string; department_name: string } | null;
  role_type: string;
  auth_mode: string;
}

export interface TaskSummary {
  task_id: string;
  task_no: string | null;
  task_name: string;
  status: TaskStatus;
  deadline: string | null;
  is_urgent: boolean | null;
  task_weight: number | null;
  task_version: number;
  creator: { employee_no: string; name: string };
  main_assignee: { employee_no: string; name: string } | null;
  current_user_relations: string[];
  allowed_actions: AllowedAction[];
  is_overdue: boolean;
  days_until_deadline: number | null;
  created_at: string;
  updated_at: string;
}

export interface TaskOverviewNode {
  node_id: string;
  task_id: string;
  task_no: string | null;
  task_name: string;
  node_name: string;
  status: string;
  task_status: TaskStatus;
  owner: { employee_no: string; name: string } | null;
  planned_start_time: string | null;
  planned_deadline: string | null;
  progress_percent: number;
  current_user_relations: string[];
  is_overdue: boolean;
  days_until_deadline: number | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedTasks {
  items: TaskSummary[];
  limit: number;
  offset: number;
  page?: number;
  pageSize?: number;
  total: number;
  status_counts?: Record<string, number>;
}

export interface PaginatedTaskOverview extends Omit<PaginatedTasks, "items"> {
  items: Array<TaskSummary | TaskOverviewNode>;
}

export interface InboxItem {
  inbox_item_type: string;
  action_code: string;
  task: TaskSummary;
  node: {
    node_id: string;
    node_name: string;
    status: string;
    progress_percent: number;
    owner_employee_no: string | null;
  } | null;
  reason: string;
  expected_task_version: number;
  endpoint: string;
  allowed_actions: AllowedAction[];
  is_overdue: boolean;
  relevant_at: string;
}

export interface PaginatedInbox {
  items: InboxItem[];
  limit: number;
  offset: number;
  total: number;
}

export interface DashboardSummary {
  created_task_count: number;
  assigned_task_count: number;
  inbox_count: number;
  in_progress_count: number;
  pending_acceptance_count: number;
  today_task_count: number;
  due_within_7_days_count: number;
  overdue_count: number;
  report_due_count: number;
  open_issue_count: number;
  blocked_task_count: number;
  completion_review_count: number;
  unread_notification_count: number;
  open_conflict_count: number;
  due_window_days: number;
  recent_tasks: TaskSummary[];
  latest_workload: Record<string, unknown> | null;
  priority_items: Array<Record<string, unknown>>;
}

export interface DepartmentOption {
  department_id: string;
  department_name: string;
}

export interface TaskActionResult {
  task_id: string;
  status: TaskStatus;
  task_version: number;
  updated_at: string;
}

export interface TaskParticipantDraftInput {
  employee_no: string;
  participant_role: string;
  is_primary?: boolean;
}

export interface TaskNodeDraftInput {
  node_id: string;
  node_order: number;
  node_name: string;
  action_detail?: string | null;
  owner_employee_no?: string | null;
  planned_start_time?: string | null;
  planned_deadline?: string | null;
  estimated_hours?: string | null;
  actual_hours?: string | null;
  deliverable?: string | null;
  acceptance_criteria?: string | null;
  tools_or_materials?: string | null;
}

export interface TaskPlanningNodeDraftInput extends TaskNodeDraftInput {
  enabled?: boolean;
}

export interface TaskNodeDependencyDraftInput {
  dependency_id?: string;
  predecessor_node_id: string;
  successor_node_id: string;
  dependency_type?: string;
}

export interface TaskNodeParticipantDraftInput {
  node_id: string;
  employee_no: string;
  participant_role: string;
}

export interface CreateTaskPayload {
  task_id?: string | null;
  task_name: string;
  task_description?: string | null;
  task_goal?: string | null;
  task_source?: string | null;
  main_assignee_employee_no?: string | null;
  report_to_employee_no?: string | null;
  report_to_level?: string | null;
  reviewer_employee_no?: string | null;
  department_id?: string | null;
  start_time?: string | null;
  deadline?: string | null;
  estimated_hours?: string | null;
  actual_hours?: string | null;
  task_weight?: number | null;
  deliverable?: string | null;
  acceptance_criteria?: string | null;
  is_urgent?: boolean | null;
  report_cycle?: string | null;
  participants?: TaskParticipantDraftInput[];
  nodes?: TaskNodeDraftInput[];
  dependencies?: TaskNodeDependencyDraftInput[];
  node_participants?: TaskNodeParticipantDraftInput[];
  extraction_record_ids?: string[];
}

export type TaskInputType = "text" | "voice" | "wecom_text";
export type TaskInputSourceChannel = "web" | "api" | "wecom";

export interface TaskInputPayload {
  input_id?: string | null;
  input_type?: TaskInputType;
  raw_text?: string | null;
  voice_file_url?: string | null;
  source_channel?: TaskInputSourceChannel;
}

export interface TaskIntakeResponse {
  input_id: string;
  input_type: string;
  raw_text: string | null;
  asr_text: string | null;
  source_channel: string;
  submitted_by_employee_no: string;
  submitted_at: string;
  extraction_id: string;
  extracted_json: Record<string, unknown>;
  missing_fields: string[];
  low_confidence_fields: string[];
  confirm_questions: string[];
  confidence_score: string | null;
}

export interface TaskClarificationPayload {
  answers: Record<string, unknown>;
}

export interface ConfirmTaskInputPayload {
  task_id?: string | null;
  extraction_id: string;
  corrections?: Record<string, unknown>;
}

export interface TaskPlanningSuggestionPayload {
  instructions?: string | null;
}

export interface TaskPlanningSuggestionNode {
  client_node_id: string;
  node_order: number;
  node_name: string;
  action_detail: string | null;
  tools_or_materials: string | null;
  suggested_owner_employee_no: string | null;
  planned_start_time: string | null;
  planned_deadline: string | null;
  estimated_hours: string | null;
  deliverable: string | null;
  acceptance_criteria: string | null;
  dependencies: string[];
  enabled: boolean;
}

export interface TaskPlanningSuggestionDependency {
  predecessor_client_node_id: string;
  successor_client_node_id: string;
  dependency_type: string;
  reason: string | null;
}

export interface TaskPlanningSuggestionResponse {
  task_id: string;
  suggested_nodes: TaskPlanningSuggestionNode[];
  suggested_dependencies: TaskPlanningSuggestionDependency[];
}

export interface ConfirmTaskPlanningPayload {
  expected_task_version: number;
  nodes: TaskPlanningNodeDraftInput[];
  dependencies?: TaskNodeDependencyDraftInput[];
  node_participants?: TaskNodeParticipantDraftInput[];
}

export interface ProgressReport {
  progress_report_id: string;
  task_id: string;
  node_id: string | null;
  reporter_employee_no: string;
  progress_percent: number;
  report_content: string;
  stage_result: string | null;
  difficulty: string | null;
  resource_request: string | null;
  actual_hours: string | null;
  corrects_report_id: string | null;
  report_period_start: string | null;
  report_period_end: string | null;
  task_version: number;
  operation_source: string;
  created_at: string;
}

export interface ProgressReportPage {
  items: ProgressReport[];
  limit: number;
  offset: number;
  total: number;
}

export type IssueAction = "start_processing" | "resolve" | "reject" | "close";

export interface TaskIssue {
  issue_id: string;
  task_id: string;
  node_id: string | null;
  source_progress_report_id: string | null;
  reported_by_employee_no: string;
  issue_type: string;
  title: string;
  description: string;
  requested_resource: string | null;
  severity: string;
  status: "open" | "processing" | "resolved" | "rejected" | "closed";
  owner_employee_no: string;
  resolution_note: string | null;
  resolved_by_employee_no: string | null;
  rejected_by_employee_no: string | null;
  closed_by_employee_no: string | null;
  created_at: string;
  processing_started_at: string | null;
  resolved_at: string | null;
  rejected_at: string | null;
  closed_at: string | null;
  allowed_actions: IssueAction[];
}

export interface TaskIssuePage {
  items: TaskIssue[];
  limit: number;
  offset: number;
  total: number;
}

export type CompletionReviewStatus = "submitted" | "approved" | "rejected";

export interface TaskCompletionReview {
  completion_review_id: string;
  task_id: string;
  review_round: number;
  submitted_by_employee_no: string;
  completion_note: string | null;
  deliverable_summary: string | null;
  reviewer_employee_no: string;
  review_status: CompletionReviewStatus;
  review_result: "approved" | "rejected" | null;
  reject_reason: string | null;
  rework_node_id: string | null;
  submitted_task_version: number;
  reviewed_task_version: number | null;
  submitted_at: string;
  reviewed_at: string | null;
  is_legacy_import: boolean;
}

export interface TaskCompletionReviewPage {
  items: TaskCompletionReview[];
  limit: number;
  offset: number;
  total: number;
}

export interface TaskPerformanceMatchSummary {
  performance_match_id: string;
  task_id: string;
  metric_id: string;
  metric_type: string;
  metric_name: string;
  period: string | null;
  business_unit: string | null;
  definition_formula: string | null;
  total_score: string;
  match_level: string;
  match_reason: string | null;
  is_confirmed: boolean;
  confirmed_by_employee_no: string | null;
  confirmed_at: string | null;
}

export interface TaskOperationLogSummary {
  operation_log_id: string;
  request_id: string | null;
  operator_employee_no: string | null;
  action: string;
  object_type: string;
  object_id: string;
  before_data: Record<string, unknown> | null;
  after_data: Record<string, unknown> | null;
  result: string;
  error_message: string | null;
  created_at: string;
}

export interface TaskChangeRequest {
  change_request_id: string;
  task_id: string;
  requester_employee_no: string;
  patch_json: Record<string, unknown>;
  reason: string;
  before_snapshot: Record<string, unknown>;
  after_snapshot: Record<string, unknown>;
  status: "pending" | "approved" | "rejected" | "cancelled";
  decision_by_employee_no: string | null;
  decision_at: string | null;
  decision_comment: string | null;
  cancelled_by_employee_no: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  requester_task_version: number;
  base_task_version: number;
  created_at: string;
}

export interface TaskChangeRequestPage {
  items: TaskChangeRequest[];
  limit: number;
  offset: number;
  total: number;
}

export interface TaskChangeRequestActionResult extends TaskActionResult {
  change_request: TaskChangeRequest;
}

export interface TaskNode {
  node_id: string;
  task_id: string;
  node_order: number;
  sort_weight: number;
  node_name: string;
  action_detail: string | null;
  owner_employee_no: string | null;
  planned_deadline: string | null;
  estimated_hours: string | null;
  actual_hours: string | null;
  deliverable: string | null;
  acceptance_criteria: string | null;
  progress_percent: number;
  status: string;
  completed_at: string | null;
  tools_or_materials: string | null;
  planned_start_time: string | null;
}

export interface TaskDetail {
  task_id: string;
  task_no: string | null;
  task_name: string;
  task_description: string | null;
  task_goal: string | null;
  task_source: string | null;
  creator_employee_no: string;
  main_assignee_employee_no: string | null;
  report_to_employee_no: string | null;
  report_to_level: string | null;
  reviewer_employee_no: string | null;
  department_id: string | null;
  status: TaskStatus;
  start_time: string | null;
  deadline: string | null;
  estimated_hours: string | null;
  actual_hours: string | null;
  task_weight: number | null;
  deliverable: string | null;
  acceptance_criteria: string | null;
  is_urgent: boolean | null;
  report_cycle: string | null;
  cancel_reason?: string | null;
  withdraw_reason?: string | null;
  close_reason?: string | null;
  merged_into_task_id?: string | null;
  task_version: number;
  created_at: string;
  updated_at: string;
  participants: Array<{ participant_id: string; employee_no: string; participant_role: string }>;
  nodes: TaskNode[];
  dependencies: Array<{
    dependency_id: string;
    predecessor_node_id: string;
    successor_node_id: string;
    dependency_type: string;
  }>;
  node_participants: Array<{
    node_participant_id: string;
    node_id: string;
    employee_no: string;
    participant_role: string;
  }>;
  performance_matches?: TaskPerformanceMatchSummary[];
  operation_logs?: TaskOperationLogSummary[];
  change_requests: TaskChangeRequest[];
  confirmed_at?: string | null;
  sent_at?: string | null;
  accepted_at?: string | null;
  completed_at?: string | null;
  archived_at?: string | null;
  ai_extraction_records?: Array<Record<string, unknown>>;
}

export interface CompletionReviewActionResult extends TaskActionResult {
  review: TaskCompletionReview;
}

export interface AvailableActions {
  task_id: string;
  task_version: number;
  allowed_actions: AllowedAction[];
  nodes: Array<{ node_id: string; allowed_actions: AllowedAction[] }>;
}

export interface StatusLogPage {
  items: Array<{
    status_log_id: string;
    from_status: TaskStatus | null;
    to_status: TaskStatus;
    action_type: string;
    reason: string | null;
    operator_employee_no: string | null;
    task_version: number;
    created_at: string;
  }>;
  limit: number;
  offset: number;
  total: number;
}

export interface ReportDueItem {
  task_id: string;
  task_no: string | null;
  task_name: string;
  task_version: number;
  report_period_start: string;
  report_period_end: string;
  overdue_seconds: number;
}

export interface ReportDueResponse {
  items: ReportDueItem[];
  total: number;
  calculated_at: string;
}

export interface SystemParameter {
  parameter_id: string;
  param_key: string;
  param_name: string;
  param_value: string;
  param_type: "number" | "string" | "boolean" | "json";
  module: string;
  description: string | null;
  is_active: boolean;
  updated_by_employee_no: string | null;
  updated_at: string;
}

export interface SystemParameterPayload {
  param_value: string;
  param_type?: "number" | "string" | "boolean" | "json";
  param_name?: string | null;
  module?: string;
  description?: string | null;
  is_active?: boolean;
}

export interface EmployeeProfilePayload {
  responsibility_text?: string | null;
  skill_tags?: string[];
  daily_capacity_hours?: string;
  standard_task_count?: number;
  standard_task_weight?: number;
  emergency_tolerance_count?: number;
  availability_status?: "available" | "busy" | "unavailable" | "disabled";
}

export interface EmployeeProfile extends Required<EmployeeProfilePayload> {
  employee_no: string;
  updated_at: string;
}

export interface RecommendationPayload {
  task_description: string;
  required_skill_tags?: string[];
  department_id?: string | null;
  limit?: number;
}

export interface Recommendation {
  employee_no: string;
  name: string;
  score: string;
  reasons: string[];
}

export interface AuthorizedScopePayload {
  employee_no: string;
  scope_type: "department" | "user" | "role" | "all_demo_data";
  scope_id?: string | null;
  permission_type?: "view" | "manage" | "export";
  valid_from?: string | null;
  valid_to?: string | null;
  status?: "active" | "expired" | "disabled";
}

export interface AuthorizedScope {
  authorized_scope_id: string;
  employee_no: string;
  scope_type: string;
  scope_id: string | null;
  permission_type: string;
  valid_from: string | null;
  valid_to: string | null;
  status: string;
  created_by_employee_no: string | null;
  created_at: string;
}

export interface PerformanceMetricPayload {
  metric_type: string;
  metric_name: string;
  period?: string | null;
  business_unit?: string | null;
  sequence_no?: number | null;
  dimension?: string | null;
  definition_formula?: string | null;
  weight?: string | null;
  target_value?: string | null;
  deliverable?: string | null;
  data_source?: string | null;
  status?: "active" | "inactive";
}

export interface PerformanceMetric extends PerformanceMetricPayload {
  metric_id: string;
  created_at: string;
  updated_at: string;
}

export interface PerformanceMatch {
  performance_match_id: string;
  task_id: string;
  metric_id: string;
  type_score: string;
  business_unit_score: string;
  metric_name_score: string;
  definition_formula_score: string;
  deliverable_score: string;
  total_score: string;
  match_level: "strong" | "weak" | "no_clear_relation";
  match_reason: string | null;
  is_confirmed: boolean;
  confirmed_by_employee_no: string | null;
  confirmed_at: string | null;
  algorithm_version: string;
  created_at: string;
  updated_at: string;
}

export interface WorkloadCalculationPayload {
  period_start: string;
  period_end: string;
}

export interface WorkloadSnapshot {
  workload_snapshot_id: string;
  employee_no: string;
  period_start: string;
  period_end: string;
  workload_score: string;
  workload_level: string;
  [key: string]: unknown;
}

export interface PriorityScore {
  priority_score_id: string;
  task_id: string;
  priority_quadrant: string;
  calculated_at: string;
  [key: string]: unknown;
}

export interface Conflict {
  conflict_id: string;
  conflict_type: string;
  employee_no: string;
  task_id: string;
  related_task_id: string | null;
  node_id: string | null;
  severity: string;
  description: string;
  suggestion: string | null;
  status: string;
  resolved_by_employee_no: string | null;
  resolution_note: string | null;
  detected_at: string;
  resolved_at: string | null;
}

export interface NotificationItem {
  notification_id: string;
  reminder_rule_id: string | null;
  task_id: string | null;
  issue_id: string | null;
  recipient_employee_no: string;
  channel: string;
  title: string;
  content: string;
  send_status: string;
  read_at: string | null;
  created_at: string;
  [key: string]: unknown;
}

export interface ArchivePayload {
  summary?: string | null;
  search_keywords?: string[];
  review_result?: string | null;
  risk_points?: string[];
}

export interface TaskArchive {
  archive_id: string;
  task_id: string;
  archive_snapshot: Record<string, unknown>;
  source_status_snapshot: string;
  summary: string | null;
  search_keywords: string[];
  review_result: string | null;
  risk_points: string[];
  reusable_template: Record<string, unknown> | null;
  actual_hours_total: string | null;
  archived_by_employee_no: string;
  archived_at: string;
}

export interface ArchiveSearchResponse {
  items: TaskArchive[];
  limit: number;
  offset: number;
  total: number;
}
