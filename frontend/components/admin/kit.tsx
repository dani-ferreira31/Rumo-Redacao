"use client";

import { AlertTriangle, CheckCircle2, type LucideIcon, XCircle } from "lucide-react";

export type Level = "ok" | "warning" | "error";

export function AdminHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
        {description ? <p className="mt-1 max-w-2xl text-sm text-slate-600">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}

export function Section({
  title,
  description,
  actions,
  children,
  className = "",
}: {
  title?: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white shadow-sm ${className}`}>
      {title ? (
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
          <div>
            <h2 className="font-semibold text-slate-900">{title}</h2>
            {description ? <p className="mt-0.5 text-sm text-slate-500">{description}</p> : null}
          </div>
          {actions}
        </div>
      ) : null}
      <div className="p-5">{children}</div>
    </section>
  );
}

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "default",
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  icon?: LucideIcon;
  tone?: "default" | "warning" | "error";
}) {
  const ring = { default: "border-slate-200", warning: "border-amber-300", error: "border-red-300" }[tone];
  return (
    <div className={`rounded-xl border bg-white p-4 shadow-sm ${ring}`}>
      <div className="flex items-center justify-between gap-2 text-sm text-slate-500">
        <span>{label}</span>
        {Icon ? <Icon aria-hidden className="h-4 w-4 text-slate-400" /> : null}
      </div>
      <p className="mt-2 text-2xl font-semibold tabular-nums text-slate-900">{value}</p>
      {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

const LEVEL = {
  ok: { icon: CheckCircle2, cls: "bg-emerald-50 text-emerald-800 ring-emerald-200", label: "OK" },
  warning: { icon: AlertTriangle, cls: "bg-amber-50 text-amber-900 ring-amber-200", label: "Atenção" },
  error: { icon: XCircle, cls: "bg-red-50 text-red-800 ring-red-200", label: "Erro" },
} as const;

/** Status com ícone + texto (nunca só cor). */
export function StatusBadge({ level, children }: { level: Level; children?: React.ReactNode }) {
  const { icon: Icon, cls, label } = LEVEL[level];
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${cls}`}>
      <Icon aria-hidden className="h-3.5 w-3.5" />
      {children ?? label}
    </span>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
  description,
  disabled,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
}) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-4 py-3">
      <span>
        <span className="block text-sm font-medium text-slate-900">{label}</span>
        {description ? <span className="block text-sm text-slate-500">{description}</span> : null}
      </span>
      <span className="relative mt-0.5 inline-flex shrink-0">
        <input
          type="checkbox"
          role="switch"
          className="peer sr-only"
          checked={checked}
          disabled={disabled}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span className="h-6 w-11 rounded-full bg-slate-300 transition-colors peer-checked:bg-indigo-600 peer-focus-visible:ring-2 peer-focus-visible:ring-indigo-500 peer-focus-visible:ring-offset-2 peer-disabled:opacity-50" />
        <span className="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform peer-checked:translate-x-5" />
      </span>
    </label>
  );
}

/** Barra de progresso do orçamento: muda de tom em 80% e 100%. */
export function BudgetBar({ pct }: { pct: number | null | undefined }) {
  if (pct === null || pct === undefined) return null;
  const tone = pct >= 100 ? "bg-red-600" : pct >= 80 ? "bg-amber-500" : "bg-indigo-600";
  return (
    <div
      className="h-2 w-full overflow-hidden rounded-full bg-slate-100"
      role="progressbar"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label="Uso do orçamento"
    >
      <div className={`h-full rounded-full ${tone}`} style={{ width: `${Math.min(pct, 100)}%` }} />
    </div>
  );
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return <p className="rounded-lg border border-dashed border-slate-200 p-6 text-center text-sm text-slate-500">{children}</p>;
}
