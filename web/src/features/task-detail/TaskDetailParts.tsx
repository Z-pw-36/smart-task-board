/**
 * Feature: V1.1 task detail read-only sections.
 * Responsibilities: render reusable detail, report, review, and permission sections from loaded DTO data.
 * Does not own: API fetching, mutations, route definitions, or backend permission authority.
 * Plan task: DEV-05.
 */

import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";

import type {
  AllowedAction,
  ProgressReport,
  StatusLogPage,
  TaskDetail,
  TaskIssue,
  TaskOperationLogSummary,
  TaskPerformanceMatchSummary,
} from "../../api/types";
import { createReturnSource } from "../../app/return-state";
import { Badge, Button, Card, EmptyState, Progress, Typography } from "../../shared/components";
import { actionLabels, displayValue, formatDateTime, nodeStatusLabels, statusLabel, statusTone } from "./format";

export function ReadOnlyBanner({ children }: { children: ReactNode }) {
  return <div className="stb-task-detail-banner" role="status">{children}</div>;
}

export function KeyValueGrid({ rows }: { rows: Array<[string, ReactNode]> }) {
  return (
    <dl className="stb-task-detail-kv">
      {rows.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function TaskSummaryCard({ task, latestReport }: { task: TaskDetail; latestReport?: ProgressReport }) {
  const progress = latestReport?.progress_percent;
  return (
    <Card className="stb-task-detail-summary">
      <div className="stb-task-detail-summary__head">
        <div>
          <Typography variant="caption" as="p">{task.task_no ?? "未编号"} · v{task.task_version}</Typography>
          <Typography variant="sectionTitle" as="h2">{task.task_name}</Typography>
        </div>
        <Badge tone={statusTone(task.status)}>{statusLabel(task.status)}</Badge>
      </div>
      <Typography variant="body" as="p">{task.task_goal || task.task_description || "暂无任务目标"}</Typography>
      {progress === undefined ? (
        <div className="stb-task-detail-progress-empty">服务端暂未返回任务级进度</div>
      ) : (
        <Progress value={progress} label="最新汇报进度" />
      )}
    </Card>
  );
}

export function BasicInfoSection({ task, nodeCount }: { task: TaskDetail; nodeCount: number }) {
  const rows: Array<[string, ReactNode]> = [
    ["任务名称", task.task_name],
    ["任务编号", task.task_no ?? "未编号"],
    ["当前状态", statusLabel(task.status)],
    ["节点任务", `${nodeCount} 项`],
    ["任务来源", displayValue(task.task_source)],
    ["创建时间", formatDateTime(task.created_at)],
    ["开始时间", formatDateTime(task.start_time)],
    ["生效时间", formatDateTime(task.accepted_at)],
    ["截止时间", formatDateTime(task.deadline)],
    ["任务权重", task.task_weight ?? "未设置"],
    ["突发任务", task.is_urgent ? "是" : "否"],
    ["汇报周期", displayValue(task.report_cycle)],
  ];
  if (task.actual_hours) rows.push(["实际工时", `${task.actual_hours} 小时（系统只读）`]);
  return (
    <Card title="基本信息" id="detail-overview" className="stb-task-detail-section">
      <KeyValueGrid rows={rows} />
      <div className="stb-task-detail-long">
        <span>任务目标</span>
        <strong>{displayValue(task.task_goal)}</strong>
      </div>
      <div className="stb-task-detail-long">
        <span>验收标准</span>
        <strong>{displayValue(task.acceptance_criteria)}</strong>
      </div>
      <div className="stb-task-detail-long">
        <span>交付物</span>
        <strong>{displayValue(task.deliverable)}</strong>
      </div>
    </Card>
  );
}

export function PeopleSection({ task }: { task: TaskDetail }) {
  const people = [
    ["创建人", task.creator_employee_no],
    ["主承办人", task.main_assignee_employee_no],
    ["汇报对象", task.report_to_employee_no],
    ["验收人", task.reviewer_employee_no],
    ...task.participants.map((item): [string, string] => [item.participant_role, item.employee_no]),
  ];
  const unique = Array.from(new Map(people.filter((item): item is [string, string] => Boolean(item[1])).map((item) => [`${item[0]}:${item[1]}`, item])).values());
  return (
    <Card title="人员信息" id="detail-people" className="stb-task-detail-section">
      {unique.length === 0 ? (
        <EmptyState title="暂无人员信息" detail="服务端没有返回任务参与人。" />
      ) : (
        <div className="stb-task-detail-people">
          {unique.map(([role, employeeNo]) => (
            <div key={`${role}-${employeeNo}`} className="stb-task-detail-person">
              <span aria-hidden="true">{employeeNo.slice(-2).toUpperCase()}</span>
              <div>
                <b>{employeeNo}</b>
                <small>{role}</small>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

export function NodesSection({ task }: { task: TaskDetail }) {
  const dependenciesBySuccessor = new Map<string, string[]>();
  task.dependencies.forEach((item) => {
    dependenciesBySuccessor.set(item.successor_node_id, [
      ...(dependenciesBySuccessor.get(item.successor_node_id) ?? []),
      item.predecessor_node_id,
    ]);
  });
  return (
    <Card title="节点执行" id="detail-nodes" className="stb-task-detail-section">
      {task.nodes.length === 0 ? (
        <EmptyState title="暂无节点任务" detail="待接受或拆解前任务允许没有节点，这不是系统异常。" />
      ) : (
        <div className="stb-task-detail-nodes">
          {task.nodes.map((node) => (
            <article id={`node-${node.node_id}`} tabIndex={-1} className="stb-task-detail-node" key={node.node_id}>
              <div className="stb-task-detail-node__head">
                <span className="stb-task-detail-node__order">{String(node.node_order).padStart(2, "0")}</span>
                <div>
                  <h3>{node.node_name}</h3>
                  <p>{node.action_detail || "暂无动作说明"}</p>
                </div>
                <Badge tone={statusTone(node.status)}>{nodeStatusLabels[node.status] ?? node.status}</Badge>
              </div>
              <Progress value={node.progress_percent} label={`节点 ${node.node_order} 进度`} />
              <KeyValueGrid rows={[
                ["负责人", displayValue(node.owner_employee_no)],
                ["开始时间", formatDateTime(node.planned_start_time)],
                ["截止时间", formatDateTime(node.planned_deadline)],
                ["交付物", displayValue(node.deliverable)],
                ["验收标准", displayValue(node.acceptance_criteria)],
                ["工具资料", displayValue(node.tools_or_materials)],
                ["依赖前置", dependenciesBySuccessor.get(node.node_id)?.join("、") || "无"],
              ]} />
            </article>
          ))}
        </div>
      )}
    </Card>
  );
}

export function ProgressSection({ reports, issues }: { reports: ProgressReport[]; issues: TaskIssue[] }) {
  const latest = [...reports].sort((left, right) => right.created_at.localeCompare(left.created_at))[0];
  return (
    <Card title="最新进度汇报" id="detail-progress" className="stb-task-detail-section">
      {!latest ? (
        <EmptyState title="暂无进度汇报" detail="服务端没有返回任何汇报记录。" />
      ) : (
        <KeyValueGrid rows={[
          ["当前进度", `${latest.progress_percent}%`],
          ["汇报人", latest.reporter_employee_no],
          ["汇报时间", formatDateTime(latest.created_at)],
          ["阶段成果", displayValue(latest.stage_result)],
          ["汇报内容", displayValue(latest.report_content)],
          ["困难说明", displayValue(latest.difficulty)],
          ["资源诉求", displayValue(latest.resource_request)],
        ]} />
      )}
      <div className="stb-task-detail-subsection">
        <Typography variant="cardTitle" as="h3">卡点与资源</Typography>
        {issues.length === 0 ? (
          <EmptyState title="暂无卡点或资源诉求" detail="服务端没有返回开放问题。" />
        ) : (
          <ul className="stb-task-detail-list">
            {issues.map((issue) => (
              <li key={issue.issue_id}>
                <Badge tone={issue.status === "open" || issue.status === "processing" ? "danger" : "neutral"}>{issue.status}</Badge>
                <strong>{issue.title}</strong>
                <span>{issue.description}</span>
                <small>{issue.reported_by_employee_no} · {formatDateTime(issue.created_at)}</small>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

function matchLevelLabel(level: string) {
  if (level === "strong") return "强相关";
  if (level === "weak") return "弱相关";
  if (level === "no_clear_relation") return "无明显相关";
  return level;
}

export function PerformanceSection({ matches }: { matches: TaskPerformanceMatchSummary[] }) {
  return (
    <Card title="绩效关联" id="detail-performance" className="stb-task-detail-section">
      {matches.length === 0 ? (
        <EmptyState title="暂无绩效关联" detail="当前只展示服务端已返回的绩效投影；未返回时不生成模拟 KPI。" />
      ) : (
        <ul className="stb-task-detail-list">
          {matches.map((match) => (
            <li key={match.performance_match_id}>
              <strong>{match.metric_name}</strong>
              <span>{displayValue(match.match_reason)}</span>
              <small>
                {matchLevelLabel(match.match_level)} · {match.total_score}分 · {displayValue(match.business_unit)}
              </small>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function TimelineSection({ logs }: { logs: StatusLogPage["items"] }) {
  return (
    <Card title="状态轨迹" className="stb-task-detail-section">
      {logs.length === 0 ? (
        <EmptyState title="暂无状态轨迹" detail="状态变化后会由服务端日志展示在这里。" />
      ) : (
        <ol className="stb-task-detail-timeline">
          {logs.map((log) => (
            <li key={log.status_log_id}>
              <strong>{log.action_type}</strong>
              <span>{log.from_status ? statusLabel(log.from_status) : "初始"} → {statusLabel(log.to_status)}</span>
              <small>{log.operator_employee_no ?? "SYSTEM"} · {formatDateTime(log.created_at)}</small>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

export function OperationLogsSection({ logs }: { logs: TaskOperationLogSummary[] }) {
  return (
    <Card title="操作记录" className="stb-task-detail-section">
      {logs.length === 0 ? (
        <EmptyState title="暂无操作记录" detail="服务端没有返回任务对象审计日志。" />
      ) : (
        <ol className="stb-task-detail-timeline">
          {logs.map((log) => (
            <li key={log.operation_log_id}>
              <strong>{log.action}</strong>
              <span>{log.result}{log.error_message ? ` · ${log.error_message}` : ""}</span>
              <small>{log.operator_employee_no ?? "SYSTEM"} · {formatDateTime(log.created_at)}</small>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

export function PermissionActions({ task, actions }: { task: TaskDetail; actions: AllowedAction[] }) {
  const location = useLocation();
  const canReport = actions.includes("submit_progress_report");
  const canReview = actions.includes("approve_completion") || actions.includes("reject_completion");
  const passiveActions = actions.filter((action) => !["submit_progress_report", "approve_completion", "reject_completion"].includes(action));
  return (
    <Card title="权限按钮" className="stb-task-detail-section">
      <div className="stb-task-detail-actions">
        {canReport && (
          <Link className="stb-task-detail-primary-link" to={`/task/${task.task_id}/report`} state={{ source: createReturnSource(location, "任务详情") }}>汇报进度</Link>
        )}
        {canReview && (
          <Link className="stb-task-detail-primary-link" to={`/task/${task.task_id}/review`} state={{ source: createReturnSource(location, "任务详情") }}>进入任务验收</Link>
        )}
        {passiveActions.map((action) => (
          <Button key={action} variant="secondary" disabled>{actionLabels[action] ?? action}（后续阶段）</Button>
        ))}
        {actions.length === 0 && <Button variant="secondary" disabled>当前任务只读</Button>}
      </div>
    </Card>
  );
}
