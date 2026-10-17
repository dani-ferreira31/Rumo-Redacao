import type { components } from "@/lib/api-schema";

type S = components["schemas"];
export type BillingPublic = S["BillingPublic"];
export type Subscription = S["SubscriptionOut"];
export type PaymentRow = S["PaymentOut"];
export type AdminPayments = S["AdminPaymentsOut"];
export type BillingAdmin = S["BillingAdminOut"];

export const brl = (v: number | string) =>
  Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export const PAYMENT_STATUS: Record<string, { label: string; level: "ok" | "warning" | "error" }> = {
  pending: { label: "Aguardando", level: "warning" },
  approved: { label: "Aprovado", level: "ok" },
  rejected: { label: "Recusado", level: "error" },
  cancelled: { label: "Cancelado", level: "error" },
  refunded: { label: "Estornado", level: "error" },
};

export const PAYMENT_KIND: Record<string, string> = { subscription: "Assinatura", donation: "Doação" };

/** Páginas que quem está sem assinatura ainda pode abrir. */
export const UNPAID_ALLOWED = ["/assinatura", "/apoiar", "/perfil"];
