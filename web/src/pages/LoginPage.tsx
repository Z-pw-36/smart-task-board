import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { ApiError, apiRequest } from "../api/client";
import type { PrototypeUser } from "../api/types";
import { useAuth } from "../auth/useAuth";
import { EmptyState, ErrorState, LoadingState } from "../components/Feedback";

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [employeeNo, setEmployeeNo] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [loginError, setLoginError] = useState<unknown>(null);
  const users = useQuery({
    queryKey: ["prototype-users"],
    queryFn: () => apiRequest<PrototypeUser[]>("/api/v1/auth/prototype-users", {}, { anonymous: true }),
    retry: false,
  });
  const loginErrorMessage =
    loginError === null
      ? null
      : loginError instanceof ApiError && loginError.message.trim()
        ? loginError.message
        : "登录失败，请稍后重试。";

  if (user) return <Navigate to="/" replace />;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!employeeNo) return;
    setSubmitting(true);
    setLoginError(null);
    try {
      await login(employeeNo);
      navigate("/", { replace: true });
    } catch (error) {
      setLoginError(error);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel" aria-labelledby="login-title">
        <div className="brand-mark large">S</div>
        <p className="eyebrow">SmartTaskBoard</p>
        <h1 id="login-title">选择演示身份</h1>
        <div className="prototype-warning" role="note">
          仅用于隔离开发和演示，不是正式企业登录。会话令牌只保存在当前标签页。
        </div>
        {users.isLoading && <LoadingState label="正在加载演示用户…" />}
        {users.isError && <ErrorState error={users.error} retry={() => void users.refetch()} />}
        {users.data?.length === 0 && <EmptyState title="暂无演示用户" detail="请先由管理员准备隔离演示数据。" />}
        {users.data && users.data.length > 0 && (
          <form onSubmit={submit} className="stack-form">
            <label htmlFor="prototype-user">演示用户</label>
            <select id="prototype-user" value={employeeNo} onChange={(event) => setEmployeeNo(event.target.value)} required>
              <option value="">请选择身份</option>
              {users.data.map((item) => (
                <option value={item.employee_no} key={item.employee_no}>
                  {item.name} · {item.employee_no} · {item.department_name || "无部门"}
                </option>
              ))}
            </select>
            {loginErrorMessage && (
              <div className="state-card error-state" role="alert">
                <strong>登录失败</strong>
                <p>{loginErrorMessage}</p>
              </div>
            )}
            <button className="button primary wide" disabled={submitting || !employeeNo}>
              {submitting ? "正在进入…" : "进入任务看板"}
            </button>
          </form>
        )}
      </section>
    </main>
  );
}
