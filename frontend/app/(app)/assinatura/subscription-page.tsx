"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { StatusBadge } from "@/components/admin/kit";
import { PageHeader } from "@/components/page-header";
import { Alert, Button, Card, Spinner } from "@/components/ui";
import { dateTime } from "@/lib/admin";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDate } from "@/lib/essays";
import { PAYMENT_KIND, PAYMENT_STATUS, type PaymentRow, type Subscription, brl } from "@/lib/payments";

/** Assinatura: situação, pagamento pelo Mercado Pago (PIX ou cartão) e histórico. */
export function SubscriptionPage() {
  const router = useRouter();
  const returned = useSearchParams().get("pagamento");
  const { reloadUser } = useAuth();
  const [sub, setSub] = useState<Subscription | null>(null);
  const [result, setResult] = useState<PaymentRow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    () => api.GET("/api/v1/me/subscription").then(({ data, error: e }) => (data ? setSub(data) : setError(errorMessage(e)))),
    [],
  );

  const check = useCallback(async () => {
    if (!returned) return;
    const { data } = await api.POST("/api/v1/payments/{payment_id}/refresh", {
      params: { path: { payment_id: returned } },
    });
    if (data) {
      setResult(data);
      if (data.status === "approved") await reloadUser();
    }
    await load();
  }, [returned, reloadUser, load]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- carga inicial e volta do Mercado Pago
    if (returned) void check();
    else void load();
  }, [returned, check, load]);

  async function pay() {
    setBusy(true);
    setError(null);
    const { data, error: e } = await api.POST("/api/v1/payments/checkout", { body: { kind: "subscription" } });
    if (data) {
      window.location.href = data.checkout_url;
      return;
    }
    setBusy(false);
    setError(errorMessage(e));
  }

  if (!sub) return error ? <Alert>{error}</Alert> : <Spinner />;
  const until = sub.paid_until ? new Date(sub.paid_until) : null;

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title="Assinatura" />

      {result ? (
        result.status === "approved" ? (
          <Alert kind="success">
            Pagamento confirmado! Obrigado.{" "}
            <button type="button" className="font-medium underline" onClick={() => router.push("/painel")}>
              Ir para o painel
            </button>
          </Alert>
        ) : result.status === "pending" ? (
          <Alert kind="info">
            Ainda aguardando a confirmação do Mercado Pago (o PIX costuma cair em poucos segundos).{" "}
            <button type="button" className="font-medium underline" onClick={() => void check()}>
              Verificar de novo
            </button>
          </Alert>
        ) : (
          <Alert>O pagamento não foi aprovado. Tente de novo, se quiser com outra forma de pagamento.</Alert>
        )
      ) : null}
      {error ? <Alert>{error}</Alert> : null}

      <Card>
        {sub.free_access ? (
          <>
            <p className="font-medium text-slate-900">Sua conta não precisa de assinatura.</p>
            <p className="mt-1 text-sm text-slate-600">Você entrou por convite ou recebeu acesso liberado.</p>
          </>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <StatusBadge level={sub.active ? "ok" : "warning"}>{sub.active ? "Ativa" : "Inativa"}</StatusBadge>
              <p className="text-slate-700">
                {sub.active && until
                  ? `Seu acesso vai até ${formatDate(until.toISOString())}.`
                  : "Assine para corrigir redações, praticar questões e usar o cronograma."}
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <p className="text-3xl font-bold text-slate-900">
                {brl(sub.price_brl)}
                <span className="text-base font-medium text-slate-500"> / {sub.period_days} dias</span>
              </p>
              <p className="mt-1 text-sm text-slate-600">
                Cada pagamento vale {sub.period_days} dias a partir da confirmação. PIX ou cartão, pelo Mercado
                Pago. Não renova sozinho: avisamos por e-mail perto
                do vencimento. {sub.active ? "Pagando agora, os dias são somados ao seu período atual." : ""}
              </p>
            </div>
            <Button onClick={() => void pay()} disabled={busy}>
              {busy ? "Abrindo o Mercado Pago..." : sub.active ? "Renovar agora" : "Assinar com PIX ou cartão"}
            </Button>
          </div>
        )}
      </Card>

      {sub.payments.length ? (
        <section>
          <h2 className="mb-2 text-lg font-semibold text-slate-900">Seus pagamentos</h2>
          <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
            {sub.payments.map((p) => {
              const st = PAYMENT_STATUS[p.status];
              return (
                <li key={p.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
                  <span>
                    {PAYMENT_KIND[p.kind]} · {brl(p.amount)}
                    <span className="block text-xs text-slate-500">{dateTime(p.created_at)}</span>
                  </span>
                  <StatusBadge level={st.level}>{st.label}</StatusBadge>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
