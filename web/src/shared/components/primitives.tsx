/**
 * Feature: V1.1 shared mobile visual primitives.
 * Responsibilities: provide accessible neutral React building blocks from the HTML visual language.
 * Does not own: business API calls, page routing, or task status mapping.
 * Plan task: DEV-01.
 */

import { type ElementType, forwardRef, type ButtonHTMLAttributes, type HTMLAttributes, type InputHTMLAttributes, type ReactNode, useEffect, useId, useRef } from "react";
import "./primitives.css";

type Tone = "info" | "success" | "warning" | "danger" | "neutral";

function cx(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

export function Card({ title, children, interactive = false, className, ...props }: HTMLAttributes<HTMLElement> & { title?: ReactNode; interactive?: boolean }) {
  return (
    <section className={cx("stb-card", interactive && "stb-card--interactive", className)} {...props}>
      {title && <h2 className="stb-card__title">{title}</h2>}
      <div className="stb-card__body">{children}</div>
    </section>
  );
}

export function Typography({ variant, as: Tag = "p", className, children }: { variant: "pageTitle" | "sectionTitle" | "cardTitle" | "body" | "secondary" | "caption" | "label" | "button" | "status" | "metric"; as?: ElementType; className?: string; children: ReactNode }) {
  const classMap = {
    pageTitle: "stb-text-page-title",
    sectionTitle: "stb-text-section-title",
    cardTitle: "stb-text-card-title",
    body: "stb-text-body",
    secondary: "stb-text-secondary",
    caption: "stb-text-caption",
    label: "stb-text-label",
    button: "stb-text-button",
    status: "stb-text-status",
    metric: "stb-text-metric",
  };
  return <Tag className={cx(classMap[variant], className)}>{children}</Tag>;
}

export function Badge({ tone = "info", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return <span className={cx("stb-badge", `stb-badge--${tone}`, className)}>{children}</span>;
}

export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger"; loading?: boolean; iconOnly?: boolean }>(function Button(
  { variant = "primary", loading = false, iconOnly = false, children, disabled, className, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      className={cx("stb-button", `stb-button--${variant}`, iconOnly && "stb-button--icon", className)}
      disabled={disabled || loading}
      type={props.type ?? "button"}
      {...props}
    >
      {loading && <span className="stb-button__spinner" aria-hidden="true" />}
      <span>{children}</span>
    </button>
  );
});

export function Input({ label, helperText, error, id, className, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string; helperText?: string; error?: string }) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const labelId = `${inputId}-label`;
  const helperId = helperText ? `${inputId}-helper` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  const describedBy = [helperId, errorId].filter(Boolean).join(" ") || undefined;

  return (
    <label className={cx("stb-field", className)} htmlFor={inputId}>
      <span id={labelId} className="stb-field__label">{label}</span>
      <input className="stb-field__control" id={inputId} aria-labelledby={labelId} aria-invalid={Boolean(error)} aria-describedby={describedBy} {...props} />
      {helperText && <span id={helperId} className="stb-field__helper">{helperText}</span>}
      {error && <span id={errorId} className="stb-field__error">{error}</span>}
    </label>
  );
}

export function Progress({ value, label }: { value: number; label?: string }) {
  const safeValue = Math.min(100, Math.max(0, value));
  return (
    <div className="stb-progress" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={safeValue}>
      <div className="stb-progress__head">
        <span>{label}</span>
        <span>{safeValue}%</span>
      </div>
      <div className="stb-progress__track"><span className="stb-progress__bar" style={{ width: `${safeValue}%` }} /></div>
    </div>
  );
}

export function TopBar({ title, subtitle, leading, actions }: { title: string; subtitle?: string; leading?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="stb-top-bar">
      {leading}
      <div className="stb-top-bar__title">
        <Typography variant="pageTitle" as="h1">{title}</Typography>
        {subtitle && <Typography variant="secondary">{subtitle}</Typography>}
      </div>
      {actions && <div className="stb-top-bar__actions">{actions}</div>}
    </header>
  );
}

export function BottomNavigation({ items, activeId, onSelect }: { items: Array<{ id: string; label: string; icon: ReactNode }>; activeId: string; onSelect?: (id: string) => void }) {
  return (
    <nav className="stb-bottom-nav" aria-label="底部导航">
      {items.map((item) => (
        <button
          key={item.id}
          className={cx("stb-bottom-nav__item", item.id === activeId && "stb-bottom-nav__item--active")}
          aria-current={item.id === activeId ? "page" : undefined}
          onClick={() => onSelect?.(item.id)}
          type="button"
        >
          <span aria-hidden="true">{item.icon}</span>
          <span>{item.label}</span>
        </button>
      ))}
    </nav>
  );
}

function useDismissible(open: boolean, onClose: () => void) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);
  return closeRef;
}

export function Sheet({ open, title, children, onClose }: { open: boolean; title: string; children: ReactNode; onClose: () => void }) {
  const titleId = useId();
  const closeRef = useDismissible(open, onClose);
  if (!open) return null;
  return (
    <div className="stb-overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="stb-sheet" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="stb-sheet__head">
          <h2 id={titleId} className="stb-sheet__title">{title}</h2>
          <Button ref={closeRef} variant="ghost" iconOnly aria-label="关闭抽屉" onClick={onClose}>×</Button>
        </div>
        {children}
      </section>
    </div>
  );
}

export function Dialog({ open, title, children, onClose, actions }: { open: boolean; title: string; children: ReactNode; onClose: () => void; actions?: ReactNode }) {
  const titleId = useId();
  const closeRef = useDismissible(open, onClose);
  if (!open) return null;
  return (
    <div className="stb-overlay stb-dialog-wrap" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="stb-dialog" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="stb-dialog__head">
          <h2 id={titleId} className="stb-dialog__title">{title}</h2>
          <Button ref={closeRef} variant="ghost" iconOnly aria-label="关闭弹窗" onClick={onClose}>×</Button>
        </div>
        <div>{children}</div>
        {actions && <div className="stb-top-bar__actions">{actions}</div>}
      </section>
    </div>
  );
}

export function Skeleton({ width = "100%", height = 16, label = "正在加载" }: { width?: number | string; height?: number | string; label?: string }) {
  return <span className="stb-skeleton" role="status" aria-label={label} style={{ width, height }} />;
}

export function EmptyState({ title, detail, action }: { title: string; detail?: string; action?: ReactNode }) {
  return (
    <section className="stb-state">
      <div className="stb-state__title">{title}</div>
      {detail && <div className="stb-state__detail">{detail}</div>}
      {action}
    </section>
  );
}

export function ErrorState({ title = "内容暂时无法加载", detail, action }: { title?: string; detail?: string; action?: ReactNode }) {
  return (
    <section className="stb-state stb-state--error" role="alert">
      <div className="stb-state__title">{title}</div>
      {detail && <div className="stb-state__detail">{detail}</div>}
      {action}
    </section>
  );
}
