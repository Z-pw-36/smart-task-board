/**
 * Feature: V1.1 read-only task review page.
 * Responsibilities: render completion review context and permission projection without approval or rejection mutations.
 * Does not own: review decisions, archive workflow, lifecycle changes, or node reopen.
 * Plan task: DEV-05.
 */

import { useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, Card, EmptyState, ErrorState, Skeleton, Typography } from "../../shared/components";
import { useReturnNavigation } from "../../app/return-state";
import { KeyValueGrid, ReadOnlyBanner } from "./TaskDetailParts";
import { displayValue, formatDateTime, statusLabel, statusTone } from "./format";
import { useTaskDetailBundle } from "./hooks";
import "./TaskDetailPage.css";

function LoadingReview() {
  return (
    <section className="stb-task-detail" aria-label="正在加载验收页面">
      <Skeleton height={92} />
      <Skeleton height={240} />
    </section>
  );
}

function reviewStatusLabel(status: string) {
  if (status === "submitted") return "待验收";
  if (status === "approved") return "已通过";
  if (status === "rejected") return "已退回";
  return status;
}

function errorTitle(error: unknown) {
  if (error instanceof ApiError && error.status === 403) return "无权限查看验收";
  if (error instanceof ApiError && error.status === 404) return "任务不存在";
  return "验收页面暂时无法加载";
}

export function TaskReviewPage() {
  const { taskId = "" } = useParams();
  const { goBack, target } = useReturnNavigation(`/task/${taskId}`);
  const query = useTaskDetailBundle(taskId);

  if (query.isLoading) return <LoadingReview />;
  if (query.isError) {
    return (
      <ErrorState
        title={errorTitle(query.error)}
        detail={query.error instanceof ApiError ? query.error.message : "请稍后重试。"}
        action={<Button variant="secondary" onClick={() => void query.refetch()}>重试</Button>}
      />
    );
  }
  if (!query.data) return <ErrorState title="验收页面暂时无法加载" detail="服务端没有返回验收上下文。" />;

  const { task, reviews, actions } = query.data;
  const currentReview = reviews.find((item) => item.review_status === "submitted");
  const canApprove = actions.allowed_actions.includes("approve_completion");
  const canReject = actions.allowed_actions.includes("reject_completion");

  return (
    <section className="stb-task-detail" data-testid="task-review-page">
      <div className="stb-task-detail-head">
        <Button variant="ghost" onClick={goBack}>返回</Button>
        <Typography variant="caption" as="p">返回目标：{target}</Typography>
      </div>
      <ReadOnlyBanner>当前为 DEV-05 只读验收页面；通过、退回、重开和归档写入在 DEV-13 启用。</ReadOnlyBanner>
      <Card className="stb-task-detail-summary">
        <div className="stb-task-detail-summary__head">
          <div>
            <Typography variant="caption" as="p">{task.task_no ?? "未编号"} · v{task.task_version}</Typography>
            <Typography variant="sectionTitle" as="h2">{task.task_name}</Typography>
          </div>
          <span className={`stb-task-detail-status stb-task-detail-status--${statusTone(task.status)}`}>{statusLabel(task.status)}</span>
        </div>
        <KeyValueGrid rows={[
          ["提交人", displayValue(currentReview?.submitted_by_employee_no)],
          ["验收人", displayValue(currentReview?.reviewer_employee_no ?? task.reviewer_employee_no)],
          ["允许通过", canApprove ? "是" : "否"],
          ["允许退回", canReject ? "是" : "否"],
        ]} />
      </Card>
      <Card title="验收信息" className="stb-task-detail-section">
        {!currentReview ? (
          <EmptyState title="暂无待验收轮次" detail="服务端没有返回当前有效完成申请。" />
        ) : (
          <KeyValueGrid rows={[
            ["验收轮次", `第 ${currentReview.review_round} 轮`],
            ["验收状态", reviewStatusLabel(currentReview.review_status)],
            ["提交时间", formatDateTime(currentReview.submitted_at)],
            ["完成说明", displayValue(currentReview.completion_note)],
            ["交付物摘要", displayValue(currentReview.deliverable_summary)],
          ]} />
        )}
        <div className="stb-task-detail-actions">
          <Button variant="secondary" disabled>验收通过（DEV-13 启用）</Button>
          <Button variant="secondary" disabled>验收退回（DEV-13 启用）</Button>
        </div>
      </Card>
      <Card title="历史验收轮次" className="stb-task-detail-section">
        {reviews.length === 0 ? (
          <EmptyState title="暂无验收记录" detail="不会生成模拟验收记录。" />
        ) : (
          <ul className="stb-task-detail-list">
            {reviews.map((review) => (
              <li key={review.completion_review_id}>
                <strong>第 {review.review_round} 轮 · {reviewStatusLabel(review.review_status)}</strong>
                <span>{review.completion_note || "无完成说明"}</span>
                <small>{review.submitted_by_employee_no} → {review.reviewer_employee_no} · {formatDateTime(review.submitted_at)}</small>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </section>
  );
}
