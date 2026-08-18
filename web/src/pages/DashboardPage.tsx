import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { DashboardSummary } from "../api/types";
import { useAuth } from "../auth/useAuth";
import { EmptyState, ErrorState, LoadingState } from "../components/Feedback";
import { TaskCard } from "../components/TaskCard";

export function DashboardPage() {
  const { user } = useAuth();
  const summary = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => apiRequest<DashboardSummary>("/api/v1/dashboard/summary"),
  });
  if (summary.isLoading) return <LoadingState label="正在汇总你的任务…" />;
  if (summary.isError) return <ErrorState error={summary.error} retry={() => void summary.refetch()} />;
  const data = summary.data;
  if (!data) return null;
  const metrics = [
    ["我创建的", data.created_task_count],
    ["我承办的", data.assigned_task_count],
    ["待处理", data.inbox_count],
    ["进行中", data.in_progress_count],
    [`未来 ${data.due_window_days} 天截止`, data.due_within_7_days_count],
    ["已逾期", data.overdue_count],
  ];
  return (
    <div className="page-stack">
      <header className="page-header dashboard-hero">
        <div><p className="eyebrow">你好，{user?.name}</p><h1>今天从重要任务开始</h1><p>所有数字仅统计与你有关的任务。</p></div>
        <Link className="button primary" to="/tasks/new">创建任务</Link>
      </header>
      <section className="metric-grid" aria-label="任务摘要">
        {metrics.map(([label, value]) => <article className="metric-card" key={label}><span>{label}</span><strong>{value}</strong></article>)}
      </section>
      <section>
        <div className="section-heading"><div><p className="eyebrow">最近动态</p><h2>最近任务</h2></div><Link to="/tasks">查看全部</Link></div>
        {data.recent_tasks.length === 0 ? (
          <EmptyState title="还没有相关任务" detail="创建第一项任务，或等待他人向你发送任务。" />
        ) : (
          <div className="task-grid">{data.recent_tasks.map((task) => <TaskCard task={task} key={task.task_id} />)}</div>
        )}
      </section>
    </div>
  );
}
