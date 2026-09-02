/**
 * Feature: V1.1 read-only task report page.
 * Responsibilities: render the DEV-05 report visual shell from real task, report, issue, and permission data.
 * Does not own: progress submission, issue creation, resource requests, or actual-hour input.
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

function LoadingReport() {
  return (
    <section className="stb-task-detail" aria-label="正在加载汇报页面">
      <Skeleton height={92} />
      <Skeleton height={220} />
    </section>
  );
}

function errorTitle(error: unknown) {
  if (error instanceof ApiError && error.status === 403) return "无权限查看汇报";
  if (error instanceof ApiError && error.status === 404) return "任务不存在";
  return "汇报页面暂时无法加载";
}

export function TaskReportPage() {
  const { taskId = "" } = useParams();
  const { goBack, target } = useReturnNavigation(`/task/${taskId}`);
  const query = useTaskDetailBundle(taskId);

  if (query.isLoading) return <LoadingReport />;
  if (query.isError) {
    return (
      <ErrorState
        title={errorTitle(query.error)}
        detail={query.error instanceof ApiError ? query.error.message : "请稍后重试。"}
        action={<Button variant="secondary" onClick={() => void query.refetch()}>重试</Button>}
      />
    );
  }
  if (!query.data) return <ErrorState title="汇报页面暂时无法加载" detail="服务端没有返回任务上下文。" />;

  const { task, reports, issues, actions } = query.data;
  const latest = [...reports].sort((left, right) => right.created_at.localeCompare(left.created_at))[0];
  const canReport = actions.allowed_actions.includes("submit_progress_report");

  return (
    <section className="stb-task-detail" data-testid="task-report-page">
      <div className="stb-task-detail-head">
        <Button variant="ghost" onClick={goBack}>返回</Button>
        <Typography variant="caption" as="p">返回目标：{target}</Typography>
      </div>
      <ReadOnlyBanner>当前为 DEV-05 只读汇报页面；提交汇报、卡点和资源诉求写入在 DEV-11 启用。</ReadOnlyBanner>
      <Card className="stb-task-detail-summary">
        <div className="stb-task-detail-summary__head">
          <div>
            <Typography variant="caption" as="p">{task.task_no ?? "未编号"} · v{task.task_version}</Typography>
            <Typography variant="sectionTitle" as="h2">{task.task_name}</Typography>
          </div>
          <span className={`stb-task-detail-status stb-task-detail-status--${statusTone(task.status)}`}>{statusLabel(task.status)}</span>
        </div>
        <KeyValueGrid rows={[
          ["主承办人", displayValue(task.main_assignee_employee_no)],
          ["截止时间", formatDateTime(task.deadline)],
          ["允许汇报", canReport ? "是" : "否"],
        ]} />
      </Card>
      <Card title="汇报字段" className="stb-task-detail-section">
        <div className="stb-task-detail-readonly-fields" aria-label="只读汇报字段">
          <label>当前进度 <input readOnly value={latest ? `${latest.progress_percent}%` : "未汇报"} /></label>
          <label>阶段成果 <textarea readOnly value={latest?.stage_result ?? ""} aria-label="阶段成果只读" /></label>
          <label>是否存在卡点 <input readOnly value={issues.some((item) => item.status === "open" || item.status === "processing") ? "是" : "否"} /></label>
          <label>备注 <textarea readOnly value={latest?.report_content ?? ""} aria-label="备注只读" /></label>
        </div>
        <Button variant="secondary" disabled>提交进度汇报（DEV-11 启用）</Button>
      </Card>
      <Card title="最新汇报记录" className="stb-task-detail-section">
        {!latest ? (
          <EmptyState title="暂无进度汇报" detail="不会生成模拟汇报内容。" />
        ) : (
          <KeyValueGrid rows={[
            ["汇报人", latest.reporter_employee_no],
            ["汇报时间", formatDateTime(latest.created_at)],
            ["汇报内容", displayValue(latest.report_content)],
          ]} />
        )}
      </Card>
    </section>
  );
}
