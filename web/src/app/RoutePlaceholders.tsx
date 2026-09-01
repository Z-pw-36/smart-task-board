/**
 * Feature: V1.1 route contract placeholders.
 * Responsibilities: render deterministic route, 403, 404, and login surfaces while later DEV tasks replace page bodies.
 * Does not own: task data fetching, auth APIs, or business workflow actions.
 * Plan task: DEV-02.
 */

import { Navigate, useLocation, useParams } from "react-router-dom";

import { useAuth } from "../auth/useAuth";
import { Button, Card, EmptyState, ErrorState, Typography } from "../shared/components";
import { findRouteContract } from "./navigation";
import { readReturnSourceState, resolveReturnTarget, useReturnNavigation } from "./return-state";

const placeholderCopy: Record<string, string> = {
  workbench: "后续 DEV-03 会替换为第二版工作台页面。",
  executive: "后续 DEV-16 会替换为高管团队看板。",
  tasks: "后续 DEV-04 会替换为任务概览页面。",
  "task-detail": "后续 DEV-05 会替换为任务详情页面。",
  "task-report": "后续 DEV-05/DEV-11 会替换为进度汇报页面。",
  "task-review": "后续 DEV-05/DEV-13 会替换为任务验收页面。",
  "task-decomposition": "后续 DEV-09 会替换为承办人接受后的 AI 拆解状态页。",
  "create-details": "后续 DEV-07/DEV-08 会替换为描述任务与信息确认页面。",
  "create-confirm": "后续 DEV-08 会替换为确认发送页面。",
  notifications: "后续 DEV-15 会替换为通知中心页面。",
  profile: "后续 DEV-15 会替换为个人中心页面。",
  "executive-employee-tasks": "后续 DEV-17 会替换为员工负荷任务明细页面。",
};

export function LoginRoute() {
  const { user } = useAuth();
  const location = useLocation();
  const source = readReturnSourceState(location.state);

  if (user) return <Navigate to={resolveReturnTarget(source)} replace />;

  return (
    <main className="stb-login-shell">
      <Card>
        <Typography variant="caption" as="p">SMARTTASKBOARD V1.1</Typography>
        <Typography variant="pageTitle" as="h1">登录</Typography>
        <Typography variant="body" as="p">
          当前为 DEV-02 路由入口占位。正式登录、当前用户和权限投影在 DEV-06 完成。
        </Typography>
        {source && (
          <Typography variant="caption" as="p">
            登录后返回：{resolveReturnTarget(source)}
          </Typography>
        )}
      </Card>
    </main>
  );
}

export function RoutePlaceholder() {
  const location = useLocation();
  const params = useParams();
  const contract = findRouteContract(location.pathname);

  if (!contract) return <NotFoundRoute />;

  return (
    <section className="stb-route-placeholder" data-testid="route-contract">
      <Card>
        <Typography variant="caption" as="p">Route Contract Placeholder</Typography>
        <Typography variant="sectionTitle" as="h2">{contract.title}</Typography>
        <Typography variant="body" as="p">{placeholderCopy[contract.id]}</Typography>
        <dl className="stb-route-placeholder__facts">
          <div>
            <dt>Route</dt>
            <dd>{contract.path}</dd>
          </div>
          {params.taskId && (
            <div>
              <dt>taskId</dt>
              <dd>{params.taskId}</dd>
            </div>
          )}
          <div>
            <dt>Business API</dt>
            <dd>No</dd>
          </div>
        </dl>
      </Card>
    </section>
  );
}

export function ForbiddenRoute() {
  const { goBack, target } = useReturnNavigation();

  return (
    <ErrorState
      title="无权限访问"
      detail="当前身份无权查看该页面。前端仅做导航边界，最终权限以后端校验为准。"
      action={<Button variant="secondary" onClick={goBack}>安全返回 {target}</Button>}
    />
  );
}

export function NotFoundRoute() {
  const { goBack, target } = useReturnNavigation();

  return (
    <EmptyState
      title="页面不存在"
      detail="该地址不是 SmartTaskBoard V1.1 的正式生产路由。"
      action={<Button variant="secondary" onClick={goBack}>安全返回 {target}</Button>}
    />
  );
}
