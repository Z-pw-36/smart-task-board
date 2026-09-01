/**
 * Feature: V1.1 route return source.
 * Responsibilities: normalize explicit source locations and safe fallback navigation for route-level back actions.
 * Does not own: browser history policy, business page state, or API authorization.
 * Plan task: DEV-02.
 */

import { useLocation, useNavigate, type Location } from "react-router-dom";

export const DEFAULT_RETURN_FALLBACK = "/workbench";

export interface ReturnSource {
  pathname: string;
  search?: string;
  hash?: string;
  label?: string;
}

export interface ReturnSourceState {
  source?: ReturnSource;
}

function isSafeInternalPath(pathname: string): boolean {
  return pathname.startsWith("/") && !pathname.startsWith("//") && !pathname.includes("://");
}

export function createReturnSource(location: Pick<Location, "pathname" | "search" | "hash">, label?: string): ReturnSource {
  return {
    pathname: location.pathname,
    search: location.search || "",
    hash: location.hash || "",
    label,
  };
}

export function readReturnSourceState(state: unknown): ReturnSource | undefined {
  if (!state || typeof state !== "object" || !("source" in state)) return undefined;
  const source = (state as ReturnSourceState).source;
  if (!source || typeof source.pathname !== "string") return undefined;
  return source;
}

export function resolveReturnTarget(source: ReturnSource | undefined, fallback = DEFAULT_RETURN_FALLBACK): string {
  const safeFallback = isSafeInternalPath(fallback) ? fallback : DEFAULT_RETURN_FALLBACK;
  if (!source || !isSafeInternalPath(source.pathname) || source.pathname === "/login") return safeFallback;
  return `${source.pathname}${source.search ?? ""}${source.hash ?? ""}`;
}

export function useReturnNavigation(fallback = DEFAULT_RETURN_FALLBACK) {
  const location = useLocation();
  const navigate = useNavigate();
  const source = readReturnSourceState(location.state);
  const target = resolveReturnTarget(source, fallback);

  return {
    source,
    target,
    goBack: () => navigate(target),
  };
}
