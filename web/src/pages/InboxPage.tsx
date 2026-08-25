import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../api/client";
import { getInbox } from "../api/endpoints";
import { actionLabels, runInboxAction } from "../api/taskActions";
import type { AllowedAction, InboxItem } from "../api/types";
import { EmptyState, ErrorState, LoadingState } from "../components/Feedback";
import { formatDate } from "../components/task-card-utils";

const completionNavigationActions = new Set<AllowedAction>([
  "plan_task",
  "submit_completion",
  "approve_completion",
  "reject_completion",
  "reopen_node",
  "submit_change_request",
  "merge_task",
]);

export function InboxPage() {
  const queryClient = useQueryClient();
  const [actionCode, setActionCode] = useState("");
  const [notice, setNotice] = useState("");
  const inbox = useQuery({
    queryKey: ["inbox", actionCode],
    queryFn: () => getInbox({ action_code: actionCode }),
  });
  const action = useMutation({
    mutationFn: async ({ item, allowedAction }: { item: InboxItem; allowedAction: AllowedAction }) => {
      let reason: string | undefined;
      let progress: number | undefined;
      if (["return", "cancel_task", "withdraw_task", "close_task", "restore_task"].includes(allowedAction)) {
        reason = window.prompt(allowedAction === "return" ? "请填写退回原因" : "请填写操作原因")?.trim();
        if (!reason) throw new Error("此操作必须填写原因。");
      }
      if (allowedAction === "reject_change_request") {
        reason = window.prompt("请填写驳回意见")?.trim();
        if (!reason) throw new Error("驳回变更申请必须填写意见。");
      }
      if (allowedAction === "cancel_change_request") {
        reason = window.prompt("请填写取消原因")?.trim();
        if (!reason) throw new Error("取消变更申请必须填写原因。");
      }
      if (["resolve_issue", "reject_issue", "close_issue"].includes(allowedAction)) {
        reason = window.prompt("请填写处理说明")?.trim();
        if (!reason) throw new Error("处理说明不能为空。");
      }
      if (allowedAction === "update_node_progress") {
        const value = window.prompt("请输入节点进度（0-100）", String(item.node?.progress_percent ?? 0));
        if (value === null) throw new Error("已取消进度更新。");
        progress = Number(value);
        if (!Number.isInteger(progress) || progress < 0 || progress > 100) throw new Error("进度必须是 0 到 100 的整数。");
      }
      await runInboxAction(item.endpoint, allowedAction, item.expected_task_version, reason, progress);
    },
    onSuccess: async () => {
      setNotice("操作成功，列表已刷新。");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["inbox"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
        queryClient.invalidateQueries({ queryKey: ["tasks"] }),
        queryClient.invalidateQueries({ queryKey: ["task"] }),
      ]);
    },
    onError: (error) => setNotice(error instanceof ApiError && error.status === 409 ? "任务已被其他操作更新，请刷新后重试。" : error instanceof Error ? error.message : "操作未完成。"),
  });
  return (
    <div className="page-stack">
      <header className="page-header"><div><p className="eyebrow">行动队列</p><h1>待处理</h1><p>最终权限仍由服务端状态机校验。</p></div></header>
      <label className="single-filter">待办类型<select value={actionCode} onChange={(event) => setActionCode(event.target.value)}><option value="">全部</option><option value="confirm_task">任务确认</option><option value="accept_task">接受任务</option><option value="handle_returned_task">退回处理</option><option value="start_node">开始节点</option><option value="update_node">更新节点</option><option value="complete_node">完成节点</option><option value="submit_completion">提交验收</option><option value="approve_completion">待我验收</option><option value="reopen_node">重开返工节点</option><option value="report_due">进度待汇报</option><option value="handle_issue">卡点待处理</option><option value="submit_change_request">提交变更申请</option><option value="approve_change_request">待审批变更</option><option value="reject_change_request">待驳回变更</option><option value="cancel_change_request">待取消变更</option><option value="cancel_task">取消任务</option><option value="withdraw_task">撤回任务</option><option value="merge_task">合并任务</option><option value="close_task">关闭任务</option><option value="archive_task">归档任务</option><option value="restore_task">恢复任务</option></select></label>
      {notice && <div className="notice" role="status">{notice}</div>}
      {inbox.isLoading && <LoadingState />}
      {inbox.isError && <ErrorState error={inbox.error} retry={() => void inbox.refetch()} />}
      {inbox.data?.items.length === 0 && <EmptyState title="当前没有待办" detail="新的确认、节点执行或验收事项会出现在这里。" />}
      <div className="inbox-list">
        {inbox.data?.items.map((item) => (
          <article className="inbox-card" key={`${item.action_code}-${item.endpoint}`}>
            <div><span className="status-pill">{item.action_code}</span>{item.is_overdue && <span className="urgent-pill">已逾期</span>}</div>
            <h2><Link to={`/tasks/${item.task.task_id}`}>{item.task.task_name}</Link></h2>
            {item.node && <p><strong>节点：</strong>{item.node.node_name}（{item.node.progress_percent}%）</p>}
            <p>{item.reason}</p>
            <p className="muted">截止：{formatDate(item.task.deadline)} · 版本 v{item.expected_task_version}</p>
            <div className="action-row">
              {item.allowed_actions.some((allowedAction) => completionNavigationActions.has(allowedAction)) && (
                <Link className="button primary" to={`/tasks/${item.task.task_id}`}>
                  {completionNavigationLabel(item.allowed_actions)}
                </Link>
              )}
              {item.allowed_actions.filter((allowedAction) => !completionNavigationActions.has(allowedAction)).map((allowedAction) => (
                allowedAction === "submit_progress_report" || allowedAction === "report_task_issue" ? (
                  <Link className="button primary" key={allowedAction} to={`/tasks/${item.task.task_id}`}>
                    {actionLabels[allowedAction]}
                  </Link>
                ) : (
                <button className="button primary" disabled={action.isPending} key={allowedAction} onClick={() => action.mutate({ item, allowedAction })}>
                  {actionLabels[allowedAction]}
                </button>
                )
              ))}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function completionNavigationLabel(actions: AllowedAction[]): string {
  if (actions.includes("plan_task")) return "打开任务规划";
  if (actions.includes("submit_change_request")) return "填写变更申请";
  if (actions.includes("merge_task")) return "打开任务详情";
  if (actions.includes("approve_completion") || actions.includes("reject_completion")) {
    return "查看并验收";
  }
  if (actions.includes("reopen_node")) return "查看返工要求";
  return "填写完成说明并提交";
}
