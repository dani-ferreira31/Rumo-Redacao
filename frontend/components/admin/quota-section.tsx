"use client";

import { useEffect, useState } from "react";

import { Section, StatusBadge } from "@/components/admin/kit";
import { Button } from "@/components/ui";
import { type QuotaRule, type QuotaUsage, fmtCompact, fmtInt } from "@/lib/admin";
import { api, errorMessage } from "@/lib/api";

const REFRESH_MS = 30_000;
const PROVIDER_LABEL: Record<string, string> = { google: "Google", openai: "OpenAI", anthropic: "Anthropic" };

function Meter({ label, used, limit, pct, hint }: { label: string; used: number; limit?: number | null; pct?: number | null; hint?: string }) {
  const tone = pct == null ? "bg-slate-400" : pct >= 100 ? "bg-red-600" : pct >= 80 ? "bg-amber-500" : "bg-indigo-600";
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span className="text-slate-600">{label}</span>
        <span className="tabular-nums font-medium text-slate-900">
          {fmtInt(used)}
          {limit ? <span className="font-normal text-slate-500"> / {fmtInt(limit)}</span> : null}
        </span>
      </div>
      <div
        className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-100"
        role="progressbar"
        aria-label={label}
        aria-valuenow={pct == null ? undefined : Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className={`h-full rounded-full ${tone}`} style={{ width: `${Math.min(pct ?? 0, 100)}%` }} />
      </div>
      {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

function resetsIn(iso: string) {
  const mins = Math.max(0, Math.round((new Date(iso).getTime() - Date.now()) / 60000));
  const h = Math.floor(mins / 60);
  const time = new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  return `zera às ${time} (em ${h ? `${h} h ` : ""}${mins % 60} min)`;
}

function QuotaCard({ q }: { q: QuotaUsage }) {
  const level = q.level === "ok" ? "ok" : q.level === "warning" ? "warning" : "error";
  const max = Math.max(1, ...q.history.map((d) => d.requests));
  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-medium text-slate-900">
            {PROVIDER_LABEL[q.rule.provider]} · modelos com “{q.rule.model_match}”
          </p>
          <p className="text-xs text-slate-500">
            {q.models.length ? `Em uso: ${q.models.join(", ")}` : "Nenhuma chamada registrada ainda."}
          </p>
        </div>
        <StatusBadge level={level}>{level === "ok" ? "Dentro da cota" : level === "warning" ? "Perto do limite" : "Limite atingido"}</StatusBadge>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Meter label="Requisições hoje" used={q.rpd.used} limit={q.rpd.limit} pct={q.rpd.pct} hint={resetsIn(q.day_resets_at)} />
        <Meter label="Requisições no último minuto" used={q.rpm.used} limit={q.rpm.limit} pct={q.rpm.pct} hint={`Pico hoje: ${q.peak_rpm_today}/min`} />
        <Meter label="Tokens de entrada no último minuto" used={q.tpm.used} limit={q.tpm.limit} pct={q.tpm.pct} />
      </div>
      <p className="mt-3 text-xs text-slate-500">
        Hoje: {fmtCompact(q.input_tokens_today)} tokens de entrada e {fmtCompact(q.output_tokens_today)} de saída.
      </p>
      {q.history.length ? (
        <div className="mt-3">
          <p className="mb-1 text-xs text-slate-500">Requisições por dia (últimos 7 dias, horário do Pacífico)</p>
          <ul className="space-y-1">
            {q.history.map((d) => (
              <li key={d.day} className="flex items-center gap-2 text-xs">
                <span className="w-12 shrink-0 tabular-nums text-slate-500">
                  {new Date(`${d.day}T12:00:00`).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })}
                </span>
                <span className="h-2 rounded-full bg-indigo-500" style={{ width: `${(d.requests / max) * 70}%` }} />
                <span className="tabular-nums text-slate-700">{fmtInt(d.requests)}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function RulesEditor({ rules, onSaved }: { rules: QuotaRule[]; onSaved: (q: QuotaUsage[]) => void }) {
  const [rows, setRows] = useState(rules);
  const [message, setMessage] = useState<{ kind: "error" | "success"; text: string } | null>(null);

  function set(i: number, field: keyof QuotaRule, value: string) {
    setRows((prev) =>
      prev.map((r, idx) =>
        idx !== i ? r : { ...r, [field]: field === "provider" || field === "model_match" ? value : value === "" ? null : Number(value) },
      ),
    );
  }

  async function save() {
    const { data, error } = await api.PUT("/api/v1/admin/ai/quotas", { body: { quotas: rows } });
    if (data) {
      onSaved(data.quotas);
      setMessage({ kind: "success", text: "Limites salvos." });
    } else setMessage({ kind: "error", text: errorMessage(error) });
  }

  const input = "w-full rounded-md border border-slate-300 px-2 py-1 text-sm tabular-nums";
  return (
    <div className="mt-4 space-y-3 border-t border-slate-100 pt-4">
      <p className="text-sm text-slate-600">
        Copie os limites do seu plano em <strong>Google AI Studio → Rate limits</strong>. O app conta só as chamadas
        que deram certo; erros de cota (429) não entram na conta.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[36rem] text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-500">
              <th className="py-1 pr-2 font-medium">Provedor</th>
              <th className="py-1 pr-2 font-medium">Nome do modelo contém</th>
              <th className="py-1 pr-2 font-medium">Req./min</th>
              <th className="py-1 pr-2 font-medium">Tokens/min</th>
              <th className="py-1 pr-2 font-medium">Req./dia</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td className="py-1 pr-2">
                  <select aria-label="Provedor" className={input} value={r.provider} onChange={(e) => set(i, "provider", e.target.value)}>
                    {Object.entries(PROVIDER_LABEL).map(([id, label]) => (
                      <option key={id} value={id}>
                        {label}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="py-1 pr-2">
                  <input aria-label="Nome do modelo contém" className={input} value={r.model_match} onChange={(e) => set(i, "model_match", e.target.value)} />
                </td>
                {(["rpm", "tpm", "rpd"] as const).map((f) => (
                  <td key={f} className="py-1 pr-2">
                    <input aria-label={f} type="number" min={1} className={input} value={r[f] ?? ""} onChange={(e) => set(i, f, e.target.value)} />
                  </td>
                ))}
                <td className="py-1">
                  <button type="button" className="text-sm text-red-700 hover:underline" onClick={() => setRows(rows.filter((_, idx) => idx !== i))}>
                    Remover
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="secondary" onClick={() => setRows([...rows, { provider: "google", model_match: "", rpm: null, tpm: null, rpd: null }])}>
          Adicionar modelo
        </Button>
        <Button onClick={() => void save()}>Salvar limites</Button>
        {message ? (
          <span role="status" className={`text-sm ${message.kind === "error" ? "text-red-700" : "text-emerald-700"}`}>
            {message.text}
          </span>
        ) : null}
      </div>
    </div>
  );
}

/** Uso do plano gratuito (ex.: Gemini Flash-Lite), contado pelo app e atualizado a cada 30 s. */
export function QuotaSection() {
  const [quotas, setQuotas] = useState<QuotaUsage[] | null>(null);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    let active = true;
    const load = () =>
      api.GET("/api/v1/admin/ai/quotas").then(({ data }) => {
        if (active && data) setQuotas(data.quotas);
      });
    void load();
    const id = setInterval(load, REFRESH_MS);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  return (
    <Section
      title="Cota do plano gratuito"
      description="O Google não informa o saldo da cota; o app conta as próprias chamadas e compara com os limites abaixo. O dia da cota vira à meia-noite do horário do Pacífico."
      actions={
        <Button variant="secondary" onClick={() => setEditing((v) => !v)} disabled={!quotas}>
          {editing ? "Fechar limites" : "Editar limites"}
        </Button>
      }
    >
      {!quotas ? (
        <p className="text-sm text-slate-500">Carregando...</p>
      ) : (
        <div className="space-y-4">
          {quotas.length === 0 ? <p className="text-sm text-slate-500">Nenhum limite cadastrado.</p> : null}
          {quotas.map((q, i) => (
            <QuotaCard key={`${q.rule.provider}-${q.rule.model_match}-${i}`} q={q} />
          ))}
          {editing ? (
            <RulesEditor
              rules={quotas.map((q) => q.rule)}
              onSaved={(next) => {
                setQuotas(next);
                setEditing(false);
              }}
            />
          ) : null}
        </div>
      )}
    </Section>
  );
}
