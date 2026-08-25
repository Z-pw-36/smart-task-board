import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useState } from "react";

import { listNotifications, markNotificationRead } from "../api/endpoints";
import { EmptyState, ErrorState, LoadingState } from "../components/Feedback";
import { formatDate } from "../components/task-card-utils";

export function NotificationsPage() {
  const queryClient = useQueryClient();
  const [unreadOnly, setUnreadOnly] = useState(false);
  const notifications = useQuery({
    queryKey: ["notifications", unreadOnly],
    queryFn: () => listNotifications(unreadOnly),
  });
  const markRead = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["notifications"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      ]);
    },
  });

  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Notifications</p>
          <h1>通知</h1>
          <p>通知来自后端提醒扫描和发送队列，读取状态直接写回服务端。</p>
        </div>
        <label className="inline-toggle">
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(event) => setUnreadOnly(event.target.checked)}
          />
          只看未读
        </label>
      </header>

      {notifications.isLoading && <LoadingState />}
      {notifications.isError && (
        <ErrorState error={notifications.error} retry={() => void notifications.refetch()} />
      )}
      {notifications.data?.length === 0 && (
        <EmptyState title="暂无通知" detail="待办提醒、逾期提醒和验收提醒会出现在这里。" />
      )}
      <div className="inbox-list">
        {notifications.data?.map((item) => (
          <article className="inbox-card" key={item.notification_id}>
            <div>
              <span className="status-pill">{item.channel}</span>
              {!item.read_at && <span className="urgent-pill">未读</span>}
            </div>
            <h2>{item.title}</h2>
            <p>{item.content}</p>
            <p className="muted">
              {item.send_status} · {formatDate(item.created_at)}
            </p>
            <div className="action-row">
              {item.task_id && (
                <Link className="button secondary" to={`/tasks/${item.task_id}`}>
                  查看任务
                </Link>
              )}
              {!item.read_at && (
                <button
                  className="button primary"
                  disabled={markRead.isPending}
                  type="button"
                  onClick={() => markRead.mutate(item.notification_id)}
                >
                  标记已读
                </button>
              )}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
