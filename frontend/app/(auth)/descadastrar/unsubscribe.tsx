"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Alert, Card, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";

export function Unsubscribe() {
  const token = useSearchParams().get("token");
  const [result, setResult] = useState<{ ok: boolean; message?: string } | null>(null);

  useEffect(() => {
    if (!token) return;
    api.GET("/api/v1/me/unsubscribe", { params: { query: { token } } }).then(({ data, error }) => {
      setResult(data ? { ok: true } : { ok: false, message: errorMessage(error) });
    });
  }, [token]);

  return (
    <Card>
      <h1 className="mb-4 text-xl font-semibold">Lembretes por e-mail</h1>
      {!token ? (
        <Alert>Link incompleto.</Alert>
      ) : !result ? (
        <Spinner />
      ) : result.ok ? (
        <div className="space-y-3">
          <Alert kind="success">Pronto! Você não vai mais receber lembretes de estudo por e-mail.</Alert>
          <p className="text-sm text-slate-600">
            Mudou de ideia? Reative quando quiser em{" "}
            <Link href="/perfil" className="text-indigo-700 hover:underline">
              Perfil
            </Link>
            .
          </p>
        </div>
      ) : (
        <Alert>{result.message}</Alert>
      )}
    </Card>
  );
}
