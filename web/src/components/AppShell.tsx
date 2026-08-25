import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth/useAuth";

const navigation = [
  { to: "/", label: "首页", icon: "⌂" },
  { to: "/inbox", label: "待处理", icon: "✓" },
  { to: "/tasks", label: "我的任务", icon: "▤" },
  { to: "/tasks/new", label: "创建", icon: "+" },
  { to: "/notifications", label: "通知", icon: "!" },
  { to: "/archives", label: "归档", icon: "#" },
];

export function AppShell() {
  const { user, logout } = useAuth();
  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="主导航">
        <NavLink className="brand" to="/" aria-label="SmartTaskBoard 首页">
          <span className="brand-mark">S</span><span>SmartTaskBoard</span>
        </NavLink>
        <nav>
          {navigation.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === "/"}>
              <span aria-hidden="true">{item.icon}</span><span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-user">
          <strong>{user?.name}</strong>
          <span>{user?.employee_no}</span>
          <button className="text-button" onClick={logout}>退出原型会话</button>
        </div>
      </aside>
      <main className="main-content"><Outlet /></main>
      <nav className="mobile-nav" aria-label="移动端主导航">
        {navigation.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.to === "/"}>
            <span aria-hidden="true">{item.icon}</span><span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
