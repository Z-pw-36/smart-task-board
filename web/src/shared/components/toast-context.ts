/**
 * Feature: V1.1 shared toast context.
 * Responsibilities: hold the neutral toast context shared by provider and hook.
 * Does not own: business API outcomes, task action messages, or notification persistence.
 * Plan task: DEV-01.
 */

import { createContext } from "react";

export const ToastContext = createContext<{ showToast: (message: string) => void } | null>(null);
