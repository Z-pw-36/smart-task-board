/**
 * Feature: V1.1 shared toast primitive.
 * Responsibilities: provide neutral toast state and rendering for later feature composition.
 * Does not own: business API outcomes, task action messages, or notification persistence.
 * Plan task: DEV-01.
 */

import { type ReactNode, useState } from "react";

import "./primitives.css";
import { ToastContext } from "./toast-context";

type ToastItem = { id: number; message: string };

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const showToast = (message: string) => {
    const id = Date.now();
    setItems((current) => [...current, { id, message }]);
    window.setTimeout(() => setItems((current) => current.filter((item) => item.id !== id)), 2500);
  };
  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="stb-toast-region" role="status" aria-live="polite">
        {items.map((item) => <div key={item.id} className="stb-toast">{item.message}</div>)}
      </div>
    </ToastContext.Provider>
  );
}
