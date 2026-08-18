export type TaskStatus =
  | "draft"
  | "pending_confirmation"
  | "pending_acceptance"
  | "returned"
  | "in_progress"
  | "pending_review"
  | "completed";

export type AllowedAction =
  | "submit_for_confirmation"
  | "confirm_and_send"
  | "confirm_self_assigned"
  | "accept"
  | "return"
  | "resend"
  | "start_node"
  | "update_node_progress"
  | "complete_node"
  | "submit_completion"
  | "approve_completion";

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

export interface PaginatedTasks {
  items: TaskSummary[];
  limit: number;
  offset: number;
  total: number;
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
  due_within_7_days_count: number;
  overdue_count: number;
  due_window_days: number;
  recent_tasks: TaskSummary[];
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
