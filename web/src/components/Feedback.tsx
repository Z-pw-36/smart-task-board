import { ApiError } from "../api/client";

export function LoadingState({ label = "正在加载…" }: { label?: string }) {
  return <div className="state-card" role="status">{label}</div>;
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="state-card empty-state">
      <strong>{title}</strong>
      <p>{detail}</p>
    </div>
  );
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const message = error instanceof ApiError ? error.message : "页面暂时无法加载，请稍后重试。";
  return (
    <div className="state-card error-state" role="alert">
      <strong>操作未完成</strong>
      <p>{message}</p>
      {retry && <button className="button secondary" onClick={retry}>重试</button>}
    </div>
  );
}
