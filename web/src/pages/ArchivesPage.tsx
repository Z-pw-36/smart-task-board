import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { useState } from "react";

import { reuseArchive, searchArchives } from "../api/endpoints";
import { EmptyState, ErrorState, LoadingState } from "../components/Feedback";
import { formatDate } from "../components/task-card-utils";

export function ArchivesPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [keyword, setKeyword] = useState("");
  const [submittedKeyword, setSubmittedKeyword] = useState("");
  const archives = useQuery({
    queryKey: ["archives", submittedKeyword],
    queryFn: () => searchArchives({ keyword: submittedKeyword, limit: 20, offset: 0 }),
  });
  const reuse = useMutation({
    mutationFn: async (archiveId: string) => {
      const taskName = window.prompt("请输入复用后任务名称，可留空使用归档模板名称。")?.trim();
      return reuseArchive(archiveId, taskName ? { task_name: taskName } : {});
    },
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["tasks"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      ]);
      navigate(`/tasks/${result.task_id}`);
    },
  });

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Archive</p>
          <h1>任务归档</h1>
          <p>归档快照、复用模板和风险点均来自后端归档接口。</p>
        </div>
      </header>

      <form
        className="filter-panel"
        aria-label="归档搜索"
        onSubmit={(event) => {
          event.preventDefault();
          setSubmittedKeyword(keyword.trim());
        }}
      >
        <label>
          关键词
          <input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="任务名称、归档摘要"
          />
        </label>
        <button className="button primary" type="submit">
          搜索
        </button>
      </form>

      {archives.isLoading && <LoadingState />}
      {archives.isError && <ErrorState error={archives.error} retry={() => void archives.refetch()} />}
      {reuse.isError && <ErrorState error={reuse.error} />}
      {archives.data?.items.length === 0 && (
        <EmptyState title="暂无归档" detail="任务完成并归档后，可在这里搜索和复用。" />
      )}
      <div className="task-grid">
        {archives.data?.items.map((archive) => (
          <article className="task-card" key={archive.archive_id}>
            <div className="task-card-top">
              <span className="status-pill">{archive.source_status_snapshot}</span>
              <span className="muted">{formatDate(archive.archived_at)}</span>
            </div>
            <h2>{archive.summary || archive.task_id}</h2>
            <p className="muted">归档人：{archive.archived_by_employee_no}</p>
            {archive.risk_points.length > 0 && <p>风险点：{archive.risk_points.join("、")}</p>}
            <div className="action-row">
              <Link className="button secondary" to={`/tasks/${archive.task_id}`}>
                查看源任务
              </Link>
              <button
                className="button primary"
                disabled={reuse.isPending}
                type="button"
                onClick={() => reuse.mutate(archive.archive_id)}
              >
                复用为草稿
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
