/**
 * Feature: V1.1 task detail page.
 * Responsibilities: render the formal read-only task detail, five modules, permission projection, return state, and node anchors.
 * Does not own: task mutations, AI decomposition, node execution, or lifecycle state changes.
 * Plan task: DEV-05.
 */

import { useEffect, useMemo, useState } from "react";
import { useLocation, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, ErrorState, Sheet, Skeleton, Typography } from "../../shared/components";
import { useReturnNavigation } from "../../app/return-state";
import { useTaskDetailBundle } from "./hooks";
import {
  BasicInfoSection,
  NodesSection,
  OperationLogsSection,
  PeopleSection,
  PerformanceSection,
  PermissionActions,
  ProgressSection,
  ReadOnlyBanner,
  TaskSummaryCard,
  TimelineSection,
} from "./TaskDetailParts";
import { detailModules, type DetailModuleId } from "./format";
import "./TaskDetailPage.css";

const scrollKeyPrefix = "smarttaskboard.task-detail.scroll.";

function LoadingDetail() {
  return (
    <section className="stb-task-detail stb-task-detail--loading" aria-label="正在加载任务详情">
      <Skeleton height={104} />
      <Skeleton height={56} />
      <Skeleton height={180} />
      <Skeleton height={220} />
    </section>
  );
}

function errorTitle(error: unknown) {
  if (error instanceof ApiError && error.status === 403) return "无权限查看任务";
  if (error instanceof ApiError && error.status === 404) return "任务不存在";
  return "任务详情暂时无法加载";
}

export function TaskDetailPage() {
  const { taskId = "" } = useParams();
  const location = useLocation();
  const [activeModule, setActiveModule] = useState<DetailModuleId>("overview");
  const [moreOpen, setMoreOpen] = useState(false);
  const { goBack, target } = useReturnNavigation("/tasks");
  const query = useTaskDetailBundle(taskId);

  const latestReport = useMemo(() => {
    return [...(query.data?.reports ?? [])].sort((left, right) => right.created_at.localeCompare(left.created_at))[0];
  }, [query.data?.reports]);

  useEffect(() => {
    const saved = sessionStorage.getItem(`${scrollKeyPrefix}${taskId}`);
    if (saved) requestAnimationFrame(() => window.scrollTo(0, Number(saved) || 0));
    return () => {
      if (taskId) sessionStorage.setItem(`${scrollKeyPrefix}${taskId}`, String(window.scrollY));
    };
  }, [taskId]);

  useEffect(() => {
    if (!query.data) return;
    const hash = decodeURIComponent(location.hash.replace(/^#/, ""));
    if (!hash.startsWith("node-")) return;
    requestAnimationFrame(() => {
      const node = document.getElementById(hash);
      if (!node) return;
      node.scrollIntoView({ block: "center" });
      node.focus({ preventScroll: true });
      setActiveModule("nodes");
    });
  }, [location.hash, query.data]);

  useEffect(() => {
    function onScroll() {
      let visible: DetailModuleId | undefined;
      detailModules.forEach((item) => {
        const element = document.getElementById(item.targetId);
        if (!element) return;
        const box = element.getBoundingClientRect();
        if (box.top <= 140) visible = item.id;
      });
      if (visible) setActiveModule(visible);
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  function goToModule(moduleId: DetailModuleId, targetId: string) {
    setActiveModule(moduleId);
    document.getElementById(targetId)?.scrollIntoView({ block: "start" });
  }

  if (query.isLoading) return <LoadingDetail />;

  if (query.isError) {
    return (
      <ErrorState
        title={errorTitle(query.error)}
        detail={query.error instanceof ApiError ? query.error.message : "请稍后重试；内部错误细节不会展示在页面上。"}
        action={<Button variant="secondary" onClick={() => void query.refetch()}>重试</Button>}
      />
    );
  }

  if (!query.data) return <ErrorState title="任务详情暂时无法加载" detail="服务端没有返回任务详情。" />;

  const { task, actions, logs, reports, issues } = query.data;
  return (
    <section className="stb-task-detail" data-testid="task-detail-page">
      <div className="stb-task-detail-head">
        <Button variant="ghost" onClick={goBack}>返回</Button>
        <Typography variant="caption" as="p">返回目标：{target}</Typography>
        <Button variant="secondary" aria-label="更多操作" onClick={() => setMoreOpen(true)}>更多</Button>
      </div>
      <ReadOnlyBanner>DEV-05 仅展示真实只读数据和权限投影；业务写操作会在后续阶段启用。</ReadOnlyBanner>
      <TaskSummaryCard task={task} latestReport={latestReport} />
      <nav className="stb-task-detail-tabs" aria-label="任务详情模块" role="tablist">
        {detailModules.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={activeModule === item.id}
            className={activeModule === item.id ? "stb-task-detail-tab stb-task-detail-tab--active" : "stb-task-detail-tab"}
            onClick={() => goToModule(item.id, item.targetId)}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <TimelineSection logs={logs} />
      <OperationLogsSection logs={task.operation_logs ?? []} />
      <BasicInfoSection task={task} nodeCount={task.nodes.length} />
      <PeopleSection task={task} />
      <NodesSection task={task} />
      <ProgressSection reports={reports} issues={issues} />
      <PerformanceSection matches={task.performance_matches ?? []} />
      <PermissionActions task={task} actions={actions.allowed_actions} />
      <Sheet open={moreOpen} title="更多任务操作" onClose={() => setMoreOpen(false)}>
        <div className="stb-task-detail-more">
          <p>任务编号：{task.task_no ?? task.task_id}</p>
          <p>权限来源：/api/v1/tasks/{task.task_id}/available-actions</p>
          {actions.allowed_actions.length === 0 ? (
            <Button variant="secondary" disabled>当前无可执行操作</Button>
          ) : (
            actions.allowed_actions.map((action) => (
              <Button key={action} variant="secondary" disabled>{action}（后续阶段启用）</Button>
            ))
          )}
        </div>
      </Sheet>
    </section>
  );
}
