"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Alert, Card, Spinner } from "@/components/ui";
import { api, errorCode, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type State = { kind: "loading" } | { kind: "ok" } | { kind: "error"; message: string };

export function VerifyEmail() {
  const token = useSearchParams().get("token");
  const { status, reloadUser } = useAuth();
  const [state, setState] = useState<State>({ kind: "loading" });
  const sent = useRef(false); // o token é de uso único: evita a 2ª chamada do StrictMode

  useEffect(() => {
    if (!token || sent.current) return;
    sent.current = true;
    api.POST("/api/v1/auth/verify-email", { body: { token } }).then(({ response, error }) => {
      if (response.ok) setState({ kind: "ok" });
      else if (errorCode(error) === "token_already_used") setState({ kind: "ok" });
      else setState({ kind: "error", message: errorMessage(error) });
    });
  }, [token]);

  useEffect(() => {
    if (state.kind === "ok" && status === "authenticated") void reloadUser();
  }, [state.kind, status, reloadUser]);

  return (
    <Card>
      <h1 className="mb-4 text-xl font-semibold">Confirmar e-mail</h1>
      {!token ? (
        <Alert>Link incompleto. Abra o link exatamente como chegou no seu e-mail.</Alert>
      ) : state.kind === "loading" ? (
        <Spinner label="Confirmando..." />
      ) : state.kind === "ok" ? (
        <div className="space-y-4">
          <Alert kind="success">E-mail confirmado! Agora você já pode enviar redações.</Alert>
          <Link
            href={status === "authenticated" ? "/painel" : "/entrar"}
            className="block text-center text-indigo-700 hover:underline"
          >
            {status === "authenticated" ? "Ir para o painel" : "Entrar"}
          </Link>
        </div>
      ) : (
        <Alert>
          {state.message} Você pode pedir um novo link no aviso que aparece no topo do painel.
        </Alert>
      )}
    </Card>
  );
}
