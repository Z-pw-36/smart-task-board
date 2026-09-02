/**
 * Feature: V1.1 task detail server state.
 * Responsibilities: bind task detail route params to the read-only aggregate query.
 * Does not own: task mutations, route transitions, or backend authorization.
 * Plan task: DEV-05.
 */

import { useQuery } from "@tanstack/react-query";

import { loadTaskDetailBundle } from "./api";

export function useTaskDetailBundle(taskId: string) {
  return useQuery({
    queryKey: ["task-detail", taskId],
    queryFn: () => loadTaskDetailBundle(taskId),
    enabled: Boolean(taskId),
  });
}
