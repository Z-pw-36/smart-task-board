import { Link } from "react-router-dom";

import type { TaskSummary } from "../api/types";
import { formatDate } from "./task-card-utils";

const statusLabels: Record<string, string> = {
  draft: "草稿",
  pending_confirmation: "待确认",
  pending_acceptance: "待接受",
  returned: "已退回",
  in_progress: "进行中",
  pending_review: "待验收",
  completed: "已完成",
};

export function TaskCard({ task }: { task: TaskSummary }) {
  return (
    <article className="task-card">
      <div className="task-card-heading">
        <div>
          <span className={`status-pill status-${task.status}`}>{statusLabels[task.status] || task.status}</span>
          {task.is_urgent && <span className="urgent-pill">紧急</span>}
        </div>
        <span className="muted">v{task.task_version}</span>
      </div>
      <h3><Link to={`/tasks/${task.task_id}`}>{task.task_name}</Link></h3>
      <dl className="compact-details">
        <div><dt>承办人</dt><dd>{task.main_assignee?.name || "未指定"}</dd></div>
        <div><dt>截止</dt><dd className={task.is_overdue ? "danger-text" : ""}>{formatDate(task.deadline)}</dd></div>
      </dl>
      <div className="tag-row" aria-label="当前用户与任务的关系">
        {task.current_user_relations.map((relation) => <span className="relation-tag" key={relation}>{relation}</span>)}
      </div>
    </article>
  );
}
