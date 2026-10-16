"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Alert, Button, Card, TextField } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const CONFIRMATION = "EXCLUIR";

export function DeleteAccount() {
  const router = useRouter();
  const { clearSession } = useAuth();
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onDelete() {
    setBusy(true);
    setError(null);
    const { response, error: apiError } = await api.DELETE("/api/v1/me");
    if (!response.ok) {
      setBusy(false);
      setError(errorMessage(apiError));
      return;
    }
    clearSession();
    router.replace("/entrar");
  }

  return (
    <Card className="border-red-200">
      <h2 className="mb-2 text-lg font-semibold text-red-700">Excluir conta</h2>
      <p className="mb-4 text-sm text-slate-600">
        Apaga permanentemente sua conta, suas redações (com as fotos), respostas, favoritos e
        cronogramas. Não dá para desfazer.
      </p>
      <div className="space-y-3">
        {error ? <Alert>{error}</Alert> : null}
        <TextField
          label={`Digite ${CONFIRMATION} para confirmar`}
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          autoComplete="off"
        />
        <Button variant="danger" onClick={onDelete} disabled={busy || confirm !== CONFIRMATION}>
          {busy ? "Excluindo..." : "Excluir minha conta"}
        </Button>
      </div>
    </Card>
  );
}
