import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import type { CurrentUser } from "../api/types";
import { AuthContext, type AuthValue } from "../auth/auth-context";

export const currentUser: CurrentUser = {
  employee_no: "E-CREATOR",
  name: "测试创建人",
  department: { department_id: "11111111-1111-4111-8111-111111111111", department_name: "测试部门" },
  role_type: "employee",
  auth_mode: "prototype",
};

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function renderPage(
  ui: React.ReactNode,
  options: { route?: string; auth?: Partial<AuthValue> } = {},
) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const auth: AuthValue = {
    user: currentUser,
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
    ...options.auth,
  };
  return {
    ...render(
      <QueryClientProvider client={queryClient}>
        <AuthContext.Provider value={auth}>
          <MemoryRouter initialEntries={[options.route || "/"]}>{ui}</MemoryRouter>
        </AuthContext.Provider>
      </QueryClientProvider>,
    ),
    auth,
    queryClient,
  };
}

export const taskSummary = {
  task_id: "22222222-2222-4222-8222-222222222222",
  task_no: "TASK-001",
  task_name: "发布原型任务看板",
  status: "in_progress" as const,
  deadline: "2026-08-25T08:00:00Z",
  is_urgent: true,
  task_weight: 3,
  task_version: 4,
  creator: { employee_no: "E-CREATOR", name: "测试创建人" },
  main_assignee: { employee_no: "E-ASSIGNEE", name: "测试承办人" },
  current_user_relations: ["created"],
  allowed_actions: [],
  is_overdue: false,
  days_until_deadline: 7,
  created_at: "2026-08-18T08:00:00Z",
  updated_at: "2026-08-18T09:00:00Z",
};
