import { useMutation, useQuery } from "@tanstack/react-query";
import { type Dispatch, type FormEvent, type SetStateAction, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import {
  clarifyTaskInput,
  confirmTaskInput,
  createTask,
  listUsers,
  submitTaskInput,
} from "../api/endpoints";
import { runTaskAction } from "../api/taskActions";
import type {
  CreateTaskPayload,
  DepartmentOption,
  PrototypeUser,
  TaskActionResult,
  TaskIntakeResponse,
} from "../api/types";
import { useAuth } from "../auth/useAuth";
import { ErrorState } from "../components/Feedback";

const emptyObjectText = "{}";

type FormState = {
  task_name: string;
  task_description: string;
  task_goal: string;
  main_assignee_employee_no: string;
  report_to_employee_no: string;
  reviewer_employee_no: string;
  department_id: string;
  deadline: string;
  estimated_hours: string;
  task_weight: string;
  deliverable: string;
  acceptance_criteria: string;
  is_urgent: boolean;
};

const initialForm: FormState = {
  task_name: "",
  task_description: "",
  task_goal: "",
  main_assignee_employee_no: "",
  report_to_employee_no: "",
  reviewer_employee_no: "",
  department_id: "",
  deadline: "",
  estimated_hours: "",
  task_weight: "3",
  deliverable: "",
  acceptance_criteria: "",
  is_urgent: false,
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value);
}

function toDateTimeLocal(value: unknown): string {
  const text = stringValue(value).trim();
  if (!text) return "";
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString().slice(0, 16);
}

function firstRecord(value: unknown): Record<string, unknown> {
  if (!isRecord(value)) return {};
  return isRecord(value.taskDraft) ? value.taskDraft : value;
}

function parseObjectText(
  text: string,
  fallback: Record<string, unknown> = {},
): Record<string, unknown> {
  const trimmed = text.trim();
  if (!trimmed) return fallback;
  const parsed = JSON.parse(trimmed) as unknown;
  if (!isRecord(parsed)) throw new Error("请输入 JSON 对象。");
  return parsed;
}

function applyExtractionToForm(
  intake: TaskIntakeResponse,
  setForm: Dispatch<SetStateAction<FormState>>,
) {
  const draft = firstRecord(intake.extracted_json);
  setForm((current) => ({
    ...current,
    task_name: stringValue(draft.task_name ?? draft.taskName) || current.task_name,
    task_description:
      stringValue(draft.task_description ?? draft.taskDescription) ||
      current.task_description,
    task_goal: stringValue(draft.task_goal ?? draft.taskGoal) || current.task_goal,
    main_assignee_employee_no:
      stringValue(draft.main_assignee_employee_no ?? draft.mainAssigneeEmployeeNo) ||
      current.main_assignee_employee_no,
    report_to_employee_no:
      stringValue(draft.report_to_employee_no ?? draft.reportToEmployeeNo) ||
      current.report_to_employee_no,
    reviewer_employee_no:
      stringValue(draft.reviewer_employee_no ?? draft.reviewerEmployeeNo) ||
      current.reviewer_employee_no,
    department_id:
      stringValue(draft.department_id ?? draft.departmentId) || current.department_id,
    deadline: toDateTimeLocal(draft.deadline) || current.deadline,
    estimated_hours:
      stringValue(draft.estimated_hours ?? draft.estimatedHours) ||
      current.estimated_hours,
    task_weight: stringValue(draft.task_weight ?? draft.taskWeight) || current.task_weight,
    deliverable: stringValue(draft.deliverable) || current.deliverable,
    acceptance_criteria:
      stringValue(draft.acceptance_criteria ?? draft.acceptanceCriteria) ||
      current.acceptance_criteria,
    is_urgent: Boolean(draft.is_urgent ?? draft.isUrgent ?? current.is_urgent),
  }));
}

export function NewTaskPage() {
  const navigate = useNavigate();
  const { user: currentUser } = useAuth();
  const users = useQuery({ queryKey: ["users"], queryFn: listUsers });
  const [step, setStep] = useState(1);
  const [form, setForm] = useState<FormState>(initialForm);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [rawText, setRawText] = useState("");
  const [intake, setIntake] = useState<TaskIntakeResponse | null>(null);
  const [clarificationText, setClarificationText] = useState(emptyObjectText);
  const [correctionsText, setCorrectionsText] = useState(emptyObjectText);
  const [notice, setNotice] = useState("");
  const departmentOptions = useMemo(
    () => deriveDepartments(users.data || []),
    [users.data],
  );

  const publishTask = async (draft: TaskActionResult) => {
    const submitted = await runTaskAction(
      draft.task_id,
      "submit_for_confirmation",
      draft.task_version,
    );
    const publishAction =
      form.main_assignee_employee_no === currentUser?.employee_no
        ? "confirm_self_assigned"
        : "confirm_and_send";
    return runTaskAction(draft.task_id, publishAction, submitted.task_version);
  };

  const create = useMutation({
    mutationFn: async () => {
      const draft = await createTask(buildPayload(form));
      return publishTask(draft);
    },
    onSuccess: (result) => navigate(`/tasks/${result.task_id}`),
    onError: (error) => setNotice(errorMessage(error)),
  });
  const intakeMutation = useMutation({
    mutationFn: () => {
      const text = rawText.trim();
      if (!text) throw new Error("请输入自然语言任务内容。");
      return submitTaskInput({ input_type: "text", raw_text: text, source_channel: "web" });
    },
    onSuccess: (result) => {
      setIntake(result);
      applyExtractionToForm(result, setForm);
      setStep(2);
      setNotice("已生成结构化建议，请确认任务信息。节点规划将在主承办人接受后进行。");
    },
    onError: (error) => setNotice(errorMessage(error)),
  });
  const clarifyMutation = useMutation({
    mutationFn: () => {
      if (!intake) throw new Error("请先提交任务输入。");
      return clarifyTaskInput(intake.input_id, { answers: parseObjectText(clarificationText) });
    },
    onSuccess: (result) => {
      setIntake(result);
      applyExtractionToForm(result, setForm);
      setClarificationText(emptyObjectText);
      setNotice("补充信息已提交，结构化建议已更新。");
    },
    onError: (error) => setNotice(errorMessage(error)),
  });
  const confirmMutation = useMutation({
    mutationFn: async () => {
      if (!intake) throw new Error("请先提交任务输入。");
      const corrections = {
        ...buildPayload(form),
        ...parseObjectText(correctionsText, {}),
      };
      const draft = await confirmTaskInput(intake.input_id, {
        extraction_id: intake.extraction_id,
        corrections,
      });
      return publishTask(draft);
    },
    onSuccess: (result) => navigate(`/tasks/${result.task_id}`),
    onError: (error) => setNotice(errorMessage(error)),
  });

  function validate(): boolean {
    const next: Record<string, string> = {};
    if (!form.task_name.trim()) next.task_name = "请输入任务名称。";
    if (!form.task_description.trim()) next.task_description = "请输入任务描述。";
    if (!form.main_assignee_employee_no) {
      next.main_assignee_employee_no = "请选择主承办人。";
    }
    if (!form.deadline) next.deadline = "请选择任务截止时间。";
    if (!form.acceptance_criteria.trim()) {
      next.acceptance_criteria = "任务发布前需要明确验收标准。";
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!validate()) {
      setStep(2);
      return;
    }
    setStep(3);
  }

  function confirmAiTask(event: FormEvent) {
    event.preventDefault();
    if (!validate()) {
      setStep(2);
      return;
    }
    confirmMutation.mutate();
  }

  return (
    <div className="page-stack narrow-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">结构化创建</p>
          <h1>创建任务</h1>
          <p>创建者确认任务事实并发布给主承办人，节点拆解由主承办人接受后完成。</p>
        </div>
      </header>

      <ol className="wizard-steps" aria-label="创建步骤">
        {["描述任务", "信息确认", "确认发布"].map((label, index) => (
          <li className={step === index + 1 ? "active" : ""} key={label}>
            <span>{index + 1}</span>
            {label}
          </li>
        ))}
      </ol>

      {notice && <div className="notice" role="status">{notice}</div>}

      <section className="form-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Step 1</p>
            <h2>描述任务</h2>
          </div>
          {intake && <span className="status-pill">置信度 {intake.confidence_score || "未给出"}</span>}
        </div>
        <form
          className="stack-form"
          onSubmit={(event) => {
            event.preventDefault();
            intakeMutation.mutate();
          }}
        >
          <label>
            任务原文
            <textarea
              value={rawText}
              onChange={(event) => setRawText(event.target.value)}
              placeholder="例如：下周五前完成门店上线方案，由王敏负责，完成后提交上线方案和验收清单。"
            />
          </label>
          <div className="action-row">
            <button className="button primary" disabled={intakeMutation.isPending} type="submit">
              {intakeMutation.isPending ? "正在识别..." : "AI 识别任务"}
            </button>
            <button className="button secondary" type="button" onClick={() => setStep(2)}>
              手动填写任务信息
            </button>
          </div>
        </form>
        {intake && (
          <div className="ai-review-grid">
            <div className="state-card">
              <strong>缺失项</strong>
              <p>{intake.missing_fields.length ? intake.missing_fields.join("、") : "无"}</p>
            </div>
            <div className="state-card">
              <strong>低置信项</strong>
              <p>{intake.low_confidence_fields.length ? intake.low_confidence_fields.join("、") : "无"}</p>
            </div>
            <div className="state-card full-field">
              <strong>确认问题</strong>
              {intake.confirm_questions.length === 0 ? (
                <p>无</p>
              ) : (
                <ol className="compact-list">
                  {intake.confirm_questions.map((question) => (
                    <li key={question}>{question}</li>
                  ))}
                </ol>
              )}
            </div>
          </div>
        )}
      </section>

      {step >= 2 && (
        <form className="task-form" onSubmit={submit} noValidate>
          <section className="form-section">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Step 2</p>
                <h2>信息确认</h2>
              </div>
            </div>
            {intake && (
              <details className="detail-panel full-field">
                <summary>结构化建议</summary>
                <pre className="json-preview">{formatJson(intake.extracted_json)}</pre>
              </details>
            )}
            <div className="form-grid">
              <label>
                任务名称 *
                <input
                  value={form.task_name}
                  onChange={(event) => setForm({ ...form, task_name: event.target.value })}
                  aria-invalid={Boolean(errors.task_name)}
                />
                {errors.task_name && <span className="field-error">{errors.task_name}</span>}
              </label>
              <label>
                主承办人 *
                <select
                  value={form.main_assignee_employee_no}
                  onChange={(event) =>
                    setForm({ ...form, main_assignee_employee_no: event.target.value })
                  }
                >
                  <option value="">请选择</option>
                  {users.data?.map((user) => (
                    <option key={user.employee_no} value={user.employee_no}>
                      {user.name} · {user.employee_no}
                    </option>
                  ))}
                </select>
                {errors.main_assignee_employee_no && (
                  <span className="field-error">{errors.main_assignee_employee_no}</span>
                )}
              </label>
              <label>
                验收人
                <select
                  value={form.reviewer_employee_no}
                  onChange={(event) => setForm({ ...form, reviewer_employee_no: event.target.value })}
                >
                  <option value="">默认创建人</option>
                  {users.data?.map((user) => (
                    <option key={user.employee_no} value={user.employee_no}>
                      {user.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                汇报对象
                <select
                  value={form.report_to_employee_no}
                  onChange={(event) => setForm({ ...form, report_to_employee_no: event.target.value })}
                >
                  <option value="">未指定</option>
                  {users.data?.map((user) => (
                    <option key={user.employee_no} value={user.employee_no}>
                      {user.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                部门
                <select
                  value={form.department_id}
                  onChange={(event) => setForm({ ...form, department_id: event.target.value })}
                >
                  <option value="">未指定</option>
                  {departmentOptions.map((department) => (
                    <option key={department.department_id} value={department.department_id}>
                      {department.department_name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                截止时间 *
                <input
                  type="datetime-local"
                  value={form.deadline}
                  onChange={(event) => setForm({ ...form, deadline: event.target.value })}
                  aria-invalid={Boolean(errors.deadline)}
                />
                {errors.deadline && <span className="field-error">{errors.deadline}</span>}
              </label>
              <label>
                预计工时
                <input
                  type="number"
                  min="0"
                  step="0.5"
                  value={form.estimated_hours}
                  onChange={(event) => setForm({ ...form, estimated_hours: event.target.value })}
                />
              </label>
              <label>
                任务权重
                <select
                  value={form.task_weight}
                  onChange={(event) => setForm({ ...form, task_weight: event.target.value })}
                >
                  {[1, 2, 3, 4, 5].map((value) => (
                    <option key={value}>{value}</option>
                  ))}
                </select>
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={form.is_urgent}
                  onChange={(event) => setForm({ ...form, is_urgent: event.target.checked })}
                />
                标记为紧急
              </label>
              <label className="span-two">
                任务描述 *
                <textarea
                  value={form.task_description}
                  onChange={(event) =>
                    setForm({ ...form, task_description: event.target.value })
                  }
                  aria-invalid={Boolean(errors.task_description)}
                />
                {errors.task_description && (
                  <span className="field-error">{errors.task_description}</span>
                )}
              </label>
              <label className="span-two">
                任务目标
                <textarea
                  value={form.task_goal}
                  onChange={(event) => setForm({ ...form, task_goal: event.target.value })}
                />
              </label>
              <label className="span-two">
                交付物
                <input
                  value={form.deliverable}
                  onChange={(event) => setForm({ ...form, deliverable: event.target.value })}
                />
              </label>
              <label className="span-two">
                任务验收标准 *
                <textarea
                  value={form.acceptance_criteria}
                  onChange={(event) =>
                    setForm({ ...form, acceptance_criteria: event.target.value })
                  }
                  aria-invalid={Boolean(errors.acceptance_criteria)}
                />
                {errors.acceptance_criteria && (
                  <span className="field-error">{errors.acceptance_criteria}</span>
                )}
              </label>
            </div>
            {intake && (
              <div className="ai-review-grid">
                <form
                  className="detail-panel full-field"
                  onSubmit={(event) => {
                    event.preventDefault();
                    clarifyMutation.mutate();
                  }}
                >
                  <h3>补充澄清</h3>
                  <label>
                    answers JSON
                    <textarea
                      value={clarificationText}
                      onChange={(event) => setClarificationText(event.target.value)}
                    />
                  </label>
                  <button className="button secondary" disabled={clarifyMutation.isPending} type="submit">
                    {clarifyMutation.isPending ? "正在更新..." : "提交补充"}
                  </button>
                </form>
              </div>
            )}
          </section>
          {users.isError && <ErrorState error={users.error} retry={() => void users.refetch()} />}
          <div className="form-actions">
            <button className="button primary" disabled={create.isPending} type="submit">
              进入确认发布
            </button>
          </div>
        </form>
      )}

      {step >= 3 && (
        <section className="form-section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Step 3</p>
              <h2>确认发布</h2>
            </div>
          </div>
          <dl className="detail-grid">
            <div><dt>任务名称</dt><dd>{form.task_name || "未填写"}</dd></div>
            <div><dt>主承办人</dt><dd>{form.main_assignee_employee_no || "未选择"}</dd></div>
            <div><dt>截止时间</dt><dd>{form.deadline || "未填写"}</dd></div>
            <div><dt>任务权重</dt><dd>{form.task_weight}</dd></div>
          </dl>
          <p className="muted">发布后任务进入 pending_acceptance，主承办人接受后再进行 AI 节点拆解。</p>
          {intake && (
            <form className="stack-form" onSubmit={confirmAiTask}>
              <label>
                corrections JSON
                <textarea
                  value={correctionsText}
                  onChange={(event) => setCorrectionsText(event.target.value)}
                />
              </label>
              <button className="button primary" disabled={confirmMutation.isPending} type="submit">
                {confirmMutation.isPending ? "正在发布..." : "确认 AI 信息并发布"}
              </button>
            </form>
          )}
          {!intake && (
            <button
              className="button primary"
              disabled={create.isPending}
              type="button"
              onClick={() => create.mutate()}
            >
              {create.isPending ? "正在发布..." : "确认发布"}
            </button>
          )}
          {(create.isError || confirmMutation.isError) && (
            <ErrorState error={create.error || confirmMutation.error} />
          )}
        </section>
      )}
    </div>
  );
}

function buildPayload(form: FormState): CreateTaskPayload {
  return {
    task_name: form.task_name.trim(),
    task_description: form.task_description || null,
    task_goal: form.task_goal || null,
    main_assignee_employee_no: form.main_assignee_employee_no,
    report_to_employee_no: form.report_to_employee_no || null,
    reviewer_employee_no: form.reviewer_employee_no || null,
    department_id: form.department_id || null,
    deadline: form.deadline ? new Date(form.deadline).toISOString() : null,
    estimated_hours: form.estimated_hours || null,
    task_weight: Number(form.task_weight),
    deliverable: form.deliverable || null,
    acceptance_criteria: form.acceptance_criteria,
    is_urgent: form.is_urgent,
  };
}

function deriveDepartments(users: PrototypeUser[]): DepartmentOption[] {
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

function formatJson(value: Record<string, unknown>): string {
  return JSON.stringify(value, null, 2);
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 409) {
    return "任务版本或业务状态已变化，请刷新后重试。";
  }
  return error instanceof Error ? error.message : "操作未完成。";
}
