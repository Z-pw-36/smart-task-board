import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../api/client";
import {
  confirmTaskPlan,
  decomposeTaskPlan,
  getAvailableActions,
  getTaskDetail,
  getTaskStatusLogs,
  listUsers,
} from "../api/endpoints";
import {
  actionLabels,
  mergeTask,
  runNodeAction,
  runTaskAction,
  type TaskLifecycleAction,
} from "../api/taskActions";
import type {
  AllowedAction,
  ConfirmTaskPlanningPayload,
  PrototypeUser,
  TaskDetail,
  TaskPlanningSuggestionResponse,
} from "../api/types";
import { ChangeRequestsPanel } from "../components/ChangeRequestsPanel";
import { CompletionReviewsPanel } from "../components/CompletionReviewsPanel";
import { EmptyState, ErrorState, LoadingState } from "../components/Feedback";
import { ProgressIssuesPanel } from "../components/ProgressIssuesPanel";
import { formatDate } from "../components/task-card-utils";

const reasonActions = new Set<TaskLifecycleAction>([
  "return",
  "cancel_task",
  "withdraw_task",
  "close_task",
  "restore_task",
  "merge_task",
]);

type LifecycleForm = {
  action: TaskLifecycleAction;
  reason: string;
  targetTaskId: string;
};

type PlanningNodeForm = {
  node_id: string;
  client_node_id: string;
  node_order: number;
  node_name: string;
  action_detail: string;
  tools_or_materials: string;
  suggested_owner_employee_no: string;
  owner_employee_no: string;
  planned_start_time: string;
  planned_deadline: string;
  estimated_hours: string;
  deliverable: string;
  acceptance_criteria: string;
  dependency_node_id: string;
  enabled: boolean;
};

export function TaskDetailPage() {
  const { taskId = "" } = useParams();
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState("");
  const [planningNotice, setPlanningNotice] = useState("");
  const [planningNodes, setPlanningNodes] = useState<PlanningNodeForm[]>([]);
  const [planningErrors, setPlanningErrors] = useState<Record<string, string>>({});
  const [lifecycleForm, setLifecycleForm] = useState<LifecycleForm | null>(null);
  const detail = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => getTaskDetail(taskId),
    enabled: Boolean(taskId),
  });
  const actions = useQuery({
    queryKey: ["task-actions", taskId],
    queryFn: () => getAvailableActions(taskId),
    enabled: Boolean(taskId),
  });
  const logs = useQuery({
    queryKey: ["task-logs", taskId],
    queryFn: () => getTaskStatusLogs(taskId),
    enabled: Boolean(taskId),
  });
  const users = useQuery({
    queryKey: ["users"],
    queryFn: listUsers,
    enabled: Boolean(taskId),
  });

  const planningMutation = useMutation({
    mutationFn: () => decomposeTaskPlan(taskId, {}),
    onSuccess: (result) => {
      setPlanningNodes(planningNodesFromSuggestion(result));
      setPlanningErrors({});
      setPlanningNotice(`AI 已生成 ${result.suggested_nodes.length} 个建议执行节点，请人工确认负责人和截止时间。`);
    },
    onError: (error) => setPlanningNotice(errorMessage(error)),
  });

  const confirmPlanningMutation = useMutation({
    mutationFn: () => {
      if (!detail.data || !actions.data) {
        throw new Error("无法读取任务版本，请刷新页面。");
      }
      return confirmTaskPlan(
        taskId,
        buildPlanningPayload(detail.data, planningNodes, actions.data.task_version),
      );
    },
    onSuccess: async () => {
      setPlanningNotice("任务规划已确认，节点已进入正式执行。");
      setPlanningNodes([]);
      await refreshQueries(queryClient, taskId);
    },
    onError: (error) => setPlanningNotice(errorMessage(error)),
  });

  const mutation = useMutation({
    mutationFn: async ({
      action,
      nodeId,
      reason,
      targetTaskId,
    }: {
      action: AllowedAction;
      nodeId?: string;
      reason?: string;
      targetTaskId?: string;
    }) => {
      const version = actions.data?.task_version ?? detail.data?.task_version;
      if (!version) throw new Error("无法读取任务版本，请刷新页面。");
      if (nodeId) {
        let progress: number | undefined;
        if (action === "update_node_progress") {
          const input = window.prompt("请输入进度（0-100）", "50");
          if (input === null) throw new Error("已取消进度更新。");
          progress = Number(input);
          if (!Number.isInteger(progress) || progress < 0 || progress > 100) {
            throw new Error("进度必须是 0 到 100 的整数。");
          }
        }
        if (!isNodeExecutionAction(action)) {
          throw new Error("该节点动作需要在验收返工区域处理。");
        }
        await runNodeAction(taskId, nodeId, action, version, progress);
        return;
      }
      if (!isTaskLifecycleAction(action)) {
        throw new Error("该任务动作需要填写完整的业务信息。");
      }
      if (action === "merge_task") {
        if (!targetTaskId?.trim() || !reason?.trim()) {
          throw new Error("合并任务必须填写目标任务和原因。");
        }
        await mergeTask(taskId, targetTaskId.trim(), version, reason.trim());
        return;
      }
      await runTaskAction(taskId, action, version, reason?.trim());
    },
    onSuccess: async () => {
      setNotice("操作成功。");
      setLifecycleForm(null);
      await refreshQueries(queryClient, taskId);
    },
    onError: (error) =>
      setNotice(
        error instanceof ApiError && error.status === 409
          ? "任务已被其他操作更新，请刷新后重试。"
          : error instanceof Error
            ? error.message
            : "操作未完成。",
      ),
  });

  if (detail.isLoading || actions.isLoading) return <LoadingState label="正在加载任务详情..." />;
  if (detail.isError || actions.isError) {
    return (
      <ErrorState
        error={detail.error || actions.error}
        retry={() => void Promise.all([detail.refetch(), actions.refetch()])}
      />
    );
  }
  if (!detail.data || !actions.data) return <EmptyState title="任务不存在" detail="该任务可能已不可见。" />;

  const task = detail.data;
  const canPlanTask = actions.data.allowed_actions.includes("plan_task");
  const availableUsers = Array.isArray(users.data) ? users.data : [];
  const ownerOptions = taskPlanningOwnerOptions(task, availableUsers);
  const nodeActions = new Map(actions.data.nodes.map((item) => [item.node_id, item.allowed_actions]));

  function openLifecycleForm(action: TaskLifecycleAction) {
    if (reasonActions.has(action)) {
      setLifecycleForm({ action, reason: "", targetTaskId: "" });
      return;
    }
    mutation.mutate({ action });
  }

  function submitLifecycleForm(event: FormEvent) {
    event.preventDefault();
    if (!lifecycleForm) return;
    if (reasonActions.has(lifecycleForm.action) && !lifecycleForm.reason.trim()) {
      setNotice(lifecycleForm.action === "merge_task" ? "合并任务必须填写原因。" : "此操作必须填写原因。");
      return;
    }
    if (lifecycleForm.action === "merge_task" && !lifecycleForm.targetTaskId.trim()) {
      setNotice("合并任务必须填写目标任务。");
      return;
    }
    mutation.mutate({ ...lifecycleForm });
  }

  function updatePlanningNode(index: number, patch: Partial<PlanningNodeForm>) {
    setPlanningNodes((current) =>
      current.map((node, nodeIndex) => (nodeIndex === index ? { ...node, ...patch } : node)),
    );
  }

  function addPlanningNode() {
    setPlanningNodes((current) => [
      ...current,
      blankPlanningNode(current.length + 1),
    ]);
  }

  function removePlanningNode(index: number) {
    const removed = planningNodes[index];
    setPlanningNodes((current) =>
      current
        .filter((_, nodeIndex) => nodeIndex !== index)
        .map((node, nodeIndex) => ({
          ...node,
          node_order: nodeIndex + 1,
          dependency_node_id:
            node.dependency_node_id === removed.node_id ? "" : node.dependency_node_id,
        })),
    );
  }

  function savePlanningDraft() {
    window.localStorage.setItem(
      `smart-task-board:planning:${task.task_id}`,
      JSON.stringify(planningNodes),
    );
    setPlanningNotice("任务规划草稿已保存到本机。");
  }

  function submitPlanning(event: FormEvent) {
    event.preventDefault();
    const validation = validatePlanningNodes(task, planningNodes);
    setPlanningErrors(validation.errors);
    if (!validation.ok) return;
    confirmPlanningMutation.mutate();
  }

  return (
    <div className="page-stack narrow-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">{task.task_no || "未编号任务"} · v{task.task_version}</p>
          <h1>{task.task_name}</h1>
          <p>{task.task_goal || "暂无任务目标"}</p>
        </div>
        <span className={`status-pill status-${task.status}`}>{task.status}</span>
      </header>
      {notice && <div className="notice" role="status">{notice}</div>}
      <section className="detail-panel">
        <h2>任务概况</h2>
        <dl className="detail-grid">
          <div><dt>创建人</dt><dd>{task.creator_employee_no}</dd></div>
          <div><dt>主承办人</dt><dd>{task.main_assignee_employee_no || "未指定"}</dd></div>
          <div><dt>验收人</dt><dd>{task.reviewer_employee_no || task.creator_employee_no}</dd></div>
          <div><dt>截止</dt><dd>{formatDate(task.deadline)}</dd></div>
          <div><dt>预计工时</dt><dd>{task.estimated_hours || "未设置"}</dd></div>
          <div><dt>交付物</dt><dd>{task.deliverable || "未设置"}</dd></div>
        </dl>
        <div className="long-text"><strong>验收标准</strong><p>{task.acceptance_criteria || "未设置"}</p></div>
        <div className="action-row">
          {actions.data.allowed_actions.filter(isTaskLifecycleAction).map((action) => (
            <button
              className="button primary"
              disabled={mutation.isPending}
              type="button"
              key={action}
              onClick={() => openLifecycleForm(action)}
            >
              {actionLabels[action]}
            </button>
          ))}
        </div>
      </section>

      {lifecycleForm && (
        <form className="detail-panel lifecycle-action-form" onSubmit={submitLifecycleForm} aria-busy={mutation.isPending}>
          <div className="section-heading">
            <h2>{actionLabels[lifecycleForm.action]}</h2>
            <button className="text-button" type="button" onClick={() => setLifecycleForm(null)}>取消</button>
          </div>
          {lifecycleForm.action === "merge_task" && (
            <label>
              目标任务 ID
              <input
                required
                value={lifecycleForm.targetTaskId}
                onChange={(event) => setLifecycleForm({ ...lifecycleForm, targetTaskId: event.target.value })}
              />
            </label>
          )}
          <label>
            {lifecycleForm.action === "merge_task" ? "合并原因" : "操作原因"}
            <textarea
              required
              value={lifecycleForm.reason}
              onChange={(event) => setLifecycleForm({ ...lifecycleForm, reason: event.target.value })}
            />
          </label>
          <button className="button primary" disabled={mutation.isPending} type="submit">
            {mutation.isPending ? "正在处理..." : `确认${actionLabels[lifecycleForm.action]}`}
          </button>
        </form>
      )}

      {canPlanTask && (
        <section className="form-section" aria-labelledby="task-planning-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">主承办人</p>
              <h2 id="task-planning-heading">任务规划</h2>
              <p className="muted">AI 已生成建议执行节点后，需要人工选择节点负责人和截止时间。</p>
            </div>
            <span className="status-pill">已生成 {planningNodes.length} 个建议节点</span>
          </div>
          {planningNotice && <div className="notice" role="status">{planningNotice}</div>}
          {planningErrors.form && <div className="notice notice-error" role="alert">{planningErrors.form}</div>}
          <div className="action-row">
            <button
              className="button primary"
              disabled={planningMutation.isPending}
              type="button"
              onClick={() => planningMutation.mutate()}
            >
              {planningMutation.isPending ? "正在生成..." : "重新生成建议"}
            </button>
            <button
              className="button secondary"
              type="button"
              onClick={addPlanningNode}
            >
              增加节点
            </button>
            <button
              className="button secondary"
              disabled={planningNodes.length === 0}
              type="button"
              onClick={savePlanningDraft}
            >
              保存草稿
            </button>
          </div>
          <form className="node-editor-list planning-editor" onSubmit={submitPlanning}>
            {planningNodes.map((node, index) => (
              <fieldset className="node-editor" key={node.node_id} disabled={confirmPlanningMutation.isPending}>
                <legend>节点 {index + 1}</legend>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={node.enabled}
                    onChange={(event) => updatePlanningNode(index, { enabled: event.target.checked })}
                  />
                  启用
                </label>
                <div className="form-grid">
                  <label>
                    节点名称 *
                    <input
                      value={node.node_name}
                      onChange={(event) => updatePlanningNode(index, { node_name: event.target.value })}
                    />
                    {planningErrors[`${node.node_id}:name`] && (
                      <span className="field-error">{planningErrors[`${node.node_id}:name`]}</span>
                    )}
                  </label>
                  <label>
                    节点负责人 *
                    <select
                      value={node.owner_employee_no}
                      onChange={(event) =>
                        updatePlanningNode(index, { owner_employee_no: event.target.value })
                      }
                    >
                      <option value="">请选择负责人</option>
                      {ownerOptions.map((option) => (
                        <option key={option.employee_no} value={option.employee_no}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    {node.suggested_owner_employee_no && (
                      <span className="muted">AI 建议：{node.suggested_owner_employee_no}</span>
                    )}
                    {planningErrors[`${node.node_id}:owner`] && (
                      <span className="field-error">{planningErrors[`${node.node_id}:owner`]}</span>
                    )}
                  </label>
                  <label>
                    节点截止时间 *
                    <input
                      type="datetime-local"
                      value={node.planned_deadline}
                      onChange={(event) =>
                        updatePlanningNode(index, { planned_deadline: event.target.value })
                      }
                    />
                    {planningErrors[`${node.node_id}:deadline`] && (
                      <span className="field-error">{planningErrors[`${node.node_id}:deadline`]}</span>
                    )}
                  </label>
                  <label>
                    依赖节点
                    <select
                      value={node.dependency_node_id}
                      onChange={(event) =>
                        updatePlanningNode(index, { dependency_node_id: event.target.value })
                      }
                    >
                      <option value="">无</option>
                      {planningNodes
                        .filter((candidate) => candidate.enabled && candidate.node_id !== node.node_id)
                        .map((candidate) => (
                          <option key={candidate.node_id} value={candidate.node_id}>
                            {candidate.node_name || `节点 ${candidate.node_order}`}
                          </option>
                        ))}
                    </select>
                  </label>
                  <label>
                    预计工时
                    <input
                      type="number"
                      min="0"
                      step="0.5"
                      value={node.estimated_hours}
                      onChange={(event) =>
                        updatePlanningNode(index, { estimated_hours: event.target.value })
                      }
                    />
                  </label>
                  <label className="span-two">
                    节点描述
                    <textarea
                      value={node.action_detail}
                      onChange={(event) =>
                        updatePlanningNode(index, { action_detail: event.target.value })
                      }
                    />
                  </label>
                  <label className="span-two">
                    预计交付
                    <input
                      value={node.deliverable}
                      onChange={(event) => updatePlanningNode(index, { deliverable: event.target.value })}
                    />
                  </label>
                  <label className="span-two">
                    验收标准
                    <textarea
                      value={node.acceptance_criteria}
                      onChange={(event) =>
                        updatePlanningNode(index, { acceptance_criteria: event.target.value })
                      }
                    />
                  </label>
                  <label className="span-two">
                    工具或资料
                    <input
                      value={node.tools_or_materials}
                      onChange={(event) =>
                        updatePlanningNode(index, { tools_or_materials: event.target.value })
                      }
                    />
                  </label>
                </div>
                <button
                  className="text-button danger-text"
                  type="button"
                  onClick={() => removePlanningNode(index)}
                >
                  删除节点
                </button>
              </fieldset>
            ))}
            <div className="form-actions">
              <button
                className="button primary"
                disabled={confirmPlanningMutation.isPending || planningNodes.length === 0}
                type="submit"
              >
                {confirmPlanningMutation.isPending ? "正在确认..." : "确认任务规划"}
              </button>
            </div>
          </form>
        </section>
      )}

      <section>
        <div className="section-heading"><h2>执行节点</h2><span>{task.nodes.length} 个</span></div>
        <div className="node-list">
          {task.nodes.map((node) => (
            <article className="node-card" key={node.node_id}>
              <div className="node-order">{node.node_order}</div>
              <div className="node-content">
                <h3>{node.node_name}</h3>
                <p>{node.action_detail || "暂无动作说明"}</p>
                <div className="progress-track" aria-label={`进度 ${node.progress_percent}%`}><span style={{ width: `${node.progress_percent}%` }} /></div>
                <p className="muted">负责人：{node.owner_employee_no || task.main_assignee_employee_no || "未指定"} · 截止：{formatDate(node.planned_deadline)} · {node.status} · {node.progress_percent}%</p>
                <p><strong>交付：</strong>{node.deliverable || "未设置"}</p>
                <p><strong>验收：</strong>{node.acceptance_criteria || "未设置"}</p>
                <div className="action-row">
                  {(nodeActions.get(node.node_id) || []).filter(isNodeExecutionAction).map((action) => (
                    <button className="button secondary" disabled={mutation.isPending} type="button" key={action} onClick={() => mutation.mutate({ action, nodeId: node.node_id })}>
                      {actionLabels[action]}
                    </button>
                  ))}
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>
      <section className="detail-panel">
        <h2>参与人与依赖</h2>
        <p>任务参与人：{task.participants.map((item) => `${item.employee_no} (${item.participant_role})`).join("、") || "无"}</p>
        <p>节点参与人：{task.node_participants.map((item) => `${item.employee_no} (${item.participant_role})`).join("、") || "无"}</p>
        <p>依赖数：{task.dependencies.length}</p>
      </section>
      <ProgressIssuesPanel task={task} actions={actions.data} />
      <CompletionReviewsPanel task={task} actions={actions.data} />
      <ChangeRequestsPanel task={task} actions={actions.data} />
      <section>
        <div className="section-heading"><h2>状态日志</h2><button className="text-button" type="button" onClick={() => void logs.refetch()}>刷新</button></div>
        {logs.isLoading && <LoadingState label="正在加载状态日志..." />}
        {logs.isError && <ErrorState error={logs.error} retry={() => void logs.refetch()} />}
        {logs.data?.items.length === 0 && <EmptyState title="暂无状态日志" detail="状态发生变化后会记录在这里。" />}
        <ol className="timeline">
          {logs.data?.items.map((log) => (
            <li key={log.status_log_id}><strong>{log.action_type}</strong><span>{log.from_status || "初始"} → {log.to_status}</span><small>{log.operator_employee_no || "SYSTEM"} · {formatDate(log.created_at)}</small></li>
          ))}
        </ol>
      </section>
      <Link className="text-link" to="/tasks">返回我的任务</Link>
    </div>
  );
}

async function refreshQueries(queryClient: ReturnType<typeof useQueryClient>, taskId: string) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["task", taskId] }),
    queryClient.invalidateQueries({ queryKey: ["task-actions", taskId] }),
    queryClient.invalidateQueries({ queryKey: ["task-logs", taskId] }),
    queryClient.invalidateQueries({ queryKey: ["tasks"] }),
    queryClient.invalidateQueries({ queryKey: ["inbox"] }),
    queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
  ]);
}

function planningNodesFromSuggestion(
  suggestion: TaskPlanningSuggestionResponse,
): PlanningNodeForm[] {
  const nodes = suggestion.suggested_nodes.map((node, index) => ({
    node_id: crypto.randomUUID(),
    client_node_id: node.client_node_id,
    node_order: index + 1,
    node_name: node.node_name || "",
    action_detail: node.action_detail || "",
    tools_or_materials: node.tools_or_materials || "",
    suggested_owner_employee_no: node.suggested_owner_employee_no || "",
    owner_employee_no: "",
    planned_start_time: toDateTimeLocal(node.planned_start_time),
    planned_deadline: toDateTimeLocal(node.planned_deadline),
    estimated_hours: node.estimated_hours || "",
    deliverable: node.deliverable || "",
    acceptance_criteria: node.acceptance_criteria || "",
    dependency_node_id: "",
    enabled: node.enabled,
  }));
  const byClientId = new Map(nodes.map((node) => [node.client_node_id, node]));
  for (const dependency of suggestion.suggested_dependencies) {
    const predecessor = byClientId.get(dependency.predecessor_client_node_id);
    const successor = byClientId.get(dependency.successor_client_node_id);
    if (predecessor && successor && !successor.dependency_node_id) {
      successor.dependency_node_id = predecessor.node_id;
    }
  }
  suggestion.suggested_nodes.forEach((node, index) => {
    if (nodes[index].dependency_node_id || node.dependencies.length === 0) return;
    const predecessor = byClientId.get(node.dependencies[0]);
    if (predecessor) nodes[index].dependency_node_id = predecessor.node_id;
  });
  return nodes;
}

function blankPlanningNode(order: number): PlanningNodeForm {
  return {
    node_id: crypto.randomUUID(),
    client_node_id: `manual-node-${order}`,
    node_order: order,
    node_name: "",
    action_detail: "",
    tools_or_materials: "",
    suggested_owner_employee_no: "",
    owner_employee_no: "",
    planned_start_time: "",
    planned_deadline: "",
    estimated_hours: "",
    deliverable: "",
    acceptance_criteria: "",
    dependency_node_id: "",
    enabled: true,
  };
}

function buildPlanningPayload(
  task: TaskDetail,
  planningNodes: PlanningNodeForm[],
  version: number,
): ConfirmTaskPlanningPayload {
  const validation = validatePlanningNodes(task, planningNodes);
  if (!validation.ok) throw new Error(Object.values(validation.errors)[0]);
  const enabledNodes = planningNodes.filter((node) => node.enabled);
  const enabledIds = new Set(enabledNodes.map((node) => node.node_id));
  return {
    expected_task_version: version,
    nodes: enabledNodes.map((node, index) => ({
      node_id: node.node_id,
      node_order: index + 1,
      node_name: node.node_name.trim(),
      action_detail: node.action_detail || null,
      tools_or_materials: node.tools_or_materials || null,
      owner_employee_no: node.owner_employee_no,
      planned_start_time: node.planned_start_time
        ? new Date(node.planned_start_time).toISOString()
        : null,
      planned_deadline: new Date(node.planned_deadline).toISOString(),
      estimated_hours: node.estimated_hours || null,
      deliverable: node.deliverable || null,
      acceptance_criteria: node.acceptance_criteria || null,
      enabled: true,
    })),
    dependencies: enabledNodes.flatMap((node) =>
      node.dependency_node_id && enabledIds.has(node.dependency_node_id)
        ? [{
            dependency_id: crypto.randomUUID(),
            predecessor_node_id: node.dependency_node_id,
            successor_node_id: node.node_id,
            dependency_type: "finish_to_start",
          }]
        : [],
    ),
    node_participants: [],
  };
}

function validatePlanningNodes(
  task: TaskDetail,
  planningNodes: PlanningNodeForm[],
): { ok: boolean; errors: Record<string, string> } {
  const errors: Record<string, string> = {};
  const enabledNodes = planningNodes.filter((node) => node.enabled);
  if (enabledNodes.length === 0) {
    errors.form = "至少需要一个启用节点。";
  }
  const taskDeadline = task.deadline ? new Date(task.deadline) : null;
  if (!taskDeadline || Number.isNaN(taskDeadline.getTime())) {
    errors.form = "任务必须先设置总截止时间，才能确认节点规划。";
  }
  const deadlines = new Map<string, Date>();
  enabledNodes.forEach((node) => {
    if (!node.node_name.trim()) errors[`${node.node_id}:name`] = "请输入节点名称。";
    if (!node.owner_employee_no) errors[`${node.node_id}:owner`] = "请选择节点负责人。";
    if (!node.planned_deadline) {
      errors[`${node.node_id}:deadline`] = "请选择节点截止时间。";
      return;
    }
    const deadline = new Date(node.planned_deadline);
    if (Number.isNaN(deadline.getTime())) {
      errors[`${node.node_id}:deadline`] = "节点截止时间无效。";
      return;
    }
    if (taskDeadline && deadline > taskDeadline) {
      errors[`${node.node_id}:deadline`] = "节点截止时间不能晚于任务截止时间。";
    }
    deadlines.set(node.node_id, deadline);
  });
  enabledNodes.forEach((node) => {
    if (!node.dependency_node_id) return;
    const predecessorDeadline = deadlines.get(node.dependency_node_id);
    const nodeDeadline = deadlines.get(node.node_id);
    if (predecessorDeadline && nodeDeadline && predecessorDeadline > nodeDeadline) {
      errors[`${node.node_id}:deadline`] = "依赖节点截止时间不能晚于当前节点。";
    }
  });
  return { ok: Object.keys(errors).length === 0, errors };
}

function taskPlanningOwnerOptions(
  task: TaskDetail,
  users: PrototypeUser[],
): Array<{ employee_no: string; label: string }> {
  const employeeNos = new Set<string>();
  [
    task.creator_employee_no,
    task.main_assignee_employee_no,
    task.report_to_employee_no,
    task.reviewer_employee_no,
  ].forEach((employeeNo) => {
    if (employeeNo) employeeNos.add(employeeNo);
  });
  task.participants.forEach((participant) => employeeNos.add(participant.employee_no));
  const byEmployeeNo = new Map(users.map((user) => [user.employee_no, user]));
  return [...employeeNos].map((employeeNo) => {
    const user = byEmployeeNo.get(employeeNo);
    return {
      employee_no: employeeNo,
      label: user ? `${user.name} · ${employeeNo}` : employeeNo,
    };
  });
}

function toDateTimeLocal(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString().slice(0, 16);
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 409) {
    return "任务版本或业务状态已变化，请刷新后重试。";
  }
  return error instanceof Error ? error.message : "操作未完成。";
}

function isTaskLifecycleAction(action: AllowedAction): action is TaskLifecycleAction {
  return [
    "submit_for_confirmation",
    "confirm_and_send",
    "confirm_self_assigned",
    "accept",
    "return",
    "resend",
    "cancel_task",
    "withdraw_task",
    "close_task",
    "archive_task",
    "restore_task",
    "merge_task",
  ].includes(action);
}

function isNodeExecutionAction(
  action: AllowedAction,
): action is "start_node" | "update_node_progress" | "complete_node" {
  return ["start_node", "update_node_progress", "complete_node"].includes(action);
}
