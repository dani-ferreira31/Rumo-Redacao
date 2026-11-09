"use client";

import { useEffect, useState } from "react";

import { MessageFields } from "@/components/admin/message-fields";
import { Section, Toggle } from "@/components/admin/kit";
import { Alert, Button, Spinner, TextField } from "@/components/ui";
import type { WelcomeSettings } from "@/lib/admin";
import { api, errorMessage } from "@/lib/api";

export function WelcomeMessage() {
  const [cfg, setCfg] = useState<WelcomeSettings | null>(null);
  const [delay, setDelay] = useState("5");
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.GET("/api/v1/admin/messages/welcome").then(({ data, error: e }) => {
      if (!data) return setError(errorMessage(e));
      setCfg(data);
      setDelay(String(data.delay_minutes ?? 5));
    });
  }, []);

  async function save(next: Partial<WelcomeSettings> = {}) {
    if (!cfg) return;
    setBusy(true);
    setError(null);
    setStatus(null);
    const body = { ...cfg, ...next, delay_minutes: Number(delay) };
    const { data, error: e } = await api.PUT("/api/v1/admin/messages/welcome", { body });
    setBusy(false);
    if (data) {
      setCfg(data);
      setStatus("Salvo.");
    } else setError(errorMessage(e));
  }

  async function test() {
    if (!cfg) return;
    setBusy(true);
    setError(null);
    setStatus(null);
    const { error: e } = await api.POST("/api/v1/admin/messages/welcome/test", {
      body: { subject: cfg.subject, body: cfg.body },
    });
    setBusy(false);
    if (e) setError(errorMessage(e));
    else setStatus("Teste enviado para o seu e-mail.");
  }

  return (
    <Section
      title="Mensagem de boas-vindas"
      description="Enviada por e-mail na primeira assinatura aprovada de cada aluno, alguns minutos depois do “pagamento confirmado”. Renovações não recebem de novo."
    >
      {!cfg ? (
        error ? <Alert>{error}</Alert> : <Spinner />
      ) : (
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <div className="divide-y divide-slate-100">
            <Toggle
              label="Enviar boas-vindas automaticamente"
              description="Desligado, ninguém recebe. Você ainda pode mandar mensagens avulsas em Usuários."
              checked={cfg.enabled ?? false}
              disabled={busy}
              onChange={(v) => void save({ enabled: v })}
            />
          </div>
          <MessageFields
            subject={cfg.subject}
            body={cfg.body}
            onSubject={(v) => setCfg({ ...cfg, subject: v })}
            onBody={(v) => setCfg({ ...cfg, body: v })}
          />
          <TextField
            label="Minutos depois do pagamento"
            type="number"
            min={0}
            max={1440}
            value={delay}
            onChange={(e) => setDelay(e.target.value)}
            className="max-w-xs"
          />
          {error ? <Alert>{error}</Alert> : null}
          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" disabled={busy}>
              Salvar mensagem
            </Button>
            <Button type="button" variant="secondary" disabled={busy} onClick={() => void test()}>
              Enviar teste para mim
            </Button>
            {status ? (
              <span role="status" className="text-sm text-emerald-700">
                {status}
              </span>
            ) : null}
          </div>
        </form>
      )}
    </Section>
  );
}
