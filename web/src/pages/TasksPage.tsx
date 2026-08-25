import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listTasks } from "../api/endpoints";
import { EmptyState, ErrorState, LoadingState } from "../components/Feedback";
import { TaskCard } from "../components/TaskCard";

export function TasksPage() {
  const [filters, setFilters] = useState({ relation: "all", status: "", search: "", deadline_from: "", deadline_to: "" });
  const [offset, setOffset] = useState(0);
  const limit = 20;
  const query = useQuery({
    queryKey: ["tasks", filters, offset],
    queryFn: () => {
      const params = { ...filters, limit, offset };
      return listTasks(params);
    },
  });
  function update(name: string, value: string) {
    setOffset(0);
    setFilters((current) => ({ ...current, [name]: value }));
  }
  return (
    <div className="page-stack">
      <header className="page-header"><div><p className="eyebrow">个人范围</p><h1>我的任务</h1><p>列表不会因角色名称自动扩大可见范围。</p></div></header>
      <section className="filter-panel" aria-label="任务筛选">
        <label>关系<select value={filters.relation} onChange={(e) => update("relation", e.target.value)}><option value="all">全部</option><option value="created">我创建</option><option value="assigned">我承办</option><option value="participating">我参与</option></select></label>
        <label>状态<select value={filters.status} onChange={(e) => update("status", e.target.value)}><option value="">全部</option><option value="draft">草稿</option><option value="pending_confirmation">待确认</option><option value="pending_acceptance">待接受</option><option value="returned">已退回</option><option value="in_progress">进行中</option><option value="pending_review">待验收</option><option value="completed">已完成</option></select></label>
        <label>搜索<input value={filters.search} onChange={(e) => update("search", e.target.value)} placeholder="任务名称" /></label>
        <label>截止从<input type="date" value={filters.deadline_from} onChange={(e) => update("deadline_from", e.target.value)} /></label>
        <label>截止到<input type="date" value={filters.deadline_to} onChange={(e) => update("deadline_to", e.target.value)} /></label>
      </section>
      {query.isLoading && <LoadingState />}
      {query.isError && <ErrorState error={query.error} retry={() => void query.refetch()} />}
      {query.data?.items.length === 0 && <EmptyState title="没有符合条件的任务" detail="调整筛选条件后再试。" />}
      {query.data && query.data.items.length > 0 && <div className="task-grid">{query.data.items.map((task) => <TaskCard task={task} key={task.task_id} />)}</div>}
      {query.data && query.data.total > limit && (
        <nav className="pagination" aria-label="任务分页">
          <button className="button secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>上一页</button>
          <span>{offset + 1}–{Math.min(offset + limit, query.data.total)} / {query.data.total}</span>
          <button className="button secondary" disabled={offset + limit >= query.data.total} onClick={() => setOffset(offset + limit)}>下一页</button>
        </nav>
      )}
    </div>
  );
}
