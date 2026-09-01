/**
 * Feature: V1.1 shared toast hook.
 * Responsibilities: expose neutral toast calls to later feature components.
 * Does not own: business API outcomes, task action messages, or notification persistence.
 * Plan task: DEV-01.
 */

import { useContext } from "react";

import { ToastContext } from "./toast-context";

export function useToast() {
  const value = useContext(ToastContext);
  if (!value) throw new Error("useToast must be used within ToastProvider");
  return value;
}
