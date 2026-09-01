/**
 * Feature: V1.1 task overview server state.
 * Responsibilities: bind URL-derived filters to the shared API client through React Query.
 * Does not own: filter authorization, task mutations, or task detail loading.
 * Plan task: DEV-04.
 */

import { useQuery } from "@tanstack/react-query";

import { loadTaskOverview, type TaskOverviewFilters } from "./api";

export function useTaskOverview(filters: TaskOverviewFilters) {
  return useQuery({
    queryKey: ["task-overview", filters],
    queryFn: () => loadTaskOverview(filters),
  });
}
