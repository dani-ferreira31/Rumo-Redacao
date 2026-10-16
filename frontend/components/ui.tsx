import { forwardRef, useId } from "react";

export function Button({
  variant = "primary",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger" | "ghost";
}) {
  const styles = {
    primary: "bg-indigo-600 text-white hover:bg-indigo-700 disabled:bg-indigo-300",
    secondary:
      "border border-slate-300 bg-white text-slate-800 hover:bg-slate-50 disabled:text-slate-400",
    danger: "bg-red-600 text-white hover:bg-red-700 disabled:bg-red-300",
    ghost: "text-slate-700 hover:bg-slate-100",
  }[variant];
  return (
    <button
      className={`inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed ${styles} ${className}`}
      {...props}
    />
  );
}

type FieldProps = React.InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string;
  hint?: string;
};

export const TextField = forwardRef<HTMLInputElement, FieldProps>(function TextField(
  { label, error, hint, id, className = "", ...props },
  ref,
) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const describedBy = error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined;
  return (
    <div className={className}>
      <label htmlFor={inputId} className="mb-1 block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        ref={ref}
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={`block w-full rounded-md border bg-white px-3 py-2 text-slate-900 shadow-sm outline-none focus:ring-2 focus:ring-indigo-500 ${
          error ? "border-red-500" : "border-slate-300"
        }`}
        {...props}
      />
      {error ? (
        <p id={`${inputId}-error`} className="mt-1 text-sm text-red-600">
          {error}
        </p>
      ) : hint ? (
        <p id={`${inputId}-hint`} className="mt-1 text-sm text-slate-500">
          {hint}
        </p>
      ) : null}
    </div>
  );
});

export function Alert({
  kind = "error",
  children,
}: {
  kind?: "error" | "success" | "info" | "warning";
  children: React.ReactNode;
}) {
  const styles = {
    error: "border-red-200 bg-red-50 text-red-800",
    success: "border-green-200 bg-green-50 text-green-800",
    info: "border-indigo-200 bg-indigo-50 text-indigo-800",
    warning: "border-amber-200 bg-amber-50 text-amber-900",
  }[kind];
  return (
    <div role={kind === "error" ? "alert" : "status"} className={`rounded-md border p-3 text-sm ${styles}`}>
      {children}
    </div>
  );
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-lg border border-slate-200 bg-white p-6 shadow-sm ${className}`}>
      {children}
    </section>
  );
}

export function Spinner({ label = "Carregando..." }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 text-slate-500">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600" />
      <span className="text-sm">{label}</span>
    </div>
  );
}
