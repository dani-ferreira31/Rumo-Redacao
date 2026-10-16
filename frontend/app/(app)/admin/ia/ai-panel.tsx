"use client";

import { ExternalLink, KeyRound, PlugZap, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AdminHeader, EmptyState, Section, StatusBadge } from "@/components/admin/kit";
import { QuotaSection } from "@/components/admin/quota-section";
import { Alert, Button, Spinner, TextField } from "@/components/ui";
import {
  type AITask,
  type Calibration,
  type ModelOption,
  type PriceRow,
  type Provider,
  type ProvidersReport,
  dateTime,
  relativeTime,
} from "@/lib/admin";
import { api, errorMessage } from "@/lib/api";

const EFFORT_LABEL: Record<string, string> = {
  none: "Nenhum",
  minimal: "Mínimo",
  low: "Baixo",
  medium: "Médio",
  high: "Alto",
  xhigh: "Muito alto",
  max: "Máximo",
};

const selectCls = "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm";

export function AIPanel() {
  const [providers, setProviders] = useState<ProvidersReport | null>(null);
  const [tasks, setTasks] = useState<AITask[] | null>(null);
  const [calibrations, setCalibrations] = useState<Calibration[]>([]);
  const [models, setModels] = useState<Record<string, ModelOption[]>>({});
  const [error, setError] = useState<string | null>(null);

  const loadProviders = useCallback(async () => {
    const { data, error: e } = await api.GET("/api/v1/admin/ai/providers");
    if (data) setProviders(data);
    else setError(errorMessage(e));
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- carga inicial
    void loadProviders();
    api.GET("/api/v1/admin/ai/tasks").then(({ data }) => setTasks(data ?? null));
    api.GET("/api/v1/admin/ai/calibrations").then(({ data }) => setCalibrations(data ?? []));
  }, [loadProviders]);

  async function testProvider(id: string) {
    const { data, error: e } = await api.POST("/api/v1/admin/ai/providers/{provider}/test", {
      params: { path: { provider: id } },
    });
    if (data?.ok) setModels((prev) => ({ ...prev, [id]: data.models ?? [] }));
    await loadProviders();
    return data ?? { ok: false, error: errorMessage(e) };
  }

  return (
    <div className="space-y-6">
      <AdminHeader
        title="Inteligência artificial"
        description="Escolha o provedor e o modelo de cada tarefa e cadastre as chaves de API. As mudanças valem em poucos segundos, sem reiniciar o servidor."
      />
      {error ? <Alert>{error}</Alert> : null}
      {providers && !providers.encryption_configured ? (
        <Alert kind="warning">
          Para salvar chaves pelo painel, defina <code>SETTINGS_ENCRYPTION_KEY</code> no <code>.env</code> do servidor
          (veja o README) e reinicie. Enquanto isso, valem as chaves do <code>.env</code>.
        </Alert>
      ) : null}

      <QuotaSection />

      <Section title="Provedores e chaves" description="A chave fica criptografada no servidor e nunca é mostrada de novo.">
        {!providers ? (
          <Spinner />
        ) : (
          <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
            {providers.providers.map((p) => (
              <ProviderCard
                key={p.id}
                provider={p}
                canSave={providers.encryption_configured}
                onChanged={loadProviders}
                onTest={() => testProvider(p.id)}
              />
            ))}
          </div>
        )}
      </Section>

      <Section
        title="Modelo por tarefa"
        description="Use “Testar conexão” no provedor para carregar a lista de modelos, ou digite o ID do modelo."
      >
        {!tasks || !providers ? (
          <Spinner />
        ) : (
          <div className="space-y-4">
            {tasks.map((t) => (
              <TaskCard
                key={t.task}
                task={t}
                providers={providers.providers}
                models={models}
                calibrations={calibrations}
                onLoadModels={testProvider}
                onSaved={setTasks}
              />
            ))}
          </div>
        )}
      </Section>

      <PricesSection />

      <Section
        title="Calibrações"
        description={
          <>
            Comparação das notas da IA com notas humanas (Essay-BR). Rode{" "}
            <code className="text-xs">python -m scripts.eval_grading --n 50 --yes</code> no servidor antes de trocar o modelo de correção.
          </>
        }
      >
        {calibrations.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                  <th className="py-2 pr-3 font-medium">Modelo</th>
                  <th className="py-2 pr-3 text-right font-medium">Redações</th>
                  <th className="py-2 pr-3 text-right font-medium">QWK total</th>
                  <th className="py-2 pr-3 text-right font-medium">±80 pontos</th>
                  <th className="py-2 pr-3 text-right font-medium">Erro médio</th>
                  <th className="py-2 text-right font-medium">Quando</th>
                </tr>
              </thead>
              <tbody>
                {calibrations.map((c) => (
                  <tr key={`${c.provider}/${c.model}`} className="border-b border-slate-100 last:border-0">
                    <td className="py-2 pr-3">
                      <span className="font-medium">{c.model}</span>
                      <span className="block text-xs text-slate-500">
                        {c.provider} · prompt {c.prompt_version}
                      </span>
                    </td>
                    <td className="py-2 pr-3 text-right tabular-nums">{c.ok}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{c.total_qwk ?? "—"}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{c.total_within !== null && c.total_within !== undefined ? `${c.total_within}%` : "—"}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{c.total_mae ?? "—"}</td>
                    <td className="py-2 text-right text-slate-500">{dateTime(c.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState>Nenhuma calibração encontrada em reports/.</EmptyState>
        )}
      </Section>
    </div>
  );
}

// ---- provedor ---------------------------------------------------------------------

function ProviderCard({
  provider: p,
  canSave,
  onChanged,
  onTest,
}: {
  provider: Provider;
  canSave: boolean;
  onChanged: () => Promise<void>;
  onTest: () => Promise<{ ok: boolean; error?: string | null }>;
}) {
  const [editing, setEditing] = useState(false);
  const [key, setKey] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "error" | "success"; text: string } | null>(null);
  const isFake = p.id === "fake";

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    const { error } = await api.PUT("/api/v1/admin/ai/providers/{provider}/key", {
      params: { path: { provider: p.id } },
      body: { api_key: key, password },
    });
    setBusy(false);
    if (error) {
      setMessage({ kind: "error", text: errorMessage(error) });
      return;
    }
    setKey("");
    setPassword("");
    setEditing(false);
    setMessage({ kind: "success", text: "Chave salva. Teste a conexão para confirmar." });
    await onChanged();
  }

  async function test() {
    setBusy(true);
    setMessage(null);
    const result = await onTest();
    setBusy(false);
    setMessage(
      result.ok
        ? { kind: "success", text: "Conexão OK. A lista de modelos foi carregada." }
        : { kind: "error", text: result.error ?? "Falhou." },
    );
  }

  async function remove() {
    setBusy(true);
    await api.DELETE("/api/v1/admin/ai/providers/{provider}/key", { params: { path: { provider: p.id } } });
    setBusy(false);
    setMessage(null);
    await onChanged();
  }

  const status = isFake ? (
    <StatusBadge level="ok">Disponível</StatusBadge>
  ) : !p.key_source ? (
    <StatusBadge level="warning">Sem chave</StatusBadge>
  ) : p.last_test_ok === false ? (
    <StatusBadge level="error">Teste falhou</StatusBadge>
  ) : p.last_test_ok ? (
    <StatusBadge level="ok">Testada</StatusBadge>
  ) : (
    <StatusBadge level="warning">Não testada</StatusBadge>
  );

  return (
    <div className="flex flex-col rounded-lg border border-slate-200 p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-medium text-slate-900">{p.label}</p>
          {!isFake ? (
            <p className="mt-0.5 text-sm text-slate-500">
              {p.key_source === "panel"
                ? `Chave do painel: ${p.key_hint}`
                : p.key_source === "env"
                  ? `Chave do .env: ${p.key_hint}`
                  : "Nenhuma chave cadastrada"}
            </p>
          ) : (
            <p className="mt-0.5 text-sm text-slate-500">Respostas de exemplo, só para desenvolvimento.</p>
          )}
          {p.last_test_at ? <p className="text-xs text-slate-400">Testada {relativeTime(p.last_test_at)}</p> : null}
        </div>
        {status}
      </div>

      {message ? (
        <p className={`mt-3 break-words text-sm ${message.kind === "error" ? "text-red-700" : "text-emerald-700"}`} role="status">
          {message.text}
        </p>
      ) : null}

      {editing ? (
        <form onSubmit={save} className="mt-3 space-y-3">
          <TextField
            label="Chave de API"
            type="password"
            autoComplete="off"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            required
            minLength={8}
          />
          <TextField
            label="Sua senha de admin (confirmação)"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <div className="flex gap-2">
            <Button type="submit" disabled={busy}>
              {busy ? "Salvando..." : "Salvar chave"}
            </Button>
            <Button type="button" variant="secondary" onClick={() => setEditing(false)}>
              Cancelar
            </Button>
          </div>
        </form>
      ) : (
        <div className="mt-auto flex flex-wrap gap-2 pt-4">
          {!isFake ? (
            <Button variant="secondary" className="px-3 py-1.5" disabled={!canSave} onClick={() => setEditing(true)}>
              <KeyRound aria-hidden className="mr-1.5 h-4 w-4" />
              {p.key_source === "panel" ? "Trocar chave" : "Cadastrar chave"}
            </Button>
          ) : null}
          <Button variant="secondary" className="px-3 py-1.5" disabled={busy || (!isFake && !p.key_source)} onClick={() => void test()}>
            <PlugZap aria-hidden className="mr-1.5 h-4 w-4" />
            {busy ? "Testando..." : "Testar conexão"}
          </Button>
          {p.key_source === "panel" ? (
            <Button variant="ghost" className="px-3 py-1.5 text-red-700" disabled={busy} onClick={() => void remove()}>
              <Trash2 aria-hidden className="mr-1.5 h-4 w-4" />
              Remover
            </Button>
          ) : null}
          {p.key_url ? (
            <a href={p.key_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 self-center text-sm text-indigo-700 hover:underline">
              Onde pegar a chave <ExternalLink aria-hidden className="h-3.5 w-3.5" />
            </a>
          ) : null}
        </div>
      )}
    </div>
  );
}

// ---- tarefa -----------------------------------------------------------------------

function TaskCard({
  task,
  providers,
  models,
  calibrations,
  onLoadModels,
  onSaved,
}: {
  task: AITask;
  providers: Provider[];
  models: Record<string, ModelOption[]>;
  calibrations: Calibration[];
  onLoadModels: (provider: string) => Promise<unknown>;
  onSaved: (tasks: AITask[]) => void;
}) {
  const [provider, setProvider] = useState(task.provider);
  const [model, setModel] = useState(task.model);
  const [effort, setEffort] = useState(task.effort ?? "");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "error" | "success"; text: string } | null>(null);

  const meta = providers.find((p) => p.id === provider);
  const options = models[provider] ?? [];
  const changed = provider !== task.provider || model !== task.model || (effort || null) !== (task.effort ?? null);
  const listId = `models-${task.task}`;
  const calibration = calibrations.find((c) => c.provider === provider && c.model === model);
  const noKey = meta && meta.id !== "fake" && !meta.key_source;

  async function save() {
    setBusy(true);
    const { data, error } = await api.PUT("/api/v1/admin/ai/tasks/{task}", {
      params: { path: { task: task.task } },
      body: { provider, model, effort: effort || null },
    });
    setBusy(false);
    if (data) {
      onSaved(data);
      setMessage({ kind: "success", text: "Salvo. Vale para os próximos trabalhos." });
    } else setMessage({ kind: "error", text: errorMessage(error) });
  }

  async function reset() {
    setBusy(true);
    const { data } = await api.DELETE("/api/v1/admin/ai/tasks/{task}", { params: { path: { task: task.task } } });
    setBusy(false);
    if (data) {
      onSaved(data);
      const fresh = data.find((t) => t.task === task.task);
      if (fresh) {
        setProvider(fresh.provider);
        setModel(fresh.model);
        setEffort(fresh.effort ?? "");
      }
      setMessage({ kind: "success", text: "Voltou ao padrão do servidor (.env)." });
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium text-slate-900">{task.label}</p>
          <p className="text-sm text-slate-500">{task.hint}</p>
        </div>
        <span className="text-xs text-slate-500">
          {task.source === "panel" ? "Definido no painel" : "Padrão do servidor (.env)"}
        </span>
      </div>
      <div className="grid gap-3 md:grid-cols-[12rem_minmax(0,1fr)_10rem]">
        <label className="text-sm">
          <span className="mb-1 block font-medium text-slate-700">Provedor</span>
          <select
            className={selectCls}
            value={provider}
            onChange={(e) => {
              setProvider(e.target.value);
              setModel(e.target.value === "fake" ? "fake" : "");
              setEffort("");
            }}
          >
            {providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
        <label className="min-w-0 text-sm">
          <span className="mb-1 flex items-center justify-between font-medium text-slate-700">
            Modelo
            {provider !== "fake" && !noKey ? (
              <button type="button" className="text-xs font-normal text-indigo-700 hover:underline" onClick={() => void onLoadModels(provider)}>
                {options.length ? "Recarregar lista" : "Carregar lista"}
              </button>
            ) : null}
          </span>
          <input
            className={selectCls}
            list={listId}
            value={model}
            placeholder="ID do modelo"
            onChange={(e) => setModel(e.target.value)}
          />
          <datalist id={listId}>
            {options.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name ?? m.id}
              </option>
            ))}
          </datalist>
        </label>
        <label className="text-sm">
          <span className="mb-1 block font-medium text-slate-700">Raciocínio</span>
          <select className={selectCls} value={effort} disabled={!meta?.efforts.length} onChange={(e) => setEffort(e.target.value)}>
            <option value="">Padrão do modelo</option>
            {meta?.efforts.map((e) => (
              <option key={e} value={e}>
                {EFFORT_LABEL[e] ?? e}
              </option>
            ))}
          </select>
        </label>
      </div>

      {noKey ? (
        <p className="mt-3 text-sm text-amber-800">Este provedor ainda não tem chave: os trabalhos vão falhar até você cadastrar uma.</p>
      ) : null}
      {task.task === "grading" && changed && provider !== "fake" ? (
        <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {calibration
            ? `Última calibração deste modelo: QWK ${calibration.total_qwk ?? "—"}, ${calibration.total_within ?? "—"}% das notas a até 80 pontos da nota humana.`
            : "Este modelo ainda não foi calibrado. As notas podem mudar bastante: rode a calibração antes de trocar em produção."}
        </p>
      ) : null}
      {message ? (
        <p className={`mt-3 text-sm ${message.kind === "error" ? "text-red-700" : "text-emerald-700"}`} role="status">
          {message.text}
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        <Button disabled={busy || !changed || !model.trim()} onClick={() => void save()}>
          Salvar
        </Button>
        {task.source === "panel" ? (
          <Button variant="ghost" disabled={busy} onClick={() => void reset()}>
            Voltar ao padrão do servidor
          </Button>
        ) : null}
      </div>
    </div>
  );
}

// ---- preços -----------------------------------------------------------------------

function PricesSection() {
  const [rows, setRows] = useState<PriceRow[] | null>(null);
  const [newModel, setNewModel] = useState("");
  const [message, setMessage] = useState<{ kind: "error" | "success"; text: string } | null>(null);

  useEffect(() => {
    api.GET("/api/v1/admin/ai/prices").then(({ data }) => setRows(data ?? []));
  }, []);

  function update(model: string, field: keyof PriceRow, value: string) {
    setRows((prev) =>
      prev?.map((r) => (r.model === model ? { ...r, [field]: value === "" ? null : Number(value.replace(",", ".")) } : r)) ?? prev,
    );
  }

  async function save() {
    if (!rows) return;
    const { data, error } = await api.PUT("/api/v1/admin/ai/prices", { body: { prices: rows } });
    if (data) {
      setRows(data);
      setMessage({ kind: "success", text: "Preços salvos. Valem para as próximas chamadas." });
    } else setMessage({ kind: "error", text: errorMessage(error) });
  }

  return (
    <section id="precos" className="scroll-mt-6">
      <Section
        title="Tabela de preços"
        description="US$ por 1 milhão de tokens. Usada para estimar os custos; confira os valores na página de preços de cada provedor."
        actions={
          <Button variant="secondary" onClick={() => void save()} disabled={!rows}>
            Salvar preços
          </Button>
        }
      >
        {!rows ? (
          <Spinner />
        ) : (
          <>
            {message ? (
              <p className={`mb-3 text-sm ${message.kind === "error" ? "text-red-700" : "text-emerald-700"}`} role="status">
                {message.text}
              </p>
            ) : null}
            <div className="overflow-x-auto">
              <table className="w-full min-w-[40rem] text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                    <th className="py-2 pr-3 font-medium">Modelo</th>
                    <th className="py-2 pr-3 font-medium">Entrada</th>
                    <th className="py-2 pr-3 font-medium">Saída</th>
                    <th className="py-2 pr-3 font-medium">Leitura de cache</th>
                    <th className="py-2 font-medium">Escrita de cache</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.model} className="border-b border-slate-100 last:border-0">
                      <td className="py-2 pr-3">
                        <span className="font-medium">{r.model}</span>
                        {r.source === "missing" ? (
                          <span className="block text-xs text-amber-700">sem preço: custo desconhecido</span>
                        ) : r.source === "default" ? (
                          <span className="block text-xs text-slate-400">valor padrão</span>
                        ) : null}
                      </td>
                      {(["input", "output", "cache_read", "cache_write"] as const).map((f) => (
                        <td key={f} className="py-2 pr-3">
                          <input
                            aria-label={`${r.model}: ${f}`}
                            type="number"
                            min={0}
                            step="any"
                            value={r[f] ?? ""}
                            onChange={(e) => update(r.model, f, e.target.value)}
                            className="w-24 rounded-md border border-slate-300 px-2 py-1 tabular-nums"
                          />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <form
              className="mt-4 flex flex-wrap items-end gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                const id = newModel.trim();
                if (!id || rows.some((r) => r.model === id)) return;
                setRows([...rows, { model: id, source: "missing" }]);
                setNewModel("");
              }}
            >
              <TextField label="Adicionar modelo" placeholder="ID do modelo" value={newModel} onChange={(e) => setNewModel(e.target.value)} />
              <Button type="submit" variant="secondary">
                Adicionar
              </Button>
            </form>
          </>
        )}
      </Section>
    </section>
  );
}
