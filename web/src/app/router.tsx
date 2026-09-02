/**
 * Feature: V1.1 target router.
 * Responsibilities: define formal routes, protected boundaries, role gates, legacy redirects, and route placeholders.
 * Does not own: business page implementations, auth APIs, or backend permission authority.
 * Plan task: DEV-02.
 */

import { Navigate, Outlet, Route, Routes, useLocation, useParams } from "react-router-dom";

import { useAuth } from "../auth/useAuth";
import { TaskDetailPage, TaskReportPage, TaskReviewPage } from "../features/task-detail";
import { TaskIntakePage } from "../features/task-intake";
import { TaskOverviewPage } from "../features/task-overview";
import { WorkbenchPage } from "../features/workbench";
import { AppShell, RouteLoadingState } from "./AppShell";
import { canAccessExecutiveRoutes } from "./navigation";
import { createReturnSource } from "./return-state";
import { ForbiddenRoute, LoginRoute, NotFoundRoute, RoutePlaceholder } from "./RoutePlaceholders";

function ProtectedLayout() {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <RouteLoadingState />;
  if (!user) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ source: createReturnSource(location) }}
      />
    );
  }

  return <AppShell />;
}

function ExecutiveBoundary() {
  const { user } = useAuth();

  if (!canAccessExecutiveRoutes(user)) return <ForbiddenRoute />;
  return <Outlet />;
}

function LegacyTaskRedirect() {
  const { taskId } = useParams();
  return <Navigate to={`/task/${taskId ?? ""}`} replace />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginRoute />} />
      <Route path="/" element={<Navigate to="/workbench" replace />} />
      <Route element={<ProtectedLayout />}>
        <Route path="/workbench" element={<WorkbenchPage />} />
        <Route element={<ExecutiveBoundary />}>
          <Route path="/executive" element={<RoutePlaceholder />} />
          <Route path="/executive/employee-tasks" element={<RoutePlaceholder />} />
        </Route>
        <Route path="/tasks" element={<TaskOverviewPage />} />
        <Route path="/tasks/:taskId" element={<LegacyTaskRedirect />} />
        <Route path="/task/:taskId" element={<TaskDetailPage />} />
        <Route path="/task/:taskId/report" element={<TaskReportPage />} />
        <Route path="/task/:taskId/review" element={<TaskReviewPage />} />
        <Route path="/task/:taskId/decomposition" element={<RoutePlaceholder />} />
        <Route path="/create/details" element={<TaskIntakePage />} />
        <Route path="/create/confirm" element={<RoutePlaceholder />} />
        <Route path="/notifications" element={<RoutePlaceholder />} />
        <Route path="/profile" element={<RoutePlaceholder />} />
        <Route path="*" element={<NotFoundRoute />} />
      </Route>
    </Routes>
  );
}
