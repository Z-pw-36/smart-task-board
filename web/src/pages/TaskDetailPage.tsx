import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError, apiRequest } from "../api/client";
import { actionLabels, runNodeAction, runTaskAction } from "../api/taskActions";
import type { AllowedAction, AvailableActions, StatusLogPage, TaskDetail } from "../api/types";
import { EmptyState, ErrorState, LoadingState } from "../components/Feedback";
import { formatDate } from "../components/task-card-utils";

export function TaskDetailPage() {
  const { taskId = "" } = useParams();
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState("");
  const detail = useQuery({ queryKey: ["task", taskId], queryFn: () => apiRequest<TaskDetail>(`/api/v1/tasks/${taskId}`), enabled: Boolean(taskId) });
  const actions = useQuery({ queryKey: ["task-actions", taskId], queryFn: () => apiRequest<AvailableActions>(`/api/v1/tasks/${taskId}/available-actions`), enabled: Boolean(taskId) });
  const logs = useQuery({ queryKey: ["task-logs", taskId], queryFn: () => apiRequest<StatusLogPage>(`/api/v1/tasks/${taskId}/status-logs?limit=50&offset=0`), enabled: Boolean(taskId) });
  const mutation = useMutation({
    mutationFn: async ({ action, nodeId }: { action: AllowedAction; nodeId?: string }) => {
      const version = actions.data?.task_version || detail.data?.task_version;
      if (!version) throw new Error("无法读取任务版本，请刷新页面。");
      if (nodeId) {
        let progress: number | undefined;
        if (action === "update_node_progress") {
          const input = window.prompt("请输入进度（0-100）", "50");
          if (input === null) throw new Error("已取消进度更新。");
          progress = Number(input);
          if (!Number.isInteger(progress) || progress < 0 || progress > 100) throw new Error("进度必须是 0 到 100 的整数。");
        }
        await runNodeAction(taskId, nodeId, action as "start_node" | "update_node_progress" | "complete_node", version, progress);
      } else {
        let reason: string | undefined;
        if (action === "return") {
          reason = window.prompt("请填写退回原因")?.trim();
          if (!reason) throw new Error("退回必须填写原因。");
        }
        await runTaskAction(taskId, action as Exclude<AllowedAction, "start_node" | "update_node_progress" | "complete_node">, version, reason);
      }
    },
    onSuccess: async () => {
      setNotice("操作成功。");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["task", taskId] }),
        queryClient.invalidateQueries({ queryKey: ["task-actions", taskId] }),
        queryClient.invalidateQueries({ queryKey: ["task-logs", taskId] }),
        queryClient.invalidateQueries({ queryKey: ["tasks"] }),
        queryClient.invalidateQueries({ queryKey: ["inbox"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      ]);
    },
    onError: (error) => setNotice(error instanceof ApiError && error.status === 409 ? "任务已被其他操作更新，请刷新后重试。" : error instanceof Error ? error.message : "操作未完成。"),
  });
  if (detail.isLoading || actions.isLoading) return <LoadingState label="正在加载任务详情…" />;
  if (detail.isError) return <ErrorState error={detail.error} retry={() => void detail.refetch()} />;
  if (!detail.data || !actions.data) return <EmptyState title="任务不存在" detail="该任务可能已不可见。" />;
  const task = detail.data;
  const nodeActions = new Map(actions.data.nodes.map((item) => [item.node_id, item.allowed_actions]));
  return (
    <div className="page-stack narrow-page">
      <header className="page-header"><div><p className="eyebrow">{task.task_no || "未编号任务"} · v{task.task_version}</p><h1>{task.task_name}</h1><p>{task.task_goal || "暂无任务目标"}</p></div><span className={`status-pill status-${task.status}`}>{task.status}</span></header>
      {notice && <div className="notice" role="status">{notice}</div>}
      <section className="detail-panel"><h2>任务概况</h2><dl className="detail-grid"><div><dt>创建人</dt><dd>{task.creator_employee_no}</dd></div><div><dt>主承办人</dt><dd>{task.main_assignee_employee_no || "未指定"}</dd></div><div><dt>验收人</dt><dd>{task.reviewer_employee_no || task.creator_employee_no}</dd></div><div><dt>截止</dt><dd>{formatDate(task.deadline)}</dd></div><div><dt>预计工时</dt><dd>{task.estimated_hours || "未设置"}</dd></div><div><dt>交付物</dt><dd>{task.deliverable || "未设置"}</dd></div></dl><div className="long-text"><strong>验收标准</strong><p>{task.acceptance_criteria || "未设置"}</p></div><div className="action-row">{actions.data.allowed_actions.map((action) => <button className="button primary" disabled={mutation.isPending} key={action} onClick={() => mutation.mutate({ action })}>{actionLabels[action]}</button>)}</div></section>
      <section><div className="section-heading"><h2>执行节点</h2><span>{task.nodes.length} 个</span></div><div className="node-list">{task.nodes.map((node) => <article className="node-card" key={node.node_id}><div className="node-order">{node.node_order}</div><div className="node-content"><h3>{node.node_name}</h3><p>{node.action_detail || "暂无动作说明"}</p><div className="progress-track" aria-label={`进度 ${node.progress_percent}%`}><span style={{ width: `${node.progress_percent}%` }} /></div><p className="muted">负责人：{node.owner_employee_no || task.main_assignee_employee_no || "未指定"} · {node.status} · {node.progress_percent}%</p><p><strong>验收：</strong>{node.acceptance_criteria || "未设置"}</p><div className="action-row">{(nodeActions.get(node.node_id) || []).map((action) => <button className="button secondary" disabled={mutation.isPending} key={action} onClick={() => mutation.mutate({ action, nodeId: node.node_id })}>{actionLabels[action]}</button>)}</div></div></article>)}</div></section>
      <section className="detail-panel"><h2>参与人与依赖</h2><p>任务参与人：{task.participants.map((item) => `${item.employee_no} (${item.participant_role})`).join("、") || "无"}</p><p>节点参与人：{task.node_participants.map((item) => `${item.employee_no} (${item.participant_role})`).join("、") || "无"}</p><p>依赖数：{task.dependencies.length}</p></section>
      <section><div className="section-heading"><h2>状态日志</h2><button className="text-button" onClick={() => void logs.refetch()}>刷新</button></div>{logs.isError && <ErrorState error={logs.error} retry={() => void logs.refetch()} />}{logs.data?.items.length === 0 && <EmptyState title="暂无状态日志" detail="状态发生变化后会记录在这里。" />}<ol className="timeline">{logs.data?.items.map((log) => <li key={log.status_log_id}><strong>{log.action_type}</strong><span>{log.from_status || "初始"} → {log.to_status}</span><small>{log.operator_employee_no || "SYSTEM"} · {formatDate(log.created_at)}</small></li>)}</ol></section>
      <Link className="text-link" to="/tasks">← 返回我的任务</Link>
    </div>
  );
}
