"use client";

import { useEffect, useState } from "react";

import { AdminHeader, EmptyState, Section, StatusBadge } from "@/components/admin/kit";
import { CopyButton } from "@/components/copy-button";
import { Alert, Button, Spinner, TextField } from "@/components/ui";
import { INVITE_STATUS, type Invite, ROLE_LABEL, dateTime } from "@/lib/admin";
import { api, errorMessage } from "@/lib/api";

const selectCls = "block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 shadow-sm";

export function InvitesAdmin() {
  const [invites, setInvites] = useState<Invite[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [role, setRole] = useState<"student" | "teacher">("student");
  const [note, setNote] = useState("");
  const [maxUses, setMaxUses] = useState("");
  const [days, setDays] = useState("30");
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<Invite | null>(null);

  function load() {
    return api.GET("/api/v1/admin/invites").then(({ data, error: e }) => {
      if (data) setInvites(data);
      else setError(errorMessage(e));
    });
  }

  useEffect(() => {
    void load();
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError(null);
    const { data, error: err } = await api.POST("/api/v1/admin/invites", {
      body: {
        role,
        note: note.trim() || null,
        max_uses: maxUses ? Number(maxUses) : null,
        expires_in_days: days ? Number(days) : null,
      },
    });
    setCreating(false);
    if (!data) {
      setError(errorMessage(err));
      return;
    }
    setCreated(data);
    setNote("");
    setMaxUses("");
    await load();
  }

  async function revoke(invite: Invite) {
    if (!window.confirm("Revogar este convite? Quem ainda não se cadastrou não vai conseguir usar o link.")) return;
    const { error: err } = await api.POST("/api/v1/admin/invites/{invite_id}/revoke", {
      params: { path: { invite_id: invite.id } },
    });
    if (err) setError(errorMessage(err));
    await load();
  }

  return (
    <div className="max-w-4xl space-y-6">
      <AdminHeader
        title="Convites"
        description="O cadastro é fechado: só entra quem abre um link de convite. O convite define se a conta é de aluno ou de professor."
      />
      {error ? <Alert>{error}</Alert> : null}

      <Section title="Novo convite">
        <form onSubmit={create} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="invite-role" className="mb-1 block text-sm font-medium text-slate-700">
                Tipo de conta
              </label>
              <select
                id="invite-role"
                className={selectCls}
                value={role}
                onChange={(e) => setRole(e.target.value as "student" | "teacher")}
              >
                <option value="student">Aluno</option>
                <option value="teacher">Professor</option>
              </select>
            </div>
            <TextField
              label="Para quem é (opcional)"
              value={note}
              maxLength={200}
              onChange={(e) => setNote(e.target.value)}
              hint="Ex.: Turma 3º A, Prof.ª Carla. Só você vê."
            />
            <TextField
              label="Limite de cadastros"
              type="number"
              min={1}
              inputMode="numeric"
              value={maxUses}
              onChange={(e) => setMaxUses(e.target.value)}
              hint="Em branco: sem limite. Use 1 para um convite individual."
            />
            <TextField
              label="Vale por quantos dias"
              type="number"
              min={1}
              max={365}
              inputMode="numeric"
              value={days}
              onChange={(e) => setDays(e.target.value)}
              hint="Em branco: não vence."
            />
          </div>
          <Button type="submit" disabled={creating}>
            {creating ? "Gerando..." : "Gerar link"}
          </Button>
        </form>
        {created ? (
          <div className="mt-4 space-y-2 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
            <p className="text-sm font-medium text-emerald-900">
              Link de {ROLE_LABEL[created.role].toLowerCase()} criado. Envie para quem vai se cadastrar:
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <code className="min-w-0 flex-1 break-all rounded bg-white px-2 py-1.5 text-sm">{created.url}</code>
              <CopyButton text={created.url} />
            </div>
          </div>
        ) : null}
      </Section>

      <Section title="Convites gerados">
        {!invites ? (
          <Spinner />
        ) : invites.length === 0 ? (
          <EmptyState>Nenhum convite ainda.</EmptyState>
        ) : (
          <ul className="divide-y divide-slate-100">
            {invites.map((inv) => {
              const status = INVITE_STATUS[inv.status];
              return (
                <li key={inv.id} className="flex flex-wrap items-center gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-slate-900">
                      {ROLE_LABEL[inv.role]}
                      {inv.note ? <span className="font-normal text-slate-600">· {inv.note}</span> : null}
                      <StatusBadge level={status.level}>{status.label}</StatusBadge>
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {inv.uses} cadastro(s){inv.max_uses ? ` de ${inv.max_uses}` : ""} · criado em{" "}
                      {dateTime(inv.created_at)}
                      {inv.expires_at ? ` · vence em ${dateTime(inv.expires_at)}` : " · não vence"}
                    </p>
                  </div>
                  {inv.status === "active" ? (
                    <div className="flex gap-2">
                      <CopyButton text={inv.url} />
                      <Button variant="ghost" onClick={() => void revoke(inv)}>
                        Revogar
                      </Button>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </Section>
    </div>
  );
}
