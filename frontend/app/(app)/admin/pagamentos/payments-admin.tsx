"use client";

import { useEffect, useState } from "react";

import { AdminHeader, EmptyState, Section, StatCard, StatusBadge, Toggle } from "@/components/admin/kit";
import { Alert, Button, Spinner, TextField } from "@/components/ui";
import { dateTime } from "@/lib/admin";
import { api, errorMessage } from "@/lib/api";
import { type AdminPayments, type BillingAdmin, PAYMENT_KIND, PAYMENT_STATUS, brl } from "@/lib/payments";

export function PaymentsAdmin() {
  const [settings, setSettings] = useState<BillingAdmin | null>(null);
  const [report, setReport] = useState<AdminPayments | null>(null);
  const [price, setPrice] = useState("");
  const [days, setDays] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => {
    api.GET("/api/v1/admin/payments/settings").then(({ data, error: e }) => {
      if (!data) return setError(errorMessage(e));
      setSettings(data);
      setPrice(String(data.price_brl));
      setDays(String(data.period_days));
    });
    api.GET("/api/v1/admin/payments").then(({ data }) => setReport(data ?? null));
  }, []);

  async function save(next: Partial<BillingAdmin>) {
    if (!settings) return;
    setError(null);
    setSaved(null);
    const body = {
      enabled: next.enabled ?? settings.enabled,
      donations_enabled: next.donations_enabled ?? settings.donations_enabled,
      price_brl: Number(price.replace(",", ".")),
      period_days: Number(days),
    };
    const { data, error: e } = await api.PUT("/api/v1/admin/payments/settings", { body });
    if (data) {
      setSettings(data);
      setSaved("Salvo.");
    } else setError(errorMessage(e));
  }

  return (
    <div className="max-w-5xl space-y-6">
      <AdminHeader
        title="Pagamentos"
        description="Assinatura para quem se cadastra sem convite e doações de qualquer usuário, pelo Mercado Pago (PIX ou cartão). Quem entra por convite não paga."
      />
      {error ? <Alert>{error}</Alert> : null}
      {settings && !settings.mercadopago_configured ? (
        <Alert kind="warning">
          Defina <code>MERCADOPAGO_ACCESS_TOKEN</code> no <code>.env</code> do servidor e reinicie o backend para
          ligar os pagamentos.
        </Alert>
      ) : null}
      {settings?.mercadopago_configured && !settings.webhook_secret_configured ? (
        <Alert kind="info">
          Recomendado: cadastre a notificação (webhook) no Mercado Pago e defina{" "}
          <code>MERCADOPAGO_WEBHOOK_SECRET</code>. Sem ela, o pagamento só é confirmado quando o aluno volta ao site.
        </Alert>
      ) : null}

      <Section title="Configuração">
        {!settings ? (
          <Spinner />
        ) : (
          <div className="space-y-2">
            <div className="divide-y divide-slate-100">
              <Toggle
                label="Cadastro aberto com assinatura"
                description="Ligado, qualquer pessoa cria a conta em /cadastro e assina para usar. Desligado, o cadastro é só por convite."
                checked={settings.enabled}
                disabled={!settings.mercadopago_configured}
                onChange={(v) => void save({ enabled: v })}
              />
              <Toggle
                label="Doações"
                description="Mostra “Apoiar o projeto” no menu de todos os usuários."
                checked={settings.donations_enabled}
                disabled={!settings.mercadopago_configured}
                onChange={(v) => void save({ donations_enabled: v })}
              />
            </div>
            <form
              className="flex flex-wrap items-end gap-3 pt-2"
              onSubmit={(e) => {
                e.preventDefault();
                void save({});
              }}
            >
              <TextField label="Preço da assinatura (R$)" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} />
              <TextField label="Dias de acesso por pagamento" type="number" min={1} max={366} value={days} onChange={(e) => setDays(e.target.value)} />
              <Button type="submit" variant="secondary">
                Salvar preço
              </Button>
              {saved ? <span role="status" className="pb-2 text-sm text-emerald-700">{saved}</span> : null}
            </form>
          </div>
        )}
      </Section>

      {!report ? (
        <Spinner />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-4">
            <StatCard label="Assinaturas no mês" value={brl(report.summary.month_subscriptions_brl)} />
            <StatCard label="Doações no mês" value={brl(report.summary.month_donations_brl)} />
            <StatCard label="Assinantes ativos" value={report.summary.active_subscribers} />
            <StatCard label="Aguardando (24 h)" value={report.summary.pending} hint="Abriram o pagamento e não concluíram" />
          </div>
          <Section title="Últimos pagamentos">
            {report.payments.length === 0 ? (
              <EmptyState>Nenhum pagamento ainda.</EmptyState>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[36rem] text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                      <th className="py-2 pr-3 font-medium">Quem</th>
                      <th className="py-2 pr-3 font-medium">Tipo</th>
                      <th className="py-2 pr-3 text-right font-medium">Valor</th>
                      <th className="py-2 pr-3 font-medium">Situação</th>
                      <th className="py-2 font-medium">Quando</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.payments.map((p) => {
                      const st = PAYMENT_STATUS[p.status];
                      return (
                        <tr key={p.id} className="border-b border-slate-100 last:border-0">
                          <td className="py-2 pr-3">
                            {p.user_name ?? "Conta excluída"}
                            {p.user_email ? <span className="block text-xs text-slate-500">{p.user_email}</span> : null}
                          </td>
                          <td className="py-2 pr-3">{PAYMENT_KIND[p.kind]}</td>
                          <td className="py-2 pr-3 text-right tabular-nums">{brl(p.amount)}</td>
                          <td className="py-2 pr-3">
                            <StatusBadge level={st.level}>{st.label}</StatusBadge>
                            {p.method ? <span className="ml-1 text-xs text-slate-500">{p.method === "bank_transfer" ? "PIX" : p.method}</span> : null}
                          </td>
                          <td className="py-2 text-slate-600">{dateTime(p.paid_at ?? p.created_at)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Section>
        </>
      )}
    </div>
  );
}
