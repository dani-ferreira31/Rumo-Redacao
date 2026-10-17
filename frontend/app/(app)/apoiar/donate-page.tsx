"use client";

import { Heart } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Alert, Button, Card, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { type BillingPublic, type PaymentRow, brl } from "@/lib/payments";

const SUGGESTED = [5, 10, 20, 50];

/** Doação de valor livre (PIX ou cartão pelo Mercado Pago), aberta a todos. */
export function DonatePage() {
  const returned = useSearchParams().get("pagamento");
  const [billing, setBilling] = useState<BillingPublic | null>(null);
  const [amount, setAmount] = useState("10");
  const [result, setResult] = useState<PaymentRow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.GET("/api/v1/billing").then(({ data }) => setBilling(data ?? null));
  }, []);

  useEffect(() => {
    if (!returned) return;
    api
      .POST("/api/v1/payments/{payment_id}/refresh", { params: { path: { payment_id: returned } } })
      .then(({ data }) => setResult(data ?? null));
  }, [returned]);

  async function donate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const value = Number(amount.replace(",", "."));
    const { data, error: err } = await api.POST("/api/v1/payments/checkout", {
      body: { kind: "donation", amount: value.toFixed(2) },
    });
    if (data) {
      window.location.href = data.checkout_url;
      return;
    }
    setBusy(false);
    setError(errorMessage(err));
  }

  if (!billing) return <Spinner />;

  return (
    <div className="max-w-xl space-y-6">
      <PageHeader
        title="Apoie o Rumo1000"
        description="O Rumo1000 é mantido por uma equipe pequena. As doações pagam o servidor e a inteligência artificial que corrige as redações."
      />
      {result?.status === "approved" ? (
        <Alert kind="success">Recebemos sua doação de {brl(result.amount)}. Muito obrigado!</Alert>
      ) : result?.status === "pending" ? (
        <Alert kind="info">Sua doação está aguardando a confirmação do Mercado Pago. Obrigado!</Alert>
      ) : result ? (
        <Alert>O pagamento não foi aprovado. Você pode tentar de novo.</Alert>
      ) : null}

      {!billing.donations_enabled ? (
        <Alert kind="info">As doações estão fechadas no momento.</Alert>
      ) : (
        <Card>
          <form onSubmit={donate} className="space-y-4">
            <fieldset>
              <legend className="mb-2 text-sm font-medium text-slate-700">Escolha um valor</legend>
              <div className="flex flex-wrap gap-2">
                {SUGGESTED.map((v) => (
                  <button
                    key={v}
                    type="button"
                    aria-pressed={amount === String(v)}
                    onClick={() => setAmount(String(v))}
                    className={`rounded-md border px-4 py-2 text-sm font-medium ${
                      amount === String(v)
                        ? "border-indigo-600 bg-indigo-50 text-indigo-800"
                        : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                    }`}
                  >
                    {brl(v)}
                  </button>
                ))}
              </div>
            </fieldset>
            <div>
              <label htmlFor="amount" className="mb-1 block text-sm font-medium text-slate-700">
                Ou digite outro valor (R$)
              </label>
              <input
                id="amount"
                inputMode="decimal"
                value={amount}
                onChange={(e) => setAmount(e.target.value.replace(/[^\d,.]/g, ""))}
                className="block w-40 rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 shadow-sm"
              />
              <p className="mt-1 text-sm text-slate-500">
                De {brl(billing.donation_min)} a {brl(billing.donation_max)}. PIX ou cartão, pelo Mercado Pago.
              </p>
            </div>
            {error ? <Alert>{error}</Alert> : null}
            <Button type="submit" disabled={busy || !amount}>
              <Heart aria-hidden className="mr-2 h-4 w-4" />
              {busy ? "Abrindo o Mercado Pago..." : `Doar ${brl(Number(amount.replace(",", ".")) || 0)}`}
            </Button>
          </form>
        </Card>
      )}
    </div>
  );
}
