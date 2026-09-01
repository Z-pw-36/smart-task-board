/**
 * Feature: V1.1 task overview page.
 * Responsibilities: render server-filtered task and node overview modes with URL-restorable filters.
 * Does not own: task detail implementation, permissions, priority calculation, or node execution.
 * Plan task: DEV-04.
 */

import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, createSearchParams, useLocation, useSearchParams } from "react-router-dom";

import type { TaskOverviewNode, TaskStatus, TaskSummary } from "../../api/types";
import { createReturnSource } from "../../app/return-state";
import { Badge, Button, Card, EmptyState, ErrorState, Progress, Sheet, Skeleton, Typography } from "../../shared/components";
import {
  datePresetOptions,
  isNodeOverviewItem,
  modeOptions,
  overviewStatusCounts,
  overviewStatuses,
  parseTaskOverviewFilters,
  quadrantOptions,
  taskOverviewSearchParams,
  type TaskOverviewFilters,
} from "./api";
import { useTaskOverview } from "./hooks";
import "./TaskOverviewPage.css";

const scrollKey = "smarttaskboard.task-overview.scroll";

const statusLabels: Record<string, string> = {
  draft: "草稿",
  pending_confirmation: "待确认",
  pending_acceptance: "待接受",
  pending_confirm: "待确认",
  pending_accept: "待接受",
  returned: "已退回",
  decomposing: "AI拆解中",
  decomposition_failed: "拆解失败",
  in_progress: "进行中",
  blocked: "受阻",
  pending_report: "待汇报",
  pending_review: "待验收",
  completed: "已完成",
  archived: "已归档",
  cancelled: "已取消",
  withdrawn: "已撤回",
  merged: "已合并",
  closed: "已关闭",
};

const nodeStatusLabels: Record<string, string> = {
  pending: "未开始",
  in_progress: "进行中",
  completed: "已完成",
};

function formatDateTime(value: string | null): string {
  if (!value) return "未设置";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "未设置";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function statusLabel(value: string) {
  return statusLabels[value] ?? value;
}

function resetPage(filters: TaskOverviewFilters): TaskOverviewFilters {
  return { ...filters, page: 1 };
}

function taskTarget(taskId: string, nodeId?: string) {
  const encodedTaskId = encodeURIComponent(taskId);
  return nodeId ? `/task/${encodedTaskId}#node-${encodeURIComponent(nodeId)}` : `/task/${encodedTaskId}`;
}

function LoadingOverview() {
  return (
    <section className="stb-task-overview stb-task-overview--loading" aria-label="正在加载任务概览">
      <Skeleton height={86} />
      <Skeleton height={116} />
      <Skeleton height={180} />
      <Skeleton height={180} />
    </section>
  );
}

function StatusCounts({
  activeStatus,
  counts,
  onSelect,
}: {
  activeStatus: TaskStatus | "";
  counts: Record<string, number>;
  onSelect: (status: TaskStatus) => void;
}) {
  return (
    <section className="stb-task-overview-status" aria-labelledby="overview-status-title">
      <Typography variant="sectionTitle" as="h2" className="stb-task-overview-status__title">
        状态概览
      </Typography>
      <div id="overview-status-title" className="stb-visually-hidden">状态概览</div>
      <div className="stb-task-overview-counts">
        {overviewStatusCounts.map((status) => (
          <button
            key={status}
            className={`stb-task-overview-count ${activeStatus === status ? "stb-task-overview-count--active" : ""}`}
            type="button"
            aria-pressed={activeStatus === status}
            onClick={() => onSelect(status)}
          >
            <span>{statusLabel(status)}任务</span>
            <strong>{counts[status] ?? 0}</strong>
          </button>
        ))}
      </div>
    </section>
  );
}

function ModeTabs({
  mode,
  onChange,
}: {
  mode: TaskOverviewFilters["mode"];
  onChange: (mode: TaskOverviewFilters["mode"]) => void;
}) {
  return (
    <div className="stb-task-overview-tabs" role="tablist" aria-label="任务概览模式">
      {modeOptions.map((item) => (
        <button
          key={item.value}
          type="button"
          role="tab"
          aria-selected={mode === item.value}
          className={mode === item.value ? "stb-task-overview-tab stb-task-overview-tab--active" : "stb-task-overview-tab"}
          onClick={() => onChange(item.value)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

function FilterSummary({ filters, onReset }: { filters: TaskOverviewFilters; onReset: () => void }) {
  const labels = [
    filters.mode === "nodes" ? "我的节点任务" : "",
    filters.status ? statusLabel(filters.status) : "",
    filters.quadrant ? quadrantOptions.find((item) => item.value === filters.quadrant)?.label : "",
    filters.support ? "需要支持" : "",
    filters.nearDue ? "未来3天临期" : "",
    filters.datePreset === "week" ? "本周开始" : "",
    filters.datePreset === "month" ? "本月开始" : "",
    filters.datePreset === "custom" && filters.startDate && filters.endDate ? `${filters.startDate} 至 ${filters.endDate}` : "",
    filters.search ? `搜索：${filters.search}` : "",
  ].filter(Boolean);

  if (labels.length === 0) {
    return <Typography variant="caption" as="p">当前显示全部可见任务。</Typography>;
  }

  return (
    <div className="stb-task-overview-filter-summary" aria-label="当前筛选">
      {labels.map((label) => <Badge key={label} tone="info">{label}</Badge>)}
      <Button variant="ghost" onClick={onReset}>重置筛选</Button>
    </div>
  );
}

function TaskCard({ task }: { task: TaskSummary }) {
  const location = useLocation();
  return (
    <Link
      className="stb-task-overview-card"
      to={taskTarget(task.task_id)}
      state={{ source: createReturnSource(location, "任务概览") }}
    >
      <span className="stb-task-overview-card__head">
        <Badge tone={task.is_overdue ? "danger" : "info"}>{statusLabel(task.status)}</Badge>
        <span>{task.task_no ?? "未编号"}</span>
      </span>
      <strong>{task.task_name}</strong>
      <span className="stb-task-overview-card__meta">
        <span>承办：{task.main_assignee?.name ?? "未指定"}</span>
        <span>截止：{formatDateTime(task.deadline)}</span>
      </span>
    </Link>
  );
}

function NodeTaskCard({ node }: { node: TaskOverviewNode }) {
  const location = useLocation();
  return (
    <Link
      className="stb-task-overview-card stb-task-overview-card--node"
      to={taskTarget(node.task_id, node.node_id)}
      state={{ source: createReturnSource(location, "任务概览"), nodeId: node.node_id }}
    >
      <span className="stb-task-overview-node-parent">所属任务 · {node.task_name}</span>
      <span className="stb-task-overview-card__head">
        <Badge tone={node.is_overdue ? "danger" : "success"}>{nodeStatusLabels[node.status] ?? node.status}</Badge>
        <span>{statusLabel(node.task_status)}</span>
      </span>
      <strong>{node.node_name}</strong>
      <Progress value={node.progress_percent} label="节点进度" />
      <span className="stb-task-overview-card__meta">
        <span>负责人：{node.owner?.name ?? "未指定"}</span>
        <span>截止：{formatDateTime(node.planned_deadline)}</span>
      </span>
    </Link>
  );
}

function FilterSheet({
  open,
  filters,
  onClose,
  onApply,
  onReset,
}: {
  open: boolean;
  filters: TaskOverviewFilters;
  onClose: () => void;
  onApply: (filters: TaskOverviewFilters) => void;
  onReset: () => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onApply(resetPage({
      ...filters,
      mode: String(form.get("mode") || "tasks") as TaskOverviewFilters["mode"],
      status: String(form.get("status") || "") as TaskOverviewFilters["status"],
      quadrant: String(form.get("quadrant") || "") as TaskOverviewFilters["quadrant"],
      support: form.get("support") === "open" ? "open" : "",
      nearDue: form.get("nearDue") === "true",
      datePreset: String(form.get("datePreset") || "all") as TaskOverviewFilters["datePreset"],
      startDate: String(form.get("startDate") || ""),
      endDate: String(form.get("endDate") || ""),
      search: String(form.get("search") || ""),
      sortBy: String(form.get("sortBy") || "deadline") as TaskOverviewFilters["sortBy"],
      sortOrder: String(form.get("sortOrder") || "asc") as TaskOverviewFilters["sortOrder"],
    }));
  }

  return (
    <Sheet open={open} title="任务筛选" onClose={onClose}>
      <form className="stb-task-filter" onSubmit={submit}>
        <label>
          <span>搜索</span>
          <input name="search" defaultValue={filters.search} placeholder="任务或节点名称" />
        </label>
        <label>
          <span>任务类型</span>
          <select name="mode" defaultValue={filters.mode}>
            {modeOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
        <label>
          <span>任务状态</span>
          <select name="status" defaultValue={filters.status}>
            <option value="">全部</option>
            {overviewStatuses.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
        <label>
          <span>优先级四象限</span>
          <select name="quadrant" defaultValue={filters.quadrant}>
            <option value="">全部</option>
            {quadrantOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
        <label className="stb-task-filter__check">
          <input name="nearDue" type="checkbox" value="true" defaultChecked={filters.nearDue} />
          <span>仅看未来3天临期</span>
        </label>
        <label className="stb-task-filter__check">
          <input name="support" type="checkbox" value="open" defaultChecked={filters.support === "open"} />
          <span>需要支持</span>
        </label>
        <label>
          <span>开始时间</span>
          <select name="datePreset" defaultValue={filters.datePreset}>
            {datePresetOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
        <div className="stb-task-filter__dates">
          <label>
            <span>开始日期</span>
            <input name="startDate" type="date" defaultValue={filters.startDate} />
          </label>
          <label>
            <span>结束日期</span>
            <input name="endDate" type="date" defaultValue={filters.endDate} />
          </label>
        </div>
        <div className="stb-task-filter__dates">
          <label>
            <span>排序</span>
            <select name="sortBy" defaultValue={filters.sortBy}>
              <option value="deadline">截止时间</option>
              <option value="created_at">创建时间</option>
              <option value="updated_at">更新时间</option>
              <option value="status">状态</option>
              <option value="task_weight">权重</option>
            </select>
          </label>
          <label>
            <span>顺序</span>
            <select name="sortOrder" defaultValue={filters.sortOrder}>
              <option value="asc">升序</option>
              <option value="desc">降序</option>
            </select>
          </label>
        </div>
        <div className="stb-task-filter__actions">
          <Button variant="secondary" onClick={onReset}>重置</Button>
          <Button type="submit">应用筛选</Button>
        </div>
      </form>
    </Sheet>
  );
}

export function TaskOverviewPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const [filterOpen, setFilterOpen] = useState(false);
  const filters = useMemo(() => parseTaskOverviewFilters(searchParams), [searchParams]);
  const query = useTaskOverview(filters);

  useEffect(() => {
    const saved = sessionStorage.getItem(scrollKey);
    if (saved) requestAnimationFrame(() => window.scrollTo(0, Number(saved) || 0));
    return () => {
      sessionStorage.setItem(scrollKey, String(window.scrollY));
    };
  }, []);

  function applyFilters(next: TaskOverviewFilters) {
    setSearchParams(taskOverviewSearchParams(next));
    setFilterOpen(false);
  }

  function resetFilters() {
    applyFilters({
      ...filters,
      mode: "tasks",
      status: "",
      quadrant: "",
      support: "",
      nearDue: false,
      datePreset: "all",
      startDate: "",
      endDate: "",
      search: "",
      page: 1,
      sortBy: "deadline",
      sortOrder: "asc",
    });
  }

  function updateFilters(patch: Partial<TaskOverviewFilters>) {
    applyFilters(resetPage({ ...filters, ...patch }));
  }

  function setPage(page: number) {
    setSearchParams(taskOverviewSearchParams({ ...filters, page }));
  }

  const total = query.data?.total ?? 0;
  const maxPage = Math.max(1, Math.ceil(total / filters.pageSize));
  const items = query.data?.items ?? [];

  if (query.isLoading) return <LoadingOverview />;

  return (
    <section className="stb-task-overview" data-testid="task-overview-page">
      <StatusCounts
        activeStatus={filters.status}
        counts={query.data?.status_counts ?? {}}
        onSelect={(status) => updateFilters({ mode: "tasks", status })}
      />
      <Card className="stb-task-overview-panel">
        <div className="stb-task-overview-toolbar">
          <div>
            <Typography variant="sectionTitle" as="h2">任务信息管理</Typography>
            <Typography variant="caption" as="p">
              {filters.mode === "nodes" ? "节点" : "任务"}结果 {total} 项
            </Typography>
          </div>
          <Button variant="secondary" onClick={() => setFilterOpen(true)}>更多筛选</Button>
        </div>
        <ModeTabs mode={filters.mode} onChange={(mode) => updateFilters({ mode })} />
        <div className="stb-task-overview-quick-status" aria-label="状态快捷筛选">
          {overviewStatusCounts.map((status) => (
            <button
              key={status}
              type="button"
              aria-pressed={filters.mode === "tasks" && filters.status === status}
              onClick={() => updateFilters({ mode: "tasks", status })}
            >
              {statusLabel(status)}
            </button>
          ))}
        </div>
        <FilterSummary filters={filters} onReset={resetFilters} />
        {query.isError && (
          <ErrorState
            title="任务概览暂时无法加载"
            detail="请检查筛选条件后重试。"
            action={<Button variant="secondary" onClick={() => void query.refetch()}>重试</Button>}
          />
        )}
        {!query.isError && items.length === 0 && (
          <EmptyState title={`当前筛选条件下暂无${filters.mode === "nodes" ? "节点" : "任务"}`} detail="清空筛选后可查看全部可见结果。" action={<Button variant="secondary" onClick={resetFilters}>重置筛选</Button>} />
        )}
        {!query.isError && items.length > 0 && (
          <div className="stb-task-overview-list">
            {items.map((item) => (
              isNodeOverviewItem(item)
                ? <NodeTaskCard key={item.node_id} node={item} />
                : <TaskCard key={item.task_id} task={item} />
            ))}
          </div>
        )}
        {!query.isError && total > filters.pageSize && (
          <nav className="stb-task-overview-pagination" aria-label="任务分页">
            <Button variant="secondary" disabled={filters.page <= 1} onClick={() => setPage(Math.max(1, filters.page - 1))}>上一页</Button>
            <span>{filters.page} / {maxPage}</span>
            <Button variant="secondary" disabled={filters.page >= maxPage} onClick={() => setPage(Math.min(maxPage, filters.page + 1))}>下一页</Button>
          </nav>
        )}
      </Card>
      <Link
        className="stb-task-overview-create"
        to={`/create/details?${createSearchParams({ source: "tasks" }).toString()}`}
        state={{ source: createReturnSource(location, "任务概览") }}
      >
        创建任务
      </Link>
      <FilterSheet
        open={filterOpen}
        filters={filters}
        onClose={() => setFilterOpen(false)}
        onApply={applyFilters}
        onReset={resetFilters}
      />
    </section>
  );
}
