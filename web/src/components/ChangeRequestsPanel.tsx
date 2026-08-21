import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";

import { ApiError } from "../api/client";
import {
  actionLabels,
  decideChangeRequest,
  submitChangeRequest,
} from "../api/taskActions";
import type { AvailableActions, TaskChangeRequest, TaskDetail } from "../api/types";
import { formatDate } from "./task-card-utils";

interface Props {
  task: TaskDetail;
  actions: AvailableActions;
}

type DecisionAction = "approve" | "reject" | "cancel";

const statusLabels: Record<TaskChangeRequest["status"], string> = {
  pending: "待审批",
  approved: "已批准",
  rejected: "已驳回",
  cancelled: "已取消",
};

export function ChangeRequestsPanel({ task, actions }: Props) {
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState<{ kind: "success" | "error"; message: string } | null>(null);
  const [patchText, setPatchText] = useState("");
  const [reason, setReason] = useState("");
  const [decision, setDecision] = useState<{
    requestId: string;
    action: DecisionAction;
    comment: string;
  } | null>(null);

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["task", task.task_id] }),
      queryClient.invalidateQueries({ queryKey: ["task-actions", task.task_id] }),
      queryClient.invalidateQueries({ queryKey: ["task-logs", task.task_id] }),
      queryClient.invalidateQueries({ queryKey: ["tasks"] }),
      queryClient.invalidateQueries({ queryKey: ["inbox"] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
    ]);
  };

  const reportError = (error: unknown) => {
    setNotice({
      kind: "error",
      message:
        error instanceof ApiError && error.status === 409
          ? "任务版本或申请状态已变化，请刷新后重试。"
          : error instanceof Error
            ? error.message
            : "操作未完成。",
    });
  };

  const submitMutation = useMutation({
    mutationFn: () => {
      let patch: unknown;
      try {
        patch = JSON.parse(patchText);
      } catch {
        throw new Error("变更内容必须是有效的 JSON 对象。");
      }
      if (!isPatchObject(patch)) {
        throw new Error("变更内容必须是非空 JSON 对象。");
      }
      return submitChangeRequest(task.task_id, actions.task_version, patch, reason.trim());
    },
    onSuccess: async () => {
      setNotice({ kind: "success", message: "变更申请已提交，等待创建人审批。" });
      setPatchText("");
      setReason("");
      await refresh();
    },
    onError: reportError,
  });

  const decisionMutation = useMutation({
    mutationFn: (input: { requestId: string; action: DecisionAction; comment: string }) =>
      decideChangeRequest(
        task.task_id,
        input.requestId,
        actions.task_version,
        input.action,
        input.comment,
      ),
    onSuccess: async (_, input) => {
      setNotice({
        kind: "success",
        message:
          input.action === "approve"
            ? "变更申请已批准并应用。"
            : input.action === "reject"
              ? "变更申请已驳回。"
              : "变更申请已取消。",
      });
      setDecision(null);
      await refresh();
    },
    onError: reportError,
  });

  function submitRequest(event: FormEvent) {
    event.preventDefault();
    if (!reason.trim()) {
      setNotice({ kind: "error", message: "申请理由不能为空。" });
      return;
    }
    submitMutation.mutate();
  }

  function submitDecision(event: FormEvent) {
    event.preventDefault();
    if (!decision) return;
    if (!decision.comment.trim() && decision.action !== "approve") {
      setNotice({ kind: "error", message: "驳回或取消申请必须填写原因。" });
      return;
    }
    decisionMutation.mutate({ ...decision, comment: decision.comment.trim() });
  }

  const pendingRequest = (task.change_requests || []).find((request) => request.status === "pending");
  const canSubmit = actions.allowed_actions.includes("submit_change_request");
  const canApprove = actions.allowed_actions.includes("approve_change_request");
  const canReject = actions.allowed_actions.includes("reject_change_request");
  const canCancel = actions.allowed_actions.includes("cancel_change_request");
  const requests = [...(task.change_requests || [])].sort((left, right) =>
    right.created_at.localeCompare(left.created_at),
  );
  const isWorking = submitMutation.isPending || decisionMutation.isPending;

  return (
    <section className="page-stack" aria-labelledby="change-requests-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">变更控制</p>
          <h2 id="change-requests-heading">变更申请</h2>
        </div>
        <span className="muted">{requests.length} 条历史</span>
      </div>

      {notice && (
        <div className={`notice ${notice.kind === "error" ? "notice-error" : ""}`} role={notice.kind === "error" ? "alert" : "status"}>
          {notice.message}
        </div>
      )}

      {canSubmit && !pendingRequest && (
        <form className="detail-panel change-request-form" onSubmit={submitRequest} aria-busy={submitMutation.isPending}>
          <h3>提交新的变更申请</h3>
          <p className="muted">申请会锁定当前任务版本，审批通过后才会一次性应用。</p>
          <label className="full-field">
            变更内容（JSON）
            <textarea
              required
              aria-label="变更内容（JSON）"
              placeholder={'例如：{"deadline":"2026-08-30T09:00:00Z"}'}
              value={patchText}
              onChange={(event) => setPatchText(event.target.value)}
            />
          </label>
          <label className="full-field">
            申请理由
            <textarea
              required
              aria-label="申请理由"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
          <button className="button primary" disabled={isWorking} type="submit">
            {submitMutation.isPending ? "正在提交…" : actionLabels.submit_change_request}
          </button>
        </form>
      )}

      {canSubmit && pendingRequest && (
        <div className="state-card" role="status">
          当前已有待审批申请，审批完成或取消后才能提交下一份申请。
        </div>
      )}

      {requests.length === 0 && !canSubmit && (
        <div className="state-card">
          <strong>暂无变更申请</strong>
          <p>任务结构发生调整时，申请和审批记录会显示在这里。</p>
        </div>
      )}

      {requests.length > 0 && (
        <ol className="review-list change-request-list" aria-label="变更申请历史">
          {requests.map((request) => {
            const isPending = request.status === "pending";
            const isSelected = decision?.requestId === request.change_request_id;
            return (
              <li className={`review-card change-request-card change-${request.status}`} key={request.change_request_id}>
                <div className="review-card-heading">
                  <h3>申请 {request.change_request_id.slice(0, 8)}</h3>
                  <span className="status-pill">{statusLabels[request.status]}</span>
                </div>
                <p><strong>申请人：</strong>{request.requester_employee_no}</p>
                <p><strong>理由：</strong>{request.reason}</p>
                <p className="muted">创建于 {formatDate(request.created_at)} · 基准版本 v{request.base_task_version}</p>
                <details>
                  <summary>查看变更内容与前后快照</summary>
                  <div className="change-request-json">
                    <strong>变更内容</strong>
                    <pre>{formatJson(request.patch_json)}</pre>
                    <strong>变更前</strong>
                    <pre>{formatJson(request.before_snapshot)}</pre>
                    <strong>变更后</strong>
                    <pre>{formatJson(request.after_snapshot)}</pre>
                  </div>
                </details>
                {request.decision_comment && <p><strong>审批意见：</strong>{request.decision_comment}</p>}
                {request.cancellation_reason && <p><strong>取消原因：</strong>{request.cancellation_reason}</p>}
                {isPending && (canApprove || canReject || canCancel) && (
                  <div className="action-row">
                    {canApprove && (
                      <button className="button primary" disabled={isWorking} type="button" onClick={() => decisionMutation.mutate({ requestId: request.change_request_id, action: "approve", comment: "" })}>
                        {actionLabels.approve_change_request}
                      </button>
                    )}
                    {canReject && (
                      <button className="button secondary" disabled={isWorking} type="button" onClick={() => setDecision({ requestId: request.change_request_id, action: "reject", comment: "" })}>
                        {actionLabels.reject_change_request}
                      </button>
                    )}
                    {canCancel && (
                      <button className="button secondary" disabled={isWorking} type="button" onClick={() => setDecision({ requestId: request.change_request_id, action: "cancel", comment: "" })}>
                        {actionLabels.cancel_change_request}
                      </button>
                    )}
                  </div>
                )}
                {isSelected && decision && (
                  <form className="review-reject-form" onSubmit={submitDecision}>
                    <label>
                      {decision.action === "reject" ? "驳回原因" : "取消原因"}
                      <textarea
                        required
                        autoFocus
                        value={decision.comment}
                        onChange={(event) => setDecision({ ...decision, comment: event.target.value })}
                      />
                    </label>
                    <div className="action-row">
                      <button className="button secondary" disabled={isWorking} type="button" onClick={() => setDecision(null)}>取消</button>
                      <button className="button primary" disabled={isWorking} type="submit">
                        {decisionMutation.isPending ? "正在处理…" : decision.action === "reject" ? "确认驳回" : "确认取消"}
                      </button>
                    </div>
                  </form>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

function isPatchObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value) && Object.keys(value).length > 0;
}

function formatJson(value: Record<string, unknown>): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return "无法显示快照";
  }
}
