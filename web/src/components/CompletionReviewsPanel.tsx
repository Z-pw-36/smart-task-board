import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";

import { ApiError } from "../api/client";
import { listCompletionReviews } from "../api/endpoints";
import {
  approveCompletion,
  rejectCompletion,
  reopenNode,
  submitCompletion,
} from "../api/taskActions";
import type {
  AvailableActions,
  TaskCompletionReview,
  TaskDetail,
} from "../api/types";
import { EmptyState, ErrorState, LoadingState } from "./Feedback";
import { formatDate } from "./task-card-utils";

interface Props {
  task: TaskDetail;
  actions: AvailableActions;
}

type Notice = { kind: "success" | "error"; message: string };
type ReworkScope = "deliverable" | "node";

const reviewStatusLabels = {
  submitted: "待验收",
  approved: "已通过",
  rejected: "已驳回",
} as const;

export function CompletionReviewsPanel({ task, actions }: Props) {
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState<Notice | null>(null);
  const [completionNote, setCompletionNote] = useState("");
  const [deliverableSummary, setDeliverableSummary] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [reworkScope, setReworkScope] = useState<ReworkScope>("deliverable");
  const [reworkNodeId, setReworkNodeId] = useState("");

  const reviewsQuery = useQuery({
    queryKey: ["completion-reviews", task.task_id],
    queryFn: () => listCompletionReviews(task.task_id, { limit: 20, offset: 0 }),
  });
  const reviews = [...(reviewsQuery.data?.items || [])].sort(
    (left, right) => right.review_round - left.review_round,
  );
  const currentReview = reviews.find((review) => review.review_status === "submitted");
  const latestRejectedReview = reviews.find((review) => review.review_status === "rejected");
  const completedNodes = task.nodes.filter((node) => node.status === "completed");
  const nodeActions = new Map(
    actions.nodes.map((item) => [item.node_id, item.allowed_actions]),
  );
  const reworkNode = latestRejectedReview?.rework_node_id
    ? task.nodes.find((node) => node.node_id === latestRejectedReview.rework_node_id)
    : undefined;
  const canReopenNode = Boolean(
    reworkNode && nodeActions.get(reworkNode.node_id)?.includes("reopen_node"),
  );
  const canSubmit = actions.allowed_actions.includes("submit_completion");
  const canApprove = actions.allowed_actions.includes("approve_completion");
  const canReject = actions.allowed_actions.includes("reject_completion");

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["completion-reviews", task.task_id] }),
      queryClient.invalidateQueries({ queryKey: ["task", task.task_id] }),
      queryClient.invalidateQueries({ queryKey: ["task-actions", task.task_id] }),
      queryClient.invalidateQueries({ queryKey: ["task-logs", task.task_id] }),
      queryClient.invalidateQueries({ queryKey: ["tasks"] }),
      queryClient.invalidateQueries({ queryKey: ["inbox"] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
    ]);
  }

  function reportError(error: unknown) {
    setNotice({
      kind: "error",
      message:
        error instanceof ApiError && error.status === 409
          ? "任务版本或验收轮次已变化。你的输入已保留，请刷新数据、复核后重试。"
          : error instanceof Error
            ? error.message
            : "操作未完成。",
    });
  }

  const submitMutation = useMutation({
    mutationFn: () =>
      submitCompletion(
        task.task_id,
        actions.task_version,
        completionNote.trim(),
        deliverableSummary.trim(),
      ),
    onSuccess: async () => {
      setNotice({ kind: "success", message: "完成申请已提交，新的验收轮次已创建。" });
      setCompletionNote("");
      setDeliverableSummary("");
      await refresh();
    },
    onError: reportError,
  });

  const approveMutation = useMutation({
    mutationFn: (review: TaskCompletionReview) =>
      approveCompletion(
        task.task_id,
        actions.task_version,
        review.completion_review_id,
      ),
    onSuccess: async () => {
      setNotice({ kind: "success", message: "本轮验收已通过。" });
      await refresh();
    },
    onError: reportError,
  });

  const rejectMutation = useMutation({
    mutationFn: (review: TaskCompletionReview) =>
      rejectCompletion(
        task.task_id,
        actions.task_version,
        review.completion_review_id,
        rejectReason.trim(),
        reworkScope === "node" ? reworkNodeId : null,
      ),
    onSuccess: async () => {
      setNotice({ kind: "success", message: "本轮验收已驳回，返工要求已记录。" });
      setRejectReason("");
      setReworkScope("deliverable");
      setReworkNodeId("");
      await refresh();
    },
    onError: reportError,
  });

  const reopenMutation = useMutation({
    mutationFn: ({ review, nodeId }: { review: TaskCompletionReview; nodeId: string }) =>
      reopenNode(
        task.task_id,
        nodeId,
        actions.task_version,
        review.completion_review_id,
      ),
    onSuccess: async () => {
      setNotice({ kind: "success", message: "返工节点已显式重开，原完成历史仍然保留。" });
      await refresh();
    },
    onError: reportError,
  });

  function onCompletionSubmit(event: FormEvent) {
    event.preventDefault();
    if (!completionNote.trim() || !deliverableSummary.trim()) {
      setNotice({ kind: "error", message: "完成说明和交付物摘要均不能为空。" });
      return;
    }
    submitMutation.mutate();
  }

  function onRejectSubmit(event: FormEvent) {
    event.preventDefault();
    if (!currentReview) {
      setNotice({ kind: "error", message: "当前待验收轮次不可用，请刷新后重试。" });
      return;
    }
    if (!rejectReason.trim()) {
      setNotice({ kind: "error", message: "验收驳回必须填写原因。" });
      return;
    }
    if (reworkScope === "node" && !reworkNodeId) {
      setNotice({ kind: "error", message: "指定节点返工时必须选择一个已完成节点。" });
      return;
    }
    rejectMutation.mutate(currentReview);
  }

  const isWorking =
    submitMutation.isPending ||
    approveMutation.isPending ||
    rejectMutation.isPending ||
    reopenMutation.isPending;
  const hasDecisionAction = canApprove || canReject;

  return (
    <section className="page-stack" aria-labelledby="completion-reviews-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">完成确认</p>
          <h2 id="completion-reviews-heading">验收与返工</h2>
        </div>
        <button
          className="text-button"
          type="button"
          onClick={() => void reviewsQuery.refetch()}
        >
          刷新验收记录
        </button>
      </div>

      {notice && (
        <div
          className={`notice ${notice.kind === "error" ? "notice-error" : ""}`}
          role={notice.kind === "error" ? "alert" : "status"}
        >
          <span>{notice.message}</span>
          {notice.kind === "error" && notice.message.includes("已保留") && (
            <button className="text-button" type="button" onClick={() => void refresh()}>
              刷新当前数据
            </button>
          )}
        </div>
      )}

      {reviewsQuery.isLoading && <LoadingState label="正在加载验收记录…" />}
      {reviewsQuery.isError && (
        <ErrorState error={reviewsQuery.error} retry={() => void reviewsQuery.refetch()} />
      )}

      {reviewsQuery.isSuccess && canSubmit && (
        <div className="detail-panel">
          <h3>提交完成申请</h3>
          <p className="muted">每次提交都会创建新的、不可覆盖的验收轮次。</p>
          <form
            className="form-grid"
            aria-busy={submitMutation.isPending}
            onSubmit={onCompletionSubmit}
          >
            <label className="full-field">
              完成说明
              <textarea
                required
                value={completionNote}
                onChange={(event) => setCompletionNote(event.target.value)}
              />
            </label>
            <label className="full-field">
              交付物摘要
              <textarea
                required
                value={deliverableSummary}
                onChange={(event) => setDeliverableSummary(event.target.value)}
              />
            </label>
            <button className="button primary" disabled={isWorking} type="submit">
              {submitMutation.isPending ? "正在提交…" : "提交完成申请"}
            </button>
          </form>
        </div>
      )}

      {reviewsQuery.isSuccess && hasDecisionAction && !currentReview && (
        <div className="state-card error-state" role="alert">
          服务端允许验收操作，但当前轮次不可用。请刷新验收记录后重试。
        </div>
      )}

      {reviewsQuery.isSuccess && currentReview && hasDecisionAction && (
        <div className="detail-panel">
          <h3>处理第 {currentReview.review_round} 轮验收</h3>
          <p><strong>完成说明：</strong>{reviewText(currentReview.completion_note, currentReview)}</p>
          <p><strong>交付物摘要：</strong>{reviewText(currentReview.deliverable_summary, currentReview)}</p>
          <p className="muted">
            提交人 {currentReview.submitted_by_employee_no} · {formatDate(currentReview.submitted_at)} ·
            提交版本 v{currentReview.submitted_task_version}
          </p>
          {canApprove && (
            <button
              className="button primary"
              disabled={isWorking}
              type="button"
              onClick={() => approveMutation.mutate(currentReview)}
            >
              {approveMutation.isPending ? "正在通过…" : "通过本轮验收"}
            </button>
          )}
          {canReject && (
            <form
              className="review-reject-form"
              aria-busy={rejectMutation.isPending}
              onSubmit={onRejectSubmit}
            >
              <label>
                驳回原因
                <textarea
                  required
                  value={rejectReason}
                  onChange={(event) => setRejectReason(event.target.value)}
                />
              </label>
              <fieldset>
                <legend>返工范围</legend>
                <label className="radio-label">
                  <input
                    checked={reworkScope === "deliverable"}
                    name="rework-scope"
                    type="radio"
                    value="deliverable"
                    onChange={() => {
                      setReworkScope("deliverable");
                      setReworkNodeId("");
                    }}
                  />
                  仅返工整体交付物，不重开节点
                </label>
                <label className="radio-label">
                  <input
                    checked={reworkScope === "node"}
                    disabled={completedNodes.length === 0}
                    name="rework-scope"
                    type="radio"
                    value="node"
                    onChange={() => setReworkScope("node")}
                  />
                  指定一个已完成节点返工
                </label>
              </fieldset>
              {reworkScope === "node" && (
                <label>
                  返工节点
                  <select
                    required
                    value={reworkNodeId}
                    onChange={(event) => setReworkNodeId(event.target.value)}
                  >
                    <option value="">请选择已完成节点</option>
                    {completedNodes.map((node) => (
                      <option key={node.node_id} value={node.node_id}>{node.node_name}</option>
                    ))}
                  </select>
                </label>
              )}
              <p className="muted">
                指定节点只记录返工范围；驳回后仍需本轮验收人显式重开该节点。
              </p>
              <button className="button secondary" disabled={isWorking} type="submit">
                {rejectMutation.isPending ? "正在驳回…" : "驳回本轮验收"}
              </button>
            </form>
          )}
        </div>
      )}

      {reviewsQuery.isSuccess && canReopenNode && reworkNode && latestRejectedReview && (
        <div className="detail-panel">
          <h3>处理指定节点返工</h3>
          <p>
            第 {latestRejectedReview.review_round} 轮要求返工节点“{reworkNode.node_name}”。
            重开是独立动作，原节点完成历史不会被删除或覆盖。
          </p>
          <button
            className="button secondary"
            disabled={isWorking}
            type="button"
            onClick={() =>
              reopenMutation.mutate({
                review: latestRejectedReview,
                nodeId: reworkNode.node_id,
              })
            }
          >
            {reopenMutation.isPending ? "正在重开…" : `重开节点：${reworkNode.node_name}`}
          </button>
        </div>
      )}

      {reviewsQuery.isSuccess && reviews.length === 0 && (
        <EmptyState
          title="暂无验收记录"
          detail="承办人提交完成申请后，每一轮验收都会追加显示在这里。"
        />
      )}

      {reviews.length > 0 && (
        <ol className="review-list" aria-label="验收历史">
          {reviews.map((review) => (
            <li className="review-card" key={review.completion_review_id}>
              <div className="review-card-heading">
                <h3>第 {review.review_round} 轮</h3>
                <span className={`status-pill review-${review.review_status}`}>
                  {reviewStatusLabels[review.review_status]}
                </span>
              </div>
              <p><strong>完成说明：</strong>{reviewText(review.completion_note, review)}</p>
              <p><strong>交付物摘要：</strong>{reviewText(review.deliverable_summary, review)}</p>
              {review.reject_reason && <p><strong>驳回原因：</strong>{review.reject_reason}</p>}
              {review.rework_node_id && (
                <p><strong>指定返工节点：</strong>{nodeName(task, review.rework_node_id)}</p>
              )}
              <p className="muted">
                提交人 {review.submitted_by_employee_no} · 验收人 {review.reviewer_employee_no} ·
                {formatDate(review.submitted_at)} · 提交版本 v{review.submitted_task_version}
              </p>
              {review.reviewed_at && (
                <p className="muted">
                  决定时间 {formatDate(review.reviewed_at)} · 决定版本 v{review.reviewed_task_version}
                </p>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function reviewText(value: string | null, review: TaskCompletionReview): string {
  if (value) return value;
  return review.is_legacy_import ? "历史迁移记录未包含此项" : "未提供";
}

function nodeName(task: TaskDetail, nodeId: string): string {
  return task.nodes.find((node) => node.node_id === nodeId)?.node_name || nodeId;
}
