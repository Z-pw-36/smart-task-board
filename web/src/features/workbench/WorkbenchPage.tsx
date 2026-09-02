/**
 * Feature: V1.1 Workbench page.
 * Responsibilities: render the second-version Workbench surface using current-user summary and task APIs.
 * Does not own: task creation workflow, AI extraction, priority calculation, or notification read state.
 * Plan task: DEV-03.
 */

import { Link, useLocation, useNavigate, createSearchParams } from "react-router-dom";

import type { TaskSummary } from "../../api/types";
import { canAccessExecutiveRoutes } from "../../app/navigation";
import { createReturnSource } from "../../app/return-state";
import { useAuth } from "../../auth/useAuth";
import { Badge, Button, Card, EmptyState, ErrorState, Progress, Skeleton, Typography } from "../../shared/components";
import {
  type WorkbenchQuadrant,
  type WorkbenchStatusFilter,
} from "./api";
import { useWorkbenchData } from "./hooks";
import "./WorkbenchPage.css";

const statusLabels: Record<string, string> = {
  draft: "草稿",
  pending_confirmation: "待确认",
  pending_acceptance: "待接受",
  returned: "已退回",
  in_progress: "进行中",
  pending_review: "待验收",
  completed: "已完成",
  archived: "已归档",
  cancelled: "已取消",
  withdrawn: "已撤回",
  merged: "已合并",
  closed: "已关闭",
};

const metricTone: Record<string, "info" | "success" | "warning" | "danger" | "neutral"> = {
  pending_acceptance: "warning",
  in_progress: "info",
  pending_review: "success",
  support: "danger",
};

function taskRoute(taskId: string) {
  return `/task/${encodeURIComponent(taskId)}`;
}

function formatDeadline(value: string | null): string {
  if (!value) return "未设置";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "未设置";
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(date);
}

function readWorkloadScore(value: Record<string, unknown> | null): number | null {
  if (!value) return null;
  const raw = value.workload_score;
  const parsed = typeof raw === "number" ? raw : typeof raw === "string" ? Number(raw) : Number.NaN;
  return Number.isFinite(parsed) ? Math.min(100, Math.max(0, parsed)) : null;
}

function LoadingWorkbench() {
  return (
    <section className="stb-workbench stb-workbench--loading" aria-label="正在加载工作台">
      <Skeleton height={96} />
      <Skeleton height={118} />
      <Skeleton height={186} />
      <Skeleton height={220} />
    </section>
  );
}

function tasksQuery(params: Record<string, string>) {
  return `/tasks?${createSearchParams(params).toString()}`;
}

function WorkbenchHeader({ userName, unreadCount }: { userName: string; unreadCount: number }) {
  const location = useLocation();

  return (
    <section className="stb-workbench-hero" aria-labelledby="workbench-welcome">
      <div>
        <Typography variant="caption" as="p">SMARTTASKBOARD V1.1</Typography>
        <div id="workbench-welcome">
          <Typography variant="sectionTitle" as="h2">早上好，{userName}</Typography>
        </div>
        <Typography variant="secondary" as="p">所有摘要均来自当前账号可访问的任务范围。</Typography>
      </div>
      <Link
        className="stb-workbench-icon-link"
        to="/notifications"
        state={{ source: createReturnSource(location, "工作台") }}
        aria-label={unreadCount > 0 ? `通知，${unreadCount} 条未读` : "通知"}
      >
        N
        {unreadCount > 0 && <span className="stb-workbench-dot" aria-hidden="true" />}
      </Link>
    </section>
  );
}

function Metrics({
  pendingAcceptance,
  inProgress,
  pendingReview,
  supportCount,
}: {
  pendingAcceptance: number;
  inProgress: number;
  pendingReview: number;
  supportCount: number;
}) {
  const items: Array<
    | { id: "pending_acceptance" | "in_progress" | "pending_review"; label: string; value: number; status: WorkbenchStatusFilter }
    | { id: "support"; label: string; value: number; href: string }
  > = [
    { id: "pending_acceptance", label: "待接受", value: pendingAcceptance, status: "pending_acceptance" as const },
    { id: "in_progress", label: "进行中", value: inProgress, status: "in_progress" as const },
    { id: "pending_review", label: "待验收", value: pendingReview, status: "pending_review" as const },
    { id: "support", label: "需要支持", value: supportCount, href: "/tasks?support=open" },
  ];

  return (
    <section className="stb-workbench-section" aria-labelledby="workbench-metrics">
      <div className="stb-workbench-section__head">
        <div id="workbench-metrics">
          <Typography variant="sectionTitle" as="h2">任务指标</Typography>
        </div>
      </div>
      <div className="stb-workbench-metrics">
        {items.map((item) => {
          const className = "stb-workbench-metric";
          if ("href" in item) {
            return (
              <Link key={item.id} className={className} to={item.href} aria-label={`${item.label} ${item.value}，查看任务概览`}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
                <Badge tone={metricTone[item.id]}>查看</Badge>
              </Link>
            );
          }
          return (
            <Link
              key={item.id}
              className={className}
              to={tasksQuery({ status: item.status })}
              aria-label={`${item.label} ${item.value}，按状态查看任务概览`}
            >
              <span>{item.label}</span>
              <strong>{item.value}</strong>
              <Badge tone={metricTone[item.id]}>查看</Badge>
            </Link>
          );
        })}
      </div>
    </section>
  );
}

function Quadrants({
  items,
}: {
  items: Array<{ id: WorkbenchQuadrant; label: string; count: number }>;
}) {
  return (
    <section className="stb-workbench-section" aria-labelledby="workbench-quadrants">
      <div className="stb-workbench-section__head">
        <div id="workbench-quadrants">
          <Typography variant="sectionTitle" as="h2">任务风险四象限</Typography>
        </div>
      </div>
      <div className="stb-workbench-quadrants">
        {items.map((item) => (
          <Link
            key={item.id}
            className={`stb-workbench-quadrant stb-workbench-quadrant--${item.id}`}
            to={tasksQuery({ quadrant: item.id })}
            aria-label={`${item.label} ${item.count}，按象限查看任务概览`}
          >
            <span>{item.label}</span>
            <strong>{item.count}</strong>
          </Link>
        ))}
      </div>
    </section>
  );
}

function SupportCard({
  openIssueCount,
  blockedTaskCount,
  conflictCount,
  workloadScore,
}: {
  openIssueCount: number;
  blockedTaskCount: number;
  conflictCount: number;
  workloadScore: number | null;
}) {
  return (
    <Card className="stb-workbench-support">
      <div className="stb-workbench-support__body">
        <div>
          <Typography variant="sectionTitle" as="h2">需要支持</Typography>
          <Typography variant="secondary" as="p">卡点、逾期和冲突入口统一进入任务概览处理。</Typography>
        </div>
        <div className="stb-workbench-support__numbers" aria-label="支持摘要">
          <span><strong>{openIssueCount}</strong>卡点</span>
          <span><strong>{blockedTaskCount}</strong>受阻</span>
          <span><strong>{conflictCount}</strong>冲突</span>
        </div>
        {workloadScore !== null && <Progress value={workloadScore} label="后端负荷评分" />}
      </div>
      <Link className="stb-workbench-row-link" to="/tasks?support=open">查看需要支持任务</Link>
    </Card>
  );
}

function QuickTaskInput() {
  const location = useLocation();

  return (
    <section className="stb-workbench-ai" aria-labelledby="workbench-ai">
      <div>
        <div id="workbench-ai">
          <Typography variant="sectionTitle" as="h2">AI 任务助手</Typography>
        </div>
        <Typography variant="secondary" as="p">从这里进入正式任务描述与信息确认流程。</Typography>
      </div>
      <div className="stb-workbench-ai__actions">
        <Link className="stb-workbench-primary-link" to="/create/details" state={{ source: createReturnSource(location, "工作台") }}>描述任务</Link>
        <Link
          className="stb-workbench-voice-link"
          to="/create/details"
          state={{ source: createReturnSource(location, "工作台") }}
          aria-label="语音描述任务"
        >
          语音入口
        </Link>
      </div>
    </section>
  );
}

function TaskList({ tasks }: { tasks: TaskSummary[] }) {
  const location = useLocation();

  return (
    <section className="stb-workbench-section" aria-labelledby="workbench-task-list">
      <div className="stb-workbench-section__head">
        <div>
          <div id="workbench-task-list">
            <Typography variant="sectionTitle" as="h2">任务信息管理</Typography>
          </div>
        </div>
        <Link className="stb-workbench-inline-link" to="/tasks" state={{ source: createReturnSource(location, "工作台") }}>全部任务</Link>
      </div>
      {tasks.length === 0 ? (
        <EmptyState title="当前筛选下暂无任务" detail="没有符合当前服务端查询或优先级投影的任务。" />
      ) : (
        <div className="stb-workbench-task-list">
          {tasks.map((task) => (
            <Link
              key={task.task_id}
              className="stb-workbench-task"
              to={taskRoute(task.task_id)}
              state={{ source: createReturnSource(location, "工作台") }}
            >
              <span className="stb-workbench-task__head">
                <Badge tone={task.is_overdue ? "danger" : "info"}>{statusLabels[task.status] ?? task.status}</Badge>
                <span>{task.task_no ?? "未编号"}</span>
              </span>
              <strong>{task.task_name}</strong>
              <span className="stb-workbench-task__meta">
                <span>承办：{task.main_assignee?.name ?? "未指定"}</span>
                <span>截止：{formatDeadline(task.deadline)}</span>
              </span>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}

export function WorkbenchPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const query = useWorkbenchData({});

  if (query.isLoading) return <LoadingWorkbench />;

  if (query.isError) {
    return (
      <ErrorState
        title="工作台暂时无法加载"
        detail="请稍后重试；错误详情已由 API 客户端屏蔽内部信息。"
        action={<Button variant="secondary" onClick={() => void query.refetch()}>重试</Button>}
      />
    );
  }

  if (!query.data) return null;
  const { summary, tasks, quadrants } = query.data;
  const totalSignals = summary.created_task_count + summary.assigned_task_count + summary.inbox_count + summary.unread_notification_count;
  const workloadScore = readWorkloadScore(summary.latest_workload);

  return (
    <div className="stb-workbench" data-testid="workbench-page">
      <WorkbenchHeader userName={user?.name ?? "当前用户"} unreadCount={summary.unread_notification_count} />
      {totalSignals === 0 && tasks.length === 0 ? (
        <EmptyState
          title="暂无工作台数据"
          detail="当前账号没有可见任务、待处理事项或通知。"
          action={<Button onClick={() => navigate("/create/details", { state: { source: createReturnSource(location, "工作台") } })}>创建任务</Button>}
        />
      ) : (
        <>
          <Metrics
            pendingAcceptance={summary.pending_acceptance_count}
            inProgress={summary.in_progress_count}
            pendingReview={summary.completion_review_count}
            supportCount={summary.open_issue_count}
          />
          <Quadrants items={quadrants} />
          <SupportCard
            openIssueCount={summary.open_issue_count}
            blockedTaskCount={summary.blocked_task_count}
            conflictCount={summary.open_conflict_count}
            workloadScore={workloadScore}
          />
          <QuickTaskInput />
          {canAccessExecutiveRoutes(user) && (
            <Link className="stb-workbench-executive" to="/executive" state={{ source: createReturnSource(location, "工作台") }}>
              团队态势
            </Link>
          )}
          <TaskList tasks={tasks} />
        </>
      )}
    </div>
  );
}
