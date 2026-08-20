import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";

import { ApiError, apiRequest } from "../api/client";
import type {
  AvailableActions,
  IssueAction,
  ProgressReport,
  ProgressReportPage,
  TaskDetail,
  TaskIssue,
  TaskIssuePage,
} from "../api/types";
import { useAuth } from "../auth/useAuth";
import { EmptyState, ErrorState, LoadingState } from "./Feedback";
import { formatDate } from "./task-card-utils";

interface Props {
  task: TaskDetail;
  actions: AvailableActions;
}

const issueActionLabels: Record<IssueAction, string> = {
  start_processing: "开始处理",
  resolve: "标记已解决",
  reject: "驳回",
  close: "确认关闭",
};

export function ProgressIssuesPanel({ task, actions }: Props) {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [notice, setNotice] = useState("");
  const [progressPercent, setProgressPercent] = useState(0);
  const [reportContent, setReportContent] = useState("");
  const [reportNodeId, setReportNodeId] = useState("");
  const [correctsReportId, setCorrectsReportId] = useState("");
  const [issueTitle, setIssueTitle] = useState("");
  const [issueDescription, setIssueDescription] = useState("");
  const [issueOwner, setIssueOwner] = useState(task.main_assignee_employee_no || "");
  const [issueType, setIssueType] = useState("blocker");
  const [issueSeverity, setIssueSeverity] = useState("medium");
  const [issueNodeId, setIssueNodeId] = useState("");

  const reportsQuery = useQuery({
    queryKey: ["progress-reports", task.task_id],
    queryFn: () =>
      apiRequest<ProgressReportPage>(
        `/api/v1/tasks/${task.task_id}/progress-reports?limit=100&offset=0`,
      ),
  });
  const issuesQuery = useQuery({
    queryKey: ["task-issues", task.task_id],
    queryFn: () =>
      apiRequest<TaskIssuePage>(
        `/api/v1/tasks/${task.task_id}/issues?limit=100&offset=0`,
      ),
  });
  const reports = Array.isArray(reportsQuery.data?.items) ? reportsQuery.data.items : [];
  const issues = Array.isArray(issuesQuery.data?.items) ? issuesQuery.data.items : [];
  const nodeActions = new Map(
    actions.nodes.map((item) => [item.node_id, item.allowed_actions]),
  );
  const reportableNodes = task.nodes.filter((node) =>
    nodeActions.get(node.node_id)?.includes("submit_progress_report"),
  );
  const issueNodes = task.nodes.filter((node) =>
    nodeActions.get(node.node_id)?.includes("report_task_issue"),
  );
  const canReportTask = actions.allowed_actions.includes("submit_progress_report");
  const canReportIssue = actions.allowed_actions.includes("report_task_issue");
  const selectedReportNodeId =
    reportNodeId || (!canReportTask ? reportableNodes[0]?.node_id || "" : "");
  const selectedIssueNodeId =
    issueNodeId || (!canReportIssue ? issueNodes[0]?.node_id || "" : "");

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["progress-reports", task.task_id] }),
      queryClient.invalidateQueries({ queryKey: ["task-issues", task.task_id] }),
      queryClient.invalidateQueries({ queryKey: ["task", task.task_id] }),
      queryClient.invalidateQueries({ queryKey: ["task-actions", task.task_id] }),
      queryClient.invalidateQueries({ queryKey: ["task-logs", task.task_id] }),
      queryClient.invalidateQueries({ queryKey: ["inbox"] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
    ]);
  }

  const submitReport = useMutation({
    mutationFn: () =>
      apiRequest<ProgressReport>(`/api/v1/tasks/${task.task_id}/progress-reports`, {
        method: "POST",
        body: JSON.stringify({
          expected_task_version: actions.task_version,
          node_id: selectedReportNodeId || null,
          progress_percent: progressPercent,
          report_content: reportContent,
          corrects_report_id: correctsReportId || null,
        }),
      }),
    onSuccess: async () => {
      setNotice(correctsReportId ? "更正汇报已追加。" : "进度汇报已提交。");
      setReportContent("");
      setCorrectsReportId("");
      await refresh();
    },
    onError: (error) => setNotice(errorMessage(error)),
  });

  const createIssue = useMutation({
    mutationFn: () =>
      apiRequest<TaskIssue>(`/api/v1/tasks/${task.task_id}/issues`, {
        method: "POST",
        body: JSON.stringify({
          expected_task_version: actions.task_version,
          node_id: selectedIssueNodeId || null,
          issue_type: issueType,
          title: issueTitle,
          description: issueDescription,
          severity: issueSeverity,
          owner_employee_no: issueOwner,
          ...(issueType === "resource_request"
            ? { requested_resource: issueDescription }
            : {}),
        }),
      }),
    onSuccess: async () => {
      setNotice("卡点已上报。");
      setIssueTitle("");
      setIssueDescription("");
      await refresh();
    },
    onError: (error) => setNotice(errorMessage(error)),
  });

  const transitionIssue = useMutation({
    mutationFn: ({ issue, action }: { issue: TaskIssue; action: IssueAction }) => {
      const reason =
        action === "start_processing"
          ? undefined
          : window.prompt("请填写处理说明")?.trim();
      if (action !== "start_processing" && !reason) {
        throw new Error("处理说明不能为空。");
      }
      return apiRequest<TaskIssue>(
        `/api/v1/tasks/${task.task_id}/issues/${issue.issue_id}/actions/${action.replace("_", "-")}`,
        {
          method: "POST",
          body: JSON.stringify({
            expected_task_version: actions.task_version,
            reason,
          }),
        },
      );
    },
    onSuccess: async () => {
      setNotice("卡点状态已更新。");
      await refresh();
    },
    onError: (error) => setNotice(errorMessage(error)),
  });

  function onReportSubmit(event: FormEvent) {
    event.preventDefault();
    submitReport.mutate();
  }

  function onIssueSubmit(event: FormEvent) {
    event.preventDefault();
    createIssue.mutate();
  }

  return (
    <section className="page-stack" aria-label="进度汇报与卡点管理">
      {notice && <div className="notice" role="status">{notice}</div>}
      <div className="detail-panel">
        <h2>进度汇报</h2>
        {(canReportTask || reportableNodes.length > 0 || correctsReportId) && (
          <form className="form-grid" onSubmit={onReportSubmit}>
            <label>
              汇报范围
              <select
                value={selectedReportNodeId}
                onChange={(event) => setReportNodeId(event.target.value)}
              >
                {canReportTask && <option value="">整个任务</option>}
                {reportableNodes.map((node) => (
                  <option value={node.node_id} key={node.node_id}>
                    {node.node_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              进度百分比
              <input
                type="number"
                min="0"
                max="100"
                required
                value={progressPercent}
                onChange={(event) => setProgressPercent(Number(event.target.value))}
              />
            </label>
            <label className="full-field">
              汇报内容
              <textarea
                required
                value={reportContent}
                onChange={(event) => setReportContent(event.target.value)}
              />
            </label>
            {correctsReportId && (
              <p className="muted full-field">正在更正汇报：{correctsReportId}</p>
            )}
            <button
              className="button primary"
              disabled={submitReport.isPending}
              type="submit"
            >
              {correctsReportId ? "追加更正" : "提交汇报"}
            </button>
          </form>
        )}
        {reportsQuery.isLoading && <LoadingState label="正在加载汇报…" />}
        {reportsQuery.isError && (
          <ErrorState
            error={reportsQuery.error}
            retry={() => void reportsQuery.refetch()}
          />
        )}
        {reports.length === 0 && !reportsQuery.isLoading && (
          <EmptyState
            title="暂无进度汇报"
            detail="有权限的执行人可提交不可变的进度快照。"
          />
        )}
        <ol className="timeline">
          {reports.map((report) => (
            <li key={report.progress_report_id}>
              <strong>
                {report.node_id ? "节点汇报" : "任务汇报"} · {report.progress_percent}%
              </strong>
              <span>{report.report_content}</span>
              <small>
                {report.reporter_employee_no} · {formatDate(report.created_at)} · v
                {report.task_version}
              </small>
              {report.corrects_report_id && (
                <small>更正根汇报：{report.corrects_report_id}</small>
              )}
              {user?.employee_no === report.reporter_employee_no && (
                <button
                  className="text-button"
                  type="button"
                  onClick={() => {
                    setCorrectsReportId(
                      report.corrects_report_id || report.progress_report_id,
                    );
                    setReportNodeId(report.node_id || "");
                    setProgressPercent(report.progress_percent);
                  }}
                >
                  更正此汇报
                </button>
              )}
            </li>
          ))}
        </ol>
      </div>

      <div className="detail-panel">
        <h2>卡点与风险</h2>
        {(canReportIssue || issueNodes.length > 0) && (
          <form className="form-grid" onSubmit={onIssueSubmit}>
            <label>
              范围
              <select value={selectedIssueNodeId} onChange={(event) => setIssueNodeId(event.target.value)}>
                {canReportIssue && <option value="">整个任务</option>}
                {issueNodes.map((node) => (
                  <option value={node.node_id} key={node.node_id}>{node.node_name}</option>
                ))}
              </select>
            </label>
            <label>
              类型
              <select value={issueType} onChange={(event) => setIssueType(event.target.value)}>
                <option value="blocker">卡点</option>
                <option value="resource_request">资源需求</option>
                <option value="collaboration_support">协同支持</option>
                <option value="risk">风险</option>
              </select>
            </label>
            <label>
              严重度
              <select value={issueSeverity} onChange={(event) => setIssueSeverity(event.target.value)}>
                <option value="low">低</option>
                <option value="medium">中</option>
                <option value="high">高</option>
                <option value="critical">严重</option>
              </select>
            </label>
            <label>
              处理人
              <input required value={issueOwner} onChange={(event) => setIssueOwner(event.target.value)} />
            </label>
            <label>
              标题
              <input required value={issueTitle} onChange={(event) => setIssueTitle(event.target.value)} />
            </label>
            <label className="full-field">
              说明
              <textarea required value={issueDescription} onChange={(event) => setIssueDescription(event.target.value)} />
            </label>
            <button className="button primary" disabled={createIssue.isPending} type="submit">
              上报卡点
            </button>
          </form>
        )}
        {issuesQuery.isLoading && <LoadingState label="正在加载卡点…" />}
        {issuesQuery.isError && (
          <ErrorState error={issuesQuery.error} retry={() => void issuesQuery.refetch()} />
        )}
        {issues.length === 0 && !issuesQuery.isLoading && (
          <EmptyState
            title="暂无卡点"
            detail="卡点关闭前会阻止相关节点完成和任务提交验收。"
          />
        )}
        <div className="node-list">
          {issues.map((issue) => (
            <article className="node-card" key={issue.issue_id}>
              <div className="node-content">
                <h3>{issue.title}</h3>
                <p>{issue.description}</p>
                <p className="muted">
                  {issue.issue_type} · {issue.severity} · {issue.status} · 处理人 {issue.owner_employee_no}
                </p>
                <div className="action-row">
                  {issue.allowed_actions.map((action) => (
                    <button
                      className="button secondary"
                      type="button"
                      disabled={transitionIssue.isPending}
                      key={action}
                      onClick={() => transitionIssue.mutate({ issue, action })}
                    >
                      {issueActionLabels[action]}
                    </button>
                  ))}
                </div>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 409) {
    return "任务版本或业务状态已变化，请刷新后重试。";
  }
  return error instanceof Error ? error.message : "操作未完成。";
}
