import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError, apiRequest } from "../api/client";
import type { PrototypeUser } from "../api/types";
import { ErrorState } from "../components/Feedback";

interface DraftNode {
  node_id: string;
  node_name: string;
  owner_employee_no: string;
  estimated_hours: string;
  deliverable: string;
  acceptance_criteria: string;
  depends_on: string;
}

function newNode(): DraftNode {
  return { node_id: crypto.randomUUID(), node_name: "", owner_employee_no: "", estimated_hours: "", deliverable: "", acceptance_criteria: "", depends_on: "" };
}

export function NewTaskPage() {
  const navigate = useNavigate();
  const users = useQuery({ queryKey: ["prototype-users"], queryFn: () => apiRequest<PrototypeUser[]>("/api/v1/auth/prototype-users", {}, { anonymous: true }) });
  const [form, setForm] = useState({ task_name: "", task_description: "", task_goal: "", main_assignee_employee_no: "", reviewer_employee_no: "", department_id: "", deadline: "", estimated_hours: "", task_weight: "3", deliverable: "", acceptance_criteria: "", is_urgent: false });
  const [nodes, setNodes] = useState<DraftNode[]>([newNode()]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const create = useMutation({
    mutationFn: (payload: Record<string, unknown>) => apiRequest<{ task_id: string }>("/api/v1/tasks", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: (result) => navigate(`/tasks/${result.task_id}`),
  });

  function updateNode(index: number, field: keyof DraftNode, value: string) {
    setNodes((current) => current.map((node, nodeIndex) => nodeIndex === index ? { ...node, [field]: value } : node));
  }
  function validate(): boolean {
    const next: Record<string, string> = {};
    if (!form.task_name.trim()) next.task_name = "请输入任务名称。";
    if (!form.main_assignee_employee_no) next.main_assignee_employee_no = "请选择主承办人。";
    if (!form.acceptance_criteria.trim()) next.acceptance_criteria = "任务发送前需要明确验收标准。";
    nodes.forEach((node, index) => {
      if (!node.node_name.trim()) next[`node-${index}-name`] = "请输入节点名称。";
      if (!node.acceptance_criteria.trim()) next[`node-${index}-acceptance`] = "请输入节点验收标准。";
    });
    setErrors(next);
    return Object.keys(next).length === 0;
  }
  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!validate()) return;
    const payload = {
      task_name: form.task_name.trim(),
      task_description: form.task_description || null,
      task_goal: form.task_goal || null,
      main_assignee_employee_no: form.main_assignee_employee_no,
      reviewer_employee_no: form.reviewer_employee_no || null,
      department_id: form.department_id || null,
      deadline: form.deadline ? new Date(form.deadline).toISOString() : null,
      estimated_hours: form.estimated_hours || null,
      task_weight: Number(form.task_weight),
      deliverable: form.deliverable || null,
      acceptance_criteria: form.acceptance_criteria,
      is_urgent: form.is_urgent,
      nodes: nodes.map((node, index) => ({
        node_id: node.node_id,
        node_order: index + 1,
        node_name: node.node_name,
        owner_employee_no: node.owner_employee_no || null,
        estimated_hours: node.estimated_hours || null,
        deliverable: node.deliverable || null,
        acceptance_criteria: node.acceptance_criteria,
      })),
      dependencies: nodes.flatMap((node) => node.depends_on ? [{ dependency_id: crypto.randomUUID(), predecessor_node_id: node.depends_on, successor_node_id: node.node_id, dependency_type: "finish_to_start" }] : []),
    };
    create.mutate(payload);
  }
  return (
    <div className="page-stack narrow-page">
      <header className="page-header"><div><p className="eyebrow">结构化创建</p><h1>创建任务草稿</h1><p>关键人员、工时和验收标准都由你明确填写，系统不会猜测。</p></div></header>
      <form className="task-form" onSubmit={submit} noValidate>
        <section className="form-section"><h2>任务信息</h2><div className="form-grid">
          <label>任务名称 *<input value={form.task_name} onChange={(e) => setForm({ ...form, task_name: e.target.value })} aria-invalid={Boolean(errors.task_name)} />{errors.task_name && <span className="field-error">{errors.task_name}</span>}</label>
          <label>主承办人 *<select value={form.main_assignee_employee_no} onChange={(e) => setForm({ ...form, main_assignee_employee_no: e.target.value })}><option value="">请选择</option>{users.data?.map((user) => <option key={user.employee_no} value={user.employee_no}>{user.name} · {user.employee_no}</option>)}</select>{errors.main_assignee_employee_no && <span className="field-error">{errors.main_assignee_employee_no}</span>}</label>
          <label>验收人<select value={form.reviewer_employee_no} onChange={(e) => setForm({ ...form, reviewer_employee_no: e.target.value })}><option value="">默认创建人</option>{users.data?.map((user) => <option key={user.employee_no} value={user.employee_no}>{user.name}</option>)}</select></label>
          <label>部门 UUID<input value={form.department_id} onChange={(e) => setForm({ ...form, department_id: e.target.value })} placeholder="可选" /></label>
          <label>截止时间<input type="datetime-local" value={form.deadline} onChange={(e) => setForm({ ...form, deadline: e.target.value })} /></label>
          <label>预计工时<input type="number" min="0" step="0.5" value={form.estimated_hours} onChange={(e) => setForm({ ...form, estimated_hours: e.target.value })} /></label>
          <label>任务权重<select value={form.task_weight} onChange={(e) => setForm({ ...form, task_weight: e.target.value })}>{[1,2,3,4,5].map((value) => <option key={value}>{value}</option>)}</select></label>
          <label className="checkbox-label"><input type="checkbox" checked={form.is_urgent} onChange={(e) => setForm({ ...form, is_urgent: e.target.checked })} />标记为紧急</label>
          <label className="span-two">任务描述<textarea value={form.task_description} onChange={(e) => setForm({ ...form, task_description: e.target.value })} /></label>
          <label className="span-two">任务目标<textarea value={form.task_goal} onChange={(e) => setForm({ ...form, task_goal: e.target.value })} /></label>
          <label className="span-two">交付物<textarea value={form.deliverable} onChange={(e) => setForm({ ...form, deliverable: e.target.value })} /></label>
          <label className="span-two">任务验收标准 *<textarea value={form.acceptance_criteria} onChange={(e) => setForm({ ...form, acceptance_criteria: e.target.value })} aria-invalid={Boolean(errors.acceptance_criteria)} />{errors.acceptance_criteria && <span className="field-error">{errors.acceptance_criteria}</span>}</label>
        </div></section>
        <section className="form-section"><div className="section-heading"><h2>执行节点</h2><button type="button" className="button secondary" onClick={() => setNodes([...nodes, newNode()])}>添加节点</button></div>
          <div className="node-editor-list">{nodes.map((node, index) => <fieldset className="node-editor" key={node.node_id}><legend>节点 {index + 1}</legend><div className="form-grid">
            <label>节点名称 *<input value={node.node_name} onChange={(e) => updateNode(index, "node_name", e.target.value)} />{errors[`node-${index}-name`] && <span className="field-error">{errors[`node-${index}-name`]}</span>}</label>
            <label>负责人<select value={node.owner_employee_no} onChange={(e) => updateNode(index, "owner_employee_no", e.target.value)}><option value="">跟随主承办人</option>{users.data?.map((user) => <option key={user.employee_no} value={user.employee_no}>{user.name}</option>)}</select></label>
            <label>预计工时<input type="number" min="0" step="0.5" value={node.estimated_hours} onChange={(e) => updateNode(index, "estimated_hours", e.target.value)} /></label>
            <label>依赖前置节点<select value={node.depends_on} onChange={(e) => updateNode(index, "depends_on", e.target.value)}><option value="">无</option>{nodes.slice(0, index).map((candidate) => <option key={candidate.node_id} value={candidate.node_id}>{candidate.node_name || `节点 ${nodes.indexOf(candidate) + 1}`}</option>)}</select></label>
            <label className="span-two">交付物<input value={node.deliverable} onChange={(e) => updateNode(index, "deliverable", e.target.value)} /></label>
            <label className="span-two">验收标准 *<textarea value={node.acceptance_criteria} onChange={(e) => updateNode(index, "acceptance_criteria", e.target.value)} />{errors[`node-${index}-acceptance`] && <span className="field-error">{errors[`node-${index}-acceptance`]}</span>}</label>
          </div>{nodes.length > 1 && <button type="button" className="text-button danger-text" onClick={() => setNodes(nodes.filter((_, nodeIndex) => nodeIndex !== index))}>删除节点</button>}</fieldset>)}</div>
        </section>
        {create.isError && <ErrorState error={create.error instanceof ApiError ? create.error : create.error} />}
        <div className="form-actions"><button className="button primary" disabled={create.isPending}>{create.isPending ? "正在创建…" : "创建草稿"}</button></div>
      </form>
    </div>
  );
}
