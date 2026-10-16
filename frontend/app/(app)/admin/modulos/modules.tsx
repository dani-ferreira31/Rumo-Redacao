"use client";

import { useEffect, useState } from "react";

import { AdminHeader, Section, Toggle } from "@/components/admin/kit";
import { Alert, Button, Spinner, TextField } from "@/components/ui";
import type { Feature, Limits } from "@/lib/admin";
import { api, errorMessage } from "@/lib/api";

const DESCRIPTIONS: Record<string, string> = {
  essays: "Envio e correção de redações por IA.",
  questions_enem: "Banco de questões oficiais do ENEM.",
  questions_concursos: "Questões das provas de concurso importadas.",
  planner: "Grade semanal de estudos.",
  registration: "Desligado, ninguém novo consegue criar conta (quem já tem continua entrando).",
  email_reminders: "Lembretes dos blocos do cronograma por e-mail.",
};

export function ModulesPanel() {
  const [features, setFeatures] = useState<Feature[] | null>(null);
  const [limits, setLimits] = useState<Limits | null>(null);
  const [perMonth, setPerMonth] = useState("");
  const [budget, setBudget] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.GET("/api/v1/admin/settings/features").then(({ data, error: e }) => (data ? setFeatures(data) : setError(errorMessage(e))));
    api.GET("/api/v1/admin/settings/limits").then(({ data }) => {
      if (!data) return;
      setLimits(data);
      setPerMonth(data.essays_per_month ? String(data.essays_per_month) : "");
      setBudget(data.ai_budget_usd ? String(data.ai_budget_usd) : "");
    });
  }, []);

  async function toggle(name: string, enabled: boolean) {
    setFeatures((prev) => prev?.map((f) => (f.name === name ? { ...f, enabled } : f)) ?? prev);
    const { data, error: e } = await api.PUT("/api/v1/admin/settings/features", {
      body: { features: { [name]: enabled } },
    });
    if (data) setFeatures(data);
    else setError(errorMessage(e));
  }

  async function saveLimits(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaved(null);
    const body = {
      essays_per_month: perMonth ? Number(perMonth) : null,
      ai_budget_usd: budget ? Number(budget.replace(",", ".")) : null,
    };
    const { data, error: err } = await api.PUT("/api/v1/admin/settings/limits", { body });
    setSaving(false);
    if (data) {
      setLimits(data);
      setSaved("Limites salvos.");
      setError(null);
    } else setError(errorMessage(err));
  }

  return (
    <div className="max-w-3xl space-y-6">
      <AdminHeader
        title="Módulos e limites"
        description="Liga e desliga partes da plataforma para os alunos. Como admin, você continua vendo tudo para testar."
      />
      {error ? <Alert>{error}</Alert> : null}

      <Section title="Módulos">
        {!features ? (
          <Spinner />
        ) : (
          <div className="divide-y divide-slate-100">
            {features.map((f) => (
              <Toggle
                key={f.name}
                label={f.label}
                description={DESCRIPTIONS[f.name]}
                checked={f.enabled}
                onChange={(v) => void toggle(f.name, v)}
              />
            ))}
          </div>
        )}
      </Section>

      <Section
        title="Limites de uso"
        description="Deixe em branco para não limitar. O mês segue o horário de Brasília."
      >
        {!limits ? (
          <Spinner />
        ) : (
          <form onSubmit={saveLimits} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <TextField
                label="Redações por aluno por mês"
                type="number"
                min={1}
                max={1000}
                inputMode="numeric"
                value={perMonth}
                onChange={(e) => setPerMonth(e.target.value)}
                hint="Ao atingir, o aluno vê uma mensagem até o mês virar."
              />
              <TextField
                label="Orçamento mensal de IA (US$)"
                type="number"
                min={0.01}
                step={0.01}
                inputMode="decimal"
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                hint="Aviso por e-mail em 80%. Em 100%, novos envios pausam."
              />
            </div>
            <div className="flex items-center gap-3">
              <Button type="submit" disabled={saving}>
                {saving ? "Salvando..." : "Salvar limites"}
              </Button>
              {saved ? <span role="status" className="text-sm text-emerald-700">{saved}</span> : null}
            </div>
          </form>
        )}
      </Section>
    </div>
  );
}
