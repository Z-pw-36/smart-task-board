/**
 * Feature: V1.1 workbench data hook.
 * Responsibilities: bind Workbench URL filters to React Query loading, error, and retry states.
 * Does not own: router contracts, business calculations, or backend authorization.
 * Plan task: DEV-03.
 */

import { useQuery } from "@tanstack/react-query";

import { loadWorkbenchData, type WorkbenchFilters } from "./api";

export function useWorkbenchData(filters: WorkbenchFilters) {
  return useQuery({
    queryKey: ["workbench", filters],
    queryFn: () => loadWorkbenchData(filters),
  });
}
